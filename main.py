# --- MAIN LOOP ---
# BIST Bot Ana Döngü - İskelet
# Henüz tam değil, adım adım doldurulacak
# Türkçe yorumlar: Neden uyuyor, neden tarıyor?

import os
import sys
import time
import logging
from datetime import datetime
import pytz

from config import ISTANBUL_TZ, ACTIVE_STOCKS, PROFILE, PROFILE_PARAMS, LOCAL_LOG_DIR, LOG_DIR
from data import StockDequeManager, is_bist_open, time_until_next_open, time_until_next_candle_close, resample_all_timeframes, mock_fetch_60d_1h
from patterns import detect_patterns, calculate_atr

# === LOGGING KURULUMU ===
def setup_logging():
    """Log hem console hem dosyaya - Türkçe mesajlar"""
    # Local mi prod mu?
    log_dir = LOG_DIR if os.path.exists("/var/log") and os.access("/var/log", os.W_OK) else LOCAL_LOG_DIR
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
    logger.info(f"Logging kuruldu - dosya: {log_file}")
    return logger

logger = setup_logging()

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
        # Sıfırla
        daily_stats['stocks_scanned'] = 0
        daily_stats['patterns_found'] = 0
        daily_stats['alerts_sent'] = 0
        daily_stats['errors'] = 0
        daily_stats['last_reset'] = today

def scan_all_stocks(deque_manager: StockDequeManager):
    """
    Tüm hisseleri tara - 40-45 dk sürer (rate limit)
    Neden 45-50sn bekleme? Ban yememek için
    """
    logger.info(f"=== TARAMA BAŞLIYOR - {len(ACTIVE_STOCKS)} hisse, profil: {PROFILE} ===")
    
    for idx, stock in enumerate(ACTIVE_STOCKS):
        try:
            reset_daily_if_needed()
            
            logger.info(f"[{idx+1}/{len(ACTIVE_STOCKS)}] {stock} taranıyor...")
            
            # Deque'den DataFrame al
            df_1h = deque_manager.to_dataframe(stock)
            
            if df_1h is None or len(df_1h) < 50:
                logger.warning(f"{stock} için yeterli veri yok ({0 if df_1h is None else len(df_1h)} mum), mock veri ile dolduruluyor (test)")
                # Test için mock - gerçekte burası yfinance/borsapy olacak
                df_1h = mock_fetch_60d_1h(stock, 360)
                deque_manager.append_dataframe(stock, df_1h)
            
            # Tüm timeframe'leri üret
            all_tfs = resample_all_timeframes(df_1h)
            
            # Her timeframe için pattern tespit
            for tf_name, df_tf in all_tfs.items():
                if df_tf is None or len(df_tf) < 20:
                    logger.debug(f"{stock} {tf_name} için yeterli veri yok, atlanıyor")
                    continue
                
                # Pattern tespit - şimdilik iskelet, None döner
                result = detect_patterns(
                    df_1h=all_tfs.get('1h'),
                    df_2h=all_tfs.get('2h'),
                    df_4h=all_tfs.get('4h'),
                    df_1d=all_tfs.get('1d'),
                    stock_name=stock,
                    profile=PROFILE
                )
                
                if result is not None:
                    daily_stats['patterns_found'] += 1
                    logger.info(f"🔍 {stock} {tf_name} - Formasyon bulundu: {result}")
                    # TODO: Telegram gönderimi (en son)
                else:
                    logger.debug(f"{stock} {tf_name} - Formasyon yok (neden? log detayında)")
            
            daily_stats['stocks_scanned'] += 1
            
            # Rate limit - son hisse değilse bekle
            if idx < len(ACTIVE_STOCKS) - 1:
                import random
                from config import RATE_LIMIT_MIN, RATE_LIMIT_MAX
                delay = random.uniform(RATE_LIMIT_MIN, RATE_LIMIT_MAX)
                logger.info(f"{stock} bitti, {delay:.1f}sn bekleniyor...")
                time.sleep(delay)
                
        except Exception as e:
            daily_stats['errors'] += 1
            logger.error(f"{stock} tarama hatası: {e} - devam ediliyor, bot çökmüyor", exc_info=True)
            continue
    
    logger.info(f"=== TARAMA BİTTİ - Günlük: {daily_stats} ===")

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
    
    deque_manager = StockDequeManager()
    
    # İlk yükleme - eğer deque boşsa 60 gün veri çek
    logger.info("İlk yükleme kontrolü...")
    for stock in ACTIVE_STOCKS[:2]:  # Test için sadece 2 hisse
        df = deque_manager.to_dataframe(stock)
        if df is None or len(df) == 0:
            logger.info(f"{stock} için ilk veri çekiliyor (mock - test)")
            df_mock = mock_fetch_60d_1h(stock, 360)
            deque_manager.append_dataframe(stock, df_mock)
            deque_manager.save_to_disk(stock)
    
    while True:
        try:
            now = datetime.now(ISTANBUL_TZ)
            
            if is_bist_open(now):
                logger.info(f"BIST AÇIK - {now.strftime('%H:%M:%S')} - tarama başlıyor")
                
                # Mum kapanışına kadar bekle (5dk sonrası)
                wait_sec = time_until_next_candle_close(now)
                if wait_sec > 60:  # 1dk'dan fazlaysa bekle
                    logger.info(f"Sonraki mum kapanış +5dk'ya kadar {wait_sec/60:.1f}dk bekleniyor")
                    time.sleep(min(wait_sec, 300))  # Max 5dk uyu, sonra tekrar kontrol et
                    continue
                
                # Tara
                scan_all_stocks(deque_manager)
                
                # Tümünü diske kaydet
                deque_manager.save_all()
                
                # Sonraki mum kapanışına kadar uyu
                wait_next = time_until_next_candle_close(datetime.now(ISTANBUL_TZ))
                logger.info(f"Tarama bitti, sonraki mum için {wait_next/60:.1f}dk uyku")
                time.sleep(max(wait_next, 60))
                
            else:
                # BIST kapalı
                wait_open = time_until_next_open(now)
                # 5dk'da bir kontrol et, ama açılışa kadar uyu
                sleep_time = min(wait_open, 300)  # Max 5dk
                logger.info(f"BIST KAPALI - {now.strftime('%Y-%m-%d %H:%M:%S')} - {sleep_time/60:.1f}dk uyku (açılışa {wait_open/3600:.1f}sa)")
                time.sleep(sleep_time)
                
        except KeyboardInterrupt:
            logger.info("Bot durduruldu (Ctrl+C)")
            deque_manager.save_all()
            break
        except Exception as e:
            logger.error(f"Ana döngü hatası: {e} - 30sn sonra yeniden denenecek", exc_info=True)
            time.sleep(30)
            continue

if __name__ == "__main__":
    main_loop()
