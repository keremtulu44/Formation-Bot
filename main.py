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
import socket
import threading
from datetime import datetime, timedelta, time as dt_time
from typing import List, Dict

try:
    from dotenv import load_dotenv
    load_dotenv()  # .env dosyasindan TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID okur
except ImportError:
    pass

from config import (ISTANBUL_TZ, ACTIVE_STOCKS, PROFILE, PROFILE_PARAMS, LOCAL_LOG_DIR, LOG_DIR,
                    ALERT_MIN_QUALITY, ALERT_MIN_QUALITY_GLOBAL, ALERT_STATES, BIST_OPEN,
                    SCAN_DELAY_AFTER_CLOSE_MIN, STALE_BAR_UYARI_DK, VERI_YOK_MODU_ESIK_DK,
                    OFFSESSION_CACHE_MAX_AGE_DAYS,
                    TARAMA_SURESI_UYARI_DK, SCAN_REQUEST_BATCH_SIZE,
                    SCAN_REQUEST_DELAY_MIN_SEC, SCAN_REQUEST_DELAY_MAX_SEC,
                    FULL_1H_FETCH_PERIOD, ROUTINE_1H_FETCH_PERIOD,
                    SCAN_BATCH_PAUSE_MIN_SEC, SCAN_BATCH_PAUSE_MAX_SEC,
                    SCAN_RETRY_BACKOFF_MIN_SEC, SCAN_RETRY_BACKOFF_MAX_SEC,
                    SUMMARY_HOURS, DEFERRED_ALERT_DIGEST_TIME, DEFERRED_ALERT_DIGEST_LIMIT,
                    POST_CLOSE_ANALYSIS_TIME, ACIL_KUYRUK_BOSALTMA_ARALIK_SN,
                    HEARTBEAT_MIN_ARALIK_SN, HEARTBEAT_UZAK_ARALIK_SN,
                    PUBLIC_MIN_QUALITY,
                    MORNING_PRELOAD_HOUR, MORNING_PRELOAD_MINUTE, EVREN_BUYUME_UYARI_ESIGI,
                    TELEGRAM_WEBHOOK_SECRET, TELEGRAM_WEBHOOK_URL, RENDER_EXTERNAL_URL)
from data import (StockDequeManager, tarama_penceresi_acik_mi, tarama_animi_mi,
                  son_kapanan_mum_ani, time_until_next_open, is_bist_open,
                  resample_all_timeframes, fetch_yfinance_1h, fetch_yfinance_1d,
                  fetch_last_bar,
                  select_yfinance_1h_period, tamamlanmis_mumlar)
from scan_pacer import YahooRequestPacer
from patterns import PatternLifecycleManager
from telegram_alert_flow import DeferredAlertBuffer, WATCH_STATES
from notifier import TelegramNotifier
from supabase_store import SupabaseStore
from health_server import start_render_health_server
from live_state import LiveState
from telegram_commands import TelegramCommandListener

# Batch 8 / C2: raporlama katmanı `reporting/format.py`'ye ayrıldı. Burada eski
# iç adlar (`_sayi`, `_panel_*`) alias olarak korunuyor: main döngüsü ve testler
# aynı isimlerle çalışmaya devam eder, davranış değişmez.
from reporting.panel import panel_raporu
from reporting.format import (
    STATE_TR, PANEL_TIMEFRAMES, PANEL_MESAJ_SINIRI,
    PANEL_DURUM_PUANI, PANEL_IPUCU, son_bar_yasi_dakika_str,
    sayi as _sayi, gecen_sure as _gecen_sure,
    filtrele_formasyonlar as _filtrele_formasyonlar, break_ok as _break_ok,
    veri_durumu_satiri as _veri_durumu_satiri,
    panel_kalite as _panel_kalite, panel_sembol as _panel_sembol,
    panel_hucre as _panel_hucre, panel_aday_puani as _panel_aday_puani,
    panel_kritik_anahtar as _panel_kritik_anahtar,
    panel_filtre_coz as _panel_filtre_coz,
    panel_durum_sayilari as _panel_durum_sayilari,
    panel_kritik_listesi as _panel_kritik_listesi,
    panel_sigdir as _panel_sigdir,
    format_deferred_alert_summary as _format_deferred_alert_summary,
)

# === LOGGING KURULUMU ===
# Batch 8 / C2: bu fonksiyon artık IMPORT anında ÇAĞRILMAZ (yan etki kaldırıldı:
# modül import edildiğinde log dizini oluşturulmuyor/`/var/log` denenmiyordu).
# `main_loop()` ve `python main.py` girişi kurulumu kendisi yapar.
_logging_kuruldu = False


def setup_logging():
    """Log hem console hem dosyaya - Türkçe mesajlar (tek seferlik)."""
    global _logging_kuruldu
    if _logging_kuruldu:
        return logging.getLogger(__name__)
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
    
    _logging_kuruldu = True
    logger = logging.getLogger(__name__)
    logger.info(f"Logging kuruldu - dosya: {log_file} - profil: {PROFILE}")
    return logger

# Import anında yalnız logger nesnesi alınır; handler'lar setup_logging() ile
# bağlanır (yukarıdaki nota bakın).
logger = logging.getLogger(__name__)

# main_loop icinde olusturulan nesnelerin global referanslari (heartbeat icin)
_deque_manager_ref = None
_notifier_ref = None
_supabase_store_ref = None
_deferred_alert_buffer = DeferredAlertBuffer()
# Bugüne ait 18:45 kapanış özetinin gönderilip gönderilmediği (ISO gün). Kalıcı
# tamponla birlikte Supabase/diske yazılır; restart sonrası aynı özet iki kez gitmez.
_digest_son_gonderim_gun = None
# Politika tek kaynak: `config.ALERT_STATES` (anlık) / `config.WATCH_STATES`
# (digest). Bu frozenset yalnız okuma kolaylığı içindir (B7 kararı config'te).
IMMEDIATE_ALERT_STATES = frozenset(ALERT_STATES)


def _evren_olcek_uyarisi(evren=None) -> str:
    """Evren eşiğin üzerindeyse pacing/panel/digest limitlerini hatırlatır.

    Davranışı DEĞİŞTİRMEZ: yalnız loga tek satır uyarı düşer (rapor B8: evren
    48'den büyürse önce pacing/digest/panel limitleri ölçülmeli).
    """
    hisseler = list(ACTIVE_STOCKS if evren is None else evren)
    if len(hisseler) <= EVREN_BUYUME_UYARI_ESIGI:
        return ""
    return (f"⚠️ Evren {len(hisseler)} hisse (eşik {EVREN_BUYUME_UYARI_ESIGI}): pacing "
            "(SCAN_*), panel mesaj bütçesi ve 18:45 digest limiti yeniden ölçülmeli "
            "(KODLAMA_PLANI → 'Evren büyütme').")


def _cache_verisi_kullanilabilir(yas_dk: float, taze_veri_var: bool, seans_acik: bool) -> bool:
    """Fetch başarısızsa seans dışı son mumları yaş sınırına kadar kullan."""
    if yas_dk > OFFSESSION_CACHE_MAX_AGE_DAYS * 24 * 60:
        return False
    if taze_veri_var:
        return True
    return not seans_acik or yas_dk <= STALE_BAR_UYARI_DK


# === SİNYAL YÖNETİMİ (systemctl stop -> SIGTERM) ===
# Neden? systemd durdururken Python anında ölürse o taramada biriken deque'ler kaybolur.
_shutdown_requested = False
_deque_manager_ref = None
# Telegram komutları için paylaşılan durum (tarama thread'i yazar, listener okur)
_live_state = LiveState()
_scan_istegi = threading.Event()
_scan_job_active = threading.Event()
_scan_request_lock = threading.Lock()
_scan_job_request = None
_scan_last_result = {}
_lifecycle_manager_ref = None
_telegram_listener_ref = None
# Webhook modunda: Telegram güncellemelerini işleyen nesne (yoklama thread'i YOK).
# health_server'ın /webhook ucu bu referans üzerinden çalışır; bot hazır değilse
# (açılıştaki ilk veri yüklemesi) uç 503 döner ve Telegram tekrar dener.
_telegram_update_processor_ref = None
# Aynı anda birden çok webhook isteği gelirse (Telegram sıralı gönderir ama ağ
# tekrarı olabilir) komut işleme serileştirilir: dinleyicinin hız sınırı/tekrar
# kümesi kilitli bir bölgede kullanılır.
_telegram_webhook_kilidi = threading.Lock()
# Render PORT'unda çalışan küçük HTTP sunucusu (webhook + /health + /test).
_health_server_ref = None

def signal_handler(signum, frame):
    global _shutdown_requested
    logger.info(f"Sinyal alındı: {signum} - güvenli kapanış hazırlanıyor...")
    _shutdown_requested = True

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# === GÜNLÜK ÖZET ===
last_run_stats = {}


def _analiz_hatasi_kaydi(exc, istek_hisse: int, kaynak: str = "analiz") -> dict:
    """scan_all_stocks dışında fırlayan hataları da tutarlı başarısız durum yap."""
    global last_run_stats
    bitis = datetime.now(ISTANBUL_TZ).isoformat()
    hata = f"{kaynak} hatası: {type(exc).__name__}: {exc}"
    _live_state.fail_scan(
        hata,
        datetime.now(ISTANBUL_TZ),
        hata_hisse=max(0, int(istek_hisse)),
        islenen_hisse=0,
        istek_hisse=max(0, int(istek_hisse)),
    )
    last_run_stats = {
        "status": "basarisiz",
        "requested": max(0, int(istek_hisse)),
        "processed": 0,
        "failed": max(0, int(istek_hisse)),
        "fresh_fetch": None,
        "fetch_failures": None,
        "data_asof": None,
        "oldest_bar_age_minutes": None,
        "finished_at": bitis,
    }
    return dict(last_run_stats)


# Aynı hisse/TF slotu gün içinde her taramada yeniden bulunur; "bugün kaç formasyon
# buldun?" sorusunun doğru cevabı BENZERSİZ slot sayısıdır. Eskiden sayaç her
# taramada yeniden artıyordu (9 tarama x 21 slot = 189) ve metrik şişiyordu.
# Set, daily_stats içinde tutulmaz (JSON'a serileşmez/heartbeat'e sığmaz).
_daily_pattern_keys: set = set()


def _note_pattern_found(stock: str, timeframe: str) -> None:
    """Günlük BENZERSİZ formasyon sayacını güncelle (aynı hisse|TF bir kez sayılır)."""
    _daily_pattern_keys.add(f"{str(stock).upper()}|{str(timeframe).lower()}")
    daily_stats['patterns_found'] = len(_daily_pattern_keys)


