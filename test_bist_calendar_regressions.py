"""Regression tests for the fail-closed XIST schedule and stale-result labeling.

The calendar dependency is third-party, not an official Borsa Istanbul feed.
Tests lock down the explicit local policy and do not assert that its holiday list
is complete or that provider timestamp labels are independently verified.
"""

from copy import deepcopy
from datetime import datetime
import inspect
import threading
from types import SimpleNamespace
from contextlib import nullcontext

import pandas as pd

import config
import main as main_module
from bist_calendar import (
    SessionStatus,
    bist_scan_due,
    bist_scan_window_open,
    bist_session_for,
    current_session_data_issue,
    latest_session_checkpoint,
    next_bist_scan_at,
    should_run_post_close_analysis,
)
from live_state import LiveState

IST = config.ISTANBUL_TZ


def _local(value: str) -> datetime:
    return IST.localize(datetime.strptime(value, "%Y-%m-%d %H:%M"))


def _frame_at(value: str) -> pd.DataFrame:
    return pd.DataFrame(
        {"open": [1.0], "high": [2.0], "low": [0.5], "close": [1.5], "volume": [10]},
        index=pd.DatetimeIndex([_local(value)]),
    )


def _persisted_state(*, status="tamamlandi", finished="2026-10-12T10:38:00+03:00",
                     asof="2026-10-12T10:30:00+03:00") -> LiveState:
    state = LiveState()
    state.hydrate({
        "status": {
            "son_tarama_durumu": status,
            "son_tarama_baslangic": "2026-10-12T10:35:00+03:00",
            "son_tarama_bitis": finished,
            "son_tarama_hissesi": len(config.ACTIVE_STOCKS),
            "son_tarama_beklenen_hisse": len(config.ACTIVE_STOCKS),
            "son_tarama_veri_zamani": asof,
            "son_tarama_kapanis_checkpoint": "2026-10-12T10:30:00+03:00",
        },
        "formations": [],
    })
    return state


def test_calendar_classifies_normal_weekend_holiday_and_unknown_fail_closed():
    normal = bist_session_for(_local("2026-10-12 10:35"))
    saturday = bist_session_for(_local("2026-10-10 12:35"))
    sunday = bist_session_for(_local("2026-10-11 12:35"))
    holiday = bist_session_for(_local("2026-10-29 12:35"))
    outside_supported_range = bist_session_for(_local("2050-01-03 10:00"))

    assert normal.status is SessionStatus.TRADING
    assert saturday.status is SessionStatus.CLOSED
    assert sunday.status is SessionStatus.CLOSED
    assert holiday.status is SessionStatus.CLOSED
    assert outside_supported_range.status is SessionStatus.UNKNOWN
    assert should_run_post_close_analysis(_local("2026-10-10 20:05"))[0] is False
    assert should_run_post_close_analysis(_local("2050-01-03 20:05"))[0] is False
    assert bist_scan_window_open(_local("2050-01-03 10:35")) is False


def test_normal_scan_checkpoints_and_existing_full_day_cutoff_are_preserved():
    before_first_scan = _local("2026-10-12 10:34")
    first_scan = _local("2026-10-12 10:35")
    last_before_final = _local("2026-10-12 18:34")
    final_scan = _local("2026-10-12 18:35")

    assert next_bist_scan_at(before_first_scan) == _local("2026-10-12 10:35")
    assert bist_scan_due(before_first_scan) is False
    assert bist_scan_due(first_scan) is True
    assert latest_session_checkpoint(last_before_final) == _local("2026-10-12 18:30")
    assert bist_scan_due(final_scan) is True
    assert bist_scan_window_open(final_scan) is True
    assert bist_scan_window_open(_local("2026-10-12 18:41")) is False


def test_half_day_keeps_existing_1300_close_and_1305_final_scan():
    before_final = _local("2026-10-28 13:04")
    final_scan = _local("2026-10-28 13:05")
    session = bist_session_for(final_scan)

    assert session.status is SessionStatus.TRADING
    assert session.is_half_day is True
    # The explicit 2026 cutoff matches Borsa Istanbul's published holiday table;
    # no completeness claim is made for the finite local date map.
    assert session.close_time.isoformat() == "13:00:00"
    assert "configured half-day cutoff" in session.reason
    assert latest_session_checkpoint(before_final) == _local("2026-10-28 13:00")
    assert bist_scan_due(before_final) is False
    assert bist_scan_due(final_scan) is True
    assert bist_scan_window_open(_local("2026-10-28 13:10")) is True
    assert bist_scan_window_open(_local("2026-10-28 13:11")) is False


