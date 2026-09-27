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

try:
    from dotenv import load_dotenv
    load_dotenv()  # .env dosyasindan TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID okur
except ImportError:
    pass

from config import ISTANBUL_TZ, ACTIVE_STOCKS, PROFILE, PROFILE_PARAMS, LOCAL_LOG_DIR, LOG_DIR, ALERT_MIN_QUALITY, ALERT_MIN_QUALITY_GLOBAL, ALERT_STATES
from data import StockDequeManager, is_bist_open, time_until_next_open, time_until_next_candle_close, resample_all_timeframes, fetch_yfinance_1h
from patterns import PatternLifecycleManager, ST_BREAK_CANDIDATE, ST_BREAK_CONFIRMED, ST_RETEST_OK, ST_COMPLETED, ST_BREAK_FAILED, ST_COMPRESSING, ST_PREP
from notifier import TelegramNotifier

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

def scan_all_stocks(deque_manager: StockDequeManager, lifecycle_manager: PatternLifecycleManager, notifier: TelegramNotifier):
    """
    Tüm hisseleri tara - 40-45 dk sürer (rate limit)
    - Deque'den veri al
    - Resample 2H/4H/1D
    - Pattern tespit (üçgen/kama/bayrak)
    - Lifecycle update (kırılım takibi)
    - Telegram (cooldown ile)
    """
    logger.info(f"=== TARAMA BAŞLIYOR - {len(ACTIVE_STOCKS)} hisse, profil: {PROFILE} ===")
    
    for idx, stock in enumerate(ACTIVE_STOCKS):
        try:
            reset_daily_if_needed()
            
            logger.info(f"[{idx+1}/{len(ACTIVE_STOCKS)}] {stock} taranıyor...")
            
            # Deque'den mevcut pencere
            df_1h = deque_manager.to_dataframe(stock)
            
            # Taze veri: yeni 1h mumlari deque'ye ekle (maxlen FIFO en eskisini atar).
            # Fetch basarisizsa cache ile devam; ikisi de yoksa hisse ATLANIR.
            # Canli dongude MOCK VERI YOK - sahte veriyle formasyon uretilmez.
            taze = fetch_yfinance_1h(stock)
            if taze is not None:
                deque_manager.append_dataframe(stock, taze)
                df_1h = deque_manager.to_dataframe(stock)
            
            if df_1h is None or len(df_1h) < 50:
                logger.warning(f"{stock}: veri yok (fetch basarisiz + cache bos) - bu tur atlandi")
                continue
            
            # Tüm timeframe'leri üret
            all_tfs = resample_all_timeframes(df_1h)
            
            # Her timeframe için pattern tespit + lifecycle
            for tf_name, df_tf in all_tfs.items():
                if df_tf is None or len(df_tf) < 30:
                    logger.debug(f"{stock} {tf_name} için yeterli veri yok")
                    continue
                
                # Motor adayı kendisi bulur ve kırılım anında dondurur (Pine v0.4.6 akışı)
                snap = lifecycle_manager.scan(stock + "_" + tf_name, df_tf)
                state, break_dir, lifecycle_log = snap.state, snap.break_dir, snap.log
                active = snap.active
                
                if active:
                    q = snap.effective_quality if snap.effective_quality is not None else active.raw_quality
                    daily_stats['patterns_found'] += 1
                    logger.info(f"🔍 {stock} {tf_name} - {active.pattern_type} kalite {q:.0f} state {state} - {snap.log}")
                    
                    # Alert eşiği kontrolü - timeframe'e göre (effective_quality üzerinden)
                    min_q = ALERT_MIN_QUALITY.get(tf_name, ALERT_MIN_QUALITY_GLOBAL)
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
                        }
                        if notifier.send(alert_data):
                            daily_stats['alerts_sent'] += 1
                            logger.info(f"📨 Telegram gönderildi: {stock} {tf_name} {state} kalite {q:.0f}")
                else:
                    # Canlı formasyon yok (terminal state'ler ve kalite kapısı dahil)
                    logger.debug(f"{stock} {tf_name} - Canlı formasyon yok: {snap.log}")
            
            daily_stats['stocks_scanned'] += 1
            
            # Rate limit
            if idx < len(ACTIVE_STOCKS) - 1:
                import random
                from config import RATE_LIMIT_MIN, RATE_LIMIT_MAX
                delay = random.uniform(RATE_LIMIT_MIN, RATE_LIMIT_MAX)
                logger.info(f"{stock} bitti, {delay:.1f}sn bekleniyor...")
                time.sleep(delay)
                
        except Exception as e:
            daily_stats['errors'] += 1
            logger.error(f"{stock} tarama hatası: {e} - devam ediliyor", exc_info=True)
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
    lifecycle_manager = PatternLifecycleManager(profile=PROFILE)
    notifier = TelegramNotifier()
    
    # İlk yükleme: cache'i boş olan hisseler için taze veri çek
    logger.info("İlk yükleme: cache'i boş olan hisseler taze çekiliyor...")
    for stock in ACTIVE_STOCKS:
        df = deque_manager.to_dataframe(stock)
        if df is None or len(df) < 50:
            taze = fetch_yfinance_1h(stock)
            if taze is not None:
                deque_manager.append_dataframe(stock, taze)
                deque_manager.save_to_disk(stock)
                logger.info(f"{stock}: {len(taze)} mum çekildi ve diske kaydedildi")
            else:
                logger.warning(f"{stock}: ilk veri çekilemedi (Yahoo yok + cache boş) - canlıda atlanacak")
    
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
                scan_all_stocks(deque_manager, lifecycle_manager, notifier)
                
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