daily_stats = {
    'stocks_scanned': 0,
    'patterns_found': 0,
    'alerts_sent': 0,
    'errors': 0,
    # --- ADAY HUNİSİ (kullanıcı isteği) ---
    # "18 üretiliyor ama 3-5'inden bahsediliyor" sorusunun cevabı: her adayın
    # akıbeti sayılır ve /durum'da tek satırda gösterilir. Hiçbir kayıt sessizce
    # düşmez: ya gönderilir, ya ertelenir, ya da NEDENİ sayılır.
    'alerts_attempted': 0,        # acil gönderim denemesi
    'alerts_failed': 0,           # deneme başarısız (HTTP/ağ)
    'alerts_deferred': 0,         # WATCH state: 18:45 digest'ine ertelendi
    'alerts_below_threshold': 0,  # kalite eşiği altı (push üretmez)
    'alerts_state_disabled': 0,   # state hiçbir push akışında değil (yalnız panel)
    'alerts_digest_overflow': 0,  # digest limiti nedeniyle gösterilmeyen aday
    'alerts_kuyruk': 0,           # acil alarm engel yüzünden kuyruğa alındı (Batch 5 / B4)
    'alerts_engel_cooldown': 0,   # cooldown nedeniyle gönderilemedi (B4 kuyruğuna girer)
    'alerts_engel_kap': 0,        # saatlik/günlük kap nedeniyle gönderilemedi
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
        _daily_pattern_keys.clear()
        daily_stats['alerts_sent'] = 0
        daily_stats['alerts_attempted'] = 0
        daily_stats['alerts_failed'] = 0
        daily_stats['alerts_deferred'] = 0
        daily_stats['alerts_below_threshold'] = 0
        daily_stats['alerts_state_disabled'] = 0
        daily_stats['alerts_digest_overflow'] = 0
        daily_stats['alerts_kuyruk'] = 0
        daily_stats['alerts_engel_cooldown'] = 0
        daily_stats['alerts_engel_kap'] = 0
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


# === ÇOKLU ÖRNEK KORUMASI (Batch 6 / B10) ===
# Aynı token + aynı Supabase anahtarıyla iki kopya çalışırsa: çift mesaj + cache
# yarışı. Yoklama modunda Telegram 409 verir; webhook modunda hiçbir sinyal yoktu.
# Sert kilit kurulmaz (kısa ağ kesintisinde botu durdurmak daha kötü olurdu):
# durum loglanır, heartbeat ve /durum'a taşınır.
INSTANCE_ID = (os.environ.get("BOT_INSTANCE_ID") or "").strip() or f"{socket.gethostname()}:{os.getpid()}"
ORNEK_KONTROL_ARALIK_SN = 300
_cift_ornek_durumu = {
    "instance_id": INSTANCE_ID,
    "son_kontrol": None,
    "canli_digerleri": [],
    "uyari": False,
}


def _tekil_ornek_kontrolu(store=None, force: bool = False) -> dict:
    """Supabase'de başka canlı bot örneği var mı? (uyarı + heartbeat alanı)"""
    global _cift_ornek_durumu
    store = _supabase_store_ref if store is None else store
    if store is None:
        return _cift_ornek_durumu
    simdi = datetime.now(ISTANBUL_TZ)
    son = _cift_ornek_durumu.get("son_kontrol")
    if not force and son is not None and (simdi - son).total_seconds() < ORNEK_KONTROL_ARALIK_SN:
        return _cift_ornek_durumu
    try:
        sonuc = store.ornek_bildir(INSTANCE_ID, simdi.isoformat())
    except Exception as exc:
        logger.debug(f"Çoklu örnek kontrolü yapılamadı: {exc}")
        return _cift_ornek_durumu
    if not isinstance(sonuc, dict):
        return _cift_ornek_durumu
    digerleri = sonuc.get("canli_digerleri") or []
    _cift_ornek_durumu = {
        "instance_id": INSTANCE_ID,
        "son_kontrol": simdi,
        "canli_digerleri": digerleri,
        "uyari": bool(digerleri),
    }
    if digerleri:
        logger.error(
            "⚠️ AYNI ANDA ÇALIŞAN BAŞKA BOT ÖRNEĞİ GÖRÜNÜYOR: %s — çift mesaj ve cache "
            "yarışı riski. Fazladan kopyayı kapatın (Render'da tek instance olmalı).",
            ", ".join(str(d.get("id")) for d in digerleri),
        )
    return _cift_ornek_durumu


# === HEARTBEAT ===
# Yazma amplifikasyonu koruması (Batch 6 / B5): heartbeat her hisse sonrası
# çağrılıyordu (48 hisse × tarama = 48 Supabase UPSERT + 48 dosya yazımı).
# Yeni kural:
#   - yerel dosya: HEARTBEAT_MIN_ARALIK_SN'den sık yazılmaz (canlılık göstergesi
#     olduğu için tamamen atlanmaz; force=True ile hemen yazılır),
#   - Supabase: içerik değişmediyse veya HEARTBEAT_UZAK_ARALIK_SN dolmadıysa yazılmaz.
_son_heartbeat_zamani = 0.0
_son_heartbeat_icerik = None
_son_heartbeat_uzak_zamani = 0.0


def _heartbeat_icerik_ozeti(payload: dict) -> str:
    """`last_scan` dışındaki alanların özeti: değişiklik tespiti için."""
    return json.dumps({k: v for k, v in payload.items() if k != "last_scan"},
                      ensure_ascii=False, sort_keys=True, default=str)


def write_heartbeat(data_dir: str = None, notifier=None, force: bool = False):
    """Botun yaşadığını dışarıdan anlamak için heartbeat dosyası.
    Dışarıdan izleme: `jq .last_scan bot_data/heartbeat.json` 2 saatten eskiyse bot takılmış/kapanmıştır."""
    global _son_heartbeat_zamani, _son_heartbeat_icerik, _son_heartbeat_uzak_zamani
    if not force and time.time() - _son_heartbeat_zamani < HEARTBEAT_MIN_ARALIK_SN:
        return
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
            # --- GÖNDERİM SAĞLIĞI (A6) ---
            # "Bot çalışıyor ama hiçbir mesaj gitmiyor" durumu dışarıdan görünsün:
            # token/chat_id yokluğu, son başarılı gönderim, son hata ve engel sayaçları.
            "notifier_enabled": (notifier.enabled if notifier is not None
                                 else (getattr(_notifier_ref, "enabled", None) if _notifier_ref else None)),
            "telegram_gonderim": (notifier.gonderim_durumu() if notifier is not None
                                  else (getattr(_notifier_ref, "gonderim_durumu", lambda: None)()
                                        if _notifier_ref else None)),
            # Bekleyen gün içi aday (18:45 digest) ve engellenen acil kuyruğu:
            # restart/tıkanma durumunda "içeride ne var" dışarıdan görünsün.
            "bekleyen_bildirim": len(_deferred_alert_buffer),
            "digest_son_gonderim_gun": _digest_son_gonderim_gun,
            "acil_kuyruk": (notifier.gonderim_durumu().get("acil_kuyruk")
                            if notifier is not None
                            else (getattr(_notifier_ref, "kuyruk_durumu", lambda: None)()
                                  if _notifier_ref else None)),
            # B5 telemetrisi: kaç uzak yazım yapıldı / kaçı gereksizdi
            "uzak_yazma": (_deque_manager_ref.uzak_yazma_durumu()
                           if _deque_manager_ref else None),
            # --- ADAY HUNİSİ (B1) ---
            "alerts_attempted": daily_stats['alerts_attempted'],
            "alerts_failed": daily_stats['alerts_failed'],
            "aday_hunisi": {
                "push": daily_stats['alerts_sent'],
                "digest_ertelenen": daily_stats['alerts_deferred'],
                "state_kapsam_disi": daily_stats['alerts_state_disabled'],
                "esik_alti": daily_stats['alerts_below_threshold'],
                "digest_tasmasi": daily_stats['alerts_digest_overflow'],
                "engel_cooldown": daily_stats['alerts_engel_cooldown'],
                "engel_kap": daily_stats['alerts_engel_kap'],
                "kuyruga_alindi": daily_stats['alerts_kuyruk'],
            },
            "cift_ornek": {
                "uyari": _cift_ornek_durumu.get("uyari", False),
                "instance_id": INSTANCE_ID,
                "canli_digerleri": _cift_ornek_durumu.get("canli_digerleri", []),
                "son_kontrol": (_cift_ornek_durumu["son_kontrol"].isoformat()
                                if _cift_ornek_durumu.get("son_kontrol") else None),
            },
            "veri_sorunlari": ({k: [x['tip'] for x in v]
                               for k, v in _deque_manager_ref.sureklilik_sorunlari.items()}
                              if _deque_manager_ref else {}),
        }
        icerik = _heartbeat_icerik_ozeti(payload)
        simdi = time.time()
        if _supabase_store_ref is not None and (
                force
                or icerik != _son_heartbeat_icerik
                or simdi - _son_heartbeat_uzak_zamani >= HEARTBEAT_UZAK_ARALIK_SN):
            if _supabase_store_ref.upsert("state:heartbeat", payload):
                _son_heartbeat_uzak_zamani = simdi
        _son_heartbeat_icerik = icerik
        with open(heartbeat_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        _son_heartbeat_zamani = simdi
    except Exception as e:
        logger.warning(f"Heartbeat yazılamadı: {e}")


def _heartbeat_yolu() -> str:
    """write_heartbeat ile AYNI dizin çözümlemesini kullanır (tek davranış)."""
    try:
        from config import DATA_DIR
        data_dir = DATA_DIR
    except ImportError:  # pragma: no cover - config her zaman var; güvenlik ağı
        data_dir = "./bot_data"
    return os.path.join(data_dir, "heartbeat.json")


def _heartbeat_yasi_sn(simdi: datetime = None) -> float:
    """heartbeat.json'daki `last_scan` damgasının yaşı (saniye); okunamazsa None.

    Denetim B-4: /health artık botun canlı olup olmadığını bu değerle raporlar.
    Dosya yoksa/bozuksa uydurma değer üretilmez, None döner ('bilinmiyor').
    """
    try:
        with open(_heartbeat_yolu(), "r", encoding="utf-8") as f:
            ham = json.load(f).get("last_scan")
        if not ham:
            return None
        damga = datetime.fromisoformat(str(ham))
        if damga.tzinfo is None:
            damga = ISTANBUL_TZ.localize(damga)
        return max(0.0, ((simdi or datetime.now(ISTANBUL_TZ)) - damga).total_seconds())
    except Exception:
        return None


def _saglik_ozeti() -> dict:
    """GET /health için canlılık alanları (denetim B-4).

    `/health` DAİMA 200 döner; Render'ın health check davranışı değişmez. Bu özet
    "bot ayakta mı, tarama sürüyor mu, seans açık mı" sorusunu dışarıdan
    cevaplanabilir yapar; `?strict=1` ile çağıran monitör heartbeat bayatken 503 alır.

    Bayatlama eşiği:
      - tarama sürüyorsa  → TARAMA_SURESI_UYARI_DK (uzun tam evren taraması yanlış
        alarm üretmesin),
      - seans açıkken     → 30 dk (tarama aralığı ~5 dk + gecikme payı),
      - seans kapalıyken  → 72 sa (hafta sonu/tatil boşluğunda heartbeat üretilmez).
    """
    simdi = datetime.now(ISTANBUL_TZ)
    try:
        seans_acik = bool(is_bist_open(simdi))
    except Exception:
        seans_acik = None
    try:
        tarama_suruyor = bool(_live_state.status().get("tarama_suruyor"))
    except Exception:
        tarama_suruyor = None
    if tarama_suruyor:
        esik_sn = int(TARAMA_SURESI_UYARI_DK * 60)
    elif seans_acik:
        esik_sn = 1800
    else:
        esik_sn = 259200
    yas = _heartbeat_yasi_sn(simdi)
    return {
        "heartbeat_age_s": None if yas is None else int(yas),
        "heartbeat_stale": None if yas is None else bool(yas > esik_sn),
        "heartbeat_stale_esik_s": esik_sn,
        "tarama_suruyor": tarama_suruyor,
        "seans_acik": seans_acik,
        "evren": len(ACTIVE_STOCKS),
        "instance_id": INSTANCE_ID,
    }

# === TELEGRAM KOMUTLARI (iki yönlü) ===
# Bot alarm gönderir; bu bölüm Telegram'dan GELEN komutları yanıtlar. Komutlar
# yalnızca TELEGRAM_CHAT_ID'den kabul edilir (yetki kontrolü telegram_commands.py
# içinde). Yanıtlar getUpdates uzun yoklamasıyla ayrı bir thread'de toplanır.
KOMUT_YARDIM = """🤖 Formation-Bot komutları

/formasyonlar — günün canlı formasyonları (detaylı)
   filtre: /formasyonlar 1h   ·   /formasyonlar THYAO
/canli veya /c — canlı formasyonlar tek mesajda kompakt (kısayol)
/panel veya /p — 48 hisse x 4 zaman dilimi paneli + puanı en yüksek 12 aday
   diğer adlar: /genel · /tablo
   filtre: /panel 1h  ·  /panel THYAO  ·  /panel 1h THYAO  ·  /panel kirilim
/ozet veya /o — günlük özet tek mesajda (tamamlanan/retest/sıkışan)
/sikisanlar veya /s — sadece sıkışması güçlenenler
/tamamlanan veya /t — sadece tamamlananlar
/retest veya /r — retest bekleyen/başarılı
/kirilim veya /k — kırılım adayı/teyitli
/durum — bot, piyasa ve veri sağlığı özeti
/tara [HISSE] — şimdi analiz et (seans dışı da çalışır)
/yardim — bu liste

Notlar:
• Komutlar yalnızca kayıtlı sohbetten (TELEGRAM_CHAT_ID) kabul edilir.
• Bu bir AL/SAT aracı değildir: formasyon durumu ve kalite skoru bildirir.
• /panel tüm evreni yeniden hesaplar; /tara [HISSE] istenen kapsamı yeniden analiz eder.
• Analiz bitince sonucu otomatik gönderir; çalışma sırasında diğer komutlar sessizce yok sayılır.
• Public kanal için: /canli, /panel ve /ozet en verimli kısayollar.
• Komutlar webhook (Render) ya da yoklama ile gelir; ikisi aynı anda açık olmaz."""

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
    status = st.get("son_tarama_durumu", "yok")
    requested = st.get("son_tarama_beklenen_hisse")
    processed = st.get("son_tarama_hissesi")
    if status == "basarisiz":
        requested = last_run_stats.get("requested", st.get("son_is_hisse_istek"))
        processed = last_run_stats.get("processed", st.get("son_is_hisse_basarili"))
    else:
        if requested is None:
            requested = last_run_stats.get("requested")
        if processed is None:
            processed = last_run_stats.get("processed")
    fresh = st.get("son_tarama_taze_veri")
    fetch_failures = st.get("son_tarama_fetch_hatasi")
    if status == "basarisiz":
        # Son başarılı taramanın sayaçlarını başarısız son denemeye mal etme.
        fresh = last_run_stats.get("fresh_fetch")
        fetch_failures = last_run_stats.get("fetch_failures")
    elif status == "yok":
        fresh = None
        fetch_failures = None
    else:
        if fresh is None:
            fresh = last_run_stats.get("fresh_fetch")
        if fetch_failures is None:
            fetch_failures = last_run_stats.get("fetch_failures")

    satirlar = [
        "🤖 Formation-Bot durum",
        f"Profil: {PROFILE} · Evren: {len(ACTIVE_STOCKS)} hisse",
        f"Piyasa: {piyasa}",
    ]
    if _scan_job_active.is_set() or st.get("tarama_suruyor"):
        satirlar.append("⏳ Analiz sürüyor; diğer komutlar iş bitene kadar yok sayılır.")
    elif status == "basarisiz":
        satirlar.append("⚠️ Son analiz başarısız; boş sonuç olarak yayımlanmadı.")
    elif status == "yok":
        satirlar.append("ℹ️ Bu oturumda henüz başarılı analiz yok; /panel ile başlat.")

    kapsam = (f"{processed if processed is not None else '—'}/"
              f"{requested if requested is not None else len(ACTIVE_STOCKS)} hisse")
    sure = (st.get("son_is_suresi_dk") if status == "basarisiz"
            else st.get("son_tarama_suresi_dk"))
    sure_metni = "—" if sure is None else _sayi(sure, 1)
    satirlar += [
        f"Son başarılı analiz: {_gecen_sure(st.get('son_tarama_bitis'))} "
        f"(durum: {status}, kapsam: {kapsam}, süre: {sure_metni} dk)",
        f"Sonuçtaki formasyon: {len(formations)}" + (
            f" · en yüksek: {en_iyi['stock']} {en_iyi['timeframe']} "
            f"{en_iyi['pattern_name']} q{_sayi(en_iyi.get('quality'), 0)}" if en_iyi else ""),
        _veri_durumu_satiri(
            (last_run_stats.get('data_asof') if status == "basarisiz" else
             st.get('son_tarama_veri_zamani') or last_run_stats.get('data_asof')),
            fresh, requested, fetch_failures,
            (last_run_stats.get("oldest_bar_age_minutes") if status == "basarisiz"
             else st.get("son_tarama_en_eski_veri_yasi_dk")),
        ),
        f"Günlük toplam: {daily_stats['patterns_found']} formasyon kaydı, "
        f"{daily_stats['alerts_sent']} alarm, {daily_stats['errors']} hata",
    ]
    # --- ADAY HUNİSİ: "kaç aday üretildi, kaçı nereye gitti?" ---
    # Kullanıcı sorusu: "18 çıktı alıyoruz ama 3-5'inden bahsediyoruz". Bu satır
    # her adayın akıbetini tek bakışta gösterir; düşen aday sessiz kalmaz.
    huni = (f"🔎 Aday hunisi: {daily_stats['patterns_found']} üretildi · "
            f"{daily_stats['alerts_sent']} push · {daily_stats['alerts_deferred']} digest · "
            f"{daily_stats['alerts_state_disabled']} state dışı · "
            f"{daily_stats['alerts_below_threshold']} eşik altı")
    if daily_stats.get('alerts_digest_overflow'):
        huni += f" · {daily_stats['alerts_digest_overflow']} digest taşması"
    if daily_stats.get('alerts_kuyruk'):
        huni += f" · {daily_stats['alerts_kuyruk']} kuyruğa alındı"
    satirlar.append(huni)
    gosterim = None
    gonderim = getattr(_notifier_ref, "gonderim_durumu", None)
    if callable(gonderim):
        try:
            gd = gonderim()
            engel = gd.get("engeller") or {}
            gosterim = (f"🚧 Gönderim engeli: {engel.get('cooldown', 0)} cooldown · "
                        f"{engel.get('gunluk_kap', 0)} günlük kap · "
                        f"{engel.get('saatlik_kap', 0)} saatlik kap · "
                        f"{gd.get('hatalar', 0)} hata")
        except Exception as exc:  # noqa: BLE001 - komut asla çökmesin
            logger.debug(f"Gönderim durumu okunamadı: {exc}")
    if gosterim:
        satirlar.append(gosterim)
    # Notifier pasifse (token/chat_id yok) komut bunu açıkça söyler: aksi halde
    # kullanıcı "hiç mesaj gelmiyor ama bot çalışıyor" durumunu ayırt edemez.
    if _cift_ornek_durumu.get("uyari"):
        kimlikler = ", ".join(str(d.get("id")) for d in _cift_ornek_durumu.get("canli_digerleri") or [])
        satirlar.append(f"🚨 Çoklu örnek uyarısı: başka canlı kopya görünüyor ({kimlikler})")
    if getattr(_notifier_ref, "enabled", None) is False:
        satirlar.append("⚠️ Telegram PASİF: token/chat_id tanımlı değil, hiçbir bildirim gönderilmiyor.")
    if st.get("son_tarama_hatasi"):
        satirlar.append(f"⚠️ Son hata: {st['son_tarama_hatasi']}")
    kapsam_notu = _kismi_kapsam_notu()
    if kapsam_notu:
        satirlar.append(kapsam_notu)
    satirlar += ["", "Komutlar: /panel · /tara [HISSE] · /formasyonlar · /durum · /yardim"]
    return "\n".join(satirlar)


def _sonuc_yok_mesaji(basarili_bos_mesaji: str, tamamlandi: bool = False) -> str:
    """İstenen filtrede sonuç yokken tarama kalitesini de doğru belirt."""
    st = _live_state.status()
    if not tamamlandi and (_scan_job_active.is_set() or st.get("tarama_suruyor")):
        return "⏳ Analiz sürüyor; tamamlanınca güncel sonuç gönderilecek."
    status = st.get("son_tarama_durumu", "yok")
    if status == "basarisiz":
        return ("⚠️ Son analiz başarısız veya eksik; bunu 'sonuç yok' olarak "
                "yorumlama. /durum ile kapsamı kontrol et.")
    if status == "tamamlandi":
        return basarili_bos_mesaji
    return "ℹ️ Henüz başarılı analiz yok. Güncel hesaplama için /panel yaz."


def _bos_analiz_mesaji(tamamlandi: bool = False) -> str:
    st = _live_state.status()
    beklenen = st.get("son_tarama_beklenen_hisse")
    if (st.get("son_tarama_durumu") == "tamamlandi" and beklenen is not None
            and 0 < int(beklenen) < len(ACTIVE_STOCKS)):
        mesaj = f"ℹ️ Son başarılı analiz {beklenen} hisselik kısmi kapsamdaydı; bu kapsamda canlı formasyon bulunmadı."
    else:
        mesaj = "ℹ️ Son başarılı analiz tamamlandı; canlı formasyon bulunmadı."
    return _sonuc_yok_mesaji(mesaj, tamamlandi=tamamlandi)


def _onceki_sonuc_uyarisi() -> str:
    """Son deneme başarısızsa yayınlanan listeyi önceki başarılı çalışmaya bağla."""
    if _live_state.status().get("son_tarama_durumu") == "basarisiz":
        return "⚠️ Son analiz başarısız; aşağıdaki kayıtlar önceki başarılı analizdendir."
    return ""


def _kismi_kapsam_notu() -> str:
    """Hisse-özel taramadan sonra korunmuş eski evren kayıtlarını açıkça belirt."""
    st = _live_state.status()
    istek = st.get("son_tarama_beklenen_hisse")
    if (st.get("son_tarama_durumu") == "tamamlandi" and istek is not None
            and 0 < int(istek) < len(ACTIVE_STOCKS)):
        islenen = st.get("son_tarama_hissesi") or istek
        return (f"ℹ️ Son başarılı analiz {islenen}/{istek} hisselik kısmi kapsamdı; "
                "diğer hisselerin kayıtları önceki başarılı analizden korunuyor.")
    return ""

def _komut_formasyonlar(arguman: str, tamamlandi: bool = False) -> str:
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
            durum_mesaji = _sonuc_yok_mesaji(
                f"🔍 '{arguman.strip()}' filtresine uyan canlı formasyon yok.",
                tamamlandi=tamamlandi,
            )
            return durum_mesaji + "\nFiltresiz liste için: /formasyonlar"

    baslik = [f"📊 CANLI FORMASYONLAR — {datetime.now(ISTANBUL_TZ).strftime('%d.%m.%Y %H:%M')}"]
    if st.get("son_tarama_bitis"):
        baslik.append(f"Son başarılı tarama: {_gecen_sure(st['son_tarama_bitis'])}")
    if st.get("son_tarama_durumu") == "basarisiz":
        baslik.append("⚠️ Son deneme başarısız; gösterilen kayıt varsa önceki başarılı taramadandır.")
    if not formations:
        baslik.append("")
        baslik.append(_bos_analiz_mesaji(tamamlandi=tamamlandi))
        if st.get("son_tarama_durumu") == "tamamlandi":
            beklenen = st.get("son_tarama_beklenen_hisse")
            if beklenen is not None and 0 < int(beklenen) < len(ACTIVE_STOCKS):
                baslik.append(
                    f"Yalnızca {beklenen} hisselik kısmi kapsam analiz edildi; "
                    "tam evrende formasyon olmadığı sonucu çıkarılamaz."
                )
            else:
                baslik.append("48 hisse ve 4 zaman diliminde uygun canlı formasyon bulunmadı.")
        else:
            baslik.append("Yeni tam tarama için /panel · tek hisse için /tara THYAO")
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
    taranan = st.get("son_tarama_hissesi")
    beklenen = st.get("son_tarama_beklenen_hisse")
    taranan_metni = "—" if taranan is None else str(taranan)
    if beklenen is not None:
        taranan_metni += f"/{beklenen}"
    satirlar.append(f"Toplam {len(formations)} canlı formasyon · son başarılı tarama {taranan_metni} hisse")
    kapsam_notu = _kismi_kapsam_notu()
    if kapsam_notu:
        satirlar.append(kapsam_notu)
    return "\n".join(satirlar)

def _komut_canli(arguman: str) -> str:
    """Kısayol: canlı hisselerde olan formasyonları tek mesajda kompakt at."""
    formations = _live_state.formations()
    formations = _filtrele_formasyonlar(formations, arguman)
    if not formations:
        filt = f" ('{arguman}' filtresi)" if arguman else ""
        return (f"🔍 {_sonuc_yok_mesaji('Son başarılı analizde canlı formasyon yok.')}{filt}\n"
                "/formasyonlar ile detaylı listeye bak.")
    sirali = sorted(formations, key=lambda x: float(x.get("quality") or 0), reverse=True)[:20]
    saat = datetime.now(ISTANBUL_TZ).strftime("%H:%M")
    filt_notu = f" [{arguman}]" if arguman else ""
    satirlar = [f"⚡ CANLI ({len(formations)}){filt_notu} - {saat} - tek mesaj"]
    onceki_uyari = _onceki_sonuc_uyarisi()
    if onceki_uyari:
        satirlar.append(onceki_uyari)
    kapsam_notu = _kismi_kapsam_notu()
    if kapsam_notu:
        satirlar.append(kapsam_notu)
    for f in sirali:
        q = f.get("quality") or 0
        ok = _break_ok(f.get("break_dir"))
        durum = f.get("state") or "—"
        # kısa durum: ilk kelimeyi koru, TR map varsa kısa kullan
        satirlar.append(
            f"{f.get('stock')} {f.get('timeframe')} {f.get('pattern_name')} q{float(q):.0f} {ok} {durum}"
        )
    if len(formations) > 20:
        satirlar.append(f"... ve {len(formations)-20} daha (/formasyonlar ile hepsi)")
    satirlar.append("")
    satirlar.append("💡 /ozet günlük özet, /s sıkışanlar, /r retest, /k kırılım")
    return "\n".join(satirlar)


def _komut_ozet(arguman: str) -> str:
    """Kısayol: günlük özet tek mesajda. Filtre destekler."""
    try:
        formations = _live_state.formations()
        formations = _filtrele_formasyonlar(formations, arguman)
        if not formations:
            st = _live_state.status()
            if not arguman.strip():
                bos = _bos_analiz_mesaji()
            else:
                bos = _sonuc_yok_mesaji(
                    f"Son başarılı analizde '{arguman.strip()}' filtresine uyan aktif formasyon bulunmadı."
                )
            if st.get("son_tarama_veri_zamani"):
                bos += f"\nSon mum: {st['son_tarama_veri_zamani']}"
            return f"📊 BIST Formasyon Özeti — {datetime.now(ISTANBUL_TZ).strftime('%d.%m %H:%M')}\n{bos}"
        notifier = _notifier_ref
        if notifier and hasattr(notifier, "format_daily_summary"):
            aktif = []
            for f in formations:
                aktif.append({
                    "stock_name": f.get("stock"),
                    "timeframe": f.get("timeframe"),
                    "pattern_name": f.get("pattern_name"),
                    "state": f.get("state"),
                    "confidence_score": f.get("quality"),
                    "contraction": f.get("contraction"),
                    "break_dir": f.get("break_dir", 0),
                })
            ozet = notifier.format_daily_summary(aktif, daily_stats)
            uyarilar = [x for x in (_onceki_sonuc_uyarisi(), _kismi_kapsam_notu()) if x]
            return "\n".join(uyarilar + [ozet]) if uyarilar else ozet
        if not formations:
            return "📊 Özet: " + _bos_analiz_mesaji()
        tamam = len([f for f in formations if f.get("state") == "FORMASYON_TAMAMLANDI"])
        retest = len([f for f in formations if str(f.get("state", "")).startswith("RETEST")])
        sikis = len([f for f in formations if f.get("state") == "SIKISMA_GUCLENIYOR"])
        kirilim = len([f for f in formations if str(f.get("state", "")).startswith("KIRILIM")])
        filt = f" [{arguman}]" if arguman else ""
        uyarilar = [x for x in (_onceki_sonuc_uyarisi(), _kismi_kapsam_notu()) if x]
        return (
            ("\n".join(uyarilar) + "\n" if uyarilar else "")
            + f"📊 Özet {datetime.now(ISTANBUL_TZ).strftime('%H:%M')}{filt}\n"
            + f"Canlı: {len(formations)} | Tamamlanan: {tamam} | Retest: {retest} | Sıkışan: {sikis} | Kırılım: {kirilim}\n"
            + "/canli ile tek mesajda hepsi"
        )
    except Exception as e:
        return f"Özet alınamadı: {e}"


def _komut_sikisanlar(arguman: str) -> str:
    formations = [f for f in _live_state.formations() if f.get("state") == "SIKISMA_GUCLENIYOR"]
    formations = _filtrele_formasyonlar(formations, arguman)
    if not formations:
        filt = f" ('{arguman}')" if arguman else ""
        return _sonuc_yok_mesaji(f"⚡ Son başarılı analizde yüksek sıkışma yok{filt}.")
    sirali = sorted(formations, key=lambda x: float(x.get("quality") or 0), reverse=True)[:15]
    satirlar = [f"⚡ SIKIŞANLAR ({len(formations)})" + (f" [{arguman}]" if arguman else "")]
    onceki_uyari = _onceki_sonuc_uyarisi()
    if onceki_uyari:
        satirlar.append(onceki_uyari)
    kapsam_notu = _kismi_kapsam_notu()
    if kapsam_notu:
        satirlar.append(kapsam_notu)
    for f in sirali:
        satirlar.append(
            f"{f.get('stock')} {f.get('timeframe')} {f.get('pattern_name')} q{float(f.get('quality') or 0):.0f} {_break_ok(f.get('break_dir'))}"
        )
    if len(formations) > 15:
        satirlar.append(f"... ve {len(formations)-15} daha")
    return "\n".join(satirlar)


def _komut_tamamlanan(arguman: str) -> str:
    formations = [f for f in _live_state.formations() if f.get("state") == "FORMASYON_TAMAMLANDI"]
    formations = _filtrele_formasyonlar(formations, arguman)
    if not formations:
        filt = f" ('{arguman}')" if arguman else ""
        return _sonuc_yok_mesaji(f"🏁 Son başarılı analizde tamamlanan yok{filt}.")
    sirali = sorted(formations, key=lambda x: float(x.get("quality") or 0), reverse=True)[:15]
    satirlar = [f"🏁 TAMAMLANAN ({len(formations)})" + (f" [{arguman}]" if arguman else "")]
    onceki_uyari = _onceki_sonuc_uyarisi()
    if onceki_uyari:
        satirlar.append(onceki_uyari)
    kapsam_notu = _kismi_kapsam_notu()
    if kapsam_notu:
        satirlar.append(kapsam_notu)
    for f in sirali:
        satirlar.append(
            f"{f.get('stock')} {f.get('timeframe')} {f.get('pattern_name')} q{float(f.get('quality') or 0):.0f} {_break_ok(f.get('break_dir'))}"
        )
    if len(formations) > 15:
        satirlar.append(f"... ve {len(formations)-15} daha")
    return "\n".join(satirlar)


def _komut_retest(arguman: str) -> str:
    formations = [
        f for f in _live_state.formations()
        if str(f.get("state", "")).startswith("RETEST")
    ]
    formations = _filtrele_formasyonlar(formations, arguman)
    if not formations:
        filt = f" ('{arguman}')" if arguman else ""
        return _sonuc_yok_mesaji(f"🎯 Son başarılı analizde retest bekleyen/başarılı yok{filt}.")
    sirali = sorted(formations, key=lambda x: float(x.get("quality") or 0), reverse=True)[:15]
    satirlar = [f"🎯 RETEST ({len(formations)})" + (f" [{arguman}]" if arguman else "")]
    onceki_uyari = _onceki_sonuc_uyarisi()
    if onceki_uyari:
        satirlar.append(onceki_uyari)
    kapsam_notu = _kismi_kapsam_notu()
    if kapsam_notu:
        satirlar.append(kapsam_notu)
    for f in sirali:
        satirlar.append(
            f"{f.get('stock')} {f.get('timeframe')} {f.get('pattern_name')} {f.get('state')} q{float(f.get('quality') or 0):.0f} {_break_ok(f.get('break_dir'))}"
        )
    if len(formations) > 15:
        satirlar.append(f"... ve {len(formations)-15} daha")
    return "\n".join(satirlar)


def _komut_kirilim(arguman: str) -> str:
    formations = [
        f for f in _live_state.formations()
        if str(f.get("state", "")).startswith("KIRILIM")
    ]
    formations = _filtrele_formasyonlar(formations, arguman)
    if not formations:
        filt = f" ('{arguman}')" if arguman else ""
        return _sonuc_yok_mesaji(f"🚀 Son başarılı analizde kırılım adayı/teyitli yok{filt}.")
    sirali = sorted(formations, key=lambda x: float(x.get("quality") or 0), reverse=True)[:15]
    satirlar = [f"🚀 KIRILIM ({len(formations)})" + (f" [{arguman}]" if arguman else "")]
    onceki_uyari = _onceki_sonuc_uyarisi()
    if onceki_uyari:
        satirlar.append(onceki_uyari)
    kapsam_notu = _kismi_kapsam_notu()
    if kapsam_notu:
        satirlar.append(kapsam_notu)
    for f in sirali:
        satirlar.append(
            f"{f.get('stock')} {f.get('timeframe')} {f.get('pattern_name')} {f.get('state')} q{float(f.get('quality') or 0):.0f} {_break_ok(f.get('break_dir'))}"
        )
    if len(formations) > 15:
        satirlar.append(f"... ve {len(formations)-15} daha")
    return "\n".join(satirlar)

# === /panel — 48 hisse x 4 zaman dilimi slot tablosu ===
# Neden ayrı komut: /canli ve /formasyonlar yalnızca DOLU slotları listeler; hangi
# hissede hiç formasyon yok, hangi TF boş, toplam kaç slot dolu -> görünmez.
# /panel evrenin tamamını (ACTIVE_STOCKS x 4 TF) tek bakışta gösterir: doluluk
# sayıları + kompozit puana göre en anlamlı 12 aday.
WATCH_CONTEXT_HAVUZU = 12    # acil mesaja eklenecek adayların seçildiği havuz (gönderilen: en fazla 3)
def _panel_raporu(arguman: str = "", tamamlandi: bool = False) -> str:
    """Panel metni (Batch 8 / 8.3): bağlam burada toplanır, üretim reporting'te.

    Global durumu okuyan tek yer burasıdır; metin üretimi saf fonksiyona taşındı.
    """
    return panel_raporu(
        arguman,
        durum=_live_state.status(),
        formations=_live_state.formations(),
        aktif_hisseler=list(ACTIVE_STOCKS),
        tarama_suruyor=_scan_job_active.is_set(),
        last_run_stats=last_run_stats,
        tamamlandi=tamamlandi,
        kapsam_notu=_kismi_kapsam_notu(),
        bos_analiz_mesaji=_bos_analiz_mesaji(tamamlandi=tamamlandi),
    )

def _manuel_tarama_istegi(tip: str, arguman: str = "") -> str:
    """Analizi ana döngüye kuyruğa koy; Telegram işleyicisini bloklama."""
    global _scan_job_request
    with _scan_request_lock:
        if _scan_job_active.is_set():
            # Normalde listener busy guard bunu kullanıcıya ulaşmadan yutar.
            return ""
        hisseler = list(ACTIVE_STOCKS)
        if tip == "tara" and arguman.strip():
            tokenlar = [t.strip().upper() for t in arguman.replace(",", " ").split()]
            hisse_tokenlari = [t for t in tokenlar if t not in PANEL_TIMEFRAMES]
            if hisse_tokenlari:
                secilen = [s for s in ACTIVE_STOCKS
                           if any(t == s or (len(t) >= 3 and t in s) for t in hisse_tokenlari)]
                if not secilen:
                    return (f"🔍 '{arguman.strip()}' için hisse bulunamadı. "
                            "Örnek: /tara THYAO")
                hisseler = list(dict.fromkeys(secilen))
        _scan_job_request = {
            "tip": tip,
            "arguman": arguman.strip(),
            "hisseler": hisseler,
            "istek_zamani": datetime.now(ISTANBUL_TZ).isoformat(),
        }
        _scan_job_active.set()
        _scan_istegi.set()
    logger.info("Telegram /%s analizi kuyruğa alındı (hisse=%s)",
                tip, ",".join(hisseler))
    kapsam = f"{len(hisseler)} hisse × 4 zaman dilimi"
    return f"🔍 Analiz başladı: {kapsam}. Bittiğinde sonucu bu sohbete göndereceğim."


def _komut_panel(arguman: str) -> str:
    """Yeni bir tam evren analizi başlatır; filtreler yalnızca sonuç görünümüne uygulanır."""
    return _manuel_tarama_istegi("panel", arguman)


def _komut_tara(arguman: str) -> str:
    """İstenen hisseyi (yoksa evreni) seans saatinden bağımsız analiz eder."""
    return _manuel_tarama_istegi("tara", arguman)


def _manuel_tarama_tamamla(request: dict, result: dict, notifier) -> None:
    """Manuel iş tamamlanınca başlatan isteğe tek final mesajı gönder."""
    global _scan_job_request
    try:
        if result.get("status") != "tamamlandi":
            mesaj = (
                "⚠️ Analiz tamamlanamadı; boş sonuç olarak kaydetmedim.\n"
                f"Başarıyla hesaplanan: {result.get('processed', 0)}/"
                f"{result.get('requested', 0)} hisse · hata/atlanan: "
                f"{result.get('failed', 0)}.\n"
                f"{_veri_durumu_satiri(result.get('data_asof'), result.get('fresh_fetch'), result.get('requested'), result.get('fetch_failures'), result.get('oldest_bar_age_minutes'))}\n"
                "Ayrıntı için bot logundaki ilk 'tarama hatası' kaydına bakın."
            )
        elif request.get("tip") == "panel":
            mesaj = _panel_raporu(request.get("arguman", ""), tamamlandi=True)
        else:
            filt = request.get("arguman", "")
            mesaj = _komut_formasyonlar(filt, tamamlandi=True)
            mesaj = (f"✅ Tarama tamamlandı: {result.get('processed', 0)}/"
                     f"{result.get('requested', 0)} hisse.\n"
                     f"{_veri_durumu_satiri(result.get('data_asof'), result.get('fresh_fetch'), result.get('requested'), result.get('fetch_failures'), result.get('oldest_bar_age_minutes'))}\n"
                     + mesaj)
        if notifier is not None:
            notifier.send_text(mesaj)
    except Exception as exc:
        logger.error("Manuel analiz sonucu Telegram'a gönderilemedi: %s", exc, exc_info=True)
    finally:
        with _scan_request_lock:
            _scan_job_request = None
            _scan_job_active.clear()


TELEGRAM_KOMUTLARI = {
    "start": _komut_yardim,
    "yardim": _komut_yardim,
    "help": _komut_yardim,
    "durum": _komut_durum,
    "formasyonlar": _komut_formasyonlar,
    "formasyon": _komut_formasyonlar,
    "liste": _komut_formasyonlar,
    "tara": _komut_tara,
    "canli": _komut_canli,
    "c": _komut_canli,
    "ozet": _komut_ozet,
    "o": _komut_ozet,
    "gunluk": _komut_ozet,
    "sikisanlar": _komut_sikisanlar,
    "sikisan": _komut_sikisanlar,
    "sıkışanlar": _komut_sikisanlar,
    "sıkışan": _komut_sikisanlar,
    "s": _komut_sikisanlar,
    "tamamlanan": _komut_tamamlanan,
    "tamam": _komut_tamamlanan,
    "t": _komut_tamamlanan,
    "retest": _komut_retest,
    "r": _komut_retest,
    "kirilim": _komut_kirilim,
    "kırılım": _komut_kirilim,
    "k": _komut_kirilim,
    "panel": _komut_panel,
    "p": _komut_panel,
    "genel": _komut_panel,
    "tablo": _komut_panel,
}

# === SON TARAMA KALICILIĞI ===
# Render'ın diski geçicidir; aynı liste mevcut bot_store tablosunda da tutulur.
# LiveState kilidinden yalnızca kopya alınır, disk/ağ I/O'su kilit dışında yapılır.
# Batch 8 / C2 (8.4): son tarama kalıcılığı `state/persistence.py`'ye taşındı.
# Aşağıdaki fonksiyonlar eski imzalarını koruyan ince adaptörlerdir (global
# durumu toplar, işi katmana bırakır).
from state import persistence as _state_persistence
from state import paths as _state_paths

# Eski iç adlar (testler ve main gövdesi) korunuyor: yol/snapshot yardımcıları
# artık `state/paths.py`'de yaşıyor.
_son_tarama_data_dir = _state_paths.son_tarama_data_dir
_son_tarama_yolu = _state_paths.son_tarama_yolu
_digest_pending_yolu = _state_paths.digest_pending_yolu
_kayit_zamani = _state_paths.kayit_zamani
_yeni_snapshot = _state_paths.yeni_snapshot
SON_TARAMA_DOSYA = _state_paths.SON_TARAMA_DOSYA
SON_TARAMA_SUPABASE_KEY = _state_paths.SON_TARAMA_SUPABASE_KEY


def son_tarama_kaydet(store=None, data_dir=None) -> bool:
    """Son listeyi Supabase + diske kaydeder (bkz. state.persistence)."""
    return _state_persistence.son_tarama_kaydet(
        _live_state,
        store=_supabase_store_ref if store is None else store,
        data_dir=data_dir,
    )


def son_tarama_yukle(store=None, data_dir=None) -> int:
    """Kayıtlı son taramayı yükler (bkz. state.persistence)."""
    return _state_persistence.son_tarama_yukle(
        _live_state,
        store=_supabase_store_ref if store is None else store,
        data_dir=data_dir,
    )

# === TELEGRAM WEBHOOK (Render) ===
# Neden: Render Free bir web servistir; uyku/restart döngüsüne girer. Yoklama
# (getUpdates) modunda uzun yoklama bağlantısı her restart'ta yeniden kurulur ve
# token'ı dinleyen ikinci bir kopya varsa 409 alınır. Webhook modunda Telegram
# güncellemeyi doğrudan HTTPS ile iter; ayrı port/thread gerekmez, mevcut küçük
# HTTP sunucusu (health_server) kullanılır.
#
# Mod seçimi: TELEGRAM_WEBHOOK_SECRET varsa webhook, yoksa yoklama. İkisi asla
# aynı anda açık olmaz: webhook açıkken getUpdates çağrılmaz (Telegram 409 verir),
# yoklamaya dönülürken de webhook silinir.

# === TELEGRAM (taşıma katmanı — Batch 8 / C2, 8.5) ===
# Sır/adres çözümleme, Bot API çağrısı ve webhook kurulumu artık
# `transport/telegram.py`'de. Buradaki adaptörler eski iç adları ve imzaları
# korur; API fonksiyonları ÇAĞRI ANINDA main globalinden okunur, böylece
# testlerdeki `monkeypatch.setattr(main_mod, "_telegram_api_cagri", ...)`
# davranışı aynen çalışır.
from transport import telegram as _transport_telegram

_webhook_adres_gizle = _transport_telegram.webhook_adres_gizle
_telegram_api_cagri = _transport_telegram.api_cagri
_telegram_yanit_oku = _transport_telegram.yanit_oku


def _telegram_webhook_secret_ayikla(secret=None) -> str:
    # config değeri ÇAĞRI ANINDA okunur: testlerdeki monkeypatch(main, ...) etkili olur.
    return _transport_telegram.webhook_secret_ayikla(secret, varsayilan=TELEGRAM_WEBHOOK_SECRET)


def _telegram_token_al(token=None) -> str:
    return _transport_telegram.token_al(token, notifier=_notifier_ref)


def _telegram_webhook_url_olustur(secret=None, webhook_url=None, render_url=None) -> str:
    return _transport_telegram.webhook_url_olustur(
        secret=secret, webhook_url=webhook_url, render_url=render_url,
        varsayilan_secret=TELEGRAM_WEBHOOK_SECRET,
        varsayilan_url=TELEGRAM_WEBHOOK_URL,
        varsayilan_render=RENDER_EXTERNAL_URL)


def _telegram_set_webhook(url=None, secret=None, token=None) -> bool:
    return _transport_telegram.set_webhook(
        url=url, secret=secret, token=token,
        api=_telegram_api_cagri, yanit_oku_fn=_telegram_yanit_oku,
        secret_ayikla_fn=_telegram_webhook_secret_ayikla, token_al_fn=_telegram_token_al,
        adres_olustur_fn=_telegram_webhook_url_olustur, gizle_fn=_webhook_adres_gizle,
    )


def _telegram_delete_webhook(token=None) -> bool:
    return _transport_telegram.delete_webhook(
        token=token, api=_telegram_api_cagri, yanit_oku_fn=_telegram_yanit_oku,
        token_al_fn=_telegram_token_al,
    )


def _telegram_komut_katmanini_kur(notifier, isleyici=None) -> str:
    """Komut katmanını AYNI ANDA TEK modda kurar: 'webhook', 'yoklama' veya 'kapali'.

    - **webhook**: secret + taban adres var, HTTP sunucusu ayakta ve setWebhook
      başarılı. Güncellemeler `/webhook/<secret>` ucundan gelir; yoklama thread'i
      AÇILMAZ (aynı token'da getUpdates 409 alır).
    - **yoklama**: eski davranış (getUpdates daemon thread). Webhook kapalıyken ya da
      setWebhook başarısız olduğunda komutlar tamamen susmasın diye buraya düşülür;
      önce eski webhook kaydı silinir (yoksa 409).
    - **kapali**: token/chat_id yok - bot yalnızca alarm gönderir.

    `isleyici` yalnızca testler için verilir (ağa çıkmayan sahte dinleyici).
    """
    global _telegram_listener_ref, _telegram_update_processor_ref
    sonuc = _transport_telegram.komut_katmanini_kur(
        notifier, isleyici,
        komutlar=TELEGRAM_KOMUTLARI, yardim_metni=KOMUT_YARDIM,
        tarama_suruyor=lambda: _scan_job_active.is_set(),
        health_server_var=_health_server_ref is not None,
        listener_factory=TelegramCommandListener,
        adres_olustur=_telegram_webhook_url_olustur,
        gizle=_webhook_adres_gizle,
        secret_ayikla=_telegram_webhook_secret_ayikla,
        set_webhook_fn=_telegram_set_webhook,
        delete_webhook_fn=_telegram_delete_webhook,
    )
    if sonuc["mod"] == "webhook":
        _telegram_update_processor_ref = sonuc["processor"]
    elif sonuc["mod"] == "yoklama":
        _telegram_listener_ref = sonuc["listener"]
    return sonuc["mod"]

def _telegram_webhook_isle(guncelleme):
    """health_server'ın /webhook ucundan gelen güncellemeyi işler (thread-safe).

    Dönen değer HTTP kodudur:
      200 → işlendi (cevap sendMessage ile gitti),
      503 → bot henüz komutları kurmadı (Telegram tekrar dener),
      500 → işleyici hatası (Telegram tekrar dener, güncelleme kaybolmaz).
    """
    isleyici = _telegram_update_processor_ref
    if isleyici is None:
        return 503
    with _telegram_webhook_kilidi:
        try:
            isleyici.handle_update(guncelleme)
        except Exception as exc:  # noqa: BLE001 - tek güncelleme sunucuyu düşürmesin
            logger.error(f"Webhook guncellemesi islenemedi: {exc}", exc_info=True)
            return 500
    return 200


def _istek_tam_evrende_tamamlandi(result: dict, evren_boyutu: int = None) -> bool:
    """Başarılı tam manuel analiz, aynı kapanış için otomatik taramayı karşılar."""
    toplam = len(ACTIVE_STOCKS) if evren_boyutu is None else int(evren_boyutu)
    return bool(
        (result or {}).get("status") == "tamamlandi"
        and (result or {}).get("requested") == toplam
    )


def _calistir_istek_taramasi(deque_manager, lifecycle_manager, notifier) -> bool:
    """Kuyruktaki kullanıcı isteğini seans saatinden bağımsız çalıştır."""
    global _scan_job_request
    with _scan_request_lock:
        request = _scan_job_request
        _scan_istegi.clear()
    if not request:
        _scan_job_active.clear()
        return False
    try:
        result = scan_all_stocks(
            deque_manager,
            lifecycle_manager,
            notifier,
            manuel=True,
            stocks=request.get("hisseler"),
            send_alerts=False,
        )
    except Exception as exc:
        logger.error("İstenen analiz çalışırken hata verdi: %s", exc, exc_info=True)
        result = _analiz_hatasi_kaydi(exc, len(request.get("hisseler") or []), "istenen analiz")
    _manuel_tarama_tamamla(request, result or {}, notifier)
    return True


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


def scan_all_stocks(deque_manager: StockDequeManager, lifecycle_manager: PatternLifecycleManager, notifier: TelegramNotifier, manuel: bool = False, stocks=None, send_alerts: bool = True):
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
    scan_stocks = list(dict.fromkeys(stocks or ACTIVE_STOCKS))
    tur_taranan = 0
    tur_formasyon = 0
    tur_hata = 0
    en_son_bar = None
    en_eski_bar_yasi_dk = None
    _live_state.begin_scan(
        simdiki_zaman,
        manuel=manuel,
        beklenen_hisse=len(scan_stocks),
        scope=scan_stocks,
        replace_all=(set(scan_stocks) == set(ACTIVE_STOCKS)),
    )
    logger.info(f"=== TARAMA BAŞLIYOR{' (ELLE)' if manuel else ''} - {len(scan_stocks)} hisse, profil: {PROFILE} "
                f"({simdiki_zaman.strftime('%H:%M')}) ===")
    logger.info(
        f"Yahoo pacing: her {SCAN_REQUEST_BATCH_SIZE} istekte "
        f"{SCAN_REQUEST_DELAY_MIN_SEC:.1f}-{SCAN_REQUEST_DELAY_MAX_SEC:.1f} sn aralık, "
        f"grup arası {SCAN_BATCH_PAUSE_MIN_SEC:.0f}-{SCAN_BATCH_PAUSE_MAX_SEC:.0f} sn"
    )

    # Sağlıklı cache'te son 5 günü, boş/5 günden eski cache'te tam 60 günü çek.
    # Böylece rutin saatlik taramada büyük geçmiş penceresi tekrar tekrar inmez.
    fetch_periods = {}
    for stock in scan_stocks:
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
        scan_stocks, pacer, "MANUEL ANALİZ" if manuel else "CANLI TARAMA", periods=fetch_periods
    )
    daily_stats['fetch_ok'] += len(taze_1h_verileri)
    daily_stats['fetch_failures'] += len(fetch_hatalari)
    daily_stats['fetch_retries'] += retry_sayisi
    daily_stats['fetch_retry_recovered'] += retry_kurtarilan

    for idx, stock in enumerate(scan_stocks):
        if _shutdown_requested:
            logger.info("Kapanış istendi, tarama durduruluyor")
            break
        try:
            reset_daily_if_needed()
            simdiki_zaman = datetime.now(ISTANBUL_TZ)
            
            logger.info(f"[{idx+1}/{len(scan_stocks)}] {stock} taranıyor...")
            
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
            son_bar = df_1h.index[-1]
            son_bar = son_bar.tz_convert(ISTANBUL_TZ) if son_bar.tzinfo else ISTANBUL_TZ.localize(son_bar)
            en_son_bar = max(en_son_bar, son_bar) if en_son_bar is not None else son_bar
            son_bar_yasi_dk = (simdiki_zaman - df_1h.index[-1].tz_convert(ISTANBUL_TZ)
                               if df_1h.index[-1].tzinfo else
                               simdiki_zaman - ISTANBUL_TZ.localize(df_1h.index[-1])).total_seconds() / 60.0
            if daily_stats['max_bar_age_min'] is None or son_bar_yasi_dk > daily_stats['max_bar_age_min']:
                daily_stats['max_bar_age_min'] = round(son_bar_yasi_dk, 1)
            if en_eski_bar_yasi_dk is None or son_bar_yasi_dk > en_eski_bar_yasi_dk:
                en_eski_bar_yasi_dk = round(son_bar_yasi_dk, 1)
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

            # Seans dışında provider'dan yeni mum gelmemesi olağandır; bu durum
            # yalnızca piyasa açıkken VERİ YOK sayılır. Kapalı seanslarda son mum,
            # genel yaş sınırına kadar değerlendirilebilir.
            seans_acik = tarama_penceresi_acik_mi(simdiki_zaman)
            if (taze is None and seans_acik and son_bar_yasi_dk is not None
                    and son_bar_yasi_dk > VERI_YOK_MODU_ESIK_DK):
                daily_stats['veri_yok_modu'] = True
                logger.info(
                    f"{stock}: seans açıkken yeni veri yok (son mum "
                    f"{son_bar_yasi_dakika_str(son_bar_yasi_dk)} önce, fetch başarısız) - analiz atlanıyor"
                )
                continue

            # Seans içinde fetch başarısızsa eski cache ile sinyal üretme. Seans
            # dışında ise en son tamamlanmış mum, yapılandırılmış yaş sınırına
            # (varsayılan 14 gün) kadar açıkça eski veri olarak kullanılabilir.
            if not _cache_verisi_kullanilabilir(
                    son_bar_yasi_dk, taze is not None, seans_acik):
                daily_stats['stale_stocks'] += 1
                daily_stats['data_stale'] = True
                logger.warning(
                    f"{stock}: son tamamlanmış mum {son_bar_yasi_dakika_str(son_bar_yasi_dk)} yaşında; "
                    "bu hisse analiz dışı bırakıldı"
                )
                continue
            if taze is None and not seans_acik and son_bar_yasi_dk > STALE_BAR_UYARI_DK:
                logger.warning(
                    f"{stock}: sağlayıcıya erişilemedi; seans dışı son mevcut cache "
                    f"({son_bar_yasi_dakika_str(son_bar_yasi_dk)}) kullanılıyor"
                )

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
            hisse_formasyonlari = []
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
                    _note_pattern_found(stock, tf_name)
                    logger.info(f"🔍 {stock} {tf_name} - {active.pattern_type} kalite {q:.0f} state {state} - {snap.log}")
                    
                    # Alert eşiği kontrolü - timeframe'e göre (effective_quality üzerinden)
                    min_q = ALERT_MIN_QUALITY.get(tf_name, ALERT_MIN_QUALITY_GLOBAL)
                    try:
                        yas_bar = max(0, int(snap.bar_index - active.start_bar))
                    except Exception:
                        yas_bar = None
                    # Telegram /formasyonlar ve Top-12 sıralaması aynı hesaplanmış
                    # formasyon kaydını kullanır; scoring için temas/daralma da saklanır.
                    tur_formasyon += 1
                    formasyon_kaydi = {
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
                        'contraction': getattr(active, 'contraction', None),
                        'upper_touches': getattr(active, 'upper_touches', None),
                        'lower_touches': getattr(active, 'lower_touches', None),
                        'age_bars': yas_bar,
                        'mtf_destek': False,
                        'bar_time': str(df_tf.index[-1]),
                        'min_quality': float(min_q),
                        'alert_gonderildi': False,
                    }
                    hisse_formasyonlari.append(formasyon_kaydi)
                    _live_state.record_formation(formasyon_kaydi)
                    # Her başarılı sembol/TF analizi bekleyen adayın son durumunu yeniler.
                    # Kalite eşiği altı kayıtlar kapanış özetine de taşınmaz.
                    if state in WATCH_STATES and q >= min_q:
                        _deferred_alert_buffer.observe(stock, tf_name, formasyon_kaydi, simdiki_zaman)
                    else:
                        _deferred_alert_buffer.observe(stock, tf_name, None, simdiki_zaman)
                    # Aday hunisi: bu kaydın akıbeti sayılır (bkz. daily_stats notu).
                    if q < min_q:
                        daily_stats['alerts_below_threshold'] += 1
                        logger.debug(f"{stock} {tf_name} kalite {q:.0f} < {min_q} (alert eşiği) - telegram atlanıyor")
                    elif send_alerts and state in WATCH_STATES:
                        daily_stats['alerts_deferred'] += 1
                        logger.info(f"{stock} {tf_name} {state}: düşük öncelikli bildirim kapanış özetine ertelendi")
                    # Teyitli kırılım, başarılı retest, tamamlanma ve başarısız kırılım acildir.
                    elif send_alerts and state in IMMEDIATE_ALERT_STATES:
                        # Humanized mesaj için ek bilgiler - var olan veriyi kullan, ekstra hesaplama yok
                        upper_touches = getattr(active, 'upper_touches', None)
                        lower_touches = getattr(active, 'lower_touches', None)
                        try:
                            age_bars = snap.bar_index - active.start_bar if hasattr(active, 'start_bar') and snap.bar_index >= 0 else None
                        except Exception:
                            age_bars = None
                        # Çoklu zaman teyidi: 1h kırılımında 4h destekliyor mu?
                        mtf_destek = False
                        try:
                            if tf_name == "1h":
                                snap_4h = lifecycle_manager.get_snapshot(stock + "_4h")
                                if snap_4h and snap_4h.active and snap_4h.state not in ("FORMASYON_GECERSIZ", "Yok", "ST_NONE"):
                                    mtf_destek = True
                            elif tf_name == "4h":
                                snap_1d = lifecycle_manager.get_snapshot(stock + "_1d")
                                if snap_1d and snap_1d.active:
                                    mtf_destek = True
                        except Exception:
                            mtf_destek = False

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
                            'upper_touches': upper_touches,
                            'lower_touches': lower_touches,
                            'age_bars': age_bars,
                            'mtf_destek': mtf_destek,
                            # Acil mesaja bağlam olarak en fazla 3 aday eklenir; havuz
                            # (12) bu listenin seçildiği yerdir, gönderilen sayı değil.
                            'watch_context': [
                                item for item in _deferred_alert_buffer.items(
                                    simdiki_zaman, limit=WATCH_CONTEXT_HAVUZU)
                                if not (item.get('stock') == stock and item.get('timeframe') == tf_name)
                            ][:3],
                        }
                        daily_stats['alerts_attempted'] += 1
                        if notifier.send(alert_data):
                            daily_stats['alerts_sent'] += 1
                            _deferred_alert_buffer.mark_reported(alert_data['watch_context'], simdiki_zaman)
                            _live_state.mark_alert_sent(stock, tf_name)
                            logger.info(f"📨 Telegram gönderildi: {stock} {tf_name} {state} kalite {q:.0f} touches={upper_touches}/{lower_touches} age={age_bars} mtf={mtf_destek}")
                        else:
                            # Neden gönderilemedi? cooldown/kap ise olay kaybolmasın
                            # (Batch 5'te kuyruğa alınır); şimdilik sayılır.
                            daily_stats['alerts_failed'] += 1
                            if getattr(notifier, "_son_engel", ""):
                                if notifier._son_engel == "cooldown":
                                    daily_stats['alerts_engel_cooldown'] += 1
                                else:
                                    daily_stats['alerts_engel_kap'] += 1
                                # Olay kaybolmadı: kuyruğa alındı, engel kalkınca gider.
                                if notifier.kuyrukta_mi(alert_data):
                                    daily_stats['alerts_kuyruk'] += 1
                                    logger.info(
                                        f"📬 {stock} {tf_name} {state} engel nedeniyle kuyruğa alındı "
                                        f"({notifier._son_engel})"
                                    )
                            logger.warning(
                                f"⚠️ Telegram gönderilemedi: {stock} {tf_name} {state} "
                                f"(engel: {getattr(notifier, '_son_engel', None) or 'gönderim hatası'})"
                            )
                    elif send_alerts:
                        # Ne acil ne izleme: mevcut state politikasında push yok,
                        # yalnız /panel ve /formasyonlar gösterir. Sessizce düşmesin.
                        daily_stats['alerts_state_disabled'] += 1
                else:
                    # Başarılı TF taramasında aday kaybolduysa bekleyen kaydı kaldır.
                    _deferred_alert_buffer.observe(stock, tf_name, None, simdiki_zaman)
                    # Canlı formasyon yok (terminal state'ler ve kalite kapısı dahil)
                    logger.debug(f"{stock} {tf_name} - Canlı formasyon yok: {snap.log}")
            
            for formasyon_kaydi in hisse_formasyonlari:
                tf_kaydi = formasyon_kaydi.get("timeframe")
                teyit_tf = "4h" if tf_kaydi in ("1h", "2h") else "1d" if tf_kaydi == "4h" else None
                if teyit_tf:
                    teyit = lifecycle_manager.get_snapshot(stock + "_" + teyit_tf)
                    formasyon_kaydi["mtf_destek"] = bool(
                        teyit and teyit.active
                        and teyit.state not in ("FORMASYON_GECERSIZ", "Yok", "ST_NONE")
                    )
                    _live_state.record_formation(formasyon_kaydi)

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
            tur_hata += 1
            logger.error(f"{stock} tarama hatası: {e} - devam ediliyor", exc_info=True)
            continue
    
    for _st in scan_stocks[:3]:
        _df_g = deque_manager.to_gunluk_dataframe(_st)
        if _df_g is not None:
            daily_stats['gunluk_bar_sayisi'] = len(_df_g)
            break

    sure_dk = (time.monotonic() - tarama_baslangici) / 60.0
    daily_stats['son_tarama_suresi_dk'] = round(sure_dk, 1)
    eksik = max(len(scan_stocks) - tur_taranan, 0)
    global last_run_stats
    run_status = "tamamlandi" if tur_taranan == len(scan_stocks) and tur_hata == 0 else "basarisiz"
    last_run_stats = {
        "status": run_status,
        "requested": len(scan_stocks),
        "processed": tur_taranan,
        "failed": max(tur_hata, eksik),
        "patterns": tur_formasyon,
        "fresh_fetch": len(taze_1h_verileri),
        "fetch_failures": len(fetch_hatalari),
        "duration_minutes": round(sure_dk, 1),
        "data_asof": en_son_bar.isoformat() if en_son_bar is not None else None,
        "oldest_bar_age_minutes": en_eski_bar_yasi_dk,
        "finished_at": datetime.now(ISTANBUL_TZ).isoformat(),
    }
    if run_status == "tamamlandi":
        _live_state.finish_scan(
            datetime.now(ISTANBUL_TZ),
            son_tarama_durumu="tamamlandi",
            son_tarama_suresi_dk=round(sure_dk, 1),
            son_tarama_hissesi=tur_taranan,
            son_tarama_beklenen_hisse=len(scan_stocks),
            son_tarama_hata_hisse=0,
            son_tarama_taze_veri=len(taze_1h_verileri),
            son_tarama_fetch_hatasi=len(fetch_hatalari),
            son_tarama_formasyonu=tur_formasyon,
            son_tarama_veri_zamani=en_son_bar.isoformat() if en_son_bar is not None else None,
            son_tarama_en_eski_veri_yasi_dk=en_eski_bar_yasi_dk,
        )
        son_tarama_kaydet()
    else:
        hata = (f"Eksik tarama: {tur_taranan}/{len(scan_stocks)} hisse başarıyla hesaplandı; "
                f"{max(tur_hata, eksik)} hata/atlanan.")
        _live_state.fail_scan(
            hata,
            datetime.now(ISTANBUL_TZ),
            hata_hisse=max(tur_hata, eksik),
            islenen_hisse=tur_taranan,
            istek_hisse=len(scan_stocks),
            sure_dk=round(sure_dk, 1),
        )
        logger.error("Tarama sonucu yayımlanmadı; son başarılı snapshot korundu. %s", hata)

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
    # Tarama bitti: heartbeat kesin yazılsın (force), böylece per-hisse
    # throttle'a takılan son durum dışarıdan anında görünür.
    write_heartbeat(notifier=notifier, force=True)
    return dict(last_run_stats)


