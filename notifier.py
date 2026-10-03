# --- TELEGRAM NOTIFIER - İNSANLAŞTIRMA V2 + KANAL MODELİ ---
# Tek sistem, gürültü azaltma, public kanal desteği

import os
import logging
import re
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List

from config import (ACTIVE_STOCKS, DATA_DIR, ISTANBUL_TZ, TELEGRAM_MAX_MESAJ_SAAT,
                    TELEGRAM_MAX_MESAJ_GUN,
                    ACIL_KUYRUK_LIMIT, ACIL_KUYRUK_TTL_DK, ALERT_STATES, WATCH_STATES,
                    TERMINAL_TAZE_BAR,
                    ALERT_MIN_QUALITY, ALERT_MIN_QUALITY_GLOBAL,
                    PUBLIC_MAX_MESAJ_SAAT, PUBLIC_MAX_MESAJ_GUN, PUBLIC_MIN_ARALIK_SN,
                    PUBLIC_MIN_QUALITY_TF)
# Watch adaylarının state'ini Türkçe basmak için TEK KAYNAK sözlük (reporting
# katmanı da aynısını kullanır; böylece alarm mesajı ile /panel aynı dili konuşur).
from reporting.format import STATE_TR
# Günlük public durumu (bütçe sayaçları + gönderilememiş kuyruk) restart'ta
# korunsun diye kalıcılık katmanı kullanılır (canlı denetim: ikisi de kayboluyordu).
from state import persistence as _state_persistence

logger = logging.getLogger(__name__)


def _istanbul(dt: datetime) -> datetime:
    """Naive datetime'ı İstanbul saatine sabitler.

    Neden: süreç UTC'de çalışsa bile gün/saat sınırları BIST saatine göre
    hesaplanmalı (Render'da TZ verilmezse günlük kota gece 03:00'te sıfırlanıyordu).
    Eski kayıtlarda (telegram_kap.json / Supabase) naive ISO damgalar var; onları
    da buradan geçirerek TypeError riskini ortadan kaldırıyoruz.
    """
    if dt.tzinfo is None:
        return ISTANBUL_TZ.localize(dt)
    return dt.astimezone(ISTANBUL_TZ)

PATTERN_EMOJI = {
    "Yükselen Üçgen": "🔺",
    "Alçalan Üçgen": "🔻",
    "Simetrik Üçgen": "🔷",
    "Yükselen Kama": "📐⬆️",
    "Alçalan Kama": "📐⬇️",
    "Boğa Bayrağı": "🚩🐂",
    "Ayı Bayrağı": "🚩🐻",
    "Boğa Flaması": "🎏🐂",
    "Ayı Flaması": "🎏🐻",
}

KRITIK_STATELER = (
    "KIRILIM_ADAYI", "KIRILIM_TEYITLI", "RETEST_BASARILI", "FORMASYON_TAMAMLANDI",
    "KIRILIM_DENEMESI", "BASARISIZ_KIRILIM",
)

TF_HUMAN = {
    "1h": "saatlik",
    "2h": "2 saatlik",
    "4h": "4 saatlik",
    "1d": "günlük",
}

def quality_comment(q: float) -> str:
    if q >= 85:
        return "çok güçlü"
    elif q >= 75:
        return "güçlü"
    elif q >= 65:
        return "orta"
    else:
        return "zayıf"

def _yon_metni(break_dir) -> str:
    """Kırılım yönünü Türkçe tek kelimeye çevirir (özet satırları için)."""
    if break_dir == 1:
        return "yukarı"
    if break_dir == -1:
        return "aşağı"
    return "belirsiz"


def quality_emoji(q: float) -> str:
    if q >= 85:
        return "⭐⭐⭐"
    elif q >= 75:
        return "⭐⭐"
    elif q >= 65:
        return "⭐"
    else:
        return "〰️"


# Türkçe ay kısaltmaları: strftime('%b') sistem yerelinden İngilizce basıyordu
# ("02 Oct 20:05"); mesajların tamamı Türkçe olduğu için tarih de Türkçe olmalı.
_AY_KISALTMALARI = {
    1: "Oca", 2: "Şub", 3: "Mar", 4: "Nis", 5: "May", 6: "Haz",
    7: "Tem", 8: "Ağu", 9: "Eyl", 10: "Eki", 11: "Kas", 12: "Ara",
}


def _tr_tarih(dt: datetime) -> str:
    """Kısa Türkçe tarih: '02 Eki 20:05'. Gün/ay/saat hizalı kalır (telefonda düzgün görünür)."""
    return f"{dt.day:02d} {_AY_KISALTMALARI.get(dt.month, '')} {dt:%H:%M}"


def _public_izleme_adaylari(aktif: List[Dict], adet: int = 5, haric=None) -> List[Dict]:
    """Sabah notu için izleme listesi: hâlâ WATCH_STATES'te olan adaylar.

    Kaynak DM tarafındaki kuyruk değil, o anki canlı durumdur; kaliteye göre
    sıralanır ve alan adları panel/kuyruk sözlüğüne çevrilir.
    `haric`: aynı mesajda zaten yazılmış hisseler (örn. ⚡ Sıkışan satırı) —
    tek mesajda aynı hisse iki kez görünmesin.
    """
    haric = set(haric or ())
    adaylar = [f for f in aktif or []
               if isinstance(f, dict) and str(f.get('state') or '') in WATCH_STATES
               and f.get('stock_name') not in haric]
    try:
        adaylar.sort(key=lambda f: float(f.get('confidence_score') or 0), reverse=True)
    except (TypeError, ValueError):
        pass
    sonuc = []
    for f in adaylar[:adet]:
        sonuc.append({"stock": f.get("stock_name"), "timeframe": f.get("timeframe"),
                      "pattern_name": f.get("pattern_name"),
                      "quality": f.get("confidence_score")})
    return sonuc

