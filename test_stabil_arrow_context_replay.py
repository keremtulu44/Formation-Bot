"""Research replay causality, censoring and unknown-context contract."""
from copy import deepcopy

import numpy as np
import pandas as pd

from data import mum_kapanis_anlari
from domain_engines.stabil import build_single_pass_history, evaluate_bar_behaviors, project_support_to_bar_closes
from research.arsiv import tf_frame
from research.stabil_arrow_context_replay import (
    _zone_bucket, aggregate, bad_bars, context_snapshots, forward_metrics, replay_symbol,
)


def _flat_frame(n=35):
    return pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=n, freq="4h", tz="Europe/Istanbul"),
        "open": np.full(n, 100.0), "high": np.full(n, 100.2),
        "low": np.full(n, 99.8), "close": np.full(n, 100.0), "volume": np.full(n, 1000.0),
        "is_closed": True, "is_complete": True,
    })


def test_forward_path_ignores_signal_bar_and_reports_same_bar_ambiguity():
    frame = _flat_frame()
    frame.loc[20, "high"] = 110.0  # signal bar cannot count toward the future MFE
    frame.loc[21, ["high", "low"]] = [102.0, 98.0]
    result = forward_metrics(frame, 20, 1.0, bad_bars(frame), (4, 8, 16))
    assert result["status_8"] == "VALID" and result["mfe_atr_8"] == 2.0
    assert result["mae_atr_8"] == 2.0 and result["weak_mfe_8"] is False
    assert result["first_1atr_8"] == "AMBIGUOUS_SAME_BAR"
    assert result["status_16"] == "RIGHT_CENSORED" and result["weak_mfe_16"] is None


def test_censoring_and_bad_future_are_never_failures():
    frame = _flat_frame()
    frame.loc[26, "close"] = 50.0  # discontinuity and malformed candle
    result = forward_metrics(frame, 20, 1.0, bad_bars(frame), (4, 8, 16))
    assert result["status_4"] == "VALID" and result["weak_mfe_4"] is True
    assert result["status_8"] == "BAD_FUTURE" and result["weak_mfe_8"] is None
    assert result["status_16"] == "RIGHT_CENSORED" and result["right_censored_16"] is True
    assert forward_metrics(frame, 20, None, bad_bars(frame), (8,))["status_8"] == "NO_ATR"


def test_unknown_zone_is_not_assigned_to_no_zone_and_empty_run_is_supported():
    assert _zone_bucket(None, False) == "UNKNOWN"
    assert _zone_bucket(None, True) == "NONE_AHEAD"
    assert _zone_bucket(1.0, True) == "NEAR_1ATR"
    assert aggregate([])["valid_arrows_8"] == 0


def test_native_context_snapshots_are_prefix_stable():
    frame = _flat_frame(160)
    # Add varied, valid prices and volumes so native detectors are actually exercised.
    x = np.arange(len(frame), dtype=float)
    center = 100 + .025 * x + np.sin(x / 4) * 2
    frame["open"] = center - .1
    frame["close"] = center + .1
    frame["high"] = center + .8
    frame["low"] = center - .8
    frame["volume"] = 1000 + (x % 9) * 80
    atrs = np.full(len(frame), 1.6)
    prefix = context_snapshots(frame.iloc[:126], {125}, atrs[:126])[125]
    saved = deepcopy(prefix)
    with_future = context_snapshots(frame, {125, 159}, atrs)
    assert prefix == with_future[125] == saved
    assert with_future[125]["domain_errors"] == {}


def test_stabil_behaviors_match_prefix_replay_at_actual_archive_cutoff():
    daily = tf_frame("ASTOR", "1d")
    h4 = tf_frame("ASTOR", "4h")
    cutoff_index = len(h4) - 50
    cutoff = mum_kapanis_anlari(h4.index, "4h")[cutoff_index]
    daily_prefix = daily.loc[mum_kapanis_anlari(daily.index, "1d") <= cutoff]
    h4_prefix = h4.iloc[:cutoff_index + 1]
    full = build_single_pass_history("ASTOR", daily, h4, include_support_prefix_events=False)
    prefix = build_single_pass_history("ASTOR", daily_prefix, h4_prefix, include_support_prefix_events=False)

    def evaluate(hist):
        projection = project_support_to_bar_closes(hist.h4_close_times, hist.support_timeline)
        return evaluate_bar_behaviors("ASTOR", "4h", hist.h4_frame, projection, hist.support_timeline)

    assert evaluate(full)[:len(prefix.h4_frame)] == evaluate(prefix)


def test_real_rebased_up_breach_is_a_vertical_warning_not_up_arrow():
    events = replay_symbol("AEFES")["events"]
    event = next(e for e in events if e["event_close_time"] == "2025-07-17 17:30:00+03:00")
    assert event["regime_proxy"] == "BREACHED_FIXED_SUPPORT"
    assert event["vertical_proxy"] is True
    assert event["kind"] == "intrabar_sweep_reclaim"
    assert event["event_class"] == "VERTICAL_SUPPRESSED_PREVIOUS_UP_CANDIDATE"


def test_archive_capture_cutoff_excludes_not_yet_closed_h4_and_daily_bars():
    from research.stabil_arrow_context_replay import capture_cutoffs, closed_at_capture

    captures = capture_cutoffs("AEFES")
    h4_all = tf_frame("AEFES", "4h")
    daily_all = tf_frame("AEFES", "1d")
    h4 = closed_at_capture(h4_all, "4h", captures["1h"])
    daily = closed_at_capture(daily_all, "1d", captures["1d"])
    assert len(h4_all) - len(h4) == 1
    assert len(daily_all) - len(daily) == 1
    assert mum_kapanis_anlari(h4.index, "4h")[-1] <= captures["1h"]
    assert mum_kapanis_anlari(h4_all.index, "4h")[-1] > captures["1h"]
    assert mum_kapanis_anlari(daily.index, "1d")[-1] <= captures["1d"]
    assert mum_kapanis_anlari(daily_all.index, "1d")[-1] > captures["1d"]
    result = replay_symbol("AEFES")
    assert result["excluded_unclosed_1d"] == result["excluded_unclosed_4h"] == 1
    assert pd.Timestamp(result["last_4h_close"]) <= captures["1h"]


def test_missing_or_untrustworthy_archive_capture_fails_closed(tmp_path):
    import json
    import pytest
    from research.stabil_arrow_context_replay import capture_cutoffs

    with pytest.raises(ValueError, match="capture record"):
        capture_cutoffs("ABC", str(tmp_path))
    good = {"durum": "ok", "dosya": "ABC_1h.csv.gz", "zaman": "2026-10-19T13:33:25+00:00", "sure_sn": 9.1}
    one_day = {**good, "dosya": "ABC_1d.csv.gz"}
    manifest = {"kayitlar": {"ABC:1h": good, "ABC:1d": one_day}}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert capture_cutoffs("ABC", str(tmp_path))["1h"] == pd.Timestamp("2026-10-19T13:33:14.9+00:00")
    for invalid in (None, "2026-10-19T13:33:25", "not-a-time"):
        good["zaman"] = invalid
        (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        with pytest.raises(ValueError, match="capture time"):
            capture_cutoffs("ABC", str(tmp_path))
