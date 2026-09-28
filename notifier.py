# --- TELEGRAM NOTIFIER - İNSANLAŞTIRMA V2 ---
# Neden insanlaştırma? Robot gibi "FORMASYON_TESPIT" değil, trader dostu mesaj
# "Her şeyi dışarı çıkarma avantajı sun dışarda insanlaştırma" dedin - o yüzden teaser tarzı
# Türkçe, samimi, ama teknik seviyeyi koruyan

import os
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from config import DATA_DIR, TELEGRAM_MAX_MESAJ_SAAT, TELEGRAM_MAX_MESAJ_GUN

logger = logging.getLogger(__name__)

# Pattern emoji ve açıklama
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

# Saatlik kapan aşıldığında BİLE geçmesine izin verilen (aksiyon gerektiren) state'ler.
# SIKISMA_GUCLENIYOR / tanımlama state'leri "izleme" kategorisidir: fırtına anında
# sessiz kalabilir, kırılım/retest sinyalleri kaçmamalı.
KRITIK_STATELER = (
    "KIRILIM_ADAYI", "KIRILIM_TEYITLI", "RETEST_BASARILI", "FORMASYON_TAMAMLANDI",
    "KIRILIM_DENEMESI", "BASARISIZ_KIRILIM",
)

# Timeframe insanlaştırma
TF_HUMAN = {
    "1h": "saatlik",
    "2h": "2 saatlik",
    "4h": "4 saatlik",
    "1d": "günlük",
}

# Kalite yorumu
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

