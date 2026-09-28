import json
from urllib.error import HTTPError
from urllib.request import urlopen

from health_server import start_render_health_server


def test_health_server_binds_and_answers_render_probe():
    server = start_render_health_server({"PORT": "0"})
    try:
        port = server.server_address[1]
        with urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["status"] == "ok"
        assert payload["service"] == "formation-bot"
    finally:
        server.shutdown()
        server.server_close()


def test_health_server_ignores_non_render_mode():
    assert start_render_health_server({}) is None


def test_health_server_returns_404_for_unknown_path():
    server = start_render_health_server({"PORT": "0"})
    try:
        port = server.server_address[1]
        try:
            urlopen(f"http://127.0.0.1:{port}/private", timeout=2)
        except HTTPError as exc:
            assert exc.code == 404
        else:
            raise AssertionError("unknown health route should return HTTP 404")
    finally:
        server.shutdown()
        server.server_close()


def _get(port, path):
    with urlopen(f"http://127.0.0.1:{port}{path}", timeout=2) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def _get_expecting_error(port, path):
    try:
        urlopen(f"http://127.0.0.1:{port}{path}", timeout=2)
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))
    raise AssertionError(f"{path} should have returned an HTTP error")


def test_test_route_is_closed_without_secret():
    calls = []
    server = start_render_health_server(
        {"PORT": "0", "TELEGRAM_TEST_KEY": ""},
        test_sender=lambda text: calls.append(text) or (True, "ok"),
    )
    try:
        port = server.server_address[1]
        code, body = _get_expecting_error(port, "/test?k=herhangi")
        assert code == 404
        assert "kapali" in body["error"]
        assert calls == []          # anahtar yoksa Telegram'a hiç gidilmez
    finally:
        server.shutdown()
        server.server_close()


def test_test_route_rejects_wrong_key_without_sending():
    calls = []
    server = start_render_health_server(
        {"PORT": "0", "TELEGRAM_TEST_KEY": "gizli"},
        test_sender=lambda text: calls.append(text) or (True, "ok"),
    )
    try:
        port = server.server_address[1]
        code, body = _get_expecting_error(port, "/test?k=yanlis")
        assert code == 403
        assert body["ok"] is False
        assert calls == []
    finally:
        server.shutdown()
        server.server_close()


def test_test_route_sends_with_correct_key():
    calls = []

    def sender(text):
        calls.append(text)
        return True, "mesaj gonderildi"

    server = start_render_health_server(
        {"PORT": "0", "TELEGRAM_TEST_KEY": "gizli"}, test_sender=sender
    )
    try:
        port = server.server_address[1]
        code, body = _get(port, "/test?k=gizli")
        assert code == 200
        assert body == {"ok": True, "detail": "mesaj gonderildi"}
        assert len(calls) == 1
    finally:
        server.shutdown()
        server.server_close()


def test_test_route_reports_sender_failure_as_bad_gateway():
    server = start_render_health_server(
        {"PORT": "0", "TELEGRAM_TEST_KEY": "gizli"},
        test_sender=lambda text: (False, "HTTP 403: chat not found"),
    )
    try:
        port = server.server_address[1]
        code, body = _get_expecting_error(port, "/test?k=gizli")
        assert code == 502
        assert "403" in body["detail"]
    finally:
        server.shutdown()
        server.server_close()
