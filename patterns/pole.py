# --- DİREK (POLE) MOTORU ---
# Pine: Bölüm 9 (f_find_pole, f_path_stats, f_local_extreme_break) + Bölüm 6 yardımcıları
# (f_range_between, f_efficiency_between). Eski Python'daki `local_break=False` TODO'su kapandı (Teşhis A4).

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .mathutil import f_clamp


@dataclass
class PoleInfo:
    """Pine: type PoleInfo."""
    valid: bool = False
    direction: int = 0          # 1 yukarı, -1 aşağı
    start_bar: Optional[int] = None
    start_price: Optional[float] = None
    end_bar: Optional[int] = None
    end_price: Optional[float] = None
    duration: int = 0
    magnitude: Optional[float] = None
    efficiency: Optional[float] = None
    quality: float = 0.0


def path_stats(close: List[float], high: List[float], low: List[float],
               start_bar: int, end_bar: int, start_price: float, end_price: float,
               max_sample: int, mintick: float) -> Tuple[float, float, float, float]:
    """Pine: f_path_stats — (netMove, totalPath, efficiency, maximumRange)."""
    duration = max(0, end_bar - start_bar)
    sample_bars = min(duration, max_sample)
    total_path = 0.0
    maximum_range = 0.0
    n = len(close)
    if sample_bars > 0 and end_bar <= n - 1:
        for step in range(sample_bars):
            absolute_bar = end_bar - step
            if absolute_bar >= 1 and absolute_bar < n:
                total_path += abs(close[absolute_bar] - close[absolute_bar - 1])
                maximum_range = max(maximum_range, high[absolute_bar] - low[absolute_bar])
    net_move = abs(end_price - start_price)
    efficiency = f_clamp(net_move / max(max(total_path, net_move), mintick), 0.0, 1.0)
    return net_move, total_path, efficiency, maximum_range


def efficiency_between(close: List[float], start_bar: int, end_bar: int,
                       maximum_bars: int, mintick: float) -> float:
    """Pine: f_efficiency_between."""
    n = len(close)
    bounded_end = min(end_bar, n - 1)
    duration = 0 if start_bar is None or end_bar is None else max(0, bounded_end - start_bar)
    sample_bars = min(duration, maximum_bars)
    total_path = 0.0
    if sample_bars > 0:
        for step in range(sample_bars):
            absolute_bar = bounded_end - step
            if absolute_bar >= 1 and absolute_bar < n:
                total_path += abs(close[absolute_bar] - close[absolute_bar - 1])
    end_offset = max(0, (n - 1) - bounded_end)
    start_offset = max(0, (n - 1) - (bounded_end - sample_bars))
    net_move = abs(close[n - 1 - end_offset] - close[n - 1 - start_offset]) if sample_bars > 0 else 0.0
    return f_clamp(net_move / max(max(total_path, net_move), mintick), 0.0, 1.0)


def range_between(high: List[float], low: List[float], start_bar: int, end_bar: int,
                  maximum_bars: int) -> Tuple[float, float]:
    """Pine: f_range_between — (rangeHigh, rangeLow)."""
    n = len(high)
    bounded_end = min(end_bar, n - 1)
    available_bars = 0 if start_bar is None or end_bar is None else min(max(bounded_end - start_bar, 0), maximum_bars)
    range_high = high[max(0, min(bounded_end, n - 1))]
    range_low = low[max(0, min(bounded_end, n - 1))]
    if available_bars > 0:
        for step in range(available_bars):
            absolute_bar = bounded_end - step
            if 0 <= absolute_bar < n:
                range_high = max(range_high, high[absolute_bar])
                range_low = min(range_low, low[absolute_bar])
    return range_high, range_low


