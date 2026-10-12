"""Pivot-side regression tests for directional same-type extremes."""

from patterns.pivots import PivotSide


def test_high_same_type_extreme_updates_unlocked_pivot_and_rejects_weaker():
    side = PivotSide()

    assert side.add(100.0, 10, 15, False, is_high=True) == (True, True)
    assert side.add(103.0, 20, 25, True, is_high=True) == (True, False)
    assert side.add(95.0, 30, 35, True, is_high=True) == (False, False)

    assert side.prices == [103.0]
    assert side.bars == [20]
    assert side.confirm_bars == [25]
    assert side.locked == [False]


def test_high_same_type_extreme_appends_only_when_locked():
    side = PivotSide()
    assert side.add(100.0, 10, 15, False, is_high=True) == (True, True)
    side.locked[-1] = True

    assert side.add(103.0, 20, 25, True, is_high=True) == (True, True)
    assert side.add(95.0, 30, 35, True, is_high=True) == (False, False)

    assert side.prices == [100.0, 103.0]
    assert side.bars == [10, 20]
    assert side.confirm_bars == [15, 25]
    assert side.locked == [True, False]


def test_low_same_type_extreme_updates_unlocked_pivot_and_rejects_weaker():
    side = PivotSide()

    assert side.add(100.0, 10, 15, False, is_high=False) == (True, True)
    assert side.add(95.0, 20, 25, True, is_high=False) == (True, False)
    assert side.add(103.0, 30, 35, True, is_high=False) == (False, False)

    assert side.prices == [95.0]
    assert side.bars == [20]
    assert side.confirm_bars == [25]
    assert side.locked == [False]


def test_low_same_type_extreme_appends_only_when_locked():
    side = PivotSide()
    assert side.add(100.0, 10, 15, False, is_high=False) == (True, True)
    side.locked[-1] = True

    assert side.add(95.0, 20, 25, True, is_high=False) == (True, True)
    assert side.add(103.0, 30, 35, True, is_high=False) == (False, False)

    assert side.prices == [100.0, 95.0]
    assert side.bars == [10, 20]
    assert side.confirm_bars == [15, 25]
    assert side.locked == [True, False]
