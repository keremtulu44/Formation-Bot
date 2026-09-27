# --- CONFIG ---
# BIST Formasyon Botu - Konfigürasyon
# Pine v0.4.6 FINAL EXPORT birebir - matematik düzgün, yüzdeye göre oynama yok

import os
from datetime import time
import pytz

# .env desteği - local ve /etc/bist-bot.env için
try:
    from dotenv import load_dotenv
    # Önce proje kökündeki .env
    load_dotenv()
    # Sonra systemd EnvironmentFile yolu
    if os.path.exists("/etc/bist-bot.env"):
        load_dotenv("/etc/bist-bot.env", override=False)
except ImportError:
    pass

PROFILE = os.getenv("BOT_PROFILE", "Dengeli").strip() or "Dengeli"
# Sadece 3 profile izin ver, yoksa Dengeli'ye düş
if PROFILE not in ("Hassas", "Dengeli", "Seçici"):
    PROFILE = "Dengeli"

BIST_50 = [
    "THYAO", "GARAN", "AKBNK", "ISCTR", "YKBNK", "KCHOL", "SAHOL", "EREGL", "SISE", "BIMAS",
    "ASELS", "TUPRS", "FROTO", "TOASO", "KRDMD", "PETKM", "PGSUS", "SASA", "HEKTS", "GUBRF",
    "KOZAL", "KOZAA", "EKGYO", "HALKB", "VAKBN", "TCELL", "TTKOM", "TAVHL", "DOHOL", "ALARK",
    "ARCLK", "ENKAI", "ODAS", "ASTOR", "KONTR", "SMRTG", "CWENE", "SNGYO", "ISMEN", "SKBNK",
    "TSKB", "TTRAK", "OTKAR", "AKSA", "AKSEN", "AYDEM", "BRSAN", "CIMSA", "DOAS", "EGEEN"
]
BIST_30 = BIST_50[:30]
ACTIVE_STOCKS = BIST_30

ISTANBUL_TZ = pytz.timezone("Europe/Istanbul")
BIST_OPEN = time(9, 50)     # gerçek BIST seans başlangıcı (Yahoo ilk mumu 09:30 etiketli)
BIST_CLOSE = time(18, 10)   # gerçek BIST kapanışı + tampon

# --- CANLI TARAMA ZAMANLAMASI (yfinance .IS verisinden ÖLÇÜLDÜ, varsayım değil) ---
# Ölçüm 1: 1H bar etiketleri 09:30, 10:30, ... 17:30 (günde 9 mum) ve barlar bitişik
#           (close[i] == open[i+1])  ->  etiket = MUM BAŞI, mum :30'da kapanır.
# Ölçüm 2: 17:30 etiketli (günün son) mumun hacmi ortalama mumun %91'i -> TAM mum,
#           yani son mum 18:30'da kapanır (Yahoo'nun .IS seansı 09:30-18:30).
# Ölçüm 3: 09:30 etiketli mumun hacmi ~0 (yfinance'nin bilinen ilk-bar hatası),
#           OHLC'i gerçek -> filtrelemeye gerek yok, sadece hacim skoru nötr kalır.
# ESKİ HATA: tetikleyici "saat başı + 5 dk" (=:05) idi. Mum :30'da kapandığı için
#            her tarama veriyi 35 dk geç gösteriyordu ve günün son mumu (18:30
#            kapanış) hiç analiz edilmiyordu (pencere 18:10'da kapanıyordu).
CANDLE_CLOSE_MINUTE = 30          # 1H mumun kapanış dakikası (saat başından offset)
SCAN_DELAY_AFTER_CLOSE_MIN = 5    # mum kapanışından kaç dk sonra taranacak
TARAMA_PENCERE_SONU = time(18, 40)  # son mum 18:30 kapanır + 5 dk = 18:35 (+ pay)
STALE_BAR_UYARI_DK = 120          # en yeni 1H mum bu kadardır eskiyse "kör çalışma" uyarısı
TERMINAL_TAZE_BAR = 3             # terminal (ölü) formasyon bu kadar bar içindeyse haber ver

DEQUE_MAXLEN = 360
RATE_LIMIT_MIN = 45
RATE_LIMIT_MAX = 50

def get_profile_params(profile: str):
    if profile == "Hassas":
        return {
            "pivot_len": 3,
            "min_age": 10,
            "min_touch_gap": 3,
            "touch_atr_mult": 0.20,
            "min_contraction_pct": 15.0,
            "break_atr_mult": 0.04,
            "confirm_window": 2,
            "min_pole_atr": 2.0,
            "min_pole_efficiency": 0.55,
            "max_pole_bars": 16,
            "max_consolidation_bars": 30,
            "min_raw_quality": 38.0,
            "min_specialized_quality": 42.0,
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
            "min_age": 24,
            "min_touch_gap": 7,
            "touch_atr_mult": 0.12,
            "min_contraction_pct": 35.0,
            "break_atr_mult": 0.08,
            "confirm_window": 3,
            "min_pole_atr": 3.6,
            "min_pole_efficiency": 0.70,
            "max_pole_bars": 26,
            "max_consolidation_bars": 50,
            "min_raw_quality": 55.0,
            "min_specialized_quality": 58.0,
            "min_pole_quality": 58.0,
            "min_break_strength": 58.0,
            "retest_window": 7,
            "retest_hold_window": 4,
            "flat_slope_norm_tol": 0.018,
            "min_slope_norm_tol": 0.006,
        }
    else:
        return {
            "pivot_len": 5,
            "min_age": 16,
            "min_touch_gap": 5,
            "touch_atr_mult": 0.15,
            "min_contraction_pct": 25.0,
            "break_atr_mult": 0.06,
            "confirm_window": 2,
            "min_pole_atr": 2.8,
            "min_pole_efficiency": 0.62,
            "max_pole_bars": 20,
            "max_consolidation_bars": 40,
            "min_raw_quality": 46.0,
            "min_specialized_quality": 50.0,
            "min_pole_quality": 49.0,
            "min_break_strength": 50.0,
            "retest_window": 5,
            "retest_hold_window": 3,
            "flat_slope_norm_tol": 0.024,
            "min_slope_norm_tol": 0.006,
        }

PROFILE_PARAMS = get_profile_params(PROFILE)

MAX_PIVOTS = 24
SEARCH_PIVOTS = 6
MAX_PATH_SAMPLE = 120
MAX_VIOLATION_SCAN = 220
MAX_VIOLATION_CACHE = 100
MAX_HISTORY_OFFSET = 900

TELEGRAM_COOLDOWN_HOURS = 4
ALERT_MIN_QUALITY = {
    "1h": 80,
    "2h": 78,
    "4h": 75,
    "1d": 70,
}
ALERT_MIN_QUALITY_GLOBAL = 75
ALERT_STATES = [
    "KIRILIM_ADAYI",
    "KIRILIM_TEYITLI",
    "RETEST_BASARILI",
    "FORMASYON_TAMAMLANDI",
    "SIKISMA_GUCLENIYOR",
]

LOG_DIR = "/var/log/bist-bot"
LOG_FILE = "bot.log"
LOCAL_LOG_DIR = "./logs"
DATA_DIR = "./bot_data"
