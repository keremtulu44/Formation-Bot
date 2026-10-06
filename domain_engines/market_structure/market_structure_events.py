from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any, Iterable, Sequence

from .market_structure_state import (
    BosMaturity,
    EVENT_BOS,
    EVENT_CHOCH,
    EVENT_FALSE_BREAK,
    EVENT_TRANSITION_FAIL,
    StructureContext,
    StructureEvent,
)
from .models import Direction


class StructureEventConfirmation(StrEnum):
    """How the closed-bar event entered the public ledger."""

    CONFIRMED = "CONFIRMED"
    CANDIDATE_FAILED = "CANDIDATE_FAILED"


class StructureEventValidity(StrEnum):
    """Whether a previously confirmed structural thesis still completed normally."""

    VALID = "VALID"
    FAILED = "FAILED"


class StructureEventRelevance(StrEnum):
    """Current relevance without deleting historical facts."""

    CURRENT = "CURRENT"
    SUPERSEDED = "SUPERSEDED"
    HISTORICAL = "HISTORICAL"


class StructureEventOutcome(StrEnum):
    """Follow-up state for events that require or receive later evidence."""

    PENDING = "PENDING"
    FOLLOW_THROUGH_CONFIRMED = "FOLLOW_THROUGH_CONFIRMED"
    FAILED = "FAILED"
    OBSERVED = "OBSERVED"


@dataclass(frozen=True, slots=True)
class MarketStructureEventRecord:
    """Immutable, replay-stable public record for one Market Structure event.

    Native event identities are scope-local. ``event_uid`` is therefore local while
    the record belongs to a single engine. ``with_namespace`` adds symbol and
    timeframe when independent engines are assembled into an MTF snapshot.
    """

    event_uid: str
    identity: int
    scope: str
    event_type: str
    direction: Direction
    candidate_bar: int | None
    event_bar: int
    candidate_at: Any
    confirmed_at: Any
    broken_swing_identity: int
    broken_source_bar: int | None
    broken_source_at: Any
    broken_level: float | None
    origin_swing_identity: int
    origin_source_bar: int | None
    origin_source_at: Any
    origin_price: float | None
    quality: float
    evidence_text: str
    confirmation_status: StructureEventConfirmation
    validity: StructureEventValidity
    relevance: StructureEventRelevance
    outcome: StructureEventOutcome
    confirmed_by_event_uid: str | None = None
    failed_by_event_uid: str | None = None
    age_bars: int = 0
    symbol: str | None = None
    timeframe: str | None = None
    confirmation_high: float | None = None
    confirmation_low: float | None = None
    confirmation_close: float | None = None
    bos_maturity: BosMaturity = BosMaturity.NOT_APPLICABLE

    @property
    def is_initial_structure(self) -> bool:
        return self.bos_maturity is BosMaturity.INITIAL_STRUCTURE

    @property
    def is_active(self) -> bool:
        return (
            self.validity is StructureEventValidity.VALID
            and self.relevance is StructureEventRelevance.CURRENT
        )

    def with_namespace(self, *, symbol: str, timeframe: str) -> MarketStructureEventRecord:
        normalized_timeframe = timeframe.strip().lower()
        prefix = f"{symbol}:{normalized_timeframe}:"

        def qualify(reference: str | None) -> str | None:
            return f"{prefix}{reference}" if reference else None

        return replace(
            self,
            event_uid=f"{prefix}{self.event_uid}",
            confirmed_by_event_uid=qualify(self.confirmed_by_event_uid),
            failed_by_event_uid=qualify(self.failed_by_event_uid),
            symbol=symbol,
            timeframe=normalized_timeframe,
        )


@dataclass(frozen=True, slots=True)
class MarketStructureScopeSnapshot:
    """Immutable public copy of one internal or external structure context."""

    scope: str
    state: str
    direction: Direction
    quality: float
    evidence_text: str
    conflict_text: str
    last_confirmed_high_identity: int
    last_confirmed_low_identity: int
    protected_high_identity: int
    protected_low_identity: int
    strong_high_identity: int
    strong_low_identity: int
    weak_high_identity: int
    weak_low_identity: int
    last_bos_identity: int
    last_choch_identity: int
    latest_event: MarketStructureEventRecord | None = None

    @classmethod
    def from_context(
        cls,
        context: StructureContext,
        *,
        latest_event: MarketStructureEventRecord | None = None,
    ) -> "MarketStructureScopeSnapshot":
        direction = (
            Direction.UP
            if context.direction > 0
            else Direction.DOWN
            if context.direction < 0
            else Direction.NEUTRAL
        )
        return cls(
            scope=context.scope,
            state=context.state,
            direction=direction,
            quality=context.quality,
            evidence_text=context.evidence_text,
            conflict_text=context.conflict_text,
            last_confirmed_high_identity=context.last_confirmed_high_identity,
            last_confirmed_low_identity=context.last_confirmed_low_identity,
            protected_high_identity=context.protected_high_identity,
            protected_low_identity=context.protected_low_identity,
            strong_high_identity=context.strong_high_identity,
            strong_low_identity=context.strong_low_identity,
            weak_high_identity=context.weak_high_identity,
            weak_low_identity=context.weak_low_identity,
            last_bos_identity=context.last_bos_identity,
            last_choch_identity=context.last_choch_identity,
            latest_event=latest_event,
        )


