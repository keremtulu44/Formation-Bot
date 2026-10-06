from __future__ import annotations

from dataclasses import dataclass

from .market_structure import SwingPoint
from .market_structure_events import MarketStructureEventRecord, MarketStructureScopeSnapshot
from .market_structure_state import (
    EVENT_BOS,
    EVENT_CHOCH,
    EVENT_FALSE_BREAK,
    EVENT_TRANSITION_FAIL,
    STATE_BEARISH,
    STATE_BULLISH,
    STATE_TRANSITION_DOWN,
    STATE_TRANSITION_UP,
    StructureContext,
    StructureEvent,
    active_by_id,
    export_state_code,
)

HANDSHAKE = 314159.0


@dataclass(frozen=True, slots=True)
class MarketStructureExport:
    external_state: float | None
    internal_state: float | None
    evidence_score: float | None
    external_protected_low: float | None
    external_protected_high: float | None
    external_weak_low: float | None
    external_weak_high: float | None
    internal_protected_low: float | None
    internal_protected_high: float | None
    internal_weak_low: float | None
    internal_weak_high: float | None
    handshake: float = HANDSHAKE
    contract_version: int = 3
    events: tuple[MarketStructureEventRecord, ...] = ()
    latest_external_event: MarketStructureEventRecord | None = None
    latest_internal_event: MarketStructureEventRecord | None = None
    external_scope: MarketStructureScopeSnapshot | None = None
    internal_scope: MarketStructureScopeSnapshot | None = None


def _latest_event(external: StructureEvent | None, internal: StructureEvent | None) -> StructureEvent | None:
    if external and external.valid and internal and internal.valid:
        ext_bar = external.event_bar if external.event_bar is not None else -1
        int_bar = internal.event_bar if internal.event_bar is not None else -1
        return internal if (int_bar, internal.identity) > (ext_bar, external.identity) else external
    if external and external.valid:
        return external
    if internal and internal.valid:
        return internal
    return None


def structure_score(
    external: StructureContext,
    internal: StructureContext,
    external_event: StructureEvent | None,
    internal_event: StructureEvent | None,
    *,
    bar_index: int,
) -> float:
    external_transition = external.state in (STATE_TRANSITION_UP, STATE_TRANSITION_DOWN)
    transition_direction = 1 if external.state == STATE_TRANSITION_UP else -1 if external.state == STATE_TRANSITION_DOWN else 0
    expected_direction = transition_direction if external_transition else external.direction

    if external_transition:
        structure_evidence = external.quality if external.quality else 55.0
    elif external.direction == 0:
        structure_evidence = 35.0
    else:
        structure_evidence = external.quality if external.quality else 65.0

    has_protected = (
        external.protected_low_identity != 0 if external.state in (STATE_BULLISH, STATE_TRANSITION_UP)
        else external.protected_high_identity != 0 if external.state in (STATE_BEARISH, STATE_TRANSITION_DOWN)
        else False
    )
    has_weak = (
        external.weak_high_identity != 0 if external.state in (STATE_BULLISH, STATE_TRANSITION_UP)
        else external.weak_low_identity != 0 if external.state in (STATE_BEARISH, STATE_TRANSITION_DOWN)
        else False
    )
    role_integrity = 92.0 if has_protected and has_weak else 68.0 if has_protected else 42.0 if external.direction == 0 and not external_transition else 25.0
    swing_integrity = 82.0 if external.last_confirmed_high_identity and external.last_confirmed_low_identity else 48.0

    if external_transition:
        relation = 60.0 if internal.direction == 0 else 82.0 if internal.direction == transition_direction else 48.0
    elif external.direction == 0:
        relation = 45.0
    else:
        relation = 60.0 if internal.direction == 0 else 90.0 if external.direction == internal.direction else 58.0

    freshest = _latest_event(external_event, internal_event)
    if freshest is not None and freshest.event_bar is not None:
        freshness = max(20.0, 100.0 - (bar_index - freshest.event_bar) * 3.0)
    else:
        freshness = 45.0

    raw = structure_evidence * 0.40 + role_integrity * 0.25 + swing_integrity * 0.15 + relation * 0.15 + freshness * 0.05

    if freshest is not None:
        key_event = freshest.event_type in (EVENT_BOS, EVENT_CHOCH, EVENT_TRANSITION_FAIL)
        opposes = key_event and expected_direction != 0 and freshest.direction != 0 and freshest.direction != expected_direction
        if opposes:
            raw -= 6.0
        if freshest.event_type == EVENT_FALSE_BREAK:
            raw -= 10.0
        if freshest.event_type == EVENT_TRANSITION_FAIL:
            raw -= 4.0
    if external.conflict_text:
        raw -= 12.0

    if external.direction == 0 and not external_transition:
        raw = min(raw, 60.0)
        if internal.direction != 0:
            raw = min(raw, 55.0)
    if external_transition:
        raw = min(raw, 79.0)
    return round(max(0.0, min(100.0, raw)))


def _price(swings: list[SwingPoint], identity: int) -> float | None:
    swing = active_by_id(swings, identity)
    return swing.price if swing.valid and not swing.broken else None


def export_snapshot(
    external_swings: list[SwingPoint],
    internal_swings: list[SwingPoint],
    external: StructureContext,
    internal: StructureContext,
    *,
    evidence_score: float,
    engine_enabled: bool = True,
) -> MarketStructureExport:
    external_safe = engine_enabled and external.conflict_text == ""
    internal_safe = engine_enabled and internal.conflict_text == ""
    score_safe = external_safe and internal_safe
    return MarketStructureExport(
        external_state=export_state_code(external.state) if external_safe else None,
        internal_state=export_state_code(internal.state) if internal_safe else None,
        evidence_score=evidence_score if score_safe else None,
        external_protected_low=_price(external_swings, external.protected_low_identity) if external_safe else None,
        external_protected_high=_price(external_swings, external.protected_high_identity) if external_safe else None,
        external_weak_low=_price(external_swings, external.weak_low_identity) if external_safe else None,
        external_weak_high=_price(external_swings, external.weak_high_identity) if external_safe else None,
        internal_protected_low=_price(internal_swings, internal.protected_low_identity) if internal_safe else None,
        internal_protected_high=_price(internal_swings, internal.protected_high_identity) if internal_safe else None,
        internal_weak_low=_price(internal_swings, internal.weak_low_identity) if internal_safe else None,
        internal_weak_high=_price(internal_swings, internal.weak_high_identity) if internal_safe else None,
    )
