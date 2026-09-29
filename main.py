# --- MAIN LOOP ---
# BIST Bot Ana Döngü - İskelet
# Henüz tam değil, adım adım doldurulacak
# Türkçe yorumlar: Neden uyuyor, neden tarıyor?

import os
import sys
import time
import json
import signal
import logging
import random
import threading
from datetime import datetime, timedelta, time as dt_time
import pytz

try:
    from dotenv import load_dotenv
    load_dotenv()  # .env dosyasindan TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID okur
except ImportError:
    pass

from config import (ISTANBUL_TZ, ACTIVE_STOCKS, PROFILE, PROFILE_PARAMS, LOCAL_LOG_DIR, LOG_DIR,
                    ALERT_MIN_QUALITY, ALERT_MIN_QUALITY_GLOBAL, ALERT_STATES, BIST_OPEN,
                    SCAN_DELAY_AFTER_CLOSE_MIN, STALE_BAR_UYARI_DK, VERI_YOK_MODU_ESIK_DK,
                    TARAMA_SURESI_UYARI_DK, SCAN_REQUEST_BATCH_SIZE,
                    SCAN_REQUEST_DELAY_MIN_SEC, SCAN_REQUEST_DELAY_MAX_SEC,
                    FULL_1H_FETCH_PERIOD, ROUTINE_1H_FETCH_PERIOD,
                    SCAN_BATCH_PAUSE_MIN_SEC, SCAN_BATCH_PAUSE_MAX_SEC,
                    SCAN_RETRY_BACKOFF_MIN_SEC, SCAN_RETRY_BACKOFF_MAX_SEC)
from data import (StockDequeManager, tarama_penceresi_acik_mi, tarama_animi_mi,
                  son_kapanan_mum_ani, time_until_next_open,
                  resample_all_timeframes, fetch_yfinance_1h, fetch_yfinance_1d,
                  select_yfinance_1h_period, tamamlanmis_mumlar)
from scan_pacer import YahooRequestPacer
from patterns import PatternLifecycleManager, ST_BREAK_CANDIDATE, ST_BREAK_CONFIRMED, ST_RETEST_OK, ST_COMPLETED, ST_BREAK_FAILED, ST_COMPRESSING, ST_PREP
from notifier import TelegramNotifier
from supabase_store import SupabaseStore
from health_server import start_render_health_server
from live_state import LiveState
from telegram_commands import TelegramCommandListener

# === LOGGING KURULUMU ===
def setup_logging():
    """Log hem console hem dosyaya - Türkçe mesajlar"""
    # Local mi prod mu? LOG_DIR (/var/log/bist-bot) GERÇEKTEN yazılabilir mi?
    # Not: /var/log'un kendisine bakmak yetmez (root dışında yazılamaz) -
    # LOG_DIR'e yazma testi yapılmalı, yoksa sunucuda loglar ./logs'a düşer.
    log_dir = LOG_DIR
    try:
        os.makedirs(log_dir, exist_ok=True)
        test_path = os.path.join(log_dir, ".write_test")
        with open(test_path, "w") as f:
            f.write("test")
        os.remove(test_path)
    except Exception:
        log_dir = LOCAL_LOG_DIR
        os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, "bot.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging kuruldu - dosya: {log_file} - profil: {PROFILE}")
    return logger

logger = setup_logging()

# main_loop icinde olusturulan nesnelerin global referanslari (heartbeat icin)
_deque_manager_ref = None
_notifier_ref = None
_supabase_store_ref = None


def son_bar_yasi_dakika_str(dk: float) -> str:
    """Dakikayı insan okunur yapar: 95 -> '1sa 35dk'"""
    dk = int(round(dk))
    if dk < 60:
        return f"{dk} dk"
    return f"{dk // 60}sa {dk % 60}dk"


# === SİNYAL YÖNETİMİ (systemctl stop -> SIGTERM) ===
# Neden? systemd durdururken Python anında ölürse o taramada biriken deque'ler kaybolur.
_shutdown_requested = False
_deque_manager_ref = None
# Telegram komutları için paylaşılan durum (tarama thread'i yazar, listener okur)
_live_state = LiveState()
_scan_istegi = threading.Event()
_telegram_listener_ref = None

def signal_handler(signum, frame):
    global _shutdown_requested
    logger.info(f"Sinyal alındı: {signum} - güvenli kapanış hazırlanıyor...")
    _shutdown_requested = True

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# === GÜNLÜK ÖZET ===
daily_stats = {
    'stocks_scanned': 0,
    'patterns_found': 0,
    'alerts_sent': 0,
    'errors': 0,
    # Veri sağlığı (FAZ 1): fetch başarısızlıkları artık SAYILIYOR ve görünür.
    # Önceden fetch başarısız olunca cache dolu olduğu için hiç log satırı yoktu
    # -> Yahoo saatlerce kapalıysa bot "sağlıklı" görünürken kör çalışıyordu.
    'fetch_ok': 0,
    'fetch_failures': 0,
    'fetch_retries': 0,
    'fetch_retry_recovered': 0,
    'stale_stocks': 0,
    'max_bar_age_min': None,
    'data_stale': False,
    'veri_yok_modu': False,
    'split_atlanan': 0,
    'son_tarama_suresi_dk': None,
    'gunluk_bar_sayisi': None,
    'last_reset': datetime.now(ISTANBUL_TZ).date()
}

def reset_daily_if_needed():
    """Gün değiştiyse günlük sayacı sıfırla"""
    today = datetime.now(ISTANBUL_TZ).date()
    if today != daily_stats['last_reset']:
        logger.info(f"=== GÜNLÜK ÖZET {daily_stats['last_reset']} ===")
        logger.info(f"Taranan hisse: {daily_stats['stocks_scanned']}, Bulunan formasyon: {daily_stats['patterns_found']}, Gönderilen alert: {daily_stats['alerts_sent']}, Hata: {daily_stats['errors']}")
        # Sıfırla
        daily_stats['stocks_scanned'] = 0
        daily_stats['patterns_found'] = 0
        daily_stats['alerts_sent'] = 0
        daily_stats['errors'] = 0
        daily_stats['fetch_ok'] = 0
        daily_stats['fetch_failures'] = 0
        daily_stats['fetch_retries'] = 0
        daily_stats['fetch_retry_recovered'] = 0
        daily_stats['stale_stocks'] = 0
        daily_stats['max_bar_age_min'] = None
        daily_stats['data_stale'] = False
        daily_stats['veri_yok_modu'] = False
        daily_stats['split_atlanan'] = 0
        daily_stats['son_tarama_suresi_dk'] = None
        daily_stats['gunluk_bar_sayisi'] = None
        daily_stats['last_reset'] = today

