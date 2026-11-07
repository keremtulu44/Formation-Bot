"""Focused resistance report respects frozen levels and causal price side."""
import numpy as np
import pandas as pd
import pytest

from research.stabil_resistance_50_model_report import f01_groups, frozen_line_breached


def test_fixed_level_break_is_symmetric_and_equal_close_is_safe():
    assert not frozen_line_breached("SUPPORT", 100., np.full(8, 100.))
    assert not frozen_line_breached("RESISTANCE", 100., np.full(8, 100.))
    support = np.array([101., 100., 102., 100., 99., 100., 103., 104.])
    resistance = 200-support
    assert frozen_line_breached("SUPPORT", 100., support)
    assert frozen_line_breached("RESISTANCE", 100., resistance)
    with pytest.raises(ValueError):
        frozen_line_breached("SUPPORT", 100., np.ones(7))
    with pytest.raises(ValueError):
        frozen_line_breached("BAD_SIDE", 100., np.ones(8))
    with pytest.raises(ValueError):
        frozen_line_breached("SUPPORT", np.nan, np.ones(8))


def test_f01_price_side_and_ambiguous_denominators():
    base = {"question": "F01", "period": "Y2026", "side": "RESISTANCE", "bucket": "ADVERSE_STEP_PROXY"}
    frame = pd.DataFrame([
        {**base, "symbol": "A", "distance_safe_daily_atr": .5, "status_8": "VALID", "first_1atr_8": "REACTION_FIRST"},
        {**base, "symbol": "B", "distance_safe_daily_atr": 0., "status_8": "VALID", "first_1atr_8": "AMBIGUOUS_SAME_BAR"},
        {**base, "symbol": "A", "distance_safe_daily_atr": -.3, "status_8": "VALID", "first_1atr_8": "BREACH_SIDE_FIRST"},
        {**base, "symbol": "A", "distance_safe_daily_atr": -.5, "status_8": "RIGHT_CENSORED", "first_1atr_8": None},
    ])
    groups = {r["price_side"]: r for r in f01_groups(frame)}
    assert groups["SAFE"]["valid"] == 2 and groups["SAFE"]["symbols"] == 2
    assert groups["SAFE"]["reaction_pct"] == 50 and groups["SAFE"]["ambiguous_pct"] == 50
    assert groups["ADVERSE"]["events"] == 2 and groups["ADVERSE"]["valid"] == 1
    assert groups["ADVERSE"]["adverse_pct"] == 100


def test_post_touch_outcomes_are_conditioned_on_same_candle_close():
    from research.stabil_resistance_50_model_report import post_touch_close_groups

    frame = pd.DataFrame([
        {"period": "Y2026", "event": "TEST", "status_8": "VALID", "symbol": "AAA", "side": "RESISTANCE",
         "contact": "TOUCH_CLOSE_SAFE", "first_1atr_8": "REACTION_FIRST"},
        {"period": "Y2026", "event": "TEST", "status_8": "VALID", "symbol": "BBB", "side": "RESISTANCE",
         "contact": "TOUCH_CLOSE_BREACHED", "first_1atr_8": "BREACH_SIDE_FIRST"},
        {"period": "Y2026", "event": "TEST", "status_8": "RIGHT_CENSORED", "symbol": "CCC", "side": "RESISTANCE",
         "contact": "TOUCH_CLOSE_SAFE", "first_1atr_8": None},
    ])
    groups = post_touch_close_groups(frame)
    safe = next(x for x in groups if x["side"] == "RESISTANCE" and x["contact"] == "TOUCH_CLOSE_SAFE")
    assert safe["n"] == 1
    assert safe["counts"]["REACTION_FIRST"] == 1
    assert safe["counts"]["BREACH_SIDE_FIRST"] == 0
