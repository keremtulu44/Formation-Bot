from datetime import datetime

import notifier as notifier_module
from data import StockDequeManager
from config import ISTANBUL_TZ
from notifier import TelegramNotifier


class RecordingStore:
    def __init__(self):
        self.writes = []

    def upsert(self, key, payload):
        self.writes.append((key, payload))
        return True


def test_manager_hydrates_hourly_daily_and_attempt_state(tmp_path):
    manager = StockDequeManager(maxlen=2, data_dir=str(tmp_path))
    rows = {
        "cache:1h:THYAO": [
            {"timestamp": "2026-09-25T10:30:00+03:00", "open": 1, "high": 2,
             "low": 0.5, "close": 1.5, "volume": 10},
            {"timestamp": "2026-09-25T11:30:00+03:00", "open": 1.5, "high": 2,
             "low": 1, "close": 1.8, "volume": 11},
            {"timestamp": "2026-09-25T12:30:00+03:00", "open": 1.8, "high": 2.1,
             "low": 1.7, "close": 2, "volume": 12},
        ],
        "cache:1d:THYAO": [
            {"timestamp": "2026-09-24T00:00:00+03:00", "open": 1, "high": 2,
             "low": 0.5, "close": 1.5, "volume": 100},
        ],
        "state:daily_fetch_attempts": {
            "THYAO": "2026-09-25T15:00:00+00:00",
        },
    }

    manager.hydrate_from_supabase(["THYAO"], rows)

    assert len(manager.get_deque("THYAO")) == 2
    assert manager.get_deque("THYAO")[-1]["close"] == 2
    assert len(manager.get_gunluk_deque("THYAO")) == 1
    assert manager._gunluk_fetch_attempts["THYAO"].isoformat() == "2026-09-25T15:00:00+00:00"


def test_notifier_loads_and_persists_remote_states(tmp_path, monkeypatch):
    monkeypatch.setattr(notifier_module, "DATA_DIR", str(tmp_path / "bot_data"))
    store = RecordingStore()
    now = datetime.now(ISTANBUL_TZ).replace(microsecond=0)
    remote = {
        "state:telegram_cooldowns": {"THYAO_pattern_1h_state": now.isoformat()},
        "state:telegram_caps": {
            "gunluk_sayac": 3,
            "gunluk_tarih": now.date().isoformat(),
            "saatlik": [now.isoformat()],
        },
    }

    notifier = TelegramNotifier(persistent_store=store, initial_store_data=remote)
    notifier._cooldown_kaydet()
    notifier._kap_kaydet()

    assert notifier.last_sent["THYAO_pattern_1h_state"] == now
    assert notifier._gunluk_sayac == 3
    assert {key for key, _ in store.writes} == {
        "state:telegram_cooldowns",
        "state:telegram_caps",
    }