class TelegramNotifier:
    """
    Telegram bildirim yöneticisi - İnsanlaştırma V2
    - Cooldown: aynı pattern için 4 saat
    - State bazlı insanlaştırma: her state farklı ton
    - Avantajı dışarda sun: her şeyi söyleme, merak uyandır
    - AL/SAT yok, sadece durum bildirimi
    """
    def __init__(self, persistent_store=None, initial_store_data=None):
        self.persistent_store = persistent_store
        self.initial_store_data = initial_store_data if isinstance(initial_store_data, dict) else {}
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        self.cooldown_hours = 4
        self.last_sent: Dict[str, datetime] = {}
        # --- GLOBAL KAPANI (FAZ 2) ---
        # Cooldown tek tek spam'i engeller ama üst sınır yoktur: teorik 3600 mesaj/gün.
        # Saatlik/günlük sayaç + saatlik kap aşıldığında sadece KRITIK_STATELER geçer.
        self.max_saatlik = TELEGRAM_MAX_MESAJ_SAAT
        self.max_gunluk = TELEGRAM_MAX_MESAJ_GUN
        self._saatlik_zamanlar: List[datetime] = []   # son 1 saatteki gönderimler
        self._gunluk_sayac = 0
        self._gunluk_tarih = datetime.now().date()
        self._kap_uyarildi = False  # aynı saat penceresinde 1 kez uyar
        # Cooldown kalıcılığı: restart sonrası aynı mesajın tekrar gitmesini engeller
        self._cooldown_dosya = os.path.join(os.path.dirname(DATA_DIR) or ".", "bot_data", "telegram_soguma.json")
        self._kap_dosya = os.path.join(os.path.dirname(self._cooldown_dosya), "telegram_kap.json")
        self._cooldown_yukle()
        self._kap_yukle()
        
        if not self.token or not self.chat_id:
            logger.warning("Telegram token/chat_id env'de yok - notifier pasif (test modu)")
            self.enabled = False
        else:
            self.enabled = True
            logger.info("Telegram notifier aktif - insanlaştırma V2")

    def check_connection(self) -> bool:
        """Başlangıçta token'ı doğrular (getMe). Mesaj GÖNDERMEZ, sadece loglar.

        Render'a yeni ortam değişkeni ekledikten sonra "Telegram çalışıyor mu?"
        sorusunu loglardan tek bakışta cevaplamak için. Token loglanmaz.
        """
        if not self.enabled:
            return False
        try:
            import requests
            resp = requests.get(
                f"https://api.telegram.org/bot{self.token}/getMe", timeout=10
            )
            if resp.status_code == 200:
                username = (resp.json().get("result") or {}).get("username", "?")
                logger.info(
                    f"Telegram bağlantısı OK (bot: @{username}, chat_id: {self.chat_id})"
                )
                return True
            logger.error(
                f"Telegram token/chat_id reddedildi: HTTP {resp.status_code} "
                f"{resp.text[:200]}"
            )
        except Exception as e:
            logger.error(f"Telegram bağlantı hatası (token yanlış olabilir): {e}")
        return False

    def _kap_yukle(self):
        """Saatlik/günlük sayaçları diskten yükle (restart kapani aşmasın)."""
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
            self._saatlik_zamanlar = [datetime.fromisoformat(t) for t in ham.get("saatlik", [])]
            logger.info(f"Telegram kap hafızası {kaynak} yüklendi: saatlik={len(self._saatlik_zamanlar)}, "
                        f"günlük={self._gunluk_sayac}")
        except Exception as e:
            logger.debug(f"Kap hafızası yüklenemedi (ilk çalışma olabilir): {e}")

    def _gonderim_kaydet(self):
        """Başarılı gönderimi sayaçlara işle (mock mod dahil)."""
        self._gunu_sifirla_gerekirse()
        self._saatligi_temizle()
        self._saatlik_zamanlar.append(datetime.now())
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
        bugun = datetime.now().date()
        if bugun != self._gunluk_tarih:
            self._gunluk_sayac = 0
            self._gunluk_tarih = bugun
            self._kap_uyarildi = False

    def _saatligi_temizle(self):
        sinir = datetime.now() - timedelta(hours=1)
        self._saatlik_zamanlar = [t for t in self._saatlik_zamanlar if t > sinir]

    def kap_durumu(self) -> Dict:
        """İzleme/log için kap durumu."""
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
                self.last_sent[k] = datetime.fromisoformat(iso)
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
        # State de dahil - aynı pattern farklı state'e geçince tekrar gönder
        # Ama aynı state için cooldown
        return f"{stock}_{pattern}_{timeframe}_{state}"

    def can_send(self, stock: str, pattern: str, timeframe: str, state: str = "") -> bool:
        key = self._cooldown_key(stock, pattern, timeframe, state)
        if key not in self.last_sent:
            cooldown_tamam = True
        else:
            elapsed = datetime.now() - self.last_sent[key]
            cooldown_tamam = elapsed > timedelta(hours=self.cooldown_hours)
        if not cooldown_tamam:
            return False

        # --- GLOBAL KAPANI (FAZ 2) ---
        self._gunu_sifirla_gerekirse()
        self._saatligi_temizle()
        if self._gunluk_sayac >= self.max_gunluk:
            # Günlük sınır: telegram SUSAR (log'da kalır). Bir kez uyar.
            if not self._kap_uyarildi:
                self._kap_uyarildi = True
                logger.error(
                    f"TELEGRAM GÜNLÜK KAPANI AŞILDI ({self.max_gunluk} mesaj) - bugün başka "
                    f"mesaj gönderilmeyecek. Tüm sinyaller log dosyasında."
                )
            return False
        if len(self._saatlik_zamanlar) >= self.max_saatlik:
            # Saatlik sınır: sadece kritik (aksiyon gerektiren) state'ler geçer.
            if state in KRITIK_STATELER:
                return True
            if not self._kap_uyarildi:
                self._kap_uyarildi = True
                logger.warning(
                    f"TELEGRAM SAATLİK KAPANI AŞILDI ({self.max_saatlik} mesaj/saat) - "
                    f"sadece kritik sinyaller (kırılım/retest) gönderilecek."
                )
            return False
        return True

    def format_message(self, data: Dict) -> str:
        """
        İnsanlaştırılmış mesaj - state bazlı
        data: stock_name, timeframe, pattern_name, state, confidence_score, critical_price_level, timestamp, break_dir, contraction, etc.
        """
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
        
        tf_human = TF_HUMAN.get(timeframe, timeframe)
        emoji = PATTERN_EMOJI.get(pattern, "📈")
        q_comment = quality_comment(quality)
        q_emoji = quality_emoji(quality)
        
        # Saat formatı
        if isinstance(timestamp, str):
            time_str = timestamp
        else:
            try:
                time_str = timestamp.strftime("%d %b %H:%M")
            except:
                time_str = str(timestamp)

        # Daralma yorumu
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

        # === STATE BAZLI MESAJLAR ===
        # Her state farklı ton, farklı avantaj sunumu
        
        if state == "ADAY_OLUSUYOR":
            templates = [
                f"{emoji} {stock} {tf_human} grafikte {pattern} oluşuyor...\n"
                f"Kalite {quality:.0f} {q_emoji} ({q_comment}), {contraction_str}\n"
                f"Üst {upper:.2f} / Alt {lower:.2f} bandında sıkışma var\n"
                f"Takipteyiz 👀 - kırılıma yaklaştıkça haber veririm",
                
                f"👀 {stock}'da bir şeyler oluyor\n"
                f"{tf_human} grafikte {pattern} {q_comment} duruyor (kalite {quality:.0f})\n"
                f"{contraction_str}, bant {lower:.2f} - {upper:.2f}\n"
                f"Henüz erken ama radarımda 📡",
            ]
            msg = random.choice(templates)
            
        elif state == "GEOMETRI_ADAYI":
            msg = (
                f"{emoji} {stock} {tf_human} - {pattern} geometrisi oturuyor\n"
                f"Kalite {quality:.0f} {q_emoji}, {contraction_str}\n"
                f"Bant: {lower:.2f} - {upper:.2f}\n"
                f"Olgunlaşmasını bekliyorum..."
            )
            
        elif state == "FORMASYON_TANIMLANDI":
            msg = (
                f"📋 {stock} {tf_human} {pattern} tanımlandı\n"
                f"Kalite {quality:.0f} {q_emoji} ({q_comment}) {contraction_str}\n"
                f"Üst: {upper:.2f} Alt: {lower:.2f}\n"
                f"Sıkışma güçlenirse kırılım gelebilir"
            )
            
        elif state == "SIKISMA_GUCLENIYOR":
            msg = (
                f"⚡ {stock}'da sıkışma güçleniyor!\n"
                f"{tf_human} {pattern} {contraction_str} - sona yaklaşıyor\n"
                f"Kalite {quality:.0f} {q_emoji}, bant {lower:.2f}-{upper:.2f}\n"
                f"Kırılım yakın olabilir, gözüm üstünde 👁️"
            )
            
        elif state == "KIRILIM_HAZIRLIGI":
            msg = (
                f"⚠️ {stock} {tf_human} {pattern} kırılım hazırlığında\n"
                f"{contraction_str}, kalite {quality:.0f} {q_emoji}\n"
                f"Kritik seviyeler: {lower:.2f} / {upper:.2f}\n"
                f"Birkaç mum içinde hareket gelebilir"
            )
            
        elif state == "KIRILIM_DENEMESI":
            direction = "yukarı" if break_dir == 1 else "aşağı" if break_dir == -1 else ""
            level = upper if break_dir == 1 else lower
            msg = (
                f"🔥 {stock}'da deneme var!\n"
                f"{tf_human} {pattern} {direction} {level:.2f}'i zorluyor\n"
                f"Güç henüz düşük, teyit bekliyorum...\n"
                f"Kalite {quality:.0f} {q_emoji} | {time_str}"
            )
            
        elif state == "KIRILIM_ADAYI":
            direction = "YUKARI" if break_dir == 1 else "AŞAĞI" if break_dir == -1 else ""
            level = upper if break_dir == 1 else lower
            power = data.get('break_strength', quality)
            templates = [
                f"🚀 {stock} KIRIYOR! {direction}\n"
                f"{tf_human} {pattern} {level:.2f} üstünde kapanış\n"
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
                f"✅ {stock} teyit aldı! {direction} kırılım\n"
                f"{tf_human} {pattern} {level:.2f} kırılımı teyitli\n"
                f"Kalite {quality:.0f} {q_emoji}, {contraction_str}\n"
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
                f"{tf_human} {pattern} {direction} kırılım sonrası retest tuttu\n"
                f"Kalite {quality:.0f} {q_emoji} - formasyon tamamlanmaya yakın\n"
                f"Bu seviyelerden sonrası için kendi analizini yap"
            )
            
        elif state == "FORMASYON_TAMAMLANDI":
            direction = "yukarı" if break_dir == 1 else "aşağı"
            msg = (
                f"🏁 {stock} {pattern} TAMAMLANDI\n"
                f"{tf_human} grafikte {direction} kırılım + retest başarılı\n"
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
            reason = data.get('invalid_reason', 'Süre doldu veya bozuldu')
            msg = (
                f"⚪ {stock} {tf_human} {pattern} geçersiz oldu\n"
                f"Sebep: {reason}\n"
                f"Yeni oluşum için takipteyim"
            )
            
        else:
            # Fallback - teknik ama insanlaştırılmış
            msg = (
                f"{emoji} {stock} {tf_human} {pattern}\n"
                f"Durum: {state} | Kalite: {quality:.0f} {q_emoji}\n"
                f"Seviye: {price:.2f} | {contraction_str}\n"
                f"{time_str}"
            )

        # Footer - avantaj dışarda, her şeyi söyleme
        footer_options = [
            f"\n\n💡 Detaylı analiz için grafiğe bak - {stock} {timeframe}",
            f"\n\n📊 Kendi analizini de ekle, sadece formasyon yetmez",
            f"\n\n🔍 {stock} {tf_human} - daha fazlası için takipte kal",
        ]
        # Sadece önemli state'lerde footer ekle, her mesajda değil
        if state in ["KIRILIM_ADAYI", "KIRILIM_TEYITLI", "RETEST_BASARILI", "FORMASYON_TAMAMLANDI"]:
            msg += random.choice(footer_options)

        return msg

    def send(self, data: Dict) -> bool:
        stock = data.get('stock_name', '')
        pattern = data.get('pattern_name', '')
        timeframe = data.get('timeframe', '')
        state = data.get('state', '')

        if not self.can_send(stock, pattern, timeframe, state):
            logger.info(f"{stock} {pattern} {timeframe} {state} - cooldown, gönderilmiyor")
            return False

        message = self.format_message(data)

        if not self.enabled:
            logger.info(f"[MOCK TELEGRAM {state}]\n{message}\n")
            key = self._cooldown_key(stock, pattern, timeframe, state)
            self.last_sent[key] = datetime.now()
            self._gonderim_kaydet()
            return True

        try:
            import requests
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': message,
            }
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info(f"Telegram gönderildi: {stock} {pattern} {state}")
                key = self._cooldown_key(stock, pattern, timeframe, state)
                self.last_sent[key] = datetime.now()
                self._cooldown_kaydet()
                self._gonderim_kaydet()
                return True
            else:
                logger.error(f"Telegram hatası: {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Telegram gönderim hatası: {e}")
            return False


