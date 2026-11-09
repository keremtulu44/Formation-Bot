"""Causal, optional Market Structure context for Stabil markers.

Windows are initial design hypotheses, not performance-validated thresholds.
No Block data are consumed. Historical records are interpreted at their event
bar; a later ledger validity/relevance must not leak backwards in time.
"""
from collections.abc import Mapping

import pandas as pd

WINDOWS = {"1h": 10, "2h": 6, "4h": 4, "1d": 2}


def field(obj, key, default=None):
    return obj.get(key, default) if isinstance(obj, Mapping) else getattr(obj, key, default)


def name(value):
    return str(getattr(value, "name", value) or "").upper()


def events_for_bars(result, bar_times):
    """Map only explicitly timestamped, confirmed external events onto source bars."""
    if result is None or field(result, "error") or field(result, "skipped", False):
        return []
    try:
        details = field(result, "details", {}) or {}
        events = field(details, "event_history", ()) or ()
    except Exception:
        # A broken optional context must not take down the chart or alert.
        return []
    def key(value):
        try:
            ts = pd.Timestamp(value)
            if pd.isna(ts):
                return None
            return ts.value
        except (ValueError, TypeError, OverflowError):
            return None
    mapping = {key(t): i for i, t in enumerate(bar_times) if key(t) is not None}
    out = []
    for e in events:
        kind = name(field(e, "event_type")).removeprefix("EVENT_")
        direction = name(field(e, "direction"))
        if (name(field(e, "scope")) != "EXTERNAL" or kind not in {"BOS", "CHOCH"}
                or name(field(e, "confirmation_status")) != "CONFIRMED"
                or direction not in {"UP", "DOWN"}):
            continue
        idx = mapping.get(key(field(e, "confirmed_at")))
        if idx is not None:
            out.append((idx, kind, direction))
    return sorted(out)


def marker_state(bar, direction, timeframe, events, as_of):
    """Return state using only events available at each decision point."""
    window = WINDOWS.get(str(timeframe).lower())
    if window is None:
        return "unknown_timeframe"
    known = [e for e in events if e[0] <= bar and bar - e[0] <= window]
    if known:
        latest_bar = max(e[0] for e in known)
        latest = [e for e in known if e[0] == latest_bar]
        # Conflicting simultaneous events are ambiguous; do not invent ordering.
        directions = {e[2] for e in latest}
        if len(directions) == 1 and direction not in directions:
            return "opposite_structure"
    for event_bar in sorted({e[0] for e in events if bar < e[0] <= min(bar + 3, as_of)}):
        bos_directions = {e[2] for e in events if e[0] == event_bar and e[1] == "BOS"}
        if bos_directions == ({"DOWN"} if direction == "UP" else {"UP"}):
            return "invalidated_by_opposite_bos"
    return "active"


def barrier_reason(close, atr, direction, barriers):
    """Return the first known same-bar barrier within 0.5 ATR, else None."""
    import math
    try:
        close, atr = float(close), float(atr)
        if not math.isfinite(close) or not math.isfinite(atr) or atr <= 0:
            return None
    except (TypeError, ValueError):
        return None
    sign = 1 if direction == "UP" else -1
    for label, value in barriers:
        try:
            distance = sign * (float(value) - close)
            if math.isfinite(distance) and 0 <= distance <= 0.5 * atr:
                return label
        except (TypeError, ValueError):
            continue
    return None
