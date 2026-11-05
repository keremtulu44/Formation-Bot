import pandas as pd

from bot.scan import _latest_completed_1h_timing


def _frame(*labels):
    index = pd.DatetimeIndex([pd.Timestamp(label) for label in labels])
    return pd.DataFrame(
        {
            "open": [100.0] * len(index),
            "high": [101.0] * len(index),
            "low": [99.0] * len(index),
            "close": [100.5] * len(index),
            "volume": [1000.0] * len(index),
        },
        index=index,
    )


def test_one_hour_label_age_is_not_mistaken_for_one_hour_close_delay():
    result = _latest_completed_1h_timing(
        "THYAO",
        _frame("2026-10-12 11:30:00+03:00"),
        "2026-10-12T12:35:00+03:00",
    )

    assert result["bar_label"] == "2026-10-12T11:30:00+03:00"
    assert result["actual_close"] == "2026-10-12T12:30:00+03:00"
    assert result["expected_close"] == "2026-10-12T12:30:00+03:00"
    assert result["lag_minutes"] == 0


def test_missing_latest_closed_bar_is_reported_as_delayed():
    result = _latest_completed_1h_timing(
        "GARAN",
        _frame("2026-10-12 10:30:00+03:00"),
        "2026-10-12T12:35:00+03:00",
    )

    assert result["actual_close"] == "2026-10-12T11:30:00+03:00"
    assert result["expected_close"] == "2026-10-12T12:30:00+03:00"
    assert result["lag_minutes"] == 60


def test_final_intraday_bar_uses_the_bist_18_00_close_not_daily_18_30():
    result = _latest_completed_1h_timing(
        "ASELS",
        _frame("2026-10-12 17:30:00+03:00"),
        "2026-10-12T18:35:00+03:00",
    )

    assert result["actual_close"] == "2026-10-12T18:00:00+03:00"
    assert result["expected_close"] == "2026-10-12T18:00:00+03:00"
    assert result["lag_minutes"] == 0


def test_half_day_uses_its_configured_intraday_close():
    result = _latest_completed_1h_timing(
        "THYAO",
        _frame("2026-03-19 12:30:00+03:00"),
        "2026-03-19T13:20:00+03:00",
    )

    assert result["actual_close"] == "2026-03-19T13:00:00+03:00"
    assert result["expected_close"] == "2026-03-19T13:00:00+03:00"
    assert result["lag_minutes"] == 0


def test_macro_candles_are_not_compared_with_bist_close_schedule():
    assert _latest_completed_1h_timing(
        "BRENT",
        _frame("2026-10-12 17:30:00+03:00"),
        "2026-10-12T18:35:00+03:00",
    ) is None
