from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

from .models import EngineResult
from .volume_participation_engine import (
    EffortResultClass,
    VolumeParticipationConfig,
    VolumeParticipationEngine as CoreVolumeParticipationEngine,
    VolumeParticipationMetrics,
    _safe_div,
)


class LifecycleStage(StrEnum):
    NONE = "NONE"
    CONFIRMED = "CONFIRMED"
    PROTECTED = "PROTECTED"
    WEAKENING = "WEAKENING"
    CLOSED = "CLOSED"


class AbsorptionSide(StrEnum):
    NONE = "NONE"
    UPPER = "UPPER"
    LOWER = "LOWER"


class AbsorptionStage(StrEnum):
    NONE = "NONE"
    CANDIDATE = "CANDIDATE"
    CONFIRMED = "CONFIRMED"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"


class BreakStage(StrEnum):
    NONE = "NONE"
    DEVELOPING = "DEVELOPING"
    SUPPORTED = "SUPPORTED"
    PROTECTED = "PROTECTED"
    UNSUPPORTED = "UNSUPPORTED"
    RECLAIMED = "RECLAIMED"


@dataclass(frozen=True, slots=True)
class ParticipationLifecycleConfig:
    recent_context_length: int = 8
    pivot_length: int = 4
    minimum_pivot_range_atr: float = 1.35
    minimum_pivot_bar_distance: int = 4
    recent_level_lookback: int = 20
    important_level_proximity_atr: float = 0.25
    break_buffer_atr: float = 0.08
    breakout_confirmation_bars: int = 2
    absorption_minimum_wick_ratio: float = 0.36
    absorption_minimum_evidence: int = 4
    absorption_confirmation_window: int = 4
    weakening_rvol_drop_factor: float = 0.85
    weakening_rtv_drop_factor: float = 0.85
    weakening_minimum_evidence: int = 4


@dataclass(frozen=True, slots=True)
class ConfirmedParticipationPivot:
    side: str
    price: float
    origin_index: int
    known_index: int
    atr_at_source: float


@dataclass(frozen=True, slots=True)
class AbsorptionEvent:
    side: AbsorptionSide = AbsorptionSide.NONE
    stage: AbsorptionStage = AbsorptionStage.NONE
    candidate_index: int | None = None
    reference_level: float | None = None
    reference_source: str | None = None
    candidate_high: float | None = None
    candidate_low: float | None = None
    candidate_mid: float | None = None
    frozen_atr: float | None = None
    frozen_buffer: float | None = None


@dataclass(frozen=True, slots=True)
class BreakParticipationEvent:
    direction: int = 0
    stage: BreakStage = BreakStage.NONE
    start_index: int | None = None
    level: float | None = None
    reference_source: str | None = None
    frozen_atr: float | None = None
    frozen_buffer: float | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ParticipationLifecycleExport:
    participation_direction: int = 0
    participation_stage: str = LifecycleStage.NONE.value
    controlled_pullback: bool = False
    controlled_reaction: bool = False
    absorption_side: str = AbsorptionSide.NONE.value
    absorption_stage: str = AbsorptionStage.NONE.value
    absorption_reference_level: float | None = None
    absorption_reference_source: str | None = None
    absorption_frozen_atr: float | None = None
    absorption_frozen_buffer: float | None = None
    break_direction: int = 0
    break_stage: str = BreakStage.NONE.value
    break_level: float | None = None
    break_reference_source: str | None = None
    break_frozen_atr: float | None = None
    break_frozen_buffer: float | None = None
    last_pivot_high: float | None = None
    last_pivot_high_known_index: int | None = None
    last_pivot_low: float | None = None
    last_pivot_low_known_index: int | None = None


