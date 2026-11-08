"""Causal resistance mirror: native pivots, colors, arrows and fail-closed data."""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from domain_engines.stabil.runtime import (
    StabilRoleStatus,
    SupportBarPoint,
    prepare_causal_ohlcv,
    project_support_to_bar_closes,
)
from domain_engines.stabil.signals import evaluate_bar_behaviors
from domain_engines.stabil.stabil_support_lifecycle import (
    DailySupportObservation,
    StabilSupportLifecycleSnapshot,
    SupportDynamics,
    SupportProgression,
    SupportValidity,
    build_daily_support_observations,
    build_support_lifecycle_timeline,
)
from domain_engines.stabil.resistance import (
    ResistanceArrowKind,
    ResistanceBarPoint,
    ResistanceDynamics,
    ResistanceEventType,
    ResistanceProgression,
    ResistanceRegime,
    ResistanceValidity,
    StabilResistanceHistory,
    _snapshot,
    build_daily_resistance_history,
    evaluate_resistance_bar_behaviors,
    evaluate_stabil_resistance,
    project_resistance_to_bar_closes,
)

TZ = "Europe/Istanbul"
MAP_EVENT = {
    None: None,
    "close_reclaim": "close_return_below",
    "intrabar_sweep_reclaim": "intrabar_sweep_rejection",
    "weak_reclaim": "weak_return",
    "long_base_breakout": "long_ceiling_breakdown",
    "upward_rebase_momentum": "downward_rebase_momentum",
    "touch_from_below": "approach_from_above",
}
MAP_PROGRESS = {
    SupportProgression.NONE: ResistanceProgression.NONE,
    SupportProgression.INITIAL: ResistanceProgression.INITIAL,
    SupportProgression.SAME: ResistanceProgression.SAME,
    SupportProgression.REBASED_HIGHER: ResistanceProgression.REBASED_LOWER,
    SupportProgression.REBASED_LOWER: ResistanceProgression.REBASED_HIGHER,
}
MAP_VALIDITY = {
    SupportValidity.NO_SUPPORT: ResistanceValidity.NO_RESISTANCE,
    SupportValidity.ACTIVE: ResistanceValidity.ACTIVE,
    SupportValidity.BREACHED: ResistanceValidity.BREACHED,
    SupportValidity.BELOW_FLOOR: ResistanceValidity.ABOVE_CEILING,
}
MAP_DYNAMICS = {
    SupportDynamics.UNAVAILABLE: ResistanceDynamics.UNAVAILABLE,
    SupportDynamics.AT_SUPPORT: ResistanceDynamics.AT_RESISTANCE,
    SupportDynamics.EXPANDING: ResistanceDynamics.EXPANDING,
    SupportDynamics.CONTRACTING: ResistanceDynamics.CONTRACTING,
    SupportDynamics.FLAT: ResistanceDynamics.FLAT,
    SupportDynamics.BELOW_SUPPORT: ResistanceDynamics.ABOVE_RESISTANCE,
}


def daily_frame(n=200, seed=3):
    rng = np.random.default_rng(seed)
    x = np.arange(n)
    center = 100.0 + 6.0 * np.sin(x * .22) + 2.2 * np.sin(x * .065) + rng.normal(0, .45, n)
    op = center + rng.normal(0, .5, n)
    close = center + rng.normal(0, .5, n)
    high = np.maximum(op, close) + rng.uniform(.3, 1.8, n)
    low = np.minimum(op, close) - rng.uniform(.3, 1.8, n)
    times = pd.date_range("2025-01-01 18:00", periods=n, freq="D", tz=TZ)
    return pd.DataFrame({"open": op, "high": high, "low": low, "close": close,
                         "volume": rng.uniform(50, 250, n), "close_time": times}, index=times)


def reflect_positive(frame, offset=200.0):
    """Test-only positive translation; actual resistance never uses this offset."""
    result = frame.copy()
    result["open"] = offset - frame["open"]
    result["high"] = offset - frame["low"]
    result["low"] = offset - frame["high"]
    result["close"] = offset - frame["close"]
    return result


def clean(frame, tf="1d"):
    data, err = prepare_causal_ohlcv(frame, symbol="ASTOR", timeframe=tf, certified_closes=True)
    assert err is None
    return data


def snapshot(time, level=100.0, age=0, progression=SupportProgression.SAME, below=False):
    return StabilSupportLifecycleSnapshot(
        as_of=time, support_level=level, support_floor=level - 5.0,
        support_origin_at=time, support_confirmed_at=time, support_available_at=time,
        validity=SupportValidity.ACTIVE, dynamics=SupportDynamics.FLAT, progression=progression,
        distance_pct=None, distance_atr=None, distance_delta_atr=None, bars_since_support=age,
        bars_above_support=0 if below else age, bars_below_support=age if below else 0,
        reclaim_count=0, intrabar_below_support=False, close_below_support=below,
        close_below_floor=False, events=(),
    )


