"""Partial, failed and interrupted nightly refreshes must not be marked complete."""

from __future__ import annotations

import threading
from contextlib import nullcontext
from datetime import datetime, time, timedelta
from types import SimpleNamespace

import pytest

import bot.app as app
import main as M
from config import ISTANBUL_TZ


def test_nightly_progress_retries_only_incomplete_symbols_and_requires_both_timeframes():
    progress = app._NightlyRefreshProgress()
    day = datetime(2026, 11, 6).date()
    assert progress.pending(day, ["A", "B"]) == ["A", "B"]
    assert not progress.record({
        "yenilenen_1h_semboller": ["A", "B"],
        "yenilenen_1d_semboller": ["A"],
    }, ["A", "B"])
    assert progress.pending(day, ["A", "B"]) == ["B"]
    # B's 1H was saved on the preceding attempt; no need for it to succeed twice.
    assert progress.record({"yenilenen_1h_semboller": [], "yenilenen_1d_semboller": ["B"]}, ["B"])
    assert progress.pending(day, ["A", "B"]) == []
    assert progress.pending(day + timedelta(days=1), ["A", "B"]) == ["A", "B"]


def test_nightly_progress_never_trusts_counts_unknown_symbols_or_interruptions():
    day = datetime(2026, 11, 6).date()
    progress = app._NightlyRefreshProgress()
    assert progress.pending(day, []) == []
    assert not progress.record({"yenilenen_1h": 100, "yenilenen_1d": 100}, [])
    assert progress.pending(day, ["A"]) == ["A"]
    assert not progress.record({"yenilenen_1h": 1, "yenilenen_1d": 1}, ["A"])
    assert not progress.record({"yenilenen_1h_semboller": ["B"], "yenilenen_1d_semboller": ["A"]}, ["A"])
    assert progress.pending(day, ["A"]) == ["A"]
    assert not progress.record({
        "yenilenen_1h_semboller": ["A"], "yenilenen_1d_semboller": ["A"],
        "kapanis_ile_kesildi": True,
    }, ["A"])


def test_nightly_local_write_failure_is_not_reported_as_success(monkeypatch, caplog):
    import domain_engines.runner as runner
    import bot.summary as summary

    changed, attempt_persistence = [], []
    monkeypatch.setattr(M, "_shutdown_requested", False)
    monkeypatch.setattr(M, "fetch_1h_stocks_paced", lambda *_: ({"A": [1] * 60}, {}, 0, 0))
    monkeypatch.setattr(M, "fetch_yfinance_1d", lambda *_: [1] * 60)
    monkeypatch.setattr(runner, "reset_incremental_domain_states", lambda stock: changed.append(stock))

    class Manager:
        def denetle_mum_butunlugu(self, _stocks):
            return {"sorunlu_sembol_sayisi": 0, "eksik_1h": [], "eksik_1d": [],
                    "bosluklu_1h": [], "duz_mum_1d": []}

        def to_dataframe(self, _stock):
            return None

        def to_gunluk_dataframe(self, _stock):
            return None

        def replace_dataframe(self, *_):
            return True

        def replace_gunluk_dataframe(self, *_):
            return True

        def save_to_disk(self, *_args, **kwargs):
            assert kwargs["persist_remote"] is False
            return False

        def save_gunluk_to_disk(self, *_args, **kwargs):
            assert kwargs["persist_remote"] is False
            raise OSError("disk full")

        def gunluk_fetch_denemesi_kaydet(self, _stock, **kwargs):
            attempt_persistence.append(kwargs)

    pacer = SimpleNamespace(request=lambda *_: nullcontext())
    result = summary.gece_mum_temizligi_ve_yenileme(Manager(), pacer, stocks=["A"])
    assert result["yenilenen_1h"] == result["yenilenen_1d"] == 0
    assert result["yenilenen_1h_semboller"] == result["yenilenen_1d_semboller"] == []
    assert "yerel cache kaydı başarısız" in result["hatalar_1h"]["A"]
    assert "yerel cache kaydı başarısız" in result["hatalar_1d"]["A"]
    assert attempt_persistence == [{"persist": False, "persist_remote": False}]
    assert changed == ["A"]  # in-memory change still invalidates incremental indicators
    assert "yerel cache kaydı başarısız" in caplog.text


