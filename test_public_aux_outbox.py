"""No network: standalone public copies survive a definite quota failure."""
import json
import threading
from datetime import timedelta
from types import SimpleNamespace

import config
from bot.domain_alarm_service import dispatch_domain_alarm_candidates
from bot.stabil_service import StabilAlarmCandidate, dispatch_stabil_scan_candidates
from public_aux_outbox import PublicAuxOutbox, auxiliary_event_id
from test_domain_alarm_service import _aday


class FakeOwner:
    def __init__(self, outcomes=()):
        self.public_enabled = True
        self.public_chat_id = "-10012345"
        self._public_send_lck = threading.RLock()
        self._son_public_deneme = "bilinmiyor"
        self.outcomes = list(outcomes)
        self.attempts = []
        self.graphics = []
        self.graphic_count = 2

    def send_to_public(self, text):
        self.attempts.append(text)
        outcome = self.outcomes.pop(0) if self.outcomes else "gonderildi"
        self._son_public_deneme = outcome
        return outcome == "gonderildi"

    def public_grafik_bagla(self, identity, graphics):
        self.graphics.append((identity, graphics))
        return self.graphic_count


def _graphics():
    return {"goruntular": [{"tf": "4h", "goruntu": {"close": 1}},
                            {"tf": "1d", "goruntu": {"close": 2}}]}


def test_budget_retry_survives_restart_without_repeating_text_or_images(tmp_path):
    owner = FakeOwner(["butce"])
    queue = PublicAuxOutbox(owner, tmp_path)
    accepted, sent = queue.submit("event-a", "alarm", identity={"stock_name": "A"}, graphics=_graphics())
    assert accepted and not sent
    assert queue.status()["pending"] == 1
    assert json.loads(queue.path.read_text())["rows"][0]["status"] == "pending"

    owner2 = FakeOwner(["gonderildi"])
    recovered = PublicAuxOutbox(owner2, tmp_path)
    assert recovered.flush() == 1
    assert owner2.attempts == ["alarm"]
    assert len(owner2.graphics) == 1
    assert recovered.status() == {"available": True, "pending": 0, "review": 0, "completed": 1}
    assert recovered.submit("event-a", "alarm", graphics=_graphics()) == (True, True)
    assert recovered.flush() == 0
    assert owner2.attempts == ["alarm"] and len(owner2.graphics) == 1


def test_ambiguous_response_never_retries_without_operator_review(tmp_path):
    owner = FakeOwner(["belirsiz", "gonderildi"])
    queue = PublicAuxOutbox(owner, tmp_path)
    assert queue.submit("timeout", "may have arrived") == (True, False)
    assert queue.status()["review"] == 1
    assert queue.flush() == 0 and len(owner.attempts) == 1
    recovered_owner = FakeOwner(["gonderildi"])
    recovered = PublicAuxOutbox(recovered_owner, tmp_path)
    assert recovered.flush() == 0 and recovered_owner.attempts == []
    assert recovered.status()["review"] == 1


def test_request_interrupted_by_crash_becomes_uncertain(tmp_path):
    owner = FakeOwner(["butce"])
    queue = PublicAuxOutbox(owner, tmp_path)
    assert queue.submit("crash", "alarm")[0]
    raw = json.loads(queue.path.read_text())
    raw["rows"][0]["status"] = "sending"
    queue.path.write_text(json.dumps(raw))
    recovered_owner = FakeOwner()
    recovered = PublicAuxOutbox(recovered_owner, tmp_path)
    assert recovered.status()["review"] == 1
    assert recovered.flush() == 0 and not recovered_owner.attempts


def test_changed_target_and_expired_entries_are_not_silently_sent(tmp_path):
    owner = FakeOwner(["butce"])
    queue = PublicAuxOutbox(owner, tmp_path)
    assert queue.submit("old-target", "private channel message")[0]
    owner.public_chat_id = "-10067890"
    assert queue.flush() == 0
    assert queue.status()["review"] == 1 and len(owner.attempts) == 1

    owner2 = FakeOwner(["butce"])
    queue2 = PublicAuxOutbox(owner2, tmp_path / "expiry")
    assert queue2.submit("old", "stale alert")[0]
    queue2.rows[0]["created"] = (queue2._now() - timedelta(days=1)).isoformat()
    assert queue2.flush() == 0 and len(owner2.attempts) == 1
    assert queue2.status()["review"] == 1