def setup_reference(rows, *, levels=None, progressions=None, below=None, ages=None, symbol="ASTOR"):
    n = len(rows)
    times = pd.date_range("2026-01-01 18:00", periods=n, freq="D", tz=TZ)
    levels = levels if levels is not None else [100.0] * n
    progressions = progressions if progressions is not None else [SupportProgression.SAME] * n
    below = below if below is not None else [False] * n
    ages = ages if ages is not None else list(range(n))
    snaps = tuple(snapshot(times[i], levels[i], ages[i], progressions[i], below[i]) for i in range(n))
    points = tuple(SupportBarPoint(i, times[i], times[i], levels[i], SupportValidity.ACTIVE,
                                   SupportDynamics.FLAT, progressions[i], "above") for i in range(n))
    frame = pd.DataFrame(rows)
    frame["timestamp"] = times
    normal = evaluate_bar_behaviors(symbol, "1d", frame, points, snaps)
    offset = 200.0
    real_frame = reflect_positive(frame, offset)
    mirrored_snaps = tuple(replace(s, support_level=s.support_level - offset,
                                   support_floor=s.support_floor - offset) for s in snaps)
    history = StabilResistanceHistory((), tuple(_snapshot(s) for s in mirrored_snaps), mirrored_snaps)
    res_points = tuple(ResistanceBarPoint(
        p.bar_index, p.bar_close_time, p.daily_as_of, offset - p.support_level,
        MAP_VALIDITY[p.validity], MAP_DYNAMICS[p.dynamics], MAP_PROGRESS[p.progression], "red",
    ) for p in points)
    opposite = evaluate_resistance_bar_behaviors(symbol, "1d", real_frame, res_points, history)
    return frame, points, snaps, normal, real_frame, res_points, history, opposite


def assert_behaviors_mirror(support, resistance):
    assert len(support) == len(resistance)
    for s, r in zip(support, resistance):
        assert r.bar_index == s.bar_index and r.bar_close_time == s.bar_close_time
        assert r.fixed_resistance == s.fixed_support
        assert r.touch_count == s.touch_count
        assert r.prev_breach_bars == s.prev_breach_bars
        assert r.prev_breach_depth_atr == pytest.approx(s.prev_breach_depth_atr, abs=1e-10)
        assert r.return_kind == MAP_EVENT[s.reclaim_kind]
        assert r.weak_return == s.weak_reclaim
        assert r.momentum_kind == MAP_EVENT[s.momentum_kind]
        assert r.vertical_resistance == s.vertical_support
        assert r.vertical_attempt_kind == MAP_EVENT[s.vertical_attempt_kind]
        assert r.rank_score == pytest.approx(s.rank_score, abs=1e-4)
        assert r.unchanged_days == s.unchanged_days
        for a, b in ((r.dist_atr, s.dist_atr), (r.high_dist_atr, s.low_dist_atr), (r.body_atr, s.body_atr)):
            assert (a is None and b is None) or a == pytest.approx(-b, abs=1e-10)
        assert r.close_pos == pytest.approx(1 - s.close_pos, abs=1e-10)
        assert (r.vol_ratio is None and s.vol_ratio is None) or r.vol_ratio == pytest.approx(s.vol_ratio)
        if r.resistance_level is not None:
            assert r.pct_vs_resistance == pytest.approx((r.close_price - r.resistance_level) / r.resistance_level * 100)


def quiet(n=29):
    return [{"open": 100.4, "high": 101.1, "low": 99.6, "close": 100.6, "volume": 100.0}
            for _ in range(n)]


@pytest.mark.parametrize("seed", [1, 3, 9, 44])
def test_native_daily_pivots_lifecycle_and_arrows_match_mirror(seed):
    real = daily_frame(seed=seed)
    output = evaluate_stabil_resistance("ASTOR", "1d", real, certified_closes=True, include_prefix_events=True)
    assert output.status == StabilRoleStatus.READY
    support_clean = clean(reflect_positive(real))
    support_obs = build_daily_support_observations(support_clean)
    support_timeline = build_support_lifecycle_timeline(support_obs, include_prefix_events=True)
    support_points = project_support_to_bar_closes(list(support_clean.timestamp), support_timeline)
    support_behaviors = evaluate_bar_behaviors("ASTOR", "1d", support_clean, support_points, support_timeline)
    assert len(output.observations) == len(support_obs) == len(real)
    assert any(o.resistance_level is not None for o in output.observations)
    for ro, so, rs, ss, rp, sp in zip(output.observations, support_obs, output.timeline, support_timeline,
                                      output.bar_projection, support_points):
        assert ro.high == pytest.approx(200 - so.low)
        assert ro.low == pytest.approx(200 - so.high)
        assert ro.close == pytest.approx(200 - so.close)
        assert ro.resistance_origin_at == so.support_origin_at
        assert ro.resistance_confirmed_at == so.support_confirmed_at
        assert ro.resistance_available_at == so.support_available_at
        assert ro.resistance_origin_index == so.support_origin_index
        assert ro.resistance_confirmed_index == so.support_confirmed_index
        if so.support_level is None:
            assert ro.resistance_level is None and rp.color_role is None
        else:
            assert ro.resistance_level == pytest.approx(200 - so.support_level)
            assert ro.resistance_level > 0
            assert ro.resistance_ceiling == pytest.approx(200 - so.support_floor)
            assert ro.resistance_origin_at <= ro.resistance_confirmed_at <= ro.resistance_available_at <= ro.timestamp
            assert rp.resistance_level == pytest.approx(ro.resistance_level)
            assert rp.color_role == ("red" if sp.color_role == "above" else "green")
        assert rs.validity == MAP_VALIDITY[ss.validity]
        assert rs.dynamics == MAP_DYNAMICS[ss.dynamics]
        assert rs.progression == MAP_PROGRESS[ss.progression]
        assert rs.bars_below_resistance == ss.bars_above_support
        assert rs.bars_above_resistance == ss.bars_below_support
        assert rs.return_count == ss.reclaim_count
        assert len(rs.events) == len(ss.events)
        for re, se in zip(rs.events, ss.events):
            assert re.available_at == se.available_at and re.price == pytest.approx(200 - se.price)
            assert re.event_type.value == se.event_type.value.replace("SUPPORT", "RESISTANCE").replace("FLOOR_BROKEN", "CEILING_BROKEN").replace("RECLAIMED", "RETURNED_BELOW").replace("REBASED_HIGHER", "SWAP").replace("REBASED_LOWER", "REBASED_HIGHER").replace("SWAP", "REBASED_LOWER")
    assert_behaviors_mirror(support_behaviors, output.bar_behaviors)


