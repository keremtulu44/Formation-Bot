"""Independent local DM delivery for standalone domain/Stabil cards.

Only definite HTTP 4xx responses are retried. A timeout/5xx or interrupted
request requires operator review because Telegram has no idempotency key.
The local outbox is not durable across loss of the host's ephemeral disk.
"""
from __future__ import annotations

import logging
import os
import re
import threading

from public_aux_outbox import PublicAuxOutbox

logger = logging.getLogger(__name__)


class _PrivateAdapter:
    """Adapt the shared outbox state machine to the private Telegram route."""

    def __init__(self, notifier):
        self.notifier = notifier
        self._public_send_lck = threading.RLock()
        self._son_public_deneme = "bilinmiyor"

    @property
    def public_enabled(self):
        n = self.notifier
        dm = str(getattr(n, "chat_id", "") or "").strip()
        public = str(getattr(n, "public_chat_id", "") or "").strip()
        return bool(getattr(n, "enabled", False) and dm and dm != public)

    @property
    def public_chat_id(self):
        return str(getattr(self.notifier, "chat_id", "") or "").strip()

    def send_to_public(self, text):
        # The ordinary helper retries timeouts; exactly ONE request here so an
        # unknown result cannot create an automatic duplicate.
        self._son_public_deneme = "belirsiz"
        result = self.notifier.send_text(text, deneme=1)
        ok = bool(result[0] if isinstance(result, tuple) else result)
        detail = str(result[1] if isinstance(result, tuple) and len(result) > 1 else "")
        if ok:
            self._son_public_deneme = "gonderildi"
        elif re.match(r"^HTTP 4\d\d(?:\D|$)", detail):
            self._son_public_deneme = "reddedildi"
        return ok

    def public_grafik_bagla(self, identity, graphics):
        """Render the saved DM snapshots and use the existing DM album path."""
        import grafik
        from notifier.util import _grafik_basligi

        frames = list(graphics.get("goruntular") or [])[:4]
        if not frames or not grafik.disk_uygun_mu():
            return 0
        event = {"sembol": graphics.get("sembol") or identity.get("stock_name") or "",
                 "state": identity.get("state") or ""}
        packages = []
        try:
            # Do not send a partial album if a frame fails to render.
            for frame in frames:
                path, meta = grafik.kareyi_yaz(frame.get("goruntu") or {}, frame.get("tf") or "1h")
                if not path:
                    return 0
                packages.append((str(path), _grafik_basligi(event, frame, meta)))
            result = self.notifier.grafik_toplu_gonder(packages)
            return sum(bool(item) for item in result)
        except Exception as exc:  # noqa: BLE001 - text is already delivered
            logger.warning("DM özel alarm grafiği üretilemedi/gönderilemedi: %s", type(exc).__name__)
            return 0
        finally:
            for path, _caption in packages:
                try:
                    os.remove(path)
                except OSError:
                    pass  # `grafik_toplu_gonder` normally removes it first


class PrivateAuxOutbox(PublicAuxOutbox):
    def __init__(self, notifier, directory):
        super().__init__(_PrivateAdapter(notifier), directory,
                         filename="telegram_dm_aux.json", max_images=4, label="DM")
