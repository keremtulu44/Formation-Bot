from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from .market_structure import (
    ROLE_NEUTRAL_HIGH,
    ROLE_NEUTRAL_LOW,
    SCOPE_EXTERNAL,
    SIDE_HIGH,
    SIDE_LOW,
    SWING_BROKEN,
    SWING_CONFIRMED,
    SwingPoint,
)

ROLE_PROTECTED_HIGH = "PROTECTED_HIGH"
ROLE_PROTECTED_LOW = "PROTECTED_LOW"
ROLE_STRONG_HIGH = "STRONG_HIGH"
ROLE_STRONG_LOW = "STRONG_LOW"
ROLE_WEAK_HIGH = "WEAK_HIGH"
ROLE_WEAK_LOW = "WEAK_LOW"

EVENT_NONE = "EVENT_NONE"
EVENT_BOS = "EVENT_BOS"
EVENT_CHOCH = "EVENT_CHOCH"
EVENT_TRANSITION_FAIL = "EVENT_TRANSITION_FAIL"
EVENT_SWEEP = "EVENT_SWEEP"
EVENT_FALSE_BREAK = "EVENT_FALSE_BREAK"

EVIDENCE_INITIAL_STRUCTURE_BREAK_CONFIRMED = "INITIAL_STRUCTURE_BREAK_CONFIRMED"


class BosMaturity(StrEnum):
    """Typed maturity of a confirmed BOS event.

    Initial structure establishes the first observed direction from a neutral
    context.  It is deliberately distinct from both a BOS that confirms a known
    transition and a continuation BOS in an already directional structure.
    """

    NOT_APPLICABLE = "NOT_APPLICABLE"
    INITIAL_STRUCTURE = "INITIAL_STRUCTURE"
    TRANSITION_CONFIRMATION = "TRANSITION_CONFIRMATION"
    CONTINUATION = "CONTINUATION"


STATE_NEUTRAL = "STATE_NEUTRAL"
STATE_BULLISH = "STATE_BULLISH"
STATE_BEARISH = "STATE_BEARISH"
STATE_TRANSITION_UP = "STATE_TRANSITION_UP"
STATE_TRANSITION_DOWN = "STATE_TRANSITION_DOWN"

BREAK_NONE = "BREAK_NONE"
BREAK_CANDIDATE = "BREAK_CANDIDATE"
BREAK_CONFIRMED = "BREAK_CONFIRMED"
BREAK_FAILED = "BREAK_FAILED"


@dataclass(slots=True)
class StructureContext:
    valid: bool = True
    scope: str = SCOPE_EXTERNAL
    direction: int = 0
    state: str = STATE_NEUTRAL
    last_confirmed_high_identity: int = 0
    last_confirmed_low_identity: int = 0
    protected_high_identity: int = 0
    protected_low_identity: int = 0
    strong_high_identity: int = 0
    strong_low_identity: int = 0
    weak_high_identity: int = 0
    weak_low_identity: int = 0
    last_bos_identity: int = 0
    last_choch_identity: int = 0
    quality: float = 0.0
    evidence_text: str = ""
    conflict_text: str = ""


@dataclass(frozen=True, slots=True)
class StructureEvent:
    valid: bool = False
    identity: int = 0
    scope: str = ""
    event_type: str = EVENT_NONE
    direction: int = 0
    event_bar: int | None = None
    broken_swing_identity: int = 0
    broken_source_bar: int | None = None
    origin_swing_identity: int = 0
    origin_source_bar: int | None = None
    level: float | None = None
    origin_price: float | None = None
    quality: float = 0.0
    evidence_text: str = ""
    candidate_bar: int | None = None
    bos_maturity: BosMaturity = BosMaturity.NOT_APPLICABLE


