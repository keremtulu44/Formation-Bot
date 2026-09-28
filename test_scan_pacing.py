"""BIST 50 Yahoo pacing ve sınırlı retry regresyon testleri."""

import sys
from datetime import datetime, timedelta
from types import SimpleNamespace

import pandas as pd

from config import (ACTIVE_STOCKS, BIST_50, ISTANBUL_TZ,
                    FULL_1H_FETCH_PERIOD, ROUTINE_1H_FETCH_PERIOD)
from data import (StockDequeManager, fetch_yfinance_1h,
                  select_yfinance_1h_period, yfinance_error_is_retryable)
from scan_pacer import YahooRequestPacer


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def make_pacer(clock, batch_size=10):
    return YahooRequestPacer(
        batch_size=batch_size,
        request_delay_min=0.9,
        request_delay_max=1.5,
        batch_pause_min=10.0,
        batch_pause_max=15.0,
        sleep_fn=clock.sleep,
        monotonic_fn=clock.monotonic,
        uniform_fn=lambda low, high: low,
    )


def test_active_universe_excludes_yahoo_unsupported_symbols():
    assert len(BIST_50) == 48
    assert len(set(BIST_50)) == 48
    assert "KOZAL" not in BIST_50
    assert "KOZAA" not in BIST_50
    assert ACTIVE_STOCKS == BIST_50


def test_fetch_window_is_full_only_for_cold_or_old_cache():
    now = ISTANBUL_TZ.localize(datetime(2026, 9, 25, 12, 0))
    recent_index = pd.date_range(end=now - timedelta(hours=1), periods=80,
                                 freq="h", tz=ISTANBUL_TZ)
    recent = pd.DataFrame({"close": 1.0}, index=recent_index)
    stale_index = pd.date_range(end=now - timedelta(days=6), periods=80,
                                freq="h", tz=ISTANBUL_TZ)
    stale = pd.DataFrame({"close": 1.0}, index=stale_index)

    assert select_yfinance_1h_period(None, now) == FULL_1H_FETCH_PERIOD
    assert select_yfinance_1h_period(recent.iloc[:49], now) == FULL_1H_FETCH_PERIOD
    assert select_yfinance_1h_period(recent, now) == ROUTINE_1H_FETCH_PERIOD
    assert select_yfinance_1h_period(stale, now) == FULL_1H_FETCH_PERIOD


def test_requests_are_spaced_and_pause_after_ten():
    clock = FakeClock()
    pacer = make_pacer(clock)

    for _ in range(10):
        with pacer.request("test"):
            pass

    assert clock.sleeps == [0.9] * 9
    with pacer.request("11th request"):
        pass
    assert clock.sleeps[-1] == 10.0
    assert len(clock.sleeps) == 10


def test_minimum_delay_is_applied_after_request_completion():
    clock = FakeClock()
    pacer = make_pacer(clock)

    with pacer.request("first"):
        clock.now += 0.4
    with pacer.request("second"):
        pass

    # Ağ isteği uzun sürse bile tamamlanınca minimum nezaket aralığı korunur.
    assert clock.sleeps == [0.9]
    assert clock.now == 1.3


def test_transient_retry_classification_excludes_bad_symbols():
    assert yfinance_error_is_retryable(TimeoutError("request timed out"))
    assert yfinance_error_is_retryable("HTTP Error 429: Too Many Requests")
    assert not yfinance_error_is_retryable("HTTP Error 404: No data found")
    assert not yfinance_error_is_retryable("possibly delisted; no timezone found")


def test_daily_fetch_is_cooled_down_after_attempt(tmp_path):
    manager = StockDequeManager(data_dir=str(tmp_path))
    start = ISTANBUL_TZ.localize(datetime(2026, 9, 25, 8, 0))

    assert manager.gunluk_veri_eksik_mi("THYAO", start)
    manager.gunluk_fetch_denemesi_kaydet("THYAO", start)
    assert not manager.gunluk_veri_eksik_mi("THYAO", start + timedelta(hours=5))
    assert manager.gunluk_veri_eksik_mi("THYAO", start + timedelta(hours=6, seconds=1))


