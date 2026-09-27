# --- CONFIG ---
# BIST Formasyon Botu - Konfigürasyon
# Pine v0.4.6 FINAL EXPORT birebir - matematik düzgün, yüzdeye göre oynama yok

import os
from datetime import date, datetime, time
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

# --- BIST RESMİ TATİL TAKVİMİ ---
# Kaynak: https://www.borsaistanbul.com/en/official-holidays (resmî BIST takvimi),
# 3 Türk aracı kaynakla çapraz doğrulandı (2026-09-27). markethours.io'nun İslami
# bayram tarihleri YANLIŞTI (31 Mart / 7-10 Haziran), kullanılmadı.
# YARIM GÜN: seans 13:00'te kapanır (son 1H mum 12:30 etiketli, 12:00-13:00).
# DİKKAT: İslami bayram tarihleri HER YIL DEĞİŞİR - her yıl başında güncellenmeli.
# Eksik takvime karşı koruma: veri kaynaklı "veri yok modu" (data.py) devrede -
# takvimde olmasa bile veri gelmiyorsa bot tatil moduna geçer.
BIST_TATILLER = {
    date(2026, 1, 1): "Yılbaşı",
    date(2026, 3, 20): "Ramazan Bayramı 1. gün",
    date(2026, 4, 23): "Ulusal Egemenlik ve Çocuk Bayramı",
    date(2026, 5, 1): "Emek ve Dayanışma Günü",
    date(2026, 5, 19): "Atatürk'ü Anma, Gençlik ve Spor Bayramı",
    date(2026, 5, 27): "Kurban Bayramı 1. gün",
    date(2026, 5, 28): "Kurban Bayramı 2. gün",
    date(2026, 5, 29): "Kurban Bayramı 3. gün",
    date(2026, 7, 15): "Demokrasi ve Milli Birlik Günü",
    date(2026, 10, 29): "Cumhuriyet Bayramı",
    # 2027 kesin tarihler (İslami bayramlar Diyanet açıklamasından sonra eklenecek)
    date(2027, 1, 1): "Yılbaşı",
    date(2027, 4, 23): "Ulusal Egemenlik ve Çocuk Bayramı",
    date(2027, 5, 19): "Atatürk'ü Anma, Gençlik ve Spor Bayramı",
    date(2027, 7, 15): "Demokrasi ve Milli Birlik Günü",
}

# Yarım gün: (açıklama, seans kapanış saati)
BIST_YARIM_GUNLER = {
    date(2026, 3, 19): ("Ramazan Bayramı arefesi", time(13, 0)),
    date(2026, 5, 26): ("Kurban Bayramı arefesi", time(13, 0)),
    date(2026, 10, 28): ("Cumhuriyet Bayramı arefesi", time(13, 0)),
}

# --- VERİ TAZELİĞİ / TATIL MODU EŞİKLERİ ---
# "Veri yok modu": seans içindeyiz, tatil değiliz ama en yeni 1H mum bu kadardır
# eskiyse bugün için veri gelmiyor demektir (bilinmeyen tatil / Yahoo arızası).
# Ölçüm: normal seans içi en yeni mum yaşı < 60 dk; tatil/arıza > 20 saat.
VERI_YOK_MODU_ESIK_DK = 20 * 60

# --- TELEGRAM GLOBAL KAPANI (FAZ 2) ---
# Cooldown (hisse+desen+TF+state, 4 saat) tek tek spam'i engeller ama üst sınır
# yoktur: 30 hisse x 4 TF x 5 desen x 5 state = 3000 anahtar x günde 6 kez
# teorik 18000 mesaj. Pratikte ölçüm: tek taramada 12-40 mesaj.
# Günde/saatte üst sınır koyuyoruz: aşıldığında sadece en kritik state'ler geçer.
# --- VERİ SÜREKLİLİK / SPLIT KONTROLÜ (FAZ 2) ---
# auto_adjust=False ile HAM fiyat geliyor (Pine/TV ile aynı). Ama hisse split/bedelsiz
# yaparsa Yahoo ham seride ani zıplama üretir: pivot, sınır, ATR ve kırılım sinyali
# SAHTE olur. Ölçüm (28 hisse, 10052 ardışık bar çifti): |open[i+1]-close[i]|/close[i]
# dağılımı p50=%0.00, p99=%1.08, p99.9=%4.17, MAKS=%9.97 -> %10 eşiği normal gürültünün
# çok üstünde, split'i ise yakalar.
SPLIT_SUREKLILIK_ESIK_PCT = 10.0
# Seans içi bar boşluğu: aynı gün 09:30-18:30 arasında 1H mum 1 saat aralıklı gelir.
# 1 mum atlanınca 2 saat boşluk oluşur -> eşik 1.5 saat (normal aralık 1 saat).
BAR_BOSLUK_ESIK_SAAT = 1.5
# --- TARAMA DRİFT KORUMASI (FAZ 2) ---
# Bir tarama 30 hisse x (45-50 sn rate limit + motor) ~= 24-26 dk sürer; mum
# kapanışları 60 dk arayla olduğu için normalde ~35 dk pay var. Tarama bu eşiği
# aşarsa (Yahoo yavaşlar, motor yavaşlar) bir sonraki mumu kaçırma riski doğar.
# Faz 1'deki "aynı mum iki kez taranmaz + kapanış bazlı tetik" yapısı sayesinde
# atlanan mum OLMAZ (sonraki döngüde taranır) ama gecikme büyür - ölçüp uyarıyoruz.
TARAMA_SURESI_UYARI_DK = 45

# --- 1D DERİNLİK (FAZ 2) ---
# 1H deque 360 bar = ~40 iş günü -> resample ile 1D sadece ~40 bar (ölçüm).
# 1D üçgen/kama oluşumu 20-60 bar sürdüğü için bu pencere MARJINAL.
# DEQUE_MAXLEN'i artırmak (A) 1H penceresini de büyütür ve Pine ile birebir uyumu
# bozabilir (Pine'da kaç bar kullanıldığı henüz bilinmiyor) -> REDDEDİLDİ.
# Buna karşılık 1D verisini AYRI ve DERİN çekiyoruz (B): 1H/2h/4h Pine uyumu
# KORUNUR, sadece günlük pencere ~2 yıla çıkar. Maliyet: günde 30 ek fetch
# (sadece günlük bar eksikse çekilir, yoksa cache).
GUNLUK_FETCH_PERIOD = "2y"
GUNLUK_DEQUE_MAXLEN = 500

TELEGRAM_MAX_MESAJ_SAAT = 20
TELEGRAM_MAX_MESAJ_GUN = 120

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
