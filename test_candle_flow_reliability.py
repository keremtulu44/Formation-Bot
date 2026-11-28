"""Offline failure injection for live candle recovery and scan evidence."""
from concurrent.futures import ThreadPoolExecutor
import json
import sys
import threading
from types import SimpleNamespace

import pandas as pd
import pytest

import config
import data.fetch as fetch
from data.quality import hourly_fetch_validator
from bot import scan_evidence as evidence
from ai_prompt.client import AIClientRouter, AIAttemptRecord
from ai_prompt.service import _generate_ai_commentary_for_packet


@pytest.fixture(autouse=True)
def isolated_provider_observations(monkeypatch):
    from copy import deepcopy
    monkeypatch.setattr(fetch, "_SAGLAYICI_DURUM", deepcopy(fetch._SAGLAYICI_DURUM))


def frame(*labels):
    return pd.DataFrame({"open": 100.0, "high": 102.0, "low": 99.0,
                         "close": 101.0, "volume": 1000.0},
                        index=pd.DatetimeIndex(labels))


@pytest.mark.parametrize("observed,label,valid", [
    ("2026-11-27T12:35+03:00", "2026-11-27T11:30+03:00", True),
    ("2026-11-27T12:35+03:00", "2026-11-27T10:30+03:00", False),
    # An open 12:30 candle must not hide the missing closed 11:30 candle.
    ("2026-11-27T12:35+03:00", "2026-11-27T12:30+03:00", False),
    ("2026-11-27T12:32+03:00", "2026-11-27T10:30+03:00", True),
    ("2026-11-28T15:00+03:00", "2026-11-27T17:30+03:00", True),
    ("2026-11-30T09:55+03:00", "2026-11-27T17:30+03:00", True),
    ("2026-11-27T18:40+03:00", "2026-11-27T17:30+03:00", True),
    ("2026-03-19T13:20+03:00", "2026-03-19T12:30+03:00", True),
    ("2026-03-19T13:20+03:00", "2026-03-19T11:30+03:00", False),
    ("2026-11-27T12:35+03:00", "2026-11-27T11:00+03:00", True),
    ("2026-11-27T12:35+03:00", "2026-11-27T10:00+03:00", False),
    ("2026-11-27T12:05+03:00", "2026-11-27T10:00+03:00", False),
    ("2026-11-27T12:05+03:00", "2026-11-27T11:00+03:00", True),
    ("2026-11-30T10:35+03:00", "2026-11-27T17:00+03:00", True),
    ("2026-03-19T13:20+03:00", "2026-03-19T12:00+03:00", True),
])
def test_live_freshness_uses_closed_bars_and_sessions(observed, label, valid):
    ok, reason = hourly_fetch_validator("THYAO", observed)(frame(label))
    assert ok is valid
    if not valid:
        assert "veri gecikmesi" in reason


def test_macro_is_not_forced_into_bist_calendar():
    assert hourly_fetch_validator("BRENT", "2026-11-27T12:35+03:00") is None


def test_unknown_calendar_cannot_claim_freshness():
    ok, reason = hourly_fetch_validator("THYAO", "2051-11-27T12:35+03:00")(
        frame("2051-11-27T11:30+03:00"))
    assert not ok and "doğrulanamadı" in reason


def test_stale_yahoo_response_recovers_via_fresh_tv(monkeypatch):
    old = frame("2026-11-27T10:30+03:00")
    fresh = frame("2026-11-27T11:30+03:00")
    fresh.attrs["veri_kaynagi"] = "tvdatafeed"
    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(
        Ticker=lambda _: SimpleNamespace(history=lambda **_: old.copy())))
    calls = []
    monkeypatch.setattr(fetch, "_tv_yedek_dene", lambda *args: (calls.append(args) or fresh, ""))
    result, retryable, reason = fetch.fetch_yfinance_1h(
        "THYAO", with_status=True, as_of=pd.Timestamp("2026-11-27T12:35+03:00"))
    assert result is fresh
    assert result.attrs["saglayici_zinciri"] == ["yahoo", "tvdatafeed"]
    assert not retryable and not reason and len(calls) == 1