def _parse_summary_hours() -> List[dt_time]:
    """SUMMARY_HOURS env'ini İstanbul saatine çevir (09:55,18:45)."""
    try:
        saatler = []
        for ham in SUMMARY_HOURS.split(","):
            ham = ham.strip()
            if not ham:
                continue
            h, m = ham.split(":")
            saatler.append(dt_time(int(h), int(m)))
        return saatler
    except Exception:
        return [dt_time(9, 55), dt_time(18, 45)]


def _parse_deferred_alert_digest_time() -> dt_time:
    """Kapanış özeti en erken son otomatik tarama sonrasına (18:45) ayarlanır."""
    try:
        h, m = DEFERRED_ALERT_DIGEST_TIME.split(":")
        saat = dt_time(int(h), int(m))
        if saat < dt_time(18, 45):
            logger.warning("DEFERRED_ALERT_DIGEST_TIME son taramadan önce; 18:45'e alındı")
            return dt_time(18, 45)
        return saat
    except Exception:
        logger.warning("DEFERRED_ALERT_DIGEST_TIME geçersiz; 18:45 kullanılacak")
        return dt_time(18, 45)


def _effective_summary_hours() -> List[dt_time]:
    """Akşam özetini son tarama sonrasına al; eski 18:15 saatiyle çakıştırma."""
    digest_time = _parse_deferred_alert_digest_time()
    morning_and_day = [hour for hour in _parse_summary_hours() if hour.hour < 18]
    return sorted(set(morning_and_day + [digest_time]))