@dataclass(slots=True)
class BreakCandidate:
    valid: bool = False
    identity: int = 0
    scope: str = ""
    side: str = ""
    intended_event_type: str = EVENT_NONE
    direction: int = 0
    status: str = BREAK_NONE
    candidate_bar: int = 0
    expiry_bar: int = 0
    level: float = 0.0
    buffer: float = 0.0
    candidate_atr: float = 1.0
    candidate_close: float = 0.0
    first_close_distance_atr: float = 0.0
    initial_quality: float = 0.0
    broken_swing_identity: int = 0
    broken_source_bar: int = 0
    broken_quality: float = 50.0
    broken_side: str = ""
    origin_swing_identity: int = 0
    origin_source_bar: int = 0
    origin_quality: float = 50.0
    origin_side: str = ""
    current_evidence: int = 0
    required_evidence: int = 0
    status_text: str = ""


@dataclass(frozen=True, slots=True)
class BreakConfig:
    profile: str = "Dengeli"
    min_tick: float = 0.01
    break_buffer_atr: float = 0.10
    break_confirm_window: int = 3
    min_confirm_body_atr: float = 0.10
    min_confirm_close_location: float = 0.53
    min_follow_through_atr: float = 0.00
    min_confirm_evidence: int = 2
    require_directional_confirm_candle: bool = False
    allow_immediate_confirm: bool = True
    immediate_body_atr: float = 0.22
    immediate_close_location: float = 0.65
    immediate_excess_atr: float = 0.16
    immediate_min_evidence: int = 3
    min_acceptance_atr: float = 0.03
    false_break_reversal_atr: float = 0.06
    shallow_reentry_atr: float = 0.04
    external_confirm_mult: float = 1.06
    internal_confirm_mult: float = 0.92
    bos_confirm_mult: float = 1.00
    choch_confirm_mult: float = 1.12
    transition_fail_confirm_mult: float = 1.08

    @property
    def profile_break_mult(self) -> float:
        return 0.78 if self.profile == "Hassas" else 1.35 if self.profile == "Seçici" else 1.0

    def event_confirm_multiplier(self, scope: str, event_type: str) -> float:
        scope_mult = self.external_confirm_mult if scope == "EXTERNAL" else self.internal_confirm_mult
        event_mult = (
            self.choch_confirm_mult if event_type == EVENT_CHOCH else
            self.transition_fail_confirm_mult if event_type == EVENT_TRANSITION_FAIL else
            self.bos_confirm_mult
        )
        return scope_mult * event_mult


@dataclass(frozen=True, slots=True)
class BreakBarEvaluation:
    confirmed: bool
    failed: bool
    false_break: bool
    evidence_count: int
    required_evidence: int
    acceptance: float
    follow_through: float | None
    final_quality: float | None
    status_text: str


def _neutral_role(side: str) -> str:
    return ROLE_NEUTRAL_HIGH if side == SIDE_HIGH else ROLE_NEUTRAL_LOW


def _index_by_id(swings: list[SwingPoint], identity: int) -> int | None:
    for idx, swing in enumerate(swings):
        if swing.identity == identity:
            return idx
    return None


def active_by_id(swings: list[SwingPoint], identity: int) -> SwingPoint:
    idx = _index_by_id(swings, identity)
    if idx is None:
        return SwingPoint()
    s = swings[idx]
    if not s.valid or s.broken or s.state == SWING_BROKEN:
        return SwingPoint()
    return s


def _replace(swings: list[SwingPoint], swing: SwingPoint) -> None:
    idx = _index_by_id(swings, swing.identity)
    if idx is None:
        raise KeyError(f"swing identity not found: {swing.identity}")
    swings[idx] = swing


def clear_role_if_matches(swings: list[SwingPoint], identity: int, role: str) -> None:
    idx = _index_by_id(swings, identity)
    if idx is None:
        return
    s = swings[idx]
    if s.structural_role == role:
        swings[idx] = replace(s, structural_role=_neutral_role(s.side))


