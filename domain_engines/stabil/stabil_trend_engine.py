from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

import pandas as pd


class WeeklyTrendState(StrEnum):
    PENDING = "WEEKLY_PENDING"
    UP_STABLE = "WEEKLY_UP_STABLE"
    UP_WEAKENING = "WEEKLY_UP_WEAKENING"
    TRANSITION = "WEEKLY_TRANSITION"
    NOT_UP = "WEEKLY_NOT_UP"
    UP_PARABOLIC = "WEEKLY_UP_PARABOLIC"


class DailyRawState(StrEnum):
    PENDING = "DAILY_RAW_PENDING"
    ADVANCE = "DAILY_RAW_ADVANCE"
    PULLBACK = "DAILY_RAW_PULLBACK"
    BALANCE = "DAILY_RAW_BALANCE"
    NEUTRAL = "DAILY_RAW_NEUTRAL"
    TOO_DEEP = "DAILY_RAW_TOO_DEEP"
    DISTRIBUTION = "DAILY_RAW_DISTRIBUTION"
    STRUCTURE_BROKEN = "DAILY_RAW_STRUCTURE_BROKEN"
    GAP_WATCH = "DAILY_RAW_GAP_WATCH"
    PARABOLIC = "DAILY_RAW_PARABOLIC"


class DailyTrendState(StrEnum):
    PENDING = "DAILY_PENDING"
    HEALTHY_ADVANCE = "DAILY_HEALTHY_ADVANCE"
    CONTROLLED_PULLBACK = "DAILY_CONTROLLED_PULLBACK"
    BASE_BUILDING = "DAILY_BASE_BUILDING"
    PULLBACK_TOO_DEEP = "DAILY_PULLBACK_TOO_DEEP"
    DISTRIBUTION_RISK = "DAILY_DISTRIBUTION_RISK"
    STRUCTURE_BROKEN = "DAILY_STRUCTURE_BROKEN"
    NEUTRAL = "DAILY_NEUTRAL"
    BEARISH_BALANCE = "DAILY_BEARISH_BALANCE"
    GAP_WATCH = "DAILY_GAP_WATCH"
    PARABOLIC = "DAILY_PARABOLIC"
    LOCAL_RECOVERY = "DAILY_LOCAL_RECOVERY"
    LOCAL_OVERHEAT = "DAILY_LOCAL_OVERHEAT"


class GapState(StrEnum):
    NONE = "GAP_NONE"
    RECLAIMED = "GAP_RECLAIMED"
    WATCH = "GAP_WATCH"
    CONFIRMED = "GAP_CONFIRMED"


class H4TrendState(StrEnum):
    PENDING = "H4_PENDING"
    NO_RECOVERY = "H4_NO_RECOVERY"
    SELLING_WEAKENING = "H4_SELLING_WEAKENING"
    BUYERS_EMERGING = "H4_BUYERS_EMERGING"
    RECOVERY_CONFIRMED = "H4_RECOVERY_CONFIRMED"
    RECOVERY_FAILED = "H4_RECOVERY_FAILED"


class H4Lifecycle(StrEnum):
    NO_EVENT = "NO_EVENT"
    DISPLACEMENT_ACTIVE = "DISPLACEMENT_ACTIVE"
    BUYERS_EMERGING = "BUYERS_EMERGING"
    RECOVERY_CONFIRMED = "RECOVERY_CONFIRMED"
    RECOVERY_FAILED = "RECOVERY_FAILED"


class H4EvidenceStatus(StrEnum):
    NONE = "NONE"
    FRESH = "FRESH"
    OLD = "OLD"
    FAILED = "FAILED"
    ATTEMPT_FAILED = "ATTEMPT_FAILED"


@dataclass(frozen=True, slots=True)
class StabilTrendConfig:
    weekly_pivot_len: int = 3
    daily_pivot_len: int = 4
    support_atr_tolerance: float = 0.35
    weekly_ema_len: int = 30
    daily_ema_len: int = 34
    slope_lookback: int = 5
    acceptance_len: int = 8
    pullback_lookback: int = 24
    healthy_depth_atr: float = 3.2
    deep_depth_atr: float = 5.0
    max_pullback_bars: int = 16
    h4_fast_ema_len: int = 13
    h4_micro_pivot_len: int = 2
    displacement_factor: float = 1.35
    h4_evidence_fresh_bars: int = 6
    min_tick: float = 0.01


@dataclass(frozen=True, slots=True)
class ConfirmedStabilPivot:
    side: str
    price: float
    origin_index: int
    known_index: int
    origin_time: Any
    known_time: Any
    atr_at_origin: float


@dataclass(frozen=True, slots=True)
class WeeklyTrendSnapshot:
    timestamp: Any | None = None
    data_ready: bool = False
    structure_usable: bool = False
    structure_quality: bool = False
    pivot_alternation_valid: bool = False
    support_held: bool = False
    state: WeeklyTrendState = WeeklyTrendState.PENDING
    slope_atr: float | None = None
    acceptance: float | None = None
    stretch_atr: float | None = None
    higher_high: bool = False
    higher_low: bool = False
    support_age: int | None = None
    support: float | None = None
    support_floor: float | None = None
    last_high: ConfirmedStabilPivot | None = None
    previous_high: ConfirmedStabilPivot | None = None
    last_low: ConfirmedStabilPivot | None = None
    previous_low: ConfirmedStabilPivot | None = None


