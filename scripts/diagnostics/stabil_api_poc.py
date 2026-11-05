"""Offline, loopback-only proof of concept for the proposed read-only Stabil API.

This is deliberately NOT imported by ``main.py`` and is NOT a production API.
It serves only the checked-in ASTOR archive, uses the real causal Stabil runner,
requires an API key for data routes, performs no network fetch/write, and binds
only to 127.0.0.1. Its purpose is to exercise request/response and as_of contracts
before choosing a production framework or exposing a public service.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hmac
import json
import logging
import math
import os
import re
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Mapping
from urllib.parse import parse_qs, unquote, urlsplit

import pandas as pd

from config import ISTANBUL_TZ
from domain_engines.runner import DomainRunResult, run_stabil_domain
from research.arsiv import tf_frame

logger = logging.getLogger(__name__)

API_VERSION = "v1"
ENGINE_VERSION = "stabil-local-poc"
SUPPORTED_SYMBOLS = ("ASTOR",)
SUPPORTED_TIMEFRAMES = ("4h", "1d")
_SYMBOL_RE = re.compile(r"^[A-Z0-9._-]{1,16}$")

FrameLoader = Callable[[str, str], pd.DataFrame]
Clock = Callable[[], datetime]


def _archive_frame(symbol: str, timeframe: str) -> pd.DataFrame:
    """Load a copy of a repository archive frame; this never contacts a provider."""
    return tf_frame(symbol, timeframe)


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    try:
        ts = pd.Timestamp(value)
        if pd.isna(ts):
            return None
        if ts.tzinfo is None:
            ts = ts.tz_localize(ISTANBUL_TZ)
        else:
            ts = ts.tz_convert(ISTANBUL_TZ)
        return ts.isoformat()
    except (TypeError, ValueError, OverflowError):
        return None


def _finite(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", value))


def _error(status: int, request_id: str, code: str, message: str,
           *, headers: Mapping[str, str] | None = None) -> tuple[int, dict, dict]:
    response_headers = dict(headers or {})
    return status, {
        "api_version": API_VERSION,
        "request_id": request_id,
        "error": {"code": code, "message": message},
    }, response_headers


class OfflineStabilApiPoc:
    """Small read-only contract adapter around the actual Stabil domain runner."""

    def __init__(self, api_key: str, *, frame_loader: FrameLoader | None = None,
                 clock: Clock | None = None) -> None:
        key = str(api_key or "").strip()
        if not key:
            raise ValueError("A non-empty local API key is required")
        self._api_key = key
        self._frame_loader = frame_loader or _archive_frame
        self._clock = clock or (lambda: datetime.now(ISTANBUL_TZ))

    def dispatch(self, method: str, target: str, headers: Mapping[str, Any]
                 ) -> tuple[int, dict, dict]:
        request_id = uuid.uuid4().hex
        try:
            parsed = urlsplit(target)
        except ValueError:
            return _error(400, request_id, "invalid_target", "Request target is invalid.")
        if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"):
            return _error(400, request_id, "invalid_target", "Use an origin-form request path.")

        if method != "GET":
            return _error(
                405, request_id, "method_not_allowed", "Only GET is supported by this read-only POC.",
                headers={"Allow": "GET"},
            )

        if parsed.path == "/v1/health":
            if parsed.query:
                return _error(422, request_id, "unexpected_query", "This endpoint accepts no query parameters.")
            return 200, {
                "status": "ok",
                "api_version": API_VERSION,
                "mode": "offline-poc",
                "read_only": True,
            }, {}

        supplied_key = str(headers.get("X-API-Key", "") or "").strip()
        if not hmac.compare_digest(supplied_key, self._api_key):
            return _error(401, request_id, "unauthorized", "Missing or invalid X-API-Key header.")

        if parsed.path == "/v1/symbols":
            if parsed.query:
                return _error(422, request_id, "unexpected_query", "This endpoint accepts no query parameters.")
            return 200, {
                "api_version": API_VERSION,
                "source": "archive",
                "symbols": [
                    {"symbol": symbol, "timeframes": list(SUPPORTED_TIMEFRAMES)}
                    for symbol in SUPPORTED_SYMBOLS
                ],
                "read_only": True,
                "not_investment_advice": True,
            }, {}

        match = re.fullmatch(r"/v1/symbols/([^/]+)/stabil", parsed.path)
        if match is None:
            return _error(404, request_id, "not_found", "No such POC endpoint.")

        try:
            symbol = unquote(match.group(1), errors="strict").upper()
        except (UnicodeDecodeError, ValueError):
            return _error(422, request_id, "invalid_symbol", "Symbol path segment is not valid UTF-8.")
        if not _SYMBOL_RE.fullmatch(symbol):
            return _error(422, request_id, "invalid_symbol", "Symbol contains unsupported characters.")
        if symbol.endswith(".IS"):
            symbol = symbol[:-3]
        if symbol not in SUPPORTED_SYMBOLS:
            return _error(404, request_id, "symbol_unavailable", "This offline POC only contains ASTOR archive data.")

        try:
            query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=False)
        except ValueError:
            return _error(422, request_id, "invalid_query", "Query string could not be parsed.")
        if set(query) - {"tf", "as_of"}:
            return _error(422, request_id, "unexpected_query", "Only tf and as_of are accepted.")
        if any(len(values) != 1 for values in query.values()):
            return _error(422, request_id, "duplicate_query", "Pass each query parameter exactly once.")
        timeframe = (query.get("tf") or [""])[0].strip().lower()
        raw_as_of = (query.get("as_of") or [""])[0].strip()
        if timeframe not in SUPPORTED_TIMEFRAMES:
            return _error(422, request_id, "unsupported_timeframe", "tf must be 4h or 1d in this POC.")
        if not raw_as_of or len(raw_as_of) > 80:
            return _error(422, request_id, "as_of_required", "Pass one timezone-aware ISO-8601 as_of value.")
        try:
            as_of_dt = datetime.fromisoformat(raw_as_of.replace("Z", "+00:00"))
        except ValueError:
            return _error(422, request_id, "invalid_as_of", "as_of must be an ISO-8601 timestamp.")
        if as_of_dt.tzinfo is None or as_of_dt.utcoffset() is None:
            return _error(422, request_id, "timezone_required", "as_of must include Z or an explicit UTC offset.")
        as_of = pd.Timestamp(as_of_dt).tz_convert(ISTANBUL_TZ)
        now = pd.Timestamp(self._clock())
        if now.tzinfo is None:
            now = now.tz_localize(ISTANBUL_TZ)
        else:
            now = now.tz_convert(ISTANBUL_TZ)
        if as_of > now:
            return _error(422, request_id, "future_as_of", "as_of cannot be in the future.")

        try:
            daily = self._frame_loader(symbol, "1d")
            h4 = self._frame_loader(symbol, "4h")
        except (FileNotFoundError, ValueError, OSError):
            logger.warning("Offline Stabil POC archive unavailable for %s", symbol)
            return _error(503, request_id, "archive_unavailable", "Local archive data is unavailable.")
        if not isinstance(daily, pd.DataFrame) or daily.empty or not isinstance(h4, pd.DataFrame) or h4.empty:
            return _error(503, request_id, "archive_unavailable", "Local archive data is unavailable.")

        target = h4 if timeframe == "4h" else daily
        try:
            result: DomainRunResult = run_stabil_domain(
                symbol,
                timeframe,
                target,
                daily_frame=daily,
                h4_frame=h4,
                as_of_close=as_of,
                isolated=True,
            )
        except Exception:
            logger.exception("Offline Stabil API POC failed for request %s", request_id)
            return _error(500, request_id, "analysis_failed", "Stabil analysis failed; inspect local diagnostic logs.")
        if result.error or result.result is None:
            logger.error("Offline Stabil API POC returned an engine error for request %s", request_id)
            return _error(500, request_id, "analysis_failed", "Stabil analysis failed; inspect local diagnostic logs.")

        output = result.result
        behavior = getattr(output, "latest_behavior", None)
        latest_bar_close = _iso(getattr(behavior, "bar_close_time", None))
        cutoff_iso = as_of.isoformat()
        if latest_bar_close is not None and pd.Timestamp(latest_bar_close) > as_of:
            logger.error("Stabil API POC causality violation for request %s", request_id)
            return _error(500, request_id, "causality_violation", "Engine returned a bar after the requested as_of.")

        role_readiness = getattr(output, "role_readiness", {}) or {}
        readiness = {
            str(name): _enum_value(getattr(role, "status", role))
            for name, role in role_readiness.items()
        }
        quality = _enum_value(result.data_quality) or "UNKNOWN"
        warnings = ["OFFLINE_ARCHIVE_NOT_LIVE"]
        if quality != "OK":
            warnings.append(f"STABIL_DATA_QUALITY_{quality}")
        if any(value != "READY" for value in readiness.values()):
            warnings.append("ONE_OR_MORE_STABIL_ROLES_NOT_READY")

        latest_age_seconds = None
        if latest_bar_close is not None:
            latest_age_seconds = max(0, int((as_of - pd.Timestamp(latest_bar_close)).total_seconds()))
        reclaim_kind = getattr(behavior, "reclaim_kind", None) if behavior is not None else None
        momentum_kind = getattr(behavior, "momentum_kind", None) if behavior is not None else None
        support_level = (
            getattr(behavior, "support_level", None)
            if behavior is not None
            else getattr(getattr(output, "support_snapshot", None), "support_level", None)
        )
        return 200, {
            "api_version": API_VERSION,
            "request_id": request_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "as_of": cutoff_iso,
            "engine_version": ENGINE_VERSION,
            "data_quality": quality,
            "source": "archive",
            "latest_bar_close": latest_bar_close,
            "latest_bar_age_seconds_at_as_of": latest_age_seconds,
            "close_price": _finite(getattr(output, "latest_close", None)),
            "support_level": _finite(support_level),
            "price_vs_support": getattr(output, "latest_support_relation", None),
            "regime": getattr(behavior, "regime", None) if behavior is not None else None,
            "signals": {
                "reclaim_kind": reclaim_kind,
                "momentum_kind": momentum_kind,
                "weak_reclaim": bool(getattr(behavior, "weak_reclaim", False)) if behavior is not None else False,
            },
            "chart_markers": {
                "reclaim_arrow": bool(reclaim_kind),
                "momentum_arrow": bool(momentum_kind),
            },
            "readiness": readiness,
            "warnings": warnings,
            "not_investment_advice": True,
        }, {}


def make_handler(service: OfflineStabilApiPoc) -> type[BaseHTTPRequestHandler]:
    """Build a small HTTP adapter; production routing/auth is intentionally absent."""
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "FormationBotStabilApiPoc/0.1"
        sys_version = ""

        def do_GET(self):  # noqa: N802 - stdlib handler API
            self._dispatch("GET")

        def do_POST(self):  # noqa: N802 - stdlib handler API
            self._dispatch("POST")

        def do_PUT(self):  # noqa: N802 - stdlib handler API
            self._dispatch("PUT")

        def do_DELETE(self):  # noqa: N802 - stdlib handler API
            self._dispatch("DELETE")

        def _dispatch(self, method: str) -> None:
            status, payload, extra_headers = service.dispatch(method, self.path, self.headers)
            body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            for name, value in extra_headers.items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: Any) -> None:
            # The POC intentionally emits no request path, query, header or key logs.
            logger.debug("API POC request handled (%s)", self.command)

    return Handler


def build_local_server(api_key: str, *, port: int = 8765,
                       frame_loader: FrameLoader | None = None,
                       clock: Clock | None = None) -> ThreadingHTTPServer:
    """Create the POC server on loopback only; never bind to 0.0.0.0."""
    service = OfflineStabilApiPoc(api_key, frame_loader=frame_loader, clock=clock)
    server = ThreadingHTTPServer(("127.0.0.1", int(port)), make_handler(service))
    server.daemon_threads = True
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    api_key = os.environ.get("FORMATION_API_POC_KEY", "").strip()
    if not api_key:
        parser.error("set FORMATION_API_POC_KEY to a local throwaway value; never use a production secret")
    server = build_local_server(api_key, port=args.port)
    print(f"Offline Stabil API POC listening only on http://127.0.0.1:{server.server_address[1]}")
    print("Source: checked-in ASTOR archive; read-only; no provider/Telegram/Supabase calls. Ctrl-C to stop.")
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised as a local tool
    raise SystemExit(main())