def test_provider_data_gate_rejects_old_empty_failed_future_and_accepts_fresh():
    now = _local("2026-10-12 13:05")
    assert current_session_data_issue(_frame_at("2026-10-12 12:30"), now) is None
    first_scan = _local("2026-10-12 10:35")
    assert "seans açılışından önce" in current_session_data_issue(
        _frame_at("2026-10-12 09:00"), first_scan
    )
    assert current_session_data_issue(_frame_at("2026-10-12 09:30"), first_scan) is None
    assert "bugüne ait değil" in current_session_data_issue(
        _frame_at("2026-10-09 17:30"), now
    )
    assert "boş veya başarısız" in current_session_data_issue(pd.DataFrame(), now)
    assert "boş veya başarısız" in current_session_data_issue(None, now)
    assert "geleceğe ait" in current_session_data_issue(
        _frame_at("2026-10-12 13:06"), now
    )
    assert "yaşında" in current_session_data_issue(_frame_at("2026-10-12 10:00"), now)


def test_post_close_freshness_uses_session_close_not_wall_clock_age():
    now = _local("2026-10-12 20:05")
    # The late-day candle is allowed even though its wall-clock age is >120 minutes.
    assert current_session_data_issue(
        _frame_at("2026-10-12 17:00"), now, after_close=True
    ) is None
    assert "kapanışına göre eski" in current_session_data_issue(
        _frame_at("2026-10-12 16:00"), now, after_close=True
    )


def test_friday_snapshot_is_labeled_as_closed_day_old_data(monkeypatch):
    state = LiveState()
    state.hydrate({
        "status": {
            "son_tarama_durumu": "tamamlandi",
            "son_tarama_bitis": "2026-10-09T17:40:00+03:00",
            "son_tarama_hissesi": len(config.ACTIVE_STOCKS),
            "son_tarama_beklenen_hisse": len(config.ACTIVE_STOCKS),
            "son_tarama_veri_zamani": "2026-10-09T17:30:00+03:00",
        },
        "formations": [],
    })
    monkeypatch.setattr(main_module, "_live_state", state)
    monkeypatch.setattr(main_module, "last_run_stats", {})

    notice = main_module._sonuc_veri_tarihi_uyarisi(_local("2026-10-10 18:45"))
    assert "Bugün BIST seansı yok" in notice
    assert "09.10.2026 17:30" in notice
    assert "bugün için yeni analiz değildir" in notice


def test_unknown_calendar_date_is_not_reported_as_a_trading_day(monkeypatch):
    state = LiveState()
    state.hydrate({
        "status": {
            "son_tarama_durumu": "tamamlandi",
            "son_tarama_veri_zamani": "2049-12-31T17:30:00+03:00",
            "son_tarama_hissesi": len(config.ACTIVE_STOCKS),
            "son_tarama_beklenen_hisse": len(config.ACTIVE_STOCKS),
        },
        "formations": [],
    })
    monkeypatch.setattr(main_module, "_live_state", state)
    monkeypatch.setattr(main_module, "last_run_stats", {})

    notice = main_module._sonuc_veri_tarihi_uyarisi(_local("2050-01-03 10:35"))
    assert "takvimi 03.01.2050 için bilinmiyor" in notice
    assert bist_scan_window_open(_local("2050-01-03 10:35")) is False


def test_live_state_snapshot_persists_scheduled_checkpoint_for_restart():
    completed_at = _local("2026-10-12 10:38")
    checkpoint = _local("2026-10-12 10:30")
    state = LiveState()
    state.begin_scan(
        _local("2026-10-12 10:35"),
        beklenen_hisse=len(config.ACTIVE_STOCKS),
        scope=config.ACTIVE_STOCKS,
    )
    state.finish_scan(
        completed_at,
        son_tarama_hissesi=len(config.ACTIVE_STOCKS),
        son_tarama_beklenen_hisse=len(config.ACTIVE_STOCKS),
        son_tarama_veri_zamani="2026-10-12T10:30:00+03:00",
        son_tarama_kapanis_checkpoint=checkpoint.isoformat(),
    )

    restored = LiveState()
    restored.hydrate(state.snapshot())
    assert restored.status()["son_tarama_kapanis_checkpoint"] == checkpoint.isoformat()


