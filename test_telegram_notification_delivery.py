"""Deterministic Telegram delivery/restart tests; no live Telegram calls."""
from datetime import date, datetime, timedelta, timezone
import json
import time

import notifier as notifier_module
from config import ISTANBUL_TZ
from notification_outbox import NotificationOutbox
from notifier import TelegramNotifier
from telegram_alert_flow import DeferredAlertBuffer


UTC = timezone.utc


def _notifier(tmp_path, *, clock=None):
    notifier = TelegramNotifier.__new__(TelegramNotifier)
    notifier.enabled = True
    notifier.token = "123456:fake-token"
    notifier.chat_id = "private-chat"
    notifier.channel_id = "public-channel"
    notifier.last_sent = {}
    notifier.persistent_store = None
    notifier.initial_store_data = {}
    notifier.cooldown_hours = 4
    notifier.max_saatlik = 20
    notifier.max_gunluk = 120
    notifier._saatlik_zamanlar = []
    notifier._gunluk_sayac = 0
    notifier._gunluk_tarih = datetime.now().date()
    notifier._kap_uyarildi = False
    notifier._cooldown_kaydet = lambda: None
    notifier._gonderim_kaydet = lambda: None
    notifier.public_min_quality = 80
    notifier.public_states = {"FORMASYON_TAMAMLANDI", "RETEST_BASARILI"}
    notifier.public_sikisma_min = 0.8
    notifier._delivery_interval_seconds = 0
    notifier._outbox_path = str(tmp_path / "telegram_delivery.json")
    notifier._outbox = NotificationOutbox(notifier._outbox_path, clock=clock or (lambda: datetime.now(UTC)))
    return notifier


def _alert(**overrides):
    data = {
        "stock_name": "THYAO",
        "timeframe": "1h",
        "pattern_name": "Simetrik Üçgen",
        "state": "FORMASYON_TAMAMLANDI",
        "confidence_score": 88,
        "critical_price_level": 101.0,
        "upper_now": 101.0,
        "lower_now": 95.0,
        "break_dir": 1,
        "timestamp": datetime(2026, 9, 25, 18, 30),
        "lifecycle_event_id": "COMPLETED:2026-09-25T18:30:00",
    }
    data.update(overrides)
    return data


def _ok_transport(_text, _chat_id):
    return True, 200, "ok", None, False


def test_send_claim_is_durable_before_fake_transport_and_same_event_is_idempotent(tmp_path):
    notifier = _notifier(tmp_path)
    calls = []

    def transport(text, chat_id):
        persisted = json.loads((tmp_path / "telegram_delivery.json").read_text())
        item = next(record for record in persisted["items"].values() if record["chat_id"] == chat_id)
        assert item["status"] == "sending"
        assert item["attempts"] == 1
        calls.append((text, chat_id))
        return _ok_transport(text, chat_id)

    notifier._send_text_direct = transport
    alert = _alert()
    assert notifier.send(alert) is True
    assert notifier.send(alert) is False  # already sent; no second transport call
    assert [chat_id for _text, chat_id in calls].count("private-chat") == 1
    assert [chat_id for _text, chat_id in calls].count("public-channel") == 1
    assert notifier._outbox.counts()["sent"] == 2


def test_formation_decision_is_durable_before_domain_context_and_restarts_with_fallback(tmp_path):
    notifier = _notifier(tmp_path)
    alert = _alert(state="KIRILIM_ADAYI")
    assert notifier.prepare_formation(alert) is True
    prepared = next(iter(notifier._outbox.state["items"].values()))
    assert prepared["status"] == "prepared"
    assert notifier._outbox.due_items(limit=10) == []  # same process waits for context

    restarted = _notifier(tmp_path)
    recovered = next(iter(restarted._outbox.state["items"].values()))
    assert recovered["status"] == "pending"
    assert "needs_context" in recovered and recovered["needs_context"] is False
    sent_texts = []
    restarted._send_text_direct = lambda text, _chat: sent_texts.append(text) or _ok_transport(text, "private-chat")
    restarted.drain_outbox(max_items=1)
    assert len(sent_texts) == 1
    assert "Yapı:" not in sent_texts[0]  # Formation-only fallback, no stale domain data


