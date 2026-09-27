# --- DATA LAYER ---
# BIST veri katmanı - deque, resampling, BIST saat kontrolü
# Türkçe açıklamalar: Her fonksiyon ne yapar, neden?

import pandas as pd
import numpy as np
from collections import deque
from datetime import datetime, timedelta
import pytz
import time
import random
import logging
import os
import pickle
from typing import Dict, List, Optional

from config import (
    ISTANBUL_TZ, BIST_OPEN, BIST_CLOSE, DEQUE_MAXLEN, 
    RATE_LIMIT_MIN, RATE_LIMIT_MAX, DATA_DIR, ACTIVE_STOCKS
)

logger = logging.getLogger(__name__)

# Timeframe -> pandas süre etiketi (tamamlanmis_mumlar filtresi için)
TF_SURELERI = {"1h": "1h", "2h": "2h", "4h": "4h", "1d": "1D"}

# === BIST SAAT KONTROLÜ ===

def is_bist_open(now: Optional[datetime] = None) -> bool:
    """
    BIST açık mı?
    - Hafta içi mi?
    - Saat 09:50-18:10 arası mı? (İstanbul)
    Neden? Bot sadece seans saatlerinde CPU harcasın, dışında uyusun
    """
    if now is None:
        now = datetime.now(ISTANBUL_TZ)
    else:
        # Eğer naive datetime gelirse Istanbul'a çevir
        if now.tzinfo is None:
            now = ISTANBUL_TZ.localize(now)
        else:
            now = now.astimezone(ISTANBUL_TZ)
    
    # Hafta sonu mu?
    if now.weekday() >= 5:  # 5=Cumartesi, 6=Pazar
        return False
    
    # Saat kontrolü
    current_time = now.time()
    return BIST_OPEN <= current_time <= BIST_CLOSE

def time_until_next_open(now: Optional[datetime] = None) -> float:
    """Bir sonraki açılışa kadar kaç saniye? Uyku için"""
    if now is None:
        now = datetime.now(ISTANBUL_TZ)
    if now.tzinfo is None:
        now = ISTANBUL_TZ.localize(now)
    else:
        now = now.astimezone(ISTANBUL_TZ)
    
    # Eğer şu an açıksa 0 dön
    if is_bist_open(now):
        return 0.0
    
    # Sonraki iş gününü bul
    next_day = now
    while True:
        next_day = next_day + timedelta(days=1)
        if next_day.weekday() < 5:  # Hafta içi
            break
    
    # O günün 09:50'si
    next_open = next_day.replace(hour=BIST_OPEN.hour, minute=BIST_OPEN.minute, second=0, microsecond=0)
    # Eğer bugün hafta içi ve saat 09:50'den önce ise, bugün açılacak
    if now.weekday() < 5 and now.time() < BIST_OPEN:
        next_open = now.replace(hour=BIST_OPEN.hour, minute=BIST_OPEN.minute, second=0, microsecond=0)
    
    delta = (next_open - now).total_seconds()
    return max(delta, 0.0)

def time_until_next_candle_close(now: Optional[datetime] = None) -> float:
    """
    Bir sonraki 1H mum kapanışına kadar kaç saniye?
    BIST mumları saat başı kapanır (10:00, 11:00, vs)
    Kapanıştan 5 dk sonra tarama başlatacağız (prompt gereği)
    """
    if now is None:
        now = datetime.now(ISTANBUL_TZ)
    if now.tzinfo is None:
        now = ISTANBUL_TZ.localize(now)
    else:
        now = now.astimezone(ISTANBUL_TZ)
    
    # Bir sonraki saat başı
    next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    # 5 dk ekle (mum kapanışından 5 dk sonra tara)
    next_scan = next_hour + timedelta(minutes=5)
    
    return (next_scan - now).total_seconds()

# === DEQUE YÖNETİMİ ===

