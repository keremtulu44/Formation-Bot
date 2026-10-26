# data/backfill.py — OHLCV cache temizlik/birleştirme/backfill (Faz 8).

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

from data.replay import (  # noqa: F401
    _istanbul_zaman,
)

def ohlcv_girdi_sorunlari(df) -> List[str]:
    """Sağlayıcıdan gelen OHLCV frame'ini analiz öncesi doğrula (TEK SINIR).

    Doğrulama sınırı append kapısıdır: `append_dataframe` ve
    `append_gunluk_dataframe` geçersiz frame'i deque'ye HİÇ yazmaz; böylece
    formation ve domain motorları ile disk/Supabase kalıcılığı bozuk veriden
    korunur. Kural sözleşmesi:
      - Sıfır hacim mevcut doğrulama sözleşmesinde GEÇERLİDİR; bu kural tek başına
        Yahoo .IS sağlayıcısının ilk-bar davranışını kanıtlamaz.
      - Negatif hacim, NaN/sonlu olmayan herhangi bir alan, imkânsız OHLC
        ilişkisi (high<low, high<max(open,close), low>min(open,close)) ve
        <=0 fiyatlar geçersizdir.
      - Duplicate/sırasız timestamp burada REDDEDİLMEZ: append timestamp bazlı
        tekilleştirir ve sıralar (idempotent birleştirme sözleşmesi korunur).
      - Kapanmamış/gelecek mum burada elemeNMEZ: `tamamlanmis_mumlar` analiz
        katmanında filtreler (çift doğrulama çoğaltması yapılmaz).
    Dönen liste boşsa frame kabul edilir; doluysa sorun tiplerini verir.
    """
    if df is None or len(df) == 0:
        return ["bos_frame"]
    gerekli = ("open", "high", "low", "close", "volume")
    eksik = [sutun for sutun in gerekli if sutun not in getattr(df, "columns", ())]
    if eksik:
        return ["eksik_sutun:" + ",".join(eksik)]
    try:
        farkli_tz = set()
        for raw_timestamp in df.index:
            if not isinstance(raw_timestamp, (str, datetime, np.datetime64, pd.Timestamp)):
                return ["gecersiz_timestamp"]
            parsed_timestamp = pd.Timestamp(raw_timestamp)
            if pd.isna(parsed_timestamp):
                return ["gecersiz_timestamp"]
            farkli_tz.add(parsed_timestamp.tzinfo is not None)
        if len(farkli_tz) > 1:
            return ["karisik_zaman_dilimi"]
    except (TypeError, ValueError, OverflowError, AttributeError):
        return ["gecersiz_timestamp"]
    try:
        o = pd.to_numeric(df["open"], errors="coerce").to_numpy(dtype=float)
        h = pd.to_numeric(df["high"], errors="coerce").to_numpy(dtype=float)
        l = pd.to_numeric(df["low"], errors="coerce").to_numpy(dtype=float)
        c = pd.to_numeric(df["close"], errors="coerce").to_numpy(dtype=float)
        v = pd.to_numeric(df["volume"], errors="coerce").to_numpy(dtype=float)
    except (TypeError, ValueError, AttributeError):
        return ["sayisal_olmayan"]

    sorunlar: List[str] = []
    fiyatlar = (o, h, l, c)
    if any(int(np.isnan(dizi).sum()) for dizi in fiyatlar + (v,)):
        sorunlar.append("nan_deger")
    sonlu = fiyatlar + (v,)
    if any(int(np.isinf(dizi).sum()) for dizi in sonlu):
        sorunlar.append("sonsuza_deger")
    if sorunlar:
        # NaN/Inf ile geometri karşılaştırması güvenilir değil; önce bunlar raporlanır.
        return sorted(sorunlar)
    if int((h < l).sum()):
        sorunlar.append("high_lt_low")
    if int((h < np.maximum(o, c)).sum()):
        sorunlar.append("high_tutarsiz")
    if int((l > np.minimum(o, c)).sum()):
        sorunlar.append("low_tutarsiz")
    if any(int((dizi <= 0).sum()) for dizi in fiyatlar):
        sorunlar.append("gecersiz_fiyat")
    if int((v < 0).sum()):
        sorunlar.append("negatif_hacim")
    return sorted(sorunlar)


