from __future__ import annotations

import builtins
import logging
import types

import pandas as pd


def _valid_frame(count: int = 4) -> pd.DataFrame:
    index = pd.date_range(
        "2025-01-02 09:30",
        periods=count,
        freq="1h",
        tz="Europe/Istanbul",
        name="timestamp",
    )
    return pd.DataFrame(
        {
            "open": [10.0 + i for i in range(count)],
            "high": [10.5 + i for i in range(count)],
            "low": [9.5 + i for i in range(count)],
            "close": [10.2 + i for i in range(count)],
            "volume": [1000.0 + i for i in range(count)],
        },
        index=index,
    )


def test_broken_short_domain_frame_does_not_skip_next_formation_timeframe(
    monkeypatch, caplog
):
    import copy
    from types import SimpleNamespace

    import main as main_module

    broken = pd.DataFrame(
        {
            "open": [10.0, 10.1],
            "high": [10.2, 10.3],
            "low": [9.8, 9.9],
            "close": [10.1, 10.2],
            "volume": [1000.0, 1100.0],
        }
    )  # RangeIndex: domain preparation must log/skip, not escape scan_all_stocks.
    next_formation_frame = _valid_frame(40)
    hourly_cache = _valid_frame(50)
    broken_before = broken.copy(deep=True)
    formation_frame_before = next_formation_frame.copy(deep=True)
    lifecycle_calls = []
    domain_calls = []
    telegram_messages = []

    class FakeLiveState:
        def __init__(self):
            self.calls = []

        def begin_scan(self, *args, **kwargs):
            self.calls.append("begin")

        def record_formation(self, *args, **kwargs):
            self.calls.append("record_formation")

        def finish_scan(self, *args, **kwargs):
            self.calls.append("finish")

        def fail_scan(self, *args, **kwargs):
            self.calls.append("fail")

    class FakeLifecycle:
        def scan(self, key, frame, *, tam_yeniden):
            lifecycle_calls.append(key)
            return SimpleNamespace(
                state="ST_NONE", break_dir=None, log="no formation", active=None
            )

    class FakeDeferredAlerts:
        def observe(self, *args, **kwargs):
            return None

    class FakeNotifier:
        def send(self, *args, **kwargs):
            telegram_messages.append((args, kwargs))
            return True

    class FakeDequeManager:
        sureklilik_sorunlari = {}

        def to_dataframe(self, stock):
            return hourly_cache.copy(deep=True)

        def gunluk_veri_eksik_mi(self, stock, now):
            return False

        def to_gunluk_dataframe(self, stock):
            return None

        def save_to_disk(self, stock):
            return None

    all_timeframes = {
        "1h": broken,
        "2h": next_formation_frame,
        "4h": pd.DataFrame(),
        "1d": pd.DataFrame(),
    }

    def fake_domain_runner(symbol, timeframe, frame, *, profile):
        domain_calls.append((symbol, timeframe))

    fresh_stats = copy.deepcopy(main_module.daily_stats)
    for key, value in fresh_stats.items():
        if isinstance(value, bool):
            fresh_stats[key] = False
        elif isinstance(value, (int, float)):
            fresh_stats[key] = 0
    live_state = FakeLiveState()
    monkeypatch.setattr(main_module, "daily_stats", fresh_stats)
    monkeypatch.setattr(main_module, "last_run_stats", {}, raising=False)
    monkeypatch.setattr(main_module, "_live_state", live_state)
    monkeypatch.setattr(main_module, "_deferred_alert_buffer", FakeDeferredAlerts())
    monkeypatch.setattr(main_module, "_load_domain_runner", lambda: fake_domain_runner)
    monkeypatch.setattr(main_module, "fetch_1h_stocks_paced", lambda *a, **k: ({}, {}, 0, 0))
    monkeypatch.setattr(main_module, "create_yahoo_pacer", lambda: object())
    monkeypatch.setattr(main_module, "select_yfinance_1h_period", lambda *_: "5d")
    monkeypatch.setattr(main_module, "resample_all_timeframes", lambda _frame: all_timeframes)
    monkeypatch.setattr(main_module, "tarama_penceresi_acik_mi", lambda *_: False)
    monkeypatch.setattr(main_module, "_cache_verisi_kullanilabilir", lambda *a, **k: True)
    monkeypatch.setattr(main_module, "reset_daily_if_needed", lambda: None)
    monkeypatch.setattr(main_module, "write_heartbeat", lambda **kwargs: None)
    monkeypatch.setattr(main_module, "son_tarama_kaydet", lambda: None)
    monkeypatch.setattr(main_module, "_shutdown_requested", False)

    with caplog.at_level(logging.ERROR):
        result = main_module.scan_all_stocks(
            FakeDequeManager(),
            FakeLifecycle(),
            FakeNotifier(),
            stocks=["AUDIT"],
            send_alerts=False,
        )

    # The malformed 1h domain frame is logged/skipped; the same stock's valid
    # 2h Formation scan and following domain call both still run.
    assert any("Domain frame preparation failed" in record.message for record in caplog.records)
    assert lifecycle_calls == ["AUDIT_2h"]
    assert domain_calls == [("AUDIT", "2h")]
    assert result["status"] == "tamamlandi"
    assert live_state.calls == ["begin", "finish"]
    assert telegram_messages == []
    pd.testing.assert_frame_equal(broken, broken_before)
    pd.testing.assert_frame_equal(next_formation_frame, formation_frame_before)


def test_domain_import_failure_is_logged_and_retried_on_next_scan(
    monkeypatch, caplog
):
    import main as main_module

    attempts = []
    runner_calls = []
    runner_module = types.ModuleType("domain_engines.runner")

    def fake_runner(symbol, timeframe, frame, *, profile):
        runner_calls.append((symbol, timeframe, profile))

    runner_module.run_domain_engines = fake_runner
    original_import = builtins.__import__

    def fail_once_then_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "domain_engines.runner":
            attempts.append(name)
            if len(attempts) == 1:
                raise ImportError("temporary audit import failure")
            return runner_module
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fail_once_then_import)
    monkeypatch.setattr(main_module, "_domain_runner_loaded", False)
    monkeypatch.setattr(main_module, "_domain_runner_function", None)

    frame = _valid_frame()
    with caplog.at_level(logging.ERROR):
        # First scan: import failure is logged and the helper returns normally.
        main_module._run_domain_engines_for_symbol("AUDIT", {"2h": frame})

    assert len(attempts) == 1
    assert main_module._domain_runner_loaded is False
    assert runner_calls == []
    assert any("Domain engine runner yüklenemedi" in record.message for record in caplog.records)

    # A later scan retries, succeeds, and resumes the optional domain branch.
    main_module._run_domain_engines_for_symbol("AUDIT", {"2h": frame})
    assert len(attempts) == 2
    assert main_module._domain_runner_loaded is True
    assert [call[1] for call in runner_calls] == ["2h"]
