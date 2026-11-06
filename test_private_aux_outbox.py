"""Offline regressions for DM/public independent special-alert delivery."""
import json
from types import SimpleNamespace

import config
from bot.domain_alarm_service import dispatch_domain_alarm_candidates
from bot.stabil_service import dispatch_stabil_scan_candidates
from private_aux_outbox import PrivateAuxOutbox
from test_alarm_routing_diagnostics import _notifier
from test_domain_alarm_service import _aday
from test_stabil_domain_and_integration import _stabil_delivery_candidate


class _Owner:
    def __init__(self, outcomes=()):
        self.enabled = True
        self.chat_id = "12345"
        self.public_chat_id = "@FormationBot1"
        self.outcomes = list(outcomes)
        self.calls = []
        self.albums = []

    def send_text(self, text, deneme=2):
        self.calls.append((text, deneme))
        outcome = self.outcomes.pop(0) if self.outcomes else "ok"
        if outcome == "timeout":
            raise TimeoutError("ambiguous")
        if outcome == "ok":
            return True, "ok"
        return False, outcome

    def grafik_toplu_gonder(self, packages):
        self.albums.append(list(packages))
        return [True] * len(packages)


def test_definite_dm_rejection_survives_restart_and_is_retried_once(tmp_path):
    owner = _Owner(["HTTP 429: rate limited"])
    queue = PrivateAuxOutbox(owner, tmp_path)
    assert queue.submit("event", "dm text") == (True, False)
    assert owner.calls == [("dm text", 1)] and queue.status()["pending"] == 1
    recovered_owner = _Owner(["ok"])
    recovered = PrivateAuxOutbox(recovered_owner, tmp_path)
    assert recovered.flush() == 1
    assert recovered_owner.calls == [("dm text", 1)]
    assert recovered.flush() == 0 and recovered.status()["completed"] == 1


def test_ambiguous_dm_failure_or_crash_never_blindly_retries(tmp_path):
    for case, response in (("timeout", "timeout"), ("server", "HTTP 500: error")):
        owner = _Owner([response, "ok"])
        queue = PrivateAuxOutbox(owner, tmp_path / case)
        assert queue.submit(case, "dm") == (True, False)
        assert queue.status()["review"] == 1
        assert queue.flush() == 0 and len(owner.calls) == 1
        restored_owner = _Owner(["ok"])
        assert PrivateAuxOutbox(restored_owner, tmp_path / case).flush() == 0
        assert restored_owner.calls == []

    owner = _Owner(["HTTP 403: blocked"])
    queue = PrivateAuxOutbox(owner, tmp_path / "crash")
    assert queue.submit("crash", "dm")[0]
    data = json.loads(queue.path.read_text())
    data["rows"][0]["status"] = "sending"
    queue.path.write_text(json.dumps(data))
    restored_owner = _Owner(["ok"])
    restored = PrivateAuxOutbox(restored_owner, tmp_path / "crash")
    assert restored.status()["review"] == 1 and restored.flush() == 0
    assert restored_owner.calls == []


def test_changed_dm_target_is_never_replayed_to_another_person(tmp_path):
    owner = _Owner(["HTTP 429: rate limited"])
    queue = PrivateAuxOutbox(owner, tmp_path)
    assert queue.submit("one", "private")[0]
    owner.chat_id = "98765"
    assert queue.flush() == 0 and queue.status()["review"] == 1
    assert len(owner.calls) == 1


def test_dm_chart_snapshots_render_only_after_successful_text(monkeypatch, tmp_path):
    import grafik
    paths = []
    def render(_snapshot, tf):
        path = tmp_path / f"{tf}.png"
        path.write_bytes(b"PNG data")
        paths.append(path)
        return str(path), {}
    monkeypatch.setattr(grafik, "kareyi_yaz", render)
    monkeypatch.setattr(grafik, "disk_uygun_mu", lambda: True)
    owner = _Owner(["HTTP 429: rate limited", "ok"])
    queue = PrivateAuxOutbox(owner, tmp_path)
    graphics = {"sembol": "THYAO", "goruntular": [
        {"tf": "4h", "goruntu": {"a": 1}}, {"tf": "1d", "goruntu": {"a": 2}}]}
    assert queue.submit("graphic", "dm text", identity={"stock_name": "THYAO"}, graphics=graphics) == (True, False)
    assert owner.albums == []
    assert queue.flush() == 1 and len(owner.albums) == 1
    assert len(owner.albums[0]) == 2 and all(not path.exists() for path in paths)
    assert queue.status()["completed"] == 1


def test_public_success_and_dm_definite_failure_are_recovered_independently(monkeypatch, tmp_path):
    import requests
    n = _notifier(monkeypatch, tmp_path)
    n.public_min_aralik_sn = n.retry_bekleme_sn = 0
    calls = []
    def post(_url, json, timeout):
        calls.append(dict(json))
        dm_attempts = sum(c["chat_id"] == n.chat_id for c in calls)
        status = 429 if json["chat_id"] == n.chat_id and dm_attempts == 1 else 200
        return SimpleNamespace(status_code=status, text="{}", json=lambda: {})
    monkeypatch.setattr(requests, "post", post)
    cand = _aday()
    state = str(tmp_path / "domain.json")
    assert dispatch_domain_alarm_candidates([cand], n, state_path=state)["tekil_gonderilen"] == 1
    assert n._dm_aux.status()["pending"] == 1
    assert len([c for c in calls if c["chat_id"] == n.public_chat_id]) == 1
    assert dispatch_domain_alarm_candidates([cand], n, state_path=state)["filtrelendi"] == 1
    restarted = _notifier(monkeypatch, tmp_path)
    restarted.public_min_aralik_sn = restarted.retry_bekleme_sn = 0
    assert restarted.dm_ozel_bosalt() == 1
    assert len([c for c in calls if c["chat_id"] == n.chat_id]) == 2
    assert len([c for c in calls if c["chat_id"] == n.public_chat_id]) == 1


