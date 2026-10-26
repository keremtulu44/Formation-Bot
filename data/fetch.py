# data/fetch.py — yfinance sağlayıcı hattı (Faz 8).

import pandas as pd
import numpy as np
from collections import deque
from datetime import date, datetime, timedelta, time as dt_time
import logging
import math
import os
import pickle
import tempfile
from typing import Dict, List, Optional, Tuple

from config import (
    ISTANBUL_TZ, BIST_OPEN, BIST_CLOSE, DEQUE_MAXLEN,
    DATA_DIR, SEED_DATA_DIR, MARKET_SUFFIX, yahoo_ticker_for_symbol,
    PROVIDER_SYMBOL_FALLBACK,
    CANDLE_CLOSE_MINUTE, SCAN_DELAY_AFTER_CLOSE_MIN, TARAMA_PENCERE_SONU,
    BIST_TATILLER, BIST_YARIM_GUNLER,
    VERI_YOK_MODU_ESIK_DK, SPLIT_SUREKLILIK_ESIK_PCT, BAR_BOSLUK_ESIK_SAAT,
    GUNLUK_FETCH_PERIOD, GUNLUK_DEQUE_MAXLEN,
    FULL_1H_FETCH_PERIOD, ROUTINE_1H_FETCH_PERIOD, FULL_1H_FETCH_STALE_DAYS,
    ALLOW_TRUSTED_PICKLE_CACHE,
)

import data as _pkg  # geç bağlama (plan §3)

def saglayici_adaylari(stock: str) -> List[str]:
    """Sembolün sağlayıcı adları: önce birincil, sonra varsa yedek.

    Neden: bazı ürünler tek bir sağlayıcı serisiyle güvenilir değil. Özellikle
    `XAUUSD`/`XAGUSD` gibi parite adları: spot seri yoksa vadeli seri (GC=F/SI=F)
    aynı ons fiyatını izler. Sessiz veri boşluğu yerine yedeğe düşülür ve hangi
    serinin kullanıldığı loga yazılır — kullanıcı hangi fiyatı gördüğünü bilir.
    """
    anahtar = str(stock or "").strip().upper()
    birincil = yahoo_ticker_for_symbol(stock)
    yedek = PROVIDER_SYMBOL_FALLBACK.get(anahtar)
    if yedek and yedek != birincil:
        return [birincil, yedek]
    return [birincil]


def fetch_yfinance_1d(stock: str, period: str = GUNLUK_FETCH_PERIOD) -> Optional[pd.DataFrame]:
    """Günlük (1D) OHLCV çeker — DERİN geçmiş (varsayılan 2 yıl, ~500 bar).

    Neden ayrı fonksiyon? 1H deque 360 bar = ~40 iş günü tutar; resample ile 1D
    yapılırsa sadece ~40 bar olur ve 1D formasyon penceresi (20-60 bar) marjinal
    kalır. 1H penceresini büyütmek Pine uyumunu bozabileceği için 1D verisini
    AYRI ve DERİN çekiyoruz. auto_adjust=False: 1H ile aynı gerekçe (ham fiyat).
    """
    try:
        import io
        import contextlib
        import yfinance as yf
        ham = None
        adaylar = saglayici_adaylari(stock)
        for sira, ticker in enumerate(adaylar):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                ham = yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=False)
            if ham is not None and len(ham) > 0:
                if sira:
                    _pkg.logger.info(f"{stock}: birincil seri boştu, yedek seri "
                                f"kullanıldı ({ticker})")
                break
            _pkg.logger.info(f"{stock}: sağlayıcı {ticker} 1d boş döndü")
        if ham is None or len(ham) == 0:
            return None
        df = ham.copy()
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC").tz_convert(ISTANBUL_TZ)
        else:
            df.index = df.index.tz_convert(ISTANBUL_TZ)
        df.columns = [c.lower() for c in df.columns]
        return df[["open", "high", "low", "close", "volume"]]
    except Exception as e:
        _pkg.logger.debug(f"{stock} 1D fetch hatası: {e}")
        return None


def select_yfinance_1h_period(
    cached: Optional[pd.DataFrame],
    now: Optional[datetime] = None,
) -> str:
    """Cache'e göre 1H fetch penceresini seç.

    İlk/boş cache veya 5 günden eski cache tam geçmiş alır. Sağlıklı ve yakın
    cache için son 5 günlük pencere yeterlidir; append_dataframe zaman bazında
    tekilleştirdiği için bu pencereyi güvenle birleştirebiliriz.
    """
    if cached is None or len(cached) < 50:
        return FULL_1H_FETCH_PERIOD

    if now is None:
        now = datetime.now(ISTANBUL_TZ)
    elif now.tzinfo is None:
        now = ISTANBUL_TZ.localize(now)
    else:
        now = now.astimezone(ISTANBUL_TZ)

    latest = pd.Timestamp(cached.index[-1])
    if latest.tzinfo is None:
        latest = ISTANBUL_TZ.localize(latest.to_pydatetime())
    else:
        latest = latest.tz_convert(ISTANBUL_TZ)

    age_days = (now - latest.to_pydatetime()).total_seconds() / 86400.0
    if age_days > FULL_1H_FETCH_STALE_DAYS:
        return FULL_1H_FETCH_PERIOD
    return ROUTINE_1H_FETCH_PERIOD


