from pathlib import Path

import pandas as pd
import pytest

from ai_prompt import build_from_frames, build_from_local_cache, render_prompt
from ai_prompt.builder import _clean_frame, _research, _fvg_status, _matching_zone

ROOT = Path(__file__).resolve().parent
CUT = "2026-09-25T18:30:00+03:00"


def hourly_for(symbol):
    frame = pd.read_json(ROOT / "bot_data" / f"{symbol}.json")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert("Europe/Istanbul")
    return frame.set_index("timestamp")


@pytest.fixture(scope="module")
def bimas():
    return build_from_local_cache("BIMAS", as_of=CUT, data_dir=str(ROOT / "bot_data"), research_mode="retrospective")


@pytest.fixture(scope="module")
def petkm():
    return build_from_local_cache("PETKM", as_of=CUT, data_dir=str(ROOT / "bot_data"), research_mode="retrospective")


def test_four_timeframes_and_no_false_alarm(bimas):
    assert list(bimas["timeframes"]) == ["1h", "2h", "4h", "1d"]
    assert [bimas["timeframes"][tf]["bars"] for tf in ("1h", "2h", "4h", "1d")] == [360, 200, 120, 40]
    assert all(bimas["timeframes"][tf]["last_close"] == pytest.approx(426.25) for tf in bimas["timeframes"])
    assert "alarm doğrulanmadı" in render_prompt(bimas)
    assert bimas["timeframes"]["1h"]["fvg"]["status"].startswith("çalıştırılmadı")
    assert bimas["timeframes"]["2h"]["fvg"]["status"].startswith("çalıştırılmadı")
    assert bimas["timeframes"]["4h"]["fvg"]["bull_count"] == 0


def test_pattern_direction_is_candidate_not_confirmed(bimas):
    p = bimas["timeframes"]["1h"]["pattern"]
    assert p["type"] == "Yükselen Kama"
    assert p["state"] == "KIRILIM_ADAYI"
    assert p["break_direction"] == "aşağı"
    assert p["break_boundary"] == pytest.approx(427.8)
    assert p["break_bar_open"].startswith("2026-09-25T16:30")


def test_market_structure_scope_and_chronology(bimas):
    ms = bimas["timeframes"]["4h"]["market_structure"]
    assert ms["scopes"]["dış"]["state"] == "aşağı geçişte"
    assert ms["scopes"]["iç"]["state"] == "aşağı yönlü"
    assert [e["bar_open"] for e in ms["events"]] == sorted(e["bar_open"] for e in ms["events"])
    assert any(e["scope"] == "iç" and e["type"] == "BOS" and e["level"] == 429 for e in ms["events"])
    assert bimas["timeframes"]["1d"]["market_structure"]["scopes"]["dış"]["state"] == "yukarı yönlü"


def test_replay_actual_episodes_closes_and_no_future(bimas):
    rows = bimas["timeframes"]["4h"]["replay"]["zones"]
    pos = next(z for z in rows if z["direction"] == "pozitif" and z["lower"] == 410.75)
    neg = next(z for z in rows if z["direction"] == "negatif")
    assert neg["episodes"] == 0
    assert pos["episodes"] == 2
    assert [r["close"] for r in pos["recent_episodes"][1]["closes"]] == [422.0, 426.25]
    assert pos["recent_episodes"][1]["next_bar_close"] is None
    assert pos["recent_episodes"][1]["ongoing_at_cut"]
    assert pos["recent_episodes"][0]["next_bar_close"]["close"] == 428.25


def test_fvg_native_singleton_is_counted_and_birth_atr_matches_research(petkm):
    row = petkm["timeframes"]["4h"]
    assert row["fvg"]["bear_count"] == 1
    z = next(z for z in row["replay"]["zones"] if z["family"] == "FVG")
    assert z["replay_status"] == "ok" and z["episodes"] == 0
    assert z["birth_atr"] > 0
    assert z["width_atr_birth"] == pytest.approx((z["upper"] - z["lower"]) / z["birth_atr"])


def test_research_fixed_sections_and_cutoff(bimas):
    retrospective = render_prompt(bimas)
    assert "ob-temas-2026-10-21" in retrospective
    assert "fvg-atr-2026-10-21" not in retrospective  # no daily FVG on main chart
    assert all(x["included"] for x in bimas["research"])
    assert "kesit sonrası/belirsiz" in retrospective
    strict = _research(pd.Timestamp(CUT), "strict")
    assert len(strict) == 5 and not any(item["included"] for item in strict)
    later = _research(pd.Timestamp("2026-11-22T12:00:00+03:00"), "strict")
    assert sum(item["included"] for item in later) == 3
    assert not next(item for item in later if item["id"].startswith("stabil"))["included"]


def test_future_hours_and_daily_do_not_change_historical_packet():
    hourly = hourly_for("BIMAS")
    asof = pd.Timestamp("2026-09-24T14:15:00+03:00")
    past_only = _clean_frame(hourly, "1h", asof)
    modified = hourly.copy()
    future_mask = modified.index >= pd.Timestamp("2026-09-24T13:30:00+03:00")
    modified.loc[future_mask, ["open", "high", "low", "close"]] *= 3
    modified.loc[future_mask, "volume"] *= 10
    a = build_from_frames("BIMAS", past_only, as_of=asof)
    b = build_from_frames("BIMAS", modified, as_of=asof)
    assert a == b
    assert render_prompt(a) == render_prompt(b)
    assert pd.Timestamp(a["timeframes"]["1h"]["last_close_time"]) <= asof
    assert pd.Timestamp(a["timeframes"]["4h"]["last_close_time"]) <= asof


