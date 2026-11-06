"""Safely quarantine public state whose original destination is unknown or changed.

The archive is local and can contain alert data; it must not be committed. It is
not an automatic resend queue, and an ephemeral Render filesystem is not a
backup. If the archive cannot be written, callers must not overwrite the old
state or deliver it to a different chat.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path

from config import ISTANBUL_TZ

logger = logging.getLogger(__name__)


def target_key(value):
    """Canonical comparison for numeric IDs and public usernames."""
    from telegram_commands import telegram_sohbet_kimligi
    target = telegram_sohbet_kimligi(value)
    return target.casefold() if target.startswith("@") else target


class PublicTargetReview:
    MAX_ARCHIVES = 100

    def __init__(self, directory):
        self.path = Path(directory) / "telegram_public_target_review.json"
        self.archives = []
        self.available = True
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("archives"), list):
                raise ValueError("invalid public target review archive")
            if any(not isinstance(row, dict) or not row.get("id") for row in data["archives"]):
                raise ValueError("invalid public target review entry")
            self.archives = data["archives"]
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError) as exc:
            self.available = False
            logger.error("Public hedef inceleme arşivi okunamadı: %s", type(exc).__name__)

    def archive(self, snapshot, current_target):
        """Atomically retain old state, returning False rather than losing it."""
        if not self.available:
            return False
        try:
            payload = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            identity = hashlib.sha256((target_key(current_target) + "\0" + payload).encode("utf-8")).hexdigest()
            if any(row.get("id") == identity for row in self.archives):
                return True
            if len(self.archives) >= self.MAX_ARCHIVES:
                raise OSError("public target review archive full")
            row = {"id": identity, "created": datetime.now(ISTANBUL_TZ).isoformat(),
                   "old_target": snapshot.get("target"), "new_target": current_target,
                   "public_state": json.loads(payload)}
            rows = self.archives + [row]
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix=".public_target_review_", suffix=".tmp", dir=str(self.path.parent))
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    json.dump({"version": 1, "archives": rows}, stream, ensure_ascii=False)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(tmp, self.path)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
            self.archives = rows
            return True
        except (OSError, TypeError, ValueError) as exc:
            logger.error("Public hedef inceleme arşivi yazılamadı: %s", type(exc).__name__)
            return False

    def status(self):
        return {"available": self.available, "archives": len(self.archives)}
