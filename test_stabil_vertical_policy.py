"""Vertical Stabil up-attempt policy, including rendering and causal alignment."""
from dataclasses import replace
from types import SimpleNamespace

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
import pandas as pd

from data import mum_kapanis_anlari
from domain_engines.stabil import (
    StabilSupportLifecycleSnapshot, SupportBarPoint, SupportDynamics,
    SupportProgression, SupportValidity, evaluate_bar_behaviors,
    summarize_symbol_for_command,
)
from grafik.render import _stabil_ciz
from grafik.tarama import _stabil_verisi


def make_series(falling=True, extra=False):
    n = 31 if extra else 30
    labels = pd.date_range("2026-08-01", periods=n, freq="D", tz="Europe/Istanbul")
    times = list(mum_kapanis_anlari(labels, "1d"))
    levels, snapshots, points, rows = [], [], [], []
    for i, close_time in enumerate(times):
        level = 95.0 if falling and i >= 28 else 100.0
        prog = SupportProgression.REBASED_LOWER if falling and i == 28 else SupportProgression.SAME
        age = i - 28 if falling and i >= 28 else i
        below = falling and i >= 28
        snap = StabilSupportLifecycleSnapshot(
            as_of=close_time, support_level=level, support_floor=level - 5,
            support_origin_at=close_time, support_confirmed_at=close_time,
            support_available_at=close_time, validity=SupportValidity.ACTIVE,
            dynamics=SupportDynamics.FLAT, progression=prog, distance_pct=None,
            distance_atr=None, distance_delta_atr=None, bars_since_support=age,
            bars_above_support=0 if below else age, bars_below_support=age if below else 0,
            reclaim_count=0, intrabar_below_support=False,
            close_below_support=below, close_below_floor=False, events=(),
        )
        snapshots.append(snap)
        points.append(SupportBarPoint(i, close_time, close_time, level, SupportValidity.ACTIVE,
                                      SupportDynamics.FLAT, prog, "above"))
        levels.append(level)
        rows.append({"open": 100.4, "high": 101.1, "low": 99.6, "close": 100.6, "volume": 100.0})
    level = levels[28]
    rows[28] = {"open": level + .1, "high": level + .2, "low": level - .6,
                "close": level - .3, "volume": 100.0}
    rows[29] = {"open": level - .3, "high": level + 1.0, "low": level - .4,
                "close": level + .8, "volume": 250.0}
    return labels, snapshots, points, pd.DataFrame(rows)


def behaviors(falling=True, extra=False):
    labels, snapshots, points, frame = make_series(falling, extra)
    return labels, snapshots, points, frame, evaluate_bar_behaviors("ASTOR", "1d", frame, points, snapshots)


def test_falling_vertical_support_blocks_reclaim_and_marks_attempt():
    _, _, _, _, result = behaviors(falling=True)
    before, attempt = result[28:30]
    assert before.regime == "STEPPING_DOWN"
    assert attempt.vertical_support and attempt.fixed_support
    assert attempt.vertical_attempt_kind == "touch_from_below"
    assert attempt.reclaim_kind is None and attempt.momentum_kind is None
    summary = summarize_symbol_for_command("ASTOR", SimpleNamespace(bar_behaviors=result))
    assert summary.bucket == "zayif_dusus" and summary.reclaim_kind is None
    assert "dikey destek" in summary.headline_tr


def test_horizontal_support_still_allows_real_reclaim():
    _, _, _, _, result = behaviors(falling=False)
    attempt = result[29]
    assert not attempt.vertical_support
    assert attempt.reclaim_kind is None
    assert attempt.vertical_attempt_kind is None


def test_vertical_warning_is_not_dispatched_as_bullish_standalone_stabil(tmp_path, monkeypatch):
    import config
    import bot.stabil_service as service

    monkeypatch.setattr(config, "STABIL_GERI_ALIM_ALARM", True)
    monkeypatch.setattr(config, "STABIL_ALARM_PUBLIC", False)
    monkeypatch.setattr(service, "tamamlanmis_mumlar", lambda frame, *_a, **_k: frame)
    monkeypatch.setattr(service, "bar_kapandi_mi", lambda *_a, **_k: True)
    now = pd.Timestamp("2026-10-01 17:00", tz="Europe/Istanbul").to_pydatetime()
    monkeypatch.setattr(service, "mum_kapanis_ani", lambda *_a: now)
    _, _, _, frame, vertical = behaviors(falling=True)
    _, _, _, _, horizontal = behaviors(falling=False)
    frame = frame.copy()
    frame.index = pd.date_range("2026-09-01", periods=len(frame), freq="4h", tz="Europe/Istanbul")
    frames = {"4h": frame, "1d": frame}

    def evaluate(bhv):
        result = SimpleNamespace(error=None, result=SimpleNamespace(latest_behavior=bhv))
        return service.evaluate_stabil_4h_candidate(
            "ASTOR", frames, now, state_path=str(tmp_path / "stabil.json"),
            domain_results_by_stock={"ASTOR": {"4h": {"stabil": result}}},
        )

    assert vertical[-1].vertical_attempt_kind == "touch_from_below"
    assert evaluate(vertical[-1]) is None  # warning is not a green reclaim alert
    candidate = evaluate(horizontal[-1])
    assert candidate is None


