from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any
import math

import pandas as pd

from .fvg_engulfing_engine import (
    FvgEngulfingEngine as _DetectorEngine,
    FvgFormation,
    EngulfingFormation,
    _clamp,
    _safe_div,
    _rma,
    ATR_LENGTH,
    FVG_CANDIDATE_QUALITY_OFFSET,
    FVG_CANDIDATE_SIZE_FACTOR,
    FVG_DISPLACEMENT_EXTRA_FACTOR,
    FVG_PROGRESS_EXTRA_FACTOR,
    FVG_SIZE_EXTRA_FACTOR,
    RETENTION_CLOSE_FLOOR,
    RETENTION_EFFICIENCY_FACTOR,
    SHOCK_CLOSE_UPPER,
    SHOCK_CLOSE_LOWER,
    SHOCK_MIDDLE_LOW,
    SHOCK_MIDDLE_HIGH,
    SHOCK_DIRECTIONLESS_BODY_SHARE,
    SHOCK_DIRECTIONLESS_WICK_SHARE,
    SHOCK_JUMP_FACTOR,
    CONFLICT_PROGRESS_FACTOR,
)
from .fvg_engulfing_models import (
    ENGULFING_DEEP_RETRACE_THRESHOLD,
    ENGULFING_PARTIAL_RETRACE_THRESHOLD,
    FLOW_LENGTH,
    FVG_REACTION_DISTANCE_FACTOR,
    FVG_REACTION_FLOW_FACTOR,
    FVG_TAKEOVER_AGE_FACTOR,
    FVG_TAKEOVER_DISTANCE_MARGIN,
    FVG_TAKEOVER_QUALITY_MARGIN,
    FvgDirection,
    FvgEngulfingConfig,
    FvgEngulfingDataQuality,
    FvgState,
    EngulfingDirection,
    EngulfingState,
    SensitivityProfile,
)


@dataclass(slots=True)
class FvgLifecycleRecord:
    direction: FvgDirection
    state: FvgState
    lower_boundary: float
    upper_boundary: float
    gap_size: float
    gap_atr: float
    formation_atr: float
    invalidation_buffer: float
    formation_index: int
    formation_time: Any
    quality: float
    evidence_count: int
    tested: bool = False
    first_test_index: int | None = None
    wick_fill_ratio: float = 0.0
    close_fill_ratio: float = 0.0
    maximum_fill_ratio: float = 0.0
    reaction_evidence_count: int = 0
    reaction_confirmed: bool = False
    failed_reaction: bool = False
    full_fill: bool = False
    invalid: bool = False
    invalid_reason: str = "YOK"
    invalid_close_count: int = 0


@dataclass(slots=True)
class EngulfingLifecycleRecord:
    direction: EngulfingDirection
    state: EngulfingState
    lower_boundary: float
    upper_boundary: float
    body_size: float
    body_atr: float
    formation_high: float
    formation_low: float
    formation_index: int
    formation_time: Any
    quality: float
    tested: bool = False
    first_test_index: int | None = None
    maximum_retrace_ratio: float = 0.0
    continuation_evidence_count: int = 0
    continuation_confirmed: bool = False
    weakened: bool = False
    weakened_index: int | None = None
    invalid: bool = False
    completion_reason: str = "YOK"


@dataclass(frozen=True, slots=True)
class FvgSideExport:
    state: int | None = None
    top: float | None = None
    bottom: float | None = None
    quality: float | None = None
    fill: float | None = None
    event: int | None = None


@dataclass(frozen=True, slots=True)
class EngulfingSideExport:
    state: int | None = None
    top: float | None = None
    bottom: float | None = None
    quality: float | None = None
    retrace: float | None = None
    event: int | None = None


@dataclass(frozen=True, slots=True)
class FvgEngulfingExport:
    bull_fvg: FvgSideExport = FvgSideExport()
    bear_fvg: FvgSideExport = FvgSideExport()
    bull_engulf: EngulfingSideExport = EngulfingSideExport()
    bear_engulf: EngulfingSideExport = EngulfingSideExport()


