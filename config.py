# --- CONFIG ---
# BIST Formasyon Botu - Konfigürasyon
# Pine v0.4.6 FINAL EXPORT birebir - matematik düzgün, yüzdeye göre oynama yok

import os
from datetime import date, time
import pytz


_APP_DIR = os.path.dirname(os.path.abspath(__file__))


def _resolve_app_path(value, default):
    """Resolve relative storage/log paths against the application directory.

    This keeps ``./bot_data`` and ``./logs`` stable when systemd, CI, or an
    operator starts the process from a different working directory.
    """
    raw = str(value or "").strip() or str(default)
    path = os.path.expanduser(raw)
    if not os.path.isabs(path):
        path = os.path.join(_APP_DIR, path)
    return os.path.abspath(path)

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

# --- PAZAR / SAĞLAYICI (C1) ---
# Sağlayıcı sembol eki ve seans adları artık tek yerde: başka bir pazara (örn.
# başka bir borsa) uyarlamak için kod içindeki ".IS" aramak gerekmez.
MARKET_SUFFIX = os.getenv("MARKET_SUFFIX", ".IS").strip() or ".IS"

# Sağlayıcı sembol eşlemesi: standart BIST hisseleri `sembol + MARKET_SUFFIX`
# (örn. THYAO -> THYAO.IS) kullanırken endeks ve emtia sembolleri doğrudan Yahoo
# karşılıklarına çevrilir.
PROVIDER_SYMBOL_MAP = {
    # --- BIST endeksleri (Yahoo'da `.IS` ekiyle) -----------------------------
    "XU100": "XU100.IS",
    "XU30": "XU030.IS",
    "XU030": "XU030.IS",
    "XU50": "XU050.IS",
    "XU050": "XU050.IS",
    "XBANK": "XBANK.IS",
    "XUSIN": "XUSIN.IS",
    "XUTUM": "XUTUM.IS",
    # --- Makro (BIST dışı, kendi seansı) ------------------------------------
    "BRENT": "BZ=F",
    "USDTRY": "USDTRY=X",
    # Ad uluslararası parite adı: XAU/USD (ons altın) ve XAG/USD (ons gümüş).
    # Türkçe "ALTIN/GUMUS" adları 2026-10-25'te kaldırıldı; kullanıcı hangi
    # ürünü izlediğini kodda da görsün diye sembol adı = parite adı.
    "XAUUSD": "XAUUSD=X",
    "XAGUSD": "XAGUSD=X",
}

#: Sağlayıcı bir sembolü tanımıyorsa (boş geçmiş) devreye giren YEDEK eşleme.
#: Spot parite (`XAUUSD=X`) sağlayıcıda yoksa ons VADELİ seri kullanılır; ikisi
#: de ons fiyatını izler, fark vadeli primidir. Amaç sessiz veri boşluğu yerine
#: verinin akmaya devam etmesi: hangi serinin kullanıldığı loga yazılır.
PROVIDER_SYMBOL_FALLBACK = {
    "XAUUSD": "GC=F",   # COMEX ons altın (vadeli)
    "XAGUSD": "SI=F",   # COMEX ons gümüş (vadeli)
}

#: Endeks sembolleri: hisse değildir, "hisse" diye sayılmaz/etiketlenmez.
ENDEKS_SEMBOLLERI = frozenset({"XU100", "XU30", "XU030", "XU50", "XU050",
                               "XBANK", "XUSIN", "XUTUM"})
#: Makro semboller: BIST dışı seans (ABD/forex). Kapanış kuralı BIST seansına
#: göre hesaplandığı için gün sonu barları BIST kapanışıyla hizalanmaz; bu
#: yüzden varsayılan olarak YALNIZ veri/bağlam içindir, alarm üretmez
#: (`MAKRO_ALARM=1` ile açılır). BRENT geçmişte alarm üretiyordu; karar artık
#: tek bayrakta toplandı.
MAKRO_SEMBOLLERI = frozenset({"BRENT", "USDTRY", "XAUUSD", "XAGUSD"})
#: Makro semboller alarm üretsin mi? Varsayılan KAPALI: bu sembollerin seans
#: kapanışı BIST'e göre değil (ABD/forex), "yalnız kapanmış mum" kuralı gün sonu
#: barlarında tam doğrulanamaz. Veri/grafik/bağlam her durumda çalışır.
MAKRO_ALARM = str(os.getenv("MAKRO_ALARM", "0")).strip().lower() in (
    "1", "true", "evet", "açık", "acik", "yes", "on")

#: Sağlayıcı bu sembollerde hacim vermiyor (endeks) veya güvenilmez (makro).
#: Kart "hacim yok" demek yerine nedeni yazar (bkz. notification_context).
HACIMSIZ_SEMBOLLERI = ENDEKS_SEMBOLLERI | MAKRO_SEMBOLLERI


def sembol_turu(sembol: str) -> str:
    """Sembol sınıfı: "endeks" | "makro" | "hisse" (kart/rapor dili için)."""
    anahtar = str(sembol or "").strip().upper()
    if anahtar in ENDEKS_SEMBOLLERI:
        return "endeks"
    if anahtar in MAKRO_SEMBOLLERI:
        return "makro"
    return "hisse"


def yahoo_ticker_for_symbol(stock: str) -> str:
    key = str(stock or "").strip().upper()
    if key in PROVIDER_SYMBOL_MAP:
        return PROVIDER_SYMBOL_MAP[key]
    if any(ch in key for ch in ("=", "^", ".")):
        return key
    return key + MARKET_SUFFIX


