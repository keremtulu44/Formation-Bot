# --- TELEGRAM NOTIFIER - İNSANLAŞTIRMA V2 + KANAL MODELİ ---
# Tek sistem, gürültü azaltma, public kanal desteği

import os
import logging
import random
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List

from config import (DATA_DIR, ISTANBUL_TZ, TELEGRAM_MAX_MESAJ_SAAT, TELEGRAM_MAX_MESAJ_GUN,
                    ACIL_KUYRUK_LIMIT, ACIL_KUYRUK_TTL_DK)

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

def quality_emoji(q: float) -> str:
    if q >= 85:
        return "⭐⭐⭐"
    elif q >= 75:
        return "⭐⭐"
    elif q >= 65:
        return "⭐"
    else:
        return "〰️"

def _env_temizle(deger) -> str:
    if deger is None:
        return ""
    s = str(deger).strip()
    while len(s) >= 2 and ((s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'")):
        s = s[1:-1].strip()
    return s.strip()

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
        self.channel_id = _env_temizle(os.environ.get("TELEGRAM_CHANNEL_ID", ""))
        self.cooldown_hours = 4
        self.last_sent: Dict[str, datetime] = {}
        self.max_saatlik = TELEGRAM_MAX_MESAJ_SAAT
        self.max_gunluk = TELEGRAM_MAX_MESAJ_GUN
        self._saatlik_zamanlar: List[datetime] = []
        # Gönderilemeyen alarmların SEBEP sayaçları (gün içi, gün değişiminde sıfırlanır).
        # Neden: can_send False döndüğünde olay hiçbir yerde görünmüyordu; kullanıcı
        # "kaç tanesi bastırıldı" sorusunun cevabını /durum'da görebilmeli.
        self.engeller = {"cooldown": 0, "gunluk_kap": 0, "saatlik_kap": 0}
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

        try:
            from config import PUBLIC_MIN_QUALITY, PUBLIC_STATES, PUBLIC_SIKISMA_MIN_CONTRACTION
            self.public_min_quality = PUBLIC_MIN_QUALITY
            self.public_states = set(PUBLIC_STATES)
            self.public_sikisma_min = PUBLIC_SIKISMA_MIN_CONTRACTION
        except Exception:
            self.public_min_quality = 80
            self.public_states = {"FORMASYON_TAMAMLANDI", "RETEST_BASARILI"}
            self.public_sikisma_min = 0.80

        if not self.token or not self.chat_id:
            logger.warning("Telegram token/chat_id env'de yok - notifier pasif (test modu)")
            self.enabled = False
        else:
            if self.channel_id:
                logger.info(f"Telegram public kanal aktif: {self.channel_id} (DM + kanal)")
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
        if quality < self.public_min_quality:
            return False
        return True

    def send_to_channel(self, text: str) -> bool:
        if not self.enabled:
            logger.info(f"[MOCK CHANNEL] {text[:120]}")
            return True
        if not self.channel_id:
            logger.debug("CHANNEL_ID yok, kanala gönderim atlandı")
            return False
        try:
            import requests
            resp = requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={"chat_id": self.channel_id, "text": text},
                timeout=15,
            )
            if resp.status_code == 200:
                logger.info(f"Telegram kanala gönderildi: {self.channel_id}")
                self._gonderim_sagligi_kaydet(basari=True)
                return True
            ipucu = telegram_hata_ipucu(resp.status_code, resp.text)
            logger.error(f"Telegram kanal hatası: {resp.text} | {ipucu}")
            self.kanal_hatasi += 1
            self._gonderim_sagligi_kaydet(basari=False, hata=f"kanal: HTTP {resp.status_code}")
            return False
        except Exception as e:
            logger.error(f"Telegram kanal gönderim hatası: {e}")
            self.kanal_hatasi += 1
            self._gonderim_sagligi_kaydet(basari=False, hata=f"kanal: {e}")
            return False

    def format_daily_summary(self, aktif_formasyonlar: List[Dict], gun_ozeti: Dict = None) -> str:
        now = datetime.now(ISTANBUL_TZ)
        baslik = f"📊 BIST Formasyon Özeti - {now.strftime('%d %b %H:%M')}\n"
        baslik += "─" * 30 + "\n"
        if not aktif_formasyonlar:
            baslik += "Şu an aktif yüksek kaliteli formasyon yok.\nTakipteyim 👀\n"
            return baslik
        # NOT: Burada eskiden hesaplanıp hiç kullanılmayan bir `[:10]` sıralaması
        # vardı (ölü kod). Özet gövdesi bilerek bölüm bazlı ve sınırlıdır:
        # tamamlanan [:3], retest [:3], sıkışan [:5]. Eksik kalan adaylar için
        # 18:45 digest'i ve /formasyonlar komutu kullanılır.
        tamamlanan = [f for f in aktif_formasyonlar if f.get('state') == 'FORMASYON_TAMAMLANDI']
        retest = [f for f in aktif_formasyonlar if f.get('state') == 'RETEST_BASARILI']
        sikisan = [f for f in aktif_formasyonlar if f.get('state') == 'SIKISMA_GUCLENIYOR' and (f.get('contraction', 0) or 0) >= self.public_sikisma_min]
        if tamamlanan:
            baslik += f"\n🏁 TAMAMLANAN ({len(tamamlanan)}):\n"
            for f in tamamlanan[:3]:
                baslik += f"• {f.get('stock_name')} {f.get('pattern_name')} {f.get('timeframe')} - Kalite {f.get('confidence_score',0):.0f}\n"
        if retest:
            baslik += f"\n🎯 RETEST BAŞARILI ({len(retest)}):\n"
            for f in retest[:3]:
                baslik += f"• {f.get('stock_name')} {f.get('pattern_name')} - {f.get('break_dir',0)} yön\n"
        if sikisan:
            baslik += f"\n⚡ SIKIŞANLAR ({len(sikisan)}):\n"
            for f in sikisan[:5]:
                baslik += f"• {f.get('stock_name')} %{(f.get('contraction',0)*100):.0f} daralma - {f.get('pattern_name')}\n"
        if gun_ozeti:
            baslik += f"\n📈 Gün: {gun_ozeti.get('stocks_scanned',0)} hisse tarandı, {gun_ozeti.get('alerts_sent',0)} alert\n"
        baslik += "\n💡 Detay için kanalı takipte kal - yatırım tavsiyesi değildir"
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
            self.engeller = {"cooldown": 0, "gunluk_kap": 0, "saatlik_kap": 0}
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
                json.dump(kayitlar, f, ensure_ascii=False)
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
                time_str = timestamp.strftime("%d %b %H:%M")
            except (AttributeError, ValueError, TypeError):
                # strftime desteklemeyen/tuhaf timestamp: metne düşür (dar kapsam).
                time_str = str(timestamp)

        contraction_str = ""
        if contraction is not None:
            pct = contraction * 100
            if pct >= 80:
                contraction_str = f"daralma %{pct:.0f} - baya sıkışmış"
            elif pct >= 60:
                contraction_str = f"daralma %{pct:.0f} - sıkışıyor"
            elif pct >= 40:
                contraction_str = f"daralma %{pct:.0f}"
            else:
                contraction_str = f"daralma %{pct:.0f} - erken"

        temas_str = ""
        if upper_touches is not None and lower_touches is not None:
            toplam = upper_touches + lower_touches
            temas_str = f", {toplam} temas"
        yas_str = f", {age_bars} bar" if age_bars else ""
        mtf_str = " + 4h destekliyor" if mtf_destek else ""

        if state == "ADAY_OLUSUYOR":
            templates = [
                f"{emoji} {stock} {tf_human} grafikte {pattern} oluşuyor...\n"
                f"Kalite {quality:.0f} {q_emoji} ({q_comment}), {contraction_str}{temas_str}{yas_str}\n"
                f"Üst {upper:.2f} / Alt {lower:.2f} bandında sıkışma var\n"
                f"Takipteyiz 👀 - kırılıma yaklaştıkça haber veririm",
                f"👀 {stock}'da bir şeyler oluyor\n"
                f"{tf_human} grafikte {pattern} {q_comment} duruyor (kalite {quality:.0f}){temas_str}\n"
                f"{contraction_str}, bant {lower:.2f} - {upper:.2f}\n"
                f"Henüz erken ama radarımda 📡",
            ]
            msg = random.choice(templates)

        elif state == "GEOMETRI_ADAYI":
            msg = (
                f"{emoji} {stock} {tf_human} - {pattern} geometrisi oturuyor\n"
                f"Kalite {quality:.0f} {q_emoji}, {contraction_str}{temas_str}\n"
                f"Bant: {lower:.2f} - {upper:.2f}\n"
                f"Olgunlaşmasını bekliyorum..."
            )

        elif state == "FORMASYON_TANIMLANDI":
            msg = (
                f"📋 {stock} {tf_human} {pattern} tanımlandı\n"
                f"Kalite {quality:.0f} {q_emoji} ({q_comment}) {contraction_str}{temas_str}{yas_str}\n"
                f"Üst: {upper:.2f} Alt: {lower:.2f}\n"
                f"Sıkışma güçlenirse kırılım gelebilir"
            )

        elif state == "SIKISMA_GUCLENIYOR":
            msg = (
                f"⚡ {stock}'da sıkışma güçleniyor!\n"
                f"{tf_human} {pattern} {contraction_str}{temas_str}{yas_str} - sona yaklaşıyor\n"
                f"Kalite {quality:.0f} {q_emoji}, bant {lower:.2f}-{upper:.2f}\n"
                f"Kırılım yakın olabilir, gözüm üstünde 👁️"
            )

        elif state == "KIRILIM_HAZIRLIGI":
            msg = (
                f"⚠️ {stock} {tf_human} {pattern} kırılım hazırlığında\n"
                f"{contraction_str}, kalite {quality:.0f} {q_emoji}{temas_str}\n"
                f"Kritik seviyeler: {lower:.2f} / {upper:.2f}\n"
                f"Birkaç mum içinde hareket gelebilir"
            )

        elif state == "KIRILIM_DENEMESI":
            direction = "yukarı" if break_dir == 1 else "aşağı" if break_dir == -1 else ""
            level = upper if break_dir == 1 else lower
            msg = (
                f"🔥 {stock}'da deneme var!\n"
                f"{tf_human} {pattern} {direction} {level:.2f}'i zorluyor\n"
                f"Güç henüz düşük, teyit bekliyorum...{mtf_str}\n"
                f"Kalite {quality:.0f} {q_emoji} | {time_str}"
            )

        elif state == "KIRILIM_ADAYI":
            direction = "YUKARI" if break_dir == 1 else "AŞAĞI" if break_dir == -1 else ""
            level = upper if break_dir == 1 else lower
            power = data.get('break_strength', quality)
            kapanis_yonu = "üstünde" if break_dir == 1 else "altında" if break_dir == -1 else "yakınında"
            templates = [
                f"🚀 {stock} KIRIYOR! {direction}\n"
                f"{tf_human} {pattern} {level:.2f} {kapanis_yonu} kapanış{mtf_str}\n"
                f"Güç {power:.0f} {q_emoji} - teyit mumu bekleniyor\n"
                f"Retest olursa fırsat olabilir, takipteyim",
                f"💥 {stock} {tf_human} {pattern}\n"
                f"{direction} kırılım adayı! {level:.2f} kırıldı\n"
                f"Güç {power:.0f} ({q_comment}) - teyit gelirse haber veririm\n"
                f"Şimdilik izle, acele etme",
            ]
            msg = random.choice(templates)

        elif state == "KIRILIM_TEYITLI":
            direction = "yukarı" if break_dir == 1 else "aşağı" if break_dir == -1 else ""
            level = data.get('break_price', upper if break_dir==1 else lower)
            msg = (
                f"✅ {stock} teyit aldı! {direction} kırılım{mtf_str}\n"
                f"{tf_human} {pattern} {level:.2f} kırılımı teyitli\n"
                f"Kalite {quality:.0f} {q_emoji}, {contraction_str}{temas_str}\n"
                f"{level:.2f} artık {'destek' if break_dir==1 else 'direnç'} olabilir\n"
                f"Retest bekleniyor..."
            )

        elif state == "RETEST_BEKLENIYOR":
            level = data.get('break_price', price)
            msg = (
                f"⏳ {stock} retest bekleniyor\n"
                f"{tf_human} {pattern} kırılım sonrası {level:.2f}'e dönüş olabilir\n"
                f"Kalite {quality:.0f} {q_emoji} - retest tutarsa güçlenir"
            )

        elif state == "RETEST_EDILIYOR":
            msg = (
                f"🔄 {stock}'da retest oluyor\n"
                f"{tf_human} {pattern} kırılan seviyeye geri döndü\n"
                f"Tutunursa devamı gelebilir, izliyorum"
            )

        elif state == "RETEST_BASARILI":
            direction = "yukarı" if break_dir == 1 else "aşağı"
            msg = (
                f"🎯 {stock} RETEST BAŞARILI!\n"
                f"{tf_human} {pattern} {direction} kırılım sonrası retest tuttu{mtf_str}\n"
                f"Kalite {quality:.0f} {q_emoji}{temas_str}{yas_str} - formasyon tamamlanmaya yakın\n"
                f"Bu seviyelerden sonrası için kendi analizini yap"
            )

        elif state == "FORMASYON_TAMAMLANDI":
            direction = "yukarı" if break_dir == 1 else "aşağı"
            detay = f"{temas_str}{yas_str}{mtf_str}"
            if retest_seen:
                msg = (
                    f"🏁 {stock} {pattern} TAMAMLANDI\n"
                    f"{tf_human} grafikte {direction} kırılım + retest başarılı{detay}\n"
                    f"Kalite {quality:.0f} {q_emoji} - görev tamam\n"
                    f"Yeni formasyon için taramaya devam"
                )
            else:
                msg = (
                    f"🏁 {stock} {pattern} TAMAMLANDI\n"
                    f"{tf_human} grafikte {direction} kırılım - retest olmadan ilerledi / "
                    f"fiyat kırılan seviyeye geri dönmedi{detay}\n"
                    f"Kalite {quality:.0f} {q_emoji} - görev tamam\n"
                    f"Yeni formasyon için taramaya devam"
                )

        elif state == "BASARISIZ_KIRILIM":
            msg = (
                f"❌ {stock} kırılım başarısız\n"
                f"{tf_human} {pattern} kırılım denedi ama geri döndü\n"
                f"Formasyon alanına dönüş - sahte kırılım olabilir\n"
                f"Tekrar sıkışma bekleniyor"
            )

        elif state == "FORMASYON_GECERSIZ":
            # Bu şablon bilerek korunuyor: ölü formasyonlar alarm akışından
            # kapı ile elenir (yalnız manuel/test gönderiminde buraya düşülür).
            reason = data.get('invalid_reason', 'Süre doldu veya bozuldu')
            msg = (
                f"⚪ {stock} {tf_human} {pattern} geçersiz oldu\n"
                f"Sebep: {reason}\n"
                f"Yeni oluşum için takipteyim"
            )

        else:
            msg = (
                f"{emoji} {stock} {tf_human} {pattern}\n"
                f"Durum: {state} | Kalite: {quality:.0f} {q_emoji}\n"
                f"Seviye: {price:.2f} | {contraction_str}\n"
                f"{time_str}"
            )

        footer_options = [
            f"\n\n💡 Detaylı analiz için grafiğe bak - {stock} {timeframe}",
            f"\n\n📊 Kendi analizini de ekle, sadece formasyon yetmez",
            f"\n\n🔍 {stock} {tf_human} - daha fazlası için takipte kal",
        ]
        if state in ["KIRILIM_ADAYI", "KIRILIM_TEYITLI", "RETEST_BASARILI", "FORMASYON_TAMAMLANDI"]:
            msg += random.choice(footer_options)

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
            candidate_state = str(candidate.get("state") or "izlemede").replace("_", " ").lower()
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
            if kuyrukla and self.enabled:
                # Kaybolmasın: kap/cooldown açılınca kuyruktan gönderilir.
                self._kuyruga_ekle(data, engel)
            logger.info(f"{stock} {pattern} {timeframe} {state} - cooldown, gönderilmiyor")
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
                logger.info(f"[MOCK CHANNEL {state}]\n{message}\n")
            key = self._cooldown_key(stock, pattern, timeframe, state)
            self.last_sent[key] = datetime.now(ISTANBUL_TZ)
            self._gonderim_kaydet()
            self.gonderilen_alarm += 1
            self._gonderim_sagligi_kaydet(basari=True)
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
                # Public kanala da gönder (filtreli)
                if self.should_send_to_public(data):
                    self.send_to_channel(message)
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