def set_unique_role(swings: list[SwingPoint], identity: int, role: str) -> None:
    target = active_by_id(swings, identity)
    if not target.valid:
        return
    for idx, s in enumerate(swings):
        if s.structural_role == role and s.identity != identity:
            swings[idx] = replace(s, structural_role=_neutral_role(s.side))
    _replace(swings, replace(target, structural_role=role))


def latest_active_after(swings: list[SwingPoint], side: str, anchor_bar: int) -> SwingPoint:
    candidates = [
        s for s in swings
        if s.valid and not s.broken and s.state == SWING_CONFIRMED and s.side == side
        and s.source_bar is not None and s.source_bar > anchor_bar
    ]
    if not candidates:
        return SwingPoint()
    return max(candidates, key=lambda s: (s.source_bar or -1, s.identity))


def assign_strong_level(swings: list[SwingPoint], ctx: StructureContext, identity: int, side: str) -> StructureContext:
    out = replace_context(ctx)
    target = active_by_id(swings, identity)
    if not target.valid or target.side != side:
        return out
    role = ROLE_STRONG_HIGH if side == SIDE_HIGH else ROLE_STRONG_LOW
    set_unique_role(swings, identity, role)
    if side == SIDE_HIGH:
        out.strong_high_identity = identity
    else:
        out.strong_low_identity = identity
    return out


def assign_weak_level(swings: list[SwingPoint], ctx: StructureContext, identity: int, side: str) -> StructureContext:
    out = replace_context(ctx)
    assigning_high = side == SIDE_HIGH
    role = ROLE_WEAK_HIGH if assigning_high else ROLE_WEAK_LOW
    previous = out.weak_high_identity if assigning_high else out.weak_low_identity
    anchor_identity = out.protected_low_identity if assigning_high else out.protected_high_identity
    if previous and previous != identity:
        clear_role_if_matches(swings, previous, role)

    target = active_by_id(swings, identity)
    anchor = active_by_id(swings, anchor_identity)
    valid = (
        target.valid and anchor.valid and target.side == side
        and target.source_bar is not None and anchor.source_bar is not None
        and target.source_bar > anchor.source_bar
    )
    if valid:
        set_unique_role(swings, identity, role)
        if assigning_high:
            out.weak_high_identity = identity
        else:
            out.weak_low_identity = identity
    else:
        if identity:
            clear_role_if_matches(swings, identity, role)
        if assigning_high:
            out.weak_high_identity = 0
        else:
            out.weak_low_identity = 0
    return out


def assign_protected_level(
    swings: list[SwingPoint], ctx: StructureContext, identity: int, side: str, promote_previous: bool
) -> StructureContext:
    out = replace_context(ctx)
    assigning_high = side == SIDE_HIGH
    new_anchor = active_by_id(swings, identity)
    if not new_anchor.valid or new_anchor.side != side:
        out.conflict_text = "INVALID_PROTECTED_HIGH_ORIGIN" if assigning_high else "INVALID_PROTECTED_LOW_ORIGIN"
        return out

    previous_same = out.protected_high_identity if assigning_high else out.protected_low_identity
    previous_opposite = out.protected_low_identity if assigning_high else out.protected_high_identity
    same_role = ROLE_PROTECTED_HIGH if assigning_high else ROLE_PROTECTED_LOW
    opposite_role = ROLE_PROTECTED_LOW if assigning_high else ROLE_PROTECTED_HIGH
    previous_swing = active_by_id(swings, previous_same)

    if previous_opposite:
        clear_role_if_matches(swings, previous_opposite, opposite_role)
    if previous_same and previous_same != identity:
        clear_role_if_matches(swings, previous_same, same_role)

    if assigning_high:
        out.protected_low_identity = 0
        out.protected_high_identity = identity
        if out.strong_high_identity == identity:
            clear_role_if_matches(swings, identity, ROLE_STRONG_HIGH)
            out.strong_high_identity = 0
    else:
        out.protected_high_identity = 0
        out.protected_low_identity = identity
        if out.strong_low_identity == identity:
            clear_role_if_matches(swings, identity, ROLE_STRONG_LOW)
            out.strong_low_identity = 0

    set_unique_role(swings, identity, same_role)
    if promote_previous and previous_swing.valid and previous_swing.identity != identity:
        out = assign_strong_level(swings, out, previous_swing.identity, side)
    return out