BIST_50 = [
    "THYAO", "GARAN", "AKBNK", "ISCTR", "YKBNK", "KCHOL", "SAHOL", "EREGL", "SISE", "BIMAS",
    "ASELS", "TUPRS", "FROTO", "TOASO", "KRDMD", "PETKM", "PGSUS", "SASA", "HEKTS", "GUBRF",
    "EKGYO", "HALKB", "VAKBN", "TCELL", "TTKOM", "TAVHL", "DOHOL", "ALARK",
    "ARCLK", "ENKAI", "ODAS", "ASTOR", "KONTR", "SMRTG", "CWENE", "SNGYO", "ISMEN", "SKBNK",
    "TSKB", "TTRAK", "OTKAR", "AKSA", "AKSEN", "AYDEM", "BRSAN", "CIMSA", "DOAS", "EGEEN",
    "XU100", "XU30", "BRENT",
    # 2026-10-22 (kullanıcı kararı): BIST 50 + sektör endeksleri + makro.
    # Endeksler hisse gibi taranır (alarm üretir); makro semboller veri/bağlam
    # içindir (alarm `MAKRO_ALARM` ile açılır).
    "XU50", "XBANK", "XUSIN", "USDTRY", "XAUUSD", "XAGUSD",
]
BIST_30 = BIST_50[:30]
# Canlı tarama evreni: mevcut BIST 50 listesinden Yahoo verisi sorunlu KOZAL/KOZAA çıkarıldı (48 sembol).
# Eksik iki bileşen için sağlayıcı desteği doğrulanmış semboller sonra eklenebilir.
# C1: evren env ile değiştirilebilir (virgülle ayrılmış semboller).
#   STOCK_UNIVERSE=THYAO,GARAN,AKBNK
_STOCK_UNIVERSE = [x.strip().upper() for x in os.getenv("STOCK_UNIVERSE", "").split(",") if x.strip()]
ACTIVE_STOCKS = _STOCK_UNIVERSE or BIST_50
#: Evren etiketi: "54 sembol (48 hisse + 4 endeks + 2 makro)". Tek yerde
#: hesaplanır ki /durum, tarama yanıtı ve özet aynı sayıyı söylesin.
def evren_ozeti(semboller=None, ayrinti: bool = True) -> str:
    """Evren etiketi: "57 sembol (48 hisse + 5 endeks + 4 makro)".

    `ayrinti=False` → yalnız "57 sembol". Gerekçe: günlük özet/panel satırları
    283 px bütçesine sığmıyor; kırpılmış parantez ("48 hisse + 5 endeks +\n
    4 makro") okunmuyordu. Ayrıntı `/durum`da kalır.
    """
    liste = list(semboller if semboller is not None else ACTIVE_STOCKS)
    ozet = f"{len(liste)} sembol"
    if not ayrinti:
        return ozet
    endeks = sum(1 for s in liste if sembol_turu(s) == "endeks")
    makro = sum(1 for s in liste if sembol_turu(s) == "makro")
    hisse = len(liste) - endeks - makro
    parcalar = [f"{hisse} hisse"] if hisse else []
    if endeks:
        parcalar.append(f"{endeks} endeks")
    if makro:
        parcalar.append(f"{makro} makro")
    return ozet + (f" ({' + '.join(parcalar)})" if parcalar else "")