def test_daily_cache_is_refreshed_once_after_session_close(tmp_path):
    manager = StockDequeManager(data_dir=str(tmp_path))
    preclose = ISTANBUL_TZ.localize(datetime(2026, 9, 25, 17, 30))
    close = ISTANBUL_TZ.localize(datetime(2026, 9, 25, 18, 30))
    manager.gunluk_fetch_denemesi_kaydet("THYAO", preclose)

    assert manager.gunluk_veri_eksik_mi("THYAO", close + timedelta(minutes=5))
    manager.gunluk_fetch_denemesi_kaydet("THYAO", close + timedelta(minutes=5))
    assert not manager.gunluk_veri_eksik_mi("THYAO", close + timedelta(minutes=6))


def test_intraday_daily_bar_is_refreshed_after_close(tmp_path):
    manager = StockDequeManager(data_dir=str(tmp_path))
    dates = pd.date_range("2026-08-27", periods=30, freq="D", tz=ISTANBUL_TZ)
    frame = pd.DataFrame(
        {"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "volume": 100.0},
        index=dates,
    )
    manager.append_gunluk_dataframe("THYAO", frame)

    preclose = ISTANBUL_TZ.localize(datetime(2026, 9, 25, 17, 30))
    manager.gunluk_fetch_denemesi_kaydet("THYAO", preclose)
    assert manager.gunluk_veri_eksik_mi(
        "THYAO", preclose + timedelta(hours=1, minutes=5)
    )


def test_fetch_reports_transient_yahoo_stderr(monkeypatch):
    class FakeTicker:
        def history(self, **kwargs):
            assert kwargs["auto_adjust"] is False
            raise TimeoutError("read timed out")

    fake_yfinance = SimpleNamespace(Ticker=lambda symbol: FakeTicker())
    monkeypatch.setitem(sys.modules, "yfinance", fake_yfinance)

    frame, retryable, reason = fetch_yfinance_1h("THYAO", with_status=True)
    assert frame is None
    assert retryable is True
    assert "timed out" in reason


def test_fetch_does_not_retry_empty_permanent_symbol(monkeypatch):
    class FakeTicker:
        def history(self, **kwargs):
            return pd.DataFrame()

    fake_yfinance = SimpleNamespace(Ticker=lambda symbol: FakeTicker())
    monkeypatch.setitem(sys.modules, "yfinance", fake_yfinance)

    frame, retryable, reason = fetch_yfinance_1h("UNKNOWN", with_status=True)
    assert frame is None
    assert retryable is False
    assert "boş veri" in reason


def test_stock_fetch_helper_retries_only_transient_failures(monkeypatch):
    import main as main_mod

    clock = FakeClock()
    pacer = make_pacer(clock)
    frames = {
        "THYAO": pd.DataFrame({"close": [1.0]}),
    }
    calls = {"THYAO": 0, "UNKNOWN": 0}
    seen_periods = []

    def fake_fetch(stock, period="60d", with_status=False):
        calls[stock] += 1
        seen_periods.append((stock, period))
        if stock == "THYAO" and calls[stock] == 1:
            return None, True, "TimeoutError: timed out"
        if stock == "UNKNOWN":
            return None, False, "404 not found"
        return frames[stock], False, ""

    monkeypatch.setattr(main_mod, "fetch_yfinance_1h", fake_fetch)
    monkeypatch.setattr(main_mod.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(main_mod.random, "uniform", lambda low, _high: low)
    monkeypatch.setattr(main_mod, "_shutdown_requested", False)

    fetched, failures, retry_count, recovered_count = main_mod.fetch_1h_stocks_paced(
        ["THYAO", "UNKNOWN"], pacer, "TEST",
        periods={"THYAO": ROUTINE_1H_FETCH_PERIOD,
                 "UNKNOWN": FULL_1H_FETCH_PERIOD},
    )

    assert list(fetched) == ["THYAO"]
    assert "UNKNOWN" in failures
    assert calls == {"THYAO": 2, "UNKNOWN": 1}
    assert seen_periods == [
        ("THYAO", ROUTINE_1H_FETCH_PERIOD),
        ("UNKNOWN", FULL_1H_FETCH_PERIOD),
        ("THYAO", ROUTINE_1H_FETCH_PERIOD),
    ]
    assert retry_count == 1
    assert recovered_count == 1