if __name__ == "__main__":
    # Test tüm state'ler
    notifier = TelegramNotifier()
    
    test_cases = [
        {'stock_name': 'THYAO', 'timeframe': '1h', 'pattern_name': 'Yükselen Üçgen', 'state': 'ADAY_OLUSUYOR', 'confidence_score': 83, 'critical_price_level': 302.11, 'upper_now': 302.11, 'lower_now': 294.32, 'contraction': 0.87, 'timestamp': datetime.now()},
        {'stock_name': 'GARAN', 'timeframe': '4h', 'pattern_name': 'Simetrik Üçgen', 'state': 'SIKISMA_GUCLENIYOR', 'confidence_score': 88, 'critical_price_level': 120.5, 'upper_now': 122.0, 'lower_now': 119.0, 'contraction': 0.91, 'timestamp': datetime.now()},
        {'stock_name': 'AKBNK', 'timeframe': '1h', 'pattern_name': 'Alçalan Kama', 'state': 'KIRILIM_ADAYI', 'confidence_score': 82, 'critical_price_level': 58.3, 'upper_now': 58.3, 'lower_now': 55.1, 'contraction': 0.75, 'break_dir': 1, 'break_strength': 82, 'timestamp': datetime.now()},
        {'stock_name': 'YKBNK', 'timeframe': '2h', 'pattern_name': 'Boğa Bayrağı', 'state': 'KIRILIM_TEYITLI', 'confidence_score': 79, 'critical_price_level': 32.5, 'upper_now': 32.5, 'lower_now': 31.2, 'contraction': 0.65, 'break_dir': 1, 'break_price': 32.5, 'timestamp': datetime.now()},
        {'stock_name': 'SAHOL', 'timeframe': '1h', 'pattern_name': 'Yükselen Üçgen', 'state': 'RETEST_BASARILI', 'confidence_score': 85, 'critical_price_level': 95.0, 'upper_now': 95.0, 'lower_now': 92.0, 'contraction': 0.88, 'break_dir': 1, 'timestamp': datetime.now()},
        {'stock_name': 'BIMAS', 'timeframe': '4h', 'pattern_name': 'Alçalan Üçgen', 'state': 'BASARISIZ_KIRILIM', 'confidence_score': 72, 'critical_price_level': 450.0, 'upper_now': 455.0, 'lower_now': 445.0, 'contraction': 0.60, 'timestamp': datetime.now()},
    ]
    
    for tc in test_cases:
        print("\n" + "="*50)
        print(f"STATE: {tc['state']}")
        print("="*50)
        print(notifier.format_message(tc))
        print()