# Yahoo Finance istek temposu. Kısa istek aralığı + grup molası; paralel istek yok.
def _env_float(name: str, default: float) -> float:
    try:
        return max(0.0, float(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


SCAN_REQUEST_BATCH_SIZE = _env_int("SCAN_REQUEST_BATCH_SIZE", 10)
SCAN_REQUEST_DELAY_MIN_SEC = _env_float("SCAN_REQUEST_DELAY_MIN_SEC", 0.9)
SCAN_REQUEST_DELAY_MAX_SEC = max(
    SCAN_REQUEST_DELAY_MIN_SEC,
    _env_float("SCAN_REQUEST_DELAY_MAX_SEC", 1.5),
)
SCAN_BATCH_PAUSE_MIN_SEC = _env_float("SCAN_BATCH_PAUSE_MIN_SEC", 10.0)
SCAN_BATCH_PAUSE_MAX_SEC = max(
    SCAN_BATCH_PAUSE_MIN_SEC,
    _env_float("SCAN_BATCH_PAUSE_MAX_SEC", 15.0),
)
SCAN_RETRY_BACKOFF_MIN_SEC = _env_float("SCAN_RETRY_BACKOFF_MIN_SEC", 30.0)
SCAN_RETRY_BACKOFF_MAX_SEC = max(
    SCAN_RETRY_BACKOFF_MIN_SEC,
    _env_float("SCAN_RETRY_BACKOFF_MAX_SEC", 60.0),
)

# Büyük 1H geçmişi yalnızca soğuk/eski cache'te indir; normal tarama daha hafif.
FULL_1H_FETCH_PERIOD = "60d"
ROUTINE_1H_FETCH_PERIOD = "5d"
FULL_1H_FETCH_STALE_DAYS = 5

ISTANBUL_TZ = pytz.timezone("Europe/Istanbul")
BIST_OPEN = time(9, 50)     # gerçek BIST seans başlangıcı (Yahoo ilk mumu 09:30 etiketli)
BIST_CLOSE = time(18, 10)   # gerçek BIST kapanışı + tampon

# C1: sağlayıcıdan bağımsız seans adları (aynı değerler; yeni kod bunları okur).
SESSION_OPEN = BIST_OPEN
SESSION_CLOSE = BIST_CLOSE

# --- CANLI TARAMA ZAMANLAMASI (yfinance .IS verisinden ÖLÇÜLDÜ, varsayım değil) ---
# Ölçüm 1: 1H bar etiketleri 09:30, 10:30, ... 17:30 (günde 9 mum) ve barlar bitişik
#           (close[i] == open[i+1])  ->  etiket = MUM BAŞI, mum bir saat sonra kapanır.
# Ölçüm 2 (2 Eki 2026, chart API meta.currentTradingPeriod.regular): seans
#           09:30–18:00'dır; 17:30 etiketli son mum 18:00'de kapanır (kapanış
#           müzayedesi fiyatı ~18:09'da oluşur). Tarama barları yine :35'te
#           işlenir; 18:35 = günün son taraması.
# Ölçüm 3: 09:30 etiketli mumun hacmi ~0 (yfinance'nin bilinen ilk-bar hatası),
#           OHLC'i gerçek -> filtrelemeye gerek yok, sadece hacim skoru nötr kalır.
# ESKİ HATA: tetikleyici "saat başı + 5 dk" (=:05) idi. Mum :30'da kapandığı için
#            her tarama veriyi 35 dk geç gösteriyordu ve günün son mumu (18:30
#            kapanış) hiç analiz edilmiyordu (pencere 18:10'da kapanıyordu).
CANDLE_CLOSE_MINUTE = 30          # 1H mumun kapanış dakikası (saat başından offset)
SCAN_DELAY_AFTER_CLOSE_MIN = 5    # mum kapanışından kaç dk sonra taranacak
TARAMA_PENCERE_SONU = time(18, 40)  # son mum 18:00'de kapanır; 18:35 taraması + pay
STALE_BAR_UYARI_DK = 120          # en yeni 1H mum bu kadardır eskiyse "kör çalışma" uyarısı
OFFSESSION_CACHE_MAX_AGE_DAYS = max(1, _env_int("OFFSESSION_CACHE_MAX_AGE_DAYS", 14))  # seans dışı son mevcut veriye izin
TERMINAL_TAZE_BAR = 3             # terminal (ölü) formasyon bu kadar bar içindeyse haber ver

# --- BIST TATİL TAKVİMİ (manuel data-layer politikası; exhaustive değildir) ---
# Borsa İstanbul'un 2026 Official Holidays sayfası 19 Mar, 26 May ve 28 Eki yarım
# günlerini 13:00'e kadar listeliyor. Genelgenin Equity Market tablosu kapanış
# saatini vermediğinden 13:00 equity seans saati genel sayfayla sınırlı doğrulandı.
# Bu tarih haritası manuel kalır; özellikle dini bayramlar her yıl gözden geçirilmelidir.
# main.py'nin otomatik scheduler'ı ayrıca üçüncü taraf XIST takvimini kullanır;
# iki kaynak arasındaki fark bilinçli olarak data katmanına birleştirilmemiştir.
# Eksik statik kayıtlara karşı ana scheduler'ın XIST fail-closed kapısı ayrıdır.
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
    # 2027 — C1 (Batch 7): üç bağımsız kaynakla çapraz doğrulandı (2026-09-30):
    # Resmî tatil listeleri + Diyanet takvimi. Hafta sonuna denk gelenler (1 Mayıs
    # Cmt, 15-16 Mayıs) listeye alınmadı: BIST zaten kapalı.
    date(2027, 1, 1): "Yılbaşı",
    date(2027, 3, 9): "Ramazan Bayramı 1. gün",
    date(2027, 3, 10): "Ramazan Bayramı 2. gün",
    date(2027, 3, 11): "Ramazan Bayramı 3. gün",
    date(2027, 4, 23): "Ulusal Egemenlik ve Çocuk Bayramı",
    date(2027, 5, 17): "Kurban Bayramı 2. gün",
    date(2027, 5, 18): "Kurban Bayramı 3. gün",
    date(2027, 5, 19): "Kurban Bayramı 4. gün + Atatürk'ü Anma, Gençlik ve Spor Bayramı",
    date(2027, 7, 15): "Demokrasi ve Milli Birlik Günü",
    date(2027, 8, 30): "Zafer Bayramı",
    date(2027, 10, 29): "Cumhuriyet Bayramı",
}

# Yarım gün: (açıklama, seans kapanış saati)
BIST_YARIM_GUNLER = {
    date(2026, 3, 19): ("Ramazan Bayramı arefesi", time(13, 0)),
    date(2026, 5, 26): ("Kurban Bayramı arefesi", time(13, 0)),
    date(2026, 10, 28): ("Cumhuriyet Bayramı arefesi", time(13, 0)),
    # 2027 (C1): arefe günleri 13:00'te kapanır (15 Mayıs Cmt olduğu için yok)
    date(2027, 3, 8): ("Ramazan Bayramı arefesi", time(13, 0)),
    date(2027, 10, 28): ("Cumhuriyet Bayramı arefesi", time(13, 0)),
}

# --- VERİ TAZELİĞİ / TATIL MODU EŞİKLERİ ---
# "Veri yok modu": seans içindeyiz, tatil değiliz ama en yeni 1H mum bu kadardır
# eskiyse bugün için veri gelmiyor demektir (bilinmeyen tatil / Yahoo arızası).
# Ölçüm: normal seans içi en yeni mum yaşı < 60 dk; tatil/arıza > 20 saat.
VERI_YOK_MODU_ESIK_DK = 20 * 60

# --- TELEGRAM GLOBAL KAPANI (FAZ 2) ---
# Cooldown (hisse+desen+TF+state, 4 saat) tek tek spam'i engeller ama üst sınır
# yoktur: 48 aktif hisse x 4 TF x 5 desen x 5 state = 4800 anahtar x günde 6 kez
# teorik 28800 mesaj. Global Telegram kapları bu yüzden önemlidir.
# Günde/saatte üst sınır koyuyoruz: aşıldığında sadece en kritik state'ler geçer.
# --- VERİ SÜREKLİLİK / SPLIT KONTROLÜ (FAZ 2) ---
# auto_adjust=False ile HAM fiyat geliyor (Pine/TV ile aynı). Ama hisse split/bedelsiz
# yaparsa Yahoo ham seride ani zıplama üretir: pivot, sınır, ATR ve kırılım sinyali
# SAHTE olur. Ölçüm (28 hisse, 10052 ardışık bar çifti): |open[i+1]-close[i]|/close[i]
# dağılımı p50=%0.00, p99=%1.08, p99.9=%4.17, MAKS=%9.97 -> %10 eşiği normal gürültünün
# çok üstünde, split'i ise yakalar.
SPLIT_SUREKLILIK_ESIK_PCT = 10.0
# Seans içi bar boşluğu eşiği: mevcut zamanlama varsayımı bir saatlik etiket aralığıdır.
# Provider/seans label sözleşmesi canlı kaynakla bu turda doğrulanmamıştır.
BAR_BOSLUK_ESIK_SAAT = 1.5
# --- TARAMA DRİFT KORUMASI (FAZ 2) ---
# Canlı tarama aktif 48 hisseyi seri fetch eder; istek pacing'i SCAN_* ayarlarıyla
# sınırlandırılır. Mevcut yapılandırma bir saatlik tarama aralığı varsayar; eşik
# Yahoo yavaşlarsa veya retry gerekirse drift görünür olacak şekilde geniş tutulur. Tarama bu eşiği
# aşarsa (Yahoo yavaşlar, motor yavaşlar) bir sonraki mumu kaçırma riski doğar.
# Faz 1'deki "aynı mum iki kez taranmaz + kapanış bazlı tetik" yapısı sayesinde
# atlanan mum OLMAZ (sonraki döngüde taranır) ama gecikme büyür - ölçüp uyarıyoruz.
TARAMA_SURESI_UYARI_DK = 45

# --- 1D DERİNLİK (FAZ 2) ---
# 360 adet 1H bar, yalnızca yaklaşık 9 bar/seans varsayımıyla ~40 seansa denk gelir;
# provider bar üretimi canlı ölçülmeden kesin tarih derinliği olarak yorumlanmamalıdır.
# 1D üçgen/kama oluşumu 20-60 bar sürdüğü için bu tahmini pencere MARJINAL.
# DEQUE_MAXLEN'i artırmak (A) 1H penceresini de büyütür ve Pine ile birebir uyumu
# bozabilir (Pine'da kaç bar kullanıldığı henüz bilinmiyor) -> REDDEDİLDİ.
# Buna karşılık 1D verisini AYRI ve DERİN çekiyoruz (B): 1H/2h/4h Pine uyumu
# KORUNUR, sadece günlük pencere ~2 yıla çıkar. Maliyet: günde 30 ek fetch
# (sadece günlük bar eksikse çekilir, yoksa cache).
GUNLUK_FETCH_PERIOD = "2y"
GUNLUK_DEQUE_MAXLEN = 500

TELEGRAM_MAX_MESAJ_SAAT = 20
TELEGRAM_MAX_MESAJ_GUN = 120

# --- ALARM MESAJ STİLİ (telefon kartı) ---
# "kart": düz metin telefon kartı (emoji + BÜYÜK HARF hiyerarşisi, satır ≤ 283 px,
#         olay başına ≤ TELEGRAM_ALERT_MAX_KARAKTER). parse_mode KULLANILMAZ.
# "klasik": 25 Eyl canlı akışındaki uzun biçim (geri dönüş/a/B karşılaştırması için).
TELEGRAM_ALERT_STYLE = os.getenv("TELEGRAM_ALERT_STYLE", "kart").strip().lower()
# GÖRSEL-7 (2026-10-15) kart süzgeci: kârenin zaten çizdiği satırlar (kırılan/
# kapanış/kalite/daralma/temas/yapı/kutular) metinden DÜŞÜLÜR; metin yalnız
# kârede görünmeyeni söyler (eşik, bant yaşı, MTF, retest, katılım yorumu, karşı
# delil). Ölçüm: geçersiz kart 31 satır/636 kr → 9 satır/219 kr, teyitli kart
# 45/980 → 10/244. "0" yazılırsa 25 Eyl biçimi (tam kart) aynen geri gelir.
TELEGRAM_KART_SUZGEC = os.getenv("TELEGRAM_KART_SUZGEC", "1").strip().lower() not in {
    "0", "false", "kapali", "kapalı", "yok", "hayir", "hayır"}
# KART YORUM KATMANI (2026-10-29): S01–S32 araştırma kapılarından kartın "şu
# an bu hissede ne var?" hâli — koşulu açılan ◇ (en fazla 3) + · dikkat (en
# fazla 1); kapı yoksa kart birebir eski hâli. Yalnız canlı akış
# (`_attach_domain_context`) bu kartı açar; kapatmak: TELEGRAM_KART_YORUM=0.
TELEGRAM_KART_YORUM = os.getenv("TELEGRAM_KART_YORUM", "1").strip().lower() not in {
    "0", "false", "kapali", "kapalı", "yok", "hayir", "hayır"}
# Beklenti (tahmin) hükmü: `◇ beklenti: devam` + sayaç satırı. VARSAYILAN
# KAPALI (2026-10-22): katman ölçülmüş ilişkilerden türetiliyor ama canlı
# akışta bir hafta izlenmeden açılmayacak (tasarım: TAHMIN_UYGULAMA_PLANI.md
# §8/3). Açmak için `TELEGRAM_KART_TAHMIN=1`.
# Kural: yön kanıtı yoksa satır basılmaz; hüküm tek kelimedir (devam · tek
# kanıt · kararsız), sıfat yok.
TELEGRAM_KART_TAHMIN = os.getenv("TELEGRAM_KART_TAHMIN", "0").strip().lower() in {
    "1", "true", "acik", "açık", "on", "evet"}
# Telefon sohbetinde metne ayrılan genişlik (px, 360 px ekran). telegram_measure.py
# bu bütçeyle satır böler; 0 = bölme yok (satır uzunluğu serbest).
# not: _env_int 0'ı 1'e yuvarlar; sıfır "bölme yok" demek olabildiği için float okunur.
TELEGRAM_SATIR_PX = max(0, int(_env_float("TELEGRAM_SATIR_PX", 283)))
# Bir alarm kartının üst sınırı (karakter). 25 Eyl ölçümü: 1358-1559 kr/olay;
# kart hedefi 850-905 kr. Aşan mesaj gönderilir ama logda uyarıya yazılır.
TELEGRAM_ALERT_MAX_KARAKTER = max(0, int(_env_float("TELEGRAM_ALERT_MAX_KARAKTER", 1100)))
# DM içerik kapısı: aynı hisse+TF+state için bağlam imzası değişmediyse kopya
# mesaj gitmez; yalnız kapanış/marj değiştiyse tek satırlık güncelleme gider.
# (25 Eyl: TOASO 10:40 ve 15:10 mesajlarının 35 satırının 30'u birebir aynıydı.)
TELEGRAM_DM_DEGISIM_KAPISI = os.getenv(
    "TELEGRAM_DM_DEGISIM_KAPISI", "1").strip().lower() not in {"0", "false", "kapali", "kapalı"}
# Kanala "geçersizleşti" yalnızca ÖNCEKİ teyitli mesaj gerçekten kanala
# gönderildiyse gider (grup/kanalda "geçersiz geçersiz" gidip gelmesin).
TELEGRAM_KANAL_GECERSIZ_KAPISI = os.getenv(
    "TELEGRAM_KANAL_GECERSIZ_KAPISI", "1").strip().lower() not in {"0", "false", "kapali", "kapalı"}

# --- GRAFİK KARESİ (G4 / docs/tasarim/GRAFIK_TASARIM.md §5) — v1'de YALNIZ 4 anahtar ---
# `yok` (varsayılan) → hiçbir kare üretilmez, gönderim yolu bayt bayt bugünküle
# aynıdır ve matplotlib HİÇ import edilmez (§6.7). `alarm` → metin gittikten SONRA
# kareler eklenir (görsel metin kotasını YEMEZ, §4).
TELEGRAM_GRAFIK = os.getenv("TELEGRAM_GRAFIK", "yok").strip().lower()
# `/grafik` komutu kill-switch'ten BAĞIMSIZDIR (§4): anahtar kapalıyken de tek tek
# kare üretir — kapatılan şey alarmın ardına eklenen otomatik karelerdir.
if TELEGRAM_GRAFIK in {"1", "acik", "açık", "true", "on", "evet"}:
    TELEGRAM_GRAFIK = "alarm"          # yaygın yanlış yazım tolere edilir
# Alarm başına en fazla kare (1-4): birincil TF her zaman ilk karedir.
TELEGRAM_GRAFIK_ADET = min(4, max(1, int(_env_float("TELEGRAM_GRAFIK_ADET", 4))))
# Kadraj (FAZ 2): formasyon YOKKEN gösterilecek mum sayısı — TF matrisi
# `grafik.SABITLER["kadraj_cerceve"]` (1g 62 · 4s 68 · 2s 74 · 1s 80).
# Formasyon varsa kadraj formasyona odaklanır (formasyon + 10 mum sol tampon,
# 35-85 aralığı; bkz. `grafik._kadrajla`), sağında her zaman 15 mumluk boşluk kalır.
GRAFIK_MUM_MAKS = max(2, int(_env_float("GRAFIK_MUM_MAKS", 80)))
# Kareye çizilen onaylı+geçerli BOS/CHoCH sayısı.
GRAFIK_OLAY_MAKS = max(0, int(_env_float("GRAFIK_OLAY_MAKS", 6)))
# NOT: `grafik.py` bu dört anahtarı İMPORT ANINDA değil ÇAĞRI ANINDA env'den okur
# (§6.1 testleri ve canlıda anahtar değişimi için); buradaki sabitler yalnız
# `deploy_check` raporu ve `/durum` içindir — sapma olmasın diye aynı okuma.

# --- TELEGRAM WEBHOOK (Render) ---
# Varsayılan mod YOKLAMA'dır (getUpdates): yerel/systemd kurulumunda inbound HTTP
# gerekmez. Render gibi bir web serviste komutları webhook ile almak için:
#
#   RENDER_EXTERNAL_URL       Render otomatik verir: https://<servis>.onrender.com
#   TELEGRAM_WEBHOOK_SECRET   rastgele bir metin; adresin son parçasıdır ve
#                             Telegram'a secret_token olarak da bildirilir
#   TELEGRAM_WEBHOOK_URL      (opsiyonel) tam adres; boşsa RENDER_EXTERNAL_URL'den
#                             https://<servis>.onrender.com/webhook üretilir (sırsız;
#                             doğrulama secret_token başlığıyla yapılır)
#
# Secret boşsa webhook modu KAPALIDIR: bot eskisi gibi getUpdates yoklaması yapar
# ve /webhook ucu 404 döner (dışarıdan varlığı görülmez).
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL", "").strip()
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "").strip()

