"""Regressions for HTTP auth, Telegram delivery, public queues and chart safety.

All Telegram/DB calls are faked; the HTTP cases use a real local server.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
import http.client
import json
import os
import threading
import time
from types import SimpleNamespace

import numpy as np
import pytest

import grafik
import main as main_mod
import notifier
import state.persistence as persistence
import telegram_commands as commands
import transport.telegram as telegram
from health_server import start_render_health_server
from supabase_store import SupabaseStore

TOKEN = "123456789:AAtestsecret_not_real_0123456789"
GROUP = "-1001234567890"
DM = "123456789"


class Response:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self.payload = {"ok": status == 200} if payload is None else payload
        self.text = json.dumps(self.payload)

    def json(self):
        return self.payload


class ReplySession:
    def __init__(self, statuses=()):
        self.statuses = list(statuses)
        self.calls = []

    def post(self, url, json=None, timeout=None):
        self.calls.append(dict(json or {}))
        return Response(self.statuses.pop(0) if self.statuses else 200)


def update(uid=1, chat=DM, chat_type="private", text="/durum", sender=555, **message_extra):
    return {"update_id": uid, "message": {
        "message_id": uid, "date": int(time.time()), "text": text,
        "chat": {"id": int(chat), "type": chat_type},
        "from": {"id": sender, "is_bot": False}, **message_extra,
    }}


@contextmanager
def http_server(env=None, **kwargs):
    server = start_render_health_server({"PORT": "0", **(env or {})}, **kwargs)
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


def http_request(server, method, path, body=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=3)
    try:
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        conn.close()


def post_update(server, event):
    return http_request(server, "POST", "/webhook", json.dumps(event), {
        "Content-Type": "application/json",
        "X-Telegram-Bot-Api-Secret-Token": "test-secret",
    })


def event(stock="THYAO", identity="one", state="KIRILIM_TEYITLI", **extra):
    return {"stock_name": stock, "timeframe": "4h", "pattern_name": "Üçgen",
            "state": state, "confidence_score": 95, "critical_price_level": 40,
            "break_dir": 1, "formation_id": identity, **extra}


@pytest.fixture
def public_notifier(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", DM)
    monkeypatch.setenv("TELEGRAM_GROUP_ID", GROUP)
    monkeypatch.delenv("TELEGRAM_CHANNEL_ID", raising=False)
    n = notifier.TelegramNotifier()
    n.public_min_aralik_sn = 0
    n.retry_bekleme_sn = 0
    return n


def test_real_http_head_has_no_body_or_test_side_effect_and_rejects_unicode_secret():
    sent = []
    with http_server({"TELEGRAM_TEST_KEY": "valid", "TELEGRAM_WEBHOOK_SECRET": "test-secret"},
                     test_sender=lambda text: (sent.append(text) or True, "ok"),
                     webhook_handler=lambda obj: 200) as server:
        status, headers, body = http_request(server, "HEAD", "/test", headers={"X-Test-Key": "valid"})
        assert status == 200 and body == b"" and sent == []
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"
        status, _, body = http_request(server, "POST", "/webhook", "{}", {
            "X-Telegram-Bot-Api-Secret-Token": "é"})
        assert status == 403 and json.loads(body)["ok"] is False
        assert sent == []
        assert http_request(server, "GET", "/test", headers={"X-Test-Key": "valid"})[0] == 200
        assert len(sent) == 1


def test_real_http_rejects_ambiguous_framing_before_handler_runs():
    seen = []
    with http_server({"TELEGRAM_WEBHOOK_SECRET": "test-secret"},
                     webhook_handler=lambda obj: seen.append(obj) or 200) as server:
        conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=3)
        try:
            conn.putrequest("POST", "/webhook")
            conn.putheader("X-Telegram-Bot-Api-Secret-Token", "test-secret")
            conn.putheader("Transfer-Encoding", "chunked")
            conn.putheader("Content-Length", "2")
            conn.endheaders()
            conn.send(b"{}")
            assert conn.getresponse().status == 400
        finally:
            conn.close()
        assert seen == []


def test_real_http_rate_limit_does_not_trust_client_forwarded_header():
    with http_server({"TELEGRAM_TEST_KEY": "valid", "HEALTH_RATE_LIMIT_PER_MIN": "1"},
                     test_sender=lambda text: (True, "ok")) as server:
        h1 = {"X-Test-Key": "valid", "X-Forwarded-For": "1.2.3.4"}
        h2 = {"X-Test-Key": "valid", "X-Forwarded-For": "8.8.8.8"}
        assert http_request(server, "HEAD", "/test", headers=h1)[0] == 200
        status, headers, body = http_request(server, "HEAD", "/test", headers=h2)
        assert status == 429 and body == b"" and headers["Retry-After"] == "60"
        assert headers["X-Frame-Options"] == "DENY"


def test_trusted_proxy_chain_stops_at_first_untrusted_hop():
    env = {"TELEGRAM_TEST_KEY": "valid", "HEALTH_RATE_LIMIT_PER_MIN": "1",
           "HEALTH_TRUSTED_PROXY_CIDRS": "127.0.0.0/8,10.0.0.0/8"}
    with http_server(env, test_sender=lambda text: (True, "ok")) as server:
        common = {"X-Test-Key": "valid"}
        first = {**common, "X-Forwarded-For": "1.1.1.1, 8.8.8.8, 10.0.0.2"}
        spoof = {**common, "X-Forwarded-For": "9.9.9.9, 8.8.8.8, 10.0.0.2"}
        assert http_request(server, "HEAD", "/test", headers=first)[0] == 200
        assert http_request(server, "HEAD", "/test", headers=spoof)[0] == 429
        assert set(server.rate_kayitlari) == {"8.8.8.8"}


def test_webhook_failed_reply_retries_only_reply_and_starts_job_after_delivery(monkeypatch):
    session, runs, jobs = ReplySession([503, 200]), [], []
    def handler(_):
        runs.append(1)
        return commands.ArkaPlanYaniti("hazır", lambda: jobs.append(1))
    listener = commands.TelegramCommandListener(TOKEN, DM, {"durum": handler}, session=session)
    monkeypatch.setattr(main_mod, "_telegram_update_processor_ref", listener)
    with http_server({"TELEGRAM_WEBHOOK_SECRET": "test-secret"},
                     webhook_handler=main_mod._telegram_webhook_isle) as server:
        assert post_update(server, update())[0] == 503
        assert runs == [1] and jobs == []
        assert post_update(server, update())[0] == 200
        assert runs == [1] and jobs == [1]
        assert post_update(server, update())[0] == 200
        assert len(session.calls) == 2
        assert all(call["chat_id"] == DM for call in session.calls)


def test_webhook_transient_admin_lookup_retries_before_running_command(monkeypatch):
    session, runs, checks = ReplySession(), [], []
    def checker(chat, user):
        checks.append((chat, user))
        if len(checks) == 1:
            raise TimeoutError("geçici hata")
        return True
    listener = commands.TelegramCommandListener(
        TOKEN, DM, {"durum": lambda _: runs.append(1) or "ok"}, session=session,
        public_chat_ids=[GROUP], public_commands=["durum"], admin_checker=checker)
    monkeypatch.setattr(main_mod, "_telegram_update_processor_ref", listener)
    message = update(chat=GROUP, chat_type="supergroup")
    with http_server({"TELEGRAM_WEBHOOK_SECRET": "test-secret"},
                     webhook_handler=main_mod._telegram_webhook_isle) as server:
        assert post_update(server, message)[0] == 503
        assert runs == [] and session.calls == []
        assert post_update(server, message)[0] == 200
        assert runs == [1] and len(checks) == 2
        assert session.calls[0]["chat_id"] == GROUP


def test_production_admin_lookup_distinguishes_transient_failure(monkeypatch):
    answers = [TimeoutError("geçici"), Response(200, {"ok": True, "result": {"status": "administrator"}})]
    monkeypatch.setattr(main_mod, "_telegram_token_al", lambda: TOKEN)
    def api(*args, **kwargs):
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer
    monkeypatch.setattr(main_mod, "_telegram_api_cagri", api)
    listener = commands.TelegramCommandListener(
        TOKEN, DM, {}, admin_checker=lambda c, u: main_mod._telegram_yonetici_mi(c, u, hata_yukselt=True))
    assert listener._yonetici_mi(GROUP, "555") is None
    assert listener._yonetici_mi(GROUP, "555") is True
    assert answers == []


@pytest.mark.parametrize("kind", ["wrong_sender_chat", "anonymous", "bot", "misconfigured_dm", "missing_type"])
def test_untrusted_group_or_sender_never_gets_dm_privileges(kind):
    session, calls = ReplySession(), []
    listener = commands.TelegramCommandListener(
        TOKEN, GROUP if kind in {"misconfigured_dm", "missing_type"} else DM,
        {"durum": lambda _: calls.append(1) or "ok"}, session=session,
        public_chat_ids=["@official"] if kind == "wrong_sender_chat" else [GROUP],
        public_commands=[] if kind in {"misconfigured_dm", "missing_type"} else ["durum"],
        admin_checker=lambda *_: True)
    msg = update(chat=GROUP, chat_type="supergroup")
    if kind == "wrong_sender_chat":
        msg["message"]["sender_chat"] = {"username": "official"}
    if kind == "anonymous":
        msg["message"]["sender_chat"] = {"id": -100999}
    if kind == "bot":
        msg["message"]["from"]["is_bot"] = True
    if kind == "missing_type":
        msg["message"]["chat"].pop("type")
    assert listener.handle_update(msg) is None
    assert calls == [] and session.calls == []


def test_public_only_graph_command_starts_job_with_group_target(monkeypatch):
    n = SimpleNamespace(enabled=False, token=TOKEN)
    calls, started = [], threading.Event()
    def worker(istek, _notifier, _manager):
        calls.append(dict(istek))
        started.set()
        with main_mod._grafik_is_kilidi:
            main_mod._grafik_aktif_is.clear()
    monkeypatch.setattr(main_mod, "_notifier_ref", n)
    monkeypatch.setattr(main_mod, "_deque_manager_ref", None)
    monkeypatch.setattr(main_mod, "_grafik_isi_calistir", worker)
    main_mod._grafik_aktif_is.clear()
    listener = commands.TelegramCommandListener(
        TOKEN, "", {"grafik": main_mod._komut_grafik}, session=ReplySession(),
        public_chat_ids=[GROUP], public_commands=["grafik"], admin_checker=lambda *_: True)
    try:
        reply = listener.handle_update(update(chat=GROUP, chat_type="supergroup", text="/grafik THYAO 4s"))
        assert "bu gruba" in reply
        assert started.wait(2)
        assert calls[0]["hedef_sohbet"] == GROUP
        assert calls[0]["tfler"] == ("4h",)
    finally:
        main_mod._grafik_aktif_is.clear()


@pytest.mark.parametrize("target", ["dm", "group", "public"])
@pytest.mark.parametrize("result", ["timeout", "server_error", "bad_request"])
def test_album_retry_only_after_definitive_rejection(public_notifier, monkeypatch, tmp_path, target, result):
    calls = []
    def multipart(method, token, fields, files, timeout=20):
        calls.append((method, str(fields["chat_id"])))
        if method == "sendMediaGroup":
            if result == "timeout":
                raise TimeoutError("response was lost")
            return Response(400 if result == "bad_request" else 503)
        return Response()
    monkeypatch.setattr(telegram, "_multipart_cagri", multipart)
    paths = []
    for i in range(2):
        p = tmp_path / f"{i}.png"
        p.write_bytes(b"PNG" + bytes([i]))
        paths.append(str(p))
    packets = [(path, "caption") for path in paths]
    n = public_notifier
    if target == "dm":
        outcomes = n.grafik_toplu_gonder(packets)
    elif target == "group":
        outcomes = n.grafik_sohbete_gonder(packets, chat_id=GROUP)
    else:
        record = event()
        n._public_grafik[n._public_kuyruk_anahtari(record)] = {
            "goruntular": [{"tf": "4h", "goruntu": {"yol": paths[0]}},
                           {"tf": "1d", "goruntu": {"yol": paths[1]}}]}
        outcomes = [bool(n.public_grafik_gonder(record))] * 2
    methods = [method for method, _ in calls]
    assert methods == (["sendMediaGroup", "sendPhoto", "sendPhoto"] if result == "bad_request"
                       else ["sendMediaGroup"])
    assert outcomes == [result == "bad_request"] * 2
    assert all(not os.path.exists(path) for path in paths)
    assert all(target_id == (DM if target == "dm" else GROUP) for _, target_id in calls)


def test_photo_rejects_symlink_fifo_and_oversized_file_before_network(monkeypatch, tmp_path):
    calls = []
    api = lambda *args, **kwargs: calls.append(args) or Response()
    secret = tmp_path / "private"
    secret.write_bytes(b"private contents")
    link = tmp_path / "link.png"
    link.symlink_to(secret)
    fifo = tmp_path / "pipe.png"
    os.mkfifo(fifo)
    large = tmp_path / "large.png"
    with open(large, "wb") as out:
        out.truncate(telegram.FOTO_MAKS_BAYT + 1)
    for path in (link, fifo, large):
        ok, _ = telegram.foto_gonder(path, chat_id=DM, token=TOKEN, api=api)
        assert ok is False
    assert calls == [] and secret.read_bytes() == b"private contents"


def test_album_total_size_limit_fails_before_network(monkeypatch, tmp_path):
    monkeypatch.setattr(telegram, "FOTO_MAKS_BAYT", 8)
    monkeypatch.setattr(telegram, "ALBUM_MAKS_BAYT", 9)
    files = [tmp_path / f"{i}.png" for i in range(2)]
    for path in files:
        path.write_bytes(b"123456")
    calls = []
    ok, reason = telegram.medya_grubu_gonder(files, chat_id=DM, token=TOKEN,
                                             api=lambda *a, **k: calls.append(1))
    assert not ok and telegram.medya_kesin_reddedildi(reason)
    assert calls == []


def test_group_chart_rejects_other_private_target_and_cleans_files(public_notifier, tmp_path, monkeypatch):
    path = tmp_path / "chart.png"
    path.write_bytes(b"png")
    calls = []
    monkeypatch.setattr(telegram, "foto_gonder", lambda *a, **k: calls.append(1) or (True, "ok"))
    assert public_notifier.grafik_sohbete_gonder([(str(path), "x")], chat_id="999999999") == [False]
    assert calls == [] and not path.exists()


def test_public_chart_snapshot_survives_restart_and_keeps_types(public_notifier, monkeypatch, tmp_path):
    now = datetime(2026, 11, 5, 9, 30, tzinfo=timezone.utc)
    image = {"goruntular": [{"tf": "4h", "goruntu": {"tarih": now, "hacim": np.int64(42)}}]}
    data = event(grafik_verisi_public=image)
    assert public_notifier.public_kuyruk(data)
    assert "grafik_verisi_public" not in data
    record = persistence.gunluk_durum_yukle()["public"]["kuyruk"][0]
    assert "_public_grafik_snapshot" in record
    recreated = notifier.TelegramNotifier()
    recreated.public_min_aralik_sn = 0
    assert len(recreated._public_kuyruk) == 1 and recreated._public_grafik == {}
    rendered, delivered = [], []
    def render(chart, tf):
        rendered.append((chart, tf))
        path = tmp_path / "rendered.png"
        path.write_bytes(b"png")
        return str(path), {}
    def send_photo(path, chat_id=None, **kwargs):
        delivered.append((path, chat_id, os.path.exists(path)))
        return True, "ok"
    monkeypatch.setattr(grafik, "kareyi_yaz", render)
    monkeypatch.setattr(telegram, "foto_gonder", send_photo)
    monkeypatch.setattr(recreated, "send_to_public", lambda text: True)
    assert recreated.public_bosalt() == 1
    assert rendered[0][0]["tarih"] == now
    assert isinstance(rendered[0][0]["tarih"], datetime)
    assert rendered[0][0]["hacim"] == 42 and isinstance(rendered[0][0]["hacim"], int)
    assert delivered[0][1:] == (GROUP, True)
    assert not os.path.exists(delivered[0][0])
    assert persistence.gunluk_durum_yukle()["public"]["kuyruk"] == []


def test_simultaneous_public_flushes_do_not_duplicate_messages(public_notifier, monkeypatch):
    n = public_notifier
    assert n.public_kuyruk(event())
    entered, release, twice = threading.Event(), threading.Event(), threading.Event()
    calls, results = [], []
    def send(text):
        calls.append(text)
        if len(calls) > 1:
            twice.set()
        entered.set()
        assert release.wait(3)
        return True
    monkeypatch.setattr(n, "send_to_public", send)
    one = threading.Thread(target=lambda: results.append(n.public_bosalt()))
    two = threading.Thread(target=lambda: results.append(n.public_bosalt()))
    one.start()
    assert entered.wait(2)
    two.start()
    try:
        assert not twice.wait(.15)
    finally:
        release.set()
        one.join(3)
        two.join(3)
    assert not one.is_alive() and not two.is_alive()
    assert sorted(results) == [0, 1] and len(calls) == 1 and n._public_kuyruk == []


def test_public_invalidation_waits_for_inflight_confirmation_and_keeps_other_entries(public_notifier, monkeypatch):
    n = public_notifier
    assert n.public_kuyruk(event(identity="one"))
    assert n.public_kuyruk(event(stock="AKBNK", identity="two"))
    entered, release, cancelled = threading.Event(), threading.Event(), threading.Event()
    outcomes = []
    monkeypatch.setattr(n, "format_public_tekil", lambda data: data["formation_id"])
    def send(text):
        entered.set()
        assert release.wait(3)
        return True
    monkeypatch.setattr(n, "send_to_public", send)
    flush = threading.Thread(target=lambda: outcomes.append(n.public_bosalt(azami=1)))
    def invalidate():
        outcomes.append(n.public_kuyruk(event(identity="one", state="KIRILIM_GECERSIZLESTI")))
        cancelled.set()
    flush.start()
    assert entered.wait(2)
    cancel = threading.Thread(target=invalidate)
    cancel.start()
    try:
        assert not cancelled.wait(.15)
        assert n.public_kuyruk(event(stock="GARAN", identity="three"))
    finally:
        release.set()
        flush.join(3)
        cancel.join(3)
    assert not flush.is_alive() and not cancel.is_alive()
    assert 1 in outcomes and True in outcomes
    assert [(x["formation_id"], x["state"]) for x in n._public_kuyruk] == [
        ("two", "KIRILIM_TEYITLI"), ("three", "KIRILIM_TEYITLI"), ("one", "KIRILIM_GECERSIZLESTI")]
    persisted = persistence.gunluk_durum_yukle()["public"]["kuyruk"]
    assert [x["formation_id"] for x in persisted] == ["two", "three", "one"]


def test_same_public_budget_is_serialized_for_concurrent_senders(public_notifier, monkeypatch):
    import requests
    n = public_notifier
    n.public_max_gunluk = 1
    entered, release = threading.Event(), threading.Event()
    calls, results = [], []
    def post(*args, **kwargs):
        calls.append(1)
        entered.set()
        assert release.wait(3)
        return Response()
    monkeypatch.setattr(requests, "post", post)
    one = threading.Thread(target=lambda: results.append(n.send_to_public("one")))
    two = threading.Thread(target=lambda: results.append(n.send_to_public("two")))
    one.start()
    assert entered.wait(2)
    two.start()
    release.set()
    one.join(3)
    two.join(3)
    assert not one.is_alive() and not two.is_alive()
    assert len(calls) == 1 and sorted(results) == [False, True]


def test_shared_state_writers_cannot_lose_each_others_updates(tmp_path, monkeypatch):
    first_read, release, other_finished = threading.Event(), threading.Event(), threading.Event()
    original = persistence.gonderim_durumu_yukle
    def read(data_dir=None):
        value = original(data_dir)
        if threading.current_thread().name == "marker-writer":
            first_read.set()
            assert release.wait(3)
        return value
    monkeypatch.setattr(persistence, "gonderim_durumu_yukle", read)
    t1 = threading.Thread(name="marker-writer", target=lambda: persistence.gonderim_durumu_kaydet(
        {"post_close": "today"}, data_dir=str(tmp_path)))
    def write_daily():
        persistence.gunluk_durum_guncelle({"public": {"kuyruk": [{"id": 1}]}}, data_dir=str(tmp_path))
        other_finished.set()
    t2 = threading.Thread(target=write_daily)
    t1.start()
    assert first_read.wait(2)
    t2.start()
    try:
        assert not other_finished.wait(.15)
    finally:
        release.set()
        t1.join(3)
        t2.join(3)
    assert not t1.is_alive() and not t2.is_alive()
    data = original(str(tmp_path))
    assert data["post_close"] == "today"
    assert data["gunluk"]["public"]["kuyruk"] == [{"id": 1}]


def test_atomic_chart_write_ignores_predictable_symlink_and_handles_concurrency(tmp_path):
    from grafik.tarama import _atom_yaz
    dest = tmp_path / "chart.bin"
    private = tmp_path / "private"
    private.write_bytes(b"secret")
    old_temp = tmp_path / f".{dest.name}.{os.getpid()}.tmp"
    old_temp.symlink_to(private)
    payloads = [f"chart-{i}".encode() * 100 for i in range(16)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda payload: _atom_yaz(str(dest), payload), payloads))
    assert private.read_bytes() == b"secret"
    assert dest.read_bytes() in payloads
    assert sorted(p.name for p in tmp_path.glob(f".{dest.name}.*.tmp")) == [old_temp.name]


def test_supabase_quotes_reserved_keys_and_discards_unrequested_rows():
    key = 'name,other)"\\escape'
    remote_key = "formation-bot:" + key
    class Session:
        def __init__(self):
            self.calls = []
        def request(self, method, url, **kwargs):
            self.calls.append(kwargs)
            return Response(200, [
                {"store_key": remote_key, "payload": {"safe": True}},
                {"store_key": "formation-bot:other", "payload": {"leaked": True}},
            ])
    session = Session()
    store = SupabaseStore("https://demo.supabase.co", "test-secret", session=session)
    assert store.get_many([key]) == {key: {"safe": True}}
    filt = session.calls[0]["params"]["store_key"]
    assert filt == 'in.("formation-bot:name,other)\\"\\\\escape")'


def test_webhook_url_and_secret_validation_are_applied_to_direct_paths(monkeypatch):
    for url in ("http://example.com/webhook", "http://example.com/webhook/s",
                "https://user:password@example.com/webhook", "https://example.com/webhook?secret=s"):
        assert telegram.webhook_url_olustur(secret="s", webhook_url=url) == ""
    calls = []
    monkeypatch.setattr(main_mod, "_telegram_api_cagri", lambda *a, **k: calls.append(1) or Response())
    assert not main_mod._telegram_set_webhook(url="http://example.com/webhook", secret="s", token=TOKEN)
    assert not main_mod._telegram_set_webhook(url="https://example.com/webhook", secret="bad secret", token=TOKEN)
    assert calls == []


def test_exceptions_and_api_response_are_redacted_in_public_delivery(public_notifier, monkeypatch, caplog):
    import requests
    n = public_notifier
    def post(*args, **kwargs):
        raise requests.Timeout(f"https://api.telegram.org/bot{TOKEN}/sendMessage")
    monkeypatch.setattr(requests, "post", post)
    with caplog.at_level("WARNING"):
        assert n.send_to_public("test", deneme=0) is False
    assert TOKEN not in caplog.text
    assert TOKEN not in n.son_gonderme_hatasi


@pytest.mark.parametrize("chat_id", ["-1001234567890", "not-a-number", "0"])
def test_invalid_dm_configuration_never_reports_command_layer_ready(chat_id):
    created = []
    def factory(**kwargs):
        created.append(kwargs)
        return SimpleNamespace(start=lambda: True)
    params = dict(komutlar={"durum": lambda _: "ok"}, yardim_metni="",
                  tarama_suruyor=lambda: False, health_server_var=False,
                  listener_factory=factory, adres_olustur=lambda: "",
                  gizle=lambda *_: "", secret_ayikla=lambda *_: "",
                  set_webhook_fn=lambda **_: False, delete_webhook_fn=lambda **_: True)
    result = telegram.komut_katmanini_kur(SimpleNamespace(token=TOKEN, chat_id=chat_id), **params)
    assert result["mod"] == "kapali" and created == []
    result = telegram.komut_katmanini_kur(
        SimpleNamespace(token=TOKEN, chat_id=chat_id), **params,
        public_sohbetler=[GROUP], public_komutlar=["durum"], admin_kontrol=lambda *_: True)
    assert result["mod"] == "yoklama" and created[0]["allowed_chat_id"] == ""


def test_webhook_unknown_outbox_lookup_is_retried_without_running_handler(monkeypatch):
    checks, runs, sent = [], [], []
    def exists(_update_id):
        checks.append(1)
        if len(checks) == 1:
            raise TimeoutError("lookup unavailable")
        return False
    listener = commands.TelegramCommandListener(
        TOKEN, DM, {"durum": lambda _: runs.append(1) or "ok"},
        response_exists=exists, response_sender=lambda uid, body: sent.append((uid, body)) or True)
    monkeypatch.setattr(main_mod, "_telegram_update_processor_ref", listener)
    with http_server({"TELEGRAM_WEBHOOK_SECRET": "test-secret"},
                     webhook_handler=main_mod._telegram_webhook_isle) as server:
        assert post_update(server, update())[0] == 503
        assert runs == [] and sent == []
        assert post_update(server, update())[0] == 200
        assert runs == [1] and sent == [(1, "ok")]
        assert post_update(server, update())[0] == 200
        assert runs == [1]


def test_concurrent_duplicate_webhooks_execute_handler_once(monkeypatch):
    entered, release = threading.Event(), threading.Event()
    calls = []
    def handle(_):
        calls.append("handler")
        entered.set()
        assert release.wait(3)
        return "ok"
    listener = commands.TelegramCommandListener(TOKEN, DM, {"durum": handle}, session=ReplySession())
    monkeypatch.setattr(main_mod, "_telegram_update_processor_ref", listener)
    with http_server({"TELEGRAM_WEBHOOK_SECRET": "test-secret"},
                     webhook_handler=main_mod._telegram_webhook_isle) as server:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(post_update, server, update())
            assert entered.wait(3)
            second = pool.submit(post_update, server, update())
            release.set()
            assert first.result(timeout=5)[0] == 200
            assert second.result(timeout=5)[0] == 200
    assert calls == ["handler"] and len(listener._session.calls) == 1
