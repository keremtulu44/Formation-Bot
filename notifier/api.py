# notifier/api.py — TelegramNotifier sınıfı (Faz 1: sınıf BÜTÜN taşındı).
# `DATA_DIR` / `ACIL_KUYRUK_TTL_DK` yamalanabilir yüzey; `_pkg` üzerinden
# çağrı anında okunur (plan §3).

import logging
import notifier as _pkg  # yamalı adlar için geç bağlama (plan §3)

import os
import re
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from config import (ACTIVE_STOCKS, DATA_DIR, ISTANBUL_TZ, TELEGRAM_MAX_MESAJ_SAAT,
                    TELEGRAM_MAX_MESAJ_GUN,
                    TELEGRAM_ALERT_STYLE, TELEGRAM_ALERT_MAX_KARAKTER, TELEGRAM_SATIR_PX,
                    TELEGRAM_KART_SUZGEC,
                    TELEGRAM_DM_DEGISIM_KAPISI, TELEGRAM_KANAL_GECERSIZ_KAPISI,
                    ACIL_KUYRUK_LIMIT, ACIL_KUYRUK_TTL_DK, ALERT_STATES, WATCH_STATES,
                    TERMINAL_TAZE_BAR,
                    ALERT_MIN_QUALITY, ALERT_MIN_QUALITY_GLOBAL,
                    PUBLIC_MAX_MESAJ_SAAT, PUBLIC_MAX_MESAJ_GUN, PUBLIC_MIN_ARALIK_SN,
                    PUBLIC_MIN_QUALITY_TF, PUBLIC_MIN_DEVLAMLILIK, DM_MIN_DEVLAMLILIK,
                    DEVLAMLILIK_AKTIF)
# Telefon satır bütçesi ölçeri (bağımlılıksız, PIL yok). Eski "satır ≤ 70 karakter"
# kuralı Türkçe/rakam genişliklerini hesaba katmadığı için 25 Eyl akışında 120
# satır telefonda sarmalanmıştı; artık piksel bütçesi kullanılıyor.
from telegram_measure import (SATIR_BUTCE, bol as _satir_bol,
                              genislik, genislik as _satir_px, metni_sigdir)
# Watch adaylarının state'ini Türkçe basmak için TEK KAYNAK sözlük (reporting
# katmanı da aynısını kullanır; böylece alarm mesajı ile /panel aynı dili konuşur).
from reporting.format import STATE_TR, sayi as _format_sayi
# Devamlılık puanı ARTIK KARTTA YOK (§11–§12): 0–100 puan tek bayraktan iyi
# çıkmadı, ondan türeyen "yüksek/normal/zayıf" etiketi de ölçümün taşımadığı bir
# hükümdü. Puan yalnız log/sıralama/gölge kayıt içinde yaşıyor. Geometri
# (confidence_score) artık yalnız bildirim eşiğini besler, kartta okunmaz.
# Ölçüm: docs/arastirma/FAZLA_ANALIZI_2026-10-25.md, PUANLAMA_MIMARISI_2026-10-25.md
import devamlilik as _dev
# Günlük public durumu (bütçe sayaçları + gönderilememiş kuyruk) restart'ta
# korunsun diye kalıcılık katmanı kullanılır (canlı denetim: ikisi de kayboluyordu).
from state import persistence as _state_persistence

from secrets_redaction import redact_sensitive_text


logger = logging.getLogger("notifier")  # eski kayıt adıyla aynı