def yfinance_error_is_retryable(error) -> bool:
    """Sadece geçici ağ/rate-limit hatalarını yeniden denemeye uygun say.

    Yahoo'nun desteklemediği semboller veya 404/no-data sonuçları tekrar denenmez.
    Bu ayrım, geçici hata olmayan hisselere gereksiz istek gönderilmesini önler.
    """
    text = f"{type(error).__name__} {error}".lower()
    permanent_markers = (
        "404", "possibly delisted", "may be delisted", "no data found",
        "no timezone found", "symbol not found", "not found",
    )
    if any(marker in text for marker in permanent_markers):
        return False

    transient_markers = (
        "429", "too many requests", "rate limit", "ratelimit",
        "timeout", "timed out", "connection", "temporarily unavailable",
        "502", "503", "504", "service unavailable", "bad gateway",
        "gateway timeout", "network is unreachable", "remote disconnected",
    )
    return any(marker in text for marker in transient_markers)


def fetch_yfinance_1h(
    stock: str,
    period: str = "60d",
    with_status: bool = False,
):
    """yfinance'den 1h OHLCV çeker; varsayılan olarak DataFrame veya None döner.

    with_status=True iken (DataFrame/None, geçici-hata-mı, hata-açıklaması)
    döndürür; ana tarama bunu kullanarak yalnız geçici hataları bir kez tekrarlar.
    Not: Yahoo bazı sembolleri taşımıyor (örn. KOZAL.IS / KOZAA.IS -> HTTP 404).

    ÖNEMLİ - auto_adjust=False: yfinance'in default'ı auto_adjust=True (v0.2.51+).
    True iken geçmiş OHLC temettü/splite göre YENİDEN AYARLANIR; TradingView/Pine ise
    ham fiyat kullanır. Bu port sırasında parametre düşmüştü -> temettü sonrası tüm
    geçmiş kayar, pivot/sınır/ATR değerleri Pine'dan sapardı. Geri konuldu.
    """
    def result(df, retryable=False, reason=""):
        return (df, retryable, reason) if with_status else df

    try:
        import io
        import contextlib
        import yfinance as yf
        captured = io.StringIO()
        ham = None
        adaylar = saglayici_adaylari(stock)
        for sira, ticker in enumerate(adaylar):
            captured = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(captured):
                ham = yf.Ticker(ticker).history(period=period, interval="1h", auto_adjust=False)
            if ham is not None and not ham.empty:
                if sira:
                    _pkg.logger.info(f"{stock}: birincil seri boştu, yedek seri "
                                f"kullanıldı ({ticker})")
                break
            _pkg.logger.info(f"{stock}: sağlayıcı {ticker} 1h boş döndü")
        if ham is None or ham.empty:
            reason = captured.getvalue().strip() or "Yahoo boş veri döndürdü"
            return result(None, yfinance_error_is_retryable(reason), reason)
        ham = ham.rename(columns=str.lower)
        gerekli = ["open", "high", "low", "close", "volume"]
        if not all(c in ham.columns for c in gerekli):
            return result(None, False, "Gerekli OHLCV sütunları eksik")
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
                # Son çare de düştüyse indeks normalize KALMAZ: dedup bozulur,
                # tamamlanmis_mumlar şaşar. Yutulmasın, iz kalsın (2026-10-26).
                _pkg.logger.warning("Mum indeksi TZ'ye normalize edilemedi; ham kalıyor", exc_info=True)
        return result(ham)
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        return result(None, yfinance_error_is_retryable(exc), reason)


def fetch_last_bar(stock: str) -> Optional[pd.DataFrame]:
    """Sabah pre-load için son 5 günlük 1h veriyi hafifçe çeker (0-latency açılış)."""
    return _pkg.fetch_yfinance_1h(stock, period="5d")


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
    
    open_ = close + np.random.randn(n_bars) * 0.1
    high = np.maximum(open_, close) + np.abs(np.random.randn(n_bars) * 0.2)
    low = np.minimum(open_, close) - np.abs(np.random.randn(n_bars) * 0.2)
    low = np.maximum(low, 0.5)
    volume = np.random.randint(100000, 5000000, n_bars)
    
    df = pd.DataFrame({
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)
    
    return df