@dataclass(frozen=True, slots=True)
class DailyTrendSnapshot:
    timestamp: Any | None = None
    data_ready: bool = False
    structure_usable: bool = False
    structure_quality: bool = False
    pivot_alternation_valid: bool = False
    support_fresh: bool = False
    support_held: bool = False
    volume_usable: bool = False
    raw_state: DailyRawState = DailyRawState.PENDING
    state: DailyTrendState = DailyTrendState.PENDING
    support: float | None = None
    support_floor: float | None = None
    support_age: int | None = None
    gap_state: GapState = GapState.NONE
    pullback_start_index: int | None = None
    pullback_start_time: Any | None = None
    pullback_origin_high: float | None = None
    pullback_origin_index: int | None = None
    pullback_reference_atr: float | None = None
    depth_atr: float | None = None
    pullback_bars: int = 0
    slope_atr: float | None = None
    acceptance: float | None = None
    down_body_atr: float | None = None
    red_share: float | None = None
    sell_volume_factor: float | None = None
    expansion_count: float | None = None
    range_compression: float | None = None
    low_support_atr: float | None = None
    higher_high: bool = False
    higher_low: bool = False
    lower_high: bool = False
    lower_low: bool = False
    uncontrolled_selling: bool = False
    heavy_sell_volume: bool = False
    support_broken: bool = False
    prior_up_context: bool = False
    bearish_structure: bool = False


@dataclass(frozen=True, slots=True)
class H4TrendSnapshot:
    timestamp: Any | None = None
    data_ready: bool = False
    volume_usable: bool = False
    state: H4TrendState = H4TrendState.PENDING
    lifecycle: H4Lifecycle = H4Lifecycle.NO_EVENT
    event_index: int | None = None
    event_time: Any | None = None
    event_low: float | None = None
    event_mid: float | None = None
    recovery_index: int | None = None
    recovery_time: Any | None = None
    invalidation_index: int | None = None
    invalidation_time: Any | None = None
    event_age: int | None = None
    recovery_age: int | None = None
    failure_age: int | None = None
    last_micro_pivot_low: ConfirmedStabilPivot | None = None
    bull_displacement: bool = False
    micro_higher_low: bool = False
    sellers_shrinking: bool = False
    close_location: float | None = None
    acceptance: float | None = None
    buyer_volume_factor: float | None = None
    volume_pass: bool = False
    buyer_body_atr: float | None = None
    buyer_body_average_ratio: float | None = None
    close_ema_atr: float | None = None
    recovery_still_valid: bool = False
    active_emergence: bool = False
    recent_failure: bool = False


@dataclass(frozen=True, slots=True)
class StabilTrendContext:
    as_of: Any | None
    weekly: WeeklyTrendSnapshot
    daily: DailyTrendSnapshot
    h4: H4TrendSnapshot
    h4_evidence: H4EvidenceStatus


def _safe_div(a: float, b: float | None, default: float | None = None) -> float | None:
    if b is None or pd.isna(b) or abs(float(b)) <= 1e-12:
        return default
    return float(a) / float(b)


def _clean(frame: pd.DataFrame, as_of: Any | None = None) -> pd.DataFrame:
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Stabil Trend requires OHLCV columns; missing={sorted(missing)}")
    out = frame.copy()
    if "is_closed" in out.columns:
        out = out[out["is_closed"].fillna(False).astype(bool)]
    if "is_complete" in out.columns:
        out = out[out["is_complete"].fillna(False).astype(bool)]
    if as_of is not None:
        out = out[out["timestamp"] <= as_of]
    return out.sort_values("timestamp").reset_index(drop=True)


def _ema(values: pd.Series, length: int) -> pd.Series:
    return values.astype(float).ewm(span=length, adjust=False).mean()


def _rma(values: list[float], length: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) < length:
        return out
    seed = sum(values[:length]) / length
    out[length - 1] = seed
    prev = seed
    alpha = 1.0 / length
    for i in range(length, len(values)):
        prev = alpha * values[i] + (1.0 - alpha) * prev
        out[i] = prev
    return out


def _atr(frame: pd.DataFrame, length: int = 14) -> list[float | None]:
    tr: list[float] = []
    for i, row in frame.iterrows():
        h, l = float(row.high), float(row.low)
        if i == 0:
            tr.append(h - l)
        else:
            pc = float(frame.iloc[i - 1].close)
            tr.append(max(h - l, abs(h - pc), abs(l - pc)))
    return _rma(tr, length)


def _rolling_mean(values: list[float], length: int) -> list[float | None]:
    s = pd.Series(values, dtype=float).rolling(length).mean()
    return [None if pd.isna(x) else float(x) for x in s]


def _confirmed_pivots(frame: pd.DataFrame, span: int, atr: list[float | None]) -> tuple[list[ConfirmedStabilPivot], list[ConfirmedStabilPivot]]:
    highs: list[ConfirmedStabilPivot] = []
    lows: list[ConfirmedStabilPivot] = []
    hv = frame["high"].astype(float).tolist()
    lv = frame["low"].astype(float).tolist()
    for origin in range(span, len(frame) - span):
        known = origin + span
        origin_atr = atr[origin]
        if origin_atr is None or origin_atr <= 0:
            continue
        hw = hv[origin - span : origin + span + 1]
        lw = lv[origin - span : origin + span + 1]
        if hv[origin] == max(hw) and hw.count(hv[origin]) == 1:
            highs.append(ConfirmedStabilPivot("HIGH", hv[origin], origin, known, frame.iloc[origin].timestamp, frame.iloc[known].timestamp, float(origin_atr)))
        if lv[origin] == min(lw) and lw.count(lv[origin]) == 1:
            lows.append(ConfirmedStabilPivot("LOW", lv[origin], origin, known, frame.iloc[origin].timestamp, frame.iloc[known].timestamp, float(origin_atr)))
    return highs, lows


def _alternates(last_h: ConfirmedStabilPivot, prev_h: ConfirmedStabilPivot, last_l: ConfirmedStabilPivot, prev_l: ConfirmedStabilPivot) -> bool:
    a, b, c, d = prev_l.origin_index, prev_h.origin_index, last_l.origin_index, last_h.origin_index
    low_high_low_high = a < b < c < d
    a, b, c, d = prev_h.origin_index, prev_l.origin_index, last_h.origin_index, last_l.origin_index
    high_low_high_low = a < b < c < d
    return low_high_low_high or high_low_high_low


