from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .models import Direction, EngineResult
from .volume_participation_engine import VolumeLevel, VolumeParticipationConfig, VolumeParticipationMetrics, _safe_div
from .volume_participation_lifecycle import (
    AbsorptionSide,
    AbsorptionStage,
    BreakStage,
    LifecycleStage,
    ParticipationLifecycleConfig,
    VolumeParticipationEngine as LifecycleVolumeParticipationEngine,
)


class FinalParticipationState(StrEnum):
    PENDING = "PARTICIPATION_PENDING"
    VOLUME_UNAVAILABLE = "PARTICIPATION_VOLUME_UNAVAILABLE"
    NEUTRAL = "PARTICIPATION_NEUTRAL"
    LOW_PARTICIPATION = "PARTICIPATION_LOW"
    RISING_PARTICIPATION = "PARTICIPATION_RISING"
    ABNORMAL_VOLUME = "PARTICIPATION_ABNORMAL_VOLUME"
    ABNORMAL_CAPITAL = "PARTICIPATION_ABNORMAL_CAPITAL"
    ONE_BAR_SHOCK = "PARTICIPATION_ONE_BAR_SHOCK"
    UP_CANDIDATE = "PARTICIPATION_UP_CANDIDATE"
    DOWN_CANDIDATE = "PARTICIPATION_DOWN_CANDIDATE"
    UP_CONFIRMED = "PARTICIPATION_UP_CONFIRMED"
    DOWN_CONFIRMED = "PARTICIPATION_DOWN_CONFIRMED"
    UP_PROTECTED = "PARTICIPATION_UP_PROTECTED"
    DOWN_PROTECTED = "PARTICIPATION_DOWN_PROTECTED"
    UP_WEAKENING = "PARTICIPATION_UP_WEAKENING"
    DOWN_WEAKENING = "PARTICIPATION_DOWN_WEAKENING"
    UP_ENDED = "PARTICIPATION_UP_ENDED"
    DOWN_ENDED = "PARTICIPATION_DOWN_ENDED"
    UPPER_ABSORPTION_CANDIDATE = "PARTICIPATION_UPPER_ABSORPTION_CANDIDATE"
    LOWER_ABSORPTION_CANDIDATE = "PARTICIPATION_LOWER_ABSORPTION_CANDIDATE"
    UPPER_ABSORPTION_CONFIRMED = "PARTICIPATION_UPPER_ABSORPTION_CONFIRMED"
    LOWER_ABSORPTION_CONFIRMED = "PARTICIPATION_LOWER_ABSORPTION_CONFIRMED"
    UPPER_ABSORPTION_INVALIDATED = "PARTICIPATION_UPPER_ABSORPTION_INVALIDATED"
    LOWER_ABSORPTION_INVALIDATED = "PARTICIPATION_LOWER_ABSORPTION_INVALIDATED"
    UP_BREAK_SUPPORTED = "PARTICIPATION_UP_BREAK_SUPPORTED"
    DOWN_BREAK_SUPPORTED = "PARTICIPATION_DOWN_BREAK_SUPPORTED"
    UP_BREAK_UNSUPPORTED = "PARTICIPATION_UP_BREAK_UNSUPPORTED"
    DOWN_BREAK_UNSUPPORTED = "PARTICIPATION_DOWN_BREAK_UNSUPPORTED"
    UP_BREAK_RECLAIMED = "PARTICIPATION_UP_BREAK_RECLAIMED"
    DOWN_BREAK_RECLAIMED = "PARTICIPATION_DOWN_BREAK_RECLAIMED"
    CONFLICT = "PARTICIPATION_CONFLICT"


@dataclass(frozen=True, slots=True)
class UnifiedParticipationExport:
    state: str | None = None
    support_direction: int = 0
    engine_direction: int = 0
    quality: float | None = None
    magnitude_quality: float | None = None
    rvol: float | None = None
    relative_traded_value: float | None = None
    volume_level: str | None = None
    capital_level: str | None = None
    volume_regime: int = 0
    capital_regime: int = 0
    directional_value_pressure_5: float | None = None
    directional_value_pressure_10: float | None = None
    net_progress_atr: float | None = None
    directional_efficiency: float | None = None
    effort_result_class: str | None = None
    participation_direction: int = 0
    participation_stage: str = LifecycleStage.NONE.value
    controlled_pullback: bool = False
    controlled_reaction: bool = False
    break_direction: int = 0
    break_stage: str = BreakStage.NONE.value
    break_level: float | None = None
    break_reference_source: str | None = None
    break_frozen_atr: float | None = None
    break_frozen_buffer: float | None = None
    absorption_side: str = AbsorptionSide.NONE.value
    absorption_stage: str = AbsorptionStage.NONE.value
    absorption_reference_level: float | None = None
    absorption_reference_source: str | None = None
    absorption_frozen_atr: float | None = None
    absorption_frozen_buffer: float | None = None
    last_pivot_high: float | None = None
    last_pivot_high_known_index: int | None = None
    last_pivot_low: float | None = None
    last_pivot_low_known_index: int | None = None
    heavy_conflict: bool = False
    one_bar_shock: bool = False
    shock_direction: int = 0