def test_closed_daily_does_not_peek_inside_session():
    frame = hourly_for("BIMAS")
    from data import resample_ohlcv
    daily = resample_ohlcv(frame, "1d")
    before_close = _clean_frame(daily, "1d", pd.Timestamp("2026-09-25T18:00:00+03:00"))
    at_close = _clean_frame(daily, "1d", pd.Timestamp("2026-09-25T18:30:00+03:00"))
    assert before_close.index[-1].date().isoformat() == "2026-09-24"
    assert at_close.index[-1].date().isoformat() == "2026-09-25"


def test_reject_bad_timestamps_ohlcv_and_explicit_unknown_flags():
    frame = hourly_for("BIMAS").tail(30)
    cutoff = pd.Timestamp(CUT)
    with pytest.raises(ValueError, match="tekrarlı"):
        _clean_frame(pd.concat([frame, frame.tail(1)]), "1h", cutoff)
    invalid = frame.copy(); invalid.iloc[-1, invalid.columns.get_loc("high")] = 0
    with pytest.raises(ValueError, match="OHLCV"):
        _clean_frame(invalid, "1h", cutoff)
    incomplete = frame.copy(); incomplete["is_complete"] = True; incomplete.iloc[-1, incomplete.columns.get_loc("is_complete")] = False
    with pytest.raises(ValueError, match="tamamlanmamış"):
        _clean_frame(incomplete, "1h", cutoff)
    with pytest.raises(ValueError, match="zaman dilimli"):
        build_from_frames("BIMAS", frame, as_of="2026-09-25 18:30")


def test_zone_ambiguity_and_error_are_not_zero_contacts():
    from types import SimpleNamespace
    failed = _fvg_status(SimpleNamespace(error="broken", skipped=False))
    assert failed["status"].startswith("hesaplama hatası")
    display = {"direction": "pozitif", "lower": 1.0, "upper": 2.0, "source_index": 1}
    assert _matching_zone(display, []) is None


def test_no_network_and_symbol_path_validation(monkeypatch):
    import socket
    def no_connect(*args, **kwargs):
        raise AssertionError("Yerel prompt üretimi ağ kullanamaz")
    monkeypatch.setattr(socket.socket, "connect", no_connect)
    packet = build_from_local_cache("ALARK", as_of=CUT, data_dir=str(ROOT / "bot_data"))
    assert packet["symbol"] == "ALARK"
    with pytest.raises(ValueError, match="sembol"):
        build_from_local_cache("../BIMAS", as_of=CUT, data_dir=str(ROOT / "bot_data"))


def test_historical_daily_future_isolation():
    from data import resample_ohlcv
    hourly = hourly_for("BIMAS")
    daily = resample_ohlcv(hourly, "1d")
    cutoff = pd.Timestamp("2026-09-24T14:15:00+03:00")
    changed = daily.copy()
    changed.loc[changed.index >= cutoff.normalize(), ["open", "high", "low", "close"]] *= 3
    changed.loc[changed.index >= cutoff.normalize(), "volume"] *= 10
    p1 = build_from_frames("BIMAS", hourly, daily=daily, as_of=cutoff)
    p2 = build_from_frames("BIMAS", hourly, daily=changed, as_of=cutoff)
    assert p1 == p2


def test_no_peek_during_intraday_kova_and_detect_stale():
    hourly = hourly_for("BIMAS")
    cutoff = pd.Timestamp("2026-09-25T12:35:00+03:00")
    p = build_from_frames("BIMAS", hourly, as_of=cutoff)
    assert pd.Timestamp(p["timeframes"]["4h"]["last_close_time"]) <= cutoff
    assert pd.Timestamp(p["timeframes"]["4h"]["last_open"]).date() < cutoff.date()
    stale = build_from_frames("BIMAS", hourly, as_of="2026-10-01T18:30:00+03:00")
    assert stale["timeframes"]["1h"]["expected_delay_minutes"] > 0
    assert "Veri gecikmesi" in render_prompt(stale)


def test_reject_incomplete_bar_even_if_close_time_has_passed():
    df = hourly_for("BIMAS").tail(20).copy()
    df["is_closed"] = pd.Series(True, index=df.index, dtype=object)
    df.iloc[-1, df.columns.get_loc("is_closed")] = None
    with pytest.raises(ValueError, match="tamamlanmamış"):
        _clean_frame(df, "1h", pd.Timestamp(CUT))


def test_mismatched_replay_does_not_become_zero_contacts(bimas, monkeypatch):
    from ai_prompt import builder
    monkeypatch.setattr(builder, "replay_ob_zones", lambda *args: [])
    frame = hourly_for("BIMAS")
    z = {"family": "OB", "direction": "pozitif", "lower": 410.75, "upper": 423.5,
         "source_open": None, "source_index": 1, "terminal": False, "state": "?"}
    from types import SimpleNamespace
    domain = SimpleNamespace(error=None, skipped=False)
    result = builder._replay("BIMAS", "1h", frame, [z], {"order_block": domain})
    assert result["zones"][0]["episodes"] is None
    assert "eşleşmedi" in result["zones"][0]["replay_status"]


