"""Small public liveness endpoint for Render Web Services.

Render provides PORT at runtime. The bot remains a normal long-running loop;
this HTTP server runs on a daemon thread so external monitors can check /health.

There is also a guarded /test route: it sends one real Telegram message so the
outbound path can be verified from a phone browser without a shell. It stays
disabled unless TELEGRAM_TEST_KEY is set, and the key must match.

Since the Telegram **webhook** mode was added, the same tiny server also carries
`POST /webhook`: Telegram pushes updates here, the JSON body is verified against
the `X-Telegram-Bot-Api-Secret-Token` header (set once via `setWebhook`'s
`secret_token`) and handed to `webhook_handler`. This removes the need for the
long-polling `getUpdates` loop, which a free Render instance cannot keep open
across sleep/restart cycles.

A7 (batch 6): the secret no longer travels in the URL path —
`POST /webhook/<secret>` is accepted only for backward compatibility while an
older registration is still active; the bot re-registers with the secret-free
path at startup. Public routes are additionally rate limited per client IP so a
stray caller cannot spam Telegram sends or webhook parsing.

The route stays CLOSED (404, exactly like /test) unless TELEGRAM_WEBHOOK_SECRET
is set, so an unconfigured deployment exposes nothing to the outside.

Denetim B-4: `/health` her koşulda 200 döner (Render health check davranışı
değişmez) ama artık botun canlılığını da raporlar. `health_provider` ile dışarıdan
enjekte edilen özet (heartbeat yaşı, tarama sürüyor mu, seans açık mı) yanıta
eklenir; monitör `?strict=1` ile çağırırsa heartbeat bayatken uç 503 döner.
Bu modül main'i import etmez; veriyi yalnızca enjekte edilen callable'dan alır.
"""

import hmac
import json
import logging
import os
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock, Thread
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)

TEST_MESSAGE = (
    "✅ Formation-Bot test mesaji.\n"
    "Telegram baglantisi calisiyor; alarmlar bu kanaldan gelecek."
)

# Sırsız webhook yolu: doğrulama `X-Telegram-Bot-Api-Secret-Token` başlığıyla yapılır.
WEBHOOK_YOL = "/webhook"
# Eski (sır yol içinde) biçim: yalnız geriye dönük uyumluluk için kabul edilir;
# bot açılışta setWebhook ile sırsız yolu yeniden kaydeder.
WEBHOOK_YOL_ONEK = "/webhook/"

