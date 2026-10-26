from __future__ import annotations

import builtins
import copy
import logging
import types
from datetime import datetime
from types import SimpleNamespace

import pandas as pd
import pytest


def _valid_frame(count: int = 40) -> pd.DataFrame:
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


def test_breakout_requires_close_beyond_frozen_level_and_retest_requires_close():
    import main as main_module

    active = SimpleNamespace(
        frozen_upper_boundary_at_break=101.0,
        frozen_lower_boundary_at_break=90.0,
        upper_now=110.0,
        lower_now=80.0,
    )
    level = main_module._alert_break_level(active, 1, "KIRILIM_TEYITLI")
    assert level == 101.0  # use the level captured at the breakout, not a later band.
    assert main_module._closed_formation_event_confirmed(
        "KIRILIM_TEYITLI", 1, 101.01, level
    ) is True
    assert main_module._closed_formation_event_confirmed(
        "KIRILIM_TEYITLI", 1, 101.0, level
    ) is False
    assert main_module._closed_formation_event_confirmed(
        "KIRILIM_TEYITLI", -1, 90.0, 90.0
    ) is False
    # A confirmed successful retest may close exactly on the held level.
    assert main_module._closed_formation_event_confirmed(
        "RETEST_BASARILI", 1, 101.0, 101.0
    ) is True
    assert main_module._closed_formation_event_confirmed(
        "RETEST_BASARILI", 1, 100.99, 101.0
    ) is False
    assert main_module._closed_formation_event_confirmed(
        "KIRILIM_TEYITLI", 1, None, 101.0
    ) is False


def test_malformed_domain_frame_skipped_without_mutating_other_timeframes(caplog):
    import main as main_module
    from config import ISTANBUL_TZ

    broken = pd.DataFrame(
        {
            "open": [10.0, 10.1],
            "high": [10.2, 10.3],
            "low": [9.8, 9.9],
            "close": [10.1, 10.2],
            "volume": [1000.0, 1100.0],
        }
    )  # RangeIndex: runner adapter must never coerce this to a fake timestamp.
    valid = _valid_frame()
    broken_before = broken.copy(deep=True)
    valid_before = valid.copy(deep=True)

    with caplog.at_level(logging.ERROR):
        prepared = main_module._completed_domain_frames(
            {"1h": broken, "2h": valid}, datetime.now(ISTANBUL_TZ)
        )

    assert any("Domain frame preparation failed" in record.message for record in caplog.records)
    assert set(prepared) == {"2h"}
    assert len(prepared["2h"]) >= 30
    pd.testing.assert_frame_equal(broken, broken_before)
    pd.testing.assert_frame_equal(valid, valid_before)


def test_domain_import_failure_is_logged_and_retried(monkeypatch, caplog):
    import main as main_module

    attempts = []
    runner_module = types.ModuleType("domain_engines.runner")
    runner_module.run_domain_engines = lambda *args, **kwargs: {}
    original_import = builtins.__import__

    def fail_once_then_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "domain_engines.runner":
            attempts.append(name)
            if len(attempts) == 1:
                raise ImportError("temporary audit import failure")
            return runner_module
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fail_once_then_import)
    monkeypatch.setattr(main_module, "_domain_runner_cache", None)

    with caplog.at_level(logging.WARNING):
        assert main_module._load_domain_runner() is None
    assert len(attempts) == 1
    assert main_module._domain_runner_cache is None
    assert any("Domain runner yüklenemedi" in record.message for record in caplog.records)

    assert main_module._load_domain_runner() is runner_module.run_domain_engines
    assert len(attempts) == 2
    assert main_module._domain_runner_cache is runner_module.run_domain_engines