def _normalized_slope(ema_now: float, ema_past: float, atr_now: float, lookback: int) -> float | None:
    raw = _safe_div(ema_now - ema_past, atr_now * max(float(lookback), 1.0))
    return None if raw is None else raw * 5.0


def _weekly_snapshot(frame: pd.DataFrame, cfg: StabilTrendConfig) -> WeeklyTrendSnapshot:
    if frame.empty:
        return WeeklyTrendSnapshot()
    return build_weekly_trend_timeline(frame, cfg)[-1]


def build_weekly_trend_timeline(frame: pd.DataFrame, cfg: StabilTrendConfig) -> tuple[WeeklyTrendSnapshot, ...]:
    """Single-pass causal timeline producing identical output to prefix `_weekly_snapshot`."""
    if frame.empty:
        return ()
    atr = _atr(frame)
    ema = _ema(frame["close"], cfg.weekly_ema_len)
    highs, lows = _confirmed_pivots(frame, cfg.weekly_pivot_len, atr)
    acceptance_series = (frame["close"].astype(float) > ema).astype(float).rolling(cfg.acceptance_len).mean()
    out: list[WeeklyTrendSnapshot] = []
    h_pos = 0
    l_pos = 0
    for i in range(len(frame)):
        while h_pos < len(highs) and highs[h_pos].known_index <= i:
            h_pos += 1
        while l_pos < len(lows) and lows[l_pos].known_index <= i:
            l_pos += 1
        acceptance = None if pd.isna(acceptance_series.iloc[i]) else float(acceptance_series.iloc[i])
        atr_i = atr[i]
        ema_i = float(ema.iloc[i])
        stretch = None if atr_i is None else _safe_div(float(frame.iloc[i].close) - ema_i, atr_i)
        history_ready = i > cfg.weekly_ema_len + cfg.slope_lookback + cfg.weekly_pivot_len * 8
        enough = h_pos >= 2 and l_pos >= 2
        ema_past = float(ema.iloc[i - cfg.slope_lookback]) if i >= cfg.slope_lookback else None
        data_ready = history_ready and enough and atr_i is not None and ema_past is not None and acceptance is not None and stretch is not None
        if not enough:
            out.append(WeeklyTrendSnapshot(timestamp=frame.iloc[i].timestamp, data_ready=False))
            continue
        last_h, prev_h = highs[h_pos - 1], highs[h_pos - 2]
        last_l, prev_l = lows[l_pos - 1], lows[l_pos - 2]
        usable = data_ready and last_h.origin_index > prev_h.origin_index and last_l.origin_index > prev_l.origin_index
        alternating = usable and _alternates(last_h, prev_h, last_l, prev_l)
        spacing = usable and last_h.origin_index - prev_h.origin_index >= cfg.weekly_pivot_len * 2 and last_l.origin_index - prev_l.origin_index >= cfg.weekly_pivot_len * 2
        current_exc = abs(last_h.price - last_l.price)
        previous_exc = abs(prev_h.price - prev_l.price)
        current_ref = max((last_h.atr_at_origin + last_l.atr_at_origin) * 0.5, cfg.min_tick)
        previous_ref = max((prev_h.atr_at_origin + prev_l.atr_at_origin) * 0.5, cfg.min_tick)
        excursion_quality = alternating and current_exc / current_ref >= 0.75 and previous_exc / previous_ref >= 0.75
        support_age = i - last_l.origin_index if usable else None
        support_fresh = usable and support_age is not None and support_age <= cfg.weekly_pivot_len * 14
        quality = usable and spacing and excursion_quality and support_fresh
        hh = usable and last_h.price > prev_h.price
        hl = usable and last_l.price > prev_l.price
        floor = last_l.price - last_l.atr_at_origin * cfg.support_atr_tolerance if usable else None
        support_held = usable and floor is not None and float(frame.iloc[i].close) >= floor
        slope = _normalized_slope(ema_i, ema_past, float(atr_i), cfg.slope_lookback) if data_ready and atr_i else None
        accepted = acceptance is not None and acceptance >= 0.625
        parabolic = bool(usable and hh and hl and support_held and accepted and stretch is not None and stretch > 4.5 and slope is not None and slope > 0.75)
        state = WeeklyTrendState.PENDING
        if data_ready:
            if not usable:
                state = WeeklyTrendState.TRANSITION
            elif parabolic and quality:
                state = WeeklyTrendState.UP_PARABOLIC
            elif hh and hl and support_held and slope is not None and slope > 0.12 and accepted and quality:
                state = WeeklyTrendState.UP_STABLE
            elif hl and support_held and slope is not None and slope > -0.05 and (accepted or float(frame.iloc[i].close) > ema_i) and quality:
                state = WeeklyTrendState.UP_WEAKENING
            elif support_held and slope is not None and slope > -0.05:
                state = WeeklyTrendState.TRANSITION
            else:
                state = WeeklyTrendState.NOT_UP
        out.append(
            WeeklyTrendSnapshot(
                frame.iloc[i].timestamp,
                data_ready,
                usable,
                quality,
                alternating,
                support_held,
                state,
                slope,
                acceptance,
                stretch,
                hh,
                hl,
                support_age,
                last_l.price if usable else None,
                floor,
                last_h,
                prev_h,
                last_l,
                prev_l,
            )
        )
    return tuple(out)


def _weekly_up_context(state: WeeklyTrendState) -> bool:
    return state in {WeeklyTrendState.UP_STABLE, WeeklyTrendState.UP_WEAKENING, WeeklyTrendState.UP_PARABOLIC}


