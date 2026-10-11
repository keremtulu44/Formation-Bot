from __future__ import annotations

from dataclasses import replace

import pandas as pd
import pytest

from zone_scoring import (
    MtfOverlap,
    ZoneMetrics,
    _ZoneBuilder,
    _mtf_overlaps,
    _normalize_completed_frame,
    _ordered_bounds,
    _proximity_ranks,
    _reaction_samples,
    analyze_symbol_completed_frames,
    analyze_universe_completed_frames,
    wilder_atr,
)


ISTANBUL = "Europe/Istanbul"


def _frame(rows: list[tuple[float, float, float, float]], start: str = "2026-01-05 10:30") -> pd.DataFrame:
    timestamps = pd.date_range(start, periods=len(rows), freq="1h", tz=ISTANBUL)
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [row[0] for row in rows],
            "high": [row[1] for row in rows],
            "low": [row[2] for row in rows],
            "close": [row[3] for row in rows],
            "volume": [1000.0] * len(rows),
        }
    )


def _zone(
    zone_id: str,
    timeframe: str,
    lower: float,
    upper: float,
    distance: float,
    *,
    atr: float = 2.0,
) -> ZoneMetrics:
    return ZoneMetrics(
        zone_id=zone_id,
        symbol="TEST",
        zone_type="OB",
        timeframe=timeframe,
        direction="bullish",
        lower=lower,
        upper=upper,
        original_lower=lower,
        original_upper=upper,
        formation_time=None,
        available_at=None,
        native_status="ACTIVE_OB",
        native_active=True,
        invalidated=False,
        terminal_at=None,
        terminal_reason=None,
        current_price=100.0,
        atr=atr,
        distance_atr=distance,
        touch_count=0,
        reaction_sample_count=0,
        censored_touch_count=0,
        median_favorable_excursion_atr=None,
        median_adverse_excursion_atr=None,
        max_favorable_excursion_atr=None,
        reaction_samples=(),
        sample_status="NO_COMPLETED_REACTION_SAMPLES",
    )


def test_wilder_atr_is_seeded_by_first_fourteen_true_ranges() -> None:
    frame = _frame([(100.0, 102.0, 100.0, 101.0)] * 16)
    atr = wilder_atr(frame)
    assert atr[:13] == (None,) * 13
    assert atr[13] == 2.0
    assert atr[14:] == (2.0, 2.0)


def test_reactions_use_only_post_touch_bars_and_cap_the_window() -> None:
    rows = [
        (100.0, 100.5, 99.5, 100.0),  # zone exists from this bar; not a touch sample
        (100.0, 100.8, 99.6, 100.1),  # touch episode starts
        (100.1, 100.7, 99.4, 100.0),  # same episode, one touch
        (101.2, 102.0, 101.1, 101.8),
        (102.0, 103.0, 101.8, 102.7),
        (102.0, 102.5, 101.5, 102.0),
        (102.0, 102.4, 101.8, 102.1),  # beyond 3-bar horizon
    ]
    frame = _frame(rows)
    frame = _normalize_completed_frame(
        frame,
        as_of=frame["timestamp"].iloc[-1],
        symbol="TEST",
        timeframe="1h",
    )
    builder = _ZoneBuilder(
        zone_id="TEST|OB|1h|bullish|0|99|101",
        symbol="TEST",
        zone_type="OB",
        timeframe="1h",
        direction="bullish",
        original_lower=99.0,
        original_upper=101.0,
        formation_time=frame["timestamp"].iloc[0],
        available_index=0,
        native_status="ACTIVE_OB",
    )

    samples, touches, censored = _reaction_samples(
        frame,
        (1.0,) * len(frame),
        builder,
        horizon=3,
    )
    assert touches == 1
    assert censored == 0
    assert len(samples) == 1
    assert samples[0].bars_observed == 3
    assert samples[0].favorable_excursion_atr == 2.0
    assert samples[0].touch_start == frame["timestamp"].iloc[1]
    assert samples[0].touch_end == frame["timestamp"].iloc[2]


def test_repeat_touch_episodes_are_separate_samples_on_one_zone() -> None:
    rows = [
        (102.0, 102.5, 101.5, 102.0),  # zone is available; no touch
        (100.0, 100.5, 99.5, 100.0),   # first touch episode
        (102.0, 103.0, 101.5, 102.5),  # first post-touch response bar
        (100.0, 100.5, 99.5, 100.0),   # separated repeat touch
        (102.0, 103.5, 101.5, 103.0),  # second post-touch window
        (103.0, 104.0, 102.5, 103.5),
    ]
    frame = _frame(rows)
    builder = _ZoneBuilder(
        zone_id="TEST|OB|1h|bullish|0|99|101",
        symbol="TEST",
        zone_type="OB",
        timeframe="1h",
        direction="bullish",
        original_lower=99.0,
        original_upper=101.0,
        formation_time=frame["timestamp"].iloc[0],
        available_index=0,
        native_status="ACTIVE_OB",
    )

    samples, touches, censored = _reaction_samples(
        frame,
        (1.0,) * len(frame),
        builder,
        horizon=2,
    )

    assert touches == 2  # two episodes, still one zone
    assert len(samples) == 2
    assert censored == 0
    assert [sample.window_end_reason for sample in samples] == ["next_touch", "horizon"]
    assert [sample.favorable_excursion_atr for sample in samples] == [2.0, 3.0]