def test_same_scan_activates_prepared_message_with_context_before_transport(tmp_path):
    notifier = _notifier(tmp_path)
    alert = _alert(state="KIRILIM_ADAYI")
    assert notifier.prepare_formation(alert) is True
    alert["dm_context"] = {"structure": "2H BOS ↑", "volume": "Yüksek"}
    transport_state = []

    def transport(text, _chat):
        item = next(iter(notifier._outbox.state["items"].values()))
        transport_state.append((item["status"], text))
        return _ok_transport(text, "private-chat")

    notifier._send_text_direct = transport
    assert notifier.send(alert) is True
    assert transport_state[0][0] == "sending"
    assert "Yapı: 2H BOS ↑" in transport_state[0][1]
    assert notifier._outbox.counts()["prepared"] == 0


def test_failed_dm_is_durable_and_retried_after_restart(tmp_path):
    now = [datetime(2026, 9, 25, 18, 31, tzinfo=UTC)]
    clock = lambda: now[0]
    first = _notifier(tmp_path, clock=clock)
    first._send_text_direct = lambda *_args: (False, 500, "temporary", None, False)

    assert first.send(_alert()) is False
    item = next(iter(first._outbox.state["items"].values()))
    assert item["status"] == "pending"
    assert item["attempts"] == 1
    assert item["next_attempt_at"] > item["created_at"]

    # A process restart recovers the persisted queue. Advancing beyond the
    # exponential backoff makes the same event eligible without rescanning it.
    now[0] += timedelta(seconds=31)
    restarted = _notifier(tmp_path, clock=clock)
    calls = []
    restarted._send_text_direct = lambda text, chat_id: calls.append(chat_id) or _ok_transport(text, chat_id)
    delivered = restarted.drain_outbox(max_items=1)

    assert len(calls) == 1
    assert delivered[0]["kind"] == "formation"
    recovered = restarted._outbox.get(delivered[0]["id"])
    assert recovered["status"] == "sent"
    assert recovered["attempts"] == 2


def test_crash_after_claim_before_transport_recovers_pending(tmp_path):
    now = [datetime(2026, 9, 25, 18, 31, tzinfo=UTC)]
    clock = lambda: now[0]
    first = _notifier(tmp_path, clock=clock)
    assert first.prepare_formation(_alert(state="KIRILIM_ADAYI")) is True
    item = next(iter(first._outbox.state["items"].values()))
    assert first._outbox.activate_prepared(item["id"], item["fallback_text"])
    assert first._outbox.claim(item["id"])["status"] == "sending"

    now[0] += timedelta(seconds=31)
    restarted = _notifier(tmp_path, clock=clock)
    now[0] += timedelta(seconds=31)  # recovery schedules its bounded backoff
    due = restarted._outbox.due_items(limit=1)
    assert [candidate["id"] for candidate in due] == [item["id"]]
    assert due[0]["attempts"] == 1  # claim attempt remains accounted for


def test_transport_success_then_sent_persistence_crash_is_ambiguous(tmp_path):
    now = [datetime(2026, 9, 25, 18, 31, tzinfo=UTC)]
    clock = lambda: now[0]
    first = _notifier(tmp_path, clock=clock)
    first.prepare_formation(_alert(state="KIRILIM_ADAYI"))
    accepted = []
    first._send_text_direct = lambda text, chat_id: accepted.append(chat_id) or _ok_transport(text, chat_id)

    def crash_before_sent_commit(_item_id):
        raise SystemExit("injected crash immediately after transport success")

    first._outbox.mark_sent = crash_before_sent_commit
    try:
        first.send(_alert(state="KIRILIM_ADAYI"))
    except SystemExit:
        pass
    else:
        raise AssertionError("fault injection did not interrupt sent persistence")
    assert accepted == ["private-chat"]

    now[0] += timedelta(seconds=31)
    restarted = _notifier(tmp_path, clock=clock)
    now[0] += timedelta(seconds=31)
    assert restarted._outbox.due_items(limit=1)  # possible duplicate: external acceptance is ambiguous


