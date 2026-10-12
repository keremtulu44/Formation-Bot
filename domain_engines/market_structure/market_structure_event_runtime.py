from __future__ import annotations

from dataclasses import replace

from .market_structure_events import (
    MarketStructureEventLedger,
    MarketStructureEventRecord,
    StructureEventOutcome,
    StructureEventRelevance,
    StructureEventValidity,
)
from .market_structure_state import EVENT_BOS, EVENT_CHOCH, EVENT_TRANSITION_FAIL


class RuntimeMarketStructureEventLedger(MarketStructureEventLedger):
    """Event ledger with exact annotation parity and lazy dynamic ages.

    Event lifecycle annotations change only when a new Structure event is appended.
    The static annotation graph is therefore cached across ordinary bars. Dynamic
    ``age_bars`` values are materialized only for external reads that require them.
    """

    def __init__(self) -> None:
        super().__init__()
        self._static_cache: tuple[MarketStructureEventRecord, ...] | None = ()
        self._latest_by_scope: dict[str, MarketStructureEventRecord] = {}
        self._snapshot_bar: int | None = None
        self._snapshot_cache: tuple[MarketStructureEventRecord, ...] = ()

    def reset(self) -> None:
        super().reset()
        self._static_cache = ()
        self._latest_by_scope = {}
        self._snapshot_bar = None
        self._snapshot_cache = ()

    def append(self, event, rows):
        record = super().append(event, rows)
        self._static_cache = None
        self._latest_by_scope = {}
        self._snapshot_bar = None
        self._snapshot_cache = ()
        return record

    def _static_snapshot(self) -> tuple[MarketStructureEventRecord, ...]:
        if self._static_cache is not None:
            return self._static_cache

        annotated: list[MarketStructureEventRecord] = []
        latest_current: dict[tuple[str, str, int], int] = {}
        pending_choch: dict[tuple[str, int], list[int]] = {}

        def current_key(record: MarketStructureEventRecord) -> tuple[str, str, int]:
            return (record.scope, record.event_type, int(record.direction))

        def clear_current(index: int) -> None:
            key = current_key(annotated[index])
            if latest_current.get(key) == index:
                latest_current.pop(key, None)

        for base_record in self._records:
            key = current_key(base_record)
            same_index = latest_current.get(key)
            if same_index is not None:
                annotated[same_index] = replace(
                    annotated[same_index],
                    relevance=StructureEventRelevance.SUPERSEDED,
                )
                latest_current.pop(key, None)

            if base_record.event_type == EVENT_BOS:
                stack = pending_choch.get((base_record.scope, int(base_record.direction)))
                if stack:
                    choch_index = stack.pop()
                    annotated[choch_index] = replace(
                        annotated[choch_index],
                        relevance=StructureEventRelevance.HISTORICAL,
                        outcome=StructureEventOutcome.FOLLOW_THROUGH_CONFIRMED,
                        confirmed_by_event_uid=base_record.event_uid,
                    )
                    clear_current(choch_index)

            if base_record.event_type == EVENT_TRANSITION_FAIL:
                stack = pending_choch.get((base_record.scope, -int(base_record.direction)))
                if stack:
                    choch_index = stack.pop()
                    annotated[choch_index] = replace(
                        annotated[choch_index],
                        validity=StructureEventValidity.FAILED,
                        relevance=StructureEventRelevance.HISTORICAL,
                        outcome=StructureEventOutcome.FAILED,
                        failed_by_event_uid=base_record.event_uid,
                    )
                    clear_current(choch_index)

            index = len(annotated)
            annotated.append(base_record)
            latest_current[key] = index
            if (
                base_record.event_type == EVENT_CHOCH
                and base_record.validity is StructureEventValidity.VALID
                and base_record.outcome is StructureEventOutcome.PENDING
            ):
                pending_choch.setdefault(
                    (base_record.scope, int(base_record.direction)), []
                ).append(index)

        self._static_cache = tuple(annotated)
        latest_by_scope: dict[str, MarketStructureEventRecord] = {}
        for record in reversed(self._static_cache):
            latest_by_scope.setdefault(record.scope, record)
        self._latest_by_scope = latest_by_scope
        return self._static_cache

    def static_snapshot(self) -> tuple[MarketStructureEventRecord, ...]:
        """Return annotated records without recomputing dynamic ``age_bars``."""
        return self._static_snapshot()

    def latest_static(self, *, scope: str) -> MarketStructureEventRecord | None:
        self._static_snapshot()
        return self._latest_by_scope.get(scope)

    @staticmethod
    def _with_age(
        record: MarketStructureEventRecord | None,
        *,
        current_bar: int,
    ) -> MarketStructureEventRecord | None:
        if record is None:
            return None
        age = max(0, current_bar - record.event_bar)
        if record.age_bars == age:
            return record
        return replace(record, age_bars=age)

    def latest_for_scope(
        self,
        *,
        current_bar: int,
        scope: str,
    ) -> MarketStructureEventRecord | None:
        return self._with_age(self.latest_static(scope=scope), current_bar=current_bar)

    def snapshot(self, *, current_bar: int) -> tuple[MarketStructureEventRecord, ...]:
        if self._snapshot_bar == current_bar:
            return self._snapshot_cache
        static = self._static_snapshot()
        self._snapshot_cache = tuple(
            record
            if record.age_bars == max(0, current_bar - record.event_bar)
            else replace(record, age_bars=max(0, current_bar - record.event_bar))
            for record in static
        )
        self._snapshot_bar = current_bar
        return self._snapshot_cache


__all__ = ["RuntimeMarketStructureEventLedger"]
