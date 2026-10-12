from __future__ import annotations

from dataclasses import replace
from typing import Any

import pandas as pd

from .market_structure import (
    SCOPE_EXTERNAL,
    SCOPE_INTERNAL,
    SIDE_HIGH,
    SIDE_LOW,
    MarketStructureConfig,
    MarketStructureEngine as _SwingCoreEngine,
    SwingPoint,
)
from .market_structure_event_runtime import RuntimeMarketStructureEventLedger
from .market_structure_events import (
    MarketStructureEventRecord,
    MarketStructureScopeSnapshot,
)
from .market_structure_runtime_bridge import MarketStructureRuntime
from .market_structure_state import BreakConfig
from .models import Direction, EngineResult


class MarketStructureEngine(_SwingCoreEngine):
    """Integrated ARGENT Market Structure engine.

    The swing detector remains the validated Tur 1 implementation. The runtime
    layer adds Tur 2 BOS/CHoCH/transition/role/break lifecycle and evidence/export
    without mixing TradingView visual state into the math path.
    """

    def __init__(
        self,
        config: MarketStructureConfig | None = None,
        break_config: BreakConfig | None = None,
    ) -> None:
        self.break_config = break_config or BreakConfig(
            profile=(config.profile if config is not None else "Dengeli"),
            min_tick=(config.min_tick if config is not None else 0.01),
        )
        super().__init__(config)

    def reset(self) -> None:
        super().reset()
        self._runtime = MarketStructureRuntime(self.break_config)
        self._event_ledger = RuntimeMarketStructureEventLedger()
        self._export = None
        self._public_export_bar: int | None = None
        self._public_export_cache = None

    def _candidate_update(self, candidate, incoming, locked_by_break: bool):
        runtime_lock = self._runtime.locks_candidate(incoming.scope, candidate) if hasattr(self, "_runtime") else False
        return super()._candidate_update(candidate, incoming, locked_by_break=locked_by_break or runtime_lock)

    def _commit_provisional(self, scope_state, snapshot: SwingPoint, confirm_bar: int, evidence: str, quality_floor: float) -> SwingPoint:
        if not snapshot.valid:
            return SwingPoint()
        previous_same = self._last_historical(scope_state.swings, snapshot.side)
        previous_opposite = self._last_historical(scope_state.swings, SIDE_LOW if snapshot.side == SIDE_HIGH else SIDE_HIGH)
        confirmed = self._promote(snapshot, previous_same, previous_opposite, confirm_bar)
        confirmed = replace(
            confirmed,
            evidence_text=evidence,
            quality=max(confirmed.quality or 0.0, quality_floor),
        )
        scope_state.swings.append(confirmed)
        if confirmed.side == SIDE_HIGH:
            scope_state.last_confirmed_high_identity = confirmed.identity
            if scope_state.high_candidate.valid and scope_state.high_candidate.identity == confirmed.identity and scope_state.high_candidate.source_bar == confirmed.source_bar:
                scope_state.high_candidate = SwingPoint()
        else:
            scope_state.last_confirmed_low_identity = confirmed.identity
            if scope_state.low_candidate.valid and scope_state.low_candidate.identity == confirmed.identity and scope_state.low_candidate.source_bar == confirmed.source_bar:
                scope_state.low_candidate = SwingPoint()
        return confirmed

    def update(self, bar: pd.Series | dict[str, Any]) -> EngineResult | None:
        row = dict(bar) if isinstance(bar, dict) else bar.to_dict()
        if not bool(row.get("is_closed", True)) or not bool(row.get("is_complete", True)):
            return self._snapshot

        base = super().update(row)
        if base is None:
            return None

        bar_index = len(self._rows) - 1
        clean = self._rows[-1]
        previous_atr = self._atr_values[-2] if len(self._atr_values) >= 2 else None
        current_atr = self._atr_values[-1] if self._atr_values else None
        safe_atr = max(float(previous_atr or current_atr or self._tr_values[-1]), self.config.min_tick)

        structure_events = []
        structure_events.extend(
            self._runtime.process_scope(
                scope="EXTERNAL",
                swings=self._external.swings,
                high_candidate=self._external.high_candidate,
                low_candidate=self._external.low_candidate,
                bar_index=bar_index,
                open_=clean["open"],
                high=clean["high"],
                low=clean["low"],
                close=clean["close"],
                safe_atr=safe_atr,
                commit_provisional=lambda snapshot, confirm_bar, evidence, quality_floor: self._commit_provisional(
                    self._external, snapshot, confirm_bar, evidence, quality_floor
                ),
            )
        )
        structure_events.extend(
            self._runtime.process_scope(
                scope="INTERNAL",
                swings=self._internal.swings,
                high_candidate=self._internal.high_candidate,
                low_candidate=self._internal.low_candidate,
                bar_index=bar_index,
                open_=clean["open"],
                high=clean["high"],
                low=clean["low"],
                close=clean["close"],
                safe_atr=safe_atr,
                commit_provisional=lambda snapshot, confirm_bar, evidence, quality_floor: self._commit_provisional(
                    self._internal, snapshot, confirm_bar, evidence, quality_floor
                ),
            )
        )

        self._event_ledger.extend(structure_events, self._rows)

        score = self._runtime.score(bar_index=bar_index)
        runtime_export = self._runtime.export(
            self._external.swings,
            self._internal.swings,
            bar_index=bar_index,
        )
        # Keep the hot per-bar path on static annotations. Dynamic ``age_bars`` is
        # materialized lazily by export_contract/event_history only when a consumer
        # actually reads the public event history.
        event_history = self._event_ledger.static_snapshot()
        latest_external = self._event_ledger.latest_static(scope=SCOPE_EXTERNAL)
        latest_internal = self._event_ledger.latest_static(scope=SCOPE_INTERNAL)
        external = self._runtime.external.context
        internal = self._runtime.internal.context
        self._export = replace(
            runtime_export,
            events=event_history,
            latest_external_event=latest_external,
            latest_internal_event=latest_internal,
            external_scope=MarketStructureScopeSnapshot.from_context(
                external,
                latest_event=latest_external,
            ),
            internal_scope=MarketStructureScopeSnapshot.from_context(
                internal,
                latest_event=latest_internal,
            ),
        )
        self._public_export_bar = None
        self._public_export_cache = None

        if external.direction > 0:
            direction = Direction.UP
        elif external.direction < 0:
            direction = Direction.DOWN
        else:
            direction = Direction.NEUTRAL

        levels = self._public_levels()
        export_levels = {
            "external_protected_low": self._export.external_protected_low,
            "external_protected_high": self._export.external_protected_high,
            "external_weak_low": self._export.external_weak_low,
            "external_weak_high": self._export.external_weak_high,
            "internal_protected_low": self._export.internal_protected_low,
            "internal_protected_high": self._export.internal_protected_high,
            "internal_weak_low": self._export.internal_weak_low,
            "internal_weak_high": self._export.internal_weak_high,
        }
        levels.update({key: float(value) for key, value in export_levels.items() if value is not None})

        event_names = list(base.events)
        event_names.extend(f"{event.scope}:{event.event_type}:{event.direction}:{event.identity}" for event in structure_events)
        reasons = [event.evidence_text for event in structure_events if event.evidence_text]
        if external.evidence_text:
            reasons.append(external.evidence_text)
        if external.conflict_text:
            reasons.append(external.conflict_text)

        self._snapshot = EngineResult(
            engine=self.name,
            state=external.state,
            timestamp=clean["timestamp"],
            direction=direction,
            score=score,
            quality=external.quality if external.quality else None,
            levels=levels,
            events=tuple(event_names),
            reasons=tuple(reasons),
            is_confirmed=True,
        )
        return self._snapshot

    @property
    def event_history(self) -> tuple[MarketStructureEventRecord, ...]:
        if not self._rows:
            return ()
        return self._event_ledger.snapshot(current_bar=len(self._rows) - 1)

    @property
    def latest_external_event(self) -> MarketStructureEventRecord | None:
        if not self._rows:
            return None
        return self._event_ledger.latest_for_scope(
            current_bar=len(self._rows) - 1,
            scope=SCOPE_EXTERNAL,
        )

    @property
    def latest_internal_event(self) -> MarketStructureEventRecord | None:
        if not self._rows:
            return None
        return self._event_ledger.latest_for_scope(
            current_bar=len(self._rows) - 1,
            scope=SCOPE_INTERNAL,
        )

    @property
    def external_context(self):
        return self._runtime.external.context

    @property
    def internal_context(self):
        return self._runtime.internal.context

    @property
    def export_contract(self):
        if self._export is None or not self._rows:
            return self._export
        current_bar = len(self._rows) - 1
        if self._public_export_bar == current_bar and self._public_export_cache is not None:
            return self._public_export_cache

        event_history = self._event_ledger.snapshot(current_bar=current_bar)
        latest_external = self._event_ledger.latest_for_scope(
            current_bar=current_bar,
            scope=SCOPE_EXTERNAL,
        )
        latest_internal = self._event_ledger.latest_for_scope(
            current_bar=current_bar,
            scope=SCOPE_INTERNAL,
        )
        external = self._runtime.external.context
        internal = self._runtime.internal.context
        self._public_export_cache = replace(
            self._export,
            events=event_history,
            latest_external_event=latest_external,
            latest_internal_event=latest_internal,
            external_scope=MarketStructureScopeSnapshot.from_context(
                external,
                latest_event=latest_external,
            ),
            internal_scope=MarketStructureScopeSnapshot.from_context(
                internal,
                latest_event=latest_internal,
            ),
        )
        self._public_export_bar = current_bar
        return self._public_export_cache

    @property
    def external_break_candidate(self):
        return self._runtime.external.candidate

    @property
    def internal_break_candidate(self):
        return self._runtime.internal.candidate
