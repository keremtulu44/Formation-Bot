# --- ADAY MOTORU ---
# Pine: Bölüm 10-12 f_build_candidate + f_refresh_active_candidate +
#       f_update_active_violation_incremental + freeze/snapshot/effective yardımcıları.
# Teşhis raporundaki A1 (S1 survival taraması), A3 (frozen referanslar) burada birebir çözülür.

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .constants import (f_classic_direction, f_is_flag, f_is_pennant, f_is_specialized)
from .mathutil import (f_age_quality, f_band_quality, f_cleanliness_quality, f_clamp,
                       f_contraction_quality, f_inverse_smoothstep, f_line_price,
                       f_progress_quality, f_slope, f_smoothstep)
from .pole import PoleInfo, range_between
from .violation import (MAX_ACCEPTED_VIOLATION, ViolationCache,
                        boundary_violation_stats_range, violation_penalty_from_stats)


@dataclass
class PatternCandidate:
    """Pine: type PatternCandidate — alan adları eşleşecek şekilde."""
    valid: bool = False
    identity: int = 0
    pattern_type: str = "Yok"
    family: str = "Yok"
    classic_dir: int = 0
    raw_quality: float = 0.0
    selection_score: float = 0.0
    geometry_score: float = 0.0
    geometry_atr: Optional[float] = None
    slope_shape_score: float = 0.0
    touch_score: float = 0.0
    contraction_score: float = 0.0
    maturity_score: float = 0.0
    violation: float = 0.0

    historical_upper_close_violations: int = 0
    historical_lower_close_violations: int = 0
    historical_upper_wick_violations: int = 0
    historical_lower_wick_violations: int = 0
    historical_close_violations: int = 0
    historical_wick_violations: int = 0
    max_historical_violation: float = 0.0
    historical_violation_penalty: float = 0.0
    historical_scanned_bars: int = 0
    violation_history_truncated: bool = False
    last_violation_processed_bar: Optional[int] = None
    violation_geometry_key: str = ""
    violation_scan_mode: str = "Bekliyor"

    upper_touches: int = 0
    lower_touches: int = 0

    start_bar: Optional[int] = None
    end_bar: Optional[int] = None
    known_bar: Optional[int] = None
    apex_bar: Optional[int] = None
    progress: Optional[float] = None

    hb1: Optional[int] = None
    hp1: Optional[float] = None
    hb2: Optional[int] = None
    hp2: Optional[float] = None
    lb1: Optional[int] = None
    lp1: Optional[float] = None
    lb2: Optional[int] = None
    lp2: Optional[float] = None

    upper_slope: Optional[float] = None
    lower_slope: Optional[float] = None
    start_width: Optional[float] = None
    current_width: Optional[float] = None
    contraction: Optional[float] = None
    upper_now: Optional[float] = None
    lower_now: Optional[float] = None

    has_pole: bool = False
    pole_dir: int = 0
    pole_start_bar: Optional[int] = None
    pole_start_price: Optional[float] = None
    pole_end_bar: Optional[int] = None
    pole_end_price: Optional[float] = None
    pole_duration: int = 0
    pole_magnitude: Optional[float] = None
    pole_efficiency: Optional[float] = None
    pole_quality: float = 0.0
    correction_depth: Optional[float] = None
    duration_ratio: Optional[float] = None
    consolidation_efficiency: Optional[float] = None
    consolidation_height_ratio: Optional[float] = None
    # Özel formasyonun Pine varyantı: "Bayrak" | "Flama (standart)" | "Flama (eğik)"
    # (standart = Simetrik Üçgen geometrisi; eğik = Yükselen/Alçalan Üçgen geometrisi)
    specialized_variant: str = ""

    quality_frozen: bool = False
    frozen_raw_quality: Optional[float] = None
    frozen_upper_boundary_at_break: Optional[float] = None
    frozen_lower_boundary_at_break: Optional[float] = None
    frozen_break_buffer: Optional[float] = None
    frozen_retest_tolerance: Optional[float] = None
    frozen_atr_at_break: Optional[float] = None
    frozen_classic_dir: int = 0
    frozen_pattern_type: str = "Yok"
    break_snapshot_bar: Optional[int] = None
    break_snapshot_price: Optional[float] = None
    break_snapshot_direction: int = 0
    break_snapshot_quality: Optional[float] = None
    break_strength: Optional[float] = None
    break_body_score: Optional[float] = None
    break_close_score: Optional[float] = None
    break_penetration_score: Optional[float] = None
    break_expansion_score: Optional[float] = None
    break_volume_score: Optional[float] = None
    break_confirmation_strength: Optional[float] = None


def copy_pole_to_candidate(candidate: PatternCandidate, pole: PoleInfo) -> PatternCandidate:
    """Pine: f_copy_pole_to_candidate."""
    candidate.has_pole = pole.valid
    candidate.pole_dir = pole.direction
    candidate.pole_start_bar = pole.start_bar
    candidate.pole_start_price = pole.start_price
    candidate.pole_end_bar = pole.end_bar
    candidate.pole_end_price = pole.end_price
    candidate.pole_duration = pole.duration
    candidate.pole_magnitude = pole.magnitude
    candidate.pole_efficiency = pole.efficiency
    candidate.pole_quality = pole.quality
    return candidate


def hard_geometry_invalid(candidate: PatternCandidate, geometry_atr: float,
                          parallel_slope_norm_tol: float, flat_slope_norm_tol: float,
                          min_contraction: float, mintick: float) -> bool:
    """Pine: f_hard_geometry_invalid — sınır ihlali DIŞI sert geometri bozulmaları."""
    if not candidate.valid:
        return False
    gatr = max(geometry_atr, mintick * 10.0)
    if f_is_flag(candidate.pattern_type):
        average_slope_norm = ((candidate.upper_slope + candidate.lower_slope) * 0.5) / gatr
        parallel_broken = abs(candidate.upper_slope - candidate.lower_slope) / gatr > parallel_slope_norm_tol * 1.8
        same_direction_too_strong = (average_slope_norm > flat_slope_norm_tol * 0.55 if candidate.pole_dir == 1
                                     else average_slope_norm < -flat_slope_norm_tol * 0.55)
        return bool(candidate.correction_depth is not None and candidate.correction_depth > 0.80
                    or (candidate.duration_ratio is not None and candidate.duration_ratio > 4.0)
                    or (candidate.consolidation_height_ratio is not None and candidate.consolidation_height_ratio > 0.70)
                    or parallel_broken or same_direction_too_strong)
    if f_is_pennant(candidate.pattern_type):
        return bool((candidate.correction_depth is not None and candidate.correction_depth > 0.80)
                    or (candidate.duration_ratio is not None and candidate.duration_ratio > 4.0)
                    or (candidate.progress is not None and candidate.progress > 1.02)
                    or (candidate.current_width is not None and candidate.current_width <= mintick * 3.0)
                    or (candidate.contraction is not None and candidate.contraction < min_contraction * 0.55))
    return bool((candidate.progress is not None and candidate.progress > 1.02)
                or (candidate.current_width is not None and candidate.current_width <= mintick * 3.0)
                or (candidate.contraction is not None and candidate.contraction < min_contraction * 0.55))