def test_restart_skips_successful_same_checkpoint_but_retries_failed_scan(monkeypatch):
    now = _local("2026-10-12 10:40")
    completed = _persisted_state()
    monkeypatch.setattr(main_module, "_live_state", completed)
    checkpoint = main_module._persisted_full_scan_checkpoint(now)
    assert checkpoint == _local("2026-10-12 10:30")
    assert bist_scan_due(now, checkpoint) is False

    failed = _persisted_state(status="basarisiz")
    monkeypatch.setattr(main_module, "_live_state", failed)
    restored_checkpoint = main_module._persisted_full_scan_checkpoint(now)
    assert restored_checkpoint is None
    assert bist_scan_due(now, restored_checkpoint) is True
    assert main_module._scheduled_scan_retry_wait(
        restored_checkpoint, retry_checkpoint=None, retry_at=None, now=100,
    ) == 0  # süreç içi bekleme restart ile sıfırlanır; başarısız checkpoint yeniden denenir


def test_scheduled_failure_keeps_checkpoint_and_installs_retry_backoff():
    checkpoint = _local("2026-10-12 10:30")
    failed = {"status": "basarisiz", "requested": 3, "processed": 2, "failed": 1}
    calls = []

    transition = main_module._execute_scheduled_scan_transition(
        scan_callable=lambda: calls.append("scan") or failed,
        checkpoint=checkpoint,
        expected_stock_count=3,
        retry_checkpoint=None,
        retry_attempts=0,
        retry_at=None,
        monotonic=lambda: 100.0,
    )

    assert calls == ["scan"]
    assert transition.scan_result is failed
    assert transition.completed_checkpoint is None
    assert transition.retry_checkpoint == checkpoint
    assert transition.retry_attempts == 1
    assert transition.retry_delay == 60.0
    assert transition.retry_at == 160.0
    assert main_module._scheduled_scan_retry_wait(
        checkpoint, transition.retry_checkpoint, transition.retry_at, now=159.0,
    ) == 1.0
    assert main_module._scheduled_scan_retry_wait(
        checkpoint, transition.retry_checkpoint, transition.retry_at, now=160.0,
    ) == 0.0


def test_scheduled_scan_exception_becomes_failure_and_installs_backoff(monkeypatch):
    checkpoint = _local("2026-10-12 10:30")
    monkeypatch.setattr(main_module, "_live_state", LiveState())
    monkeypatch.setattr(main_module, "last_run_stats", {})

    def scan_raises():
        raise RuntimeError("synthetic scheduled failure")

    transition = main_module._execute_scheduled_scan_transition(
        scan_callable=scan_raises,
        checkpoint=checkpoint,
        expected_stock_count=3,
        retry_checkpoint=None,
        retry_attempts=0,
        retry_at=None,
        monotonic=lambda: 50.0,
    )

    assert transition.scan_result["status"] == "basarisiz"
    assert transition.completed_checkpoint is None
    assert transition.retry_checkpoint == checkpoint
    assert transition.retry_attempts == 1
    assert transition.retry_at == 110.0
    assert transition.retry_delay == 60.0


def test_scheduled_full_success_advances_checkpoint_and_resets_retry_state():
    checkpoint = _local("2026-10-12 10:30")
    success = {"status": "tamamlandi", "requested": 3, "processed": 3, "failed": 0}

    transition = main_module._execute_scheduled_scan_transition(
        scan_callable=lambda: success,
        checkpoint=checkpoint,
        expected_stock_count=3,
        retry_checkpoint=checkpoint,
        retry_attempts=4,
        retry_at=999.0,
        monotonic=lambda: 100.0,
    )

    assert transition.completed_checkpoint == checkpoint
    assert transition.retry_checkpoint is None
    assert transition.retry_attempts == 0
    assert transition.retry_at is None
    assert transition.retry_delay == 0.0


def test_scheduled_scan_only_consumes_checkpoint_for_exact_full_success():
    checkpoint = _local("2026-10-12 10:30")
    incomplete_results = [
        {"status": "tamamlandi", "requested": 3, "processed": 2, "failed": 0},
        {"status": "tamamlandi", "requested": 3, "processed": 3, "failed": 1},
        {"status": "tamamlandi", "requested": 2, "processed": 2, "failed": 0},
    ]

    for stats in incomplete_results:
        transition = main_module._execute_scheduled_scan_transition(
            scan_callable=lambda stats=stats: stats,
            checkpoint=checkpoint,
            expected_stock_count=3,
            retry_checkpoint=None,
            retry_attempts=0,
            retry_at=None,
            monotonic=lambda: 100.0,
        )
        assert transition.completed_checkpoint is None
        assert transition.retry_checkpoint == checkpoint
        assert transition.retry_delay == 60.0


