"""Small public liveness endpoint for Render Web Services.

Render provides PORT at runtime. The bot remains a normal long-running loop;
this HTTP server runs on a daemon thread so external monitors can check /health.
"""

import json
import logging
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

logger = logging.getLogger(__name__)


class _HealthHandler(BaseHTTPRequestHandler):
    def _send_health(self):
        if self.path not in ("/", "/health"):
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


def start_render_health_server(environ=None):
    """Start on Render's injected PORT; in local/systemd mode do nothing."""
    environ = os.environ if environ is None else environ
    raw_port = environ.get("PORT")
    if not raw_port:
        logger.info("PORT env yok; Render health endpoint başlatılmadı")
        return None

    port = int(raw_port)
    server = ThreadingHTTPServer(("0.0.0.0", port), _HealthHandler)
    server.daemon_threads = True
    thread = Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.5},
        name="render-health-server",
        daemon=True,
    )
    thread.start()
    logger.info(f"Render health endpoint 0.0.0.0:{port} üzerinde başladı (/health)")
    return server
