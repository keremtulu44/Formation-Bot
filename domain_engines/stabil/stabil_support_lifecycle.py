from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable

import pandas as pd

from .stabil_trend_engine import (
    ConfirmedStabilPivot,
    StabilTrendConfig,
    _atr,
    _clean,
    _confirmed_pivots,
)


class SupportValidity(StrEnum):
    NO_SUPPORT = "NO_SUPPORT"
    ACTIVE = "ACTIVE"
    BREACHED = "BREACHED"
    BELOW_FLOOR = "BELOW_FLOOR"


class SupportDynamics(StrEnum):
    UNAVAILABLE = "UNAVAILABLE"
    AT_SUPPORT = "AT_SUPPORT"
    EXPANDING = "EXPANDING"
    CONTRACTING = "CONTRACTING"
    FLAT = "FLAT"
    BELOW_SUPPORT = "BELOW_SUPPORT"


class SupportProgression(StrEnum):
    NONE = "NONE"
    INITIAL = "INITIAL"
    SAME = "SAME"
    REBASED_HIGHER = "REBASED_HIGHER"
    REBASED_LOWER = "REBASED_LOWER"


class SupportLifecycleEventType(StrEnum):
    SUPPORT_CONFIRMED = "SUPPORT_CONFIRMED"
    SUPPORT_TESTED = "SUPPORT_TESTED"
    SUPPORT_HELD = "SUPPORT_HELD"
    SUPPORT_BREACHED = "SUPPORT_BREACHED"
    SUPPORT_FLOOR_BROKEN = "SUPPORT_FLOOR_BROKEN"
    SUPPORT_RECLAIMED = "SUPPORT_RECLAIMED"
    SUPPORT_LOST = "SUPPORT_LOST"
    SUPPORT_REBASED_HIGHER = "SUPPORT_REBASED_HIGHER"
    SUPPORT_REBASED_LOWER = "SUPPORT_REBASED_LOWER"


@dataclass(frozen=True, slots=True)
class DailySupportObservation:
    timestamp: Any
    high: float
    low: float
    close: float
    atr: float | None
    support_level: float | None
    support_floor: float | None
    support_origin_at: Any | None
    support_confirmed_at: Any | None
    support_available_at: Any | None
    support_origin_index: int | None
    support_confirmed_index: int | None

    @property
    def support_identity(self) -> tuple[Any, Any, float] | None:
        if (
            self.support_level is None
            or self.support_origin_at is None
            or self.support_confirmed_at is None
        ):
            return None
        return (
            self.support_origin_at,
            self.support_confirmed_at,
            float(self.support_level),
        )


@dataclass(frozen=True, slots=True)
class SupportLifecycleEvent:
    sequence: int
    event_type: SupportLifecycleEventType
    event_time: Any
    origin_at: Any | None
    confirmed_at: Any | None
    available_at: Any
    support_level: float | None
    support_floor: float | None
    previous_support: float | None
    new_support: float | None
    price: float
    atr: float | None
    distance_pct: float | None
    distance_atr: float | None
    bars_since_support: int | None
    bars_above_support: int
    bars_below_support: int
    reclaim_count: int
    progression: SupportProgression


@dataclass(frozen=True, slots=True)
class StabilSupportLifecycleSnapshot:
    as_of: Any | None
    support_level: float | None
    support_floor: float | None
    support_origin_at: Any | None
    support_confirmed_at: Any | None
    support_available_at: Any | None
    validity: SupportValidity
    dynamics: SupportDynamics
    progression: SupportProgression
    distance_pct: float | None
    distance_atr: float | None
    distance_delta_atr: float | None
    bars_since_support: int | None
    bars_above_support: int
    bars_below_support: int
    reclaim_count: int
    intrabar_below_support: bool
    close_below_support: bool
    close_below_floor: bool
    events: tuple[SupportLifecycleEvent, ...]


def _distance_pct(price: float, support: float | None) -> float | None:
    if support is None or abs(float(support)) <= 1e-12:
        return None
    return (float(price) - float(support)) / abs(float(support)) * 100.0


def _distance_atr(price: float, support: float | None, atr: float | None) -> float | None:
    if support is None or atr is None or abs(float(atr)) <= 1e-12:
        return None
    return (float(price) - float(support)) / float(atr)