@dataclass(frozen=True, slots=True)
class _LifecycleMetrics:
    close: float
    low: float
    high: float
    candle_bullish: bool
    candle_bearish: bool
    close_location: float
    body_to_prior_atr: float
    net_progress_atr: float
    directional_efficiency: float
    higher_close_share: float
    lower_close_share: float
    buy_continuation_candidate: bool
    sell_continuation_candidate: bool
    buy_continuation_confirmed: bool
    sell_continuation_confirmed: bool
    lower_rejection: bool
    upper_rejection: bool
    bullish_engulfing: bool
    bearish_engulfing: bool


class FvgEngulfingEngine(_DetectorEngine):
    """Final v0.3.8 facade: detector + closed-bar lifecycle + Export Contract v1."""

    def __init__(self, config: FvgEngulfingConfig | None = None) -> None:
        super().__init__(config)
        self._bull_fvg: FvgLifecycleRecord | None = None
        self._bear_fvg: FvgLifecycleRecord | None = None
        self._bull_engulf: EngulfingLifecycleRecord | None = None
        self._bear_engulf: EngulfingLifecycleRecord | None = None
        self._bull_fvg_event: tuple[int, FvgState] | None = None
        self._bear_fvg_event: tuple[int, FvgState] | None = None
        self._bull_engulf_event: tuple[int, EngulfingState] | None = None
        self._bear_engulf_event: tuple[int, EngulfingState] | None = None
        self._export = FvgEngulfingExport()
        self._completed_fvg: list[FvgLifecycleRecord] = []
        self._completed_engulfing: list[EngulfingLifecycleRecord] = []

    @property
    def export(self) -> FvgEngulfingExport:
        return self._export

    @property
    def active_bullish_fvg(self) -> FvgLifecycleRecord | None:
        return self._bull_fvg

    @property
    def active_bearish_fvg(self) -> FvgLifecycleRecord | None:
        return self._bear_fvg

    @property
    def active_bullish_engulfing(self) -> EngulfingLifecycleRecord | None:
        return self._bull_engulf

    @property
    def active_bearish_engulfing(self) -> EngulfingLifecycleRecord | None:
        return self._bear_engulf

    @property
    def completed_fvg(self) -> tuple[FvgLifecycleRecord, ...]:
        return tuple(self._completed_fvg)

    @property
    def completed_engulfing(self) -> tuple[EngulfingLifecycleRecord, ...]:
        return tuple(self._completed_engulfing)

    def reset(self) -> None:
        super().reset()
        self._bull_fvg = None
        self._bear_fvg = None
        self._bull_engulf = None
        self._bear_engulf = None
        self._bull_fvg_event = None
        self._bear_fvg_event = None
        self._bull_engulf_event = None
        self._bear_engulf_event = None
        self._export = FvgEngulfingExport()
        self._completed_fvg = []
        self._completed_engulfing = []

    def update(self, bar: pd.Series | dict[str, Any]):
        row = dict(bar)
        if not bool(row.get("is_closed", True)):
            return super().update(row)

        before_fvg = len(self._fvg_formations)
        before_engulf = len(self._engulfing_formations)
        result = super().update(row)

        if self.last_data_quality is not FvgEngulfingDataQuality.OK:
            # SOURCE_GAP/WARMUP do not advance confirmed lifecycle or overwrite export.
            return result

        idx = len(self._rows) - 1
        metrics = self._lifecycle_metrics(idx)
        self._repair_candidate_alignment(idx, metrics)

        # Source order: update existing records first, then evaluate new formations/takeover.
        self._update_fvg_record(True, idx, metrics)
        self._update_fvg_record(False, idx, metrics)
        self._update_engulfing_record(True, idx, metrics)
        self._update_engulfing_record(False, idx, metrics)

        for formation in self._fvg_formations[before_fvg:]:
            self._accept_fvg_formation(formation, idx, metrics)
        for formation in self._engulfing_formations[before_engulf:]:
            self._accept_engulfing_formation(formation, idx)

        self._export = self._build_export(idx)
        return result

    def _profile_lifecycle_values(self) -> tuple[int, int, int, int, float, int, int, int]:
        p = self.config.sensitivity
        if p is SensitivityProfile.SENSITIVE:
            return 30, 2, 1, 2, 0.03, 1, 3, 1
        if p is SensitivityProfile.BALANCED:
            return 45, 3, 2, 3, 0.05, 2, 5, 2
        return 60, 4, 2, 3, 0.08, 2, 6, 2

    def _repair_candidate_alignment(self, idx: int, metrics: _LifecycleMetrics) -> None:
        """Close Tur-1 parity edge: continuation candidate shares candle-state family in Pine."""
        if not self._fvg_formations:
            return
        candidates = [f for f in self._fvg_formations if f.formation_index == idx]
        for formation in candidates:
            add = False
            if formation.direction is FvgDirection.BULLISH:
                add = metrics.buy_continuation_candidate and formation.embedded_candle_contribution < 10.0
            else:
                add = metrics.sell_continuation_candidate and formation.embedded_candle_contribution < 10.0
            if not add:
                continue
            pos = self._fvg_formations.index(formation)
            self._fvg_formations[pos] = replace(
                formation,
                quality=min(100.0, formation.quality + 5.0),
                embedded_candle_contribution=min(10.0, formation.embedded_candle_contribution + 5.0),
            )

    def _lifecycle_metrics(self, i: int) -> _LifecycleMetrics:
        rows = self._rows
        t = self._thresholds
        tick = self.config.minimum_tick
        r = rows[i]
        o, h, l, c = r["open"], r["high"], r["low"], r["close"]
        candle_range = max(h - l, 0.0)
        body = abs(c - o)
        bull, bear = c > o, c < o
        close_loc = 0.5 if candle_range <= 1e-10 else _safe_div(c - l, candle_range, 0.5, tick)

        tr: list[float | None] = []
        for j, bar in enumerate(rows):
            if not self._valid[j]:
                tr.append(None)
                continue
            prev = rows[j - 1]["close"] if j > 0 and self._valid[j - 1] else None
            value = bar["high"] - bar["low"]
            if prev is not None:
                value = max(value, abs(bar["high"] - prev), abs(bar["low"] - prev))
            tr.append(max(value, 0.0))
        atr = _rma(tr, ATR_LENGTH)
        prior_atr = atr[i - 1] if i > 0 and atr[i - 1] is not None else tick
        safe_prior_atr = max(prior_atr, tick)
        body_to_atr = _safe_div(body, safe_prior_atr, 0.0, tick)

        net_progress = c - rows[i - FLOW_LENGTH]["close"]
        net_progress_atr = _safe_div(net_progress, atr[i] or tick, 0.0, tick)
        path = sum(abs(rows[j]["close"] - rows[j - 1]["close"]) for j in range(i - 3, i + 1))
        efficiency = _safe_div(abs(net_progress), path, 0.0, tick)
        higher_share = sum(rows[j]["close"] > rows[j - 1]["close"] for j in range(i - 3, i + 1)) / 4.0
        lower_share = sum(rows[j]["close"] < rows[j - 1]["close"] for j in range(i - 3, i + 1)) / 4.0

        current_series = super()._calculate_series()
        m = current_series[i]
        bull_engulf = bool(m["bullish_engulfing"])
        bear_engulf = bool(m["bearish_engulfing"])

        # Candidate raw is re-evaluated solely to restore Pine candle-state family parity.
        upper_wick = max(h - max(o, c), 0.0)
        lower_wick = max(min(o, c) - l, 0.0)
        safe_body = max(body, tick)
        upper_wick_body = _safe_div(upper_wick, safe_body, 0.0, tick)
        lower_wick_body = _safe_div(lower_wick, safe_body, 0.0, tick)
        upper_wick_atr = _safe_div(upper_wick, safe_prior_atr, 0.0, tick)
        lower_wick_atr = _safe_div(lower_wick, safe_prior_atr, 0.0, tick)
        prev_high = max(rows[j]["high"] for j in range(i - 4, i))
        prev_low = min(rows[j]["low"] for j in range(i - 4, i))
        primitive_lower = lower_wick_body >= t.minimum_rejection_wick_body and lower_wick_atr >= t.minimum_rejection_wick_atr and close_loc >= t.rejection_close_location and lower_wick >= upper_wick * t.minimum_wick_dominance and l <= prev_low
        primitive_upper = upper_wick_body >= t.minimum_rejection_wick_body and upper_wick_atr >= t.minimum_rejection_wick_atr and close_loc <= 1.0 - t.rejection_close_location and upper_wick >= lower_wick * t.minimum_wick_dominance and h >= prev_high
        strong_buy = bull and body_to_atr >= t.minimum_continuation_body_atr and close_loc >= t.minimum_continuation_close_location and net_progress_atr > 0
        strong_sell = bear and body_to_atr >= t.minimum_continuation_body_atr and close_loc <= 1.0 - t.minimum_continuation_close_location and net_progress_atr < 0
        prev = rows[i - 1]
        prev_range = max(prev["high"] - prev["low"], 0.0)
        body_share = _safe_div(body, candle_range, 0.0, tick)
        green_share = sum(rows[j]["close"] > rows[j]["open"] for j in range(i - 3, i + 1)) / 4.0
        red_share = sum(rows[j]["close"] < rows[j]["open"] for j in range(i - 3, i + 1)) / 4.0
        buy_e = [bull, body_to_atr >= t.minimum_continuation_body_atr, body_share >= t.minimum_continuation_body_share, close_loc >= t.minimum_continuation_close_location, upper_wick_body <= t.maximum_opposing_wick_body, net_progress_atr >= t.minimum_continuation_progress_atr, efficiency >= t.minimum_continuation_efficiency, higher_share >= .5, green_share >= .5, c > prev["close"], c >= prev["high"] or c >= prev["low"] + prev_range * .70]
        sell_e = [bear, body_to_atr >= t.minimum_continuation_body_atr, body_share >= t.minimum_continuation_body_share, close_loc <= 1.0 - t.minimum_continuation_close_location, lower_wick_body <= t.maximum_opposing_wick_body, net_progress_atr <= -t.minimum_continuation_progress_atr, efficiency >= t.minimum_continuation_efficiency, lower_share >= .5, red_share >= .5, c < prev["close"], c <= prev["low"] or c <= prev["low"] + prev_range * .30]
        buy_base = bull and (buy_e[1] or buy_e[2]) and (buy_e[3] or (close_loc >= RETENTION_CLOSE_FLOOR and buy_e[4])) and sum(buy_e[5:]) >= 2 and sum(buy_e) >= t.continuation_evidence_minimum and not (primitive_upper or strong_sell)
        sell_base = bear and (sell_e[1] or sell_e[2]) and (sell_e[3] or (close_loc <= 1.0 - RETENTION_CLOSE_FLOOR and sell_e[4])) and sum(sell_e[5:]) >= 2 and sum(sell_e) >= t.continuation_evidence_minimum and not (primitive_lower or strong_buy)
        if buy_base and sell_base:
            threshold = t.minimum_continuation_progress_atr * CONFLICT_PROGRESS_FACTOR
            if net_progress_atr > threshold: sell_base = False
            elif net_progress_atr < -threshold: buy_base = False
            else: buy_base = sell_base = False
        # The full shock veto is intentionally conservative here: only clear candidates on source shock extremes.
        extreme = (candle_range / safe_prior_atr >= t.shock_range_atr) or (body_to_atr >= t.shock_body_atr)
        one_bar_shock = extreme and ((bull and close_loc >= SHOCK_CLOSE_UPPER and net_progress_atr > 0) or (bear and close_loc <= SHOCK_CLOSE_LOWER and net_progress_atr < 0) or (body_share <= SHOCK_DIRECTIONLESS_BODY_SHARE and SHOCK_MIDDLE_LOW <= close_loc <= SHOCK_MIDDLE_HIGH))
        buy_candidate = buy_base and not one_bar_shock
        sell_candidate = sell_base and not one_bar_shock

        # Confirmation family is observable through previous/current detector context; for lifecycle
        # promotion/reaction only current source state is needed. Candidate counts as same candle family.
        buy_confirmed = buy_candidate and close_loc >= max(RETENTION_CLOSE_FLOOR, t.minimum_continuation_close_location - .12) and efficiency >= t.minimum_continuation_efficiency * RETENTION_EFFICIENCY_FACTOR and net_progress_atr > 0
        sell_confirmed = sell_candidate and close_loc <= 1.0 - max(RETENTION_CLOSE_FLOOR, t.minimum_continuation_close_location - .12) and efficiency >= t.minimum_continuation_efficiency * RETENTION_EFFICIENCY_FACTOR and net_progress_atr < 0

        lower_rejection, upper_rejection = primitive_lower, primitive_upper
        return _LifecycleMetrics(c, l, h, bull, bear, close_loc, body_to_atr, net_progress_atr, efficiency, higher_share, lower_share, buy_candidate, sell_candidate, buy_confirmed, sell_confirmed, lower_rejection, upper_rejection, bull_engulf, bear_engulf)

    def _update_fvg_record(self, bullish: bool, idx: int, m: _LifecycleMetrics) -> None:
        rec = self._bull_fvg if bullish else self._bear_fvg
        if rec is None:
            return
        max_age, max_candidate_age, min_reaction, failed_window, _, invalid_close_bars, _, _ = self._profile_lifecycle_values()
        age = idx - rec.formation_index
        completed = False
        if rec.state is FvgState.CANDIDATE:
            close_lost = m.close < rec.lower_boundary - rec.invalidation_buffer if bullish else m.close > rec.upper_boundary + rec.invalidation_buffer
            touched = idx > rec.formation_index and (m.low <= rec.upper_boundary if bullish else m.high >= rec.lower_boundary)
            evidence = sum([
                m.close >= rec.upper_boundary if bullish else m.close <= rec.lower_boundary,
                m.candle_bullish if bullish else m.candle_bearish,
                m.net_progress_atr > 0 if bullish else m.net_progress_atr < 0,
                m.higher_close_share >= .5 if bullish else m.lower_close_share >= .5,
                not m.sell_continuation_confirmed if bullish else not m.buy_continuation_confirmed,
            ])
            min_quality = max(self._thresholds.minimum_fvg_quality - FVG_CANDIDATE_QUALITY_OFFSET, 30.0)
            promotion = 1 <= age <= max_candidate_age and rec.quality >= min_quality and evidence >= 3 and (m.close >= rec.upper_boundary if bullish else m.close <= rec.lower_boundary) and not close_lost
            if close_lost:
                rec.state, rec.invalid, rec.invalid_reason, completed = FvgState.INVALID, True, "Kapanışla geçersizlik", True
            elif promotion:
                if touched:
                    fill = _clamp(_safe_div(rec.upper_boundary - m.low if bullish else m.high - rec.lower_boundary, rec.gap_size, 0.0, self.config.minimum_tick), 0.0, 1.0)
                    rec.tested = True; rec.first_test_index = idx; rec.wick_fill_ratio = max(rec.wick_fill_ratio, fill); rec.maximum_fill_ratio = max(rec.maximum_fill_ratio, rec.wick_fill_ratio); rec.state = FvgState.FIRST_TEST
                else:
                    rec.state = FvgState.ACTIVE
            elif touched or age > max_candidate_age:
                rec.state, rec.invalid, rec.invalid_reason, completed = FvgState.INVALID, True, "Kalite yetersizliği", True
        else:
            eligible = idx > rec.formation_index
            touch = eligible and (m.low <= rec.upper_boundary if bullish else m.high >= rec.lower_boundary)
            if touch:
                wick = _clamp(_safe_div(rec.upper_boundary - m.low if bullish else m.high - rec.lower_boundary, rec.gap_size, 0.0, self.config.minimum_tick), 0.0, 1.0)
                close_fill = _clamp(_safe_div(rec.upper_boundary - m.close if bullish else m.close - rec.lower_boundary, rec.gap_size, 0.0, self.config.minimum_tick), 0.0, 1.0)
                rec.wick_fill_ratio = max(rec.wick_fill_ratio, wick); rec.close_fill_ratio = max(rec.close_fill_ratio, close_fill); rec.maximum_fill_ratio = max(rec.maximum_fill_ratio, rec.wick_fill_ratio)
                if not rec.tested: rec.tested = True; rec.first_test_index = idx
            beyond = m.close < rec.lower_boundary - rec.invalidation_buffer if bullish else m.close > rec.upper_boundary + rec.invalidation_buffer
            rec.invalid_close_count = rec.invalid_close_count + 1 if beyond else 0
            close_invalid = rec.invalid_close_count >= invalid_close_bars
            age_invalid = age > max_age
            full_fill = eligible and (m.low <= rec.lower_boundary if bullish else m.high >= rec.upper_boundary)
            since_test = idx - rec.first_test_index if rec.tested and rec.first_test_index is not None else 0
            away = rec.tested and (m.close > rec.upper_boundary + rec.gap_size * FVG_REACTION_DISTANCE_FACTOR if bullish else m.close < rec.lower_boundary - rec.gap_size * FVG_REACTION_DISTANCE_FACTOR)
            candle_reaction = (m.buy_continuation_candidate or m.bullish_engulfing or m.lower_rejection) if bullish else (m.sell_continuation_candidate or m.bearish_engulfing or m.upper_rejection)
            flow_reaction = (m.net_progress_atr > self._thresholds.minimum_fvg_progress_atr * FVG_REACTION_FLOW_FACTOR if bullish else m.net_progress_atr < -self._thresholds.minimum_fvg_progress_atr * FVG_REACTION_FLOW_FACTOR) and m.directional_efficiency >= self._thresholds.minimum_fvg_efficiency * RETENTION_EFFICIENCY_FACTOR
            held = m.close > rec.lower_boundary if bullish else m.close < rec.upper_boundary
            rec.reaction_evidence_count = sum([away, candle_reaction, flow_reaction, held])
            reaction = rec.tested and away and held and rec.reaction_evidence_count >= 2 and (since_test >= min_reaction or rec.reaction_evidence_count >= 3)
            opposing = (m.sell_continuation_candidate or m.bearish_engulfing or m.upper_rejection) if bullish else (m.buy_continuation_candidate or m.bullish_engulfing or m.lower_rejection)
            failed = rec.tested and not reaction and since_test >= failed_window and (rec.maximum_fill_ratio >= .50 or opposing or (m.net_progress_atr < 0 if bullish else m.net_progress_atr > 0))
            if age_invalid: rec.state, rec.invalid, rec.invalid_reason, completed = FvgState.INVALID, True, "Yaş sınırı", True
            elif close_invalid: rec.state, rec.invalid, rec.invalid_reason, completed = FvgState.INVALID, True, "Kapanışla geçersizlik", True
            elif full_fill: rec.state, rec.full_fill, rec.invalid_reason, completed = FvgState.FULL_FILL, True, "Tam dolum", True
            elif reaction: rec.state, rec.reaction_confirmed, rec.invalid_reason, completed = FvgState.REACTION, True, "Tepki üretti", True
            elif failed: rec.state, rec.failed_reaction, rec.invalid_reason = FvgState.FAILED_REACTION, True, "Tepki üretmedi"
            elif rec.tested: rec.state = FvgState.DEEP_TEST if rec.maximum_fill_ratio >= .50 else FvgState.PARTIAL_FILL if rec.maximum_fill_ratio >= .25 else FvgState.FIRST_TEST
            else: rec.state = FvgState.ACTIVE
        if completed:
            self._complete_fvg(rec, idx)
            if bullish: self._bull_fvg = None
            else: self._bear_fvg = None

    def _complete_fvg(self, rec: FvgLifecycleRecord, idx: int) -> None:
        self._completed_fvg.append(replace(rec))
        if rec.direction is FvgDirection.BULLISH: self._bull_fvg_event = (idx, rec.state)
        else: self._bear_fvg_event = (idx, rec.state)

    def _accept_fvg_formation(self, formation: FvgFormation, idx: int, m: _LifecycleMetrics) -> None:
        bullish = formation.direction is FvgDirection.BULLISH
        existing = self._bull_fvg if bullish else self._bear_fvg
        accept = existing is None
        if existing is not None and formation.state is FvgState.ACTIVE:
            max_age, _, _, _, buffer_factor, _, _, _ = self._profile_lifecycle_values()
            atr_now = max(formation.formation_atr, self.config.minimum_tick)
            existing_distance = abs(m.close - (existing.upper_boundary if bullish else existing.lower_boundary)) / atr_now
            new_distance = abs(m.close - (formation.upper_boundary if bullish else formation.lower_boundary)) / atr_now
            existing_candidate = existing.state is FvgState.CANDIDATE
            clearly_better = formation.quality >= existing.quality + FVG_TAKEOVER_QUALITY_MARGIN
            aged = idx - existing.formation_index >= round(max_age * FVG_TAKEOVER_AGE_FACTOR) and formation.quality >= existing.quality - 2.0
            closer = new_distance + FVG_TAKEOVER_DISTANCE_MARGIN < existing_distance and formation.quality >= existing.quality
            accept = existing_candidate or clearly_better or aged or closer
        if not accept:
            return
        if existing is not None:
            existing.state = FvgState.SUPERSEDED; existing.invalid_reason = "Yeni bullish FVG tarafından devralındı" if bullish else "Yeni bearish FVG tarafından devralındı"; self._complete_fvg(existing, idx)
        _, _, _, _, buffer_factor, _, _, _ = self._profile_lifecycle_values()
        rec = FvgLifecycleRecord(formation.direction, formation.state, formation.lower_boundary, formation.upper_boundary, formation.gap_size, formation.gap_atr, formation.formation_atr, formation.formation_atr * buffer_factor, formation.formation_index, formation.timestamp, formation.quality, formation.evidence_count)
        if bullish: self._bull_fvg = rec
        else: self._bear_fvg = rec

    def _update_engulfing_record(self, bullish: bool, idx: int, m: _LifecycleMetrics) -> None:
        rec = self._bull_engulf if bullish else self._bear_engulf
        if rec is None: return
        _, _, _, _, _, _, max_age, continuation_window = self._profile_lifecycle_values()
        age = idx - rec.formation_index
        eligible = age > 0
        test = eligible and (m.low <= rec.upper_boundary if bullish else m.high >= rec.lower_boundary)
        if test:
            if not rec.tested: rec.first_test_index = idx
            rec.tested = True
            retrace = _clamp(_safe_div(rec.upper_boundary - m.low if bullish else m.high - rec.lower_boundary, rec.body_size, 0.0, self.config.minimum_tick), 0.0, 1.0)
            rec.maximum_retrace_ratio = max(rec.maximum_retrace_ratio, retrace)
        continuation_break = m.close > rec.formation_high if bullish else m.close < rec.formation_low
        acceptance = m.candle_bullish and m.close_location >= self._thresholds.engulfing_close_location if bullish else m.candle_bearish and m.close_location <= 1.0 - self._thresholds.engulfing_close_location
        progress = m.net_progress_atr > 0 if bullish else m.net_progress_atr < 0
        efficiency = m.directional_efficiency >= self._thresholds.minimum_continuation_efficiency
        evidence = sum([continuation_break, acceptance, progress, efficiency]); rec.continuation_evidence_count = evidence
        continuation = eligible and continuation_break and evidence >= 3
        invalid = eligible and (m.close < rec.lower_boundary if bullish else m.close > rec.upper_boundary)
        strong_opposing = m.candle_bearish and m.body_to_prior_atr >= self._thresholds.minimum_engulfing_body_atr and m.close_location <= 1.0 - self._thresholds.engulfing_close_location and m.net_progress_atr < 0 if bullish else m.candle_bullish and m.body_to_prior_atr >= self._thresholds.minimum_engulfing_body_atr and m.close_location >= self._thresholds.engulfing_close_location and m.net_progress_atr > 0
        opposing = (m.bearish_engulfing if bullish else m.bullish_engulfing) or strong_opposing
        weakened_now = rec.tested and not continuation and age >= continuation_window and (rec.maximum_retrace_ratio >= ENGULFING_DEEP_RETRACE_THRESHOLD or opposing or (m.net_progress_atr < 0 if bullish else m.net_progress_atr > 0))
        grace_expired = rec.state is EngulfingState.WEAKENED and rec.weakened_index is not None and idx > rec.weakened_index
        expired = age > max_age or grace_expired
        terminal = False
        if invalid: rec.state, rec.invalid, rec.completion_reason, terminal = EngulfingState.INVALID, True, "Gövde altı kapanış" if bullish else "Gövde üstü kapanış", True
        elif continuation: rec.state, rec.continuation_confirmed, rec.completion_reason, terminal = EngulfingState.CONTINUATION_CONFIRMED, True, "Devam teyidi", True
        elif expired: rec.state, rec.completion_reason, terminal = EngulfingState.EXPIRED, "Zayıflama sonrası izleme süresi doldu" if grace_expired else "Yaş sınırı doldu", True
        elif weakened_now:
            rec.state, rec.weakened = EngulfingState.WEAKENED, True
            if rec.weakened_index is None: rec.weakened_index = idx
        elif rec.maximum_retrace_ratio >= ENGULFING_PARTIAL_RETRACE_THRESHOLD: rec.state = EngulfingState.PARTIAL_RETRACE
        elif rec.tested: rec.state = EngulfingState.FIRST_TEST
        else: rec.state = EngulfingState.ACTIVE
        if terminal:
            self._completed_engulfing.append(replace(rec))
            if bullish: self._bull_engulf_event = (idx, rec.state); self._bull_engulf = None
            else: self._bear_engulf_event = (idx, rec.state); self._bear_engulf = None

    def _accept_engulfing_formation(self, formation: EngulfingFormation, idx: int) -> None:
        bullish = formation.direction is EngulfingDirection.BULLISH
        existing = self._bull_engulf if bullish else self._bear_engulf
        accept = existing is None or (idx > existing.formation_index and formation.quality >= existing.quality)
        if not accept: return
        if existing is not None:
            existing.state = EngulfingState.EXPIRED; existing.completion_reason = "Yeni bullish engulfing tarafından devralındı" if bullish else "Yeni bearish engulfing tarafından devralındı"; self._completed_engulfing.append(replace(existing))
            if bullish: self._bull_engulf_event = (idx, EngulfingState.EXPIRED)
            else: self._bear_engulf_event = (idx, EngulfingState.EXPIRED)
        row = self._rows[idx]
        rec = EngulfingLifecycleRecord(formation.direction, EngulfingState.ACTIVE, formation.lower_boundary, formation.upper_boundary, formation.body_size, formation.body_atr, row["high"], row["low"], formation.formation_index, formation.timestamp, formation.quality)
        if bullish: self._bull_engulf = rec
        else: self._bear_engulf = rec

    def _build_export(self, idx: int) -> FvgEngulfingExport:
        def fvg(rec: FvgLifecycleRecord | None, event: tuple[int, FvgState] | None, bearish: bool) -> FvgSideExport:
            if rec is None:
                return FvgSideExport(event=(-int(event[1]) if bearish else int(event[1])) if event and event[0] == idx else None)
            fill = _clamp(rec.maximum_fill_ratio, 0.0, 1.0)
            top = rec.upper_boundary if bearish else max(rec.lower_boundary, rec.upper_boundary - rec.gap_size * fill)
            bottom = min(rec.upper_boundary, rec.lower_boundary + rec.gap_size * fill) if bearish else rec.lower_boundary
            return FvgSideExport(-int(rec.state) if bearish else int(rec.state), top, bottom, rec.quality, fill, (-int(event[1]) if bearish else int(event[1])) if event and event[0] == idx else None)
        active_engulf_states = {EngulfingState.ACTIVE, EngulfingState.FIRST_TEST, EngulfingState.PARTIAL_RETRACE, EngulfingState.WEAKENED}
        def engulf(rec: EngulfingLifecycleRecord | None, event: tuple[int, EngulfingState] | None, bearish: bool) -> EngulfingSideExport:
            visible = rec is not None and rec.state in active_engulf_states
            ev = (-int(event[1]) if bearish else int(event[1])) if event and event[0] == idx else None
            if not visible: return EngulfingSideExport(event=ev)
            return EngulfingSideExport(-int(rec.state) if bearish else int(rec.state), rec.upper_boundary, rec.lower_boundary, rec.quality, _clamp(rec.maximum_retrace_ratio, 0.0, 1.0), ev)
        return FvgEngulfingExport(fvg(self._bull_fvg, self._bull_fvg_event, False), fvg(self._bear_fvg, self._bear_fvg_event, True), engulf(self._bull_engulf, self._bull_engulf_event, False), engulf(self._bear_engulf, self._bear_engulf_event, True))
