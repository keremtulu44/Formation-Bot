"""Closed-bar event evidence for domain alarms; no trend or return prediction."""
from collections.abc import Mapping
import math

import pandas as pd


def _get(obj, key, default=None):
    return obj.get(key, default) if isinstance(obj, Mapping) else getattr(obj, key, default)


def _number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError, OverflowError):
        return None


def ob_reaction_reasons(context, frame):
    """Touch a known remaining zone, close back outside, zone still valid.

    Uses the pre-bar export; the post-touch remaining band has already shrunk
    toward the wick and cannot identify the rejection. Missing/misaligned
    evidence is unknown, never an invented OB reaction. Other channels remain
    independent. Native invalidation/removal always wins.
    """
    if context is None or frame is None or len(frame) < 2:
        return []
    try:
        if (pd.Timestamp(_get(context, "bar_time")) != pd.Timestamp(frame.index[-1])
                or pd.Timestamp(_get(context, "previous_bar_time")) != pd.Timestamp(frame.index[-2])):
            return []
        row = frame.iloc[-1]
        o, high, low, close = (_number(row[k]) for k in ("open", "high", "low", "close"))
        if (any(v is None for v in (o, high, low, close)) or low <= 0
                or low > min(o, close) or high < max(o, close)):
            return []
        survivors = set(tuple(v) for v in (_get(context, "surviving_sources", ()) or ()))
    except (TypeError, ValueError, KeyError, IndexError, OverflowError):
        return []
    previous = _get(context, "previous_export")
    reasons = []
    for side, sign in (("bull", 1), ("bear", -1)):
        zone = _get(previous, side)
        source = _number(_get(zone, "source_bar"))
        top, bottom = _number(_get(zone, "top")), _number(_get(zone, "bottom"))
        if (source is None or not source.is_integer() or source < 0 or source >= len(frame) - 1
                or (int(source), sign) not in survivors or top is None or bottom is None
                or bottom <= 0 or top < bottom):
            continue
        touched = low <= top and high >= bottom
        held = close > top if sign == 1 else close < bottom
        if touched and held:
            reasons.append(f"OB {'boğa' if sign == 1 else 'ayı'} bölge tepkisi")
    return sorted(reasons)
