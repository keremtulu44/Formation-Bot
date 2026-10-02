"""Telegram komut dinleyicisi — bot artık iki yönlü.

Bot, alarm göndermenin yanında `getUpdates` ile uzun yoklama (long polling)
yapıp **yalnızca `TELEGRAM_CHAT_ID`**'den gelen komutları yanıtlar. Tasarım
kararları ve gerekçeleri:

- **Yetki**: Başka bir sohbetten gelen mesajlar sessizce yok sayılır (loglanır,
  cevap verilmez). Böylece token'ı bilen biri botu kurcalayamaz.
- **Backlog atlama**: Açılışta eski mesajlar TÜKETİLMEZ, atlanır. Aksi halde
  servis 3 gün uyuduktan sonra dünkü "/tara" komutu yeniden çalışırdı.
- **Onay (offset)**: Her güncelleme işlendikten hemen sonra `offset = id + 1`
  ile onaylanır; `update_id` için küçük bir küme tutulur (restart sonrası aynı
  komutun iki kez çalışmaması için).
- **409 Conflict**: Aynı token'la başka bir süreç de `getUpdates` yapıyorsa
  (örn. Termux'ta açık kalmış ikinci kopya) Telegram bu kodu döner. Dinleyici
  durur ve logda net söylenir — sonsuz hata döngüsüne girmez.
- **401**: Token geçersiz; dinleyici durur (tekrar denemek anlamsız).
- **Ağ hatası**: 5 → 60 sn üstel geri çekilme, sonra devam.
- **İşleyici hatası**: Kullanıcıya kısa bir hata mesajı gider, dinleyici devam eder.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org"
MAX_MESSAGE_LEN = 4000          # Telegram sınırı 4096; pay bırakıyoruz
MIN_KOMUT_ARALIK_SN = 1.0       # aynı sohbetten saniyede 1 komut
BACKLOG_SINIR_SN = 15 * 60      # açılışta bundan eski mesajlar yok sayılır


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
    ) -> None:
        self.token = (token or "").strip()
        self.allowed_chat_id = str(allowed_chat_id or "").strip()
        self.handlers = dict(handlers or {})
        self.help_text = help_text
        self.komutlari_yoksay = komutlari_yoksay
        self.poll_timeout = max(1, int(poll_timeout))
        self._session = session
        self._offset: Optional[int] = None
        self._gorulen: Dict[int, float] = {}
        self._son_komut_zamani: Dict[str, float] = {}
        self._stop = stop_event or threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._backoff = 5.0

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
        self._backlog_atla()
        while not self._stop.is_set():
            try:
                fatal = self.poll_once()
            except Exception as exc:  # noqa: BLE001 - thread asla ölmemeli
                logger.warning(f"Telegram komut yoklaması hata verdi: {exc}")
                fatal = None
            if fatal:
                logger.error(f"Telegram komut dinleyicisi durdu: {fatal}")
                return
            if self._stop.is_set():
                return
        logger.info("Telegram komut dinleyicisi kapandı")

    def _backlog_atla(self, azami_tur: int = 20) -> None:
        """Açılıştaki BAYAT komutları atla, yeni komutları koru.

        Neden: servis gece uyuyabilir. Sabah açıldığında dün akşam yazılmış
        "/tara" yeniden çalışmamalı, ama 3 dakika önce yazılmış komut
        kaybolmamalı. Kural: `BACKLOG_SINIR_SN`'den (15 dk) eski mesajlar
        onaylanıp geçilir; ilk taze mesajdan itibaren normal yoklama devralır.
        """
        esik = time.time() - BACKLOG_SINIR_SN
        offset = self._offset
        atlanan = 0
        for _ in range(azami_tur):
            params = {"timeout": 0, "limit": 100, "allowed_updates": '["message"]'}
            if offset is not None:
                params["offset"] = offset
            try:
                yanit = self._api("getUpdates", params, timeout=15)
            except Exception as exc:  # noqa: BLE001 - açılışta önemsiz
                logger.debug(f"Backlog atlama yapılamadı: {exc}")
                return
            if getattr(yanit, "status_code", 0) != 200:
                return
            try:
                guncellemeler = (yanit.json() or {}).get("result") or []
            except ValueError:
                return
            if not guncellemeler:
                break

            taze_index = None
            for i, guncelleme in enumerate(guncellemeler):
                tarih = (guncelleme.get("message") or {}).get("date")
                if not isinstance(tarih, (int, float)) or float(tarih) >= esik:
                    taze_index = i
                    break

            if taze_index is None:
                # Partinin tamamı bayat: onayla, sonraki partiyi iste.
                son_id = int(guncellemeler[-1].get("update_id", 0))
                atlanan += len(guncellemeler)
                offset = son_id + 1
                continue

            # İlk taze mesajdan itibaren normal akış (bu mesaj tüketilmez).
            self._offset = int(guncellemeler[taze_index].get("update_id", 0))
            break
        else:
            self._offset = offset
            logger.warning(f"Telegram backlog atlama {azami_tur} turda bitmedi; offset={self._offset}")
            return

        if atlanan:
            if offset is not None:
                self._offset = offset
            logger.info(f"Telegram komut dinleyicisi: {atlanan} bayat mesaj atlandı (offset={self._offset})")
        else:
            logger.info("Telegram komut dinleyicisi: bekleyen mesaj yok")

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
            logger.warning(f"Telegram getUpdates ağ hatası ({exc}); {self._backoff:.0f} sn sonra tekrar")
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
            try:
                self.handle_update(guncelleme)
            except Exception as exc:  # noqa: BLE001 - tek güncelleme döngüyü bozmasın
                logger.error(f"Telegram komutu işlenemedi: {exc}", exc_info=True)
            finally:
                try:
                    self._offset = int(guncelleme.get("update_id", 0)) + 1
                except (TypeError, ValueError):
                    pass
        return None

    def _islenenleri_temizle(self) -> None:
        if len(self._gorulen) < 500:
            return
        su_an = time.time()
        self._gorulen = {k: v for k, v in self._gorulen.items() if su_an - v < 3600}

    # --- güncelleme işleme ---------------------------------------------
    def handle_update(self, update: Dict[str, Any]) -> Optional[str]:
        """Yetki + hız kontrolünden geçen komutu işler, cevabı gönderir.

        Dönen değer: gönderilen cevap metni (test edilebilirlik için) ya da None.
        """
        update_id = update.get("update_id")
        if isinstance(update_id, int):
            if update_id in self._gorulen:
                logger.debug(f"Telegram update {update_id} zaten işlenmişti, atlandı")
                return None
            self._gorulen[update_id] = time.time()

        mesaj = update.get("message") or update.get("edited_message") or {}
        sohbet_id = str(((mesaj.get("chat") or {}).get("id")) or "")
        metin = mesaj.get("text")

        if str(sohbet_id) != self.allowed_chat_id:
            logger.warning(
                f"Telegram komutu yetkisiz sohbetten geldi (chat_id={sohbet_id or '?'}) — yok sayıldı"
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
                             sohbet_id or "?")
                return None
            return self._cevapla(self.help_text or "Komut listesi için /yardim yazın.")

        # Uzun analiz sırasında komut update'i tüketilir ama cevap verilmez ve
        # iş kuyruğuna konmaz. Aynı kontrol webhook ve getUpdates yollarında çalışır.
        try:
            if self.komutlari_yoksay is not None and self.komutlari_yoksay():
                logger.info(f"Telegram /{komut}: analiz sürerken sessizce yok sayıldı")
                return None
        except Exception as exc:
            logger.warning(f"Telegram komut meşguliyet kontrolü başarısız: {exc}")

        simdi = time.monotonic()
        son = self._son_komut_zamani.get(komut, 0.0)
        if simdi - son < MIN_KOMUT_ARALIK_SN:
            logger.info(f"Telegram komutu çok sık geldi (/={komut}) — yok sayıldı")
            return None
        self._son_komut_zamani[komut] = simdi

        isleyici = self.handlers.get(komut)
        if isleyici is None:
            return self._cevapla(
                f"Bilinmeyen komut: /{komut}\n\n" + (self.help_text or "Komut listesi için /yardim yazın.")
            )

        logger.info(f"Telegram komutu: /{komut} {arguman}".rstrip())
        try:
            cevap = isleyici(arguman)
        except Exception as exc:  # noqa: BLE001 - kullanıcıya sade hata
            logger.error(f"/{komut} işleyicisi hata verdi: {exc}", exc_info=True)
            cevap = f"❌ /{komut} çalıştırılamadı: {str(exc)[:200]}"
        if not cevap:
            return None
        return self._cevapla(cevap)

    def _cevapla(self, text: str) -> Optional[str]:
        govde = kirp(text)
        try:
            yanit = self._session_obj().post(
                f"{API_BASE}/bot{self.token}/sendMessage",
                json={"chat_id": self.allowed_chat_id, "text": govde, "disable_web_page_preview": True},
                timeout=20,
            )
            if getattr(yanit, "status_code", 0) != 200:
                logger.warning(f"Telegram cevabı gönderilemedi: HTTP {getattr(yanit, 'status_code', '?')}")
                return None
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Telegram cevabı gönderilemedi: {exc}")
            return None
        return govde