class VolumeParticipationEngine(LifecycleVolumeParticipationEngine):
    """Final resolver/export layer over the Tur-1 math and Tur-2 lifecycle."""

    def __init__(
        self,
        config: VolumeParticipationConfig | None = None,
        lifecycle_config: ParticipationLifecycleConfig | None = None,
    ) -> None:
        super().__init__(config, lifecycle_config)
        self.final_export = UnifiedParticipationExport()

    def _reset(self) -> None:
        super()._reset()
        self.final_export = UnifiedParticipationExport()

    def _shock(self, metrics: VolumeParticipationMetrics) -> tuple[bool, int]:
        if not metrics.data_ready or len(self._rows) < 2:
            return False, 0
        atr_series = self._atr_series()
        prior_atr = atr_series[-2] if len(atr_series) >= 2 else None
        if prior_atr is None or prior_atr <= 0:
            return False, 0
        row = self._rows[-1]
        o, h, l, c = map(float, (row["open"], row["high"], row["low"], row["close"]))
        span = h - l
        close_location = _safe_div(c - l, span, 0.5)
        range_to_atr = _safe_div(max(h - l, abs(h - float(self._rows[-2]["close"])), abs(l - float(self._rows[-2]["close"]))), prior_atr)
        body_to_atr = _safe_div(abs(c - o), prior_atr)
        extreme = range_to_atr >= 2.30 or body_to_atr >= 1.50
        abnormal = metrics.volume_level == VolumeLevel.ABNORMAL or (
            metrics.volume_level == VolumeLevel.HIGH and metrics.capital_level == VolumeLevel.ABNORMAL
        )
        prior_developing = False
        if len(self._metrics_history) >= 2:
            prev = self._metrics_history[-2]
            prior_developing = prev.volume_level in {VolumeLevel.RISING, VolumeLevel.HIGH, VolumeLevel.ABNORMAL} or prev.capital_level in {VolumeLevel.RISING, VolumeLevel.HIGH, VolumeLevel.ABNORMAL}
        shock = abnormal and extreme and not prior_developing
        if not shock:
            return False, 0
        if c > o and close_location >= self.config.up_close_location and (metrics.net_progress_atr or 0.0) > 0.0:
            return True, 1
        if c < o and close_location <= self.config.down_close_location and (metrics.net_progress_atr or 0.0) < 0.0:
            return True, -1
        return True, 0

    def _heavy_conflict(self, metrics: VolumeParticipationMetrics) -> bool:
        if not metrics.data_ready:
            return False
        pressure = abs(metrics.directional_value_pressure_5 or 0.0)
        directional_proxy = (
            metrics.up_evidence_count >= self.config.participation_minimum_evidence
            and metrics.down_evidence_count >= self.config.participation_minimum_evidence
            and abs(metrics.up_evidence_count - metrics.down_evidence_count) <= 1
            and pressure <= self.config.minimum_capital_pressure
        )
        confirmed_absorption = (
            (metrics.up_confirmed and self._absorption.side == AbsorptionSide.UPPER and self._absorption.stage == AbsorptionStage.CONFIRMED)
            or (metrics.down_confirmed and self._absorption.side == AbsorptionSide.LOWER and self._absorption.stage == AbsorptionStage.CONFIRMED)
        )
        breakout_absorption = (
            (self._break.direction == 1 and self._break.stage in {BreakStage.SUPPORTED, BreakStage.PROTECTED} and self._absorption.side == AbsorptionSide.UPPER and self._absorption.stage == AbsorptionStage.CONFIRMED)
            or (self._break.direction == -1 and self._break.stage in {BreakStage.SUPPORTED, BreakStage.PROTECTED} and self._absorption.side == AbsorptionSide.LOWER and self._absorption.stage == AbsorptionStage.CONFIRMED)
        )
        direction_breakout = (
            (metrics.up_confirmed and self._break.direction == -1 and self._break.stage in {BreakStage.SUPPORTED, BreakStage.PROTECTED})
            or (metrics.down_confirmed and self._break.direction == 1 and self._break.stage in {BreakStage.SUPPORTED, BreakStage.PROTECTED})
        )
        near_high = self._nearest_reference(True, len(self._rows) - 1)[0] is not None
        near_low = self._nearest_reference(False, len(self._rows) - 1)[0] is not None
        capital_price = (
            metrics.effort_result_class.value == "VERY_HIGH_EFFORT_WEAK_RESULT"
            and metrics.up_evidence_count >= self.config.participation_minimum_evidence - 1
            and metrics.down_evidence_count >= self.config.participation_minimum_evidence - 1
            and pressure <= self.config.minimum_capital_pressure * 0.50
            and not near_high
            and not near_low
        )
        return directional_proxy or confirmed_absorption or breakout_absorption or direction_breakout or capital_price

    def _resolve_final(self, metrics: VolumeParticipationMetrics, shock: bool) -> FinalParticipationState:
        if not metrics.data_ready:
            return FinalParticipationState.PENDING if metrics.volume_usable or metrics.capital_usable else FinalParticipationState.VOLUME_UNAVAILABLE
        if self._heavy_conflict(metrics):
            return FinalParticipationState.CONFLICT
        if self._absorption.stage == AbsorptionStage.CONFIRMED:
            return FinalParticipationState.UPPER_ABSORPTION_CONFIRMED if self._absorption.side == AbsorptionSide.UPPER else FinalParticipationState.LOWER_ABSORPTION_CONFIRMED
        if self._absorption.stage == AbsorptionStage.INVALIDATED:
            return FinalParticipationState.UPPER_ABSORPTION_INVALIDATED if self._absorption.side == AbsorptionSide.UPPER else FinalParticipationState.LOWER_ABSORPTION_INVALIDATED
        if self._break.stage == BreakStage.RECLAIMED:
            return FinalParticipationState.UP_BREAK_RECLAIMED if self._break.direction == 1 else FinalParticipationState.DOWN_BREAK_RECLAIMED
        if self._break.stage == BreakStage.UNSUPPORTED:
            return FinalParticipationState.UP_BREAK_UNSUPPORTED if self._break.direction == 1 else FinalParticipationState.DOWN_BREAK_UNSUPPORTED
        if self._break.stage in {BreakStage.SUPPORTED, BreakStage.PROTECTED}:
            return FinalParticipationState.UP_BREAK_SUPPORTED if self._break.direction == 1 else FinalParticipationState.DOWN_BREAK_SUPPORTED
        if metrics.up_confirmed:
            return FinalParticipationState.UP_CONFIRMED
        if metrics.down_confirmed:
            return FinalParticipationState.DOWN_CONFIRMED
        if self._participation_stage == LifecycleStage.PROTECTED:
            return FinalParticipationState.UP_PROTECTED if self._participation_direction == 1 else FinalParticipationState.DOWN_PROTECTED
        if shock:
            return FinalParticipationState.ONE_BAR_SHOCK
        if self._absorption.stage == AbsorptionStage.CANDIDATE:
            return FinalParticipationState.UPPER_ABSORPTION_CANDIDATE if self._absorption.side == AbsorptionSide.UPPER else FinalParticipationState.LOWER_ABSORPTION_CANDIDATE
        if metrics.up_candidate:
            return FinalParticipationState.UP_CANDIDATE
        if metrics.down_candidate:
            return FinalParticipationState.DOWN_CANDIDATE
        if self._participation_stage == LifecycleStage.WEAKENING:
            return FinalParticipationState.UP_WEAKENING if self._participation_direction == 1 else FinalParticipationState.DOWN_WEAKENING
        if self._participation_stage == LifecycleStage.CLOSED:
            return FinalParticipationState.UP_ENDED if self._participation_direction == 1 else FinalParticipationState.DOWN_ENDED
        if metrics.volume_level == VolumeLevel.ABNORMAL:
            return FinalParticipationState.ABNORMAL_VOLUME
        if metrics.capital_level == VolumeLevel.ABNORMAL and metrics.volume_level in {VolumeLevel.RISING, VolumeLevel.HIGH, VolumeLevel.ABNORMAL}:
            return FinalParticipationState.ABNORMAL_CAPITAL
        if metrics.volume_level in {VolumeLevel.RISING, VolumeLevel.HIGH, VolumeLevel.ABNORMAL}:
            return FinalParticipationState.RISING_PARTICIPATION
        if metrics.volume_level in {VolumeLevel.VERY_LOW, VolumeLevel.LOW} and metrics.capital_level in {VolumeLevel.VERY_LOW, VolumeLevel.LOW}:
            return FinalParticipationState.LOW_PARTICIPATION
        return FinalParticipationState.NEUTRAL

    @staticmethod
    def _support_direction(state: FinalParticipationState) -> int:
        if state in {FinalParticipationState.UP_CONFIRMED, FinalParticipationState.UP_PROTECTED, FinalParticipationState.UP_BREAK_SUPPORTED, FinalParticipationState.LOWER_ABSORPTION_CONFIRMED}:
            return 2
        if state in {FinalParticipationState.UP_CANDIDATE, FinalParticipationState.LOWER_ABSORPTION_CANDIDATE}:
            return 1
        if state in {FinalParticipationState.DOWN_CONFIRMED, FinalParticipationState.DOWN_PROTECTED, FinalParticipationState.DOWN_BREAK_SUPPORTED, FinalParticipationState.UPPER_ABSORPTION_CONFIRMED}:
            return -2
        if state in {FinalParticipationState.DOWN_CANDIDATE, FinalParticipationState.UPPER_ABSORPTION_CANDIDATE}:
            return -1
        return 0

    @staticmethod
    def _engine_direction(state: FinalParticipationState) -> Direction:
        if state in {FinalParticipationState.UP_CONFIRMED, FinalParticipationState.UP_PROTECTED, FinalParticipationState.UP_BREAK_SUPPORTED, FinalParticipationState.LOWER_ABSORPTION_CONFIRMED}:
            return Direction.UP
        if state in {FinalParticipationState.DOWN_CONFIRMED, FinalParticipationState.DOWN_PROTECTED, FinalParticipationState.DOWN_BREAK_SUPPORTED, FinalParticipationState.UPPER_ABSORPTION_CONFIRMED}:
            return Direction.DOWN
        return Direction.NEUTRAL

    def _build_final_export(self, state: FinalParticipationState, engine_direction: Direction, shock: bool, shock_direction: int) -> UnifiedParticipationExport:
        core = self.export_contract
        life = self.lifecycle_export
        return UnifiedParticipationExport(
            state=state.value,
            support_direction=self._support_direction(state),
            engine_direction=int(engine_direction),
            quality=core.quality,
            magnitude_quality=core.magnitude_quality,
            rvol=core.rvol,
            relative_traded_value=core.relative_traded_value,
            volume_level=core.volume_level,
            capital_level=core.capital_level,
            volume_regime=core.volume_regime,
            capital_regime=core.capital_regime,
            directional_value_pressure_5=core.directional_value_pressure_5,
            directional_value_pressure_10=core.directional_value_pressure_10,
            net_progress_atr=core.net_progress_atr,
            directional_efficiency=core.directional_efficiency,
            effort_result_class=core.effort_result_class,
            participation_direction=life.participation_direction,
            participation_stage=life.participation_stage,
            controlled_pullback=life.controlled_pullback,
            controlled_reaction=life.controlled_reaction,
            break_direction=life.break_direction,
            break_stage=life.break_stage,
            break_level=life.break_level,
            break_reference_source=life.break_reference_source,
            break_frozen_atr=life.break_frozen_atr,
            break_frozen_buffer=life.break_frozen_buffer,
            absorption_side=life.absorption_side,
            absorption_stage=life.absorption_stage,
            absorption_reference_level=life.absorption_reference_level,
            absorption_reference_source=life.absorption_reference_source,
            absorption_frozen_atr=life.absorption_frozen_atr,
            absorption_frozen_buffer=life.absorption_frozen_buffer,
            last_pivot_high=life.last_pivot_high,
            last_pivot_high_known_index=life.last_pivot_high_known_index,
            last_pivot_low=life.last_pivot_low,
            last_pivot_low_known_index=life.last_pivot_low_known_index,
            heavy_conflict=state == FinalParticipationState.CONFLICT,
            one_bar_shock=shock,
            shock_direction=shock_direction,
        )

    def update(self, bar: Any) -> EngineResult | None:
        row = dict(bar) if not isinstance(bar, dict) else bar.copy()
        if row.get("is_closed") is False or row.get("is_complete") is False:
            return self._snapshot
        base_result = super().update(row)
        if base_result is None:
            return None
        metrics = self._metrics_history[-1]
        shock, shock_direction = self._shock(metrics)
        state = self._resolve_final(metrics, shock)
        direction = self._engine_direction(state)
        final = EngineResult(
            engine=base_result.engine,
            state=state.value,
            timestamp=base_result.timestamp,
            direction=direction,
            score=base_result.score,
            quality=base_result.quality,
            levels=base_result.levels,
            events=base_result.events + ((f"SHOCK_{shock_direction}",) if shock else ()),
            reasons=base_result.reasons + (f"final_state={state.value}", f"support_direction={self._support_direction(state)}"),
            is_confirmed=True,
        )
        self.final_export = self._build_final_export(state, direction, shock, shock_direction)
        self._snapshot = self._lifecycle_snapshot = final
        return final