def test_native_level_is_confirmed_high_without_arbitrary_extra_wait():
    frame = daily_frame()
    out = evaluate_stabil_resistance("ASTOR", "1d", frame, certified_closes=True)
    first_index = next(i for i, obs in enumerate(out.observations) if obs.resistance_level is not None)
    obs = out.observations[first_index]
    assert obs.resistance_level == pytest.approx(frame.high.iloc[obs.resistance_origin_index])
    assert obs.resistance_confirmed_index == obs.resistance_origin_index + 4
    assert obs.resistance_available_at == obs.timestamp
    assert all(p.resistance_level is None for p in out.bar_projection[:first_index])
    assert out.bar_projection[first_index].resistance_level == pytest.approx(obs.resistance_level)


def test_4h_projection_waits_for_daily_close_not_origin_or_future():
    daily = daily_frame(100)
    daily_out = evaluate_stabil_resistance("ASTOR", "1d", daily, certified_closes=True)
    first = next(o for o in daily_out.observations if o.resistance_level is not None)
    t = first.resistance_available_at
    times = pd.DatetimeIndex([t - pd.Timedelta(hours=4), t, t + pd.Timedelta(hours=4)])
    target = pd.DataFrame({"open": [98., 98., 98.], "high": [100., 100., 100.],
                           "low": [97., 97., 97.], "close": [99., 99., 99.],
                           "volume": [100., 100., 100.], "close_time": times}, index=times)
    out = evaluate_stabil_resistance("ASTOR", "4h", target, daily_frame=daily, certified_closes=True)
    assert out.status == StabilRoleStatus.READY
    assert out.bar_projection[0].resistance_level is None
    assert out.bar_projection[1].resistance_level == pytest.approx(first.resistance_level)
    assert out.bar_projection[1].daily_as_of == t
    assert out.bar_projection[2].daily_as_of == t
    assert all(p.daily_as_of is None or p.daily_as_of <= p.bar_close_time for p in out.bar_projection)


def test_prefix_and_future_mutations_do_not_change_line_event_or_arrows():
    full = daily_frame(150)
    complete = evaluate_stabil_resistance("ASTOR", "1d", full, certified_closes=True, include_prefix_events=True)
    for end in (45, 75, 110):
        cutoff = full.close_time.iloc[end - 1]
        prefix = evaluate_stabil_resistance("ASTOR", "1d", full, as_of_close=cutoff,
                                            certified_closes=True, include_prefix_events=True)
        modified = full.copy()
        modified.iloc[end:, modified.columns.get_loc("close")] = np.nan
        future_changed = evaluate_stabil_resistance("ASTOR", "1d", modified, as_of_close=cutoff,
                                                    certified_closes=True, include_prefix_events=True)
        assert prefix.observations == complete.observations[:end]
        assert prefix.timeline == complete.timeline[:end]
        assert prefix.bar_projection == complete.bar_projection[:end]
        assert prefix.bar_behaviors == complete.bar_behaviors[:end]
        assert future_changed == prefix


def test_validity_colors_and_equality_are_exact_native_inverse():
    times = pd.date_range("2026-01-01 18:00", periods=4, freq="D", tz=TZ)
    closes = [100., 101., 103., 100.]
    observations = tuple(DailySupportObservation(
        timestamp=t, high=-min(c, 99.), low=-max(c, 104.), close=-c, atr=4.,
        support_level=-100., support_floor=-102., support_origin_at=times[0],
        support_confirmed_at=times[0], support_available_at=times[0],
        support_origin_index=0, support_confirmed_index=0,
    ) for t, c in zip(times, closes))
    native = build_support_lifecycle_timeline(observations, include_prefix_events=True)
    history = StabilResistanceHistory((), tuple(_snapshot(s) for s in native), native)
    points = project_resistance_to_bar_closes(times, history)
    assert [p.validity for p in points] == [ResistanceValidity.ACTIVE, ResistanceValidity.BREACHED,
                                           ResistanceValidity.ABOVE_CEILING, ResistanceValidity.ACTIVE]
    assert [p.color_role for p in points] == ["red", "green", "green", "red"]
    assert history.timeline[0].distance_pct == 0
    assert history.timeline[1].distance_pct == pytest.approx(1)
    assert history.timeline[1].distance_atr == pytest.approx(.25)
    assert history.timeline[2].close_above_ceiling
    assert history.timeline[3].return_count == 1  # equality is safe side
    assert history.timeline[-1].events[-1].event_type == ResistanceEventType.RESISTANCE_TESTED
    assert any(e.event_type == ResistanceEventType.RESISTANCE_RETURNED_BELOW
               for e in history.timeline[-1].events)