@pytest.mark.parametrize("fresh_preload", [False, True])
def test_main_loop_does_not_stamp_partial_night_and_retries_only_missing(monkeypatch, fresh_preload):
    """Exercise the actual scheduler, including fresh and hydrated startups."""
    calls, stamps, before_retry = [], [], []
    clock = {"seconds": 0.0}
    base = ISTANBUL_TZ.localize(datetime(2026, 11, 6, 2, 10))

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            value = base + timedelta(seconds=clock["seconds"])
            return value if tz else value.replace(tzinfo=None)

    class Manager:
        def __init__(self, **_kwargs):
            pass

        def to_dataframe(self, _stock):
            return None if fresh_preload else [0] * 50

        def gunluk_veri_eksik_mi(self, _stock):
            return fresh_preload

        def append_dataframe(self, *_):
            return True

        def save_to_disk(self, *_):
            return True

        def append_gunluk_dataframe(self, *_):
            return True

        def save_gunluk_to_disk(self, *_):
            return True

        def gunluk_fetch_denemesi_kaydet(self, *_):
            pass

        def save_all(self):
            pass

    class Notifier:
        enabled = public_enabled = False

        def __init__(self, **_kwargs):
            pass

        def check_connection(self):
            pass

        def teslimleri_dene(self):
            pass

    monkeypatch.setattr(M, "datetime", Clock)
    monkeypatch.setattr(M, "ACTIVE_STOCKS", ["A", "B"])
    monkeypatch.setattr(M, "NIGHTLY_CANDLE_REFRESH_HOUR", 2)
    monkeypatch.setattr(M, "NIGHTLY_CANDLE_REFRESH_MINUTE", 0)
    monkeypatch.setattr(M, "_shutdown_requested", False)
    monkeypatch.setattr(M, "_scan_istegi", threading.Event())
    monkeypatch.setattr(M, "_scan_job_active", threading.Event())
    monkeypatch.setattr(M, "_telegram_listener_ref", None)
    for name in ("_startup_ready", "_supabase_store_ref", "_deque_manager_ref",
                 "_lifecycle_manager_ref", "_notifier_ref", "_telegram_update_processor_ref"):
        monkeypatch.setattr(M, name, getattr(M, name))
    monkeypatch.setattr(app.SupabaseStore, "from_env", lambda **_: None)
    monkeypatch.setattr(app, "StockDequeManager", Manager)
    monkeypatch.setattr(app, "PatternLifecycleManager", lambda **_: object())
    monkeypatch.setattr(app, "TelegramNotifier", Notifier)
    monkeypatch.setattr(app, "islem_gunu_mu", lambda _: False)
    monkeypatch.setattr(app, "time_until_next_open", lambda _: 3600)
    monkeypatch.setattr(app.time, "monotonic", lambda: clock["seconds"])
    monkeypatch.setattr(app._state_persistence, "gonderim_durumu_yukle", lambda: {})
    monkeypatch.setattr(app, "_shutdown_bekle", lambda _: (_ for _ in ()).throw(AssertionError("loop error")))

    for name in ("setup_logging", "son_tarama_yukle", "_formation_history_baslangic_kontrolu",
                 "digest_tamponu_yukle", "_kacirilan_digest_ozeti", "_acil_kuyruk_acilista_isle",
                 "_telegram_komut_katmanini_kur", "_karne_uzak_kaydet", "_gunluk_sayac_yukle",
                 "_ileri_test_gece", "_gece_denetimi", "son_tarama_kaydet", "digest_tamponu_kaydet",
                 "write_heartbeat", "_tekil_ornek_kontrolu"):
        monkeypatch.setattr(M, name, lambda *_args, **_kwargs: None)
    monkeypatch.setattr(M, "_render_runtime_status_init", lambda: {})
    monkeypatch.setattr(M, "_evren_olcek_uyarisi", lambda: "")
    monkeypatch.setattr(M, "_ozet_isaretlerini_yukle", lambda: ({}, {}))
    monkeypatch.setattr(M, "_ozet_slot_gonderilmeli", lambda *_: False)
    monkeypatch.setattr(M, "create_yahoo_pacer", lambda: SimpleNamespace(request=lambda *_: nullcontext()))
    monkeypatch.setattr(M, "fetch_1h_stocks_paced", lambda stocks, *_: ({s: [0] * 60 for s in stocks}, {}, 0, 0))
    monkeypatch.setattr(app, "fetch_yfinance_1d", lambda _: [0] * 60)
    monkeypatch.setattr(M, "_karne_al", lambda: SimpleNamespace(buda=lambda: None, boyut=lambda: 0, dosya="test"))
    monkeypatch.setattr(M, "_effective_summary_hours", lambda: [])
    monkeypatch.setattr(M, "_parse_deferred_alert_digest_time", lambda: time(18, 45))
    monkeypatch.setattr(M, "_parse_post_close_analysis_time", lambda: time(20, 0))
    monkeypatch.setattr(M, "_gece_mum_yenileme_son_gun_oku", lambda: None)
    monkeypatch.setattr(M, "_gece_mum_yenileme_son_gun_kaydet", stamps.append)
    monkeypatch.setattr(M, "tarama_penceresi_acik_mi", lambda _: False)

    def refresh(_manager, _pacer, *, stocks):
        calls.append(list(stocks))
        if len(calls) == 1:
            return {"yenilenen_1h_semboller": ["A", "B"], "yenilenen_1d_semboller": ["A"]}
        return {"yenilenen_1h_semboller": [], "yenilenen_1d_semboller": ["B"]}

    def wait(_seconds):
        before_retry.append(list(stamps))
        if len(calls) == 1:
            clock["seconds"] += 600
        else:
            M._shutdown_requested = True
        return False

    monkeypatch.setattr(M, "gece_mum_temizligi_ve_yenileme", refresh)
    monkeypatch.setattr(M, "_bekle_veya_tarama", wait)
    app.main_loop()
    assert calls == [["A", "B"], ["B"]]
    assert before_retry == [[], [base.date()]]
    assert stamps == [base.date()]
