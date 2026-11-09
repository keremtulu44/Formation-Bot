from types import SimpleNamespace
import pandas as pd
from domain_engines.stabil.structure_context import events_for_bars, marker_state


def event(t, direction, kind="BOS", **kw):
    return SimpleNamespace(scope="EXTERNAL", event_type=kind, direction=direction,
                           confirmed_at=t, confirmation_status="CONFIRMED", **kw)


def test_tf_windows_and_repair_are_causal():
    times = pd.date_range("2026-01-01", periods=20, freq="h", tz="UTC")
    result = SimpleNamespace(details={"event_history": [event(times[4], "DOWN"), event(times[8], "UP")]})
    events = events_for_bars(result, times)
    assert marker_state(7, "UP", "4h", events, 7) == "opposite_structure"
    assert marker_state(7, "UP", "1d", events, 7) == "active"
    assert marker_state(8, "UP", "4h", events, 8) == "active"
    assert marker_state(4, "UP", "4h", events, 4) == "opposite_structure"


def test_later_bos_only_changes_status_after_it_occurs():
    events = [(6, "BOS", "DOWN")]
    assert marker_state(5, "UP", "4h", events, 5) == "active"
    assert marker_state(5, "UP", "4h", events, 6) == "invalidated_by_opposite_bos"
    assert marker_state(2, "UP", "4h", events, 6) == "active"
    assert marker_state(5, "UP", "4h", [(6, "CHOCH", "DOWN")], 6) == "active"


def test_missing_timestamp_and_conflicting_events_do_not_guess():
    times = pd.date_range("2026-01-01", periods=10, freq="h", tz="UTC")
    result = SimpleNamespace(details={"event_history": [event(times[3], "DOWN"), event(times[3], "UP"),
                                                         event(times[-1] + pd.Timedelta(hours=1), "DOWN")]})
    events = events_for_bars(result, times)
    assert len(events) == 2
    assert marker_state(4, "UP", "4h", events, 4) == "active"


def test_chart_suppresses_near_corridor_and_causal_bos(monkeypatch):
    import grafik.tarama as tarama
    times = pd.date_range("2026-01-01", periods=20, freq="h", tz="UTC")
    frame = pd.DataFrame({"open": [100.] * 20, "high": [101.] * 20,
                          "low": [99.] * 20, "close": [100.] * 20,
                          "volume": [100.] * 20}, index=times)
    monkeypatch.setattr(tarama, "_bar_kapandi_mi", lambda *_a, **_k: True)
    monkeypatch.setattr(tarama, "_stabil_verisi", lambda *_a: {
        "hazir": True, "seviyeler": [99.] * 20, "renkler": ["ust"] * 20,
        "reclaim_barlar": [17, 19], "momentum_barlar": []})
    monkeypatch.setattr(tarama, "_stabil_direnc_verisi", lambda *_a: {
        "hazir": True, "seviyeler": [102.] * 19 + [100.4], "renkler": ["alt"] * 20,
        "donus_barlar": [], "momentum_barlar": []})
    ms = SimpleNamespace(details={"event_history": [event(times[18], "DOWN")]})
    image = tarama.anlik_goruntu(None, "1h", frame, sonuclar={"market_structure": ms})
    assert image["stabil"]["reclaim_barlar"] == []
    reasons = {x["bar"]: x["neden"] for x in image["stabil"]["baglam_bastirilan"]}
    assert reasons == {17: "invalidated_by_opposite_bos", 19: "opposite_structure"}
    image = tarama.anlik_goruntu(None, "1h", frame, sonuclar={})
    assert image["stabil"]["reclaim_barlar"] == [17]
    assert image["stabil"]["baglam_bastirilan"] == [
        {"bar": 19, "tur": "reclaim_barlar", "neden": "stabil_koridoru"}]


def test_pattern_boundary_only_applies_at_current_snapshot(monkeypatch):
    import grafik.tarama as tarama
    times = pd.date_range("2026-01-01", periods=20, freq="h", tz="UTC")
    frame = pd.DataFrame({"open": [100.] * 20, "high": [101.] * 20,
                          "low": [99.] * 20, "close": [100.] * 20,
                          "volume": [100.] * 20}, index=times)
    monkeypatch.setattr(tarama, "_bar_kapandi_mi", lambda *_a, **_k: True)
    monkeypatch.setattr(tarama, "_stabil_verisi", lambda *_a: {
        "hazir": True, "seviyeler": [99.] * 20, "renkler": ["ust"] * 20,
        "reclaim_barlar": [17, 19], "momentum_barlar": []})
    monkeypatch.setattr(tarama, "_stabil_direnc_verisi", lambda *_a: None)
    image = tarama.anlik_goruntu({"state": "ADAY", "upper_now": 100.4}, "1h", frame)
    assert image["stabil"]["reclaim_barlar"] == [17]
    assert image["stabil"]["baglam_bastirilan"][0]["neden"] == "formasyon_siniri"


