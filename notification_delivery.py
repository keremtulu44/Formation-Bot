"""Durable FIFO for one alert text + its prepared album.

No pickle, no live DataFrames: only the chart snapshot and PNG bytes are saved.
Local atomic replacement precedes every network side effect. Optional remote
backup survives ephemeral-disk redeploys. Telegram has no idempotency key:
a crash/timeout after acceptance can still duplicate the last unacknowledged API
operation (at-least-once delivery, never pretend exactly-once).
"""
import base64
import hashlib
import json
import logging
import os
import tempfile
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

log = logging.getLogger(__name__)
KEY = "state:notification_delivery"


def _encode(value):
    if isinstance(value, (datetime, date)):
        return {"__delivery_datetime__": value.isoformat()}
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"Unsupported delivery snapshot: {type(value).__name__}")


def _decode(value):
    if set(value) == {"__delivery_datetime__"}:
        return datetime.fromisoformat(value["__delivery_datetime__"])
    return value


def freeze(value):
    return json.loads(json.dumps(value, default=_encode), object_hook=_decode)


def event_id(data):
    fields = [data.get(k) for k in ("stock_name", "timeframe", "state", "break_dir", "formation_id")]
    if not data.get("formation_id"):
        fields.append(str(data.get("bar_time") or data.get("timestamp") or ""))
    return hashlib.sha256(json.dumps(fields, default=str).encode()).hexdigest()


def _pattern_family(name):
    from config import mtf_family_match_enabled
    if not mtf_family_match_enabled():
        return name
    from patterns.constants import PATTERN_TYPE_MAP, f_is_specialized
    if f_is_specialized(name):
        return "direkli"
    code = PATTERN_TYPE_MAP.get(name)
    if code in (1, 2, 3):
        return "ucgen"
    if code in (4, 5):
        return "kama"
    return name


def related(a, b):
    """Same directional development on another TF, not an opposite/new-slot event."""
    return (a.get("timeframe") != b.get("timeframe")
            and all(a.get(k) == b.get(k) for k in ("stock_name", "state", "break_dir"))
            and _pattern_family(a.get("pattern_name")) == _pattern_family(b.get("pattern_name"))
            and a.get("break_dir") in (-1, 1))


