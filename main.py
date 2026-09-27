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
from datetime import datetime, timedelta, time as dt_time
import pytz

try:
    from dotenv import load_dotenv
    load_dotenv()  # .env dosyasindan TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID okur
except ImportError:
    pass

from config import (ISTANBUL_TZ, ACTIVE_STOCKS, PROFILE, PROFILE_PARAMS, LOCAL_LOG_DIR, LOG_DIR,
                    ALERT_MIN_QUALITY, ALERT_MIN_QUALITY_GLOBAL, ALERT_STATES, BIST_OPEN,
                    SCAN_DELAY_AFTER_CLOSE_MIN, STALE_BAR_UYARI_DK)
from data import (StockDequeManager, tarama_penceresi_acik_mi, tarama_animi_mi,
                  son_kapanan_mum_ani, time_until_next_open,
                  resample_all_timeframes, fetch_yfinance_1h, tamamlanmis_mumlar)
from patterns import PatternLifecycleManager, ST_BREAK_CANDIDATE, ST_BREAK_CONFIRMED, ST_RETEST_OK, ST_COMPLETED, ST_BREAK_FAILED, ST_COMPRESSING, ST_PREP
from notifier import TelegramNotifier

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
    'stale_stocks': 0,
    'max_bar_age_min': None,
    'data_stale': False,
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
        daily_stats['stale_stocks'] = 0
        daily_stats['max_bar_age_min'] = None
        daily_stats['data_stale'] = False
        daily_stats['last_reset'] = today

# === HEARTBEAT ===
def write_heartbeat(data_dir: str = None):
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
            "stale_stocks": daily_stats['stale_stocks'],
            "max_bar_age_min": daily_stats['max_bar_age_min'],
            "data_stale": daily_stats['data_stale'],
        }
        with open(heartbeat_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Heartbeat yazılamadı: {e}")

def scan_all_stocks(deque_manager: StockDequeManager, lifecycle_manager: PatternLifecycleManager, notifier: TelegramNotifier):
    """
    Tüm hisseleri tara - 40-45 dk sürer (rate limit)
    - Deque'den veri al
    - Resample 2H/4H/1D
    - Pattern tespit (üçgen/kama/bayrak)
    - Lifecycle update (kırılım takibi)
    - Telegram (cooldown ile)
    """
    simdiki_zaman = datetime.now(ISTANBUL_TZ)
    logger.info(f"=== TARAMA BAŞLIYOR - {len(ACTIVE_STOCKS)} hisse, profil: {PROFILE} "
                f"({simdiki_zaman.strftime('%H:%M')}) ===")
    
    for idx, stock in enumerate(ACTIVE_STOCKS):
        if _shutdown_requested:
            logger.info("Kapanış istendi, tarama durduruluyor")
            break
        try:
            reset_daily_if_needed()
            
            logger.info(f"[{idx+1}/{len(ACTIVE_STOCKS)}] {stock} taranıyor...")
            
            # Deque'den mevcut pencere
            df_1h = deque_manager.to_dataframe(stock)
            
            # Taze veri: yeni 1h mumlari deque'ye ekle (maxlen FIFO en eskisini atar).
            # Fetch basarisizsa cache ile devam; ikisi de yoksa hisse ATLANIR.
            # Canli dongude MOCK VERI YOK - sahte veriyle formasyon uretilmez.
            # FAZ 1: fetch basarisizligi ARTIK LOGLANIYOR ve SAYILIYOR. Onceki kodda
            # cache doluysa tek satir log bile yoktu -> "saglikli" gorunen kor bot.
            taze = fetch_yfinance_1h(stock)
            if taze is not None:
                deque_manager.append_dataframe(stock, taze)
                df_1h = deque_manager.to_dataframe(stock)
                daily_stats['fetch_ok'] += 1
            else:
                daily_stats['fetch_failures'] += 1
            
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
            
            # Her hisse sonrası diske kaydet (crash durumunda kayıp azalsın) + heartbeat
            try:
                deque_manager.save_to_disk(stock)
            except Exception as e:
                logger.warning(f"{stock} save_to_disk hatası: {e}")
            write_heartbeat()
            
            # Rate limit
            if idx < len(ACTIVE_STOCKS) - 1:
                from config import RATE_LIMIT_MIN, RATE_LIMIT_MAX
                delay = random.uniform(RATE_LIMIT_MIN, RATE_LIMIT_MAX)
                logger.info(f"{stock} bitti, {delay:.1f}sn bekleniyor...")
                time.sleep(delay)
                
        except Exception as e:
            daily_stats['errors'] += 1
            logger.error(f"{stock} tarama hatası: {e} - devam ediliyor", exc_info=True)
            continue
    
    logger.info(f"=== TARAMA BİTTİ - Günlük: {daily_stats} ===")
    if daily_stats['fetch_failures'] > 0 or daily_stats['data_stale']:
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
    write_heartbeat()

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
    
    global _deque_manager_ref
    deque_manager = StockDequeManager()
    _deque_manager_ref = deque_manager
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
    
    # Aynı mum iki kez taranmasın (drift koruması). Restart'ta None -> bir sonraki
    # kapanışta tazelenir, son mum gerekiyorsa bir kez daha taranır (zararsız).
    son_taranan_kapanis = None
    
    while not _shutdown_requested:
        try:
            now = datetime.now(ISTANBUL_TZ)
            
            if tarama_penceresi_acik_mi(now):
                if tarama_animi_mi(now, son_taranan_kapanis):
                    # Tarama anı: en son kapanmış mum + 5 dk doldu.
                    kapanis = son_kapanan_mum_ani(now)
                    logger.info(f"TARAMA - {now.strftime('%H:%M:%S')} "
                                f"(mum {kapanis.strftime('%H:%M')}'de kapandı, "
                                f"günün {kapanis.hour - 9}. taraması)")
                    scan_all_stocks(deque_manager, lifecycle_manager, notifier)
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
                time.sleep(min(bekle, 300))  # Max 5dk uyu, sonra tekrar kontrol et
                
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
            write_heartbeat()
            time.sleep(30)
            continue
    
    # Güvenli kapanış (SIGTERM/SIGINT)
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