# Batch 8 / C2 (8.4): digest tamponu kalıcılığı da `state/persistence.py`'de.
DIGEST_PENDING_SUPABASE_KEY = _state_persistence.DIGEST_PENDING_SUPABASE_KEY
DIGEST_PENDING_DOSYA = _state_paths.DIGEST_PENDING_DOSYA


def digest_tamponu_kaydet(store=None, data_dir=None) -> bool:
    """Bekleyen gün içi adayları Supabase + diske yazar."""
    return _state_persistence.digest_tamponu_kaydet(
        _deferred_alert_buffer,
        store=_supabase_store_ref if store is None else store,
        data_dir=data_dir,
        son_digest_gun=_digest_son_gonderim_gun,
    )


def digest_tamponu_yukle(store=None, data_dir=None) -> int:
    """En yeni digest tamponunu yükler; yüklenen aday sayısını döner."""
    global _digest_son_gonderim_gun
    sayi, son_digest_gun = _state_persistence.digest_tamponu_yukle(
        _deferred_alert_buffer,
        store=_supabase_store_ref if store is None else store,
        data_dir=data_dir,
    )
    if son_digest_gun is not None:
        _digest_son_gonderim_gun = son_digest_gun
    return sayi

def _kacirilan_digest_ozeti(notifier, simdiki_zaman) -> str:
    """Geçmiş günden kalan bekleyen adaylar için kaçırılan 18:45 telafisi.

    Bot akşam 18:45'te kapalıysa tampon bir sonraki açılışa kadar bekler;
    burada tek seferde gönderilir (aksi halde _ensure_day ilk taramada temizler).
    """
    global _digest_son_gonderim_gun
    gun = _deferred_alert_buffer.gun()
    if not _deferred_alert_buffer or gun is None or gun >= simdiki_zaman.date():
        return ""
    bekleyen = _deferred_alert_buffer.items(
        ISTANBUL_TZ.localize(datetime.combine(gun, dt_time(23, 59))),
        limit=DEFERRED_ALERT_DIGEST_LIMIT,
    )
    if not bekleyen:
        return ""
    watch_summary = _format_deferred_alert_summary(bekleyen, len(_deferred_alert_buffer))
    metin = f"⏰ Kaçırılan kapanış özeti ({gun.strftime('%d.%m')} 18:45)\n{watch_summary}"
    if notifier is None or not notifier.enabled:
        # Pasif modda sessizce düşmesin: bir sonraki açılışta tekrar denenmeyecek,
        # bu yüzden kayıt yine de temizlenir ve durum loglanır.
        logger.warning("Kaçırılan kapanış özeti gönderilemedi (Telegram pasif): %d aday", len(bekleyen))
    else:
        gonderildi, hata = notifier.send_text(metin)
        if gonderildi:
            _deferred_alert_buffer.mark_reported(bekleyen, simdiki_zaman)
            # Telafi edilen gün "gönderildi" sayılır; bugünün 18:45'i hâlâ bekliyor.
            _digest_son_gonderim_gun = gun.isoformat()
            logger.info("Kaçırılan kapanış özeti gönderildi: %d aday (%s)", len(bekleyen), gun)
        else:
            logger.warning("Kaçırılan kapanış özeti gönderilemedi: %s", hata)
    _deferred_alert_buffer.clear(simdiki_zaman)
    digest_tamponu_kaydet()
    return metin


