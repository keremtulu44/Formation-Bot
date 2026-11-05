"""HTTP-level contract checks for the offline, read-only Stabil API POC.

These tests bind only to 127.0.0.1, use the checked-in ASTOR archive, and never
call Yahoo, Telegram, Supabase, Render, or a broker.
"""

from __future__ import annotations

from contextlib import contextmanager
from http.server import ThreadingHTTPServer
import json
from threading import Thread
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
import pytest

from config import ISTANBUL_TZ
from data import mum_kapanis_anlari
from research.arsiv import tf_frame
from scripts.diagnostics.stabil_api_poc import OfflineStabilApiPoc, make_handler

_API_KEY = "local-test-key-not-a-secret"
_AS_OF = "2026-10-16T18:30:00+03:00"
_PARTIAL_AS_OF = "2026-10-16T17:30:00+03:00"


@contextmanager
def _serve(service):
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service))
    server.daemon_threads = True
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _request(base_url, path, *, api_key=None, method="GET", data=None):
    headers = {"Accept": "application/json"}
    if api_key is not None:
        headers["X-API-Key"] = api_key
    request = Request(base_url + path, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, response.headers, response.read()
    except HTTPError as exc:
        return exc.code, exc.headers, exc.read()
    except URLError as exc:  # pragma: no cover - makes local HTTP failures clear
        pytest.fail(f"local API POC HTTP request failed: {exc}")


def _stabil_path(as_of=_AS_OF, tf="4h"):
    query = urlencode([("tf", tf), ("as_of", as_of)])
    return f"/v1/symbols/ASTOR/stabil?{query}"


def test_http_readonly_stabil_request_returns_real_causal_archive_result():
    service = OfflineStabilApiPoc(_API_KEY)
    with _serve(service) as base:
        status, headers, body = _request(
            base, _stabil_path(), api_key=_API_KEY,
        )

    payload = json.loads(body.decode("utf-8"))
    assert status == 200
    assert headers.get("Cache-Control") == "no-store"
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert payload["symbol"] == "ASTOR"
    assert payload["timeframe"] == "4h"
    assert payload["as_of"] == _AS_OF
    assert payload["engine_version"] == "stabil-local-poc"
    assert payload["source"] == "archive"
    assert payload["data_quality"] == "OK"
    assert payload["latest_bar_close"] == "2026-10-16T18:00:00+03:00"
    assert payload["latest_bar_age_seconds_at_as_of"] == 1800
    assert payload["price_vs_support"] == "destek altında"
    assert payload["close_price"] == pytest.approx(164.9, abs=1e-3)
    assert payload["support_level"] == pytest.approx(172.1, abs=1e-3)
    assert payload["readiness"] == {
        "daily_support": "READY",
        "weekly_trend": "READY",
        "daily_trend": "READY",
        "h4_trend": "READY",
    }
    assert payload["warnings"] == ["OFFLINE_ARCHIVE_NOT_LIVE"]
    assert payload["not_investment_advice"] is True
    assert len(payload["request_id"]) == 32
    assert not ({"open", "high", "low", "close", "volume", "timestamp"} & payload.keys())


def test_timezone_equivalent_cutoffs_match_and_daily_endpoint_uses_daily_close():
    service = OfflineStabilApiPoc(_API_KEY)
    utc_path = _stabil_path(as_of="2026-10-16T15:30:00Z")
    daily_path = _stabil_path(tf="1d")
    with _serve(service) as base:
        utc_status, _, utc_raw = _request(base, utc_path, api_key=_API_KEY)
        local_status, _, local_raw = _request(base, _stabil_path(), api_key=_API_KEY)
        daily_status, _, daily_raw = _request(base, daily_path, api_key=_API_KEY)

    utc_payload = json.loads(utc_raw.decode("utf-8"))
    local_payload = json.loads(local_raw.decode("utf-8"))
    daily_payload = json.loads(daily_raw.decode("utf-8"))
    assert utc_status == local_status == daily_status == 200
    assert utc_payload["as_of"] == _AS_OF  # normalized to Istanbul, same instant
    for key in utc_payload:
        if key != "request_id":
            assert utc_payload[key] == local_payload[key]
    assert daily_payload["timeframe"] == "1d"
    assert daily_payload["latest_bar_close"] == _AS_OF
    assert daily_payload["latest_bar_age_seconds_at_as_of"] == 0
    assert daily_payload["close_price"] == pytest.approx(164.9, abs=1e-3)


def test_contract_health_auth_symbols_and_write_method_are_explicit():
    service = OfflineStabilApiPoc(_API_KEY)
    with _serve(service) as base:
        status, _, raw = _request(base, "/v1/health")
        health = json.loads(raw.decode("utf-8"))
        assert status == 200
        assert health["status"] == "ok"
        assert health["mode"] == "offline-poc"
        assert health["read_only"] is True

        status, _, raw = _request(base, "/v1/symbols")
        error = json.loads(raw.decode("utf-8"))
        assert status == 401
        assert error["error"]["code"] == "unauthorized"

        status, _, raw = _request(base, "/v1/symbols", api_key="wrong-local-key")
        error = json.loads(raw.decode("utf-8"))
        assert status == 401
        assert error["error"]["code"] == "unauthorized"

        status, _, raw = _request(base, "/v1/symbols", api_key=_API_KEY)
        symbols = json.loads(raw.decode("utf-8"))
        assert status == 200
        assert symbols["symbols"] == [{"symbol": "ASTOR", "timeframes": ["4h", "1d"]}]

        status, headers, raw = _request(
            base, "/v1/symbols", api_key=_API_KEY, method="POST", data=b"{}",
        )
        error = json.loads(raw.decode("utf-8"))
        assert status == 405
        assert headers.get("Allow") == "GET"
        assert error["error"]["code"] == "method_not_allowed"


def test_bad_symbol_timeframe_and_as_of_fail_closed_before_engine_call():
    calls = []

    def forbidden_loader(symbol, timeframe):
        calls.append((symbol, timeframe))
        raise AssertionError("invalid request must fail before archive access")

    service = OfflineStabilApiPoc(_API_KEY, frame_loader=forbidden_loader)
    with _serve(service) as base:
        cases = [
            ("/v1/symbols/THYAO/stabil?tf=4h&as_of=2026-10-16T18%3A30%3A00%2B03%3A00", 404, "symbol_unavailable"),
            (_stabil_path(tf="1h"), 422, "unsupported_timeframe"),
            ("/v1/symbols/ASTOR/stabil?tf=4h", 422, "as_of_required"),
            (_stabil_path(as_of="2026-10-16T18:30:00"), 422, "timezone_required"),
            (_stabil_path(as_of="not-a-time"), 422, "invalid_as_of"),
            ("/v1/symbols/ASTOR/stabil?tf=4h&tf=1d&as_of=2026-10-16T18%3A30%3A00%2B03%3A00", 422, "duplicate_query"),
        ]
        for path, expected_status, expected_code in cases:
            status, _, raw = _request(base, path, api_key=_API_KEY)
            payload = json.loads(raw.decode("utf-8"))
            assert status == expected_status
            assert payload["error"]["code"] == expected_code
    assert calls == []


def test_future_as_of_is_rejected_before_archive_access():
    calls = []

    def forbidden_loader(symbol, timeframe):
        calls.append((symbol, timeframe))
        raise AssertionError("future as_of must fail before archive access")

    def frozen_clock():
        return pd.Timestamp("2026-10-16T18:00:00+03:00").to_pydatetime()

    service = OfflineStabilApiPoc(_API_KEY, frame_loader=forbidden_loader, clock=frozen_clock)
    with _serve(service) as base:
        status, _, raw = _request(base, _stabil_path(), api_key=_API_KEY)

    payload = json.loads(raw.decode("utf-8"))
    assert status == 422
    assert payload["error"]["code"] == "future_as_of"
    assert calls == []


def test_archive_unavailable_returns_sanitized_503():
    def missing_archive(symbol, timeframe):
        raise FileNotFoundError("/private/path/ASTOR.csv.gz")

    service = OfflineStabilApiPoc(_API_KEY, frame_loader=missing_archive)
    with _serve(service) as base:
        status, _, raw = _request(base, _stabil_path(), api_key=_API_KEY)

    payload = json.loads(raw.decode("utf-8"))
    assert status == 503
    assert payload["error"]["code"] == "archive_unavailable"
    assert "/private/path" not in raw.decode("utf-8")


def test_as_of_cutoff_ignores_poisoned_future_archive_rows():
    cutoff = pd.Timestamp(_PARTIAL_AS_OF)
    mutated_rows = {}

    def ordinary_loader(symbol, timeframe):
        return tf_frame(symbol, timeframe)

    def future_poisoned_loader(symbol, timeframe):
        frame = tf_frame(symbol, timeframe)
        local_index = frame.index.tz_convert(ISTANBUL_TZ)
        close_times = pd.DatetimeIndex(mum_kapanis_anlari(local_index, timeframe))
        future_mask = close_times > cutoff
        mutated_rows[timeframe] = int(future_mask.sum())
        if timeframe == "4h":
            # This bar's label is at the cutoff but its close is 30 minutes later.
            # It must not leak merely because its timestamp label is <= as_of.
            mutated_rows["4h_straddling_cutoff"] = int(((local_index <= cutoff) & future_mask).sum())
        if future_mask.any():
            frame.loc[future_mask, ["open", "high", "low", "close", "volume"]] = [
                10_000.0, 10_001.0, 9_999.0, 10_000.5, 1_000_000_000.0,
            ]
        return frame

    def clock():
        return pd.Timestamp("2026-11-03T12:00:00+03:00").to_pydatetime()
    baseline_service = OfflineStabilApiPoc(_API_KEY, frame_loader=ordinary_loader, clock=clock)
    poisoned_service = OfflineStabilApiPoc(_API_KEY, frame_loader=future_poisoned_loader, clock=clock)

    with _serve(baseline_service) as base:
        status, _, raw = _request(base, _stabil_path(as_of=_PARTIAL_AS_OF), api_key=_API_KEY)
    baseline = json.loads(raw.decode("utf-8"))
    assert status == 200

    with _serve(poisoned_service) as base:
        status, _, raw = _request(base, _stabil_path(as_of=_PARTIAL_AS_OF), api_key=_API_KEY)
    poisoned = json.loads(raw.decode("utf-8"))
    assert status == 200

    assert set(mutated_rows) == {"1d", "4h", "4h_straddling_cutoff"}
    assert all(count > 0 for count in mutated_rows.values())
    assert baseline["as_of"] == _PARTIAL_AS_OF
    assert pd.Timestamp(baseline["latest_bar_close"]) <= pd.Timestamp(baseline["as_of"])
    assert pd.Timestamp(poisoned["latest_bar_close"]) <= pd.Timestamp(poisoned["as_of"])
    for key in baseline:
        if key != "request_id":
            assert poisoned[key] == baseline[key], f"future-row mutation leaked through response field {key!r}"