def test_strict_same_report_date_is_not_assumed_published():
    result = _research(pd.Timestamp("2026-10-21T23:59:00+03:00"), "strict")
    assert not next(x for x in result if x["id"].startswith("ob-temas"))["included"]


def test_chart_events_are_chronological_and_unrendered_native_events_are_omitted(bimas):
    prompt = render_prompt(bimas)
    assert "SWEEP" not in prompt and "geçiş başarısızlığı" not in prompt
    for tf, row in bimas["timeframes"].items():
        events = row["chart_events"]
        assert [e["bar_open"] for e in events] == sorted(e["bar_open"] for e in events)
        assert all(e["type"] in {"BOS", "CHoCH"} for e in events)


def test_quality_warning_and_explicit_absence_of_stabil_replay(bimas):
    assert "STABİL GÜNLÜK DESTEK REPLAY" in render_prompt(bimas)
    assert "4s temas veya ret teyidi değildir" in render_prompt(bimas)
    assert bimas["quality_notes"] == []


def test_untrusted_json_is_not_silently_cleaned(tmp_path):
    import json
    rows = hourly_for("BIMAS").tail(10).reset_index()
    rows.loc[rows.index[1], "high"] = -1.0
    rows["timestamp"] = rows["timestamp"].map(lambda t: t.isoformat())
    (tmp_path / "BIMAS.json").write_text(json.dumps(rows.to_dict("records")), encoding="utf-8")
    with pytest.raises(ValueError, match="OHLCV"):
        build_from_local_cache("BIMAS", as_of=CUT, data_dir=str(tmp_path))


def test_macro_session_is_not_silently_treated_as_bist():
    with pytest.raises(ValueError, match="yalnız BIST"):
        build_from_frames("XAUUSD", hourly_for("BIMAS"), as_of=CUT)


def test_isolated_build_does_not_change_live_latest_registry():
    from domain_engines.runner import get_all_latest_domain_results
    before = get_all_latest_domain_results()
    build_from_local_cache("BIMAS", as_of=CUT, data_dir=str(ROOT / "bot_data"))
    assert get_all_latest_domain_results() == before


def test_cli_does_not_overwrite_existing_output(tmp_path):
    import os
    import subprocess
    import sys
    target = tmp_path / "already.txt"
    target.write_text("önemli veri", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "scripts/diagnostics/ai_prompt_sample.py", "BIMAS", "--as-of", CUT,
         "--output", str(target)], cwd=ROOT, capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(ROOT)}, timeout=60,
    )
    assert result.returncode == 2
    assert "üzerine yazılmaz" in result.stderr
    assert target.read_text(encoding="utf-8") == "önemli veri"


def test_zone_selection_balances_directions_and_fvg_by_edge_distance():
    from types import SimpleNamespace
    from ai_prompt.builder import _zones
    ok = SimpleNamespace(error=None, skipped=False)
    results = {"order_block": ok, "fvg": ok}
    def zone(kind, direction, lower, upper, index, status=None):
        return {"tip": kind, "yon": direction, "alt": lower, "ust": upper,
                "kaynak": index, "zaman": f"2026-09-{index:02d}T09:30:00+03:00", "durum": status}
    zones = [zone("ob", -1, 108, 110, 1), zone("ob", -1, 102, 103, 2),
             zone("ob", 1, 90, 95, 3), zone("fvg", -1, 101, 102, 4),
             zone("fvg", 1, 100, 101, 5, "FULL_FILL")]
    selected = _zones({"son_kapanis": 100, "zone": {"cizilen": zones}}, results, limit=3)
    assert {z["source_index"] for z in selected} == {2, 3, 4}
    assert not any(z["terminal"] or "distance" in z for z in selected)
    assert selected[0]["source_index"] == 4
    # Missing price is safe and deterministic, no infinite values in packet.
    assert len(_zones({"zone": {"cizilen": zones}}, results, limit=3)) == 3
    assert len(_zones({"zone": {"cizilen": zones}}, results)) == 5


def test_zone_selection_does_not_reserve_terminal_over_active():
    from types import SimpleNamespace
    from ai_prompt.builder import _zones, _render_zone
    ok = SimpleNamespace(error=None, skipped=False)
    def zone(index, direction, status):
        return {"tip": "ob", "yon": direction, "alt": index, "ust": index + 1,
                "kaynak": index, "zaman": None, "durum": status}
    view = {"son_kapanis": 10, "zone": {"cizilen": [zone(1, 1, "FULL_FILL"),
            zone(9, -1, "ACTIVE"), zone(7, -1, "ACTIVE"), zone(5, -1, "ACTIVE")]}}
    chosen = _zones(view, {"order_block": ok}, limit=3)
    assert len(chosen) == 3 and all(not z["terminal"] for z in chosen)
    terminal = _zones({"son_kapanis": 10, "zone": {"cizilen": [zone(1, 1, "FULL_FILL")]}}, {"order_block": ok})[0]
    assert terminal["terminal"] and "geçmiş/terminal kayıt" in _render_zone(terminal)


