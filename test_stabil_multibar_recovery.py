"""Causal support recovery and surface contract (no replay performance claims)."""
from dataclasses import replace
from types import SimpleNamespace

from domain_engines.stabil import evaluate_bar_behaviors, summarize_symbol_for_command
from grafik.tarama import _stabil_verisi
from test_stabil_vertical_policy import make_series


def sample(follow_close=99.95, follow_open=99.8):
    labels, snapshots, points, frame = make_series(falling=False, extra=True)
    frame.loc[27, ["open", "high", "low", "close"]] = [99.0, 99.5, 98.8, 99.4]
    frame.loc[28, ["open", "high", "low", "close"]] = [99.3, 99.9, 99.2, 99.8]
    frame.loc[29, ["open", "high", "low", "close"]] = [99.8, 100.7, 99.7, 100.5]
    frame.loc[30, ["open", "high", "low", "close"]] = [follow_open, 100.1, 99.7, follow_close]
    return labels, snapshots, points, frame


def evaluate(frame, points, snapshots):
    return evaluate_bar_behaviors("TEST", "1d", frame, points, snapshots)


def test_confirmation_is_next_bar_only_even_if_close_below_support():
    labels, snapshots, points, frame = sample()
    full = evaluate(frame, points, snapshots)
    prefix = evaluate(frame.iloc[:30], points[:30], snapshots[:30])
    assert full[:30] == prefix
    assert full[29].reclaim_kind is None
    assert full[30].reclaim_kind == "multi_bar_recovery"
    assert full[30].close_price < full[30].support_level
    summary = summarize_symbol_for_command("TEST", SimpleNamespace(bar_behaviors=full))
    assert summary.reclaim_kind == "multi_bar_recovery"
    layer = _stabil_verisi({"stabil": SimpleNamespace(error=None, skipped=False, details={
        "bar_projection": points, "bar_behaviors": full})}, "1d", 0, len(points), list(labels))
    assert layer["reclaim_barlar"] == [30]


def test_red_or_doji_follow_does_not_confirm_and_cannot_confirm_later():
    for close in (99.7, 99.8):
        _, snapshots, points, frame = sample(follow_close=close)
        assert evaluate(frame, points, snapshots)[-1].reclaim_kind is None


def test_support_change_or_non_progressive_path_cancels():
    _, snapshots, points, frame = sample()
    points[30] = replace(points[30], support_level=99.0)
    assert evaluate(frame, points, snapshots)[-1].reclaim_kind is None
    _, snapshots, points, frame = sample()
    frame.loc[28, "close"] = 99.3
    assert evaluate(frame, points, snapshots)[-1].reclaim_kind is None


def test_old_snapshot_close_reclaim_is_not_projected_or_summarized():
    labels, snapshots, points, frame = sample()
    result = list(evaluate(frame, points, snapshots))
    result[-1] = replace(result[-1], reclaim_kind="close_reclaim", momentum_kind=None)
    layer = _stabil_verisi({"stabil": SimpleNamespace(error=None, skipped=False, details={
        "bar_projection": points, "bar_behaviors": result})}, "1d", 0, len(points), list(labels))
    assert not layer["reclaim_barlar"]
    assert summarize_symbol_for_command("TEST", SimpleNamespace(bar_behaviors=result)).reclaim_kind is None


def test_alarm_uses_same_known_market_and_pattern_context(tmp_path, monkeypatch):
    import config
    import bot.stabil_service as service
    from test_stabil_structure_context import event
    _, snapshots, points, frame = sample()
    behavior = evaluate(frame, points, snapshots)[-1]
    frame.index = __import__("pandas").date_range("2026-09-01", periods=len(frame), freq="4h", tz="UTC")
    now = frame.index[-1].to_pydatetime()
    monkeypatch.setattr(config, "STABIL_GERI_ALIM_ALARM", True)
    monkeypatch.setattr(config, "STABIL_ALARM_PUBLIC", False)
    monkeypatch.setattr(service, "tamamlanmis_mumlar", lambda f, *_a, **_k: f)
    monkeypatch.setattr(service, "bar_kapandi_mi", lambda *_a, **_k: True)
    monkeypatch.setattr(service, "mum_kapanis_ani", lambda *_a: now)
    result = SimpleNamespace(error=None, result=SimpleNamespace(latest_behavior=behavior))
    per_tf = {"stabil": result}
    args = ("ASTOR", {"4h": frame, "1d": frame}, now)
    def candidate(**kwargs):
        return service.evaluate_stabil_4h_candidate(*args,
            domain_results_by_stock={"ASTOR": {"4h": per_tf}},
            state_path=str(tmp_path / "state.json"), **kwargs)
    assert candidate() is not None
    per_tf["market_structure"] = SimpleNamespace(details={"event_history": [event(frame.index[-2], "DOWN")]})
    assert candidate() is None
    per_tf.pop("market_structure")
    pattern = {"state": "ADAY", "bar_time": str(frame.index[-1]), "upper": behavior.close_price + .1}
    assert candidate(pattern_snapshot=pattern) is None
    pattern["bar_time"] = str(frame.index[-2])
    assert candidate(pattern_snapshot=pattern) is not None