def _daily_context(raw: DailyRawState, weekly: WeeklyTrendState, prior_up: bool, bearish: bool) -> DailyTrendState:
    up = _weekly_up_context(weekly) or prior_up
    return {
        DailyRawState.ADVANCE: DailyTrendState.HEALTHY_ADVANCE if up else DailyTrendState.LOCAL_RECOVERY,
        DailyRawState.PULLBACK: DailyTrendState.CONTROLLED_PULLBACK if up else DailyTrendState.BEARISH_BALANCE,
        DailyRawState.BALANCE: DailyTrendState.BASE_BUILDING if up else DailyTrendState.BEARISH_BALANCE,
        DailyRawState.NEUTRAL: DailyTrendState.BEARISH_BALANCE if bearish and not up else DailyTrendState.NEUTRAL,
        DailyRawState.TOO_DEEP: DailyTrendState.PULLBACK_TOO_DEEP,
        DailyRawState.DISTRIBUTION: DailyTrendState.DISTRIBUTION_RISK,
        DailyRawState.STRUCTURE_BROKEN: DailyTrendState.STRUCTURE_BROKEN,
        DailyRawState.GAP_WATCH: DailyTrendState.GAP_WATCH,
        DailyRawState.PARABOLIC: DailyTrendState.PARABOLIC if up else DailyTrendState.LOCAL_OVERHEAT,
    }.get(raw, DailyTrendState.PENDING)


def recontextualize_daily_snapshot(snapshot: DailyTrendSnapshot, weekly: WeeklyTrendState) -> DailyTrendSnapshot:
    """Apply weekly context purely to a causal daily snapshot without mutating raw daily math."""
    if snapshot.timestamp is None and not snapshot.data_ready and snapshot.raw_state == DailyRawState.PENDING:
        return snapshot
    if snapshot.raw_state == DailyRawState.PENDING and not snapshot.data_ready and not snapshot.structure_usable:
        # Mirrors the `if not enough: DailyTrendSnapshot(timestamp=...)` branch verbatim.
        return snapshot
    state = _daily_context(snapshot.raw_state, weekly, snapshot.prior_up_context, snapshot.bearish_structure)
    if state == snapshot.state:
        return snapshot
    return replace(snapshot, state=state)


