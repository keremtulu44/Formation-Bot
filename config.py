# --- CONFIG ---
# BIST Formasyon Botu - Konfigürasyon
# Tüm ayarlar burada, kodun geri kalanı buradan okur
# Türkçe yorumlar: Neden bu değer? Pine'daki karşılığı ne?

from datetime import time
import pytz

# === PROFIL AYARI ===
# Pine'daki 3 profil: Hassas, Dengeli, Seçici
# Dengeli = default, en mantıklı
PROFILE = "Dengeli"  # Hassas / Dengeli / Seçici

# === BIST HİSSE LİSTESİ ===
# 50 en likit hisse - BIST30 + BIST50 karışımı
# TradingView formatı: BIST:THYAO, Yahoo formatı: THYAO.IS
# Şimdilik TradingView formatını baz alıyoruz, data katmanı çevirir
# Aciliyeti yok dedin, o yüzden ilk 30 ile başlayıp genişletiriz
BIST_50 = [
    "THYAO", "GARAN", "AKBNK", "ISCTR", "YKBNK", "KCHOL", "SAHOL", "EREGL", "SISE", "BIMAS",
    "ASELS", "TUPRS", "FROTO", "TOASO", "KRDMD", "PETKM", "PGSUS", "SASA", "HEKTS", "GUBRF",
    "KOZAL", "KOZAA", "EKGYO", "HALKB", "VAKBN", "TCELL", "TTKOM", "TAVHL", "DOHOL", "ALARK",
    "ARCLK", "ENKAI", "ODAS", "ASTOR", "KONTR", "SMRTG", "CWENE", "SNGYO", "ISMEN", "SKBNK",
    "TSKB", "TTRAK", "OTKAR", "AKSA", "AKSEN", "AYDEM", "BRSAN", "CIMSA", "DOAS", "EGEEN"
]

# BIST30 alt kümesi - hızlı test için
BIST_30 = BIST_50[:30]

# Hangi listeyi kullanacağız? Başlangıçta 30 ile test, prod'da 50
ACTIVE_STOCKS = BIST_30  # Prod'da BIST_50 yapacağız

# === ZAMAN AYARLARI ===
# BIST seans saatleri: 09:50 - 18:10 İstanbul
ISTANBUL_TZ = pytz.timezone("Europe/Istanbul")
BIST_OPEN = time(9, 50)
BIST_CLOSE = time(18, 10)

# === VERİ KATMANI AYARLARI ===
# Rolling window: 60 iş günü ~ 360 saatlik mum (günde ~6 saat * 60)
DEQUE_MAXLEN = 360

# Rate limit: her hisse arası bekleme
RATE_LIMIT_MIN = 45  # saniye
RATE_LIMIT_MAX = 50  # saniye

# === PROFİL PARAMETRELERİ (Pine'dan birebir) ===
def get_profile_params(profile: str):
    """
    Pine'daki base* değişkenlerini Python'a çevirir
    Neden fonksiyon? Çünkü manuel override de olabilir ileride
    """
    if profile == "Hassas":
        return {
            "pivot_len": 3,
            "min_age": 12,
            "min_touch_gap": 5,
            "touch_atr_mult": 0.15,
            "min_contraction_pct": 25.0,
            "break_atr_mult": 0.04,
            "confirm_window": 2,
            "min_pole_atr": 2.0,
            "min_pole_efficiency": 0.55,
            "max_pole_bars": 16,
            "max_consolidation_bars": 30,
            "min_raw_quality": 45.0,
            "min_specialized_quality": 48.0,
            "min_pole_quality": 40.0,
            "min_break_strength": 42.0,
            "retest_window": 5,
            "retest_hold_window": 2,
            "flat_slope_norm_tol": 0.030,
            "min_slope_norm_tol": 0.006,
        }
    elif profile == "Seçici":
        return {
            "pivot_len": 7,
            "min_age": 28,
            "min_touch_gap": 9,
            "touch_atr_mult": 0.08,
            "min_contraction_pct": 45.0,
            "break_atr_mult": 0.08,
            "confirm_window": 3,
            "min_pole_atr": 3.6,
            "min_pole_efficiency": 0.70,
            "max_pole_bars": 26,
            "max_consolidation_bars": 50,
            "min_raw_quality": 65.0,
            "min_specialized_quality": 68.0,
            "min_pole_quality": 58.0,
            "min_break_strength": 58.0,
            "retest_window": 7,
            "retest_hold_window": 4,
            "flat_slope_norm_tol": 0.018,
            "min_slope_norm_tol": 0.006,
        }
    else:  # Dengeli - en iyi denge: random %22, collective 16
        return {
            "pivot_len": 5,
            "min_age": 16,
            "min_touch_gap": 7,
            "touch_atr_mult": 0.10,
            "min_contraction_pct": 35.0,
            "break_atr_mult": 0.06,
            "confirm_window": 2,
            "min_pole_atr": 2.8,
            "min_pole_efficiency": 0.62,
            "max_pole_bars": 20,
            "max_consolidation_bars": 40,
            "min_raw_quality": 58.0,  # Adım3: 46->58, random kalite 77-95 ama yine de filtre
            "min_specialized_quality": 62.0,  # Adım3: 50->62
            "min_pole_quality": 49.0,
            "min_break_strength": 50.0,
            "retest_window": 5,
            "retest_hold_window": 3,
            "flat_slope_norm_tol": 0.024,
            "min_slope_norm_tol": 0.006,
        }

PROFILE_PARAMS = get_profile_params(PROFILE)

# === DİĞER SABİTLER ===
MAX_PIVOTS = 24
SEARCH_PIVOTS = 6
MAX_PATH_SAMPLE = 120
MAX_VIOLATION_SCAN = 220
MAX_VIOLATION_CACHE = 100
MAX_HISTORY_OFFSET = 900

# === TELEGRAM AYARLARI - İnsanlaştırma V2 ===
# Token ve chat_id .env'den gelecek, burada hardcoded yok
# İnsanlaştırma yapıldı, state bazlı mesajlar
TELEGRAM_COOLDOWN_HOURS = 4  # Aynı pattern+state için spam önleme

# Alert kalite eşikleri - toplu test 73 pattern ort 80.5, 38% >=80
# Tespit eşiği 46 (Dengeli) ama alert için daha yüksek olmalı yoksa çok spam
# Timeframe'e göre kademeli: 1h daha gürültülü, daha yüksek eşik
ALERT_MIN_QUALITY = {
    "1h": 80,  # saatlik gürültülü, sadece yüksek kalite alert
    "2h": 78,
    "4h": 75,
    "1d": 70,  # günlük daha az pattern, daha düşük eşik kabul
}
# Global fallback
ALERT_MIN_QUALITY_GLOBAL = 75

# Sadece önemli state'lerde alert gönder (ADAY_OLUSUYOR spam olur)
ALERT_STATES = [
    "KIRILIM_ADAYI",
    "KIRILIM_TEYITLI",
    "RETEST_BASARILI",
    "FORMASYON_TAMAMLANDI",
    "SIKISMA_GUCLENIYOR",  # sıkışma da önemli, erken uyarı
]

# === LOGGING ===
LOG_DIR = "/var/log/bist-bot"  # Prod'da bu path, local'de ./logs
LOG_FILE = "bot.log"
LOCAL_LOG_DIR = "./logs"  # Local test için

# === KALICI VERİ ===
DATA_DIR = "./bot_data"  # Her hisse için pickle/json
