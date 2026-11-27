"""Shared interpretation of explicit per-bar completion flags."""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd


def flag_is_true(row: Mapping[str, Any], name: str) -> bool:
    """Missing column keeps the legacy default; an explicit unknown is not true."""
    if name not in row:
        return True
    value = row[name]
    try:
        if bool(pd.isna(value)):
            return False
        if isinstance(value, str):
            # Never let the truthy string "False" mean a completed candle.
            return value.strip().lower() == "true"
        return bool(value == 1)
    except (TypeError, ValueError):
        return False


def bar_is_completed(row: Mapping[str, Any]) -> bool:
    return flag_is_true(row, "is_closed") and flag_is_true(row, "is_complete")