def _parse_post_close_analysis_time() -> dt_time:
    """Gün sonu tam tarama saatini İstanbul yerel saati olarak çöz."""
    try:
        hour, minute = POST_CLOSE_ANALYSIS_TIME.strip().split(":", 1)
        return dt_time(int(hour), int(minute))
    except (AttributeError, TypeError, ValueError):
        logger.warning("POST_CLOSE_ANALYSIS_TIME geçersiz; 20:00 kullanılacak")
        return dt_time(20, 0)


def _build_active_formations_for_summary(lifecycle_manager, min_quality: float = None) -> List[Dict]:
    """Özet için aktif formasyonları topla (canlı + taze terminal)."""
    if min_quality is None:
        min_quality = PUBLIC_MIN_QUALITY
    aktif = []
    try:
        # Özet ile /panel AYNI kaynaktan beslenir: son başarılı taramanın canlı
        # listesi. (Eski kod olmayan bir metodu -get_formations- hasattr ile
        # yoklayıp her zaman lifecycle snapshots yoluna düşüyordu; sonuç: özet ile
        # panel farklı listeler gösterebiliyordu.)
        formations = _live_state.formations()
        # LiveState boşsa (ilk tarama öncesi) lifecycle_manager snapshots'a düş.
        if not formations:
            for key, snap in getattr(lifecycle_manager, 'last_snapshots', {}).items():
                if snap.active and snap.effective_quality and snap.effective_quality >= min_quality:
                    # stock_timeframe key'ini ayır
                    parts = key.rsplit("_", 1)
                    stock = parts[0] if len(parts) == 2 else key
                    tf = parts[1] if len(parts) == 2 else "1h"
                    aktif.append({
                        'stock_name': stock,
                        'timeframe': tf,
                        'pattern_name': snap.active.pattern_type,
                        'state': snap.state,
                        'confidence_score': snap.effective_quality,
                        'contraction': getattr(snap.active, 'contraction', None),
                        'break_dir': snap.break_dir,
                    })
        else:
            for f in formations:
                if f.get('quality', 0) >= min_quality:
                    aktif.append({
                        'stock_name': f.get('stock'),
                        'timeframe': f.get('timeframe'),
                        'pattern_name': f.get('pattern_name'),
                        'state': f.get('state'),
                        'confidence_score': f.get('quality'),
                        # Daralma gerçek kayıttan gelir; eskiden sabit None
                        # yazılıyordu ve özetin "⚡ SIKIŞANLAR" bölümü sessizce
                        # boşalıyordu (karşılaştırma: contraction >= eşik).
                        'contraction': f.get('contraction'),
                        'break_dir': f.get('break_dir', 0),
                    })
    except Exception as e:
        logger.debug(f"Özet için formasyon toplanamadı: {e}")
    return aktif