def test_crash_after_remote_acceptance_is_ambiguous_and_at_least_once(tmp_path):
    now = [datetime(2026, 9, 25, 18, 31, tzinfo=UTC)]
    clock = lambda: now[0]
    first = _notifier(tmp_path, clock=clock)
    accepted = []

    def accepted_then_crash(text, chat_id):
        accepted.append((text, chat_id))  # fake service accepted the message
        raise SystemExit("simulated process death before local sent persistence")

    first._send_text_direct = accepted_then_crash
    try:
        first.send(_alert(state="KIRILIM_ADAYI"))
    except SystemExit:
        pass
    else:
        raise AssertionError("fault injection did not interrupt delivery")
    assert len(accepted) == 1
    assert any(item["status"] == "sending" for item in first._outbox.state["items"].values())

    now[0] += timedelta(seconds=31)
    restarted = _notifier(tmp_path, clock=clock)
    now[0] += timedelta(seconds=31)  # restart recovery applies its own backoff
    assert restarted._outbox.due_items(limit=1)
    second_acceptance = []
    restarted._send_text_direct = lambda text, chat_id: second_acceptance.append(chat_id) or _ok_transport(text, chat_id)
    restarted.drain_outbox(max_items=1)
    assert len(second_acceptance) == 1  # a duplicate is possible; exactly-once is not claimed


def test_dm_and_public_fail_independently_and_public_has_no_private_context(tmp_path):
    notifier = _notifier(tmp_path)
    calls = []

    def transport(text, chat_id):
        calls.append((text, chat_id))
        if chat_id == "private-chat":
            return False, 500, "DM unavailable", None, False
        return _ok_transport(text, chat_id)

    notifier._send_text_direct = transport
    private_watch = [{
        "stock": "PRIVATE-WATCH-STOCK", "timeframe": "4h",
        "pattern_name": "Yükselen Üçgen", "state": "KIRILIM_ADAYI", "quality": 83,
    }]
    alert = _alert(watch_context=private_watch, dm_context={"structure": "1H BOS ↑", "volume": "Yüksek"})

    assert notifier.send(alert) is False  # API contract remains DM outcome
    assert [chat_id for _, chat_id in calls] == ["private-chat", "public-channel"]
    dm_text, public_text = calls[0][0], calls[1][0]
    assert "PRIVATE-WATCH-STOCK" in dm_text
    assert "1H BOS ↑" in dm_text
    assert "PRIVATE-WATCH-STOCK" not in public_text
    assert "Yapı:" not in public_text
    assert notifier._outbox.counts()["pending"] == 1
    assert notifier._outbox.counts()["sent"] == 1


def test_a_distinct_event_on_the_same_bar_shape_is_not_false_positive_dedup(tmp_path):
    notifier = _notifier(tmp_path)
    calls = []
    notifier._send_text_direct = lambda text, chat_id: calls.append(chat_id) or _ok_transport(text, chat_id)

    assert notifier.send(_alert(lifecycle_event_id="COMPLETED:bar:100")) is True
    assert notifier.send(_alert(lifecycle_event_id="COMPLETED:bar:101", timestamp=datetime(2026, 9, 25, 19, 30))) is True
    assert calls.count("private-chat") == 2