def test_downward_return_and_intrabar_sweep_are_distinct():
    rows = quiet(28) + [
        {"open": 100.1, "high": 100.2, "low": 99.4, "close": 99.7, "volume": 100.0},
        {"open": 99.7, "high": 101.0, "low": 99.6, "close": 100.8, "volume": 250.0},
        {"open": 100.2, "high": 101.0, "low": 99.8, "close": 100.8, "volume": 250.0},
    ]
    *_, support, real, points, history, resistance = setup_reference(rows)
    assert_behaviors_mirror(support, resistance)
    assert resistance[-2].return_kind == "close_return_below"
    assert resistance[-1].return_kind == "intrabar_sweep_rejection"
    assert resistance[-1].arrow_kind == ResistanceArrowKind.STRONG_RETURN_DOWN
    assert resistance[-2].prev_breach_bars == 1
    assert real.high.iloc[-1] > points[-1].resistance_level  # real sweep, not just gap


def test_weak_return_not_promoted_and_gap_is_not_invented_as_touch():
    breach = {"open": 100.1, "high": 100.2, "low": 99.4, "close": 99.7, "volume": 100.0}
    weak = {"open": 99.7, "high": 100.08, "low": 99.6, "close": 100.02, "volume": 100.0}
    *_, support, real, points, _history, resistance = setup_reference(quiet(28) + [breach, weak])
    assert_behaviors_mirror(support, resistance)
    assert resistance[-1].weak_return and resistance[-1].arrow_kind is None
    gap = {"open": 100.2, "high": 101.3, "low": 100.1, "close": 101.2, "volume": 250.0}
    *_, support, real, points, _history, resistance = setup_reference(quiet(28) + [breach, gap])
    assert_behaviors_mirror(support, resistance)
    assert real.high.iloc[-1] < points[-1].resistance_level
    assert resistance[-1].return_kind == "close_return_below"  # native close return, not a touch claim


def test_repeated_down_momentum_has_exact_three_bar_repeat_cooldown():
    strong = {"open": 100.8, "high": 101.7, "low": 100.7, "close": 101.6, "volume": 250.0}
    *_, support, _real, _points, _history, resistance = setup_reference(quiet() + [strong] * 8)
    assert_behaviors_mirror(support, resistance)
    arrows = [i for i, b in enumerate(resistance) if b.arrow_kind == ResistanceArrowKind.STRONG_MOMENTUM_DOWN]
    assert arrows == [29, 32, 35]
    assert all(resistance[i].momentum_kind == "long_ceiling_breakdown" for i in arrows)


def test_vertical_resistance_suppresses_down_signal_and_marks_up_warning():
    rows = quiet(29) + [{"open": 101.4, "high": 102.3, "low": 101.3, "close": 102.2, "volume": 250.0}]
    levels = [100.] * 29 + [101.]
    progression = [SupportProgression.SAME] * 29 + [SupportProgression.REBASED_HIGHER]
    ages = list(range(29)) + [0]
    *_, support, _real, _points, _history, resistance = setup_reference(
        rows, levels=levels, progressions=progression, ages=ages,
    )
    assert_behaviors_mirror(support, resistance)
    last = resistance[-1]
    assert last.regime == ResistanceRegime.STEPPING_DOWN
    assert last.vertical_resistance and not last.fixed_resistance
    assert last.vertical_attempt_kind == "downward_rebase_momentum"
    assert last.arrow_kind == ResistanceArrowKind.VERTICAL_ATTEMPT_WARNING_UP
    assert last.return_kind is None and last.momentum_kind is None


@pytest.mark.parametrize("touch_only", [False, True])
def test_rising_vertical_proxy_return_and_touch_are_upward_warnings(touch_only):
    rows = quiet(28) + [
        {"open": 95.1, "high": 95.2, "low": 94.4, "close": 94.7, "volume": 100.0},
        ({"open": 94.7, "high": 95.05, "low": 94.2, "close": 94.4, "volume": 100.0} if touch_only else
         {"open": 94.7, "high": 96.0, "low": 94.6, "close": 95.8, "volume": 250.0}),
    ]
    levels = [100.] * 28 + [95., 95.]
    progression = [SupportProgression.SAME] * 28 + [SupportProgression.REBASED_LOWER, SupportProgression.SAME]
    below = [False] * 28 + [True, True]
    ages = list(range(28)) + [0, 1]
    *_, support, _real, _points, _history, resistance = setup_reference(
        rows, levels=levels, progressions=progression, below=below, ages=ages,
    )
    assert_behaviors_mirror(support, resistance)
    last = resistance[-1]
    assert last.regime == ResistanceRegime.STEPPING_UP and last.vertical_resistance
    assert last.vertical_attempt_kind == ("approach_from_above" if touch_only else "close_return_below")
    assert last.arrow_kind == ResistanceArrowKind.VERTICAL_ATTEMPT_WARNING_UP
    assert last.return_kind is None and last.momentum_kind is None


