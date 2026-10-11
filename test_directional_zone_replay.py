from types import SimpleNamespace

import pandas as pd

from directional_zone_replay import (
    FAVORABLE_ATR_THRESHOLDS,
    HORIZONS,
    build_touch_episodes,
    build_window_rows,
    classify_arrival,
    classify_fvg_terminal,
    classify_ob_removal,
    directional_excursions,
)


def _frame(count, *, highs=None, lows=None):
    highs = highs or [111.0] * count
    lows = lows or [99.0] * count
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01 09:30", periods=count, freq="h", tz="Europe/Istanbul"),
        "open": [105.0] * count,
        "high": highs,
        "low": lows,
        "close": [105.0] * count,
        "volume": [1.0] * count,
    })


def _zone(*, terminal_index=None):
    return {
        "zone_id": "TEST|OB|1h|bullish|1|100|110",
        "symbol": "TEST",
        "family": "OB",
        "timeframe": "1h",
        "direction": "bullish",
        "expected_reaction_direction": "UP",
        "origin_index": 1,
        "origin_time": None,
        "available_index": 1,
        "available_at": None,
        "zone_lower": 100.0,
        "zone_upper": 110.0,
        "native_status_at_asof": "ACTIVE_OB",
        "native_terminal_index": terminal_index,
        "native_terminal_at": None,
        "native_terminal_state": None,
        "native_terminal_reason": None,
        "native_terminal_category": "ACTIVE_AT_ASOF",
        "native_price_violation": False,
        "native_full_fill": False,
        "native_fill_ratio_at_terminal_or_asof": 0.0,
        "current_remaining_lower": 100.0,
        "current_remaining_upper": 110.0,
        "contact_bars": [
            {"index": 2, "remaining_lower": 100.0, "remaining_upper": 110.0, "fill_ratio_before_bar": 0.0},
            {"index": 3, "remaining_lower": 100.0, "remaining_upper": 110.0, "fill_ratio_before_bar": 0.0},
            {"index": 5, "remaining_lower": 100.0, "remaining_upper": 110.0, "fill_ratio_before_bar": 0.0},
        ],
        "touch_bars": [
            {"index": 2, "remaining_lower": 100.0, "remaining_upper": 110.0, "fill_ratio_before_bar": 0.0},
            {"index": 3, "remaining_lower": 100.0, "remaining_upper": 110.0, "fill_ratio_before_bar": 0.0},
            {"index": 5, "remaining_lower": 100.0, "remaining_upper": 110.0, "fill_ratio_before_bar": 0.0},
        ],
        "active_at_asof": True,
    }


def test_directional_favorable_and_adverse_excursions_are_oriented_by_zone():
    future = [{"high": 115.0, "low": 96.0}]
    bullish = directional_excursions("bullish", 100.0, 110.0, future, 2.0)
    bearish = directional_excursions("bearish", 100.0, 110.0, future, 2.0)
    assert bullish == {
        "favorable_price": 5.0,
        "adverse_price": 4.0,
        "favorable_atr": 2.5,
        "adverse_atr": 2.0,
    }
    assert bearish == {
        "favorable_price": 4.0,
        "adverse_price": 5.0,
        "favorable_atr": 2.0,
        "adverse_atr": 2.5,
    }


def test_arrival_side_is_separate_from_post_touch_reaction():
    assert classify_arrival(111.0, 100.0, 110.0) == ("FROM_ABOVE", "DOWN_TOWARD_ZONE")
    assert classify_arrival(99.0, 100.0, 110.0) == ("FROM_BELOW", "UP_TOWARD_ZONE")
    assert classify_arrival(105.0, 100.0, 110.0) == ("INSIDE_ZONE", "AMBIGUOUS")
    assert classify_arrival(None, 100.0, 110.0) == ("NO_PREVIOUS_BAR", "UNKNOWN")


def test_predeclared_windows_and_thresholds_are_not_outcome_selected():
    assert HORIZONS == (10, 12)
    assert FAVORABLE_ATR_THRESHOLDS == (0.5, 1.0, 1.5)


