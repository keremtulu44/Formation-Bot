"""Standalone, causal mirror of Stabil support as a resistance line and arrows.

This module has no chart or alert side effects; a separate, source-checked
adapter may use its results when preparing existing graphics. Daily structural
levels reuse the unmodified native support lifecycle on a sign-reflected OHLC
series, then expose only real, positive resistance prices. Bar behavior is
implemented in real-price coordinates and mirrors the existing support rules;
it does not use a future-derived translation or treat a flat stepline as a
user-confirmed visual regime.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from enum import StrEnum
import math
from typing import Any, Sequence

import numpy as np
import pandas as pd

from .candidate_regime import CandidateLineRegime, classify_candidate_support_regimes
from .runtime import StabilRoleStatus, _to_istanbul_timestamp, prepare_causal_ohlcv, project_support_to_bar_closes
from .signals import (
    _GUCLU_YUKARI_COOLDOWN_BAR,
    _GUCLU_YUKARI_COK_GUCLU_GOVDE_ATR,
    _GUCLU_YUKARI_GOVDE_ATR,
    _GUCLU_YUKARI_HACIM_ORAN,
    _GUCLU_YUKARI_KAPANIS_POZ,
    _causal_atr14,
    _causal_vol_ratio20,
    _enum_value,
    _is_index_symbol,
)
from .stabil_support_lifecycle import (
    DailySupportObservation,
    StabilSupportLifecycleSnapshot,
    SupportDynamics,
    SupportLifecycleEvent,
    SupportLifecycleEventType,
    SupportProgression,
    SupportValidity,
    build_daily_support_observations,
    build_support_lifecycle_timeline,
)
from .stabil_trend_engine import StabilTrendConfig


class ResistanceValidity(StrEnum):
    NO_RESISTANCE = "NO_RESISTANCE"
    ACTIVE = "ACTIVE"
    BREACHED = "BREACHED"
    ABOVE_CEILING = "ABOVE_CEILING"


class ResistanceDynamics(StrEnum):
    UNAVAILABLE = "UNAVAILABLE"
    AT_RESISTANCE = "AT_RESISTANCE"
    EXPANDING = "EXPANDING"
    CONTRACTING = "CONTRACTING"
    FLAT = "FLAT"
    ABOVE_RESISTANCE = "ABOVE_RESISTANCE"


class ResistanceProgression(StrEnum):
    NONE = "NONE"
    INITIAL = "INITIAL"
    SAME = "SAME"
    REBASED_HIGHER = "REBASED_HIGHER"
    REBASED_LOWER = "REBASED_LOWER"


class ResistanceEventType(StrEnum):
    RESISTANCE_CONFIRMED = "RESISTANCE_CONFIRMED"
    RESISTANCE_TESTED = "RESISTANCE_TESTED"
    RESISTANCE_HELD = "RESISTANCE_HELD"
    RESISTANCE_BREACHED = "RESISTANCE_BREACHED"
    RESISTANCE_CEILING_BROKEN = "RESISTANCE_CEILING_BROKEN"
    RESISTANCE_RETURNED_BELOW = "RESISTANCE_RETURNED_BELOW"
    RESISTANCE_LOST = "RESISTANCE_LOST"
    RESISTANCE_REBASED_HIGHER = "RESISTANCE_REBASED_HIGHER"
    RESISTANCE_REBASED_LOWER = "RESISTANCE_REBASED_LOWER"


class ResistanceRegime(StrEnum):
    """Native-based candidates, NOT user-validated visual line states."""

    UNAVAILABLE = "UNAVAILABLE"
    STEPPING_DOWN = "STEPPING_DOWN"
    STEPPING_UP = "STEPPING_UP"
    BREACHED_FIXED_RESISTANCE = "BREACHED_FIXED_RESISTANCE"
    NEWLY_FLATTENED_AFTER_FALL = "NEWLY_FLATTENED_AFTER_FALL"
    LONG_HORIZONTAL = "LONG_HORIZONTAL"
    HORIZONTAL_AFTER_RISE = "HORIZONTAL_AFTER_RISE"
    HORIZONTAL_CEILING = "HORIZONTAL_CEILING"


class ResistanceArrowKind(StrEnum):
    STRONG_RETURN_DOWN = "STRONG_RETURN_DOWN"
    STRONG_MOMENTUM_DOWN = "STRONG_MOMENTUM_DOWN"
    VERTICAL_ATTEMPT_WARNING_UP = "VERTICAL_ATTEMPT_WARNING_UP"


_VALIDITY = {
    SupportValidity.NO_SUPPORT: ResistanceValidity.NO_RESISTANCE,
    SupportValidity.ACTIVE: ResistanceValidity.ACTIVE,
    SupportValidity.BREACHED: ResistanceValidity.BREACHED,
    SupportValidity.BELOW_FLOOR: ResistanceValidity.ABOVE_CEILING,
}
_DYNAMICS = {
    SupportDynamics.UNAVAILABLE: ResistanceDynamics.UNAVAILABLE,
    SupportDynamics.AT_SUPPORT: ResistanceDynamics.AT_RESISTANCE,
    SupportDynamics.EXPANDING: ResistanceDynamics.EXPANDING,
    SupportDynamics.CONTRACTING: ResistanceDynamics.CONTRACTING,
    SupportDynamics.FLAT: ResistanceDynamics.FLAT,
    SupportDynamics.BELOW_SUPPORT: ResistanceDynamics.ABOVE_RESISTANCE,
}
_PROGRESSION = {
    SupportProgression.NONE: ResistanceProgression.NONE,
    SupportProgression.INITIAL: ResistanceProgression.INITIAL,
    SupportProgression.SAME: ResistanceProgression.SAME,
    SupportProgression.REBASED_HIGHER: ResistanceProgression.REBASED_LOWER,
    SupportProgression.REBASED_LOWER: ResistanceProgression.REBASED_HIGHER,
}
_EVENT = {
    SupportLifecycleEventType.SUPPORT_CONFIRMED: ResistanceEventType.RESISTANCE_CONFIRMED,
    SupportLifecycleEventType.SUPPORT_TESTED: ResistanceEventType.RESISTANCE_TESTED,
    SupportLifecycleEventType.SUPPORT_HELD: ResistanceEventType.RESISTANCE_HELD,
    SupportLifecycleEventType.SUPPORT_BREACHED: ResistanceEventType.RESISTANCE_BREACHED,
    SupportLifecycleEventType.SUPPORT_FLOOR_BROKEN: ResistanceEventType.RESISTANCE_CEILING_BROKEN,
    SupportLifecycleEventType.SUPPORT_RECLAIMED: ResistanceEventType.RESISTANCE_RETURNED_BELOW,
    SupportLifecycleEventType.SUPPORT_LOST: ResistanceEventType.RESISTANCE_LOST,
    SupportLifecycleEventType.SUPPORT_REBASED_HIGHER: ResistanceEventType.RESISTANCE_REBASED_LOWER,
    SupportLifecycleEventType.SUPPORT_REBASED_LOWER: ResistanceEventType.RESISTANCE_REBASED_HIGHER,
}
_REGIME = {
    CandidateLineRegime.UNAVAILABLE.value: ResistanceRegime.UNAVAILABLE,
    CandidateLineRegime.STEPPING_UP.value: ResistanceRegime.STEPPING_DOWN,
    CandidateLineRegime.STEPPING_DOWN.value: ResistanceRegime.STEPPING_UP,
    CandidateLineRegime.BREACHED_FIXED_SUPPORT.value: ResistanceRegime.BREACHED_FIXED_RESISTANCE,
    CandidateLineRegime.NEWLY_FLATTENED_AFTER_RISE.value: ResistanceRegime.NEWLY_FLATTENED_AFTER_FALL,
    CandidateLineRegime.LONG_HORIZONTAL.value: ResistanceRegime.LONG_HORIZONTAL,
    CandidateLineRegime.HORIZONTAL_AFTER_DROP.value: ResistanceRegime.HORIZONTAL_AFTER_RISE,
    CandidateLineRegime.HORIZONTAL_BASE.value: ResistanceRegime.HORIZONTAL_CEILING,
}


def _opposite(value: float | None) -> float | None:
    return None if value is None else -float(value)


@dataclass(frozen=True, slots=True)
class DailyResistanceObservation:
    timestamp: Any
    high: float
    low: float
    close: float
    atr: float | None
    resistance_level: float | None
    resistance_ceiling: float | None
    resistance_origin_at: Any | None
    resistance_confirmed_at: Any | None
    resistance_available_at: Any | None
    resistance_origin_index: int | None
    resistance_confirmed_index: int | None

    @property
    def resistance_identity(self) -> tuple[Any, Any, float] | None:
        if self.resistance_level is None or self.resistance_origin_at is None or self.resistance_confirmed_at is None:
            return None
        return (self.resistance_origin_at, self.resistance_confirmed_at, self.resistance_level)


@dataclass(frozen=True, slots=True)
class ResistanceLifecycleEvent:
    sequence: int
    event_type: ResistanceEventType
    event_time: Any
    origin_at: Any | None
    confirmed_at: Any | None
    available_at: Any
    resistance_level: float | None
    resistance_ceiling: float | None
    previous_resistance: float | None
    new_resistance: float | None
    price: float
    atr: float | None
    distance_pct: float | None  # positive above the resistance
    distance_atr: float | None  # positive above the resistance
    bars_since_resistance: int | None
    bars_below_resistance: int
    bars_above_resistance: int
    return_count: int
    progression: ResistanceProgression


@dataclass(frozen=True, slots=True)
class StabilResistanceSnapshot:
    as_of: Any | None
    resistance_level: float | None
    resistance_ceiling: float | None
    resistance_origin_at: Any | None
    resistance_confirmed_at: Any | None
    resistance_available_at: Any | None
    validity: ResistanceValidity
    dynamics: ResistanceDynamics
    progression: ResistanceProgression
    distance_pct: float | None  # positive above the resistance
    distance_atr: float | None
    distance_delta_atr: float | None
    bars_since_resistance: int | None
    bars_below_resistance: int
    bars_above_resistance: int
    return_count: int
    intrabar_above_resistance: bool
    close_above_resistance: bool
    close_above_ceiling: bool
    events: tuple[ResistanceLifecycleEvent, ...]


@dataclass(frozen=True, slots=True)
class ResistanceBarPoint:
    bar_index: int
    bar_close_time: Any
    daily_as_of: Any | None
    resistance_level: float | None
    validity: ResistanceValidity
    dynamics: ResistanceDynamics
    progression: ResistanceProgression
    # Mirror of the actual support color roles: active=red, breached=green.
    color_role: str | None


@dataclass(frozen=True, slots=True)
class StabilResistanceBarBehavior:
    bar_index: int
    bar_close_time: Any
    resistance_level: float | None
    close_price: float | None
    pct_vs_resistance: float | None  # positive above the resistance
    dist_atr: float | None           # positive above the resistance
    high_dist_atr: float | None      # positive when the wick is above
    body_atr: float | None           # negative for a bearish body
    close_pos: float | None          # measured from low=0 to high=1
    vol_ratio: float | None
    fixed_resistance: bool
    regime: ResistanceRegime
    unchanged_days: int
    touch_count: int
    prev_breach_bars: int
    prev_breach_depth_atr: float
    return_kind: str | None          # close_return_below | intrabar_sweep_rejection
    weak_return: bool
    rank_score: float
    momentum_kind: str | None = None # long_ceiling_breakdown | downward_rebase_momentum
    vertical_resistance: bool = False
    vertical_attempt_kind: str | None = None

    @property
    def arrow_kind(self) -> ResistanceArrowKind | None:
        if self.vertical_attempt_kind:
            return ResistanceArrowKind.VERTICAL_ATTEMPT_WARNING_UP
        if self.return_kind:
            return ResistanceArrowKind.STRONG_RETURN_DOWN
        if self.momentum_kind:
            return ResistanceArrowKind.STRONG_MOMENTUM_DOWN
        return None


@dataclass(frozen=True, slots=True)
class StabilResistanceHistory:
    observations: tuple[DailyResistanceObservation, ...]
    timeline: tuple[StabilResistanceSnapshot, ...]
    # Internal native-coordinate timeline, needed to reuse the same candidate
    # regime classifier. Public prices above remain actual positive prices.
    _mirrored_timeline: tuple[StabilSupportLifecycleSnapshot, ...] = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class StabilResistanceOutput:
    symbol: str
    timeframe: str
    as_of_close: Any | None
    status: StabilRoleStatus
    reason: str | None
    observations: tuple[DailyResistanceObservation, ...] = ()
    timeline: tuple[StabilResistanceSnapshot, ...] = ()
    bar_projection: tuple[ResistanceBarPoint, ...] = ()
    bar_behaviors: tuple[StabilResistanceBarBehavior, ...] = ()
    latest_behavior: StabilResistanceBarBehavior | None = None


def _validate_real_ohlcv(frame: pd.DataFrame) -> None:
    """Reject malformed/negative real prices instead of inventing a line."""
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    if not required.issubset(frame.columns):
        raise ValueError("missing OHLCV columns")
    if frame.empty:
        return
    times = pd.DatetimeIndex(pd.to_datetime(frame["timestamp"], utc=True, errors="coerce"))
    if times.isna().any() or not times.is_monotonic_increasing or times.has_duplicates:
        raise ValueError("missing, duplicate or out-of-order timestamps")
    values = frame[["open", "high", "low", "close", "volume"]].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values[:, :4] <= 0).any() or (values[:, 4] < 0).any():
        raise ValueError("non-finite, nonpositive OHLC or negative volume")
    op, hi, lo, close = (values[:, i] for i in range(4))
    if np.any(hi < np.maximum(op, close)) or np.any(lo > np.minimum(op, close)) or np.any(hi < lo):
        raise ValueError("inconsistent OHLC bar")


def _mirror_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    _validate_real_ohlcv(frame)
    result = frame.copy(deep=True)
    result["open"] = -frame["open"].astype(float)
    result["high"] = -frame["low"].astype(float)
    result["low"] = -frame["high"].astype(float)
    result["close"] = -frame["close"].astype(float)
    return result


def _observation(value: DailySupportObservation) -> DailyResistanceObservation:
    return DailyResistanceObservation(
        timestamp=value.timestamp, high=-value.low, low=-value.high, close=-value.close, atr=value.atr,
        resistance_level=_opposite(value.support_level), resistance_ceiling=_opposite(value.support_floor),
        resistance_origin_at=value.support_origin_at, resistance_confirmed_at=value.support_confirmed_at,
        resistance_available_at=value.support_available_at, resistance_origin_index=value.support_origin_index,
        resistance_confirmed_index=value.support_confirmed_index,
    )


def _event(value: SupportLifecycleEvent) -> ResistanceLifecycleEvent:
    return ResistanceLifecycleEvent(
        sequence=value.sequence, event_type=_EVENT[value.event_type], event_time=value.event_time,
        origin_at=value.origin_at, confirmed_at=value.confirmed_at, available_at=value.available_at,
        resistance_level=_opposite(value.support_level), resistance_ceiling=_opposite(value.support_floor),
        previous_resistance=_opposite(value.previous_support), new_resistance=_opposite(value.new_support),
        price=-value.price, atr=value.atr, distance_pct=_opposite(value.distance_pct),
        distance_atr=_opposite(value.distance_atr), bars_since_resistance=value.bars_since_support,
        bars_below_resistance=value.bars_above_support, bars_above_resistance=value.bars_below_support,
        return_count=value.reclaim_count, progression=_PROGRESSION[value.progression],
    )


def _snapshot(value: StabilSupportLifecycleSnapshot) -> StabilResistanceSnapshot:
    return StabilResistanceSnapshot(
        as_of=value.as_of, resistance_level=_opposite(value.support_level),
        resistance_ceiling=_opposite(value.support_floor), resistance_origin_at=value.support_origin_at,
        resistance_confirmed_at=value.support_confirmed_at, resistance_available_at=value.support_available_at,
        validity=_VALIDITY[value.validity], dynamics=_DYNAMICS[value.dynamics],
        progression=_PROGRESSION[value.progression], distance_pct=_opposite(value.distance_pct),
        distance_atr=_opposite(value.distance_atr), distance_delta_atr=_opposite(value.distance_delta_atr),
        bars_since_resistance=value.bars_since_support, bars_below_resistance=value.bars_above_support,
        bars_above_resistance=value.bars_below_support, return_count=value.reclaim_count,
        intrabar_above_resistance=value.intrabar_below_support, close_above_resistance=value.close_below_support,
        close_above_ceiling=value.close_below_floor, events=tuple(_event(event) for event in value.events),
    )


def _validate_config(config: StabilTrendConfig) -> None:
    if (not isinstance(config, StabilTrendConfig)
            or isinstance(config.daily_pivot_len, bool)
            or not isinstance(config.daily_pivot_len, int) or config.daily_pivot_len < 1
            or not math.isfinite(float(config.min_tick)) or config.min_tick <= 0
            or not math.isfinite(float(config.support_atr_tolerance)) or config.support_atr_tolerance < 0):
        raise ValueError("invalid resistance configuration")


def build_daily_resistance_history(
    daily_clean: pd.DataFrame,
    *,
    config: StabilTrendConfig | None = None,
    include_prefix_events: bool = False,
) -> StabilResistanceHistory:
    """Build confirmed resistance from already-closed, timestamped daily OHLCV."""
    cfg = config or StabilTrendConfig()
    _validate_config(cfg)
    mirrored = _mirror_ohlcv(daily_clean)
    observations = build_daily_support_observations(mirrored, config=cfg)
    timeline = build_support_lifecycle_timeline(
        observations, min_tick=cfg.min_tick, include_prefix_events=include_prefix_events,
    )
    return StabilResistanceHistory(tuple(map(_observation, observations)), tuple(map(_snapshot, timeline)), timeline)


def project_resistance_to_bar_closes(
    bar_close_times: Sequence[Any], history: StabilResistanceHistory,
) -> tuple[ResistanceBarPoint, ...]:
    """Project only daily snapshots available at or before each target bar close."""
    points = project_support_to_bar_closes(list(bar_close_times), history._mirrored_timeline)
    return tuple(
        ResistanceBarPoint(
            bar_index=p.bar_index, bar_close_time=p.bar_close_time, daily_as_of=p.daily_as_of,
            resistance_level=_opposite(p.support_level), validity=_VALIDITY[p.validity],
            dynamics=_DYNAMICS[p.dynamics], progression=_PROGRESSION[p.progression],
            color_role=("red" if p.color_role == "above" else "green" if p.color_role == "below" else None),
        ) for p in points
    )


def evaluate_resistance_bar_behaviors(
    symbol: str,
    timeframe: str,
    target_clean: pd.DataFrame,
    bar_projection: Sequence[ResistanceBarPoint],
    history: StabilResistanceHistory,
    *,
    min_tick: float = 0.01,
) -> tuple[StabilResistanceBarBehavior, ...]:
    """Mirror support arrows in original-price coordinates, with no BOS filter.

    The 3-bar momentum *repeat* cooldown is inherited from support, not an extra
    confirmation delay after a newly confirmed resistance. Native step regimes
    remain provisional proxies, not verified visual horizontal/vertical states.
    """
    # This deliberately mirrors signals.evaluate_bar_behaviors without changing
    # the established support implementation/provenance. Keep both rules and
    # test_stabil_resistance_engine.py's parity tests in sync on future changes.
    del timeframe  # support evaluator currently has no timeframe-specific branch
    _validate_real_ohlcv(target_clean)
    if len(target_clean) != len(bar_projection):
        raise ValueError("target/projection length mismatch")
    if not math.isfinite(float(min_tick)) or min_tick <= 0:
        raise ValueError("invalid min_tick")
    n = len(target_clean)
    if not n:
        return ()
    previous_time = None
    for index, (timestamp, point) in enumerate(zip(target_clean["timestamp"], bar_projection)):
        bar_time = _to_istanbul_timestamp(timestamp)
        point_time = _to_istanbul_timestamp(point.bar_close_time)
        daily_time = _to_istanbul_timestamp(point.daily_as_of)
        if bar_time is None or point_time is None or bar_time != point_time or point.bar_index != index:
            raise ValueError("target/projection timestamp mismatch")
        if previous_time is not None and bar_time <= previous_time:
            raise ValueError("target timestamps must be strictly increasing")
        if daily_time is not None and daily_time > bar_time:
            raise ValueError("future daily snapshot in projection")
        previous_time = bar_time
    opens, highs, lows, closes, volumes = (
        target_clean[col].to_numpy(dtype=float)[:n] for col in ("open", "high", "low", "close", "volume")
    )
    atr_arr = _causal_atr14(highs, lows, closes, period=14)
    volume_arr = _causal_vol_ratio20(volumes, window=20)
    is_index = _is_index_symbol(symbol)
    tol = max(float(min_tick) * 0.5, 1e-6)
    regime_points = classify_candidate_support_regimes(history._mirrored_timeline) if history._mirrored_timeline else ()
    daily_times = [snap.as_of for snap in history._mirrored_timeline]
    vertical_max_age = 2 * StabilTrendConfig().daily_pivot_len

    def regime_at(daily_as_of: Any) -> tuple[str, int, bool]:
        if not regime_points or daily_as_of is None:
            return CandidateLineRegime.UNAVAILABLE.value, 0, False
        try:
            idx = bisect_right(daily_times, daily_as_of) - 1
        except TypeError:
            idx = -1
        if idx < 0 or idx >= len(regime_points):
            return CandidateLineRegime.UNAVAILABLE.value, 0, False
        rp = regime_points[idx]
        age = int(rp.bars_since_support or 0)
        recent_favorable_step = (
            rp.progression is SupportProgression.REBASED_HIGHER
            and rp.bars_since_support is not None
            and age <= vertical_max_age
        )
        return rp.regime.value, age, recent_favorable_step

    result: list[StabilResistanceBarBehavior] = []
    touch_count = 0
    last_touch_bar = -999
    separated_since_touch = True
    breach_bars = 0
    max_breach_depth_atr = 0.0
    previous_line: float | None = None
    previous_close: float | None = None
    last_momentum_bar = -999

    for i in range(n):
        pt = bar_projection[i]
        resistance = pt.resistance_level
        c, o, h, lo = float(closes[i]), float(opens[i]), float(highs[i]), float(lows[i])
        atr = float(atr_arr[i]) if math.isfinite(float(atr_arr[i])) and atr_arr[i] > 0 else np.nan
        vr = float(volume_arr[i]) if math.isfinite(float(volume_arr[i])) else None
        candle_range = max(h - lo, 0.0)
        close_pos = (c - lo) / candle_range if candle_range > 1e-9 else 0.5
        # Calculate in reflected coordinates directly: this avoids a second
        # subtraction (1 - close_pos) at exact threshold boundaries.
        bearish_close_pos = (h - c) / candle_range if candle_range > 1e-9 else 0.5
        body_atr = (c - o) / atr if math.isfinite(atr) and atr > 0 else None
        bearish_body_atr = -body_atr if body_atr is not None else None

        if resistance is None or not math.isfinite(float(resistance)) or float(resistance) <= 0:
            result.append(StabilResistanceBarBehavior(
                bar_index=i, bar_close_time=pt.bar_close_time, resistance_level=None, close_price=c,
                pct_vs_resistance=None, dist_atr=None, high_dist_atr=None, body_atr=body_atr,
                close_pos=close_pos, vol_ratio=vr, fixed_resistance=False, regime=ResistanceRegime.UNAVAILABLE,
                unchanged_days=0, touch_count=0, prev_breach_bars=0, prev_breach_depth_atr=0.0,
                return_kind=None, weak_return=False, rank_score=0.0,
            ))
            previous_line, previous_close = None, c
            touch_count, breach_bars, max_breach_depth_atr = 0, 0, 0.0
            last_momentum_bar = -999
            continue

        line = float(resistance)
        fixed = previous_line is not None and abs(line - previous_line) <= max(tol, 1e-6 * max(1.0, line))
        if not fixed:
            touch_count, last_touch_bar, separated_since_touch = 0, -999, True
            breach_bars, max_breach_depth_atr = 0, 0.0
        pct = (c - line) / line * 100.0
        dist = (c - line) / atr if math.isfinite(atr) and atr > 0 else None
        high_dist = (h - line) / atr if math.isfinite(atr) and atr > 0 else None
        safe_dist = -dist if dist is not None else None
        mirrored_low_dist = -high_dist if high_dist is not None else None
        candidate, unchanged_days, recently_rebased_down = regime_at(pt.daily_as_of)
        vertical = (
            candidate in {CandidateLineRegime.STEPPING_UP.value, CandidateLineRegime.STEPPING_DOWN.value}
            or recently_rebased_down
            or (previous_line is not None and not fixed)
        )
        if safe_dist is not None and mirrored_low_dist is not None:
            if safe_dist >= 0.55:
                separated_since_touch = True
            near_touch = (-0.15 <= safe_dist <= 0.45) and (mirrored_low_dist <= 0.25)
            if near_touch and separated_since_touch and i - last_touch_bar >= 4:
                touch_count += 1
                last_touch_bar, separated_since_touch = i, False

        prior_breach_bars, prior_breach_depth = breach_bars, max_breach_depth_atr
        return_kind: str | None = None
        weak_return = False
        momentum_kind: str | None = None
        if (fixed and previous_line is not None and previous_close is not None
                and safe_dist is not None and mirrored_low_dist is not None and bearish_body_atr is not None):
            was_above = previous_close > previous_line + tol
            now_below = c < line - tol
            was_below = previous_close <= previous_line + tol
            volume_ok_return = ((vr is not None and vr >= 1.0) or bearish_body_atr >= 0.45
                                or (is_index and bearish_body_atr >= 0.38))
            volume_ok_sweep = ((vr is not None and vr >= 1.0) or bearish_body_atr >= 0.50
                               or (is_index and bearish_body_atr >= 0.40))
            if was_above and now_below:
                if (0.0 < prior_breach_depth <= 1.50 and bearish_body_atr >= 0.32
                        and bearish_close_pos >= 0.65 and safe_dist >= 0.05 and volume_ok_return):
                    return_kind = "close_return_below"
                else:
                    weak_return = True
            elif (was_below and now_below and -1.20 <= mirrored_low_dist <= -0.08
                  and safe_dist >= 0.08 and bearish_body_atr >= 0.35
                  and bearish_close_pos >= 0.68 and volume_ok_sweep):
                return_kind = "intrabar_sweep_rejection"

        if (return_kind is None and not weak_return and pct < 0.0
                and safe_dist is not None and bearish_body_atr is not None
                and bearish_body_atr >= _GUCLU_YUKARI_GOVDE_ATR
                and bearish_close_pos >= _GUCLU_YUKARI_KAPANIS_POZ and touch_count < 3
                and ((vr is not None and vr >= _GUCLU_YUKARI_HACIM_ORAN)
                     or bearish_body_atr >= _GUCLU_YUKARI_COK_GUCLU_GOVDE_ATR)
                and pt.validity == ResistanceValidity.ACTIVE
                and i - last_momentum_bar >= _GUCLU_YUKARI_COOLDOWN_BAR):
            long_ceiling = unchanged_days >= 20 and 0.15 <= safe_dist <= 1.80
            step_down = (candidate == CandidateLineRegime.STEPPING_UP.value
                         or _enum_value(pt.progression) == ResistanceProgression.REBASED_LOWER.value)
            stepping = step_down and 0.10 <= safe_dist <= 1.60
            if long_ceiling or stepping:
                momentum_kind = "long_ceiling_breakdown" if long_ceiling else "downward_rebase_momentum"

        vertical_attempt_kind = None
        if vertical:
            vertical_attempt_kind = return_kind or ("weak_return" if weak_return else None) or momentum_kind
            if vertical_attempt_kind is None and previous_close is not None and previous_line is not None:
                if previous_close > previous_line + tol and lo <= line + tol:
                    # The native tolerance also admits near-line/gap cases; it
                    # is a structural attempt, not proof of an actual touch.
                    vertical_attempt_kind = "approach_from_above"
            return_kind, momentum_kind, weak_return = None, None, False
        elif momentum_kind is not None:
            last_momentum_bar = i

        if c > line + tol:
            breach_bars += 1
            if dist is not None:
                max_breach_depth_atr = max(max_breach_depth_atr, max(0.0, dist))
        else:
            breach_bars, max_breach_depth_atr = 0, 0.0

        rank_score = 0.0
        if return_kind is not None and bearish_body_atr is not None:
            vol_bonus = min(0.8, max(0.0, (vr - 1.0) * 0.4)) if vr is not None else 0.15
            base_bonus = 0.35 if unchanged_days >= 20 else (0.15 if unchanged_days >= 8 else 0.0)
            exhaustion_pen = -0.25 if touch_count >= 3 else (0.15 if touch_count == 2 else 0.0)
            rank_score = round(float(bearish_body_atr) * 1.4 + float(bearish_close_pos) * 0.8
                               + vol_bonus + base_bonus + exhaustion_pen, 4)
        result.append(StabilResistanceBarBehavior(
            bar_index=i, bar_close_time=pt.bar_close_time, resistance_level=line, close_price=c,
            pct_vs_resistance=pct, dist_atr=dist, high_dist_atr=high_dist, body_atr=body_atr,
            close_pos=close_pos, vol_ratio=vr, fixed_resistance=fixed, regime=_REGIME[candidate],
            unchanged_days=unchanged_days, touch_count=touch_count, prev_breach_bars=prior_breach_bars,
            prev_breach_depth_atr=prior_breach_depth, return_kind=return_kind, weak_return=weak_return,
            rank_score=rank_score, momentum_kind=momentum_kind, vertical_resistance=vertical,
            vertical_attempt_kind=vertical_attempt_kind,
        ))
        previous_line, previous_close = line, c
    return tuple(result)


def _prepare_checked(
    frame: pd.DataFrame | None,
    *,
    symbol: str,
    timeframe: str,
    cutoff: Any | None,
    certified_closes: bool,
) -> tuple[pd.DataFrame, str | None]:
    """Use native closed-bar rules, but don't silently bridge a malformed bar.

    Native preparation drops nonnumeric OHLC. A probe preserves those rows
    using a non-finite sentinel, then applies the *same* close/cutoff/duplicate
    filters. Thus an invalid eligible bar fails closed without inspecting or
    rejecting an incomplete or future bar. Missing volume retains native
    support's zero-volume handling; a missing volume column is still an error.
    """
    kwargs = dict(symbol=symbol, timeframe=timeframe, cutoff_close=cutoff, certified_closes=certified_closes)
    try:
        if frame is not None and not isinstance(frame, pd.DataFrame):
            return pd.DataFrame(), "invalid_frame"
        if frame is None or not len(frame):
            return prepare_causal_ohlcv(frame, **kwargs)
        raw = frame.rename(columns={c: str(c).lower() for c in frame.columns}).copy()
        ohlc = ("open", "high", "low", "close")
        if not all(col in raw.columns for col in (*ohlc, "volume")):
            return prepare_causal_ohlcv(raw, **kwargs)

        # Native .astype(bool) would read the string "False" as True. Normalize
        # known flags before preparation and separately flag unknown values.
        safe = raw.copy()
        flag_columns = [col for col in ("is_closed", "is_complete") if col in raw.columns]
        eligible = np.ones(len(raw), dtype=bool)
        invalid_flag = np.zeros(len(raw), dtype=bool)
        for col in flag_columns:
            column = np.zeros(len(raw), dtype=bool)
            for i, value in enumerate(raw[col].to_numpy(dtype=object)):
                if pd.isna(value):
                    continue
                if isinstance(value, (bool, int, float, np.bool_, np.integer, np.floating)) and value in (0, 1):
                    column[i] = bool(value)
                else:
                    invalid_flag[i] = True
                    # Unknown must fail unless a different flag unambiguously
                    # excludes the bar; don't accidentally treat it as closed.
                    column[i] = True
            eligible &= column
            safe[col] = column
        invalid_flag &= eligible

        # A missing close time on an otherwise eligible bar must not be dropped
        # and bridged silently. A valid open/label after the cutoff is future;
        # a missing label cannot establish this and therefore fails closed.
        time_values = None
        if certified_closes and "close_time" in raw.columns:
            time_values = raw["close_time"]
        elif isinstance(raw.index, pd.DatetimeIndex):
            time_values = raw.index
        elif "timestamp" in raw.columns:
            time_values = raw["timestamp"]
        if time_values is not None:
            parsed = pd.DatetimeIndex(pd.to_datetime(time_values, utc=True, errors="coerce"))
            missing_time = parsed.isna()
            if missing_time.any():
                if "timestamp" in raw.columns:
                    label_values = raw["timestamp"]
                elif isinstance(raw.index, pd.DatetimeIndex):
                    label_values = raw.index
                else:
                    label_values = [None] * len(raw)
                def valid_label(value: Any) -> pd.Timestamp | None:
                    try:
                        return _to_istanbul_timestamp(value)
                    except (ValueError, TypeError, OverflowError):
                        return None
                labels = pd.DatetimeIndex([valid_label(value) for value in label_values], tz="Europe/Istanbul")
                future_label = ((~labels.isna()) & (labels > _to_istanbul_timestamp(cutoff))
                                if cutoff is not None else np.zeros(len(raw), dtype=bool))
                if (missing_time & eligible & ~future_label).any():
                    return pd.DataFrame(), "invalid_timestamp"

                # If an explicitly incomplete row also has a bad close time,
                # use its known label only to tell trailing/future from an
                # internal hole. If even its label is missing, don't bridge it.
                excluded = missing_time & ~eligible & ~future_label
                if excluded.any():
                    if labels[excluded].isna().any():
                        return pd.DataFrame(), "invalid_timestamp"
                    reference = ~missing_time & eligible
                    if cutoff is not None:
                        reference &= parsed <= _to_istanbul_timestamp(cutoff)
                    if reference.any() and (labels[excluded] <= labels[reference].max()).any():
                        return pd.DataFrame(), "internal_incomplete_bar"
                # Native preparation parses times before applying flags/cutoff;
                # remove known-unclosed and known-future malformed times first.
                keep = ~missing_time
                raw, safe = raw.loc[keep].copy(), safe.loc[keep].copy()
                eligible, invalid_flag = eligible[keep], invalid_flag[keep]

        price_probe = safe.copy()
        has_invalid = False
        for col in ohlc:
            numeric = pd.to_numeric(price_probe[col], errors="coerce").to_numpy(dtype=float)
            invalid = ~np.isfinite(numeric)
            if invalid.any():
                has_invalid = True
                numeric[invalid] = np.inf
                price_probe[col] = numeric
        if has_invalid:
            inspected, _ = prepare_causal_ohlcv(price_probe, **kwargs)
            if not inspected.empty and not np.isfinite(inspected[list(ohlc)].to_numpy(dtype=float)).all():
                return pd.DataFrame(), "invalid_ohlc"
        prepared, err = prepare_causal_ohlcv(safe, **kwargs)

        # A trailing incomplete bar is excluded. An explicitly incomplete bar
        # *between* valid bars must not be silently bridged by ATR, breach state
        # or a daily pivot. Entirely absent, unflagged bars cannot be detected
        # here; callers must supply complete sources/quality flags.
        if flag_columns and (invalid_flag.any() or not eligible.all()):
            probe = raw.copy()
            for col in ohlc:
                probe[col] = 1.0
            probe["volume"] = np.where(invalid_flag, -2.0, np.where(eligible, 1.0, -1.0))
            for col in flag_columns:
                probe[col] = True
            checked, _ = prepare_causal_ohlcv(probe, **kwargs)
            if (checked["volume"] == -2.0).any():
                return pd.DataFrame(), "invalid_completion_flag"
            if not prepared.empty:
                internal_bad = (checked["volume"] == -1.0) & (checked["timestamp"] <= prepared["timestamp"].iloc[-1])
                if internal_bad.any():
                    return pd.DataFrame(), "internal_incomplete_bar"
        return prepared, err
    except (ValueError, TypeError, OverflowError) as exc:
        return pd.DataFrame(), f"invalid_input:{exc}"



def evaluate_stabil_resistance(
    symbol: str,
    timeframe: str,
    target_frame: pd.DataFrame | None,
    *,
    daily_frame: pd.DataFrame | None = None,
    as_of_close: Any | None = None,
    config: StabilTrendConfig | None = None,
    certified_closes: bool = False,
    include_prefix_events: bool = False,
) -> StabilResistanceOutput:
    """Isolated closed-bar resistance calculation; no chart/alert side effects."""
    clean_symbol = str(symbol or "").strip().upper().replace(".IS", "")
    tf = str(timeframe or "1d").strip().lower()
    cutoff = None
    def empty(status: StabilRoleStatus, reason: str) -> StabilResistanceOutput:
        return StabilResistanceOutput(clean_symbol, tf, cutoff, status, reason)
    try:
        cutoff = _to_istanbul_timestamp(as_of_close)
    except (ValueError, TypeError, OverflowError):
        return empty(StabilRoleStatus.DATA_ERROR, "invalid_as_of_close")
    if as_of_close is not None and cutoff is None:
        return empty(StabilRoleStatus.DATA_ERROR, "invalid_as_of_close")
    if tf not in {"1h", "2h", "4h", "1d"}:
        return empty(StabilRoleStatus.DATA_ERROR, "unsupported_timeframe")
    target, target_err = _prepare_checked(
        target_frame, symbol=clean_symbol, timeframe=tf, cutoff=cutoff, certified_closes=certified_closes,
    )
    if target.empty:
        status = (StabilRoleStatus.UNAVAILABLE if target_err in {"missing_frame", "no_completed_bars_at_cutoff"}
                  else StabilRoleStatus.DATA_ERROR)
        return empty(status, target_err or "empty_target")
    if cutoff is None:
        cutoff = _to_istanbul_timestamp(target.timestamp.iloc[-1])
    daily_source = daily_frame if daily_frame is not None else (target_frame if tf == "1d" else None)
    # A caller's wall-clock cutoff can be later than the newest target bar.
    # Later daily candles cannot affect that bar, even via quality validation.
    daily_cutoff = min(cutoff, _to_istanbul_timestamp(target.timestamp.iloc[-1]))
    daily, daily_err = _prepare_checked(
        daily_source, symbol=clean_symbol, timeframe="1d", cutoff=daily_cutoff, certified_closes=certified_closes,
    )
    if daily.empty:
        status = (StabilRoleStatus.UNAVAILABLE if daily_err in {"missing_frame", "no_completed_bars_at_cutoff"}
                  else StabilRoleStatus.DATA_ERROR)
        return empty(status, daily_err or "empty_daily")
    cfg = config or StabilTrendConfig()
    try:
        _validate_real_ohlcv(target)
        history = build_daily_resistance_history(daily, config=cfg, include_prefix_events=include_prefix_events)
        projection = project_resistance_to_bar_closes(list(target.timestamp), history)
        behaviors = evaluate_resistance_bar_behaviors(clean_symbol, tf, target, projection, history, min_tick=cfg.min_tick)
    except (ValueError, TypeError, OverflowError) as exc:
        return empty(StabilRoleStatus.DATA_ERROR, f"invalid_ohlcv:{exc}")
    ready = bool(projection and projection[-1].resistance_level is not None)
    return StabilResistanceOutput(
        symbol=clean_symbol, timeframe=tf, as_of_close=cutoff,
        status=StabilRoleStatus.READY if ready else StabilRoleStatus.WARMUP,
        reason=None if ready else "insufficient_history_for_resistance",
        observations=history.observations, timeline=history.timeline, bar_projection=projection,
        bar_behaviors=behaviors, latest_behavior=behaviors[-1] if behaviors else None,
    )