def _run_manual_full_scan_at(monkeypatch, start_time):
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return start_time.astimezone(tz) if tz else start_time.replace(tzinfo=None)

    monkeypatch.setattr(main_module, "datetime", FrozenDatetime)
    monkeypatch.setattr(main_module, "ACTIVE_STOCKS", ["A", "B"])
    monkeypatch.setattr(main_module, "_scan_istegi", threading.Event())
    main_module._scan_istegi.set()
    monkeypatch.setattr(main_module, "_scan_job_request", {"hisseler": ["A", "B"]})
    monkeypatch.setattr(main_module, "last_run_stats", {})
    monkeypatch.setattr(main_module, "_manuel_tarama_tamamla", lambda *_args: None)
    result = {"status": "tamamlandi", "requested": 2, "processed": 2, "failed": 0}
    scan_kwargs = {}

    def fake_scan(*_args, **kwargs):
        scan_kwargs.update(kwargs)
        main_module.last_run_stats = result
        return result

    monkeypatch.setattr(main_module, "scan_all_stocks", fake_scan)
    ran, checkpoint = main_module._calistir_istek_taramasi(None, None, None)
    return ran, checkpoint, scan_kwargs, result


def test_manual_full_scan_before_due_does_not_consume_checkpoint(monkeypatch):
    started_at = _local("2026-10-12 12:31")
    checkpoint = _local("2026-10-12 12:30")
    assert latest_session_checkpoint(started_at) == checkpoint
    assert bist_scan_due(started_at) is False

    ran, captured_checkpoint, scan_kwargs, result = _run_manual_full_scan_at(monkeypatch, started_at)

    assert ran is True
    assert captured_checkpoint is None
    assert scan_kwargs["scheduled_checkpoint"] is None
    assert scan_kwargs["require_current_session"] is False
    retry_checkpoint = _local("2026-10-12 11:30")
    retry_state = (retry_checkpoint, 2, 150.0)
    transition = main_module._manual_scan_checkpoint_transition(
        result, captured_checkpoint, retry_state[0], retry_state[1], retry_state[2],
    )
    assert transition == (None, *retry_state)
    assert bist_scan_due(_local("2026-10-12 12:35"), retry_checkpoint) is True


def test_long_manual_scan_consumes_only_checkpoint_captured_at_start(monkeypatch):
    started_at = _local("2026-10-12 10:35")
    captured_checkpoint = _local("2026-10-12 10:30")
    ran, checkpoint, scan_kwargs, result = _run_manual_full_scan_at(monkeypatch, started_at)

    assert ran is True
    assert checkpoint == captured_checkpoint
    assert scan_kwargs["scheduled_checkpoint"] == captured_checkpoint
    assert scan_kwargs["require_current_session"] is True

    finished_at = _local("2026-10-12 11:36")
    later_checkpoint = latest_session_checkpoint(finished_at)
    assert later_checkpoint == _local("2026-10-12 11:30")
    transition = main_module._manual_scan_checkpoint_transition(
        result, checkpoint, retry_checkpoint=captured_checkpoint,
        retry_attempts=4, retry_at=999.0,
    )
    assert transition == (captured_checkpoint, None, 0, None)
    assert transition[0] != later_checkpoint
    assert bist_scan_due(finished_at, transition[0]) is True


def test_successful_full_manual_scan_resets_scheduled_retry_state(monkeypatch):
    checkpoint = _local("2026-10-12 10:30")
    monkeypatch.setattr(main_module, "ACTIVE_STOCKS", ["A", "B", "C"])
    result = {"status": "tamamlandi", "requested": 3}

    transition = main_module._manual_scan_checkpoint_transition(
        result, checkpoint, retry_checkpoint=checkpoint,
        retry_attempts=5, retry_at=999.0,
    )

    assert transition == (checkpoint, None, 0, None)


def test_failed_manual_scan_preserves_scheduled_retry_state():
    retry_state = ("old-checkpoint", 3, 150.0)
    transition = main_module._manual_scan_checkpoint_transition(
        {"status": "basarisiz", "requested": 3}, _local("2026-10-12 10:30"),
        retry_checkpoint=retry_state[0], retry_attempts=retry_state[1], retry_at=retry_state[2],
    )

    assert transition == (None, *retry_state)