def test_two_stale_providers_never_become_fresh(monkeypatch):
    old = frame("2026-11-27T10:30+03:00")
    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(
        Ticker=lambda _: SimpleNamespace(history=lambda **_: old.copy())))
    monkeypatch.setattr(fetch, "_tv_yedek_dene", lambda *args: (old.copy(), ""))
    result, retryable, reason = fetch.fetch_yfinance_1h(
        "THYAO", with_status=True, as_of=pd.Timestamp("2026-11-27T12:35+03:00"))
    assert result is None and retryable
    assert "veri gecikmesi" in reason
    assert fetch.son_veri_kaynagi("THYAO", "1h") is None


def test_historical_fetch_without_cutoff_stays_compatible(monkeypatch):
    old = frame("2026-09-25T10:30+03:00")
    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(
        Ticker=lambda _: SimpleNamespace(history=lambda **_: old.copy())))
    monkeypatch.setattr(fetch, "_tv_yedek_dene", lambda *a: pytest.fail("healthy historical fetch used TV"))
    assert fetch.fetch_yfinance_1h("THYAO") is not None


def test_timeframe_provider_provenance_does_not_mix(monkeypatch):
    monkeypatch.setattr(fetch, "_SAGLAYICI_DURUM", {"son_kaynak_by_symbol": {}})
    fetch._saglayici_kaydet("THYAO", "tvdatafeed", tf="1h")
    fetch._saglayici_kaydet("THYAO", "yahoo", tf="1d")
    assert fetch.son_veri_kaynagi("THYAO", "1h") == "tvdatafeed"
    assert fetch.son_veri_kaynagi("THYAO", "1d") == "yahoo"


def test_tv_timeout_keeps_worker_slot_until_real_completion(monkeypatch):
    from scripts import tvdatafeed_client
    # Earlier timeout regressions may still be finishing their bounded fake job.
    for thread in threading.enumerate():
        if thread.name.startswith("tv-"):
            thread.join(timeout=2)
    gate = threading.Event()
    calls = []

    def blocked(**kwargs):
        calls.append(kwargs)
        assert gate.wait(timeout=3)
        return frame("2026-11-27T11:30+03:00")

    monkeypatch.setattr(tvdatafeed_client, "get_hist", blocked)
    monkeypatch.setattr(fetch, "TV_YEDEK_AKTIF", True)
    monkeypatch.setattr(fetch, "TV_ZAMAN_ASIMI_SN", .001)
    try:
        assert "zaman aşımı" in fetch._tv_yedek_dene("THYAO", "1h")[1]
        assert "zaman aşımı" in fetch._tv_yedek_dene("GARAN", "1h")[1]
        assert "sınırı dolu" in fetch._tv_yedek_dene("AKBNK", "1h")[1]
        assert len(calls) == 2 and fetch._TV_AKTIF_ISCI == 2
    finally:
        gate.set()
        for thread in threading.enumerate():
            if thread.name.startswith("tv-"):
                thread.join(timeout=3)
    assert fetch._TV_AKTIF_ISCI == 0


def snapshot(mode="scheduled_full", day="2026-11-27", **kwargs):
    return evidence.new_snapshot(
        started_at=f"{day}T12:35:00+03:00", finished_at=f"{day}T12:37:00+03:00",
        requested=50, processed=49, mode=mode, policy="P6",
        data={"received": 48, "fetch_failed": 2, "skipped": 1},
        formation={"sent": 3}, domain={"triggered": 8, "policy_rejected": 5},
        problems=["THYAO:stale"], **kwargs)


def test_evidence_persists_and_survives_reader_restart(tmp_path):
    assert evidence.save_evidence(snapshot(), tmp_path)
    loaded = evidence.load_evidence(tmp_path)
    assert len(loaded) == 1 and loaded[0]["policy"] == "P6"
    report = evidence.command_report(tmp_path)
    assert "48" in report and "politika eledi 5" in report
    assert "teslim adedi değildir" in report


def test_corrupt_evidence_is_not_silently_overwritten(tmp_path):
    path = evidence.evidence_path(tmp_path)
    path.write_text("{broken", encoding="utf-8")
    assert not evidence.save_evidence(snapshot(), tmp_path)
    assert path.read_text() == "{broken"
    assert "korunuyor" in evidence.command_report(tmp_path)