def test_fixed_line_tolerance_uses_actual_resistance_not_research_offset():
    rows = quiet(3)
    _, _points, _snaps, _support, real, points, history, _ = setup_reference(rows)
    # Price=10 is deliberately tiny relative to the old research translation.
    real.loc[:, ["open", "high", "low", "close"]] /= 10.0
    levels = [10., 10.03, 10.030001]
    points = tuple(replace(p, resistance_level=level) for p, level in zip(points, levels))
    result = evaluate_resistance_bar_behaviors("ASTOR", "1d", real, points, history)
    assert not result[1].fixed_resistance and result[1].vertical_resistance
    assert result[2].fixed_resistance
    assert result[-1].pct_vs_resistance == pytest.approx((real.close.iloc[-1] - levels[-1]) / levels[-1] * 100)


def test_incomplete_bars_future_cutoff_and_unavailable_inputs():
    raw = daily_frame(100)
    raw["is_closed"] = True
    raw["is_complete"] = True
    raw.iloc[-1, raw.columns.get_loc("is_closed")] = False
    raw.iloc[-2, raw.columns.get_loc("is_complete")] = False
    raw.iloc[-1, raw.columns.get_loc("close")] = np.nan
    out = evaluate_stabil_resistance("ASTOR", "1d", raw, certified_closes=True)
    assert out.status == StabilRoleStatus.READY
    assert out.as_of_close == raw.close_time.iloc[-3]
    assert len(out.bar_projection) == 98
    assert out.bar_behaviors[-1].bar_close_time == raw.close_time.iloc[-3]
    assert evaluate_stabil_resistance("ASTOR", "4h", raw, certified_closes=True).status == StabilRoleStatus.UNAVAILABLE
    assert evaluate_stabil_resistance("ASTOR", "1d", None).status == StabilRoleStatus.UNAVAILABLE
    assert evaluate_stabil_resistance("ASTOR", "weekly", raw, certified_closes=True).status == StabilRoleStatus.DATA_ERROR


@pytest.mark.parametrize("column,bad", [("high", np.nan), ("close", np.inf), ("low", 0.),
                                        ("open", -1.), ("volume", -1.)])
def test_malformed_eligible_bar_fails_closed(column, bad):
    raw = daily_frame(100)
    raw.iloc[60, raw.columns.get_loc(column)] = bad
    out = evaluate_stabil_resistance("ASTOR", "1d", raw, certified_closes=True)
    assert out.status == StabilRoleStatus.DATA_ERROR
    assert not out.timeline and not out.bar_projection and not out.bar_behaviors


def test_bad_daily_high_low_and_bad_cutoff_fail_closed():
    raw = daily_frame(100)
    raw.iloc[60, raw.columns.get_loc("high")] = raw.close.iloc[60] - 1
    assert evaluate_stabil_resistance("ASTOR", "1d", raw, certified_closes=True).status == StabilRoleStatus.DATA_ERROR
    for cutoff in ("not-a-date", pd.NaT):
        result = evaluate_stabil_resistance("ASTOR", "1d", daily_frame(100), as_of_close=cutoff, certified_closes=True)
        assert result.status == StabilRoleStatus.DATA_ERROR and result.reason == "invalid_as_of_close"


def test_unclosed_invalid_bar_is_not_allowed_to_leak_or_mutate_input():
    raw = daily_frame(100)
    raw["is_closed"] = True
    raw.iloc[-1, raw.columns.get_loc("is_closed")] = False
    raw.iloc[-1, raw.columns.get_loc("high")] = np.nan
    original = raw.copy(deep=True)
    result = evaluate_stabil_resistance("ASTOR", "1d", raw, certified_closes=True)
    pd.testing.assert_frame_equal(raw, original)
    assert result.status == StabilRoleStatus.READY
    assert result.as_of_close == raw.close_time.iloc[-2]


def test_mismatched_projection_is_rejected_instead_of_misaligned():
    _, _, _, _, real, points, history, _ = setup_reference(quiet(4))
    with pytest.raises(ValueError, match="length mismatch"):
        evaluate_resistance_bar_behaviors("ASTOR", "1d", real, points[:-1], history)
    bad = (replace(points[0], bar_close_time=points[1].bar_close_time), *points[1:])
    with pytest.raises(ValueError, match="timestamp mismatch"):
        evaluate_resistance_bar_behaviors("ASTOR", "1d", real, bad, history)


@pytest.mark.parametrize("flag", ["is_closed", "is_complete"])
def test_known_internal_incomplete_bar_is_not_bridged_and_future_gap_is_ignored(flag):
    raw = daily_frame(100)
    raw[flag] = True
    raw.iloc[70, raw.columns.get_loc(flag)] = False
    full = evaluate_stabil_resistance("ASTOR", "1d", raw, certified_closes=True)
    assert full.status == StabilRoleStatus.DATA_ERROR
    assert full.reason == "internal_incomplete_bar"
    assert not full.bar_projection and not full.bar_behaviors
    cutoff = raw.close_time.iloc[65]
    prefix = evaluate_stabil_resistance("ASTOR", "1d", raw, as_of_close=cutoff, certified_closes=True)
    reference = evaluate_stabil_resistance("ASTOR", "1d", raw.iloc[:66], certified_closes=True)
    assert prefix == reference


