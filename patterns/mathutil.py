# --- ORTAK MATEMATİK YARDIMCILARI ---
# Pine: Bölüm 6 (f_clamp ... f_breakout_strength) birebir karşılığı.

import math
from typing import Optional, Tuple


def f_clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def f_smoothstep(edge0: float, edge1: float, value: float) -> float:
    if edge1 == edge0:
        return 1.0 if value >= edge1 else 0.0
    normalized = f_clamp((value - edge0) / (edge1 - edge0), 0.0, 1.0)
    return normalized * normalized * (3.0 - 2.0 * normalized)


def f_inverse_smoothstep(edge0: float, edge1: float, value: float) -> float:
    return 1.0 - f_smoothstep(edge0, edge1, value)


def f_band_quality(value: float, hard_low: float, optimal_low: float,
                   optimal_high: float, hard_high: float) -> float:
    lower_quality = f_smoothstep(hard_low, optimal_low, value)
    upper_quality = f_inverse_smoothstep(optimal_high, hard_high, value)
    return f_clamp(min(lower_quality, upper_quality) * 100.0, 0.0, 100.0)


def f_progress_quality(progress_value: Optional[float]) -> float:
    if progress_value is None or math.isnan(progress_value):
        return 0.0
    return f_clamp(f_smoothstep(0.15, 0.42, progress_value)
                   * f_inverse_smoothstep(0.82, 1.03, progress_value) * 100.0, 0.0, 100.0)


def f_age_quality(age_value: int, target_age: int) -> float:
    ratio = float(max(age_value, 0)) / max(1.0, float(target_age))
    return f_clamp(f_smoothstep(0.42, 1.05, ratio) * 100.0, 0.0, 100.0)


def f_contraction_quality(contraction_value: Optional[float], min_contraction: float) -> float:
    """Pine: f_contraction_quality (minContraction global'den parametreye alındı)."""
    if contraction_value is None or math.isnan(contraction_value):
        return 0.0
    strong_contraction = max(0.52, min_contraction * 2.20)
    below_threshold_score = f_smoothstep(min_contraction * 0.55, min_contraction, contraction_value) * 45.0
    above_threshold_score = 45.0 + f_smoothstep(min_contraction, strong_contraction, contraction_value) * 55.0
    return f_clamp(below_threshold_score if contraction_value < min_contraction else above_threshold_score,
                   0.0, 100.0)


def f_cleanliness_quality(violation_penalty_value: float) -> float:
    return f_clamp(100.0 - f_smoothstep(10.0, 62.0, violation_penalty_value) * 100.0, 0.0, 100.0)


def f_depth_quality(depth: Optional[float]) -> float:
    if depth is None or math.isnan(depth):
        return 0.0
    return f_band_quality(depth, 0.03, 0.16, 0.45, 0.82)


def f_duration_quality(duration_ratio: Optional[float]) -> float:
    if duration_ratio is None or math.isnan(duration_ratio):
        return 0.0
    return f_band_quality(duration_ratio, 0.12, 0.35, 1.55, 3.60)


def f_line_price(x1: int, y1: float, x2: int, y2: float, x: int) -> float:
    """İki noktadan geçen doğrunun x'teki değeri (sınır çizgileri)."""
    if x2 == x1:
        return y2
    return y1 + (y2 - y1) / float(x2 - x1) * float(x - x1)


def f_slope(x1: int, y1: float, x2: int, y2: float) -> float:
    if x2 == x1:
        return 0.0
    return (y2 - y1) / float(x2 - x1)


def f_breakout_strength(open_p: float, high_p: float, low_p: float, close_p: float,
                        volume: float, volume_sma: Optional[float],
                        direction: int, boundary: float, atr_value: float,
                        base_break_atr: float, mintick: float) -> Tuple[float, float, float, float, float, float]:
    """
    Pine: f_breakout_strength — kırılım mum gücü.
    Döner: (strength, bodyScore, closeScore, penetrationScore, expansionScore, volumeScore)
    """
    candle_range = max(high_p - low_p, mintick)
    # GÖREV 1: atr_value None / NaN koruması — crash önleme (matematik değişmeden)
    if atr_value is None or (isinstance(atr_value, float) and math.isnan(atr_value)):
        effective_atr = float(mintick) * 10.0 if mintick else float(mintick)
    else:
        effective_atr = float(atr_value)
    directional_body_ratio = (close_p - open_p) / candle_range if direction == 1 else (open_p - close_p) / candle_range
    close_location = (close_p - low_p) / candle_range if direction == 1 else (high_p - close_p) / candle_range
    penetration_atr = ((close_p - boundary) if direction == 1 else (boundary - close_p)) / max(effective_atr, mintick)
    expansion_atr = candle_range / max(effective_atr, mintick)

    volume_available = (volume is not None and not (volume_sma is None or math.isnan(volume_sma))
                        and volume > 0 and volume_sma > 0)
    volume_ratio = volume / volume_sma if volume_available else 1.0

    body_score = f_smoothstep(0.10, 0.65, directional_body_ratio) * 100.0
    close_score = f_smoothstep(0.56, 0.88, close_location) * 100.0
    penetration_score = f_smoothstep(base_break_atr * 0.75, max(0.24, base_break_atr * 4.0), penetration_atr) * 100.0
    expansion_score = f_smoothstep(0.65, 1.55, expansion_atr) * 100.0
    volume_score = f_smoothstep(0.90, 1.55, volume_ratio) * 100.0 if volume_available else 50.0

    strength = f_clamp(body_score * 0.24 + close_score * 0.28 + penetration_score * 0.25
                       + expansion_score * 0.15 + volume_score * 0.08, 0.0, 100.0)
    return strength, body_score, close_score, penetration_score, expansion_score, volume_score