def evening_maintenance(deque_manager, lifecycle_manager):
    """18:10-19:00 kapanış bakımı - 3 problem için tek seferlik hafif iş."""
    logger.info("=== AKŞAM BAKIMI BAŞLIYOR (veri hijyeni + state temizliği + rapor) ===")
    try:
        # 1. Veri hijyeni: hacmi 0 veya zaman damgası hatalı son barları temizle
        temizlenen = 0
        for stock in ACTIVE_STOCKS:
            try:
                df = deque_manager.to_dataframe(stock)
                if df is not None and len(df) > 0:
                    # Son bar hacmi 0 ise ve gün içinde eksik kalmışsa
                    son = df.iloc[-1]
                    if son.get('volume', 1) == 0:
                        # Sadece logla, silme değil - data.py zaten filtreliyor
                        logger.debug(f"{stock}: son bar hacim 0 - hijyen logu")
                        temizlenen += 1
            except Exception as e:
                logger.debug(f"{stock} hijyen hatası: {e}")
        logger.info(f"Veri hijyeni: {temizlenen} hisse kontrol edildi")

        # 2. State temizliği: 48 saatten uzun süredir kırılım yapmamış dosyalar
        # lifecycle_manager zaten terminal tazelik kontrolü yapıyor, burada disk temizliği
        try:
            import glob
            from config import DATA_DIR
            import os
            json_files = glob.glob(os.path.join(DATA_DIR, "*.json"))
            if len(json_files) > 100:
                logger.warning(f"bot_data'da {len(json_files)} dosya var, şişme riski - Supabase kullanılıyor mu kontrol et")
        except Exception as e:
            logger.debug(f"State temizliği atlandı: {e}")

        # 3. Gün sonu raporu
        try:
            rapor = _live_state.status() if hasattr(_live_state, 'status') else {}
            logger.info(f"GÜN SONU RAPORU: {rapor}")
            # Telegram DM'e gün sonu özeti (sadece owner)
            if _notifier_ref and _notifier_ref.enabled:
                aktif = _build_active_formations_for_summary(lifecycle_manager)
                ozet = _notifier_ref.format_daily_summary(aktif, daily_stats)
                _notifier_ref.send_text(f"📋 Gün Sonu Bakım Raporu\n{ozet}")
        except Exception as e:
            logger.warning(f"Gün sonu raporu hatası: {e}")

        logger.info("=== AKŞAM BAKIMI BİTTİ ===")
    except Exception as e:
        logger.error(f"Akşam bakımı hatası: {e}", exc_info=True)


