"""Strict close-time alignment for the chart-only resistance layer."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pandas as pd

import grafik
from data import mum_kapanis_anlari, resample_ohlcv
from domain_engines.stabil.chart_bridge import resistance_for_chart
from domain_engines.stabil.runtime import StabilRoleStatus
from grafik.tarama import _stabil_direnc_verisi
from test_stabil_resistance_chart_bridge import _frames


def _record(labels):
    closes = mum_kapanis_anlari(labels, "1h")
    points = []
    behaviors = []
    for i, close in enumerate(closes):
        points.append(SimpleNamespace(bar_index=i, bar_close_time=close, daily_as_of=close - pd.Timedelta(days=1),
                                      resistance_level=100.0 + i * 0.01, color_role=("red" if i != 2 else "green"),
                                      validity="ACTIVE" if i != 2 else "BREACHED"))
        behaviors.append(SimpleNamespace(bar_index=i, bar_close_time=close, resistance_level=100.0 + i * 0.01,
                                         return_kind=("close_return_below" if i == 1 else None),
                                         momentum_kind=("downward_rebase_momentum" if i == 2 else None),
                                         vertical_resistance=i == 3,
                                         vertical_attempt_kind=("approach_from_above" if i == 3 else None)))
    return SimpleNamespace(status="READY", reason=None, bar_projection=points, bar_behaviors=behaviors)


def test_exact_matching_carries_no_old_level_or_arrow_over_a_missing_bar():
    labels = pd.date_range("2026-03-10 09:30", periods=5, freq="h", tz="Europe/Istanbul")
    record = _record(labels)
    record.bar_projection.pop(2)
    record.bar_behaviors.pop(2)
    snapshot = _stabil_direnc_verisi({"stabil_direnc": record}, "1h", 0, len(labels), labels)
    assert snapshot["seviyeler"] == [100.0, 100.01, None, 100.03, 100.04]
    assert snapshot["renkler"] == ["alt", "alt", None, "alt", "alt"]
    assert snapshot["donus_barlar"] == [1]
    assert snapshot["momentum_barlar"] == []
    assert snapshot["dikey_deneme_barlar"] == [3]


def test_reverse_colors_and_only_engine_arrows_even_with_step_connectors():
    labels = pd.date_range("2026-03-10 09:30", periods=5, freq="h", tz="Europe/Istanbul")
    snapshot = _stabil_direnc_verisi({"stabil_direnc": _record(labels)}, "1h", 0, len(labels), labels)
    assert snapshot["renkler"] == ["alt", "alt", "ust", "alt", "alt"]
    assert snapshot["donus_barlar"] == [1]
    assert snapshot["momentum_barlar"] == [2]
    assert snapshot["dikey_barlar"] == snapshot["dikey_deneme_barlar"] == [3]


def test_unreliable_times_future_daily_and_other_bar_behavior_do_not_guess():
    labels = pd.date_range("2026-03-10 09:30", periods=5, freq="h", tz="Europe/Istanbul")
    record = _record(labels)
    no_times = _stabil_direnc_verisi({"stabil_direnc": record}, "1h", 0, 5, None)
    assert not no_times["hazir"] and no_times["neden"] == "invalid_time_alignment"
    record.bar_projection[1].daily_as_of = record.bar_projection[1].bar_close_time + pd.Timedelta(seconds=1)
    future = _stabil_direnc_verisi({"stabil_direnc": record}, "1h", 0, 5, labels)
    assert not future["hazir"] and future["neden"] == "future_daily_snapshot"
    record = _record(labels)
    record.bar_behaviors[1].bar_index = 99
    wrong_bar = _stabil_direnc_verisi({"stabil_direnc": record}, "1h", 0, 5, labels)
    assert wrong_bar["donus_barlar"] == []
    record = _record(labels)
    record.bar_projection[1].bar_close_time = record.bar_projection[0].bar_close_time
    duplicate = _stabil_direnc_verisi({"stabil_direnc": record}, "1h", 0, 5, labels)
    assert not duplicate["hazir"] and duplicate["neden"] == "invalid_time_alignment"


def test_real_domain_points_match_visible_chart_without_modifying_support():
    daily, hourly = _frames()
    target = resample_ohlcv(hourly, "4h")
    cutoff = mum_kapanis_anlari(target.index, "4h")[-1]
    result = resistance_for_chart("AKBNK", "4h", target, daily_frame=daily,
                                  hourly_frame=hourly, as_of_close=cutoff)
    assert result.status == StabilRoleStatus.READY
    other = {"market_structure": None, "stabil": None}
    old = grafik.anlik_goruntu(None, "4h", target, sonuclar=other, sembol="AKBNK", simdi=cutoff)
    new = grafik.anlik_goruntu(None, "4h", target, sonuclar={**other, "stabil_direnc": result},
                               sembol="AKBNK", simdi=cutoff)
    assert old["stabil"] == new["stabil"]
    assert new["stabil_direnc"]["son_seviye"] == result.bar_projection[-1].resistance_level
    assert new["stabil_direnc"]["seviyeler"][-len(result.bar_projection):] == [
        pt.resistance_level for pt in result.bar_projection
    ]


def test_unavailable_result_reports_reason_without_dropping_chart():
    daily, hourly = _frames()
    target = resample_ohlcv(hourly, "4h")
    cutoff = mum_kapanis_anlari(target.index, "4h")[-1]
    result = resistance_for_chart("AKBNK", "4h", target, daily_frame=daily, hourly_frame=None,
                                  as_of_close=cutoff)
    image = grafik.anlik_goruntu(None, "4h", target, sonuclar={"stabil_direnc": result},
                                 sembol="AKBNK", simdi=cutoff)
    assert not image["stabil_direnc"]["hazir"]
    assert image["stabil_direnc"]["neden"] == "missing_source"
    assert any("Stabil direnç gösterilemedi" in s for s in image["uyarilar"])


def test_future_target_bar_never_gets_stale_last_price_chip():
    daily, hourly = _frames()
    target = resample_ohlcv(hourly, "4h")
    cutoff = mum_kapanis_anlari(target.index[-2:-1], "4h")[0]
    result = resistance_for_chart("AKBNK", "4h", target, daily_frame=daily,
                                  hourly_frame=hourly, as_of_close=cutoff)
    labels = list(target.index[-3:])
    snapshot = _stabil_direnc_verisi({"stabil_direnc": result}, "4h", 0, 3, labels)
    assert snapshot["seviyeler"][-1] is None
    assert snapshot["son_seviye"] is None and snapshot["son_renk"] is None
    # Suppressing the signal is independent from the status of earlier points.
    assert snapshot["hazir"]


def test_data_error_reason_is_not_lost_in_snapshot():
    daily, hourly = _frames()
    target = resample_ohlcv(hourly, "4h")
    result = resistance_for_chart("AKBNK", "4h", target, daily_frame=daily, hourly_frame=None)
    result = replace(result, status=StabilRoleStatus.DATA_ERROR, reason="incomplete_hourly_bucket")
    snap = _stabil_direnc_verisi({"stabil_direnc": result}, "4h", 0, len(target), list(target.index))
    assert snap["neden"] == "incomplete_hourly_bucket" and not snap["hazir"]


def test_failed_result_with_stale_projection_never_renders_a_line_or_arrow():
    labels = pd.date_range("2026-03-10 09:30", periods=5, freq="h", tz="Europe/Istanbul")
    record = _record(labels)
    record.status = "DATA_ERROR"
    record.reason = "invalid_ohlcv"
    snapshot = _stabil_direnc_verisi({"stabil_direnc": record}, "1h", 0, 5, labels)
    assert not snapshot["hazir"] and snapshot["neden"] == "invalid_ohlcv"
    assert not snapshot["seviyeler"] and not snapshot["donus_barlar"]


def test_level_without_daily_snapshot_time_is_never_drawn():
    labels = pd.date_range("2026-03-10 09:30", periods=5, freq="h", tz="Europe/Istanbul")
    record = _record(labels)
    record.bar_projection[1].daily_as_of = None
    snapshot = _stabil_direnc_verisi({"stabil_direnc": record}, "1h", 0, 5, labels)
    assert not snapshot["hazir"] and snapshot["neden"] == "missing_daily_snapshot"
    assert not snapshot["seviyeler"] and not snapshot["donus_barlar"]
