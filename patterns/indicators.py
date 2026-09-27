# --- GÖSTERGELER ---
# Pine: ta.atr(14) ve ta.sma(volume, 20) birebir karşılığı.
# Pine ta.atr = RMA(TR, 14): ilk 14 TR'nin SMA'sı ile tohumlanır, sonra
# rma = (prev*(period-1) + tr) / period. Eski ewm(adjust=False) tohumlaması
# TradingView'den sapıyordu (Teşhis Raporu C1) — artık TV usulü.

import numpy as np
import pandas as pd


def true_range(df: pd.DataFrame) -> np.ndarray:
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    close = df["close"].to_numpy(dtype=float)
    tr = np.empty(len(df), dtype=float)
    if len(df) == 0:
        return tr
    tr[0] = high[0] - low[0]  # Pine: önceki close yoksa TR = high - low
    if len(df) > 1:
        pc = close[:-1]
        tr[1:] = np.maximum.reduce([
            high[1:] - low[1:],
            np.abs(high[1:] - pc),
            np.abs(low[1:] - pc),
        ])
    return tr


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder RMA, SMA tohumlu — ta.atr ile aynı seri."""
    tr = true_range(df)
    n = len(tr)
    atr = np.full(n, np.nan)
    if n < period:
        return pd.Series(atr, index=df.index)
    # Tohum: ilk `period` TR'nin SMA'sı
    atr[period - 1] = tr[:period].mean()
    inv = 1.0 / period
    for i in range(period, n):
        atr[i] = atr[i - 1] * (1.0 - inv) + tr[i] * inv
    return pd.Series(atr, index=df.index)


def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    """ta.sma karşılığı."""
    return series.rolling(window=period, min_periods=period).mean()


def volume_sma_series(df: pd.DataFrame, period: int = 20) -> np.ndarray:
    """Hacim SMA'sı (kırılım gücü volume skoru için). Hacim yoksa NaN'lar."""
    if "volume" not in df.columns:
        return np.full(len(df), np.nan)
    vol = pd.to_numeric(df["volume"], errors="coerce").fillna(0.0)
    return calculate_sma(vol, period).to_numpy(dtype=float)
