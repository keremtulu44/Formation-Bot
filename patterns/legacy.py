# --- ESKİ (BATCH) F_BUILD_TRIANGLE_CANDIDATE SHIM ---
# check_4_candidates.py gibi eski diagnostic'ler doğrudan bu imzayı çağırıyor.
# Artık Pine-birebir build_candidate'in üzerine ince bir köprü: verilen pivot listeleriyle
# tek aday kurulur, (candidate, reason) döner.

import math
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .candidate import PatternCandidate, build_candidate
from .lifecycle import ArgentEngine
from .pivots import side_from_legacy
from .pole import find_pole as _find_pole_core


def _prepare_context(df: pd.DataFrame, atr_series: Optional[pd.Series],
                     profile: str, current_bar: Optional[int]) -> ArgentEngine:
    """Eski batch API'ler için motor bağlamı kurar."""
    engine = ArgentEngine(profile=profile)
    engine.open = df["open"].to_numpy(dtype=float).tolist()
    engine.high = df["high"].to_numpy(dtype=float).tolist()
    engine.low = df["low"].to_numpy(dtype=float).tolist()
    engine.close = df["close"].to_numpy(dtype=float).tolist()
    engine.volume = (pd.to_numeric(df["volume"], errors="coerce").fillna(0.0).to_numpy(dtype=float).tolist()
                     if "volume" in df.columns else [0.0] * len(df))
    if atr_series is not None:
        engine.atr_array = atr_series.to_numpy(dtype=float).tolist()
    else:
        engine.atr_array = [engine.safe_atr] * len(df)
    if current_bar is not None:
        engine.bar_index = current_bar
        atr_b = engine.atr_at(current_bar)
        engine.safe_atr = max(atr_b, engine.mintick * 10.0)
        engine.tol = max(engine.mintick * 2.0, engine.safe_atr * engine.touch_atr_mult)
        engine.break_buffer = max(engine.mintick * 2.0, engine.safe_atr * engine.base_break_atr)
    return engine


def find_pole(*args, **kwargs):
    """Dispatch: (df, atr, dict-listeleri, end_bar, end_price, yön, params) -> eski API;
    (close, high, low, atr_array, safe_atr, high_side, low_side, ...) -> motor API."""
    if args and isinstance(args[0], pd.DataFrame):
        return find_pole_legacy(*args, **kwargs)
    return _find_pole_core(*args, **kwargs)


def find_pole_legacy(df: pd.DataFrame, atr_series: pd.Series,
                     high_pivots: List[Dict], low_pivots: List[Dict],
                     end_bar: int, end_price: float, direction: int, params: dict) -> "object":
    """Eski test imzası — aynı profil varsayımıyla motora delege eder."""
    profile = None
    # params içindeki değerlerden profili tahmin etmeye gerek yok; Dengeli varsay
    engine = _prepare_context(df, atr_series, "Dengeli", end_bar)
    engine.high_side = side_from_legacy(high_pivots)
    engine.low_side = side_from_legacy(low_pivots)
    return _find_pole_core(engine.close, engine.high, engine.low, engine.atr_array, engine.safe_atr,
                           engine.high_side, engine.low_side, end_bar, end_price, direction,
                           engine.min_pole_atr, engine.min_pole_efficiency, engine.max_pole_bars,
                           engine.min_pole_quality, engine.touch_atr_mult, engine.max_path_sample,
                           engine.max_history_offset, engine.mintick)


def f_build_triangle_candidate(df: pd.DataFrame, atr_series: pd.Series,
                               high_pivots: List[Dict], low_pivots: List[Dict],
                               hiA: int, hiB: int, loA: int, loB: int,
                               params: dict, profile: str, current_bar: int
                               ) -> Tuple[Optional[PatternCandidate], str]:
    """Eski imza; motor bağlamı elle kurulur."""
    if current_bar >= len(df) or current_bar < 0:
        return None, "Bar index geçersiz"
    engine = _prepare_context(df, atr_series, profile, current_bar)
    engine.high_side = side_from_legacy(high_pivots)
    engine.low_side = side_from_legacy(low_pivots)

    if hiB >= len(engine.high_side) or loB >= len(engine.low_side):
        return None, "Pivot index hatası"

    # Pole'lar: seçilen ikinci pivotları direk ucu kabul et (motorun cache mantığıyla aynı)
    def _pole(end_bar, end_price, direction):
        return _find_pole_core(engine.close, engine.high, engine.low, engine.atr_array, engine.safe_atr,
                               engine.high_side, engine.low_side, end_bar, end_price, direction,
                               engine.min_pole_atr, engine.min_pole_efficiency, engine.max_pole_bars,
                               engine.min_pole_quality, engine.touch_atr_mult, engine.max_path_sample,
                               engine.max_history_offset, engine.mintick)

    bull = _pole(engine.high_side.bars[hiB], engine.high_side.prices[hiB], 1)
    bear = _pole(engine.low_side.bars[loB], engine.low_side.prices[loB], -1)

    cand = build_candidate(engine, hiA, hiB, loA, loB, bull, bear)
    if cand.valid:
        return cand, f"OK - {cand.pattern_type} kalite {cand.raw_quality:.1f}"
    # Red gerekçesi (yaklaşık, eski log stiliyle uyumlu)
    if cand.pattern_type == "Yok":
        return None, ("Geometri uyuşmadı (touchBasics/converging/apex koşulları) "
                      f"contraction={cand.contraction if cand.contraction is None else round(cand.contraction, 3)}")
    if cand.historical_close_violations >= 2 or cand.historical_violation_penalty >= 62.0:
        return None, (f"Tarihsel ihlal fazla: close={cand.historical_close_violations} "
                      f"maxViol={cand.max_historical_violation:.2f} penalty={cand.historical_violation_penalty:.1f}")
    threshold = engine.min_specialized_quality if cand.family in ("Bayrak", "Flama") else engine.min_raw_quality
    if cand.raw_quality < threshold:
        return None, f"Kalite düşük: {cand.raw_quality:.1f} < {threshold}"
    return None, "S1 hayatta kalma taraması geçilemedi (son pivot sonrası sınır delinmiş)"