def normalize_directional_roles(swings: list[SwingPoint], ctx: StructureContext) -> StructureContext:
    out = replace_context(ctx)
    bullish = out.state in (STATE_BULLISH, STATE_TRANSITION_UP)
    bearish = out.state in (STATE_BEARISH, STATE_TRANSITION_DOWN)
    if bullish:
        if out.strong_high_identity:
            clear_role_if_matches(swings, out.strong_high_identity, ROLE_STRONG_HIGH)
        if out.weak_low_identity:
            clear_role_if_matches(swings, out.weak_low_identity, ROLE_WEAK_LOW)
        out.strong_high_identity = 0
        out.weak_low_identity = 0
        anchor = active_by_id(swings, out.protected_low_identity)
        weak = latest_active_after(swings, SIDE_HIGH, anchor.source_bar) if anchor.valid else SwingPoint()
        out = assign_weak_level(swings, out, weak.identity if weak.valid else 0, SIDE_HIGH)
    elif bearish:
        if out.strong_low_identity:
            clear_role_if_matches(swings, out.strong_low_identity, ROLE_STRONG_LOW)
        if out.weak_high_identity:
            clear_role_if_matches(swings, out.weak_high_identity, ROLE_WEAK_HIGH)
        out.strong_low_identity = 0
        out.weak_high_identity = 0
        anchor = active_by_id(swings, out.protected_high_identity)
        weak = latest_active_after(swings, SIDE_LOW, anchor.source_bar) if anchor.valid else SwingPoint()
        out = assign_weak_level(swings, out, weak.identity if weak.valid else 0, SIDE_LOW)
    else:
        for identity, role in (
            (out.strong_high_identity, ROLE_STRONG_HIGH), (out.strong_low_identity, ROLE_STRONG_LOW),
            (out.weak_high_identity, ROLE_WEAK_HIGH), (out.weak_low_identity, ROLE_WEAK_LOW),
        ):
            if identity:
                clear_role_if_matches(swings, identity, role)
        out.strong_high_identity = out.strong_low_identity = 0
        out.weak_high_identity = out.weak_low_identity = 0
    return out


def mark_broken(swings: list[SwingPoint], identity: int, bar_index: int) -> None:
    idx = _index_by_id(swings, identity)
    if idx is None:
        return
    s = swings[idx]
    swings[idx] = replace(s, state=SWING_BROKEN, broken=True, broken_bar=bar_index, structural_role=_neutral_role(s.side))