def test_current_events_transition_fail_and_historical_fallback():
    from types import SimpleNamespace as N
    from ai_prompt.builder import _ms, _render_event
    def event(n, scope, kind, relevance):
        return N(event_type=kind, scope=scope, relevance=relevance,
                 confirmed_at=pd.Timestamp(f"2026-09-{n:02d}T09:30:00+03:00"), event_uid=str(n),
                 direction=1, broken_level=10, confirmation_status="CONFIRMED", validity="VALID", outcome="OBSERVED")
    events = [event(1, "EXTERNAL", "EVENT_BOS", "CURRENT"),
              event(2, "EXTERNAL", "EVENT_CHOCH", "HISTORICAL"),
              event(3, "INTERNAL", "EVENT_CHOCH", "HISTORICAL"),
              event(4, "INTERNAL", "EVENT_TRANSITION_FAIL", "CURRENT"),
              event(5, "EXTERNAL", "EVENT_SWEEP", "CURRENT")]
    result = N(error=None, skipped=False, export=N(external_scope=None, internal_scope=None, events=events))
    selected = _ms(result)["events"]
    assert [e["type"] for e in selected] == ["BOS", "CHOCH", "TRANSITION_FAIL", "SWEEP"]
    assert selected[1]["relevance"] == "HISTORICAL"
    assert "olay yönü yukarı" in _render_event(selected[2])


def test_render_main_replay_and_translate_known_states_without_hiding_unknowns(bimas):
    from ai_prompt.builder import _label, STABIL_LABELS, _VOLUME_STATE_LABELS
    prompt = render_prompt(bimas)
    assert "4H REPLAY" in prompt and "1H REPLAY" not in prompt
    assert "aşağı geçiş başarısız" not in prompt
    assert "haftalık=hazır değil" not in prompt
    assert "kalite PARTICIPATION_" not in prompt
    assert "ob-temas-2026-10-21" in prompt
    assert _label(STABIL_LABELS, "UNKNOWN_FUTURE_STATE") == "UNKNOWN_FUTURE_STATE"
    assert _VOLUME_STATE_LABELS["PARTICIPATION_UP_CANDIDATE"] == "yukarı katılım adayı"
    assert _VOLUME_STATE_LABELS["PARTICIPATION_UP_CONFIRMED"] == "yukarı katılım teyitli"


def test_replay_render_follows_selected_main_tf(bimas):
    packet = {**bimas, "main_tf": "1h"}
    prompt = render_prompt(packet)
    assert "1H REPLAY" in prompt and "4H REPLAY" not in prompt


def test_fvg_candidates_are_not_active_and_unknown_is_not_zero():
    from types import SimpleNamespace as N
    from domain_engines.fvg.fvg_engulfing_models import FvgState
    result = N(error=None, skipped=False, data_quality="OK", details={
        "active_bullish_fvg": N(state=FvgState.CANDIDATE),
        "active_bearish_fvg": [N(state=FvgState.ACTIVE), N(state=FvgState.FIRST_TEST), N(state=None)],
    })
    state = _fvg_status(result)
    assert state["bull_count"] == 0 and state["bull_candidates"] == 1
    assert state["bear_count"] == 2 and state["bear_unknown"] == 1
    result.details.pop("active_bearish_fvg")
    assert "bilinmiyor" in _fvg_status(result)["status"]


def test_small_values_do_not_collapse_and_width_bucket_is_not_rounded():
    from ai_prompt.builder import _fmt, _matching_zone
    from research.olcum import yukseklik_kovasi
    assert _fmt(0.000042) == "0,000042"
    assert _fmt(0.000043) != _fmt(0.000042)
    assert yukseklik_kovasi(0.4999999) == "0-0.5"
    assert yukseklik_kovasi(0.5) == "0.5-1"
    assert yukseklik_kovasi(1.9999999) == "1-2"
    assert yukseklik_kovasi(2.0) == ">=2"
    display = {"direction": "pozitif", "lower": 0.00004, "upper": 0.00005, "source_index": 1}
    different = {"active_at_asof": True, "direction": "bullish", "origin_index": 1,
                 "zone_lower": 0.000041, "zone_upper": 0.000051}
    assert _matching_zone(display, [different]) is None


