# --- MAIN LOOP ---
# BIST Bot Ana Döngü - Canlı için güvenli
# Türkçe yorumlar: Neden uyuyor, neden tarıyor?

import os
import sys
import time
import logging
import random
import signal
import json
from datetime import datetime
import pytz

# .env yükle - local ve systemd için
try:
    from dotenv import load_dotenv
    load_dotenv()
    if os.path.exists("/etc/bist-bot.env"):
        load_dotenv("/etc/bist-bot.env", override=False)
except ImportError:
    pass

from config import ISTANBUL_TZ, ACTIVE_STOCKS, PROFILE, PROFILE_PARAMS, LOCAL_LOG_DIR, LOG_DIR, ALERT_MIN_QUALITY, ALERT_MIN_QUALITY_GLOBAL, ALERT_STATES, DATA_DIR
from data import StockDequeManager, is_bist_open, time_until_next_open, time_until_next_candle_close, resample_all_timeframes, fetch_with_retry, fetch_yfinance_1h
from patterns import calculate_atr, PatternLifecycleManager, find_best_triangle_candidate, find_best_flag_candidate, ST_BREAK_CANDIDATE, ST_BREAK_CONFIRMED, ST_RETEST_OK, ST_COMPLETED, ST_BREAK_FAILED, ST_COMPRESSING, ST_PREP
from notifier import TelegramNotifier

# === LOGGING KURULUMU ===
def setup_logging():
    """Log hem console hem dosyaya - duplicate handler korumalı"""
    # Eğer zaten handler varsa tekrar ekleme (import yan etkisi)
    root_logger = logging.getLogger()
    if root_logger.handlers:
        # Zaten kurulmuş, sadece bizim logger'ı döndür
        logger = logging.getLogger(__name__)
        return logger

    # Local mi prod mu?
    # /var/log/bist-bot yazılabilir mi kontrol et, yoksa LOCAL_LOG_DIR
    log_dir = LOG_DIR
    try:
        os.makedirs(log_dir, exist_ok=True)
        # Yazılabilir mi test et
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

# === GLOBAL STATE FOR SIGNAL HANDLING ===
_shutdown_requested = False
_deque_manager_ref = None

def signal_handler(signum, frame):
    global _shutdown_requested
    logger.info(f"Sinyal alındı: {signum} - güvenli kapanış hazırlanıyor...")
    _shutdown_requested = True
    # Deque'yi kaydetmeye çalış
    if _deque_manager_ref is not None:
        try:
            logger.info("Kapanış öncesi deque'ler kaydediliyor...")
            _deque_manager_ref.save_all()
        except Exception as e:
            logger.error(f"Kapanış kayıt hatası: {e}")

# SIGTERM ve SIGINT için handler kur
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# === GÜNLÜK ÖZET ===
daily_stats = {
    'stocks_scanned': 0,
    'patterns_found': 0,
    'alerts_sent': 0,
    'errors': 0,
    'last_reset': datetime.now(ISTANBUL_TZ).date()
}

def reset_daily_if_needed():
    """Gün değiştiyse günlük sayacı sıfırla"""
    today = datetime.now(ISTANBUL_TZ).date()
    if today != daily_stats['last_reset']:
        logger.info(f"=== GÜNLÜK ÖZET {daily_stats['last_reset']} ===")
        logger.info(f"Taranan hisse: {daily_stats['stocks_scanned']}, Bulunan formasyon: {daily_stats['patterns_found']}, Gönderilen alert: {daily_stats['alerts_sent']}, Hata: {daily_stats['errors']}")
        daily_stats['stocks_scanned'] = 0
        daily_stats['patterns_found'] = 0
        daily_stats['alerts_sent'] = 0
        daily_stats['errors'] = 0
        daily_stats['last_reset'] = today