def test_failed_snapshot_write_prevents_network_call(monkeypatch, tmp_path):
    owner = FakeOwner()
    queue = PublicAuxOutbox(owner, tmp_path)
    def fail():
        raise OSError("disk full")
    monkeypatch.setattr(queue, "_save", fail)
    assert queue.submit("no-disk", "alarm") == (False, False)
    assert owner.attempts == [] and queue.rows == []


def test_partial_graphics_are_flagged_for_review_without_resending_text(tmp_path):
    owner = FakeOwner()
    owner.graphic_count = 1
    queue = PublicAuxOutbox(owner, tmp_path)
    assert queue.submit("partial", "alarm", graphics=_graphics()) == (True, True)
    assert queue.status()["review"] == 1
    assert queue.flush() == 0 and owner.attempts == ["alarm"] and len(owner.graphics) == 1


def test_unreadable_file_is_not_overwritten(tmp_path):
    path = tmp_path / "telegram_public_aux.json"
    path.write_text("not-json")
    owner = FakeOwner()
    queue = PublicAuxOutbox(owner, tmp_path)
    assert not queue.status()["available"]
    assert queue.submit("event", "alarm") == (False, False)
    assert path.read_text() == "not-json" and owner.attempts == []


def test_event_ids_are_stable_and_order_independent():
    assert auxiliary_event_id("burst", [("A", "1h"), ("B", "4h")]) == (
        auxiliary_event_id("burst", [("B", "4h"), ("A", "1h")])
    )
    assert auxiliary_event_id("domain", [("A", "1h")]) != auxiliary_event_id("stabil", [("A", "1h")])


class RoutedNotifier(FakeOwner):
    def __init__(self, directory):
        super().__init__(["butce", "gonderildi"])
        self.enabled = True
        self.dm = []
        self.aux = PublicAuxOutbox(self, directory)

    def send_text(self, text):
        self.dm.append(text)
        return True, "ok"

    def public_ozel_gonder(self, event_id, text, *, identity=None, graphics=None):
        return self.aux.submit(event_id, text, identity=identity, graphics=graphics)

    def grafik_kuyruga_ekle(self, *_args, **_kwargs):
        return 0


def test_domain_dm_success_no_longer_loses_quota_blocked_public_copy(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM", True)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_DM", True)
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM_PUBLIC", True)
    n = RoutedNotifier(tmp_path)
    cand = _aday(grafik_verisi_public=_graphics())
    state_path = str(tmp_path / "domain-state.json")
    first = dispatch_domain_alarm_candidates([cand], n, state_path=state_path)
    assert first["tekil_gonderilen"] == 1 and len(n.dm) == 1
    assert n.aux.status()["pending"] == 1 and not n.graphics
    # The global domain seal prevents a second DM; the separate queue carries public.
    assert dispatch_domain_alarm_candidates([cand], n, state_path=state_path)["filtrelendi"] == 1
    assert len(n.dm) == 1
    assert n.aux.flush() == 1 and len(n.graphics) == 1 and len(n.dm) == 1


def test_stabil_dm_success_no_longer_loses_quota_blocked_public_copy(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "STABIL_ALARM_DM", True)
    monkeypatch.setattr(config, "STABIL_ALARM_PUBLIC", True)
    n = RoutedNotifier(tmp_path)
    behavior = SimpleNamespace(reclaim_kind="close_reclaim", rank_score=1.5,
                               unchanged_days=26, touch_count=2, vol_ratio=1.35)
    cand = StabilAlarmCandidate(symbol="THYAO", bar_open_ts="2026-11-06T09:30:00+03:00",
                                bar_close_ts="2026-11-06T13:30:00+03:00", bar_label="06.11 13:30",
                                close_price=102.4, support_level=100.0, behavior=behavior,
                                card_lines=("Destek üstünde kapanış",), grafik_verisi_public=_graphics())
    result = dispatch_stabil_scan_candidates([cand], n, state_path=str(tmp_path / "stabil-state.json"))
    assert result["tekil_gonderilen"] == 1 and len(n.dm) == 1
    assert n.aux.status()["pending"] == 1
    assert n.aux.flush() == 1 and len(n.graphics) == 1 and len(n.dm) == 1