def test_stabil_daily_replay_research_rule_and_no_future():
    from types import SimpleNamespace as N
    from ai_prompt.stabil_replay import daily_support_replay
    def obs(day, ident, low, high, close, atr=10):
        return N(timestamp=pd.Timestamp(f"2026-09-{day:02d}T18:30:00+03:00"),
                 support_identity=ident, support_available_at=pd.Timestamp("2026-09-02T18:30:00+03:00"),
                 low=low, high=high, close=close, atr=atr)
    def snap(close, support=100):
        return N(support_level=support, close_below_support=close < support)
    # First identity unknown: it must never be reported as a complete count.
    old = obs(1, ("old",), 100, 102, 101)
    data = [old, obs(2, ("new",), 99, 102, 101),
            obs(3, ("new",), 101, 105, 103.5),  # exactly 0.35 ATR separation
            obs(4, ("new",), 99, 102, 100.5),
            obs(5, ("new",), 99, 102, 99)]  # close below: not a research touch
    snaps = [snap(item.close) for item in data]
    first = daily_support_replay(data[:1], snaps[:1])
    assert first["observed_count"] == 1 and not first["sequence_known"]
    current = daily_support_replay(data, snaps)
    from research.stabil_support_resistance_compare import legacy_daily_touch_sequence
    for item in data:
        item.support_level = 100
    legacy_sequence, legacy_known = legacy_daily_touch_sequence(tuple(data), tuple(snaps))
    assert legacy_known[-1] and legacy_sequence[-1] == current["observed_count"]
    assert current["sequence_known"] and current["observed_count"] == 2
    assert [r["close"] for r in current["recent_touch_days"]] == [101, 100.5]
    # Later support and its touches cannot alter an already frozen prefix.
    future = data + [obs(6, ("future",), 99, 102, 100)]
    assert daily_support_replay(future[:5], (snaps + [snap(100)])[:5]) == current


def test_stabil_replay_missing_atr_and_identity_gaps_are_not_full_history():
    from types import SimpleNamespace as N
    from ai_prompt.stabil_replay import daily_support_replay
    def make(i, ident, low, high, close, atr):
        o = N(timestamp=pd.Timestamp(f"2026-09-{i:02d}T18:30:00+03:00"), support_identity=ident,
              support_available_at=pd.Timestamp(f"2026-09-{i:02d}T18:30:00+03:00"),
              low=low, high=high, close=close, atr=atr)
        return o, N(support_level=100 if ident is not None else None, close_below_support=close < 100)
    pairs = [make(1, ("old",), 99, 101, 100, 10), make(2, ("new",), 99, 101, 100, 10),
             make(3, ("new",), 101, 105, 104, None)]
    packet = daily_support_replay([x[0] for x in pairs], [x[1] for x in pairs])
    assert not packet["sequence_known"] and not packet["atr_complete_for_separation"]
    pairs += [make(4, None, 101, 105, 104, 10), make(5, ("new",), 99, 101, 100, 10)]
    packet = daily_support_replay([x[0] for x in pairs], [x[1] for x in pairs])
    assert not packet["sequence_known"] and packet["unknown_reason"] == "tekrar_gorunen_kimlik"
    from ai_prompt.builder import _render_stabil_daily_replay
    assert "aradan sonra tekrar" in "\n".join(_render_stabil_daily_replay(packet))
    assert "eşleşmiyor" in daily_support_replay([pairs[0][0]], [])["status"]


def test_local_daily_stabil_replay_is_frozen_at_main_tf_close(bimas):
    row = bimas["timeframes"]["4h"]
    replay = row["stabil_daily_replay"]
    assert replay["status"] == "ok" and replay["support_level"] == 390
    assert not replay["sequence_known"]
    assert pd.Timestamp(replay["support_available_at"]) <= pd.Timestamp(row["last_close_time"])
    for item in replay["recent_touch_days"]:
        assert pd.Timestamp(item["daily_close_time"]) <= pd.Timestamp(row["last_close_time"])


def test_structural_selection_sorts_input_not_assuming_ledger_order():
    from types import SimpleNamespace as N
    from ai_prompt.builder import _ms
    def event(day):
        return N(event_type="EVENT_BOS", scope="EXTERNAL", relevance="CURRENT",
                 confirmed_at=pd.Timestamp(f"2026-09-{day:02d}T09:30:00+03:00"), event_uid=str(day),
                 direction=1, broken_level=day, confirmation_status="CONFIRMED", validity="VALID", outcome="OBSERVED")
    result = N(error=None, skipped=False, export=N(external_scope=None, internal_scope=None,
                                                   events=[event(10), event(2), event(7)]))
    assert _ms(result)["events"][0]["level"] == 10


def test_replay_episode_failure_is_unknown_and_atr_failure_preserves_contacts(monkeypatch):
    from types import SimpleNamespace
    from ai_prompt import builder
    data = hourly_for("BIMAS")
    domain = SimpleNamespace(error=None, skipped=False)
    z = {"family": "OB", "direction": "pozitif", "lower": 1.0, "upper": 2.0,
         "source_open": None, "source_index": 1, "terminal": False, "state": "ACTIVE"}
    native = {"zone_id": "x", "active_at_asof": True, "direction": "bullish", "origin_index": 1,
              "zone_lower": 1.0, "zone_upper": 2.0, "available_at": data.index[1],
              "current_remaining_lower": 1.0, "current_remaining_upper": 2.0}
    monkeypatch.setattr(builder, "replay_ob_zones", lambda *args: [native])
    def fail(*args, **kwargs):
        raise RuntimeError("hesaplama hatası")
    monkeypatch.setattr(builder, "build_touch_episodes", fail)
    result = builder._replay("BIMAS", "1h", data, [z], {"order_block": domain})["zones"][0]
    assert result["episodes"] is None and "bilinmiyor" in result["replay_status"]
    monkeypatch.setattr(builder, "build_touch_episodes", lambda *args: [])
    monkeypatch.setattr(builder, "compute_wilder_atr", fail)
    result = builder._replay("BIMAS", "1h", data, [z], {"order_block": domain})["zones"][0]
    assert result["episodes"] == 0 and result["birth_atr"] is None