def _ohlcv_kayit_sorunlari(candle: dict) -> List[str]:
    """Validate one persisted/provider candle with the same OHLCV contract."""
    if not isinstance(candle, dict):
        return ["bozuk_kayit"]
    if "timestamp" not in candle:
        return ["gecersiz_timestamp"]
    raw_timestamp = candle.get("timestamp")
    if not isinstance(raw_timestamp, (str, datetime, np.datetime64, pd.Timestamp)):
        return ["gecersiz_timestamp"]
    try:
        if pd.isna(pd.Timestamp(raw_timestamp)):
            return ["gecersiz_timestamp"]
        values = [float(candle[key]) for key in ("open", "high", "low", "close", "volume")]
    except (KeyError, TypeError, ValueError, OverflowError):
        return ["eksik_veya_sayisal_olmayan_ohlcv"]
    if not all(math.isfinite(value) for value in values):
        return ["sonlu_olmayan_ohlcv"]
    o, h, l, c, v = values
    sorunlar = []
    if h < l:
        sorunlar.append("high_lt_low")
    if h < max(o, c):
        sorunlar.append("high_tutarsiz")
    if l > min(o, c):
        sorunlar.append("low_tutarsiz")
    if min(o, h, l, c) <= 0:
        sorunlar.append("gecersiz_fiyat")
    if v < 0:
        sorunlar.append("negatif_hacim")
    return sorunlar


def _karisik_timestamp_zaman_dilimi(bars: List[dict]) -> bool:
    """Naive and timezone-aware labels cannot be safely sorted/merged together."""
    aware = set()
    for candle in bars:
        try:
            aware.add(pd.Timestamp(candle["timestamp"]).tzinfo is not None)
        except (KeyError, TypeError, ValueError, OverflowError):
            return True
    return len(aware) > 1


def _temiz_1h_cache_kayitlari(raw):
    """Parse and filter untrusted persisted 1H JSON/pickle/Supabase records."""
    if not isinstance(raw, (list, tuple, deque)):
        return [], 1
    valid, skipped = [], 0
    for value in raw:
        if not isinstance(value, dict):
            skipped += 1
            continue
        timestamp = value.get("timestamp")
        if not isinstance(timestamp, (str, datetime, np.datetime64, pd.Timestamp)):
            skipped += 1
            continue
        try:
            timestamp = pd.Timestamp(timestamp)
            if pd.isna(timestamp):
                raise ValueError("invalid timestamp")
            if timestamp.tzinfo is not None:
                timestamp = timestamp.tz_convert(ISTANBUL_TZ)
            candle = {
                "timestamp": timestamp,
                "open": float(value["open"]),
                "high": float(value["high"]),
                "low": float(value["low"]),
                "close": float(value["close"]),
                "volume": float(value["volume"]),
            }
        except (KeyError, TypeError, ValueError, OverflowError):
            skipped += 1
            continue
        if _ohlcv_kayit_sorunlari(candle):
            skipped += 1
            continue
        valid.append(candle)
    if _karisik_timestamp_zaman_dilimi(valid):
        return [], skipped + len(valid)
    try:
        valid.sort(key=lambda candle: candle["timestamp"])
    except (TypeError, ValueError):
        return [], skipped + len(valid)
    return valid, skipped


