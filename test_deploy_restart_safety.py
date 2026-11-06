"""Cold-start safety for immutable Supabase snapshots; no external calls."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

import bot.app as app
import main
import notifier as notifier_module
from config import ISTANBUL_TZ
from state import persistence
from state.paths import DIGEST_PENDING_SUPABASE_KEY, digest_pending_yolu
from telegram_alert_flow import DeferredAlertBuffer


def _snapshot(now, stock="GARAN"):
    buffer = DeferredAlertBuffer()
    buffer.observe(stock, "1h", {
        "stock": stock, "timeframe": "1h", "pattern_name": "Üçgen",
        "state": "SIKISMA_GUCLENIYOR", "quality": 80,
    }, now)
    data = buffer.snapshot()
    data.update(kayit_zamani=now.isoformat(), son_digest_gun=None)
    return data


class _Reader:
    def __init__(self, payload, *, writable=False):
        self.payload = payload
        self.writable = writable
        self.reads = 0

    def get_many(self, keys):
        assert keys == [DIGEST_PENDING_SUPABASE_KEY]
        self.reads += 1
        return {DIGEST_PENDING_SUPABASE_KEY: self.payload}

    def upsert(self, *_args):
        pytest.fail("Salt okunur başlangıç uzakta değişiklik yapmamalı")


def test_readonly_remote_digest_does_not_replay_across_cold_starts(tmp_path, monkeypatch, caplog):
    now = datetime.now(ISTANBUL_TZ)
    reader = _Reader(_snapshot(now - timedelta(days=7)))
    sent = []
    notifier = SimpleNamespace(enabled=True, send_text=lambda text: (sent.append(text), True))

    # Two empty/ephemeral filesystems would otherwise resend the same old digest.
    for _ in range(2):
        buffer = DeferredAlertBuffer()
        count, last = persistence.digest_tamponu_yukle(buffer, store=reader, data_dir=str(tmp_path))
        monkeypatch.setattr(main, "_deferred_alert_buffer", buffer)
        assert (count, last) == (0, None)
        assert main._kacirilan_digest_ozeti(notifier, now) == ""
    assert sent == []
    assert reader.reads == 2
    assert "Salt okunur uzak digest otomatik yüklenmedi" in caplog.text


def test_readonly_digest_uses_local_even_if_remote_timestamp_is_newer(tmp_path):
    now = datetime.now(ISTANBUL_TZ)
    local = _snapshot(now - timedelta(days=2), "AKBNK")
    remote = _snapshot(now - timedelta(days=1), "GARAN")
    with open(digest_pending_yolu(str(tmp_path)), "w", encoding="utf-8") as stream:
        json.dump(local, stream)
    buffer = DeferredAlertBuffer()
    count, _ = persistence.digest_tamponu_yukle(buffer, _Reader(remote), str(tmp_path))
    assert count == 1
    assert buffer.gun() == (now - timedelta(days=2)).date()
    assert buffer.snapshot()["bekleyen"][0]["stock"] == "AKBNK"


def test_writable_digest_still_selects_newest_snapshot(tmp_path):
    now = datetime.now(ISTANBUL_TZ)
    local = _snapshot(now - timedelta(days=2), "AKBNK")
    remote = _snapshot(now - timedelta(days=1), "GARAN")
    with open(digest_pending_yolu(str(tmp_path)), "w", encoding="utf-8") as stream:
        json.dump(local, stream)
    buffer = DeferredAlertBuffer()
    assert persistence.digest_tamponu_yukle(buffer, _Reader(remote, writable=True), str(tmp_path))[0] == 1
    assert buffer.snapshot()["bekleyen"][0]["stock"] == "GARAN"


def test_readonly_remote_notification_pending_is_quarantined_but_history_kept(tmp_path, caplog):
    remote = {
        "state:telegram_acil_kuyruk": [{"veri": {"stock_name": "OLD"}}],
        "state:notification_delivery": {
            "saved_at": "2026-10-30T15:44:00+03:00",
            "rows": [{"id": "completed", "done": True}, {"id": "unknown", "done": False}],
            "public": [{"id": "historic-public"}],
        },
        "state:telegram_son_alerts": {"OLD_1h": "KIRILIM_TEYITLI", "new": {"state": "X"}},
        "cache:1h:AKBNK": [1],
    }
    result = app._salt_okunur_notifier_baslangici(remote, str(tmp_path))
    assert "state:telegram_acil_kuyruk" not in result
    assert result["state:notification_delivery"]["rows"] == [{"id": "completed", "done": True}]
    assert result["state:notification_delivery"]["public"] == [{"id": "historic-public"}]
    assert result["state:telegram_son_alerts"] == {"new": {"state": "X"}}
    assert result["cache:1h:AKBNK"] == [1]
    assert len(remote["state:notification_delivery"]["rows"]) == 2  # source never mutated
    assert "doğrulanmamış satır" in caplog.text


def test_local_outbox_caps_and_emergency_queue_beat_readonly_remote(tmp_path, monkeypatch):
    monkeypatch.setattr(notifier_module, "DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    local_outbox = {"saved_at": "2020-01-01", "rows": [{"id": "local", "done": False}], "public": []}
    (tmp_path / "notification_delivery.json").write_text(json.dumps(local_outbox), encoding="utf-8")
    local_queue = [{"veri": {"stock_name": "LOCAL", "timeframe": "1h"}}]
    (tmp_path / "telegram_acil_kuyruk.json").write_text(json.dumps(local_queue), encoding="utf-8")
    today = datetime.now(ISTANBUL_TZ).date().isoformat()
    (tmp_path / "telegram_kap.json").write_text(json.dumps({"gunluk_sayac": 7, "gunluk_tarih": today}),
                                               encoding="utf-8")
    remote = {
        "state:telegram_acil_kuyruk": [],
        "state:telegram_caps": {"gunluk_sayac": 0, "gunluk_tarih": today},
        "state:notification_delivery": {"saved_at": "2999-01-01", "rows": [], "public": []},
    }
    safe = app._salt_okunur_notifier_baslangici(remote, str(tmp_path))
    bot = notifier_module.TelegramNotifier(initial_store_data=safe)
    assert bot._delivery.state["rows"][0]["id"] == "local"
    assert bot._acil_kuyruk[0]["veri"]["stock_name"] == "LOCAL"
    assert bot._gunluk_sayac == 7