def build_daily_raw_trend_timeline(
    frame: pd.DataFrame,
    cfg: StabilTrendConfig,
    *,
    weekly: WeeklyTrendState = WeeklyTrendState.PENDING,
) -> tuple[DailyTrendSnapshot, ...]:
    """Single-pass causal daily timeline preserving exact `05_stabil.txt` math."""
    if frame.empty:
        return ()
    atr = _atr(frame)
    ema = _ema(frame["close"], cfg.daily_ema_len)
    tr_vals = _true_ranges(frame)
    atr5 = _rma(tr_vals, 5)
    atr20 = _rma(tr_vals, 20)
    volume_avg = frame["volume"].astype(float).rolling(20).mean()
    positive_share = (frame["volume"].fillna(0).astype(float) > 0).astype(float).rolling(20).mean()
    acceptance_series = (frame["close"].astype(float) > ema).astype(float).rolling(cfg.acceptance_len).mean()
    highs, lows = _confirmed_pivots(frame, cfg.daily_pivot_len, atr)
    pull_origin: float | None = None
    pull_origin_index: int | None = None
    pull_start: int | None = None
    pull_ref_atr: float | None = None
    gap_start: int | None = None
    last_above_support: int | None = None
    last_snapshot = DailyTrendSnapshot()
    prev_provisional = False
    h_pos = 0
    l_pos = 0
    out: list[DailyTrendSnapshot] = []
    for i in range(len(frame)):
        while h_pos < len(highs) and highs[h_pos].known_index <= i:
            h_pos += 1
        while l_pos < len(lows) and lows[l_pos].known_index <= i:
            l_pos += 1
        enough = h_pos >= 2 and l_pos >= 2
        atr_i = atr[i]
        acceptance = None if pd.isna(acceptance_series.iloc[i]) else float(acceptance_series.iloc[i])
        history_ready = i > max(cfg.daily_ema_len + cfg.slope_lookback, cfg.pullback_lookback) + cfg.daily_pivot_len * 8
        ema_past = float(ema.iloc[i - cfg.slope_lookback]) if i >= cfg.slope_lookback else None
        data_ready = history_ready and enough and atr_i is not None and ema_past is not None and acceptance is not None
        if not enough:
            last_snapshot = DailyTrendSnapshot(timestamp=frame.iloc[i].timestamp)
            out.append(last_snapshot)
            continue
        lh, ph, ll, pl = highs[h_pos - 1], highs[h_pos - 2], lows[l_pos - 1], lows[l_pos - 2]
        usable = data_ready and lh.origin_index > ph.origin_index and ll.origin_index > pl.origin_index
        alternating = usable and _alternates(lh, ph, ll, pl)
        spacing = usable and lh.origin_index - ph.origin_index >= cfg.daily_pivot_len * 2 and ll.origin_index - pl.origin_index >= cfg.daily_pivot_len * 2
        excursion = alternating and abs(lh.price - ll.price) / max((lh.atr_at_origin + ll.atr_at_origin) * 0.5, cfg.min_tick) >= 0.75 and abs(ph.price - pl.price) / max((ph.atr_at_origin + pl.atr_at_origin) * 0.5, cfg.min_tick) >= 0.75
        support_age = i - ll.origin_index if usable else None
        support_fresh = usable and support_age is not None and support_age <= cfg.pullback_lookback * 3
        quality = usable and spacing and excursion and support_fresh
        slope = _normalized_slope(float(ema.iloc[i]), ema_past, float(atr_i), cfg.slope_lookback) if data_ready and atr_i else None
        hh, hl = usable and lh.price > ph.price, usable and ll.price > pl.price
        lower_h, lower_l = usable and lh.price < ph.price, usable and ll.price < pl.price
        floor = ll.price - ll.atr_at_origin * cfg.support_atr_tolerance if usable else None
        below = bool(usable and floor is not None and float(frame.iloc[i].close) < floor)
        if not below:
            last_above_support = i
        if usable and floor is not None and i > 0:
            prev_floor = last_snapshot.support_floor if last_snapshot.support_floor is not None else floor
            gap_started = float(frame.iloc[i].open) < floor and float(frame.iloc[i - 1].close) >= prev_floor and abs(float(frame.iloc[i].open) - float(frame.iloc[i - 1].close)) >= float(atr_i) * 0.20
            if gap_started:
                gap_start = i
        gap_active = gap_start is not None and i - gap_start <= 2
        start = max(0, i - 4)
        red_indices = [j for j in range(start, i + 1) if float(frame.iloc[j].close) < float(frame.iloc[j].open) and atr[j] is not None]
        down_body_atr = sum(abs(float(frame.iloc[j].close) - float(frame.iloc[j].open)) / float(atr[j]) for j in red_indices) / len(red_indices) if red_indices else 0.0
        red_share = len(red_indices) / min(5.0, float(i + 1))
        vol_usable = i >= 19 and not pd.isna(volume_avg.iloc[i]) and float(volume_avg.iloc[i]) > 0 and not pd.isna(positive_share.iloc[i]) and float(positive_share.iloc[i]) >= 0.50
        sell_start = max(0, i - 7)
        sell_vols = [float(frame.iloc[j].volume) for j in range(sell_start, i + 1) if float(frame.iloc[j].close) < float(frame.iloc[j].open) and vol_usable]
        sell_factor = (sum(sell_vols) / len(sell_vols)) / float(volume_avg.iloc[i]) if sell_vols and vol_usable else 1.0
        sell_share = len(sell_vols) / min(8.0, float(i + 1))
        expansion_count = 0.0
        for j in range(max(1, i - 3), i + 1):
            if atr[j] is not None and float(frame.iloc[j].close) < float(frame.iloc[j].open) and abs(float(frame.iloc[j].close) - float(frame.iloc[j].open)) > float(atr[j]) * 0.85 and float(frame.iloc[j].close) < float(frame.iloc[j - 1].low):
                expansion_count += 1.0
        down_composite = down_body_atr * red_share
        sell_composite = sell_factor * sell_share if vol_usable else 1.0
        uncontrolled = data_ready and expansion_count >= 2 and down_composite > 0.55 and red_share >= 0.60
        heavy = data_ready and vol_usable and sell_composite > 1.25 and red_share >= 0.55
        selling_continues = data_ready and (i > 0 and float(frame.iloc[i].close) < float(frame.iloc[i - 1].close) or uncontrolled or heavy)
        bars_since_above = i - last_above_support if last_above_support is not None else i + 1
        gap_confirmed = below and gap_active and bars_since_above >= 2 and selling_continues
        direct_break = below and not gap_active
        gap_watch = below and gap_active and not gap_confirmed
        gap_reclaimed = bool(usable and floor is not None and float(frame.iloc[i].close) >= floor and gap_start is not None and i - gap_start <= 2)
        support_broken = direct_break or gap_confirmed
        recent_start = max(0, i - cfg.pullback_lookback + 1)
        recent_slice = frame.iloc[recent_start : i + 1]
        recent_high = float(recent_slice["high"].max())
        recent_origin = int(recent_slice["high"].astype(float).idxmax())
        provisional_depth = _safe_div(recent_high - float(frame.iloc[i].close), float(atr_i)) if data_ready and atr_i else None
        provisional = bool(data_ready and usable and not support_broken and provisional_depth is not None and provisional_depth > 0.60)
        if provisional and not prev_provisional and atr_i is not None:
            pull_origin, pull_origin_index, pull_start, pull_ref_atr = recent_high, recent_origin, i, float(atr_i)
        prev_provisional = provisional
        if pull_origin is not None and (float(frame.iloc[i].close) >= pull_origin or support_broken):
            pull_origin = pull_origin_index = pull_start = pull_ref_atr = None
        active = pull_origin is not None and pull_origin_index is not None and pull_start is not None and pull_ref_atr is not None
        depth = _safe_div(float(pull_origin) - float(frame.iloc[i].close), pull_ref_atr) if active else provisional_depth
        pull_bars = max(i - int(pull_start), 0) if active else 0
        support_held = bool(usable and not support_broken and not gap_watch)
        low_support_atr = _safe_div(float(frame.iloc[i].low) - ll.price, float(atr_i)) if usable and atr_i else None
        prolonged = data_ready and pull_bars > cfg.max_pullback_bars
        pull_active = bool(data_ready and active and depth is not None and depth > 0.60 and not support_broken)
        advancing = bool(data_ready and usable and quality and float(frame.iloc[i].close) > float(ema.iloc[i]) and slope is not None and slope > 0.10 and acceptance is not None and acceptance >= 0.625 and (hh or lh.price >= ph.price) and support_held)
        controlled = bool(data_ready and usable and quality and pull_active and support_held and depth is not None and depth <= cfg.healthy_depth_atr and not uncontrolled and not heavy and not prolonged)
        compression = _safe_div(float(atr5[i]), float(atr20[i])) if atr5[i] is not None and atr20[i] is not None else None
        basing = bool(data_ready and usable and quality and pull_active and support_held and pull_bars >= 5 and compression is not None and compression < 0.85 and slope is not None and abs(slope) <= 0.18 and not uncontrolled)
        stretch = _safe_div(float(frame.iloc[i].close) - float(ema.iloc[i]), float(atr_i)) if atr_i else None
        parabolic = bool(data_ready and usable and quality and hh and hl and float(frame.iloc[i].close) > float(ema.iloc[i]) and slope is not None and slope > 0.35 and stretch is not None and stretch > 4.0)
        validated = bool(data_ready and usable and quality and hh and hl and support_held and slope is not None and slope > 0.08 and acceptance is not None and acceptance >= 0.60)
        prior_validated = validated or (last_snapshot.prior_up_context and not support_broken and not lower_l)
        bearish = bool(data_ready and usable and (lower_h or lower_l or (slope is not None and slope < -0.05)) and not validated)
        gap = GapState.CONFIRMED if gap_confirmed else GapState.WATCH if gap_watch else GapState.RECLAIMED if gap_reclaimed else GapState.NONE
        raw = DailyRawState.PENDING
        if data_ready:
            if not usable:
                raw = DailyRawState.NEUTRAL
            elif support_broken:
                raw = DailyRawState.STRUCTURE_BROKEN
            elif gap_watch:
                raw = DailyRawState.GAP_WATCH
            elif uncontrolled or (heavy and depth is not None and depth > cfg.healthy_depth_atr):
                raw = DailyRawState.DISTRIBUTION
            elif parabolic:
                raw = DailyRawState.PARABOLIC
            elif (depth is not None and depth >= cfg.deep_depth_atr) or (prolonged and not hl):
                raw = DailyRawState.TOO_DEEP
            elif advancing:
                raw = DailyRawState.ADVANCE
            elif basing:
                raw = DailyRawState.BALANCE
            elif controlled:
                raw = DailyRawState.PULLBACK
            else:
                raw = DailyRawState.NEUTRAL
        state = _daily_context(raw, weekly, prior_validated, bearish)
        last_snapshot = DailyTrendSnapshot(
            frame.iloc[i].timestamp,
            data_ready,
            usable,
            quality,
            alternating,
            support_fresh,
            support_held,
            vol_usable,
            raw,
            state,
            ll.price if usable else None,
            floor,
            support_age,
            gap,
            pull_start,
            frame.iloc[pull_start].timestamp if pull_start is not None else None,
            pull_origin,
            pull_origin_index,
            pull_ref_atr,
            depth,
            pull_bars,
            slope,
            acceptance,
            down_body_atr,
            red_share,
            sell_factor,
            expansion_count,
            compression,
            low_support_atr,
            hh,
            hl,
            lower_h,
            lower_l,
            uncontrolled,
            heavy,
            support_broken,
            prior_validated,
            bearish,
        )
        out.append(last_snapshot)
    return tuple(out)


