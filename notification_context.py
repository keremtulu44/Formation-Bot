"""Format existing domain-engine exports for Telegram formation alerts.

This module is deliberately read-only and knows nothing about domain-engine
algorithms. It only renders the fresh exports returned by ``run_domain_engines``;
missing, skipped, errored, or empty outputs are omitted rather than guessed.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any

TIMEFRAME_ORDER = ("1h", "2h", "4h", "1d")
TIMEFRAME_LABELS = {"1h": "1s", "2h": "2s", "4h": "4s", "1d": "1g"}


def _field(value: Any, name: str, default=None):
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _token(value: Any) -> str:
    if value is None:
        return ""
    return str(getattr(value, "value", value)).strip().upper()


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if isfinite(number) else None


def _price(value: Any) -> str:
    number = _number(value)
    return f"{number:.2f}".replace(".", ",") if number is not None else ""


def _usable_export(result: Any):
    if result is None or bool(_field(result, "skipped", False)) or _field(result, "error"):
        return None
    return _field(result, "export")


def _domain(results_by_timeframe: Any, timeframe: str, name: str):
    if not isinstance(results_by_timeframe, Mapping):
        return None
    per_tf = results_by_timeframe.get(timeframe)
    if not isinstance(per_tf, Mapping):
        return None
    return per_tf.get(name)


def _direction(value: Any) -> str:
    number = _number(value)
    if number is None:
        return ""
    if number > 0:
        return "↑"
    if number < 0:
        return "↓"
    return ""


def _structure_state(scope: Any, exported_code: Any) -> str:
    state = _token(_field(scope, "state"))
    if not state:
        code = _number(exported_code)
        if code is None:
            return ""
        state = {
            2.0: "STATE_BULLISH",
            1.0: "STATE_TRANSITION_UP",
            -2.0: "STATE_BEARISH",
            -1.0: "STATE_TRANSITION_DOWN",
            0.0: "STATE_NEUTRAL",
        }.get(code, "")
    return {
        "STATE_BULLISH": "yükseliş",
        "STATE_BEARISH": "düşüş",
        "STATE_TRANSITION_UP": "yukarı geçiş",
        "STATE_TRANSITION_DOWN": "aşağı geçiş",
        "STATE_NEUTRAL": "yatay",
    }.get(state, "")


def _event_rows(export: Any) -> list[Any]:
    events = _field(export, "events", ()) or ()
    if not isinstance(events, (tuple, list)):
        events = ()
    # Older/partial exports may expose only the latest event fields.
    candidates = list(events)
    candidates.extend(
        event for event in (
            _field(export, "latest_external_event"),
            _field(export, "latest_internal_event"),
        ) if event is not None
    )
    seen: set[str] = set()
    output = []
    for event in candidates:
        uid = str(_field(event, "event_uid") or "")
        key = uid or "|".join(
            str(_field(event, field, ""))
            for field in ("scope", "event_type", "event_bar", "broken_level")
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(event)
    return output


def _format_market_structure(results_by_timeframe: Any) -> list[str]:
    lines: list[str] = []
    level_fields = (
        ("PH", "external_protected_high", "korunan"),
        ("PL", "external_protected_low", "korunan"),
        ("WH", "external_weak_high", "zayıf"),
        ("WL", "external_weak_low", "zayıf"),
    )

    for timeframe in TIMEFRAME_ORDER:
        result = _domain(results_by_timeframe, timeframe, "market_structure")
        export = _usable_export(result)
        if export is None:
            continue

        tf_label = TIMEFRAME_LABELS[timeframe]
        state_parts = []
        external_state = _structure_state(
            _field(export, "external_scope"), _field(export, "external_state")
        )
        internal_state = _structure_state(
            _field(export, "internal_scope"), _field(export, "internal_state")
        )
        if external_state:
            state_parts.append(f"dış {external_state}")
        if internal_state:
            state_parts.append(f"iç {internal_state}")
        if state_parts:
            lines.append(f"• {tf_label} yapı: " + " · ".join(state_parts))

        current_events = []
        for event in _event_rows(export):
            event_type = _token(_field(event, "event_type"))
            if event_type not in {"EVENT_BOS", "BOS", "EVENT_CHOCH", "CHOCH"}:
                continue
            validity = _token(_field(event, "validity"))
            relevance = _token(_field(event, "relevance"))
            confirmation = _token(_field(event, "confirmation_status"))
            if confirmation != "CONFIRMED":
                continue
            if validity == "FAILED" or relevance in {"SUPERSEDED", "HISTORICAL"}:
                continue
            if not bool(_field(event, "is_active", True)):
                continue
            current_events.append(event)

        # At most the latest current BOS/CHoCH from each scope keeps the alert
        # concise without hiding the active external/internal direction.
        latest_by_scope: dict[str, Any] = {}
        for event in current_events:
            scope = _token(_field(event, "scope")) or "STRUCTURE"
            prior = latest_by_scope.get(scope)
            event_bar = _number(_field(event, "event_bar"))
            prior_bar = _number(_field(prior, "event_bar")) if prior is not None else None
            if prior is None or (event_bar is not None and (prior_bar is None or event_bar >= prior_bar)):
                latest_by_scope[scope] = event
        for event in latest_by_scope.values():
            raw_type = _token(_field(event, "event_type"))
            label = "CHoCH" if "CHOCH" in raw_type else "BOS"
            direction = _direction(_field(event, "direction"))
            level = _price(_field(event, "broken_level"))
            scope = _token(_field(event, "scope"))
            scope_label = "dış" if scope == "EXTERNAL" else "iç" if scope == "INTERNAL" else ""
            status_parts = []
            if _token(_field(event, "confirmation_status")) == "CONFIRMED":
                status_parts.append("teyitli")
            if _token(_field(event, "validity")) == "VALID":
                status_parts.append("geçerli")
            if _token(_field(event, "relevance")) == "CURRENT":
                status_parts.append("güncel")
            details = [part for part in (scope_label, " ".join(status_parts)) if part]
            suffix = f" · {' · '.join(details)}" if details else ""
            level_text = f" {level}" if level else ""
            lines.append(f"  {label} {direction}{level_text}{suffix}")

        levels = []
        for label, field_name, role in level_fields:
            level = _price(_field(export, field_name))
            if level:
                levels.append(f"{label} {level} ({role}, güncel)")
        if levels:
            lines.append("  " + " · ".join(levels))

    return lines


def _zone_location(top: float, bottom: float, reference: float | None) -> tuple[str, float] | None:
    if reference is None:
        return None
    if bottom > reference:
        return "üst", bottom - reference
    if top < reference:
        return "alt", reference - top
    return "içinde", 0.0


def _format_order_blocks(results_by_timeframe: Any, reference_price: float | None) -> list[str]:
    candidates: dict[str, list[tuple[float, str]]] = {"üst": [], "alt": []}
    if reference_price is None:
        return []

    for timeframe in TIMEFRAME_ORDER:
        result = _domain(results_by_timeframe, timeframe, "order_block")
        export = _usable_export(result)
        if export is None:
            continue
        for side_key, side_label in (("bull", "boğa OB"), ("bear", "ayı OB")):
            side = _field(export, side_key)
            top = _number(_field(side, "top"))
            bottom = _number(_field(side, "bottom"))
            if top is None or bottom is None or top < bottom:
                continue
            location = _zone_location(top, bottom, reference_price)
            if location is None:
                continue
            group, distance = location
            # A zone containing the current close is neither above nor below;
            # this compact alert only allocates one slot to each requested side.
            if group not in candidates:
                continue
            fill = _number(_field(side, "fill"))
            state = _number(_field(side, "state"))
            parts = [
                f"{TIMEFRAME_LABELS[timeframe]} {side_label} "
                f"{_price(bottom)}–{_price(top)} TL"
            ]
            if state is not None and state != 0:
                parts.append("aktif")
            if fill is not None:
                parts.append(f"%{max(0, min(100, round(fill * 100)))} dolu")
            candidates[group].append((distance, " · ".join(parts)))

    lines = []
    for group, label in (("üst", "Üst"), ("alt", "Alt")):
        if candidates[group]:
            # Order-block exports do not expose a comparable score. The engine
            # already selects its per-TF candidate; choose the nearest exported
            # zone across timeframes without inventing a score or test count.
            _, text = min(candidates[group], key=lambda item: item[0])
            lines.append(f"• {label}: {text}")
    return lines


_FVG_STATE_LABELS = {
    2: "aday",
    3: "aktif",
    4: "ilk temas",
    5: "kısmi dolum",
    6: "derin temas",
    8: "reaksiyon",
}
_FVG_TERMINAL_STATES = {7, 9, 10, 11}


def _format_fvgs(results_by_timeframe: Any, reference_price: float | None) -> list[str]:
    candidates: dict[str, list[tuple[float | None, float, str]]] = {"üst": [], "alt": []}
    if reference_price is None:
        return []

    for timeframe in TIMEFRAME_ORDER:
        result = _domain(results_by_timeframe, timeframe, "fvg")
        export = _usable_export(result)
        if export is None:
            continue
        for side_key, side_label in (("bull_fvg", "boğa FVG"), ("bear_fvg", "ayı FVG")):
            side = _field(export, side_key)
            state = _number(_field(side, "state"))
            top = _number(_field(side, "top"))
            bottom = _number(_field(side, "bottom"))
            if state is None or top is None or bottom is None or top < bottom:
                continue
            state_code = abs(int(state))
            if state_code in _FVG_TERMINAL_STATES or state_code not in _FVG_STATE_LABELS:
                continue
            location = _zone_location(top, bottom, reference_price)
            if location is None:
                continue
            group, distance = location
            if group not in candidates:
                continue
            quality = _number(_field(side, "quality"))
            fill = _number(_field(side, "fill"))
            parts = [
                f"{TIMEFRAME_LABELS[timeframe]} {side_label} "
                f"{_price(bottom)}–{_price(top)} TL",
                _FVG_STATE_LABELS[state_code],
            ]
            if fill is not None:
                parts.append(f"%{max(0, min(100, round(fill * 100)))} dolu")
            # Quality is used only to choose the best exported zone; it is not
            # printed in the user-facing alert.
            candidates[group].append((quality, distance, " · ".join(parts)))

    lines = []
    for group, label in (("üst", "Üst"), ("alt", "Alt")):
        zones = candidates[group]
        if not zones:
            continue
        scored = [zone for zone in zones if zone[0] is not None]
        if scored:
            _, _, text = min(scored, key=lambda item: (-item[0], item[1]))
        else:
            _, _, text = min(zones, key=lambda item: item[1])
        lines.append(f"• {label}: {text}")
    return lines


_VOLUME_STATE_LABELS = {
    "PARTICIPATION_LOW": "katılım düşük",
    "PARTICIPATION_RISING": "katılım artıyor",
    "PARTICIPATION_ABNORMAL_VOLUME": "anormal hacim",
    "PARTICIPATION_ABNORMAL_CAPITAL": "anormal işlem değeri",
    "PARTICIPATION_ONE_BAR_SHOCK": "tek mumda olağandışı hareket",
    "PARTICIPATION_UP_CANDIDATE": "yukarı katılım adayı",
    "PARTICIPATION_DOWN_CANDIDATE": "aşağı katılım adayı",
    "PARTICIPATION_UP_CONFIRMED": "yukarı katılım teyitli",
    "PARTICIPATION_DOWN_CONFIRMED": "aşağı katılım teyitli",
    "PARTICIPATION_UP_PROTECTED": "yukarı katılım korunuyor",
    "PARTICIPATION_DOWN_PROTECTED": "aşağı katılım korunuyor",
    "PARTICIPATION_UP_WEAKENING": "yukarı katılım zayıflıyor",
    "PARTICIPATION_DOWN_WEAKENING": "aşağı katılım zayıflıyor",
    "PARTICIPATION_UP_ENDED": "yukarı katılım sona erdi",
    "PARTICIPATION_DOWN_ENDED": "aşağı katılım sona erdi",
    "PARTICIPATION_UPPER_ABSORPTION_CANDIDATE": "üst bölgede satış emilimi adayı",
    "PARTICIPATION_LOWER_ABSORPTION_CANDIDATE": "alt bölgede alış emilimi adayı",
    "PARTICIPATION_UPPER_ABSORPTION_CONFIRMED": "üst bölgede satış emilimi teyitli",
    "PARTICIPATION_LOWER_ABSORPTION_CONFIRMED": "alt bölgede alış emilimi teyitli",
    "PARTICIPATION_UPPER_ABSORPTION_INVALIDATED": "üst bölge emilim işareti geçersizleşti",
    "PARTICIPATION_LOWER_ABSORPTION_INVALIDATED": "alt bölge emilim işareti geçersizleşti",
    "PARTICIPATION_UP_BREAK_SUPPORTED": "yukarı kırılımda katılım desteği var",
    "PARTICIPATION_DOWN_BREAK_SUPPORTED": "aşağı kırılımda katılım desteği var",
    "PARTICIPATION_UP_BREAK_UNSUPPORTED": "yukarı kırılımda katılım desteği yok",
    "PARTICIPATION_DOWN_BREAK_UNSUPPORTED": "aşağı kırılımda katılım desteği yok",
    "PARTICIPATION_UP_BREAK_RECLAIMED": "yukarı kırılım seviyesi geri alındı",
    "PARTICIPATION_DOWN_BREAK_RECLAIMED": "aşağı kırılım seviyesi geri alındı",
    "PARTICIPATION_CONFLICT": "hacim/işlem değeri çelişkili",
}
_VOLUME_LEVEL_LABELS = {
    "VERY_LOW": "çok düşük",
    "LOW": "düşük",
    "NORMAL": "normal",
    "RISING": "yükselen",
    "HIGH": "yüksek",
    "ABNORMAL": "olağandışı",
}


def _format_volume(results_by_timeframe: Any) -> list[str]:
    lines = []
    for timeframe in TIMEFRAME_ORDER:
        result = _domain(results_by_timeframe, timeframe, "volume_participation")
        export = _usable_export(result)
        if export is None:
            continue
        state = _token(_field(export, "state"))
        if state in {"", "PARTICIPATION_PENDING", "PARTICIPATION_VOLUME_UNAVAILABLE", "PARTICIPATION_NEUTRAL"}:
            state = ""
        findings = []
        if state:
            label = _VOLUME_STATE_LABELS.get(state)
            if label:
                findings.append(label)

        rvol = _number(_field(export, "rvol"))
        if rvol is not None and rvol > 0:
            findings.append(f"Son mum hacmi / 20 mumluk ortalama: {rvol:.2f}× (RVOL)".replace(".", ",", 1))
        relative_value = _number(_field(export, "relative_traded_value"))
        if relative_value is not None and relative_value > 0:
            findings.append(f"göreli işlem değeri {relative_value:.2f}×".replace(".", ",", 1))

        volume_level = _token(_field(export, "volume_level"))
        volume_label = _VOLUME_LEVEL_LABELS.get(volume_level)
        if volume_label and volume_level not in {"NORMAL"}:
            findings.append(f"hacim {volume_label}")
        capital_level = _token(_field(export, "capital_level"))
        capital_label = _VOLUME_LEVEL_LABELS.get(capital_level)
        if capital_label and capital_level not in {"NORMAL"}:
            findings.append(f"işlem değeri {capital_label}")

        absorption_stage = _token(_field(export, "absorption_stage"))
        absorption_side = _token(_field(export, "absorption_side"))
        if absorption_stage == "CONFIRMED" and absorption_side in {"UPPER", "LOWER"}:
            side_label = "üstte satış" if absorption_side == "UPPER" else "altta alış"
            level = _price(_field(export, "absorption_reference_level"))
            findings.append(f"{side_label} emilimi teyitli" + (f" {level}" if level else ""))

        break_stage = _token(_field(export, "break_stage"))
        break_direction = _direction(_field(export, "break_direction"))
        break_labels = {
            "SUPPORTED": "katılım desteği var",
            "PROTECTED": "katılım desteği korunuyor",
            "UNSUPPORTED": "katılım desteği yok",
            "RECLAIMED": "kırılım seviyesi geri alındı",
        }
        if break_stage in break_labels:
            break_text = break_labels[break_stage]
            if break_direction:
                break_text = f"{break_direction} yönde {break_text}"
            break_level = _price(_field(export, "break_level"))
            findings.append(break_text + (f" ({break_level} TL)" if break_level else ""))

        if findings:
            lines.append(f"• {TIMEFRAME_LABELS[timeframe]}: " + " · ".join(findings))
    return lines


def _market_structure_failed(results_by_timeframe: Any) -> bool:
    if not isinstance(results_by_timeframe, Mapping):
        return False
    for timeframe in TIMEFRAME_ORDER:
        result = _domain(results_by_timeframe, timeframe, "market_structure")
        if result is not None and not bool(_field(result, "skipped", False)) and _field(result, "error"):
            return True
    return False


def format_domain_context(results_by_timeframe: Any, reference_price: Any = None) -> str:
    """Render concise, read-only context from fresh domain-engine exports.

    Candidate scores are selection-only. Missing/skipped results are omitted;
    a real Market Structure execution error is explicitly identified instead of
    being made to look like a successful analysis with no findings.
    """
    reference = _number(reference_price)
    market_lines = _format_market_structure(results_by_timeframe)
    if _market_structure_failed(results_by_timeframe):
        failure = "⚠️ Piyasa yapısı analizi tamamlanamadı"
        if market_lines:
            market_lines.append(failure)
        else:
            market_lines = [failure]

    sections = []
    for heading, lines in (
        ("🏗 Piyasa Yapısı", market_lines),
        ("🧱 Order Block (OB)", _format_order_blocks(results_by_timeframe, reference)),
        ("🟪 Fair Value Gap (FVG)", _format_fvgs(results_by_timeframe, reference)),
        ("📊 Hacim / Katılım", _format_volume(results_by_timeframe)),
    ):
        if lines:
            sections.append(heading + "\n" + "\n".join(lines))
    return "\n\n".join(sections)