def test_scheduled_scan_backoff_is_exponential_bounded_and_checkpoint_scoped():
    assert [main_module._scheduled_scan_retry_delay(attempt) for attempt in range(1, 7)] == [
        60.0, 120.0, 240.0, 480.0, 900.0, 900.0,
    ]
    assert main_module._scheduled_scan_retry_wait(
        checkpoint="checkpoint-a", retry_checkpoint="checkpoint-a",
        retry_at=70, now=10,
    ) == 60
    assert main_module._scheduled_scan_retry_wait(
        checkpoint="checkpoint-a", retry_checkpoint="checkpoint-a",
        retry_at=10, now=10,
    ) == 0
    assert main_module._scheduled_scan_retry_wait(
        checkpoint="checkpoint-b", retry_checkpoint="checkpoint-a",
        retry_at=70, now=10,
    ) == 0


def test_main_loop_is_wired_to_scheduled_and_manual_checkpoint_transitions():
    # A full main_loop run performs extensive startup/cache/network setup and is
    # intentionally not exercised here; keep its transition-helper wiring explicit.
    source = inspect.getsource(main_module.main_loop)

    assert "retry_wait = _scheduled_scan_retry_wait(" in source
    assert "transition = _execute_scheduled_scan_transition(" in source
    assert "scheduled_retry_checkpoint = transition.retry_checkpoint" in source
    assert "scheduled_retry_attempts = transition.retry_attempts" in source
    assert "scheduled_retry_at = transition.retry_at" in source
    assert "son_taranan_kapanis = completed_checkpoint" in source
    assert "_manual_scan_checkpoint_transition(" in source

    manual_flow = source[
        source.index("if _scan_istegi.is_set():"):
        source.index("# --- GÜNLÜK ÖZET", source.index("if _scan_istegi.is_set():"))
    ]
    assert "manual_scan_ran, manual_scheduled_checkpoint = _calistir_istek_taramasi(" in manual_flow
    assert "last_run_stats, manual_scheduled_checkpoint," in manual_flow
    assert "son_kapanan_mum_ani(" not in manual_flow


def test_restart_skips_successful_post_close_scan_but_failed_scan_can_retry(monkeypatch):
    now = _local("2026-10-12 20:10")
    completed = _persisted_state(
        finished="2026-10-12T20:04:00+03:00",
        asof="2026-10-12T17:00:00+03:00",
    )
    monkeypatch.setattr(main_module, "_live_state", completed)
    assert main_module._persisted_post_close_scan_completed(now) is True

    failed = _persisted_state(
        status="basarisiz",
        finished="2026-10-12T20:04:00+03:00",
        asof="2026-10-12T17:00:00+03:00",
    )
    monkeypatch.setattr(main_module, "_live_state", failed)
    assert main_module._persisted_post_close_scan_completed(now) is False

    stale_success = _persisted_state(
        finished="2026-10-12T20:04:00+03:00",
        asof="2026-10-12T16:00:00+03:00",
    )
    monkeypatch.setattr(main_module, "_live_state", stale_success)
    assert main_module._persisted_post_close_scan_completed(now) is False


def test_scheduled_scan_refuses_weekend_before_provider_fetch(monkeypatch):
    saturday = _local("2026-10-10 20:05")

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return saturday.astimezone(tz) if tz else saturday.replace(tzinfo=None)

    live_state = LiveState()
    monkeypatch.setattr(main_module, "datetime", FrozenDatetime)
    monkeypatch.setattr(main_module, "_live_state", live_state)
    monkeypatch.setattr(main_module, "last_run_stats", {})
    monkeypatch.setattr(
        main_module, "fetch_1h_stocks_paced",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("provider fetch must not run")),
    )

    result = main_module.scan_all_stocks(
        None, None, None,
        stocks=["THYAO"],
        require_current_session=True,
        after_close=True,
    )
    assert result["status"] == "basarisiz"
    assert "BIST işlem günü/zamanı doğrulanmadı" in live_state.status()["son_tarama_hatasi"]