def update_active_violation_incremental(engine, candidate: PatternCandidate,
                                        violation_end_bar: int) -> PatternCandidate:
    """Pine: f_update_active_violation_incremental."""
    if not candidate.valid:
        return candidate
    if candidate.quality_frozen:
        candidate.violation_scan_mode = "Dondurulmuş"
        return candidate
    bounded_end = max(candidate.start_bar, min(violation_end_bar, engine.bar_index))
    current_key = f"{candidate.hb1}:{candidate.hb2}:{candidate.lb1}:{candidate.lb2}"
    full_rescan = candidate.violation_geometry_key != current_key or candidate.last_violation_processed_bar is None
    if full_rescan:
        stats = boundary_violation_stats_range(
            candidate.hb1, candidate.hp1, candidate.hb2, candidate.hp2,
            candidate.lb1, candidate.lp1, candidate.lb2, candidate.lp2,
            candidate.start_bar, candidate.start_bar, bounded_end, True, engine.profile,
            engine.close, engine.high, engine.low, engine.atr_array, engine.safe_atr,
            engine.max_violation_scan, engine.max_history_offset, engine.mintick)
        (ucl, lcl, uwk, lwk, mux, mul, pen, bars, trunc) = stats
        candidate.historical_upper_close_violations = ucl
        candidate.historical_lower_close_violations = lcl
        candidate.historical_upper_wick_violations = uwk
        candidate.historical_lower_wick_violations = lwk
        candidate.historical_close_violations = ucl + lcl
        candidate.historical_wick_violations = uwk + lwk
        candidate.max_historical_violation = max(mux, mul)
        candidate.historical_violation_penalty = pen
        candidate.historical_scanned_bars = bars
        candidate.violation_history_truncated = trunc
        candidate.last_violation_processed_bar = bounded_end
        candidate.violation_geometry_key = current_key
        candidate.violation_scan_mode = "Tam"
    elif bounded_end > candidate.last_violation_processed_bar:
        incremental_start = max(candidate.start_bar, candidate.last_violation_processed_bar + 1)
        (ducl, dlcl, duwk, dlwk, dmux, dmul, _dpen, dbars, dtrunc) = boundary_violation_stats_range(
            candidate.hb1, candidate.hp1, candidate.hb2, candidate.hp2,
            candidate.lb1, candidate.lp1, candidate.lb2, candidate.lp2,
            candidate.start_bar, incremental_start, bounded_end, False, engine.profile,
            engine.close, engine.high, engine.low, engine.atr_array, engine.safe_atr,
            engine.max_violation_scan, engine.max_history_offset, engine.mintick)
        candidate.historical_upper_close_violations += ducl
        candidate.historical_lower_close_violations += dlcl
        candidate.historical_upper_wick_violations += duwk
        candidate.historical_lower_wick_violations += dlwk
        candidate.historical_close_violations = (candidate.historical_upper_close_violations
                                                 + candidate.historical_lower_close_violations)
        candidate.historical_wick_violations = (candidate.historical_upper_wick_violations
                                                + candidate.historical_lower_wick_violations)
        candidate.max_historical_violation = max(candidate.max_historical_violation, dmux, dmul)
        candidate.historical_scanned_bars += dbars
        candidate.violation_history_truncated = candidate.violation_history_truncated or dtrunc
        candidate.historical_violation_penalty = violation_penalty_from_stats(
            candidate.historical_close_violations, candidate.historical_wick_violations,
            candidate.max_historical_violation, candidate.violation_history_truncated, engine.profile)
        candidate.last_violation_processed_bar = bounded_end
        candidate.violation_scan_mode = "Artımlı"
    return candidate