def _support_progression(
    previous: float | None,
    current: float | None,
    *,
    min_tick: float,
) -> SupportProgression:
    if current is None:
        return SupportProgression.NONE
    if previous is None:
        return SupportProgression.INITIAL
    delta = float(current) - float(previous)
    if delta > min_tick:
        return SupportProgression.REBASED_HIGHER
    if delta < -min_tick:
        return SupportProgression.REBASED_LOWER
    return SupportProgression.SAME


def build_daily_support_observations(
    frame: pd.DataFrame,
    *,
    config: StabilTrendConfig | None = None,
    as_of: Any | None = None,
) -> tuple[DailySupportObservation, ...]:
    """Build causal observations for Stabil's confirmed daily pivot-low support.

    Support availability is intentionally independent from the legacy Stabil trend
    warm-up (EMA, slope, acceptance and pullback lookback). Those are context inputs,
    not prerequisites for a confirmed structural support. We still preserve the
    existing pivot source, causal confirmation boundary, two-pivot structural ordering
    and ATR-derived support floor.
    """
    cfg = config or StabilTrendConfig()
    clean = _clean(frame, as_of=as_of)
    if clean.empty:
        return ()

    atr = _atr(clean)
    highs, lows = _confirmed_pivots(clean, cfg.daily_pivot_len, atr)

    out: list[DailySupportObservation] = []
    first_available_by_identity: dict[tuple[Any, Any, float], Any] = {}
    h_pos = 0
    l_pos = 0

    for i, row in clean.iterrows():
        while h_pos < len(highs) and highs[h_pos].known_index <= i:
            h_pos += 1
        while l_pos < len(lows) and lows[l_pos].known_index <= i:
            l_pos += 1
        enough = h_pos >= 2 and l_pos >= 2
        atr_i = atr[i]

        support: ConfirmedStabilPivot | None = None
        if enough:
            last_h, previous_h = highs[h_pos - 1], highs[h_pos - 2]
            last_l, previous_l = lows[l_pos - 1], lows[l_pos - 2]
            usable = (
                last_h.origin_index > previous_h.origin_index
                and last_l.origin_index > previous_l.origin_index
            )
            if usable:
                support = last_l

        support_level = float(support.price) if support is not None else None
        support_floor = (
            float(support.price - support.atr_at_origin * cfg.support_atr_tolerance)
            if support is not None
            else None
        )
        identity = (
            (support.origin_time, support.known_time, float(support.price))
            if support is not None
            else None
        )
        if identity is not None and identity not in first_available_by_identity:
            first_available_by_identity[identity] = row.timestamp

        out.append(
            DailySupportObservation(
                timestamp=row.timestamp,
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                atr=None if atr_i is None else float(atr_i),
                support_level=support_level,
                support_floor=support_floor,
                support_origin_at=support.origin_time if support is not None else None,
                support_confirmed_at=support.known_time if support is not None else None,
                support_available_at=(
                    first_available_by_identity.get(identity)
                    if identity is not None
                    else None
                ),
                support_origin_index=support.origin_index if support is not None else None,
                support_confirmed_index=support.known_index if support is not None else None,
            )
        )
    return tuple(out)