def test_scheduled_scan_rejects_stale_provider_before_cache_analysis(tmp_path, monkeypatch):
    scan_now = _local("2026-10-12 13:05")

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return scan_now.astimezone(tz) if tz else scan_now.replace(tzinfo=None)

    class CacheStub:
        sureklilik_sorunlari = {}

        def __init__(self):
            self.appends = 0

        def to_dataframe(self, _stock):
            return pd.DataFrame(
                {"open": [1.0] * 50, "high": [2.0] * 50, "low": [0.5] * 50,
                 "close": [1.5] * 50, "volume": [10.0] * 50},
                index=pd.date_range("2026-10-09 10:00", periods=50, freq="h", tz=IST),
            )

        def append_dataframe(self, _stock, _frame):
            self.appends += 1
            return True

        def to_gunluk_dataframe(self, _stock):
            return None

    cache = CacheStub()
    live_state = LiveState()
    monkeypatch.setattr(main_module, "datetime", FrozenDatetime)
    monkeypatch.setattr(main_module, "_live_state", live_state)
    monkeypatch.setattr(main_module, "last_run_stats", {})
    monkeypatch.setattr(main_module, "daily_stats", deepcopy(main_module.daily_stats))
    monkeypatch.setattr(main_module, "_shutdown_requested", False)
    monkeypatch.setattr(main_module, "reset_daily_if_needed", lambda: None)
    monkeypatch.setattr(main_module, "create_yahoo_pacer", lambda: object())
    monkeypatch.setattr(main_module, "son_tarama_kaydet", lambda: None)
    monkeypatch.setattr(main_module, "write_heartbeat", lambda **kwargs: None)
    monkeypatch.setattr(
        main_module,
        "fetch_1h_stocks_paced",
        lambda *args, **kwargs: ({"THYAO": _frame_at("2026-10-12 10:00")}, {}, 0, 0),
    )

    result = main_module.scan_all_stocks(
        cache, None, None,
        stocks=["THYAO"],
        require_current_session=True,
    )
    assert result["status"] == "basarisiz"
    assert result["processed"] == 0
    assert cache.appends == 0
    assert live_state.status()["son_tarama_durumu"] == "basarisiz"


def test_one_symbol_error_is_counted_and_later_symbols_still_scan(monkeypatch):
    now = _local("2026-10-12 10:35")
    hourly = pd.DataFrame(
        {
            "open": [100.0] * 60,
            "high": [101.0] * 60,
            "low": [99.0] * 60,
            "close": [100.5] * 60,
            "volume": [1000.0] * 60,
        },
        index=pd.date_range(end=_local("2026-10-12 09:30"), periods=60, freq="h"),
    )
    attempted = []

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.astimezone(tz) if tz else now.replace(tzinfo=None)

    class CacheStub:
        sureklilik_sorunlari = {}

        def to_dataframe(self, _stock):
            return hourly.copy()

        def append_dataframe(self, _stock, _frame):
            return True

        def gunluk_veri_eksik_mi(self, _stock, _now):
            return False

        def to_gunluk_dataframe(self, _stock):
            return None

        def save_to_disk(self, _stock):
            return None

    class LiveStateStub:
        def __init__(self):
            self.failure = None

        def begin_scan(self, *_args, **_kwargs):
            return None

        def fail_scan(self, message, *_args, **kwargs):
            self.failure = (message, kwargs)

        def finish_scan(self, *_args, **_kwargs):
            raise AssertionError("partial scan must not be published as complete")

    class LifecycleStub:
        def scan(self, key, _frame, *, tam_yeniden):
            attempted.append(key)
            if key.startswith("THYAO_"):
                raise RuntimeError("injected single-symbol failure")
            return SimpleNamespace(state="ST_NONE", break_dir=None, log="", active=None)

    class DeferredStub:
        def observe(self, *_args, **_kwargs):
            return None

        def snapshot(self, *_args, **_kwargs):
            return {}

    class NotifierStub:
        def send(self, *_args, **_kwargs):
            raise AssertionError("no alert expected")

        def persist_watch_state(self, *_args, **_kwargs):
            return True

    class PacerStub:
        def request(self, _label):
            return nullcontext()

    monkeypatch.setattr(main_module, "datetime", FrozenDatetime)
    monkeypatch.setattr(main_module, "daily_stats", deepcopy(main_module.daily_stats))
    monkeypatch.setattr(main_module, "last_run_stats", {})
    monkeypatch.setattr(main_module, "_live_state", LiveStateStub())
    monkeypatch.setattr(main_module, "_deferred_alert_buffer", DeferredStub())
    monkeypatch.setattr(main_module, "_shutdown_requested", False)
    monkeypatch.setattr(main_module, "reset_daily_if_needed", lambda: None)
    monkeypatch.setattr(main_module, "create_yahoo_pacer", lambda: PacerStub())
    monkeypatch.setattr(main_module, "select_yfinance_1h_period", lambda *_args: "5d")
    monkeypatch.setattr(
        main_module,
        "fetch_1h_stocks_paced",
        lambda stocks, *_args, **_kwargs: ({stock: hourly.copy() for stock in stocks}, {}, 0, 0),
    )
    monkeypatch.setattr(
        main_module,
        "resample_all_timeframes",
        lambda _frame: {"1h": hourly.copy(), "2h": pd.DataFrame(), "4h": pd.DataFrame(), "1d": pd.DataFrame()},
    )
    monkeypatch.setattr(main_module, "tamamlanmis_mumlar", lambda frame, _tf: frame)
    monkeypatch.setattr(
        main_module, "_safe_completed_domain_frame",
        lambda _stock, _tf, frame, already_completed=False: frame,
    )
    monkeypatch.setattr(main_module, "_run_domain_engines_for_symbol", lambda *_args: {})
    monkeypatch.setattr(main_module, "write_heartbeat", lambda **_kwargs: None)
    monkeypatch.setattr(main_module, "son_tarama_kaydet", lambda: None)

    result = main_module.scan_all_stocks(
        CacheStub(),
        LifecycleStub(),
        NotifierStub(),
        stocks=["THYAO", "ASELS"],
        send_alerts=False,
    )

    assert attempted == ["THYAO_1h", "ASELS_1h"]
    assert result["status"] == "basarisiz"
    assert result["processed"] == 1
    assert result["failed"] == 1
    assert main_module._live_state.failure is not None