def test_touch_candles_are_excluded_and_fixed_10_12_bar_windows_are_separate():
    highs = [111.0, 111.0, 999.0] + [111.0] * 13
    lows = [99.0, 99.0, 1.0] + [109.0] * 13
    frame = _frame(16, highs=highs, lows=lows)
    zone = _zone()
    episodes = build_touch_episodes([zone], {("TEST", "1h"): frame})
    first_episode = [episode for episode in episodes if episode["touch_number_for_zone"] == 1]
    atr = tuple([2.0] * len(frame))
    rows = build_window_rows(
        first_episode,
        {zone["zone_id"]: zone},
        {("TEST", "1h"): frame},
        {("TEST", "1h"): atr},
    )
    by_horizon = {row["horizon_bars"]: row for row in rows}
    assert set(by_horizon) == {10, 12}
    assert by_horizon[10]["window_complete"] is True
    assert by_horizon[12]["window_complete"] is True
    # The huge touch-candle high/low at index 2 must not enter either response.
    assert by_horizon[10]["full_window_favorable_excursion_atr"] == 0.5
    assert by_horizon[10]["full_window_adverse_excursion_atr"] == 0.0
    assert by_horizon[10]["reaction_start"] == frame.at[4, "timestamp"]
    assert by_horizon[12]["reaction_window_end"] == frame.at[15, "timestamp"]


def test_incomplete_10_and_12_bar_horizons_are_right_censored_not_failed():
    frame = _frame(10)
    zone = _zone()
    episodes = build_touch_episodes([zone], {("TEST", "1h"): frame})
    first_episode = [episode for episode in episodes if episode["touch_number_for_zone"] == 1]
    rows = build_window_rows(
        first_episode,
        {zone["zone_id"]: zone},
        {("TEST", "1h"): frame},
        {("TEST", "1h"): tuple([2.0] * len(frame))},
    )
    assert len(rows) == 2
    assert all(row["window_status"] == "RIGHT_CENSORED_DATA_END" for row in rows)
    assert all(row["window_complete"] is False for row in rows)
    assert all(row["full_window_favorable_excursion_atr"] is None for row in rows)
    assert all(row["target_0p5_atr_hit_full_window"] is None for row in rows)


def test_repeated_contacts_are_separate_episodes_but_keep_one_zone_id():
    zone = _zone()
    frame = _frame(8)
    episodes = build_touch_episodes([zone], {("TEST", "1h"): frame})
    assert len(episodes) == 2
    assert {episode["zone_id"] for episode in episodes} == {zone["zone_id"]}
    assert [episode["touch_number_for_zone"] for episode in episodes] == [1, 2]
    assert episodes[0]["touch_bar_count"] == 2
    assert episodes[0]["_next_episode_start_index"] == 5


def test_targets_on_native_terminal_bar_are_flagged_as_intrabar_ambiguous():
    highs = [111.0, 111.0, 111.0, 111.0, 111.0, 115.0] + [111.0] * 10
    lows = [99.0, 99.0, 109.0, 109.0, 109.0, 109.0] + [109.0] * 10
    frame = _frame(16, highs=highs, lows=lows)
    zone = _zone(terminal_index=5)
    episode = build_touch_episodes([zone], {("TEST", "1h"): frame})
    # Use the first episode ending at bar 3; terminal is within the post-touch window.
    ep = [row for row in episode if row["touch_end_index"] == 3][0]
    rows = build_window_rows(
        [ep],
        {zone["zone_id"]: zone},
        {("TEST", "1h"): frame},
        {("TEST", "1h"): tuple([2.0] * len(frame))},
    )
    ten = next(row for row in rows if row["horizon_bars"] == 10)
    assert ten["native_terminal_within_observed_window"] is True
    assert ten["native_terminal_within_full_horizon"] is True
    assert ten["target_1p5_atr_hit_full_window"] is True
    assert ten["target_1p5_atr_active_zone_category"] == "AMBIGUOUS_ON_TERMINAL_BAR"
    assert ten["target_1p5_atr_hit_before_native_terminal"] is False


def test_ob_removal_and_fvg_terminal_labels_follow_native_rules():
    bull = SimpleNamespace(bullish=True, bottom=100.0, top=110.0, fill_boundary=110.0, fill_ratio=0.0)
    reason, ratio = classify_ob_removal(bull, {"low": 103.0, "high": 111.0}, 0.70)
    assert reason == "fill_cancel_threshold"
    assert ratio == 0.7
    reason, _ = classify_ob_removal(bull, {"low": 90.0, "high": 99.0}, 0.70)
    assert reason == "gap_through"
    assert classify_fvg_terminal("INVALID", "Kapanışla geçersizlik") == "CLOSE_INVALIDATION"
    assert classify_fvg_terminal("FULL_FILL", "Tam dolum") == "FULL_FILL"
    assert classify_fvg_terminal("INVALID", "Yaş sınırı") == "AGE_EXPIRY_NOT_PRICE_BREACH"
    assert classify_fvg_terminal("REACTION", "Tepki üretti") == "NATIVE_REACTION_TERMINAL"
    assert classify_fvg_terminal("SUPERSEDED", "Yeni bullish FVG tarafından devralındı") == "SUPERSEDED_NOT_PRICE_BREACH"