def test_scheduled_digest_idempotency_key_prevents_restart_replay(tmp_path):
    notifier = _notifier(tmp_path)
    calls = []
    notifier._send_text_direct = lambda text, chat_id: calls.append((text, chat_id)) or _ok_transport(text, chat_id)
    key = "daily-summary:dm:2026-09-25:18:45"

    assert notifier.send_text("digest payload", idempotency_key=key)[0] is True
    restarted = _notifier(tmp_path)
    restarted._send_text_direct = lambda *_args: (_ for _ in ()).throw(AssertionError("duplicate send"))
    assert restarted.send_text("different regenerated payload", idempotency_key=key)[0] is True
    assert len(calls) == 1


def test_watch_snapshot_mirrors_to_fake_store_and_restores_without_shared_disk(tmp_path):
    class Store:
        payload = None

        def upsert(self, key, value):
            assert key == "state:telegram_delivery"
            self.payload = value
            return True

    store = Store()
    source = NotificationOutbox(str(tmp_path / "source.json"), persistent_store=store)
    snapshot = {"date": "2026-09-25", "pending": [_alert(state="KIRILIM_ADAYI")], "reported": []}
    assert source.set_watch(snapshot)

    replacement = NotificationOutbox(
        str(tmp_path / "replacement.json"), initial_state=store.payload
    )
    assert replacement.get_watch() == snapshot


def test_same_day_watch_snapshot_restores_and_stale_day_is_rejected():
    now = datetime(2026, 9, 25, 12, 0)
    source = DeferredAlertBuffer()
    source.observe("THYAO", "1h", {
        "stock": "THYAO", "timeframe": "1h", "pattern_name": "Triangle",
        "state": "KIRILIM_ADAYI", "quality": 82,
    }, now)
    snapshot = source.snapshot(now)

    restored = DeferredAlertBuffer()
    assert restored.restore(snapshot, now) == 1
    assert len(restored) == 1
    assert restored.restore(snapshot, now + timedelta(days=1)) == 0
    assert len(restored) == 0


def test_sent_but_unacknowledged_formation_survives_restart_for_watch_reconciliation(tmp_path):
    notifier = _notifier(tmp_path)
    notifier._send_text_direct = _ok_transport
    assert notifier.send(_alert(state="KIRILIM_ADAYI")) is True
    item = next(iter(notifier._outbox.state["items"].values()))
    assert item["status"] == "sent"
    assert item["application_acknowledged"] is False

    restarted = _notifier(tmp_path)
    delivered = restarted.drain_outbox(max_items=1)
    assert len(delivered) == 1
    assert delivered[0]["id"] == item["id"]
    assert restarted.acknowledge_delivery(item["id"]) is True
    assert restarted._outbox.unacknowledged_sent() == []


def test_failed_application_ack_is_replayed_after_restart(tmp_path, monkeypatch):
    notifier = _notifier(tmp_path)
    notifier._send_text_direct = _ok_transport
    notifier.send(_alert(state="KIRILIM_ADAYI"))
    item = next(iter(notifier._outbox.state["items"].values()))
    monkeypatch.setattr(notifier._outbox, "_save", lambda **_kwargs: False)
    assert notifier.acknowledge_delivery(item["id"]) is False

    restarted = _notifier(tmp_path)
    assert [record["id"] for record in restarted._outbox.unacknowledged_sent()] == [item["id"]]


def test_telegram_429_retry_after_is_respected(tmp_path):
    now = [datetime(2026, 9, 25, 18, 31, tzinfo=UTC)]
    notifier = _notifier(tmp_path, clock=lambda: now[0])
    notifier._send_text_direct = lambda *_args: (False, 429, "flood control", 3600, False)
    assert notifier.send(_alert(state="KIRILIM_ADAYI")) is False
    item = next(iter(notifier._outbox.state["items"].values()))
    next_attempt = datetime.fromisoformat(item["next_attempt_at"])
    assert (next_attempt - now[0]).total_seconds() == 3600
    assert item["attempts"] == 1
    assert item["status"] == "pending"