def test_scheduled_scan_does_not_analyze_stale_cache_after_failed_fetch(monkeypatch):
    scan_now = _local("2026-10-12 13:05")
    old_cache = pd.DataFrame(
        {
            "open": [100.0] * 60,
            "high": [101.0] * 60,
            "low": [99.0] * 60,
            "close": [100.5] * 60,
            "volume": [1000.0] * 60,
        },
        index=pd.date_range(end=_local("2026-10-09 17:30"), periods=60, freq="h"),
    )

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return scan_now.astimezone(tz) if tz else scan_now.replace(tzinfo=None)

    class CacheStub:
        sureklilik_sorunlari = {}

        def __init__(self):
            self.appends = 0

        def to_dataframe(self, _stock):
            return old_cache.copy()

        def append_dataframe(self, _stock, _frame):
            self.appends += 1
            return True

        def to_gunluk_dataframe(self, _stock):
            return None

    cache = CacheStub()
    state = LiveState()
    lifecycle_calls = []
    monkeypatch.setattr(main_module, "datetime", FrozenDatetime)
    monkeypatch.setattr(main_module, "_live_state", state)
    monkeypatch.setattr(main_module, "last_run_stats", {})
    monkeypatch.setattr(main_module, "daily_stats", deepcopy(main_module.daily_stats))
    monkeypatch.setattr(main_module, "_shutdown_requested", False)
    monkeypatch.setattr(main_module, "reset_daily_if_needed", lambda: None)
    monkeypatch.setattr(main_module, "select_yfinance_1h_period", lambda *_args: "5d")
    monkeypatch.setattr(main_module, "create_yahoo_pacer", lambda: object())
    monkeypatch.setattr(main_module, "son_tarama_kaydet", lambda: None)
    monkeypatch.setattr(main_module, "write_heartbeat", lambda **_kwargs: None)
    monkeypatch.setattr(
        main_module,
        "fetch_1h_stocks_paced",
        lambda *_args, **_kwargs: ({}, {"THYAO": "timeout"}, 1, 0),
    )

    class LifecycleStub:
        def scan(self, *_args, **_kwargs):
            lifecycle_calls.append(True)
            raise AssertionError("failed scheduled fetch must not analyze cached bars")

    result = main_module.scan_all_stocks(
        cache,
        LifecycleStub(),
        None,
        stocks=["THYAO"],
        require_current_session=True,
    )

    assert result["status"] == "basarisiz"
    assert result["processed"] == 0
    assert cache.appends == 0
    assert lifecycle_calls == []
    assert state.status()["son_tarama_durumu"] == "basarisiz"
