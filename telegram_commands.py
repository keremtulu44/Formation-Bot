"""Telegram komut dinleyicisi — bot artık iki yönlü.

Bot, alarm göndermenin yanında `getUpdates` ile uzun yoklama (long polling)
yapıp **yalnızca `TELEGRAM_CHAT_ID`**'den gelen komutları yanıtlar. Tasarım
kararları ve gerekçeleri:

- **Yetki**: Başka bir sohbetten gelen mesajlar sessizce yok sayılır (loglanır,
  cevap verilmez). Böylece token'ı bilen biri botu kurcalayamaz.
- **Backlog atlama**: Açılışta eski komutlar çalıştırılmadan offset ile atlanır;
  sayfalar doğru onaylanır ve ilk taze update korunur. Geçici ağ hatasında
  backlog tamamlanana kadar normal polling başlamaz (fail-closed). Atlanan
  mesaj varsa kullanıcıya TEK bir bilgi mesajı gider ("bot uyanık değildi") —
  sessiz kaybolma, "komutlar çalışmıyor" şikâyetinin en büyük sebebiydi.
- **Geç teslim**: Webhook tekrarı ya da açılış nedeniyle 15 dakikadan eski bir
  komut gelirse durum değiştirenler (tara/panel) çalıştırılmaz; yalnızca okuma
  komutları (yardim/durum) gecikme notuyla yanıtlanır.
- **Teşhis**: `durum()` sayaçları `/health` alanına girer (islenen, yetkisiz,
  bayat, son komut yaşı) — "bot çalışıyor ama komut yok" farkı dışarıdan görünür.
- **Onay (offset)**: Komut cevabı dayanıklı outbox'a yazıldıktan sonra
  `offset = id + 1` ile onaylanır. Aynı süreçte yazma başarısızsa cevap bellekte
  tutulur ve update yeniden denenir; restart sonrası outbox'taki `update_id`
  kaydı handler'ın tekrar çalışmasını önler. `update_id` için küçük bir küme de
  tutulur (restart sonrası aynı komutun iki kez çalışmaması için).
- **409 Conflict**: Aynı token'la başka bir süreç de `getUpdates` yapıyorsa
  (örn. Termux'ta açık kalmış ikinci kopya) Telegram bu kodu döner. Dinleyici
  durur ve logda net söylenir — sonsuz hata döngüsüne girmez.
- **401**: Token geçersiz; dinleyici durur (tekrar denemek anlamsız).
- **Ağ hatası**: 5 → 60 sn üstel geri çekilme, sonra devam.
- **Analiz sürerken**: komut kuyruğa alınmaz (aynı anda tek iş) ama sessiz de
  kalınmaz; kısa bir "⏳ Analiz sürüyor" bilgi mesajı gider.
- **İşleyici hatası**: Kullanıcıya kısa bir hata mesajı gider, dinleyici devam eder.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

from secrets_redaction import redact_sensitive_text

logger = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org"
MAX_MESSAGE_LEN = 4000          # Telegram sınırı 4096; pay bırakıyoruz
MIN_KOMUT_ARALIK_SN = 1.0       # aynı sohbetten saniyede 1 komut
BACKLOG_SINIR_SN = 15 * 60      # açılışta bundan eski mesajlar yok sayılır

# Eski komutlar: bot uykudayken (Render Free 15 dk hareketsizlikte uyur) yazılan
# komutlar Telegram tarafından saatler sonra teslim edilebilir. Durum değiştiren
# komutlar (tara/panel) eski veriyle yanlış sonuç üretmesin diye ÇALIŞTIRILMAZ;
# yalnızca okuma amaçlı komutlar gecikmeli de olsa yanıtlanır — böylece kullanıcı
# "hiç cevap gelmedi" yerine "bot uyuyordu" bilgisini alır.
BAYAT_GUVENLI_KOMUTLAR = frozenset({"yardim", "help", "start", "durum"})


def kirp(text: str, sinir: int = MAX_MESSAGE_LEN) -> str:
    """Telegram mesaj sınırına sığdırır (kesildiğini de söyler)."""
    if len(text) <= sinir:
        return text
    return text[: sinir - 40].rstrip() + "\n\n… (mesaj sınırı nedeniyle kesildi)"


def komut_coz(text: str) -> Tuple[str, str]:
    """'/formasyonlar@bot 1h' -> ('formasyonlar', '1h'). Komut değilse ('', '')."""
    temiz = (text or "").strip()
    if not temiz.startswith("/"):
        return "", ""
    parcalar = temiz.split()
    komut = parcalar[0][1:].split("@")[0].strip().lower()
    arguman = " ".join(parcalar[1:]).strip()
    return komut, arguman


class TelegramCommandListener:
    """`getUpdates` uzun yoklaması + komut dağıtımı (daemon thread)."""

    def __init__(
        self,
        token: str,
        allowed_chat_id: str,
        handlers: Dict[str, Callable[[str], str]],
        help_text: str = "",
        session: Any = None,
        poll_timeout: int = 25,
        stop_event: Optional[threading.Event] = None,
        komutlari_yoksay: Optional[Callable[[], bool]] = None,
        response_sender: Optional[Callable[[int, str], bool]] = None,
        response_exists: Optional[Callable[[int], bool]] = None,
        bayat_sinir_sn: int = BACKLOG_SINIR_SN,
        bayat_bildirim: bool = True,
    ) -> None:
        self.token = (token or "").strip()
        self.allowed_chat_id = str(allowed_chat_id or "").strip()
        self.handlers = dict(handlers or {})
        self.help_text = help_text
        self.komutlari_yoksay = komutlari_yoksay
        self.response_sender = response_sender
        self.response_exists = response_exists
        self.poll_timeout = max(1, int(poll_timeout))
        self._session = session
        self._offset: Optional[int] = None
        self._gorulen: Dict[int, float] = {}
        self._pending_reply: Dict[int, str] = {}
        self._son_komut_zamani: Dict[str, float] = {}
        self._stop = stop_event or threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._backoff = 5.0
        # Teşhis sayaçları (/health'te görünür): "komutlar çalışmıyor" şikâyetinde
        # bot ayakta mı, komut geldi mi, yetkisiz sohbetten mi geldi, kaç komut
        # bayat diye atıldı — hepsi dışarıdan okunabilsin.
        self.bayat_sinir_sn = max(0, int(bayat_sinir_sn))
        self.bayat_bildirim = bool(bayat_bildirim)
        self._sayac = {"islenen": 0, "yetkisiz": 0, "bayat": 0, "hata": 0, "mesgul": 0}
        self._son_komut_adi: Optional[str] = None
        self._son_komut_ts: Optional[float] = None
        self._son_yetkisiz_chat = ""

    # --- yaşam döngüsü -------------------------------------------------
    @property
    def enabled(self) -> bool:
        return bool(self.token and self.allowed_chat_id)

    def start(self) -> bool:
        if not self.enabled:
            logger.warning("Telegram komut dinleyicisi kapalı (token veya chat_id yok)")
            return False
        if self._thread is not None and self._thread.is_alive():
            return True
        self._thread = threading.Thread(target=self.run_forever, name="telegram-commands", daemon=True)
        self._thread.start()
        logger.info("Telegram komut dinleyicisi başladı (/yardim ile komut listesi)")
        return True

    def stop(self) -> None:
        self._stop.set()

    @property
    def stopped(self) -> bool:
        return self._stop.is_set()

    # --- teşhis ---------------------------------------------------------
    @staticmethod
    def _maskele(kimlik: str) -> str:
        """Sohbet kimliğini loga/health'e tam yazmadan son 4 hanesiyle gösterir."""
        kimlik = str(kimlik or "")
        if not kimlik:
            return ""
        return ("…" + kimlik[-4:]) if len(kimlik) > 4 else "…"

    def durum(self) -> Dict[str, Any]:
        """Komut katmanının son hali (`/health` alanı).

        NEDEN: "DM'den hiçbir komut çalışmıyor ama /health tamam diyor" farkı
        ancak buradan görülür. Kişisel veri yazılmaz: son komutun ADI ve yaşı,
        sayaçlar ve maskelenmiş yetkisiz sohbet kimliği döner.
        """
        son = self._son_komut_ts
        return {
            "calisiyor": bool(self._thread is not None and self._thread.is_alive()),
            "son_komut": self._son_komut_adi,
            "son_komut_sn_once": None if son is None else int(max(0.0, time.time() - son)),
            "islenen": self._sayac["islenen"],
            "yetkisiz_sohbet": self._sayac["yetkisiz"],
            "bayat_atlanan": self._sayac["bayat"],
            "mesgul_atlanan": self._sayac["mesgul"],
            "isleyici_hatasi": self._sayac["hata"],
            "son_yetkisiz_sohbet": self._maskele(self._son_yetkisiz_chat),
        }

    def _bayat_uyarisi(self, komut: str, yas_sn: float) -> str:
        dk = int(max(0.0, yas_sn) // 60)
        return (f"🕓 /{komut} yaklaşık {dk} dk önce gönderilmişti; bot bu sırada "
                "uykudaydı/kapalıydı (servis 15 dk hareketsizlikte uyur).")

    # --- HTTP ----------------------------------------------------------
    def _session_obj(self):
        if self._session is None:
            import requests

            self._session = requests.Session()
        return self._session

    def _api(self, method: str, params: Optional[dict] = None, timeout: Optional[int] = None):
        url = f"{API_BASE}/bot{self.token}/{method}"
        return self._session_obj().get(url, params=params or {}, timeout=timeout or (self.poll_timeout + 15))

    # --- ana döngü -----------------------------------------------------
    def run_forever(self) -> None:
        # Polling yalnızca backlog sınıflandırması BİTTİKTEN sonra başlar. Ağ
        # hatasında ilk sıradan yoklama süzülmemiş bir tekrar oynatmasın.
        while not self._stop.is_set():
            try:
                backlog_ready = self._backlog_atla()
            except Exception as exc:  # noqa: BLE001 - thread asla ölmemeli
                logger.warning(
                    "Telegram backlog yoklaması hata verdi: %s",
                    redact_sensitive_text(exc, self.token),
                )
                backlog_ready = False
            if isinstance(backlog_ready, str):
                logger.error(f"Telegram komut dinleyicisi durdu: {backlog_ready}")
                return
            if backlog_ready:
                self._backoff = 5.0
                break
            logger.warning(
                "Telegram backlog henüz güvenle sınıflandırılamadı; %.0f sn sonra tekrar",
                self._backoff,
            )
            self._stop.wait(self._backoff)
            self._backoff = min(self._backoff * 2, 60.0)

        while not self._stop.is_set():
            try:
                fatal = self.poll_once()
            except Exception as exc:  # noqa: BLE001 - thread asla ölmemeli
                logger.warning(
                    "Telegram komut yoklaması hata verdi: %s",
                    redact_sensitive_text(exc, self.token),
                )
                fatal = None
            if fatal:
                logger.error(f"Telegram komut dinleyicisi durdu: {fatal}")
                return
            if self._stop.is_set():
                return
        logger.info("Telegram komut dinleyicisi kapandı")

    def _backlog_atla(self, azami_tur: int = 20):
        """Açılıştaki BAYAT komutları atla, yeni komutları koru.

        Neden: servis gece uyuyabilir. Sabah açıldığında dün akşam yazılmış
        "/tara" yeniden çalışmamalı, ama 3 dakika önce yazılmış komut
        kaybolmamalı. Kural: `BACKLOG_SINIR_SN`'den (15 dk) eski mesajlar
        onaylanıp geçilir; ilk taze mesajdan itibaren normal yoklama devralır.
        Başarılı sınıflandırmada True, geçici hatada False döner. Geçici hata
        normal polling'i başlatmaz (fail-closed); aynı backlog offset'iyle geri
        çekilerek denenir. 401/409 fatal sayılır ve hata metni döner.
        """
        esik = time.time() - BACKLOG_SINIR_SN
        atlanan = 0
        for _ in range(azami_tur):
            params = {"timeout": 0, "limit": 100, "allowed_updates": '["message"]'}
            if self._offset is not None:
                params["offset"] = self._offset
            try:
                yanit = self._api("getUpdates", params, timeout=15)
            except Exception as exc:  # noqa: BLE001 - backlog tamamlanana dek fail-closed
                logger.debug(
                    "Backlog atlama yapılamadı: %s", redact_sensitive_text(exc, self.token)
                )
                return False

            kod = getattr(yanit, "status_code", 0)
            if kod == 401:
                return "HTTP 401 — TELEGRAM_BOT_TOKEN geçersiz (BotFather'dan yenileyin)"
            if kod == 409:
                return ("HTTP 409 — aynı token'ı başka bir süreç de dinliyor; "
                        "Termux/PC'de açık ikinci kopya varsa kapatın, aksi halde komutlar çalışmaz")
            if kod != 200:
                logger.warning("Telegram backlog getUpdates beklenmeyen yanıt: HTTP %s", kod)
                return False
            try:
                guncellemeler = (yanit.json() or {}).get("result") or []
            except (AttributeError, TypeError, ValueError):
                logger.warning("Telegram backlog getUpdates JSON çözümlenemedi")
                return False
            if not guncellemeler:
                self._bayat_ozetle(atlanan)
                return True

            taze_index = None
            for i, guncelleme in enumerate(guncellemeler):
                tarih = (guncelleme.get("message") or {}).get("date")
                if not isinstance(tarih, (int, float)) or float(tarih) >= esik:
                    taze_index = i
                    break

            if taze_index is not None:
                # offset, ilk taze update'in ID'siyle yalnız bayat öneki onaylanır;
                # Telegram bu update'i sonraki yoklamada yine getirir.
                try:
                    taze_id = int(guncellemeler[taze_index].get("update_id", 0))
                except (AttributeError, TypeError, ValueError):
                    return False
                if self._offset is None or taze_id > self._offset:
                    self._offset = taze_id
                self._bayat_ozetle(atlanan)
                return True

            # Partinin tamamı bayat: offset hemen ilerletilir ki sonraki sayfa ya
            # da geçici bir ağ hatası offset'i geri alamazsın.
            try:
                son_id = int(guncellemeler[-1].get("update_id", 0))
            except (AttributeError, TypeError, ValueError):
                return False
            yeni_offset = son_id + 1
            if self._offset is None or yeni_offset > self._offset:
                self._offset = yeni_offset
            atlanan += len(guncellemeler)

        logger.warning(
            "Telegram backlog atlama %s turda bitmedi; offset=%s",
            azami_tur, self._offset,
        )
        return False

    def _bayat_ozetle(self, atlanan: int) -> None:
        """Backlog turu özeti: teşhis sayacı + kullanıcının gördüğü TEK mesaj."""
        if not atlanan:
            logger.info("Telegram komut dinleyicisi: bekleyen mesaj yok")
            return
        self._sayac["bayat"] += atlanan
        logger.info(
            "Telegram komut dinleyicisi: %s bayat mesaj atlandı (offset=%s)",
            atlanan, self._offset,
        )
        # Sessiz kaybolmasın: kullanıcı "neden hiç cevap gelmedi?" diye
        # düşünmek yerine servisin uyuduğunu ve komutun yanıtlanmadığını görsün.
        if self.bayat_bildirim:
            self._cevapla(
                f"💤 Bot uyanık değildi: {atlanan} eski komut yanıtlanmadı "
                "(eskimiş /tara,/panel yanlış sonuç üretmesin diye çalıştırılmaz).\n"
                f"{int(BACKLOG_SINIR_SN // 60)} dakikadan eski mesajlar açılışta atlanır; "
                "güncel komutu yeniden gönderin."
            )

    def poll_once(self) -> Optional[str]:
        """Tek yoklama turu. Dönen değer: durdurma sebebi (yoksa None)."""
        params = {
            "timeout": self.poll_timeout,
            "limit": 20,
            "allowed_updates": '["message"]',
        }
        if self._offset is not None:
            params["offset"] = self._offset
        try:
            yanit = self._api("getUpdates", params)
        except Exception as exc:  # noqa: BLE001 - ağ hatası: geri çekilme
            logger.warning(
                "Telegram getUpdates ağ hatası (%s); %.0f sn sonra tekrar",
                redact_sensitive_text(exc, self.token), self._backoff,
            )
            self._stop.wait(self._backoff)
            self._backoff = min(self._backoff * 2, 60.0)
            return None

        kod = getattr(yanit, "status_code", 0)
        if kod == 401:
            return "HTTP 401 — TELEGRAM_BOT_TOKEN geçersiz (BotFather'dan yenileyin)"
        if kod == 409:
            return ("HTTP 409 — aynı token'ı başka bir süreç de dinliyor; "
                    "Termux/PC'de açık ikinci kopya varsa kapatın, aksi halde komutlar çalışmaz")
        if kod != 200:
            logger.warning(f"Telegram getUpdates beklenmeyen yanıt: HTTP {kod}")
            self._stop.wait(self._backoff)
            self._backoff = min(self._backoff * 2, 60.0)
            return None

        self._backoff = 5.0
        try:
            guncellemeler = (yanit.json() or {}).get("result") or []
        except ValueError:
            logger.warning("Telegram getUpdates: JSON çözümlenemedi")
            return None

        for guncelleme in guncellemeler:
            self._islenenleri_temizle()
            update_id = guncelleme.get("update_id") if isinstance(guncelleme, dict) else None
            try:
                self.handle_update(guncelleme)
            except Exception as exc:  # noqa: BLE001 - tek güncelleme döngüyü bozmasın
                logger.error(
                    "Telegram komutu işlenemedi: %s",
                    redact_sensitive_text(exc, self.token),
                )
            # Cevap outbox'a dayanıklı biçimde yazılamadıysa update ACK edilmez:
            # aynı süreçte saklanan cevap tekrar denenir, komut yan etkisi yeniden
            # çalıştırılmaz. Sonraki getUpdates turu aynı update_id'yi getirir.
            if isinstance(update_id, int) and update_id in self._pending_reply:
                break
            try:
                self._offset = int(update_id) + 1
            except (TypeError, ValueError):
                pass
        return None

    def update_waiting_for_delivery(self, update_id) -> bool:
        """Webhook/polling ACK'ini bekletmesi gereken, outbox'ta cevabi bekleyen update."""
        return isinstance(update_id, int) and update_id in self._pending_reply

    def _islenenleri_temizle(self) -> None:
        if len(self._gorulen) < 500:
            return
        su_an = time.time()
        self._gorulen = {k: v for k, v in self._gorulen.items() if su_an - v < 3600}

    # --- güncelleme işleme ---------------------------------------------
    def handle_update(self, update: Dict[str, Any]) -> Optional[str]:
        """Yetki + hız kontrolünden geçen komutu işler, cevabı gönderir/kuyruğa alır.

        Dönen değer test için cevap metnidir; dayanıklı cevap kuyruğa alınamazsa
        None döner ve polling/webhook katmanı update'i ACK etmez.
        """
        update_id = update.get("update_id") if isinstance(update, dict) else None
        if isinstance(update_id, int):
            if update_id in self._pending_reply:
                # Cevap bellekte bekliyor: handler YENİDEN çalıştırılmaz, yalnız
                # teslim denenir.
                return self._cevapla(self._pending_reply[update_id], update_id)

            if self.response_exists is not None:
                try:
                    reply_exists = bool(self.response_exists(update_id))
                except Exception as exc:  # noqa: BLE001 - kaynağı teşhis et, handler devam eder
                    logger.warning(
                        "Komut cevap kaydı sorgulanamadı: %s",
                        redact_sensitive_text(exc, self.token, self.allowed_chat_id),
                    )
                    reply_exists = False
                if reply_exists:
                    # Restart sonrası: cevap outbox'ta kayıtlı, komut tekrar çalışmaz.
                    self._gorulen[update_id] = time.time()
                    self._cevapla("", update_id)
                    return None

            if update_id in self._gorulen:
                logger.debug("Telegram update %s zaten işlenmişti, atlandı", update_id)
                return None
            self._gorulen[update_id] = time.time()

        mesaj = update.get("message") or update.get("edited_message") or {}
        sohbet_id = str(((mesaj.get("chat") or {}).get("id")) or "")
        metin = mesaj.get("text")

        if str(sohbet_id) != self.allowed_chat_id:
            # Sayaç + maskeli kimlik: "DM'imden yazıyorum ama cevap yok" durumunun
            # en sık sebebi, gelen sohbetin TELEGRAM_CHAT_ID ile eşleşmemesidir.
            # Kimlik tam yazılmaz (kişisel veri), son 4 hane yeterli.
            self._sayac["yetkisiz"] += 1
            self._son_yetkisiz_chat = sohbet_id
            logger.warning(
                "Telegram komutu yetkisiz sohbetten geldi (chat_id=%s, tip=%s, beklenen=%s) — yok sayıldı",
                self._maskele(sohbet_id) or "?",
                (mesaj.get("chat") or {}).get("type") or "?",
                self._maskele(self.allowed_chat_id) or "?",
            )
            return None
        if not metin:
            return None

        komut, arguman = komut_coz(metin)
        if not komut:
            # GRUPLARDA sohbete karışılmaz: admin bot tüm mesajları görür, ama
            # yalnız komutlara cevap verir. (Eskiden komut olmayan HER metne
            # /yardim basılıyordu; grup sohbetinde bot spam'i olurdu.)
            sohbet_tipi = str((mesaj.get("chat") or {}).get("type") or "").lower()
            if sohbet_tipi and sohbet_tipi != "private":
                logger.debug("Grup sohbetinde komut olmayan mesaj yok sayıldı (chat_id=%s)",
                             self._maskele(sohbet_id) or "?")
                return None
            return self._cevapla(self.help_text or "Komut listesi için /yardim yazın.", update_id)

        # Geç teslim edilen komut (bot uykudayken yazıldı; webhook tekrarı ya da
        # açılış) → durum değiştiren komutlar çalıştırılmaz, okuma komutları
        # gecikme notuyla yanıtlanır. Aksi halde dünkü "/tara" bugün sessizce
        # çalışıp yanlış/geç sonuç üretebilirdi.
        yas_sn = self._mesaj_yasi_sn(mesaj)
        gecikme_notu = ""
        if yas_sn is not None and self.bayat_sinir_sn > 0 and yas_sn > self.bayat_sinir_sn:
            self._sayac["bayat"] += 1
            if komut not in BAYAT_GUVENLI_KOMUTLAR:
                logger.info("Telegram /%s: %.0f dk gecikmeli geldi, çalıştırılmadı",
                            komut, yas_sn / 60)
                return self._cevapla(
                    self._bayat_uyarisi(komut, yas_sn)
                    + " Eski komut yeniden çalıştırılmaz; güncel sonuç için şimdi tekrar gönderin.",
                    update_id,
                )
            gecikme_notu = self._bayat_uyarisi(komut, yas_sn) + " Yine de yanıtlanıyor.\n\n"

        # Uzun analiz sırasında komut iş kuyruğuna KONMAZ (aynı anda tek iş) ama
        # sessiz de kalınmaz: kullanıcı "komut çalışmıyor" sanmasın diye kısa bir
        # bilgi mesajı gider. Aynı kontrol webhook ve getUpdates yollarında çalışır.
        try:
            mesgul = bool(self.komutlari_yoksay is not None and self.komutlari_yoksay())
        except Exception as exc:
            logger.warning(
                "Telegram komut meşguliyet kontrolü başarısız: %s",
                redact_sensitive_text(exc, self.token, self.allowed_chat_id),
            )
            mesgul = False
        if mesgul:
            self._sayac["mesgul"] += 1
            logger.info(f"Telegram /{komut}: analiz sürerken yok sayıldı (bilgi mesajı gönderildi)")
            return self._cevapla(
                f"\u23f3 Analiz sürüyor; /{komut} şu an çalıştırılmadı (aynı anda tek iş çalışır).\n"
                "Sonuç bitince bu sohbete gelecek — sonra komutu yeniden gönderin.",
                update_id,
            )

        simdi = time.monotonic()
        son = self._son_komut_zamani.get(komut, 0.0)
        if simdi - son < MIN_KOMUT_ARALIK_SN:
            logger.info("Telegram komutu çok sık geldi (/%s) — yok sayıldı", komut)
            return None
        self._son_komut_zamani[komut] = simdi

        isleyici = self.handlers.get(komut)
        if isleyici is None:
            return self._cevapla(
                f"Bilinmeyen komut: /{komut}\n\n" + (self.help_text or "Komut listesi için /yardim yazın."),
                update_id,
            )

        # Argüman loglanmaz: komut adı teşhis için yeterli, sohbet kimliği/argüman
        # loga sızmamalı.
        logger.info("Telegram komutu: /%s", komut)
        try:
            cevap = isleyici(arguman)
        except Exception as exc:  # noqa: BLE001 - kullanıcıya sade, maskelenmiş hata
            safe_error = redact_sensitive_text(exc, self.token, self.allowed_chat_id)
            logger.error("/%s işleyicisi hata verdi: %s", komut, safe_error, exc_info=True)
            self._sayac["hata"] += 1
            cevap = f"\u274c /{komut} çalıştırılamadı: {safe_error[:200]}"
        if not cevap:
            return None
        self._sayac["islenen"] += 1
        self._son_komut_adi = komut
        self._son_komut_ts = time.time()
        return self._cevapla(gecikme_notu + cevap, update_id)

    @staticmethod
    def _mesaj_yasi_sn(mesaj: Dict[str, Any]) -> Optional[float]:
        """Mesajın yaşı (saniye); `date` yoksa/geçersizse None.

        Telegram `date` alanı sunucu tarafında üretilir; istemci saati güvenilmez.
        """
        tarih = mesaj.get("date")
        if not isinstance(tarih, (int, float)):
            return None
        return max(0.0, time.time() - float(tarih))

    def _cevapla(self, text: str, update_id=None) -> Optional[str]:
        # Kırpma ÖNCESİ redakte et: Telegram boyur sınırında bölünen bir sır
        # bire-bir eşleştirmeden kaçabilirdi.
        govde = kirp(redact_sensitive_text(str(text), self.token))
        if self.response_sender is not None and isinstance(update_id, int):
            try:
                queued = bool(self.response_sender(update_id, govde))
            except Exception as exc:  # noqa: BLE001 - cevap dayanıklı olana dek ACK etme
                logger.warning(
                    "Telegram cevap outbox'ı hata verdi: %s",
                    redact_sensitive_text(exc, self.token, self.allowed_chat_id),
                )
                queued = False
            if queued:
                self._pending_reply.pop(update_id, None)
                return govde
            self._pending_reply[update_id] = govde
            logger.error("Telegram update %s cevabı dayanıklı kuyruğa yazılamadı", update_id)
            return None

        try:
            yanit = self._session_obj().post(
                f"{API_BASE}/bot{self.token}/sendMessage",
                json={"chat_id": self.allowed_chat_id, "text": govde, "disable_web_page_preview": True},
                timeout=20,
            )
            if getattr(yanit, "status_code", 0) != 200:
                logger.warning(
                    "Telegram cevabı gönderilemedi: HTTP %s",
                    getattr(yanit, "status_code", "?"),
                )
                if isinstance(update_id, int):
                    self._pending_reply[update_id] = govde
                return None
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Telegram cevabı gönderilemedi: %s",
                redact_sensitive_text(exc, self.token, self.allowed_chat_id),
            )
            if isinstance(update_id, int):
                self._pending_reply[update_id] = govde
            return None
        if isinstance(update_id, int):
            self._pending_reply.pop(update_id, None)
        return govde