def test_strict_keeps_timeless_baselines_but_never_future_statistics():
    packet = build_from_local_cache("PETKM", as_of=CUT, research_mode="strict")
    prompt = render_prompt(packet)
    for item in packet["research"]:
        assert item["text"] not in prompt
    assert "0–<0,5 olanlarda n=3.276" not in prompt


def test_zone_default_keeps_all_visible_entries():
    from types import SimpleNamespace
    from ai_prompt.builder import _zones
    zones = [{"tip": "ob", "yon": (-1 if i % 2 else 1), "alt": i, "ust": i + 0.5,
              "kaynak": i, "zaman": None} for i in range(6)]
    rows = _zones({"son_kapanis": 3, "zone": {"cizilen": zones}},
                  {"order_block": SimpleNamespace(error=None, skipped=False)})
    assert {row["source_index"] for row in rows} == set(range(6))


def test_float32_feed_noise_is_shortened_without_two_decimal_price_cap():
    import numpy as np
    from ai_prompt.builder import _fmt
    price = float(np.float32(21.1))
    assert _fmt(price) == "21,10"
    narrow_a = float(np.float32(0.000042))
    narrow_b = float(np.nextafter(np.float32(narrow_a), np.float32(float('inf'))))
    assert _fmt(narrow_a) != _fmt(narrow_b)
    assert float(np.float32(float(_fmt(narrow_a).replace(',', '.')))) == narrow_a
    assert float(np.float32(float(_fmt(narrow_b).replace(',', '.')))) == narrow_b


def test_single_native_daily_record_does_not_silently_disappear():
    from data import resample_ohlcv
    frame = hourly_for("BIMAS")
    daily = resample_ohlcv(frame, "1d").tail(1)
    packet = build_from_frames("BIMAS", frame, daily=daily, as_of=CUT)
    assert "günlük kayıt sayısı 1, yetersiz" in packet["daily_source"]
    assert "günlük kayıt sayısı 1, yetersiz" in render_prompt(packet)


@pytest.mark.parametrize("mode", ["odak", "baglam"])
def test_prompt_chart_selection_matches_real_renderer(monkeypatch, tmp_path, mode):
    import grafik
    captured = {}
    original = grafik.anlik_goruntu
    def capture(candidate, tf, frame, **kwargs):
        view = original(candidate, tf, frame, **kwargs)
        captured[tf] = (view, frame)
        return view
    monkeypatch.delenv("GRAFIK_SADE", raising=False)
    monkeypatch.setenv("GRAFIK_GORUNUM", mode)
    monkeypatch.delenv("GRAFIK_ODAK_MESAFE_ATR", raising=False)
    monkeypatch.setattr(grafik, "anlik_goruntu", capture)
    packet = build_from_local_cache("BIMAS", as_of=CUT, research_mode="retrospective")
    for tf, row in packet["timeframes"].items():
        snapshot, frame = captured[tf]
        path, meta = grafik.ciz(snapshot, tf, {"cikti": str(tmp_path / f"{tf}.png"), "serit": True})
        assert path and not meta["eksik_katmanlar"]
        expected = [frame.index[i].isoformat() for i in meta["olay"].get("olay_barlari", [])]
        assert [e["bar_open"] for e in row["chart_events"]] == expected
        assert len(row["chart_levels"]) == meta["olay"]["dis_seviye"]
        assert len(row["zones"]) == meta["zone"]["cizilen"]
        labels = meta["serit"].get("rozetler", [])
        expected_badges = [(frame.index[snapshot["sol"] + b["bar"]].isoformat(), b["yon"], b["deger"]) for b in labels]
        assert [(b["bar_open"], b["direction"], b["value"]) for b in row["chart_volume_badges"]] == expected_badges
    text = render_prompt(packet)
    assert "SWEEP" not in text and "geçiş başarısızlığı" not in text
    if mode == "odak":
        assert len(text) < 7000


def test_simple_chart_mode_omits_hidden_layers(monkeypatch):
    monkeypatch.setenv("GRAFIK_SADE", "1")
    packet = build_from_local_cache("BIMAS", as_of=CUT, research_mode="retrospective")
    for row in packet["timeframes"].values():
        assert row["chart_events"] == [] and row["zones"] == []
        assert row["chart_levels"] == [] and row["chart_volume_badges"] == []
        assert row["chart_stabil_support"] is None
    assert "STABİL GÜNLÜK DESTEK REPLAY" not in render_prompt(packet)


def test_shared_price_frame_excludes_distant_structure_event():
    from grafik.render import olay_kadrajini_hazirla
    source = {"kapanis": [100.0, 101.0], "yuksek": [102.0, 102.0],
              "dusuk": [99.0, 100.0], "gorunum": {"mod": "odak"},
              "olay": {"olaylar": [{"bar": 0, "seviye": 101.0},
                                   {"bar": 1, "seviye": 10000.0}]}}
    view, _, outside, _, _ = olay_kadrajini_hazirla(source, 2)
    assert [e["seviye"] for e in view["olay"]["olaylar"]] == [101.0]
    assert outside == 1 and len(source["olay"]["olaylar"]) == 2