def test_dispatch_refuses_legacy_candidate(tmp_path):
    from bot.stabil_service import dispatch_stabil_scan_candidates
    candidate = SimpleNamespace(behavior=SimpleNamespace(reclaim_kind="close_reclaim"))
    assert dispatch_stabil_scan_candidates([candidate], None, state_path=str(tmp_path / "s.json")) == {
        "aday": 0, "tekil_gonderilen": 0, "toplu_ozet": 0}


def test_scan_updates_delivered_status_during_cooldown(tmp_path, monkeypatch):
    import json
    import pandas as pd
    import config
    import bot.stabil_service as service
    from test_stabil_structure_context import event
    _, snapshots, points, frame = sample(follow_close=99.7)
    behavior = evaluate(frame, points, snapshots)[-1]
    frame.index = pd.date_range("2026-09-01", periods=len(frame), freq="4h", tz="UTC")
    now = frame.index[-1].to_pydatetime()
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({"version": 1, "symbols": {"ASTOR": {
        "last_bar_open": frame.index[-2].isoformat(), "kind": "multi_bar_recovery"}}}))
    monkeypatch.setattr(config, "STABIL_GERI_ALIM_ALARM", True)
    monkeypatch.setattr(service, "tamamlanmis_mumlar", lambda f, *_a, **_k: f)
    monkeypatch.setattr(service, "bar_kapandi_mi", lambda *_a, **_k: True)
    monkeypatch.setattr(service, "mum_kapanis_ani", lambda *_a: now)
    result = SimpleNamespace(error=None, result=SimpleNamespace(latest_behavior=behavior))
    ms = SimpleNamespace(details={"event_history": [event(frame.index[-1], "DOWN")]})
    cancelled = []
    notifier = SimpleNamespace(stabil_bekleyen_iptal=lambda event_id: cancelled.append(event_id))
    candidate = service.evaluate_stabil_4h_candidate(
        "ASTOR", {"4h": frame, "1d": frame}, now,
        domain_results_by_stock={"ASTOR": {"4h": {"stabil": result, "market_structure": ms}}},
        state_path=str(state_path), notifier=notifier)
    assert candidate is None
    assert json.loads(state_path.read_text())["symbols"]["ASTOR"]["signal_status"] == "invalidated_by_opposite_bos"
    from public_aux_outbox import auxiliary_event_id
    assert cancelled == [auxiliary_event_id("stabil", [("ASTOR", frame.index[-2].isoformat())])]


def test_new_recovery_alert_does_not_claim_old_replay_rates_or_above_support():
    from bot.stabil_service import StabilAlarmCandidate, format_stabil_reclaim_alert_card, format_stabil_burst_summary_card
    _, snapshots, points, frame = sample()
    behavior = evaluate(frame, points, snapshots)[-1]
    candidate = StabilAlarmCandidate(symbol="TEST", bar_open_ts="2026-01-01", bar_close_ts="2026-01-01",
        bar_label="test", close_price=behavior.close_price, support_level=behavior.support_level,
        behavior=behavior, card_lines=("Stabil yapı: çok mumlu toparlanma",))
    text = format_stabil_reclaim_alert_card(candidate)
    assert "%91,5" not in text and "+0,26 ATR" not in text
    summary = format_stabil_burst_summary_card([candidate])
    assert "-%" in summary and "destek üstüne güçlü dönen" not in summary
