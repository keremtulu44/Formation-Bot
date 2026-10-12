"""Pure DataFrame-shape adapter for the extracted domain engines.

This module does not fetch, resample, fill, deduplicate, or numerically alter
market data. It only exposes an existing timestamp index as a column, maps
string column labels to lowercase, and orders existing rows chronologically.
"""

from __future__ import annotations

import pandas as pd


def to_domain_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with a ``timestamp`` column and stable chronological order.

    Formation-Bot currently provides lowercase OHLCV columns and a
    Europe/Istanbul ``DatetimeIndex`` named ``timestamp``. The copy preserves
    every input bar and value; no timestamps or market values are synthesized.
    """
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("domain adapter requires a pandas DataFrame")

    adapted = frame.copy()
    renamed = {
        column: column.lower()
        for column in adapted.columns
        if isinstance(column, str) and column != column.lower()
    }
    if renamed:
        adapted = adapted.rename(columns=renamed)

    if adapted.columns.has_duplicates:
        raise ValueError("domain adapter found duplicate columns after lowercase mapping")

    if "timestamp" not in adapted.columns:
        if isinstance(adapted.index, pd.DatetimeIndex) or adapted.index.name == "timestamp":
            adapted.insert(0, "timestamp", adapted.index)
        else:
            raise ValueError(
                "domain adapter requires a timestamp column or a DatetimeIndex"
            )

    if adapted["timestamp"].isna().any():
        raise ValueError("domain adapter found missing timestamps; input was not changed")

    # Timestamp is now an ordinary column. Drop only the pandas index metadata
    # so an index also named ``timestamp`` cannot make sorting ambiguous.
    adapted = adapted.reset_index(drop=True)
    return adapted.sort_values("timestamp", kind="stable").reset_index(drop=True)