def test_touch_without_full_post_touch_horizon_is_censored_not_a_failure() -> None:
    frame = _frame([
        (102.0, 102.5, 101.5, 102.0),
        (100.0, 100.5, 99.5, 100.0),  # touch
        (102.0, 103.0, 101.5, 102.5),
        (102.5, 103.5, 102.0, 103.0),  # only two of three horizon bars exist
    ])
    builder = _ZoneBuilder(
        zone_id="TEST|OB|1h|bullish|0|99|101",
        symbol="TEST",
        zone_type="OB",
        timeframe="1h",
        direction="bullish",
        original_lower=99.0,
        original_upper=101.0,
        formation_time=frame["timestamp"].iloc[0],
        available_index=0,
        native_status="ACTIVE_OB",
    )

    samples, touches, censored = _reaction_samples(
        frame,
        (1.0,) * len(frame),
        builder,
        horizon=3,
    )

    assert touches == 1
    assert samples == ()
    assert censored == 1


def test_as_of_clips_future_bars_before_any_engine_replay() -> None:
    rows = [(100.0, 110.0, 90.0, 100.0 + index * 0.1) for index in range(18)]
    rows[-1] = (500.0, 700.0, 400.0, 650.0)  # must not affect price or history
    frame = _frame(rows)
    cutoff = frame["timestamp"].iloc[14]

    analysis = analyze_symbol_completed_frames(
        "TEST",
        {"1h": frame},
        as_of=cutoff,
    )

    assert analysis.as_of == cutoff
    assert analysis.current_price == rows[14][3]
    assert analysis.readiness[0].completed_bar_count == 15
    assert analysis.readiness[0].fvg_status == "UNSUPPORTED_TIMEFRAME"
    assert analysis.zones == ()


def test_universe_requires_one_shared_as_of_cutoff() -> None:
    frame = _frame([(100.0, 101.0, 99.0, 100.0)] * 15)
    with pytest.raises(ValueError, match="common as_of timestamp"):
        analyze_universe_completed_frames({"TEST": {"1h": frame}})


def test_explicit_incomplete_bars_are_rejected() -> None:
    frame = _frame([(100.0, 101.0, 99.0, 100.0)] * 15)
    frame["is_complete"] = True
    frame.loc[frame.index[-1], "is_complete"] = False
    with pytest.raises(ValueError, match="non-completed is_complete bar"):
        analyze_symbol_completed_frames("TEST", {"1h": frame})


def test_native_fvg_warmup_is_reported_without_inventing_zones() -> None:
    flat = _frame([(100.0, 101.0, 99.0, 100.0)] * 110)
    analysis = analyze_symbol_completed_frames("TEST", {"2h": flat})
    readiness = analysis.readiness[0]
    assert readiness.timeframe == "2h"
    assert readiness.completed_bar_count == 110
    assert readiness.fvg_status == "OK"
    assert readiness.fvg_zone_count == 0
    assert all(zone.probability is None for zone in analysis.zones)


def test_order_block_active_bounds_are_normalized_low_to_high() -> None:
    # The native export helper returns (active_top, active_bottom), including for
    # bullish zones; the measurement API consistently exposes (lower, upper).
    assert _ordered_bounds(105.0, 100.0) == (100.0, 105.0)
    assert _ordered_bounds(110.0, 105.0) == (105.0, 110.0)


def test_mtf_overlap_is_iou_and_atr_normalized_not_a_weighted_score() -> None:
    left = _zone("left", "2h", 100.0, 110.0, 0.0, atr=2.0)
    right = _zone("right", "4h", 105.0, 115.0, 0.0, atr=8.0)

    overlaps = _mtf_overlaps((left, right))
    assert len(overlaps) == 1
    pair = overlaps[0]
    assert pair.intersection_over_union == 1.0 / 3.0
    assert pair.interval_gap == 0.0
    assert pair.normalized_gap_atr == 0.0
    assert pair.normalized_center_distance_atr == 1.25
    assert pair.same_price_region is True
    assert isinstance(pair, MtfOverlap)


def test_empirical_proximity_rank_is_relative_and_probability_stays_unestimated() -> None:
    far = _zone("far", "2h", 120.0, 125.0, 5.0)
    middle = _zone("middle", "2h", 105.0, 110.0, 2.0)
    close = _zone("close", "2h", 99.0, 101.0, 0.0)

    ranked = _proximity_ranks((far, middle, close))
    by_id = {zone.zone_id: zone for zone in ranked}
    assert by_id["close"].proximity_rank_percentile > by_id["middle"].proximity_rank_percentile
    assert by_id["middle"].proximity_rank_percentile > by_id["far"].proximity_rank_percentile
    assert all(zone.proximity_rank_n == 3 for zone in ranked)
    assert all(zone.probability is None for zone in ranked)
    assert all(zone.probability_status == "NOT_CALIBRATED" for zone in ranked)


def test_inactive_zones_do_not_get_current_proximity_rank() -> None:
    active = _zone("active", "2h", 99.0, 101.0, 0.0)
    inactive = replace(_zone("inactive", "2h", 120.0, 125.0, 5.0), native_active=False)
    ranked = _proximity_ranks((active, inactive))
    assert ranked[0].proximity_rank_n == 1
    assert ranked[0].proximity_rank_percentile is None
    assert ranked[1].proximity_rank_n == 0
    assert ranked[1].proximity_rank_percentile is None
