"""Persistence safety regression tests; every fixture is isolated under tmp_path."""

import json
import os
import pickle
from datetime import datetime, timedelta

import pandas as pd
import pytest

import config
import data as data_module
from data import StockDequeManager

IST = config.ISTANBUL_TZ


def _frame(n=55, end=None, base=100.0):
    end = end or datetime.now(IST) - timedelta(hours=2)
    index = pd.date_range(end=end, periods=n, freq="h")
    close = [base + i * 0.05 for i in range(n)]
    return pd.DataFrame(
        {
            "open": close,
            "high": [value + 0.2 for value in close],
            "low": [value - 0.2 for value in close],
            "close": close,
            "volume": [1000.0] * n,
        },
        index=index,
    )


def test_relative_storage_path_is_anchored_to_app_directory():
    app_dir = os.path.dirname(os.path.abspath(config.__file__))
    resolved = config._resolve_app_path("isolated-test-cache", "unused-default")
    assert resolved == os.path.join(app_dir, "isolated-test-cache")
    absolute = os.path.join(os.path.sep, "tmp", "absolute-cache")
    assert config._resolve_app_path(absolute, "unused-default") == absolute


def test_append_candle_canonicalizes_iso_timestamp_and_numeric_strings(tmp_path):
    manager = StockDequeManager(data_dir=str(tmp_path / "cache"))
    candle = {
        "timestamp": "2026-10-08T10:30:00+03:00",
        "open": "100", "high": "101", "low": "99", "close": "100.5", "volume": "10",
    }
    assert manager.append_candle("THYAO", candle) is True
    saved = manager.get_deque("THYAO")[0]
    assert isinstance(saved["timestamp"], pd.Timestamp)
    assert saved["timestamp"].tzinfo is not None
    assert all(isinstance(saved[field], float) for field in ("open", "high", "low", "close", "volume"))

    next_bar = pd.DataFrame(
        {"open": [100.5], "high": [102.0], "low": [100.0], "close": [101.0], "volume": [11.0]},
        index=pd.DatetimeIndex(["2026-10-08T11:30:00+03:00"]),
    )
    assert manager.append_dataframe("THYAO", next_bar) is True
    frame = manager.to_dataframe("THYAO")
    assert len(frame) == 2
    assert frame.index.is_monotonic_increasing


def test_save_to_disk_writes_json_and_legacy_pickle_in_isolated_dir(tmp_path):
    data_dir = tmp_path / "cache"
    manager = StockDequeManager(data_dir=str(data_dir))
    assert manager.append_dataframe("THYAO", _frame())

    manager.save_to_disk("THYAO")

    json_path = data_dir / "THYAO.json"
    pickle_path = data_dir / "THYAO.pkl"
    assert json_path.is_file() and pickle_path.is_file()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert len(payload) == 55
    assert isinstance(payload[-1]["timestamp"], str)


def test_json_survives_optional_pickle_write_failure(tmp_path, monkeypatch):
    data_dir = tmp_path / "cache"
    manager = StockDequeManager(data_dir=str(data_dir))
    assert manager.append_dataframe("THYAO", _frame())

    def fail_pickle(*_args, **_kwargs):
        raise OSError("simulated pickle disk failure")

    monkeypatch.setattr(data_module, "_atomic_pickle_write", fail_pickle)
    manager.save_to_disk("THYAO")

    assert json.loads((data_dir / "THYAO.json").read_text(encoding="utf-8"))
    assert not (data_dir / "THYAO.pkl").exists()


def test_json_is_default_cache_and_takes_priority_over_pickle(tmp_path, monkeypatch):
    data_dir = tmp_path / "cache"
    writer = StockDequeManager(data_dir=str(data_dir))
    assert writer.append_dataframe("THYAO", _frame())
    writer.save_to_disk("THYAO")
    monkeypatch.setattr(data_module, "ALLOW_TRUSTED_PICKLE_CACHE", False)

    loaded = StockDequeManager(data_dir=str(data_dir)).load_from_disk("THYAO")

    assert loaded is not None and len(loaded) == 55