def _daily_snapshot(frame: pd.DataFrame, weekly: WeeklyTrendState, cfg: StabilTrendConfig) -> DailyTrendSnapshot:
    if frame.empty:
        return DailyTrendSnapshot()
    return build_daily_raw_trend_timeline(frame, cfg, weekly=weekly)[-1]


def _true_ranges(frame: pd.DataFrame) -> list[float]:
    out: list[float] = []
    for i, row in frame.iterrows():
        h, l = float(row.high), float(row.low)
        if i == 0:
            out.append(h - l)
        else:
            pc = float(frame.iloc[i - 1].close)
            out.append(max(h - l, abs(h - pc), abs(l - pc)))
    return out


def build_h4_trend_timeline(frame: pd.DataFrame, cfg: StabilTrendConfig) -> tuple[H4TrendSnapshot, ...]:
    """Single-pass causal H4 timeline preserving exact `05_stabil.txt` math."""
    if frame.empty:
        return ()
    atr = _atr(frame)
    ema = _ema(frame["close"], cfg.h4_fast_ema_len)
    bodies = (frame["close"].astype(float) - frame["open"].astype(float)).abs()
    body_avg = bodies.rolling(12).mean()
    acceptance_series = (frame["close"].astype(float) > ema).astype(float).rolling(5).mean()
    volume_avg = frame["volume"].astype(float).rolling(20).mean()
    positive_share = (frame["volume"].fillna(0).astype(float) > 0).astype(float).rolling(20).mean()
    _, lows = _confirmed_pivots(frame, cfg.h4_micro_pivot_len, atr)
    lifecycle = H4Lifecycle.NO_EVENT
    event_i = recovery_i = failure_i = None
    event_low = event_mid = None
    invalidation_i = None
    seller_weak_indices: list[int] = []
    l_pos = 0
    out: list[H4TrendSnapshot] = []
    for i in range(len(frame)):
        while l_pos < len(lows) and lows[l_pos].known_index <= i:
            l_pos += 1
        atr_i = atr[i]
        acceptance = None if pd.isna(acceptance_series.iloc[i]) else float(acceptance_series.iloc[i])
        history_ready = i > cfg.h4_fast_ema_len + cfg.h4_micro_pivot_len * 8 + 24
        data_ready = history_ready and atr_i is not None and not pd.isna(body_avg.iloc[i]) and acceptance is not None and i >= 3
        row = frame.iloc[i]
        body = abs(float(row.close) - float(row.open))
        candle_range = float(row.high) - float(row.low)
        close_loc = (float(row.close) - float(row.low)) / candle_range if candle_range > cfg.min_tick * 0.10 else 0.50
        lower_wick = min(float(row.open), float(row.close)) - float(row.low)
        lower_wick_ratio = lower_wick / candle_range if candle_range > cfg.min_tick * 0.10 else 0.0
        vol_usable = i >= 19 and not pd.isna(volume_avg.iloc[i]) and float(volume_avg.iloc[i]) > 0 and not pd.isna(positive_share.iloc[i]) and float(positive_share.iloc[i]) >= 0.50
        buyer_vol_factor = float(row.volume) / float(volume_avg.iloc[i]) if vol_usable else 1.0
        volume_pass = not vol_usable or buyer_vol_factor >= 1.0
        buyer_body = body if float(row.close) > float(row.open) else 0.0
        buyer_body_atr = _safe_div(buyer_body, float(atr_i)) if atr_i else None
        buyer_body_avg_ratio = _safe_div(buyer_body, float(body_avg.iloc[i])) if not pd.isna(body_avg.iloc[i]) else None
        bull_displacement = bool(data_ready and float(row.close) > float(row.open) and body > float(body_avg.iloc[i]) * cfg.displacement_factor and buyer_body >= float(atr_i) * 0.45 and close_loc >= 0.70 and volume_pass)
        last_pivot = lows[l_pos - 1] if l_pos >= 1 else None
        prev_pivot = lows[l_pos - 2] if l_pos >= 2 else None
        micro_hl = bool(last_pivot and prev_pivot and last_pivot.origin_index > prev_pivot.origin_index and last_pivot.price > prev_pivot.price)
        current_seller = float(row.close) < float(row.open)
        seller_shrinking_raw = False
        if current_seller:
            previous = [j for j in seller_weak_indices if i - j <= 8][-3:]
            if len(previous) >= 2:
                avg_prev = sum(abs(float(frame.iloc[j].close) - float(frame.iloc[j].open)) for j in previous) / len(previous)
                body_shrink = body < avg_prev * 0.72
                wick_e = lower_wick_ratio >= 0.22
                no_fresh_low = i >= 3 and float(row.low) >= float(frame.iloc[i - 3 : i]["low"].min())
                close_recovery = close_loc >= 0.45
                seller_shrinking_raw = body_shrink and (wick_e or no_fresh_low or close_recovery)
            seller_weak_indices.append(i)
        sellers_shrinking = seller_shrinking_raw or any(i - j <= 2 for j in seller_weak_indices if j < i and j >= 0)
        recovery_age_before = i - recovery_i if recovery_i is not None else None
        candidate_active = lifecycle in {H4Lifecycle.DISPLACEMENT_ACTIVE, H4Lifecycle.BUYERS_EMERGING}
        old_recovery_renewable = lifecycle == H4Lifecycle.RECOVERY_CONFIRMED and recovery_age_before is not None and recovery_age_before > cfg.h4_evidence_fresh_bars
        can_start = bull_displacement and (lifecycle == H4Lifecycle.NO_EVENT or lifecycle == H4Lifecycle.RECOVERY_FAILED and failure_i is not None and i > failure_i or old_recovery_renewable)
        if data_ready:
            if can_start:
                event_i, event_low, event_mid = i, float(row.low), (float(row.open) + float(row.close)) * 0.5
                recovery_i = invalidation_i = failure_i = None
                lifecycle = H4Lifecycle.DISPLACEMENT_ACTIVE
            else:
                event_age = i - event_i if event_i is not None else None
                recovery_age = i - recovery_i if recovery_i is not None else None
                failure_age = i - failure_i if failure_i is not None else None
                event_within = event_age is not None and event_age <= cfg.h4_evidence_fresh_bars * 2
                micro_for_event = bool(micro_hl and event_i is not None and last_pivot and last_pivot.origin_index >= event_i)
                follow = bool(event_within and event_mid is not None and i > int(event_i) and float(row.close) > event_mid and float(row.close) > float(ema.iloc[i]) and float(ema.iloc[i]) > float(ema.iloc[i - 3]) and acceptance is not None and acceptance >= 0.60 and float(row.close) >= float(frame.iloc[i - 1].close) and micro_for_event)
                if candidate_active:
                    if not event_within:
                        lifecycle, event_i, event_low, event_mid, recovery_i, invalidation_i, failure_i = H4Lifecycle.NO_EVENT, None, None, None, None, None, None
                    elif event_low is not None and float(row.close) < event_low:
                        invalidation_i = failure_i = i
                        lifecycle = H4Lifecycle.RECOVERY_FAILED
                    elif follow:
                        recovery_i = i
                        lifecycle = H4Lifecycle.RECOVERY_CONFIRMED
                    else:
                        lifecycle = H4Lifecycle.BUYERS_EMERGING
                elif lifecycle == H4Lifecycle.RECOVERY_CONFIRMED:
                    if event_low is not None and float(row.close) < event_low:
                        invalidation_i = failure_i = i
                        lifecycle = H4Lifecycle.RECOVERY_FAILED
                    elif recovery_age is not None and recovery_age > cfg.h4_evidence_fresh_bars * 2:
                        lifecycle, event_i, event_low, event_mid, recovery_i, invalidation_i, failure_i = H4Lifecycle.NO_EVENT, None, None, None, None, None, None
                elif lifecycle == H4Lifecycle.RECOVERY_FAILED and failure_age is not None and failure_age > cfg.h4_evidence_fresh_bars:
                    lifecycle, event_i, event_low, event_mid, recovery_i, invalidation_i, failure_i = H4Lifecycle.NO_EVENT, None, None, None, None, None, None
        event_age = i - event_i if event_i is not None else None
        recovery_age = i - recovery_i if recovery_i is not None else None
        failure_age = i - failure_i if failure_i is not None else None
        retained = lifecycle == H4Lifecycle.RECOVERY_CONFIRMED and recovery_age is not None and recovery_age <= cfg.h4_evidence_fresh_bars * 2
        recovery_valid = bool(retained and event_mid is not None and float(row.close) > event_mid and float(row.close) > float(ema.iloc[i]))
        active_emergence = lifecycle in {H4Lifecycle.DISPLACEMENT_ACTIVE, H4Lifecycle.BUYERS_EMERGING} and event_age is not None and event_age <= cfg.h4_evidence_fresh_bars
        recent_failure = lifecycle == H4Lifecycle.RECOVERY_FAILED and failure_age is not None and failure_age <= cfg.h4_evidence_fresh_bars
        state = H4TrendState.PENDING
        if data_ready:
            state = H4TrendState.RECOVERY_FAILED if recent_failure else H4TrendState.RECOVERY_CONFIRMED if recovery_valid else H4TrendState.BUYERS_EMERGING if active_emergence else H4TrendState.SELLING_WEAKENING if sellers_shrinking else H4TrendState.NO_RECOVERY
        close_ema_atr = _safe_div(float(row.close) - float(ema.iloc[i]), float(atr_i)) if atr_i else None
        out.append(
            H4TrendSnapshot(
                row.timestamp,
                data_ready,
                vol_usable,
                state,
                lifecycle,
                event_i,
                frame.iloc[event_i].timestamp if event_i is not None else None,
                event_low,
                event_mid,
                recovery_i,
                frame.iloc[recovery_i].timestamp if recovery_i is not None else None,
                invalidation_i,
                frame.iloc[invalidation_i].timestamp if invalidation_i is not None else None,
                event_age,
                recovery_age,
                failure_age,
                last_pivot,
                bull_displacement,
                micro_hl,
                sellers_shrinking,
                close_loc,
                acceptance,
                buyer_vol_factor,
                volume_pass,
                buyer_body_atr,
                buyer_body_avg_ratio,
                close_ema_atr,
                recovery_valid,
                active_emergence,
                recent_failure,
            )
        )
    return tuple(out)


