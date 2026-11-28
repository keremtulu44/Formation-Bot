"""Offline audit contracts; production alarm policy stays untouched."""
import json

import pandas as pd
import pytest

from research.alarm_filter_audit import audit, main, measure, unique_events


def row(index=10, date="2026-11-02", **kw):
    return dict(symbol="TEST", timeframe="1h", bar_index=index,
                bar_time=f"{date}T11:30:00+03:00", kanallar=["OB"],
                bagl_sikisma=.5, bagl_gunici_kosu=1.5, hacim_tier=None,
                formasyon_state=None, kontrol=False, yon=1,
                yon_asim_100=True, ters_h12=False, **kw)


def test_pair_is_one_event_and_side_order_does_not_change_counts():
    first = row()
    second = {**first, "yon": -1, "yon_asim_100": False, "ters_h12": True}
    for rows in ([first, second], [second, first]):
        events = unique_events(pd.DataFrame(rows))
        assert len(events) == 1 and events.outcome_sides.iloc[0] == 2
        stats, _ = measure(events, ["2026-11-02"])
        assert stats["events"] == 1 and stats["any_1atr_12_rate"] == 1
        assert stats["both_1atr_12_rate"] == 0


@pytest.mark.parametrize("change", [{"yon": 1}, {"bar_time": "2026-11-03T11:30+03:00", "yon": -1},
                                    {"kanallar": ["BOS"], "yon": -1},
                                    {"yon": -1, "yon_asim_100": False, "ters_h12": False}])
def test_corrupt_pairs_are_rejected(change):
    first = row()
    with pytest.raises(ValueError):
        unique_events(pd.DataFrame([first, {**first, **change}]))


def test_zero_day_is_in_denominator_and_censored_is_not_failure():
    events = unique_events(pd.DataFrame([{**row(), "yon_asim_100": None, "ters_h12": None}]))
    stats, daily = measure(events, ["2026-11-02", "2026-11-03"])
    assert stats["daily_mean"] == .5 and stats["zero_days"] == 1
    assert stats["events"] == 1 and stats["measured_12"] == 0
    assert stats["any_1atr_12_rate"] is None and daily.iloc[1] == 0


def test_cooldown_keeps_prewindow_history():
    events = unique_events(pd.DataFrame([row(10), row(12, "2026-11-03"), row(16, "2026-11-03")]))
    stats, _ = measure(events, ["2026-11-03"])
    assert stats["events"] == 1 and stats["cooldown_rejected"] == 1


def test_policy_precedes_cooldown():
    events = unique_events(pd.DataFrame([row(10), row(12, "2026-11-03")]))
    stats, _ = measure(events, ["2026-11-03"], rule=lambda r: r.bar_index == 12)
    assert stats["events"] == 1


def test_symmetry_is_separate_hypothesis_not_a_change_to_p6():
    events = unique_events(pd.DataFrame([{**row(), "bagl_gunici_kosu": -2}]))
    result, _ = audit(events, ["2026-11-02", "2026-11-03"])
    assert result["policies"]["P6"]["events"] == 0
    assert result["policies"]["HYP_symmetric_run_NOT_LIVE"]["events"] == 1
    assert result["context"]["run_le_minus1"] == 1


def test_no_repeat_removes_only_formation_channel():
    events = unique_events(pd.DataFrame([
        {**row(10), "kanallar": ["FORMASYON"], "formasyon_state": "KIRILIM_TEYITLI"},
        {**row(20), "kanallar": ["FORMASYON", "OB"], "formasyon_state": "KIRILIM_TEYITLI"},
    ]))
    result, _ = audit(events, ["2026-11-02"])
    assert result["policies"]["P6"]["events"] == 2
    assert result["policies"]["P6_no_immediate_repeat_proxy"]["events"] == 1


def test_empty_denominator_rejected():
    with pytest.raises(ValueError):
        measure(unique_events(pd.DataFrame([row()])), [])


def test_cli_jsonl_roundtrip_and_full_series_denominator(tmp_path, monkeypatch):
    import config
    from research import arsiv
    monkeypatch.setattr(config, "ACTIVE_STOCKS", ["THYAO"])
    monkeypatch.setattr(arsiv, "arsiv_sembolleri", lambda **kw: ["THYAO"])
    source = tmp_path / "source"
    source.mkdir()
    event = {**row(), "symbol": "THYAO"}
    (source / "tetikler.jsonl").write_text(json.dumps(event) + "\n")
    meta = [dict(symbol="THYAO", timeframe=tf,
                 seans_bar_sayilari={"2026-11-02": 1, "2026-11-03": 1, "2026-11-04": 1})
            for tf in ["1h", "2h", "4h", "1d"]]
    (source / "meta.jsonl").write_text("\n".join(json.dumps(m) for m in meta))
    target = tmp_path / "out"
    assert main(["--input", str(source), "--output", str(target), "--first", "2026-11-02", "--last", "2026-11-04"]) == 0
    result = json.loads((target / "summary.json").read_text())
    assert result["policies"]["P0"]["daily_mean"] == .5
    assert result["manifest"]["session_dates"] == ["2026-11-02", "2026-11-03"]
    assert len(result["manifest"]["archive_hashes"]) == 4
    (source / "hatalar.jsonl").write_text('{"error":"partial"}\n')
    with pytest.raises(ValueError, match="Replay has errors"):
        main(["--input", str(source), "--output", str(target)])