# --- PUBLIC KANAL ve ÖZET ---
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
SUMMARY_HOURS = "18:45"  # İstanbul saati, virgülle ayrılmış (V1: yalnız 18:45 kapanış özeti)
DEFERRED_ALERT_DIGEST_TIME = os.getenv("DEFERRED_ALERT_DIGEST_TIME", "18:45").strip()
# 18:45 erteleme özetinde gösterilecek EN FAZLA aday. Kalan adaylar kaybolmaz:
# başlıkta "12/21 gösteriliyor" ve altta "… 9 aday daha (tam liste: /formasyonlar)"
# satırı ile sayılır. Env ile büyütülebilir (Telegram 4096 karakter sınırı):
#   DEFERRED_ALERT_DIGEST_LIMIT=20
DEFERRED_ALERT_DIGEST_LIMIT = _env_int("DEFERRED_ALERT_DIGEST_LIMIT", 12)
POST_CLOSE_ANALYSIS_TIME = os.getenv("POST_CLOSE_ANALYSIS_TIME", "20:00").strip()  # gün sonu tam evren taraması
# V2: 20:00 taraması her işlem günü çalışır; mesaj yalnız 18:45 sonrası yeni teyit/iptal varsa gider (False=her zaman tam panel).
POST_CLOSE_ONLY_ON_DIFF = True