class VolumeParticipationEngine(CoreVolumeParticipationEngine):
    """Tur-2 lifecycle wrapper. Tur-1 math remains untouched."""

    def __init__(self, config: VolumeParticipationConfig | None = None, lifecycle_config: ParticipationLifecycleConfig | None = None) -> None:
        super().__init__(config)
        self.lifecycle_config = lifecycle_config or ParticipationLifecycleConfig()
        self._init_lifecycle()

    def _init_lifecycle(self) -> None:
        self.lifecycle_export = ParticipationLifecycleExport()
        self._participation_direction = 0
        self._participation_stage = LifecycleStage.NONE
        self._participation_confirmed_index: int | None = None
        self._absorption = AbsorptionEvent()
        self._absorption_hold_until = -1
        self._break = BreakParticipationEvent()
        self._accepted_pivot: ConfirmedParticipationPivot | None = None
        self._last_high_pivot: ConfirmedParticipationPivot | None = None
        self._last_low_pivot: ConfirmedParticipationPivot | None = None
        self._lifecycle_snapshot: EngineResult | None = None

    def _reset(self) -> None:
        super()._reset()
        self._init_lifecycle()

    def _atr_series(self) -> list[float | None]:
        """Return the core engine's incrementally maintained Wilder ATR series."""

        return self._atr_values

    def _accept_pivot(self, pivot: ConfirmedParticipationPivot) -> None:
        self._accepted_pivot = pivot
        if pivot.side == "HIGH":
            self._last_high_pivot = pivot
        else:
            self._last_low_pivot = pivot

    def _update_pivot(self, index: int) -> None:
        p = self.lifecycle_config.pivot_length
        origin = index - p
        if origin < p or index < 2 * p:
            return
        highs = self._high_values
        lows = self._low_values
        high_window = highs[origin - p : origin + p + 1]
        low_window = lows[origin - p : origin + p + 1]
        is_high = highs[origin] == max(high_window) and high_window.count(highs[origin]) == 1
        is_low = lows[origin] == min(low_window) and low_window.count(lows[origin]) == 1
        if is_high == is_low:
            return
        atr = self._atr_values[origin]
        if atr is None or atr <= 0:
            return
        pivot = ConfirmedParticipationPivot("HIGH" if is_high else "LOW", highs[origin] if is_high else lows[origin], origin, index, float(atr))
        previous = self._accepted_pivot
        if previous is None:
            self._accept_pivot(pivot)
            return
        if pivot.side == previous.side:
            more_extreme = pivot.price > previous.price if pivot.side == "HIGH" else pivot.price < previous.price
            if more_extreme:
                self._accept_pivot(pivot)
            return
        if pivot.origin_index - previous.origin_index < self.lifecycle_config.minimum_pivot_bar_distance:
            return
        if _safe_div(abs(pivot.price - previous.price), pivot.atr_at_source) < self.lifecycle_config.minimum_pivot_range_atr:
            return
        self._accept_pivot(pivot)

    def _flow_shares_5(self) -> tuple[float, float, float, float]:
        length = self.config.flow_short_length
        n = len(self._rows)
        if n < length:
            return 0.5, 0.5, 0.5, 0.5
        start = n - length
        uv = dv = uc = dc = tv = tc = 0.0
        for i in range(start, n):
            volume = self._volume_values[i]
            capital = self._traded_values[i]
            tv += volume
            tc += capital
            if i > 0 and self._close_values[i] > self._close_values[i - 1]:
                uv += volume; uc += capital
            elif i > 0 and self._close_values[i] < self._close_values[i - 1]:
                dv += volume; dc += capital
        return _safe_div(uv, tv, 0.5), _safe_div(dv, tv, 0.5), _safe_div(uc, tc, 0.5), _safe_div(dc, tc, 0.5)

    def _update_participation_lifecycle(self, index: int, metrics: VolumeParticipationMetrics) -> tuple[bool, bool]:
        if not metrics.data_ready:
            return False, False
        if metrics.up_confirmed:
            self._participation_direction, self._participation_stage, self._participation_confirmed_index = 1, LifecycleStage.CONFIRMED, index
        elif metrics.down_confirmed:
            self._participation_direction, self._participation_stage, self._participation_confirmed_index = -1, LifecycleStage.CONFIRMED, index
        if self._participation_confirmed_index is None:
            return False, False
        if index - self._participation_confirmed_index > self.lifecycle_config.recent_context_length:
            self._participation_direction, self._participation_stage = 0, LifecycleStage.CLOSED
            return False, False

        up_v, down_v, up_c, down_c = self._flow_shares_5()
        close = self._close_values[index]
        prev_close = self._close_values[index - 1]
        rvol, rtv, pressure = metrics.rvol or 0.0, metrics.rtv or 0.0, metrics.directional_value_pressure_5 or 0.0
        controlled_up = self._participation_direction == 1 and close < prev_close and metrics.down_evidence_count < self.config.participation_minimum_evidence and down_v < self.config.minimum_directional_share and down_c < self.config.minimum_directional_share and rvol <= 1.05 and rtv <= 1.05 and pressure > -self.config.minimum_capital_pressure
        controlled_down = self._participation_direction == -1 and close > prev_close and metrics.up_evidence_count < self.config.participation_minimum_evidence and up_v < self.config.minimum_directional_share and up_c < self.config.minimum_directional_share and rvol <= 1.05 and rtv <= 1.05 and pressure < self.config.minimum_capital_pressure
        if controlled_up or controlled_down:
            self._participation_stage = LifecycleStage.PROTECTED

        if len(self._metrics_history) >= 2 and self._participation_direction:
            prev = self._metrics_history[-2]
            if prev.data_ready:
                prev_rvol, prev_rtv = prev.rvol or rvol, prev.rtv or rtv
                evidence = 0
                evidence += int(rvol < prev_rvol * self.lifecycle_config.weakening_rvol_drop_factor and (metrics.volume_slope or 0.0) < 0.0)
                evidence += int(rtv < prev_rtv * self.lifecycle_config.weakening_rtv_drop_factor and (metrics.capital_slope or 0.0) < 0.0)
                evidence += int((metrics.directional_efficiency or 0.0) < (prev.directional_efficiency or 0.0) and (metrics.directional_efficiency or 0.0) < self.config.minimum_efficiency)
                if self._participation_direction == 1:
                    evidence += int((metrics.net_progress_atr or 0.0) < (prev.net_progress_atr or 0.0) and (metrics.net_progress_atr or 0.0) < self.config.minimum_progress_atr * 0.60)
                    evidence += int(metrics.down_evidence_count >= self.config.participation_minimum_evidence - 1)
                else:
                    evidence += int((metrics.net_progress_atr or 0.0) > (prev.net_progress_atr or 0.0) and (metrics.net_progress_atr or 0.0) > -self.config.minimum_progress_atr * 0.60)
                    evidence += int(metrics.up_evidence_count >= self.config.participation_minimum_evidence - 1)
                if evidence >= self.lifecycle_config.weakening_minimum_evidence:
                    self._participation_stage = LifecycleStage.WEAKENING
        return controlled_up, controlled_down

    def _nearest_reference(self, upper: bool, index: int) -> tuple[float | None, float | None, str | None]:
        atr = self._atr_values[index]
        if atr is None:
            return None, None, None
        price = self._high_values[index] if upper else self._low_values[index]
        candidates: list[tuple[float, float, str]] = []
        pivot = self._last_high_pivot if upper else self._last_low_pivot
        if pivot:
            candidates.append((pivot.price, pivot.atr_at_source, "PIVOT"))
        start = max(0, index - self.lifecycle_config.recent_level_lookback)
        if index > start:
            recent = max(self._high_values[start:index]) if upper else min(self._low_values[start:index])
            candidates.append((recent, float(atr), "RECENT_20"))
        if not candidates:
            return None, None, None
        level, ref_atr, source = min(candidates, key=lambda item: abs(price - item[0]))
        if abs(price - level) <= ref_atr * self.lifecycle_config.important_level_proximity_atr:
            return level, ref_atr, source
        return None, None, None

    def _update_absorption(self, index: int, metrics: VolumeParticipationMetrics) -> None:
        if not metrics.data_ready or index == 0:
            return
        cfg = self.lifecycle_config
        row, prev_row = self._rows[index], self._rows[index - 1]
        o, h, l, c = map(float, (row["open"], row["high"], row["low"], row["close"]))
        span = h - l
        close_loc = _safe_div(c - l, span, 0.5)
        upper_wick = _safe_div(h - max(o, c), span)
        lower_wick = _safe_div(min(o, c) - l, span)
        previous = self._metrics_history[-2] if len(self._metrics_history) >= 2 else metrics
        upper_deteriorating = (metrics.net_progress_atr or 0.0) < (previous.net_progress_atr or 0.0) or (metrics.directional_efficiency or 0.0) < (previous.directional_efficiency or 0.0)
        lower_deteriorating = (metrics.net_progress_atr or 0.0) > (previous.net_progress_atr or 0.0) or (metrics.directional_efficiency or 0.0) < (previous.directional_efficiency or 0.0)
        effort_mismatch = metrics.effort_result_class in {EffortResultClass.HIGH_EFFORT_WEAK_RESULT, EffortResultClass.VERY_HIGH_EFFORT_WEAK_RESULT}
        upper_ref, upper_atr, upper_source = self._nearest_reference(True, index)
        lower_ref, lower_atr, lower_source = self._nearest_reference(False, index)
        upper_evidence = sum((upper_wick >= cfg.absorption_minimum_wick_ratio, close_loc < 0.60, (metrics.directional_efficiency or 0.0) <= self.config.weak_result_efficiency_limit, abs(metrics.net_progress_atr or 0.0) <= self.config.weak_result_progress_limit, upper_deteriorating, (metrics.directional_value_pressure_5 or 0.0) < self.config.minimum_capital_pressure))
        lower_evidence = sum((lower_wick >= cfg.absorption_minimum_wick_ratio, close_loc > 0.40, (metrics.directional_efficiency or 0.0) <= self.config.weak_result_efficiency_limit, abs(metrics.net_progress_atr or 0.0) <= self.config.weak_result_progress_limit, lower_deteriorating, (metrics.directional_value_pressure_5 or 0.0) > -self.config.minimum_capital_pressure))
        upper_signal = effort_mismatch and upper_ref is not None and h >= float(prev_row["high"]) and (c > o or (metrics.net_progress_atr or 0.0) >= 0.0) and (upper_wick >= cfg.absorption_minimum_wick_ratio or close_loc < 0.60) and upper_evidence >= cfg.absorption_minimum_evidence
        lower_signal = effort_mismatch and lower_ref is not None and l <= float(prev_row["low"]) and (c < o or (metrics.net_progress_atr or 0.0) <= 0.0) and (lower_wick >= cfg.absorption_minimum_wick_ratio or close_loc > 0.40) and lower_evidence >= cfg.absorption_minimum_evidence

        active = self._absorption
        if active.stage == AbsorptionStage.CANDIDATE and active.candidate_index is not None:
            age = index - active.candidate_index
            if active.side == AbsorptionSide.UPPER:
                invalid = c > float(active.candidate_high) + float(active.frozen_buffer) and metrics.up_evidence_count >= self.config.participation_minimum_evidence
                confirm = index > active.candidate_index and age <= cfg.absorption_confirmation_window and h <= float(active.candidate_high) + float(active.frozen_buffer) and c <= float(active.candidate_mid)
            else:
                invalid = c < float(active.candidate_low) - float(active.frozen_buffer) and metrics.down_evidence_count >= self.config.participation_minimum_evidence
                confirm = index > active.candidate_index and age <= cfg.absorption_confirmation_window and l >= float(active.candidate_low) - float(active.frozen_buffer) and c >= float(active.candidate_mid)
            if invalid:
                self._absorption = replace(active, stage=AbsorptionStage.INVALIDATED); return
            if confirm:
                self._absorption = replace(active, stage=AbsorptionStage.CONFIRMED); self._absorption_hold_until = index + 2; return
            if age > cfg.absorption_confirmation_window:
                self._absorption = replace(active, stage=AbsorptionStage.EXPIRED); return

        if self._absorption.stage == AbsorptionStage.CONFIRMED and index <= self._absorption_hold_until:
            return
        if index <= self._absorption_hold_until:
            return
        if upper_signal and lower_signal:
            if upper_wick > lower_wick and close_loc < 0.50: lower_signal = False
            elif lower_wick > upper_wick and close_loc > 0.50: upper_signal = False
            else: upper_signal = lower_signal = False
        if upper_signal:
            assert upper_ref is not None and upper_atr is not None
            self._absorption = AbsorptionEvent(AbsorptionSide.UPPER, AbsorptionStage.CANDIDATE, index, upper_ref, upper_source, h, l, (h + l) / 2.0, upper_atr, upper_atr * cfg.break_buffer_atr)
        elif lower_signal:
            assert lower_ref is not None and lower_atr is not None
            self._absorption = AbsorptionEvent(AbsorptionSide.LOWER, AbsorptionStage.CANDIDATE, index, lower_ref, lower_source, h, l, (h + l) / 2.0, lower_atr, lower_atr * cfg.break_buffer_atr)

    def _crossed_reference(self, index: int) -> tuple[int, float | None, float | None, str | None]:
        if index == 0:
            return 0, None, None, None
        close, prev = self._close_values[index], self._close_values[index - 1]
        candidates: list[tuple[int, float, float, str]] = []
        if self._last_high_pivot and prev <= self._last_high_pivot.price < close:
            candidates.append((1, self._last_high_pivot.price, self._last_high_pivot.atr_at_source, "PIVOT"))
        if self._last_low_pivot and prev >= self._last_low_pivot.price > close:
            candidates.append((-1, self._last_low_pivot.price, self._last_low_pivot.atr_at_source, "PIVOT"))
        start = max(0, index - self.lifecycle_config.recent_level_lookback)
        atr = self._atr_values[index]
        if index > start and atr is not None:
            rh = max(self._high_values[start:index]); rl = min(self._low_values[start:index])
            if prev <= rh < close: candidates.append((1, rh, float(atr), "RECENT_20"))
            if prev >= rl > close: candidates.append((-1, rl, float(atr), "RECENT_20"))
        if not candidates:
            return 0, None, None, None
        return min(candidates, key=lambda item: abs(close - item[1]))

    def _update_break(self, index: int, metrics: VolumeParticipationMetrics) -> None:
        if not metrics.data_ready:
            return
        if self._break.stage in {BreakStage.UNSUPPORTED, BreakStage.RECLAIMED}:
            self._break = BreakParticipationEvent()
        if self._break.stage == BreakStage.NONE:
            direction, level, atr, source = self._crossed_reference(index)
            if direction and level is not None and atr is not None:
                row = self._rows[index]
                loc = _safe_div(float(row["close"]) - float(row["low"]), float(row["high"]) - float(row["low"]), 0.5)
                valid = direction == 1 and loc >= 0.55 and (metrics.net_progress_atr or 0.0) > 0.0 or direction == -1 and loc <= 0.45 and (metrics.net_progress_atr or 0.0) < 0.0
                if valid:
                    self._break = BreakParticipationEvent(direction, BreakStage.DEVELOPING, index, level, source, atr, atr * self.lifecycle_config.break_buffer_atr)
            return
        active = self._break
        assert active.start_index is not None and active.level is not None and active.frozen_buffer is not None
        close = self._close_values[index]
        if active.direction == 1 and close < active.level or active.direction == -1 and close > active.level:
            self._break = replace(active, stage=BreakStage.RECLAIMED, reason="level reclaimed"); return
        age = index - active.start_index
        accepted = close >= active.level + active.frozen_buffer if active.direction == 1 else close <= active.level - active.frozen_buffer
        result_ok = metrics.up_evidence_count >= self.config.participation_minimum_evidence if active.direction == 1 else metrics.down_evidence_count >= self.config.participation_minimum_evidence
        support = (metrics.rvol or 0.0) >= self.config.rising_rvol and (metrics.rtv or 0.0) >= self.config.rising_rtv and result_ok
        if active.stage == BreakStage.DEVELOPING and index > active.start_index and age <= self.lifecycle_config.breakout_confirmation_bars and accepted and support:
            self._break = replace(active, stage=BreakStage.SUPPORTED); return
        if active.stage == BreakStage.DEVELOPING and age > self.lifecycle_config.breakout_confirmation_bars:
            self._break = replace(active, stage=BreakStage.UNSUPPORTED, reason="participation support incomplete"); return
        if active.stage == BreakStage.SUPPORTED:
            row = self._rows[index]
            low_participation = (metrics.rvol or 0.0) <= 1.05 and (metrics.rtv or 0.0) <= 1.05
            retest = float(row["low"]) <= active.level + active.frozen_buffer if active.direction == 1 else float(row["high"]) >= active.level - active.frozen_buffer
            accepted_side = close >= active.level if active.direction == 1 else close <= active.level
            if retest and accepted_side and low_participation:
                self._break = replace(active, stage=BreakStage.PROTECTED)

    def _sync_lifecycle_export(self, controlled_up: bool, controlled_down: bool) -> None:
        self.lifecycle_export = ParticipationLifecycleExport(
            self._participation_direction, self._participation_stage.value, controlled_up, controlled_down,
            self._absorption.side.value, self._absorption.stage.value, self._absorption.reference_level, self._absorption.reference_source, self._absorption.frozen_atr, self._absorption.frozen_buffer,
            self._break.direction, self._break.stage.value, self._break.level, self._break.reference_source, self._break.frozen_atr, self._break.frozen_buffer,
            self._last_high_pivot.price if self._last_high_pivot else None, self._last_high_pivot.known_index if self._last_high_pivot else None,
            self._last_low_pivot.price if self._last_low_pivot else None, self._last_low_pivot.known_index if self._last_low_pivot else None,
        )

    def update(self, bar: Any) -> EngineResult | None:
        row = dict(bar) if not isinstance(bar, dict) else bar.copy()
        if row.get("is_closed") is False or row.get("is_complete") is False:
            return self._lifecycle_snapshot or self._snapshot
        result = super().update(row)
        if result is None:
            return None
        index, metrics = len(self._rows) - 1, self._metrics_history[-1]
        self._update_pivot(index)
        controlled_up, controlled_down = self._update_participation_lifecycle(index, metrics)
        self._update_absorption(index, metrics)
        self._update_break(index, metrics)
        self._sync_lifecycle_export(controlled_up, controlled_down)
        events = list(result.events)
        if controlled_up: events.append("CONTROLLED_UP_PULLBACK")
        if controlled_down: events.append("CONTROLLED_DOWN_REACTION")
        if self._absorption.stage != AbsorptionStage.NONE: events.append(f"ABSORPTION_{self._absorption.side.value}_{self._absorption.stage.value}")
        if self._break.stage != BreakStage.NONE: events.append(f"BREAK_{self._break.direction}_{self._break.stage.value}")
        enriched = EngineResult(result.engine, result.state, result.timestamp, result.direction, result.score, result.quality, result.levels, tuple(events), result.reasons + (f"participation_stage={self._participation_stage.value}", f"absorption={self._absorption.side.value}/{self._absorption.stage.value}", f"break={self._break.direction}/{self._break.stage.value}"), True)
        self._snapshot = self._lifecycle_snapshot = enriched
        return enriched