@pytest.mark.parametrize("domain_fails", [False, True])
@pytest.mark.parametrize(("engine_state", "expected_notification_state"), [
    ("KIRILIM_TEYITLI", "KIRILIM_TEYITLI"),
    ("BASARISIZ_KIRILIM", "KIRILIM_GECERSIZLESTI"),
])
def test_formation_alert_runs_fresh_domains_before_telegram_and_tolerates_failure(
    monkeypatch, domain_fails, engine_state, expected_notification_state
):
    import main as main_module
    from config import ACTIVE_STOCKS, ISTANBUL_TZ

    events = []
    alerts = []
    runner_frames = []
    stale_lookups = []
    formation_frame = _valid_frame()
    hourly_cache = _valid_frame(50)
    all_timeframes = {
        "1h": pd.DataFrame(),
        "2h": formation_frame,
        "4h": pd.DataFrame(),
        "1d": pd.DataFrame(),
    }
    invalidation_case = engine_state == "BASARISIZ_KIRILIM"
    active = SimpleNamespace(
        raw_quality=92.0,
        pattern_type="Simetrik Üçgen",
        upper_now=60.0 if invalidation_case else 20.0,
        lower_now=10.0,
        frozen_upper_boundary_at_break=50.0 if invalidation_case else 20.0,
        frozen_lower_boundary_at_break=10.0,
        stable_id="stable-formation-audit",
        start_bar=4,
        break_strength=91.0,
        contraction=0.6,
        upper_touches=3,
        lower_touches=2,
    )

    class FakeLiveState:
        def __init__(self):
            self.finish_fields = {}

        def begin_scan(self, *args, **kwargs):
            return None

        def record_formation(self, *args, **kwargs):
            return None

        def mark_alert_sent(self, *args, **kwargs):
            return None

        def finish_scan(self, *args, **kwargs):
            self.finish_fields = dict(kwargs)

        def fail_scan(self, *args, **kwargs):
            raise AssertionError("domain failure must not fail the Formation scan")

    class FakeLifecycle:
        def scan(self, key, _frame, *, tam_yeniden):
            assert key == "AUDIT_2h"
            assert tam_yeniden is True
            events.append("formation.scan")
            now = datetime.now(ISTANBUL_TZ)
            lifecycle_events = []
            invalid_reason = "Yok"
            if invalidation_case:
                lifecycle_events = [
                    {
                        "type": "BREAK_CONFIRMED", "state": "KIRILIM_TEYITLI",
                        "bar": 38, "time": (now - pd.Timedelta(minutes=5)).isoformat(),
                        "stable_id": active.stable_id, "direction": 1,
                        "quality": 92.0, "price": 51.0,
                    },
                    {
                        "type": "BREAK_FAILED", "state": "BASARISIZ_KIRILIM",
                        "bar": 39, "time": now.isoformat(),
                        "stable_id": active.stable_id, "direction": 1,
                        "quality": 92.0, "price": float(formation_frame["close"].iloc[-1]),
                    },
                ]
                invalid_reason = "Kırılım sonrası formasyon alanına dönüldü"
            return SimpleNamespace(
                state=engine_state,
                invalid_reason=invalid_reason,
                events=lifecycle_events,
                break_dir=1,
                log="immediate formation alert",
                active=active,
                effective_quality=92.0,
                bar_index=39,
                retest_seen=False,
            )

        def get_snapshot(self, _key):
            return None

    class FakeDeferredAlerts:
        def observe(self, *args, **kwargs):
            return None

    class FakeNotifier:
        def send(self, alert_data):
            events.append("telegram.send")
            alerts.append(alert_data.copy())
            return True

        def public_bosalt(self):
            return 0

    class FakeDequeManager:
        sureklilik_sorunlari = {}

        def to_dataframe(self, _stock):
            return hourly_cache.copy(deep=True)

        def gunluk_veri_eksik_mi(self, _stock, _now):
            return False

        def to_gunluk_dataframe(self, _stock):
            return None

        def save_to_disk(self, _stock):
            return None

    def fake_domain_runner(symbol, timeframe, completed_frame, *, profile):
        events.append("domain.start")
        runner_frames.append((symbol, timeframe, completed_frame.copy(deep=True), profile))
        if domain_fails:
            events.append("domain.failure")
            raise RuntimeError("simulated domain engine failure")
        events.append("domain.finish")
        structure = SimpleNamespace(
            external_scope=SimpleNamespace(state="STATE_BULLISH"),
            internal_scope=None,
            events=(),
            external_protected_high=None,
            external_protected_low=None,
            external_weak_high=None,
            external_weak_low=None,
        )
        return {"market_structure": SimpleNamespace(export=structure, error=None, skipped=False)}

    def stale_domain_lookup(*args, **kwargs):
        stale_lookups.append((args, kwargs))
        return {"market_structure": "stale-previous-scan-result"}

    import domain_engines.runner as domain_runner_mod

    # 2026-10-26: yama eskiden `main.get_latest_domain_results`'ı hedefliyordu
    # ama o ad main'de HİÇ yoktu (`raising=False` ile sessizce işe yaramıyordu).
    # Adın gerçek evi `domain_engines.runner`; oradan yamalanınca sözleşme
    # canlı kalır: tarama asla bayat domain sonucuna düşerse `stale_lookups`
    # dolar ve aşağıdaki iddia patlar.
    monkeypatch.setattr(domain_runner_mod, "get_latest_domain_results", stale_domain_lookup)
    fresh_stats = copy.deepcopy(main_module.daily_stats)
    for key, value in fresh_stats.items():
        if isinstance(value, bool):
            fresh_stats[key] = False
        elif isinstance(value, (int, float)):
            fresh_stats[key] = 0

    fake_live_state = FakeLiveState()
    monkeypatch.setattr(main_module, "ACTIVE_STOCKS", ["AUDIT"])
    monkeypatch.setattr(main_module, "daily_stats", fresh_stats)
    monkeypatch.setattr(main_module, "last_run_stats", {}, raising=False)
    monkeypatch.setattr(main_module, "_live_state", fake_live_state)
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
    monkeypatch.setattr(main_module, "_daily_pattern_keys", set())
    monkeypatch.setattr(main_module, "_daily_lifecycle_event_keys", set())
    monkeypatch.setattr(main_module, "_daily_basarisiz_keys", set())
    monkeypatch.setattr(main_module, "_gunluk_sayac_kaydet", lambda: None)

    result = main_module.scan_all_stocks(
        FakeDequeManager(),
        FakeLifecycle(),
        FakeNotifier(),
        stocks=["AUDIT"],
        send_alerts=True,
    )

    assert result["status"] == "tamamlandi"
    assert fake_live_state.finish_fields["son_tarama_beklenen_hisse"] == 1
    assert fake_live_state.finish_fields["son_basarili_tam_tarama"] == result["finished_at"]
    assert [call[:2] for call in runner_frames] == [("AUDIT", "2h")]
    assert float(runner_frames[0][2]["close"].iloc[-1]) == float(formation_frame["close"].iloc[-1])
    assert len(alerts) == 1
    assert alerts[0]["state"] == expected_notification_state
    assert alerts[0]["formation_id"] == "stable-formation-audit"
    assert alerts[0]["candle_close_price"] == float(formation_frame["close"].iloc[-1])
    assert alerts[0]["watch_context"] == []
    assert "domain_result" not in alerts[0]
    assert stale_lookups == []
    if invalidation_case:
        assert alerts[0]["break_price"] == 50.0
        assert fresh_stats["kirilim_teyitli_olay_sayisi"] == 1
        assert fresh_stats["kirilim_gecersizlesti_olay_sayisi"] == 1
    else:
        assert fresh_stats["kirilim_gecersizlesti_olay_sayisi"] == 0

    if domain_fails:
        assert events == [
            "formation.scan",
            "domain.start",
            "domain.failure",
            "telegram.send",
        ]
        assert alerts[0]["domain_context"] == ""
    else:
        assert events == [
            "formation.scan",
            "domain.start",
            "domain.finish",
            "telegram.send",
        ]
        assert "Piyasa Yapısı" in alerts[0]["domain_context"]
        assert "dış yükseliş" in alerts[0]["domain_context"]
