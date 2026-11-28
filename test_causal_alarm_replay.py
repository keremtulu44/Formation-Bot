"""Causal replay contracts: decisions cannot see outcomes or live identity state."""
from types import SimpleNamespace

import pandas as pd
import pytest

from research.causal_alarm_replay import (
    channel_reasons, decision_snapshots, direction_from_reasons, forward_outcome,
)
from research.alarm_recall_study import analyze, assign_decisions, closed_archive, run


def frame(n=30):
    index = pd.date_range("2026-10-01T10:00+03:00", periods=n, freq="D")
    return pd.DataFrame({"open": 100., "high": 100.2, "low": 99.8,
                         "close": 100., "volume": 1000.}, index=index)


@pytest.mark.parametrize("reasons,form,direction,status", [
    (["BOS ↓"], 0, -1, "explicit"), (["BOS ↑"], 0, 1, "explicit"),
    (["OB ayı bölge tepkisi"], 0, -1, "explicit"),
    (["FVG boğa reaksiyon"], 0, 1, "explicit"),
    (["BOS ↑", "OB ayı bölge tepkisi"], 0, 0, "conflict"),
    (["formasyon: Üçgen"], -1, -1, "explicit"),
    (["hacim 5×"], 0, 0, "unknown"),
])
def test_direction_never_defaults_to_up(reasons, form, direction, status):
    assert direction_from_reasons(reasons, form) == (direction, status)


def test_actual_channel_predicates_match_live_at_capture():
    from bot.domain_alarm_service import _bos_ve_choch_sebepleri, _bolge_sebepleri, _formasyon_sebepleri
    f = frame(60)
    event = {"event_type": "BOS", "direction": -1, "event_bar": 59,
             "confirmation_status": "CONFIRMED", "validity": "VALID", "relevance": "ACTIVE"}
    exports = {"1h": {"market_structure": {"export": {"events": [event]}},
                       "order_block": {"export": {"bull": {"top": 101, "bottom": 99}}, "data_quality": "OK"}}}
    reasons, vol = channel_reasons(exports, "1h", f, [])
    assert reasons == sorted(set(_bos_ve_choch_sebepleri(exports, "1h", len(f))
        + _bolge_sebepleri(exports, "1h", 100) + _formasyon_sebepleri([], "1h")))
    assert "BOS ↓" in reasons and vol["source"] == "yerel"


def test_first_touch_ignores_anchor_and_keeps_ambiguity():
    f = frame(20)
    f.iloc[5, f.columns.get_loc("high")] = 200  # anchor cannot count
    f.iloc[6, f.columns.get_loc("high")] = 101.5
    f.iloc[6, f.columns.get_loc("low")] = 98.5
    result = forward_outcome(f, 5, 1, 1)
    assert result["first_touch"] == "AMBIGUOUS_SAME_BAR" and result["touch_delay_bars"] == 1


def test_negative_first_touch_and_unknown_direction_are_separate():
    f = frame(20)
    f.iloc[6, f.columns.get_loc("low")] = 98.5
    assert forward_outcome(f, 5, -1, 1)["first_touch"] == "FAVORABLE_FIRST"
    assert forward_outcome(f, 5, 1, 1)["first_touch"] == "ADVERSE_FIRST"
    assert forward_outcome(f, 5, 0, 1)["status"] == "UNKNOWN_DIRECTION"
    assert forward_outcome(f, 15, 1, 1)["status"] == "RIGHT_CENSORED"


def test_bad_future_is_not_a_failed_alarm():
    f = frame(20)
    f.iloc[7, f.columns.get_loc("low")] = -1
    assert forward_outcome(f, 5, 1, 1)["status"] == "BAD_FUTURE"


def test_private_formation_engine_never_touches_identity_stores(monkeypatch):
    import patterns.lifecycle as lifecycle
    def forbid(*a, **kw):
        raise AssertionError("Replay accessed live identity store")
    # Helpers may be invoked, but must see a deliberately unset identity key.
    def guard(engine, *a):
        assert engine._key is None
        return None
    monkeypatch.setattr(lifecycle, "_match_registry", guard)
    monkeypatch.setattr(lifecycle, "_match_persisted_anchor", guard)
    monkeypatch.setattr(lifecycle, "_save_formation_anchor", guard)
    from research.arsiv import tf_frame
    f = tf_frame("THYAO", "4h", legacy_resample=False).tail(160)
    before = lifecycle.ArgentEngine._process_bar
    decision_snapshots("THYAO", "4h", f)
    assert lifecycle.ArgentEngine._process_bar is before


@pytest.mark.parametrize("tf", ["1h", "2h", "4h", "1d"])
def test_real_archive_prefix_and_altered_future_do_not_change_decisions(tf):
    from research.arsiv import tf_frame
    f = tf_frame("THYAO", tf, legacy_resample=False).tail(180)
    a, errors = decision_snapshots("THYAO", tf, f)
    prefix, _ = decision_snapshots("THYAO", tf, f.iloc[:135])
    assert [r for r in a if r["bar_index"] < 135] == prefix
    changed = f.copy()
    changed.iloc[135:, :4] *= 1.2
    mutated, _ = decision_snapshots("THYAO", tf, changed)
    assert [r for r in mutated if r["bar_index"] < 135] == prefix
    assert not errors


def event(index, *, passed=True, date="2026-11-02", outcome="FAVORABLE_FIRST"):
    return {"symbol": "TEST", "timeframe": "1h", "bar_index": index,
            "bar_time": f"{date}T12:00+03:00", "kanallar": ["BOS"],
            "bagl_gunici_kosu": 2 if passed else -2, "bagl_sikisma": .5,
            "formation": None, "source_direction": 1, "unknown_domains": [],
            "outcome_12": {"status": "VALID", "first_touch": outcome,
                           "close_atr": .7, "mae_atr": .2}}


def test_decisions_do_not_read_outcomes_or_reset_prewindow_cooldown():
    rows = [event(10, date="2026-10-30"), event(12), event(16)]
    def rule(r):
        return r["bagl_gunici_kosu"] >= 1
    decisions = assign_decisions(rows, rule)
    changed = [{**r, "outcome_12": {"status": "BAD_FUTURE"}} for r in rows]
    assert assign_decisions(changed, rule) == decisions
    assert list(decisions.values()) == ["selected", "cooldown_blocked", "selected"]


def test_cohorts_count_missed_favorable_events_not_just_reduction():
    rows = [event(10, passed=False), event(12), event(20)]
    result, daily, _ = analyze(rows, ["2026-11-02", "2026-11-03"])
    assert result["policies"]["P6"]["policy_blocked"]["favorable_first"] == 1
    assert result["vs_P0_after_cooldown"]["P6"]["P0_only"]["favorable_first"] == 1
    assert result["vs_P0_after_cooldown"]["P6"]["policy_only"]["events"] == 1
    assert daily[1]["P6"] == 0


def test_new_output_directory_is_required(tmp_path):
    (tmp_path / "old").write_text("do not overwrite")
    with pytest.raises(ValueError, match="new empty"):
        run([], tmp_path)


def test_capture_excludes_open_final_bar(monkeypatch):
    from research import arsiv
    f = frame(5)
    monkeypatch.setattr(arsiv, "tf_frame", lambda *a, **kw: f)
    monkeypatch.setattr(arsiv, "manifest_oku", lambda: {"kayitlar": {"TEST:1d": {
        "durum": "ok", "dosya": "TEST_1d.csv.gz", "native": True,
        "zaman": "2026-10-05T12:00+03:00", "sure_sn": 1}}})
    actual = closed_archive("TEST", "1d", 480)
    assert len(actual) == 4