# --- HAFTALIK DOĞRULUK KARNESİ (yerel dosya; Supabase GEREKTİRMEZ) ---
# Cuma gün sonu mesajının (18:45 özeti; gönderilemezse 20:00 gün sonu analizi)
# ALTINA eklenir. Defter DATA_DIR/karne_defteri.json'da tutulur; /karne komutuyla
# istenildiği an alınabilir. Amaç: "bu hafta kaç formasyon bulundu, kırılımdan
# sonra kaçı pozitif/negatif gitti?" sorusunun ölçülmüş cevabı.
KARNE_GUNU = _env_int("KARNE_GUNU", 4)                 # 0=Pazartesi ... 4=Cuma (gönderim günü)
KARNE_HEDEF_ATR = _env_float("KARNE_HEDEF_ATR", 1.5)   # hedef: lehte bu kadar ATR (ilk dokunuş)
KARNE_STOP_ATR = _env_float("KARNE_STOP_ATR", 1.0)     # stop: alehte bu kadar ATR (ilk dokunuş)
KARNE_HORIZON_BAR = _env_int("KARNE_HORIZON_BAR", 10)  # sinyalden sonra kaç bar izlenecek
KARNE_SAKLAMA_GUN = _env_int("KARNE_SAKLAMA_GUN", 120)  # bu günden eski kayıtlar budanır
KARNE_FORMASYON_TTL_SAAT = _env_int("KARNE_FORMASYON_TTL_SAAT", 48)  # aynı hisse/TF/formasyon sayımı
# --- YAZMA AMPLİKASYONU (Batch 6 / B5) ---
# Heartbeat her hisse sonrası yazılıyordu: 48 hisse × tarama = 48 Supabase UPSERT.
# Yerel dosya canlılık göstergesi olduğu için her zaman yazılır; Supabase'e yazım
# bu aralıktan sık yapılmaz ve içerik değişmediyse atlanır.
HEARTBEAT_MIN_ARALIK_SN = _env_int("HEARTBEAT_MIN_ARALIK_SN", 60)      # yerel dosya
HEARTBEAT_UZAK_ARALIK_SN = _env_int("HEARTBEAT_UZAK_ARALIK_SN", 300)   # Supabase