def refresh_active_candidate(engine, candidate: PatternCandidate, violation_end_bar: int) -> PatternCandidate:
    """Pine: f_refresh_active_candidate — aktif adayın her-bar hafif güncellemesi."""
    result = candidate
    if not result.valid:
        return result
    b = engine.bar_index
    result.upper_now = f_line_price(result.hb1, result.hp1, result.hb2, result.hp2, b)
    result.lower_now = f_line_price(result.lb1, result.lp1, result.lb2, result.lp2, b)
    if not result.quality_frozen:
        quality_end_bar = max(result.start_bar, min(b, violation_end_bar))
        quality_upper_now = f_line_price(result.hb1, result.hp1, result.hb2, result.hp2, quality_end_bar)
        quality_lower_now = f_line_price(result.lb1, result.lp1, result.lb2, result.lp2, quality_end_bar)
        active_upper_start = f_line_price(result.hb1, result.hp1, result.hb2, result.hp2, result.start_bar)
        active_lower_start = f_line_price(result.lb1, result.lp1, result.lb2, result.lp2, result.start_bar)
        result.start_width = active_upper_start - active_lower_start
        result.current_width = quality_upper_now - quality_lower_now
        result.contraction = ((result.start_width - result.current_width) / result.start_width
                              if result.start_width > engine.mintick else None)
        active_age_for_progress = quality_end_bar - result.start_bar
        if result.apex_bar is not None and result.apex_bar > result.start_bar:
            result.progress = f_clamp(float(active_age_for_progress) / max(1.0, float(result.apex_bar - result.start_bar)), 0.0, 2.0)
        else:
            result.progress = f_clamp(float(active_age_for_progress) / max(1.0, float(engine.max_consolidation_bars)), 0.0, 2.0)
        tol = max(engine.mintick * 2.0, engine.safe_atr * engine.touch_atr_mult)
        active_violation_up = max(0.0, engine.high[b] - result.upper_now) / max(tol, engine.mintick)
        active_violation_down = max(0.0, result.lower_now - engine.low[b]) / max(tol, engine.mintick)
        result.violation = max(active_violation_up, active_violation_down)
        result = update_active_violation_incremental(engine, result, violation_end_bar)

        current_contraction_score = f_contraction_quality(result.contraction, engine.min_contraction)
        current_progress_score = f_progress_quality(result.progress)
        current_maturity_score = f_clamp(
            f_age_quality(quality_end_bar - result.start_bar, engine.min_age) * 0.58
            + current_progress_score * 0.42, 0.0, 100.0)
        current_cleanliness_score = f_cleanliness_quality(result.historical_violation_penalty)
        result.contraction_score = current_contraction_score
        result.maturity_score = current_maturity_score
        result.geometry_score = (result.slope_shape_score if f_is_flag(result.pattern_type)
                                 else f_clamp(result.slope_shape_score * 0.65 + current_contraction_score * 0.35, 0.0, 100.0))

        if f_is_specialized(result.pattern_type):
            obs_high, obs_low = range_between(engine.high, engine.low, result.pole_end_bar, quality_end_bar,
                                              engine.max_path_sample)
            active_consol_low = min(min(result.lp1, result.lp2), obs_low)
            active_consol_high = max(max(result.hp1, result.hp2), obs_high)
            active_height = max(active_consol_high - active_consol_low, engine.mintick)
            pole_mag = max(result.pole_magnitude, engine.mintick)
            result.correction_depth = (f_clamp((result.pole_end_price - active_consol_low) / pole_mag, 0.0, 2.0)
                                       if result.pole_dir == 1
                                       else f_clamp((active_consol_high - result.pole_end_price) / pole_mag, 0.0, 2.0))
            result.duration_ratio = float(max(1, quality_end_bar - result.start_bar)) / max(1.0, float(result.pole_duration))
            result.consolidation_height_ratio = active_height / pole_mag
            result.consolidation_efficiency = engine.efficiency_between(result.start_bar, quality_end_bar)
            depth_quality = engine.depth_quality(result.correction_depth)
            duration_quality = engine.duration_quality(result.duration_ratio)
            calmness_quality = (100.0 if result.consolidation_efficiency <= result.pole_efficiency
                                else f_inverse_smoothstep(0.00, 0.28,
                                                          result.consolidation_efficiency - result.pole_efficiency) * 100.0)
            if f_is_flag(result.pattern_type):
                result.raw_quality = f_clamp(result.pole_quality * 0.28 + depth_quality * 0.20 + duration_quality * 0.12
                                             + result.geometry_score * 0.16 + result.touch_score * 0.12
                                             + calmness_quality * 0.07 + current_cleanliness_score * 0.05, 0.0, 100.0)
            else:
                result.raw_quality = f_clamp(result.pole_quality * 0.26 + depth_quality * 0.18 + duration_quality * 0.12
                                             + result.geometry_score * 0.20 + result.touch_score * 0.10
                                             + calmness_quality * 0.07 + current_cleanliness_score * 0.07, 0.0, 100.0)
        else:
            result.raw_quality = f_clamp(result.geometry_score * 0.38 + result.touch_score * 0.32
                                         + current_maturity_score * 0.18 + current_cleanliness_score * 0.12, 0.0, 100.0)
    else:
        result.violation_scan_mode = "Dondurulmuş"
    return result


def reset_quality_snapshot(candidate: PatternCandidate) -> PatternCandidate:
    """Pine: f_reset_quality_snapshot."""
    candidate.quality_frozen = False
    candidate.frozen_raw_quality = None
    candidate.frozen_upper_boundary_at_break = None
    candidate.frozen_lower_boundary_at_break = None
    candidate.frozen_break_buffer = None
    candidate.frozen_retest_tolerance = None
    candidate.frozen_atr_at_break = None
    candidate.frozen_classic_dir = 0
    candidate.frozen_pattern_type = "Yok"
    candidate.break_snapshot_bar = None
    candidate.break_snapshot_price = None
    candidate.break_snapshot_direction = 0
    candidate.break_snapshot_quality = None
    candidate.break_strength = None
    candidate.break_body_score = None
    candidate.break_close_score = None
    candidate.break_penetration_score = None
    candidate.break_expansion_score = None
    candidate.break_volume_score = None
    candidate.break_confirmation_strength = None
    return candidate


def freeze_pattern_quality(engine, candidate: PatternCandidate) -> PatternCandidate:
    """Pine: f_freeze_pattern_quality — kırılım anında kalite/sınır dondurma."""
    if candidate.valid and not candidate.quality_frozen:
        candidate.quality_frozen = True
        candidate.frozen_raw_quality = candidate.raw_quality
        candidate.frozen_upper_boundary_at_break = candidate.upper_now
        candidate.frozen_lower_boundary_at_break = candidate.lower_now
        candidate.frozen_break_buffer = engine.break_buffer
        candidate.frozen_retest_tolerance = engine.tol
        candidate.frozen_atr_at_break = engine.safe_atr
        candidate.frozen_classic_dir = candidate.classic_dir
        candidate.frozen_pattern_type = candidate.pattern_type
        candidate.break_snapshot_bar = engine.bar_index
        candidate.break_snapshot_direction = engine.break_candidate_dir
        candidate.break_snapshot_price = (candidate.upper_now if engine.break_candidate_dir == 1
                                          else candidate.lower_now)
        candidate.break_snapshot_quality = candidate.raw_quality
        candidate.violation_scan_mode = "Dondurulmuş"
    return candidate


def effective_raw_quality(candidate: PatternCandidate) -> float:
    """Pine: f_effective_raw_quality."""
    if candidate.quality_frozen and candidate.frozen_raw_quality is not None:
        return candidate.frozen_raw_quality
    return candidate.raw_quality


def effective_break_buffer(engine, candidate: PatternCandidate) -> float:
    if candidate.quality_frozen and candidate.frozen_break_buffer is not None:
        return candidate.frozen_break_buffer
    return engine.break_buffer


def effective_retest_tolerance(engine, candidate: PatternCandidate) -> float:
    if candidate.quality_frozen and candidate.frozen_retest_tolerance is not None:
        return candidate.frozen_retest_tolerance
    return engine.tol


