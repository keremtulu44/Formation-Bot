from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Iterable

import pandas as pd

from .base import BaseEngine
from .models import Direction, EngineResult

SCOPE_EXTERNAL = "EXTERNAL"
SCOPE_INTERNAL = "INTERNAL"
SIDE_HIGH = "HIGH"
SIDE_LOW = "LOW"

SWING_CANDIDATE = "SWING_CANDIDATE"
SWING_CONFIRMED = "SWING_CONFIRMED"
SWING_BROKEN = "SWING_BROKEN"
SWING_ARCHIVED = "SWING_ARCHIVED"

CLASS_PH = "PH"
CLASS_PL = "PL"
CLASS_HH = "HH"
CLASS_HL = "HL"
CLASS_LH = "LH"
CLASS_LL = "LL"

ROLE_NEUTRAL_HIGH = "NEUTRAL_HIGH"
ROLE_NEUTRAL_LOW = "NEUTRAL_LOW"

CANDIDATE_REJECT = 0
CANDIDATE_NEW = 1
CANDIDATE_REPLACE = 2
CANDIDATE_MERGE = 3

PROFILE_DISTANCE_MULT = {
    "Hassas": 0.72,
    "Dengeli": 1.0,
    "Seçici": 1.42,
}


@dataclass(frozen=True, slots=True)
class MarketStructureConfig:
    profile: str = "Dengeli"
    external_pivot_len: int = 5
    internal_pivot_len: int = 2
    external_min_atr_distance: float = 0.45
    internal_min_atr_distance: float = 0.20
    equal_tolerance_atr: float = 0.16
    atr_length: int = 14
    min_tick: float = 0.01

    def __post_init__(self) -> None:
        if self.profile not in PROFILE_DISTANCE_MULT:
            raise ValueError(f"unsupported profile: {self.profile}")
        if self.external_pivot_len < 2:
            raise ValueError("external_pivot_len must be >= 2")
        if self.internal_pivot_len < 1:
            raise ValueError("internal_pivot_len must be >= 1")
        if self.atr_length < 1:
            raise ValueError("atr_length must be >= 1")
        if self.min_tick <= 0:
            raise ValueError("min_tick must be > 0")

    @property
    def distance_multiplier(self) -> float:
        return PROFILE_DISTANCE_MULT[self.profile]

    @property
    def effective_external_min_atr(self) -> float:
        return self.external_min_atr_distance * self.distance_multiplier

    @property
    def effective_internal_min_atr(self) -> float:
        return self.internal_min_atr_distance * self.distance_multiplier

    @property
    def mintick_tolerance(self) -> float:
        return self.min_tick * 2.0


@dataclass(frozen=True, slots=True)
class SwingPoint:
    valid: bool = False
    identity: int = 0
    scope: str = ""
    side: str = ""
    state: str = SWING_CANDIDATE
    swing_class: str = ""
    structural_role: str = ""
    source_bar: int | None = None
    confirm_bar: int | None = None
    price: float | None = None
    atr_at_source: float | None = None
    prominence_atr: float | None = None
    distance_atr: float | None = None
    distance_pct: float | None = None
    previous_same_side_identity: int = 0
    previous_opposite_identity: int = 0
    finalized: bool = False
    locked: bool = False
    broken: bool = False
    broken_bar: int | None = None
    quality: float | None = None
    evidence_text: str = ""
    invalid_reason: str = ""


@dataclass(slots=True)
class _ScopeState:
    swings: list[SwingPoint]
    high_candidate: SwingPoint
    low_candidate: SwingPoint
    last_confirmed_high_identity: int = 0
    last_confirmed_low_identity: int = 0