# --- ENGELLENEN ACİL OLAYLAR (Batch 5 / B4) ---
# Cooldown veya saatlik/günlük kap nedeniyle gönderilemeyen ACİL alarmlar kuyruğa
# girer ve engel kalkınca gider. Kuyruk hem Supabase'e hem diske yazılır.
# Neden: teyitli kırılım gibi bir olay kap yüzünden tamamen kayboluyordu.
ACIL_KUYRUK_LIMIT = _env_int("ACIL_KUYRUK_LIMIT", 20)          # kuyrukta en fazla olay
ACIL_KUYRUK_TTL_DK = _env_int("ACIL_KUYRUK_TTL_DK", 180)       # bu süreden eski kayıt atılır
ACIL_KUYRUK_BOSALTMA_ARALIK_SN = _env_int("ACIL_KUYRUK_BOSALTMA_ARALIK_SN", 60)  # ana döngü denemesi
# Ek TABAN (0 = kapalı; kalite kapısı TF bazlı PUBLIC_MIN_QUALITY_TF ile işler).
# _env_int 0'ı 1'e yuvarladığı için float okunur.
PUBLIC_MIN_QUALITY = _env_float("PUBLIC_MIN_QUALITY", 0)
PUBLIC_STATES = [s.strip() for s in os.getenv(
    "PUBLIC_STATES", "KIRILIM_TEYITLI,RETEST_BASARILI,KIRILIM_GECERSIZLESTI").split(",") if s.strip()]
# Kanal için günlük SIKISMA özetinde min daralma
PUBLIC_SIKISMA_MIN_CONTRACTION = _env_float("PUBLIC_SIKISMA_MIN_CONTRACTION", 0.80)

# --- PUBLIC GRUP (Faz 1) ---------------------------------------------------
# Grup, DM'den BAĞIMSIZ hedeftir: TELEGRAM_GROUP_ID tanımlıysa DM kapalı olsa
# bile yayın sürer. Kanal kullanacaksan TELEGRAM_CHANNEL_ID de aynı role düşer
# (grup önceliklidir). Değer @kullanici_adi ya da -100... sayısal ID olabilir.
TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID", "").strip()


# --- PUBLIC GRUP KOMUTLARI (2026-10-28) -------------------------------------
# Eskiden kural kesindi: komutlar YALNIZ TELEGRAM_CHAT_ID (DM) sohbetinden
# kabul edilirdi; public grup yalnız yayın alırdı ("orası yalnız yayın alır").
# Artık grup/supergroup sohbetinde komut çalışabilir — ama YALNIZCA o sohbetin
# YÖNETİCİLERİ için ve yalnız okuma komutlarında. Üç kilit birlikte çalışır:
#   1. sohbet public komut listesinde olacak (PUBLIC_COMMAND_CHATS),
#   2. komut public beyaz listesinde olacak (bot/commands.py PUBLIC_KOMUT_ADLARI),
#   3. gönderen kişi getChatMember ile administrator/creator çıkacak.
# DM davranışı DEĞİŞMEZ: DM'de beyaz liste yoktur, her komut çalışır.
_PUBLIC_COMMANDS_HAM = os.getenv("PUBLIC_COMMANDS_ENABLED", "1").strip().lower()
PUBLIC_COMMANDS_ENABLED = _PUBLIC_COMMANDS_HAM not in {"0", "false", "no", "off", "hayir"}
# Public komut kabul edecek sohbetler. Boşsa TELEGRAM_GROUP_ID / TELEGRAM_CHANNEL_ID
# kullanılır (yani mevcut kurulumda ek env GEREKMEZ). Virgülle çok sohbet eklenebilir.
def _sohbet_listesi_coz(ham: str) -> list:
    """`-100…,@grup,t.me/grup` biçimini eşleştirme kimliklerine indirger.

    Tırnak, boşluk ve `t.me/...` bağlantısı yapıştırılabilir (kullanıcı hatası
    çok yaygın); bunlar temizlenmezse sohbet hiç eşleşmez. Eşleştirme için `@`
    atılır — API çağrılarında geri eklenir (telegram_sohbet_kimligi).
    """
    kimlikler = []
    for parca in str(ham or "").split(","):
        deger = parca.strip().strip('"').strip("'").strip()
        if not deger:
            continue
        dusuk = deger.lower()
        for onek in ("https://t.me/", "http://t.me/", "t.me/", "telegram.me/"):
            if dusuk.startswith(onek):
                deger = deger[len(onek):].split("?", 1)[0].strip("/")
                break
        deger = deger.lstrip("@").strip()
        if deger and deger not in kimlikler:
            kimlikler.append(deger)
    return kimlikler


PUBLIC_COMMAND_CHATS = _sohbet_listesi_coz(os.getenv("PUBLIC_COMMAND_CHATS", ""))
# Yönetici doğrulaması (getChatMember) sonucu bu kadar saniye önbelleklenir:
# her komutta API çağrısı yapılırsa Telegram hız limitine takılabilir.
PUBLIC_COMMAND_ADMIN_CACHE_SN = _env_int("PUBLIC_COMMAND_ADMIN_CACHE_SN", 300)
# Public'te varsayılan olarak KAPALI olan komutları tek tek açmak için
# (örn. "tara,evet"). Boş = yalnız varsayılan okuma listesi.
PUBLIC_COMMAND_EXTRA = [p.strip().lower() for p in os.getenv(
    "PUBLIC_COMMAND_EXTRA", "").split(",") if p.strip()]