def _h4_snapshot(frame: pd.DataFrame, cfg: StabilTrendConfig) -> H4TrendSnapshot:
    if frame.empty:
        return H4TrendSnapshot()
    return build_h4_trend_timeline(frame, cfg)[-1]


def _h4_evidence(daily: DailyTrendSnapshot, h4: H4TrendSnapshot, cfg: StabilTrendConfig) -> H4EvidenceStatus:
    correction = daily.state in {DailyTrendState.CONTROLLED_PULLBACK, DailyTrendState.BASE_BUILDING}
    if not correction or daily.pullback_start_time is None or not h4.data_ready:
        return H4EvidenceStatus.NONE
    after = h4.recovery_time is not None and h4.recovery_time >= daily.pullback_start_time
    pre_fail = h4.lifecycle == H4Lifecycle.RECOVERY_FAILED and h4.recovery_time is None and h4.invalidation_time is not None and h4.event_time is not None and h4.event_time >= daily.pullback_start_time and h4.invalidation_time >= h4.event_time
    confirmed_fail = h4.lifecycle == H4Lifecycle.RECOVERY_FAILED and h4.recovery_time is not None and h4.invalidation_time is not None and h4.recovery_time >= daily.pullback_start_time and h4.invalidation_time > h4.recovery_time
    if pre_fail:
        return H4EvidenceStatus.ATTEMPT_FAILED
    if confirmed_fail:
        return H4EvidenceStatus.FAILED
    if after and h4.lifecycle == H4Lifecycle.RECOVERY_CONFIRMED and h4.recovery_age is not None:
        if h4.recovery_age <= cfg.h4_evidence_fresh_bars:
            return H4EvidenceStatus.FRESH
        if h4.recovery_age <= cfg.h4_evidence_fresh_bars * 2:
            return H4EvidenceStatus.OLD
    return H4EvidenceStatus.NONE


