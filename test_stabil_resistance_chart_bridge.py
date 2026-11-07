"""Chart-only resistance source gates; no change to alert/support contracts."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from bist_calendar import SessionStatus, bist_session_for
from data import mum_kapanis_anlari, resample_ohlcv
from domain_engines.stabil.chart_bridge import add_chart_resistance, resistance_for_chart
from domain_engines.stabil.runtime import StabilRoleStatus


def _frames():
    days = [d for d in pd.date_range("2026-01-05", "2026-04-15")
            if bist_session_for(d.date()).status is SessionStatus.TRADING][:60]
    x = np.arange(len(days), dtype=float)
    close = 100.0 + 0.03 * x + 2.0 * np.sin(x / 3.0)
    daily = pd.DataFrame({
        "open": close - 0.15, "high": close + 0.9, "low": close - 1.0,
        "close": close, "volume": np.full(len(days), 1000.0),
    }, index=pd.DatetimeIndex(days, tz="Europe/Istanbul"))
    labels = []
    for day in days[-5:]:
        labels.extend(pd.date_range(day + pd.Timedelta(hours=9, minutes=30), periods=9, freq="h"))
    labels = pd.DatetimeIndex(labels, tz="Europe/Istanbul")
    series = 101.0 + np.arange(len(labels)) * 0.01
    hourly = pd.DataFrame({"open": series, "high": series + 0.8, "low": series - 0.8,
                           "close": series + 0.1, "volume": np.full(len(labels), 100.0)}, index=labels)
    return daily, hourly


def _output(tf, daily, hourly, *, target=None, cutoff=None):
    target = target if target is not None else (
        daily if tf == "1d" else hourly if tf == "1h" else resample_ohlcv(hourly, tf)
    )
    cutoff = cutoff or mum_kapanis_anlari(target.index, tf)[-1]
    return resistance_for_chart("AKBNK", tf, target, daily_frame=daily,
                                hourly_frame=hourly, as_of_close=cutoff)


@pytest.mark.parametrize("tf", ["1h", "2h", "4h", "1d"])
def test_complete_native_sources_work_and_do_not_mutate(tf):
    daily, hourly = _frames()
    before_daily, before_hourly = daily.copy(deep=True), hourly.copy(deep=True)
    result = _output(tf, daily, hourly)
    assert result.status == StabilRoleStatus.READY, result.reason
    assert result.bar_projection[-1].daily_as_of <= result.bar_projection[-1].bar_close_time
    pd.testing.assert_frame_equal(daily, before_daily)
    pd.testing.assert_frame_equal(hourly, before_hourly)


def test_partial_rolling_prefix_is_not_invented():
    daily, hourly = _frames()
    hourly = hourly.iloc[1:]
    target = resample_ohlcv(hourly, "4h")
    result = _output("4h", daily, hourly, target=target)
    assert result.status == StabilRoleStatus.READY, result.reason
    assert result.bar_projection[0].bar_close_time == mum_kapanis_anlari(target.index[1:2], "4h")[0]
    assert len(result.bar_projection) == len(target) - 1


@pytest.mark.parametrize("tf,missing_count", [("1h", 1), ("2h", 1), ("4h", 1), ("4h", 4)])
def test_internal_missing_hourly_bar_or_whole_bucket_fails_closed(tf, missing_count):
    daily, hourly = _frames()
    hourly = hourly.drop(hourly.index[10:10 + missing_count])
    result = _output(tf, daily, hourly)
    assert result.status == StabilRoleStatus.DATA_ERROR
    assert result.reason in {"missing_or_invalid_target_bucket", "incomplete_hourly_bucket"}
    assert not result.bar_projection


def test_known_closed_day_provider_row_is_excluded_without_mutating_source(caplog):
    daily, hourly = _frames()
    closed_day = pd.Timestamp("2026-03-28", tz="Europe/Istanbul")  # Saturday
    daily.loc[closed_day] = daily.iloc[-1].to_numpy()
    daily = daily.sort_index()
    before = daily.copy(deep=True)

    result = _output("4h", daily, hourly)

    assert result.status == StabilRoleStatus.READY, result.reason
    assert all(obs.timestamp.date() != closed_day.date() for obs in result.observations)
    assert "2026-03-28" in caplog.text
    pd.testing.assert_frame_equal(daily, before)


def test_daily_chart_and_resistance_both_ignore_known_closed_day_provider_row():
    daily, hourly = _frames()
    closed_day = pd.Timestamp("2026-03-28", tz="Europe/Istanbul")  # Saturday
    daily.loc[closed_day] = daily.iloc[-1].to_numpy()
    daily = daily.sort_index()

    result = _output("1d", daily, hourly)

    assert result.status == StabilRoleStatus.READY, result.reason
    assert all(point.bar_close_time.date() != closed_day.date() for point in result.bar_projection)


def test_missing_daily_trading_session_or_latest_completed_daily_fails_closed():
    daily, hourly = _frames()
    assert _output("4h", daily.drop(daily.index[20]), hourly).reason == "missing_daily_session"
    # After today's daily close, yesterday's stale daily is not certified as current.
    cutoff = mum_kapanis_anlari(daily.index[-1:], "1d")[0]
    result = _output("4h", daily.iloc[:-1], hourly, cutoff=cutoff)
    # The target 4H closes at 18:00, *before* today's 18:30 daily close.
    assert result.status == StabilRoleStatus.READY
    result = _output("1d", daily.iloc[:-1], hourly, target=daily, cutoff=cutoff)
    assert result.reason == "missing_daily_session"


def test_partial_flag_and_different_aggregate_fail_closed():
    daily, hourly = _frames()
    target = resample_ohlcv(hourly, "4h")
    hourly["is_complete"] = True
    hourly.iloc[10, hourly.columns.get_loc("is_complete")] = False
    result = _output("4h", daily, hourly, target=target)
    assert result.reason == "incomplete_or_invalid_flag"
    hourly["is_complete"] = True
    target.iloc[4, target.columns.get_loc("high")] += 0.5
    result = _output("4h", daily, hourly, target=target)
    assert result.reason == "target_source_mismatch"


def test_future_bad_values_duplicates_and_flags_do_not_affect_cutoff():
    daily, hourly = _frames()
    hourly["is_complete"] = True
    target = resample_ohlcv(hourly, "4h")
    cutoff = mum_kapanis_anlari(target.index[-4:-3], "4h")[0]
    reference = _output("4h", daily, hourly, target=target, cutoff=cutoff)
    # Future anomalies are not allowed to rewrite history or its quality verdict.
    future_time = cutoff.normalize() + pd.Timedelta(days=1, hours=9, minutes=30)
    future = hourly.iloc[-1:].copy()
    future.index = pd.DatetimeIndex([future_time])
    future["close"] = float("nan")
    future["is_complete"] = False
    hourly_future = pd.concat([hourly, future, future])
    daily_future = daily.copy()
    daily_future.loc[daily_future.index > cutoff, "close"] = float("nan")
    future_target = pd.concat([target, target.iloc[-1:]])  # duplicate is after cutoff
    actual = _output("4h", daily_future, hourly_future, target=future_target, cutoff=cutoff)
    assert actual.status == reference.status == StabilRoleStatus.READY
    assert actual.bar_projection == reference.bar_projection
    assert actual.bar_behaviors == reference.bar_behaviors


def test_known_bad_flags_and_missing_sources_never_produce_a_line():
    daily, hourly = _frames()
    daily["is_closed"] = pd.Series(True, index=daily.index, dtype=object)
    daily.iloc[10, daily.columns.get_loc("is_closed")] = "False"
    assert _output("4h", daily, hourly).reason == "incomplete_or_invalid_flag"
    target = resample_ohlcv(hourly, "4h")
    result = resistance_for_chart("AKBNK", "4h", target, daily_frame=daily, hourly_frame=None)
    assert not result.bar_projection
    daily, hourly = _frames()
    result = resistance_for_chart("AKBNK", "4h", target, daily_frame=daily, hourly_frame=None)
    assert result.status == StabilRoleStatus.UNAVAILABLE and result.reason == "missing_source"
    result = resistance_for_chart("BRENT", "4h", target, daily_frame=daily, hourly_frame=hourly)
    assert result.status == StabilRoleStatus.UNAVAILABLE and result.reason == "unsupported_session"


def test_daily_split_that_would_retroactively_change_scale_is_not_plotted():
    daily, hourly = _frames()
    columns = ["open", "high", "low", "close"]
    daily.loc[daily.index[-5:], columns] *= 0.5
    result = _output("1d", daily, hourly)
    assert result.status == StabilRoleStatus.DATA_ERROR
    assert result.reason == "daily_split_scale_unverified"
    assert not result.bar_projection


def test_chart_results_copy_preserves_existing_domain_results():
    daily, hourly = _frames()
    frames = {"4h": resample_ohlcv(hourly, "4h"), "1d": daily}
    existing = {"4h": {"stabil": object(), "market_structure": object()}, "1d": {"stabil": object()}}
    original = {tf: dict(values) for tf, values in existing.items()}
    result = add_chart_resistance("AKBNK", frames, existing, daily_frame=daily,
                                  hourly_frame=hourly, as_of_close=pd.Timestamp("2026-12-01", tz="Europe/Istanbul"))
    assert existing == original
    assert result["4h"]["stabil"] is existing["4h"]["stabil"]
    assert result["1d"]["stabil"] is existing["1d"]["stabil"]
    assert result["4h"]["stabil_direnc"].status == StabilRoleStatus.READY
    assert result["1d"]["stabil_direnc"].status == StabilRoleStatus.READY


def test_half_day_constituents_follow_real_session_end():
    daily, _ = _frames()
    half_day = date(2026, 5, 26)
    assert bist_session_for(half_day).is_half_day
    # Build a short, fully observed intraday window and a contiguous native daily
    # suffix through the half-day (the main fixture ends earlier).
    more = [d for d in pd.date_range(daily.index[-1].date() + pd.Timedelta(days=1), half_day)
            if bist_session_for(d.date()).status is SessionStatus.TRADING]
    for i, day in enumerate(more):
        daily.loc[pd.Timestamp(day, tz="Europe/Istanbul")] = [102, 103 + (i % 3), 101, 102, 1000]
    labels = pd.date_range(pd.Timestamp(half_day, tz="Europe/Istanbul") + pd.Timedelta(hours=9, minutes=30),
                           periods=4, freq="h")
    hourly = pd.DataFrame({"open": 102.0, "high": 103.0, "low": 101.0, "close": 102.1,
                           "volume": 100.0}, index=labels)
    result = _output("4h", daily, hourly)
    assert result.status == StabilRoleStatus.READY, result.reason
    assert result.bar_projection[-1].bar_close_time == pd.Timestamp("2026-05-26 13:00", tz="Europe/Istanbul")
    assert result.bar_projection[-1].daily_as_of == result.bar_projection[-1].bar_close_time