# Public kalite eşiği TF bazlıdır ve DM alarm eşikleriyle AYNI (tek kaynak):
# 1h 80 · 2h 78 · 4h 75 · 1d 70. Env ile geçersiz kılmak için "1h:82,4h:78".
def _tf_esiklerini_coz(ham: str, varsayilan: dict) -> dict:
    esikler = dict(varsayilan)
    for parca in str(ham or "").split(","):
        if ":" not in parca:
            continue
        tf, _, deger = parca.partition(":")
        try:
            esikler[tf.strip().lower()] = float(deger.strip())
        except ValueError:
            continue
    return esikler


# NOT: PUBLIC_MIN_QUALITY_TF, ALERT_MIN_QUALITY tanımından SONRA kurulur
# (aşağıda, "ALARM / KANAL POLİTİKASI" bloğunun hemen ardında) — tek kaynak orası.

# Public bütçe + tempo: DM kapılarından AYRI (grup başına 20 mesaj/dk sınırı var).
#
# 2026-10-22 (akşam): public mesajı artık olay BAŞINA gidiyor (toplu bülten yok),
# bu yüzden varsayılanlar DM'in mesaj tavanıyla eşitlendi. Eski 6/saat · 25/gün
# değerleri "mesaj başına 12 olaya kadar" varsayımına dayanıyordu; yeni düzende
# aynı kalsaydı grup, DM'in gördüğü alarmların çoğunu **sessizce** kaçırırdı
# (kayıt kuyrukta bekler, gün dönünce bayatlar). 1 mesaj = 1 olay olduğu için
# eşit tavan, iki tarafın aynı alarmları görmesi demek.
PUBLIC_MAX_MESAJ_SAAT = _env_int("PUBLIC_MAX_MESAJ_SAAT", TELEGRAM_MAX_MESAJ_SAAT)
PUBLIC_MAX_MESAJ_GUN = _env_int("PUBLIC_MAX_MESAJ_GUN", TELEGRAM_MAX_MESAJ_GUN)
#: Public mesajlar arası en az aralık (sn). 1,2 → 2,0 (2026-10-22): bülten artık
#: DM ile aynı 7 bloğu basıyor ve ardından kare(ler) gidiyor; 1,2 sn Telegram'ın
#: grup hız sınırında 429 üretiyordu. Değer env ile geri alınabilir.
PUBLIC_MIN_ARALIK_SN = _env_float("PUBLIC_MIN_ARALIK_SN", 2.0)

# --- FAILURE PENALTY ---
FAILED_PATTERN_PENALTY_BARS = _env_int("FAILED_PATTERN_PENALTY_BARS", 24)

# --- PRE-LOAD ---
MORNING_PRELOAD_HOUR = _env_int("MORNING_PRELOAD_HOUR", 8)
MORNING_PRELOAD_MINUTE = _env_int("MORNING_PRELOAD_MINUTE", 30)

DEQUE_MAXLEN = 360

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

# Public (grup) kalite eşiği: DM alarm eşikleriyle AYNI kalsın diye buradan
# türetilir; env ile TF bazında geçersiz kılınabilir ("1h:82,4h:78").
PUBLIC_MIN_QUALITY_TF = _tf_esiklerini_coz(
    os.getenv("PUBLIC_MIN_QUALITY_TF", ""), ALERT_MIN_QUALITY)

# --- DEVAMLILIK PUANI (2026-10-25) ------------------------------------------
# Kullanıcıya aktarılan tek sıralama ölçüsü. Geometri (ALERT_MIN_QUALITY) artık
# yalnız bildirim eşiğini besler, kartta okunmaz. Ölçüm:
# docs/arastirma/PUANLAMA_MIMARISI_2026-10-25.md
#
# Hacim musluğu: 0 = KAPALI (davranış eskisiyle birebir aynı). >0 verilirse
# kanal/DM yalnız bu puanın üstündeki olayları geçirir. Ölçülen noktalar:
#   55 → bugünkü hacmin ~%76'sı, fazla +4,2 (bugün +1,5)
#   45 → hacim ~%100, fazla ~+4,0
DEVLAMLILIK_AKTIF = os.getenv("DEVLAMLILIK_AKTIF", "1").strip().lower() not in (
    "0", "false", "hayir", "hayır", "off", "no")


def _sayi_env(ad: str, varsayilan: float) -> float:
    try:
        return float(os.getenv(ad, str(varsayilan)))
    except (TypeError, ValueError):
        return varsayilan


PUBLIC_MIN_DEVLAMLILIK = _sayi_env("PUBLIC_MIN_DEVLAMLILIK", 0.0)
DM_MIN_DEVLAMLILIK = _sayi_env("DM_MIN_DEVLAMLILIK", 0.0)

# --- ALARM / KANAL POLİTİKASI (TEK KAYNAK) ----------------------------------
# KURAL: Aşağıdaki listeler BİRBİRİNDEN AYRIDIR (aynı state iki listede olamaz).
# Lifecycle state adları patterns/constants.py'de tanımlıdır.
# KIRILIM_GECERSIZLESTI yalnız bildirim katmanı alias'ıdır; motor state'i değildir
# ve main.py bunu sadece önceden teyit edilmiş kırılımın sonraki kapanışta
# formasyon içine döndüğü olay için üretir.
#
# 1) ANINDA iletilen (gecikmeden push) kritik olaylar:
ALERT_STATES = [
    # Yalnızca kapanışta doğrulanmış olaylar anlık gönderilir.
    "KIRILIM_TEYITLI",
    "RETEST_BASARILI",
    "KIRILIM_GECERSIZLESTI",
]

# 2) 18:45 kapanış özetine (digest) ertelenen düşük öncelikli yapılar.
# Kırılım hazırlığı ve retest bekleme/deneme state'leri, digest dahil hiçbir
# Telegram bildiriminde gösterilmez; teyitli olay veya sıkışma oluşana kadar
# sessiz kalınır. Politikayı değiştirmek için SADECE bu listeyi düzenle.
WATCH_STATES = frozenset({
    "SIKISMA_GUCLENIYOR",
})