class StockDequeManager:
    """
    Her hisse için 360 mumluk deque tutar
    Neden deque? maxlen=360 ile en eski otomatik silinir, rolling window
    Neden kalıcı? Bot restart olursa diskten yükle, 60 gün veriyi tekrar çekme
    """
    def __init__(self, maxlen: int = DEQUE_MAXLEN, data_dir: str = DATA_DIR):
        self.maxlen = maxlen
        self.data_dir = data_dir
        self.deques: Dict[str, deque] = {}
        
        # Data dir oluştur
        os.makedirs(data_dir, exist_ok=True)
        
        logger.info(f"Deque manager başlatıldı - maxlen={maxlen}, dir={data_dir}")
    
    def get_deque(self, stock: str) -> deque:
        """Hisse için deque al, yoksa oluştur"""
        if stock not in self.deques:
            # Diskten yüklemeyi dene
            loaded = self.load_from_disk(stock)
            if loaded is not None:
                self.deques[stock] = loaded
                logger.info(f"{stock} deque diskten yüklendi - {len(loaded)} mum")
            else:
                self.deques[stock] = deque(maxlen=self.maxlen)
                logger.info(f"{stock} için yeni deque oluşturuldu")
        return self.deques[stock]
    
    def append_candle(self, stock: str, candle: dict):
        """
        Yeni mum ekle
        candle: {'open','high','low','close','volume','timestamp'}
        """
        dq = self.get_deque(stock)
        dq.append(candle)
    
    def append_dataframe(self, stock: str, df: pd.DataFrame):
        """DataFrame'den toplu ekle — timestamp bazlı TEKİLLEŞTİRİLMİŞ (idempotent).
        Aynı zamana sahip mum varsa yeni değerler yazılır (taze kazınır),
        pencere taşarsa en eski düşer (maxlen FIFO). Böylece aynı 60d penceresi
        tekrar çekilip eklense bile deque bozulmaz."""
        dq = self.get_deque(stock)
        birlesik: Dict[datetime, dict] = {c['timestamp']: c for c in dq}
        yeni = 0
        guncellenen = 0
        for idx, row in df.iterrows():
            ts = idx if isinstance(idx, datetime) else pd.to_datetime(idx)
            candle = {
                'timestamp': ts,
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': float(row.get('volume', 0))
            }
            if ts in birlesik:
                guncellenen += 1
            else:
                yeni += 1
            birlesik[ts] = candle
        tumu = sorted(birlesik.values(), key=lambda c: c['timestamp'])
        dq.clear()
        for c in tumu[-self.maxlen:]:
            dq.append(c)
        logger.info(f"{stock}: {yeni} yeni / {guncellenen} güncellenen mum (geldi {len(df)}, toplam {len(dq)})")
    
    def to_dataframe(self, stock: str) -> Optional[pd.DataFrame]:
        """Deque'yi DataFrame'e çevir - pattern tespiti için"""
        dq = self.get_deque(stock)  # Diskten yüklemeyi de dene
        if len(dq) == 0:
            return None
        data = list(dq)
        
        # Timestamp'e göre sırala
        data_sorted = sorted(data, key=lambda x: x['timestamp'])
        
        df = pd.DataFrame(data_sorted)
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)
        
        # Sütun sırası
        df = df[['open', 'high', 'low', 'close', 'volume']]
        
        return df
    
    def save_to_disk(self, stock: str):
        """Diske kaydet - hem pickle hem json (senin isteğin both)"""
        if stock not in self.deques:
            return
        
        # Pickle - hızlı
        pkl_path = os.path.join(self.data_dir, f"{stock}.pkl")
        # JSON - GitHub'da görünsün, human-readable
        json_path = os.path.join(self.data_dir, f"{stock}.json")
        
        try:
            data_list = list(self.deques[stock])
            
            # Pickle
            with open(pkl_path, 'wb') as f:
                pickle.dump(data_list, f)
            
            # JSON - timestamp'i string'e çevir
            json_data = []
            for candle in data_list:
                json_candle = candle.copy()
                # Timestamp'i ISO format string yap
                if 'timestamp' in json_candle:
                    ts = json_candle['timestamp']
                    if hasattr(ts, 'isoformat'):
                        json_candle['timestamp'] = ts.isoformat()
                    else:
                        json_candle['timestamp'] = str(ts)
                json_data.append(json_candle)
            
            import json
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"{stock} deque diske kaydedildi - {pkl_path} + {json_path} ({len(data_list)} mum)")
        except Exception as e:
            logger.error(f"{stock} diske kaydedilemedi: {e}")
    
    def load_from_disk(self, stock: str) -> Optional[deque]:
        """Diskten yükle - önce pickle, yoksa json"""
        pkl_path = os.path.join(self.data_dir, f"{stock}.pkl")
        json_path = os.path.join(self.data_dir, f"{stock}.json")
        
        # Önce pickle dene (hızlı)
        if os.path.exists(pkl_path):
            try:
                with open(pkl_path, 'rb') as f:
                    data = pickle.load(f)
                dq = deque(data, maxlen=self.maxlen)
                logger.debug(f"{stock} pickle'dan yüklendi: {len(dq)} mum")
                return dq
            except Exception as e:
                logger.warning(f"{stock} pickle yüklenemedi: {e}, json deneniyor")
        
        # Pickle yoksa json dene
        if os.path.exists(json_path):
            try:
                import json
                from dateutil import parser as date_parser
                with open(json_path, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                
                data_list = []
                for candle in json_data:
                    # Timestamp'i geri çevir
                    if 'timestamp' in candle and isinstance(candle['timestamp'], str):
                        try:
                            candle['timestamp'] = date_parser.parse(candle['timestamp'])
                        except:
                            pass
                    data_list.append(candle)
                
                dq = deque(data_list, maxlen=self.maxlen)
                logger.debug(f"{stock} json'dan yüklendi: {len(dq)} mum")
                return dq
            except Exception as e:
                logger.warning(f"{stock} json'dan yüklenemedi: {e}")
        
        return None
    
    def save_all(self):
        """Tümünü kaydet"""
        for stock in self.deques:
            self.save_to_disk(stock)
        logger.info(f"Tüm deque'ler kaydedildi - {len(self.deques)} hisse")

# === RESAMPLING ===

def resample_ohlcv(df_1h: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """
    1H veriyi 2H, 4H, 1D'ye çevir
    Pine'daki resample mantığı ile aynı
    
    Neden dropna? BIST seans dışı boş mumlar oluşur, onları at
    Neden session gap handling? Gece mumları olmamalı
    
    ÖNEMLİ (B1 fix): 2H/4H kovaları BIST SEANS başına (ilk 1H mumun etiketi, 09:30)
    hizalanır. Neden? Pine'daki request.security(..., "120"/"240") seans başından
    sayar; pandas'in varsayılanı gece yarısıdır. Varsayıanla BIST gününün ilk 1H mumu
    (09:30) TEK BAŞINA bir "2H mumu" oluyor ve sonraki tüm barlar 1 saat kayıyordu
    -> 2H/4H formasyonlar TradingView'dekiyle aynı pivotları üretmiyordu.
    Ölçüm: eskiden 08:00/10:00/12:00... -> şimdi 09:30/11:30/13:30... (TV ile aynı)
    """
    if df_1h is None or len(df_1h) == 0:
        return pd.DataFrame()
    
    # Sütun isimleri küçük harf mi büyük mü kontrol et
    # Bizim deque open/high/low/close küçük, ama yfinance büyük olabilir
    df = df_1h.copy()
    # Normalize et - küçük harfe çevir
    df.columns = [c.lower() for c in df.columns]
    
    # Resample
    # open: first, high: max, low: min, close: last, volume: sum
    agg_dict = {
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }
    
    # Sadece var olan sütunları agg'le
    available_cols = {k: v for k, v in agg_dict.items() if k in df.columns}
    
    try:
        # Kova hizası: günlük için gece yarısı (doğal), 2H/4H için SEANS başı.
        # origin=start_day + offset=<seans başı> -> kovalar 09:30'dan itibaren N saatlik.
        # Seans başını veriden çıkarıyoruz (hard-code 09:30 değil): ilk barın saati.
        offset = None
        if timeframe in ("2h", "4h") and len(df.index) > 0:
            ilk = df.index[0]
            offset = f"{ilk.hour}h{ilk.minute:02d}min"
        
        if offset:
            df_resampled = df.resample(timeframe, offset=offset).agg(available_cols)
        else:
            df_resampled = df.resample(timeframe).agg(available_cols)
        
        # Boşları at - BIST seans dışı
        df_resampled.dropna(inplace=True)
        
        # Eğer hiç veri kalmadıysa
        if len(df_resampled) == 0:
            logger.warning(f"{timeframe} resample sonrası boş - {len(df)} -> 0")
            return pd.DataFrame()
        
        logger.debug(f"Resample {len(df)} 1H -> {len(df_resampled)} {timeframe}")
        return df_resampled
        
    except Exception as e:
        logger.error(f"Resample hatası {timeframe}: {e}")
        return pd.DataFrame()

def tamamlanmis_mumlar(df: pd.DataFrame, tf: str, now: Optional[datetime] = None) -> pd.DataFrame:
    """Devam eden (yarım) mumu çıkarır: kova etiketi + TF süresi > now ise o mum henüz
    kapanmamıştır ve motor verilmemelidir. Yahoo'nun etiket hizalaması ne olursa olsun
    güvenlidir — her mum kapanışından sonraki İLK taramada beslenir (Pine bar kapanışı
    mantığıyla birebir). Resample sol-etiketli olduğu için etiket+TF = kova kapanışıdır."""
    if df is None or len(df) == 0:
        return df
    if now is None:
        now = datetime.now(ISTANBUL_TZ)
    idx = df.index
    if idx.tz is None:
        idx = idx.tz_localize(ISTANBUL_TZ)
    else:
        idx = idx.tz_convert(ISTANBUL_TZ)
    sinir = pd.Timestamp(now).tz_convert(ISTANBUL_TZ) if pd.Timestamp(now).tzinfo else ISTANBUL_TZ.localize(pd.Timestamp(now))
    tamam = (idx + pd.Timedelta(TF_SURELERI.get(tf, "1h"))) <= sinir
    return df[np.asarray(tamam, dtype=bool)]


def resample_all_timeframes(df_1h: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """
    1H'den tüm timeframe'leri üret
    Döner: {'1h': df, '2h': df, '4h': df, '1d': df}
    """
    result = {}
    result['1h'] = df_1h
    
    for tf in ['2h', '4h', '1D']:
        resampled = resample_ohlcv(df_1h, tf)
        # Key'i normalize et: 1D -> 1d
        key = tf.lower()
        result[key] = resampled
    
    return result

# === VERİ ÇEKME (MOCK + GERÇEK İSKELET) ===

def fetch_with_rate_limit(stock: str, fetch_func, *args, **kwargs) -> Optional[pd.DataFrame]:
    """
    Rate limit korumalı veri çekme
    - 45-50 sn bekleme
    - Hata olursa logla, None dön, crash etme
    Neden? tvdatafeed/yfinance ban yemesin, bot çökmesin
    """
    try:
        # Rate limit bekleme
        delay = random.uniform(RATE_LIMIT_MIN, RATE_LIMIT_MAX)
        logger.info(f"{stock} için {delay:.1f}sn bekleniyor (rate limit)")
        time.sleep(delay)
        
        # Veriyi çek
        df = fetch_func(stock, *args, **kwargs)
        
        if df is None or len(df) == 0:
            logger.warning(f"{stock} boş veri döndü, atlanıyor")
            return None
        
        logger.info(f"{stock} için {len(df)} mum çekildi")
        return df
        
    except Exception as e:
        logger.error(f"{stock} veri çekme hatası: {e} - atlanıyor, bot devam ediyor")
        return None

def fetch_yfinance_1h(stock: str, period: str = "60d") -> Optional[pd.DataFrame]:
    """yfinance'den 1h OHLCV çeker (gürültü bastırılmış). Başarısızlıkta None döner.
    Not: Yahoo bazı sembolleri taşımıyor (örn. KOZAL.IS / KOZAA.IS -> HTTP 404)."""
    try:
        import io
        import contextlib
        import yfinance as yf
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            ham = yf.Ticker(stock + ".IS").history(period=period, interval="1h")
        if ham is None or ham.empty:
            return None
        ham = ham.rename(columns=str.lower)
        gerekli = ["open", "high", "low", "close", "volume"]
        if not all(c in ham.columns for c in gerekli):
            return None
        ham = ham[gerekli]
        # Zaman dilimi: deque'daki mumlar Europe/Istanbul tz-aware. yfinance genelde
        # borsa saatini verir ama bazı durumlarda UTC/naive dönebilir - normalize et,
        # yoksa dedup bozulur (aynı mum iki kez eklenir) ve tamamlanmis_mumlar şaşar.
        try:
            if ham.index.tz is None:
                ham.index = ham.index.tz_localize("UTC").tz_convert(ISTANBUL_TZ)
            else:
                ham.index = ham.index.tz_convert(ISTANBUL_TZ)
        except Exception:
            try:
                ham.index = pd.to_datetime(ham.index).tz_localize(ISTANBUL_TZ)
            except Exception:
                pass
        return ham
    except Exception:
        return None


def mock_fetch_60d_1h(stock: str, n_bars: int = 360) -> pd.DataFrame:
    """
    Mock veri çekme - gerçek API yoksa test için
    Gerçek implementasyonda burası yfinance/borsapy olacak
    """
    np.random.seed(hash(stock) % 2**32)
    
    # Son 60 iş günü ~ 360 saat
    end = datetime.now(ISTANBUL_TZ)
    # İş günlerini hesapla - basit: son 60 gün, ama hafta sonu atla
    # Şimdilik sadece hourly freq
    dates = pd.date_range(end=end, periods=n_bars, freq='h')
    
    # Random walk - hisseye göre farklı seed
    base_price = 10 + (hash(stock) % 100)  # Her hisse farklı fiyat
    close = base_price + np.cumsum(np.random.randn(n_bars) * 0.3)
    close = np.maximum(close, 1.0)  # Negatif olmasın
    
    high = close + np.abs(np.random.randn(n_bars) * 0.2)
    low = close - np.abs(np.random.randn(n_bars) * 0.2)
    low = np.maximum(low, 0.5)
    open_ = close + np.random.randn(n_bars) * 0.1
    volume = np.random.randint(100000, 5000000, n_bars)
    
    df = pd.DataFrame({
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)
    
    return df

# === TEST ===

if __name__ == "__main__":
    print("=== Data.py Test ===")
    
    # BIST açık mı?
    print(f"BIST açık mı? {is_bist_open()}")
    print(f"Sonraki açılışa: {time_until_next_open()/3600:.2f} saat")
    print(f"Sonraki mum kapanışına: {time_until_next_candle_close()/60:.1f} dk")
    
    # Deque test
    manager = StockDequeManager(maxlen=10, data_dir="./test_data")
    df_mock = mock_fetch_60d_1h("THYAO", 20)
    print(f"\nMock THYAO: {len(df_mock)} bar")
    print(df_mock.tail(3))
    
    manager.append_dataframe("THYAO", df_mock)
    df_from_deque = manager.to_dataframe("THYAO")
    print(f"\nDeque'den DataFrame: {len(df_from_deque)} bar")
    
    # Resample test
    resampled = resample_all_timeframes(df_from_deque)
    for tf, df in resampled.items():
        print(f"{tf}: {len(df)} bar")
    
    # Temizle
    import shutil
    shutil.rmtree("./test_data", ignore_errors=True)
    print("\nTest bitti")
