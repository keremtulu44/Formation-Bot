"""Reporting does not confuse unknown or censored events with weak arrows."""
import numpy as np
import pandas as pd

from research.stabil_arrow_report import _bools, cluster_difference, groups


def test_reporting_preserves_known_unknown_and_counts_actual_bools():
    frame = pd.DataFrame({
        "symbol": ["A", "A", "B", "C"],
        "volume_bucket": ["LOW_LT_0.8", "LOW_LT_0.8", "UNKNOWN", "HIGH_GE_1.2"],
        "weak_mfe_8": [True, False, "False", "True"],
        "return_atr_8": [1.0, -1.0, 0.5, -2.0],
        "first_1atr_8": ["UP_FIRST", "DOWN_FIRST", "NEITHER", "AMBIGUOUS_SAME_BAR"],
    })
    result = {row["grup"]: row for row in groups(frame, ["volume_bucket"])}
    assert result["LOW_LT_0.8"]["n"] == 2
    assert result["LOW_LT_0.8"]["hisse"] == 1
    assert result["LOW_LT_0.8"]["zayif_yuzde"] == 50
    assert result["UNKNOWN"]["zayif"] == 0
    assert result["HIGH_GE_1.2"]["ilk_asagi_yuzde"] == 0  # dual touch is not down-first
    assert _bools(pd.Series([True, False, "True", "False", np.nan])).tolist() == [True, False, True, False, False]


def test_bootstrap_requires_both_groups_and_is_deterministic():
    frame = pd.DataFrame({
        "symbol": ["A", "A", "B", "B", "C", "C"],
        "volume_bucket": ["LOW_LT_0.8", "HIGH_GE_1.2"] * 3,
        "weak_mfe_8": [True, False, True, True, False, False],
    })
    interval = cluster_difference(frame, draws=100)
    assert interval == cluster_difference(frame, draws=100)
    assert interval is not None and abs(interval[0] - 100 / 3) < 1e-9
    assert cluster_difference(frame[frame.volume_bucket == "LOW_LT_0.8"], draws=100) is None