def build_candidate(engine, hi_a: int, hi_b: int, lo_a: int, lo_b: int,
                    bull_pole: PoleInfo, bear_pole: PoleInfo) -> PatternCandidate:
    """Pine: f_build_candidate birebir çevirisi (üçgen/kama + bayrak + flama)."""
    b = engine.bar_index
    mintick = engine.mintick
    hp1 = engine.high_side.prices[hi_a]
    hp2 = engine.high_side.prices[hi_b]
    hb1 = engine.high_side.bars[hi_a]
    hb2 = engine.high_side.bars[hi_b]
    hc1 = engine.high_side.confirm_bars[hi_a]
    hc2 = engine.high_side.confirm_bars[hi_b]
    lp1 = engine.low_side.prices[lo_a]
    lp2 = engine.low_side.prices[lo_b]
    lb1 = engine.low_side.bars[lo_a]
    lb2 = engine.low_side.bars[lo_b]
    lc1 = engine.low_side.confirm_bars[lo_a]
    lc2 = engine.low_side.confirm_bars[lo_b]

    chronological = (hb1 < lb1 < hb2 < lb2) or (lb1 < hb1 < lb2 < hb2)
    start_bar = min(min(hb1, hb2), min(lb1, lb2))
    end_bar = max(max(hb1, hb2), max(lb1, lb2))
    known_bar = max(max(hc1, hc2), max(lc1, lc2))
    age = b - start_bar
    candidate_end_bar = end_bar
    formed_duration = max(1, candidate_end_bar - start_bar)

    # Pine: geometryAtr = start ve end barlarındaki ATR ortalaması (Teşhis C2 düzeltildi)
    geometry_start_offset = max(0, min(engine.max_history_offset, b - start_bar))
    geometry_end_offset = max(0, min(engine.max_history_offset, b - candidate_end_bar))
    atr_start = engine.atr_array[b - geometry_start_offset] if b - geometry_start_offset >= 0 else engine.safe_atr
    atr_end = engine.atr_array[b - geometry_end_offset] if b - geometry_end_offset >= 0 else engine.safe_atr
    atr_start = engine.safe_atr if atr_start is None or atr_start != atr_start else atr_start
    atr_end = engine.safe_atr if atr_end is None or atr_end != atr_end else atr_end
    geometry_atr = max((atr_start + atr_end) * 0.5, mintick * 10.0)
    candidate_touch_tolerance = max(mintick * 2.0, geometry_atr * engine.touch_atr_mult)

    upper_start = f_line_price(hb1, hp1, hb2, hp2, start_bar)
    lower_start = f_line_price(lb1, lp1, lb2, lp2, start_bar)
    upper_now = f_line_price(hb1, hp1, hb2, hp2, b)
    lower_now = f_line_price(lb1, lp1, lb2, lp2, b)
    start_width = upper_start - lower_start
    current_width = upper_now - lower_now
    upper_slope = f_slope(hb1, hp1, hb2, hp2)
    lower_slope = f_slope(lb1, lp1, lb2, lp2)
    upper_slope_norm = upper_slope / geometry_atr
    lower_slope_norm = lower_slope / geometry_atr
    slope_gap_norm = upper_slope_norm - lower_slope_norm
    slope_gap = upper_slope - lower_slope
    apex_float = float(start_bar) - start_width / slope_gap if abs(slope_gap) > mintick * 0.0001 else None
    apex_bar = None if apex_float is None else int(round(apex_float))
    contraction = (start_width - current_width) / start_width if start_width > mintick else None
    apex_ok = (apex_bar is not None and apex_bar > b
               and apex_bar <= start_bar + max(engine.min_age * 8, 260))
    if apex_ok:
        progress = f_clamp(float(b - start_bar) / max(1.0, float(apex_bar - start_bar)), 0.0, 2.0)
    else:
        progress = f_clamp(float(age) / max(1.0, float(engine.max_consolidation_bars)), 0.0, 2.0)

    top_above = upper_start > lower_start and upper_now > lower_now
    converging = (start_width > mintick and current_width > mintick and contraction is not None
                  and contraction >= engine.min_contraction and slope_gap_norm < -engine.min_slope_norm_tol)
    parallel_like = abs(slope_gap_norm) <= engine.parallel_slope_norm_tol
    horizontal_upper = abs(upper_slope_norm) <= engine.flat_slope_norm_tol
    horizontal_lower = abs(lower_slope_norm) <= engine.flat_slope_norm_tol
    strict_upper_down = upper_slope_norm < -engine.flat_slope_norm_tol
    strict_upper_up = upper_slope_norm > engine.flat_slope_norm_tol
    strict_lower_up = lower_slope_norm > engine.flat_slope_norm_tol
    strict_lower_down = lower_slope_norm < -engine.flat_slope_norm_tol

    # Temas istatistikleri (Pine: f_touch_stats, endBar = bar_index)
    upper_touches, upper_avg_dist, upper_first, upper_last = engine.touch_stats(
        engine.high_side, hb1, hp1, hb2, hp2, start_bar, b, candidate_touch_tolerance)
    lower_touches, lower_avg_dist, lower_first, lower_last = engine.touch_stats(
        engine.low_side, lb1, lp1, lb2, lp2, start_bar, b, candidate_touch_tolerance)
    total_touches = upper_touches + lower_touches
    touch_distribution = (total_touches >= 4 and upper_first is not None and lower_first is not None
                          and min(upper_last, lower_last) - start_bar >= max(engine.min_age // 2, engine.min_touch_gap * 2))
    touch_basics = (chronological and b >= known_bar and top_above
                    and age >= max(5, engine.min_age // 2)
                    and upper_touches >= 2 and lower_touches >= 2 and touch_distribution)

    violation_up = max(0.0, engine.high[b] - upper_now) / max(candidate_touch_tolerance, mintick)
    violation_down = max(0.0, lower_now - engine.low[b]) / max(candidate_touch_tolerance, mintick)
    current_violation = max(violation_up, violation_down)
    highs_lower = hp2 <= hp1 + candidate_touch_tolerance
    lows_higher = lp2 >= lp1 - candidate_touch_tolerance

    generic_type = "Yok"
    if touch_basics and converging and apex_ok and not parallel_like:
        if horizontal_upper and strict_lower_up and lows_higher:
            generic_type = "Yükselen Üçgen"
        elif horizontal_lower and strict_upper_down and highs_lower:
            generic_type = "Alçalan Üçgen"
        elif strict_upper_down and strict_lower_up:
            generic_type = "Simetrik Üçgen"
        elif strict_upper_up and strict_lower_up and lower_slope_norm > upper_slope_norm + engine.min_slope_norm_tol:
            generic_type = "Yükselen Kama"
        elif strict_upper_down and strict_lower_down and upper_slope_norm < lower_slope_norm - engine.min_slope_norm_tol:
            generic_type = "Alçalan Kama"

    generic_geometry_supported = generic_type != "Yok"
    parallel_geometry_supported = (touch_basics and parallel_like and not converging
                                   and start_width > mintick and current_width > mintick)
    pre_geometry_score = f_clamp(
        (22.0 if chronological else 0.0) + (18.0 if top_above else 0.0)
        + (24.0 if upper_touches >= 2 and lower_touches >= 2 else 0.0)
        + (14.0 if touch_distribution else 0.0)
        + (22.0 if generic_geometry_supported or parallel_geometry_supported else 0.0), 0.0, 100.0)
    violation_scan_eligible = (touch_basics and (generic_geometry_supported or parallel_geometry_supported)
                               and pre_geometry_score >= 55.0)

    historical_upper_close = 0
    historical_lower_close = 0
    historical_upper_wick = 0
    historical_lower_wick = 0
    historical_max_upper = 0.0
    historical_max_lower = 0.0
    historical_violation_penalty = 0.0
    historical_scanned_bars = 0
    violation_history_truncated = False
    violation_scan_end_bar = max(start_bar, candidate_end_bar)
    violation_geometry_key = f"{hb1}:{hb2}:{lb1}:{lb2}"
    max_accepted_violation = MAX_ACCEPTED_VIOLATION.get(engine.profile, 0.72)
    post_pivot_scanned_bars = 0

    if violation_scan_eligible:
        cached = engine.violation_cache.get(violation_geometry_key)
        if cached is not None:
            historical_upper_close = cached["ucl"]
            historical_lower_close = cached["lcl"]
            historical_upper_wick = cached["uwk"]
            historical_lower_wick = cached["lwk"]
            historical_max_upper = cached["mux"]
            historical_max_lower = cached["mul"]
            historical_violation_penalty = cached["penalty"]
            historical_scanned_bars = cached["bars"]
            violation_history_truncated = cached["trunc"]
            last_processed = cached["last"]
            if last_processed is None or last_processed < start_bar or last_processed > violation_scan_end_bar:
                stats = boundary_violation_stats_range(
                    hb1, hp1, hb2, hp2, lb1, lp1, lb2, lp2,
                    start_bar, start_bar, violation_scan_end_bar, True, engine.profile,
                    engine.close, engine.high, engine.low, engine.atr_array, engine.safe_atr,
                    engine.max_violation_scan, engine.max_history_offset, mintick)
                (ucl, lcl, uwk, lwk, mux, mul, pen, bars, trunc) = stats
                historical_upper_close, historical_lower_close = ucl, lcl
                historical_upper_wick, historical_lower_wick = uwk, lwk
                historical_max_upper, historical_max_lower = mux, mul
                historical_violation_penalty = pen
                historical_scanned_bars = bars
                violation_history_truncated = trunc
                engine.violation_cache.set(violation_geometry_key, {
                    "ucl": ucl, "lcl": lcl, "uwk": uwk, "lwk": lwk, "mux": mux, "mul": mul,
                    "penalty": pen, "bars": bars, "trunc": trunc, "last": violation_scan_end_bar})
            elif last_processed < violation_scan_end_bar:
                delta_start = max(start_bar, last_processed + 1)
                (ducl, dlcl, duwk, dlwk, dmux, dmul, _dpen, dbars, dtrunc) = boundary_violation_stats_range(
                    hb1, hp1, hb2, hp2, lb1, lp1, lb2, lp2,
                    start_bar, delta_start, violation_scan_end_bar, False, engine.profile,
                    engine.close, engine.high, engine.low, engine.atr_array, engine.safe_atr,
                    engine.max_violation_scan, engine.max_history_offset, mintick)
                historical_upper_close += ducl
                historical_lower_close += dlcl
                historical_upper_wick += duwk
                historical_lower_wick += dlwk
                historical_max_upper = max(historical_max_upper, dmux)
                historical_max_lower = max(historical_max_lower, dmul)
                historical_scanned_bars += dbars
                violation_history_truncated = violation_history_truncated or dtrunc
                historical_violation_penalty = violation_penalty_from_stats(
                    historical_upper_close + historical_lower_close,
                    historical_upper_wick + historical_lower_wick,
                    max(historical_max_upper, historical_max_lower),
                    violation_history_truncated, engine.profile)
                engine.violation_cache.set(violation_geometry_key, {
                    "ucl": historical_upper_close, "lcl": historical_lower_close,
                    "uwk": historical_upper_wick, "lwk": historical_lower_wick,
                    "mux": historical_max_upper, "mul": historical_max_lower,
                    "penalty": historical_violation_penalty, "bars": historical_scanned_bars,
                    "trunc": violation_history_truncated, "last": violation_scan_end_bar})
        else:
            (ucl, lcl, uwk, lwk, mux, mul, pen, bars, trunc) = boundary_violation_stats_range(
                hb1, hp1, hb2, hp2, lb1, lp1, lb2, lp2,
                start_bar, start_bar, violation_scan_end_bar, True, engine.profile,
                engine.close, engine.high, engine.low, engine.atr_array, engine.safe_atr,
                engine.max_violation_scan, engine.max_history_offset, mintick)
            historical_upper_close, historical_lower_close = ucl, lcl
            historical_upper_wick, historical_lower_wick = uwk, lwk
            historical_max_upper, historical_max_lower = mux, mul
            historical_violation_penalty = pen
            historical_scanned_bars = bars
            violation_history_truncated = trunc
            engine.violation_cache.set(violation_geometry_key, {
                "ucl": ucl, "lcl": lcl, "uwk": uwk, "lwk": lwk, "mux": mux, "mul": mul,
                "penalty": pen, "bars": bars, "trunc": trunc, "last": violation_scan_end_bar})

    historical_close_violations = historical_upper_close + historical_lower_close
    historical_wick_violations = historical_upper_wick + historical_lower_wick
    max_historical_violation = max(historical_max_upper, historical_max_lower)
    historical_geometry_acceptable = (violation_scan_eligible and historical_close_violations < 2
                                      and max_historical_violation <= max_accepted_violation
                                      and historical_violation_penalty < 62.0)

    # S1 — son pivot ile karar barından önceki son kapanmış bar arası yaşam boşluğu taraması.
    # Karar barı taramaya alınmaz; gerçek breakout lifecycle'a kalır. (Teşhis A1'in ilacı)
    survival_start = candidate_end_bar + 1
    survival_end = max(candidate_end_bar, b - 1)
    post_pivot_close_violations = 0
    post_pivot_max_violation = 0.0
    post_pivot_violation_penalty = 0.0
    post_pivot_survival_passed = True
    if historical_geometry_acceptable and survival_end >= survival_start:
        (pucl, plcl, puwk, plwk, pmux, pmul, ppen, pbars, ptrunc) = boundary_violation_stats_range(
            hb1, hp1, hb2, hp2, lb1, lp1, lb2, lp2,
            start_bar, survival_start, survival_end, False, engine.profile,
            engine.close, engine.high, engine.low, engine.atr_array, engine.safe_atr,
            engine.max_violation_scan, engine.max_history_offset, mintick)
        post_pivot_close_violations = pucl + plcl
        post_pivot_max_violation = max(pmux, pmul)
        post_pivot_violation_penalty = ppen
        post_pivot_scanned_bars = pbars
        post_pivot_survival_passed = (post_pivot_close_violations == 0
                                      and post_pivot_max_violation <= max_accepted_violation
                                      and post_pivot_violation_penalty < 62.0)
        historical_upper_close += pucl
        historical_lower_close += plcl
        historical_upper_wick += puwk
        historical_lower_wick += plwk
        historical_close_violations = historical_upper_close + historical_lower_close
        historical_wick_violations = historical_upper_wick + historical_lower_wick
        historical_max_upper = max(historical_max_upper, pmux)
        historical_max_lower = max(historical_max_lower, pmul)
        max_historical_violation = max(historical_max_upper, historical_max_lower)
        historical_scanned_bars += pbars
        violation_history_truncated = violation_history_truncated or ptrunc
        historical_violation_penalty = violation_penalty_from_stats(
            historical_close_violations, historical_wick_violations,
            max_historical_violation, violation_history_truncated, engine.profile)

    historical_geometry_acceptable = (historical_geometry_acceptable and post_pivot_survival_passed
                                      and historical_violation_penalty < 62.0)

    contraction_score = 0.0 if generic_type == "Yok" else f_contraction_quality(contraction, engine.min_contraction)
    upper_flat_quality = f_inverse_smoothstep(engine.flat_slope_norm_tol * 0.55, engine.flat_slope_norm_tol * 1.65,
                                              abs(upper_slope_norm)) * 100.0
    lower_flat_quality = f_inverse_smoothstep(engine.flat_slope_norm_tol * 0.55, engine.flat_slope_norm_tol * 1.65,
                                              abs(lower_slope_norm)) * 100.0
    upper_down_quality = f_smoothstep(engine.flat_slope_norm_tol * 0.70, engine.flat_slope_norm_tol * 4.50, -upper_slope_norm) * 100.0
    upper_up_quality = f_smoothstep(engine.flat_slope_norm_tol * 0.70, engine.flat_slope_norm_tol * 4.50, upper_slope_norm) * 100.0
    lower_up_quality = f_smoothstep(engine.flat_slope_norm_tol * 0.70, engine.flat_slope_norm_tol * 4.50, lower_slope_norm) * 100.0
    lower_down_quality = f_smoothstep(engine.flat_slope_norm_tol * 0.70, engine.flat_slope_norm_tol * 4.50, -lower_slope_norm) * 100.0
    if generic_type == "Yükselen Üçgen":
        slope_shape_quality = upper_flat_quality * 0.52 + lower_up_quality * 0.48
    elif generic_type == "Alçalan Üçgen":
        slope_shape_quality = lower_flat_quality * 0.52 + upper_down_quality * 0.48
    elif generic_type == "Simetrik Üçgen":
        slope_shape_quality = upper_down_quality * 0.50 + lower_up_quality * 0.50
    elif generic_type == "Yükselen Kama":
        slope_shape_quality = (upper_up_quality * 0.42 + lower_up_quality * 0.42
                               + f_smoothstep(engine.min_slope_norm_tol, engine.flat_slope_norm_tol * 2.5,
                                              lower_slope_norm - upper_slope_norm) * 16.0)
    elif generic_type == "Alçalan Kama":
        slope_shape_quality = (upper_down_quality * 0.42 + lower_down_quality * 0.42
                               + f_smoothstep(engine.min_slope_norm_tol, engine.flat_slope_norm_tol * 2.5,
                                              upper_slope_norm - lower_slope_norm) * 16.0)
    else:
        slope_shape_quality = 0.0
    geometry_score = 0.0 if generic_type == "Yok" else f_clamp(slope_shape_quality * 0.65 + contraction_score * 0.35, 0.0, 100.0)

    average_touch_distance = (upper_avg_dist + lower_avg_dist) * 0.5
    touch_precision_quality = f_inverse_smoothstep(0.15, 1.10, average_touch_distance) * 100.0
    touch_count_quality = f_smoothstep(4.0, 7.0, float(total_touches)) * 100.0
    weakest_last_touch = min(upper_last if upper_last is not None else start_bar,
                             lower_last if lower_last is not None else start_bar)
    touch_span_ratio = float(weakest_last_touch - start_bar) / max(1.0, float(age))
    touch_span_quality = f_smoothstep(0.35, 0.78, touch_span_ratio) * 100.0
    touch_score = (f_clamp(touch_precision_quality * 0.42 + touch_count_quality * 0.33 + touch_span_quality * 0.25,
                           0.0, 100.0) if touch_basics else 0.0)
    maturity_score = (0.0 if generic_type == "Yok"
                      else f_clamp(f_age_quality(age, engine.min_age) * 0.58 + f_progress_quality(progress) * 0.42,
                                   0.0, 100.0))
    cleanliness_score = f_cleanliness_quality(historical_violation_penalty)
    generic_raw = (0.0 if generic_type == "Yok" or not historical_geometry_acceptable
                   else f_clamp(geometry_score * 0.38 + touch_score * 0.32 + maturity_score * 0.18
                                + cleanliness_score * 0.12, 0.0, 100.0))

    # --- Pole bağlantısı ve özel (bayrak/flama) geometri ---
    geometry_can_use_pole = (touch_basics and historical_geometry_acceptable
                             and (parallel_like or generic_type in ("Simetrik Üçgen", "Yükselen Üçgen", "Alçalan Üçgen")))
    bull_sequence_compatible = chronological and hb1 < lb1
    bear_sequence_compatible = chronological and lb1 < hb1
    bull_pole_linked = (geometry_can_use_pole and bull_sequence_compatible and bull_pole.valid
                        and abs(bull_pole.end_bar - start_bar) <= engine.max_pole_link_bars)
    bear_pole_linked = (geometry_can_use_pole and bear_sequence_compatible and bear_pole.valid
                        and abs(bear_pole.end_bar - start_bar) <= engine.max_pole_link_bars)

    bull_obs_high, bull_obs_low = max(hp1, hp2), min(lp1, lp2)
    bear_obs_high, bear_obs_low = bull_obs_high, bull_obs_low
    if bull_pole_linked:
        bh, bl = range_between(engine.high, engine.low, bull_pole.end_bar, candidate_end_bar, engine.max_path_sample)
        bull_obs_high, bull_obs_low = bh, bl
    if bear_pole_linked:
        bh, bl = range_between(engine.high, engine.low, bear_pole.end_bar, candidate_end_bar, engine.max_path_sample)
        bear_obs_high, bear_obs_low = bh, bl
    base_consol_low = min(lp1, lp2)
    base_consol_high = max(hp1, hp2)
    bull_consol_low = min(base_consol_low, bull_obs_low)
    bull_consol_high = max(base_consol_high, bull_obs_high)
    bear_consol_low = min(base_consol_low, bear_obs_low)
    bear_consol_high = max(base_consol_high, bear_obs_high)
    base_consol_height = max(base_consol_high - base_consol_low, mintick)
    bull_consol_height = max(bull_consol_high - bull_consol_low, mintick)
    bear_consol_height = max(bear_consol_high - bear_consol_low, mintick)

    center_start = (upper_start + lower_start) * 0.5
    center_end = (f_line_price(hb1, hp1, hb2, hp2, end_bar) + f_line_price(lb1, lp1, lb2, lp2, end_bar)) * 0.5
    pivot_path = abs(hp2 - hp1) + abs(lp2 - lp1) + base_consol_height
    consolidation_efficiency = f_clamp(abs(center_end - center_start) / max(pivot_path, mintick), 0.0, 1.0)

    bull_depth = (f_clamp((bull_pole.end_price - bull_consol_low) / max(bull_pole.magnitude, mintick), 0.0, 2.0)
                  if bull_pole_linked else None)
    bear_depth = (f_clamp((bear_consol_high - bear_pole.end_price) / max(bear_pole.magnitude, mintick), 0.0, 2.0)
                  if bear_pole_linked else None)
    bull_duration_ratio = (float(formed_duration) / max(1.0, float(bull_pole.duration))) if bull_pole_linked else None
    bear_duration_ratio = (float(formed_duration) / max(1.0, float(bear_pole.duration))) if bear_pole_linked else None
    bull_height_ratio = (bull_consol_height / max(bull_pole.magnitude, mintick)) if bull_pole_linked else None
    bear_height_ratio = (bear_consol_height / max(bear_pole.magnitude, mintick)) if bear_pole_linked else None

    average_slope_norm = (upper_slope_norm + lower_slope_norm) * 0.5
    parallel_quality = (f_inverse_smoothstep(engine.parallel_slope_norm_tol * 0.30, engine.parallel_slope_norm_tol * 1.05,
                                             abs(slope_gap_norm)) * 100.0) if parallel_like else 0.0
    bull_flag_slope = average_slope_norm <= engine.flat_slope_norm_tol * 0.35 and average_slope_norm >= -0.16
    bear_flag_slope = average_slope_norm >= -engine.flat_slope_norm_tol * 0.35 and average_slope_norm <= 0.16
    bull_flag_geometry = touch_basics and parallel_like and bull_flag_slope and not converging
    bear_flag_geometry = touch_basics and parallel_like and bear_flag_slope and not converging

    def _flag_valid(linked, geometry, depth, height_ratio, duration_ratio, pole):
        return bool(linked and geometry
                    and depth is not None and 0.08 <= depth <= 0.80
                    and height_ratio is not None and height_ratio <= 0.58
                    and duration_ratio is not None and duration_ratio <= 3.50
                    and formed_duration <= engine.max_consolidation_bars
                    and consolidation_efficiency < pole.efficiency + 0.10)

    bull_flag_valid = _flag_valid(bull_pole_linked, bull_flag_geometry, bull_depth, bull_height_ratio,
                                  bull_duration_ratio, bull_pole)
    bear_flag_valid = _flag_valid(bear_pole_linked, bear_flag_geometry, bear_depth, bear_height_ratio,
                                  bear_duration_ratio, bear_pole)

    def _calmness(linked, pole):
        if not linked:
            return 0.0
        if consolidation_efficiency <= pole.efficiency:
            return 100.0
        return f_inverse_smoothstep(0.00, 0.28, consolidation_efficiency - pole.efficiency) * 100.0

    bull_calmness = _calmness(bull_pole_linked, bull_pole)
    bear_calmness = _calmness(bear_pole_linked, bear_pole)

    def _flag_quality(is_valid, pole, depth, duration_ratio, calmness):
        if not is_valid:
            return 0.0
        return f_clamp(pole.quality * 0.28 + engine.depth_quality(depth) * 0.20
                       + engine.duration_quality(duration_ratio) * 0.12 + parallel_quality * 0.16
                       + touch_score * 0.12 + calmness * 0.07 + cleanliness_score * 0.05, 0.0, 100.0)

    bull_flag_quality = _flag_quality(bull_flag_valid, bull_pole, bull_depth, bull_duration_ratio, bull_calmness)
    bear_flag_quality = _flag_quality(bear_flag_valid, bear_pole, bear_depth, bear_duration_ratio, bear_calmness)

    # Flamalar — Pine'daki dört ayrı tablo koşulu birebir:
    # standard (Simetrik Üçgen): depth 0.06-0.70, height<=0.46, dur<=2.80, eff<pole+0.08, kalite>=minSpecialized
    # inclined (Yükselen/Alçalan Üçgen): pole kalitesi >= min+10, depth 0.08-0.60, height<=0.40, dur<=2.40,
    #   süre <= maxConsolidation*0.85, eff<pole, kalite>=minSpecialized+8
    standard_pennant_geometry = generic_type == "Simetrik Üçgen"
    bull_inclined_pennant_geometry = generic_type == "Yükselen Üçgen"
    bear_inclined_pennant_geometry = generic_type == "Alçalan Üçgen"
    msq = engine.min_specialized_quality
    inclined_max_duration = int(round(engine.max_consolidation_bars * 0.85))

    def _std_base(pole, linked, depth, height_ratio, duration_ratio):
        # Pine: standart flama YALNIZ Simetrik Üçgen geometrisinde kurulur
        return bool(standard_pennant_geometry and linked and depth is not None and 0.06 <= depth <= 0.70
                    and height_ratio is not None and height_ratio <= 0.46
                    and duration_ratio is not None and duration_ratio <= 2.80
                    and formed_duration <= engine.max_consolidation_bars
                    and consolidation_efficiency < pole.efficiency + 0.08)

    def _incl_base(pole, linked, depth, height_ratio, duration_ratio):
        return bool(linked and pole.quality >= engine.min_pole_quality + 10.0
                    and depth is not None and 0.08 <= depth <= 0.60
                    and height_ratio is not None and height_ratio <= 0.40
                    and duration_ratio is not None and duration_ratio <= 2.40
                    and formed_duration <= inclined_max_duration
                    and consolidation_efficiency < pole.efficiency)

    bull_std_base = _std_base(bull_pole, bull_pole_linked, bull_depth, bull_height_ratio, bull_duration_ratio)
    bull_inc_base = (bull_inclined_pennant_geometry
                     and _incl_base(bull_pole, bull_pole_linked, bull_depth, bull_height_ratio, bull_duration_ratio))
    bear_std_base = _std_base(bear_pole, bear_pole_linked, bear_depth, bear_height_ratio, bear_duration_ratio)
    bear_inc_base = (bear_inclined_pennant_geometry
                     and _incl_base(bear_pole, bear_pole_linked, bear_depth, bear_height_ratio, bear_duration_ratio))
    bull_pennant_base = bull_std_base or bull_inc_base
    bear_pennant_base = bear_std_base or bear_inc_base

    def _pennant_quality(base, pole, depth, duration_ratio, calmness):
        if not base:
            return 0.0
        return f_clamp(pole.quality * 0.26 + engine.depth_quality(depth) * 0.18
                       + engine.duration_quality(duration_ratio) * 0.12 + geometry_score * 0.20
                       + touch_score * 0.10 + calmness * 0.07 + cleanliness_score * 0.07, 0.0, 100.0)

    bull_pennant_pre = _pennant_quality(bull_pennant_base, bull_pole, bull_depth, bull_duration_ratio, bull_calmness)
    bear_pennant_pre = _pennant_quality(bear_pennant_base, bear_pole, bear_depth, bear_duration_ratio, bear_calmness)

    bull_pennant_valid = bull_pennant_base and (bull_pennant_pre >= (msq + 8.0 if bull_inc_base and not bull_std_base else msq))
    bear_pennant_valid = bear_pennant_base and (bear_pennant_pre >= (msq + 8.0 if bear_inc_base and not bear_std_base else msq))
    bull_pennant_quality = bull_pennant_pre if bull_pennant_valid else 0.0
    bear_pennant_quality = bear_pennant_pre if bear_pennant_valid else 0.0

    # Seçim: en iyi özel tip generic'in üzerine geçebilir
    selected_type = generic_type
    selected_family = ("Kama" if generic_type in ("Yükselen Kama", "Alçalan Kama")
                       else "Üçgen" if generic_type != "Yok" else "Yok")
    selected_raw = generic_raw
    selected_pole = bull_pole
    selected_depth = None
    selected_duration_ratio = None
    selected_height_ratio = None
    selected_geometry_score = geometry_score
    selected_contraction_score = contraction_score
    selected_slope_shape = slope_shape_quality
    selected_variant = ""

    best_specialized = max(bull_flag_quality, bear_flag_quality, bull_pennant_quality, bear_pennant_quality)
    if best_specialized >= engine.min_specialized_quality:
        if best_specialized == bull_flag_quality:
            selected_type, selected_family, selected_raw = "Boğa Bayrağı", "Bayrak", bull_flag_quality
            selected_pole, selected_depth = bull_pole, bull_depth
            selected_duration_ratio, selected_height_ratio = bull_duration_ratio, bull_height_ratio
            selected_geometry_score, selected_contraction_score = parallel_quality, 0.0
            selected_slope_shape = parallel_quality
            selected_variant = "Bayrak"
        elif best_specialized == bear_flag_quality:
            selected_type, selected_family, selected_raw = "Ayı Bayrağı", "Bayrak", bear_flag_quality
            selected_pole, selected_depth = bear_pole, bear_depth
            selected_duration_ratio, selected_height_ratio = bear_duration_ratio, bear_height_ratio
            selected_geometry_score, selected_contraction_score = parallel_quality, 0.0
            selected_slope_shape = parallel_quality
            selected_variant = "Bayrak"
        elif best_specialized == bull_pennant_quality:
            selected_type, selected_family, selected_raw = "Boğa Flaması", "Flama", bull_pennant_quality
            selected_pole, selected_depth = bull_pole, bull_depth
            selected_duration_ratio, selected_height_ratio = bull_duration_ratio, bull_height_ratio
            selected_variant = ("Flama (eğik)" if (bull_inc_base and not bull_std_base) else "Flama (standart)")
        else:
            selected_type, selected_family, selected_raw = "Ayı Flaması", "Flama", bear_pennant_quality
            selected_pole, selected_depth = bear_pole, bear_depth
            selected_duration_ratio, selected_height_ratio = bear_duration_ratio, bear_height_ratio
            selected_variant = ("Flama (eğik)" if (bear_inc_base and not bear_std_base) else "Flama (standart)")

    accepted = (selected_type != "Yok" and historical_geometry_acceptable and post_pivot_survival_passed
                and selected_raw >= (engine.min_specialized_quality if f_is_specialized(selected_type)
                                     else engine.min_raw_quality))

    candidate = PatternCandidate()
    candidate.valid = accepted
    candidate.pattern_type = selected_type
    candidate.family = selected_family
    candidate.classic_dir = f_classic_direction(selected_type)
    candidate.raw_quality = selected_raw
    candidate.geometry_score = selected_geometry_score
    candidate.geometry_atr = geometry_atr
    candidate.slope_shape_score = (parallel_quality if f_is_flag(selected_type) else selected_slope_shape)
    candidate.touch_score = touch_score
    candidate.contraction_score = selected_contraction_score
    candidate.maturity_score = maturity_score
    candidate.violation = current_violation
    candidate.historical_upper_close_violations = historical_upper_close
    candidate.historical_lower_close_violations = historical_lower_close
    candidate.historical_upper_wick_violations = historical_upper_wick
    candidate.historical_lower_wick_violations = historical_lower_wick
    candidate.historical_close_violations = historical_close_violations
    candidate.historical_wick_violations = historical_wick_violations
    candidate.max_historical_violation = max_historical_violation
    candidate.historical_violation_penalty = historical_violation_penalty
    candidate.historical_scanned_bars = historical_scanned_bars
    candidate.violation_history_truncated = violation_history_truncated
    candidate.last_violation_processed_bar = (max(violation_scan_end_bar, survival_end)
                                              if violation_scan_eligible else None)
    candidate.violation_geometry_key = violation_geometry_key
    candidate.violation_scan_mode = (("Tam+Survival" if post_pivot_scanned_bars > 0 else "Tam")
                                     if violation_scan_eligible else "Atlandı")
    candidate.upper_touches = upper_touches
    candidate.lower_touches = lower_touches
    candidate.start_bar = start_bar
    candidate.end_bar = end_bar
    candidate.known_bar = known_bar
    candidate.apex_bar = apex_bar
    candidate.progress = progress
    candidate.hb1, candidate.hp1, candidate.hb2, candidate.hp2 = hb1, hp1, hb2, hp2
    candidate.lb1, candidate.lp1, candidate.lb2, candidate.lp2 = lb1, lp1, lb2, lp2
    candidate.upper_slope = upper_slope
    candidate.lower_slope = lower_slope
    candidate.start_width = start_width
    candidate.current_width = current_width
    candidate.contraction = contraction
    candidate.upper_now = upper_now
    candidate.lower_now = lower_now
    candidate.correction_depth = selected_depth
    candidate.duration_ratio = selected_duration_ratio
    candidate.consolidation_efficiency = consolidation_efficiency
    candidate.consolidation_height_ratio = selected_height_ratio
    candidate.specialized_variant = selected_variant
    if f_is_specialized(selected_type):
        candidate = copy_pole_to_candidate(candidate, selected_pole)
    return candidate