def test_native_daily_resistance_visible_on_renderer_and_in_prompt(monkeypatch, tmp_path):
    import grafik
    from research.arsiv import tf_frame
    captured = {}
    original = grafik.anlik_goruntu
    def capture(candidate, tf, frame, **kwargs):
        snapshot = original(candidate, tf, frame, **kwargs)
        captured[tf] = snapshot
        return snapshot
    monkeypatch.delenv("GRAFIK_SADE", raising=False)
    monkeypatch.delenv("GRAFIK_GORUNUM", raising=False)
    monkeypatch.setattr(grafik, "anlik_goruntu", capture)
    daily = tf_frame("BIMAS", "1d").tail(500)
    packet = build_from_frames("BIMAS", hourly_for("BIMAS"), daily=daily, as_of=CUT)
    row = packet["timeframes"]["4h"]
    assert row["chart_stabil_resistance"] == pytest.approx(437.5)
    path, meta = grafik.ciz(captured["4h"], "4h", {"cikti": str(tmp_path / "4h.png"), "serit": True})
    assert path and meta["cizgiler"]["stabil_direnc"]["cizildi"]
    assert meta["cizgiler"]["stabil_direnc"]["son_seviye"] == row["chart_stabil_resistance"]
    assert "Grafikte Stabil direnç: 437,50." in render_prompt(packet)


def test_only_rendered_volume_badges_not_raw_last_rvol_are_in_prompt(bimas):
    prompt = render_prompt(bimas)
    first = prompt.split("1H GRAFİK\n", 1)[1].split("\n2H GRAFİK", 1)[0]
    assert "1,39143" not in first
    for badge in bimas["timeframes"]["1h"]["chart_volume_badges"]:
        assert f"×{badge['value']}" in first
    assert "25.09.26 17:30 kuruma ×0,31" in prompt


def test_compact_replay_keeps_cross_day_times_truncation_and_unknowns():
    from ai_prompt.builder import _render_replay
    zone = {"direction": "pozitif", "family": "OB", "lower": 1, "upper": 2,
            "replay_status": "ok", "episodes": 4, "available_open": "2025-12-29T09:30:00+03:00",
            "remaining_lower": 1, "remaining_upper": 1.5, "birth_atr": None, "width_atr_birth": None,
            "recent_episodes": [{"number": 4, "start_open": "2025-12-31T17:30:00+03:00",
                "end_open": "2026-01-02T09:30:00+03:00", "bar_count": 4,
                "closes": [{"bar_open": "2026-01-02T09:30:00+03:00", "close": 1.25}],
                "closes_truncated": True, "next_bar_close": None, "ongoing_at_cut": True}]}
    text = "\n".join(_render_replay("4h", {"status": "available", "_main_tf": "4h", "replay": {"zones": [zone]}}))
    for part in ("31.12.25 17:30–02.01.26 09:30", "(son 3 mum)", "02.01.26 09:30=1,25",
                 "sonraki kapanmış mum yok", "devam ediyor olabilir", "doğum ATR hesaplanamadı"):
        assert part in text


def test_failed_chart_does_not_turn_hidden_layers_into_visible_evidence(monkeypatch):
    import grafik
    monkeypatch.setattr(grafik, "ciz", lambda *_args, **_kwargs: (None, {"red": True, "eksik_katmanlar": ["cizim"]}))
    packet = build_from_local_cache("BIMAS", as_of=CUT)
    assert all("çizilemedi" in row["status"] for row in packet["timeframes"].values())
    text = render_prompt(packet)
    assert "grafik çizilemedi" in text
    assert "Grafik hacim rozetleri" not in text and "Dış yapı:" not in text
    assert "Grafikte Stabil destek:" not in text


def test_fallback_chart_and_failed_layers_are_not_presented_as_drawn(monkeypatch):
    import grafik
    def fallback(*_args, **_kwargs):
        return "/tmp/fallback.png", {"uyarilar": ["çökme modu: yalnız mumlar çizildi"], "eksik_katmanlar": []}
    monkeypatch.setattr(grafik, "ciz", fallback)
    packet = build_from_local_cache("BIMAS", as_of=CUT)
    assert all("çizilemedi" in row["status"] for row in packet["timeframes"].values())

    def partial(*_args, **_kwargs):
        return "/tmp/partial.png", {"uyarilar": [], "eksik_katmanlar": ["zone", "ms", "formasyon"]}
    monkeypatch.setattr(grafik, "ciz", partial)
    packet = build_from_local_cache("BIMAS", as_of=CUT)
    for row in packet["timeframes"].values():
        assert row["zones"] == [] and row["chart_events"] == [] and row["chart_levels"] == []
        assert row["pattern"]["status"] == "error"