def test_real_notifier_public_budget_unblocks_without_repeating_dm(monkeypatch, tmp_path):
    import requests
    from test_alarm_routing_diagnostics import _notifier

    n = _notifier(monkeypatch, tmp_path)
    n.public_max_saatlik = 0
    n.public_min_aralik_sn = 0
    dm, public, images = [], [], []
    monkeypatch.setattr(n, "send_text", lambda text: (dm.append(text) or True, "ok"))
    monkeypatch.setattr(n, "public_grafik_bagla", lambda identity, graphic: images.append(identity) or 2)
    monkeypatch.setattr(requests, "post", lambda _url, json, timeout: (
        public.append(json) or SimpleNamespace(status_code=200, text="{}")))
    cand = _aday(grafik_verisi_public=_graphics())
    state_path = str(tmp_path / "domain-real-state.json")
    first = dispatch_domain_alarm_candidates([cand], n, state_path=state_path)
    assert first["tekil_gonderilen"] == 1 and len(dm) == 1 and public == []
    assert n.gonderim_durumu()["public_ozel_kuyruk"]["pending"] == 1
    n.public_max_saatlik = 20
    assert n.public_ozel_bosalt() == 1
    assert len(dm) == len(public) == len(images) == 1
    assert public[0]["text"] == dm[0] and public[0]["chat_id"] == n.public_chat_id
    assert n.public_ozel_bosalt() == 0 and len(public) == 1


def test_real_chart_snapshots_survive_restart_and_render_two_pngs(monkeypatch, tmp_path):
    import os
    import requests
    import grafik
    import transport.telegram as transport
    from test_alarm_routing_diagnostics import _notifier
    from test_domain_alarm_service import _frame

    monkeypatch.setenv("TELEGRAM_GRAFIK", "alarm")
    graphics = grafik.kare_listesi(
        None, "1d", _frame(), ek_cerceveler={"4h": _frame()}, adet=2, sembol="ASTOR")
    assert len(graphics["goruntular"]) == 2
    identity = {"stock_name": "ASTOR", "timeframe": "1d", "state": "YENI_DOMAIN"}
    original = _notifier(monkeypatch, tmp_path)
    original.public_max_saatlik = 0
    assert original.public_ozel_gonder("real-graphics", "text", identity=identity, graphics=graphics) == (True, False)
    row = json.loads((tmp_path / "telegram_public_aux.json").read_text())["rows"][0]
    assert row["graphics"] and not row["volatile_graphics"]

    restarted = _notifier(monkeypatch, tmp_path)
    restarted.public_min_aralik_sn = 0
    calls = []
    monkeypatch.setattr(requests, "post", lambda _url, json, timeout:
                        SimpleNamespace(status_code=200, text="{}"))
    def album(paths, captions, chat_id, notifier):
        assert all(os.path.getsize(path) > 1000 for path in paths)
        calls.append((list(paths), chat_id))
        return True, "ok"
    monkeypatch.setattr(transport, "medya_grubu_gonder", album)
    assert restarted.public_ozel_bosalt() == 1
    assert len(calls) == 1 and len(calls[0][0]) == 2 and calls[0][1] == restarted.public_chat_id
    assert all(not os.path.exists(path) for path in calls[0][0])
    assert restarted.public_grafik_gonderilen == 2 and restarted._public_aux.status()["completed"] == 1


def test_text_sent_before_crash_resumes_only_its_graphics(tmp_path):
    owner = FakeOwner(["butce"])
    queue = PublicAuxOutbox(owner, tmp_path)
    assert queue.submit("text-done", "alarm", graphics=_graphics())[0]
    raw = json.loads(queue.path.read_text())
    raw["rows"][0].update(status="text_sent", text_sent=True)
    queue.path.write_text(json.dumps(raw))
    recovered_owner = FakeOwner()
    recovered = PublicAuxOutbox(recovered_owner, tmp_path)
    assert recovered.flush() == 0
    assert recovered_owner.attempts == [] and len(recovered_owner.graphics) == 1
    assert recovered.status()["completed"] == 1
