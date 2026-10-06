from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import math
import pandas as pd

from .fvg_engulfing_models import (
    ATR_LENGTH,
    ENGULFING_DEEP_RETRACE_THRESHOLD,
    ENGULFING_PARTIAL_RETRACE_THRESHOLD,
    FLOW_LENGTH,
    FVG_CANDIDATE_QUALITY_OFFSET,
    FVG_CANDIDATE_SIZE_FACTOR,
    FVG_DISPLACEMENT_EXTRA_FACTOR,
    FVG_PROGRESS_EXTRA_FACTOR,
    FVG_SIZE_EXTRA_FACTOR,
    FvgDirection,
    FvgEngulfingConfig,
    FvgEngulfingDataQuality,
    FvgState,
    EngulfingDirection,
    EngulfingState,
    LOCAL_CONTEXT_LENGTH,
    MINIMUM_HISTORY_BARS,
    SensitivityProfile,
)
from .models import Direction, EngineResult


# Source constants that are detector-internal only. They are deliberately not
# exported as a separate candle/story engine.
DOJI_BODY_SHARE = 0.12
DOJI_BODY_ATR = 0.08
PREVIOUS_ZONE_UPPER_SHARE = 0.70
PREVIOUS_ZONE_LOWER_SHARE = 0.30
RETENTION_CLOSE_FLOOR = 0.55
RETENTION_CLOSE_OFFSET = 0.12
RETENTION_EFFICIENCY_FACTOR = 0.60
CONFLICT_PROGRESS_FACTOR = 0.25
SHOCK_CLOSE_UPPER = 0.65
SHOCK_CLOSE_LOWER = 0.35
SHOCK_MIDDLE_LOW = 0.35
SHOCK_MIDDLE_HIGH = 0.65
SHOCK_DIRECTIONLESS_BODY_SHARE = 0.35
SHOCK_DIRECTIONLESS_WICK_SHARE = 0.20
SHOCK_JUMP_FACTOR = 1.25
LARGE_GAP_REAL_PROGRESS_FACTOR = 0.80
LARGE_GAP_BREAK_ATR = 0.10
VERY_STRONG_ENGULFING_FACTOR = 1.35
VERY_STRONG_ENGULFING_RATIO_FACTOR = 1.15
ENGULFING_NEUTRAL_FLOW_FACTOR = 0.25
REJECTION_CONFLICT_MARGIN = 1.15


@dataclass(frozen=True, slots=True)
class FvgFormation:
    direction: FvgDirection
    state: FvgState
    formation_index: int
    timestamp: Any
    lower_boundary: float
    upper_boundary: float
    gap_size: float
    gap_atr: float
    formation_atr: float
    quality: float
    embedded_candle_contribution: float
    evidence_count: int


@dataclass(frozen=True, slots=True)
class EngulfingFormation:
    direction: EngulfingDirection
    state: EngulfingState
    formation_index: int
    timestamp: Any
    lower_boundary: float
    upper_boundary: float
    body_size: float
    body_atr: float
    formation_atr: float
    quality: float


@dataclass(frozen=True, slots=True)
class FormationSnapshot:
    bullish_fvg_candidate: bool = False
    bearish_fvg_candidate: bool = False
    bullish_fvg_active: bool = False
    bearish_fvg_active: bool = False
    bullish_engulfing: bool = False
    bearish_engulfing: bool = False
    bullish_fvg_quality: float = 0.0
    bearish_fvg_quality: float = 0.0
    bullish_engulfing_quality: float = 0.0
    bearish_engulfing_quality: float = 0.0


@dataclass(slots=True)
class _Thresholds:
    minimum_continuation_body_atr: float
    minimum_continuation_body_share: float
    minimum_continuation_efficiency: float
    minimum_continuation_progress_atr: float
    minimum_continuation_close_location: float
    maximum_opposing_wick_body: float
    continuation_evidence_minimum: int
    continuation_confirmation_bars: int
    minimum_engulfing_body_atr: float
    minimum_previous_body_atr: float
    minimum_engulfing_body_ratio: float
    engulfing_close_location: float
    maximum_engulfing_gap_atr: float
    minimum_rejection_wick_body: float
    minimum_rejection_wick_atr: float
    rejection_close_location: float
    minimum_wick_dominance: float
    shock_range_atr: float
    shock_body_atr: float
    minimum_fvg_size_atr: float
    minimum_displacement_body_atr: float
    minimum_displacement_body_share: float
    minimum_displacement_close_location: float
    minimum_fvg_progress_atr: float
    minimum_fvg_efficiency: float
    maximum_fvg_opening_gap_atr: float
    minimum_fvg_evidence: int
    minimum_fvg_quality: float


def _thresholds(profile: SensitivityProfile) -> _Thresholds:
    if profile is SensitivityProfile.SENSITIVE:
        return _Thresholds(
            0.35, 0.48, 0.45, 0.35, 0.62, 1.20, 5, 2,
            0.35, 0.10, 1.05, 0.62, 0.90,
            1.50, 0.25, 0.58, 1.15,
            2.20, 1.40,
            0.10, 0.35, 0.50, 0.62, 0.30, 0.42, 0.90, 6, 45.0,
        )
    if profile is SensitivityProfile.BALANCED:
        return _Thresholds(
            0.45, 0.55, 0.52, 0.50, 0.68, 0.95, 6, 2,
            0.45, 0.14, 1.15, 0.68, 0.75,
            1.80, 0.32, 0.64, 1.30,
            2.35, 1.55,
            0.15, 0.45, 0.58, 0.68, 0.45, 0.50, 0.75, 7, 55.0,
        )
    return _Thresholds(
        0.55, 0.62, 0.60, 0.65, 0.74, 0.75, 7, 3,
        0.55, 0.18, 1.25, 0.74, 0.60,
        2.10, 0.40, 0.70, 1.45,
        2.50, 1.70,
        0.22, 0.55, 0.65, 0.74, 0.60, 0.58, 0.60, 8, 65.0,
    )


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _safe_div(numerator: float, denominator: float, fallback: float, minimum_tick: float) -> float:
    floor = max(1e-10, abs(minimum_tick) * 0.000001)
    if not math.isfinite(numerator) or not math.isfinite(denominator) or abs(denominator) <= floor:
        return fallback
    return numerator / denominator