from notifier.util import (
    CONFIRMED_PUBLIC_STATES,
    KRITIK_STATELER,
    PATTERN_EMOJI,
    PUBLIC_STATE_ETIKET,
    TF_EVENT_HUMAN,
    TF_HUMAN,
    TF_KISA,
    _AY_KISALTMALARI,
    _ENGEL_SAYACLAR,
    _FORMATION_ALERT_MUHR_TTL_SAAT,
    _KART_AYLAR,
    _KART_MAKS_SATIR,
    _KART_OLAY,
    _KART_OLAY_KISA,
    _KART_UST_TF,
    _KART_UST_TF_SOZ,
    _KART_YON,
    _PUBLIC_MAX_METIN,
    _TF_BAR_SAAT,
    _dm_anahtar,
    _dm_imza,
    _env_temizle,
    _evren_ozeti,
    _format_price,
    _format_price_tl,
    _grafik_basligi,
    _grafik_dipnotu,
    _grafik_salteri_acik,
    _istanbul,
    _kirp,
    _kuyruk_verisi,
    _muhur_ttl_saat,
    _px_butce,
    _satir,
    _sayı,
    _summary_int,
    _tr_tarih,
    _yon_kisa,
    _yon_metni,
    _yuzde,
    telegram_hata_ipucu,
    token_bicimi_uygun_mu,
)
from notifier.format_kart import (
    _format_lifecycle_alert,
    _format_lifecycle_alert_kart,
    _format_lifecycle_alert_kart_sade,
    _format_lifecycle_alert_klasik,
    _kart_bant,
    _kart_daralma,
    _kart_esik,
    _kart_esik_px,
    _kart_mum_damgasi,
    _kart_sigan,
    _kart_suzgec_aktif,
    _kart_temas,
    _kart_yas_metni,
    _quality_grade,
    devamlilik_puani,
    quality_comment,
    quality_emoji,
)
from notifier.format_summary import (
    _public_izleme_adaylari,
    _summary_last_full_scan,
    _summary_lifecycle_counts,
)
class TelegramNotifier:
    def __init__(self, persistent_store=None, initial_store_data=None):
        self.persistent_store = persistent_store
        self.initial_store_data = initial_store_data if isinstance(initial_store_data, dict) else {}
        self.token = _env_temizle(os.environ.get("TELEGRAM_BOT_TOKEN", ""))
        self.chat_id = _env_temizle(os.environ.get("TELEGRAM_CHAT_ID", ""))
        # Public hedef: grup (tercih) ya da eski kanal ayarı. Grup, DM'den BAĞIMSIZ
        # çalışır; DM kapalıyken de grup yayını sürer.
        self.group_id = _env_temizle(os.environ.get("TELEGRAM_GROUP_ID", ""))
        self.channel_id = _env_temizle(os.environ.get("TELEGRAM_CHANNEL_ID", ""))
        self.public_chat_id = self.group_id or self.channel_id
        self.cooldown_hours = 4
        self.last_sent: Dict[str, datetime] = {}
        self.max_saatlik = TELEGRAM_MAX_MESAJ_SAAT
        self.max_gunluk = TELEGRAM_MAX_MESAJ_GUN
        self._saatlik_zamanlar: List[datetime] = []
        # Gönderilemeyen alarmların SEBEP sayaçları (gün içi, gün değişiminde sıfırlanır).
        # Neden: can_send False döndüğünde olay hiçbir yerde görünmüyordu; kullanıcı
        # "kaç tanesi bastırıldı" sorusunun cevabını /durum'da görebilmeli.
        self.engeller = dict(_ENGEL_SAYACLAR)
        # DM içerik kapısı durumu: anahtar -> {"imza","kapanis","gün"}
        self._dm_imzalar: Dict[str, Dict] = {}
        self._dm_imza_lck = threading.Lock()
        # --- içerik kopyası kapısı (2026-10-23) ---
        # Mühür `formation_id` ile tekilleşir; motor aynı kurulumu her taramada
        # YENİ kimlikle üretirse kimlik değişir ve mühür tutmaz → ALARK 4s üç
        # kez, KCHOL 2s üç kez birebir aynı kart basıldı (kullanıcı bildirimi).
        # Bu kapı kimliğe değil KARTIN KENDİSİNE bakar: aynı hisse+TF+state
        # için birebir aynı metin TTL içinde ikinci kez gönderilmez. Fiyat/
        # kapanış/kalite değişirse metin değişir → gerçekten yeni olay geçer.
        self._kart_imzalar: Dict[str, Dict] = {}
        self._kart_imza_lck = threading.Lock()
        self.gonderim_hatasi = 0
        self.gonderilen_alarm = 0
        # Son can_send çağrısının engel sebebi (None = engel yok). Çağıran taraf
        # "gönderilemedi" durumunu bundan ayırt eder (kuyruk için gerekli).
        self._son_engel = None
        # --- gönderim sağlığı (heartbeat) ---
        # "Yaşıyor ama hiçbir şey gönderemiyor" durumu dışarıdan görünmeli.
        self.son_basarili_gonderim = None   # ISO (İstanbul)
        self.son_gonderme_hatasi = None     # son hata metni
        self.kanal_hatasi = 0               # public kanal gönderim hatası
        self.retry_bekleme_sn = 1.0         # testlerde 0'a çekilir
        self._gunluk_sayac = 0
        # Gün/saat sınırları İstanbul'a göre (naive now() UTC sunucuda 03:00 sıfırlaması yapıyordu).
        self._gunluk_tarih = datetime.now(ISTANBUL_TZ).date()
        self._kap_uyarildi = False
        # C4: dosyalar doğrudan DATA_DIR'e (eskiden DATA_DIR'ın ebeveyni + "bot_data"
        # sabitleniyordu; DATA_DIR repo dışına çıkınca yol tutarsız kalıyordu).
        self._cooldown_dosya = os.path.join(_pkg.DATA_DIR, "telegram_soguma.json")
        self._kap_dosya = os.path.join(os.path.dirname(self._cooldown_dosya), "telegram_kap.json")
        self._cooldown_yukle()
        self._kap_yukle()
        # --- engellenen acil olay kuyruğu (Batch 5 / B4) ---
        # Neden: cooldown/kap yüzünden gönderilemeyen teyitli olaylar kaybolmasın.
        # Engel digest saatinden önce kalkarsa gönderilir; kapanıştan sonra kalanlar
        # ayrı push yapılmaz, 18:45 DM özetine eklenir (main loop zaman kapısı).
        # Live alerts now use a durable, event-locked text+album FIFO.
        from notification_delivery import DeliveryOutbox
        self._delivery = DeliveryOutbox(self, _pkg.DATA_DIR)
        self._grafik_kuyruk: List[dict] = []
        self._grafik_gonderim_lck = threading.Lock()
        self._acil_kuyruk: List[dict] = []  # en eski kayıt önce
        self._kuyruk_dosya = os.path.join(os.path.dirname(self._cooldown_dosya),
                                          "telegram_acil_kuyruk.json")
        self.kuyruk_gonderildi = 0
        self.kuyruk_zaman_asimi = 0
        self.kuyruk_tasmasi = 0
        self._kuyruk_yukle()
        # Legacy picture-only adapters remain for explicit command/test callers.
        # They are not the live alert delivery path; that is self._delivery.
        self._grafik_lck = threading.Lock()
        self._son_grafik_ts = None
        self._grafik_supuruldu = False   # bayat dosya süpürmesi süreçte bir kez
        self.grafik_gonderilen = 0
        self.grafik_atlanan_hata = 0
        self.grafik_atlanan_kota = 0
        self.grafik_atlanan_baglam = 0   # „bağlam değişmedi" güncellemesi → kare yok
        self.grafik_olay = 0             # grafik açıkken gönderilmiş alarm kartı
        self.grafik_olay_karesiz = 0     # açıkken köprüden kare alamayan alarm kartı
        self.grafik_kopru_hata = 0
        self.grafik_son_neden = None
        self.grafik_toplam_ms = 0
        self.grafik_kare_sayisi = 0
        # --- tek-seferlik olay hafızası (repeat-guard) ---
        # Neden: motor tam_yeniden=True ile pencereyi her taramada baştan oynatır;
        # terminal/acil state'ler her tur yeniden üretilir ve eski tek koruma
        # (4 saatlik zaman cooldown'ı) dolunca AYNI olay tekrar basılıyordu
        # (örn. 4h TF'de 1 bar = 4 saat = cooldown süresi).
        # Mühür (hisse+TF+state) başına son bildirilen İstanbul GÜNÜNÜ tutar:
        # aynı gün içinde aynı olay bir kez bildirilir; state ilerlemesi
        # (TEYITLI -> RETEST -> TAMAMLANDI) serbest kalır; yeni gün tekrar
        # haberdar. Slot sıfırlama (flicker) mühürü silmez. Kalıcıdır:
        # Supabase "state:telegram_son_alerts" + disk (eski düz-string biçimi
        # açılışta yeni biçime taşınır).
        self._son_alert: Dict[str, dict] = {}
        self._son_alert_dosya = os.path.join(_pkg.DATA_DIR, "telegram_son_alerts.json")
        self._son_alert_yukle()

        try:
            from config import PUBLIC_MIN_QUALITY, PUBLIC_STATES, PUBLIC_SIKISMA_MIN_CONTRACTION
            self.public_min_quality = PUBLIC_MIN_QUALITY
            # Public anlık bildirim de yalnızca kapanışla doğrulanan olayları
            # alır; eski/env kaynaklı attempt/fail/wait/complete state'leri
            # public kuyruğa yanlışlıkla taşınamaz.
            self.public_states = set(PUBLIC_STATES) & CONFIRMED_PUBLIC_STATES
            self.public_sikisma_min = PUBLIC_SIKISMA_MIN_CONTRACTION
        except Exception:
            self.public_min_quality = 0
            self.public_states = set(CONFIRMED_PUBLIC_STATES)
            self.public_sikisma_min = 0.80
        # TF bazlı public eşik: DM alarm eşikleriyle AYNI (tek kaynak ALERT_MIN_QUALITY);
        # `public_min_quality` sıfırdan büyükse ek taban olarak uygulanır.
        try:
            self.public_min_quality_tf = {str(k).lower(): float(v)
                                          for k, v in dict(PUBLIC_MIN_QUALITY_TF).items()}
        except Exception:
            self.public_min_quality_tf = dict(ALERT_MIN_QUALITY)

        # --- PUBLIC (grup) kuyruğu: olaylar tarama turu boyunca toplanır, tur
        # sonunda TEK bülten olarak gönderilir (mum kapanışında 9 ayrı mesaj
        # yerine 1 mesaj). Bütçe DM'den ayrıdır: grup için saatte/günde sınır.
        self._public_kuyruk: List[dict] = []
        self._public_alert_markers: Dict[str, str] = {}
        self._public_lck = threading.Lock()
        self._public_saatlik: List[datetime] = []
        self._public_gun_sayac = 0
        self._public_gun = datetime.now(ISTANBUL_TZ).date()
        self._son_public_ts = None
        self.public_max_saatlik = PUBLIC_MAX_MESAJ_SAAT
        self.public_max_gunluk = PUBLIC_MAX_MESAJ_GUN
        self.public_min_aralik_sn = PUBLIC_MIN_ARALIK_SN
        self.public_kuyruk_limit = 40
        # Public kare defteri: {olay anahtarı: grafik_verisi}. Kuyruk kaydına
        # GİRMEZ (dosya yolu/PIL nesnesi JSON'a yazılmaz); yeniden başlatmada
        # kare kaybolur, metin kalır — görsel metnin eki, sahibi değil.
        self._public_grafik: Dict[str, dict] = {}
        self.public_gonderilen = 0
        self.public_hatasi = 0
        self.public_engel = 0
        self.public_kuyruk_tasmasi = 0
        self.son_public_gonderim = None
        # Public görsel sayaçları: metinden AYRI. Eski kod `yol` alanı olmayan
        # kareleri sessizce atlıyordu; "0 kare" durumu buradan görünür olmalı.
        self.public_grafik_gonderilen = 0
        self.public_grafik_hatasi = 0

        self.public_enabled = bool(self.token and self.public_chat_id)
        # GÖREV 6 (A10): Telegram sayaç ayrımı — alert/watch/digest/command
        # Mevcut alert/watch/digest/command ayrımını bozmayacak şekilde eklenir.
        # send_text() içeriğine göre kategorize edilir; mevcut çağrı noktaları değişmeden çalışır.
        self.command_sayac = 0        # /durum, /ozet, /karne gibi komut yanıtları
        self.digest_sayac = 0         # 18:45 digest (WATCH_STATES) — not: bu ayrı bir mekanizma,
        # ancak notifier üzerinden gönderilen digest parçaları için sayılır.
        self.alert_sayac = 0          # ALERT_STATES (anlık push) — mevcut _gunluk_sayac ile paralel
        # Kanal hedefi doğrulamasının önbelleği (main açılışta bir kez doldurur;
        # heartbeat ağa çıkmadan bunu okur).
        self.public_hedef_bilgi: Dict = {}
        # Restart gün sürekliliği: bütçe sayaçları ve gönderilememiş kuyruk
        # (canlı denetimde ölçüldü: restart'ta ikisi de sıfırlanıyordu -> günlük
        # tavan aşılabiliyor ve bültendeki olaylar sessizce kayboluyordu).
        self._public_durum_yukle()
        if not self.token:
            logger.warning("Telegram token env'de yok - notifier pasif (test modu)")
            self.enabled = False
        elif not self.chat_id:
            # DM kapalı ama public hedef tanımlı: grup yayını DM olmadan çalışır.
            logger.info("TELEGRAM_CHAT_ID yok: DM kapalı, public hedef (%s) yayında",
                        self.public_chat_id or "-")
            self.enabled = False
        else:
            if self.public_enabled:
                logger.info(f"Telegram public hedef aktif: {self.public_chat_id} (DM + public)")
            if not token_bicimi_uygun_mu(self.token):
                logger.warning("Telegram token biçimi uygun değil (beklenen 123456789:AA...). Kontrol et.")
            self.enabled = True
            logger.info("Telegram notifier aktif - insanlaştırma V2 + kanal")

    def _gonderim_sagligi_kaydet(self, basari: bool, hata: str = "") -> None:
        """Son başarılı/başarısız gönderimi işaretle (heartbeat ve /durum okur).

        Neden: token yanlış/eksikken veya ağ sürekli hata veriyorken bot
        "çalışıyor" görünüyordu; dışarıdan "hiç mesaj gitmiyor" durumu
        görülemiyordu.
        """
        if basari:
            self.son_basarili_gonderim = datetime.now(ISTANBUL_TZ).isoformat()
        else:
            self.gonderim_hatasi += 1
            self.son_gonderme_hatasi = str(hata or "bilinmeyen hata")[:200]

    def send_text(self, text: str, deneme: int = 2):
        """Düz metin gönderir (özet, komut yanıtı, /test).

        - Telegram'ın 4096 karakter sınırına karşı metin `kirp()` ile kısaltılır;
          eskiden uzun bir özet sessizce HTTP 400 alabiliyordu.
        - Geçici hatada (ağ hatası, 5xx, 429) bir kez daha denenir; 4xx kalıcı
          hatalar (403 engel, 400 bozuk istek) tekrar denenmez.
        """
        if not self.enabled:
            return False, "Telegram notifier pasif (token/chat_id env'de yok)"

        from telegram_commands import kirp  # döngüsel import yok: telegram_commands notifier'ı import etmez
        # Satır bütçesi burada, tek noktadan: özetler, sistem uyarıları, /test ve
        # karne aynı yolu kullanıyor ve 300-600 px'lık satırlarla telefonda
        # dağılıyordu. Alarm yolu (``_gonder``) burada DEĞİL: kart satırlarını
        # kendi üretirken bütçeliyor, klasik stil ise eski haliyle kalmalı.
        govde = kirp(metni_sigdir(text, guvenlik=1.0))
        deneme = max(1, int(deneme))
        son_hata = ""
        for i in range(deneme):
            try:
                import requests
                resp = requests.post(
                    f"https://api.telegram.org/bot{self.token}/sendMessage",
                    json={"chat_id": self.chat_id, "text": govde},
                    timeout=15,
                )
                if resp.status_code == 200:
                    self._gonderim_sagligi_kaydet(basari=True)
                    # GÖREV 6 (A10): Telegram sayaç ayrımı — içerik tabanlı kategorize
                    # Mevcut alert/watch/digest/command ayrımını bozmaz; sadece sayaçları ayırır.
                    # Heuristik: mesaj içeriğine göre kategori belirlenir.
                    metin_kucuk = (govde or "").lower()
                    if "📊" in metin_kucuk or "📋" in metin_kucuk or "📈" in metin_kucuk or "haftalık" in metin_kucuk:
                        self.digest_sayac += 1  # Digest / WATCH_STATES (18:45 özet)
                    elif "/durum" in metin_kucuk or "/ozet" in metin_kucuk or "/karne" in metin_kucuk or "/yardim" in metin_kucuk:
                        self.command_sayac += 1  # Komut yanıtı
                    elif any(x in metin_kucuk for x in ["formasyon", "üçgen", "kema", "bayrak", "flama", "kırılım", "retest", "tamamlanma"]):
                        self.alert_sayac += 1  # ALERT_STATES (anlık formasyon bildirimi)
                    else:
                        # Diğer mesajlar (genel duyuru, hata, vb.) mevcut alert sayacına eklenir
                        # (mevcut davranış korunur)
                        pass
                    # Ana günlük/saatlik sayaç (mevcut budget) alert için korunur;
                    # diğer kategoriler ayrı sayaçta takip edilir.
                    return True, "mesaj gonderildi"
                # Önce maskele, sonra kırp: ipucu metni ham yanıtın kesitini taşıyor;
                # token 200. karakterden sonra başlıyorsa kırpma secret'ı korumazdı.
                ipucu = telegram_hata_ipucu(resp.status_code,
                                             redact_sensitive_text(resp.text, self.token))
                son_hata = (f"HTTP {resp.status_code}: "
                            f"{redact_sensitive_text(resp.text, self.token)[:200]} | {ipucu}")
                if 400 <= resp.status_code < 500 and resp.status_code != 429:
                    break  # kalıcı hata: tekrar denemek anlamsız
                logger.warning(f"Telegram gönderimi başarısız (deneme {i + 1}/{deneme}): HTTP {resp.status_code}")
            except Exception as e:
                son_hata = f"istek hatasi: {e}"[:200]
                logger.warning(f"Telegram gönderim hatası (deneme {i + 1}/{deneme}): {e}")
            if i + 1 < deneme and self.retry_bekleme_sn > 0:
                time.sleep(self.retry_bekleme_sn)
        self._gonderim_sagligi_kaydet(basari=False, hata=son_hata)
        return False, son_hata

    def check_connection(self) -> bool:
        if not self.enabled:
            return False
        try:
            import requests
            resp = requests.get(
                f"https://api.telegram.org/bot{self.token}/getMe", timeout=10
            )
            if resp.status_code == 200:
                username = (resp.json().get("result") or {}).get("username", "?")
                logger.info(f"Telegram bağlantısı OK (bot: @{username}, chat_id: {self.chat_id})")
                return True
            ipucu = telegram_hata_ipucu(resp.status_code,
                                                 redact_sensitive_text(resp.text, self.token))
            logger.error("Telegram token/chat_id reddedildi: HTTP %s %s | %s",
                         resp.status_code, redact_sensitive_text(resp.text, self.token)[:200], ipucu)
        except Exception as e:
            logger.error(f"Telegram bağlantı hatası (token yanlış olabilir): {e}")
        return False

    def check_public_connection(self) -> Dict:
        """Public hedefi (kanal/grup) açılışta doğrular ve önbelleğe alır.

        NEDEN: canlıdaki en olası hata "bot kanalda yönetici değil / mesaj
        gönderme izni kapalı". Bu durumda her gönderim 403 döner ve kullanıcı
        sebebi ancak loglara bakınca anlar. Açılışta tek isteklerle kontrol
        edilir, sonuç heartbeat'e yazılır (`public_hedef`).
        Döner: {"hedef","baslik","tip","yonetici","can_post","hata"} (ağ hatası
        botu durdurmaz, hata alanına yazılır).
        """
        bilgi: Dict = {"hedef": self.public_chat_id, "baslik": None, "tip": None,
                       "yonetici": None, "can_post": None, "hata": ""}
        if not self.public_enabled:
            bilgi["hata"] = "public hedef tanımlı değil"
            self.public_hedef_bilgi = bilgi
            return bilgi
        try:
            import requests
            temel = f"https://api.telegram.org/bot{self.token}"

            def _cagri(method, **params):
                yanit = requests.post(f"{temel}/{method}", json=params, timeout=10)
                veri = yanit.json() if yanit.status_code == 200 else {}
                return veri.get("result") if veri.get("ok") else None, yanit

            ben, _ = _cagri("getMe")
            sohbet, yanit = _cagri("getChat", chat_id=self.public_chat_id)
            if sohbet is None:
                ipucu = telegram_hata_ipucu(yanit.status_code,
                                     redact_sensitive_text(getattr(yanit, "text", ""), self.token))
                bilgi["hata"] = f"getChat başarısız ({getattr(yanit, 'status_code', '?')}) {ipucu}"
                logger.error(
                    "❌ Public hedef doğrulanamadı (%s): %s. Kanal/grup kimliğini ve botun "
                    "hedefe eklenmiş olduğunu kontrol et.", self.public_chat_id, bilgi["hata"])
                self.public_hedef_bilgi = bilgi
                return bilgi
            bilgi["baslik"] = sohbet.get("title") or sohbet.get("username")
            bilgi["tip"] = sohbet.get("type")
            uye, _ = _cagri("getChatMember", chat_id=self.public_chat_id,
                            user_id=(ben or {}).get("id"))
            durum = str((uye or {}).get("status") or "")
            bilgi["yonetici"] = durum in ("administrator", "creator")
            # Kanallarda 'can_post_messages' alanı; gruplarda yokluğu "serbest" demek.
            bilgi["can_post"] = bool((uye or {}).get("can_post_messages")) or (
                bilgi["tip"] != "channel" and bilgi["yonetici"])
            if bilgi["tip"] == "channel" and not bilgi["can_post"]:
                logger.error(
                    "❌ Public hedef '%s' bir KANAL ve bot yönetici değil ya da 'Mesaj "
                    "gönderme' izni kapalı. Kanal → Yöneticiler → bot → Mesaj gönderme.",
                    bilgi["baslik"])
            else:
                logger.info("✅ Public hedef doğrulandı: %s (%s) · yönetici=%s · mesaj gönderme=%s",
                            bilgi["baslik"], bilgi["tip"], bilgi["yonetici"], bilgi["can_post"])
        except Exception as exc:  # noqa: BLE001 - ağ hatası botu durdurmaz
            bilgi["hata"] = f"{type(exc).__name__}: {exc}"
            logger.warning("Public hedef doğrulanamadı (ağ): %s", bilgi["hata"])
        self.public_hedef_bilgi = bilgi
        return bilgi

    def should_send_to_public(self, data: Dict) -> bool:
        """Public kanala gönderilsin mi? (DM'den bağımsız filtre)

        Kural bugün iki koşula bakar: state `PUBLIC_STATES` içinde olacak ve
        kalite `PUBLIC_MIN_QUALITY` üstünde olacak.

        NOT: Eskiden burada `SIKISMA_GUCLENIYOR` için "daralma >= eşik ise
        gönderilebilir" gibi görünen bir dal vardı ama iki yolda da `False`
        dönüyordu (ölü kod). Kanal davranışı KİMSENİN onayı olmadan
        değiştirilmesin diye dal kaldırıldı: sıkışma adaylarını kanalda görmek
        istersen `PUBLIC_STATES` env'ine `SIKISMA_GUCLENIYOR` ekle (günlük
        özetteki daralma eşiği `PUBLIC_SIKISMA_MIN_CONTRACTION` ayrıca geçerli).
        """
        state = data.get('state', '')
        quality = data.get('confidence_score', 0)
        if state not in CONFIRMED_PUBLIC_STATES or state not in self.public_states:
            return False
        # GERİ ALMA KALİTE KAPISINA TAKILMAZ (2026-10-22): teyit eşiği geçmiş bir
        # olayın "geçersizleşti" mesajı, formasyonun kalitesi sonradan eşiğin
        # altına indi diye düşürülüyordu → grupta sinyal sonsuza kadar "geçerli"
        # kalıyordu. Kalite kapısı yalnız YENİ iddialar (teyit/retest) içindir.
        if state == "KIRILIM_GECERSIZLESTI":
            return True
        # 2026-10-25: hacim musluğu artık devamlılık puanı. `PUBLIC_MIN_DEVLAMLILIK`
        # 0 iken davranış eskisiyle birebir aynı; >0 verilirse ek eleme puanla.
        # Geri alma ("geçersizleşti") bu kapıya takılmaz — yukarıda muaf.
        if PUBLIC_MIN_DEVLAMLILIK > 0:
            _p = devamlilik_puani(data)
            if _p is None or _p < PUBLIC_MIN_DEVLAMLILIK:
                return False
        try:
            q = float(quality or 0)
        except (TypeError, ValueError):
            return False
        tf = str(data.get('timeframe') or '').lower()
        esik = self.public_min_quality_tf.get(tf, ALERT_MIN_QUALITY_GLOBAL)
        try:
            esik = max(float(esik), float(self.public_min_quality or 0))
        except (TypeError, ValueError):
            pass
        return q >= esik

    # --- PUBLIC (grup) gönderim yolu ------------------------------------
    # DM yolundan tamamen bağımsızdır: kendi bütçesi, kendi sayaçları, kendi
    # hata durumu vardır. DM kapalıyken de çalışır.

    @staticmethod
    def _public_event_key(data: Dict) -> str:
        """Kalıcı public tekrar mührü: aynı formation/state ikinci bültene girmez."""
        formation_id = str(data.get("formation_id") or "").strip()
        if not formation_id:
            return ""
        stock = str(data.get("stock_name") or "").strip().upper()
        timeframe = str(data.get("timeframe") or "").strip().lower()
        state = str(data.get("state") or "").strip().upper()
        if not stock or not timeframe or state not in CONFIRMED_PUBLIC_STATES:
            return ""
        return f"{stock}|{timeframe}|{state}|{formation_id}"

    def _public_alert_muhurlerini_temizle(self, now=None) -> bool:
        """7 günden eski public event mühürlerini buda; harita sınırlı kalsın."""
        now = now or datetime.now(ISTANBUL_TZ)
        degisti = False
        for key, raw_time in list(self._public_alert_markers.items()):
            try:
                sent_at = _istanbul(datetime.fromisoformat(str(raw_time)))
            except (TypeError, ValueError):
                del self._public_alert_markers[key]
                degisti = True
                continue
            age_hours = (now - sent_at).total_seconds() / 3600.0
            if age_hours < 0 or age_hours >= _FORMATION_ALERT_MUHR_TTL_SAAT:
                del self._public_alert_markers[key]
                degisti = True
        return degisti

    def _public_durum_yukle(self) -> None:
        """Aynı güne ait public bütçe, kuyruk ve olay mühürlerini geri yükler."""
        try:
            veri = _state_persistence.gunluk_durum_yukle() or {}
        except Exception as hata:  # noqa: BLE001
            logger.debug("Public günlük durum okunamadı: %s", hata)
            return
        public = veri.get("public") or {}
        if not isinstance(public, dict):
            return
        raw_markers = public.get("alert_muhurlari")
        if isinstance(raw_markers, dict):
            self._public_alert_markers = {
                str(key): str(value) for key, value in raw_markers.items()
                if key and value
            }
        markers_changed = self._public_alert_muhurlerini_temizle()
        try:
            self._public_gun_sayac = int(public.get("gun_sayac") or 0)
        except (TypeError, ValueError):
            self._public_gun_sayac = 0
        saatlik = []
        for damga in list(public.get("saatlik_ts") or []):
            try:
                saatlik.append(datetime.fromisoformat(str(damga)))
            except (TypeError, ValueError):
                continue
        self._public_saatlik = saatlik
        kuyruk = public.get("kuyruk")
        if isinstance(kuyruk, list):
            temiz = [k for k in kuyruk if isinstance(k, dict)
                     and k.get("stock_name")
                     and str(k.get("state") or "").strip().upper() in CONFIRMED_PUBLIC_STATES
                     and str(k.get("state") or "").strip().upper() in self.public_states]
            if temiz:
                self._public_kuyruk = temiz[:self.public_kuyruk_limit]
                logger.info("Public kuyruk restart'tan geri yüklendi: %d olay", len(self._public_kuyruk))
            if len(temiz) != len(kuyruk):
                logger.info("Public kuyruktan yeni politikaya kapalı %d eski olay temizlendi",
                            len(kuyruk) - len(temiz))
                self._public_durum_kaydet()
        if markers_changed:
            self._public_durum_kaydet()
        if self._public_gun_sayac or self._public_kuyruk:
            logger.info("Public günlük bütçe geri yüklendi: %d/%d gönderim (kuyruk %d)",
                        self._public_gun_sayac, self.public_max_gunluk,
                        len(self._public_kuyruk))

    def _public_durum_kaydet(self) -> None:
        """Public bütçe + kuyruğu GÜN damgalı yazar (I/O hatası gönderimi bozmaz)."""
        try:
            with self._public_lck:
                self._public_alert_muhurlerini_temizle()
                kuyruk = [dict(k) for k in self._public_kuyruk]
                markers = dict(self._public_alert_markers)
            _state_persistence.gunluk_durum_guncelle({"public": {
                "gun_sayac": self._public_gun_sayac,
                "saatlik_ts": [t.isoformat() for t in self._public_saatlik],
                "kuyruk": kuyruk,
                "alert_muhurlari": markers,
            }})
        except Exception as hata:  # noqa: BLE001
            logger.debug("Public günlük durum yazılamadı: %s", hata)

    def _public_gun_sifirla_gerekirse(self, simdi: datetime) -> None:
        if simdi.date() != self._public_gun:
            self._public_gun = simdi.date()
            self._public_gun_sayac = 0
            self._public_saatlik = []
            self._public_durum_kaydet()

    def _public_kap_gec(self) -> bool:
        """Saatlik/günlük public bütçesi müsait mi? (DM kapılarından AYRI)"""
        simdi = datetime.now(ISTANBUL_TZ)
        self._public_gun_sifirla_gerekirse(simdi)
        self._public_saatlik = [t for t in self._public_saatlik
                                if (simdi - t).total_seconds() < 3600]
        if self._public_gun_sayac >= self.public_max_gunluk:
            return False
        if len(self._public_saatlik) >= self.public_max_saatlik:
            return False
        return True

    def _public_pace(self) -> None:
        """Sohbet başına ~1 mesaj/sn kuralı: aynı flush içinde kısa bekleme."""
        try:
            ara = float(self.public_min_aralik_sn or 0)
        except (TypeError, ValueError):
            ara = 0.0
        if ara <= 0 or self._son_public_ts is None:
            return
        bekle = ara - (time.monotonic() - self._son_public_ts)
        if bekle > 0:
            time.sleep(min(bekle, 5.0))

    def send_to_public(self, text: str, deneme: int = 1) -> bool:
        """Grup/kanal hedefine gönderir: bütçe + pacing + 429 retry + kırpma."""
        if not self.public_enabled:
            logger.info(f"[MOCK PUBLIC] {text[:120]}")
            return True
        if not self._public_kap_gec():
            self.public_engel += 1
            logger.warning("Public bütçe dolu (saatlik %d / günlük %d) - gönderim atlandı",
                           self.public_max_saatlik, self.public_max_gunluk)
            return False
        govde = _kirp(metni_sigdir(text, guvenlik=1.0))
        try:
            import requests
            self._public_pace()
            for deneme_no in range(max(0, int(deneme)) + 1):
                resp = requests.post(
                    f"https://api.telegram.org/bot{self.token}/sendMessage",
                    json={"chat_id": self.public_chat_id, "text": govde},
                    timeout=15,
                )
                if resp.status_code == 200:
                    self._son_public_ts = time.monotonic()
                    self._public_saatlik.append(datetime.now(ISTANBUL_TZ))
                    self._public_gun_sayac += 1
                    self.public_gonderilen += 1
                    self.son_public_gonderim = datetime.now(ISTANBUL_TZ).isoformat()
                    self._public_durum_kaydet()
                    logger.info("Telegram public hedefe gönderildi: %s", self.public_chat_id)
                    return True
                if resp.status_code == 429 and deneme_no < max(0, int(deneme)):
                    bekle = 3.0
                    try:
                        bekle = float((resp.json().get("parameters") or {}).get("retry_after") or bekle)
                    except Exception:  # noqa: BLE001, S110 - alan yoksa 3 sn varsayılanı kalır
                        pass
                    logger.warning("Public 429: %.0f sn sonra tekrar denenecek", bekle)
                    time.sleep(max(0.0, min(bekle, 20.0)))
                    continue
                ipucu = telegram_hata_ipucu(resp.status_code,
                                                 redact_sensitive_text(resp.text, self.token))
                logger.error("Telegram public hata: %s | %s",
                             redact_sensitive_text(resp.text, self.token)[:200], ipucu)
                break
            self.public_hatasi += 1
            self._gonderim_sagligi_kaydet(basari=False, hata="public: gönderim başarısız")
            return False
        except Exception as e:
            logger.error("Telegram public gönderim hatası: %s", e)
            self.public_hatasi += 1
            self._gonderim_sagligi_kaydet(basari=False, hata=f"public: {e}")
            return False

    def send_to_channel(self, text: str) -> bool:
        """Geriye dönük ad: eski kanal çağrıları artık public yola düşer."""
        return self.send_to_public(text)

    def public_kuyruk(self, data: Dict) -> bool:
        """Uygun olayı public kuyruğa alır (gönderim tarama turu sonunda)."""
        # Kare verisi payload'dan ERKEN alınır: DM teslim kuyruğu (`DeliveryOutbox`)
        # aynı sözlüğü diske yazıyor; public'e ait kare listesi orada kalırsa
        # her alarm için onlarca KB kare verisi 7 gün boyunca saklanırdı. Kare
        # yalnız burada, bellekteki `_public_grafik` defterinde yaşar.
        grafik_verisi = data.pop("grafik_verisi_public", None) \
            if isinstance(data, dict) else None
        if not self.public_enabled:
            return False
        try:
            if not self.should_send_to_public(data):
                return False
        except Exception as exc:  # noqa: BLE001 - kuyruk hatası taramayı durdurmasın
            logger.debug("Public filtre hatası: %s", exc)
            return False
        if self._delivery.public_duplicate(data):
            return False
        # Grup mesajı DM kartının BİREBİR aynısıdır (2026-10-22, akşam):
        # kartın okuduğu HER alan kuyruk kaydına kopyalanır; biri eksik olursa
        # metin DM'den sessizce ayrışır (`close_price` bu yüzden eklendi).
        # Yalnız JSON'a yazılabilir değerler girer (zaman damgaları ISO metne
        # çevrilir); kare dosyaları `_public_grafik` defterinde ayrı tutulur.
        kayit = {k: data.get(k) for k in (
            "stock_name", "timeframe", "pattern_name", "state", "confidence_score",
            "critical_price_level", "break_price", "break_dir", "contraction", "bar_metni",
            "candle_close_price", "close_price", "upper_touches", "lower_touches",
            "formation_id", "break_strength", "age_bars", "band_baslangic", "upper_now",
            "lower_now", "retest_seen", "mtf_destek", "domain_bolumleri", "domain_karsi")}
        for zaman_alani in ("bar_time", "bar_kapanis"):
            deger = data.get(zaman_alani)
            if deger is None:
                kayit[zaman_alani] = None
                continue
            try:
                kayit[zaman_alani] = (deger.isoformat()
                                      if hasattr(deger, "isoformat") else str(deger))
            except (TypeError, ValueError):
                kayit[zaman_alani] = None
        bolumler = kayit.get("domain_bolumleri")
        if isinstance(bolumler, dict):
            kayit["domain_bolumleri"] = {
                str(anahtar): [str(x) for x in (deger or [])][:(3 if anahtar == "olcum" else 6)]
                for anahtar, deger in bolumler.items()
            }
        anahtar = (str(kayit["stock_name"] or "").upper(),
                   str(kayit["timeframe"] or "").lower(),
                   str(kayit["state"] or "").strip().upper())
        event_key = self._public_event_key(kayit)
        # Kanal/grup: "geçersizleşti" YALNIZCA önceki teyitli mesaj gerçekten bu
        # kanala gittiyse gider. Kanalda görmemiş bir teyidin geri alınması
        # okuyucu için anlamsızdır ve "geçersiz geçersiz" gidip gelmesi üretir.
        # DM tarafı bu kapıdan etkilenmez (oradaki seri kendi içinde okunur).
        if (TELEGRAM_KANAL_GECERSIZ_KAPISI
                and str(kayit.get("state") or "").strip().upper() == "KIRILIM_GECERSIZLESTI"):
            teyit_key = self._public_event_key({**kayit, "state": "KIRILIM_TEYITLI"})
            onek = "%s|%s|KIRILIM_TEYITLI|" % (
                str(kayit.get("stock_name") or "").strip().upper(),
                str(kayit.get("timeframe") or "").strip().lower())
            with self._public_lck:
                # TEYİT HÂLÂ KUYRUKTAYSA (henüz gruba gitmedi): ikisi de düşer.
                # Eskiden yalnız gönderilmiş mühürler aranıyordu; ağ/bütçe hatası
                # yüzünden kuyrukta bekleyen teyit + hemen ardından gelen
                # geçersizleşme → teyit sonradan gidiyor, geri alma ise sonsuza
                # kadar kayboluyordu (grupta yanlış "geçerli" sinyal). Okuyucu
                # hiç görmemiş bir teyidin geri alınmasına ihtiyaç duymaz.
                bekleyen = [
                    k for k in self._public_kuyruk
                    if teyit_key and self._public_event_key(k) == teyit_key
                ]
                if bekleyen:
                    self._public_kuyruk = [
                        k for k in self._public_kuyruk
                        if not (teyit_key and self._public_event_key(k) == teyit_key)
                    ]
                    # Kilit DIŞINDA kalıcı yazılır: `_public_durum_kaydet` aynı
                    # kilidi alır, içeride çağırmak kilitlenme üretir.
                    kuyruk_degisti = True
                else:
                    kuyruk_degisti = False
                    gonderilmis = bool(
                        (teyit_key and teyit_key in self._public_alert_markers)
                        or any(str(k).startswith(onek) for k in self._public_alert_markers)
                    )
            if kuyruk_degisti:
                self._public_durum_kaydet()
                logger.info("Public: teyit henüz gönderilmemişti (%s); teyit ve "
                            "geçersizleşme birlikte düşürüldü", onek.rstrip("|"))
                return False
            if not gonderilmis:
                logger.info("Public geçersizleşme atlandı (%s): önceki teyitli mesaj bu "
                            "kanala gönderilmemiş", onek.rstrip("|"))
                return False
        with self._public_lck:
            self._public_alert_muhurlerini_temizle()
            if event_key and event_key in self._public_alert_markers:
                return False
            for queued in self._public_kuyruk:
                if event_key:
                    if self._public_event_key(queued) == event_key:
                        return False
                elif (str(queued.get("stock_name") or "").upper(),
                      str(queued.get("timeframe") or "").lower(),
                      str(queued.get("state") or "").strip().upper()) == anahtar:
                    return False
            if len(self._public_kuyruk) >= self.public_kuyruk_limit:
                self.public_kuyruk_tasmasi += 1
                logger.warning("Public kuyruk dolu (%d) - olay atıldı: %s",
                               self.public_kuyruk_limit, anahtar)
                return False
            self._public_kuyruk.append(kayit)
        veri = grafik_verisi
        if isinstance(veri, dict) and veri.get("goruntular"):
            # Kapasite: kare verisi yalnız kuyruktaki olaylar için tutulur;
            # tavan aşılırsa en eski kayıt düşer (kare, metnin eki — sahibi değil).
            if len(self._public_grafik) >= max(2 * self.public_kuyruk_limit, 40):
                self._public_grafik_buda()
                if len(self._public_grafik) >= max(2 * self.public_kuyruk_limit, 40):
                    for eski in list(self._public_grafik)[:len(self._public_grafik) // 2]:
                        self._public_grafik.pop(eski, None)
            self._public_grafik[self._public_kuyruk_anahtari(kayit)] = veri
        self._public_durum_kaydet()
        self._delivery.remember_public(data)
        return True

    def _public_kuyruk_anahtari(self, kayit: Dict) -> str:
        """Kuyruk kaydının kare defteri anahtarı (tek kaynak).

        Eski kod anahtarı iki ayrı yerde üretiyordu (yazma: `event_key or anahtar`,
        okuma: aynısı); tek fonksiyona alındı ki ikisi sessizce ayrışmasın.
        """
        if not isinstance(kayit, dict):
            return ""
        return str(self._public_event_key(kayit) or (
            str(kayit.get("stock_name") or "").upper(),
            str(kayit.get("timeframe") or "").lower(),
            str(kayit.get("state") or "").strip().upper()))

    def _public_grafik_buda(self) -> None:
        """Kuyrukta karşılığı olmayan kare verisini atar (bellek sızıntısı)."""
        kalan = {self._public_kuyruk_anahtari(k) for k in self._public_kuyruk}
        for anahtar in list(self._public_grafik):
            if anahtar not in kalan:
                del self._public_grafik[anahtar]

    def public_bosalt(self, azami: int = 12) -> int:
        """Kuyruğu gönderir: olay başına BİR mesaj, metin DM kartının aynısı.

        Kullanıcı kararı (22 Ekim 2026, akşam): *"Gelişme olmamalı, DM ile aynı
        olmalı."* Toplu bülten kaldırıldı; `azami` artık tur başına gönderilecek
        MESAJ sayısıdır (eskiden tek bültendeki olay sayısıydı). Bütçe/ağ engeli
        olursa gönderilemeyenler OLDUĞU GİBİ kuyrukta kalır.
        """
        with self._public_lck:
            original_count = len(self._public_kuyruk)
            self._public_kuyruk = [
                kayit for kayit in self._public_kuyruk
                if str(kayit.get("state") or "").strip().upper() in CONFIRMED_PUBLIC_STATES
                and str(kayit.get("state") or "").strip().upper() in self.public_states
            ]
            queue_changed = len(self._public_kuyruk) != original_count
            kuyruk = list(self._public_kuyruk)
        if queue_changed:
            # Kuyruktan düşen kayıtların kare verisi bellekte kalmasın: sözlük
            # yalnız gerçekten gönderilecek olayları tutar.
            self._public_grafik_buda()
            self._public_durum_kaydet()
        if not kuyruk or not self.public_enabled:
            return 0
        gonderilen = 0
        basarili_kayitlar = []
        for kayit in kuyruk[:max(1, int(azami))]:
            metin = self.format_public_tekil(kayit)
            if not metin:
                # Biçimlenemeyen kayıt: sessizce düşürmek yerine turu bitir
                # (kayıt kuyrukta kalır, sonraki turda yeniden denenir).
                logger.warning("Public mesajı üretilemedi (%s %s); kuyrukta kalıyor",
                               kayit.get("stock_name"), kayit.get("timeframe"))
                break
            if not self.send_to_public(metin):
                # Bütçe/ağ engeli: kayıtlar kuyrukta kalır, sonraki turda denenir.
                break
            # Metnin HEMEN ardından kare: public görsel = 1 kare + üst TF.
            # Görsel hatası metni geri almaz; sayaçla raporlanır.
            self.public_grafik_gonder(kayit)
            gonderilen += 1
            basarili_kayitlar.append(kayit)
        if gonderilen:
            damga = datetime.now(ISTANBUL_TZ).isoformat()
            with self._public_lck:
                self._public_kuyruk = self._public_kuyruk[gonderilen:]
                for kayit in basarili_kayitlar:
                    event_key = self._public_event_key(kayit)
                    if event_key:
                        self._public_alert_markers[event_key] = damga
                self._public_alert_muhurlerini_temizle()
            self._public_durum_kaydet()
            logger.info("Public: %d olay, %d ayrı mesaj", gonderilen, gonderilen)
        return gonderilen

    def format_public_tekil(self, kayit: Dict) -> str:
        """Grup mesajı: DM kartının BİREBİR aynısı (tek olay, tek mesaj).

        Kullanıcı kararı (22 Ekim 2026, akşam): *"Gelişme olmamalı, DM ile aynı
        olmalı."* Eski toplu bülten (`📊 Bülten · 3 gelişme` + tarih + sonda tek
        yasal uyarı) kaldırıldı: başlık, sayı ve tarih satırı yok; her olay
        DM'de ne görünüyorsa aynen o metinle gider. Bu yüzden biçimleyiciye
        `public` diye ikinci bir kip verilmez — iki kip zamanla ayrışır
        (ölçü 3 ↔ 2, uyarı kart başına ↔ bültede bir kez) ve "aynı" iddiası
        sessizce bozulurdu.

        Kural: metin `_format_lifecycle_alert_kart(kayit)` çıktısıdır; burada
        ekleme/çıkarma YAPILMAZ. Satır bütçesi (283 px) kartın kendi içinde
        uygulanır.
        """
        if not isinstance(kayit, dict):
            return ""
        try:
            state = str(kayit.get("state") or "").strip().upper()
        except Exception:  # noqa: BLE001 - bozuk kayıt gönderimi düşürmesin
            return ""
        if state not in CONFIRMED_PUBLIC_STATES:
            return ""
        return _format_lifecycle_alert_kart(kayit)

    def format_public_summary(self, aktif_formasyonlar: List[Dict], gun_ozeti: Dict = None,
                              izleme: List[Dict] = None, karne_kisa: str = "",
                              tarama_turu=None, kapanis: bool = True) -> str:
        """Grup sürümü kapanış/sabah özeti: sayılar + izleme listesi, teknik döküm yok.

        `kapanis=False` (09:55 sabah notu): başlık ve izleme listesi başlığı değişir;
        dün akşam gönderilen kuyruk yerine o an İZLENEN adaylar listelenir; gün
        sıfırlandığı için "❌ bugün" satırı ve tarama sayısı yazılmaz.
        """
        simdi = datetime.now(ISTANBUL_TZ)
        aktif = [f for f in (aktif_formasyonlar or []) if isinstance(f, dict)]
        freshness_known = isinstance(gun_ozeti, dict) and "tam_tarama_guncel" in gun_ozeti
        scan_current = (bool(gun_ozeti.get("tam_tarama_guncel"))
                        if freshness_known else True)
        if freshness_known and not scan_current:
            aktif = []
            izleme = []
        # Başlık eskiden "📊 13 Eki 19:30 kapanış · BIST formasyon özeti" idi ve
        # 372 px ile sarmalanıyordu. Etiket öne, tarih alta taşınır: aynı kelime.
        # (Grup tarafında "kapanış/sabah notu" ayrımı başlıkta okunmaya devam eder.)
        baslik = (f"📊 BIST kapanış · {_tr_tarih(simdi)}" if kapanis
                  else f"📊 BIST sabah notu · {_tr_tarih(simdi)}")
        satirlar = [baslik]
        retest = [f for f in aktif if f.get('state') == 'RETEST_BASARILI']
        teyitli = [f for f in aktif if f.get('state') == 'KIRILIM_TEYITLI']
        sikisan = [f for f in aktif if f.get('state') == 'SIKISMA_GUCLENIYOR'
                   and (f.get('contraction') or 0) >= self.public_sikisma_min]
        if retest or teyitli:
            # İki sayaç ayrı satırda: birleşik hali 315 px'tı ve ortadan ikiye
            # düşüp "· ✅ Teyitli kırılım 2" satırını üretiyordu.
            satirlar.append(f"🎯 Retest başarılı {len(retest)}")
            satirlar.append(f"✅ Teyitli kırılım {len(teyitli)}")
        if sikisan:
            ilk = " · ".join(f"{f.get('stock_name')} {f.get('timeframe') or ''} "
                             f"(%{(f.get('contraction') or 0) * 100:.0f})" for f in sikisan[:3])
            satirlar.append(f"⚡ Sıkışan {len(sikisan)}: {ilk}")
        if not izleme and not kapanis:
            # Sabah: dün akşamki kuyruk çoktan tüketildi; o an izlenen adaylar
            # (sıkışma/olgunlaşma) kaliteye göre sıralanıp "bugünün listesi" olur.
            izleme = _public_izleme_adaylari(aktif, haric={f.get('stock_name') for f in sikisan})
        if izleme:
            satirlar.append("")
            basliklar = ("Yarının izleme listesi" if kapanis else "Bugünün izleme listesi")
            satirlar.append(f"📡 {basliklar} (ilk {min(5, len(izleme))})")
            for k in list(izleme)[:5]:
                if not isinstance(k, dict):
                    continue
                # Kartla aynı dil: "4s" + "q89". "4 saatlik · kalite 89" ikilisi
                # satırı 330 px'a çıkarıp her maddeyi ikiye bölüyordu.
                try:
                    from reporting.format import tf_kisa as _tf_kisa
                    tf = _tf_kisa(k.get('timeframe'))
                except Exception:
                    tf = TF_HUMAN.get(k.get('timeframe'), str(k.get('timeframe') or ''))
                try:
                    kalite = f" q{float(k.get('quality') or 0):.0f}"
                except (TypeError, ValueError):
                    kalite = ""
                satirlar.append(f"• {k.get('stock')} {tf} {k.get('pattern_name') or 'formasyon'}"
                                f"{kalite}")
        if not (retest or teyitli or sikisan) and not izleme:
            if freshness_known and not scan_current:
                satirlar.append("Bugün güncel tam tarama yok;")
                satirlar.append("   eski formasyonlar gösterilmedi.")
            else:
                # "…formasyon olmadı." 287 px'ti ve satır bütçesini aşınca cümlenin
                # ortasından bölünüyordu; kısa hali tek satıra sığıyor.
                satirlar.append("Bugün öne çıkan formasyon yok." if kapanis
                                else "Şu an izlenen formasyon yok.")
        try:
            tur = int(tarama_turu) if tarama_turu is not None else 0
        except (TypeError, ValueError):
            tur = 0
        satirlar.append("")
        # "…zaman dilimi · 4 tarama · gün yeni başlıyor" 470 px'lık tek satırdı.
        if tur:
            satirlar.append(f"📈 Gün: {tur} tarama")
        # "hisse" değil "sembol": evrende endeks ve makro semboller de var.
        satirlar.append(f"   {_evren_ozeti(ayrinti=False)} × {len(TF_HUMAN)} zaman dilimi")
        if not kapanis:
            satirlar.append("   gün yeni başlıyor")
        if freshness_known and kapanis:
            event_counts = _summary_lifecycle_counts(gun_ozeti)
            if event_counts:
                satirlar.append(event_counts)
        scan_line = _summary_last_full_scan(gun_ozeti)
        if scan_line:
            satirlar.append(scan_line)
        if karne_kisa:
            satirlar += ["", karne_kisa]
        satirlar.append("📌 yatırım tavsiyesi değildir")
        return metni_sigdir("\n".join(satirlar), guvenlik=1.0)

    def format_daily_summary(self, aktif_formasyonlar: List[Dict], gun_ozeti: Dict = None) -> str:
        now = datetime.now(ISTANBUL_TZ)
        # Başlık iki satır: tek satırda 310 px'e çıkıp "· 02 Eki 20:05" kısmını
        # kaydırıyordu. Ayraç 30 çizgi 300 px ediyordu (24 = 240 px, sarmaz).
        baslik = f"📊 BIST Formasyon Özeti\n   {_tr_tarih(now)}\n"
        baslik += "─" * 24 + "\n"
        # Yalnızca doğrulanmış kırılım/retest ve yüksek sıkışma özetlenir.
        # Tamamlandı/başarısız/deneme state'leri scheduled Telegram özetine girmez.
        freshness_known = isinstance(gun_ozeti, dict) and "tam_tarama_guncel" in gun_ozeti
        scan_current = (bool(gun_ozeti.get("tam_tarama_guncel"))
                        if freshness_known else True)
        snapshot = [f for f in (aktif_formasyonlar or []) if isinstance(f, dict)]
        if freshness_known and not scan_current:
            snapshot = []
        retest = [f for f in snapshot if f.get('state') == 'RETEST_BASARILI']
        teyitli = [f for f in snapshot if f.get('state') == 'KIRILIM_TEYITLI']
        sikisan = [f for f in snapshot if f.get('state') == 'SIKISMA_GUCLENIYOR' and (f.get('contraction', 0) or 0) >= self.public_sikisma_min]
        # Madde biçimi /canli ile aynı: "HISSE TF DESEN q<KALİTE> · YÖN". Uzun
        # hali ("… · aşağı yön · kalite 88") 350 px edip her maddeyi ikiye
        # bölüyordu; 10 maddelik liste 20 satır oluyordu. Kelime kısalır,
        # veri (hisse/desen/TF/kalite/yön) aynen durur.
        def _madde(f, ek=""):
            tf = str(f.get("timeframe") or "")
            # Yön oku yalnız gerçek yönde basılır: sıkışanlarda "↔" gürültüydü ve
            # satırı 283 px sınırının üstüne taşıyordu.
            ok = "↑" if f.get("break_dir") == 1 else ("↓" if f.get("break_dir") == -1 else "")
            try:
                q = f"q{float(f.get('confidence_score') or 0):.0f}"
            except (TypeError, ValueError):
                q = ""
            # "·" ayraçları kaldırıldı: "• … · … · …" biçimi 350 px'ı aşıp her
            # maddeyi ikiye bölüyordu (10 madde = 20 satır). "•" kalır — liste
            # maddesi olarak okunması, satır sayısından daha önemli.
            return (f"• {ok} {f.get('stock_name')} {tf} {f.get('pattern_name')} {q} "
                    f"{ek}").replace("  ", " ").strip() + "\n"

        if teyitli:
            baslik += (f"\n✅ TEYİTLİ KIRILIM ({len(teyitli)}"
                       f"{' · ilk 3' if len(teyitli) > 3 else ''}):\n")
            for f in teyitli[:3]:
                baslik += _madde(f)
        if retest:
            baslik += (f"\n🎯 RETEST BAŞARILI ({len(retest)}"
                       f"{' · ilk 3' if len(retest) > 3 else ''}):\n")
            for f in retest[:3]:
                baslik += _madde(f)
        if sikisan:
            baslik += (f"\n⚡ SIKIŞANLAR ({len(sikisan)}"
                       f"{' · ilk 5' if len(sikisan) > 5 else ''}):\n")
            for f in sikisan[:5]:
                try:
                    yuzde = f"%{(float(f.get('contraction') or 0) * 100):.0f}"
                except (TypeError, ValueError):
                    yuzde = ""
                baslik += _madde(f, ek=yuzde + " ")
        if not (teyitli or retest or sikisan):
            if freshness_known and not scan_current:
                baslik += ("Güncel tam tarama yok;\n"
                           "   eski formasyonlar gösterilmedi.\n")
            else:
                baslik += "Şu an öne çıkan teyitli olay ya da sıkışma yok.\n"
        if gun_ozeti:
            # "432 hisse tarandı" = 48 hisse × 9 tarama; yanıltıcıydı.
            # Doğru okuma: kaç tur tarandı + evren büyüklüğü.
            try:
                tur = int(gun_ozeti.get("tarama_sayisi") or 0)
            except (TypeError, ValueError):
                tur = 0
            if tur <= 0:
                baslik += "\n📈 Gün: henüz tarama yapılmadı\n"
            else:
                # İki tasarlanmış satır: tek satır 435 px'a çıkıp ortadan ikiye
                # düşüyordu ("· 6 bildirim" havada kalıyordu).
                _adet = gun_ozeti.get('alerts_sent', 0)
                baslik += ("\n📈 Gün: " + (f"{tur} tarama" if tur else "tarama")
                           + (f" · {_adet} bildirim" if _adet else "") + "\n")
                baslik += (f"   {_evren_ozeti(ayrinti=False)} × {len(TF_HUMAN)} "
                           f"zaman dilimi\n")
            if freshness_known:
                event_counts = _summary_lifecycle_counts(gun_ozeti)
                if event_counts:
                    baslik += event_counts + "\n"
        scan_line = _summary_last_full_scan(gun_ozeti)
        if scan_line:
            baslik += scan_line + "\n"
        baslik += "\n📌 yatırım tavsiyesi değildir"
        return metni_sigdir(baslik, guvenlik=1.0)

    def _kap_yukle(self):
        try:
            import json
            ham = self.initial_store_data.get("state:telegram_caps")
            kaynak = "Supabase"
            if not isinstance(ham, dict):
                kaynak = "disk"
                if not os.path.exists(self._kap_dosya):
                    return
                with open(self._kap_dosya, "r", encoding="utf-8") as f:
                    ham = json.load(f)
            self._gunluk_sayac = int(ham.get("gunluk_sayac", 0))
            self._gunluk_tarih = datetime.fromisoformat(ham["gunluk_tarih"]).date()
            self._saatlik_zamanlar = [_istanbul(datetime.fromisoformat(t))
                                      for t in ham.get("saatlik", [])]
            logger.info(f"Telegram kap hafızası {kaynak} yüklendi: saatlik={len(self._saatlik_zamanlar)}, günlük={self._gunluk_sayac}")
        except Exception as e:
            logger.debug(f"Kap hafızası yüklenemedi (ilk çalışma olabilir): {e}")

    def _gonderim_kaydet(self):
        self._gunu_sifirla_gerekirse()
        self._saatligi_temizle()
        self._saatlik_zamanlar.append(datetime.now(ISTANBUL_TZ))
        self._gunluk_sayac += 1
        self._kap_kaydet()

    def _kap_kaydet(self):
        payload = {
            "gunluk_sayac": self._gunluk_sayac,
            "gunluk_tarih": self._gunluk_tarih.isoformat(),
            "saatlik": [t.isoformat() for t in self._saatlik_zamanlar],
        }
        try:
            import json
            os.makedirs(os.path.dirname(self._kap_dosya), exist_ok=True)
            with open(self._kap_dosya, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
        except Exception as e:
            logger.debug(f"Kap hafızası kaydedilemedi: {e}")
        if self.persistent_store is not None:
            self.persistent_store.upsert("state:telegram_caps", payload)

    def _gunu_sifirla_gerekirse(self):
        bugun = datetime.now(ISTANBUL_TZ).date()
        if bugun != self._gunluk_tarih:
            self._gunluk_sayac = 0
            self._gunluk_tarih = bugun
            self._kap_uyarildi = False
            # Engel/hata sayaçları da günlüktür; yoksa /durum dünün engelini gösterir.
            self.engeller = dict(_ENGEL_SAYACLAR)
            self.gonderim_hatasi = 0
            self.gonderilen_alarm = 0

    def _dm_degisim_durumu(self, data: Dict) -> str:
        """'yeni' | 'guncelleme' — bağlam önceki kartla birebir aynıysa kısalt.

        Tam susturma YAPILMAZ: kopya olayı zaten mühür keser. Buradaki amaç,
        mührü farklı bir olaya değse bile (25 Eyl TOASO: 10:40 → 15:10, 35 satırın
        30'u aynı) değişmemiş 600-800 kr'luk bağlam bloğunu tekrar basmamak.
        """
        anahtar = _dm_anahtar(data)
        if not anahtar.strip("|"):
            return "yeni"
        if not isinstance(data.get("domain_bolumleri"), dict) or not data.get("domain_bolumleri"):
            return "yeni"        # bağlam zaten yok → kısaltılacak bir şey yok
        imza = _dm_imza(data)
        with self._dm_imza_lck:
            kayit = self._dm_imzalar.get(anahtar) or {}
        return "guncelleme" if str(kayit.get("imza") or "") == imza else "yeni"

    # --- içerik kopyası kapısı ---------------------------------------------

    def _kart_metni(self, data: Dict) -> str:
        """Gönderilecek kart metni (hata olursa boş: kapı sessizce devre dışı)."""
        try:
            return str(data.get("_delivery_message") or self.format_message(data) or "")
        except Exception:  # noqa: BLE001 - metin üretilemezse kopya kapısı çalışmaz
            return ""

    def _kart_imza_anahtari(self, data: Dict) -> str:
        return "|".join(str(data.get(k) or "") for k in
                        ("stock_name", "timeframe", "state")).upper()

    def _kart_kopyasi_mi(self, data: Dict) -> bool:
        """Aynı hisse+TF+state kartı TTL içinde birebir aynıysa True.

        TTL, mühürle aynı ölçekte (`_muhur_ttl_saat`): motorun "aynı olay"
        penceresini kapsar. Metin birebir aynı değilse olay yenidir.
        """
        import hashlib
        metin = self._kart_metni(data)
        if not metin:
            return False
        anahtar = self._kart_imza_anahtari(data)
        imza = hashlib.sha1(metin.encode("utf-8")).hexdigest()
        with self._kart_imza_lck:
            kayit = dict(self._kart_imzalar.get(anahtar) or {})
        if str(kayit.get("imza") or "") != imza:
            return False
        try:
            zaman = datetime.fromisoformat(str(kayit.get("zaman") or ""))
        except (TypeError, ValueError):
            return False
        ttl = _muhur_ttl_saat(str(data.get("timeframe") or ""))
        return (datetime.now(ISTANBUL_TZ) - _istanbul(zaman)) <= timedelta(hours=ttl)

    def _kart_imza_kaydet(self, data: Dict) -> None:
        import hashlib
        metin = self._kart_metni(data)
        anahtar = self._kart_imza_anahtari(data)
        if not metin or not anahtar.strip("|"):
            return
        with self._kart_imza_lck:
            self._kart_imzalar[anahtar] = {
                "imza": hashlib.sha1(metin.encode("utf-8")).hexdigest(),
                "zaman": datetime.now(ISTANBUL_TZ).isoformat(),
            }

    def _dm_imza_kaydet(self, data: Dict) -> None:
        anahtar = _dm_anahtar(data)
        if not anahtar.strip("|"):
            return
        with self._dm_imza_lck:
            self._dm_imzalar[anahtar] = {
                "imza": _dm_imza(data),
                "gun": datetime.now(ISTANBUL_TZ).date().isoformat(),
            }
            # Gün değişince imzalar düşer: ertesi gün aynı bağlam bile olsa yeni
            # bir seans bilgisidir.
            gunler = {v.get("gun") for v in self._dm_imzalar.values()}
            if len(gunler) > 1:
                guncel = datetime.now(ISTANBUL_TZ).date().isoformat()
                self._dm_imzalar = {k: v for k, v in self._dm_imzalar.items()
                                    if v.get("gun") == guncel}

    def _saatligi_temizle(self):
        sinir = datetime.now(ISTANBUL_TZ) - timedelta(hours=1)
        self._saatlik_zamanlar = [t for t in self._saatlik_zamanlar if t > sinir]

    def kap_durumu(self) -> Dict:
        self._saatligi_temizle()
        self._gunu_sifirla_gerekirse()
        return {
            "saatlik": len(self._saatlik_zamanlar),
            "saatlik_limit": self.max_saatlik,
            "gunluk": self._gunluk_sayac,
            "gunluk_limit": self.max_gunluk,
            # GÖREV 6 (A10): Ayrı kategori sayaçları — mevcut alert/watch/digest/command ayrımı korunur
            "alert_sayac": getattr(self, 'alert_sayac', 0),
            "watch_digest_sayac": getattr(self, 'digest_sayac', 0),
            "command_sayac": getattr(self, 'command_sayac', 0),
        }

    def _cooldown_yukle(self):
        try:
            import json
            ham = self.initial_store_data.get("state:telegram_cooldowns")
            kaynak = "Supabase"
            if not isinstance(ham, dict):
                kaynak = "disk"
                if not os.path.exists(self._cooldown_dosya):
                    return
                with open(self._cooldown_dosya, "r", encoding="utf-8") as f:
                    ham = json.load(f)
            for k, iso in ham.items():
                # Eski kayıtlar naive olabilir; _istanbul ile normalize edilir.
                self.last_sent[k] = _istanbul(datetime.fromisoformat(iso))
            logger.info(f"Cooldown hafızası {kaynak} yüklendi: {len(ham)} kayıt")
        except Exception as e:
            logger.warning(f"Cooldown yüklenemedi (devam ediliyor): {e}")

    def _cooldown_kaydet(self):
        payload = {k: v.isoformat() for k, v in self.last_sent.items()}
        try:
            import json
            os.makedirs(os.path.dirname(self._cooldown_dosya), exist_ok=True)
            with open(self._cooldown_dosya, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=0)
        except Exception as e:
            logger.warning(f"Cooldown kaydedilemedi (devam ediliyor): {e}")
        if self.persistent_store is not None:
            self.persistent_store.upsert("state:telegram_cooldowns", payload)

    def _cooldown_key(self, stock: str, pattern: str, timeframe: str, state: str) -> str:
        return f"{stock}_{pattern}_{timeframe}_{state}"

    # --- tek-seferlik olay hafızası (repeat-guard) --------------------------
    # Mühür (hisse + TF + state + varsa formation ID) anahtarlıdır. Kimliksiz
    # eski olaylar bar süresine göre TTL ile; yeni stable-ID olaylar 7 gün ile
    # sınırlandırılır. Üç kök neden düzeltildi:
    #   1) pattern anahtardan ÇİKARILDI: motor aynı slotta bazen "Simetrik
    #      Üçgen", bazen "Alçalan Üçgen" etiketi üretebiliyordu; iki farklı
    #      anahtar = iki ayrı mesaj (örn. PETKM 4h iki kez TAMAMLANDI).
    #   2) mühür "slot sıfırlama" ile siliniyordu; canlı geometri (has_pattern)
    #      kayan pencerede bir taramada False olup FORMASYON_YOK'a düştüğünde
    #      (flicker) mühür silinip aynı olay tekrar basılıyordu.
    #   3) bayatlık "İstanbul günü" ölçülüyordu; motor terminal formasyonu
    #      TERMINAL_TAZE_BAR bar taze tuttuğu için gün sınırını aşan formasyon
    #      (1 günlük grafikte 3 gün, 4 saatlikte ertesi sabah) tekrar
    #      bildiriliyordu. Artık TTL bar süresine göre ölçekleniyor.
    # Aynı hisse+TF+state, motorun aynı olay penceresi içinde en fazla BİR kez bildirilir.
    def _son_alert_key(self, stock: str, timeframe: str, state: str,
                       formation_id=None) -> str:
        """Olay anahtarı: hisse + TF + state; varsa formasyon kimliğiyle tekilleştir."""
        base = f"{stock}_{timeframe}_{state}"
        event_id = str(formation_id or "").strip()
        return f"{base}_formation_{event_id}" if event_id else base

    @classmethod
    def _muhr_gecerli_mi(cls, muhur, state: str, timeframe: str = "",
                         formation_id=None) -> bool:
        """Mühür hâlâ geçerliyse True (olay zaten bildirildi, tekrar basma).

        Formation ID varsa aynı teyitli olayı 7 gün boyunca tekilleştir; bu
        süre 1 günlük TF'deki retest tutunma penceresini de kapsar. Kimliksiz
        eski kayıtlar, geriye dönük uyum için bar süresi tabanlı TTL kullanır.
        """
        if not muhur or not isinstance(muhur, dict):
            return False
        if muhur.get("state") != state:
            return False
        incoming_id = str(formation_id or "").strip()
        stored_id = str(muhur.get("formation_id") or "").strip()
        if incoming_id and stored_id and incoming_id != stored_id:
            return False
        zaman = muhur.get("zaman")
        if not isinstance(zaman, str):
            return False
        try:
            basma = datetime.fromisoformat(zaman)
        except (TypeError, ValueError):
            return False
        if basma.tzinfo is None:
            basma = ISTANBUL_TZ.localize(basma)
        yas_saat = (datetime.now(ISTANBUL_TZ) - basma).total_seconds() / 3600.0
        ttl = (_FORMATION_ALERT_MUHR_TTL_SAAT
               if incoming_id and stored_id == incoming_id
               else _muhur_ttl_saat(muhur.get("tf") or timeframe))
        return 0 <= yas_saat < ttl

    @staticmethod
    def _muhur_kaydi(state: str, timeframe: str, gun: str = None,
                     zaman: str = None, formation_id=None) -> Dict:
        """Mühür kaydı üretir; oluşum kimliği varsa olay bazında saklar.

        Yeni mühür ŞU AN ile damgalanır. Yalnız ESKİ (gün bazlı) kayıtlar
        dönüştürülürken o günün 00:00'i kullanılır: böylece deploy öncesi
        basılmış mühürler bayat sayılmaz, upgrade anında kopya dalgası çıkmaz.
        """
        if not isinstance(zaman, str) or not zaman:
            if isinstance(gun, str) and gun:
                # ESKİ BİÇİM (gün bazlı): o günün 00:00'i (İstanbul).
                try:
                    zaman = datetime.fromisoformat(gun).isoformat()
                except (TypeError, ValueError):
                    zaman = datetime.now(ISTANBUL_TZ).isoformat()
            else:
                zaman = datetime.now(ISTANBUL_TZ).isoformat()
        kayit = {"state": state, "zaman": zaman, "tf": timeframe}
        event_id = str(formation_id or "").strip()
        if event_id:
            kayit["formation_id"] = event_id
        return kayit

    @staticmethod
    def _anahtardan_tf(anahtar: str) -> str:
        """"hisse_tf_STATE" anahtarından zaman dilimini çıkar (eski kayıtlar için).

        STATE adları alt çizgi içerir (FORMASYON_TAMAMLANDI), bu yüzden sağdan
        değil bilinen state listesiyle eşleştirilerek ayrıştırılır.
        """
        for state in ALERT_STATES:
            if anahtar.endswith(f"_{state}"):
                _, _, tf = anahtar[:-len(f"_{state}")].rpartition("_")
                return tf
        return ""

    def _son_alert_yukle(self):
        try:
            import json
            ham = self.initial_store_data.get("state:telegram_son_alerts")
            kaynak = "Supabase"
            if not isinstance(ham, dict):
                kaynak = "disk"
                if not os.path.exists(self._son_alert_dosya):
                    return
                with open(self._son_alert_dosya, "r", encoding="utf-8") as f:
                    ham = json.load(f)
            if isinstance(ham, dict):
                for k, v in ham.items():
                    if not isinstance(k, str):
                        continue
                    if isinstance(v, str):
                        # ESKİ BİÇİM: anahtar "hisse_pattern_tf", değer state.
                        # Yeni anahtara ("hisse_tf_state") taşınır ve bugüne
                        # mühürlenir — upgrade anında olay tekrar basmaz.
                        stock_pattern, _, tf = k.rpartition("_")
                        if not stock_pattern or not tf or not v:
                            continue
                        stock = stock_pattern.split("_", 1)[0]
                        if not stock:
                            continue
                        self._son_alert[f"{stock}_{tf}_{v}"] = self._muhur_kaydi(v, tf)
                    elif isinstance(v, dict) and isinstance(v.get("state"), str):
                        # Yeni biçim: zaman damgası korunur (bayatsa _muhr_gecerli_mi reddeder).
                        self._son_alert[k] = self._muhur_kaydi(
                            v["state"], v.get("tf") or self._anahtardan_tf(k),
                            gun=v.get("gun"), zaman=v.get("zaman"),
                            formation_id=v.get("formation_id"))
            logger.info(f"Son-alert mühürleri {kaynak} yüklendi: {len(self._son_alert)} kayıt")
        except Exception as e:
            logger.warning(f"Son-alert mühürleri yüklenemedi (devam ediliyor): {e}")

    def _son_alert_kaydet(self):
        # TTL'si dolmuş mühürler diske/Supabase'a taşınmaz; sözlük şişmesin.
        bayat_anahtarlar = [
            key for key, marker in self._son_alert.items()
            if not self._muhr_gecerli_mi(
                marker,
                marker.get("state", ""),
                marker.get("tf", ""),
                marker.get("formation_id"),
            )
        ]
        for key in bayat_anahtarlar:
            del self._son_alert[key]
        payload = {k: dict(v) for k, v in self._son_alert.items()}
        try:
            import json
            os.makedirs(os.path.dirname(self._son_alert_dosya), exist_ok=True)
            with open(self._son_alert_dosya, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=0)
        except Exception as e:
            logger.warning(f"Son-alert mühürleri diske kaydedilemedi: {e}")
        if self.persistent_store is not None:
            try:
                self.persistent_store.upsert("state:telegram_son_alerts", payload)
            except Exception as e:
                logger.debug(f"Son-alert mühürleri Supabase'e kaydedilemedi: {e}")

    def _tek_seferlik_isle(self, stock: str, pattern: str, timeframe: str,
                           state: str, formation_id=None) -> None:
        """Başarılı gönderim sonrası teyitli olaya tek-seferlik mühür basar.

        Deneme, bekleme, başarısızlık ve tamamlanma state'leri push politikasında
        değildir. Formation ID varsa aynı state'in aynı oluşumdan tekrar çıkmasını
        engeller; kimlik yoksa geriye dönük slot/TTL mührü kullanılır.
        """
        if state not in ALERT_STATES:
            return
        key = self._son_alert_key(stock, timeframe, state, formation_id)
        self._son_alert[key] = self._muhur_kaydi(
            state, timeframe, formation_id=formation_id
        )
        self._son_alert_kaydet()

    def son_alert_sifirla(self, stock: str, timeframe: str) -> None:
        """Slotun (hisse+TF) ZAMAN cooldown'larını siler; mühürlere DOKUNMAZ.

        NEDEN DEĞİŞTİ: bu fonksiyon önce mühürleri de siliyordu. Motorun canlı
        geometrisi (has_pattern) kayan pencerede bir taramada False olup
        FORMASYON_YOK'a düştüğünde (flicker) main bu fonksiyonu çağırıyordu;
        mühür silinince aynı formasyon bir sonraki taramada yeniden "doğup"
        AYNI TAMAMLANDI/BAŞARISIZ mesajını tekrar basıyordu (ölçüm: kullanıcının
        günlüğünde ~45 mesajın ~13'ü birebir kopya). Mühür artık yalnız gün
        değişiminde bayatlar.

        Cooldown temizliği KORUNUR: slotu tekrar kaplayan yeni formasyonun
        ilerleme mesajları (TEYITLI -> RETEST -> TAMAMLANDI) 4 saat beklemez.
        """
        on_ek = f"{stock}_"
        # Anahtar biçimi hisse_desen_tf_STATE; STATE listesi üzerinden sonek eşle.
        durumler = set(ALERT_STATES) | set(WATCH_STATES)
        for anahtar in list(self.last_sent.keys()):
            if not anahtar.startswith(on_ek):
                continue
            govde = anahtar[len(on_ek):]
            if any(govde.endswith(f"_{timeframe}_{durum}") for durum in durumler):
                del self.last_sent[anahtar]
        self._cooldown_kaydet()

    # --- engellenen acil olay kuyruğu (Batch 5 / B4) ------------------------

    @staticmethod
    def _kuyruk_key(veri: Dict) -> tuple:
        return (
            str(veri.get("stock_name") or "").strip().upper(),
            str(veri.get("pattern_name") or "").strip(),
            str(veri.get("timeframe") or "").strip().lower(),
            str(veri.get("state") or "").strip().upper(),
        )

    def _kuyruk_yukle(self):
        try:
            import json
            ham = self.initial_store_data.get("state:telegram_acil_kuyruk")
            kaynak = "Supabase"
            if not isinstance(ham, list):
                kaynak = "disk"
                if not os.path.exists(self._kuyruk_dosya):
                    return
                with open(self._kuyruk_dosya, "r", encoding="utf-8") as f:
                    ham = json.load(f)
            if not isinstance(ham, list):
                return
            from notification_delivery import _decode
            ham = json.loads(json.dumps(ham), object_hook=_decode)
            self._acil_kuyruk = [k for k in ham if isinstance(k, dict) and isinstance(k.get("veri"), dict)]
            logger.info(f"Telegram acil kuyruğu {kaynak} yüklendi: {len(self._acil_kuyruk)} olay")
        except Exception as e:
            logger.debug(f"Acil kuyruk yüklenemedi (ilk çalışma olabilir): {e}")

    def _kuyruk_kaydet(self):
        import json
        from notification_delivery import _encode
        kayitlar = json.loads(json.dumps(self._acil_kuyruk, default=_encode))
        try:
            os.makedirs(os.path.dirname(self._kuyruk_dosya), exist_ok=True)
            with open(self._kuyruk_dosya + ".tmp", "w", encoding="utf-8") as f:
                json.dump(kayitlar, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(self._kuyruk_dosya + ".tmp", self._kuyruk_dosya)
        except Exception as e:
            logger.debug(f"Acil kuyruk dosyaya kaydedilemedi: {e}")
        if self.persistent_store is not None:
            try:
                self.persistent_store.upsert("state:telegram_acil_kuyruk", kayitlar)
            except Exception as e:
                logger.debug(f"Acil kuyruk Supabase'e kaydedilemedi: {e}")

    def _public_kayitli_mi(self, data: Dict) -> bool:
        """Olay public defterinde/kuyruğunda zaten var mı? (mühürsüzse: hayır)"""
        event_key = self._public_event_key(data)
        if not event_key:
            return False
        with self._public_lck:
            if event_key in self._public_alert_markers:
                return True
            return any(self._public_event_key(k) == event_key for k in self._public_kuyruk)

    def _public_kurtar(self, data: Dict, prepare_context) -> bool:
        """DM "tekrar" dediğinde public'in kaybolmuş olayını kurtarır.

        Dönen değer: bağlam hazırlandı mı (yani public kuyruğuna giriş denendi mi).
        Karar public'in kendi kapılarına bırakılır (`should_send_to_public`,
        kuyruk mührü); burada yalnız "bağlamı hazırlamaya değer mi" sorusu
        cevaplanır. Sessiz istisna yok: hata loglanır, alarm akışı durmaz.
        """
        if not self.public_enabled:
            return False
        try:
            if not self.should_send_to_public(data):
                return False
        except Exception as exc:  # noqa: BLE001 - public filtresi DM'i düşürmesin
            logger.debug("Public kurtarma filtresi hata verdi: %s", exc)
            return False
        if self._public_kayitli_mi(data):
            return False
        prepare_context()
        return True

    def _kuyruga_ekle(self, data: Dict, engel: str) -> None:
        """Engel nedeniyle gönderilemeyen acil olayı kuyruğa alır (en fazla 1 kopya)."""
        key = self._kuyruk_key(data)
        if not all(key):
            return
        simdi = datetime.now(ISTANBUL_TZ)
        for kayit in self._acil_kuyruk:
            if self._kuyruk_key(kayit.get("veri") or {}) == key:
                # Aynı sinyal zaten kuyrukta: veriyi tazele, kuyrukta bekleme süresi
                # ilk girişten sayılmaya devam etsin (TTL şişmesin).
                kayit["veri"] = _kuyruk_verisi(data)
                kayit["son_deneme"] = simdi.isoformat()
                kayit["son_engel"] = engel
                self._kuyruk_kaydet()
                return
        while len(self._acil_kuyruk) >= ACIL_KUYRUK_LIMIT:
            self._acil_kuyruk.pop(0)
            self.kuyruk_tasmasi += 1
        self._acil_kuyruk.append({
            "kuyruk_zaman": simdi.isoformat(),
            "son_deneme": simdi.isoformat(),
            "son_engel": engel,
            "veri": _kuyruk_verisi(data),
        })
        logger.info(f"📬 Acil olay kuyruğa alındı ({engel}): {key[0]} {key[2]} {key[3]} "
                    f"(kuyruk: {len(self._acil_kuyruk)})")
        self._kuyruk_kaydet()

    def kuyrukta_mi(self, data: Dict) -> bool:
        """Bu olay kuyrukta bekliyor mu? (çağıran taraf sayaç/huni için kullanır)"""
        key = self._kuyruk_key(data)
        return any(self._kuyruk_key(kayit.get("veri") or {}) == key for kayit in self._acil_kuyruk)

    def kuyruk_durumu(self) -> Dict:
        return {
            "bekleyen": len(self._acil_kuyruk),
            "limit": ACIL_KUYRUK_LIMIT,
            "gonderildi": self.kuyruk_gonderildi,
            "zaman_asimi": self.kuyruk_zaman_asimi,
            "tasma": self.kuyruk_tasmasi,
        }

    def kuyruk_ozet_kayitlari(self, now: Optional[datetime] = None) -> List[dict]:
        """Kapanış özetinde gösterilebilecek taze, henüz bildirilmemiş olayları kopyala.

        Bu yöntem hiçbir şeyi tüketmez. Özet Telegram'a başarıyla teslim olduktan
        sonra çağıran `kuyruk_ozetleneni_tuket()` ile yalnızca gösterilenleri alır.
        """
        simdi = _istanbul(now) if now is not None else datetime.now(ISTANBUL_TZ)
        ttl_siniri = simdi - timedelta(minutes=max(1, _pkg.ACIL_KUYRUK_TTL_DK))
        sonuc = []
        for kayit in self._acil_kuyruk:
            veri = dict(kayit.get("veri") or {})
            state = str(veri.get("state") or "").strip().upper()
            if state not in ALERT_STATES:
                continue
            try:
                kuyruk_zamani = _istanbul(datetime.fromisoformat(kayit.get("kuyruk_zaman")))
            except (TypeError, ValueError):
                kuyruk_zamani = simdi
            if kuyruk_zamani < ttl_siniri or kuyruk_zamani.date() != simdi.date():
                continue
            stock, pattern, timeframe, _state = self._kuyruk_key(veri)
            formation_id = veri.get("formation_id")
            marker = self._son_alert.get(
                self._son_alert_key(stock, timeframe, state, formation_id))
            if (not marker and formation_id):
                marker = self._son_alert.get(self._son_alert_key(stock, timeframe, state))
            if self._muhr_gecerli_mi(marker, state, timeframe, formation_id):
                continue
            sonuc.append({"kuyruk_zaman": kayit.get("kuyruk_zaman"), "veri": veri})
        return sonuc

    def kuyruk_ozetleneni_tuket(self, kayitlar: List[dict]) -> int:
        """Başarıyla iletilen kapanış özetindeki olayları tüket ve tekilleştir.

        Özetin Telegram kabulü, olayın kullanıcıya görünür teslimidir. Böylece
        aynı formation/state ertesi turda ayrı bir acil mesaj olarak yinelenmez.
        """
        imzalar = set()
        for kayit in kayitlar or []:
            if not isinstance(kayit, dict) or not isinstance(kayit.get("veri"), dict):
                continue
            imzalar.add((self._kuyruk_key(kayit["veri"]),
                         str(kayit.get("kuyruk_zaman") or "")))
        if not imzalar:
            return 0
        kalan = []
        tuketilen = []
        for kayit in self._acil_kuyruk:
            imza = (self._kuyruk_key(kayit.get("veri") or {}),
                    str(kayit.get("kuyruk_zaman") or ""))
            (tuketilen if imza in imzalar else kalan).append(kayit)
        if not tuketilen:
            return 0
        self._acil_kuyruk = kalan
        muhur_degisti = False
        for kayit in tuketilen:
            veri = kayit.get("veri") or {}
            state = str(veri.get("state") or "").strip().upper()
            if state not in ALERT_STATES:
                continue
            stock, pattern, timeframe, _state = self._kuyruk_key(veri)
            muhur_anahtari = self._son_alert_key(
                stock, timeframe, state, veri.get("formation_id"))
            self._son_alert[muhur_anahtari] = self._muhur_kaydi(
                state, timeframe, formation_id=veri.get("formation_id"))
            muhur_degisti = True
        if muhur_degisti:
            self._son_alert_kaydet()
        self._kuyruk_kaydet()
        return len(tuketilen)

    def kuyruk_tumunu_temizle(self) -> int:
        """Kapanış özeti daha önce gönderildiyse eski kuyruğu post-digest push'tan al."""
        adet = len(self._acil_kuyruk)
        if adet:
            self._acil_kuyruk.clear()
            self._kuyruk_kaydet()
        return adet

    def kuyrugu_bosalt(self, max_adet: int = 5, now: Optional[datetime] = None) -> int:
        """Çağıran zaman kapısı açıksa, engel kalkınca acil olayları sırayla gönder.

        Main loop bunu kapanış digest saatinden önce çağırır; daha geç saatlerde
        bekleyen kayıtlar DM kapanış özetine katılır.
        - TTL'yi aşan kayıtlar gönderilmez, atılır (bayat sinyal zarar verir).
        - Aynı sinyal sonradan gönderilmişse kuyruk kopyası sessizce düşürülür.
        - Kap/cooldown sürüyorsa sıradaki tura kadar beklenir; ağ hatasında
          kayıt korunur (veri kaybı yok).
        """
        if not self.enabled or not self._acil_kuyruk:
            return 0
        simdi = _istanbul(now) if now is not None else datetime.now(ISTANBUL_TZ)
        ttl_siniri = simdi - timedelta(minutes=max(1, _pkg.ACIL_KUYRUK_TTL_DK))
        gonderilen = 0
        degisti = False
        for kayit in list(self._acil_kuyruk):
            if gonderilen >= max(1, int(max_adet)):
                break
            veri = dict(kayit.get("veri") or {})
            if str(veri.get("state") or "").strip().upper() not in ALERT_STATES:
                # Eski deploy'lardan kalan deneme/başarısız/tamamlandı kuyrukları
                # yeni bildirim politikasında kesinlikle gönderme.
                self._acil_kuyruk.remove(kayit)
                degisti = True
                continue
            try:
                kuyruk_zamani = _istanbul(datetime.fromisoformat(kayit.get("kuyruk_zaman")))
            except (TypeError, ValueError):
                kuyruk_zamani = simdi
            if kuyruk_zamani.date() != simdi.date():
                self._acil_kuyruk.remove(kayit)
                self.kuyruk_zaman_asimi += 1
                degisti = True
                logger.warning(
                    "📬 Önceki İstanbul gününde kalan acil olay ayrı push yapılmadı: %s %s",
                    self._kuyruk_key(veri)[0], veri.get("state"),
                )
                continue
            if kuyruk_zamani < ttl_siniri:
                self._acil_kuyruk.remove(kayit)
                self.kuyruk_zaman_asimi += 1
                degisti = True
                logger.warning(
                    f"📬 Kuyruktaki acil olay bayatladı ({_pkg.ACIL_KUYRUK_TTL_DK} dk): "
                    f"{self._kuyruk_key(veri)[0]} {veri.get('state')}"
                )
                continue
            key = self._kuyruk_key(veri)
            if not self.can_send(
                key[0], key[1], key[2], key[3], formation_id=veri.get("formation_id")
            ):
                if self._son_engel == "tekrar":
                    # Mühür bu olayın zaten gönderildiğini söylüyor; kuyruktaki
                    # bayat kopya gereksiz -> sessizce düşür (cooldown dalından önce).
                    self._acil_kuyruk.remove(kayit)
                    degisti = True
                    continue
                if self._son_engel == "cooldown" and key in self.last_sent:
                    if _istanbul(self.last_sent[key]) > kuyruk_zamani:
                        # Aynı sinyal kuyruğa girdikten sonra gönderildi; kopya gereksiz.
                        self._acil_kuyruk.remove(kayit)
                        degisti = True
                        continue
                break  # engel sürüyor: sırayı bozmadan bekle
            # Acil kuyrukta `grafik_verisi` bilerek yoktur; bunu normal bir
            # köprü atlaması gibi sayıp karesiz sayaçlarını şişirmeyelim.
            veri["_kuyruktan"] = True
            if self._gonder(veri):
                self._acil_kuyruk.remove(kayit)
                self.kuyruk_gonderildi += 1
                gonderilen += 1
                degisti = True
                logger.info(f"📬 Kuyruktan gönderildi: {key[0]} {key[2]} {key[3]}")
            else:
                # Ağ/Telegram hatası: kayıt kuyrukta kalır, kaybolmaz.
                break
        if degisti:
            self._kuyruk_kaydet()
        return gonderilen

    def can_send(self, stock: str, pattern: str, timeframe: str, state: str = "",
                 formation_id=None) -> bool:
        """Gönderim yapılabilir mi? Hayırsa SEBEBİ sayaca yazılır (bkz. self.engeller)."""
        # Her çağrı temiz başlar: kritik state'in kapıyı geçmesi bir önceki
        # engelin sebebini taşımaz (yanlış "kuyruğa al" kararı olmasın).
        self._son_engel = None
        # Tek-seferlik mühür (repeat-guard) ZAMAN cooldown'undan ÖNCE gelir:
        # motor aynı terminal state'i her tur yeniden ürettiği için 4 saat dolunca
        # kopya mesaj basılıyordu. Mühür "bu slot bu state'i BUGÜN zaten bildirdi"
        # derse olay NİHAİ reddir (kuyruğa alınmaz, beklenmez). Slot sıfırlama
        # (flicker) mühürü artık silmez; bayatlık yalnız gün değişiminde.
        if state in ALERT_STATES:
            marker_key = self._son_alert_key(stock, timeframe, state, formation_id)
            marker = self._son_alert.get(marker_key)
            # Deploy öncesi mühürler kimliksizdir; kısa legacy TTL süresince
            # yeni anahtara taşınırken yinelenen push'u da engellesin.
            if (not marker and formation_id
                    and self._muhr_gecerli_mi(
                        self._son_alert.get(self._son_alert_key(stock, timeframe, state)),
                        state, timeframe, formation_id)):
                marker = self._son_alert.get(self._son_alert_key(stock, timeframe, state))
            if self._muhr_gecerli_mi(marker, state, timeframe, formation_id):
                self.engeller["tekrar"] += 1
                self._son_engel = "tekrar"
                return False
        key = self._cooldown_key(stock, pattern, timeframe, state)
        if key not in self.last_sent:
            cooldown_tamam = True
        else:
            elapsed = datetime.now(ISTANBUL_TZ) - _istanbul(self.last_sent[key])
            cooldown_tamam = elapsed > timedelta(hours=self.cooldown_hours)
        if not cooldown_tamam:
            self.engeller["cooldown"] += 1
            self._son_engel = "cooldown"
            return False
        self._gunu_sifirla_gerekirse()
        self._saatligi_temizle()
        if self._gunluk_sayac >= self.max_gunluk:
            self.engeller["gunluk_kap"] += 1
            self._son_engel = "gunluk_kap"
            if not self._kap_uyarildi:
                self._kap_uyarildi = True
                logger.error(f"TELEGRAM GÜNLÜK KAPANI AŞILDI ({self.max_gunluk} mesaj) - bugün başka mesaj gönderilmeyecek.")
            return False
        if len(self._saatlik_zamanlar) >= self.max_saatlik:
            if state in KRITIK_STATELER:
                return True
            self.engeller["saatlik_kap"] += 1
            self._son_engel = "saatlik_kap"
            if not self._kap_uyarildi:
                self._kap_uyarildi = True
                logger.warning(f"TELEGRAM SAATLİK KAPANI AŞILDI ({self.max_saatlik} mesaj/saat) - sadece kritik sinyaller.")
            return False
        self._son_engel = None
        return True

    def gonderim_durumu(self) -> Dict:
        """Bugünün gönderim/engel özeti (/durum ve heartbeat için)."""
        return {
            "enabled": self.enabled,
            "gonderilen_alarm": self.gonderilen_alarm,
            "hatalar": self.gonderim_hatasi,
            "kanal_hatasi": self.kanal_hatasi,
            "engeller": dict(self.engeller),
            "gunluk_kap": self.max_gunluk,
            "saatlik_kap": self.max_saatlik,
            "son_basarili_gonderim": self.son_basarili_gonderim,
            "son_gonderme_hatasi": self.son_gonderme_hatasi,
            # Engellenen acil olaylar: kaç tanesi bekliyor / kaçı gönderildi.
            "acil_kuyruk": len(self._acil_kuyruk),
            "teslim_kuyrugu": self._delivery.status(),
            "kuyruk_gonderildi": self.kuyruk_gonderildi,
            "kuyruk_zaman_asimi": self.kuyruk_zaman_asimi,
            "kuyruk_tasmasi": self.kuyruk_tasmasi,
            # Public (grup) hedefi: DM'den bağımsız sayaçlar.
            "public_enabled": self.public_enabled,
            "public_chat_id": self.public_chat_id,
            "public_gonderilen": self.public_gonderilen,
            "public_hatasi": self.public_hatasi,
            "public_engel": self.public_engel,
            "public_grafik_gonderilen": self.public_grafik_gonderilen,
            "public_grafik_hatasi": self.public_grafik_hatasi,
            # Görsel kuyruğu (§4): metin kotasından bağımsız sayaçlar.
            "grafik_acik": _grafik_salteri_acik(),
            "grafik_olay": self.grafik_olay,
            "grafik_olay_karesiz": self.grafik_olay_karesiz,
            "grafik_kopru_hata": self.grafik_kopru_hata,
            "grafik_son_neden": self.grafik_son_neden,
            "grafik_gonderilen": self.grafik_gonderilen,
            "grafik_kuyruk": len(getattr(self, "_grafik_kuyruk", []) or []),
            "grafik_atlanan_hata": self.grafik_atlanan_hata,
            "grafik_atlanan_kota": self.grafik_atlanan_kota,
            "grafik_atlanan_baglam": self.grafik_atlanan_baglam,
            "grafik_ort_ms": (round(self.grafik_toplam_ms / self.grafik_kare_sayisi, 1)
                              if self.grafik_kare_sayisi else 0.0),
            "public_kuyruk": len(self._public_kuyruk),
            "public_kuyruk_tasmasi": self.public_kuyruk_tasmasi,
            "son_public_gonderim": self.son_public_gonderim,
        }

    def format_message(self, data: Dict) -> str:
        stock = data.get('stock_name', 'Bilinmiyor')
        timeframe = data.get('timeframe', '1h')
        pattern = data.get('pattern_name', 'Formasyon')
        state = data.get('state', 'ADAY_OLUSUYOR')
        # Raw failure/attempt/completed lifecycle states remain suppressed. A
        # separate notification-only alias is created only after a prior
        # confirmed breakout later closes back inside the formation band.
        if state in {"KIRILIM_DENEMESI", "BASARISIZ_KIRILIM", "FORMASYON_TAMAMLANDI"}:
            return ""
        if state in {"KIRILIM_TEYITLI", "RETEST_BASARILI", "KIRILIM_GECERSIZLESTI"}:
            return _format_lifecycle_alert(
                data, guncelleme=bool(data.get("_dm_bağlam_değişmedi"))
            )
        quality = data.get('confidence_score', 0)
        price = data.get('critical_price_level', 0)
        timestamp = data.get('timestamp', datetime.now())
        break_dir = data.get('break_dir', 0)
        upper = data.get('upper_now', price)
        lower = data.get('lower_now', price)
        contraction = data.get('contraction', None)
        retest_seen = data.get('retest_seen', True)
        upper_touches = data.get('upper_touches', None)
        lower_touches = data.get('lower_touches', None)
        age_bars = data.get('age_bars', None)
        mtf_destek = data.get('mtf_destek', False)

        tf_human = TF_HUMAN.get(timeframe, timeframe)
        emoji = PATTERN_EMOJI.get(pattern, "📈")
        q_comment = quality_comment(quality)
        q_emoji = quality_emoji(quality)

        if isinstance(timestamp, str):
            time_str = timestamp
        else:
            try:
                time_str = _tr_tarih(timestamp)
            except (AttributeError, ValueError, TypeError):
                # strftime desteklemeyen/tuhaf timestamp: metne düşür (dar kapsam).
                time_str = str(timestamp)

        # Daralma metni: "baya sıkışmış" gibi günlük konuşma dilinden çıkarıldı;
        # aynı bilgi kısa ve nötr veriliyor.
        contraction_str = ""
        if contraction is not None:
            pct = contraction * 100
            if pct >= 80:
                contraction_str = f"daralma %{pct:.0f} · sıkışma güçlü"
            elif pct >= 60:
                contraction_str = f"daralma %{pct:.0f} · sıkışıyor"
            elif pct >= 40:
                contraction_str = f"daralma %{pct:.0f}"
            else:
                contraction_str = f"daralma %{pct:.0f} · erken"

        temas_str = ""
        if upper_touches is not None and lower_touches is not None:
            temas_str = f"Temas üst/alt {upper_touches}/{lower_touches}"
        yas_str = f"{age_bars} bar" if age_bars else ""

        kalite_str = f"Kalite {quality:.0f} {q_emoji} ({q_comment})"
        # Kalite ve detay AYRI satırlarda: telefon ekranında hiçbir satırın
        # tek satıra sığması gerekiyor (eskiden tek satır ~90 karaktere çıkıp
        # üç satıra bölünüyordu).
        detay_str = " · ".join(p for p in (contraction_str, temas_str, yas_str,
                                           "4h destekliyor" if mtf_destek else "") if p)

        # Her mesaj aynı iskeleti paylaşır: başlık / olay / kalite / detay / seviye.
        # Rastgele şablon seçimi yok: aynı olay her zaman birebir aynı metni üretir.
        # Dil herkese açık kanal dili — kişisel asistan sesi ve tavsiye cümlesi yok.
        if state == "ADAY_OLUSUYOR":
            satirlar = [f"👀 {stock} {tf_human} · {pattern}",
                        "Formasyon oluşuyor",
                        kalite_str]
            if detay_str:
                satirlar.append(detay_str)
            satirlar.append(f"Bant: {_sayı(lower)} - {_sayı(upper)}")

        elif state == "GEOMETRI_ADAYI":
            satirlar = [f"{emoji} {stock} {tf_human} · {pattern}",
                        "Geometri oturuyor",
                        kalite_str]
            if detay_str:
                satirlar.append(detay_str)
            satirlar.append(f"Bant: {_sayı(lower)} - {_sayı(upper)} · olgunlaşma bekleniyor")

        elif state == "FORMASYON_TANIMLANDI":
            satirlar = [f"📋 {stock} {tf_human} · {pattern}",
                        "Formasyon tanımlandı",
                        kalite_str]
            if detay_str:
                satirlar.append(detay_str)
            satirlar.append(f"Üst: {_sayı(upper)} / Alt: {_sayı(lower)}")

        elif state == "SIKISMA_GUCLENIYOR":
            satirlar = [f"⚡ {stock} {tf_human} · {pattern}",
                        "Sıkışma güçleniyor",
                        kalite_str]
            if detay_str:
                satirlar.append(detay_str)
            satirlar.append(f"Bant: {_sayı(lower)} - {_sayı(upper)} · kırılım yakın")

        elif state == "KIRILIM_HAZIRLIGI":
            satirlar = [f"⚠️ {stock} {tf_human} · {pattern}",
                        "Kırılım hazırlığında",
                        kalite_str]
            if detay_str:
                satirlar.append(detay_str)
            satirlar.append(f"Kritik seviyeler: {_sayı(lower)} / {_sayı(upper)}")

        elif state == "KIRILIM_DENEMESI":
            direction = "yukarı" if break_dir == 1 else "aşağı" if break_dir == -1 else ""
            level = upper if break_dir == 1 else lower
            yon_eki = f"{direction} yönde " if direction else ""
            satirlar = [f"🔥 {stock} {tf_human} · {pattern}",
                        f"Kırılım denemesi · {yon_eki}{_sayı(level)} zorlanıyor",
                        kalite_str]
            if detay_str:
                satirlar.append(detay_str)
            satirlar.append("Kırılım gücü henüz düşük, teyit bekleniyor")

        elif state == "KIRILIM_ADAYI":
            direction = "YUKARI" if break_dir == 1 else "AŞAĞI" if break_dir == -1 else ""
            level = upper if break_dir == 1 else lower
            power = data.get('break_strength', quality)
            kapanis_yonu = "üstünde" if break_dir == 1 else "altında" if break_dir == -1 else "yakınında"
            baslik_eki = f"{direction} " if direction else ""
            # Eskiden iki şablon rastgele seçiliyordu (🚀 KIRIYOR / 💥 kırılım adayı);
            # aynı olay iki farklı metinle gidiyordu. Artık tek metin.
            satirlar = [f"🚀 {stock} {tf_human} · {pattern}",
                        f"{baslik_eki}kırılım adayı · {_sayı(level)} {kapanis_yonu} kapanış",
                        f"Kırılım gücü {power:.0f} {q_emoji} · teyit mumu bekleniyor"]

        elif state == "KIRILIM_TEYITLI":
            direction = "yukarı" if break_dir == 1 else "aşağı" if break_dir == -1 else ""
            level = _format_price(data.get('break_price', upper if break_dir == 1 else lower))
            yon = f"{direction} " if direction else ""
            event_line = f"Kapanışla teyitli {yon}kırılım"
            if level:
                event_line += f" · seviye {level}"
            satirlar = [f"✅ {stock} {tf_human} · {pattern}", event_line, kalite_str]
            if detay_str:
                satirlar.append(detay_str)

        elif state == "RETEST_BEKLENIYOR":
            level = data.get('break_price', price)
            satirlar = [f"⏳ {stock} {tf_human} · {pattern}",
                        f"Retest bekleniyor · {_sayı(level)}'e dönüş olabilir",
                        kalite_str]
            if detay_str:
                satirlar.append(detay_str)
            satirlar.append("Retest tutarsa yapı güçlenir")

        elif state == "RETEST_EDILIYOR":
            satirlar = [f"🔄 {stock} {tf_human} · {pattern}",
                        "Retest sürüyor · kırılan seviyeye geri dönüldü",
                        kalite_str]
            if detay_str:
                satirlar.append(detay_str)
            satirlar.append("Tutunursa devamı bekleniyor")

        elif state == "RETEST_BASARILI":
            direction = "yukarı" if break_dir == 1 else "aşağı" if break_dir == -1 else ""
            yon = f"{direction} kırılım" if direction else "kırılım"
            level = _format_price(data.get('break_price', price))
            event_line = f"Kapanışla başarılı retest · {yon}"
            satirlar = [f"🎯 {stock} {tf_human} · {pattern}", event_line]
            if level:
                satirlar.append(f"Seviye {level} korundu")
            satirlar.append(kalite_str)
            if detay_str:
                satirlar.append(detay_str)

        elif state == "FORMASYON_GECERSIZ":
            # Bu şablon bilerek korunuyor: ölü formasyonlar alarm akışından
            # kapı ile elenir (yalnız manuel/test gönderiminde buraya düşülür).
            reason = data.get('invalid_reason', 'Süre doldu veya bozuldu')
            satirlar = [f"⚪ {stock} {tf_human} · {pattern}",
                        f"Formasyon geçersiz · sebep: {reason}"]

        else:
            satirlar = [f"{emoji} {stock} {tf_human} · {pattern}",
                        f"Durum: {state}",
                        kalite_str,
                        f"Seviye: {_sayı(price)} · {time_str}"]

        # Kapanan mum satırı (P0): anlık olay mesajlarında "hangi mum kapandı?"
        # sorusu mesajın içinde cevaplanır. İzleme/digest akışına eklenmez
        # (orada yer bütçesi farklı ve o adaylar zaten kapanış özetiyle gider).
        mum_str = str(data.get('bar_metni') or "").strip()
        if state in ("KIRILIM_TEYITLI", "RETEST_BASARILI"):
            insert_at = 2
            if mum_str:
                satirlar.insert(insert_at, mum_str)
                insert_at += 1
            close_price = _format_price(
                data.get("candle_close_price", data.get("close_price"))
            )
            if close_price:
                satirlar.insert(insert_at, f"Mum kapanışı: {close_price}")

        msg = "\n".join(satirlar)

        # Domain başlıkları yalnızca formatlayıcının ürettiği gerçek bulgular
        # varsa görünür; boş bir Market Structure/OB/FVG/hacim başlığı eklenmez.
        domain_context = str(data.get("domain_context") or "").strip()
        if domain_context:
            msg += "\n\n" + domain_context

        # Eski kuyruk kayıtları için alanı okumaya devam et; yeni acil mesajlarda
        # izleme adayları bu alana eklenmez ve kapanış digest'inde tutulur.
        # Acil olay mesajına, ayrı alarm olarak henüz gönderilmemiş en fazla üç
        # kısa izleme adayı bağlamı eklenir. Adaylar kendi başlarına gönderilmez.
        watch_context = data.get("watch_context") or []
        context_lines = []
        for candidate in watch_context[:3]:
            if not isinstance(candidate, dict):
                continue
            candidate_stock = str(candidate.get("stock") or "?")
            candidate_tf = TF_HUMAN.get(candidate.get("timeframe"), candidate.get("timeframe", ""))
            candidate_pattern = str(candidate.get("pattern_name") or "formasyon")
            # State adı Türkçe ve tek kaynaktan (STATE_TR): eskiden
            # "SIKISMA_GUCLENIYOR" -> "sikisma gucleniyor" gibi Türkçe
            # karaktersiz/eksik metin basıyordu.
            _ham_state = str(candidate.get("state") or "").strip().upper()
            candidate_state = STATE_TR.get(
                _ham_state, _ham_state.title().replace("_", " ") or "izlemede")
            try:
                candidate_quality = float(candidate.get("quality") or 0)
                quality_suffix = f" · kalite {candidate_quality:.0f}"
            except (TypeError, ValueError):
                quality_suffix = ""
            context_lines.append(
                f"• {candidate_stock} {candidate_tf} {candidate_pattern}: {candidate_state}{quality_suffix}"
            )
        if context_lines:
            msg += "\n\n👀 Diğer izleme adayları\n" + "\n".join(context_lines)

        if state in ("KIRILIM_TEYITLI", "RETEST_BASARILI"):
            msg += "\n\n📌 Formasyon takibi · yatırım tavsiyesi değildir"
        return msg

    def send(self, data: Dict, kuyrukla: bool = True) -> bool:
        """Kapanışta teyitli alarm gönder; diğer lifecycle state'lerini reddet."""
        return self.send_with_prepare(data, before_send=None, kuyrukla=kuyrukla)

    def send_with_prepare(self, data: Dict, before_send=None, kuyrukla: bool = True) -> bool:
        """Gönderim kapısını geçince bağlamı hazırla, sonra tek kez gönder.

        ``before_send`` scanner'ın yalnızca gerçekten gönderilecek/yedeklenecek
        olay için taze domain çıktısı eklemesini sağlar. Repeat mührü olan eski
        olaylarda domain motorları hiç çalıştırılmaz. Cooldown/kap nedeniyle
        kuyruğa girecek yeni olayın bağlamı da kuyruk kaydına alınır.
        """
        stock = data.get("stock_name", "")
        pattern = data.get("pattern_name", "")
        timeframe = data.get("timeframe", "")
        state = str(data.get("state", "") or "").strip().upper()
        if state not in ALERT_STATES:
            self._son_engel = "state_disabled"
            logger.info("%s %s %s %s - state bildirim politikasında kapalı",
                        stock, pattern, timeframe, state)
            return False
        data["state"] = state
        if self.enabled and (self._delivery.already_done(data)
                             or self._delivery.is_cross_duplicate(data)
                             or self._delivery.is_story_duplicate(data)):
            # Hikâye tekrarı da kimlik tekrarı gibi NİHAİ reddir (acil
            # kuyruğa girmez): aynı hisse+yön hikâyesi o gün zaten anlatıldı.
            self._son_engel = "tekrar"
            self.engeller["tekrar"] += 1
            return False
        if data.get("formation_id") is not None:
            data["formation_id"] = str(data["formation_id"])

        def prepare_context():
            if not callable(before_send):
                return
            try:
                before_send(data)
            except Exception as exc:  # noqa: BLE001 - domain bağlamı alarmı düşürmesin
                data["domain_context"] = ""
                logger.warning("Bildirim bağlamı hazırlanamadı (%s %s): %s",
                               stock, timeframe, exc)

        if not self.can_send(
            stock, pattern, timeframe, state, formation_id=data.get("formation_id")
        ):
            engel = self._son_engel or "cooldown"
            # "tekrar" nihai reddir: mühürlü olay için ne DM kuyruğu ne de domain
            # işi. AMA public DM'den bağımsızdır: mühür "tekrar" dediğinde
            # `before_send` hiç çalışmadığı için public kuyruğu da dolmuyordu ve
            # gruba hiç gitmemiş olay (ağ hatası, bülten bütçesi, restart) bir
            # daha denenmiyordu. Yalnız public'te KAYDI OLMAYAN olay için bağlam
            # hazırlanır — yani motor bedeli yalnız gerçek boşlukta ödenir.
            if kuyrukla and self.enabled and engel != "tekrar":
                prepare_context()
                self._kuyruga_ekle(data, engel)
            elif engel == "tekrar":
                self._public_kurtar(data, prepare_context)
            logger.info("%s %s %s %s - %s, gönderilmiyor",
                        stock, pattern, timeframe, state, engel)
            return False

        prepare_context()
        # İçerik kapısı: bağlam ve kapanış önceki mesajla birebir aynıysa kopya
        # gitmez; yalnız kapanış/marj değiştiyse kısa güncelleme gider.
        if TELEGRAM_DM_DEGISIM_KAPISI and state in ALERT_STATES:
            durum = self._dm_degisim_durumu(data)
            data["_dm_bağlam_değişmedi"] = (durum == "guncelleme")
            if durum == "guncelleme":
                self.engeller["baglam_degismedi"] = int(self.engeller.get("baglam_degismedi", 0)) + 1
                logger.info("%s %s %s - bağlam önceki kartla aynı: yapı/bölge/hacim bloğu "
                            "kısaltıldı (%d kez bugün)", stock, timeframe, state,
                            self.engeller["baglam_degismedi"])
        ok = self._gonder(data)
        if ok:
            self._dm_imza_kaydet(data)
        return ok

    # --- grafik karesi teslimi (G4 / §4) -----------------------------------

    def grafik_kopru_hatasi(self, neden: str) -> None:
        """Tarayıcı-kare köprüsü hatasını say ve ilkini görünür biçimde logla."""
        neden_kisa = " ".join(
            redact_sensitive_text(str(neden), self.token).split()
        )[:120]
        with self._grafik_lck:
            self.grafik_kopru_hata += 1
            self.grafik_son_neden = neden_kisa
            sayi = self.grafik_kopru_hata
        if sayi == 1:
            # Bir kere WARNING: Render'ın varsayılan INFO loglarında teşhis görünür.
            logger.warning("grafik köprüsü ilk hatası: %s", neden_kisa)
        else:
            # Tekrarlayan tarama hataları sayılır, fakat log akışını doldurmaz.
            logger.debug("grafik köprüsü hatası #%d: %s", sayi, neden_kisa)

    def grafik_kuyruga_ekle(self, data: Dict, *, gonder: bool = False) -> int:
        """`data["grafik_verisi"]`ni gönderim kuyruğuna alır; eklenen kare sayısı.

        `gonder=True` (canlı akış, GÖRSEL-4): kuyruğa ekledikten sonra boşta
        bir gönderim işçisi başlatılır — kareler metnin hemen ardından gider ve
        tur sonu toplu gönderimi tekrar tetiklemez. Test/mock yolları bayrağı
        vermez; eski davranış (tur sonunda boşaltma) korunur.

        Neden burada: kart metni gitmiş oldu — kare ALARMIN devamıdır, ayrı olay
        değildir (§4: 1 olay = 1 metin + kareler). Şalter açıkken köprüden görsel
        alamayan olaylar sayılır; acil kuyruktan gelen kartlar bu sayımlara girmez.
        """
        if not isinstance(data, dict):
            return 0
        grafik_acik = _grafik_salteri_acik()
        kuyruktan = bool(data.get("_kuyruktan"))
        if grafik_acik and not kuyruktan:
            veri_sayac = data.get("grafik_verisi")
            goruntu_sayac = (veri_sayac.get("goruntular")
                             if isinstance(veri_sayac, dict) else None)
            with self._grafik_lck:
                self.grafik_olay += 1
                if not goruntu_sayac:
                    self.grafik_olay_karesiz += 1

        veri = data.get("grafik_verisi")
        if not isinstance(veri, dict):
            return 0
        goruntular = veri.get("goruntular") or []
        if not goruntular:
            return 0
        if data.get("_dm_bağlam_değişmedi"):
            # Kısa güncelleme kartı (§DM içerik kapısı): bağlam birebir aynıysa tek
            # satır gider. Aynı olayın 4 karesini yeniden göndermek „1 olay = 1 mesaj
            # + kareleri" kuralını şişirir ve medyayı yorar → kare eklenmez.
            self.grafik_atlanan_baglam += 1
            logger.debug("grafik: bağlam güncellemesi olduğu için kare eklenmedi (%s %s)",
                         data.get("stock_name"), data.get("timeframe"))
            return 0
        if not grafik_acik:
            return 0
        try:
            import grafik
            if not grafik.grafik_aktif_mi():
                return 0
        except Exception as hata:  # pragma: no cover - bağımlılık yoksa görsel yok
            logger.debug("grafik modülü hazır değil: %s", hata)
            return 0
        with self._grafik_lck:
            self._grafik_kuyruk.append({
                "anahtar": (str(data.get("stock_name") or ""),
                            str(data.get("timeframe") or ""),
                            str(data.get("state") or "")),
                "sembol": veri.get("sembol") or data.get("stock_name") or "",
                "goruntular": list(goruntular),
                "kota": int(veri.get("kota") or 0),
            })
            if veri.get("kota"):
                self.grafik_atlanan_kota += int(veri.get("kota"))
        if gonder:
            self._grafik_gonderim_baslat()
        return len(goruntular)

    def _grafik_gonderim_baslat(self) -> None:
        """Boşta işçi yoksa bir tane başlatır (her çağrı thread AÇMAZ).

        Neden tek işçi: medya gönderimi SIRALI olmalı — kullanıcının istediği
        akış "bir metin, ardından o metnin görselleri". Kuyruk boşalınca işçi
        çıkar; yeni kare geldiğinde yeni bir işçi başlar.
        """
        with self._grafik_gonderim_lck:
            mevcut = getattr(self, "_grafik_gonderim_isi", None)
            if mevcut is not None and mevcut.is_alive():
                return
            is_ = threading.Thread(target=self._grafik_gonderim_dongusu,
                                   name="grafik-gonderim", daemon=True)
            self._grafik_gonderim_isi = is_
            is_.start()

    def _grafik_gonderim_dongusu(self) -> None:
        """İşçi gövdesi: kuyruk boşalana kadar parça parça gönderir; sızdırmaz."""
        try:
            while True:
                ozet = self.grafikleri_gonder()
                if int(ozet.get("kare") or 0) == 0:
                    return
        except Exception as hata:  # noqa: BLE001 - metin/görsel akışını düşürmesin
            logger.warning("grafik arka plan gönderimi durdu: %s: %s",
                           type(hata).__name__, hata)

    def _public_kare_png(self, kare: Dict) -> str:
        """Kareyi PNG'ye yazar ve yolu döner (yoksa "").

        NEDEN AYRI ADIM: `grafik.kare_listesi()` yalnız ÇİZİLEBİLİR veri sözlüğü
        üretir; içinde `yol` alanı YOKTUR (dosya adı `grafik.kare_yolu()`nda
        uuid ile üretilir). Eski kod `kare["goruntu"]["yol"]` beklediği için hiç
        kare bulamıyor, public tarafına **hiç görüntü gitmiyordu** (0 sessizce
        dönüyordu). DM yolu (`notification_delivery.prepare`) her zaman
        `grafik.kareyi_yaz()` çağırır; public de aynı sözleşmeyi kullanmalı.
        """
        goruntu = ((kare or {}).get("goruntu") or {}) if isinstance(kare, dict) else {}
        hazir = str(goruntu.get("yol") or "").strip()
        if hazir and os.path.exists(hazir):        # eski/elle verilmiş yol
            return hazir
        if not goruntu:
            return ""
        import grafik
        tf = str((kare or {}).get("tf") or "").strip() or "1h"
        yol, _meta = grafik.kareyi_yaz(goruntu, tf)
        return str(yol or "")

    def public_grafik_gonder(self, kayit: Dict) -> int:
        """Public kaydının karelerini gruba TEK ALBÜM gönderir; `(gönderilen)`.

        2026-10-22 kararı: public görseli **1 kare + üst zaman dilimi** karesidir
        (DM 4 kare alır). Kareler bildirim anında üretilir, burada çizilip
        gönderilir; dosya her durumda silinir. Görsel hiçbir koşulda metni/
        bülteni düşürmez.

        Neden albüm: Telegram ayrı `sendPhoto` mesajlarını — aralarındaki süre
        ne kadar kısa olursa olsun — ASLA birleştirmez; iki kare ancak tek
        `sendMediaGroup` çağrısıyla tek albüm görünür (zamanlama/pacing
        meselesi değil, çağrı biçimi meselesi). Eski kod kareyi çizip hemen
        `foto_gonder` çağırdığı (araya `_public_pace` + ikinci çizim girdiği)
        için grupta hep iki ayrı mesaj görünüyordu. DM yolu
        (`grafik_toplu_gonder` / `notification_delivery.send_images`) baştan
        beri albüm gönderir; public artık aynı sözleşmeyi kullanır: ÖNCE
        bütün kareler çizilir, SONRA tek seferde gönderilir. Tek kare
        kalırsa (üst TF yok ya da biri çizilemedi) albüm 2–10 öğe istediği
        için `sendPhoto`'ya düşülür; albüm reddedilirse kare kaybı olmaması
        için DM'deki gibi kare kare yeniden denenir.
        """
        if not isinstance(kayit, dict):
            return 0
        anahtar = self._public_kuyruk_anahtari(kayit)
        veri = self._public_grafik.pop(anahtar, None)
        if not veri:
            return 0
        hedef = str(getattr(self, "public_chat_id", "") or "").strip()
        if not hedef or not getattr(self, "public_enabled", False):
            return 0
        try:
            from transport.telegram import foto_gonder, medya_grubu_gonder
        except Exception:  # pragma: no cover - taşıma yoksa görsel de yok
            return 0
        tf = TF_KISA.get(str(kayit.get("timeframe") or "").lower(),
                         str(kayit.get("timeframe") or ""))
        bas = f"{str(kayit.get('stock_name') or '').upper()} {tf}".strip()
        desen = str(kayit.get("pattern_name") or "").strip()
        paketler = []                     # (yol, caption) — olay başına TEK albüm
        for sira, kare in enumerate(list(veri.get("goruntular") or [])[:2]):
            kare_tf = TF_KISA.get(str((kare or {}).get("tf") or "").lower(),
                                  str((kare or {}).get("tf") or ""))
            try:
                yol = self._public_kare_png(kare)
            except Exception as hata:  # noqa: BLE001 - görsel akışı düşürmesin
                yol = ""
                logger.warning("public karesi çizilemedi (%s %s): %s: %s",
                               kayit.get("stock_name"), kare_tf,
                               type(hata).__name__, hata)
            if not yol:
                self.public_grafik_hatasi += 1
                self.grafik_atlanan_hata += 1
                self.grafik_son_neden = "public: kare üretilemedi"
                continue
            caption = (f"{bas} · {desen}" if sira == 0 and desen
                       else f"{bas} · {kare_tf} üst zaman dilimi")
            paketler.append((yol, caption[:1024]))
        if not paketler:
            return 0

        def _tek_gonder(yol, caption) -> bool:
            try:
                self._public_pace()
                ok, aciklama = foto_gonder(yol, chat_id=hedef, notifier=self,
                                           caption=caption)
                if ok:
                    self.public_grafik_gonderilen += 1
                    self.grafik_gonderilen += 1
                    return True
                self.public_grafik_hatasi += 1
                logger.warning("public karesi gönderilemedi: %s",
                               redact_sensitive_text(str(aciklama), self.token)[:160])
            except Exception as hata:  # noqa: BLE001 - görsel akışı düşürmesin
                self.public_grafik_hatasi += 1
                logger.debug("public karesi hatası: %s: %s", type(hata).__name__, hata)
            return False

        gonderilen = 0
        try:
            if len(paketler) == 1:
                gonderilen = 1 if _tek_gonder(*paketler[0]) else 0
            else:
                # Pacing albümden BİR KEZ önce; kareler arasına bekleme girmez.
                self._public_pace()
                try:
                    ok, aciklama = medya_grubu_gonder(
                        [y for y, _c in paketler],
                        captions=[c for _y, c in paketler],
                        chat_id=hedef, notifier=self)
                except Exception as hata:  # noqa: BLE001 - taşıma zaten yutuyor
                    ok, aciklama = False, type(hata).__name__
                if ok:
                    gonderilen = len(paketler)
                    self.public_grafik_gonderilen += len(paketler)
                    self.grafik_gonderilen += len(paketler)
                else:
                    logger.warning(
                        "public albümü gönderilemedi, kare kare deneniyor: %s",
                        redact_sensitive_text(str(aciklama), self.token)[:160])
                    for yol, caption in paketler:
                        gonderilen += 1 if _tek_gonder(yol, caption) else 0
        finally:
            for yol, _c in paketler:
                try:
                    os.remove(yol)
                except (OSError, TypeError):
                    pass
        return gonderilen

    def grafik_dosya_gonder(self, yol, caption: str = "") -> tuple:
        """Bir PNG'yi DM'e gönderir ve dosyayı SİLER (§4); `(ok, aciklama)`.

        Neden ayrı metod: `/grafik` komutu kareyi kullanıcının kendisi istediği için
        sıraya bekletmeden gönderir; alarm kuyruğu da aynı gönderimi kullanır. Dosya
        her durumda silinir (kalan tek şey disk çöpü olurdu), geçici yol
        `grafik.kare_yolu`ndan gelir — `_pkg.DATA_DIR` dışı.
        """
        ok, aciklama = False, "gönderim denenmedi"
        try:
            if not self.enabled:
                return False, "Telegram notifier pasif (token/chat_id env'de yok)"
            # Fotoğraf hedefi gerçekten DM olmalı. CHAT_ID yanlışlıkla public
            # grupla eşlenmişse metin politikasına dokunmadan görseli reddet.
            try:
                dm_kimligi = int(str(self.chat_id).strip()) > 0
            except (ValueError, TypeError):
                dm_kimligi = False
            public_hedef = str(getattr(self, "public_chat_id", "") or "").strip()
            if not dm_kimligi or (public_hedef and public_hedef == str(self.chat_id).strip()):
                self.grafik_atlanan_hata += 1
                return False, "görseller yalnız DM'e gönderilir; hedef private DM değil"
            from transport.telegram import foto_gonder

            self._grafik_pace()
            ok, aciklama = foto_gonder(yol, notifier=self, caption=caption)
            self._son_grafik_ts = time.monotonic()
            if ok:
                self.grafik_gonderilen += 1
            else:
                self.grafik_atlanan_hata += 1
                logger.warning("grafik karesi gönderilemedi: %s",
                               redact_sensitive_text(str(aciklama), self.token)[:160])
        except Exception as hata:  # noqa: BLE001 - görsel hiçbir akışı düşürmesin
            ok, aciklama = False, f"{type(hata).__name__}"[:120]
            self.grafik_atlanan_hata += 1
        finally:
            try:
                os.remove(yol)
            except (OSError, TypeError):
                pass
        return ok, aciklama

    def _grafik_pace(self) -> None:
        """Kareler arası kısa bekleme: §4 mevcut pacing yardımcısını kullanır.

        `public_min_aralik_sn` yeniden okunur ama kendi zaman damgasımız tutulur:
        grup bülteni ile görseller birbirinin temposunu bozmasın.
        """
        try:
            ara = float(self.public_min_aralik_sn or 0)
        except (TypeError, ValueError):
            ara = 0.0
        if ara <= 0 or self._son_grafik_ts is None:
            return
        bekle = ara - (time.monotonic() - self._son_grafik_ts)
        if bekle > 0:
            time.sleep(min(bekle, 5.0))

    def grafikleri_gonder(self, sinir: Optional[int] = None) -> Dict:
        """Kuyruğu boşaltır: kare → PNG → `sendPhoto` (tarama turu sonunda çağrılır).

        Sıra §4'teki gibi: önce alarm METNİ gitmiştir; kareler onun altında, olay
        sırasında ve tek tek gider (`sendMediaGroup` v2'de, §4). Görsel hiçbir
        koşulda metni/alamı engellemez: her hata sayılır ve sıradaki kareye geçilir.
        Üretilen geçici PNG gönderimden sonra silinir (§4).
        """
        with self._grafik_gonderim_lck:
            kuyruk = list(self._grafik_kuyruk)
            self._grafik_kuyruk.clear()
        ozet = {"gonderilen": 0, "hata": 0, "kare": 0, "sure_ms": 0, "atlanan": 0}
        if not kuyruk or not self.enabled:
            return ozet
        try:
            import grafik  # noqa: F401 - yoksa katman zaten çalışmaz
        except Exception as hata:  # pragma: no cover - matplotlib yoksa görsel yok
            logger.warning("grafik teslimi kapatıldı (%s): %s", type(hata).__name__, hata)
            ozet["atlanan"] = sum(len(k["goruntular"]) for k in kuyruk)
            self.grafik_atlanan_hata += ozet["atlanan"]
            return ozet
        if not grafik.disk_uygun_mu():
            logger.warning("diskte %d MB altında yer var: kareler üretilmedi",
                           grafik.DISK_MIN_BOS_MB)
            ozet["atlanan"] = sum(len(k["goruntular"]) for k in kuyruk)
            self.grafik_atlanan_hata += ozet["atlanan"]
            return ozet
        if not self._grafik_supuruldu:
            self._grafik_supuruldu = True
            silinen = grafik.bayat_kareleri_supur()
            if silinen:
                logger.info("grafik: %d bayat kare dosyası silindi", silinen)
        # `sinir` KARE sayısısıdır, OLAY sayısı değil (bir olay 4 kare taşıyabilir;
        # ilk sürümde `len(kuyruk)` kullanıldığı için ikinci kare kuyrukta kalıyordu).
        limit = -1 if sinir is None else max(0, int(sinir))
        kalan = []
        for olay in kuyruk:
            paketler = []          # (yol, caption, meta) — olay başına TEK albüm
            for kare in olay["goruntular"]:
                if 0 <= limit <= ozet["kare"] + len(paketler):
                    kalan.append({"olay": olay, "kare": kare})
                    continue
                yol, meta = None, {}
                try:
                    yol, meta = grafik.kareyi_yaz(kare.get("goruntu") or {},
                                                   kare.get("tf") or "1h")
                except Exception as hata:  # noqa: BLE001 - görsel alarmı düşürmesin
                    logger.warning("grafik: kare üretilemedi (%s %s): %s",
                                   olay["sembol"], kare.get("tf"), hata)
                    self.grafik_atlanan_hata += 1
                    ozet["hata"] += 1
                    ozet["kare"] += 1
                    continue
                if not yol:
                    # Çizim reddi (kadraj/uyuşmazlık): meta'da nedeni var, sessiz olmasın.
                    logger.info("grafik: kare çizilmedi (%s %s): %s", olay["sembol"],
                                kare.get("tf"), " · ".join(meta.get("uyarilar") or []))
                    self.grafik_atlanan_hata += 1
                    ozet["hata"] += 1
                    ozet["kare"] += 1
                    continue
                paketler.append((yol, _grafik_basligi(olay, kare, meta), meta))
            ozet["kare"] += len(paketler)
            if not paketler:
                continue
            sonuc = self.grafik_toplu_gonder([(y, c) for y, c, _m in paketler])
            for (_y, _c, meta), ok in zip(paketler, sonuc):
                # Sayaçları `grafik_toplu_gonder` tutuyor; burada yalnız tur özeti ve süre.
                if ok:
                    self.grafik_kare_sayisi += 1
                    self.grafik_toplam_ms += float(meta.get("sure_ms") or 0)
                    ozet["gonderilen"] += 1
                    ozet["sure_ms"] += int(meta.get("sure_ms") or 0)
                else:
                    ozet["hata"] += 1
        if kalan:
            with self._grafik_gonderim_lck:
                for parca in reversed(kalan):
                    self._grafik_kuyruk.insert(0, {
                        "anahtar": parca["olay"]["anahtar"], "sembol": parca["olay"]["sembol"],
                        "goruntular": [parca["kare"]], "kota": 0})
            ozet["atlanan"] = len(kalan)
        return ozet

    def grafik_toplu_gonder(self, paketler) -> list:
        """`[(yol, caption)]` → kare başına başarı listesi; geçici dosyaları SİLER.

        Tek kare → `sendPhoto` (`grafik_dosya_gonder`). 2–10 kare → TEK albüm
        (`sendMediaGroup`): kareler arasına metin girmez. Albüm reddedilirse kareler
        tek tek yeniden denenir (kare kaybı olmasın). Her yol, sonuçtan bağımsız
        olarak bu fonksiyonda silinir (§4).
        """
        paketler = [(y, c) for y, c in (paketler or []) if y]
        sonuc = [False] * len(paketler)
        try:
            if not paketler:
                return sonuc
            if not self.enabled:
                self.grafik_atlanan_hata += len(paketler)
                return sonuc
            try:
                dm_kimligi = int(str(self.chat_id).strip()) > 0
            except (ValueError, TypeError):
                dm_kimligi = False
            public_hedef = str(getattr(self, "public_chat_id", "") or "").strip()
            if not dm_kimligi or (public_hedef and public_hedef == str(self.chat_id).strip()):
                self.grafik_atlanan_hata += len(paketler)
                logger.warning("grafik: görseller yalnız DM'e gönderilir; hedef private DM değil")
                return sonuc
            if len(paketler) == 1:
                ok, aciklama = self.grafik_dosya_gonder(paketler[0][0], caption=paketler[0][1])
                sonuc[0] = ok
                return sonuc
            from transport.telegram import medya_grubu_gonder

            self._grafik_pace()
            ok, aciklama = medya_grubu_gonder(
                [y for y, _c in paketler], captions=[c for _y, c in paketler],
                notifier=self)
            self._son_grafik_ts = time.monotonic()
            if ok:
                self.grafik_gonderilen += len(paketler)
                return [True] * len(paketler)
            logger.warning("grafik albümü gönderilemedi, kare kare deneniyor: %s",
                           redact_sensitive_text(str(aciklama), self.token)[:160])
            # Yedek: albüm reddedildiyse kareleri tek tek dene (kare kaybı olmasın).
            # `grafik_dosya_gonder` dosyayı siler; önce kopya gerekmez, yalnız bir kez denenir.
            for k, (yol, caption) in enumerate(paketler):
                sonuc[k] = self._tekil_gonder_dosyasiz(yol, caption)
            return sonuc
        finally:
            for yol, _c in paketler:
                try:
                    os.remove(yol)
                except (OSError, TypeError):
                    pass

    def _tekil_gonder_dosyasiz(self, yol, caption: str) -> bool:
        """`grafik_dosya_gonder` ile aynı, ama dosyayı silmez (toplu çağıran siler)."""
        try:
            from transport.telegram import foto_gonder

            self._grafik_pace()
            ok, aciklama = foto_gonder(yol, notifier=self, caption=caption)
            self._son_grafik_ts = time.monotonic()
            if ok:
                self.grafik_gonderilen += 1
            else:
                self.grafik_atlanan_hata += 1
                logger.warning("grafik karesi gönderilemedi: %s",
                               redact_sensitive_text(str(aciklama), self.token)[:160])
            return bool(ok)
        except Exception as hata:  # noqa: BLE001 - görsel hiçbir akışı düşürmesin
            self.grafik_atlanan_hata += 1
            logger.debug("grafik yedek gönderimi: %s", type(hata).__name__)
            return False

    def _gonder(self, data: Dict) -> bool:
        # İçerik kopyası kapısı: mühür kimliğe bağlı olduğu için kimlik değişince
        # birebir aynı kart yeniden gidebiliyordu. Gönderimden ÖNCE bakılır.
        if self._kart_kopyasi_mi(data):
            self.engeller["tekrar"] += 1
            self._son_engel = "tekrar"
            logger.info("%s %s %s - kart birebir aynı, kopya gönderilmiyor",
                        data.get("stock_name"), data.get("timeframe"), data.get("state"))
            return False
        if self.enabled:
            try:
                ok = self._delivery.submit(data)
            except Exception as exc:
                logger.error("Bildirim kalıcı kuyruğa alınamadı: %s", type(exc).__name__)
                return False
            if ok:
                self._kart_imza_kaydet(data)
            return ok
        ok = self._gonder_metin(data)
        if ok:
            self._kart_imza_kaydet(data)
        return ok

    def teslimleri_dene(self) -> int:
        return self._delivery.flush() if self.enabled else 0

    def teyit_teslim_edildi_mi(self, formation_id) -> bool:
        """Aynı formation_id'li KIRILIM_TEYITLI teslim kuyruğunda gerçekten gitti mi?"""
        return bool(self._delivery.confirmation_delivered(formation_id))

    def _gonder_metin(self, data: Dict) -> bool:
        """can_send kapısı geçildikten sonraki gerçek gönderim (kuyruk bunu çağırır)."""
        stock = data.get('stock_name', '')
        pattern = data.get('pattern_name', '')
        timeframe = data.get('timeframe', '')
        state = data.get('state', '')

        message = data.get("_delivery_message") or self.format_message(data)
        # Güvenlik: 4096 kr üzeri istek Telegram'da 400 döner ve mesaj tamamen
        # kaybolurdu. Artık sınırına kırpılır ve logda iz bırakır.
        if len(message) > _PUBLIC_MAX_METIN:
            logger.warning("Alarm mesajı Telegram sınırını aştı (%d kr) → kırpıldı", len(message))
            message = _kirp(message)
        elif TELEGRAM_ALERT_MAX_KARAKTER and len(message) > TELEGRAM_ALERT_MAX_KARAKTER:
            logger.warning("Alarm kartı hedefin üstünde: %s %s %s · %d kr (hedef %d)",
                           stock, timeframe, state, len(message), TELEGRAM_ALERT_MAX_KARAKTER)
        asiyan = [satir for satir in message.splitlines() if _satir_px(satir) > (_px_butce() or 1e9)]
        if asiyan:
            logger.warning("Alarm kartında %d satır telefon bütçesini aşıyor (%s %s)",
                           len(asiyan), stock, timeframe)

        if not self.enabled:
            logger.info(f"[MOCK TELEGRAM {state}]\n{message}\n")
            if self.should_send_to_public(data):
                # Public hedef artık bültenle gider; mock modda yalnız görünürlük.
                logger.info(f"[MOCK PUBLIC {state}] {stock} {timeframe} bültene eklenecek")
            key = self._cooldown_key(stock, pattern, timeframe, state)
            self.last_sent[key] = datetime.now(ISTANBUL_TZ)
            self._gonderim_kaydet()
            self.gonderilen_alarm += 1
            self._gonderim_sagligi_kaydet(basari=True)
            self._tek_seferlik_isle(
                stock, pattern, timeframe, state, formation_id=data.get("formation_id")
            )
            return True

        try:
            import requests
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {'chat_id': self.chat_id, 'text': message}
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info(f"Telegram gönderildi: {stock} {pattern} {state}")
                key = self._cooldown_key(stock, pattern, timeframe, state)
                self.last_sent[key] = datetime.now(ISTANBUL_TZ)
                self._cooldown_kaydet()
                self._gonderim_kaydet()
                self.gonderilen_alarm += 1
                self._gonderim_sagligi_kaydet(basari=True)
                # Tek-seferlik mühür: DM ve public hedef aynı kapıdan geçtiği
                # için her ikisi de tekilleşir.
                self._tek_seferlik_isle(
                    stock, pattern, timeframe, state, formation_id=data.get("formation_id")
                )
                # NOT: Public (grup) gönderimi burada YAPILMAZ. Olaylar tarama
                # turu boyunca `public_kuyruk()` ile toplanır ve tur sonunda tek
                # bültende gider; DM başarısız olsa bile grup yayını etkilenmez.
                # Prepared media is sent synchronously by the durable FIFO.
                # This method only acknowledges the text component.
                return True
            else:
                ipucu = telegram_hata_ipucu(resp.status_code,
                                                 redact_sensitive_text(resp.text, self.token))
                logger.error(f"Telegram hatası: {resp.text} | {ipucu}")
                self._gonderim_sagligi_kaydet(basari=False, hata=ipucu)
                return False
        except Exception as e:
            logger.error(f"Telegram gönderim hatası: {e}")
            self._gonderim_sagligi_kaydet(basari=False, hata=f"istek hatasi: {e}")
            return False


