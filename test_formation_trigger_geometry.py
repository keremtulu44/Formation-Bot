"""Trigger location is the existing engine line at this bar, not a new filter."""
from types import SimpleNamespace

import pandas as pd
import pytest

from bot.lifecycle_events import _closed_formation_event_confirmed
from bot.security import _alert_break_level
from patterns import ArgentEngine
from patterns.mathutil import candidate_boundary_at_bar
from research.alarm_recall_study import closed_archive
from research.formation_trigger_audit import snapshots, summarize
from tutarlilik import seviye


def candidate(**kwargs):
    return SimpleNamespace(hb1=0, hp1=105., hb2=10, hp2=100.,
                           lb1=0, lp1=90., lb2=10, lp2=95.,
                           frozen_upper_boundary_at_break=100.,
                           frozen_lower_boundary_at_break=95., **kwargs)


@pytest.mark.parametrize("direction,price,expected", [(1, 99., 98.), (-1, 96., 97.)])
@pytest.mark.parametrize("state", ["KIRILIM_TEYITLI", "RETEST_BASARILI"])
def test_held_sloping_boundary_not_vetoed_by_historical_price(direction, price, expected, state):
    active = candidate()
    level = _alert_break_level(active, direction, state, bar_index=14)
    assert level == expected
    assert seviye(active, direction, state, bar_index=14) == level
    assert _closed_formation_event_confirmed(state, direction, price, level)
    legacy = _alert_break_level(active, direction, state)
    assert not _closed_formation_event_confirmed(state, direction, price, legacy)


@pytest.mark.parametrize("direction,price", [(1, 97.9), (-1, 97.1)])
def test_inside_close_still_rejected(direction, price):
    level = _alert_break_level(candidate(), direction, "KIRILIM_TEYITLI", bar_index=14)
    assert not _closed_formation_event_confirmed("KIRILIM_TEYITLI", direction, price, level)


def test_rising_upper_boundary_cannot_use_old_lower_price_to_pass():
    active = candidate()
    active.hp1, active.hp2 = 95., 100.
    level = _alert_break_level(active, 1, "KIRILIM_TEYITLI", bar_index=14)
    assert level == 102.
    assert not _closed_formation_event_confirmed("KIRILIM_TEYITLI", 1, 101., level)


@pytest.mark.parametrize("direction,expected", [(1, 100.), (-1, 95.)])
def test_invalidation_keeps_historical_reference(direction, expected):
    assert _alert_break_level(candidate(), direction, "KIRILIM_GECERSIZLESTI", bar_index=14) == expected
    assert seviye(candidate(), direction, "KIRILIM_GECERSIZLESTI", bar_index=14) == expected


@pytest.mark.parametrize("attribute,value", [("hb1", None), ("hp1", float("nan")),
    ("hp2", float("inf")), ("hb2", 0), ("hb2", 50), ("hb2", 10.5)])
def test_invalid_geometry_does_not_invent_a_line(attribute, value):
    active = candidate()
    setattr(active, attribute, value)
    assert candidate_boundary_at_bar(active, 1, 14) is None
    assert _alert_break_level(active, 1, "KIRILIM_TEYITLI", bar_index=14) == 100.


def test_real_native_retest_is_eligible_at_onset_in_two_window_sizes():
    frame = closed_archive("AKBNK", "2h", 0)
    frame = frame.loc[frame.index <= pd.Timestamp("2026-10-21T14:00Z")]
    for bars in (360, 480):
        prefix = frame.tail(bars)
        engine = ArgentEngine(timeframe="2h")
        snap = engine.process(prefix, tam_yeniden=True)
        assert snap.state == "RETEST_BASARILI"
        assert snap.effective_quality > 78
        price = float(prefix.close.iloc[-1])
        assert price == pytest.approx(67.2)
        old = _alert_break_level(snap.active, snap.break_dir, snap.state)
        current = _alert_break_level(snap.active, snap.break_dir, snap.state, bar_index=snap.bar_index)
        assert old == pytest.approx(67.2272727273)
        assert current == pytest.approx(66.875)
        assert current == pytest.approx(snap.active.upper_now)
        assert not _closed_formation_event_confirmed(snap.state, snap.break_dir, price, old)
        assert _closed_formation_event_confirmed(snap.state, snap.break_dir, price, current)


@pytest.mark.parametrize("tf", ["1h", "2h", "4h", "1d"])
def test_trigger_audit_is_prefix_stable_and_future_independent(tf):
    frame = closed_archive("AKBNK", tf, 180)
    expected = snapshots("AKBNK", tf, frame.iloc[:135])
    full = snapshots("AKBNK", tf, frame)
    assert [r for r in full if r["bar_index"] < 135] == expected
    changed = frame.copy()
    changed.iloc[135:, :4] *= 1.1
    assert [r for r in snapshots("AKBNK", tf, changed) if r["bar_index"] < 135] == expected


def test_episode_analysis_does_not_count_three_bars_as_three_signals():
    base = {"symbol": "TEST", "timeframe": "2h", "formation": "TEST|1", "state": "RETEST_BASARILI",
        "state_start": 10, "candidate_age_bars": 5, "distance_from_line_atr": .4,
        "bar_time": "2026-10-21T14:00Z", "quality_pass": True,
        "legacy_fixed_close_pass": False, "projected_close_pass": True,
        "eligible_before_delivery": False, "eligible_after_alignment": True}
    rows = [{**base, "bar_index": 10+i, "state_age_bars": i} for i in range(3)]
    rows[-1]["eligible_before_delivery"] = True
    rows[-1]["legacy_fixed_close_pass"] = True
    result = summarize(rows, "2026-10-19", "2026-11-18")
    assert result["state_onsets"]["episodes"] == 1
    assert result["alignment_effect"]["earlier_state_episodes"] == 1
    assert result["alignment_effect"]["earlier_examples"][0]["bars_earlier"] == 2
    assert result["alignment_effect"]["rescued_state_episodes"]["episodes"] == 0
