from __future__ import annotations

from dataclasses import dataclass

from .market_structure import SCOPE_EXTERNAL, SCOPE_INTERNAL, SIDE_HIGH, SIDE_LOW, SWING_CANDIDATE, SWING_CONFIRMED, SwingPoint
from .market_structure_evidence import MarketStructureExport, export_snapshot, structure_score
from .market_structure_state import (
    BREAK_NONE,
    EVENT_BOS,
    EVENT_CHOCH,
    EVENT_FALSE_BREAK,
    EVENT_SWEEP,
    EVENT_TRANSITION_FAIL,
    ROLE_PROTECTED_HIGH,
    ROLE_PROTECTED_LOW,
    STATE_BEARISH,
    STATE_BULLISH,
    STATE_NEUTRAL,
    STATE_TRANSITION_DOWN,
    STATE_TRANSITION_UP,
    BreakCandidate,
    BreakConfig,
    StructureContext,
    StructureEvent,
    active_by_id,
    break_impulse_quality,
    evaluate_break_candidate,
    finalize_confirmed_break,
    is_sweep,
    normalize_directional_roles,
)


@dataclass(slots=True)
class _RuntimeScope:
    context: StructureContext
    candidate: BreakCandidate
    last_event: StructureEvent | None = None
    last_broken_high: int = 0
    last_broken_low: int = 0
    next_candidate_id: int = 0
    next_event_id: int = 0