# Zaman dilimi -> bir bar kaç saat? Tek-seferlik mühürün bayatma süresi buna
# göre ölçeklenir (bkz. _muhur_ttl_saat).
_TF_BAR_SAAT = {"1h": 1, "2h": 2, "4h": 4, "1d": 24}


def _muhur_ttl_saat(timeframe: str) -> float:
    """Tek-seferlik mühürün kaç saat geçerli olduğu.

    NEDEN VAR: motor bitmiş (terminal) bir formasyonu TERMINAL_TAZE_BAR bar
    boyunca "taze" sayar ve raporlamaya devam eder (ölü formasyon
    filtresindeki istisna — "az önce tamamlandı" bilgisi kaçmasın diye).
    Mühür gün bazlı bayatıyorsa bu pencereden taşan formasyon sonraki
    gün/taramada TEKRAR bildiriliyordu:
        1 günlük grafikte 3 bar = 3 gün  -> aynı haber 3 gün daha basılıyordu
        4 saatlikte     3 bar = 12 saat -> ertesi sabah yine basılıyordu
    TTL artık bar süresine göre ölçekleniyor: 3 bar + 1 saat pay.
    Böylece mühür her zaman motorun "aynı olay" penceresini kapsar.
    """
    bar_saat = _TF_BAR_SAAT.get(str(timeframe or "").lower())
    if bar_saat is None:
        return 24.0          # bilinmeyen TF: eski gün bazlı davranış
    return TERMINAL_TAZE_BAR * bar_saat + 1