def _ratio_score(value: float, target: float, minimum_tick: float) -> float:
    return _clamp(_safe_div(value, target, 0.0, minimum_tick) * 100.0, 0.0, 100.0)


def _rma(values: list[float | None], length: int) -> list[float | None]:
    """Pine-style RMA seed: SMA of first `length` valid values, then Wilder update.

    A None input breaks the recursive source chain; a fresh seed requires a new
    contiguous run of `length` valid values. This is Python's source-gap safety
    boundary and does not fabricate missing bars.
    """
    out: list[float | None] = [None] * len(values)
    run: list[float] = []
    prev: float | None = None
    for i, value in enumerate(values):
        if value is None or not math.isfinite(value):
            run = []
            prev = None
            continue
        if prev is None:
            run.append(value)
            if len(run) < length:
                continue
            if len(run) > length:
                run = run[-length:]
            prev = sum(run) / length
            out[i] = prev
        else:
            prev = (prev * (length - 1) + value) / length
            out[i] = prev
    return out


class FvgEngulfingEngine:
    """Tur-1 source-faithful FVG/Engulfing detector + immutable formations.

    No lifecycle/takeover/export logic is implemented here; those remain Tur-2.
    Internal candle/flow evidence exists only because v0.3.8 detector math uses
    it. It is not surfaced as a separate production signal.
    """

    def __init__(self, config: FvgEngulfingConfig | None = None) -> None:
        self.config = config or FvgEngulfingConfig()
        self._thresholds = _thresholds(self.config.sensitivity)
        self._rows: list[dict[str, Any]] = []
        self._valid: list[bool] = []
        self._fvg_formations: list[FvgFormation] = []
        self._engulfing_formations: list[EngulfingFormation] = []
        self._snapshot = FormationSnapshot()
        self._last_data_quality = FvgEngulfingDataQuality.WARMUP

    @property
    def fvg_formations(self) -> tuple[FvgFormation, ...]:
        return tuple(self._fvg_formations)

    @property
    def engulfing_formations(self) -> tuple[EngulfingFormation, ...]:
        return tuple(self._engulfing_formations)

    @property
    def snapshot(self) -> FormationSnapshot:
        return self._snapshot

    @property
    def last_data_quality(self) -> FvgEngulfingDataQuality:
        return self._last_data_quality

    def reset(self) -> None:
        self._rows.clear()
        self._valid.clear()
        self._fvg_formations.clear()
        self._engulfing_formations.clear()
        self._snapshot = FormationSnapshot()
        self._last_data_quality = FvgEngulfingDataQuality.WARMUP

    def replay(self, frame: pd.DataFrame) -> list[EngineResult | None]:
        self.reset()
        return [self.update(row._asdict()) for row in frame.itertuples(index=False)]

    def update(self, bar: pd.Series | dict[str, Any]) -> EngineResult | None:
        row = dict(bar)
        if not bool(row.get("is_closed", True)):
            self._last_data_quality = FvgEngulfingDataQuality.INCOMPLETE_BAR
            return self._result(row.get("timestamp"), confirmed=False)

        complete = bool(row.get("is_complete", True))
        normalized = self._normalize_row(row)
        self._rows.append(normalized)
        self._valid.append(complete)

        if not complete:
            self._snapshot = FormationSnapshot()
            self._last_data_quality = FvgEngulfingDataQuality.SOURCE_GAP
            return self._result(normalized["timestamp"], confirmed=False)

        metrics = self._calculate_series()
        current = metrics[-1]
        if not current["data_ready"]:
            self._snapshot = FormationSnapshot()
            self._last_data_quality = FvgEngulfingDataQuality.WARMUP
            return self._result(normalized["timestamp"])

        self._snapshot = FormationSnapshot(
            bullish_fvg_candidate=current["bullish_fvg_candidate"],
            bearish_fvg_candidate=current["bearish_fvg_candidate"],
            bullish_fvg_active=current["bullish_fvg_active"],
            bearish_fvg_active=current["bearish_fvg_active"],
            bullish_engulfing=current["bullish_engulfing"],
            bearish_engulfing=current["bearish_engulfing"],
            bullish_fvg_quality=current["bullish_fvg_quality"],
            bearish_fvg_quality=current["bearish_fvg_quality"],
            bullish_engulfing_quality=current["bullish_engulfing_quality"],
            bearish_engulfing_quality=current["bearish_engulfing_quality"],
        )
        self._capture_formations(current, normalized)
        self._last_data_quality = FvgEngulfingDataQuality.OK
        return self._result(normalized["timestamp"])

    def _normalize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "timestamp": row.get("timestamp"),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row.get("volume", 0.0)),
        }

    def _result(self, timestamp: Any, confirmed: bool = True) -> EngineResult:
        direction = Direction.NEUTRAL
        events: list[str] = []
        qualities: list[float] = []
        s = self._snapshot
        if s.bullish_fvg_active:
            events.append("BULL_FVG_ACTIVE_FORMATION")
            qualities.append(s.bullish_fvg_quality)
            direction = Direction.UP
        elif s.bullish_fvg_candidate:
            events.append("BULL_FVG_CANDIDATE_FORMATION")
            qualities.append(s.bullish_fvg_quality)
            direction = Direction.UP
        if s.bearish_fvg_active:
            events.append("BEAR_FVG_ACTIVE_FORMATION")
            qualities.append(s.bearish_fvg_quality)
            direction = Direction.DOWN if direction is Direction.NEUTRAL else direction
        elif s.bearish_fvg_candidate:
            events.append("BEAR_FVG_CANDIDATE_FORMATION")
            qualities.append(s.bearish_fvg_quality)
            direction = Direction.DOWN if direction is Direction.NEUTRAL else direction
        if s.bullish_engulfing:
            events.append("BULL_ENGULFING_FORMATION")
            qualities.append(s.bullish_engulfing_quality)
        if s.bearish_engulfing:
            events.append("BEAR_ENGULFING_FORMATION")
            qualities.append(s.bearish_engulfing_quality)
        return EngineResult(
            engine="fvg_engulfing",
            state=self._last_data_quality.value,
            timestamp=timestamp,
            direction=direction,
            quality=max(qualities) if qualities else None,
            events=tuple(events),
            is_confirmed=confirmed,
        )

    def _capture_formations(self, m: dict[str, Any], row: dict[str, Any]) -> None:
        idx = len(self._rows) - 1
        if m["bullish_fvg_active"] or m["bullish_fvg_candidate"]:
            self._fvg_formations.append(FvgFormation(
                FvgDirection.BULLISH,
                FvgState.ACTIVE if m["bullish_fvg_active"] else FvgState.CANDIDATE,
                idx,
                row["timestamp"],
                m["bull_fvg_lower"], m["bull_fvg_upper"], m["bull_fvg_gap_size"],
                m["bull_fvg_gap_atr"], m["formation_atr"], m["bullish_fvg_quality"],
                m["bull_embedded_contribution"], m["bull_fvg_evidence"],
            ))
        if m["bearish_fvg_active"] or m["bearish_fvg_candidate"]:
            self._fvg_formations.append(FvgFormation(
                FvgDirection.BEARISH,
                FvgState.ACTIVE if m["bearish_fvg_active"] else FvgState.CANDIDATE,
                idx,
                row["timestamp"],
                m["bear_fvg_lower"], m["bear_fvg_upper"], m["bear_fvg_gap_size"],
                m["bear_fvg_gap_atr"], m["formation_atr"], m["bearish_fvg_quality"],
                m["bear_embedded_contribution"], m["bear_fvg_evidence"],
            ))
        if m["bullish_engulfing"]:
            self._engulfing_formations.append(EngulfingFormation(
                EngulfingDirection.BULLISH, EngulfingState.ACTIVE, idx, row["timestamp"],
                m["swallowed_lower"], m["swallowed_upper"], m["swallowed_size"],
                m["swallowed_atr"], m["safe_prior_atr"], m["bullish_engulfing_quality"],
            ))
        if m["bearish_engulfing"]:
            self._engulfing_formations.append(EngulfingFormation(
                EngulfingDirection.BEARISH, EngulfingState.ACTIVE, idx, row["timestamp"],
                m["swallowed_lower"], m["swallowed_upper"], m["swallowed_size"],
                m["swallowed_atr"], m["safe_prior_atr"], m["bearish_engulfing_quality"],
            ))

    def _calculate_series(self) -> list[dict[str, Any]]:
        n = len(self._rows)
        mintick = self.config.minimum_tick
        t = self._thresholds

        tr: list[float | None] = []
        for i, r in enumerate(self._rows):
            if not self._valid[i]:
                tr.append(None)
                continue
            prev_close = self._rows[i - 1]["close"] if i > 0 and self._valid[i - 1] else None
            value = r["high"] - r["low"]
            if prev_close is not None:
                value = max(value, abs(r["high"] - prev_close), abs(r["low"] - prev_close))
            tr.append(max(value, 0.0))
        atr = _rma(tr, ATR_LENGTH)

        out: list[dict[str, Any]] = []
        candidate_core_buy = [False] * n
        candidate_core_sell = [False] * n
        candidate_raw_buy = [False] * n
        candidate_raw_sell = [False] * n
        confirmed_buy = [False] * n
        confirmed_sell = [False] * n
        range_to_atr_series = [0.0] * n
        body_to_atr_series = [0.0] * n

        def valid_range(start: int, end: int) -> bool:
            return start >= 0 and all(self._valid[j] for j in range(start, end + 1))

        for i, r in enumerate(self._rows):
            m: dict[str, Any] = {
                "data_ready": False,
                "bullish_fvg_candidate": False, "bearish_fvg_candidate": False,
                "bullish_fvg_active": False, "bearish_fvg_active": False,
                "bullish_engulfing": False, "bearish_engulfing": False,
                "bullish_fvg_quality": 0.0, "bearish_fvg_quality": 0.0,
                "bullish_engulfing_quality": 0.0, "bearish_engulfing_quality": 0.0,
                "bull_fvg_lower": math.nan, "bull_fvg_upper": math.nan,
                "bear_fvg_lower": math.nan, "bear_fvg_upper": math.nan,
                "bull_fvg_gap_size": 0.0, "bear_fvg_gap_size": 0.0,
                "bull_fvg_gap_atr": 0.0, "bear_fvg_gap_atr": 0.0,
                "formation_atr": math.nan, "safe_prior_atr": math.nan,
                "swallowed_lower": math.nan, "swallowed_upper": math.nan,
                "swallowed_size": 0.0, "swallowed_atr": 0.0,
                "bull_embedded_contribution": 0.0, "bear_embedded_contribution": 0.0,
                "bull_fvg_evidence": 0, "bear_fvg_evidence": 0,
            }
            out.append(m)
            if not self._valid[i]:
                continue

            o, h, l, c = r["open"], r["high"], r["low"], r["close"]
            candle_range = max(h - l, 0.0)
            body = abs(c - o)
            upper_wick = max(h - max(o, c), 0.0)
            lower_wick = max(min(o, c) - l, 0.0)
            safe_body = max(body, mintick)
            prior_atr = atr[i - 1] if i > 0 else None
            safe_prior_atr = max(prior_atr if prior_atr is not None else mintick, mintick)
            m["safe_prior_atr"] = safe_prior_atr
            range_to_atr = _safe_div(candle_range, safe_prior_atr, 0.0, mintick)
            body_to_atr = _safe_div(body, safe_prior_atr, 0.0, mintick)
            body_share = _safe_div(body, candle_range, 0.0, mintick)
            close_loc = 0.5 if candle_range <= 1e-10 else _safe_div(c - l, candle_range, 0.5, mintick)
            upper_wick_body = _safe_div(upper_wick, safe_body, 0.0, mintick)
            lower_wick_body = _safe_div(lower_wick, safe_body, 0.0, mintick)
            upper_wick_atr = _safe_div(upper_wick, safe_prior_atr, 0.0, mintick)
            lower_wick_atr = _safe_div(lower_wick, safe_prior_atr, 0.0, mintick)
            gap_abs = abs(o - self._rows[i - 1]["close"]) if i > 0 and self._valid[i - 1] else 0.0
            gap_atr = _safe_div(gap_abs, safe_prior_atr, 0.0, mintick)
            bull = c > o
            bear = c < o
            range_to_atr_series[i] = range_to_atr
            body_to_atr_series[i] = body_to_atr

            flow_ready = valid_range(i - FLOW_LENGTH, i)
            local_ready = valid_range(i - LOCAL_CONTEXT_LENGTH, i - 1)
            compression_ready = valid_range(i - 5, i)
            minimum_history_ready = i >= MINIMUM_HISTORY_BARS - 1
            atr_ready = atr[i] is not None and prior_atr is not None
            previous_ready = i >= 1 and self._valid[i - 1]
            data_ready = minimum_history_ready and atr_ready and previous_ready and flow_ready and compression_ready and local_ready
            imbalance_ready = data_ready and i >= 2 and self._valid[i - 2] and atr[i - 2] is not None
            m["data_ready"] = data_ready
            if not data_ready:
                continue

            green_share = sum(self._rows[j]["close"] > self._rows[j]["open"] for j in range(i - 3, i + 1)) / 4.0
            red_share = sum(self._rows[j]["close"] < self._rows[j]["open"] for j in range(i - 3, i + 1)) / 4.0
            higher_close_share = sum(self._rows[j]["close"] > self._rows[j - 1]["close"] for j in range(i - 3, i + 1)) / 4.0
            lower_close_share = sum(self._rows[j]["close"] < self._rows[j - 1]["close"] for j in range(i - 3, i + 1)) / 4.0
            net_progress = c - self._rows[i - FLOW_LENGTH]["close"]
            net_progress_atr = _safe_div(net_progress, atr[i] or mintick, 0.0, mintick)
            path = sum(abs(self._rows[j]["close"] - self._rows[j - 1]["close"]) for j in range(i - 3, i + 1))
            directional_efficiency = _safe_div(abs(net_progress), path, 0.0, mintick)
            prev_local_high = max(self._rows[j]["high"] for j in range(i - LOCAL_CONTEXT_LENGTH, i))
            prev_local_low = min(self._rows[j]["low"] for j in range(i - LOCAL_CONTEXT_LENGTH, i))
            new_local_high = h >= prev_local_high
            new_local_low = l <= prev_local_low

            primitive_lower = (
                lower_wick_body >= t.minimum_rejection_wick_body and
                lower_wick_atr >= t.minimum_rejection_wick_atr and
                close_loc >= t.rejection_close_location and
                lower_wick >= upper_wick * t.minimum_wick_dominance and
                new_local_low
            )
            primitive_upper = (
                upper_wick_body >= t.minimum_rejection_wick_body and
                upper_wick_atr >= t.minimum_rejection_wick_atr and
                close_loc <= 1.0 - t.rejection_close_location and
                upper_wick >= lower_wick * t.minimum_wick_dominance and
                new_local_high
            )
            strong_buy = bull and body_to_atr >= t.minimum_continuation_body_atr and close_loc >= t.minimum_continuation_close_location and net_progress_atr > 0.0
            strong_sell = bear and body_to_atr >= t.minimum_continuation_body_atr and close_loc <= 1.0 - t.minimum_continuation_close_location and net_progress_atr < 0.0

            prev_range = max(self._rows[i - 1]["high"] - self._rows[i - 1]["low"], 0.0)
            prev_upper_zone = self._rows[i - 1]["low"] + prev_range * PREVIOUS_ZONE_UPPER_SHARE
            prev_lower_zone = self._rows[i - 1]["low"] + prev_range * PREVIOUS_ZONE_LOWER_SHARE

            buy_evidence = [
                bull,
                body_to_atr >= t.minimum_continuation_body_atr,
                body_share >= t.minimum_continuation_body_share,
                close_loc >= t.minimum_continuation_close_location,
                upper_wick_body <= t.maximum_opposing_wick_body,
                net_progress_atr >= t.minimum_continuation_progress_atr,
                directional_efficiency >= t.minimum_continuation_efficiency,
                higher_close_share >= 0.50,
                green_share >= 0.50,
                c > self._rows[i - 1]["close"],
                c >= self._rows[i - 1]["high"] or c >= prev_upper_zone,
            ]
            sell_evidence = [
                bear,
                body_to_atr >= t.minimum_continuation_body_atr,
                body_share >= t.minimum_continuation_body_share,
                close_loc <= 1.0 - t.minimum_continuation_close_location,
                lower_wick_body <= t.maximum_opposing_wick_body,
                net_progress_atr <= -t.minimum_continuation_progress_atr,
                directional_efficiency >= t.minimum_continuation_efficiency,
                lower_close_share >= 0.50,
                red_share >= 0.50,
                c < self._rows[i - 1]["close"],
                c <= self._rows[i - 1]["low"] or c <= prev_lower_zone,
            ]
            buy_veto = primitive_upper or strong_sell
            sell_veto = primitive_lower or strong_buy
            buy_flow_count = sum(buy_evidence[5:])
            sell_flow_count = sum(sell_evidence[5:])
            buy_base = bull and (buy_evidence[1] or buy_evidence[2]) and (buy_evidence[3] or (close_loc >= RETENTION_CLOSE_FLOOR and buy_evidence[4])) and buy_flow_count >= 2 and sum(buy_evidence) >= t.continuation_evidence_minimum and not buy_veto
            sell_base = bear and (sell_evidence[1] or sell_evidence[2]) and (sell_evidence[3] or (close_loc <= 1.0 - RETENTION_CLOSE_FLOOR and sell_evidence[4])) and sell_flow_count >= 2 and sum(sell_evidence) >= t.continuation_evidence_minimum and not sell_veto
            if buy_base and sell_base:
                conflict_threshold = t.minimum_continuation_progress_atr * CONFLICT_PROGRESS_FACTOR
                if net_progress_atr > conflict_threshold:
                    sell_base = False
                elif net_progress_atr < -conflict_threshold:
                    buy_base = False
                else:
                    buy_base = sell_base = False
            candidate_core_buy[i] = buy_base
            candidate_core_sell[i] = sell_base

            extreme = range_to_atr >= t.shock_range_atr or body_to_atr >= t.shock_body_atr
            upper_wick_range = _safe_div(upper_wick, candle_range, 0.0, mintick)
            lower_wick_range = _safe_div(lower_wick, candle_range, 0.0, mintick)
            shock_up = extreme and bull and close_loc >= SHOCK_CLOSE_UPPER and net_progress_atr > 0
            shock_down = extreme and bear and close_loc <= SHOCK_CLOSE_LOWER and net_progress_atr < 0
            shock_directionless = extreme and body_share <= SHOCK_DIRECTIONLESS_BODY_SHARE and upper_wick_range >= SHOCK_DIRECTIONLESS_WICK_SHARE and lower_wick_range >= SHOCK_DIRECTIONLESS_WICK_SHARE and SHOCK_MIDDLE_LOW <= close_loc <= SHOCK_MIDDLE_HIGH
            prior_range_max = max(range_to_atr_series[max(0, i - 3):i], default=0.0)
            prior_body_max = max(body_to_atr_series[max(0, i - 3):i], default=0.0)
            abrupt = range_to_atr >= prior_range_max * SHOCK_JUMP_FACTOR or body_to_atr >= prior_body_max * SHOCK_JUMP_FACTOR
            pre_buy = any(candidate_core_buy[max(0, i - 3):i])
            pre_sell = any(candidate_core_sell[max(0, i - 3):i])
            one_bar_shock = (shock_up and abrupt and not pre_buy) or (shock_down and abrupt and not pre_sell) or (shock_directionless and abrupt and not pre_buy and not pre_sell)
            candidate_raw_buy[i] = buy_base and not one_bar_shock
            candidate_raw_sell[i] = sell_base and not one_bar_shock

            confirm_n = t.continuation_confirmation_bars
            buy_sequence = i >= confirm_n - 1 and all(candidate_raw_buy[i - k] for k in range(confirm_n))
            sell_sequence = i >= confirm_n - 1 and all(candidate_raw_sell[i - k] for k in range(confirm_n))
            buy_retention_close = max(RETENTION_CLOSE_FLOOR, t.minimum_continuation_close_location - RETENTION_CLOSE_OFFSET)
            sell_retention_close = 1.0 - buy_retention_close
            retention_eff = t.minimum_continuation_efficiency * RETENTION_EFFICIENCY_FACTOR
            hard_seller = bear and body_to_atr >= t.minimum_continuation_body_atr and close_loc <= 1.0 - t.minimum_continuation_close_location
            hard_buyer = bull and body_to_atr >= t.minimum_continuation_body_atr and close_loc >= t.minimum_continuation_close_location
            buy_retention = net_progress_atr > 0 and close_loc >= buy_retention_close and directional_efficiency >= retention_eff and not primitive_upper and not hard_seller and not candidate_raw_sell[i]
            sell_retention = net_progress_atr < 0 and close_loc <= sell_retention_close and directional_efficiency >= retention_eff and not primitive_lower and not hard_buyer and not candidate_raw_buy[i]
            confirmed_buy[i] = buy_sequence and buy_retention
            confirmed_sell[i] = sell_sequence and sell_retention
            if confirmed_buy[i] and confirmed_sell[i]:
                conflict_threshold = t.minimum_continuation_progress_atr * CONFLICT_PROGRESS_FACTOR
                if net_progress_atr > conflict_threshold:
                    confirmed_sell[i] = False
                elif net_progress_atr < -conflict_threshold:
                    confirmed_buy[i] = False
                else:
                    confirmed_buy[i] = confirmed_sell[i] = False

            prev_body = abs(self._rows[i - 1]["close"] - self._rows[i - 1]["open"])
            safe_prev_body = max(prev_body, mintick)
            prev_body_atr = _safe_div(prev_body, safe_prior_atr, 0.0, mintick)
            prev_body_range = _safe_div(prev_body, prev_range, 0.0, mintick)
            previous_bull = self._rows[i - 1]["close"] > self._rows[i - 1]["open"]
            previous_bear = self._rows[i - 1]["close"] < self._rows[i - 1]["open"]
            previous_doji = prev_body_range <= DOJI_BODY_SHARE or prev_body_atr <= DOJI_BODY_ATR
            body_ratio = _safe_div(body, safe_prev_body, 0.0, mintick)
            body_progress_ex_gap = max(body - gap_abs, 0.0)
            bull_coverage = o <= self._rows[i - 1]["close"] and c >= self._rows[i - 1]["open"]
            bear_coverage = o >= self._rows[i - 1]["close"] and c <= self._rows[i - 1]["open"]
            bull_large_gap_progress = body_progress_ex_gap >= prev_body * LARGE_GAP_REAL_PROGRESS_FACTOR and c >= self._rows[i - 1]["open"] + safe_prior_atr * LARGE_GAP_BREAK_ATR
            bear_large_gap_progress = body_progress_ex_gap >= prev_body * LARGE_GAP_REAL_PROGRESS_FACTOR and c <= self._rows[i - 1]["open"] - safe_prior_atr * LARGE_GAP_BREAK_ATR
            bull_gap_quality = gap_atr <= t.maximum_engulfing_gap_atr or bull_large_gap_progress
            bear_gap_quality = gap_atr <= t.maximum_engulfing_gap_atr or bear_large_gap_progress
            very_strong_bull_engulf = bull and body_to_atr >= t.minimum_engulfing_body_atr * VERY_STRONG_ENGULFING_FACTOR and body_ratio >= t.minimum_engulfing_body_ratio * VERY_STRONG_ENGULFING_RATIO_FACTOR and close_loc >= t.engulfing_close_location and directional_efficiency >= retention_eff
            very_strong_bear_engulf = bear and body_to_atr >= t.minimum_engulfing_body_atr * VERY_STRONG_ENGULFING_FACTOR and body_ratio >= t.minimum_engulfing_body_ratio * VERY_STRONG_ENGULFING_RATIO_FACTOR and close_loc <= 1.0 - t.engulfing_close_location and directional_efficiency >= retention_eff
            prev_bull_quality = prev_body_atr >= t.minimum_previous_body_atr or very_strong_bear_engulf
            prev_bear_quality = prev_body_atr >= t.minimum_previous_body_atr or very_strong_bull_engulf
            bull_micro = not previous_doji or very_strong_bull_engulf
            bear_micro = not previous_doji or very_strong_bear_engulf
            bull_context = net_progress_atr <= t.minimum_continuation_progress_atr * ENGULFING_NEUTRAL_FLOW_FACTOR or new_local_low or primitive_lower or very_strong_bull_engulf
            bear_context = net_progress_atr >= -t.minimum_continuation_progress_atr * ENGULFING_NEUTRAL_FLOW_FACTOR or new_local_high or primitive_upper or very_strong_bear_engulf
            bull_engulf = previous_bear and bull and bull_coverage and body_to_atr >= t.minimum_engulfing_body_atr and prev_bear_quality and body_ratio >= t.minimum_engulfing_body_ratio and close_loc >= t.engulfing_close_location and bull_gap_quality and bull_micro and bull_context
            bear_engulf = previous_bull and bear and bear_coverage and body_to_atr >= t.minimum_engulfing_body_atr and prev_bull_quality and body_ratio >= t.minimum_engulfing_body_ratio and close_loc <= 1.0 - t.engulfing_close_location and bear_gap_quality and bear_micro and bear_context
            m["bullish_engulfing"] = bull_engulf
            m["bearish_engulfing"] = bear_engulf
            if bull_engulf:
                m["bullish_engulfing_quality"] = _clamp(
                    _ratio_score(body_to_atr, t.minimum_engulfing_body_atr, mintick) * 0.25 +
                    _ratio_score(body_ratio, t.minimum_engulfing_body_ratio, mintick) * 0.20 +
                    _clamp(close_loc * 100.0, 0.0, 100.0) * 0.20 +
                    15.0 + 10.0 + 10.0, 0.0, 100.0)
            if bear_engulf:
                m["bearish_engulfing_quality"] = _clamp(
                    _ratio_score(body_to_atr, t.minimum_engulfing_body_atr, mintick) * 0.25 +
                    _ratio_score(body_ratio, t.minimum_engulfing_body_ratio, mintick) * 0.20 +
                    _clamp((1.0 - close_loc) * 100.0, 0.0, 100.0) * 0.20 +
                    15.0 + 10.0 + 10.0, 0.0, 100.0)
            swallowed_lower = min(self._rows[i - 1]["open"], self._rows[i - 1]["close"])
            swallowed_upper = max(self._rows[i - 1]["open"], self._rows[i - 1]["close"])
            swallowed_size = swallowed_upper - swallowed_lower
            m["swallowed_lower"], m["swallowed_upper"], m["swallowed_size"] = swallowed_lower, swallowed_upper, swallowed_size
            m["swallowed_atr"] = _safe_div(swallowed_size, safe_prior_atr, 0.0, mintick)

            # Resolved wick evidence used by FVG embedded candle contribution.
            lower_rejection = primitive_lower and not strong_sell and not confirmed_sell[i] and close_loc > SHOCK_CLOSE_LOWER
            upper_rejection = primitive_upper and not strong_buy and not confirmed_buy[i] and close_loc < SHOCK_CLOSE_UPPER
            if lower_rejection and upper_rejection:
                lower_dom = lower_wick >= upper_wick * REJECTION_CONFLICT_MARGIN
                upper_dom = upper_wick >= lower_wick * REJECTION_CONFLICT_MARGIN
                if lower_dom and not upper_dom:
                    upper_rejection = False
                elif upper_dom and not lower_dom:
                    lower_rejection = False
                else:
                    lower_rejection = upper_rejection = False

            if not imbalance_ready:
                continue
            bull_geom = l > self._rows[i - 2]["high"]
            bear_geom = h < self._rows[i - 2]["low"]
            bull_lower = self._rows[i - 2]["high"] if bull_geom else math.nan
            bull_upper = l if bull_geom else math.nan
            bear_lower = h if bear_geom else math.nan
            bear_upper = self._rows[i - 2]["low"] if bear_geom else math.nan
            bull_gap_size = bull_upper - bull_lower if bull_geom else 0.0
            bear_gap_size = bear_upper - bear_lower if bear_geom else 0.0
            formation_atr = atr[i - 1] or mintick
            safe_formation_atr = max(formation_atr, mintick)
            m["formation_atr"] = formation_atr
            bull_gap_atr = _safe_div(bull_gap_size, safe_formation_atr, 0.0, mintick)
            bear_gap_atr = _safe_div(bear_gap_size, safe_formation_atr, 0.0, mintick)
            middle = self._rows[i - 1]
            middle_range = max(middle["high"] - middle["low"], 0.0)
            middle_body = abs(middle["close"] - middle["open"])
            middle_body_atr = _safe_div(middle_body, safe_formation_atr, 0.0, mintick)
            middle_body_share = _safe_div(middle_body, middle_range, 0.0, mintick)
            middle_close_loc = 0.5 if middle_range <= 1e-10 else _safe_div(middle["close"] - middle["low"], middle_range, 0.5, mintick)
            middle_bull = middle["close"] > middle["open"]
            middle_bear = middle["close"] < middle["open"]
            three_progress = c - self._rows[i - 2]["close"]
            three_progress_atr = _safe_div(three_progress, safe_formation_atr, 0.0, mintick)
            three_path = abs(middle["close"] - self._rows[i - 2]["close"]) + abs(c - middle["close"])
            three_eff = _safe_div(abs(three_progress), three_path, 0.0, mintick)
            opening_gap = abs(middle["open"] - self._rows[i - 2]["close"])
            opening_gap_atr = _safe_div(opening_gap, safe_formation_atr, 0.0, mintick)
            large_open_gap = opening_gap_atr > t.maximum_fvg_opening_gap_atr
            bull_size_pass = bull_gap_atr >= t.minimum_fvg_size_atr
            bear_size_pass = bear_gap_atr >= t.minimum_fvg_size_atr
            body_atr_pass = middle_body_atr >= t.minimum_displacement_body_atr
            body_share_pass = middle_body_share >= t.minimum_displacement_body_share
            bull_middle_close = middle_close_loc >= t.minimum_displacement_close_location
            bear_middle_close = middle_close_loc <= 1.0 - t.minimum_displacement_close_location
            bull_displacement = middle_bull and body_atr_pass and body_share_pass and bull_middle_close
            bear_displacement = middle_bear and body_atr_pass and body_share_pass and bear_middle_close
            bull_progress_pass = three_progress_atr >= t.minimum_fvg_progress_atr
            bear_progress_pass = three_progress_atr <= -t.minimum_fvg_progress_atr
            eff_pass = three_eff >= t.minimum_fvg_efficiency
            bull_accept = bull_geom and c >= bull_upper
            bear_accept = bear_geom and c <= bear_lower
            bull_invalid = bull_geom and c <= bull_lower
            bear_invalid = bear_geom and c >= bear_upper
            bull_direction = bull_progress_pass and eff_pass and bull_accept
            bear_direction = bear_progress_pass and eff_pass and bear_accept
            bull_extra = middle_body_atr >= t.minimum_displacement_body_atr * FVG_DISPLACEMENT_EXTRA_FACTOR and three_progress_atr >= t.minimum_fvg_progress_atr * FVG_PROGRESS_EXTRA_FACTOR and bull_gap_atr >= t.minimum_fvg_size_atr * FVG_SIZE_EXTRA_FACTOR and bull_accept
            bear_extra = middle_body_atr >= t.minimum_displacement_body_atr * FVG_DISPLACEMENT_EXTRA_FACTOR and three_progress_atr <= -t.minimum_fvg_progress_atr * FVG_PROGRESS_EXTRA_FACTOR and bear_gap_atr >= t.minimum_fvg_size_atr * FVG_SIZE_EXTRA_FACTOR and bear_accept
            bull_defense = not large_open_gap or bull_extra
            bear_defense = not large_open_gap or bear_extra
            bull_evidence = sum([bull_geom, bull_size_pass, middle_bull, body_atr_pass, body_share_pass, bull_middle_close, bull_progress_pass, eff_pass, bull_accept, not bull_invalid]) if bull_geom else 0
            bear_evidence = sum([bear_geom, bear_size_pass, middle_bear, body_atr_pass, body_share_pass, bear_middle_close, bear_progress_pass, eff_pass, bear_accept, not bear_invalid]) if bear_geom else 0
            bull_disp_evidence = sum([middle_bull, body_atr_pass, body_share_pass, bull_middle_close])
            bear_disp_evidence = sum([middle_bear, body_atr_pass, body_share_pass, bear_middle_close])
            bull_alignment = confirmed_buy[i] or bull_engulf or lower_rejection or (bull and close_loc >= t.minimum_continuation_close_location)
            bear_alignment = confirmed_sell[i] or bear_engulf or upper_rejection or (bear and close_loc <= 1.0 - t.minimum_continuation_close_location)
            bull_counter_absent = not confirmed_sell[i] and not bear_engulf and not upper_rejection
            bear_counter_absent = not confirmed_buy[i] and not bull_engulf and not lower_rejection
            bull_embedded = (5.0 if bull_alignment else 0.0) + (5.0 if bull_counter_absent else 0.0) if bull_geom else 0.0
            bear_embedded = (5.0 if bear_alignment else 0.0) + (5.0 if bear_counter_absent else 0.0) if bear_geom else 0.0

            def fvg_quality(is_bull: bool) -> float:
                geom = bull_geom if is_bull else bear_geom
                if not geom:
                    return 0.0
                gap_metric = bull_gap_atr if is_bull else bear_gap_atr
                close_metric = middle_close_loc if is_bull else 1.0 - middle_close_loc
                progress_metric = max(three_progress_atr, 0.0) if is_bull else max(-three_progress_atr, 0.0)
                defense = bull_defense if is_bull else bear_defense
                invalid = bull_invalid if is_bull else bear_invalid
                alignment = bull_alignment if is_bull else bear_alignment
                counter_absent = bull_counter_absent if is_bull else bear_counter_absent
                return _clamp(
                    _ratio_score(gap_metric, t.minimum_fvg_size_atr, mintick) * 0.15 +
                    _ratio_score(middle_body_atr, t.minimum_displacement_body_atr, mintick) * 0.15 +
                    _ratio_score(middle_body_share, t.minimum_displacement_body_share, mintick) * 0.12 +
                    _ratio_score(close_metric, t.minimum_displacement_close_location, mintick) * 0.12 +
                    _ratio_score(progress_metric, t.minimum_fvg_progress_atr, mintick) * 0.12 +
                    _ratio_score(three_eff, t.minimum_fvg_efficiency, mintick) * 0.12 +
                    (12.0 if defense and not invalid else 0.0) +
                    (5.0 if alignment else 0.0) +
                    (5.0 if counter_absent else 0.0),
                    0.0, 100.0,
                )

            bull_quality = fvg_quality(True)
            bear_quality = fvg_quality(False)
            min_candidate_evidence = max(t.minimum_fvg_evidence - 1, 5)
            min_candidate_quality = max(t.minimum_fvg_quality - FVG_CANDIDATE_QUALITY_OFFSET, 30.0)
            bull_candidate_size = bull_gap_atr >= t.minimum_fvg_size_atr * FVG_CANDIDATE_SIZE_FACTOR
            bear_candidate_size = bear_gap_atr >= t.minimum_fvg_size_atr * FVG_CANDIDATE_SIZE_FACTOR
            bull_candidate_direction = three_progress_atr > 0.0 and bull_accept
            bear_candidate_direction = three_progress_atr < 0.0 and bear_accept
            bull_active = imbalance_ready and bull_geom and bull_size_pass and bull_displacement and bull_direction and bull_defense and not bull_invalid and bull_evidence >= t.minimum_fvg_evidence and bull_quality >= t.minimum_fvg_quality
            bear_active = imbalance_ready and bear_geom and bear_size_pass and bear_displacement and bear_direction and bear_defense and not bear_invalid and bear_evidence >= t.minimum_fvg_evidence and bear_quality >= t.minimum_fvg_quality
            bull_candidate = imbalance_ready and bull_geom and not bull_active and bull_candidate_size and bull_disp_evidence >= 3 and bull_candidate_direction and bull_defense and not bull_invalid and bull_evidence >= min_candidate_evidence and bull_quality >= min_candidate_quality
            bear_candidate = imbalance_ready and bear_geom and not bear_active and bear_candidate_size and bear_disp_evidence >= 3 and bear_candidate_direction and bear_defense and not bear_invalid and bear_evidence >= min_candidate_evidence and bear_quality >= min_candidate_quality

            m.update({
                "bullish_fvg_active": bull_active,
                "bearish_fvg_active": bear_active,
                "bullish_fvg_candidate": bull_candidate,
                "bearish_fvg_candidate": bear_candidate,
                "bullish_fvg_quality": bull_quality,
                "bearish_fvg_quality": bear_quality,
                "bull_fvg_lower": bull_lower,
                "bull_fvg_upper": bull_upper,
                "bear_fvg_lower": bear_lower,
                "bear_fvg_upper": bear_upper,
                "bull_fvg_gap_size": bull_gap_size,
                "bear_fvg_gap_size": bear_gap_size,
                "bull_fvg_gap_atr": bull_gap_atr,
                "bear_fvg_gap_atr": bear_gap_atr,
                "bull_embedded_contribution": bull_embedded,
                "bear_embedded_contribution": bear_embedded,
                "bull_fvg_evidence": bull_evidence,
                "bear_fvg_evidence": bear_evidence,
            })

        return out