def finalize_confirmed_break(
    swings: list[SwingPoint],
    ctx: StructureContext,
    candidate: BreakCandidate,
    *,
    event_identity: int,
    event_bar: int,
    acceptance: float,
    follow_through: float | None,
) -> tuple[StructureContext, StructureEvent]:
    broken = active_by_id(swings, candidate.broken_swing_identity)
    origin = active_by_id(swings, candidate.origin_swing_identity)
    if not broken.valid or not origin.valid:
        raise ValueError("confirmed break references must still be active")
    if broken.source_bar != candidate.broken_source_bar or origin.source_bar != candidate.origin_source_bar:
        raise ValueError("break reference identity/source mismatch")
    if origin.source_bar is None or broken.source_bar is None or not (broken.source_bar < origin.source_bar < candidate.candidate_bar):
        raise ValueError("break origin chronology invalid")

    q = break_final_quality(candidate, acceptance, follow_through)
    initial = (
        candidate.intended_event_type == EVENT_BOS
        and ctx.state == STATE_NEUTRAL
        and ctx.direction == 0
    )
    bos_maturity = (
        BosMaturity.INITIAL_STRUCTURE
        if initial
        else BosMaturity.TRANSITION_CONFIRMATION
        if candidate.intended_event_type == EVENT_BOS
        and ctx.state in (STATE_TRANSITION_UP, STATE_TRANSITION_DOWN)
        else BosMaturity.CONTINUATION
        if candidate.intended_event_type == EVENT_BOS
        else BosMaturity.NOT_APPLICABLE
    )
    evidence = (
        EVIDENCE_INITIAL_STRUCTURE_BREAK_CONFIRMED
        if bos_maturity is BosMaturity.INITIAL_STRUCTURE
        else "TRANSITION_BOS_CONFIRMED"
        if bos_maturity is BosMaturity.TRANSITION_CONFIRMATION
        else "BOS_CONFIRMED"
        if bos_maturity is BosMaturity.CONTINUATION
        else "CHOCH_CONFIRMED"
        if candidate.intended_event_type == EVENT_CHOCH
        else "TRANSITION_FAILED"
    )
    event = StructureEvent(
        valid=True, identity=event_identity, scope=candidate.scope,
        event_type=candidate.intended_event_type, direction=candidate.direction,
        candidate_bar=candidate.candidate_bar, event_bar=event_bar,
        broken_swing_identity=broken.identity, broken_source_bar=broken.source_bar,
        origin_swing_identity=origin.identity, origin_source_bar=origin.source_bar,
        level=broken.price,
        origin_price=origin.price,
        quality=q,
        evidence_text=evidence,
        bos_maturity=bos_maturity,
    )

    out = replace_context(ctx)
    mark_broken(swings, broken.identity, event_bar)

    if candidate.intended_event_type == EVENT_CHOCH:
        if candidate.direction == 1:
            if out.weak_low_identity:
                clear_role_if_matches(swings, out.weak_low_identity, ROLE_WEAK_LOW)
            out.weak_low_identity = 0
            out = assign_protected_level(swings, out, origin.identity, SIDE_LOW, False)
            out.state = STATE_TRANSITION_UP
            out.evidence_text = "CHOCH_UP_WAITING_BOS"
        else:
            if out.weak_high_identity:
                clear_role_if_matches(swings, out.weak_high_identity, ROLE_WEAK_HIGH)
            out.weak_high_identity = 0
            out = assign_protected_level(swings, out, origin.identity, SIDE_HIGH, False)
            out.state = STATE_TRANSITION_DOWN
            out.evidence_text = "CHOCH_DOWN_WAITING_BOS"
        out.direction = 0
        out.last_choch_identity = event.identity

    elif candidate.intended_event_type == EVENT_TRANSITION_FAIL:
        if candidate.direction == 1:
            out.weak_high_identity = 0
            out = assign_protected_level(swings, out, origin.identity, SIDE_LOW, False)
            out.direction = 1
            out.state = STATE_BULLISH
            out.evidence_text = "TRANSITION_DOWN_FAILED"
        else:
            out.weak_low_identity = 0
            out = assign_protected_level(swings, out, origin.identity, SIDE_HIGH, False)
            out.direction = -1
            out.state = STATE_BEARISH
            out.evidence_text = "TRANSITION_UP_FAILED"

    else:
        confirming_transition = (
            (out.state == STATE_TRANSITION_UP and candidate.direction == 1)
            or (out.state == STATE_TRANSITION_DOWN and candidate.direction == -1)
        )
        if candidate.direction == 1:
            out.weak_high_identity = 0
            out = assign_protected_level(swings, out, origin.identity, SIDE_LOW, not initial)
            out.direction = 1
            out.state = STATE_BULLISH
        else:
            out.weak_low_identity = 0
            out = assign_protected_level(swings, out, origin.identity, SIDE_HIGH, not initial)
            out.direction = -1
            out.state = STATE_BEARISH
        out.last_bos_identity = event.identity
        out.evidence_text = "INITIAL_STRUCTURE_ESTABLISHED" if initial else "TRANSITION_CONFIRMED_BY_BOS" if confirming_transition else "BOS_CONFIRMED"

    out.quality = q
    out.conflict_text = ""
    out = normalize_directional_roles(swings, out)
    return out, event