def build_support_lifecycle_timeline(
    observations: Iterable[DailySupportObservation],
    *,
    min_tick: float = 0.01,
    include_prefix_events: bool = True,
) -> tuple[StabilSupportLifecycleSnapshot, ...]:
    """Single-pass causal timeline producing exact prefix `StabilSupportLifecycleSnapshot`s."""
    items = tuple(observations)
    if not items:
        return ()

    events: list[SupportLifecycleEvent] = []
    sequence = 0

    current_identity: tuple[Any, Any, float] | None = None
    current_support: float | None = None
    current_floor: float | None = None
    current_origin_at: Any | None = None
    current_confirmed_at: Any | None = None
    current_available_at: Any | None = None
    current_available_index: int | None = None

    previous_distance_price: float | None = None
    previous_touch = False
    previous_below = False
    previous_below_floor = False

    validity = SupportValidity.NO_SUPPORT
    dynamics = SupportDynamics.UNAVAILABLE
    progression = SupportProgression.NONE
    bars_above = 0
    bars_below = 0
    reclaim_count = 0
    distance_pct = distance_atr = distance_delta_atr = None
    intrabar_below = close_below = close_below_floor = False
    timeline: list[StabilSupportLifecycleSnapshot] = []

    def emit(
        *,
        event_type: SupportLifecycleEventType,
        obs: DailySupportObservation,
        previous_support: float | None = None,
        new_support: float | None = None,
        event_progression: SupportProgression = SupportProgression.NONE,
        focal_support: float | None = None,
        focal_floor: float | None = None,
        focal_origin_at: Any | None = None,
        focal_confirmed_at: Any | None = None,
    ) -> None:
        nonlocal sequence
        sequence += 1
        price = float(obs.close)
        level = obs.support_level if focal_support is None else focal_support
        floor = obs.support_floor if focal_floor is None else focal_floor
        origin_at = (
            obs.support_origin_at
            if focal_origin_at is None
            else focal_origin_at
        )
        confirmed_at = (
            obs.support_confirmed_at
            if focal_confirmed_at is None
            else focal_confirmed_at
        )
        events.append(
            SupportLifecycleEvent(
                sequence=sequence,
                event_type=event_type,
                event_time=obs.timestamp,
                origin_at=origin_at,
                confirmed_at=confirmed_at,
                available_at=obs.timestamp,
                support_level=level,
                support_floor=floor,
                previous_support=previous_support,
                new_support=new_support,
                price=price,
                atr=obs.atr,
                distance_pct=_distance_pct(price, level),
                distance_atr=_distance_atr(price, level, obs.atr),
                bars_since_support=(
                    None
                    if current_available_index is None
                    else index - current_available_index
                ),
                bars_above_support=bars_above,
                bars_below_support=bars_below,
                reclaim_count=reclaim_count,
                progression=event_progression,
            )
        )

    for index, obs in enumerate(items):
        identity = obs.support_identity
        if identity is None:
            current_identity = None
            current_support = None
            current_floor = None
            current_origin_at = None
            current_confirmed_at = None
            current_available_at = None
            current_available_index = None
            previous_distance_price = None
            previous_touch = False
            previous_below = False
            previous_below_floor = False
            validity = SupportValidity.NO_SUPPORT
            dynamics = SupportDynamics.UNAVAILABLE
            progression = SupportProgression.NONE
            bars_above = 0
            bars_below = 0
            distance_pct = distance_atr = distance_delta_atr = None
            intrabar_below = close_below = close_below_floor = False
            timeline.append(
                StabilSupportLifecycleSnapshot(
                    as_of=obs.timestamp,
                    support_level=None,
                    support_floor=None,
                    support_origin_at=None,
                    support_confirmed_at=None,
                    support_available_at=None,
                    validity=validity,
                    dynamics=dynamics,
                    progression=progression,
                    distance_pct=None,
                    distance_atr=None,
                    distance_delta_atr=None,
                    bars_since_support=None,
                    bars_above_support=0,
                    bars_below_support=0,
                    reclaim_count=reclaim_count,
                    intrabar_below_support=False,
                    close_below_support=False,
                    close_below_floor=False,
                    events=tuple(events) if include_prefix_events else (),
                )
            )
            continue

        rebased = identity != current_identity
        old_support = current_support
        old_was_below = previous_below or previous_below_floor

        if rebased:
            progression = _support_progression(
                old_support,
                obs.support_level,
                min_tick=min_tick,
            )
            if (
                old_support is not None
                and progression is SupportProgression.REBASED_LOWER
                and old_was_below
            ):
                emit(
                    event_type=SupportLifecycleEventType.SUPPORT_LOST,
                    obs=obs,
                    previous_support=old_support,
                    new_support=obs.support_level,
                    event_progression=progression,
                    focal_support=old_support,
                    focal_floor=current_floor,
                    focal_origin_at=current_origin_at,
                    focal_confirmed_at=current_confirmed_at,
                )

            current_identity = identity
            current_support = obs.support_level
            current_floor = obs.support_floor
            current_origin_at = obs.support_origin_at
            current_confirmed_at = obs.support_confirmed_at
            current_available_at = obs.support_available_at or obs.timestamp
            current_available_index = index
            previous_distance_price = None
            previous_touch = False
            previous_below = False
            previous_below_floor = False
            bars_above = 0
            bars_below = 0
            reclaim_count = 0

            if old_support is None or progression in {
                SupportProgression.INITIAL,
                SupportProgression.SAME,
            }:
                emit(
                    event_type=SupportLifecycleEventType.SUPPORT_CONFIRMED,
                    obs=obs,
                    previous_support=old_support,
                    new_support=obs.support_level,
                    event_progression=progression,
                )
            elif progression is SupportProgression.REBASED_HIGHER:
                emit(
                    event_type=SupportLifecycleEventType.SUPPORT_REBASED_HIGHER,
                    obs=obs,
                    previous_support=old_support,
                    new_support=obs.support_level,
                    event_progression=progression,
                )
            elif progression is SupportProgression.REBASED_LOWER:
                emit(
                    event_type=SupportLifecycleEventType.SUPPORT_REBASED_LOWER,
                    obs=obs,
                    previous_support=old_support,
                    new_support=obs.support_level,
                    event_progression=progression,
                )

        assert current_support is not None
        support = float(current_support)
        floor = (
            float(current_floor)
            if current_floor is not None
            else support
        )
        close = float(obs.close)
        intrabar_below = float(obs.low) < support
        close_below = close < support
        close_below_floor = close < floor
        touch = float(obs.low) <= support <= float(obs.high)

        if close_below:
            bars_below += 1
            bars_above = 0
        else:
            bars_above += 1
            if previous_below:
                reclaim_count += 1
            bars_below = 0

        if close_below_floor:
            validity = SupportValidity.BELOW_FLOOR
        elif close_below:
            validity = SupportValidity.BREACHED
        else:
            validity = SupportValidity.ACTIVE

        current_distance_price = close - support
        distance_pct = _distance_pct(close, support)
        distance_atr = _distance_atr(close, support, obs.atr)
        if (
            previous_distance_price is None
            or obs.atr is None
            or abs(float(obs.atr)) <= 1e-12
        ):
            distance_delta_atr = None
        else:
            distance_delta_atr = (
                current_distance_price - previous_distance_price
            ) / float(obs.atr)

        if close_below:
            dynamics = SupportDynamics.BELOW_SUPPORT
        elif touch:
            dynamics = SupportDynamics.AT_SUPPORT
        elif distance_delta_atr is None:
            dynamics = SupportDynamics.FLAT
        else:
            epsilon = min_tick / max(abs(float(obs.atr or 0.0)), min_tick)
            if distance_delta_atr > epsilon:
                dynamics = SupportDynamics.EXPANDING
            elif distance_delta_atr < -epsilon:
                dynamics = SupportDynamics.CONTRACTING
            else:
                dynamics = SupportDynamics.FLAT

        if close_below and not previous_below:
            emit(
                event_type=SupportLifecycleEventType.SUPPORT_BREACHED,
                obs=obs,
                event_progression=progression,
            )
        if close_below_floor and not previous_below_floor:
            emit(
                event_type=SupportLifecycleEventType.SUPPORT_FLOOR_BROKEN,
                obs=obs,
                event_progression=progression,
            )
        if not close_below and previous_below:
            emit(
                event_type=SupportLifecycleEventType.SUPPORT_RECLAIMED,
                obs=obs,
                event_progression=progression,
            )
        if touch and not close_below and not previous_touch:
            emit(
                event_type=SupportLifecycleEventType.SUPPORT_TESTED,
                obs=obs,
                event_progression=progression,
            )
        if previous_touch and not touch and not close_below:
            emit(
                event_type=SupportLifecycleEventType.SUPPORT_HELD,
                obs=obs,
                event_progression=progression,
            )

        previous_distance_price = current_distance_price
        previous_touch = touch and not close_below
        previous_below = close_below
        previous_below_floor = close_below_floor

        bars_since_support = (
            None
            if current_available_index is None
            else index - current_available_index
        )
        timeline.append(
            StabilSupportLifecycleSnapshot(
                as_of=obs.timestamp,
                support_level=current_support,
                support_floor=current_floor,
                support_origin_at=current_origin_at,
                support_confirmed_at=current_confirmed_at,
                support_available_at=current_available_at,
                validity=validity,
                dynamics=dynamics,
                progression=progression,
                distance_pct=distance_pct,
                distance_atr=distance_atr,
                distance_delta_atr=distance_delta_atr,
                bars_since_support=bars_since_support,
                bars_above_support=bars_above,
                bars_below_support=bars_below,
                reclaim_count=reclaim_count,
                intrabar_below_support=intrabar_below,
                close_below_support=close_below,
                close_below_floor=close_below_floor,
                events=tuple(events) if include_prefix_events else (),
            )
        )

    if not include_prefix_events and timeline:
        timeline[-1] = StabilSupportLifecycleSnapshot(
            as_of=timeline[-1].as_of,
            support_level=timeline[-1].support_level,
            support_floor=timeline[-1].support_floor,
            support_origin_at=timeline[-1].support_origin_at,
            support_confirmed_at=timeline[-1].support_confirmed_at,
            support_available_at=timeline[-1].support_available_at,
            validity=timeline[-1].validity,
            dynamics=timeline[-1].dynamics,
            progression=timeline[-1].progression,
            distance_pct=timeline[-1].distance_pct,
            distance_atr=timeline[-1].distance_atr,
            distance_delta_atr=timeline[-1].distance_delta_atr,
            bars_since_support=timeline[-1].bars_since_support,
            bars_above_support=timeline[-1].bars_above_support,
            bars_below_support=timeline[-1].bars_below_support,
            reclaim_count=timeline[-1].reclaim_count,
            intrabar_below_support=timeline[-1].intrabar_below_support,
            close_below_support=timeline[-1].close_below_support,
            close_below_floor=timeline[-1].close_below_floor,
            events=tuple(events),
        )
    return tuple(timeline)