class MarketStructureEngine(BaseEngine):
    """ARGENT Market Structure swing core, ported from Pine without visual state.

    Turn 1 intentionally contains only deterministic swing discovery/lifecycle:
    raw pivot confirmation, candidate replace/merge, alternating confirmation,
    and HH/HL/LH/LL classification. Break/BOS/CHoCH roles are layered later.
    """

    name = "market_structure"

    def __init__(self, config: MarketStructureConfig | None = None) -> None:
        self.config = config or MarketStructureConfig()
        self.reset()

    def reset(self) -> None:
        self._rows: list[dict[str, Any]] = []
        self._atr_values: list[float | None] = []
        self._tr_values: list[float] = []
        self._next_swing_identity = 0
        self._external = _ScopeState([], SwingPoint(), SwingPoint())
        self._internal = _ScopeState([], SwingPoint(), SwingPoint())
        self._snapshot: EngineResult | None = None

    def replay(self, frame: pd.DataFrame) -> list[EngineResult]:
        self.reset()
        results: list[EngineResult] = []
        for row in frame.to_dict("records"):
            result = self.update(row)
            if result is not None:
                results.append(result)
        return results

    def update(self, bar: pd.Series | dict[str, Any]) -> EngineResult | None:
        row = dict(bar) if isinstance(bar, dict) else bar.to_dict()
        if not bool(row.get("is_closed", True)) or not bool(row.get("is_complete", True)):
            return self._snapshot

        required = ("timestamp", "open", "high", "low", "close")
        missing = [key for key in required if key not in row or pd.isna(row[key])]
        if missing:
            raise ValueError(f"market structure requires closed OHLC bars; missing {missing}")

        clean = {
            "timestamp": row["timestamp"],
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
        }
        self._rows.append(clean)
        self._append_atr(clean)
        bar_index = len(self._rows) - 1

        events: list[str] = []
        events.extend(self._process_scope(self._external, SCOPE_EXTERNAL, self.config.external_pivot_len, self.config.effective_external_min_atr, bar_index))
        events.extend(self._process_scope(self._internal, SCOPE_INTERNAL, self.config.internal_pivot_len, self.config.effective_internal_min_atr, bar_index))

        levels = self._public_levels()
        reasons = tuple(events)
        state = "SWING_READY" if (self._external.swings or self._internal.swings) else "SWING_BUILDING"
        self._snapshot = EngineResult(
            engine=self.name,
            state=state,
            timestamp=clean["timestamp"],
            direction=Direction.NEUTRAL,
            levels=levels,
            events=tuple(events),
            reasons=reasons,
            is_confirmed=True,
        )
        return self._snapshot

    def snapshot(self) -> EngineResult | None:
        return self._snapshot

    @property
    def external_swings(self) -> tuple[SwingPoint, ...]:
        return tuple(self._external.swings)

    @property
    def internal_swings(self) -> tuple[SwingPoint, ...]:
        return tuple(self._internal.swings)

    @property
    def external_candidates(self) -> tuple[SwingPoint, SwingPoint]:
        return self._external.high_candidate, self._external.low_candidate

    @property
    def internal_candidates(self) -> tuple[SwingPoint, SwingPoint]:
        return self._internal.high_candidate, self._internal.low_candidate

    def _append_atr(self, row: dict[str, Any]) -> None:
        idx = len(self._rows) - 1
        previous_close = self._rows[idx - 1]["close"] if idx > 0 else None
        tr = row["high"] - row["low"]
        if previous_close is not None:
            tr = max(tr, abs(row["high"] - previous_close), abs(row["low"] - previous_close))
        self._tr_values.append(float(tr))

        length = self.config.atr_length
        if len(self._tr_values) < length:
            atr = None
        elif len(self._tr_values) == length:
            atr = sum(self._tr_values[-length:]) / length
        else:
            previous_atr = self._atr_values[-1]
            if previous_atr is None:
                atr = sum(self._tr_values[-length:]) / length
            else:
                atr = (previous_atr * (length - 1) + tr) / length
        self._atr_values.append(None if atr is None else float(atr))

    def _process_scope(self, scope_state: _ScopeState, scope: str, pivot_len: int, min_atr_distance: float, bar_index: int) -> list[str]:
        source_bar = bar_index - pivot_len
        if source_bar < pivot_len or bar_index < pivot_len * 2:
            return []

        high_pivot = self._is_pivot_high(source_bar, pivot_len)
        low_pivot = self._is_pivot_low(source_bar, pivot_len)
        if not high_pivot and not low_pivot:
            return []

        source_atr = self._atr_at(source_bar)
        window = self._rows[source_bar - pivot_len : source_bar + pivot_len + 1]
        pivot_high = self._rows[source_bar]["high"]
        pivot_low = self._rows[source_bar]["low"]
        window_low = min(r["low"] for r in window)
        window_high = max(r["high"] for r in window)
        high_prominence = max(pivot_high - window_low, 0.0) / source_atr
        low_prominence = max(window_high - pivot_low, 0.0) / source_atr

        use_high = high_pivot and not low_pivot
        use_low = low_pivot and not high_pivot
        if high_pivot and low_pivot:
            choice = self._choose_dual_pivot(scope_state.swings, high_prominence, low_prominence, self._rows[source_bar]["open"], self._rows[source_bar]["close"])
            use_high = choice == 1
            use_low = choice == -1

        events: list[str] = []
        if use_high:
            events.extend(self._accept_pivot(scope_state, scope, SIDE_HIGH, source_bar, bar_index, pivot_high, source_atr, high_prominence, min_atr_distance, pivot_len))
        if use_low:
            events.extend(self._accept_pivot(scope_state, scope, SIDE_LOW, source_bar, bar_index, pivot_low, source_atr, low_prominence, min_atr_distance, pivot_len))
        return events

    def _accept_pivot(
        self,
        scope_state: _ScopeState,
        scope: str,
        side: str,
        source_bar: int,
        confirm_bar: int,
        price: float,
        source_atr: float,
        prominence: float,
        min_atr_distance: float,
        pivot_len: int,
    ) -> list[str]:
        previous_high = self._last_historical(scope_state.swings, SIDE_HIGH)
        previous_low = self._last_historical(scope_state.swings, SIDE_LOW)
        previous_same = previous_high if side == SIDE_HIGH else previous_low
        previous_opposite = previous_low if side == SIDE_HIGH else previous_high

        if previous_opposite.valid and previous_opposite.price is not None:
            distance_atr = abs(price - previous_opposite.price) / self._leg_reference_atr(source_atr, previous_opposite)
            denominator = max(abs(previous_opposite.price if side == SIDE_HIGH else price), self.config.min_tick)
            distance_pct = abs(price - previous_opposite.price) / denominator * 100.0
        else:
            distance_atr = min_atr_distance + 0.5
            distance_pct = None

        incoming = self._new_swing(
            identity=self._next_swing_identity + 1,
            scope=scope,
            side=side,
            source_bar=source_bar,
            confirm_bar=confirm_bar,
            price=price,
            source_atr=source_atr,
            prominence_atr=prominence,
            distance_atr=distance_atr,
            distance_pct=distance_pct,
            previous_same=previous_same,
            previous_opposite=previous_opposite,
            evidence="raw pivot high" if side == SIDE_HIGH else "raw pivot low",
        )

        current_candidate = scope_state.high_candidate if side == SIDE_HIGH else scope_state.low_candidate
        updated, action = self._candidate_update(current_candidate, incoming, locked_by_break=False)
        if side == SIDE_HIGH:
            scope_state.high_candidate = updated
            opposite_candidate = scope_state.low_candidate
        else:
            scope_state.low_candidate = updated
            opposite_candidate = scope_state.high_candidate

        if action == CANDIDATE_NEW:
            self._next_swing_identity += 1

        last_any = self._last_historical_any(scope_state.swings)
        min_leg_bars = max(3, pivot_len) if scope == SCOPE_EXTERNAL else max(2, pivot_len)
        events: list[str] = []
        if self._can_confirm(opposite_candidate, last_any, min_atr_distance, min_leg_bars):
            opp_same = self._last_historical(scope_state.swings, opposite_candidate.side)
            opp_other = self._last_historical(scope_state.swings, SIDE_LOW if opposite_candidate.side == SIDE_HIGH else SIDE_HIGH)
            confirmed = self._promote(opposite_candidate, opp_same, opp_other, confirm_bar)
            scope_state.swings.append(confirmed)
            if confirmed.side == SIDE_HIGH:
                scope_state.last_confirmed_high_identity = confirmed.identity
                scope_state.high_candidate = SwingPoint()
            else:
                scope_state.last_confirmed_low_identity = confirmed.identity
                scope_state.low_candidate = SwingPoint()
            events.append(f"{scope}:SWING_CONFIRMED:{confirmed.side}:{confirmed.swing_class}:{confirmed.identity}")
        return events

    def _new_swing(
        self,
        *,
        identity: int,
        scope: str,
        side: str,
        source_bar: int,
        confirm_bar: int,
        price: float,
        source_atr: float,
        prominence_atr: float,
        distance_atr: float,
        distance_pct: float | None,
        previous_same: SwingPoint,
        previous_opposite: SwingPoint,
        evidence: str,
    ) -> SwingPoint:
        quality = min(100.0, 34.0 + min(max(prominence_atr, 0.0), 3.0) * 12.0 + min(max(distance_atr, 0.0), 3.0) * 14.0)
        return SwingPoint(
            valid=True,
            identity=identity,
            scope=scope,
            side=side,
            structural_role=ROLE_NEUTRAL_HIGH if side == SIDE_HIGH else ROLE_NEUTRAL_LOW,
            source_bar=source_bar,
            confirm_bar=confirm_bar,
            price=float(price),
            atr_at_source=float(source_atr),
            prominence_atr=float(prominence_atr),
            distance_atr=float(distance_atr),
            distance_pct=distance_pct,
            previous_same_side_identity=previous_same.identity if previous_same.valid else 0,
            previous_opposite_identity=previous_opposite.identity if previous_opposite.valid else 0,
            quality=quality,
            evidence_text=evidence,
        )

    def _candidate_update(self, candidate: SwingPoint, incoming: SwingPoint, locked_by_break: bool) -> tuple[SwingPoint, int]:
        if not candidate.valid:
            return incoming, CANDIDATE_NEW

        tolerance = max(self._pair_reference_atr(candidate, incoming) * self.config.equal_tolerance_atr, self.config.mintick_tolerance)
        stronger = incoming.price > candidate.price if incoming.side == SIDE_HIGH else incoming.price < candidate.price
        clearly_stronger = incoming.price > candidate.price + tolerance if incoming.side == SIDE_HIGH else incoming.price < candidate.price - tolerance
        same_area = abs(float(incoming.price) - float(candidate.price)) <= tolerance

        if locked_by_break:
            if clearly_stronger or (same_area and stronger):
                return replace(incoming, evidence_text="candidate fork: prior identity locked by break"), CANDIDATE_NEW
            return candidate, CANDIDATE_REJECT

        if clearly_stronger:
            return replace(
                incoming,
                identity=candidate.identity,
                quality=max(incoming.quality or 0.0, (candidate.quality or 0.0) * 0.92),
                prominence_atr=max(incoming.prominence_atr or 0.0, candidate.prominence_atr or 0.0),
                evidence_text="candidate replace: stronger extreme",
            ), CANDIDATE_REPLACE

        if same_area:
            if stronger:
                merged = replace(
                    incoming,
                    identity=candidate.identity,
                    quality=max(incoming.quality or 0.0, candidate.quality or 0.0),
                    prominence_atr=max(incoming.prominence_atr or 0.0, candidate.prominence_atr or 0.0),
                    evidence_text="candidate merge: stronger extreme",
                )
            else:
                merged = replace(
                    candidate,
                    confirm_bar=incoming.confirm_bar,
                    prominence_atr=max(candidate.prominence_atr or 0.0, incoming.prominence_atr or 0.0),
                    quality=max(candidate.quality or 0.0, (incoming.quality or 0.0) * 0.95),
                    evidence_text="candidate merge: existing extreme kept",
                )
            return merged, CANDIDATE_MERGE

        return candidate, CANDIDATE_REJECT

    def _promote(self, candidate: SwingPoint, previous_same: SwingPoint, previous_opposite: SwingPoint, confirm_bar: int) -> SwingPoint:
        promoted_quality = (
            36.0
            + min(max(candidate.prominence_atr or 0.0, 0.0), 3.0) * 12.0
            + min(max(candidate.distance_atr or 0.0, 0.0), 3.0) * 14.0
            + (8.0 if previous_opposite.valid else 0.0)
        )
        return replace(
            candidate,
            state=SWING_CONFIRMED,
            confirm_bar=confirm_bar,
            finalized=True,
            locked=True,
            swing_class=self._classify(candidate, previous_same),
            previous_same_side_identity=previous_same.identity if previous_same.valid else 0,
            previous_opposite_identity=previous_opposite.identity if previous_opposite.valid else 0,
            quality=min(100.0, max(candidate.quality or 0.0, promoted_quality)),
            invalid_reason="",
            evidence_text="confirmed by opposite pivot",
        )

    def _classify(self, candidate: SwingPoint, previous_same: SwingPoint) -> str:
        cls = CLASS_PH if candidate.side == SIDE_HIGH else CLASS_PL
        if not previous_same.valid:
            return cls
        tolerance = max(self._pair_reference_atr(candidate, previous_same) * self.config.equal_tolerance_atr, self.config.mintick_tolerance)
        if candidate.side == SIDE_HIGH:
            if candidate.price > previous_same.price + tolerance:
                return CLASS_HH
            if candidate.price < previous_same.price - tolerance:
                return CLASS_LH
            return CLASS_PH
        if candidate.price < previous_same.price - tolerance:
            return CLASS_LL
        if candidate.price > previous_same.price + tolerance:
            return CLASS_HL
        return CLASS_PL

    def _can_confirm(self, candidate: SwingPoint, last_confirmed: SwingPoint, min_atr_distance: float, min_leg_bars: int) -> bool:
        if not candidate.valid:
            return False
        alternates = not last_confirmed.valid or last_confirmed.side != candidate.side
        if not alternates:
            return False

        first_historical = not last_confirmed.valid
        reference_atr = max(candidate.atr_at_source or self.config.min_tick, self.config.min_tick) if first_historical else self._pair_reference_atr(candidate, last_confirmed)
        leg_distance_atr = min_atr_distance + 1.0 if first_historical else abs(candidate.price - last_confirmed.price) / reference_atr
        leg_bars = min_leg_bars if first_historical else abs(int(candidate.source_bar) - int(last_confirmed.source_bar))
        full_distance = leg_distance_atr >= min_atr_distance
        prominence_floor = max(0.20, min_atr_distance * 0.55) if candidate.scope == SCOPE_EXTERNAL else max(0.12, min_atr_distance * 0.55)
        near_distance = leg_distance_atr >= min_atr_distance * 0.90
        supported_near = near_distance and leg_bars >= min_leg_bars and (candidate.prominence_atr or 0.0) >= prominence_floor
        return first_historical or full_distance or supported_near

    def _pair_reference_atr(self, first: SwingPoint, second: SwingPoint) -> float:
        values = [value for value in (first.atr_at_source if first.valid else None, second.atr_at_source if second.valid else None) if value is not None]
        if values:
            return max(sum(values) / len(values), self.config.min_tick)
        latest = next((value for value in reversed(self._atr_values) if value is not None), self.config.min_tick)
        return max(float(latest), self.config.min_tick)

    def _leg_reference_atr(self, source_atr: float, opposite: SwingPoint) -> float:
        opposite_atr = opposite.atr_at_source if opposite.valid and opposite.atr_at_source is not None else source_atr
        return max((source_atr + float(opposite_atr)) * 0.5, self.config.min_tick)

    def _choose_dual_pivot(self, swings: Iterable[SwingPoint], high_prominence: float, low_prominence: float, source_open: float, source_close: float) -> int:
        last = self._last_historical_any(list(swings))
        if last.valid:
            return 1 if last.side == SIDE_LOW else -1
        difference = high_prominence - low_prominence
        if abs(difference) > 0.05:
            return 1 if difference > 0.0 else -1
        return 1 if source_close >= source_open else -1

    def _is_pivot_high(self, source: int, length: int) -> bool:
        value = self._rows[source]["high"]
        window = [row["high"] for row in self._rows[source - length : source + length + 1]]
        return value == max(window)

    def _is_pivot_low(self, source: int, length: int) -> bool:
        value = self._rows[source]["low"]
        window = [row["low"] for row in self._rows[source - length : source + length + 1]]
        return value == min(window)

    def _atr_at(self, source_bar: int) -> float:
        value = self._atr_values[source_bar]
        if value is not None:
            return max(value, self.config.min_tick)
        current = next((v for v in reversed(self._atr_values) if v is not None), None)
        if current is not None:
            return max(current, self.config.min_tick)
        true_range = self._tr_values[source_bar] if source_bar < len(self._tr_values) else self.config.min_tick
        return max(true_range, self.config.min_tick)

    @staticmethod
    def _last_historical(swings: list[SwingPoint], side: str) -> SwingPoint:
        for swing in reversed(swings):
            if swing.valid and swing.finalized and swing.side == side and swing.state in {SWING_CONFIRMED, SWING_BROKEN}:
                return swing
        return SwingPoint()

    @staticmethod
    def _last_historical_any(swings: list[SwingPoint]) -> SwingPoint:
        for swing in reversed(swings):
            if swing.valid and swing.finalized and swing.state in {SWING_CONFIRMED, SWING_BROKEN}:
                return swing
        return SwingPoint()

    def _public_levels(self) -> dict[str, float]:
        levels: dict[str, float] = {}
        for prefix, state in (("external", self._external), ("internal", self._internal)):
            high = self._last_historical(state.swings, SIDE_HIGH)
            low = self._last_historical(state.swings, SIDE_LOW)
            if high.valid and high.price is not None:
                levels[f"{prefix}_confirmed_high"] = float(high.price)
            if low.valid and low.price is not None:
                levels[f"{prefix}_confirmed_low"] = float(low.price)
            if state.high_candidate.valid and state.high_candidate.price is not None:
                levels[f"{prefix}_candidate_high"] = float(state.high_candidate.price)
            if state.low_candidate.valid and state.low_candidate.price is not None:
                levels[f"{prefix}_candidate_low"] = float(state.low_candidate.price)
        return levels