# Basit IP başına istek limiti (dakikada). 0 = kapalı.
VARSAYILAN_DAKIKA_LIMIT = 60

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

    # --- A7: IP başına basit istek limiti ---------------------------------
    def _istemci_ip(self) -> str:
        # Render/proxy arkasında gerçek istemci ilk X-Forwarded-For değeridir.
        fwd = (self.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        return fwd or (self.client_address[0] if self.client_address else "?")

    def _limit_asildi(self) -> bool:
        """(ip, pencere) başına istek sayısı sınırı; aşıldıysa 429 yollar."""
        limit = int(getattr(self.server, "rate_limit_per_min", 0) or 0)
        if limit <= 0:
            return False
        simdi = time.time()
        ip = self._istemci_ip()
        with self.server.rate_kilidi:
            gecmis = [t for t in self.server.rate_kayitlari.get(ip, []) if simdi - t < 60.0]
            if len(gecmis) >= limit:
                self.server.rate_kayitlari[ip] = gecmis
                logger.warning(f"Rate limit: {ip} dakikada {len(gecmis)} istek (limit {limit}) - 429")
                self.send_response(429)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Retry-After", "60")
                self.send_header("Cache-Control", "no-store")
                govde = json.dumps({"ok": False, "error": "cok fazla istek"}).encode("utf-8")
                self.send_header("Content-Length", str(len(govde)))
                self.end_headers()
                self.wfile.write(govde)
                return True
            gecmis.append(simdi)
            self.server.rate_kayitlari[ip] = gecmis
        return False

    def _test_anahtari(self) -> str:
        """Başlıktan anahtar: X-Test-Key veya Authorization: Bearer <anahtar>."""
        baslik = (self.headers.get("X-Test-Key") or "").strip()
        if baslik:
            return baslik
        yetki = (self.headers.get("Authorization") or "").strip()
        if yetki.lower().startswith("bearer "):
            return yetki[7:].strip()
        return ""

    def _handle_test(self):
        # Endpoint kurulu degilse hic bilgi verme: herkesin bilgisi olmaz.
        if not self._test_enabled():
            self._send_json(404, {
                "ok": False,
                "error": "test endpoint kapali (TELEGRAM_TEST_KEY tanimli degil)",
            })
            return
        if self._limit_asildi():
            return

        # A7: anahtar artık başlıktan okunur (URL/erişim loglarına düşmesin).
        provided = self._test_anahtari()
        kaynak = "baslik"
        if not provided and getattr(self.server, "test_key_query", True):
            # Geriye dönük: telefon yer imleri için ?k= hâlâ kabul edilir ama
            # sır URL'de kalır; başlığa geçilmesi logla hatırlatılır.
            provided = parse_qs(urlparse(self.path).query).get("k", [""])[0]
            if provided:
                logger.warning(
                    "/test anahtarı URL sorgusunda geldi (?k=). Sır erişim loglarına düşer; "
                    "X-Test-Key başlığına geçin (TELEGRAM_TEST_KEY_QUERY=0 ile kapatılır)."
                )
        if not provided or not hmac.compare_digest(provided, self.server.test_key):
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
        # Sırsız yol (yeni) + sır yol içinde (eski kayıt; geriye dönük).
        if yol == WEBHOOK_YOL or yol.startswith(WEBHOOK_YOL_ONEK):
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
        """Telegram güncellemesini işleyiciye verir (`POST /webhook`).

        Sıra: (1) uç kurulu mu, (2) kimlik doğrulama — sırsız yolda
        `X-Telegram-Bot-Api-Secret-Token` başlığı ZORUNLU, eski `<secret>`
        yolunda yol parçası + (varsa) başlık, (3) JSON çözümle, (4) işleyiciyi
        çağır. Yanıt 200 olmazsa Telegram güncellemeyi tekrar gönderir; bu
        yüzden işleyici hatasında 500 döneriz (update kaybolmaz).
        """
        expected = self._webhook_secret()
        # Uç kurulu değilse varlığını bile belli etme (aynı /test kuralı).
        if not expected:
            self._send_json(404, {
                "ok": False,
                "error": "webhook kapali (TELEGRAM_WEBHOOK_SECRET tanimli degil)",
            })
            return
        if self._limit_asildi():
            return

        # Karşılaştırmalar sabit zamanlı: sır uzunluğu/prefix'i zamanlamadan sızmasın.
        yol_sirri = yol[len(WEBHOOK_YOL_ONEK):] if yol.startswith(WEBHOOK_YOL_ONEK) else ""
        if yol_sirri:
            logger.warning(
                "Webhook isteği ESKİ sırlı yoldan geldi (/webhook/<secret>). "
                "Sır adres/erişim loglarında görünür; bot açılışta sırsız yolu kaydeder."
            )
            if not hmac.compare_digest(yol_sirri, expected):
                self._send_json(403, {"ok": False, "error": "yanlis webhook adresi"})
                return

        baslik = (self.headers.get("X-Telegram-Bot-Api-Secret-Token") or "").strip()
        if baslik:
            if not hmac.compare_digest(baslik, expected):
                self._send_json(403, {"ok": False, "error": "yanlis secret token basligi"})
                return
        elif not yol_sirri:
            # Sırsız yolda başlık yoksa istek kimliksizdir: reddet.
            self._send_json(403, {"ok": False, "error": "secret token basligi gerekli"})
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

    def _canlilik_ozeti(self):
        """health_provider'dan (varsa) canlılık alanlarını al; hata olsa bile uç düşmesin.

        Denetim B-4: bu modül main'i import etmez; özet dışarıdan enjekte edilir.
        Sağlayıcı patlarsa /health yine 200 döner, yalnız 'canlilik_hatasi' alanı eklenir.
        """
        saglayici = getattr(self.server, "health_provider", None)
        if not callable(saglayici):
            return None
        try:
            ozet = saglayici()
        except Exception as exc:  # noqa: BLE001 - /health asla 500 dönmemeli
            logger.warning("Canlılık özeti alınamadı: %s: %s", type(exc).__name__, exc)
            return {"heartbeat_stale": None,
                    "canlilik_hatasi": f"{type(exc).__name__}: {exc}"[:120]}
        return ozet if isinstance(ozet, dict) else None

    def _strict_istendi(self) -> bool:
        """`?strict=1` ile çağıran monitör, bayat heartbeat'te 503 ister."""
        sorgu = parse_qs(urlparse(self.path).query)
        deger = (sorgu.get("strict", ["0"])[0] or "").strip().lower()
        return deger not in ("", "0", "false", "no")

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
        # --- CANLILIK (denetim B-4) ---
        # Render'ın health check'i sorgusuz `/health` çağırır -> her zaman 200.
        # Gerçek canlılık ayrı alanlarda raporlanır; monitör ?strict=1 ile
        # bayat heartbeat'i 503'e çevirebilir.
        canli = self._canlilik_ozeti()
        if canli:
            payload.update(canli)
        kod = 200
        if self._strict_istendi() and payload.get("heartbeat_stale") is True:
            kod = 503
            payload["status"] = "bayat"
        body = json.dumps(payload).encode("utf-8")
        self.send_response(kod)
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
                               webhook_handler=None, webhook_secret=None,
                               health_provider=None):
    """Start on Render's injected PORT; in local/systemd mode do nothing.

    test_sender(text) -> (ok, detail) enables the guarded /test route that sends
    one real Telegram message. It stays 404 unless TELEGRAM_TEST_KEY is set.

    webhook_handler(update) -> int (HTTP kodu, None=200) enables the guarded
    /webhook/<secret> route. It stays 404 unless TELEGRAM_WEBHOOK_SECRET is set;
    the secret comes from `webhook_secret` (tercih edilir) ya da aynı adlı env
    değişkeninden.

    health_provider() -> dict enables the liveness fields on /health (heartbeat
    yaşı, tarama sürüyor mu, seans açık mı). Verilmezse /health eski hâliyle
    yalnız status/service/time/commit/branch döner. `/health?strict=1` çağrısı,
    heartbeat bayatken 503 döner (Render'ın kendi health check'i sorgusuz
    çağırdığı için bu davranış yalnız monitörleri etkiler).
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
    # Denetim B-4: /health canlılık alanları (main, _saglik_ozeti'ni enjekte eder).
    server.health_provider = health_provider
    if webhook_secret is None:
        webhook_secret = environ.get("TELEGRAM_WEBHOOK_SECRET")
    server.webhook_secret = (webhook_secret or "").strip()
    # A7: public uçlarda IP başına istek limiti + sorgu anahtarı politikası.
    try:
        server.rate_limit_per_min = max(0, int((environ.get("HEALTH_RATE_LIMIT_PER_MIN")
                                                or VARSAYILAN_DAKIKA_LIMIT)))
    except (TypeError, ValueError):
        server.rate_limit_per_min = VARSAYILAN_DAKIKA_LIMIT
    server.rate_kayitlari = {}
    server.rate_kilidi = Lock()
    server.test_key_query = (environ.get("TELEGRAM_TEST_KEY_QUERY", "1") or "").strip() not in ("0", "false", "False")
    thread = Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.5},
        name="render-health-server",
        daemon=True,
    )
    thread.start()
    logger.info(f"Render health endpoint 0.0.0.0:{port} üzerinde başladı (/health)")
    if callable(health_provider):
        logger.info("GET /health canlılık alanlarını döndürür "
                    "(heartbeat yaşı; ?strict=1 -> bayatsa 503)")
    if server.test_key:
        logger.info("Telegram /test ucu etkin (TELEGRAM_TEST_KEY tanimli, anahtar X-Test-Key basliginda)")
        if server.test_key_query:
            logger.warning("TELEGRAM_TEST_KEY_QUERY=1: ?k= sorgu anahtari hâlâ kabul ediliyor (sır URL'de)")
    if server.rate_limit_per_min:
        logger.info(f"HTTP rate limit: IP başına {server.rate_limit_per_min} istek/dk")
    else:
        logger.info("Telegram /test ucu kapali (TELEGRAM_TEST_KEY tanimli degil)")
    if server.webhook_secret:
        # Sırrın kendisi ASLA loglanmaz; yalnızca ucun açık olduğu söylenir.
        logger.info("Telegram webhook ucu etkin (POST /webhook, secret X-Telegram-Bot-Api-Secret-Token basliginda)")
        if webhook_handler is None:
            logger.warning("Webhook ucu acik ama isleyici yok; guncellemeler 503 alacak")
    else:
        logger.info("Telegram webhook ucu kapali (TELEGRAM_WEBHOOK_SECRET tanimli degil)")
    return server