def test_projection_rejects_a_future_daily_snapshot():
    _, _, _, _, real, points, history, _ = setup_reference(quiet(4))
    bad = (replace(points[0], daily_as_of=points[1].daily_as_of), *points[1:])
    with pytest.raises(ValueError, match="future daily snapshot"):
        evaluate_resistance_bar_behaviors("ASTOR", "1d", real, bad, history)


def test_vertical_tolerance_warning_does_not_claim_actual_touch_on_gap():
    rows = quiet(28) + [
        {"open": 95.1, "high": 95.2, "low": 94.4, "close": 94.7, "volume": 100.0},
        {"open": 95.004, "high": 95.0045, "low": 95.001, "close": 95.002, "volume": 100.0},
    ]
    levels = [100.] * 28 + [95., 95.]
    progression = [SupportProgression.SAME] * 28 + [SupportProgression.REBASED_LOWER, SupportProgression.SAME]
    below = [False] * 28 + [True, True]
    ages = list(range(28)) + [0, 1]
    *_, support, real, points, _history, resistance = setup_reference(
        rows, levels=levels, progressions=progression, below=below, ages=ages,
    )
    assert_behaviors_mirror(support, resistance)
    assert real.high.iloc[-1] < points[-1].resistance_level
    assert resistance[-1].vertical_attempt_kind == "approach_from_above"
    assert resistance[-1].arrow_kind == ResistanceArrowKind.VERTICAL_ATTEMPT_WARNING_UP


@pytest.mark.parametrize("symbol,cutoff,expected_line,expected_close", [
    ("EFOR", "2026-07-28 13:30", 19.53, 19.80),
    ("AKBNK", "2026-01-06 17:30", 73.65, 74.15),
])
def test_two_historical_path_examples_and_all_their_4h_arrows_mirror_support(
    symbol, cutoff, expected_line, expected_close,
):
    """Two previously identified anchors; a parity check, not a performance replay."""
    from research.arsiv import ham_frame, tf_frame

    cutoff = pd.Timestamp(cutoff, tz=TZ)
    daily, h4 = ham_frame(symbol, "1d"), tf_frame(symbol, "4h")
    actual = evaluate_stabil_resistance(symbol, "4h", h4, daily_frame=daily, as_of_close=cutoff)
    assert actual.status == StabilRoleStatus.READY
    last, behavior = actual.bar_projection[-1], actual.bar_behaviors[-1]
    assert last.bar_close_time == cutoff
    assert last.resistance_level == pytest.approx(expected_line, abs=.001)
    assert behavior.close_price == pytest.approx(expected_close, abs=.001)
    assert last.daily_as_of < last.bar_close_time

    mirrored_daily, err = prepare_causal_ohlcv(reflect_positive(daily), symbol=symbol,
                                               timeframe="1d", cutoff_close=cutoff)
    assert err is None
    mirrored_h4, err = prepare_causal_ohlcv(reflect_positive(h4), symbol=symbol,
                                            timeframe="4h", cutoff_close=cutoff)
    assert err is None
    observations = build_daily_support_observations(mirrored_daily)
    timeline = build_support_lifecycle_timeline(observations, include_prefix_events=False)
    projection = project_support_to_bar_closes(list(mirrored_h4.timestamp), timeline)
    support = evaluate_bar_behaviors(symbol, "4h", mirrored_h4, projection, timeline)
    assert_behaviors_mirror(support, actual.bar_behaviors)


def test_equality_does_not_fabricate_a_return_but_can_precede_a_real_sweep():
    breach = {"open": 100.1, "high": 100.2, "low": 99.4, "close": 99.7, "volume": 100.0}
    equality = {"open": 99.7, "high": 100.2, "low": 99.6, "close": 100., "volume": 250.0}
    sweep = {"open": 100.2, "high": 101.0, "low": 99.8, "close": 100.8, "volume": 250.0}
    *_, support, _real, _points, _history, resistance = setup_reference(quiet(28) + [breach, equality, sweep])
    assert_behaviors_mirror(support, resistance)
    assert resistance[-2].close_price == resistance[-2].resistance_level
    assert resistance[-2].return_kind is None and resistance[-2].arrow_kind is None
    assert resistance[-1].return_kind == "intrabar_sweep_rejection"


def test_string_completion_flag_fails_closed_instead_of_becoming_true():
    raw = daily_frame(100)
    raw["is_closed"] = [True] * 100
    raw["is_closed"] = raw["is_closed"].astype(object)
    raw.iloc[70, raw.columns.get_loc("is_closed")] = "False"
    out = evaluate_stabil_resistance("ASTOR", "1d", raw, certified_closes=True)
    assert out.status == StabilRoleStatus.DATA_ERROR and out.reason == "invalid_completion_flag"
    cutoff = raw.close_time.iloc[60]
    prefix = evaluate_stabil_resistance("ASTOR", "1d", raw, as_of_close=cutoff, certified_closes=True)
    reference = evaluate_stabil_resistance("ASTOR", "1d", raw.iloc[:61], certified_closes=True)
    assert prefix == reference and prefix.status != StabilRoleStatus.DATA_ERROR


