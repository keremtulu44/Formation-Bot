"""Causality, literal native inversion and ambiguity tests for research replay."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from domain_engines.stabil import build_daily_support_observations
from research.stabil_resistance_replay import (
    Forward,
    Line,
    build_models,
    classify_contact,
    crossing_cause,
    first_hit,
    intraday_completeness,
    native_mirror,
    pivot_lines,
    project_daily_at_bar_open,
    replay_4h,
    reverse_ohlc,
)


def daily_fixture(n: int = 150) -> pd.DataFrame:
    i = np.arange(n, dtype=float)
    close = 60 + np.sin(i * .32) * 6 + np.sin(i * .071) * 3 + .03 * i
    opens = close - .2 * np.cos(i)
    return pd.DataFrame({"timestamp": pd.date_range("2025-01-01 18:30", periods=n, freq="D", tz="Europe/Istanbul"),
                         "open": opens, "high": np.maximum(opens, close) + 1 + .01*i,
                         "low": np.minimum(opens, close) - 1 - .005*i,
                         "close": close, "volume": np.full(n, 1000.0)})


def test_mirror_is_the_unmodified_native_support_and_independent_pivot_high() -> None:
    daily = daily_fixture()
    line, obs, timeline, _ = native_mirror(daily)
    independently_computed = pivot_lines(daily, 4)["latest"]
    assert np.isfinite(line.level).sum() > 20
    np.testing.assert_allclose(line.level, independently_computed.level, equal_nan=True)
    np.testing.assert_allclose(line.ceiling, independently_computed.ceiling, equal_nan=True)
    direct = build_daily_support_observations(reverse_ohlc(daily))
    for i, item in enumerate(direct):
        assert item == obs[i]
        if item.support_level is not None:
            assert line.level[i] == pytest.approx(float(daily.iloc[item.support_origin_index]["high"]))
            assert line.ceiling[i] == pytest.approx(-item.support_floor)
            assert item.support_confirmed_index == item.support_origin_index + 4
            assert item.support_available_at >= item.support_confirmed_at
            assert timeline[i].support_level == item.support_level


def test_prefix_and_future_mutation_cannot_change_prior_mirror_or_alternatives() -> None:
    frame = daily_fixture()
    full, *_ = build_models(frame)
    for stop in (55, 80, 110, 135):
        partial, *_ = build_models(frame.iloc[:stop].copy().reset_index(drop=True))
        changed = frame.copy()
        changed.loc[stop:, ["open", "high", "low", "close"]] *= 2
        modified, *_ = build_models(changed)
        for model in full:
            np.testing.assert_allclose(partial[model].level, full[model].level[:stop], equal_nan=True)
            np.testing.assert_allclose(modified[model].level[:stop], full[model].level[:stop], equal_nan=True)
            np.testing.assert_allclose(partial[model].ceiling, full[model].ceiling[:stop], equal_nan=True)


def test_daily_level_only_projected_if_known_at_h4_open() -> None:
    daily = pd.DatetimeIndex(["2026-01-05 18:30+03:00", "2026-01-06 18:30+03:00"])
    starts = pd.DatetimeIndex(["2026-01-05 13:30+03:00", "2026-01-05 18:30+03:00",
                               "2026-01-06 09:30+03:00", "2026-01-06 18:29+03:00"])
    assert project_daily_at_bar_open(daily, starts).tolist() == [-1, 0, 0, 0]


def test_first_hit_same_bar_is_not_given_an_invented_order() -> None:
    assert first_hit(np.array([11.2]), np.array([8.8]), 10, 1) == "AMBIGUOUS_SAME_BAR"
    assert first_hit(np.array([10.5, 11.1]), np.array([9.5, 9.7]), 10, 1) == "UP_FIRST"
    assert first_hit(np.array([10.5, 10.7]), np.array([9.1, 8.9]), 10, 1) == "DOWN_FIRST"
    assert first_hit(np.array([10.5]), np.array([9.5]), 10, 1) == "NEITHER"


@pytest.mark.parametrize("args,expected", [
    ((99, 101, 100, 100), ("UP", "PRICE_ONLY")),
    ((99, 99.5, 100, 98), ("UP", "LINE_ONLY")),
    ((98.5, 99.5, 100, 99), ("UP", "BOTH_REQUIRED")),
    ((99.5, 100.5, 100, 99), ("UP", "EITHER_SUFFICIENT")),
    ((101, 99, 100, 100), ("DOWN", "PRICE_ONLY")),
    ((101, 100.5, 100, 102), ("DOWN", "LINE_ONLY")),
])
def test_level_and_price_crossing_attribution(args, expected) -> None:
    assert crossing_cause(*args) == expected


def test_forward_censors_end_split_and_missing_and_starts_after_entry() -> None:
    times = pd.date_range("2025-12-28", periods=48, freq="4h", tz="Europe/Istanbul")
    frame = pd.DataFrame({"timestamp": times, "open": 10., "high": 10.2, "low": 9.8, "close": 10.})
    atr = np.ones(len(frame))
    bad = np.zeros(len(frame), dtype=bool)
    gaps = np.zeros(len(frame), dtype=bool)
    fwd = Forward(frame, atr, bad, gaps)
    assert fwd.at(22)["status_4"] == "CROSS_SPLIT"
    assert fwd.at(47)["status_4"] == "RIGHT_CENSORED"
    assert fwd.at(26)["status_4"] == "VALID"
    assert fwd.at(26)["first_1atr_4"] == "NEITHER"
    gaps[29] = True
    assert Forward(frame, atr, bad, gaps).at(26)["status_4"] == "BAD_FUTURE_OR_MISSING"
    bad[25] = True
    assert Forward(frame, atr, bad, gaps).at(26)["status_4"] == "BAD_HISTORY_OR_MISSING"
    structural = np.zeros(len(frame), bool)
    structural[30:] = True
    clean = np.zeros(len(frame), bool)
    assert Forward(frame, atr, clean, clean, structural).at(26)["status_4"] == "BAD_DAILY_SOURCE_FUTURE"


def test_retest_does_not_call_gap_a_clean_hold() -> None:
    frame = pd.DataFrame({"timestamp": pd.date_range("2026-01-02", periods=35, freq="4h", tz="Europe/Istanbul"),
                          "open": 11., "high": 11.5, "low": 10.5, "close": 11.})
    frame.loc[21, ["open", "high", "low", "close"]] = [9.9, 11.3, 9.8, 11.]
    fwd = Forward(frame, np.ones(len(frame)), np.zeros(len(frame), bool), np.zeros(len(frame), bool))
    result = fwd.line_outcomes(20, 10, 10.35, "BREAK_UP")
    assert result["first_retest_8"] == "GAP_OR_OPEN_AT_BELOW_RECLAIM"
    frame.loc[21, ["open", "high", "low", "close"]] = [10.5, 11.3, 9.8, 11.]
    fwd = Forward(frame, np.ones(len(frame)), np.zeros(len(frame), bool), np.zeros(len(frame), bool))
    assert fwd.line_outcomes(20, 10, 10.35, "BREAK_UP")["first_retest_8"] == "TOUCH_CLOSE_ABOVE"


def test_hourly_constituent_gaps_and_whole_bucket_gaps_are_distinct() -> None:
    tz = "Europe/Istanbul"
    labels = pd.date_range("2026-06-01 09:30", periods=9, freq="h", tz=tz)
    hourly = pd.DataFrame({"close": 1.0}, index=labels.delete(2))
    h4 = pd.DataFrame({"close": 1.0}, index=pd.DatetimeIndex([labels[0], labels[8]]))
    daily = pd.DataFrame({"close": 1.0}, index=pd.DatetimeIndex([pd.Timestamp("2026-06-01", tz=tz)]))
    incomplete, gaps, counts = intraday_completeness(hourly, h4, daily, pd.Timestamp("2026-06-01 20:00", tz=tz))
    assert incomplete.tolist() == [True, False]
    assert gaps.tolist() == [False, True]
    assert counts == {"incomplete_h4_buckets": 1, "missing_whole_h4_buckets": 1}


def test_break_then_return_tracks_only_observed_same_identity_episode() -> None:
    n = 50
    times = pd.date_range("2026-02-01", periods=n, freq="4h", tz="Europe/Istanbul")
    frame = pd.DataFrame({"timestamp": times, "open": 9., "high": 9.2, "low": 8.8,
                          "close": 9., "volume": 100.})
    frame.loc[22, ["open", "high", "low", "close"]] = [9., 10.7, 8.9, 10.5]
    frame.loc[23, ["open", "high", "low", "close"]] = [10.5, 10.9, 10.2, 10.6]
    frame.loc[24, ["open", "high", "low", "close"]] = [10.6, 10.7, 9.6, 9.8]
    daily = pd.DataFrame({"timestamp": [times[0] - pd.Timedelta(days=1)]})
    line = Line(*[np.array([x], dtype=float) for x in (10., 10.35, 0., 0., 0., 0.)], [(0, 0, 10.)])
    regime = (SimpleNamespace(regime=SimpleNamespace(value="HORIZONTAL_BASE")),)
    timeline = (SimpleNamespace(validity="ACTIVE"),)
    rows, _ = replay_4h("SYNTH", frame, daily, times-pd.Timedelta(hours=4), {"MIRROR_P4": line},
                        timeline, regime, np.zeros(n, bool), np.zeros(n, bool))
    ret = [r for r in rows if r["event"] == "RETURN_DOWN" and r["bar_index"] == 24][0]
    assert ret["episode_known"] is True
    assert ret["above_bars_before_return"] == 2
    assert ret["above_max_depth_atr"] > 0
    assert ret["break_bar_index"] == 22
    # If the entry is missing, the earlier episode is not invented.
    gaps = np.zeros(n, bool)
    gaps[23] = True
    rows, _ = replay_4h("SYNTH", frame, daily, times-pd.Timedelta(hours=4), {"MIRROR_P4": line},
                        timeline, regime, np.zeros(n, bool), gaps)
    ret = [r for r in rows if r["event"] == "RETURN_DOWN" and r["bar_index"] == 24][0]
    assert ret["episode_known"] is False
    assert ret["above_bars_before_return"] is None


def test_matching_does_not_use_future_censoring_to_choose_a_better_control() -> None:
    from research.stabil_resistance_report import matched_pairs, matched_summary

    def row(model, idx, status, outcome):
        return {"event": "TEST", "period": "Y2026", "model": model, "symbol": "ONE",
                "quarter": "2026Q1", "session_close": "13:30", "bar_index": idx,
                "event_close_time": f"2026-01-{idx:02d}", "gap_to_line_atr": .3,
                "prior_4bar_move_atr": .2, "status_8": status,
                "first_1atr_8": outcome, "return_atr_8": .1}
    rows = [row("MIRROR_P4", 10, "VALID", "DOWN_FIRST"),
            row("SHIFT_UP", 18, "RIGHT_CENSORED", None),
            row("SHIFT_UP", 20, "VALID", "UP_FIRST")]
    pairs = matched_pairs(pd.DataFrame(rows), "SHIFT_UP")
    assert len(pairs) == 1
    assert pairs.iloc[0].control_bar == 18  # nearest match, despite future censoring
    assert matched_summary(pairs)["valid_pairs"] == 0


def test_departure_race_uses_frozen_prior_line_and_future_closes() -> None:
    n = 45
    times = pd.date_range("2026-02-01", periods=n, freq="4h", tz="Europe/Istanbul")
    frame = pd.DataFrame({"timestamp": times, "open": 9.8, "high": 9.9, "low": 9.7,
                          "close": 9.8, "volume": 100.})
    frame.loc[22, ["open", "high", "low", "close"]] = [9.8, 9.9, 8.0, 8.2]
    frame.loc[23, ["open", "high", "low", "close"]] = [8.2, 9.5, 8.1, 9.2]
    frame.loc[24, ["open", "high", "low", "close"]] = [9.2, 10.2, 9.1, 10.1]
    daily = pd.DataFrame({"timestamp": [times[0] - pd.Timedelta(days=1)]})
    line = Line(*[np.array([x], dtype=float) for x in (10., 10.35, 0., 0., 0., 0.)], [(0, 0, 10.)])
    regime = (SimpleNamespace(regime=SimpleNamespace(value="HORIZONTAL_BASE")),)
    timeline = (SimpleNamespace(validity="ACTIVE"),)
    rows, _ = replay_4h("SYNTH", frame, daily, times-pd.Timedelta(hours=4), {"MIRROR_P4": line},
                        timeline, regime, np.zeros(n, bool), np.zeros(n, bool))
    depart = [r for r in rows if r["event"] == "DEPART_BELOW" and r["bar_index"] == 22][0]
    assert depart["status_4"] == "VALID"
    assert depart["first_follow_or_return_4"] == "PRICE_RETURNS_FIRST"


def test_gap_above_is_not_falsely_counted_as_a_line_touch() -> None:
    assert classify_contact(10.5, 10.1, 10.3, 10.0) == "GAP_ABOVE_NO_TOUCH"
    assert classify_contact(10.5, 9.9, 10.3, 10.0) == "TOUCH_CLOSE_ABOVE"
    assert classify_contact(10.5, 9.9, 9.95, 10.0) == "WICK_TOUCH_CLOSE_AT_OR_BELOW"
    assert classify_contact(9.9, 9.6, 9.8, 10.0) == "NEAR_ONLY"