# 3) PUBLIC KANAL akışı: yalnız bu state'ler ve eşikleri geçen kayıtlar kanala
# gider (DM'den bağımsız). Kanal politikasını değiştirmek için PUBLIC_* env'leri
# veya aşağıdaki varsayılanlar kullanılır (tek kaynak burasıdır; B9 kararı).
#   PUBLIC_STATES, PUBLIC_MIN_QUALITY, PUBLIC_SIKISMA_MIN_CONTRACTION (aşağıda)

# Politika tutarlılık kontrolü (import anında; sessiz çift bildirimi engeller).
_politika_hatalari = []
_ortak_state = set(ALERT_STATES) & set(WATCH_STATES)
if _ortak_state:
    _politika_hatalari.append(f"ALERT_STATES ve WATCH_STATES kesişiyor: {sorted(_ortak_state)}")

# Evren büyürse pacing/panel/digest limitleri yeniden ölçülmeli (rapor B8; 48 hisse + XU100/XU30/BRENT = 51).
EVREN_BUYUME_UYARI_ESIGI = 51

LOG_DIR = _resolve_app_path(os.getenv("LOG_DIR"), "/var/log/bist-bot")
LOG_FILE = "bot.log"
# Göreli log dizini de uygulama köküne sabitlenir (cwd farkı logu kaybederdi).
LOCAL_LOG_DIR = _resolve_app_path(os.getenv("LOCAL_LOG_DIR"), "logs")


def _varsayilan_data_dir() -> str:
    """Veri dizini: repo DIŞI varsayılan (C4).

    Neden: `bot_data/` git-tracked ve canlı sunucuda her taramada yeniden yazılıyor;
    `git pull`/deploy çakışıyordu. Artık:
      - `DATA_DIR` env verilirse o kullanılır,
      - Render/konteynerde repo geçici olduğu için `/tmp/formation-bot-data`
        (kalıcı veri zaten Supabase'de),
      - yerel/systemd kurulumda `/var/lib/formation-bot/data`, yazılamıyorsa
        `~/.formation-bot/data`, o da olmazsa son çare `./bot_data`.
    Repodaki `bot_data/*.json` örnek/seed verisi README'de anlatıldığı gibi yalnız
    OKUMA yedeği olarak kullanılabilir (SEED_DATA_DIR).
    """
    ortam = (os.getenv("DATA_DIR") or "").strip()
    if ortam:
        # Göreli yol verilirse süreç nereden başlatılırsa başlatılsın uygulama
        # köküne sabitlenir (systemd/CI/Render cwd farkı).
        return _resolve_app_path(ortam, ortam)
    if os.environ.get("RENDER"):
        return "/tmp/formation-bot-data"
    for aday in ("/var/lib/formation-bot/data",
                 os.path.expanduser("~/.formation-bot/data")):
        try:
            os.makedirs(aday, exist_ok=True)
            if os.access(aday, os.W_OK):
                return aday
        except OSError:
            continue
    return _resolve_app_path("", "bot_data")


DATA_DIR = _varsayilan_data_dir()
# Repodaki örnek veri: DATA_DIR'de dosya yoksa yalnız okuma için buraya bakılır.
SEED_DATA_DIR = _resolve_app_path(os.getenv("SEED_DATA_DIR"), "./bot_data")

_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
_LOG_LEVEL_ENV = (os.getenv("LOG_LEVEL", "INFO") or "INFO").strip().upper()
LOG_LEVEL = _LOG_LEVEL_ENV if _LOG_LEVEL_ENV in _LOG_LEVELS else "INFO"
ALLOW_TRUSTED_PICKLE_CACHE = (
    (os.getenv("ALLOW_TRUSTED_PICKLE_CACHE", "0") or "0").strip().lower()
    in {"1", "true", "yes", "on"}
)

# Consecutive closed bars before a return inside invalidates a breakout.
INVALIDATION_CONFIRM_BARS = max(1, _env_int("INVALIDATION_CONFIRM_BARS", 3))
INVALIDATION_CONFIRM_BARS_TF = "1h:3,2h:2,4h:2,1d:2"
# Minimum depth inside broken band (in ATR multiples) to advance invalidation counter (0 = off).
INVALIDATION_MIN_DEPTH_ATR = 0.3
# Only push instant KIRILIM_GECERSIZLESTI when prior KIRILIM_TEYITLI for the same formation_id was delivered.
INVALIDATION_REQUIRE_DELIVERED_CONFIRM = True
MTF_ALERT_MERGE_HOURS = max(0.0, _env_float("MTF_ALERT_MERGE_HOURS", 4.0))
# Family-level pattern matching across TFs in related() (False restores exact pattern_name match).
MTF_FAMILY_MATCH = True


def _parse_tf_int_map(raw) -> dict:
    if isinstance(raw, dict):
        out = {}
        for k, v in raw.items():
            try:
                out[str(k).strip().lower()] = max(1, int(v))
            except (TypeError, ValueError):
                continue
        return out
    text = str(raw or "").strip()
    if not text or text.lower() in {"0", "false", "no", "off", "kapali", "kapalı", "yok"}:
        return {}
    out = {}
    for part in text.split(","):
        if ":" not in part:
            continue
        tf, _, val = part.partition(":")
        try:
            out[tf.strip().lower()] = max(1, int(val.strip()))
        except ValueError:
            continue
    return out


def invalidation_confirm_bars_for_tf(tf=None) -> int:
    fallback = max(1, int(INVALIDATION_CONFIRM_BARS))
    if not tf:
        return fallback
    tf_map = _parse_tf_int_map(INVALIDATION_CONFIRM_BARS_TF)
    return tf_map.get(str(tf).strip().lower(), fallback)


def invalidation_min_depth_atr() -> float:
    try:
        return max(0.0, float(INVALIDATION_MIN_DEPTH_ATR))
    except (TypeError, ValueError):
        return 0.0


def invalidation_require_delivered_confirm() -> bool:
    return bool(INVALIDATION_REQUIRE_DELIVERED_CONFIRM)


def mtf_family_match_enabled() -> bool:
    return bool(MTF_FAMILY_MATCH)


def post_close_only_on_diff_enabled() -> bool:
    return bool(POST_CLOSE_ONLY_ON_DIFF)


