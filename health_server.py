"""Small public liveness endpoint for Render Web Services.

Render provides PORT at runtime. The bot remains a normal long-running loop;
this HTTP server runs on a daemon thread so external monitors can check /health.

There is also a guarded /test route: it sends one real Telegram message so the
outbound path can be verified from a phone browser without a shell. It stays
disabled unless TELEGRAM_TEST_KEY is set, and the key must match.
"""

import hmac
import json
import logging
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)

TEST_MESSAGE = (
    "✅ Formation-Bot test mesaji.\n"
    "Telegram baglantisi calisiyor; alarmlar bu kanaldan gelecek."
)


class _HealthHandler(BaseHTTPRequestHandler):
    def _send_json(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _test_enabled(self):
        expected = (getattr(self.server, "test_key", "") or "").strip()
        return bool(expected)

    def _handle_test(self):
        # Endpoint kurulu degilse hic bilgi verme: herkesin bilgisi olmaz.
        if not self._test_enabled():
            self._send_json(404, {
                "ok": False,
                "error": "test endpoint kapali (TELEGRAM_TEST_KEY tanimli degil)",
            })
            return

        provided = parse_qs(urlparse(self.path).query).get("k", [""])[0]
        if not hmac.compare_digest(provided, self.server.test_key):
            self._send_json(403, {"ok": False, "error": "yanlis anahtar"})
            return

        sender = getattr(self.server, "test_sender", None)
        if sender is None:
            self._send_json(503, {
                "ok": False,
                "error": "bot henuz baslamadi, birkac saniye sonra tekrar dene",
            })
            return

        ok, detail = sender(TEST_MESSAGE)
        logger.info(f"/test Telegram denemesi: ok={ok} ({detail})")
        self._send_json(200 if ok else 502, {"ok": ok, "detail": detail})

    def _send_health(self):
        if self.path not in ("/", "/health"):
            if self.path.split("?")[0] == "/test":
                self._handle_test()
                return
            self.send_error(404)
            return

        body = json.dumps({
            "status": "ok",
            "service": "formation-bot",
            "time": datetime.now(timezone.utc).isoformat(),
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        self._send_health()

    def do_HEAD(self):
        self._send_health()

    def log_message(self, format, *args):
        # Avoid one info log for each 5-minute monitor request.
        logger.debug("Health HTTP: " + format, *args)


def start_render_health_server(environ=None, test_sender=None):
    """Start on Render's injected PORT; in local/systemd mode do nothing.

    test_sender(text) -> (ok, detail) enables the guarded /test route that sends
    one real Telegram message. It stays 404 unless TELEGRAM_TEST_KEY is set.
    """
    environ = os.environ if environ is None else environ
    raw_port = environ.get("PORT")
    if not raw_port:
        logger.info("PORT env yok; Render health endpoint başlatılmadı")
        return None

    port = int(raw_port)
    server = ThreadingHTTPServer(("0.0.0.0", port), _HealthHandler)
    server.daemon_threads = True
    # Handler sınıfına değil sunucuya tak: instance attribute binding sorunu olmaz.
    server.test_sender = test_sender
    server.test_key = (environ.get("TELEGRAM_TEST_KEY") or "").strip()
    thread = Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.5},
        name="render-health-server",
        daemon=True,
    )
    thread.start()
    logger.info(f"Render health endpoint 0.0.0.0:{port} üzerinde başladı (/health)")
    if server.test_key:
        logger.info("Telegram /test ucu etkin (TELEGRAM_TEST_KEY tanimli)")
    else:
        logger.info("Telegram /test ucu kapali (TELEGRAM_TEST_KEY tanimli degil)")
    return server