def _temiz_1d_cache_kayitlari(raw):
    """Parse daily cache rows, normalize labels to Istanbul, then validate OHLCV."""
    if not isinstance(raw, (list, tuple, deque)):
        return [], 1
    valid, skipped = [], 0
    for value in raw:
        if not isinstance(value, dict):
            skipped += 1
            continue
        raw_timestamp = value.get("timestamp")
        if not isinstance(raw_timestamp, (str, datetime, np.datetime64, pd.Timestamp)):
            skipped += 1
            continue
        try:
            timestamp = pd.Timestamp(raw_timestamp)
            if pd.isna(timestamp):
                raise ValueError("invalid timestamp")
            timestamp = (
                ISTANBUL_TZ.localize(timestamp.to_pydatetime())
                if timestamp.tzinfo is None else timestamp.tz_convert(ISTANBUL_TZ)
            )
            candle = {
                "timestamp": timestamp,
                "open": float(value["open"]),
                "high": float(value["high"]),
                "low": float(value["low"]),
                "close": float(value["close"]),
                "volume": float(value["volume"]),
            }
        except (KeyError, TypeError, ValueError, OverflowError):
            skipped += 1
            continue
        if _ohlcv_kayit_sorunlari(candle):
            skipped += 1
            continue
        valid.append(candle)
    valid.sort(key=lambda candle: candle["timestamp"])
    return valid, skipped


def _cache_barlari_birlestir(remote_bars, local_bars, maxlen, stock, timeframe):
    """Merge valid cache copies, letting the copy with the later tail win revisions.

    Supabase is the tie-breaker when both copies end at the same candle. The
    local copy wins overlapping timestamps only when its latest timestamp is
    newer; this recovers locally persisted candles after a failed remote upsert
    without changing normal Supabase precedence for equally fresh copies.
    """
    remote_bars = list(remote_bars or [])
    local_bars = list(local_bars or [])
    if not remote_bars:
        return local_bars[-maxlen:]
    if not local_bars:
        return remote_bars[-maxlen:]
    if _karisik_timestamp_zaman_dilimi(remote_bars + local_bars):
        _pkg.logger.warning(
            "%s %s Supabase/yerel cache zaman dilimleri uyuşmuyor; "
            "güvenli sıralama yapılamadığı için Supabase kopyası korundu",
            stock, timeframe,
        )
        return remote_bars[-maxlen:]

    try:
        local_latest = max(bar["timestamp"] for bar in local_bars)
        remote_latest = max(bar["timestamp"] for bar in remote_bars)
        local_is_newer = local_latest > remote_latest
    except (KeyError, TypeError, ValueError, OverflowError):
        _pkg.logger.warning(
            "%s %s Supabase/yerel cache zamanları karşılaştırılamadı; "
            "Supabase kopyası korundu",
            stock, timeframe,
        )
        return remote_bars[-maxlen:]

    preferred, secondary = (
        (local_bars, remote_bars) if local_is_newer else (remote_bars, local_bars)
    )
    by_timestamp = {bar["timestamp"]: dict(bar) for bar in preferred}
    for bar in secondary:
        by_timestamp.setdefault(bar["timestamp"], dict(bar))
    try:
        merged = sorted(by_timestamp.values(), key=lambda bar: bar["timestamp"])
    except (KeyError, TypeError, ValueError):
        _pkg.logger.warning(
            "%s %s Supabase/yerel cache birleştirilemedi; Supabase kopyası korundu",
            stock, timeframe,
        )
        return remote_bars[-maxlen:]
    return merged[-maxlen:]


def yuvarlak_orana_yakin_mi(yuzde: float, tolerans: float = 1.0) -> Optional[float]:
    """
    Zıplama yüzdesi bir SPLIT oranına yakın mı? (2:1 -> %50, 3:1 -> %33.3, 5:1 -> %20 ...)

    Neden? Haber şoku da tek barda %15 yapabilir ama split oranları yuvarlaktır.
    Yuvarlak oran = split/bedelsiz (kalıcı, tüm geçmişi etkiler);
    yuvarlak olmayan = tek barlık fiyat şoku (geçici).
    Oranı döner (örn. 2.0), değilse None.
    """
    for oran in (2, 3, 4, 5, 6, 7, 8, 9, 10, 20):
        beklenen = (1 - 1 / oran) * 100  # 2:1 -> %50
        if abs(yuzde - beklenen) <= tolerans:
            return float(oran)
    return None


