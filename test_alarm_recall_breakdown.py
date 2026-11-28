"""Coverage detail must not equate a repeated text label with a duplicate event."""
import json

import pytest

from research.alarm_recall_breakdown import breakdown, cooldown_information, information_signature
from research.alarm_recall_study import assign_decisions, event_key
from research.causal_alarm_replay import VERSION
from test_causal_alarm_replay import event


def full_event(index, **kwargs):
    return {**event(index, **kwargs), "reasons": ["BOS ↑"], "direction_status": "explicit",
            "outcome_12": {**event(index)["outcome_12"], "touch_delay_bars": 1}}


def test_cooldown_proxy_preserves_prewindow_selection_and_changed_reason():
    rows = [full_event(1, date="2026-10-30"), full_event(2), full_event(3)]
    rows[2]["reasons"] = ["BOS ↑", "OB boğa bölge tepkisi"]
    decisions = assign_decisions(rows, lambda r: True)
    result = cooldown_information(rows, decisions, ["2026-11-02"])
    assert result["same_categorical_signature"]["events"] == 1
    assert result["categorical_change"]["events"] == 1
    assert result["categorical_change"]["favorable_first"] == 1


def test_signature_ignores_outcomes_but_tracks_direction_and_form_state():
    row = full_event(1)
    assert information_signature(row) == information_signature({**row, "outcome_12": {}})
    assert information_signature(row) != information_signature({**row, "source_direction": -1})
    a = {**row, "formation": {"formation_id": "a", "notification_state": "A"}}
    b = {**row, "formation": {"formation_id": "a", "notification_state": "B"}}
    assert information_signature(a) != information_signature(b)


def test_cooldown_without_selection_fails_closed():
    row = full_event(2)
    with pytest.raises(ValueError, match="prior selection"):
        cooldown_information([row], {event_key(row): "cooldown_blocked"}, ["2026-11-02"])


def test_breakdown_delay_is_deduplicated_by_later_event(tmp_path):
    rows = [full_event(10, passed=False), full_event(11, passed=False), full_event(12)]
    for row in rows:
        row["formation"] = {"formation_id": "same", "notification_state": "RETEST", "break_dir": 1}
    (tmp_path / "summary.json").write_text(json.dumps({"manifest": {"schema": VERSION, "sessions": ["2026-11-02"]}}))
    (tmp_path / "events.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    result, examples = breakdown(tmp_path)
    delay = result["delayed_same_formation"]
    assert delay["blocked_rows"] == 2
    assert delay["distinct_later_events"] == 1
    assert delay["favorable_first_reached_by_later_close_rows"] == 2
    assert delay["distinct_later_events_with_prior_favorable_touch"] == 1
    assert len(examples) == 1  # Only the first blocked row was selected by P0.


def test_breakdown_refuses_duplicate_events(tmp_path):
    row = full_event(10)
    (tmp_path / "summary.json").write_text(json.dumps({"manifest": {"schema": VERSION, "sessions": ["2026-11-02"]}}))
    (tmp_path / "events.jsonl").write_text(json.dumps(row) + "\n" + json.dumps(row))
    with pytest.raises(ValueError, match="Duplicate"):
        breakdown(tmp_path)