def test_bounded_history_and_concurrent_saves(tmp_path, monkeypatch):
    monkeypatch.setattr(evidence, "MAX_RUNS", 8)
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert all(pool.map(lambda _: evidence.save_evidence(snapshot(), tmp_path), range(16)))
    assert len(evidence.load_evidence(tmp_path)) == 8
    assert not list(tmp_path.glob("*.tmp"))


def test_manual_and_subset_runs_do_not_inflate_scheduled_daily_comparison():
    rows = [snapshot(), snapshot("manual"), snapshot("analysis_only"), snapshot("scheduled_subset")]
    report = evidence.format_evidence(rows)
    assert "2026-11-27: 1 tur" in report
    assert "2026-11-27: 4 tur" not in report


def test_flow_command_is_read_only_and_authorized_like_other_status_commands():
    from bot.commands import TELEGRAM_KOMUTLARI, PUBLIC_KOMUT_ISLEYICILERI, _komut_akis
    assert TELEGRAM_KOMUTLARI["akis"] is _komut_akis
    assert _komut_akis in PUBLIC_KOMUT_ISLEYICILERI
    assert "sicili yok" in _komut_akis("")


def test_router_total_budget_is_shared_not_reset_for_each_provider():
    clock = [0.0]
    budgets = []

    class Provider:
        name = "fake"
        model = None

        def ask(self, prompt, *, system=None, max_wall_seconds=None):
            budgets.append(max_wall_seconds)
            clock[0] += 6
            return None, AIAttemptRecord("fake", None, False, "problem", 200, 0, 6)

    router = AIClientRouter([Provider(), Provider(), Provider()], clock=lambda: clock[0])
    result = router.ask("test", max_wall_seconds_per_provider=8, max_total_seconds=10)
    assert budgets == [8, 4]
    assert not result.ok and len(result.attempts) == 2


@pytest.mark.parametrize("delay", [None, 60, float("nan"), "invalid"])
def test_stale_or_unknown_alarm_packet_never_calls_ai(delay):
    router = SimpleNamespace(ask_bundle=lambda *a, **k: pytest.fail("AI must not be called"))
    packet = {"symbol": "THYAO", "main_tf": "4h", "timeframes": {
        "4h": {"status": "available", "expected_delay_minutes": delay}}}
    outcome = _generate_ai_commentary_for_packet(packet, router=router, source_kind="alarm")
    assert outcome["reason"] == "stale_or_unknown_data"
    assert outcome["fallback_to_plain_card"]


def test_router_does_not_accept_late_success_as_within_budget():
    clock = [0.0]

    class Late:
        name = "late"
        model = None

        def ask(self, *args, **kwargs):
            clock[0] = 20
            return "too late", AIAttemptRecord("late", None, True, "done", 200, 0, 20)

    result = AIClientRouter([Late()], clock=lambda: clock[0]).ask("test", max_total_seconds=10)
    assert not result.ok and result.fallback_to_normal_alarm


@pytest.mark.parametrize("budget", [0, -1, float("inf"), float("nan")])
def test_router_rejects_invalid_total_budget(budget):
    with pytest.raises(ValueError):
        AIClientRouter([]).ask("test", max_total_seconds=budget)


@pytest.mark.parametrize("last_hour,cutoff,expected_delay", [
    (11, "2026-11-27T12:35+03:00", 0),
    (10, "2026-11-27T12:05+03:00", 30),
])
def test_ai_hourly_freshness_respects_native_grid_without_hiding_a_missing_bar(
        monkeypatch, last_hour, cutoff, expected_delay):
    import ai_prompt.service as service
    hourly = frame(*[f"2026-11-{day}T{last_hour}:00+03:00" for day in range(23, 28)])
    packet = {"timeframes": {"1h": {"expected_delay_minutes": 30}}}
    monkeypatch.setattr(service, "build_from_frames", lambda *a, **kw: packet)
    monkeypatch.setattr(service, "_generate_ai_commentary_for_packet", lambda p, **kw: p)
    result = service.generate_ai_commentary_for_frames(
        "THYAO", hourly, as_of=cutoff, main_tf="1h", source_kind="alarm",
        router=SimpleNamespace(providers=[object()]))
    assert result["timeframes"]["1h"]["expected_delay_minutes"] == expected_delay