def morning_preload(deque_manager, pacer):
    """08:30 pre-load - açılışta 0-latency için son barları yavaşça çek."""
    logger.info("=== SABAH ÖN-YÜKLEME BAŞLIYOR (08:30) ===")
    try:
        for stock in ACTIVE_STOCKS[:10]:  # ilk 10 hisse, yavaşça
            if _shutdown_requested:
                break
            try:
                with pacer.request(f"{stock} preload"):
                    taze = fetch_last_bar(stock)
                if taze is not None and len(taze) > 0:
                    deque_manager.append_dataframe(stock, taze)
                    logger.debug(f"{stock}: preload {len(taze)} bar")
                time.sleep(1)
            except Exception as e:
                logger.debug(f"{stock} preload hatası: {e}")
        logger.info("=== SABAH ÖN-YÜKLEME BİTTİ ===")
    except Exception as e:
        logger.error(f"Sabah preload hatası: {e}", exc_info=True)


def main_loop():
    """
    Ana döngü:
    1. BIST açık mı kontrol et
    2. Açıksa -> mum kapanışından 5dk sonra tara
    3. Kapalıysa -> 5dk uyu, tekrar kontrol et
    Neden 24/7 çalışıp sadece seans saatlerinde CPU harcasın? Oracle Free'de kaynak kısıtlı
    """
    setup_logging()   # Batch 8 / C2: handler'lar burada bağlanır (import yan etkisi yok)
    logger.info("=== BIST FORMASYON BOTU BAŞLATILIYOR ===")
    logger.info(f"Profil: {PROFILE}, Params: {PROFILE_PARAMS}")
    logger.info(f"Hisseler: {ACTIVE_STOCKS[:5]}... (toplam {len(ACTIVE_STOCKS)})")
    evren_uyarisi = _evren_olcek_uyarisi()
    if evren_uyarisi:
        logger.warning(evren_uyarisi)
    
    global _deque_manager_ref, _notifier_ref, _supabase_store_ref, _telegram_update_processor_ref, _lifecycle_manager_ref
    # Digest damgası main_loop içinde birden çok yerde okunur/yazılır; global
    # bildirimi fonksiyon başında olmalı (Python kuralı).
    global _digest_son_gonderim_gun
    supabase_store = SupabaseStore.from_env()
    _supabase_store_ref = supabase_store
    if supabase_store is not None:
        # Ortam değişkenleri yanlışsa teşhis loga düşsün; hata halinde bot durmaz.
        supabase_store.ping()
    # Restart/uyku sonrası son başarılı tarama listesi geri yüklenir (Supabase ve
    # yerel dosyanın EN YENİ kopyası). Bu çağrı olmadan /panel, /canli, /durum ve
    # sabah özeti her yeniden başlatmada boş görünür; kalıcılık yazılır ama okunmaz.
    son_tarama_yukle(supabase_store)
    # Çoklu kopya koruması: aynı anahtarlarla başka bir canlı örnek var mı?
    _tekil_ornek_kontrolu(supabase_store, force=True)
    # Bekleyen gün içi aday tamponu da kalıcıdır (Batch 5): 18:45'ten önce
    # restart olursa adaylar kaybolmaz. Telafi gönderimi notifier kurulduktan
    # hemen sonra yapılır (tampon günü eskiyse).
    digest_tamponu_yukle(supabase_store)
    # Analiz snapshot'ı komutların güncel kaynağı değildir. Her /panel ve
    # /tara isteği yeni veriyle yeniden hesaplanır. OHLCV önbelleği Supabase
    # erişilemezse yerel disk/Yahoo üzerinden kurulabilir.
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
    _lifecycle_manager_ref = lifecycle_manager
    notifier = TelegramNotifier(
        persistent_store=supabase_store,
        initial_store_data=remote_rows,
    )
    _notifier_ref = notifier
    # Telegram token/chat_id teşhisi: mesaj göndermeden getMe ile doğrular.
    notifier.check_connection()

    # İki yönlü Telegram: komutları (panel/canli/formasyonlar/durum/tara/yardim)
    # dinleyen katman. İki mod var, AYNI ANDA YALNIZCA BİRİ açılır:
    #   - webhook  : TELEGRAM_WEBHOOK_SECRET varsa ve HTTP sunucusu ayaktaysa
    #                (Telegram → POST /webhook/<secret>, health_server taşır)
    #   - yoklama  : aksi halde getUpdates uzun yoklaması (daemon thread)
    # Token/chat_id yoksa hiçbiri başlatılmaz; bot eskisi gibi yalnızca alarm gönderir.
    # 18:45 kapanış özeti kaçırıldıysa (bot akşam kapalıydı) ilk fırsatta telafi et.
    _kacirilan_digest_ozeti(notifier, datetime.now(ISTANBUL_TZ))
    # Kapanıştan önce engellenip kuyruğa giren acil olaylar varsa açılışta denensin.
    try:
        if notifier.enabled and notifier.kuyruk_durumu().get("bekleyen"):
            notifier.kuyrugu_bosalt()
    except Exception as _kuyruk_hata:
        logger.debug(f"Açılış kuyruk boşaltma hatası: {_kuyruk_hata}")

    _telegram_komut_katmanini_kur(notifier)
    
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
    # Özet ve bakım takibi (bedava kalma için)
    summary_hours = _effective_summary_hours()
    deferred_alert_digest_time = _parse_deferred_alert_digest_time()
    post_close_analysis_time = _parse_post_close_analysis_time()
    last_summary_sent = {}  # DM özeti: "09:55" -> date
    last_summary_channel_sent = {}  # kanal özeti ayrı izlenir; DM retry kanala kopya üretmesin
    last_post_close_analysis_date = None
    last_maintenance_date = None
    last_preload_date = None
    son_kuyruk_bosaltma = 0.0  # engellenen acil olaylar bu aralıkla yeniden denenir
    
    while not _shutdown_requested:
        try:
            now = datetime.now(ISTANBUL_TZ)
            # Kullanıcı isteği seans saatinden bağımsız olarak ilk fırsatta çalışır.
            if _scan_istegi.is_set():
                if _calistir_istek_taramasi(deque_manager, lifecycle_manager, notifier):
                    if _istek_tam_evrende_tamamlandi(last_run_stats):
                        kapanis = son_kapanan_mum_ani(datetime.now(ISTANBUL_TZ))
                        if kapanis is not None:
                            # Manuel /panel aynı kapanış mumunu başarıyla hesapladı;
                            # otomatik döngüde aynı tam evreni hemen tekrar tarama.
                            son_taranan_kapanis = kapanis
                    deque_manager.save_all()
                    continue
            # --- ENGELLENEN ACİL OLAYLAR (Batch 5 / B4) ---
            # Cooldown/saatlik kap yüzünden gönderilemeyen teyitli kırılım gibi
            # olaylar kuyrukta bekler; engel kalkınca en geç birkaç dakikada gider.
            try:
                if (notifier.enabled and notifier.kuyruk_durumu().get("bekleyen")
                        and time.time() - son_kuyruk_bosaltma >= ACIL_KUYRUK_BOSALTMA_ARALIK_SN):
                    son_kuyruk_bosaltma = time.time()
                    gonderilen_kuyruk = notifier.kuyrugu_bosalt()
                    if gonderilen_kuyruk:
                        logger.info(f"Engellenen acil kuyruğundan {gonderilen_kuyruk} olay gönderildi")
            except Exception as e:
                logger.debug(f"Acil kuyruk boşaltma hatası: {e}")

            # --- ÇOKLU ÖRNEK KONTROLÜ (Batch 6 / B10) ---
            # 5 dakikada bir: aynı Supabase anahtarlarını kullanan başka bir canlı
            # kopya var mı? (webhook modunda 409 sinyali yok; bu onun yerini tutar)
            try:
                _tekil_ornek_kontrolu(supabase_store)
            except Exception as e:
                logger.debug(f"Çoklu örnek kontrol hatası: {e}")

            # --- GÜNLÜK ÖZET + ERTELENMİŞ ADAYLAR (akşam 18:45) ---
            try:
                for sh in summary_hours:
                    sh_str = sh.strftime("%H:%M")
                    hedef = ISTANBUL_TZ.localize(datetime.combine(now.date(), sh))
                    gecikme_sn = (now - hedef).total_seconds()
                    # Normal özetler 10 dakikalık pencerede; kapanış özeti ise
                    # tarama uzasa bile aynı gün ilk fırsatta gönderilir.
                    ozet_zamani = now >= hedef and (
                        sh == deferred_alert_digest_time or gecikme_sn < 600
                    )
                    # Kapanış özeti kalıcı tampon taşır: restart sonrası aynı
                    # özet ikinci kez gönderilmesin (state:digest_pending).
                    if (ozet_zamani and sh == deferred_alert_digest_time
                            and _digest_son_gonderim_gun == now.date().isoformat()):
                        ozet_zamani = False
                    if not ozet_zamani:
                        continue
                    aktif = _build_active_formations_for_summary(lifecycle_manager)
                    ozet = notifier.format_daily_summary(aktif, daily_stats)
                    bekleyen = (
                        _deferred_alert_buffer.items(now, limit=DEFERRED_ALERT_DIGEST_LIMIT)
                        if sh == deferred_alert_digest_time else []
                    )
                    # Tampondaki gerçek aday sayısı: kesilenler özet metninde
                    # "… N aday daha" satırıyla görünür ve sayaca yazılır.
                    bekleyen_toplam = len(_deferred_alert_buffer) if bekleyen else 0
                    if bekleyen and bekleyen_toplam > len(bekleyen):
                        daily_stats['alerts_digest_overflow'] = bekleyen_toplam - len(bekleyen)
                    watch_summary = _format_deferred_alert_summary(bekleyen, bekleyen_toplam)
                    dm_ozet = f"📋 Günlük Özet\n{ozet}"
                    if watch_summary:
                        dm_ozet += "\n\n" + watch_summary

                    if last_summary_sent.get(sh_str) != now.date():
                        if notifier.enabled:
                            gonderildi, hata = notifier.send_text(dm_ozet)
                            if gonderildi:
                                last_summary_sent[sh_str] = now.date()
                                if bekleyen:
                                    _deferred_alert_buffer.mark_reported(bekleyen, now)
                                if sh == deferred_alert_digest_time:
                                    _digest_son_gonderim_gun = now.date().isoformat()
                                    digest_tamponu_kaydet()
                                logger.info(f"Günlük DM özeti gönderildi: {sh_str}")
                            else:
                                logger.warning(f"Günlük DM özeti gönderilemedi ({sh_str}): {hata}")
                        else:
                            # Test/pasif modda döngü boyunca aynı özeti tekrar deneme.
                            last_summary_sent[sh_str] = now.date()
                            if sh == deferred_alert_digest_time:
                                _digest_son_gonderim_gun = now.date().isoformat()

                    if (notifier.channel_id
                            and last_summary_channel_sent.get(sh_str) != now.date()):
                        if notifier.send_to_channel(ozet):
                            last_summary_channel_sent[sh_str] = now.date()
            except Exception as e:
                logger.debug(f"Özet gönderim hatası: {e}")

            # --- GÜN SONU TAM EVREN ANALİZİ (varsayılan 20:00 İstanbul) ---
            try:
                if now.time() >= post_close_analysis_time and last_post_close_analysis_date != now.date():
                    logger.info("Gün sonu tam evren analizi başlıyor (%s)",
                                post_close_analysis_time.strftime("%H:%M"))
                    _scan_job_active.set()
                    try:
                        try:
                            result = scan_all_stocks(
                                deque_manager, lifecycle_manager, notifier,
                                manuel=True, stocks=ACTIVE_STOCKS, send_alerts=False,
                            )
                        except Exception as exc:
                            logger.error("Gün sonu analiz çalıştırması çöktü: %s", exc, exc_info=True)
                            result = _analiz_hatasi_kaydi(
                                exc, len(ACTIVE_STOCKS), "gün sonu analiz",
                            )
                        if result.get("status") == "tamamlandi":
                            rapor = _panel_raporu("", tamamlandi=True)
                            notifier.send_text("🌙 GÜN SONU ANALİZİ\n" + rapor)
                        else:
                            notifier.send_text(
                                "⚠️ Gün sonu analizi tamamlanamadı; eski sonuç yeni sonuç gibi "
                                "gösterilmedi. Ayrıntı için bot loglarını kontrol edin."
                            )
                    finally:
                        _scan_job_active.clear()
                        last_post_close_analysis_date = now.date()
                    continue
            except Exception as e:
                logger.error("Gün sonu analizi zamanlayıcısı hata verdi: %s", e, exc_info=True)

            # --- SABAH PRE-LOAD (08:30) ---
            try:
                if now.hour == MORNING_PRELOAD_HOUR and now.minute >= MORNING_PRELOAD_MINUTE and now.minute < MORNING_PRELOAD_MINUTE + 10:
                    if last_preload_date != now.date():
                        morning_preload(deque_manager, pacer)
                        last_preload_date = now.date()
            except Exception as e:
                logger.debug(f"Preload kontrol hatası: {e}")

            # --- AKŞAM BAKIMI (18:10-19:00) ---
            try:
                if now.hour == 18 and now.minute >= 10 and now.minute < 60:
                    if last_maintenance_date != now.date():
                        evening_maintenance(deque_manager, lifecycle_manager)
                        last_maintenance_date = now.date()
            except Exception as e:
                logger.debug(f"Bakım kontrol hatası: {e}")
            
            
            if tarama_penceresi_acik_mi(now):
                if tarama_animi_mi(now, son_taranan_kapanis):
                    # Tarama anı: en son kapanmış mum + 5 dk doldu.
                    kapanis = son_kapanan_mum_ani(now)
                    logger.info(f"TARAMA - {now.strftime('%H:%M:%S')} "
                                f"(mum {kapanis.strftime('%H:%M')}'de kapandı, "
                                f"günün {kapanis.hour - 9}. taraması)")
                    _scan_job_active.set()
                    try:
                        scan_all_stocks(
                            deque_manager, lifecycle_manager, notifier,
                            manuel=False, stocks=ACTIVE_STOCKS, send_alerts=True,
                        )
                    finally:
                        _scan_job_active.clear()
                    son_taranan_kapanis = kapanis
                    deque_manager.save_all()
                    # Tarama sonunda bekleyen aday tamponu kalıcılaştır (Batch 5 / B3):
                    # restart tamponun tamamını kaybetmesin, tarama başına tek yazma.
                    digest_tamponu_kaydet()
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
                if now.time() < post_close_analysis_time:
                    rapor_anina = now.replace(
                        hour=post_close_analysis_time.hour,
                        minute=post_close_analysis_time.minute,
                        second=0, microsecond=0,
                    )
                    sleep_time = min(sleep_time, max(1.0, (rapor_anina - now).total_seconds()))
                # TABAN UYKU (regresyon koruması): tatil/yarım gün gibi "pencere
                # kapalı ama is_bist_open True" durumlarında sleep_time 0'a düşüp
                # ana döngü boş dönüyordu (ölçüm: ~21.500 log satırı/sn; tatil
                # günü ~600 milyon satır). time_until_next_open artık tatili
                # atlıyor; bu taban ikinci güvenlik ağı, hiçbir koşulda 0 sn uyku
                # ile dönülmez (60 sn'de bir uyanıp durumu yeniden değerlendirir).
                sleep_time = max(sleep_time, 60.0)
                logger.info(f"BIST KAPALI - {now.strftime('%Y-%m-%d %H:%M:%S')} - {sleep_time/60:.1f}dk uyku (açılışa {wait_open/3600:.1f}sa)")
                if _bekle_veya_tarama(sleep_time):
                    logger.info("Seans dışı analiz isteği geldi; ana döngü uyandırıldı")
                    continue
                
        except KeyboardInterrupt:
            logger.info("Bot durduruldu (Ctrl+C)")
            break
        except Exception as e:
            daily_stats['errors'] += 1
            logger.error(f"Ana döngü hatası: {e} - 30sn sonra yeniden denenecek", exc_info=True)
            if _live_state.status().get('tarama_suruyor'):
                _analiz_hatasi_kaydi(e, len(ACTIVE_STOCKS), "ana döngü")
            write_heartbeat(force=True)
            time.sleep(30)
            continue
    
    # Güvenli kapanış (SIGTERM/SIGINT)
    logger.info("Bot kapanıyor, son kayıtlar yapılıyor...")
    try:
        if _telegram_listener_ref is not None:
            _telegram_listener_ref.stop()
    except Exception as e:
        logger.warning(f"Komut dinleyicisi kapatılamadı: {e}")
    # Webhook modunda: kapanışta gelen güncellemeler 503 alsın (Telegram tekrar
    # dener; yarım kalan komut yanıtı üretilmez).
    _telegram_update_processor_ref = None
    try:
        if _deque_manager_ref is not None:
            _deque_manager_ref.save_all()
        son_tarama_kaydet()
        # Bekleyen gün içi adaylar kapanışta da kaybolmasın (Batch 5 / B3).
        digest_tamponu_kaydet()
        write_heartbeat(force=True)
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
    setup_logging()
    # HTTP sunucusu main_loop'tan ÖNCE başlar: Render'ın health check'i ilk veri
    # yüklemesi sürerken de yanıt verir. Webhook modunda güncellemeler bu sunucudan
    # gelir; bot komutları kurana kadar /webhook 503 döner (Telegram tekrar dener).
    _health_server_ref = start_render_health_server(
        test_sender=_render_test_sender,
        webhook_handler=_telegram_webhook_isle,
        webhook_secret=TELEGRAM_WEBHOOK_SECRET,
        # Denetim B-4: /health botun canlılığını da raporlasın (heartbeat yaşı).
        health_provider=_saglik_ozeti,
    )
    main_loop()