def test_command_ignores_stale_cache_and_applies_confirmed_structure(monkeypatch):
    from types import SimpleNamespace
    import domain_engines.runner as runner
    from bot.stabil_service import _command_structure_context
    from test_stabil_multibar_recovery import sample, evaluate
    from domain_engines.stabil import summarize_symbol_for_command
    _, snapshots, points, frame = sample()
    bhvs = evaluate(frame, points, snapshots)
    bhv = bhvs[-1]
    summary = summarize_symbol_for_command("TEST", SimpleNamespace(bar_behaviors=bhvs))
    frame.index = pd.date_range("2026-01-01", periods=len(frame), freq="h", tz="UTC")
    record = SimpleNamespace(result=SimpleNamespace(timestamp=frame.index[-1]),
        details={"event_history": [event(frame.index[-2], "DOWN")]})
    monkeypatch.setattr(runner, "get_latest_domain_results", lambda *_: {"market_structure": record})
    changed_bhv, changed_summary = _command_structure_context("TEST", "4h", frame, bhv, summary)
    assert changed_bhv.reclaim_kind is None and changed_summary.bucket == "notr"
    record.result.timestamp = frame.index[-2]
    assert _command_structure_context("TEST", "4h", frame, bhv, summary) == (bhv, summary)


def test_command_pattern_context_uses_only_same_bar():
    from bot.stabil_service import _command_barrier_context
    from test_stabil_multibar_recovery import sample, evaluate
    from domain_engines.stabil import summarize_symbol_for_command
    _, snapshots, points, frame = sample()
    behavior = evaluate(frame, points, snapshots)[-1]
    summary = summarize_symbol_for_command("TEST", SimpleNamespace(bar_behaviors=evaluate(frame, points, snapshots)))
    frame.index = pd.date_range("2026-01-01", periods=len(frame), freq="h", tz="UTC")
    manager = SimpleNamespace(to_gunluk_dataframe=lambda _: None, to_dataframe=lambda _: None)
    pattern = {"stock": "TEST", "timeframe": "4h", "state": "ADAY",
               "bar_time": str(frame.index[-1]), "upper": behavior.close_price + 0.1}
    bhv, result = _command_barrier_context("TEST", "4h", frame, behavior, summary, manager,
                                            frame.index[-1], [pattern])
    assert bhv.reclaim_kind is None and result.bucket == "notr"
    pattern["bar_time"] = str(frame.index[-2])
    assert _command_barrier_context("TEST", "4h", frame, behavior, summary, manager,
                                    frame.index[-1], [pattern]) == (behavior, summary)


def test_delivered_alert_status_changes_only_when_later_bos_is_known():
    from bot.stabil_service import _update_sent_stabil_status
    times = pd.date_range("2026-01-01", periods=8, freq="h", tz="UTC")
    frame = pd.DataFrame(index=times)
    state = {"symbols": {"TEST": {"last_bar_open": times[4].isoformat(), "kind": "multi_bar_recovery"}}}
    ms = SimpleNamespace(details={"event_history": [event(times[6], "DOWN")]})
    assert not _update_sent_stabil_status(state, "TEST", frame.iloc[:6], ms)
    assert _update_sent_stabil_status(state, "TEST", frame.iloc[:7], ms)
    item = state["symbols"]["TEST"]
    assert item["signal_status"] == "invalidated_by_opposite_bos"
    assert item["invalidated_bar_open"] == times[6].isoformat()
    assert not _update_sent_stabil_status(state, "TEST", frame, ms)


def test_failed_choch_repairs_only_from_transition_failure_bar():
    times = pd.date_range("2026-01-01", periods=6, freq="h", tz="UTC")
    history = [event(times[1], "DOWN", "CHOCH", validity="FAILED"),
               event(times[3], "UP", "TRANSITION_FAIL")]
    events = events_for_bars(SimpleNamespace(details={"event_history": history}), times)
    assert marker_state(2, "UP", "4h", events, 2) == "opposite_structure"
    assert marker_state(3, "UP", "4h", events, 3) == "active"


