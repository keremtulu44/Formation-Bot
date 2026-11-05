"""Contracts for the read-only alarm/request context packet prototype."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
from typing import Any

import numpy as np
import pandas as pd
import pytest

from alarm_context_packet import DOMAIN_ORDER, build_context_packet, packet_json, to_jsonable


@dataclass
class FakeDomainResult:
    domain: str
    symbol: str = "ASTOR"
    timeframe: str = "4h"
    result: Any = None
    export: Any = None
    data_quality: Any = "OK"
    details: dict[str, Any] = field(default_factory=dict)
    skipped: bool = False
    reason: str | None = None
    error: str | None = None


class SampleEnum(Enum):
    READY = "ready"


def _packet(*, results=None, **overrides):
    args = {
        "symbol": "ASTOR",
        "timeframe": "4h",
        "as_of": pd.Timestamp("2026-10-16T13:30:00+03:00"),
        "domain_results": results or {},
        "context_kind": "historical_sample",
        "generated_at": pd.Timestamp("2026-11-04T10:00:00+03:00"),
        "reference_price": 183.2,
        "price_time": pd.Timestamp("2026-10-16T13:30:00+03:00"),
    }
    args.update(overrides)
    return build_context_packet(**args)


def test_strict_json_retains_complete_domain_fields_and_pandas_structure():
    result = FakeDomainResult(
        domain="market_structure",
        result={"all_events": [{"event": "BOS", "level": np.float64(123.4)}]},
        export={"status": SampleEnum.READY, "last_event_at": "2026-10-16T12:30:00+03:00"},
        details={
            "full_history": [1, 2, {"kept": True}],
            "non_finite": [np.nan, np.inf, -np.inf],
            "array": np.array([[1, 2], [3, 4]], dtype=np.int16),
            "frame": pd.DataFrame(
                {"close": [10.5, 11.0], "tag": ["a", "b"]},
                index=pd.Index(["2026-10-16T09:30:00+03:00", "2026-10-16T13:30:00+03:00"], name="bar"),
            ),
            "series": pd.Series([7, 8], index=pd.Index(["x", "y"], name="key"), name="count"),
        },
    )

    packet = _packet(results={"market_structure": result})
    encoded = packet_json(packet)
    decoded = json.loads(encoded)
    assert decoded["schema_version"] == "1.1"
    native = decoded["domain_outputs"]["market_structure"]["native"]

    assert set(native) == {
        "domain", "symbol", "timeframe", "result", "export", "data_quality",
        "details", "skipped", "reason", "error",
    }
    assert native["result"]["all_events"][0]["level"] == pytest.approx(123.4)
    assert native["export"]["status"] == "ready"
    assert native["details"]["full_history"] == [1, 2, {"kept": True}]
    assert native["details"]["non_finite"] == [None, None, None]
    assert native["details"]["array"]["shape"] == [2, 2]
    assert native["details"]["array"]["dtype"] == "int16"
    frame = native["details"]["frame"]
    assert frame["__type__"] == "pandas.DataFrame"
    assert frame["index"]["values"] == [
        "2026-10-16T09:30:00+03:00", "2026-10-16T13:30:00+03:00"
    ]
    assert frame["columns"]["values"] == ["close", "tag"]
    assert frame["column_dtypes"] == ["float64", "object"]
    assert frame["data"] == [[10.5, "a"], [11.0, "b"]]
    series = native["details"]["series"]
    assert series["__type__"] == "pandas.Series"
    assert series["name"] == "count"
    assert series["index"]["values"] == ["x", "y"]

    # Strict RFC JSON output contains no NaN/Infinity literals.
    assert "NaN" not in encoded
    assert "Infinity" not in encoded


def test_all_domains_report_missing_skipped_error_and_available_states():
    available = FakeDomainResult(
        domain="market_structure",
        result={"full_result": {"nested": [1, 2, 3]}},
        export={"external_scope": None, "internal_scope": None},
        details={"unabridged": True},
    )
    skipped = FakeDomainResult(
        domain="volume_participation", skipped=True, reason="unsupported on this call"
    )
    errored = FakeDomainResult(domain="order_block", error="fixture engine error")

    packet = _packet(results={
        "market_structure": available,
        "volume_participation": skipped,
        "order_block": errored,
    })
    outputs = packet["domain_outputs"]

    assert tuple(outputs) == DOMAIN_ORDER
    assert outputs["market_structure"]["status"] == "available"
    assert outputs["market_structure"]["native"]["details"]["unabridged"] is True
    assert outputs["volume_participation"]["status"] == "skipped"
    assert outputs["volume_participation"]["reason"] == "unsupported on this call"
    assert outputs["order_block"]["status"] == "error"
    assert outputs["order_block"]["error"] == "fixture engine error"
    assert outputs["fvg"]["status"] == "not_returned"
    assert outputs["stabil"]["status"] == "not_returned"
    assert "## FVG · TF yok" in packet["readable_text"]
    assert "Durum: skipped" in packet["readable_text"]
    assert "Durum: error" in packet["readable_text"]
    assert "not_returned" in packet["readable_text"]


def test_curated_findings_are_domain_scoped_sourced_and_timeline_labeled():
    packet = _packet()
    evidence = packet["replay_evidence"]

    ms = evidence["market_structure"]
    assert [item["finding_id"] for item in ms] == ["ms-4h-external-bos-replay-2026-10-21"]
    assert ms[0]["scope"]["n"] == 3387
    assert ms[0]["timeline"]["data_through"] == "2026-10-19"
    assert ms[0]["timeline"]["available_at_snapshot"] is False

    # The shared OB/FVG reaction result is deliberately attached to both, while
    # family-specific lifecycle results remain scoped to their own domain.
    ob_ids = {item["finding_id"] for item in evidence["order_block"]}
    fvg_ids = {item["finding_id"] for item in evidence["fvg"]}
    assert "zone-touch-response-replay-2026-10-21" in ob_ids & fvg_ids
    assert "ob-lifecycle-replay-2026-10-21" in ob_ids
    assert "fvg-lifecycle-replay-2026-10-21" in fvg_ids
    assert "ob-lifecycle-replay-2026-10-21" not in fvg_ids

    all_findings = [item for group in evidence.values() for item in group]
    for finding in all_findings:
        assert finding["scope"]
        assert finding["sample"]
        assert finding["method"]
        assert finding["sources"]
        assert finding["limitations"]
        assert finding["timeline"]["snapshot_as_of"] == "2026-10-16T13:30:00+03:00"

    assert evidence["formation_alert"][0]["metrics"]["FRM_19_zone_at_breakout"]["zone_present"]["n"] == 11905
    text = packet["readable_text"]
    assert "SONRAKİ ARAŞTIRMA; tarihsel kesitte bilinmiyordu" in text
    assert "n=6.740" in text and "n=11.928" in text
    assert "n=17.103" in text and "n=14.857" in text
    assert "run_id=replay-2026-10-21" in text
    assert "işlem tavsiyesi üretmez" in text


def test_symbol_specific_supplemental_replay_is_separate_and_timeline_labeled():
    finding = {
        "finding_id": "symbol-4h-breakout-replay-2026-10-30",
        "symbol": "ASTOR",
        "recorded_at": "2026-10-30",
        "data_through": "2026-10-19",
        "domains": ["formation_alert"],
        "title": "ASTOR 4h formasyon/kırılım replay özeti",
        "summary": "n=21 aday; medyan yönlü kapanış değişimi -1,232 ATR.",
        "scope": {
            "run_id": "breakout-confirm-replay-2026-10-30",
            "symbol": "ASTOR",
            "symbols": 174,
            "series": 696,
            "timeframe": "4h",
            "unit": "aday olayı",
            "n": 21,
            "valid_nonoverlap_n": 16,
        },
        "sample": "ASTOR 4h n=21 aday; VALID ve nonoverlap=true alt-kümesi n=16.",
        "metrics": {"median_end_atr": -1.232},
        "replay_events": [{"anchor": "2026-10-16T13:30:00+03:00", "end_atr": -1.232}],
        "method": "Replay aday dosyasındaki geçerli, örtüşmeyen 4h olaylar özetlendi.",
        "limitations": ["Sonuç 2026-10-16 kesitinden sonra yayımlandı; canlı olasılık değildir."],
        "sources": ["docs/arastirma/sonuclar/kirilim_replay/adaylar.csv.gz"],
    }
    packet = _packet(supplemental_replay_findings=[finding])
    replay = packet["replay_evidence"]["symbol_specific"]

    assert len(replay) == 1
    assert replay[0]["symbol"] == "ASTOR"
    assert replay[0]["scope"]["valid_nonoverlap_n"] == 16
    assert replay[0]["replay_events"] == [
        {"anchor": "2026-10-16T13:30:00+03:00", "end_atr": -1.232}
    ]
    assert replay[0]["timeline"]["relation"] == "later_than_snapshot"
    assert replay[0]["timeline"]["available_at_snapshot"] is False
    assert "Sembole özgü replay incelemesi" in packet["readable_text"]
    assert "SONRAKİ ARAŞTIRMA; tarihsel kesitte bilinmiyordu" in packet["readable_text"]
    assert json.loads(packet_json(packet))["replay_evidence"]["symbol_specific"][0]["metrics"]["median_end_atr"] == -1.232


def test_symbol_specific_replay_rejects_incomplete_or_cross_symbol_evidence():
    base = {
        "finding_id": "symbol-test",
        "symbol": "OTHER",
        "recorded_at": "2026-10-30",
        "data_through": "2026-10-19",
        "domains": ["formation_alert"],
        "title": "test",
        "summary": "test",
        "scope": {"run_id": "test-run", "symbol": "OTHER"},
        "sample": "n=1",
        "metrics": {"n": 1},
        "method": "test method",
        "limitations": ["test caveat"],
        "sources": ["test-source"],
    }
    with pytest.raises(ValueError, match="symbol does not match"):
        _packet(supplemental_replay_findings=[base])

    missing_scope_id = {**base, "symbol": "ASTOR", "scope": {"symbol": "ASTOR"}}
    with pytest.raises(ValueError, match="scope.run_id"):
        _packet(supplemental_replay_findings=[missing_scope_id])


def test_replay_timing_is_conservative_when_run_or_data_cutoff_is_unknown():
    packet = _packet(as_of=pd.Timestamp("2026-11-04T10:00:00+03:00"))
    by_id = {
        item["finding_id"]: item
        for group in packet["replay_evidence"].values()
        for item in group
    }
    assert by_id["zone-touch-response-replay-2026-10-21"]["timeline"]["available_at_snapshot"] is True
    assert by_id["volume-zone-and-ms-context-2026-10"]["timeline"]["available_at_snapshot"] is None
    assert by_id["stabil-contact-behavior-2026-11-01"]["timeline"]["relation"] == "data_cutoff_unknown"
    assert by_id["formation-zone-context-2026-10"]["timeline"]["relation"] == "report_date_unknown"


def test_future_snapshot_trigger_price_and_native_timestamps_are_rejected():
    cutoff = pd.Timestamp("2026-10-16T13:30:00+03:00")
    with pytest.raises(ValueError, match="trigger.triggered_at is later"):
        _packet(trigger={
            "symbol": "ASTOR", "timeframe": "4h",
            "triggered_at": "2026-10-16T13:30:01+03:00",
        })

    with pytest.raises(ValueError, match="price_time is later"):
        _packet(price_time=pd.Timestamp("2026-10-16T13:30:01+03:00"))

    with pytest.raises(ValueError, match="domain_outputs.market_structure.native.*later than"):
        _packet(results={
            "market_structure": FakeDomainResult(
                domain="market_structure",
                details={"future_event_time": "2026-10-16T13:31:00+03:00"},
            )
        })

    # A cutoff and timestamp that are equal are valid; future replay evidence is
    # retained separately and explicitly marked in its timeline metadata.
    packet = _packet(as_of=cutoff, price_time=cutoff)
    assert packet["snapshot"]["price_time"] == cutoff.isoformat()
    assert all(
        item["timeline"]["available_at_snapshot"] is False
        for item in packet["replay_evidence"]["market_structure"]
    )


def test_alarm_context_requires_original_trigger_timestamp():
    with pytest.raises(ValueError, match="alarm context requires the original trigger"):
        _packet(context_kind="alarm", trigger=None)
    with pytest.raises(ValueError, match="alarm trigger must include timezone-aware triggered_at"):
        _packet(context_kind="alarm", trigger={"symbol": "ASTOR", "timeframe": "4h"})

    packet = _packet(
        context_kind="alarm",
        trigger={
            "symbol": "ASTOR",
            "timeframe": "4h",
            "triggered_at": "2026-10-16T13:30:00+03:00",
        },
    )
    assert packet["trigger"]["triggered_at"] == "2026-10-16T13:30:00+03:00"


def test_closed_bar_count_is_optional_but_must_be_nonnegative_integer():
    packet = _packet(closed_bar_count=np.int64(1075))
    assert packet["snapshot"]["closed_bar_count"] == 1075
    assert "Tamamlanmış mum sayısı: 1075" in packet["readable_text"]
    assert json.loads(packet_json(packet))["snapshot"]["closed_bar_count"] == 1075

    with pytest.raises(ValueError, match="closed_bar_count must be a non-negative integer"):
        _packet(closed_bar_count=-1)
    with pytest.raises(TypeError, match="closed_bar_count must be a non-negative integer"):
        _packet(closed_bar_count=1075.0)


def test_naive_times_and_unknown_domains_are_rejected():
    with pytest.raises(ValueError, match="as_of must be timezone-aware"):
        _packet(as_of=pd.Timestamp("2026-10-16 13:30:00"))
    with pytest.raises(ValueError, match="price_time must be timezone-aware"):
        _packet(price_time=pd.Timestamp("2026-10-16 13:30:00"))
    with pytest.raises(ValueError, match="unknown domain result"):
        _packet(results={"made_up_domain": {}})


def test_to_jsonable_preserves_non_string_mapping_keys_without_collisions():
    converted = to_jsonable({1: "integer", "1": "string"})
    assert converted == {
        "__type__": "mapping",
        "items": [
            {"key": 1, "value": "integer"},
            {"key": "1", "value": "string"},
        ],
    }
