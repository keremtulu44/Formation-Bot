"""Read-only native domain context for a single Formation scan's DM."""

from __future__ import annotations

from collections.abc import Mapping
import math
from typing import Any

import pandas as pd

TIMEFRAMES = ("1h", "2h", "4h", "1d")
_TIMEFRAME_LABELS = {"1h": "1H", "2h": "2H", "4h": "4H", "1d": "1D"}
# Used only for exact distance ties, never as a distance override.
_TIMEFRAME_TIE_RANK = {"1h": 1, "2h": 2, "4h": 3, "1d": 4}
_FVG_TIMEFRAMES = frozenset({"2h", "4h", "1d"})
_FVG_STATES = frozenset({"ACTIVE", "FIRST_TEST", "PARTIAL_FILL", "DEEP_TEST", "FAILED_REACTION"})
_EVENT_LABELS = {"EVENT_BOS": "BOS", "EVENT_CHOCH": "CHoCH"}
_VOLUME_LABELS = {
    "VERY_LOW": "Çok düşük",
    "LOW": "Düşük",
    "NORMAL": "Normal",
    "RISING": "Yükselen",
    "HIGH": "Yüksek",
    "ABNORMAL": "Anormal",
}


def _time(value: Any) -> pd.Timestamp | None:
    try:
        stamp = pd.Timestamp(value)
        return None if pd.isna(stamp) else stamp
    except (TypeError, ValueError, OverflowError):
        return None


def _not_after(value: Any, as_of: Any) -> bool:
    stamp, bound = _time(value), _time(as_of)
    if stamp is None or bound is None:
        return False
    try:
        return bool(stamp <= bound)
    except (TypeError, ValueError):
        return False


def _current(
    results: Mapping[str, Any], expected_asofs: Mapping[str, Any], *,
    timeframe: str, domain: str, symbol: str, scan_asof: Any,
) -> tuple[Any, Any] | None:
    """Return only a successful result matching this scan's timeframe frame."""
    by_domain = results.get(timeframe)
    output = by_domain.get(domain) if isinstance(by_domain, Mapping) else None
    expected = expected_asofs.get(timeframe)
    if output is None or expected is None:
        return None
    if getattr(output, "error", None) or getattr(output, "skipped", False):
        return None
    if getattr(output, "domain", domain) != domain:
        return None
    if getattr(output, "symbol", symbol) != symbol:
        return None
    if str(getattr(output, "timeframe", timeframe)).lower() != timeframe:
        return None
    result_time = getattr(getattr(output, "result", None), "timestamp", None)
    try:
        if pd.Timestamp(result_time) != pd.Timestamp(expected):
            return None
    except (TypeError, ValueError, OverflowError):
        return None
    if not _not_after(expected, scan_asof):
        return None
    return output, expected


def _quality(output: Any) -> Any:
    value = getattr(output, "data_quality", None)
    return getattr(value, "value", value)


def _market_structure(
    results: Mapping[str, Any], expected_asofs: Mapping[str, Any], *,
    symbol: str, scan_asof: Any,
) -> str | None:
    labels: list[str] = []
    found_current_event = False
    for timeframe in TIMEFRAMES:
        current = _current(
            results, expected_asofs, timeframe=timeframe,
            domain="market_structure", symbol=symbol, scan_asof=scan_asof,
        )
        marker = "—"
        if current is not None:
            output, expected = current
            export = getattr(output, "export", None)
            events = getattr(export, "events", ()) if export is not None else ()
            eligible = []
            for event in events or ():
                kind = getattr(event, "event_type", None)
                confirmation = getattr(event, "confirmation_status", None)
                if kind not in _EVENT_LABELS or not getattr(event, "is_active", False):
                    continue
                if getattr(confirmation, "value", confirmation) != "CONFIRMED":
                    continue
                event_tf = getattr(event, "timeframe", None)
                event_symbol = getattr(event, "symbol", None)
                if event_tf is not None and str(event_tf).lower() != timeframe:
                    continue
                if event_symbol is not None and event_symbol != symbol:
                    continue
                confirmed_at = getattr(event, "confirmed_at", None)
                stamp = _time(confirmed_at)
                if stamp is None or not _not_after(confirmed_at, expected):
                    continue
                eligible.append((stamp, event))
            if eligible:
                event = max(eligible, key=lambda pair: pair[0])[1]
                try:
                    direction = int(getattr(event, "direction", 0))
                except (TypeError, ValueError, OverflowError):
                    direction = 0
                arrow = "↑" if direction > 0 else "↓" if direction < 0 else "—"
                marker = f"{_EVENT_LABELS[event.event_type]} {arrow}"
                found_current_event = True
        labels.append(f"{_TIMEFRAME_LABELS[timeframe]} {marker}")
    return " · ".join(labels) if found_current_event else None


def _volume(
    results: Mapping[str, Any], expected_asofs: Mapping[str, Any], *,
    symbol: str, timeframe: str, scan_asof: Any,
) -> str | None:
    current = _current(
        results, expected_asofs, timeframe=timeframe,
        domain="volume_participation", symbol=symbol, scan_asof=scan_asof,
    )
    if current is None:
        return None
    output, _ = current
    details = getattr(output, "details", {}) or {}
    metrics = details.get("latest_metrics") if isinstance(details, Mapping) else None
    if metrics is None or not getattr(metrics, "data_ready", False):
        return None
    export = getattr(output, "export", None)
    level = getattr(export, "volume_level", None) if export is not None else None
    level = getattr(level, "value", level)
    return _VOLUME_LABELS.get(level.upper()) if isinstance(level, str) else None