def close_location(direction: int, high: float, low: float, close: float, min_tick: float) -> float:
    spread = max(high - low, min_tick)
    return (close - low) / spread if direction == 1 else (high - close) / spread


def break_impulse_quality(
    direction: int, level: float, buffer: float, frozen_atr: float,
    *, open_: float, high: float, low: float, close: float, min_tick: float,
) -> float:
    safe_atr = max(frozen_atr, min_tick)
    directional_distance = close - level if direction == 1 else level - close
    buffer_atr = max(buffer / safe_atr, 0.01)
    excess_atr = max(directional_distance - buffer, 0.0) / safe_atr
    body_atr = abs(close - open_) / safe_atr
    location = close_location(direction, high, low, close, min_tick)
    body_score = min(100.0, max(0.0, body_atr / 0.70 * 100.0))
    location_score = min(100.0, max(0.0, (location - 0.50) / 0.35 * 100.0))
    excess_score = min(100.0, max(0.0, excess_atr / max(buffer_atr * 1.25, 0.08) * 100.0))
    direction_score = 100.0 if (close > open_ if direction == 1 else close < open_) else 25.0
    return round(min(100.0, max(0.0, body_score * 0.30 + location_score * 0.25 + excess_score * 0.35 + direction_score * 0.10)))


def break_final_quality(candidate: BreakCandidate, acceptance: float, follow_through: float | None) -> float:
    structural = min(100.0, max(0.0, (candidate.broken_quality + candidate.origin_quality) * 0.50))
    if follow_through is None:
        q = candidate.initial_quality * 0.60 + structural * 0.40
    else:
        q = candidate.initial_quality * 0.25 + structural * 0.25 + acceptance * 0.25 + follow_through * 0.25
    return round(min(100.0, max(0.0, q)))


