import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from health_server import start_render_health_server


def _test_url(port, path, key=None):
    """/test anahtarı A7 sonrası varsayılan olarak BAŞLIKTAN okunur
    (X-Test-Key). query-string (?k=) yalnız TELEGRAM_TEST_KEY_QUERY=1 ile
    çalışır. Bu yardımcı, varsayılan güvenli yolu (başlık) kullanır."""
    headers = {"X-Test-Key": key} if key else {}
    return Request(f"http://127.0.0.1:{port}{path}", headers=headers)


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


def _get(port, path, key=None):
    with urlopen(_test_url(port, path, key), timeout=2) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def _get_expecting_error(port, path, key=None):
    try:
        urlopen(_test_url(port, path, key), timeout=2)
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
        code, body = _get(port, "/test", key="gizli")
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
        code, body = _get_expecting_error(port, "/test", key="gizli")
        assert code == 502
        assert "403" in body["detail"]
    finally:
        server.shutdown()
        server.server_close()


def test_health_ignores_query_string_and_trailing_slash():
    """Keep-alive ve uptime monitörleri `/health?ka=...` çağırır; 404 olmamalı."""
    server = start_render_health_server({"PORT": "0"})
    try:
        port = server.server_address[1]
        for yol in ("/health?ka=1727530000", "/health/", "/?x=1", "/health?t=1&b=2"):
            durum, govde = _get(port, yol)
            assert durum == 200, yol
            assert govde["status"] == "ok", yol
    finally:
        server.shutdown()
        server.server_close()


def test_test_route_query_string_ile_calisir():
    # Bu test ÖZELLEŞTİRİLMİŞ query-string yolunu deniyor; o yüzden
    # TELEGRAM_TEST_KEY_QUERY=1 ile açıyoruz (varsayılan kapalıdır, A7).
    server = start_render_health_server(
        {"PORT": "0", "TELEGRAM_TEST_KEY": "k7m2x9", "TELEGRAM_TEST_KEY_QUERY": "1"},
        test_sender=lambda text: (True, "mesaj gonderildi"),
    )
    try:
        port = server.server_address[1]
        durum, govde = _get(port, "/test?k=k7m2x9")
        assert durum == 200 and govde["ok"] is True
        # Bilinmeyen yol: send_error HTML döner, JSON beklemeyiz.
        try:
            urlopen(f"http://127.0.0.1:{port}/bilinmeyen?x=1", timeout=2)
        except HTTPError as exc:
            assert exc.code == 404
        else:
            raise AssertionError("bilinmeyen yol 404 dönmeli")
    finally:
        server.shutdown()
        server.server_close()


def test_health_render_git_bilgilerini_dondurur(monkeypatch):
    """Render deploy sırasında RENDER_GIT_COMMIT/Branch enjekte eder."""
    monkeypatch.setenv("RENDER_GIT_COMMIT", "67cadbd1f2e3")
    monkeypatch.setenv("RENDER_GIT_BRANCH", "main")
    server = start_render_health_server({"PORT": "0"})
    try:
        port = server.server_address[1]
        _, govde = _get(port, "/health?ka=1")
        assert govde["commit"] == "67cadbd"
        assert govde["branch"] == "main"
    finally:
        server.shutdown()
        server.server_close()


def test_health_commit_alanini_env_yokken_eklemez(monkeypatch):
    monkeypatch.delenv("RENDER_GIT_COMMIT", raising=False)
    monkeypatch.delenv("RENDER_GIT_BRANCH", raising=False)
    server = start_render_health_server({"PORT": "0"})
    try:
        port = server.server_address[1]
        _, govde = _get(port, "/health")
        assert "commit" not in govde and "branch" not in govde
    finally:
        server.shutdown()
        server.server_close()


# --- Denetim B-4: /health canlılık alanları ve ?strict=1 ---


def test_health_reports_liveness_from_provider():
    server = start_render_health_server(
        {"PORT": "0"},
        health_provider=lambda: {"heartbeat_age_s": 42, "heartbeat_stale": False,
                                 "tarama_suruyor": False, "seans_acik": True},
    )
    try:
        port = server.server_address[1]
        kod, payload = _get(port, "/health")
        assert kod == 200
        assert payload["status"] == "ok"
        assert payload["heartbeat_age_s"] == 42
        assert payload["heartbeat_stale"] is False
        assert payload["seans_acik"] is True
    finally:
        server.shutdown()
        server.server_close()


def test_health_without_provider_stays_backward_compatible():
    server = start_render_health_server({"PORT": "0"})
    try:
        port = server.server_address[1]
        kod, payload = _get(port, "/health")
        assert kod == 200
        assert "heartbeat_stale" not in payload
    finally:
        server.shutdown()
        server.server_close()


def test_health_strict_mode_returns_503_only_when_stale():
    server = start_render_health_server(
        {"PORT": "0"},
        health_provider=lambda: {"heartbeat_age_s": 99999, "heartbeat_stale": True},
    )
    try:
        port = server.server_address[1]
        # Render'ın kendi health check'i sorgusuz çağırır -> 200 kalmalı.
        kod, _ = _get(port, "/health")
        assert kod == 200
        # ?strict=1 isteyen monitör bayat heartbeat'te 503 alır.
        kod_strict, payload = _get_expecting_error(port, "/health?strict=1")
        assert kod_strict == 503
        assert payload["status"] == "bayat"
        assert payload["heartbeat_stale"] is True
    finally:
        server.shutdown()
        server.server_close()


def test_health_strict_mode_ok_when_fresh():
    server = start_render_health_server(
        {"PORT": "0", "HEALTH_RATE_LIMIT_PER_MIN": "0"},
        health_provider=lambda: {"heartbeat_age_s": 30, "heartbeat_stale": False},
    )
    try:
        port = server.server_address[1]
        kod, payload = _get(port, "/health?strict=1")
        assert kod == 200
        assert payload["status"] == "ok"
    finally:
        server.shutdown()
        server.server_close()


def test_health_provider_failure_does_not_break_endpoint():
    def patlat():
        raise RuntimeError("boom")

    server = start_render_health_server({"PORT": "0"}, health_provider=patlat)
    try:
        port = server.server_address[1]
        kod, payload = _get(port, "/health")
        assert kod == 200
        assert payload["heartbeat_stale"] is None
        assert "canlilik_hatasi" in payload
    finally:
        server.shutdown()
        server.server_close()
