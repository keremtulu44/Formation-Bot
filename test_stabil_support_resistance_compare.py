"""Verify support-side symmetry and legacy-like pathway measurement."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from research.stabil_resistance_replay import Forward, Line, replay_4h
from research.stabil_support_resistance_compare import (
    REFLECTION,
    check_reflection_against_native,
    checkpoint_race_24,
    full_window_status,
    legacy_daily_touch_sequence,
    native_support_as_reflected_line,
    reflect_prices,
    verify_direct_event_selection,
)


def daily_fixture(n: int = 150) -> pd.DataFrame:
    x = np.arange(n, dtype=float)
    close = 60 + 6*np.sin(.32*x) + 3*np.sin(.071*x) + .03*x
    opening = close - .2*np.cos(x)
    return pd.DataFrame({"timestamp": pd.date_range("2025-01-01 18:30", periods=n, freq="D", tz="Europe/Istanbul"),
                         "open": opening, "high": np.maximum(opening, close)+1+.01*x,
                         "low": np.minimum(opening, close)-1-.005*x,
                         "close": close, "volume": np.full(n, 1000.)})


def test_reflection_round_trip_and_support_is_real_native() -> None:
    daily = daily_fixture()
    reflected = reflect_prices(daily)
    twice = reflect_prices(reflected)
    for col in ("open", "high", "low", "close"):
        np.testing.assert_allclose(daily[col], twice[col], rtol=0, atol=1e-10)
    line, obs, timeline, _ = native_support_as_reflected_line(daily)
    check_reflection_against_native(daily, line, timeline)
    assert sum(item.support_level is not None for item in obs) > 20
    for i, item in enumerate(obs):
        if item.support_level is not None:
            assert REFLECTION-line.level[i] == pytest.approx(item.support_level, abs=1e-9)
            assert REFLECTION-line.ceiling[i] == pytest.approx(item.support_floor, abs=1e-9)
            assert item.support_confirmed_index == item.support_origin_index + 4
            assert timeline[i].support_level == item.support_level


def test_reflected_native_support_is_prefix_causal() -> None:
    full = daily_fixture()
    full_line, _, _, _ = native_support_as_reflected_line(full)
    for stop in (60, 90, 120):
        prefix, _, _, _ = native_support_as_reflected_line(full.iloc[:stop].reset_index(drop=True))
        changed = full.copy()
        changed.loc[stop:, ["open", "high", "low", "close"]] *= 1.7
        future_changed, _, _, _ = native_support_as_reflected_line(changed)
        np.testing.assert_allclose(prefix.level, full_line.level[:stop], equal_nan=True)
        np.testing.assert_allclose(future_changed.level[:stop], full_line.level[:stop], equal_nan=True)


def test_reflection_fails_closed_on_out_of_range_price() -> None:
    frame = daily_fixture(20)
    frame.loc[0, "high"] = REFLECTION
    with pytest.raises(ValueError):
        reflect_prices(frame)
    frame.loc[0, "low"] = 0
    with pytest.raises(ValueError):
        reflect_prices(frame)


def test_replay_touch_and_break_agree_with_direct_support_conditions() -> None:
    n = 50
    times = pd.date_range("2026-02-01", periods=n, freq="4h", tz="Europe/Istanbul")
    original = pd.DataFrame({"timestamp": times, "open": 10.5, "high": 10.7, "low": 10.3,
                             "close": 10.5, "volume": 100.})
    original.loc[22, ["open", "high", "low", "close"]] = [10.5, 10.6, 9.8, 10.2]
    original.loc[25, ["open", "high", "low", "close"]] = [10.5, 10.6, 9.5, 9.8]
    original.loc[26, ["open", "high", "low", "close"]] = [9.8, 10.3, 9.7, 10.2]
    daily = pd.DataFrame({"timestamp": [times[0]-pd.Timedelta(days=1)]})
    line = Line(*[np.array([x], dtype=float) for x in (REFLECTION-10, REFLECTION-9.65, 0, 0, 0, 0)],
                [(0, 0, REFLECTION-10)])
    timeline = (SimpleNamespace(validity="ACTIVE"),)
    regimes = (SimpleNamespace(regime=SimpleNamespace(value="HORIZONTAL_BASE")),)
    reflected = reflect_prices(original)
    rows, _ = replay_4h("SYNTH", reflected, daily, times-pd.Timedelta(hours=4), {"MIRROR_P4": line},
                        timeline, regimes, np.zeros(n, bool), np.zeros(n, bool))
    checks = verify_direct_event_selection(original, daily, times-pd.Timedelta(hours=4),
                                           (SimpleNamespace(support_level=10.0),), rows)
    assert checks["BREAK_UP"] >= 1 and checks["RETURN_DOWN"] >= 1
    assert any(r["bar_index"] == 25 and r["event"] == "BREAK_UP" for r in rows)
    assert any(r["bar_index"] == 26 and r["event"] == "RETURN_DOWN" for r in rows)


def test_old_daily_touch_ordinal_tracks_only_known_episodes_and_separation() -> None:
    def obs(identity, low, high, close):
        return SimpleNamespace(support_identity=identity, support_level=10., low=low, high=high, close=close, atr=1.)
    def snap(below=False):
        return SimpleNamespace(close_below_support=below)
    records = (obs((1,), 9.9, 10.2, 10.0),  # first historical episode unknown
               obs((2,), 9.9, 10.2, 10.0),  # known new episode, first test
               obs((2,), 9.9, 10.2, 10.0),  # still active, not a second
               obs((2,), 10.4, 10.6, 10.4),  # separates >=0.35 ATR
               obs((2,), 9.9, 10.2, 10.0))  # second test
    sequence, known = legacy_daily_touch_sequence(records, tuple(snap() for _ in records))
    assert sequence.tolist() == [-1, 1, 1, 1, 2]
    assert known.tolist() == [False, True, True, True, True]


def test_24_bar_race_censors_and_preserves_same_bar_ambiguity() -> None:
    times = pd.date_range("2026-02-01", periods=60, freq="4h", tz="Europe/Istanbul")
    frame = pd.DataFrame({"timestamp": times, "open": 101., "high": 101.2, "low": 100.5, "close": 101.})
    bad, gaps, atr = np.zeros(60, bool), np.zeros(60, bool), np.ones(60)
    levels = np.full(60, 100.)
    frame.loc[21, "low"] = 100.0
    levels[21:] = 101.0
    fwd = Forward(frame, atr, bad, gaps)
    assert checkpoint_race_24(20, fwd, levels) == ("VALID", "AMBIGUOUS_SAME_BAR")
    levels[:] = 100.0
    assert checkpoint_race_24(20, fwd, levels) == ("VALID", "PRICE_RETURN_FIRST")
    gaps[25] = True
    fwd = Forward(frame, atr, bad, gaps)
    assert checkpoint_race_24(20, fwd, levels) == ("BAD_FUTURE_OR_MISSING", None)
    assert full_window_status(fwd, 55, 24) == "RIGHT_CENSORED"


def test_matching_uses_reaction_direction_not_the_original_resistance_label() -> None:
    from research.stabil_support_resistance_report import matched_side_comparison
    base = {"symbol": "TEST", "quarter": "2026Q1", "session_close": "13:30", "event": "TEST",
            "period": "Y2026", "gap_to_line_atr": .25, "prior_4bar_move_atr": .5,
            "status_8": "VALID", "reaction_return_atr_8": .2, "event_close_time": "2026-02-01"}
    events = pd.DataFrame([
        {**base, "side": "SUPPORT", "bar_index": 10, "first_1atr_8": "REACTION_FIRST"},
        {**base, "side": "RESISTANCE", "bar_index": 20, "first_1atr_8": "BREACH_SIDE_FIRST"},
        {**base, "side": "SUPPORT", "bar_index": 100, "first_1atr_8": "REACTION_FIRST"},
        {**base, "side": "RESISTANCE", "bar_index": 110, "first_1atr_8": "BREACH_SIDE_FIRST"},
    ])
    pairs, result = matched_side_comparison(events)
    assert result["valid_pairs"] == 2
    assert result["support_reaction_first"] == 2
    assert result["resistance_reaction_first"] == 0
    assert result["difference_pp"] == 100.0
    assert (pairs.support_first_8 == "REACTION_FIRST").all()
    assert (pairs.resistance_first_8 == "BREACH_SIDE_FIRST").all()


def test_describe_keeps_ambiguous_and_neither_in_the_denominator() -> None:
    from research.stabil_support_resistance_report import describe
    frame = pd.DataFrame({"symbol": ["A", "A", "B", "B", "C"],
                          "status_8": ["VALID"]*4+["RIGHT_CENSORED"],
                          "right_censored_8": [False]*4+[True],
                          "first_1atr_8": ["REACTION_FIRST", "BREACH_SIDE_FIRST", "AMBIGUOUS_SAME_BAR", "NEITHER", None],
                          "reaction_return_atr_8": [1., -1., 0., .1, np.nan]})
    result = describe(frame)
    assert result["events"] == 5 and result["valid"] == 4 and result["right_censored_any"] == 1
    assert result["reaction_first_pct"] == 25.0 and result["breach_side_first_pct"] == 25.0
    assert result["ambiguous_pct"] == 25.0 and result["neither_pct"] == 25.0