def test_foreign_symbol_requires_certified_close_times():
    raw = daily_frame(100)
    assert evaluate_stabil_resistance("BRENT", "1d", raw).status == StabilRoleStatus.DATA_ERROR
    assert evaluate_stabil_resistance("BRENT", "1d", raw, certified_closes=True).status == StabilRoleStatus.READY


@pytest.mark.parametrize("bad", [pd.NaT, "not-a-close-time"])
def test_unknown_close_time_fails_closed_without_leaking_future(bad):
    raw = daily_frame(100)
    raw["close_time"] = raw["close_time"].astype(object)
    raw.iloc[70, raw.columns.get_loc("close_time")] = bad
    out = evaluate_stabil_resistance("ASTOR", "1d", raw, certified_closes=True)
    assert out.status == StabilRoleStatus.DATA_ERROR and out.reason == "invalid_timestamp"
    cutoff = raw.index[65]
    prefix = evaluate_stabil_resistance("ASTOR", "1d", raw, as_of_close=cutoff, certified_closes=True)
    reference = evaluate_stabil_resistance("ASTOR", "1d", raw.iloc[:66], certified_closes=True)
    assert prefix == reference


def test_unclosed_row_with_bad_timestamp_is_ignored():
    raw = daily_frame(100)
    raw["is_closed"] = True
    raw["close_time"] = raw["close_time"].astype(object)
    raw.iloc[-1, raw.columns.get_loc("is_closed")] = False
    raw.iloc[-1, raw.columns.get_loc("close_time")] = "bad"
    out = evaluate_stabil_resistance("ASTOR", "1d", raw, certified_closes=True)
    reference = evaluate_stabil_resistance("ASTOR", "1d", raw.iloc[:-1], certified_closes=True)
    assert out == reference


@pytest.mark.parametrize("change", [
    {"daily_pivot_len": 0}, {"daily_pivot_len": -1}, {"min_tick": 0},
    {"min_tick": float("nan")}, {"support_atr_tolerance": -0.1},
])
def test_bad_config_fails_closed(change):
    from domain_engines.stabil.stabil_trend_engine import StabilTrendConfig

    result = evaluate_stabil_resistance("ASTOR", "1d", daily_frame(100), certified_closes=True,
                                        config=replace(StabilTrendConfig(), **change))
    assert result.status == StabilRoleStatus.DATA_ERROR
    assert not result.bar_projection and not result.bar_behaviors


def test_daily_after_last_target_close_cannot_change_earlier_target_even_if_cutoff_is_later():
    daily = daily_frame(180)
    t = daily.close_time.iloc[150] - pd.Timedelta(hours=4)
    times = pd.DatetimeIndex([t - pd.Timedelta(hours=4), t])
    target = pd.DataFrame({"open": [98., 98.], "high": [100., 100.], "low": [97., 97.],
                           "close": [99., 99.], "volume": [100., 100.], "close_time": times}, index=times)
    cutoff = t + pd.Timedelta(hours=12)
    unchanged = evaluate_stabil_resistance("ASTOR", "4h", target, daily_frame=daily,
                                           as_of_close=cutoff, certified_closes=True)
    later_bad = daily.copy()
    later_bad.iloc[150, later_bad.columns.get_loc("close")] = np.nan
    changed = evaluate_stabil_resistance("ASTOR", "4h", target, daily_frame=later_bad,
                                         as_of_close=cutoff, certified_closes=True)
    assert changed == unchanged
    assert all(o.timestamp <= t for o in unchanged.observations)
    assert all(p.daily_as_of is None or p.daily_as_of <= p.bar_close_time for p in unchanged.bar_projection)


def test_large_real_resistance_uses_native_relative_tolerance():
    _, _, _, _, real, points, history, _ = setup_reference(quiet(3))
    real.loc[:, ["open", "high", "low", "close"]] *= 1000.0
    levels = [100_000., 100_000.05, 100_000.20]
    points = tuple(replace(p, resistance_level=level) for p, level in zip(points, levels))
    result = evaluate_resistance_bar_behaviors("ASTOR", "1d", real, points, history)
    assert result[1].fixed_resistance  # tolerance is 1e-6 * the real resistance
    assert not result[2].fixed_resistance and result[2].vertical_resistance


def test_missing_volume_keeps_native_strong_body_alternative():
    rows = quiet() + [{"open": 100.8, "high": 101.7, "low": 100.7, "close": 101.6, "volume": 0.0}]
    for row in rows:
        row["volume"] = 0.0
    *_, support, _real, _points, _history, resistance = setup_reference(rows)
    assert_behaviors_mirror(support, resistance)
    assert resistance[-1].vol_ratio is None
    assert resistance[-1].momentum_kind == "long_ceiling_breakdown"