def test_old_scheduled_digest_expires_instead_of_sending_next_day(tmp_path):
    now = [datetime(2026, 9, 25, 18, 0, tzinfo=UTC)]
    path = str(tmp_path / "outbox.json")
    first = NotificationOutbox(path, clock=lambda: now[0])
    first.enqueue("scheduled", {
        "text": "old digest", "chat_id": "chat", "kind": "scheduled",
        "destination": "scheduled_dm",
    })
    now[0] += timedelta(hours=7)
    restarted = NotificationOutbox(path, clock=lambda: now[0])
    assert restarted.get("scheduled")["status"] == "expired"
    assert restarted.due_items(limit=10) == []


def test_daily_caps_use_istanbul_calendar_not_host_utc_date(monkeypatch):
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            instant = datetime(2026, 10, 8, 22, 30, tzinfo=UTC)
            if tz is None:
                return instant.astimezone(ISTANBUL_TZ).replace(tzinfo=None)
            return instant.astimezone(tz)

    notifier = TelegramNotifier.__new__(TelegramNotifier)
    notifier._gunluk_tarih = date(2026, 10, 8)  # host UTC is still Oct 8
    notifier._gunluk_sayac = 7
    notifier._kap_uyarildi = True
    notifier._saatlik_zamanlar = [
        datetime(2026, 10, 9, 0, 45),  # 45 minutes old in Istanbul
        datetime(2026, 10, 8, 23, 0),  # 150 minutes old in Istanbul
    ]
    monkeypatch.setattr(notifier_module, "datetime", FrozenDateTime)

    notifier._gunu_sifirla_gerekirse()
    notifier._saatligi_temizle()

    assert notifier._gunluk_tarih == date(2026, 10, 9)
    assert notifier._gunluk_sayac == 0
    assert notifier._kap_uyarildi is False
    assert notifier._saatlik_zamanlar == [datetime(2026, 10, 9, 0, 45)]


def test_legacy_utc_cap_snapshot_does_not_reset_at_istanbul_midnight(tmp_path, monkeypatch):
    class FrozenHostClock(datetime):
        @classmethod
        def now(cls, tz=None):
            instant = datetime(2026, 10, 8, 22, 30, tzinfo=UTC)
            if tz is None:
                return instant.replace(tzinfo=None)  # previous writer's host-local UTC
            return instant.astimezone(tz)

    notifier = TelegramNotifier.__new__(TelegramNotifier)
    notifier.initial_store_data = {
        "state:telegram_caps": {
            "gunluk_tarih": "2026-10-08",
            "gunluk_sayac": 7,
            "saatlik": [],
        }
    }
    notifier._kap_dosya = str(tmp_path / "no-local-snapshot.json")
    monkeypatch.setattr(notifier_module, "datetime", FrozenHostClock)

    notifier._kap_yukle()

    assert notifier._gunluk_tarih == date(2026, 10, 9)
    assert notifier._gunluk_sayac == 7  # conservatively carry old UTC-day count
    assert notifier._saatlik_zamanlar == []


def test_cooldown_and_cap_writers_persist_explicit_istanbul_timezone(tmp_path):
    notifier = TelegramNotifier.__new__(TelegramNotifier)
    now = datetime.now(ISTANBUL_TZ).replace(tzinfo=None)
    notifier.cooldown_hours = 4
    notifier.last_sent = {"THYAO|event:complete": now}
    notifier._cooldown_dosya = str(tmp_path / "cooldowns.json")
    notifier.persistent_store = None
    notifier._cooldown_kaydet()
    saved_cooldown = json.loads((tmp_path / "cooldowns.json").read_text(encoding="utf-8"))
    assert saved_cooldown["THYAO|event:complete"].endswith("+03:00")

    notifier._gunluk_sayac = 1
    notifier._gunluk_tarih = now.date()
    notifier._saatlik_zamanlar = [now]
    notifier._kap_dosya = str(tmp_path / "caps.json")
    notifier._kap_kaydet()
    saved_caps = json.loads((tmp_path / "caps.json").read_text(encoding="utf-8"))
    assert saved_caps["timezone"] == "Europe/Istanbul"
    assert saved_caps["saatlik"][0].endswith("+03:00")
    assert saved_caps["updated_at"].endswith("+03:00")