def local_extreme_break(high_side, low_side, start_bar: int, end_price: float,
                        direction: int, reference_tolerance: float,
                        max_pole_bars: int) -> bool:
    """Pine: f_local_extreme_break — direk, start öncesi local ekstremumu kırdı mı?"""
    found_reference = False
    broke = False
    if direction == 1:
        previous_high = None
        for i in range(len(high_side.bars)):
            pivot_bar = high_side.bars[i]
            if start_bar - max_pole_bars * 3 <= pivot_bar < start_bar:
                pivot_price = high_side.prices[i]
                previous_high = pivot_price if previous_high is None else max(previous_high, pivot_price)
                found_reference = True
        broke = found_reference and previous_high is not None and end_price > previous_high + reference_tolerance
    else:
        previous_low = None
        for i in range(len(low_side.bars)):
            pivot_bar = low_side.bars[i]
            if start_bar - max_pole_bars * 3 <= pivot_bar < start_bar:
                pivot_price = low_side.prices[i]
                previous_low = pivot_price if previous_low is None else min(previous_low, pivot_price)
                found_reference = True
        broke = found_reference and previous_low is not None and end_price < previous_low - reference_tolerance
    return broke


def find_pole(close: List[float], high: List[float], low: List[float],
              atr_array: List[float], safe_atr: float,
              high_side, low_side,
              end_bar: int, end_price: float, direction: int,
              min_pole_atr: float, min_pole_efficiency: float, max_pole_bars: int,
              min_pole_quality: float, touch_atr_mult: float,
              max_path_sample: int, max_history_offset: int, mintick: float) -> PoleInfo:
    """Pine: f_find_pole birebir."""
    best = PoleInfo()
    n = len(close)
    history_available = end_bar <= n - 1 and (n - 1) - end_bar <= max_history_offset - max_pole_bars
    source_side = low_side if direction == 1 else high_side
    if len(source_side) == 0 or not history_available:
        return best
    for i in range(len(source_side)):
        start_bar = source_side.bars[i]
        start_price = source_side.prices[i]
        duration = end_bar - start_bar
        if not (start_bar < end_bar and 1 <= duration <= max_pole_bars):
            continue
        magnitude = abs(end_price - start_price)
        _net, _path, efficiency, maximum_range = path_stats(
            close, high, low, start_bar, end_bar, start_price, end_price, max_path_sample, mintick)
        pole_atr = max(atr_array[end_bar] if end_bar < len(atr_array) and not math.isnan(atr_array[end_bar]) else safe_atr,
                       mintick * 10.0)
        atr_units = magnitude / pole_atr
        speed = atr_units / duration if duration > 0 else 0.0
        directional = end_price > start_price if direction == 1 else end_price < start_price
        local_break_tolerance = max(mintick * 2.0, pole_atr * touch_atr_mult)
        local_break = directional and local_extreme_break(
            high_side, low_side, start_bar, end_price, direction, local_break_tolerance, max_pole_bars)
        single_shock = duration <= 1 or maximum_range >= magnitude * 0.72

        magnitude_score = f_clamp(atr_units / max(min_pole_atr, 0.1) * 65.0, 0.0, 100.0)
        efficiency_score = f_clamp((efficiency - 0.30) / 0.70 * 100.0, 0.0, 100.0)
        duration_score = 100.0 if duration >= 2 else 35.0
        speed_score = f_clamp(speed / 0.22 * 100.0, 0.0, 100.0)
        uncapped_quality = f_clamp(
            magnitude_score * 0.30 + efficiency_score * 0.30 + duration_score * 0.16 + speed_score * 0.12
            + (12.0 if local_break else 0.0) - (24.0 if single_shock else 0.0), 0.0, 100.0)
        quality = min(uncapped_quality, 46.0) if single_shock else uncapped_quality
        valid = directional and atr_units >= min_pole_atr and efficiency >= min_pole_efficiency and quality >= min_pole_quality
        outranks = (valid and not best.valid) or (valid == best.valid and quality > best.quality)
        if outranks:
            best.valid = valid
            best.direction = direction
            best.start_bar = start_bar
            best.start_price = start_price
            best.end_bar = end_bar
            best.end_price = end_price
            best.duration = duration
            best.magnitude = magnitude
            best.efficiency = efficiency
            best.quality = quality
    return best
