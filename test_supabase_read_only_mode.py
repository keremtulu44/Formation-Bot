"""Supabase yalnız okuma: bot ve tanılama hiçbir veri yazmamalı."""

import pytest

from supabase_store import SupabaseStore
from test_supabase_store import FakeResponse, FakeSession


def test_read_only_get_is_allowed_all_mutating_methods_are_blocked():
    session = FakeSession([FakeResponse(payload=[
        {"store_key": "formation-bot:state:son_tarama", "payload": {"ok": True}},
    ])])
    store = SupabaseStore("https://demo.supabase.co", "test-key", session=session, read_only=True)
    assert store.enabled and not store.writable
    assert store.get_many(["state:son_tarama"]) == {"state:son_tarama": {"ok": True}}
    assert not store.upsert("state:heartbeat", {"value": 1})
    for method in ("POST", "post", "PATCH", "PUT", "DELETE"):
        assert store.request_table("f2_formations", method, json={"stable_id": "s"}) is None
    assert store.request_table_for_mirror("f2_events", "POST", json=[]) is None
    assert [call[0] for call in session.calls] == ["GET"]


def test_read_only_from_env_requires_no_change_to_existing_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://demo.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "fake-secret")
    store = SupabaseStore.from_env(read_only=True)
    assert store is not None and not store.writable


def test_mirror_disabled_does_not_create_or_flush_queue(tmp_path, monkeypatch):
    from state import formation_mirror as mirror

    q = mirror.FormationMirrorQueue(data_dir=str(tmp_path))
    q.enqueue_diff({"f2_formations": [{"stable_id": "existing"}]})
    session = FakeSession([])
    reader = SupabaseStore("https://demo.supabase.co", "test-key", session=session, read_only=True)
    assert q.flush(reader) == 0
    assert q.size() == 1  # önceki kuyruk korunur
    monkeypatch.setattr(mirror, "_MIRROR_WRITES_ENABLED", False)
    monkeypatch.setattr(mirror, "get_mirror_queue", lambda *a, **k: pytest.fail("kuyruk oluşturuldu"))
    assert mirror.mirror_kaydet({"stock": "T", "timeframe": "1h"}, data_dir=str(tmp_path)) == 0
    assert session.calls == []


def test_bot_startup_uses_read_only_reader_but_no_runtime_writer(monkeypatch):
    import bot.app as app
    from state import formation_mirror as mirror

    class StopStartup(Exception):
        pass

    pkg = app._pkg
    session = FakeSession([])
    reader = SupabaseStore("https://demo.supabase.co", "fake-secret", session=session, read_only=True)
    calls = []
    monkeypatch.setattr(app.SupabaseStore, "from_env", lambda *, read_only=False: (
        reader if read_only else pytest.fail("store salt okunur değil")
    ))
    monkeypatch.setattr(reader, "ping", lambda: True)
    monkeypatch.setattr(reader, "get_many", lambda keys: {"state:telegram_caps": {}})
    monkeypatch.setattr(reader, "ornek_bildir", lambda *a, **kw: pytest.fail("instance yazımı denendi"))
    monkeypatch.setattr(mirror, "hydrate_all_open", lambda store: calls.append(("hydrate", store)))
    monkeypatch.setattr(mirror, "_MIRROR_WRITES_ENABLED", True)
    monkeypatch.setattr(pkg, "setup_logging", lambda: None)
    monkeypatch.setattr(pkg, "_evren_olcek_uyarisi", lambda: "")
    monkeypatch.setattr(pkg, "son_tarama_yukle", lambda store: calls.append(("son_tarama", store)))
    monkeypatch.setattr(pkg, "_formation_history_baslangic_kontrolu", lambda: {})
    monkeypatch.setattr(pkg, "digest_tamponu_yukle", lambda store: calls.append(("digest", store)))
    monkeypatch.setattr(pkg, "_supabase_store_ref", None)
    monkeypatch.setattr(pkg, "_deque_manager_ref", None)
    monkeypatch.setattr(pkg, "_lifecycle_manager_ref", None)
    monkeypatch.setattr(pkg, "_startup_ready", False)

    class FakeDeque:
        def __init__(self, *, persistent_store):
            assert persistent_store is None

        def hydrate_from_supabase(self, stocks, rows):
            calls.append(("cache", rows))

    monkeypatch.setattr(app, "StockDequeManager", FakeDeque)
    monkeypatch.setattr(app, "PatternLifecycleManager", lambda **kwargs: object())

    def fake_notifier(*, persistent_store, initial_store_data):
        assert persistent_store is None
        assert initial_store_data == {"state:telegram_caps": {}}
        raise StopStartup

    monkeypatch.setattr(app, "TelegramNotifier", fake_notifier)
    with pytest.raises(StopStartup):
        app.main_loop()
    assert {item[0] for item in calls} == {"son_tarama", "hydrate", "digest", "cache"}
    assert not mirror._MIRROR_WRITES_ENABLED
    assert session.calls == []


def test_deploy_check_does_not_write_or_use_stale_remote_heartbeat(monkeypatch, capsys):
    import deploy_check
    import requests

    class Response:
        status_code = 200
        text = ""

    monkeypatch.setattr(requests, "get", lambda *a, **k: Response())
    monkeypatch.setattr(requests, "post", lambda *a, **k: pytest.fail("Supabase yazma testi yapıldı"))
    monkeypatch.setattr(deploy_check, "_heartbeat_kontrol", lambda *a, **k: pytest.fail("bayat heartbeat okundu"))
    deploy_check.kontrol_supabase("https://demo.supabase.co", "fake-key")
    assert "salt okunur" in capsys.readouterr().out