def sureklilik_sorunlari_bul(dq) -> List[Dict]:
    """
    Deque'daki mumlarda veri bütünlüğü sorunu ara.

    Üç kontrol (config'teki ölçülmüş eşiklerle):
      1) split/bedelsiz: SEANS İÇİ ve NORMAL aralıklı (≈1 saat) iki mumda
         |open[i+1]-close[i]|/close[i] > %10 VE oran yuvarlak (2:1, 3:1, 5:1...).
      2) eksik veri: aynı seans içinde 1.5 saatten fazla boşluk (1 mum atlaması).
      3) fiyat şoku: %10 üstü ama yuvarlak olmayan zıplama (haber/tek olay).

    Neden gerekli? auto_adjust=False (Pine uyumu için) HAM seri verir; split olan
    hissede fiyat aniden yarıya iner ve motor bunu "kırılım" sanıp sahte alarm
    üretir. Gece/hafta sonu boşlukları (15-60 saat) DOĞALDIR, onlar sayılmaz.
    """
    sorunlar: List[Dict] = []
    if dq is None or len(dq) < 3:
        return sorunlar

    onceki = None
    for c in dq:
        ts = _istanbul_zaman(c['timestamp'])
        if onceki is not None:
            onceki_ts, onceki_kapanis, onceki_gun = onceki
            bosluk_saat = (ts - onceki_ts).total_seconds() / 3600.0
            if ts.date() == onceki_gun:  # sadece aynı seans içi
                if bosluk_saat > BAR_BOSLUK_ESIK_SAAT:
                    sorunlar.append({
                        'tip': 'bosluk',
                        'mesaj': (f"SEANS İÇİ EKSİK VERİ: {onceki_ts.strftime('%d %b %H:%M')} ile "
                                  f"{ts.strftime('%H:%M')} arasında {bosluk_saat:.1f} saat boşluk"),
                        'zamandar': ts, 'yuzde': round(bosluk_saat, 2),
                    })
                elif onceki_kapanis > 0:
                    # Zıplama kontrolü SADECE normal aralıkta (boşlukta fiyat
                    # normalde hareket eder, onu split sanmak yanlış pozitiftir)
                    ziplama = abs(c['open'] - onceki_kapanis) / onceki_kapanis * 100.0
                    if ziplama > SPLIT_SUREKLILIK_ESIK_PCT:
                        oran = yuvarlak_orana_yakin_mi(ziplama)
                        if oran:
                            sorunlar.append({
                                'tip': 'split',
                                'mesaj': (f"FİYAT SÜREKLİLİĞİ İHLALİ (SPLIT/BEDELSİZ ~{oran:.0f}:1): "
                                          f"{ts.strftime('%d %b %H:%M')} mumu önceki kapanışa göre "
                                          f"%{ziplama:.1f} zıplamış ({onceki_kapanis:.2f} -> "
                                          f"{c['open']:.2f})"),
                                'zamandar': ts, 'yuzde': round(ziplama, 2), 'oran': oran,
                            })
                        else:
                            sorunlar.append({
                                'tip': 'sok',
                                'mesaj': (f"FİYAT ŞOKU (split değil): {ts.strftime('%d %b %H:%M')} mumu "
                                          f"%{ziplama:.1f} zıplamış ({onceki_kapanis:.2f} -> "
                                          f"{c['open']:.2f}) - tek barlık hareket, oran yuvarlak değil"),
                                'zamandar': ts, 'yuzde': round(ziplama, 2),
                            })
        onceki = (ts, c['close'], ts.date())
    return sorunlar