def test_pickle_only_cache_is_not_unpickled_by_default(tmp_path, monkeypatch):
    data_dir = tmp_path / "cache"
    data_dir.mkdir()
    marker = tmp_path / "pickle-executed.txt"

    class MaliciousPickle:
        def __reduce__(self):
            return os.system, (f"touch {marker}",)

    (data_dir / "THYAO.pkl").write_bytes(pickle.dumps(MaliciousPickle()))
    monkeypatch.setattr(data_module, "ALLOW_TRUSTED_PICKLE_CACHE", False)

    loaded = StockDequeManager(data_dir=str(data_dir)).load_from_disk("THYAO")

    assert loaded is None
    assert not marker.exists()


def test_trusted_pickle_opt_in_loads_a_test_generated_legacy_cache(tmp_path, monkeypatch):
    data_dir = tmp_path / "cache"
    data_dir.mkdir()
    writer = StockDequeManager(data_dir=str(data_dir))
    assert writer.append_dataframe("THYAO", _frame())
    with (data_dir / "THYAO.pkl").open("wb") as stream:
        pickle.dump(list(writer.get_deque("THYAO")), stream)
    monkeypatch.setattr(data_module, "ALLOW_TRUSTED_PICKLE_CACHE", True)

    loaded = StockDequeManager(data_dir=str(data_dir)).load_from_disk("THYAO")

    assert loaded is not None and len(loaded) == 55


def test_json_load_does_not_fall_through_to_malicious_pickle(tmp_path, monkeypatch):
    data_dir = tmp_path / "cache"
    writer = StockDequeManager(data_dir=str(data_dir))
    assert writer.append_dataframe("THYAO", _frame())
    writer.save_to_disk("THYAO")
    marker = tmp_path / "pickle-executed.txt"

    class MaliciousPickle:
        def __reduce__(self):
            return os.system, (f"touch {marker}",)

    (data_dir / "THYAO.pkl").write_bytes(pickle.dumps(MaliciousPickle()))
    monkeypatch.setattr(data_module, "ALLOW_TRUSTED_PICKLE_CACHE", True)

    loaded = StockDequeManager(data_dir=str(data_dir)).load_from_disk("THYAO")

    assert loaded is not None and len(loaded) == 55
    assert not marker.exists()