def create_yahoo_pacer() -> YahooRequestPacer:
    """Her Yahoo isteğine uygulanan seri pacing ayarları."""
    return YahooRequestPacer(
        batch_size=SCAN_REQUEST_BATCH_SIZE,
        request_delay_min=SCAN_REQUEST_DELAY_MIN_SEC,
        request_delay_max=SCAN_REQUEST_DELAY_MAX_SEC,
        batch_pause_min=SCAN_BATCH_PAUSE_MIN_SEC,
        batch_pause_max=SCAN_BATCH_PAUSE_MAX_SEC,
        logger=logger,
    )


def fetch_1h_stocks_paced(stocks, pacer: YahooRequestPacer, phase: str, periods=None):
    """1H verilerini seri çeker; geçici hatalı sembolleri bir kez tekrar dener.

    Dönenler: başarılı DataFrame'ler, kalıcı/son hatalar, retry sayısı,
    retry ile kurtarılan sembol sayısı.
    """
    fetched = {}
    failures = {}
    retryable = {}
    periods = periods or {}

    for index, stock in enumerate(stocks, start=1):
        if _shutdown_requested:
            logger.info(f"{phase}: kapanış istendi; veri çekimi durduruluyor")
            break
        period = periods.get(stock, FULL_1H_FETCH_PERIOD)
        try:
            with pacer.request(f"{stock} 1H"):
                frame, can_retry, reason = fetch_yfinance_1h(
                    stock, period=period, with_status=True
                )
        except Exception as exc:
            frame, can_retry, reason = None, False, f"{type(exc).__name__}: {exc}"

        if frame is not None:
            fetched[stock] = frame
            logger.info(
                f"{phase} [{index}/{len(stocks)}] {stock}: {period} taze 1H veri alındı "
                f"({len(frame)} bar)"
            )
        else:
            failures[stock] = reason or "veri alınamadı"
            if can_retry:
                retryable[stock] = failures.pop(stock)
                logger.warning(f"{phase} {stock}: geçici fetch hatası; son turda bir kez denenecek ({retryable[stock]})")
            else:
                logger.warning(f"{phase} {stock}: yeniden denenmeyecek fetch hatası ({failures[stock]})")

    retry_count = 0
    recovered_count = 0
    if retryable and _shutdown_requested:
        failures.update(retryable)
    if retryable and not _shutdown_requested:
        backoff = random.uniform(SCAN_RETRY_BACKOFF_MIN_SEC, SCAN_RETRY_BACKOFF_MAX_SEC)
        logger.warning(
            f"{phase}: {len(retryable)} geçici veri hatası için tek tekrar denemesi; "
            f"{backoff:.1f} sn bekleniyor"
        )
        time.sleep(backoff)
        pacer.reset_batch()

        for stock, first_reason in retryable.items():
            if _shutdown_requested:
                failures[stock] = first_reason
                continue
            retry_count += 1
            try:
                with pacer.request(f"{stock} 1H retry"):
                    frame, _can_retry_again, reason = fetch_yfinance_1h(
                        stock,
                        period=periods.get(stock, FULL_1H_FETCH_PERIOD),
                        with_status=True,
                    )
            except Exception as exc:
                frame, reason = None, f"{type(exc).__name__}: {exc}"

            if frame is not None:
                fetched[stock] = frame
                recovered_count += 1
                logger.info(f"{phase} {stock}: tekrar denemesi başarılı ({len(frame)} bar)")
            else:
                failures[stock] = reason or first_reason or "tekrar denemesi başarısız"
                logger.warning(f"{phase} {stock}: tekrar denemesi de başarısız ({failures[stock]})")

    return fetched, failures, retry_count, recovered_count