def test_user_reference_and_compact_instructions_keep_core_interpretation():
    reference = (ROOT / "ai_prompt" / "kullanici_ana_referans.txt").read_text(encoding="utf-8")
    instructions = (ROOT / "ai_prompt" / "talimat.txt").read_text(encoding="utf-8")
    for heading in ("YORUMLAMA YÖNTEMİ", "DOĞRULUK", "ÇIKTI", "GRAFİK VERİSİ",
                    "BU GRAFİĞE ÖZEL 4 SAATLİK REPLAY", "SABİT GENEL ARAŞTIRMA BLOĞU"):
        assert heading in reference
    for concept in ("karşı kanıt", "kararsız kal", "Temas ve sonraki kapanışı ayır", "Araştırmayı kapsamında kullan",
                    "emir defteri", "üzerinde kalmak", "Hazır olmayan", "tek başına yön",
                    "Tek kapanış kalıcılık veya dönüş teyidi değildir", "bilinmeyen devamı kesin anlatma",
                    "Kanıt yokluğu tersinin kanıtı değildir", "OB, CHoCH, BOS, FVG kullanılabilir",
                    "epizot gibi iç jargon", "orijinal bölgeye göre yerini", "formasyon yönü verilmemişse varsayma",
                    "Mevcut durum / Bağlam / Replay notu", "120–180"):
        assert concept in instructions
    assert "410,75" not in instructions and "426,25" not in instructions


@pytest.mark.parametrize("symbol", ["BIMAS", "ALARK"])
def test_compact_test_drafts_preserve_visible_graph_and_replay(symbol, bimas):
    """Manual historical examples, not a general-purpose 4000-char renderer."""
    from ai_prompt.builder import _fmt
    packet = (bimas if symbol == "BIMAS" else
              build_from_local_cache(symbol, as_of=CUT, research_mode="retrospective"))
    text = (ROOT / "docs" / "arastirma" / "ai_prompt_ornekleri" /
            f"{symbol}_2026-09-25_denge_v3.txt").read_text(encoding="utf-8")
    instructions = (ROOT / "ai_prompt" / "talimat.txt").read_text(encoding="utf-8").strip()
    assert text.startswith(instructions) and len(text) <= 4000
    for tf, end in (("1h", "2H |"), ("2h", "4H |"), ("4h", "1D |"), ("1d", "4H REPLAY")):
        section = text.split(f"{tf.upper()} |", 1)[1].split(end, 1)[0]
        row = packet["timeframes"][tf]
        for event in row["chart_events"]:
            when = pd.Timestamp(event["bar_open"]).strftime("%d.%m %H:%M")
            arrow = {"yukarı": "↑", "aşağı": "↓"}[event["direction"]]
            assert f"{when} {event['type']} {arrow}{_fmt(event['level'])}" in section
        for zone in row["zones"]:
            assert f"{_fmt(zone['lower'])}–{_fmt(zone['upper'])}" in section
        for badge in row["chart_volume_badges"]:
            when = pd.Timestamp(badge["bar_open"]).strftime("%d.%m %H:%M")
            code = {"artis": "A", "dusus": "K"}[badge["direction"]]
            assert f"{when} {code}×{badge['value']}" in section
    replay = text.split("4H REPLAY", 1)[1]
    for zone in packet["timeframes"]["4h"]["replay"]["zones"]:
        assert f"{_fmt(zone['lower'])}–{_fmt(zone['upper'])}" in replay
        if symbol == "ALARK" and zone["lower"] == pytest.approx(99.15):
            assert "Bu bölgenin temas kapanışları gösterilmedi" in replay
            continue
        for episode in zone["recent_episodes"]:
            bars = episode["closes"] + ([episode["next_bar_close"]] if episode["next_bar_close"] else [])
            for bar in bars:
                assert f"{pd.Timestamp(bar['bar_open']).strftime('%H:%M')}={_fmt(bar['close'])}" in replay
    assert "kesit sonrası" in text.lower() and "21.10.2026" in text


def test_visible_pattern_numbers_match_chart_precision_no_hidden_exact_line():
    from ai_prompt.builder import _render_pattern
    pattern = {"status": "available", "type": "Üçgen", "state": "SIKISMA_GUCLENIYOR",
               "quality": 89.2827, "contraction": .773164, "upper_touches": 2, "lower_touches": 2,
               "upper_now": 108.684371233, "lower_now": 101.465625525}
    result = _render_pattern(pattern)
    assert "kalite 89/100" in result and "Daralma %77" in result
    assert "108,684" not in result and "101,465" not in result
    assert pattern["upper_now"] == 108.684371233  # packet retains diagnostic data


def test_replay_latest_close_position_is_against_original_band(bimas):
    from ai_prompt.builder import _render_replay
    row = {**bimas["timeframes"]["4h"], "_main_tf": "4h"}
    text = "\n".join(_render_replay("4h", row))
    assert "Pozitif OB 410,75–423,50:" in text
    assert "son 4h kapanışı orijinal bölgenin üzerinde" in text
    assert "son 4h kapanışı orijinal bölgenin altında" in text
    for price, expected in ((410.75, "içinde veya sınırında"), (423.50, "içinde veya sınırında"),
                            (410.74, "altında"), (423.51, "üzerinde")):
        only_one = {**row, "last_close": price,
                    "replay": {"zones": [row["replay"]["zones"][0]]}}
        assert "orijinal bölgenin " + expected in "\n".join(_render_replay("4h", only_one))
    no_close = {**row, "last_close": None}
    assert "son 4h kapanışı orijinal bölgenin" not in "\n".join(_render_replay("4h", no_close))