def display_price(value: Any) -> str:
    """Format a native zone/bound for a human-facing message only.

    Zone objects/results are never modified; the presentation uses two decimal
    places rather than exposing a binary-float representation. Geçersiz/eksik/
    sonlu olmayan girdiler asla geçerli fiyat gibi gösterilmez: boş metin döner
    (mesajda 'nan'/'inf' yazısı üretilmez).
    """
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return ""
    if not math.isfinite(number):
        return ""
    return f"{number:.2f}"


# İç kullanım için kısa ad korunur; davranış tek kaynaktan (display_price) gelir.
_display_price = display_price


def _zone_side(top: Any, bottom: Any, reference: float) -> tuple[str, float] | None:
    try:
        upper, lower = float(top), float(bottom)
    except (TypeError, ValueError, OverflowError):
        return None
    if not all(math.isfinite(value) for value in (upper, lower, reference)) or upper <= lower:
        return None
    if lower > reference:
        return "upper", lower - reference
    if upper < reference:
        return "lower", reference - upper
    # Price touches/overlaps the zone: it is neither above nor below.
    return None


def _nearby_zones(
    results: Mapping[str, Any], expected_asofs: Mapping[str, Any], *,
    symbol: str, scan_asof: Any, reference_price: float,
) -> list[str]:
    candidates: dict[str, list[tuple[float, str, str, Any, Any]]] = {"upper": [], "lower": []}

    def add(timeframe: str, kind: str, top: Any, bottom: Any) -> None:
        position = _zone_side(top, bottom, reference_price)
        if position is not None:
            side, distance = position
            candidates[side].append((distance, timeframe, kind, bottom, top))

    for timeframe in TIMEFRAMES:
        ob_current = _current(
            results, expected_asofs, timeframe=timeframe,
            domain="order_block", symbol=symbol, scan_asof=scan_asof,
        )
        if ob_current is not None:
            output, expected = ob_current
            details = getattr(output, "details", {}) or {}
            records = details.get("active_records", ()) if isinstance(details, Mapping) else ()
            if _quality(output) == "OK":
                for record in records or ():
                    source_time = getattr(record, "source_time", None)
                    if not getattr(record, "active", False) or source_time is None:
                        continue
                    if _not_after(source_time, expected):
                        # Native active-record bounds; no fill/cancel logic is repeated.
                        add(timeframe, "OB", record.top, record.bottom)

        if timeframe not in _FVG_TIMEFRAMES:
            continue
        fvg_current = _current(
            results, expected_asofs, timeframe=timeframe,
            domain="fvg", symbol=symbol, scan_asof=scan_asof,
        )
        if fvg_current is None:
            continue
        output, expected = fvg_current
        if _quality(output) != "OK":
            continue
        details = getattr(output, "details", {}) or {}
        export = getattr(output, "export", None)
        if not isinstance(details, Mapping) or export is None:
            continue
        for side_name, record_name in (
            ("bull_fvg", "active_bullish_fvg"),
            ("bear_fvg", "active_bearish_fvg"),
        ):
            record = details.get(record_name)
            side_export = getattr(export, side_name, None)
            if record is None or side_export is None:
                continue
            state = getattr(record, "state", None)
            state_name = getattr(state, "name", getattr(state, "value", state))
            formation_time = getattr(record, "formation_time", None)
            if state_name not in _FVG_STATES or getattr(record, "invalid", False):
                continue
            if getattr(record, "full_fill", False) or formation_time is None:
                continue
            if not _not_after(formation_time, expected):
                continue
            add(timeframe, "FVG", side_export.top, side_export.bottom)

    selected = []
    for side, arrow in (("upper", "↑"), ("lower", "↓")):
        zones = candidates[side]
        if not zones:
            continue
        _, timeframe, kind, bottom, top = min(
            zones,
            key=lambda item: (item[0], -_TIMEFRAME_TIE_RANK[item[1]]),
        )
        selected.append(
            f"{arrow} {_TIMEFRAME_LABELS[timeframe]} {kind} · "
            f"{_display_price(bottom)}–{_display_price(top)}"
        )
    return selected


def build_formation_dm_context(
    domain_results_by_tf: Mapping[str, Mapping[str, Any]],
    expected_as_of_by_tf: Mapping[str, Any], *, symbol: str,
    formation_timeframe: str, reference_price: Any, scan_as_of: Any,
) -> dict[str, Any]:
    """Select current native context without cache fallback or new state."""
    if not isinstance(domain_results_by_tf, Mapping) or not isinstance(expected_as_of_by_tf, Mapping):
        return {}
    timeframe = str(formation_timeframe).lower()
    if timeframe not in TIMEFRAMES or _time(scan_as_of) is None:
        return {}
    try:
        reference = float(reference_price)
    except (TypeError, ValueError, OverflowError):
        return {}
    if not math.isfinite(reference):
        return {}

    context: dict[str, Any] = {}
    structure = _market_structure(
        domain_results_by_tf, expected_as_of_by_tf, symbol=symbol, scan_asof=scan_as_of
    )
    if structure is not None:
        context["structure"] = structure
    volume = _volume(
        domain_results_by_tf, expected_as_of_by_tf, symbol=symbol,
        timeframe=timeframe, scan_asof=scan_as_of,
    )
    if volume is not None:
        context["volume"] = volume
    zones = _nearby_zones(
        domain_results_by_tf, expected_as_of_by_tf, symbol=symbol,
        scan_asof=scan_as_of, reference_price=reference,
    )
    if zones:
        context["nearby_zones"] = zones[:2]
    return context