# === HEARTBEAT ===
def write_heartbeat(data_dir: str = None, notifier=None):
    """Botun yaşadığını dışarıdan anlamak için heartbeat dosyası.
    Dışarıdan izleme: `jq .last_scan bot_data/heartbeat.json` 2 saatten eskiyse bot takılmış/kapanmıştır."""
    if data_dir is None:
        try:
            from config import DATA_DIR
            data_dir = DATA_DIR
        except ImportError:
            data_dir = "./bot_data"
    try:
        heartbeat_path = os.path.join(data_dir, "heartbeat.json")
        os.makedirs(data_dir, exist_ok=True)
        payload = {
            "last_scan": datetime.now(ISTANBUL_TZ).isoformat(),
            "profile": PROFILE,
            "stocks_scanned": daily_stats['stocks_scanned'],
            "patterns_found": daily_stats['patterns_found'],
            "alerts_sent": daily_stats['alerts_sent'],
            "errors": daily_stats['errors'],
            "active_stocks": len(ACTIVE_STOCKS),
            # --- veri sağlığı (FAZ 1) ---
            "fetch_ok": daily_stats['fetch_ok'],
            "fetch_failures": daily_stats['fetch_failures'],
            "fetch_retries": daily_stats['fetch_retries'],
            "fetch_retry_recovered": daily_stats['fetch_retry_recovered'],
            "stale_stocks": daily_stats['stale_stocks'],
            "max_bar_age_min": daily_stats['max_bar_age_min'],
            "data_stale": daily_stats['data_stale'],
            "veri_yok_modu": daily_stats['veri_yok_modu'],
            "split_atlanan": daily_stats['split_atlanan'],
            "son_tarama_suresi_dk": daily_stats['son_tarama_suresi_dk'],
            "gunluk_bar_sayisi": daily_stats['gunluk_bar_sayisi'],
            "telegram_kap": (notifier.kap_durumu() if notifier is not None
                             else (_notifier_ref.kap_durumu() if _notifier_ref else None)),
            "veri_sorunlari": ({k: [x['tip'] for x in v]
                               for k, v in _deque_manager_ref.sureklilik_sorunlari.items()}
                              if _deque_manager_ref else {}),
        }
        if _supabase_store_ref is not None:
            _supabase_store_ref.upsert("state:heartbeat", payload)
        with open(heartbeat_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Heartbeat yazılamadı: {e}")

# === TELEGRAM KOMUTLARI (iki yönlü) ===
# Bot alarm gönderir; bu bölüm Telegram'dan GELEN komutları yanıtlar. Komutlar
# yalnızca TELEGRAM_CHAT_ID'den kabul edilir (yetki kontrolü telegram_commands.py
# içinde). Yanıtlar getUpdates uzun yoklamasıyla ayrı bir thread'de toplanır.
KOMUT_YARDIM = """🤖 Formation-Bot komutları

/formasyonlar — günün canlı formasyonları
   filtre: /formasyonlar 1h   ·   /formasyonlar THYAO
/durum — bot, piyasa ve veri sağlığı özeti
/tara — şimdi tara (yalnızca seans içinde; mum kapanışını beklemez)
/yardim — bu liste

Notlar:
• Komutlar yalnızca kayıtlı sohbetten (TELEGRAM_CHAT_ID) kabul edilir.
• Bu bir AL/SAT aracı değildir: formasyon durumu ve kalite skoru bildirir.
• Alarmlar mum kapanışından 5 dk sonra kendiliğinden gelir; /tara bunu beklemez."""

STATE_TR = {
    "ADAY_OLUSUYOR": "Aday oluşuyor",
    "GEOMETRI_ADAYI": "Geometri adayı",
    "FORMASYON_TANIMLANDI": "Formasyon tanımlandı",
    "OLGUNLASIYOR": "Olgunlaşıyor",
    "SIKISMA_GUCLENIYOR": "Sıkışma güçleniyor",
    "KIRILIM_HAZIRLIGI": "Kırılım hazırlığı",
    "KIRILIM_DENEMESI": "Kırılım denemesi",
    "KIRILIM_ADAYI": "Kırılım adayı",
    "KIRILIM_TEYITLI": "Kırılım teyitli",
    "RETEST_BEKLENIYOR": "Retest bekleniyor",
    "RETEST_EDILIYOR": "Retest ediliyor",
    "RETEST_BASARILI": "Retest başarılı",
    "FORMASYON_TAMAMLANDI": "Formasyon tamamlandı",
}

def _gecen_sure(iso_zaman):
    """'12 dk önce' gibi kısa yaş metni."""
    if not iso_zaman:
        return "—"
    try:
        an = datetime.fromisoformat(iso_zaman)
    except (TypeError, ValueError):
        return "—"
    if an.tzinfo is None:
        an = ISTANBUL_TZ.localize(an)
    fark = (datetime.now(ISTANBUL_TZ) - an).total_seconds()
    if fark < 90:
        return f"{int(fark)} sn önce"
    if fark < 5400:
        return f"{int(fark // 60)} dk önce"
    return f"{fark / 3600:.1f} sa önce"

def _sayi(deger, basamak=2, varsayilan="—"):
    try:
        return f"{float(deger):.{basamak}f}"
    except (TypeError, ValueError):
        return varsayilan

def _komut_yardim(_arguman: str) -> str:
    return KOMUT_YARDIM

def _komut_durum(_arguman: str) -> str:
    now = datetime.now(ISTANBUL_TZ)
    st = _live_state.status()
    if tarama_penceresi_acik_mi(now):
        piyasa = "AÇIK (tarama penceresi içinde)"
    else:
        try:
            kalan = time_until_next_open(now)
            piyasa = f"KAPALI · açılışa {kalan / 3600:.1f} saat"
        except Exception:
            piyasa = "KAPALI"
    formations = _live_state.formations()
    en_iyi = formations[0] if formations else None
    yas = daily_stats.get('max_bar_age_min')
    satirlar = [
        "🤖 Formation-Bot durum",
        f"Profil: {PROFILE} · Evren: {len(ACTIVE_STOCKS)} hisse",
        f"Piyasa: {piyasa}",
    ]
    if st.get("tarama_suruyor"):
        satirlar.append("⏳ Şu an tarama sürüyor (liste son tamamlanan taramadan)")
    satirlar += [
        f"Son tarama: {_gecen_sure(st.get('son_tarama_bitis'))} "
        f"(süre {st.get('son_tarama_suresi_dk') or '—'} dk, {st.get('son_tarama_hissesi') or '—'} hisse)",
        f"Canlı formasyon: {len(formations)}" + (
            f" · en yüksek: {en_iyi['stock']} {en_iyi['timeframe']} "
            f"{en_iyi['pattern_name']} q{_sayi(en_iyi.get('quality'), 0)}" if en_iyi else ""),
        f"Bugün: {daily_stats['patterns_found']} formasyon kaydı, "
        f"{daily_stats['alerts_sent']} alarm, {daily_stats['errors']} hata",
        f"Veri: taze {daily_stats['fetch_ok']}/{len(ACTIVE_STOCKS)} hisse · "
        f"en eski mum {_sayi(yas, 0, '—')} dk · eski veri {daily_stats['stale_stocks']} hisse",
    ]
    if daily_stats.get('veri_yok_modu'):
        satirlar.append("⚠️ VERİ YOK MODU: bugün yeni piyasa verisi alınamadı (tatil/arıza)")
    if st.get("son_tarama_hatasi"):
        satirlar.append(f"⚠️ Son tarama hatası: {st['son_tarama_hatasi']}")
    satirlar.append("")
    satirlar.append("Komutlar: /formasyonlar · /tara · /durum · /yardim")
    return "\n".join(satirlar)

def _komut_formasyonlar(arguman: str) -> str:
    st = _live_state.status()
    formations = _live_state.formations()
    filtre = (arguman or "").strip().lower()

    if filtre:
        if filtre in ("1h", "2h", "4h", "1d"):
            formations = [f for f in formations if str(f.get("timeframe")) == filtre]
        else:
            formations = [f for f in formations
                          if filtre in str(f.get("stock", "")).lower()
                          or filtre in str(f.get("pattern_name", "")).lower()]
        if not formations:
            return (f"🔍 '{arguman.strip()}' filtresine uyan canlı formasyon yok.\n"
                    "Filtresiz liste için: /formasyonlar")

    baslik = [f"📊 CANLI FORMASYONLAR — {datetime.now(ISTANBUL_TZ).strftime('%d.%m.%Y %H:%M')}"]
    if st.get("son_tarama_bitis"):
        baslik.append(f"Son tarama: {_gecen_sure(st['son_tarama_bitis'])}"
                      + (" · tarama sürüyor" if st.get("tarama_suruyor") else ""))
    if not formations:
        if not st.get("son_tarama_bitis"):
            baslik.append("")
            baslik.append("Henüz tamamlanmış tarama yok; ilk tarama mum kapanışından 5 dk sonra yapılır.")
            baslik.append("/tara ile hemen tarama isteyebilirsin (seans içinde).")
        else:
            baslik.append("")
            baslik.append("Şu an canlı formasyon yok (calisan motor: üçgen/kama/bayrak/flama).")
            baslik.append("Bot her mum kapanışından sonra otomatik tarar; kırılım yaklaşınca yazar.")
        return "\n".join(baslik)

    gosterilecek = formations[:15]
    satirlar = list(baslik)
    satirlar.append("")
    for i, f in enumerate(gosterilecek, 1):
        q = float(f.get("quality") or 0.0)
        yon = "⬆️ yukarı" if f.get("break_dir") == 1 else ("⬇️ aşağı" if f.get("break_dir") == -1 else "↔️ belirsiz")
        durum = STATE_TR.get(str(f.get("state")), str(f.get("state") or "—"))
        esik = f.get("min_quality")
        esik_notu = "" if esik is None else ("" if q >= float(esik) else f" (alarm eşiği {_sayi(esik, 0)} altında)")
        satirlar.append(f"{i}) {f.get('stock')} · {f.get('timeframe')} · {f.get('pattern_name')}")
        satirlar.append(f"   kalite {_sayi(q, 0)}{esik_notu} · {durum} · {yon}")
        satirlar.append(f"   üst {_sayi(f.get('upper'))} / alt {_sayi(f.get('lower'))}"
                        f" · kritik {_sayi(f.get('critical_price'))}")
    if len(formations) > len(gosterilecek):
        satirlar.append("")
        satirlar.append(f"… ve {len(formations) - len(gosterilecek)} tane daha "
                        f"(filtre: /formasyonlar 1h veya /formasyonlar THYAO)")
    satirlar.append("")
    taranan = st.get("son_tarama_hissesi") or daily_stats['stocks_scanned']
    satirlar.append(f"Toplam {len(formations)} canlı formasyon · son tarama {taranan} hisse")
    return "\n".join(satirlar)

def _komut_tara(_arguman: str) -> str:
    now = datetime.now(ISTANBUL_TZ)
    if not tarama_penceresi_acik_mi(now):
        try:
            kalan = time_until_next_open(now)
            ek = f"\nSonraki açılışa: {kalan / 3600:.1f} saat"
        except Exception:
            ek = ""
        return ("🚫 Piyasa kapalı — elle tarama yapılmıyor.\n"
                "Kapanış saatlerinde taze veri gelmediği için tarama yanıltıcı sinyal üretir;\n"
                "bot mum kapanışından 5 dk sonra seans içinde kendiliğinden tarar." + ek)
    if _live_state.status().get("tarama_suruyor"):
        return "⏳ Tarama zaten sürüyor; bitince /formasyonlar ile sonucu görebilirsin."
    if _scan_istegi.is_set():
        return "🕓 Tarama isteği kuyrukta; birkaç saniye içinde başlıyor."
    _scan_istegi.set()
    logger.info("Telegram /tara: elle tarama istendi")
    return ("🔍 Tarama isteği alındı, birkaç saniye içinde başlıyor.\n"
            "Bitince /formasyonlar yazınca güncel liste gelir.")

TELEGRAM_KOMUTLARI = {
    "start": _komut_yardim,
    "yardim": _komut_yardim,
    "help": _komut_yardim,
    "durum": _komut_durum,
    "formasyonlar": _komut_formasyonlar,
    "formasyon": _komut_formasyonlar,
    "liste": _komut_formasyonlar,
    "tara": _komut_tara,
}

def _bekle_veya_tarama(seconds: float) -> bool:
    """Belirtilen süre bekler; /tara isteği gelirse erken döner (True).

    Neden: ana döngü 5 dakikaya kadar uyuyor. Elle tarama isteği geldiğinde
    uykuyu beklemek yerine hemen taramaya geçilir (komut 5 dk askıda kalmasın).
    """
    bitis = time.monotonic() + seconds
    while not _shutdown_requested:
        kalan = bitis - time.monotonic()
        if kalan <= 0:
            return False
        if _scan_istegi.wait(min(kalan, 1.0)):
            return True
    return False


def scan_all_stocks(deque_manager: StockDequeManager, lifecycle_manager: PatternLifecycleManager, notifier: TelegramNotifier, manuel: bool = False):
    """
    Aktif tarama evrenini tara; Yahoo verisi seri ve gruplu alınır, analiz ardından yapılır.
    - Deque'den veri al
    - Resample 2H/4H/1D
    - Pattern tespit (üçgen/kama/bayrak)
    - Lifecycle update (kırılım takibi)
    - Telegram (cooldown ile)
    """
    simdiki_zaman = datetime.now(ISTANBUL_TZ)
    tarama_baslangici = time.monotonic()
    tur_taranan = 0
    tur_formasyon = 0
    _live_state.begin_scan(simdiki_zaman, manuel=manuel)
    logger.info(f"=== TARAMA BAŞLIYOR{' (ELLE /tara)' if manuel else ''} - {len(ACTIVE_STOCKS)} hisse, profil: {PROFILE} "
                f"({simdiki_zaman.strftime('%H:%M')}) ===")
    logger.info(
        f"Yahoo pacing: her {SCAN_REQUEST_BATCH_SIZE} istekte "
        f"{SCAN_REQUEST_DELAY_MIN_SEC:.1f}-{SCAN_REQUEST_DELAY_MAX_SEC:.1f} sn aralık, "
        f"grup arası {SCAN_BATCH_PAUSE_MIN_SEC:.0f}-{SCAN_BATCH_PAUSE_MAX_SEC:.0f} sn"
    )

    # Sağlıklı cache'te son 5 günü, boş/5 günden eski cache'te tam 60 günü çek.
    # Böylece rutin saatlik taramada büyük geçmiş penceresi tekrar tekrar inmez.
    fetch_periods = {}
    for stock in ACTIVE_STOCKS:
        cached = deque_manager.to_dataframe(stock)
        fetch_periods[stock] = select_yfinance_1h_period(cached)
    full_count = sum(period == FULL_1H_FETCH_PERIOD for period in fetch_periods.values())
    routine_count = len(fetch_periods) - full_count
    logger.info(
        f"1H fetch penceresi: tam {FULL_1H_FETCH_PERIOD}={full_count}, "
        f"rutin cache güncellemesi={routine_count} ({ROUTINE_1H_FETCH_PERIOD})"
    )

    # Önce 1H fetch turu ve yalnız geçici hatalar için tek retry; analiz retry
    # tamamlandıktan sonra yapılır ki kurtarılan taze veri aynı turda kullanılsın.
    pacer = create_yahoo_pacer()
    taze_1h_verileri, fetch_hatalari, retry_sayisi, retry_kurtarilan = fetch_1h_stocks_paced(
        ACTIVE_STOCKS, pacer, "CANLI TARAMA", periods=fetch_periods
    )
    daily_stats['fetch_ok'] += len(taze_1h_verileri)
    daily_stats['fetch_failures'] += len(fetch_hatalari)
    daily_stats['fetch_retries'] += retry_sayisi
    daily_stats['fetch_retry_recovered'] += retry_kurtarilan

    for idx, stock in enumerate(ACTIVE_STOCKS):
        if _shutdown_requested:
            logger.info("Kapanış istendi, tarama durduruluyor")
            break
        try:
            reset_daily_if_needed()
            simdiki_zaman = datetime.now(ISTANBUL_TZ)
            
            logger.info(f"[{idx+1}/{len(ACTIVE_STOCKS)}] {stock} taranıyor...")
            
            # Deque'den mevcut pencere; fetch aşaması yukarıda, retry dahil tamamlandı.
            df_1h = deque_manager.to_dataframe(stock)
            taze = taze_1h_verileri.get(stock)
            if taze is not None:
                deque_manager.append_dataframe(stock, taze)
                df_1h = deque_manager.to_dataframe(stock)
            else:
                logger.warning(
                    f"{stock}: taze 1H veri yok ({fetch_hatalari.get(stock, 'fetch yapılmadı')}); "
                    "cache varsa yalnız veri tazeliği uygunsa kullanılacak"
                )
            
            if df_1h is None or len(df_1h) < 50:
                logger.warning(f"{stock}: veri yok (fetch basarisiz + cache bos) - bu tur atlandi")
                continue
            
            # --- VERİ TAZELİĞİ ÖLÇÜMÜ (FAZ 1) ---
            # En yeni 1H mumun yaşı. Yahoo saatlerce kapalıysa bu değer büyür ve
            # bot eski veriyle (yanlış sinyalle) çalışmaya devam eder. Ölçüp
            # loglayıp heartbeat'e yazıyoruz ki kör çalışma görünür olsun.
            son_bar_yasi_dk = (simdiki_zaman - df_1h.index[-1].tz_convert(ISTANBUL_TZ)
                               if df_1h.index[-1].tzinfo else
                               simdiki_zaman - ISTANBUL_TZ.localize(df_1h.index[-1])).total_seconds() / 60.0
            if daily_stats['max_bar_age_min'] is None or son_bar_yasi_dk > daily_stats['max_bar_age_min']:
                daily_stats['max_bar_age_min'] = round(son_bar_yasi_dk, 1)
            # Seansın ilk saatinde en yeni veri dünkü kapanıştır (ilk mum 10:30'da
            # kapanır) -> o pencereyi uyarı dışında tut.
            erken_seans = simdiki_zaman.time() < dt_time(10, 50)
            # --- SPLIT / VERİ SORUNU KONTROLÜ (FAZ 2) ---
            # Ham seride split/bedelsiz tespit edildiyse bu hisseyi ANALİZ ETME:
            # pivot/sınır/kırılım sahte olur. Log'da net yazar, kullanıcı müdahale
            # edene kadar hisse sessiz kalır (yanlış sinyal vermekten iyidir).
            st_sorunlar = deque_manager.sureklilik_sorunlari.get(stock)
            if st_sorunlar:
                tipler = sorted({x['tip'] for x in st_sorunlar})
                if 'split' in tipler:
                    daily_stats['split_atlanan'] += 1
                    logger.error(
                        f"{stock}: analiz atlanıyor - veri sorunu {tipler}. "
                        f"Detay yukarıdaki uyarılarda; veri düzeltilince otomatik döner."
                    )
                    continue
                # boşluk/şok: analize devam (tek olay, motor ATR ile absorbe eder)
                logger.info(f"{stock}: veri notu {tipler} - analiz devam ediyor")

            # --- VERİ YOK MODU (FAZ 2) ---
            # Fetch başarısız ve cache'deki son mum çok eskiyse bugün için piyasa
            # verisi yoktur (bilinmeyen tatil / Yahoo arızası). Bu hisseyi analiz
            # ETME: eski veriyle formasyon üretmek yanlış sinyaldir. Karar fetch
            # SONRASI verilir (cache her sabah dünkü olduğu için fetch öncesi
            # bakılsa normal sabah taraması yanlışta atılırdı).
            if taze is None and son_bar_yasi_dk is not None and son_bar_yasi_dk > VERI_YOK_MODU_ESIK_DK:
                daily_stats['veri_yok_modu'] = True
                logger.info(
                    f"{stock}: bugün için veri yok (son mum {son_bar_yasi_dakika_str(son_bar_yasi_dk)} önce, "
                    f"fetch başarısız) - analiz atlanıyor"
                )
                continue

            # Fetch başarısızken sınırın ötesindeki cache ile formasyon/Telegram
            # üretme. Cache'i yalnızca makul tazelikteyse analizde kullan.
            if taze is None and son_bar_yasi_dk > STALE_BAR_UYARI_DK:
                daily_stats['stale_stocks'] += 1
                daily_stats['data_stale'] = True
                logger.warning(
                    f"{stock}: taze fetch başarısız ve cache {son_bar_yasi_dakika_str(son_bar_yasi_dk)} "
                    f"yaşında (eşik {STALE_BAR_UYARI_DK} dk); eski cache ile analiz/alert atlanıyor"
                )
                continue

            if son_bar_yasi_dk > STALE_BAR_UYARI_DK and not erken_seans:
                daily_stats['stale_stocks'] += 1
                daily_stats['data_stale'] = True
                logger.warning(
                    f"{stock}: VERİ ESKİ - en yeni 1H mum {son_bar_yasi_dakika_str(son_bar_yasi_dk)} önce "
                    f"(eşik {STALE_BAR_UYARI_DK} dk). yfinance çekimi "
                    f"{'başarısız' if taze is None else 'veri gelmiyor'}, cache ile devam ediliyor - "
                    f"formasyonlar eski veriyle hesaplanıyor!"
                )
            
            # Tüm timeframe'leri üret
            all_tfs = resample_all_timeframes(df_1h)
            
            # --- 1D İÇİN DERİN VERİ (FAZ 2) ---
            # Resample 1D sadece 1H penceresi kadar (~40 bar) derinlikte olur ve 1D
            # formasyon penceresi (20-60 bar) marjinal kalıyordu (ölçüm: 40.0 bar).
            # 1H penceresini büyütmek Pine uyumunu bozabileceği için günlük veriyi
            # AYRI ve DERİN (~2 yıl) çekiyoruz. Veri yoksa resample'e geri dönülür
            # (davranış asla kötüleşmez, sadece iyileşir).
            if deque_manager.gunluk_veri_eksik_mi(stock, simdiki_zaman):
                with pacer.request(f"{stock} 1D"):
                    taze_gunluk = fetch_yfinance_1d(stock)
                deque_manager.gunluk_fetch_denemesi_kaydet(stock, simdiki_zaman)
                if taze_gunluk is not None and len(taze_gunluk) >= 30:
                    deque_manager.append_gunluk_dataframe(stock, taze_gunluk)
                    logger.info(f"{stock}: günlük veri tazelendi ({len(taze_gunluk)} bar)")
                else:
                    logger.warning(f"{stock}: günlük derin veri çekilemedi - resample kullanılacak")
            df_gunluk = deque_manager.to_gunluk_dataframe(stock)
            if df_gunluk is not None and len(df_gunluk) >= 30:
                all_tfs['1d'] = df_gunluk
            
            # Her TF için: yarım (devam eden) mumu çıkar, TAMAMLANMIŞ mumları besle
            for tf_name, df_tf in all_tfs.items():
                if df_tf is None or len(df_tf) < 30:
                    logger.debug(f"{stock} {tf_name} için yeterli veri yok")
                    continue
                df_tf = tamamlanmis_mumlar(df_tf, tf_name)
                if df_tf is None or len(df_tf) < 30:
                    logger.debug(f"{stock} {tf_name}: tamamlanmış mum kalmadı (seans içi erken tarama)")
                    continue
                
                # Motor adayı kendisi bulur ve kırılım anında dondurur (Pine v0.4.6 akışı).
                # tam_yeniden=True: pencere her taramada sıfırdan deterministik oynatılır.
                snap = lifecycle_manager.scan(stock + "_" + tf_name, df_tf, tam_yeniden=True)
                state, break_dir, lifecycle_log = snap.state, snap.break_dir, snap.log
                active = snap.active
                
                if active:
                    q = snap.effective_quality if snap.effective_quality is not None else active.raw_quality
                    daily_stats['patterns_found'] += 1
                    logger.info(f"🔍 {stock} {tf_name} - {active.pattern_type} kalite {q:.0f} state {state} - {snap.log}")
                    
                    # Alert eşiği kontrolü - timeframe'e göre (effective_quality üzerinden)
                    min_q = ALERT_MIN_QUALITY.get(tf_name, ALERT_MIN_QUALITY_GLOBAL)
                    # Telegram /formasyonlar komutu bu kayittan beslenir (esik altindakiler de gorunur).
                    tur_formasyon += 1
                    _live_state.record_formation({
                        'stock': stock,
                        'timeframe': tf_name,
                        'pattern_name': active.pattern_type,
                        'quality': float(q),
                        'state': state,
                        'break_dir': break_dir,
                        'upper': getattr(active, 'upper_now', None),
                        'lower': getattr(active, 'lower_now', None),
                        'critical_price': (active.upper_now if break_dir == 1 else active.lower_now),
                        'break_strength': getattr(active, 'break_strength', None),
                        'bar_time': str(df_tf.index[-1]),
                        'min_quality': float(min_q),
                        'alert_gonderildi': False,
                    })
                    if q < min_q:
                        logger.debug(f"{stock} {tf_name} kalite {q:.0f} < {min_q} (alert eşiği) - telegram atlanıyor")
                    # Sadece önemli state'lerde Telegram gönder (insanlaştırma V2)
                    elif state in ALERT_STATES or state in [ST_BREAK_CANDIDATE, ST_BREAK_CONFIRMED, ST_RETEST_OK, ST_COMPLETED, ST_COMPRESSING, ST_PREP]:
                        # Humanized mesaj için ek bilgiler
                        alert_data = {
                            'stock_name': stock,
                            'timeframe': tf_name,
                            'pattern_name': active.pattern_type,
                            'state': state,
                            'confidence_score': q,
                            'critical_price_level': active.upper_now if break_dir == 1 else active.lower_now,
                            'upper_now': active.upper_now,
                            'lower_now': active.lower_now,
                            'contraction': getattr(active, 'contraction', None),
                            'timestamp': df_tf.index[-1],
                            'break_dir': break_dir,
                            'break_strength': getattr(active, 'break_strength', q),
                            'break_price': active.upper_now if break_dir == 1 else active.lower_now,
                            'retest_seen': getattr(snap, 'retest_seen', False),
                        }
                        if notifier.send(alert_data):
                            daily_stats['alerts_sent'] += 1
                            _live_state.mark_alert_sent(stock, tf_name)
                            logger.info(f"📨 Telegram gönderildi: {stock} {tf_name} {state} kalite {q:.0f}")
                else:
                    # Canlı formasyon yok (terminal state'ler ve kalite kapısı dahil)
                    logger.debug(f"{stock} {tf_name} - Canlı formasyon yok: {snap.log}")
            
            daily_stats['stocks_scanned'] += 1
            tur_taranan += 1
            
            # Her hisse sonrası diske kaydet (crash durumunda kayıp azalsın) + heartbeat
            try:
                deque_manager.save_to_disk(stock)
            except Exception as e:
                logger.warning(f"{stock} save_to_disk hatası: {e}")
            write_heartbeat(notifier=notifier)
            
        except Exception as e:
            daily_stats['errors'] += 1
            logger.error(f"{stock} tarama hatası: {e} - devam ediliyor", exc_info=True)
            continue
    
    for _st in ACTIVE_STOCKS[:3]:
        _df_g = deque_manager.to_gunluk_dataframe(_st)
        if _df_g is not None:
            daily_stats['gunluk_bar_sayisi'] = len(_df_g)
            break

    sure_dk = (time.monotonic() - tarama_baslangici) / 60.0
    daily_stats['son_tarama_suresi_dk'] = round(sure_dk, 1)
    _live_state.finish_scan(
        datetime.now(ISTANBUL_TZ),
        son_tarama_suresi_dk=round(sure_dk, 1),
        son_tarama_hissesi=tur_taranan,
        son_tarama_formasyonu=tur_formasyon,
    )

    # --- TARAMA DRİFT KORUMASI (FAZ 2) ---
    if sure_dk > TARAMA_SURESI_UYARI_DK:
        logger.warning(
            f"TARAMA ÇOK UZUN SÜRDÜ: {sure_dk:.1f} dk (eşik {TARAMA_SURESI_UYARI_DK} dk, "
            f"mum kapanış aralığı 60 dk). Bir sonraki mum gecikmeli analiz edilecek - "
            f"Yahoo yavaşlığı veya rate-limit birikmesi olabilir."
        )

    logger.info(f"=== TARAMA BİTTİ - Günlük: {daily_stats} ===")
    if daily_stats['split_atlanan']:
        logger.error(
            f"SPLIT/VERİ SORUNU: {daily_stats['split_atlanan']} hisse analiz edilmedi "
            f"(ham seride fiyat sürekliliği ihlali). Detay: "
            f"{ {k: [x['tip'] for x in v] for k, v in deque_manager.sureklilik_sorunlari.items()} }"
        )
    if daily_stats['veri_yok_modu']:
        logger.warning(
            f"VERİ YOK MODU: bugün için yeni piyasa verisi alınamadı "
            f"(fetch hatası {daily_stats['fetch_failures']}/{len(ACTIVE_STOCKS)}, "
            f"en eski mum {daily_stats['max_bar_age_min']} dk). Analiz yapılmadı - "
            f"tatil veya veri kaynağı arızası olabilir."
        )
    elif daily_stats['fetch_failures'] > 0 or daily_stats['data_stale']:
        logger.warning(
            f"VERİ SAĞLIĞI: taze veri {daily_stats['fetch_ok']}/{len(ACTIVE_STOCKS)} hisse, "
            f"fetch hatası {daily_stats['fetch_failures']}, eski veri {daily_stats['stale_stocks']} hisse, "
            f"en eski mum {daily_stats['max_bar_age_min']} dk"
        )
    else:
        logger.info(
            f"VERİ SAĞLIĞI: taze veri {daily_stats['fetch_ok']}/{len(ACTIVE_STOCKS)} hisse, "
            f"en eski mum {daily_stats['max_bar_age_min']} dk"
        )
    write_heartbeat(notifier=notifier)

def main_loop():
    """
    Ana döngü:
    1. BIST açık mı kontrol et
    2. Açıksa -> mum kapanışından 5dk sonra tara
    3. Kapalıysa -> 5dk uyu, tekrar kontrol et
    Neden 24/7 çalışıp sadece seans saatlerinde CPU harcasın? Oracle Free'de kaynak kısıtlı
    """
    logger.info("=== BIST FORMASYON BOTU BAŞLATILIYOR ===")
    logger.info(f"Profil: {PROFILE}, Params: {PROFILE_PARAMS}")
    logger.info(f"Hisseler: {ACTIVE_STOCKS[:5]}... (toplam {len(ACTIVE_STOCKS)})")
    
    global _deque_manager_ref, _notifier_ref, _supabase_store_ref
    supabase_store = SupabaseStore.from_env()
    _supabase_store_ref = supabase_store
    if supabase_store is not None:
        # Ortam değişkenleri yanlışsa teşhis loga düşsün; hata halinde bot durmaz.
        supabase_store.ping()
    deque_manager = StockDequeManager(persistent_store=supabase_store)
    _deque_manager_ref = deque_manager

    # Başlangıçta tüm cache ve notifier durumlarını tek Supabase isteğiyle al.
    # Supabase boş/erişilemezse mevcut bot_data JSON/pickle fallback'i kullanılır.
    remote_rows = None
    if supabase_store is not None:
        remote_keys = [
            key
            for stock in ACTIVE_STOCKS
            for key in (f"cache:1h:{stock}", f"cache:1d:{stock}")
        ] + [
            "state:daily_fetch_attempts",
            "state:telegram_cooldowns",
            "state:telegram_caps",
        ]
        remote_rows = supabase_store.get_many(remote_keys)
        if remote_rows is not None:
            deque_manager.hydrate_from_supabase(ACTIVE_STOCKS, remote_rows)
    lifecycle_manager = PatternLifecycleManager(profile=PROFILE)
    notifier = TelegramNotifier(
        persistent_store=supabase_store,
        initial_store_data=remote_rows,
    )
    _notifier_ref = notifier
    # Telegram token/chat_id teşhisi: mesaj göndermeden getMe ile doğrular.
    notifier.check_connection()

    # İki yönlü Telegram: komutları (formasyonlar/durum/tara/yardim) dinleyen
    # daemon thread. getUpdates uzun yoklaması kullanır; token/chat_id yoksa
    # hiç başlatılmaz (bot eskisi gibi yalnızca alarm gönderir).
    global _telegram_listener_ref
    if notifier.enabled:
        liste = ", ".join("/" + k for k in TELEGRAM_KOMUTLARI)
        listener = TelegramCommandListener(
            token=notifier.token,
            allowed_chat_id=notifier.chat_id,
            handlers=TELEGRAM_KOMUTLARI,
            help_text=KOMUT_YARDIM,
        )
        if listener.start():
            _telegram_listener_ref = listener
            logger.info(f"Telegram komutları aktif: {liste} (yalnızca chat_id {notifier.chat_id})")
    else:
        logger.info("Telegram komut dinleyicisi başlatılmadı (token/chat_id yok)")
    
    # İlk kurulum/preload de aynı hız sınırını kullanır; boş 1H cache'ler seri çekilir.
    logger.info(
        f"İlk yükleme: {len(ACTIVE_STOCKS)} hisse evreni; eksik cache'ler "
        f"{SCAN_REQUEST_BATCH_SIZE}'li istek gruplarıyla yavaşça doldurulacak"
    )
    pacer = create_yahoo_pacer()
    cache_eksik_hisseler = []
    for stock in ACTIVE_STOCKS:
        mevcut = deque_manager.to_dataframe(stock)
        if mevcut is None or len(mevcut) < 50:
            cache_eksik_hisseler.append(stock)

    ilk_veriler, ilk_hatalar, ilk_retry, ilk_kurtarilan = fetch_1h_stocks_paced(
        cache_eksik_hisseler, pacer, "İLK YÜKLEME"
    )
    if ilk_retry:
        logger.info(
            f"İlk yükleme retry özeti: {ilk_retry} tekrar, {ilk_kurtarilan} başarılı, "
            f"{len(ilk_hatalar)} çözülemeyen"
        )
    for stock in cache_eksik_hisseler:
        taze = ilk_veriler.get(stock)
        if taze is not None:
            deque_manager.append_dataframe(stock, taze)
            deque_manager.save_to_disk(stock)
            logger.info(f"{stock}: {len(taze)} mum çekildi ve diske kaydedildi")
        else:
            logger.warning(
                f"{stock}: ilk veri çekilemedi ({ilk_hatalar.get(stock, 'veri yok')}); "
                "canlı taramada tekrar denenecek"
            )

    # 1D derin veri de eksikse aynı pacing kuyruğundan geçir.
    for stock in ACTIVE_STOCKS:
        if _shutdown_requested:
            break
        if deque_manager.gunluk_veri_eksik_mi(stock):
            with pacer.request(f"{stock} initial 1D"):
                taze_gunluk = fetch_yfinance_1d(stock)
            deque_manager.gunluk_fetch_denemesi_kaydet(stock)
            if taze_gunluk is not None and len(taze_gunluk) >= 30:
                deque_manager.append_gunluk_dataframe(stock, taze_gunluk)
                deque_manager.save_gunluk_to_disk(stock)
                logger.info(f"{stock}: {len(taze_gunluk)} GÜNLÜK mum çekildi ve diske kaydedildi")
            else:
                logger.warning(f"{stock}: ilk günlük veri çekilemedi - resample kullanılacak")
    
    # Aynı mum iki kez taranmasın (drift koruması). Restart'ta None -> bir sonraki
    # kapanışta tazelenir, son mum gerekiyorsa bir kez daha taranır (zararsız).
    son_taranan_kapanis = None
    
    while not _shutdown_requested:
        try:
            now = datetime.now(ISTANBUL_TZ)
            
            if tarama_penceresi_acik_mi(now):
                # Telegram /tara: mum kapanışını beklemeden tara (aynı mum tekrar
                # taranabilir; alarm cooldown'ı tekrar mesajı engeller).
                elle = _scan_istegi.is_set()
                if elle:
                    _scan_istegi.clear()
                if elle or tarama_animi_mi(now, son_taranan_kapanis):
                    # Tarama anı: en son kapanmış mum + 5 dk doldu.
                    kapanis = son_kapanan_mum_ani(now)
                    if elle:
                        logger.info(f"ELLE TARAMA (Telegram /tara) - {now.strftime('%H:%M:%S')}")
                    else:
                        logger.info(f"TARAMA - {now.strftime('%H:%M:%S')} "
                                    f"(mum {kapanis.strftime('%H:%M')}'de kapandı, "
                                    f"günün {kapanis.hour - 9}. taraması)")
                    scan_all_stocks(deque_manager, lifecycle_manager, notifier, manuel=elle)
                    son_taranan_kapanis = kapanis
                    # Tümünü diske kaydet (yarım kaldıysa sonraki turda devam)
                    deque_manager.save_all()
                    time.sleep(5)  # aynı saniyede tekrar girmesin
                    continue
                
                # Henüz tarama anı değil: ne kadar bekleyeceğiz?
                kapanis = son_kapanan_mum_ani(now)
                if kapanis is None or kapanis.date() != now.date():
                    # Bugün henüz mum kapanmadı (ilk kapanış 10:30) -> ilk tarama anını bekle
                    hedef = (now.replace(hour=BIST_OPEN.hour, minute=BIST_OPEN.minute,
                                         second=0, microsecond=0)
                             + timedelta(minutes=40 + SCAN_DELAY_AFTER_CLOSE_MIN))
                else:
                    hedef = kapanis + timedelta(minutes=SCAN_DELAY_AFTER_CLOSE_MIN)
                bekle = max((hedef - now).total_seconds(), 30)
                logger.info(f"Sonraki tarama {hedef.strftime('%H:%M')} -> {bekle/60:.1f} dk bekleniyor")
                # Max 5dk uyu; /tara isteği gelirse uyku erken biter.
                if _bekle_veya_tarama(min(bekle, 300)):
                    logger.info("Elle tarama isteği geldi, uyku kesildi")
                    continue
                
            else:
                # BIST kapalı
                wait_open = time_until_next_open(now)
                # 5dk'da bir kontrol et, ama açılışa kadar uyu
                sleep_time = min(wait_open, 300)  # Max 5dk
                logger.info(f"BIST KAPALI - {now.strftime('%Y-%m-%d %H:%M:%S')} - {sleep_time/60:.1f}dk uyku (açılışa {wait_open/3600:.1f}sa)")
                time.sleep(sleep_time)
                
        except KeyboardInterrupt:
            logger.info("Bot durduruldu (Ctrl+C)")
            break
        except Exception as e:
            daily_stats['errors'] += 1
            logger.error(f"Ana döngü hatası: {e} - 30sn sonra yeniden denenecek", exc_info=True)
            if _live_state.status().get('tarama_suruyor'):
                _live_state.fail_scan(f"ana döngü: {e}")
            write_heartbeat()
            time.sleep(30)
            continue
    
    # Güvenli kapanış (SIGTERM/SIGINT)
    logger.info("Bot kapanıyor, son kayıtlar yapılıyor...")
    try:
        if _telegram_listener_ref is not None:
            _telegram_listener_ref.stop()
    except Exception as e:
        logger.warning(f"Komut dinleyicisi kapatılamadı: {e}")
    try:
        if _deque_manager_ref is not None:
            _deque_manager_ref.save_all()
        write_heartbeat()
    except Exception as e:
        logger.error(f"Kapanış kayıt hatası: {e}")
    logger.info("Bot durdu")

def _render_test_sender(text):
    """/test ucu icin geri cagirma: notifier hazirsa tek mesaj gonderir.

    Notifier main_loop icinde kurulur; bu yuzden modul seviyesindeki global
    uzerinden okunur (server startup'ta None olabilir, cagri aninda doludur).
    """
    notifier = _notifier_ref
    if notifier is None:
        return False, "bot henuz baslamadi"
    return notifier.send_text(text)


if __name__ == "__main__":
    start_render_health_server(test_sender=_render_test_sender)
    main_loop()