def write_heartbeat(data_dir: str = DATA_DIR):
    """Botun yaşadığını dışarıdan anlamak için heartbeat dosyası"""
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
        }
        with open(heartbeat_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Heartbeat yazılamadı: {e}")

def scan_all_stocks(deque_manager: StockDequeManager, lifecycle_manager: PatternLifecycleManager, notifier: TelegramNotifier):
    """
    Tüm hisseleri tara - rate limit 45-50sn ile 30 hisse ~25dk sürer
    - Deque'den veri al, yoksa yfinance ile taze çek
    - Resample 2H/4H/1D
    - Pattern tespit (üçgen/kama/bayrak)
    - Lifecycle update (kırılım takibi)
    - Telegram (cooldown ile)
    """
    logger.info(f"=== TARAMA BAŞLIYOR - {len(ACTIVE_STOCKS)} hisse, profil: {PROFILE} ===")
    
    for idx, stock in enumerate(ACTIVE_STOCKS):
        if _shutdown_requested:
            logger.info("Kapanış istendi, tarama durduruluyor")
            break

        try:
            reset_daily_if_needed()
            
            logger.info(f"[{idx+1}/{len(ACTIVE_STOCKS)}] {stock} taranıyor...")
            
            # Deque'den DataFrame al
            df_1h = deque_manager.to_dataframe(stock)
            
            # Yeterli veri yoksa gerçek veriyi çek, mock ASLA kullanma
            if df_1h is None or len(df_1h) < 50:
                logger.warning(f"{stock} için yeterli veri yok ({0 if df_1h is None else len(df_1h)} bar), yfinance ile çekiliyor...")
                # Rate limit beklemeden önce değil, fetch_with_retry kendi içinde retry yapar
                # Ama tarama arası beklemeyi de koruyacağız
                fresh_df = fetch_with_retry(stock, retries=2, base_delay=5.0)
                if fresh_df is not None and len(fresh_df) >= 50:
                    deque_manager.append_dataframe(stock, fresh_df)
                    deque_manager.save_to_disk(stock)
                    df_1h = deque_manager.to_dataframe(stock)
                    logger.info(f"{stock} taze veri ile dolduruldu: {len(df_1h)} bar")
                else:
                    logger.warning(f"{stock} taze veri alınamadı, bu tur atlanıyor (cache: {0 if df_1h is None else len(df_1h)} bar)")
                    # Yetersiz veriyle devam etme, skip
                    if df_1h is None or len(df_1h) < 30:
                        continue
                    # 30-50 arası varsa yine de dene ama kalite düşük olabilir
            
            # Tüm timeframe'leri üret
            all_tfs = resample_all_timeframes(df_1h)
            
            # Her timeframe için pattern tespit + lifecycle
            for tf_name, df_tf in all_tfs.items():
                if df_tf is None or len(df_tf) < 30:
                    logger.debug(f"{stock} {tf_name} için yeterli veri yok")
                    continue
                
                # Candidate bul
                cand_tri, logs_tri = find_best_triangle_candidate(df_tf, profile=PROFILE, verbose=False)
                cand_flag, logs_flag = find_best_flag_candidate(df_tf, profile=PROFILE, verbose=False)
                
                # En iyi candidate - kaliteye göre
                best_cand = None
                if cand_tri and cand_tri.valid:
                    best_cand = cand_tri
                if cand_flag and cand_flag.valid:
                    if best_cand is None or cand_flag.raw_quality > best_cand.raw_quality:
                        best_cand = cand_flag
                
                # Lifecycle update - stock + timeframe için ayrı state
                state, break_dir, lifecycle_log = lifecycle_manager.update(stock + "_" + tf_name, df_tf, best_cand)
                
                if best_cand:
                    daily_stats['patterns_found'] += 1
                    logger.info(f"🔍 {stock} {tf_name} - {best_cand.pattern_type} kalite {best_cand.raw_quality:.0f} state {state} - {lifecycle_log}")
                    
                    # Alert eşiği kontrolü - timeframe'e göre
                    min_q = ALERT_MIN_QUALITY.get(tf_name, ALERT_MIN_QUALITY_GLOBAL)
                    if best_cand.raw_quality < min_q:
                        logger.debug(f"{stock} {tf_name} kalite {best_cand.raw_quality:.0f} < {min_q} (alert eşiği) - telegram atlanıyor")
                    # Sadece önemli state'lerde Telegram gönder
                    # ALERT_STATES içinde zaten SIKISMA_GUCLENIYOR var, redundant listeyi temizledik
                    elif state in ALERT_STATES:
                        alert_data = {
                            'stock_name': stock,
                            'timeframe': tf_name,
                            'pattern_name': best_cand.pattern_type,
                            'state': state,
                            'confidence_score': best_cand.raw_quality,
                            'critical_price_level': best_cand.upper_now if break_dir == 1 else best_cand.lower_now,
                            'upper_now': best_cand.upper_now,
                            'lower_now': best_cand.lower_now,
                            'contraction': getattr(best_cand, 'contraction', None),
                            'timestamp': df_tf.index[-1],
                            'break_dir': break_dir,
                            'break_strength': getattr(best_cand, 'break_strength', best_cand.raw_quality),
                            'break_price': best_cand.upper_now if break_dir == 1 else best_cand.lower_now,
                        }
                        if notifier.send(alert_data):
                            daily_stats['alerts_sent'] += 1
                            logger.info(f"📨 Telegram gönderildi: {stock} {tf_name} {state} kalite {best_cand.raw_quality:.0f}")
                else:
                    # Neden yok? Debug için ilk log
                    if logs_tri and len(logs_tri) > 0:
                        logger.debug(f"{stock} {tf_name} - Formasyon yok: {logs_tri[0]}")
            
            daily_stats['stocks_scanned'] += 1
            
            # Her hisse sonrası diske kaydet (crash durumunda kayıp azalsın)
            try:
                deque_manager.save_to_disk(stock)
            except Exception as e:
                logger.warning(f"{stock} save_to_disk hatası: {e}")

            # Heartbeat güncelle
            write_heartbeat()
            
            # Rate limit - son hisse değilse bekle
            if idx < len(ACTIVE_STOCKS) - 1:
                if _shutdown_requested:
                    break
                delay = random.uniform(45, 50)  # config'den de okunabilir ama sabit tutalım canlı için güvenli
                # config'den okuma dene
                try:
                    from config import RATE_LIMIT_MIN, RATE_LIMIT_MAX
                    delay = random.uniform(RATE_LIMIT_MIN, RATE_LIMIT_MAX)
                except ImportError:
                    pass
                logger.info(f"{stock} bitti, {delay:.1f}sn bekleniyor (rate limit)...")
                # Uyku sırasında shutdown kontrolü için küçük parçalara böl
                slept = 0
                while slept < delay and not _shutdown_requested:
                    chunk = min(5.0, delay - slept)
                    time.sleep(chunk)
                    slept += chunk
                
        except Exception as e:
            daily_stats['errors'] += 1
            logger.error(f"{stock} tarama hatası: {e} - devam ediliyor", exc_info=True)
            continue
    
    logger.info(f"=== TARAMA BİTTİ - Günlük: {daily_stats} ===")
    write_heartbeat()

def main_loop():
    """
    Ana döngü:
    1. BIST açık mı kontrol et
    2. Açıksa -> mum kapanışından 5dk sonra tara
    3. Kapalıysa -> 5dk uyu, tekrar kontrol et
    """
    global _deque_manager_ref

    logger.info("=== BIST FORMASYON BOTU BAŞLATILIYOR ===")
    logger.info(f"Profil: {PROFILE}, Params: {PROFILE_PARAMS}")
    logger.info(f"Hisseler: {ACTIVE_STOCKS[:5]}... (toplam {len(ACTIVE_STOCKS)})")
    
    deque_manager = StockDequeManager()
    _deque_manager_ref = deque_manager
    lifecycle_manager = PatternLifecycleManager(profile=PROFILE)
    notifier = TelegramNotifier()
    
    # İlk yükleme - TÜM hisseler için, mock yok
    logger.info("İlk yükleme kontrolü - tüm hisseler...")
    for stock in ACTIVE_STOCKS:
        if _shutdown_requested:
            break
        try:
            df = deque_manager.to_dataframe(stock)
            if df is None or len(df) < 50:
                logger.info(f"{stock} için ilk veri çekiliyor (yfinance)...")
                fresh = fetch_with_retry(stock, retries=2, base_delay=5.0)
                if fresh is not None and len(fresh) >= 30:
                    deque_manager.append_dataframe(stock, fresh)
                    deque_manager.save_to_disk(stock)
                    logger.info(f"{stock} ilk yükleme tamam: {len(fresh)} bar")
                else:
                    logger.warning(f"{stock} ilk yüklemede veri alınamadı, sonra tekrar denenecek")
                # İlk yüklemede de rate limit
                if stock != ACTIVE_STOCKS[-1]:
                    time.sleep(random.uniform(2, 4))
        except Exception as e:
            logger.error(f"{stock} ilk yükleme hatası: {e}", exc_info=True)
            continue
    
    logger.info("İlk yükleme bitti, ana döngüye geçiliyor")
    write_heartbeat()

    while not _shutdown_requested:
        try:
            now = datetime.now(ISTANBUL_TZ)
            
            if is_bist_open(now):
                logger.info(f"BIST AÇIK - {now.strftime('%H:%M:%S')} - tarama kontrolü")
                
                # Mum kapanışına kadar bekle (5dk sonrası)
                wait_sec = time_until_next_candle_close(now)
                if wait_sec > 60:  # 1dk'dan fazlaysa bekle
                    logger.info(f"Sonraki mum kapanış +5dk'ya kadar {wait_sec/60:.1f}dk bekleniyor")
                    # 5dk parçalı uyku, shutdown kontrolü
                    sleep_target = min(wait_sec, 300)
                    slept = 0
                    while slept < sleep_target and not _shutdown_requested:
                        chunk = min(5.0, sleep_target - slept)
                        time.sleep(chunk)
                        slept += chunk
                    continue
                
                # Tara
                scan_all_stocks(deque_manager, lifecycle_manager, notifier)
                
                # Tümünü diske kaydet
                deque_manager.save_all()
                write_heartbeat()
                
                # Sonraki mum kapanışına kadar uyu
                wait_next = time_until_next_candle_close(datetime.now(ISTANBUL_TZ))
                logger.info(f"Tarama bitti, sonraki mum için {wait_next/60:.1f}dk uyku")
                sleep_target = max(wait_next, 60)
                slept = 0
                while slept < sleep_target and not _shutdown_requested:
                    chunk = min(5.0, sleep_target - slept)
                    time.sleep(chunk)
                    slept += chunk
                
            else:
                # BIST kapalı
                wait_open = time_until_next_open(now)
                sleep_time = min(wait_open, 300)  # Max 5dk
                logger.info(f"BIST KAPALI - {now.strftime('%Y-%m-%d %H:%M:%S')} - {sleep_time/60:.1f}dk uyku (açılışa {wait_open/3600:.1f}sa)")
                slept = 0
                while slept < sleep_time and not _shutdown_requested:
                    chunk = min(5.0, sleep_time - slept)
                    time.sleep(chunk)
                    slept += chunk
                
        except KeyboardInterrupt:
            logger.info("Bot durduruldu (Ctrl+C)")
            break
        except Exception as e:
            logger.error(f"Ana döngü hatası: {e} - 30sn sonra yeniden denenecek", exc_info=True)
            # Hata durumunda da heartbeat yaz
            write_heartbeat()
            slept = 0
            while slept < 30 and not _shutdown_requested:
                time.sleep(1)
                slept += 1
            continue

    # Graceful shutdown
    logger.info("Bot kapanıyor, son kayıtlar yapılıyor...")
    try:
        if _deque_manager_ref is not None:
            _deque_manager_ref.save_all()
        write_heartbeat()
    except Exception as e:
        logger.error(f"Kapanış kayıt hatası: {e}")
    logger.info("Bot durdu")

if __name__ == "__main__":
    main_loop()