def test_no_line_resets_state_and_cooldown_exactly_like_support():
    strong = {"open": 100.8, "high": 101.7, "low": 100.7, "close": 101.6, "volume": 250.0}
    frame, points, snapshots, _, real, res_points, history, _ = setup_reference(quiet() + [strong] * 4)
    missing = 30
    points = tuple(replace(p, support_level=None) if i == missing else p for i, p in enumerate(points))
    res_points = tuple(replace(p, resistance_level=None) if i == missing else p for i, p in enumerate(res_points))
    support = evaluate_bar_behaviors("ASTOR", "1d", frame, points, snapshots)
    resistance = evaluate_resistance_bar_behaviors("ASTOR", "1d", real, res_points, history)
    assert_behaviors_mirror(support, resistance)
    assert resistance[29].arrow_kind == ResistanceArrowKind.STRONG_MOMENTUM_DOWN
    assert resistance[30].arrow_kind is None and resistance[30].resistance_level is None
    assert resistance[31].arrow_kind == ResistanceArrowKind.STRONG_MOMENTUM_DOWN


@pytest.mark.parametrize("timeframe", ["1h", "2h", "4h", "1d"])
def test_supported_target_timeframes_project_only_known_daily_lines(timeframe):
    daily = daily_frame(200)
    if timeframe == "1d":
        target = daily.copy()
    else:
        last = daily.close_time.iloc[170] - pd.Timedelta(hours=1)
        times = pd.date_range(end=last, periods=30, freq=timeframe, tz=TZ)
        target = pd.DataFrame({"open": 98., "high": 100., "low": 97., "close": 99.,
                               "volume": 100., "close_time": times}, index=times)
    result = evaluate_stabil_resistance("ASTOR", timeframe, target, daily_frame=daily, certified_closes=True)
    assert result.status == StabilRoleStatus.READY
    assert len(result.bar_projection) == len(target)
    assert all(p.daily_as_of is None or p.daily_as_of <= p.bar_close_time for p in result.bar_projection)
    assert all(p.resistance_level is None or p.resistance_level > 0 for p in result.bar_projection)


def test_invalid_frame_type_is_data_error_not_an_exception():
    result = evaluate_stabil_resistance("ASTOR", "1d", "not-a-frame")
    assert result.status == StabilRoleStatus.DATA_ERROR and result.reason == "invalid_frame"


def test_insufficient_unique_pivots_remain_warmup_without_invented_level():
    raw = daily_frame(80)
    raw.loc[:, ["open", "high", "low", "close"]] = [100., 101., 99., 100.]
    result = evaluate_stabil_resistance("ASTOR", "1d", raw, certified_closes=True)
    assert result.status == StabilRoleStatus.WARMUP
    assert all(point.resistance_level is None and point.color_role is None for point in result.bar_projection)
    assert all(behavior.arrow_kind is None for behavior in result.bar_behaviors)


def test_deep_breach_does_not_become_strong_return():
    rows = quiet(28) + [
        {"open": 100., "high": 100.2, "low": 95.8, "close": 96., "volume": 100.},
        {"open": 96., "high": 101., "low": 95.9, "close": 100.8, "volume": 250.},
    ]
    *_, support, _real, _points, _history, resistance = setup_reference(rows)
    assert_behaviors_mirror(support, resistance)
    assert resistance[-1].prev_breach_depth_atr > 1.5
    assert resistance[-1].weak_return and resistance[-1].arrow_kind is None


def test_zero_volume_no_longer_blocks_return_on_index_or_stock():
    """2026-11-08: dolu ▼/▲ için hacim şartı kaldırıldı (kullanıcı kararı).

    Önceden bu test "endeks istisnası"nı koruyordu: hacim 0 iken endeks dönüş
    alıyor, hisse almıyordu. Hacim kapısı kalktığı için ikisi de aynı davranır;
    geriye yalnız mum anatomisi (gövde/kapanış konumu/mesafe) kalır.
    """
    rows = quiet(28) + [
        {"open": 100.1, "high": 100.2, "low": 99.4, "close": 99.7, "volume": 0.},
        {"open": 99.8, "high": 100.5, "low": 99.7, "close": 100.4, "volume": 0.},
    ]
    for row in rows:
        row["volume"] = 0.
    *_, support, _real, _points, _history, index = setup_reference(rows, symbol="XU100")
    assert_behaviors_mirror(support, index)
    assert index[-1].return_kind == "close_return_below"
    *_, stock_support, _real, _points, _history, stock = setup_reference(rows, symbol="ASTOR")
    assert_behaviors_mirror(stock_support, stock)
    assert stock[-1].return_kind == "close_return_below"
    assert stock[-1].weak_return is False


def test_unclosed_internal_row_with_bad_time_does_not_disappear_from_history():
    raw = daily_frame(100)
    raw["is_closed"] = True
    raw["close_time"] = raw["close_time"].astype(object)
    raw.iloc[70, raw.columns.get_loc("is_closed")] = False
    raw.iloc[70, raw.columns.get_loc("close_time")] = "bad"
    result = evaluate_stabil_resistance("ASTOR", "1d", raw, certified_closes=True)
    assert result.status == StabilRoleStatus.DATA_ERROR and result.reason == "internal_incomplete_bar"
    prefix = evaluate_stabil_resistance("ASTOR", "1d", raw, as_of_close=raw.index[65], certified_closes=True)
    reference = evaluate_stabil_resistance("ASTOR", "1d", raw.iloc[:66], certified_closes=True)
    assert prefix == reference
