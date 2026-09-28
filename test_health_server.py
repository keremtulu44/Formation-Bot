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