def compose_trend_context(
    weekly_snapshot: WeeklyTrendSnapshot,
    daily_raw_snapshot: DailyTrendSnapshot,
    h4_snapshot: H4TrendSnapshot,
    cfg: StabilTrendConfig,
    *,
    as_of: Any | None = None,
) -> StabilTrendContext:
    """Compose a full causal `StabilTrendContext` from role snapshots without altering math."""
    daily_snapshot = recontextualize_daily_snapshot(daily_raw_snapshot, weekly_snapshot.state)
    evidence = _h4_evidence(daily_snapshot, h4_snapshot, cfg)
    candidates = [x for x in (weekly_snapshot.timestamp, daily_snapshot.timestamp, h4_snapshot.timestamp) if x is not None]
    context_as_of = max(candidates) if candidates else as_of
    return StabilTrendContext(context_as_of, weekly_snapshot, daily_snapshot, h4_snapshot, evidence)


class StabilTrendEngine:
    """Tur-1 MTF trend-health foundation from the supplied Stabil Yükseliş Pine.

    This class intentionally stops before the final MAIN_* resolver and score layer;
    Tur-2 owns final state, health/risk scoring, export and live-smoke integration.
    """

    def __init__(self, config: StabilTrendConfig | None = None) -> None:
        self.config = config or StabilTrendConfig()
        self._snapshot: StabilTrendContext | None = None

    def analyze(self, weekly: pd.DataFrame, daily: pd.DataFrame, h4: pd.DataFrame, *, as_of: Any | None = None) -> StabilTrendContext:
        w = _clean(weekly, as_of)
        d = _clean(daily, as_of)
        h = _clean(h4, as_of)
        weekly_snapshot = _weekly_snapshot(w, self.config)
        daily_snapshot = _daily_snapshot(d, weekly_snapshot.state, self.config)
        h4_snapshot = _h4_snapshot(h, self.config)
        evidence = _h4_evidence(daily_snapshot, h4_snapshot, self.config)
        candidates = [x for x in (weekly_snapshot.timestamp, daily_snapshot.timestamp, h4_snapshot.timestamp) if x is not None]
        context_as_of = max(candidates) if candidates else as_of
        self._snapshot = StabilTrendContext(context_as_of, weekly_snapshot, daily_snapshot, h4_snapshot, evidence)
        return self._snapshot

    def snapshot(self) -> StabilTrendContext | None:
        return self._snapshot