def test_falling_vertical_lower_wick_attempt_also_gets_warning():
    _, snapshots, points, frame = make_series(falling=True)
    frame.loc[29, ["open", "high", "low", "close"]] = [94.7, 95.05, 94.2, 94.4]
    last = evaluate_bar_behaviors("ASTOR", "1d", frame, points, snapshots)[-1]
    assert last.vertical_support and last.vertical_attempt_kind == "touch_from_below"
    assert last.reclaim_kind is None and last.momentum_kind is None


def test_future_bar_does_not_change_prior_vertical_decision():
    _, _, _, _, first = behaviors(falling=True)
    _, _, _, _, extended = behaviors(falling=True, extra=True)
    assert first == extended[:len(first)]


def test_vertical_warning_is_projected_and_rendered_as_down_arrow():
    labels, _, points, frame, result = behaviors(falling=True)
    record = SimpleNamespace(error=None, skipped=False, details={"bar_projection": points, "bar_behaviors": result})
    layer = _stabil_verisi({"stabil": record}, "1d", 0, len(points), list(labels))
    assert 29 in layer["dikey_barlar"] and layer["dikey_deneme_barlar"] == [29]
    assert 29 not in layer["reclaim_barlar"] and 29 not in layer["momentum_barlar"]
    fig, ax = plt.subplots()
    try:
        meta = _stabil_ciz(ax, {"stabil": layer}, len(points), (90, 105),
                           dusuk=frame["low"], yuksek=frame["high"])
        assert meta["dikey_deneme_isaret"] == 0
        assert meta["reclaim_isaret"] == 0 and meta["momentum_isaret"] == 0
        assert not any(item.get_gid() == "grafik-stabil-dikey-deneme" for item in ax.collections)
    finally:
        plt.close(fig)


def test_legacy_snapshot_with_level_step_cannot_draw_up_arrow():
    layer = {"hazir": True, "seviyeler": [100.0, 95.0, 95.0],
             "renkler": ["ust"] * 3, "reclaim_barlar": [1, 2], "momentum_barlar": [1]}
    fig, ax = plt.subplots()
    try:
        meta = _stabil_ciz(ax, {"stabil": layer}, 3, (90, 105),
                           dusuk=[99, 94, 94], yuksek=[101, 96, 96])
        assert meta["dikey_deneme_isaret"] == 0
        assert meta["reclaim_isaret"] == 1 and meta["momentum_isaret"] == 0
        assert not any(c.get_gid() == "grafik-stabil-dikey-deneme" for c in ax.collections)
    finally:
        plt.close(fig)


def test_missing_projection_bar_carries_support_but_not_old_arrow():
    labels, _, points, _, result = behaviors(falling=False)
    # Replace early behavior with a synthetic upward marker and omit middle timestamp.
    marker = replace(result[0], momentum_kind="long_base_breakout")
    selected_points = [points[0], points[2]]
    record = SimpleNamespace(error=None, skipped=False, details={
        "bar_projection": selected_points, "bar_behaviors": [marker, result[2]],
    })
    layer = _stabil_verisi({"stabil": record}, "1d", 0, 3, list(labels[:3]))
    assert layer["seviyeler"] == [100.0, 100.0, 100.0]
    assert layer["momentum_barlar"] == [0]


def test_recent_upward_step_stays_vertical_when_breach_regime_takes_priority():
    _, snapshots, points, frame = make_series(falling=True)
    for i in (28, 29):
        progression = SupportProgression.REBASED_HIGHER if i == 28 else SupportProgression.SAME
        snapshots[i] = replace(snapshots[i], support_level=105.0, support_floor=100.0,
                               progression=progression, close_below_support=True)
        points[i] = replace(points[i], support_level=105.0, progression=progression)
    frame.loc[28, ["open", "high", "low", "close"]] = [105.1, 105.2, 104.4, 104.7]
    frame.loc[29, ["open", "high", "low", "close"]] = [104.7, 106.0, 104.6, 105.8]
    last = evaluate_bar_behaviors("ASTOR", "1d", frame, points, snapshots)[-1]
    assert last.regime == "BREACHED_FIXED_SUPPORT" and last.vertical_support
    assert last.vertical_attempt_kind == "touch_from_below"
    assert last.reclaim_kind is None and last.momentum_kind is None


def test_older_breached_upward_step_does_not_remain_vertical_forever():
    _, snapshots, points, frame = make_series(falling=True)
    snapshots[28] = replace(snapshots[28], progression=SupportProgression.REBASED_HIGHER)
    snapshots[29] = replace(snapshots[29], bars_since_support=9)
    result = evaluate_bar_behaviors("ASTOR", "1d", frame, points, snapshots)
    assert result[-1].regime == "BREACHED_FIXED_SUPPORT"
    assert not result[-1].vertical_support and result[-1].reclaim_kind is None