def test_native_pattern_candidate_boundary_and_invalidation(monkeypatch):
    import grafik.tarama as tarama
    from patterns.candidate import PatternCandidate
    times = pd.date_range("2026-01-01", periods=20, freq="h", tz="UTC")
    frame = pd.DataFrame({"open": [100.] * 20, "high": [101.] * 20,
                          "low": [99.] * 20, "close": [100.] * 20,
                          "volume": [100.] * 20}, index=times)
    monkeypatch.setattr(tarama, "_bar_kapandi_mi", lambda *_a, **_k: True)
    monkeypatch.setattr(tarama, "_stabil_verisi", lambda *_a: {
        "hazir": True, "seviyeler": [99.] * 20, "renkler": ["ust"] * 20,
        "reclaim_barlar": [19], "momentum_barlar": []})
    monkeypatch.setattr(tarama, "_stabil_direnc_verisi", lambda *_a: None)
    candidate = PatternCandidate(valid=True, pattern_type="test", upper_now=100.4)
    image = tarama.anlik_goruntu(candidate, "1h", frame, alarm_turu="aday")
    assert image["stabil"]["reclaim_barlar"] == []
    image = tarama.anlik_goruntu(candidate, "1h", frame, alarm_turu="gecersiz")
    assert image["stabil"]["reclaim_barlar"] == [19]


def test_real_card_surfaces_apply_aligned_opposite_structure():
    from test_stabil_multibar_recovery import sample, evaluate
    from notification_context import _kart_stabil
    from bot.domain_alarm_service import _stabil_bilgisi
    labels, snapshots, points, frame = sample()
    frame.index = labels
    behavior = evaluate(frame, points, snapshots)[-1]
    output = SimpleNamespace(latest_behavior=behavior, bar_projection=points)
    stabil = SimpleNamespace(error=None, skipped=False, result=output,
                             details={"latest_behavior": behavior, "bar_projection": points})
    market = SimpleNamespace(details={"event_history": [event(labels[-2], "DOWN")]})
    results = {"1d": {"stabil": stabil, "market_structure": market}}
    assert any("toparlanma" in s for s in _kart_stabil({"1d": {"stabil": stabil}}, "1d", behavior.close_price))
    assert not any("toparlanma" in s for s in _kart_stabil(results, "1d", behavior.close_price))
    assert not any("toparlanma" in s for s in _stabil_bilgisi(results, "1d", frame)["card_lines"])
    assert behavior.reclaim_kind == "multi_bar_recovery"  # raw lifecycle is unchanged


def test_later_bos_renders_original_arrow_as_faded_not_new_diamond(monkeypatch):
    import grafik.tarama as tarama
    from grafik.render import _stabil_ciz
    from matplotlib.figure import Figure
    times = pd.date_range("2026-01-01", periods=20, freq="h", tz="UTC")
    frame = pd.DataFrame({"open": [100.] * 20, "high": [101.] * 20,
                          "low": [99.] * 20, "close": [100.] * 20,
                          "volume": [100.] * 20}, index=times)
    monkeypatch.setattr(tarama, "_bar_kapandi_mi", lambda *_a, **_k: True)
    monkeypatch.setattr(tarama, "_stabil_verisi", lambda *_a: {
        "hazir": True, "seviyeler": [99.] * 20, "renkler": ["ust"] * 20,
        "reclaim_barlar": [17], "momentum_barlar": []})
    monkeypatch.setattr(tarama, "_stabil_direnc_verisi", lambda *_a: None)
    ms = SimpleNamespace(details={"event_history": [event(times[18], "DOWN")]})
    image = tarama.anlik_goruntu(None, "1h", frame, sonuclar={"market_structure": ms})
    assert image["stabil"]["iptal_barlar"] == [17]
    ax = Figure().subplots()
    meta = _stabil_ciz(ax, image, 20, (95, 105), dusuk=[99.] * 20, yuksek=[101.] * 20)
    assert meta["iptal_isaret"] == 1 and meta["reclaim_isaret"] == 0
    assert any(c.get_gid() == "grafik-stabil-iptal" for c in ax.collections)
    assert not any(c.get_gid() == "grafik-stabil-dikey-deneme" for c in ax.collections)
