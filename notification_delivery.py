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


# --- Hikâye kapısı -----------------------------------------------------------
# Kimlik (formation_id = uuid4) her yeniden tespitte değiştiği için ne DM
# mührü ne public mührü "aynı hissenin aynı yöndeki hikâyesi" tekrarını
# kesebiliyor (ölçüm: docs/arastirma/KOVA_FAZI_OLCUMU_2026-10-23.md).
# Bu kapı kimliğe değil hisse+yön+durum aşamasına bakar:
#   * TEYİT (1) -> RETEST (2) ileri gidiş serbest, geri geliş (RETEST'ten
#     sonra tekrar TEYİT) aynı formasyonda her zaman / farklı formasyonda
#     aynı olay-gününde engellenir.
#   * Aynı aşama: aynı formation_id veya aynı olay-günü (bar tarihi) ikinci
#     kez basılmaz — TF ve desen ailesi farkı gözetilmez (KCHOL 4s üçgen +
#     2s kama aynı hikâyedir).
#   * Adayın barı, kabul edilmiş bir hikâye olayından yeni değilse replay/
#     kopyadır (restart sonrası eski mumun yeniden gelişi).
#   * Mutlak bayatlık: gün-içi TF olayı ancak kendi İstanbul gününde anlık
#     push olur; 1g için pencere 7 gündür (Cuma barı Pazartesi sabahı meşru).
#   * KIRILIM_GECERSIZLESTI asla burada engellenmez (geri almanin kendi
#     "önce teyit gitti mi" kapilari var); ama hikâyeyi kapatır: kapatış
#     anina kadarki bayat olaylar düşer, sonrasındaki taze hikâye serbesttir.
# Adayda bar zamani yoksa kapı ÇALIŞMAZ (eski davranış korunur): üretim
# payload'i bar_time'i her zaman taşır; zamansız kayit "yeni mi eski mi"
# sorusunu cevaplayamaz, tahminle sinyal düşürülmez.
_HIKAYE_ASAMA = {"KIRILIM_TEYITLI": 1, "RETEST_BASARILI": 2}
_GECERSIZ_STATE = "KIRILIM_GECERSIZLESTI"


