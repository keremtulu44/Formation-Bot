"""Keepalive audit checks actual schedule and HTTP steps, not just green jobs."""

from datetime import datetime, timedelta, timezone

import pytest

from scripts import keepalive_audit as audit

UTC = timezone.utc


def _run(run_id, when, *, event="schedule", conclusion="success"):
    return {"id": run_id, "event": event, "run_started_at": when.isoformat(),
            "status": "completed", "conclusion": conclusion}


def _jobs(outcome):
    return {"jobs": [{"conclusion": "success", "steps": [{"name": "GET /health", "conclusion": outcome}]}]}


def test_summary_catches_gaps_and_does_not_treat_green_job_as_ping():
    start = datetime(2026, 11, 3, tzinfo=UTC)
    data = {"workflow_runs": [_run(1, start), _run(2, start + timedelta(hours=3)),
                              _run(3, start + timedelta(hours=3, minutes=5)),
                              _run(4, start + timedelta(minutes=2), event="workflow_dispatch")]}
    result = audit.analyze_runs(data, now=start + timedelta(hours=3, minutes=5))
    assert len(result["selected"]) == 3
    assert result["over_threshold"] == 1 and result["max_gap"] == 180
    assert result["conclusions"]["success"] == 3
    assert audit.health_step(_jobs("skipped")) == "skipped"
    assert audit.health_step({"jobs": [{"conclusion": "success", "steps": []}]}) == "missing"


def test_nightly_counts_only_fully_observed_windows():
    # Istanbul is UTC+3. First night's 02:00-02:20 is only partially covered.
    start = datetime(2026, 11, 2, 23, 10, tzinfo=UTC)
    data = {"workflow_runs": [
        _run(1, start),
        _run(2, datetime(2026, 11, 3, 23, 5, tzinfo=UTC)),  # next day 02:05
        _run(3, datetime(2026, 11, 4, 5, 0, tzinfo=UTC)),
        _run(4, datetime(2026, 11, 5, 0, 0, tzinfo=UTC)),  # last day no start in window
    ]}
    result = audit.analyze_runs(data, now=datetime(2026, 11, 5, 0, 0, tzinfo=UTC))
    assert result["windows"] == [("2026-11-04", 1), ("2026-11-05", 0)]


def test_live_audit_samples_steps_and_does_not_call_render(monkeypatch, capsys):
    now = datetime(2026, 11, 6, 6, 0, tzinfo=UTC)
    runs = {"workflow_runs": [_run(1, now - timedelta(minutes=5)), _run(2, now)]}
    calls = []

    def fake_gh(path):
        calls.append(path)
        if path.endswith("workflows/keepalive.yml"):
            return {"state": "active"}
        if "/workflows/" in path:
            return runs
        if "/runs/2/" in path:
            return _jobs("skipped")
        return _jobs("success")

    monkeypatch.setattr(audit, "gh_json", fake_gh)
    assert audit.main(["--repo", "owner/repo", "--now", now.isoformat()]) == 0
    output = capsys.readouterr().out
    assert "skipped=1" in output and "success=1" in output
    assert "HTTP ping" in output and "garanti değildir" in output
    assert len(calls) == 4 and all(call.startswith("repos/owner/repo/actions/") for call in calls)


@pytest.mark.parametrize("outcome", ["failure", "timed_out", "cancelled"])
def test_failed_ping_is_not_green_even_with_good_schedule(monkeypatch, outcome):
    now = datetime(2026, 11, 6, 6, 0, tzinfo=UTC)
    runs = {"workflow_runs": [_run(1, now - timedelta(minutes=5)), _run(2, now)]}
    monkeypatch.setattr(audit, "gh_json", lambda path: (
        {"state": "active"} if path.endswith("workflows/keepalive.yml") else
        runs if "/workflows/" in path else _jobs(outcome)))
    assert audit.main(["--now", now.isoformat()]) == 1


def test_missing_steps_or_metadata_are_inconclusive(monkeypatch, capsys):
    now = datetime(2026, 11, 6, 6, 0, tzinfo=UTC)
    runs = {"workflow_runs": [_run(1, now - timedelta(minutes=5)), _run(2, now)]}
    monkeypatch.setattr(audit, "gh_json", lambda path: (
        {"state": "active"} if path.endswith("workflows/keepalive.yml") else
        runs if "/workflows/" in path else {"jobs": []}))
    assert audit.main(["--now", now.isoformat()]) == 2
    assert "kanıt eksik" in capsys.readouterr().out.lower()


def test_offline_cadence_failure_and_unknown_state(tmp_path, capsys):
    import json

    now = datetime(2026, 11, 6, 6, 0, tzinfo=UTC)
    path = tmp_path / "runs.json"
    path.write_text(json.dumps({"workflow_runs": [_run(1, now - timedelta(hours=5)), _run(2, now)]}))
    assert audit.main(["--input", str(path), "--now", now.isoformat(), "--workflow-state", "active"]) == 1
    assert ">15 dk=1/1" in capsys.readouterr().out
    path.write_text(json.dumps({"workflow_runs": [_run(1, now - timedelta(minutes=5)), _run(2, now)]}))
    assert audit.main(["--input", str(path), "--now", now.isoformat()]) == 2


def test_audit_avoids_printing_raw_gh_error(monkeypatch, capsys):
    class Failed:
        returncode = 1
        stderr = "potential secret or signed URL"
        stdout = ""

    monkeypatch.setattr(audit.subprocess, "run", lambda *_args, **_kwargs: Failed())
    assert audit.main([]) == 2
    assert "potential secret" not in capsys.readouterr().err


def test_invalid_or_missing_timestamps_are_not_silently_green():
    now = datetime(2026, 11, 6, 6, 0, tzinfo=UTC)
    report = audit.analyze_runs({"workflow_runs": [_run(1, now), {"event": "schedule"}]}, now=now)
    assert report["invalid"] == 1 and len(report["selected"]) == 1
    assert audit.timestamp("2026-11-06T06:00:00") is None