def test_real_dm_chart_snapshot_survives_restart_and_renders_album(monkeypatch, tmp_path):
    import os
    import requests
    import grafik
    import transport.telegram as transport
    from test_domain_alarm_service import _frame

    monkeypatch.setenv("TELEGRAM_GRAFIK", "alarm")
    graphics = grafik.kare_listesi(None, "1d", _frame(), ek_cerceveler={"4h": _frame()},
                                   adet=2, sembol="ASTOR")
    assert len(graphics["goruntular"]) == 2
    n = _notifier(monkeypatch, tmp_path)
    n.public_min_aralik_sn = n.retry_bekleme_sn = 0
    attempts = []
    def post(_url, json, timeout):
        attempts.append(json["chat_id"])
        code = 429 if json["chat_id"] == n.chat_id and attempts.count(n.chat_id) == 1 else 200
        return SimpleNamespace(status_code=code, text="{}", json=lambda: {})
    monkeypatch.setattr(requests, "post", post)
    state = str(tmp_path / "domain-with-images.json")
    dispatch_domain_alarm_candidates([_aday(grafik_verisi=graphics)], n, state_path=state)
    assert n._dm_aux.status()["pending"] == 1
    row = json.loads((tmp_path / "telegram_dm_aux.json").read_text())["rows"][0]
    assert row["graphics"] and not row["volatile_graphics"]
    restarted = _notifier(monkeypatch, tmp_path)
    restarted.public_min_aralik_sn = restarted.retry_bekleme_sn = 0
    albums = []
    def album(paths, captions, notifier):
        assert all(os.path.getsize(p) > 1000 for p in paths)
        albums.append(list(paths))
        return True, "ok"
    monkeypatch.setattr(transport, "medya_grubu_gonder", album)
    assert restarted.dm_ozel_bosalt() == 1
    assert len(albums) == 1 and len(albums[0]) == 2
    assert all(not os.path.exists(p) for p in albums[0])
    assert restarted._dm_aux.status()["completed"] == 1
    assert attempts.count(n.public_chat_id) == 1


def test_stabil_dm_failure_is_queued_even_if_public_succeeds(monkeypatch, tmp_path):
    import requests
    monkeypatch.setattr(config, "STABIL_ALARM_DM", True)
    monkeypatch.setattr(config, "STABIL_ALARM_PUBLIC", True)
    n = _notifier(monkeypatch, tmp_path)
    n.public_min_aralik_sn = n.retry_bekleme_sn = 0
    def post(_url, json, timeout):
        status = 429 if json["chat_id"] == n.chat_id else 200
        return SimpleNamespace(status_code=status, text="{}", json=lambda: {})
    monkeypatch.setattr(requests, "post", post)
    result = dispatch_stabil_scan_candidates([_stabil_delivery_candidate()], n,
                                             state_path=str(tmp_path / "stabil.json"))
    assert result["tekil_gonderilen"] == 1
    assert n._dm_aux.status()["pending"] == 1 and n._public_aux.status()["completed"] == 1


def test_failed_public_checkpoint_does_not_mark_candidate_or_repeat_dm(monkeypatch, tmp_path):
    import requests
    n = _notifier(monkeypatch, tmp_path)
    n.public_min_aralik_sn = n.retry_bekleme_sn = 0
    calls = []
    monkeypatch.setattr(requests, "post", lambda _url, json, timeout: (
        calls.append(dict(json)) or SimpleNamespace(status_code=200, text="{}")))
    save = n._public_aux._save
    def fail():
        raise OSError("disk full")
    monkeypatch.setattr(n._public_aux, "_save", fail)
    cand = _aday()
    state = tmp_path / "domain.json"
    dispatch_domain_alarm_candidates([cand], n, state_path=str(state))
    assert not state.exists()
    assert [c["chat_id"] for c in calls] == [n.chat_id]
    monkeypatch.setattr(n._public_aux, "_save", save)
    dispatch_domain_alarm_candidates([cand], n, state_path=str(state))
    assert state.exists()
    assert [c["chat_id"] for c in calls].count(n.chat_id) == 1
    assert [c["chat_id"] for c in calls].count(n.public_chat_id) == 1


def test_failed_dm_checkpoint_does_not_mark_candidate_or_repeat_public(monkeypatch, tmp_path):
    import requests
    n = _notifier(monkeypatch, tmp_path)
    n.public_min_aralik_sn = n.retry_bekleme_sn = 0
    calls = []
    monkeypatch.setattr(requests, "post", lambda _url, json, timeout: (
        calls.append(dict(json)) or SimpleNamespace(status_code=200, text="{}")))
    save = n._dm_aux._save
    def fail():
        raise OSError("disk full")
    monkeypatch.setattr(n._dm_aux, "_save", fail)
    cand = _aday()
    state = tmp_path / "domain.json"
    dispatch_domain_alarm_candidates([cand], n, state_path=str(state))
    assert not state.exists()  # missing DM is still eligible on the next scan
    assert [c["chat_id"] for c in calls] == [n.public_chat_id]
    monkeypatch.setattr(n._dm_aux, "_save", save)
    dispatch_domain_alarm_candidates([cand], n, state_path=str(state))
    assert state.exists()
    assert [c["chat_id"] for c in calls].count(n.public_chat_id) == 1
    assert [c["chat_id"] for c in calls].count(n.chat_id) == 1
