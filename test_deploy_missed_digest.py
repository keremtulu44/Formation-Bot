"""A failed startup digest remains available for manual review, not blind replay."""

import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

import bot.summary as summary
import config
import main
from config import ISTANBUL_TZ
from telegram_alert_flow import DeferredAlertBuffer


def _buffer(day):
    result = DeferredAlertBuffer()
    result.observe("GARAN", "1h", {"stock": "GARAN", "timeframe": "1h", "pattern_name": "Üçgen",
                                   "state": "SIKISMA_GUCLENIYOR", "quality": 80}, day)
    return result


@pytest.mark.parametrize("mode", ["disabled", "failure", "exception"])
def test_failed_or_ambiguous_digest_is_archived_before_day_rollover(tmp_path, monkeypatch, caplog, mode):
    now = datetime.now(ISTANBUL_TZ)
    previous = now - timedelta(days=1)
    buffer = _buffer(previous)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(main, "_supabase_store_ref", None)
    monkeypatch.setattr(main, "_deferred_alert_buffer", buffer)
    monkeypatch.setattr(main, "_digest_son_gonderim_gun", None)
    secret = "test-fake-token"

    def send(_text):
        if mode == "exception":
            raise TimeoutError(secret)
        return False, f"transport failure {secret}"

    notifier = None if mode == "disabled" else SimpleNamespace(enabled=True, token=secret, send_text=send)
    assert main._kacirilan_digest_ozeti(notifier, now)
    archives = list(tmp_path.glob("telegram_missed_digest_*.json"))
    assert len(archives) == 1
    payload = json.loads(archives[0].read_text(encoding="utf-8"))
    assert payload["gun"] == previous.date().isoformat()
    assert payload["teslim_durumu"] == "belirsiz"
    assert payload["tampon"]["bekleyen"][0]["stock"] == "GARAN"
    assert "GARAN" in payload["metin"]
    assert secret not in caplog.text
    assert main._digest_son_gonderim_gun is None
    assert len(buffer) == 0  # today's buffer can now start independently
    buffer.observe("AKBNK", "1h", {"stock": "AKBNK", "timeframe": "1h", "pattern_name": "Üçgen",
                                    "state": "SIKISMA_GUCLENIYOR", "quality": 80}, now)
    assert len(buffer) == 1 and archives[0].exists()


def test_archival_failure_does_not_clear_original_buffer_immediately(tmp_path, monkeypatch, caplog):
    now = datetime.now(ISTANBUL_TZ)
    buffer = _buffer(now - timedelta(days=1))
    monkeypatch.setattr(main, "_deferred_alert_buffer", buffer)
    monkeypatch.setattr(summary, "_kacirilan_digest_arsivle", lambda *_: False)
    main._kacirilan_digest_ozeti(None, now)
    assert len(buffer) == 1
    assert "arşiv yazma hatası" in caplog.text


def test_successful_missed_digest_does_not_leave_failed_archive(tmp_path, monkeypatch):
    now = datetime.now(ISTANBUL_TZ)
    previous = now - timedelta(days=1)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(main, "_supabase_store_ref", None)
    monkeypatch.setattr(main, "_deferred_alert_buffer", _buffer(previous))
    monkeypatch.setattr(main, "_digest_son_gonderim_gun", None)
    sent = []
    notifier = SimpleNamespace(enabled=True, send_text=lambda text: (sent.append(text) or True, "ok"))
    main._kacirilan_digest_ozeti(notifier, now)
    assert len(sent) == 1
    assert main._digest_son_gonderim_gun == previous.date().isoformat()
    assert list(tmp_path.glob("telegram_missed_digest_*.json")) == []