def test_legacy_cooldown_and_cap_sources_merge_without_stale_remote_override(tmp_path):
    from notifier import TelegramNotifier

    now = datetime.now(ISTANBUL_TZ)
    local_cooldown = {
        "THYAO_Triangle_1h_FORMASYON_TAMAMLANDI": (now - timedelta(minutes=5)).isoformat(),
        "REMOTE_ONLY_event": (now - timedelta(minutes=10)).isoformat(),
    }
    remote_cooldown = {
        "THYAO_Triangle_1h_FORMASYON_TAMAMLANDI": (now - timedelta(minutes=20)).isoformat(),
    }
    cooldown_path = tmp_path / "cooldowns.json"
    cooldown_path.write_text(json.dumps(local_cooldown), encoding="utf-8")
    notifier = TelegramNotifier.__new__(TelegramNotifier)
    notifier.initial_store_data = {"state:telegram_cooldowns": remote_cooldown}
    notifier._cooldown_dosya = str(cooldown_path)
    notifier.last_sent = {}
    notifier.cooldown_hours = 4
    notifier._cooldown_yukle()
    assert notifier.last_sent["THYAO_Triangle_1h_FORMASYON_TAMAMLANDI"] == (now - timedelta(minutes=5)).replace(tzinfo=None)
    assert "REMOTE_ONLY_event" in notifier.last_sent

    today = now.date().isoformat()
    remote_t1 = now - timedelta(minutes=15)
    remote_t2 = now - timedelta(minutes=10)
    local_t1 = now - timedelta(minutes=8)
    cap_path = tmp_path / "caps.json"
    cap_path.write_text(json.dumps({
        "gunluk_tarih": today, "gunluk_sayac": 9, "saatlik": [local_t1.isoformat()],
    }), encoding="utf-8")
    notifier._kap_dosya = str(cap_path)
    notifier.initial_store_data["state:telegram_caps"] = {
        "gunluk_tarih": today, "gunluk_sayac": 10,
        "saatlik": [remote_t1.isoformat(), remote_t2.isoformat()],
    }
    notifier._gunluk_sayac = 0
    notifier._gunluk_tarih = now.date()
    notifier._saatlik_zamanlar = []
    notifier._kap_yukle()
    assert notifier._gunluk_sayac == 10  # conservative max on same day
    assert set(notifier._saatlik_zamanlar) == {
        remote_t1.replace(tzinfo=None), remote_t2.replace(tzinfo=None), local_t1.replace(tzinfo=None),
    }


def test_route_specific_legacy_cooldown_migration_does_not_cross_suppress(tmp_path):
    notifier = _notifier(tmp_path)
    alert = _alert()
    old_channel_key = notifier._cooldown_key(
        alert["stock_name"], alert["pattern_name"], alert["timeframe"],
        alert["state"], destination="channel",
    )
    notifier.last_sent[old_channel_key] = datetime.now()
    assert notifier.can_send(
        alert["stock_name"], alert["pattern_name"], alert["timeframe"], alert["state"],
        event_id=alert["lifecycle_event_id"], destination="channel",
    ) is False
    # A prior public post does not suppress the independent private DM.
    assert notifier.can_send(
        alert["stock_name"], alert["pattern_name"], alert["timeframe"], alert["state"],
        event_id=alert["lifecycle_event_id"], destination="dm",
    ) is True


def test_outbox_rejects_enqueue_when_no_durable_write_is_possible(tmp_path, monkeypatch):
    outbox = NotificationOutbox(str(tmp_path / "outbox.json"))
    monkeypatch.setattr(outbox, "_save", lambda **_kwargs: False)
    record, created = outbox.enqueue("id", {"text": "x", "chat_id": "chat", "kind": "scheduled"})
    assert record is None
    assert created is False
    assert outbox.get("id") is None


