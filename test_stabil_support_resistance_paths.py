"""Path branches must preserve chronology and explicit same-bar ambiguity."""
from __future__ import annotations

import numpy as np
import pytest

from research.stabil_support_resistance_paths import trace_break


def base():
    return (np.full(30, 100.5), np.full(30, 100.), [("first",)]*30, ["STEPPING_DOWN"]*30)


def test_price_returns_to_fixed_line_then_breaks_again() -> None:
    close, levels, ids, regimes = base()
    close[2] = 99.9
    result = trace_break(0, close, levels, ids, regimes)
    assert result["first_path"] == "PRICE_RETURNS_FIXED_FIRST"
    assert result["first_step"] == 2
    assert result["after_price_first"] == "PRICE_BREAKS_FIXED_AGAIN"
    assert result["after_line_first"] is None


def test_line_moves_adverse_then_flat_same_identity_then_price_crosses() -> None:
    close, levels, ids, regimes = base()
    levels[2:] = 101.
    ids[2:] = [("second",)]*28
    regimes[4:] = ["HORIZONTAL_AFTER_DROP"]*26
    close[5:] = 101.2
    result = trace_break(0, close, levels, ids, regimes)
    assert result["first_path"] == "LINE_ADVERSE_FIRST"
    assert result["line_first_price_side"] == "SAFE_TO_NEW_LINE"
    assert result["after_line_first"] == "FLAT_PROXY_FIRST"
    assert result["flat_step"] == 4
    assert result["flat_price_side"] == "SAFE_TO_NEW_LINE"
    assert result["after_flat_first"] == "PRICE_CROSSES_NEW_LINE"


def test_same_bar_price_return_and_line_move_is_ambiguous() -> None:
    close, levels, ids, regimes = base()
    close[1] = 99.8
    levels[1:] = 101.
    ids[1:] = [("second",)]*29
    assert trace_break(0, close, levels, ids, regimes)["first_path"] == "AMBIGUOUS_SAME_BAR"


def test_line_moves_then_price_returns_old_line_before_candidate_flat() -> None:
    close, levels, ids, regimes = base()
    levels[2:] = 101.
    ids[2:] = [("second",)]*28
    close[3] = 100.
    regimes[4:] = ["HORIZONTAL_AFTER_DROP"]*26
    result = trace_break(0, close, levels, ids, regimes)
    assert result["after_line_first"] == "PRICE_RETURNS_OLD_FIRST"
    assert result["after_flat_first"] is None


def test_identity_change_at_same_value_is_not_silently_fixed() -> None:
    close, levels, ids, regimes = base()
    ids[3:] = [("second",)]*27
    assert trace_break(0, close, levels, ids, regimes)["first_path"] == "IDENTITY_SAME_LEVEL_FIRST"


def test_horizon_must_be_complete_and_break_adverse() -> None:
    close, levels, ids, regimes = base()
    with pytest.raises(ValueError):
        trace_break(10, close, levels, ids, regimes)
    close[0] = 99.
    with pytest.raises(ValueError):
        trace_break(0, close, levels, ids, regimes)
