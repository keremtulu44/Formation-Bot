"""Local outbox for standalone Stabil/domain PUBLIC text and optional charts.

The ordinary lifecycle public queue cannot store these cards. A DM success must
not discard an unsent public copy. The outbox records intent before HTTP, keeps
budget/definite 4xx failures pending, and never automatically repeats an
ambiguous request (timeout/5xx or process death while sending). Telegram has no
idempotency key. Files on Render's default ephemeral disk are NOT durable across
redeploys; manual-review entries are intentionally not silently replayed.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import threading
from datetime import datetime, timedelta
from pathlib import Path

from config import ACIL_KUYRUK_TTL_DK, ISTANBUL_TZ
from notification_delivery import snapshot_from_json, snapshot_to_json

logger = logging.getLogger(__name__)


def auxiliary_event_id(kind, identities):
    """Stable ID for one card or a deterministic burst summary."""
    data = sorted([list(map(str, identity)) for identity in identities])
    digest = hashlib.sha256(json.dumps(data, ensure_ascii=False).encode("utf-8")).hexdigest()
    return f"{kind}:{digest}"


class PublicAuxOutbox:
    """Persist public-only cards without coupling their state to DM success."""

    MAX_PENDING = 100
    RECEIPT_DAYS = 7

    def __init__(self, notifier, directory, *, filename="telegram_public_aux.json", max_images=2, label="Public"):
        self.owner = notifier
        self.label = label
        self.path = Path(directory) / filename
        self.max_images = max_images
        self.lock = threading.RLock()
        self.rows = []
        self.available = True
        self._volatile_graphics = {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or raw.get("version") != 1 or not isinstance(raw.get("rows"), list):
                raise ValueError("invalid outbox")
            if any(not isinstance(row, dict) or not row.get("id") for row in raw["rows"]):
                raise ValueError("invalid row")
            self.rows = raw["rows"]
            for row in self.rows:
                # The process could have died after Telegram accepted the call.
                if row.get("status") == "sending":
                    row["status"] = "uncertain"
                elif row.get("status") == "graphics_sending":
                    row["status"] = "graphics_uncertain"
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError) as exc:
            self.available = False
            logger.error("%s özel alarm kuyruğu okunamadı; üzerine yazılmayacak: %s", self.label, type(exc).__name__)

    def _now(self):
        return datetime.now(ISTANBUL_TZ)

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".public_aux_", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump({"version": 1, "rows": self.rows}, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def _prune_receipts(self, now):
        kept = []
        for row in self.rows:
            if row.get("status") not in {"complete", "cancelled"}:
                kept.append(row)
                continue
            try:
                created = datetime.fromisoformat(str(row["created"]))
                if created.tzinfo is None:
                    created = ISTANBUL_TZ.localize(created)
                if now - created < timedelta(days=self.RECEIPT_DAYS):
                    kept.append(row)
            except (KeyError, TypeError, ValueError):
                kept.append(row)  # malformed receipt is not silently discarded
        self.rows = kept

    def submit(self, event_id, text, *, identity=None, graphics=None):
        """Return (persisted, text_sent); public target must already be known."""
        if not self.available or not event_id or not text or not self.owner.public_enabled:
            if not self.owner.public_enabled:
                logger.warning("%s özel alarmı kuyruğa alınamadı: hedef kapalı", self.label)
            return False, False
        target = str(self.owner.public_chat_id or "").strip()
        if not target:
            return False, False
        with self.lock:
            row = next((item for item in self.rows if item.get("id") == str(event_id)), None)
            if row is not None:
                if row.get("target") != target:
                    logger.error("%s özel alarm hedefi değişmiş; eski kayıt yeni hedefe gönderilmeyecek", self.label)
                    return False, False
                return True, bool(row.get("text_sent"))
            now = self._now()
            self._prune_receipts(now)
            if sum(r.get("status") not in {"complete", "cancelled"} for r in self.rows) >= self.MAX_PENDING:
                logger.error("%s özel alarm kuyruğu dolu (%d); yeni olay saklanamadı", self.label, self.MAX_PENDING)
                return False, False
            snapshot = None
            if isinstance(graphics, dict) and graphics.get("goruntular"):
                try:
                    snapshot = snapshot_to_json(graphics)
                except (TypeError, ValueError, OverflowError) as exc:
                    # Still send text and, if the process stays alive, the image.
                    # A restart cannot recover an unserializable in-memory image.
                    self._volatile_graphics[str(event_id)] = graphics
                    logger.warning("%s özel alarm görseli diske saklanamadı (%s); "
                                   "restart sonrası geri yüklenemez", self.label, type(exc).__name__)
            row = {
                "id": str(event_id), "target": target, "created": now.isoformat(),
                "status": "pending", "text_sent": False, "text": str(text),
                "identity": dict(identity or {}), "graphics": snapshot,
                "volatile_graphics": str(event_id) in self._volatile_graphics,
            }
            self.rows.append(row)
            try:
                self._save()  # write intent BEFORE a network side effect
            except (OSError, TypeError, ValueError) as exc:
                self.rows.remove(row)
                self._volatile_graphics.pop(str(event_id), None)
                logger.error("%s özel alarmı diske kaydedilemedi; gönderim denenmedi: %s", self.label, type(exc).__name__)
                return False, False
            try:
                # Older pending work gets the first available public budget.
                self._flush_locked(max_items=3)
            except (OSError, TypeError, ValueError) as exc:
                # Intent was persisted; an interrupted request is not replayed.
                if row.get("status") == "sending":
                    row["status"] = "uncertain"
                elif row.get("status") == "graphics_sending":
                    row["status"] = "graphics_uncertain"
                logger.error("%s özel alarm sonucu kaydedilemedi: %s", self.label, type(exc).__name__)
            return True, bool(row.get("text_sent"))

    def _mark_expired(self, row, now):
        try:
            created = datetime.fromisoformat(str(row["created"]))
            if created.tzinfo is None:
                created = ISTANBUL_TZ.localize(created)
            age = (now - created).total_seconds()
            if created.astimezone(ISTANBUL_TZ).date() != now.date() or age > ACIL_KUYRUK_TTL_DK * 60:
                row["status"] = "expired"
                logger.warning("%s özel alarmı bayatladı; otomatik gönderilmeyecek (%s)", self.label, row.get("id"))
                return True
            if age < -120:
                row["status"] = "uncertain"
                return True
        except (KeyError, TypeError, ValueError):
            row["status"] = "uncertain"
            return True
        return False

    def _finish_graphics(self, row):
        graphics = self._volatile_graphics.get(row["id"])
        if graphics is None and row.get("graphics") is not None:
            try:
                graphics = snapshot_from_json(row["graphics"])
            except (TypeError, ValueError, OverflowError):
                row["status"] = "graphics_uncertain"
                self._save()
                return
        if not graphics:
            if row.get("volatile_graphics"):
                row["status"] = "graphics_uncertain"
                logger.warning("%s özel alarm görseli restart sonrasında bulunamadı; metin korunuyor", self.label)
            else:
                row["status"] = "complete"
            self._save()
            return
        row["status"] = "graphics_sending"
        self._save()  # a crash here means the image outcome requires review
        try:
            sent = int(self.owner.public_grafik_bagla(row.get("identity") or {}, graphics) or 0)
        except Exception as exc:  # noqa: BLE001 - alert text has already been sent
            sent = 0
            logger.warning("%s özel alarm görseli gönderilemedi: %s", self.label, type(exc).__name__)
        self._volatile_graphics.pop(row["id"], None)
        expected = min(self.max_images, len(graphics.get("goruntular") or []))
        if expected and sent >= expected:
            row["status"] = "complete"
            row["graphics"] = None
        else:
            row["status"] = "graphics_uncertain"
            logger.warning("%s özel alarm metni gitti, %d/%d görsel bildirildi; "
                           "belirsizlik/çift riskine karşı otomatik tekrar yok", self.label, sent, expected)
        self._save()

    def _flush_locked(self, max_items, only_id=None):
        if not self.available or not self.owner.public_enabled:
            return 0
        now = self._now()
        sent_count = 0
        attempted = 0
        for row in self.rows:
            if only_id is not None and row.get("id") != only_id:
                continue
            if row.get("status") not in {"pending", "text_sent"}:
                continue
            if attempted >= max_items:
                break
            attempted += 1
            if row.get("target") != str(self.owner.public_chat_id or "").strip():
                row["status"] = "target_changed"
                self._save()
                logger.error("%s özel alarm hedefi değişti; kayıt elle incelenmeli", self.label)
                continue
            if self._mark_expired(row, now):
                self._save()
                continue
            if row.get("status") == "text_sent":
                self._finish_graphics(row)
                continue
            with self.owner._public_send_lck:
                row["status"] = "sending"
                self._save()
                try:
                    ok = bool(self.owner.send_to_public(row["text"]))
                    outcome = getattr(self.owner, "_son_public_deneme", "belirsiz")
                except Exception as exc:  # noqa: BLE001 - unknown HTTP outcome
                    ok, outcome = False, "belirsiz"
                    logger.warning("%s özel alarm gönderim sonucu belirsiz: %s", self.label, type(exc).__name__)
                if ok and outcome != "hedef_yok":
                    row["text_sent"] = True
                    row["status"] = "text_sent"
                    self._save()
                    sent_count += 1
                    self._finish_graphics(row)
                elif outcome in {"butce", "reddedildi", "hedef_yok"}:
                    row["status"] = "pending"  # no delivery occurred; safe to retry later
                    self._save()
                    logger.warning("%s özel alarmı (%s) beklemede; daha sonra denenebilir", self.label, outcome)
                    break
                else:
                    row["status"] = "uncertain"
                    self._save()
                    logger.warning("%s özel alarm teslimi belirsiz; otomatik tekrar yok, elle incele", self.label)
        return sent_count

    def cancel_retired_stabil(self):
        """Retire definitely-unsent, individually identified old reclaim cards."""
        with self.lock:
            if not self.available:
                return 0
            ids = []
            for row in self.rows:
                identity = row.get("identity") or {}
                if (row.get("status") == "pending" and not row.get("text_sent")
                        and identity.get("state") == "STABIL_GERI_ALIM"
                        and identity.get("pattern_name") == "STABİL GÜÇLÜ GERİ ALIM"):
                    ids.append(row["id"])
            return sum(bool(self.cancel_pending(event_id)) for event_id in ids)

    def cancel_pending(self, event_id):
        """Cancel a definitely unsent single event; never alter ambiguous/delivered work."""
        with self.lock:
            if not self.available:
                return False
            row = next((r for r in self.rows if r.get("id") == str(event_id)), None)
            if row is None or row.get("status") != "pending" or row.get("text_sent"):
                return False
            row["status"] = "cancelled"
            row["graphics"] = None
            self._volatile_graphics.pop(str(event_id), None)
            self._save()
            return True

    def cancel_stabil_member(self, event_id):
        """Cancel an unsent single; quarantine unsent summaries containing it.

        A grouped card cannot safely be rewritten without reconstructing all
        members; retain it for review rather than silently lose other members.
        """
        with self.lock:
            cancelled = int(self.cancel_pending(event_id))
            changed = False
            for row in self.rows:
                identity = row.get("identity") or {}
                if (row.get("status") == "pending" and not row.get("text_sent")
                        and identity.get("state") == "STABIL_OZET"
                        and str(event_id) in (identity.get("stabil_event_ids") or [])):
                    row["status"] = "invalidated_group"
                    changed = True
            if changed:
                self._save()
            return cancelled + int(changed)

    def flush(self, max_items=3):
        with self.lock:
            try:
                return self._flush_locked(max(1, int(max_items)))
            except (OSError, TypeError, ValueError) as exc:
                logger.error("%s özel alarm kuyruğu kaydedilemedi: %s", self.label, type(exc).__name__)
                return 0

    def status(self):
        with self.lock:
            return {
                "available": self.available,
                "pending": sum(r.get("status") in {"pending", "text_sent"} for r in self.rows),
                "review": sum(r.get("status") in {"uncertain", "graphics_uncertain", "expired", "target_changed", "sending", "graphics_sending", "invalidated_group"} for r in self.rows),
                "completed": sum(r.get("status") == "complete" for r in self.rows),
            }