def build_support_lifecycle(
    observations: Iterable[DailySupportObservation],
    *,
    min_tick: float = 0.01,
) -> StabilSupportLifecycleSnapshot:
    items = tuple(observations)
    if not items:
        return StabilSupportLifecycleSnapshot(
            as_of=None,
            support_level=None,
            support_floor=None,
            support_origin_at=None,
            support_confirmed_at=None,
            support_available_at=None,
            validity=SupportValidity.NO_SUPPORT,
            dynamics=SupportDynamics.UNAVAILABLE,
            progression=SupportProgression.NONE,
            distance_pct=None,
            distance_atr=None,
            distance_delta_atr=None,
            bars_since_support=None,
            bars_above_support=0,
            bars_below_support=0,
            reclaim_count=0,
            intrabar_below_support=False,
            close_below_support=False,
            close_below_floor=False,
            events=(),
        )
    return build_support_lifecycle_timeline(
        items,
        min_tick=min_tick,
        include_prefix_events=False,
    )[-1]


class StabilSupportLifecycleEngine:
    """Daily structural-support lifecycle only; no trend or trading authority."""

    name = "stabil_support_lifecycle"

    def __init__(self, config: StabilTrendConfig | None = None) -> None:
        self.config = config or StabilTrendConfig()
        self._snapshot = StabilSupportLifecycleSnapshot(
            as_of=None,
            support_level=None,
            support_floor=None,
            support_origin_at=None,
            support_confirmed_at=None,
            support_available_at=None,
            validity=SupportValidity.NO_SUPPORT,
            dynamics=SupportDynamics.UNAVAILABLE,
            progression=SupportProgression.NONE,
            distance_pct=None,
            distance_atr=None,
            distance_delta_atr=None,
            bars_since_support=None,
            bars_above_support=0,
            bars_below_support=0,
            reclaim_count=0,
            intrabar_below_support=False,
            close_below_support=False,
            close_below_floor=False,
            events=(),
        )

    def analyze(
        self,
        daily: pd.DataFrame,
        *,
        as_of: Any | None = None,
    ) -> StabilSupportLifecycleSnapshot:
        observations = build_daily_support_observations(
            daily,
            config=self.config,
            as_of=as_of,
        )
        self._snapshot = build_support_lifecycle(
            observations,
            min_tick=self.config.min_tick,
        )
        return self._snapshot

    def snapshot(self) -> StabilSupportLifecycleSnapshot:
        return self._snapshot

    def export(self) -> StabilSupportLifecycleSnapshot:
        return self._snapshot