class MarketStructureRuntime:
    """Wires the validated swing, break/state, and evidence/export layers.

    This class owns only runtime chronology/state. It intentionally delegates the
    already-tested swing math and break-quality math to their existing modules.
    """

    def __init__(self, break_config: BreakConfig | None = None) -> None:
        self.break_config = break_config or BreakConfig()
        self.external = _RuntimeScope(StructureContext(scope=SCOPE_EXTERNAL), BreakCandidate())
        self.internal = _RuntimeScope(StructureContext(scope=SCOPE_INTERNAL), BreakCandidate())

    def reset(self) -> None:
        self.external = _RuntimeScope(StructureContext(scope=SCOPE_EXTERNAL), BreakCandidate())
        self.internal = _RuntimeScope(StructureContext(scope=SCOPE_INTERNAL), BreakCandidate())

    def scope(self, scope: str) -> _RuntimeScope:
        return self.external if scope == SCOPE_EXTERNAL else self.internal

    def locks_candidate(self, scope: str, candidate: SwingPoint) -> bool:
        if not candidate.valid:
            return False
        runtime = self.scope(scope)
        bc = runtime.candidate
        if not bc.valid:
            return False
        return candidate.identity in {bc.broken_swing_identity, bc.origin_swing_identity}

    @staticmethod
    def _latest_confirmed(swings: list[SwingPoint], side: str) -> SwingPoint:
        eligible = [s for s in swings if s.valid and s.finalized and s.state == SWING_CONFIRMED and not s.broken and s.side == side]
        return max(eligible, key=lambda s: (s.source_bar if s.source_bar is not None else -1, s.identity)) if eligible else SwingPoint()

    @staticmethod
    def _latest_confirmed_after(swings: list[SwingPoint], side: str, anchor_bar: int) -> SwingPoint:
        eligible = [
            s for s in swings
            if s.valid and s.finalized and s.state == SWING_CONFIRMED and not s.broken and s.side == side
            and s.source_bar is not None and s.source_bar > anchor_bar
        ]
        return max(eligible, key=lambda s: (s.source_bar or -1, s.identity)) if eligible else SwingPoint()

    def _provisional_gate(self, s: SwingPoint, scope: str, bar_index: int, origin_role: bool) -> bool:
        if not s.valid or s.state != SWING_CANDIDATE or s.source_bar is None:
            return False
        scope_min = 0.45 if scope == SCOPE_EXTERNAL else 0.20
        if self.break_config.profile == "Hassas":
            scope_min *= 0.72
        elif self.break_config.profile == "Seçici":
            scope_min *= 1.42
        min_prominence = max(0.15 if scope == SCOPE_EXTERNAL else 0.10, scope_min * 0.45)
        min_distance = scope_min * 0.55
        min_quality = 42.0 if scope == SCOPE_EXTERNAL else 39.0
        min_age = 1 if origin_role else 1
        age = bar_index - s.source_bar
        return (
            age >= min_age
            and (s.quality or 0.0) >= min_quality
            and ((s.prominence_atr or 0.0) >= min_prominence or (s.distance_atr or 0.0) >= min_distance)
        )

    def _find_origin(
        self,
        swings: list[SwingPoint],
        candidate_origin: SwingPoint,
        required_side: str,
        broken_source_bar: int,
        break_bar: int,
        scope: str,
    ) -> SwingPoint:
        eligible = [
            s for s in swings
            if s.valid and s.finalized and s.state == SWING_CONFIRMED and not s.broken
            and s.side == required_side and s.source_bar is not None
            and broken_source_bar < s.source_bar < break_bar
        ]
        out = max(eligible, key=lambda s: (s.source_bar or -1, s.identity)) if eligible else SwingPoint()
        candidate_ok = (
            candidate_origin.valid and candidate_origin.side == required_side and candidate_origin.source_bar is not None
            and broken_source_bar < candidate_origin.source_bar < break_bar
            and self._provisional_gate(candidate_origin, scope, break_bar, True)
        )
        if candidate_ok and (not out.valid or (candidate_origin.source_bar or -1) > (out.source_bar or -1)):
            out = candidate_origin
        return out

    def _buffer(self, scope: str, event_type: str, safe_atr: float) -> float:
        base = max(safe_atr * self.break_config.break_buffer_atr * self.break_config.profile_break_mult, self.break_config.min_tick * 3.0)
        return max(base * self.break_config.event_confirm_multiplier(scope, event_type), self.break_config.min_tick * 3.0)

    @staticmethod
    def _breaks_level(direction: int, level: float, buffer: float, close: float) -> bool:
        return close > level + buffer if direction == 1 else close < level - buffer

    def _new_candidate(
        self,
        runtime: _RuntimeScope,
        *,
        scope: str,
        event_type: str,
        direction: int,
        broken: SwingPoint,
        origin: SwingPoint,
        bar_index: int,
        close: float,
        safe_atr: float,
        open_: float,
        high: float,
        low: float,
    ) -> BreakCandidate:
        runtime.next_candidate_id += 1
        buffer = self._buffer(scope, event_type, safe_atr)
        initial_quality = break_impulse_quality(
            direction,
            float(broken.price),
            buffer,
            safe_atr,
            open_=open_,
            high=high,
            low=low,
            close=close,
            min_tick=self.break_config.min_tick,
        )
        distance = (close - float(broken.price)) / safe_atr if direction == 1 else (float(broken.price) - close) / safe_atr
        return BreakCandidate(
            valid=True,
            identity=runtime.next_candidate_id,
            scope=scope,
            side=broken.side,
            intended_event_type=event_type,
            direction=direction,
            status="BREAK_CANDIDATE",
            candidate_bar=bar_index,
            expiry_bar=bar_index + self.break_config.break_confirm_window,
            level=float(broken.price),
            buffer=buffer,
            candidate_atr=safe_atr,
            candidate_close=close,
            first_close_distance_atr=distance,
            initial_quality=initial_quality,
            broken_swing_identity=broken.identity,
            broken_source_bar=int(broken.source_bar),
            broken_quality=broken.quality or 50.0,
            broken_side=broken.side,
            origin_swing_identity=origin.identity,
            origin_source_bar=int(origin.source_bar),
            origin_quality=origin.quality or 50.0,
            origin_side=origin.side,
        )

    def _candidate_target(
        self,
        runtime: _RuntimeScope,
        swings: list[SwingPoint],
        high_candidate: SwingPoint,
        low_candidate: SwingPoint,
        *,
        scope: str,
        bar_index: int,
        close: float,
        safe_atr: float,
        open_: float,
        high: float,
        low: float,
    ) -> BreakCandidate:
        ctx = runtime.context
        last_high = active_by_id(swings, ctx.last_confirmed_high_identity)
        last_low = active_by_id(swings, ctx.last_confirmed_low_identity)
        protected_high = active_by_id(swings, ctx.protected_high_identity)
        protected_low = active_by_id(swings, ctx.protected_low_identity)
        weak_high = active_by_id(swings, ctx.weak_high_identity)
        weak_low = active_by_id(swings, ctx.weak_low_identity)

        # Priority 1: transition failure restores the old main direction.
        if ctx.state == STATE_TRANSITION_DOWN and protected_high.valid:
            buffer = self._buffer(scope, EVENT_TRANSITION_FAIL, safe_atr)
            if self._breaks_level(1, float(protected_high.price), buffer, close) and protected_high.identity != runtime.last_broken_high:
                origin = self._find_origin(swings, low_candidate, SIDE_LOW, int(protected_high.source_bar), bar_index, scope)
                if origin.valid:
                    return self._new_candidate(runtime, scope=scope, event_type=EVENT_TRANSITION_FAIL, direction=1, broken=protected_high, origin=origin, bar_index=bar_index, close=close, safe_atr=safe_atr, open_=open_, high=high, low=low)
        if ctx.state == STATE_TRANSITION_UP and protected_low.valid:
            buffer = self._buffer(scope, EVENT_TRANSITION_FAIL, safe_atr)
            if self._breaks_level(-1, float(protected_low.price), buffer, close) and protected_low.identity != runtime.last_broken_low:
                origin = self._find_origin(swings, high_candidate, SIDE_HIGH, int(protected_low.source_bar), bar_index, scope)
                if origin.valid:
                    return self._new_candidate(runtime, scope=scope, event_type=EVENT_TRANSITION_FAIL, direction=-1, broken=protected_low, origin=origin, bar_index=bar_index, close=close, safe_atr=safe_atr, open_=open_, high=high, low=low)

        # Priority 2: CHoCH only breaks the protected anchor of the main direction.
        if ctx.state == STATE_BEARISH and ctx.direction == -1 and protected_high.valid:
            buffer = self._buffer(scope, EVENT_CHOCH, safe_atr)
            if self._breaks_level(1, float(protected_high.price), buffer, close) and protected_high.identity != runtime.last_broken_high:
                origin = self._find_origin(swings, low_candidate, SIDE_LOW, int(protected_high.source_bar), bar_index, scope)
                if origin.valid:
                    return self._new_candidate(runtime, scope=scope, event_type=EVENT_CHOCH, direction=1, broken=protected_high, origin=origin, bar_index=bar_index, close=close, safe_atr=safe_atr, open_=open_, high=high, low=low)
        if ctx.state == STATE_BULLISH and ctx.direction == 1 and protected_low.valid:
            buffer = self._buffer(scope, EVENT_CHOCH, safe_atr)
            if self._breaks_level(-1, float(protected_low.price), buffer, close) and protected_low.identity != runtime.last_broken_low:
                origin = self._find_origin(swings, high_candidate, SIDE_HIGH, int(protected_low.source_bar), bar_index, scope)
                if origin.valid:
                    return self._new_candidate(runtime, scope=scope, event_type=EVENT_CHOCH, direction=-1, broken=protected_low, origin=origin, bar_index=bar_index, close=close, safe_atr=safe_atr, open_=open_, high=high, low=low)

        # Priority 3: BOS. Weak is preferred, then latest confirmed after protected,
        # then a gated provisional candidate.
        neutral = ctx.state == STATE_NEUTRAL and ctx.direction == 0
        bullish_allowed = ctx.direction == 1 or ctx.state == STATE_TRANSITION_UP or neutral
        bearish_allowed = ctx.direction == -1 or ctx.state == STATE_TRANSITION_DOWN or neutral

        bullish_fallback = self._latest_confirmed_after(swings, SIDE_HIGH, int(protected_low.source_bar)) if protected_low.valid else SwingPoint()
        bearish_fallback = self._latest_confirmed_after(swings, SIDE_LOW, int(protected_high.source_bar)) if protected_high.valid else SwingPoint()
        bullish_provisional = high_candidate if (
            high_candidate.valid and (neutral or (protected_low.valid and high_candidate.source_bar is not None and high_candidate.source_bar > int(protected_low.source_bar)))
            and self._provisional_gate(high_candidate, scope, bar_index, False)
        ) else SwingPoint()
        bearish_provisional = low_candidate if (
            low_candidate.valid and (neutral or (protected_high.valid and low_candidate.source_bar is not None and low_candidate.source_bar > int(protected_high.source_bar)))
            and self._provisional_gate(low_candidate, scope, bar_index, False)
        ) else SwingPoint()

        bullish_target = (weak_high if weak_high.valid else bullish_fallback if bullish_fallback.valid else bullish_provisional) if (ctx.direction == 1 or ctx.state == STATE_TRANSITION_UP) else (last_high if last_high.valid else bullish_provisional)
        bearish_target = (weak_low if weak_low.valid else bearish_fallback if bearish_fallback.valid else bearish_provisional) if (ctx.direction == -1 or ctx.state == STATE_TRANSITION_DOWN) else (last_low if last_low.valid else bearish_provisional)

        bullish_break = False
        bearish_break = False
        bos_buffer = self._buffer(scope, EVENT_BOS, safe_atr)
        if bullish_allowed and bullish_target.valid and bullish_target.identity != runtime.last_broken_high:
            bullish_break = self._breaks_level(1, float(bullish_target.price), bos_buffer, close)
        if bearish_allowed and bearish_target.valid and bearish_target.identity != runtime.last_broken_low:
            bearish_break = self._breaks_level(-1, float(bearish_target.price), bos_buffer, close)

        bullish_excess = (close - float(bullish_target.price)) / safe_atr if bullish_break else -1.0
        bearish_excess = (float(bearish_target.price) - close) / safe_atr if bearish_break else -1.0
        choose_bullish = bullish_break and (not bearish_break or bullish_excess >= bearish_excess)
        choose_bearish = bearish_break and not choose_bullish

        if choose_bullish:
            origin = self._find_origin(swings, low_candidate, SIDE_LOW, int(bullish_target.source_bar), bar_index, scope)
            if origin.valid:
                return self._new_candidate(runtime, scope=scope, event_type=EVENT_BOS, direction=1, broken=bullish_target, origin=origin, bar_index=bar_index, close=close, safe_atr=safe_atr, open_=open_, high=high, low=low)
        if choose_bearish:
            origin = self._find_origin(swings, high_candidate, SIDE_HIGH, int(bearish_target.source_bar), bar_index, scope)
            if origin.valid:
                return self._new_candidate(runtime, scope=scope, event_type=EVENT_BOS, direction=-1, broken=bearish_target, origin=origin, bar_index=bar_index, close=close, safe_atr=safe_atr, open_=open_, high=high, low=low)
        return BreakCandidate()

    def process_scope(
        self,
        *,
        scope: str,
        swings: list[SwingPoint],
        high_candidate: SwingPoint,
        low_candidate: SwingPoint,
        bar_index: int,
        open_: float,
        high: float,
        low: float,
        close: float,
        safe_atr: float,
    ) -> list[StructureEvent]:
        runtime = self.scope(scope)
        ctx = runtime.context
        latest_high = self._latest_confirmed(swings, SIDE_HIGH)
        latest_low = self._latest_confirmed(swings, SIDE_LOW)
        ctx.last_confirmed_high_identity = latest_high.identity if latest_high.valid else ctx.last_confirmed_high_identity
        ctx.last_confirmed_low_identity = latest_low.identity if latest_low.valid else ctx.last_confirmed_low_identity
        ctx = normalize_directional_roles(swings, ctx)
        runtime.context = ctx

        events: list[StructureEvent] = []

        # Sweep remains an event, not a structural direction change.
        protected_high = active_by_id(swings, ctx.protected_high_identity)
        protected_low = active_by_id(swings, ctx.protected_low_identity)
        weak_high = active_by_id(swings, ctx.weak_high_identity)
        weak_low = active_by_id(swings, ctx.weak_low_identity)
        high_target = protected_high if protected_high.valid else weak_high if weak_high.valid else latest_high
        low_target = protected_low if protected_low.valid else weak_low if weak_low.valid else latest_low
        sweep_buffer = max(safe_atr * self.break_config.break_buffer_atr * self.break_config.profile_break_mult, self.break_config.min_tick * 3.0)
        if high_target.valid and is_sweep(SIDE_HIGH, float(high_target.price), sweep_buffer, high=high, low=low, close=close):
            runtime.next_event_id += 1
            events.append(StructureEvent(valid=True, identity=runtime.next_event_id, scope=scope, event_type=EVENT_SWEEP, direction=-1, candidate_bar=bar_index, event_bar=bar_index, broken_swing_identity=high_target.identity, level=high_target.price, quality=45.0, evidence_text="HIGH_SWEEP"))
        elif low_target.valid and is_sweep(SIDE_LOW, float(low_target.price), sweep_buffer, high=high, low=low, close=close):
            runtime.next_event_id += 1
            events.append(StructureEvent(valid=True, identity=runtime.next_event_id, scope=scope, event_type=EVENT_SWEEP, direction=1, candidate_bar=bar_index, event_bar=bar_index, broken_swing_identity=low_target.identity, level=low_target.price, quality=45.0, evidence_text="LOW_SWEEP"))

        if not runtime.candidate.valid:
            runtime.candidate = self._candidate_target(runtime, swings, high_candidate, low_candidate, scope=scope, bar_index=bar_index, close=close, safe_atr=safe_atr, open_=open_, high=high, low=low)

        if runtime.candidate.valid:
            evaluation = evaluate_break_candidate(runtime.candidate, self.break_config, bar_index=bar_index, open_=open_, high=high, low=low, close=close)
            runtime.candidate.current_evidence = evaluation.evidence_count
            runtime.candidate.required_evidence = evaluation.required_evidence
            runtime.candidate.status_text = evaluation.status_text
            if evaluation.confirmed:
                runtime.next_event_id += 1
                new_ctx, event = finalize_confirmed_break(
                    swings,
                    runtime.context,
                    runtime.candidate,
                    event_identity=runtime.next_event_id,
                    event_bar=bar_index,
                    acceptance=evaluation.acceptance,
                    follow_through=evaluation.follow_through,
                )
                runtime.context = new_ctx
                runtime.last_event = event
                if runtime.candidate.direction == 1:
                    runtime.last_broken_high = runtime.candidate.broken_swing_identity
                else:
                    runtime.last_broken_low = runtime.candidate.broken_swing_identity
                runtime.candidate = BreakCandidate()
                events.append(event)
            elif evaluation.failed:
                runtime.next_event_id += 1
                event = StructureEvent(
                    valid=True,
                    identity=runtime.next_event_id,
                    scope=scope,
                    event_type=EVENT_FALSE_BREAK,
                    direction=-runtime.candidate.direction,
                    candidate_bar=runtime.candidate.candidate_bar,
                    event_bar=bar_index,
                    broken_swing_identity=runtime.candidate.broken_swing_identity,
                    broken_source_bar=runtime.candidate.broken_source_bar,
                    origin_swing_identity=runtime.candidate.origin_swing_identity,
                    origin_source_bar=runtime.candidate.origin_source_bar,
                    level=runtime.candidate.level,
                    quality=runtime.candidate.initial_quality,
                    evidence_text=evaluation.status_text,
                )
                runtime.last_event = event
                runtime.candidate = BreakCandidate()
                events.append(event)

        return events

    def score(self, *, bar_index: int) -> float:
        return structure_score(self.external.context, self.internal.context, self.external.last_event, self.internal.last_event, bar_index=bar_index)

    def export(self, external_swings: list[SwingPoint], internal_swings: list[SwingPoint], *, bar_index: int) -> MarketStructureExport:
        score = self.score(bar_index=bar_index)
        return export_snapshot(external_swings, internal_swings, self.external.context, self.internal.context, evidence_score=score)
