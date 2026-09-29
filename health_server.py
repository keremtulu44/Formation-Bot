"""Small public liveness endpoint for Render Web Services.

Render provides PORT at runtime. The bot remains a normal long-running loop;
this HTTP server runs on a daemon thread so external monitors can check /health.

There is also a guarded /test route: it sends one real Telegram message so the
outbound path can be verified from a phone browser without a shell. It stays
disabled unless TELEGRAM_TEST_KEY is set, and the key must match.

Since the Telegram **webhook** mode was added, the same tiny server also carries
`POST /webhook/<secret>`: Telegram pushes updates here, the secret in the path
(plus the `X-Telegram-Bot-Api-Secret-Token` header, when Telegram sends it) is
verified, the JSON body is parsed and handed to `webhook_handler`. This removes
the need for the long-polling `getUpdates` loop, which a free Render instance
cannot keep open across sleep/restart cycles.

The route stays CLOSED (404, exactly like /test) unless TELEGRAM_WEBHOOK_SECRET
is set, so an unconfigured deployment exposes nothing to the outside.
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

# /webhook/<secret> — secret adresin son parçasıdır (Telegram yol içinde sır kabul etmez
# ama pratikte bu yöntem yaygındır; asıl doğrulama secret_token başlığıyla da yapılır).
WEBHOOK_YOL_ONEK = "/webhook/"

# Telegram güncellemeleri birkaç KB'dir. Content-Length ile gövde okuduğumuz için
# bozuk/kötü niyetli bir istek belleği şişirmesin diye üst sınır koyuyoruz.
WEBHOOK_MAKS_GOVDE_BAYT = 1_000_000


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
        # Sorgu dizesini AT: uptime monitörleri ve keep-alive iş akışı
        # `/health?ka=<zaman>` gibi önbellek kırıcı parametre ekler. Önceden
        # self.path ("/health?ka=...") tam eşleşmediği için 404 dönüyordu ve
        # ping "servis ölü" sanılıyordu. Sondaki tek slash da tolere edilir.
        yol = urlparse(self.path).path
        if len(yol) > 1:
            yol = yol.rstrip("/") or "/"
        if yol in ("/", "/health"):
            self._send_ok()
            return
        if yol == "/test":
            self._handle_test()
            return
        if yol.startswith(WEBHOOK_YOL_ONEK):
            self._handle_webhook(yol)
            return
        self.send_error(404)

    # --- Telegram webhook -------------------------------------------------
    def _webhook_secret(self):
        return (getattr(self.server, "webhook_secret", "") or "").strip()

    def _webhook_handler(self):
        return getattr(self.server, "webhook_handler", None)

    def _govde_oku(self):
        """Content-Length sınırlı gövde okuma. Hata halinde None (yanıt gönderilir)."""
        try:
            uzunluk = int(self.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            uzunluk = 0
        if uzunluk <= 0:
            self._send_json(400, {"ok": False, "error": "govde bos"})
            return None
        if uzunluk > WEBHOOK_MAKS_GOVDE_BAYT:
            self._send_json(413, {"ok": False, "error": "govde cok buyuk"})
            return None
        try:
            return self.rfile.read(uzunluk)
        except Exception as exc:  # noqa: BLE001 - istemci yarım gönderip kopabilir
            logger.warning(f"Webhook govdesi okunamadi: {exc}")
            self._send_json(400, {"ok": False, "error": "govde okunamadi"})
            return None

    def _handle_webhook(self, yol: str):
        """POST /webhook/<secret> — Telegram güncellemesini işleyiciye verir.

        Sıra: (1) uç kurulu mu, (2) path secret'ı doğru mu, (3) varsa
        `X-Telegram-Bot-Api-Secret-Token` başlığı doğru mu, (4) JSON çözümle,
        (5) işleyiciyi çağır. Yanıt 200 olmazsa Telegram güncellemeyi tekrar
        gönderir; bu yüzden işleyici hatasında 500 döneriz (update kaybolmaz).
        """
        expected = self._webhook_secret()
        # Uç kurulu değilse varlığını bile belli etme (aynı /test kuralı).
        if not expected:
            self._send_json(404, {
                "ok": False,
                "error": "webhook kapali (TELEGRAM_WEBHOOK_SECRET tanimli degil)",
            })
            return

        # Karşılaştırmalar sabit zamanlı: sır uzunluğu/prefix'i zamanlamadan sızmasın.
        verilen = yol[len(WEBHOOK_YOL_ONEK):]
        if not verilen or not hmac.compare_digest(verilen, expected):
            self._send_json(403, {"ok": False, "error": "yanlis webhook adresi"})
            return

        baslik = (self.headers.get("X-Telegram-Bot-Api-Secret-Token") or "").strip()
        if baslik and not hmac.compare_digest(baslik, expected):
            self._send_json(403, {"ok": False, "error": "yanlis secret token basligi"})
            return

        # GET: telefondan tarayıcıyla durum kontrolü. Güncelleme işlemez, sır sızdırmaz.
        if self.command in ("GET", "HEAD"):
            self._send_json(200, {
                "ok": True,
                "webhook": "hazir",
                "bot_hazir": self._webhook_handler() is not None,
                "time": datetime.now(timezone.utc).isoformat(),
            })
            return

        govde = self._govde_oku()
        if govde is None:
            return
        try:
            guncelleme = json.loads(govde.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            logger.warning(f"Webhook JSON cozumlenemedi: {exc}")
            self._send_json(400, {"ok": False, "error": "JSON cozumlenemedi"})
            return
        if not isinstance(guncelleme, dict):
            self._send_json(400, {"ok": False, "error": "guncelleme bir nesne olmali"})
            return

        isleyici = self._webhook_handler()
        if isleyici is None:
            # Bot henüz komutları kurmadı (açılış sırasındaki ilk veri yüklemesi).
            # 503 -> Telegram tekrar dener, komut kaybolmaz.
            self._send_json(503, {
                "ok": False,
                "error": "bot henuz baslamadi, birkac saniye sonra tekrar dene",
            })
            return

        try:
            kod = isleyici(guncelleme)
        except Exception as exc:  # noqa: BLE001 - tek güncelleme sunucuyu düşürmesin
            logger.error(f"Webhook isleyicisi hata verdi: {exc}", exc_info=True)
            self._send_json(500, {"ok": False, "error": "isleyici hatasi"})
            return

        if not isinstance(kod, int):
            kod = 200
        self._send_json(kod, {
            "ok": kod < 400,
            "update_id": guncelleme.get("update_id"),
        })

    def _send_ok(self):
        # Render bu değişkenleri deploy sırasında enjekte eder: hangi commit'in
        # canlı olduğunu /health'ten görebilmek, "deploy düştü mü?" sorusunu
        # log/dashboard gezmeden cevaplar (deploy_check.py bunu karşılaştırır).
        payload = {
            "status": "ok",
            "service": "formation-bot",
            "time": datetime.now(timezone.utc).isoformat(),
        }
        commit = (os.environ.get("RENDER_GIT_COMMIT") or "").strip()
        if commit:
            payload["commit"] = commit[:7]
        branch = (os.environ.get("RENDER_GIT_BRANCH") or "").strip()
        if branch:
            payload["branch"] = branch
        body = json.dumps(payload).encode("utf-8")
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

    def do_POST(self):
        # Webhook dışındaki POST'lar da aynı yönlendirmeden geçer: /health -> 200 JSON,
        # /test -> 404/403, /webhook/<secret> -> güncelleme. Bilinmeyen yol 404.
        self._send_health()

    def log_message(self, format, *args):
        # Avoid one info log for each 5-minute monitor request.
        logger.debug("Health HTTP: " + format, *args)


def start_render_health_server(environ=None, test_sender=None,
                               webhook_handler=None, webhook_secret=None):
    """Start on Render's injected PORT; in local/systemd mode do nothing.

    test_sender(text) -> (ok, detail) enables the guarded /test route that sends
    one real Telegram message. It stays 404 unless TELEGRAM_TEST_KEY is set.

    webhook_handler(update) -> int (HTTP kodu, None=200) enables the guarded
    /webhook/<secret> route. It stays 404 unless TELEGRAM_WEBHOOK_SECRET is set;
    the secret comes from `webhook_secret` (tercih edilir) ya da aynı adlı env
    değişkeninden.
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
    server.webhook_handler = webhook_handler
    if webhook_secret is None:
        webhook_secret = environ.get("TELEGRAM_WEBHOOK_SECRET")
    server.webhook_secret = (webhook_secret or "").strip()
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
    if server.webhook_secret:
        # Sırrın kendisi ASLA loglanmaz; yalnızca ucun açık olduğu söylenir.
        logger.info("Telegram webhook ucu etkin (POST /webhook/<secret>, secret gizli)")
        if webhook_handler is None:
            logger.warning("Webhook ucu acik ama isleyici yok; guncellemeler 503 alacak")
    else:
        logger.info("Telegram webhook ucu kapali (TELEGRAM_WEBHOOK_SECRET tanimli degil)")
    return server
