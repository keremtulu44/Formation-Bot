"""Small durable Telegram delivery outbox and watch-state snapshot.

The local JSON snapshot is atomically replaced. When Supabase is configured the
same bounded snapshot is mirrored as one row, so a service replacement can
recover it without introducing another queue service.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import os
import threading
from typing import Any, Dict, Iterable, Optional


logger = logging.getLogger(__name__)
STATE_KEY = "state:telegram_delivery"
SCHEMA_VERSION = 1
MAX_PENDING = 500
MAX_TERMINAL = 1000
MAX_ATTEMPTS = 5
MAX_AGE = timedelta(hours=24)
SCHEDULED_MAX_AGE = timedelta(hours=6)
TERMINAL_RETENTION = timedelta(days=30)
RETRY_BASE_SECONDS = 30
RETRY_MAX_SECONDS = 1800


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(value: Any) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value)
    except ValueError:
        return None
    if result.tzinfo is None:
        return result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _valid_state(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and value.get("schema_version") == SCHEMA_VERSION
        and isinstance(value.get("items"), dict)
        and (value.get("watch") is None or isinstance(value.get("watch"), dict))
    )


def _atomic_write(path: str, payload: dict) -> None:
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    temp_path = path + ".tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
    finally:
        try:
            os.remove(temp_path)
        except FileNotFoundError:
            pass


class NotificationOutbox:
    """Process-safe-enough single-writer ledger for this single bot process.

    `sending` is persisted before network I/O. On restart it is retried after a
    backoff (at-least-once); Telegram offers no sendMessage idempotency token,
    so a crash after Telegram accepts but before `sent` is committed can still
    produce one duplicate.
    """

    def __init__(
        self,
        path: str,
        *,
        persistent_store=None,
        initial_state: Any = None,
        clock=_utc_now,
    ) -> None:
        self.path = path
        self.persistent_store = persistent_store
        self._clock = clock
        self._lock = threading.RLock()
        self.state = self._normalize_state(self._load(initial_state))
        self._recover_interrupted_sends()
        self._prune()

    def _default_state(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "updated_at": _iso(self._clock()),
            "items": {},
            "watch": None,
            "last_attempt_at": None,
        }

    def _normalize_state(self, value: dict) -> dict:
        normalized = self._default_state()
        if isinstance(value, dict):
            normalized.update({
                key: value.get(key, normalized[key])
                for key in ("updated_at", "watch", "last_attempt_at")
            })
            normalized["schema_version"] = SCHEMA_VERSION
        if _parse_time(normalized.get("updated_at")) is None:
            normalized["updated_at"] = _iso(self._clock())
        if normalized.get("last_attempt_at") is not None and _parse_time(normalized.get("last_attempt_at")) is None:
            normalized["last_attempt_at"] = None
        raw_items = value.get("items", {}) if isinstance(value, dict) else {}
        if not isinstance(raw_items, dict):
            logger.warning("Telegram outbox items field malformed; starting with empty item ledger")
            return normalized
        valid_statuses = {"prepared", "pending", "sending", "sent", "dead", "expired"}
        for item_id, raw in raw_items.items():
            if not isinstance(item_id, str) or not isinstance(raw, dict):
                logger.warning("Ignoring malformed Telegram outbox item")
                continue
            record = deepcopy(raw)
            status = record.get("status")
            if status not in valid_statuses:
                record.update(status="dead", last_error="unsupported item status in persisted state")
            if not isinstance(record.get("text"), str) or not isinstance(record.get("chat_id"), str):
                record.update(status="dead", last_error="malformed item missing text/chat_id")
            for field in ("destination", "kind"):
                if not isinstance(record.get(field), str):
                    record.update(status="dead", last_error=f"malformed item missing {field}")
            if not isinstance(record.get("series_key"), (str, type(None))):
                record["series_key"] = None
                record.update(status="dead", last_error="malformed ordering key")
            if not isinstance(record.get("policy", False), bool):
                record["policy"] = False
                record.update(status="dead", last_error="malformed delivery policy")
            if not isinstance(record.get("watch_context", []), list):
                record["watch_context"] = []
            try:
                record["attempts"] = max(0, int(record.get("attempts", 0)))
            except (TypeError, ValueError):
                record["attempts"] = 0
                record.update(status="dead", last_error="malformed attempt counter")
            record["id"] = item_id
            now = self._clock()
            defaults = {
                "created_at": normalized["updated_at"],
                "updated_at": normalized["updated_at"],
                "next_attempt_at": _iso(now),
                "expires_at": _iso(now + (SCHEDULED_MAX_AGE if record.get("kind") == "scheduled" else MAX_AGE)),
            }
            for field, fallback in defaults.items():
                if not isinstance(record.get(field), str) or _parse_time(record.get(field)) is None:
                    record[field] = fallback
            normalized["items"][item_id] = record
        active_items = [
            (item_id, record) for item_id, record in normalized["items"].items()
            if record.get("status") in {"prepared", "pending", "sending"}
        ]
        active_items.sort(key=lambda pair: (pair[1].get("created_at", ""), pair[0]))
        for item_id, record in active_items[MAX_PENDING:]:
            record.update(
                status="dead", updated_at=_iso(self._clock()),
                last_error="restored outbox exceeded bounded pending capacity",
            )
        terminal = [
            (item_id, record) for item_id, record in normalized["items"].items()
            if record.get("status") not in {"prepared", "pending", "sending"}
        ]
        terminal.sort(key=lambda pair: (pair[1].get("updated_at", ""), pair[0]), reverse=True)
        for item_id, _record in terminal[MAX_TERMINAL:]:
            normalized["items"].pop(item_id, None)
        if normalized.get("watch") is not None and not isinstance(normalized["watch"], dict):
            normalized["watch"] = None
        return normalized

    def _read_local(self):
        if not os.path.exists(self.path):
            return None
        try:
            with open(self.path, encoding="utf-8") as stream:
                value = json.load(stream)
        except (json.JSONDecodeError, UnicodeError, OSError) as exc:
            logger.warning("Telegram delivery state file is unreadable; trying remote/default state: %s", exc)
            return None
        if not _valid_state(value):
            logger.warning("Telegram delivery state has unsupported/old schema; safe empty state will be used")
            return None
        return value

    def _load(self, remote):
        local = self._read_local()
        remote = remote if _valid_state(remote) else None
        if local is None and remote is None:
            return self._default_state()
        if local is None:
            return deepcopy(remote)
        if remote is None:
            return deepcopy(local)
        local_time = _parse_time(local.get("updated_at")) or datetime.min.replace(tzinfo=timezone.utc)
        remote_time = _parse_time(remote.get("updated_at")) or datetime.min.replace(tzinfo=timezone.utc)
        return deepcopy(local if local_time >= remote_time else remote)

    def _save(self, *, remote: bool = True) -> bool:
        self.state["updated_at"] = _iso(self._clock())
        local_ok = False
        try:
            _atomic_write(self.path, self.state)
            local_ok = True
        except Exception:
            logger.exception("Telegram delivery state local persistence failed")
        remote_ok = False
        if remote and self.persistent_store is not None:
            try:
                remote_ok = bool(self.persistent_store.upsert(STATE_KEY, deepcopy(self.state)))
                if not remote_ok:
                    logger.warning("Telegram delivery state Supabase upsert returned false; local copy=%s", local_ok)
            except Exception:
                logger.exception("Telegram delivery state Supabase persistence failed; local copy=%s", local_ok)
        return local_ok or remote_ok

    @staticmethod
    def make_id(logical_identity: str, destination: str) -> str:
        canonical = f"{destination}\0{logical_identity}".encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def get(self, item_id: str) -> Optional[dict]:
        with self._lock:
            item = self.state["items"].get(item_id)
            return deepcopy(item) if item else None

    def enqueue(self, item_id: str, item: dict, *, prepared: bool = False) -> tuple[Optional[dict], bool]:
        """Idempotently enqueue; prepared records are held until context is attached."""
        with self._lock:
            existing = self.state["items"].get(item_id)
            if existing is not None:
                return deepcopy(existing), False
            self._prune_locked()
            pending = sum(
                record.get("status") in {"prepared", "pending", "sending"}
                for record in self.state["items"].values()
            )
            if pending >= MAX_PENDING:
                logger.error("Telegram outbox full (%d pending); rejecting new item %s", pending, item_id)
                return None, False
            now = self._clock()
            record = dict(item)
            record.update({
                "id": item_id,
                "application_acknowledged": not (item.get("kind") == "formation" and item.get("destination") == "dm"),
                "status": "prepared" if prepared else "pending",
                "attempts": 0,
                "created_at": _iso(now),
                "updated_at": _iso(now),
                "next_attempt_at": _iso(now),
                "expires_at": _iso(now + (SCHEDULED_MAX_AGE if item.get("kind") == "scheduled" else MAX_AGE)),
                "last_error": None,
            })
            if prepared:
                record["fallback_text"] = str(item.get("fallback_text", item.get("text", "")))
                record["needs_context"] = True
            self.state["items"][item_id] = record
            if not self._save():
                self.state["items"].pop(item_id, None)
                logger.error("Telegram outbox enqueue rejected because no durable snapshot was written")
                return None, False
            return deepcopy(record), True

    def activate_prepared(self, item_id: str, text: str, updates: Optional[dict] = None) -> bool:
        """Persist enriched/current-scan text before making a prepared job sendable."""
        with self._lock:
            record = self.state["items"].get(item_id)
            if not record or record.get("status") != "prepared":
                return False
            original = deepcopy(record)
            if updates:
                record.update(deepcopy(updates))
            record.update(
                text=str(text), status="pending", needs_context=False,
                updated_at=_iso(self._clock()),
            )
            if self._save():
                return True
            self.state["items"][item_id] = original
            logger.error("Prepared Telegram job remains blocked: enriched payload was not durable")
            return False

    def due_items(self, *, limit: int = 10) -> list[dict]:
        with self._lock:
            if self._prune_locked():
                self._save()
            records = list(self.state["items"].values())
            records.sort(key=lambda r: (r.get("created_at", ""), r.get("id", "")))
            earlier_pending_by_series = set()
            selected = []
            for record in records:
                if record.get("status") not in {"prepared", "pending", "sending"}:
                    continue
                series = record.get("series_key")
                if series and series in earlier_pending_by_series:
                    continue
                if series:
                    earlier_pending_by_series.add(series)
                if record.get("status") != "pending":
                    continue
                due = _parse_time(record.get("next_attempt_at"))
                if due is not None and due > self._clock():
                    continue
                selected.append(deepcopy(record))
                if len(selected) >= limit:
                    break
            return selected

    def prepared_items(self, *, limit: int = 500) -> list[dict]:
        with self._lock:
            records = [
                record for record in self.state["items"].values()
                if record.get("status") == "prepared"
            ]
            records.sort(key=lambda record: (record.get("created_at", ""), record.get("id", "")))
            return [deepcopy(record) for record in records[:max(1, int(limit))]]

    def unacknowledged_sent(self, *, limit: int = 100) -> list[dict]:
        with self._lock:
            records = [
                record for record in self.state["items"].values()
                if record.get("status") == "sent" and not record.get("application_acknowledged", True)
            ]
            records.sort(key=lambda record: (record.get("sent_at", ""), record.get("id", "")))
            return [deepcopy(record) for record in records[:max(1, int(limit))]]

    def acknowledge_delivery(self, item_id: str) -> bool:
        with self._lock:
            record = self.state["items"].get(item_id)
            if not record or record.get("status") != "sent":
                return False
            if record.get("application_acknowledged", True):
                return True
            record["application_acknowledged"] = True
            record["updated_at"] = _iso(self._clock())
            return self._save()

    def claim(self, item_id: str) -> Optional[dict]:
        with self._lock:
            record = self.state["items"].get(item_id)
            if not record or record.get("status") != "pending":
                return None
            now = self._clock()
            previous_attempts = int(record.get("attempts", 0))
            record["status"] = "sending"
            record["attempts"] = previous_attempts + 1
            record["attempt_started_at"] = _iso(now)
            record["updated_at"] = _iso(now)
            if not self._save():
                record["status"] = "pending"
                record["attempts"] = previous_attempts
                record.pop("attempt_started_at", None)
                logger.error("Telegram outbox claim rejected because sending state was not durable")
                return None
            return deepcopy(record)

    def mark_sent(self, item_id: str, *, confirmed_by_cooldown: bool = False) -> None:
        with self._lock:
            record = self.state["items"].get(item_id)
            if not record:
                return
            record.update(status="sent", updated_at=_iso(self._clock()), sent_at=_iso(self._clock()))
            if confirmed_by_cooldown:
                record["recovered_from_cooldown"] = True
            self._save()

    def defer(self, item_id: str, delay_seconds: float) -> None:
        """Reschedule policy/cap deferral without spending a delivery attempt."""
        with self._lock:
            record = self.state["items"].get(item_id)
            if not record or record.get("status") not in {"pending", "sending"}:
                return
            now = self._clock()
            record.update(
                status="pending",
                next_attempt_at=_iso(now + timedelta(seconds=max(1.0, float(delay_seconds)))),
                updated_at=_iso(now),
            )
            self._save()

    def mark_retry(self, item_id: str, error: str, *, delay_seconds: Optional[float] = None,
                   permanent: bool = False) -> None:
        with self._lock:
            record = self.state["items"].get(item_id)
            if not record:
                return
            attempts = int(record.get("attempts", 0))
            dead = permanent or attempts >= MAX_ATTEMPTS
            now = self._clock()
            if dead:
                record.update(status="dead", dead_at=_iso(now))
            else:
                if delay_seconds is None:
                    delay_seconds = min(RETRY_BASE_SECONDS * (2 ** max(0, attempts - 1)), RETRY_MAX_SECONDS)
                # Telegram retry_after can legitimately exceed the exponential
                # backoff ceiling; respect it (bounded by the 24h item TTL).
                delay_seconds = max(1.0, min(float(delay_seconds), MAX_AGE.total_seconds()))
                record.update(
                    status="pending",
                    next_attempt_at=_iso(now + timedelta(seconds=delay_seconds)),
                )
            record["last_error"] = str(error)[:300]
            record["updated_at"] = _iso(now)
            self._save()

    def set_last_attempt(self, at: datetime) -> None:
        with self._lock:
            self.state["last_attempt_at"] = _iso(at)
            self._save()

    def last_attempt(self) -> Optional[datetime]:
        with self._lock:
            return _parse_time(self.state.get("last_attempt_at"))

    def set_watch(self, snapshot: dict, *, remote: bool = True) -> bool:
        with self._lock:
            self.state["watch"] = deepcopy(snapshot)
            return self._save(remote=remote)

    def get_watch(self) -> Optional[dict]:
        with self._lock:
            watch = self.state.get("watch")
            return deepcopy(watch) if isinstance(watch, dict) else None

    def counts(self) -> dict:
        with self._lock:
            result = {status: 0 for status in ("prepared", "pending", "sending", "sent", "dead", "expired")}
            for record in self.state["items"].values():
                status = record.get("status")
                if status in result:
                    result[status] += 1
            return result

    def _recover_interrupted_sends(self) -> None:
        changed = False
        now = self._clock()
        with self._lock:
            original_items = deepcopy(self.state["items"])
            for record in self.state["items"].values():
                if record.get("status") == "prepared":
                    record.update(
                        status="pending",
                        text=str(record.get("fallback_text") or record.get("text") or ""),
                        needs_context=False,
                        next_attempt_at=_iso(now),
                        last_error="restart before context activation; using Formation-only fallback",
                    )
                    record["updated_at"] = _iso(now)
                    changed = True
                    continue
                if record.get("status") != "sending":
                    continue
                attempts = int(record.get("attempts", 0))
                if attempts >= MAX_ATTEMPTS:
                    record.update(status="dead", dead_at=_iso(now), last_error="recovered after repeated interrupted sends")
                else:
                    delay = min(RETRY_BASE_SECONDS * (2 ** max(0, attempts - 1)), RETRY_MAX_SECONDS)
                    record.update(
                        status="pending",
                        next_attempt_at=_iso(now + timedelta(seconds=delay)),
                        last_error="process interrupted during send; Telegram outcome is ambiguous",
                    )
                record["updated_at"] = _iso(now)
                changed = True
            if changed:
                logger.warning("Recovered interrupted Telegram send(s); outcome may be ambiguous")
                if not self._save():
                    self.state["items"] = original_items
                    logger.error("Interrupted send recovery was not durable; keeping jobs blocked")

    def _prune(self) -> None:
        with self._lock:
            if self._prune_locked():
                self._save()

    def _prune_locked(self) -> bool:
        now = self._clock()
        changed = False
        for item_id, record in list(self.state["items"].items()):
            status = record.get("status")
            if status in {"prepared", "pending", "sending"}:
                expires = _parse_time(record.get("expires_at"))
                if expires is not None and expires <= now:
                    record.update(status="expired", updated_at=_iso(now), last_error="outbox TTL expired")
                    changed = True
            elif status in {"sent", "dead", "expired"}:
                updated = _parse_time(record.get("updated_at"))
                if updated is not None and updated + TERMINAL_RETENTION <= now:
                    self.state["items"].pop(item_id, None)
                    changed = True
        terminal = [
            (item_id, record) for item_id, record in self.state["items"].items()
            if record.get("status") in {"sent", "dead", "expired"}
        ]
        if len(terminal) > MAX_TERMINAL:
            terminal.sort(key=lambda pair: (pair[1].get("updated_at", ""), pair[0]))
            for item_id, _record in terminal[:len(terminal) - MAX_TERMINAL]:
                self.state["items"].pop(item_id, None)
                changed = True
        return changed