class MarketStructureEventLedger:
    """Append-only event chronology with immutable lifecycle annotations.

    Records are never deleted. Later BOS/transition-failure events annotate an older
    CHoCH as followed-through or failed while retaining the original confirmation
    time and price references.
    """

    def __init__(self) -> None:
        self._records: list[MarketStructureEventRecord] = []

    def reset(self) -> None:
        self._records = []

    @staticmethod
    def _timestamp(rows: Sequence[dict[str, Any]], index: int | None) -> Any:
        if index is None or index < 0 or index >= len(rows):
            return None
        return rows[index].get("timestamp")

    @staticmethod
    def _price(rows: Sequence[dict[str, Any]], index: int | None, field: str) -> float | None:
        if index is None or index < 0 or index >= len(rows):
            return None
        value = rows[index].get(field)
        return None if value is None else float(value)

    @staticmethod
    def _direction(value: int) -> Direction:
        if value > 0:
            return Direction.UP
        if value < 0:
            return Direction.DOWN
        return Direction.NEUTRAL

    def append(self, event: StructureEvent, rows: Sequence[dict[str, Any]]) -> MarketStructureEventRecord:
        if not event.valid or event.event_bar is None:
            raise ValueError("only valid, confirmed-time structure events can enter the ledger")

        event_uid = f"{event.scope}:{event.identity}"
        if any(record.event_uid == event_uid for record in self._records):
            raise ValueError(f"duplicate Market Structure event identity: {event_uid}")

        candidate_failed = event.event_type == EVENT_FALSE_BREAK
        outcome = (
            StructureEventOutcome.PENDING
            if event.event_type == EVENT_CHOCH
            else StructureEventOutcome.FAILED
            if candidate_failed
            else StructureEventOutcome.OBSERVED
        )
        record = MarketStructureEventRecord(
            event_uid=event_uid,
            identity=event.identity,
            scope=event.scope,
            event_type=event.event_type,
            direction=self._direction(event.direction),
            candidate_bar=event.candidate_bar,
            event_bar=event.event_bar,
            candidate_at=self._timestamp(rows, event.candidate_bar),
            confirmed_at=self._timestamp(rows, event.event_bar),
            broken_swing_identity=event.broken_swing_identity,
            broken_source_bar=event.broken_source_bar,
            broken_source_at=self._timestamp(rows, event.broken_source_bar),
            broken_level=None if event.level is None else float(event.level),
            origin_swing_identity=event.origin_swing_identity,
            origin_source_bar=event.origin_source_bar,
            origin_source_at=self._timestamp(rows, event.origin_source_bar),
            origin_price=None if event.origin_price is None else float(event.origin_price),
            quality=float(event.quality),
            evidence_text=event.evidence_text,
            confirmation_status=(
                StructureEventConfirmation.CANDIDATE_FAILED
                if candidate_failed
                else StructureEventConfirmation.CONFIRMED
            ),
            validity=(
                StructureEventValidity.FAILED
                if candidate_failed
                else StructureEventValidity.VALID
            ),
            relevance=StructureEventRelevance.CURRENT,
            outcome=outcome,
            confirmation_high=self._price(rows, event.event_bar, "high"),
            bos_maturity=event.bos_maturity,
            confirmation_low=self._price(rows, event.event_bar, "low"),
            confirmation_close=self._price(rows, event.event_bar, "close"),
        )
        self._records.append(record)
        return record

    def extend(
        self,
        events: Iterable[StructureEvent],
        rows: Sequence[dict[str, Any]],
    ) -> tuple[MarketStructureEventRecord, ...]:
        return tuple(self.append(event, rows) for event in events)

    def snapshot(self, *, current_bar: int) -> tuple[MarketStructureEventRecord, ...]:
        """Return annotations in one chronological pass without mutating facts."""

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
                pending_key = (base_record.scope, int(base_record.direction))
                stack = pending_choch.get(pending_key)
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
                pending_key = (base_record.scope, -int(base_record.direction))
                stack = pending_choch.get(pending_key)
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

        return tuple(
            replace(record, age_bars=max(0, current_bar - record.event_bar))
            for record in annotated
        )

    def latest(
        self,
        *,
        current_bar: int,
        scope: str | None = None,
        event_type: str | None = None,
        direction: Direction | None = None,
    ) -> MarketStructureEventRecord | None:
        records = self.snapshot(current_bar=current_bar)
        for record in reversed(records):
            if scope is not None and record.scope != scope:
                continue
            if event_type is not None and record.event_type != event_type:
                continue
            if direction is not None and record.direction is not direction:
                continue
            return record
        return None
