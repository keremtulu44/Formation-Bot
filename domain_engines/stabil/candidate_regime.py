"""Provisional candidate mapping for vertical-step vs horizontal-hold regimes.

GOVERNANCE RULE:
- Charts draw the native daily `support_level` stepline directly. Their signal
  layer uses stepping states only as a conservative vertical-warning proxy,
  not as a user-confirmed visual classification or native support calculation.
- `support[t] == support[t-1]` / `SupportProgression.SAME` alone is NOT treated
  as user-approved horizontalization.
- This candidate mapping is derived strictly from `05_stabil.txt`'s native pivot
  confirmation geometry (`daily_pivot_len = 4`, native spacing `2 * daily_pivot_len = 8`,
  `pullback_lookback = 24`) with ZERO extra post-confirmation delay bars added
  on downward stabilization, and remains flagged `user_confirmed=False` until
  verified with the user on a real chart example.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Sequence

from .stabil_support_lifecycle import (
    StabilSupportLifecycleSnapshot,
    SupportProgression,
    SupportValidity,
)
from .stabil_trend_engine import StabilTrendConfig


class CandidateLineRegime(StrEnum):
    UNAVAILABLE = "UNAVAILABLE"
    STEPPING_UP = "STEPPING_UP"                # Rebased higher within native pivot spacing window (held above)
    STEPPING_DOWN = "STEPPING_DOWN"            # Downward rebase bar or active breach under downward step
    BREACHED_FIXED_SUPPORT = "BREACHED_FIXED_SUPPORT"  # Support broken downward while support level remains fixed (reclaim watch)
    NEWLY_FLATTENED_AFTER_RISE = "NEWLY_FLATTENED_AFTER_RISE"  # First horizontal extension past pivot-spacing window after rise
    LONG_HORIZONTAL = "LONG_HORIZONTAL"        # Extended horizontal hold (>= pullback_lookback daily bars)
    HORIZONTAL_AFTER_DROP = "HORIZONTAL_AFTER_DROP"  # Stabilized horizontal step after downward rebase (no extra bar delay)
    HORIZONTAL_BASE = "HORIZONTAL_BASE"        # Initial/same-level horizontal support


@dataclass(frozen=True, slots=True)
class CandidateRegimePoint:
    daily_index: int
    as_of: object
    support_level: float | None
    validity: SupportValidity
    progression: SupportProgression
    bars_since_support: int | None
    prior_step_interval_bars: int | None
    consecutive_higher_rebases: int
    consecutive_lower_rebases: int
    regime: CandidateLineRegime
    provisional: bool = True


def classify_candidate_support_regimes(
    timeline: Sequence[StabilSupportLifecycleSnapshot],
    *,
    config: StabilTrendConfig | None = None,
    user_confirmed: bool = False,
) -> tuple[CandidateRegimePoint, ...]:
    """Derive provisional vertical-step vs horizontal-hold labels from native support snapshots."""
    cfg = config or StabilTrendConfig()
    spacing_window = cfg.daily_pivot_len * 2          # 8 daily bars in native config
    long_horizontal_bars = cfg.pullback_lookback      # 24 daily bars in native config

    out: list[CandidateRegimePoint] = []
    prev_rebase_index: int | None = None
    last_step_interval: int | None = None
    higher_streak = 0
    lower_streak = 0
    active_origin_progression = SupportProgression.NONE

    for idx, snap in enumerate(timeline):
        if snap.support_level is None or snap.validity is SupportValidity.NO_SUPPORT:
            prev_rebase_index = None
            last_step_interval = None
            higher_streak = 0
            lower_streak = 0
            active_origin_progression = SupportProgression.NONE
            out.append(
                CandidateRegimePoint(
                    daily_index=idx,
                    as_of=snap.as_of,
                    support_level=None,
                    validity=snap.validity,
                    progression=snap.progression,
                    bars_since_support=None,
                    prior_step_interval_bars=None,
                    consecutive_higher_rebases=0,
                    consecutive_lower_rebases=0,
                    regime=CandidateLineRegime.UNAVAILABLE,
                    provisional=not user_confirmed,
                )
            )
            continue

        rebased_today = snap.bars_since_support == 0
        if rebased_today:
            if prev_rebase_index is not None:
                last_step_interval = idx - prev_rebase_index
            prev_rebase_index = idx
            active_origin_progression = snap.progression
            if snap.progression is SupportProgression.REBASED_HIGHER:
                higher_streak += 1
                lower_streak = 0
            elif snap.progression is SupportProgression.REBASED_LOWER:
                lower_streak += 1
                higher_streak = 0
            else:
                higher_streak = 0
                lower_streak = 0

        age = int(snap.bars_since_support or 0)

        if active_origin_progression is SupportProgression.REBASED_HIGHER:
            if snap.close_below_support:
                regime = CandidateLineRegime.BREACHED_FIXED_SUPPORT
            elif age <= spacing_window:
                regime = CandidateLineRegime.STEPPING_UP
            elif age < long_horizontal_bars:
                regime = CandidateLineRegime.NEWLY_FLATTENED_AFTER_RISE
            else:
                regime = CandidateLineRegime.LONG_HORIZONTAL
        elif active_origin_progression is SupportProgression.REBASED_LOWER:
            # No artificial 2/3/5-bar confirmation delay: on the rebase bar itself
            # (age == 0) or while price already closes below the new downward step,
            # the step is still descending; once held on the next closed bar (age >= 1
            # and close >= support), native 4-bar pivot confirmation already holds.
            if age == 0 or snap.close_below_support:
                regime = CandidateLineRegime.STEPPING_DOWN
            elif age >= long_horizontal_bars:
                regime = CandidateLineRegime.LONG_HORIZONTAL
            else:
                regime = CandidateLineRegime.HORIZONTAL_AFTER_DROP
        else:
            if snap.close_below_support:
                regime = CandidateLineRegime.BREACHED_FIXED_SUPPORT
            elif age >= long_horizontal_bars:
                regime = CandidateLineRegime.LONG_HORIZONTAL
            else:
                regime = CandidateLineRegime.HORIZONTAL_BASE

        out.append(
            CandidateRegimePoint(
                daily_index=idx,
                as_of=snap.as_of,
                support_level=snap.support_level,
                validity=snap.validity,
                progression=active_origin_progression,
                bars_since_support=age,
                prior_step_interval_bars=last_step_interval,
                consecutive_higher_rebases=higher_streak,
                consecutive_lower_rebases=lower_streak,
                regime=regime,
                provisional=not user_confirmed,
            )
        )
    return tuple(out)
