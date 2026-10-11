"""Small log-safety helpers for credentials embedded in API URLs and errors."""

from __future__ import annotations

import re
from typing import Any


_RE_TELEGRAM_BOT_PATH = re.compile(r"(?i)(/bot)[^/?#\s'\"<>]+")
_RE_SECRET_QUERY = re.compile(
    r"(?i)([?&](?:token|secret(?:_token)?|api[_-]?key|k)=)[^&#\s'\"<>]+"
)
_REDACTED = "[REDACTED]"


def redact_sensitive_text(value: Any, *secrets: Any) -> str:
    """Return text with explicitly supplied secrets and common Telegram URL tokens masked.

    Requests exceptions often include the request path (``/bot<TOKEN>/...``),
    but not the request headers. Callers should still pass the credential they
    own so a token is redacted even if a transport formats it in an unusual way.
    """
    text = str(value)
    unique = sorted(
        {str(secret) for secret in secrets if secret is not None and str(secret)},
        key=len,
        reverse=True,
    )
    for secret in unique:
        text = text.replace(secret, _REDACTED)
    text = _RE_TELEGRAM_BOT_PATH.sub(r"\1" + _REDACTED, text)
    text = _RE_SECRET_QUERY.sub(r"\1" + _REDACTED, text)
    return text