def _env_temizle(deger) -> str:
    if deger is None:
        return ""
    s = str(deger).strip()
    while len(s) >= 2 and ((s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'")):
        s = s[1:-1].strip()
    return s.strip()

_PUBLIC_MAX_METIN = 4000     # Telegram sınırı 4096; kanal/grup yolu da kırpmalı


def _kirp(metin: str, sinir: int = _PUBLIC_MAX_METIN) -> str:
    """Public gönderim için Telegram sınırına sığdırır (eskiden kırpma yoktu →
    uzun özet 400 alabiliyordu)."""
    metin = str(metin or "")
    if len(metin) <= sinir:
        return metin
    return metin[: sinir - 40].rstrip() + "\n\n… (mesaj sınırı nedeniyle kesildi)"


# Public grup için SADE durum etiketleri: iç izleme notları ("teyit bekleniyor",
# "retest tutarsa yapı güçlenir") gruba taşınmaz.
PUBLIC_STATE_ETIKET = {
    "KIRILIM_TEYITLI": "kırılım teyitli",
    "RETEST_BASARILI": "retest başarılı",
    "FORMASYON_TAMAMLANDI": "tamamlandı",
}


def _yon_kisa(break_dir) -> str:
    if break_dir == 1:
        return "yukarı"
    if break_dir == -1:
        return "aşağı"
    return ""


def token_bicimi_uygun_mu(token: str) -> bool:
    t = _env_temizle(token)
    if not t:
        return False
    if ":" not in t:
        return False
    parcalar = t.split(":", 1)
    if len(parcalar) != 2:
        return False
    ilk, ikinci = parcalar
    if not ilk.isdigit():
        return False
    if len(ilk) < 5:
        return False
    if len(ikinci) < 20:
        return False
    if not re.match(r"^[A-Za-z0-9_\-]+$", ikinci):
        return False
    return True

def telegram_hata_ipucu(status_code: int, response_text: str = "") -> str:
    txt = (response_text or "").lower()
    if status_code == 401:
        return (
            "Token geçersiz veya iptal edilmiş (401). "
            "@BotFather'dan token'ı tam kopyala, Render → Environment → TELEGRAM_BOT_TOKEN'ı güncelle. "
            "Sızdıysa /revoke ile iptal edip yeni bot aç."
        )
    if status_code == 404:
        return (
            "Bot bulunamadı veya endpoint yanlış (404). "
            "Token doğru mu? URL https://api.telegram.org/bot<token>/... olmalı. "
            "BotFather'da bot silinmiş olabilir."
        )
    if "chat not found" in txt:
        return (
            "Sohbet bulunamadı (chat not found). "
            "Kendi botuna Telegram'da /start yaz, sonra tekrar dene. "
            "chat_id yanlışsa @userinfobot'tan Id'yi tekrar al."
        )
    if "bot was blocked" in txt or "blocked" in txt:
        return (
            "Bot engellenmiş (bot was blocked): Telegram'da bot sohbetinde Unblock yap, "
            "engellenmiş olabilir, /start ile yeniden başlat."
        )
    if status_code == 400:
        return (
            "İstek hatalı (400). chat_id sayı mı, mesaj boş mu? "
            "@userinfobot'tan Id'yi tekrar al, grup için -100... ile başlayan id kullan. "
            "Sohbet bulunamadı (chat not found) ise kendi botuna /start yaz. "
            "Mesaj çok uzun veya biçim hatalı olabilir."
        )
    if status_code == 403:
        return (
            "Bot bu sohbete mesaj gönderemiyor (403). "
            "Kendi botuna Telegram'da bir kez /start yaz, engeli kaldır, engellenmiş olabilir. "
            "Grup ise botu gruba ekle ve admin yap. chat not found ise botla hiç konuşmamışsındır. "
            "Unblock yapman gerekebilir."
        )
    if status_code == 409:
        return (
            "Aynı token'ı iki yer aynı anda dinliyor (409 Conflict). "
            "Termux/PC'de açık kalan ikinci kopyayı kapat, Render'da tek instance çalışmalı. "
            "getUpdates aynı anda iki süreçten çağrılamaz."
        )
    return f"Telegram hatası HTTP {status_code}: {response_text[:200]}"


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
        self.engeller = {"cooldown": 0, "gunluk_kap": 0, "saatlik_kap": 0, "tekrar": 0}
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
        self._cooldown_dosya = os.path.join(DATA_DIR, "telegram_soguma.json")
        self._kap_dosya = os.path.join(os.path.dirname(self._cooldown_dosya), "telegram_kap.json")
        self._cooldown_yukle()
        self._kap_yukle()
        # --- engellenen acil olay kuyruğu (Batch 5 / B4) ---
        # Neden: cooldown/kap yüzünden gönderilemeyen teyitli kırılım gibi acil
        # olaylar tamamen kayboluyordu; artık engel kalkınca gönderilir.
        self._acil_kuyruk: List[dict] = []  # en eski kayıt önce
        self._kuyruk_dosya = os.path.join(os.path.dirname(self._cooldown_dosya),
                                          "telegram_acil_kuyruk.json")
        self.kuyruk_gonderildi = 0
        self.kuyruk_zaman_asimi = 0
        self.kuyruk_tasmasi = 0
        self._kuyruk_yukle()
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
        self._son_alert_dosya = os.path.join(DATA_DIR, "telegram_son_alerts.json")
        self._son_alert_yukle()

        try:
            from config import PUBLIC_MIN_QUALITY, PUBLIC_STATES, PUBLIC_SIKISMA_MIN_CONTRACTION
            self.public_min_quality = PUBLIC_MIN_QUALITY
            self.public_states = set(PUBLIC_STATES)
            self.public_sikisma_min = PUBLIC_SIKISMA_MIN_CONTRACTION
        except Exception:
            self.public_min_quality = 0
            self.public_states = {"FORMASYON_TAMAMLANDI", "RETEST_BASARILI",
                                  "KIRILIM_TEYITLI"}
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
        self._public_lck = threading.Lock()
        self._public_saatlik: List[datetime] = []
        self._public_gun_sayac = 0
        self._public_gun = datetime.now(ISTANBUL_TZ).date()
        self._son_public_ts = None
        self.public_max_saatlik = PUBLIC_MAX_MESAJ_SAAT
        self.public_max_gunluk = PUBLIC_MAX_MESAJ_GUN
        self.public_min_aralik_sn = PUBLIC_MIN_ARALIK_SN
        self.public_kuyruk_limit = 40
        self.public_gonderilen = 0
        self.public_hatasi = 0
        self.public_engel = 0
        self.public_kuyruk_tasmasi = 0
        self.son_public_gonderim = None

        self.public_enabled = bool(self.token and self.public_chat_id)
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
        govde = kirp(text)
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
                    return True, "mesaj gonderildi"
                ipucu = telegram_hata_ipucu(resp.status_code, resp.text)
                son_hata = f"HTTP {resp.status_code}: {resp.text[:200]} | {ipucu}"
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
            ipucu = telegram_hata_ipucu(resp.status_code, resp.text)
            logger.error(f"Telegram token/chat_id reddedildi: HTTP {resp.status_code} {resp.text[:200]} | {ipucu}")
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
                ipucu = telegram_hata_ipucu(yanit.status_code, getattr(yanit, "text", ""))
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
        if state not in self.public_states:
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

    def _public_durum_yukle(self) -> None:
        """Aynı güne ait public bütçe + kuyruğu diskten geri yükler."""
        try:
            veri = _state_persistence.gunluk_durum_yukle() or {}
        except Exception as hata:  # noqa: BLE001
            logger.debug("Public günlük durum okunamadı: %s", hata)
            return
        public = veri.get("public") or {}
        if not isinstance(public, dict):
            return
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
                     and k.get("stock_name") and k.get("state")]
            if temiz:
                self._public_kuyruk = temiz[:self.public_kuyruk_limit]
                logger.info("Public kuyruk restart'tan geri yüklendi: %d olay", len(self._public_kuyruk))
        if self._public_gun_sayac or self._public_kuyruk:
            logger.info("Public günlük bütçe geri yüklendi: %d/%d gönderim (kuyruk %d)",
                        self._public_gun_sayac, self.public_max_gunluk,
                        len(self._public_kuyruk))

    def _public_durum_kaydet(self) -> None:
        """Public bütçe + kuyruğu GÜN damgalı yazar (I/O hatası gönderimi bozmaz)."""
        try:
            with self._public_lck:
                kuyruk = [dict(k) for k in self._public_kuyruk]
            _state_persistence.gunluk_durum_guncelle({"public": {
                "gun_sayac": self._public_gun_sayac,
                "saatlik_ts": [t.isoformat() for t in self._public_saatlik],
                "kuyruk": kuyruk,
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
        govde = _kirp(text)
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
                    except Exception:
                        pass
                    logger.warning("Public 429: %.0f sn sonra tekrar denenecek", bekle)
                    time.sleep(max(0.0, min(bekle, 20.0)))
                    continue
                ipucu = telegram_hata_ipucu(resp.status_code, resp.text)
                logger.error("Telegram public hata: %s | %s", resp.text[:200], ipucu)
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
        if not self.public_enabled:
            return False
        try:
            if not self.should_send_to_public(data):
                return False
        except Exception as exc:  # noqa: BLE001 - kuyruk hatası taramayı durdurmasın
            logger.debug("Public filtre hatası: %s", exc)
            return False
        kayit = {k: data.get(k) for k in (
            "stock_name", "timeframe", "pattern_name", "state", "confidence_score",
            "critical_price_level", "break_price", "break_dir", "contraction", "bar_metni")}
        anahtar = (str(kayit["stock_name"] or "").upper(),
                   str(kayit["timeframe"] or "").lower(),
                   str(kayit["state"] or ""))
        with self._public_lck:
            for k in self._public_kuyruk:
                if (str(k.get("stock_name") or "").upper(),
                        str(k.get("timeframe") or "").lower(),
                        str(k.get("state") or "")) == anahtar:
                    return False
            if len(self._public_kuyruk) >= self.public_kuyruk_limit:
                self.public_kuyruk_tasmasi += 1
                logger.warning("Public kuyruk dolu (%d) - olay atıldı: %s",
                               self.public_kuyruk_limit, anahtar)
                return False
            self._public_kuyruk.append(kayit)
        self._public_durum_kaydet()
        return True

    def public_bosalt(self, azami: int = 12) -> int:
        """Kuyruğu tek bülten(ler) halinde gönderir; engel varsa kayıtlar bekler."""
        with self._public_lck:
            kuyruk = list(self._public_kuyruk)
        if not kuyruk or not self.public_enabled:
            return 0
        gonderilen = 0
        kalan = list(kuyruk)
        while kalan:
            parca = kalan[:max(1, int(azami))]
            metin = self.format_public_batch(parca)
            if not metin:
                kalan = kalan[len(parca):]
                continue
            if not self.send_to_public(metin):
                # Bütçe/ağ engeli: kayıtlar kuyrukta kalır, sonraki turda denenir.
                break
            gonderilen += len(parca)
            kalan = kalan[len(parca):]
        if gonderilen:
            with self._public_lck:
                self._public_kuyruk = self._public_kuyruk[gonderilen:]
            self._public_durum_kaydet()
            logger.info("Public bülten gönderildi: %d olay (%d mesaj)",
                        gonderilen, max(1, (gonderilen + azami - 1) // azami))
        return gonderilen

    def format_public_batch(self, kayitlar: List[Dict]) -> str:
        """Grup sürümü bülten: sade satırlar, iç izleme notu ve kuyruk yok."""
        kayitlar = [k for k in (kayitlar or []) if isinstance(k, dict)]
        if not kayitlar:
            return ""
        satirlar = [f"📊 Formasyon bülteni · {_tr_tarih(datetime.now(ISTANBUL_TZ))} "
                    f"· {len(kayitlar)} gelişme"]
        for k in kayitlar:
            stock = str(k.get("stock_name") or "?")
            tf = TF_HUMAN.get(k.get("timeframe"), str(k.get("timeframe") or ""))
            pattern = str(k.get("pattern_name") or "Formasyon")
            state = str(k.get("state") or "")
            etiket = PUBLIC_STATE_ETIKET.get(state, STATE_TR.get(state, state))
            yon = _yon_kisa(k.get("break_dir"))
            satir = (f"{PATTERN_EMOJI.get(pattern, '📈')} {stock} {tf} · {pattern} · "
                     f"{yon + ' ' if yon else ''}{etiket}")
            seviye = k.get("critical_price_level") or k.get("break_price")
            try:
                if seviye:
                    satir += f" · {float(seviye):.2f}"
            except (TypeError, ValueError):
                pass
            try:
                satir += f" · q{float(k.get('confidence_score') or 0):.0f}"
            except (TypeError, ValueError):
                pass
            mum = str(k.get("bar_metni") or "").strip().splitlines()
            if mum:
                satir += f"\n   {mum[-1]}" if len(mum) > 1 else ""
            satirlar.append(satir)
        satirlar.append("")
        satirlar.append("📌 Formasyon takibi · yatırım tavsiyesi değildir")
        return "\n".join(satirlar)

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
        baslik = (f"📊 {_tr_tarih(simdi)} kapanış · BIST formasyon özeti" if kapanis
                  else f"📊 {_tr_tarih(simdi)} sabah notu · BIST formasyon takibi")
        satirlar = [baslik]
        tamamlanan = [f for f in aktif if f.get('state') == 'FORMASYON_TAMAMLANDI']
        retest = [f for f in aktif if f.get('state') == 'RETEST_BASARILI']
        teyitli = [f for f in aktif if f.get('state') == 'KIRILIM_TEYITLI']
        sikisan = [f for f in aktif if f.get('state') == 'SIKISMA_GUCLENIYOR'
                   and (f.get('contraction') or 0) >= self.public_sikisma_min]
        if tamamlanan:
            ilk = " · ".join(f"{f.get('stock_name')} {f.get('timeframe') or ''}".strip()
                             for f in tamamlanan[:3])
            ek = f" (ilk {min(3, len(tamamlanan))})" if len(tamamlanan) > 3 else ""
            satirlar.append(f"🏁 Tamamlanan {len(tamamlanan)}{ek}: {ilk}")
        if retest or teyitli:
            satirlar.append(f"🎯 Retest başarılı {len(retest)} · "
                            f"✅ Teyitli kırılım {len(teyitli)}")
        basarisiz = int((gun_ozeti or {}).get('basarisiz_kirilim') or 0)
        if basarisiz and kapanis:
            satirlar.append(f"❌ {basarisiz} kırılım başarısız oldu")
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
                tf = TF_HUMAN.get(k.get('timeframe'), str(k.get('timeframe') or ''))
                try:
                    kalite = f" · kalite {float(k.get('quality') or 0):.0f}"
                except (TypeError, ValueError):
                    kalite = ""
                satirlar.append(f"• {k.get('stock')} {tf} {k.get('pattern_name') or 'formasyon'}"
                                f"{kalite}")
        if not aktif and not izleme:
            satirlar.append("Bugün öne çıkan formasyon olmadı." if kapanis
                            else "Şu an izlenen formasyon yok.")
        try:
            tur = int(tarama_turu) if tarama_turu is not None else 0
        except (TypeError, ValueError):
            tur = 0
        satirlar.append("")
        satirlar.append(f"{len(ACTIVE_STOCKS)} hisse × 4 zaman dilimi"
                        + (f" · {tur} tarama" if tur else "")
                        + ("" if kapanis else " · gün yeni başlıyor"))
        if karne_kisa:
            satirlar += ["", karne_kisa]
        satirlar.append("📌 Formasyon takibi · yatırım tavsiyesi değildir")
        return "\n".join(satirlar)

    def format_daily_summary(self, aktif_formasyonlar: List[Dict], gun_ozeti: Dict = None) -> str:
        now = datetime.now(ISTANBUL_TZ)
        # Türkçe ay kısaltması + tek ayırıcı: "📊 BIST Formasyon Özeti · 02 Eki 20:05"
        baslik = f"📊 BIST Formasyon Özeti · {_tr_tarih(now)}\n"
        baslik += "─" * 30 + "\n"
        if not aktif_formasyonlar:
            baslik += "Şu an aktif yüksek kaliteli formasyon yok.\n"
            return baslik
        # NOT: Burada eskiden hesaplanıp hiç kullanılmayan bir `[:10]` sıralaması
        # vardı (ölü kod). Özet gövdesi bilerek bölüm bazlı ve sınırlıdır:
        # tamamlanan [:3], retest [:3], sıkışan [:5]. Eksik kalan adaylar için
        # 18:45 digest'i ve /formasyonlar komutu kullanılır.
        tamamlanan = [f for f in aktif_formasyonlar if f.get('state') == 'FORMASYON_TAMAMLANDI']
        retest = [f for f in aktif_formasyonlar if f.get('state') == 'RETEST_BASARILI']
        sikisan = [f for f in aktif_formasyonlar if f.get('state') == 'SIKISMA_GUCLENIYOR' and (f.get('contraction', 0) or 0) >= self.public_sikisma_min]
        if tamamlanan:
            # Başlık toplamı, gövde ise ilk 3'ü listeler; "(6)" ile 3 satır
            # görmek kafa karıştırıyordu → "6 · ilk 3".
            baslik += (f"\n🏁 TAMAMLANAN ({len(tamamlanan)}"
                       f"{' · ilk 3' if len(tamamlanan) > 3 else ''}):\n")
            for f in tamamlanan[:3]:
                # Diğer bölümlerle aynı madde biçimi: hisse · desen · tf · kalite
                baslik += (f"• {f.get('stock_name')} {f.get('pattern_name')} "
                           f"{f.get('timeframe') or ''} · kalite "
                           f"{f.get('confidence_score', 0):.0f}\n").replace("  ", " ")
        if retest:
            baslik += (f"\n🎯 RETEST BAŞARILI ({len(retest)}"
                       f"{' · ilk 3' if len(retest) > 3 else ''}):\n")
            for f in retest[:3]:
                # Yön Türkçe ve kalite de görünüyor: tüm bölümler aynı madde biçimini kullanır.
                baslik += (f"• {f.get('stock_name')} {f.get('pattern_name')} "
                           f"{f.get('timeframe') or ''} · {_yon_metni(f.get('break_dir', 0))} yön"
                           f" · kalite {f.get('confidence_score', 0):.0f}\n").replace("  ", " ")
        if sikisan:
            baslik += (f"\n⚡ SIKIŞANLAR ({len(sikisan)}"
                       f"{' · ilk 5' if len(sikisan) > 5 else ''}):\n")
            for f in sikisan[:5]:
                baslik += (f"• {f.get('stock_name')} {f.get('pattern_name')} "
                           f"{f.get('timeframe') or ''} · %{(f.get('contraction', 0) * 100):.0f} "
                           f"daralma\n").replace("  ", " ")
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
                baslik += (f"\n📈 Gün: {tur} tarama · {len(ACTIVE_STOCKS)} hisse × "
                           f"4 zaman dilimi · {gun_ozeti.get('alerts_sent', 0)} bildirim\n")
        baslik += "\n📌 Formasyon takibi · yatırım tavsiyesi değildir"
        return baslik

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
            self.engeller = {"cooldown": 0, "gunluk_kap": 0, "saatlik_kap": 0, "tekrar": 0}
            self.gonderim_hatasi = 0
            self.gonderilen_alarm = 0

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
    # Mühür (hisse + TF + state) anahtarlı ve ZAMAN damgalı bayatlar (TTL,
    # bkz. _muhur_ttl_saat). Üç kök neden düzeltildi:
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
    def _son_alert_key(self, stock: str, timeframe: str, state: str) -> str:
        """Slot anahtarı: hisse + zaman dilimi + state (pattern GİRMEZ)."""
        return f"{stock}_{timeframe}_{state}"

    @classmethod
    def _muhr_gecerli_mi(cls, muhur, state: str, timeframe: str = "") -> bool:
        """Mühür hâlâ geçerliyse True (olay zaten bildirildi, tekrar basma).

        Bayatlık ölçütü TTL: motor terminal formasyonu TERMINAL_TAZE_BAR bar
        boyunca taze sayar, mühür de en az o kadar süre (bkz. _muhur_ttl_saat)
        geçerli kalır. Gün bazlı ölçüt 1 günlük grafikte aynı haberi 3 gün
        daha tekrar bastırıyordu.
        """
        if not muhur or not isinstance(muhur, dict):
            return False
        if muhur.get("state") != state:
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
        return 0 <= yas_saat < _muhur_ttl_saat(muhur.get("tf") or timeframe)

    @staticmethod
    def _muhur_kaydi(state: str, timeframe: str, gun: str = None, zaman: str = None) -> Dict:
        """Mühür kaydı üretir: {"state", "zaman" (ISO), "tf"}.

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
        return {"state": state, "zaman": zaman, "tf": timeframe}

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
                            gun=v.get("gun"), zaman=v.get("zaman"))
            logger.info(f"Son-alert mühürleri {kaynak} yüklendi: {len(self._son_alert)} kayıt")
        except Exception as e:
            logger.warning(f"Son-alert mühürleri yüklenemedi (devam ediliyor): {e}")

    def _son_alert_kaydet(self):
        # Bayat (TTL dolmuş) mühürler diske/Supabase'a taşınmaz; sözlük şişmesin.
        for anahtar in [k for k, v in self._son_alert.items()
                        if not self._muhr_gecerli_mi(v, v.get("state", ""), v.get("tf", ""))]:
            del self._son_alert[anahtar]
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

    def _tek_seferlik_isle(self, stock: str, pattern: str, timeframe: str, state: str) -> None:
        """Başarılı gönderim sonrası acil (ALERT_STATES) olaya tek-seferlik mühür basar.

        Mühür yalnız AYNI state'i susturur; yaşam döngüsü ilerlemesi
        (TEYITLI -> RETEST_BASARILI -> TAMAMLANDI) her biri bir kez bildirilebilir.
        `pattern` bilinçli olarak anahtara girmez: aynı slotta motorun ürettiği
        farklı formasyon etiketleri aynı olayın kopyasıdır.
        """
        if state not in ALERT_STATES:
            return
        self._son_alert[self._son_alert_key(stock, timeframe, state)] = \
            self._muhur_kaydi(state, timeframe)
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
            self._acil_kuyruk = [k for k in ham if isinstance(k, dict) and isinstance(k.get("veri"), dict)]
            logger.info(f"Telegram acil kuyruğu {kaynak} yüklendi: {len(self._acil_kuyruk)} olay")
        except Exception as e:
            logger.debug(f"Acil kuyruk yüklenemedi (ilk çalışma olabilir): {e}")

    def _kuyruk_kaydet(self):
        kayitlar = [dict(k) for k in self._acil_kuyruk]
        try:
            import json
            os.makedirs(os.path.dirname(self._kuyruk_dosya), exist_ok=True)
            with open(self._kuyruk_dosya, "w", encoding="utf-8") as f:
                json.dump(kayitlar, f, ensure_ascii=False, default=str)
        except Exception as e:
            logger.debug(f"Acil kuyruk dosyaya kaydedilemedi: {e}")
        if self.persistent_store is not None:
            try:
                self.persistent_store.upsert("state:telegram_acil_kuyruk", kayitlar)
            except Exception as e:
                logger.debug(f"Acil kuyruk Supabase'e kaydedilemedi: {e}")

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
                kayit["veri"] = dict(data)
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
            "veri": dict(data),
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

    def kuyrugu_bosalt(self, max_adet: int = 5) -> int:
        """Engel kalkınca kuyruktaki acil olayları sırayla gönderir (Batch 5 / B4).

        - TTL'yi aşan kayıtlar gönderilmez, atılır (bayat sinyal zarar verir).
        - Aynı sinyal sonradan gönderilmişse kuyruk kopyası sessizce düşürülür.
        - Kap/cooldown sürüyorsa sıradaki tura kadar beklenir; ağ hatasında
          kayıt korunur (veri kaybı yok).
        """
        if not self.enabled or not self._acil_kuyruk:
            return 0
        simdi = datetime.now(ISTANBUL_TZ)
        ttl_siniri = simdi - timedelta(minutes=max(1, ACIL_KUYRUK_TTL_DK))
        gonderilen = 0
        degisti = False
        for kayit in list(self._acil_kuyruk):
            if gonderilen >= max(1, int(max_adet)):
                break
            veri = kayit.get("veri") or {}
            try:
                kuyruk_zamani = _istanbul(datetime.fromisoformat(kayit.get("kuyruk_zaman")))
            except (TypeError, ValueError):
                kuyruk_zamani = simdi
            if kuyruk_zamani < ttl_siniri:
                self._acil_kuyruk.remove(kayit)
                self.kuyruk_zaman_asimi += 1
                degisti = True
                logger.warning(
                    f"📬 Kuyruktaki acil olay bayatladı ({ACIL_KUYRUK_TTL_DK} dk): "
                    f"{self._kuyruk_key(veri)[0]} {veri.get('state')}"
                )
                continue
            key = self._kuyruk_key(veri)
            if not self.can_send(key[0], key[1], key[2], key[3]):
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

    def can_send(self, stock: str, pattern: str, timeframe: str, state: str = "") -> bool:
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
            if self._muhr_gecerli_mi(
                    self._son_alert.get(self._son_alert_key(stock, timeframe, state)),
                    state, timeframe):
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
            "kuyruk_gonderildi": self.kuyruk_gonderildi,
            "kuyruk_zaman_asimi": self.kuyruk_zaman_asimi,
            "kuyruk_tasmasi": self.kuyruk_tasmasi,
            # Public (grup) hedefi: DM'den bağımsız sayaçlar.
            "public_enabled": self.public_enabled,
            "public_chat_id": self.public_chat_id,
            "public_gonderilen": self.public_gonderilen,
            "public_hatasi": self.public_hatasi,
            "public_engel": self.public_engel,
            "public_kuyruk": len(self._public_kuyruk),
            "public_kuyruk_tasmasi": self.public_kuyruk_tasmasi,
            "son_public_gonderim": self.son_public_gonderim,
        }

    def format_message(self, data: Dict) -> str:
        stock = data.get('stock_name', 'Bilinmiyor')
        timeframe = data.get('timeframe', '1h')
        pattern = data.get('pattern_name', 'Formasyon')
        state = data.get('state', 'ADAY_OLUSUYOR')
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
            temas_str = f"{upper_touches + lower_touches} temas"
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
            satirlar.append(f"Bant: {lower:.2f} - {upper:.2f}")

        elif state == "GEOMETRI_ADAYI":
            satirlar = [f"{emoji} {stock} {tf_human} · {pattern}",
                        "Geometri oturuyor",
                        kalite_str]
            if detay_str:
                satirlar.append(detay_str)
            satirlar.append(f"Bant: {lower:.2f} - {upper:.2f} · olgunlaşma bekleniyor")

        elif state == "FORMASYON_TANIMLANDI":
            satirlar = [f"📋 {stock} {tf_human} · {pattern}",
                        "Formasyon tanımlandı",
                        kalite_str]
            if detay_str:
                satirlar.append(detay_str)
            satirlar.append(f"Üst: {upper:.2f} / Alt: {lower:.2f}")

        elif state == "SIKISMA_GUCLENIYOR":
            satirlar = [f"⚡ {stock} {tf_human} · {pattern}",
                        "Sıkışma güçleniyor",
                        kalite_str]
            if detay_str:
                satirlar.append(detay_str)
            satirlar.append(f"Bant: {lower:.2f} - {upper:.2f} · kırılım yakın")

        elif state == "KIRILIM_HAZIRLIGI":
            satirlar = [f"⚠️ {stock} {tf_human} · {pattern}",
                        "Kırılım hazırlığında",
                        kalite_str]
            if detay_str:
                satirlar.append(detay_str)
            satirlar.append(f"Kritik seviyeler: {lower:.2f} / {upper:.2f}")

        elif state == "KIRILIM_DENEMESI":
            direction = "yukarı" if break_dir == 1 else "aşağı" if break_dir == -1 else ""
            level = upper if break_dir == 1 else lower
            yon_eki = f"{direction} yönde " if direction else ""
            satirlar = [f"🔥 {stock} {tf_human} · {pattern}",
                        f"Kırılım denemesi · {yon_eki}{level:.2f} zorlanıyor",
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
                        f"{baslik_eki}kırılım adayı · {level:.2f} {kapanis_yonu} kapanış",
                        f"Kırılım gücü {power:.0f} {q_emoji} · teyit mumu bekleniyor"]

        elif state == "KIRILIM_TEYITLI":
            direction = "yukarı" if break_dir == 1 else "aşağı" if break_dir == -1 else ""
            level = data.get('break_price', upper if break_dir==1 else lower)
            yon = f"{direction} kırılım" if direction else "Kırılım"
            rol = "destek" if break_dir == 1 else "direnç" if break_dir == -1 else "kritik seviye"
            satirlar = [f"✅ {stock} {tf_human} · {pattern}",
                        f"{yon} teyitli · {level:.2f}",
                        kalite_str]
            if detay_str:
                satirlar.append(detay_str)
            satirlar.append(f"Retest bekleniyor · {level:.2f} artık {rol}")

        elif state == "RETEST_BEKLENIYOR":
            level = data.get('break_price', price)
            satirlar = [f"⏳ {stock} {tf_human} · {pattern}",
                        f"Retest bekleniyor · {level:.2f}'e dönüş olabilir",
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
            yon = f"{direction} kırılım" if direction else "Kırılım"
            satirlar = [f"🎯 {stock} {tf_human} · {pattern}",
                        f"RETEST BAŞARILI · {yon} sonrası retest tuttu",
                        kalite_str]
            if detay_str:
                satirlar.append(detay_str)
            satirlar.append("Formasyon tamamlanmaya yakın")

        elif state == "FORMASYON_TAMAMLANDI":
            direction = "yukarı" if break_dir == 1 else "aşağı" if break_dir == -1 else ""
            yon = f"{direction} kırılım" if direction else "Kırılım"
            if retest_seen:
                satirlar = [f"🏁 {stock} {tf_human} · {pattern}",
                            f"TAMAMLANDI · {yon} + retest başarılı",
                            kalite_str]
            else:
                satirlar = [f"🏁 {stock} {tf_human} · {pattern}",
                            f"TAMAMLANDI · {yon}, retest olmadan ilerledi",
                            "Fiyat kırılan seviyeye geri dönmedi",
                            kalite_str]
            if detay_str:
                satirlar.append(detay_str)

        elif state == "BASARISIZ_KIRILIM":
            satirlar = [f"❌ {stock} {tf_human} · {pattern}",
                        "Kırılım başarısız · formasyon alanına dönüldü",
                        "Sahte kırılım olabilir · yeniden sıkışma bekleniyor"]

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
                        f"Seviye: {price:.2f} · {time_str}"]

        # Kapanan mum satırı (P0): anlık olay mesajlarında "hangi mum kapandı?"
        # sorusu mesajın içinde cevaplanır. İzleme/digest akışına eklenmez
        # (orada yer bütçesi farklı ve o adaylar zaten kapanış özetiyle gider).
        mum_str = str(data.get('bar_metni') or "").strip()
        if mum_str and state in ("KIRILIM_TEYITLI", "RETEST_BASARILI",
                                 "FORMASYON_TAMAMLANDI", "BASARISIZ_KIRILIM"):
            satirlar.insert(1, mum_str)

        msg = "\n".join(satirlar)

        # Tek ve sabit footer: eskiden üç cümleden biri rastgele ekleniyordu —
        # hem mesajı gereksiz uzatıyordu hem de aynı olay iki farklı metinle
        # gidiyordu. Tavsiye veren cümleler ("kendi analizini yap", "acele etme")
        # kaldırıldı; kanal dili birebir aynı kalıyor.
        if state in ("KIRILIM_ADAYI", "KIRILIM_TEYITLI", "RETEST_BASARILI", "FORMASYON_TAMAMLANDI"):
            msg += "\n\n📌 Formasyon takibi · yatırım tavsiyesi değildir"

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

        return msg

    def send(self, data: Dict, kuyrukla: bool = True) -> bool:
        """Acil alarm gönderir; engel varsa olay kuyruğa alınır (Batch 5 / B4).

        `kuyrukla=False` kuyruktan gelen gönderimlerde kullanılır (aynı olay
        tekrar kuyruğa girmesin).
        """
        stock = data.get('stock_name', '')
        pattern = data.get('pattern_name', '')
        timeframe = data.get('timeframe', '')
        state = data.get('state', '')

        if not self.can_send(stock, pattern, timeframe, state):
            engel = self._son_engel or "cooldown"
            # "tekrar" engeli nihai reddir: olay zaten gönderildi (mühür var),
            # bayat kopyası kuyrukta birikip sonra çift mesaj üretmesin.
            if kuyrukla and self.enabled and engel != "tekrar":
                # Kaybolmasın: kap/cooldown açılınca kuyruktan gönderilir.
                self._kuyruga_ekle(data, engel)
            logger.info(f"{stock} {pattern} {timeframe} {state} - {engel}, gönderilmiyor")
            return False

        return self._gonder(data)

    def _gonder(self, data: Dict) -> bool:
        """can_send kapısı geçildikten sonraki gerçek gönderim (kuyruk bunu çağırır)."""
        stock = data.get('stock_name', '')
        pattern = data.get('pattern_name', '')
        timeframe = data.get('timeframe', '')
        state = data.get('state', '')

        message = self.format_message(data)

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
            self._tek_seferlik_isle(stock, pattern, timeframe, state)
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
                self._tek_seferlik_isle(stock, pattern, timeframe, state)
                # NOT: Public (grup) gönderimi burada YAPILMAZ. Olaylar tarama
                # turu boyunca `public_kuyruk()` ile toplanır ve tur sonunda tek
                # bültende gider; DM başarısız olsa bile grup yayını etkilenmez.
                return True
            else:
                ipucu = telegram_hata_ipucu(resp.status_code, resp.text)
                logger.error(f"Telegram hatası: {resp.text} | {ipucu}")
                self._gonderim_sagligi_kaydet(basari=False, hata=ipucu)
                return False
        except Exception as e:
            logger.error(f"Telegram gönderim hatası: {e}")
            self._gonderim_sagligi_kaydet(basari=False, hata=f"istek hatasi: {e}")
            return False


if __name__ == "__main__":
    notifier = TelegramNotifier()
    test_cases = [
        {'stock_name': 'THYAO', 'timeframe': '1h', 'pattern_name': 'Yükselen Üçgen', 'state': 'ADAY_OLUSUYOR', 'confidence_score': 83, 'critical_price_level': 302.11, 'upper_now': 302.11, 'lower_now': 294.32, 'contraction': 0.87, 'timestamp': datetime.now(), 'upper_touches': 2, 'lower_touches': 2, 'age_bars': 18},
        {'stock_name': 'GARAN', 'timeframe': '4h', 'pattern_name': 'Simetrik Üçgen', 'state': 'SIKISMA_GUCLENIYOR', 'confidence_score': 88, 'critical_price_level': 120.5, 'upper_now': 122.0, 'lower_now': 119.0, 'contraction': 0.91, 'timestamp': datetime.now(), 'upper_touches': 3, 'lower_touches': 2, 'age_bars': 22},
        {'stock_name': 'AKBNK', 'timeframe': '1h', 'pattern_name': 'Alçalan Kama', 'state': 'KIRILIM_ADAYI', 'confidence_score': 82, 'critical_price_level': 58.3, 'upper_now': 58.3, 'lower_now': 55.1, 'contraction': 0.75, 'break_dir': 1, 'break_strength': 82, 'timestamp': datetime.now()},
    ]
    for tc in test_cases:
        print(notifier.format_message(tc))
        print("---")