def test_atomic_json_replace_failure_preserves_previous_file(tmp_path, monkeypatch):
    path = tmp_path / "cache.json"
    path.write_text('{"generation": "old"}', encoding="utf-8")

    def fail_replace(_source, _destination):
        raise OSError("simulated atomic replace failure")

    monkeypatch.setattr(data_module.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated"):
        data_module._atomic_json_write(str(path), {"generation": "new"})

    assert json.loads(path.read_text(encoding="utf-8")) == {"generation": "old"}
    assert not list(tmp_path.glob(".*.tmp"))


def test_daily_fetch_attempt_is_persisted_and_restored(tmp_path):
    data_dir = tmp_path / "cache"
    attempt = IST.localize(datetime(2026, 10, 8, 12, 0))
    manager = StockDequeManager(data_dir=str(data_dir))
    manager.gunluk_fetch_denemesi_kaydet("THYAO", attempt)

    restored = StockDequeManager(data_dir=str(data_dir))
    assert restored._gunluk_fetch_attempts["THYAO"] == attempt
    assert not restored.gunluk_veri_eksik_mi("THYAO", attempt + timedelta(hours=2))
    assert restored.gunluk_veri_eksik_mi("THYAO", attempt + timedelta(hours=7))
    payload = json.loads((data_dir / "gunluk_fetch_attempts.json").read_text())
    assert "THYAO" in payload


def test_daily_fetch_attempt_memory_only_mode_does_not_persist(tmp_path):
    class FakeStore:
        def __init__(self):
            self.writes = []

        def upsert(self, key, payload):
            self.writes.append((key, payload))
            return True

    store = FakeStore()
    data_dir = tmp_path / "memory-only"
    manager = StockDequeManager(data_dir=str(data_dir), persistent_store=store)
    attempt = IST.localize(datetime(2026, 10, 8, 12, 0))

    manager.gunluk_fetch_denemesi_kaydet("THYAO", attempt, persist=False)

    assert manager._gunluk_fetch_attempts["THYAO"] == attempt
    assert not (data_dir / "gunluk_fetch_attempts.json").exists()
    assert store.writes == []


@pytest.mark.parametrize("remote_failure", ["raises", "rejects"])
def test_daily_fetch_attempt_remote_failure_keeps_local_recovery_state(
    tmp_path, remote_failure, caplog
):
    class FakeStore:
        def upsert(self, _key, _payload):
            if remote_failure == "raises":
                raise RuntimeError("credential-bearing adapter detail must not be logged")
            return False

    data_dir = tmp_path / remote_failure
    manager = StockDequeManager(data_dir=str(data_dir), persistent_store=FakeStore())
    attempt = IST.localize(datetime(2026, 10, 8, 12, 0))

    # Remote persistence is a best-effort mirror: its failure cannot abort the
    # caller after the local attempt snapshot has been atomically written.
    manager.gunluk_fetch_denemesi_kaydet("THYAO", attempt)

    saved = json.loads((data_dir / "gunluk_fetch_attempts.json").read_text(encoding="utf-8"))
    assert saved["THYAO"].endswith("+00:00")
    restored = StockDequeManager(data_dir=str(data_dir))
    assert restored._gunluk_fetch_attempts["THYAO"] == attempt
    assert "uzak saklayıcı" in caplog.text
    assert "credential-bearing adapter detail" not in caplog.text


@pytest.mark.parametrize("remote_result", [True, False, RuntimeError("remote write failed")])
def test_hourly_cache_reports_remote_write_result_and_keeps_local_copy(
    tmp_path, remote_result
):
    class FakeStore:
        def __init__(self):
            self.writes = []

        def upsert(self, key, payload):
            self.writes.append((key, payload))
            if isinstance(remote_result, Exception):
                raise remote_result
            return remote_result

    store = FakeStore()
    data_dir = tmp_path / "hourly-cache"
    manager = StockDequeManager(data_dir=str(data_dir), persistent_store=store)
    assert manager.append_dataframe("THYAO", _frame(n=40))

    assert manager.save_to_disk("THYAO") is (remote_result is True)
    assert json.loads((data_dir / "THYAO.json").read_text(encoding="utf-8"))
    assert [key for key, _ in store.writes] == ["cache:1h:THYAO"]


def test_save_all_isolates_a_single_daily_cache_write_failure(tmp_path, monkeypatch):
    manager = StockDequeManager(data_dir=str(tmp_path / "save-all"))
    manager.deques = {"H1A": object(), "H1B": object()}
    manager.gunluk_deques = {"BROKEN": object(), "OK": object()}
    hourly_calls = []
    daily_calls = []

    def save_hourly(stock):
        hourly_calls.append(stock)
        return True

    def save_daily(stock):
        daily_calls.append(stock)
        if stock == "BROKEN":
            raise OSError("simulated local daily cache failure")
        return True

    monkeypatch.setattr(manager, "save_to_disk", save_hourly)
    monkeypatch.setattr(manager, "save_gunluk_to_disk", save_daily)

    assert manager.save_all() is False
    assert hourly_calls == ["H1A", "H1B"]
    assert daily_calls == ["BROKEN", "OK"]


def test_daily_cache_remote_write_failure_is_not_durable(tmp_path):
    class FakeStore:
        def __init__(self):
            self.writes = []

        def upsert(self, key, payload):
            self.writes.append((key, payload))
            return False

    store = FakeStore()
    data_dir = tmp_path / "remote-fail"
    manager = StockDequeManager(data_dir=str(data_dir), persistent_store=store)
    assert manager.append_gunluk_dataframe("THYAO", _frame(n=40))

    assert manager.save_gunluk_to_disk("THYAO") is False
    assert (data_dir / "THYAO_gunluk.json").is_file()
    assert [key for key, _ in store.writes] == ["cache:1d:THYAO"]


def test_supabase_hydrate_uses_newer_daily_fetch_attempt_and_keeps_newer_local(tmp_path):
    data_dir = tmp_path / "cache"
    local_time = IST.localize(datetime(2026, 10, 8, 12, 0))
    remote_time = IST.localize(datetime(2026, 10, 8, 13, 0))
    manager = StockDequeManager(data_dir=str(data_dir))
    manager.gunluk_fetch_denemesi_kaydet("THYAO", local_time)

    manager.hydrate_from_supabase(
        ["THYAO"],
        {"state:daily_fetch_attempts": {"THYAO": remote_time.isoformat()}},
    )
    assert manager._gunluk_fetch_attempts["THYAO"] == remote_time

    older_remote = IST.localize(datetime(2026, 10, 8, 11, 0))
    manager.hydrate_from_supabase(
        ["THYAO"],
        {"state:daily_fetch_attempts": {"THYAO": older_remote.isoformat()}},
    )
    assert manager._gunluk_fetch_attempts["THYAO"] == remote_time


def test_future_daily_fetch_attempt_keeps_cooldown_active_from_future_timestamp(tmp_path):
    """Audit evidence: a future persisted attempt suppresses refresh until six hours
    after that future timestamp. This policy is reported, not silently changed.
    """
    now = IST.localize(datetime(2026, 10, 8, 14, 0))
    future_attempt = now + timedelta(days=1)
    manager = StockDequeManager(data_dir=str(tmp_path / "future-attempt"))
    manager.gunluk_fetch_denemesi_kaydet("THYAO", future_attempt)

    assert manager.gunluk_veri_eksik_mi("THYAO", now) is False


def test_future_telegram_legacy_cooldown_is_retained_and_suppresses_send(
    tmp_path, monkeypatch
):
    """Audit evidence only: don't alter user-visible alert repeat/cooldown policy.

    A future state cooldown is retained and `now - future_time <= 4h` keeps the
    legacy event suppressed. The correction/expiry policy needs operator approval.
    """
    import notifier as notifier_module
    from notifier import TelegramNotifier

    now = IST.localize(datetime(2026, 10, 8, 14, 0))
    monkeypatch.setattr(
        notifier_module, "_local_now_naive", lambda: now.replace(tzinfo=None)
    )
    notifier = TelegramNotifier.__new__(TelegramNotifier)
    notifier.initial_store_data = {
        "state:telegram_cooldowns": {
            "THYAO_Pattern_1h_KIRILIM_ADAYI":
                (now + timedelta(days=1)).isoformat()
        }
    }
    notifier._cooldown_dosya = str(tmp_path / "missing-cooldown.json")
    notifier.cooldown_hours = 4
    notifier.last_sent = {}
    notifier._gunluk_tarih = now.date()
    notifier._gunluk_sayac = 0
    notifier.max_gunluk = 100
    notifier.max_saatlik = 100
    notifier._saatlik_zamanlar = []
    notifier._kap_uyarildi = False

    notifier._cooldown_yukle()

    assert notifier.can_send("THYAO", "Pattern", "1h", "KIRILIM_ADAYI") is False


def _cache_rows(frame):
    return [
        {
            "timestamp": timestamp.isoformat(),
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "volume": float(row.volume),
        }
        for timestamp, row in frame.iterrows()
    ]


def test_supabase_hourly_hydration_merges_newer_local_cache(tmp_path):
    data_dir = tmp_path / "hourly-cache"
    remote = _frame(n=5, end=IST.localize(datetime(2026, 10, 8, 10, 0)), base=100.0)
    local = _frame(n=5, end=IST.localize(datetime(2026, 10, 8, 13, 0)), base=200.0)

    writer = StockDequeManager(data_dir=str(data_dir))
    assert writer.append_dataframe("THYAO", local)
    writer.save_to_disk("THYAO")

    restarted = StockDequeManager(data_dir=str(data_dir))
    restarted.hydrate_from_supabase(
        ["THYAO"], {"cache:1h:THYAO": _cache_rows(remote)}
    )

    merged = restarted.to_dataframe("THYAO")
    assert len(merged) == 8  # five remote + five local, with two duplicate hours
    assert merged.index.is_monotonic_increasing
    assert merged.index[-1] == local.index[-1]
    # The source with the later final bar wins for overlapping candle revisions.
    assert merged.loc[local.index[0], "close"] == local.loc[local.index[0], "close"]


def test_supabase_hydration_uses_latest_timestamp_not_deque_insertion_order(tmp_path):
    data_dir = tmp_path / "unsorted-local-cache"
    remote = _frame(n=5, end=IST.localize(datetime(2026, 10, 8, 12, 0)), base=100.0)
    local = _frame(n=5, end=IST.localize(datetime(2026, 10, 8, 14, 0)), base=200.0)

    manager = StockDequeManager(data_dir=str(data_dir))
    # append_candle permits an out-of-order update; hydration must compare true
    # latest timestamps, not rely on the deque's final insertion.
    for timestamp, row in reversed(list(local.iterrows())):
        assert manager.append_candle("THYAO", {
            "timestamp": timestamp,
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "volume": float(row.volume),
        })

    manager.hydrate_from_supabase(
        ["THYAO"], {"cache:1h:THYAO": _cache_rows(remote)}
    )

    merged = manager.to_dataframe("THYAO")
    assert merged.index.is_monotonic_increasing
    assert merged.index[-1] == local.index[-1]
    assert merged.loc[remote.index[-1], "close"] == local.loc[remote.index[-1], "close"]


def test_supabase_cache_wins_overlapping_bars_when_tail_timestamps_match(tmp_path):
    data_dir = tmp_path / "equal-tail-cache"
    timestamp = IST.localize(datetime(2026, 10, 8, 10, 0))
    remote = _frame(n=5, end=timestamp, base=100.0)
    local = _frame(n=5, end=timestamp, base=200.0)

    writer = StockDequeManager(data_dir=str(data_dir))
    assert writer.append_dataframe("THYAO", local)
    writer.save_to_disk("THYAO")

    restarted = StockDequeManager(data_dir=str(data_dir))
    restarted.hydrate_from_supabase(
        ["THYAO"], {"cache:1h:THYAO": _cache_rows(remote)}
    )

    merged = restarted.to_dataframe("THYAO")
    assert len(merged) == len(remote)
    assert merged.loc[timestamp, "close"] == remote.loc[timestamp, "close"]


def test_supabase_daily_hydration_merges_newer_local_cache(tmp_path):
    data_dir = tmp_path / "daily-cache"
    remote_index = pd.date_range(
        end=IST.localize(datetime(2026, 10, 8, 12, 0)), periods=5, freq="D"
    )
    local_index = pd.date_range(
        end=IST.localize(datetime(2026, 10, 11, 12, 0)), periods=5, freq="D"
    )

    def daily_frame(index, base):
        close = [base + i * 0.05 for i in range(len(index))]
        return pd.DataFrame(
            {
                "open": close,
                "high": [value + 0.2 for value in close],
                "low": [value - 0.2 for value in close],
                "close": close,
                "volume": [1000.0] * len(index),
            },
            index=index,
        )

    remote = daily_frame(remote_index, 100.0)
    local = daily_frame(local_index, 200.0)
    writer = StockDequeManager(data_dir=str(data_dir))
    assert writer.append_gunluk_dataframe("THYAO", local)
    assert writer.save_gunluk_to_disk("THYAO") is True

    restarted = StockDequeManager(data_dir=str(data_dir))
    restarted.hydrate_from_supabase(
        ["THYAO"], {"cache:1d:THYAO": _cache_rows(remote)}
    )

    merged = restarted.to_gunluk_dataframe("THYAO")
    assert len(merged) == 8
    assert merged.index.is_monotonic_increasing
    assert merged.index[-1] == local.index[-1]
    assert merged.loc[local.index[0], "close"] == local.loc[local.index[0], "close"]