def test_empty_corrupt_old_and_partial_schema_states_are_isolated(tmp_path):
    path = tmp_path / "outbox.json"
    path.write_text("", encoding="utf-8")
    empty = NotificationOutbox(str(path))
    assert empty.counts()["pending"] == 0

    path.write_text('{"schema_version": 0, "items": {}}', encoding="utf-8")
    old = NotificationOutbox(str(path))
    assert old.counts()["pending"] == 0

    path.write_text(json.dumps({
        "schema_version": 1,
        "updated_at": datetime.now(UTC).isoformat(),
        "items": {
            "malformed": {"status": "pending", "text": {"not": "text"}, "chat_id": "chat",
                          "kind": "scheduled", "destination": "scheduled_dm", "series_key": []},
            "valid": {"status": "pending", "text": "ok", "chat_id": "chat",
                      "kind": "scheduled", "destination": "scheduled_dm"},
        },
        "watch": None,
    }), encoding="utf-8")
    partial = NotificationOutbox(str(path))
    assert partial.get("malformed")["status"] == "dead"
    assert [item["id"] for item in partial.due_items(limit=10)] == ["valid"]


def test_failure_retry_backoff_is_bounded_and_dead_letter_isolated(tmp_path):
    outbox = NotificationOutbox(str(tmp_path / "outbox.json"))
    record, _ = outbox.enqueue("bad", {"text": "bad", "chat_id": "chat", "kind": "scheduled"})
    claimed = outbox.claim("bad")
    outbox.mark_retry("bad", "permanent 400", permanent=True)
    assert outbox.get("bad")["status"] == "dead"
    good, _ = outbox.enqueue("good", {"text": "good", "chat_id": "chat", "kind": "scheduled"})
    assert outbox.due_items(limit=10)[0]["id"] == "good"


def test_two_scans_producing_same_event_concurrently_send_once(tmp_path):
    """Aşama 4 P4: iki tarama aynı lifecycle event'i EŞZAMANLI üretirse transport
    yalnız bir kez çağrılır. Outbox claim'i atomiktir (RLock + 'pending' durum
    kontrolü): ikinci thread claim alamaz, ikinci gönderim False döner. Bu, süreç
    içi yarışı kapatır; gerçek duplicate riski 'kabul sonrası sent-yazılamadı'
    penceresiyle sınırlıdır (test_crash_after_remote_acceptance...)."""
    import threading

    notifier = _notifier(tmp_path)
    transport_threads = []

    chat_cagrilari = []

    def yavas_transport(text, chat_id):
        chat_cagrilari.append(chat_id)
        transport_threads.append(threading.current_thread().name)
        time.sleep(0.05)  # claim penceresini genişlet: diğer thread tam bu arada dener
        return _ok_transport(text, chat_id)

    notifier._send_text_direct = yavas_transport
    alert = _alert()
    baraj = threading.Barrier(2)
    sonuclar = []

    def tarama():
        baraj.wait()
        sonuclar.append(notifier.send(alert))

    t1 = threading.Thread(target=tarama)
    t2 = threading.Thread(target=tarama)
    t1.start(); t2.start()
    t1.join(timeout=10); t2.join(timeout=10)

    # İkinci thread de True dönebilir: dönüş değeri 'durably sent' demektir,
    # 'bu thread transport yaptı' değil. Garanti tek transport çağrısıdır:
    assert len(sonuclar) == 2 and all(sonuclar)
    counts = notifier._outbox.counts()
    assert counts["sent"] == 2                    # dm + channel, tek kopya
    assert counts.get("pending", 0) == 0 and counts.get("sending", 0) == 0
    assert sorted(chat_cagrilari) == ["private-chat", "public-channel"]
    assert len(transport_threads) == 2            # her hedefe tam bir transport
