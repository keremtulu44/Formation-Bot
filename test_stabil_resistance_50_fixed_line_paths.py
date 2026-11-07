"""Fixed-line paths are directional mirrors and do not invent extra waits."""
import numpy as np

from research.stabil_resistance_50_fixed_line_paths import trace_fixed


def test_reclaim_then_rebreak_matches_support_resistance_mirror():
    support = np.array([9.5, 10.1, 9.9, 9.8])
    lines = np.full(4, 10.0)
    ids = [("level",)]*4
    result = trace_fixed("SUPPORT", 0, 3, support, lines, ids)
    mirror = trace_fixed("RESISTANCE", 0, 3, 20-support, lines, ids)
    assert result == mirror
    assert result["price_side_at_step"] == "ADVERSE"
    assert result["first"] == "PRICE_CROSSES_FIRST"
    assert result["first_step"] == 1
    assert result["after_safe_return"] == "PRICE_CROSSES_FIRST"


def test_same_bar_line_change_and_price_cross_are_ambiguous():
    values = np.array([10.5, 9.9, 9.8])
    levels = np.array([10., 11., 11.])
    ids = [("old",), ("new",), ("new",)]
    out = trace_fixed("RESISTANCE", 0, 2, values, levels, ids)
    assert out["first"] == "AMBIGUOUS_SAME_BAR"


def test_no_remaining_bar_is_not_counted_as_neither():
    values = np.array([10.5])
    levels = np.array([10.0])
    out = trace_fixed("RESISTANCE", 0, 0, values, levels, [("level",)])
    assert out["first"] == "NO_REMAINING"
    assert out["remaining_at_step"] == 0


def test_equal_is_safe_but_not_a_strict_cross():
    prices = np.array([10.5, 10.0, 10.2])
    out = trace_fixed("RESISTANCE", 0, 2, prices, np.full(3, 10.0), [("level",)]*3)
    assert out["first"] == "PRICE_CROSSES_FIRST"
    assert out["first_cross_position"] == "EQUAL"
    assert out["strict_safe_first"] == "NEITHER"
    assert out["after_safe_return"] == "PRICE_CROSSES_FIRST"