def _zaman_coz(deger):
    """datetime/Timestamp/ISO-metin -> tz-aware datetime (yoksa None)."""
    if deger is None:
        return None
    if isinstance(deger, dict) and "__delivery_datetime__" in deger:
        deger = deger.get("__delivery_datetime__")
    if isinstance(deger, datetime):
        dt = deger
    elif isinstance(deger, date):
        dt = datetime(deger.year, deger.month, deger.day)
    elif hasattr(deger, "to_pydatetime"):
        try:
            dt = deger.to_pydatetime()
        except Exception:
            return None
    elif isinstance(deger, str):
        try:
            dt = datetime.fromisoformat(deger.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        # Bar etiketleri İstanbul duvar saatidir; tz'siz gelirse öyle oku.
        from config import ISTANBUL_TZ
        try:
            dt = ISTANBUL_TZ.localize(dt)
        except Exception:
            dt = dt.replace(tzinfo=ISTANBUL_TZ)
    return dt


def _olay_zamani(data):
    for alan in ("bar_time", "timestamp", "bar_kapanis"):
        dt = _zaman_coz((data or {}).get(alan))
        if dt is not None:
            return dt
    return None


def _yon(data):
    try:
        yon = int((data or {}).get("break_dir"))
    except (TypeError, ValueError):
        return 0
    return yon if yon in (-1, 1) else 0


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

    def _story_duplicate(self, data, oncekiler):
        """Hisse+yön hikâyesi bu olayı zaten anlattı mi? (`oncekiler`: (data, created)).

        Saf okuma: yan etki yok, mühür yazmaz. Kurallar modül başındaki
        "Hikâye kapısı" bloğunda. `created` yalnız eski kayitlarda bar
        zamanı yoksa yedek zaman olarak kullanılır.
        """
        state = str((data or {}).get("state") or "").strip().upper()
        if state == _GECERSIZ_STATE or state not in _HIKAYE_ASAMA:
            return False
        stock = str(data.get("stock_name") or "").strip().upper()
        yon = _yon(data)
        aday_zaman = _olay_zamani(data)
        if not stock or not yon or aday_zaman is None:
            return False
        tf = str(data.get("timeframe") or "").strip().lower()
        bugun = self.now().date()
        # Mutlak bayatlık: anlık push eski günün haberi olamaz.
        if tf in ("1h", "2h", "4h") and aday_zaman.date() < bugun:
            return True
        if tf == "1d" and (bugun - aday_zaman.date()).days > 7:
            return True
        kapatis = None            # son KIRILIM_GECERSIZLESTI (hikâye kapanışı)
        ilgili = []               # (zaman, asama, formation_id)
        for eski, created in oncekiler:
            if str((eski or {}).get("stock_name") or "").strip().upper() != stock:
                continue
            if _yon(eski) != yon:
                continue
            eski_zaman = _olay_zamani(eski) or _zaman_coz(created)
            if eski_zaman is None:
                continue
            eski_state = str(eski.get("state") or "").strip().upper()
            if eski_state == _GECERSIZ_STATE:
                if kapatis is None or eski_zaman > kapatis:
                    kapatis = eski_zaman
            elif eski_state in _HIKAYE_ASAMA:
                ilgili.append((eski_zaman, _HIKAYE_ASAMA[eski_state],
                               str(eski.get("formation_id") or "")))
        if kapatis is not None:
            if aday_zaman <= kapatis:     # kapanmış hikâyenin bayat tekrarı
                return True
            ilgili = [k for k in ilgili if k[0] > kapatis]
        asama = _HIKAYE_ASAMA[state]
        aday_fid = str(data.get("formation_id") or "")
        for eski_zaman, eski_asama, eski_fid in ilgili:
            if aday_zaman <= eski_zaman:  # aynı/eski bar: replay veya kopya
                return True
            ayni_kimlik = bool(aday_fid and eski_fid and aday_fid == eski_fid)
            ayni_gun = aday_zaman.date() == eski_zaman.date()
            if asama < eski_asama and (ayni_kimlik or ayni_gun):
                return True               # geri geliş: RETEST sonrası TEYİT
            if asama == eski_asama and (ayni_kimlik or ayni_gun):
                return True               # aynı aşama ikinci kez anlatılmaz
        return False

    def is_story_duplicate(self, data):
        """DM hikâye kapısı: teslim defterindeki (bekleyen dahil) satırlar kaynak."""
        with self.lock:
            return self._story_duplicate(
                data, [(r.get("data") or {}, r.get("created"))
                       for r in self.state["rows"]])

    def public_duplicate(self, data):
        with self.lock:
            # Hikâye kapısı TF/aile gözetmez; eski related/alias mantığı
            # (bar zamanı taşımayan kayıtlar dahil) onun ALTINDA korunur.
            if self._story_duplicate(
                    data, [(r.get("data") or {}, r.get("created"))
                           for r in self.state["public"]]):
                log.info("Public hikâye tekrarı engellendi: %s %s %s",
                         data.get("stock_name"), data.get("timeframe"),
                         data.get("state"))
                return True
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
            # formation_id + bar_time: hikâye kapısının kimlik/bar karşılaştırması
            # bunlara bakar; eski kayıtlarda yoksa kapı o kayıt için eski
            # davranışa düşer (created zamanı yedek olur).
            self.state["public"].append({"data": {k: data.get(k) for k in
                ("stock_name", "timeframe", "state", "break_dir", "pattern_name",
                 "formation_id", "bar_time")},
                "created": self.now().isoformat()})
            self.save()

    def submit(self, data):
        with self.lock:
            identity = event_id(data)
            row = next((r for r in self.state["rows"] if r["id"] == identity), None)
            if row is not None and row["done"]:
                return False
            if row is None:
                if self.is_cross_duplicate(data) or self.is_story_duplicate(data):
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