class DeliveryOutbox:
    def __init__(self, notifier, directory):
        self.owner = notifier
        self.path = Path(directory) / "notification_delivery.json"
        self.lock = threading.RLock()
        self.state = {"rows": [], "public": [], "saved_at": ""}
        candidates = []
        remote = notifier.initial_store_data.get(KEY)
        if isinstance(remote, dict):
            candidates.append(remote)
        try:
            candidates.append(json.loads(self.path.read_text()))
        except FileNotFoundError:
            pass
        except (ValueError, OSError):
            # Never silently overwrite an unreadable outbox (would lose alerts).
            log.exception("Teslim kuyruğu okunamadı")
            if not candidates:
                raise  # no good backup: fail closed rather than discard deliveries
        if candidates:
            raw = max(candidates, key=lambda x: x.get("saved_at", ""))
            self.state = json.loads(json.dumps(raw), object_hook=_decode)

    def now(self):
        from config import ISTANBUL_TZ
        return datetime.now(ISTANBUL_TZ)

    def save(self):
        self.state["saved_at"] = self.now().isoformat()
        raw = json.loads(json.dumps(self.state, default=_encode))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        with temp.open("w") as stream:
            json.dump(raw, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, self.path)
        store = self.owner.persistent_store
        if store is not None:
            try:
                if not store.upsert(KEY, raw):
                    log.warning("Teslim kuyruğunun uzak yedeği yazılamadı; yerel kayıt korundu")
            except Exception:
                log.exception("Teslim kuyruğu uzak yedeği başarısız; yerel kayıt korundu")

    def recent(self, row):
        from config import MTF_ALERT_MERGE_HOURS
        stamp = datetime.fromisoformat(row["created"])
        return 0 <= (self.now() - stamp).total_seconds() < MTF_ALERT_MERGE_HOURS * 3600

    def already_done(self, data):
        with self.lock:
            return any(r["done"] and r["id"] == event_id(data) for r in self.state["rows"])

    def confirmation_delivered(self, data_or_id):
        fid = data_or_id.get("formation_id") if isinstance(data_or_id, dict) else data_or_id
        if not fid:
            return False
        fid = str(fid)
        with self.lock:
            return any(
                (r.get("done") or r.get("text_sent"))
                and r.get("data", {}).get("state") == "KIRILIM_TEYITLI"
                and str(r.get("data", {}).get("formation_id") or "") == fid
                for r in self.state["rows"]
            )

    has_delivered_confirmation = confirmation_delivered

    def is_cross_duplicate(self, data):
        with self.lock:
            for row in self.state["rows"]:
                aliases = row.get("aliases", [])
                # Suppressed TFs must not reappear after the short merge window.
                if data.get("formation_id") and any(
                        all(a.get(k) == data.get(k) for k in
                            ("stock_name", "timeframe", "formation_id", "state", "break_dir")) for a in aliases):
                    return True
                # Do not retract a confirmation from an unannounced TF.
                if data.get("state") == "KIRILIM_GECERSIZLESTI" and data.get("formation_id") and any(
                        all(a.get(k) == data.get(k) for k in
                            ("stock_name", "timeframe", "formation_id", "break_dir")) for a in aliases):
                    return True
                if self.recent(row) and related(row["data"], data):
                    alias = {k: data.get(k) for k in
                             ("stock_name", "timeframe", "formation_id", "state", "break_dir")}
                    if alias not in aliases:
                        row.setdefault("aliases", []).append(alias)
                        self.save()
                    return True
            return False

    def public_duplicate(self, data):
        with self.lock:
            for row in self.state["public"]:
                aliases = row.get("aliases", [])
                if data.get("formation_id") and any(
                        all(a.get(k) == data.get(k) for k in
                            ("stock_name", "timeframe", "formation_id", "state", "break_dir")) for a in aliases):
                    return True
                if self.recent(row) and related(row["data"], data):
                    alias = {k: data.get(k) for k in
                             ("stock_name", "timeframe", "formation_id", "state", "break_dir")}
                    if alias not in aliases:
                        row.setdefault("aliases", []).append(alias)
                        self.save()
                    return True
            return False

    def remember_public(self, data):
        with self.lock:
            self.state["public"] = [r for r in self.state["public"] if
                (self.now() - datetime.fromisoformat(r["created"])).total_seconds() < 7 * 86400]
            self.state["public"].append({"data": {k: data.get(k) for k in
                ("stock_name", "timeframe", "state", "break_dir", "pattern_name")},
                "created": self.now().isoformat()})
            self.save()

    def submit(self, data):
        with self.lock:
            identity = event_id(data)
            row = next((r for r in self.state["rows"] if r["id"] == identity), None)
            if row is not None and row["done"]:
                return False
            if row is None:
                if self.is_cross_duplicate(data):
                    return False
                row = {"id": identity, "created": self.now().isoformat(),
                       "data": freeze(data), "text_sent": False, "done": False,
                       "images": []}
                row["data"]["_delivery_message"] = self.owner.format_message(data)
                # Bound completed history only. Pending deliveries never expire.
                self.state["rows"] = [r for r in self.state["rows"] if not r["done"] or
                    (self.now() - datetime.fromisoformat(r["created"])).total_seconds() < 7 * 86400]
                self.state["rows"].append(row)
                self.save()
            elif not row["text_sent"] and not row["data"].get("grafik_verisi"):
                row["data"] = freeze(data)
                row["data"]["_delivery_message"] = self.owner.format_message(data)
                self.save()
            self.flush()
            return row["done"]

    def prepare(self, row):
        from notifier import _grafik_salteri_acik, _grafik_basligi
        data = row["data"]
        # All pending pictures from older chart policies are regenerated from the
        # saved snapshot: no internal markers, no engulf, exact right-side ranges.
        if row.get("prepared") and row.get("graph_policy") == "chart-trust-focus-v3":
            return
        if _grafik_salteri_acik():
            frames = (data.get("grafik_verisi") or {}).get("goruntular") or []
            if not frames:
                raise RuntimeError("Görsel açık ama kare verisi yok; metin bekletiliyor")
            import grafik
            images = []
            for frame in frames:
                path, meta = grafik.kareyi_yaz(frame["goruntu"], frame["tf"])
                if not path:
                    raise RuntimeError("Kare üretilemedi; metin bekletiliyor")
                try:
                    images.append({"png": base64.b64encode(Path(path).read_bytes()).decode(),
                        "caption": _grafik_basligi({"sembol": data.get("stock_name"),
                                                  "state": data.get("state")}, frame, meta)})
                finally:
                    Path(path).unlink(missing_ok=True)
            row["images"] = images
        row["prepared"] = True
        row["graph_policy"] = "chart-trust-focus-v3"
        self.save()

    def send_images(self, row):
        from transport.telegram import foto_gonder, medya_grubu_gonder
        owner = self.owner
        try:
            private = int(str(owner.chat_id)) > 0
        except ValueError:
            private = False
        if not private or str(owner.chat_id) == str(getattr(owner, "public_chat_id", "")):
            raise RuntimeError("Görseller yalnız private DM'e gönderilebilir")
        with tempfile.TemporaryDirectory(prefix="formation-delivery-") as folder:
            paths, captions = [], []
            for i, image in enumerate(row["images"]):
                path = Path(folder) / f"{i}.png"
                path.write_bytes(base64.b64decode(image["png"]))
                paths.append(str(path))
                captions.append(image["caption"])
            if len(paths) == 1:
                ok, _ = foto_gonder(paths[0], notifier=owner, caption=captions[0])
            else:
                ok, _ = medya_grubu_gonder(paths, captions=captions, notifier=owner)
            # Do not fall back to single photos on ambiguous album failure.
            if not ok:
                raise RuntimeError("Albüm teslim edilemedi; yeniden denenecek")
            owner.grafik_gonderilen += len(paths)
            import time
            owner._son_grafik_ts = time.monotonic()

    def status(self):
        with self.lock:
            pending = [r for r in self.state["rows"] if not r["done"]]
            return {"pending": len(pending),
                    "text_sent_media_pending": sum(bool(r["text_sent"]) for r in pending),
                    "oldest_created": pending[0]["created"] if pending else None,
                    "last_error": pending[0].get("last_error") if pending else None,
                    "retry_at": pending[0].get("retry_at") if pending else None}

    def flush(self, *, force=False):
        with self.lock:
            delivered = 0
            for row in self.state["rows"]:
                if row["done"]:
                    continue
                if not force and row.get("retry_at") and self.now() < datetime.fromisoformat(row["retry_at"]):
                    break
                try:
                    if not row["text_sent"]:
                        d = row["data"]
                        if not self.owner.can_send(d.get("stock_name", ""), d.get("pattern_name", ""),
                                                   d.get("timeframe", ""), d.get("state", ""),
                                                   formation_id=d.get("formation_id")):
                            break
                    self.prepare(row)  # all pictures ready BEFORE sending any text
                    # A previous checkpoint may have failed after mutating memory.
                    # Re-establish durability even when prepare() is already cached.
                    self.save()
                    if row["images"]:
                        self.owner._grafik_pace()  # pace BEFORE text, not between text and album
                    if not row["text_sent"]:
                        if not self.owner._gonder_metin(row["data"]):
                            break
                        row["text_sent"] = True
                        self.save()
                    if row["images"]:
                        self.send_images(row)
                    row["done"] = True
                    row.pop("retry_at", None)
                    row.pop("last_error", None)
                    row["images"] = []
                    row["data"].pop("grafik_verisi", None)
                    self.save()
                    delivered += 1
                except Exception as exc:
                    from secrets_redaction import redact_sensitive_text
                    row["last_error"] = redact_sensitive_text(str(exc), getattr(self.owner, "token", ""))[:200]
                    row["retry_at"] = (self.now() + timedelta(seconds=30)).isoformat()
                    try:
                        self.save()
                    except OSError:
                        log.exception("Teslim yeniden-deneme kaydı yazılamadı")
                    log.warning("Bildirim teslimi bekliyor (%s): %s", row["id"][:12], row["last_error"])
                    break  # FIFO: no other stock's text can interleave
            return delivered