def evaluate_break_candidate(
    candidate: BreakCandidate,
    config: BreakConfig,
    *, bar_index: int, open_: float, high: float, low: float, close: float,
) -> BreakBarEvaluation:
    atr = max(candidate.candidate_atr, config.min_tick)
    direction = candidate.direction
    beyond = close > candidate.level + candidate.buffer if direction == 1 else close < candidate.level - candidate.buffer
    holds = close > candidate.level if direction == 1 else close < candidate.level
    hold_margin = max(candidate.buffer * 0.20, config.min_tick * 2.0)
    holds_margin = close > candidate.level + hold_margin if direction == 1 else close < candidate.level - hold_margin
    back_inside = not holds
    within = bar_index <= candidate.expiry_bar
    after = bar_index > candidate.candidate_bar
    same = bar_index == candidate.candidate_bar

    excess_distance = close - (candidate.level + candidate.buffer) if direction == 1 else (candidate.level - candidate.buffer) - close
    progress_distance = close - candidate.candidate_close if direction == 1 else candidate.candidate_close - close
    excess_atr = max(excess_distance, 0.0) / atr
    progress_atr = progress_distance / atr
    body_atr = abs(close - open_) / atr
    location = close_location(direction, high, low, close, config.min_tick)
    directional = close > open_ if direction == 1 else close < open_

    strictness = max(0.85, min(1.20, 0.75 + config.event_confirm_multiplier(candidate.scope, candidate.intended_event_type) * 0.25))
    body_threshold = config.min_confirm_body_atr * config.profile_break_mult * strictness
    close_threshold = max(0.50, min(0.92, config.min_confirm_close_location + (strictness - 1.0) * 0.18))
    acceptance_threshold = config.min_acceptance_atr * config.profile_break_mult * strictness
    min_evidence = max(1, min(4, config.min_confirm_evidence + (1 if strictness >= 1.06 else -1 if strictness <= 0.94 else 0)))
    evidence = int(body_atr >= body_threshold) + int(location >= close_threshold) + int(excess_atr >= acceptance_threshold) + int(directional)

    strong_initial = candidate.first_close_distance_atr >= config.break_buffer_atr * config.event_confirm_multiplier(candidate.scope, candidate.intended_event_type) * 1.15
    acceptance_zone_ok = beyond or (holds_margin and strong_initial)
    candle_direction_ok = (not config.require_directional_confirm_candle) or directional

    immediate_min = max(2, min(4, config.immediate_min_evidence + (1 if strictness >= 1.06 else -1 if strictness <= 0.94 else 0)))
    immediate_location = min(0.92, config.immediate_close_location + (strictness - 1.0) * 0.16)
    immediate_evidence = (
        int(body_atr >= config.immediate_body_atr * config.profile_break_mult * strictness)
        + int(location >= immediate_location)
        + int(excess_atr >= config.immediate_excess_atr * config.profile_break_mult * strictness)
        + int(directional)
    )
    immediate = config.allow_immediate_confirm and same and beyond and immediate_evidence >= immediate_min
    normal = after and within and acceptance_zone_ok and evidence >= min_evidence and candle_direction_ok

    buffer_atr = candidate.buffer / atr
    acceptance_distance = max((close - candidate.level) if direction == 1 else (candidate.level - close), 0.0) / atr if holds else 0.0
    acceptance_target = max(0.06, buffer_atr * 1.50, acceptance_threshold * 2.0)
    acceptance = min(100.0, max(0.0, acceptance_distance / acceptance_target * 100.0)) if holds else 0.0
    ft_target = max(0.10, buffer_atr, config.min_follow_through_atr * strictness * 2.0)
    follow = min(100.0, max(0.0, max(progress_atr, 0.0) / ft_target * 100.0)) if after and acceptance_zone_ok else None

    reversal_distance = candidate.level - close if direction == 1 else close - candidate.level
    reversal_atr = max(reversal_distance, 0.0) / atr
    opposite = close < open_ if direction == 1 else close > open_
    opposite_location = 1.0 - close_location(direction, high, low, close, config.min_tick)
    meaningful_reversal = back_inside and reversal_atr >= config.false_break_reversal_atr * config.profile_break_mult and (opposite or opposite_location >= 0.55)
    deep_reentry = back_inside and reversal_atr > config.shallow_reentry_atr * config.profile_break_mult
    failed = not (immediate or normal) and (meaningful_reversal or (bar_index > candidate.expiry_bar and deep_reentry))
    confirmed = immediate or normal
    quality = break_final_quality(candidate, acceptance, follow) if confirmed else None
    status = "confirmed" if confirmed else "false break" if meaningful_reversal else "inside risk" if back_inside else "acceptance pending"
    return BreakBarEvaluation(confirmed, failed, meaningful_reversal, immediate_evidence if same else evidence, immediate_min if same else min_evidence, acceptance, follow, quality, status)


def is_sweep(side: str, level: float, buffer: float, *, high: float, low: float, close: float) -> bool:
    return high > level + buffer and close <= level if side == SIDE_HIGH else low < level - buffer and close >= level


def export_state_code(state: str) -> float:
    return 2.0 if state == STATE_BULLISH else 1.0 if state == STATE_TRANSITION_UP else -2.0 if state == STATE_BEARISH else -1.0 if state == STATE_TRANSITION_DOWN else 0.0


def export_directional_level(state: str, bullish_level: float | None, bearish_level: float | None) -> float | None:
    if state in (STATE_BULLISH, STATE_TRANSITION_UP):
        return bullish_level
    if state in (STATE_BEARISH, STATE_TRANSITION_DOWN):
        return bearish_level
    return None


def replace_context(ctx: StructureContext) -> StructureContext:
    return StructureContext(**{field: getattr(ctx, field) for field in StructureContext.__dataclass_fields__})
