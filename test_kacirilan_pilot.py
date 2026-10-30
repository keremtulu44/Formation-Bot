import pandas as pd

from research.kacirilan_pilot import price_outcomes, series, zone_context


def test_end_and_path_are_separate_and_thresholds_inclusive():
    f = pd.DataFrame({"close": [100, 102, 99, 98, 100]})
    result = price_outcomes(f, 0, 1, horizon=4)
    assert result == {"end_up": False, "end_down": False, "path_up": True, "path_down": True}
    assert price_outcomes(f, 2, 1, horizon=4) is None


def test_zone_availability_and_terminal_are_asof():
    zone = {"native_terminal_index": 10, "available_index": 5, "direction": "bullish",
            "zone_lower": 99, "zone_upper": 100}
    assert not zone_context([zone], 4, 100, 1, "up")
    assert zone_context([zone], 5, 101, 1, "up")
    assert not zone_context([zone], 10, 100, 1, "up")
    assert not zone_context([zone], 5, 100, 1, "down")


def test_future_prices_do_not_change_prior_pattern_or_zone(tmp_path):
    n = 180
    close = [100 + .1 * i for i in range(n)]
    f = pd.DataFrame({"bar_time": pd.date_range("2025-01-01", periods=n, tz="Europe/Istanbul"),
                      "open": close, "high": [c + 1 for c in close],
                      "low": [c - 1 for c in close], "close": close, "volume": 100})
    a, b = tmp_path / "a.gz", tmp_path / "b.gz"
    f.to_csv(a, index=False, compression="gzip")
    f.loc[120:, ["open", "high", "low", "close"]] *= 1.1
    f.to_csv(b, index=False, compression="gzip")
    x, _ = series("ASTOR", "1d", a, n)
    y, _ = series("ASTOR", "1d", b, n)
    bx, by = {r["anchor"]: r for r in x}, {r["anchor"]: r for r in y}
    shared = sorted(set(bx) & set(by))
    assert shared
    for day in shared:
        if pd.Timestamp(day) >= pd.Timestamp(f.bar_time.iloc[110]): continue
        for field in ("pattern_active", "pattern_recent10", "pattern_state", "break_dir", "ob_up", "ob_down"):
            assert bx[day][field] == by[day][field]


def test_real_zone_context_matches_truncated_asof_replay():
    from directional_zone_replay import replay_ob_zones
    from research.arsiv import tf_frame
    from research.capraz_piyasa import quality

    frame = tf_frame("ASTOR", "1h").iloc[-400:]
    _, _, atr = quality(frame)
    full = replay_ob_zones("ASTOR", "1h", frame)
    for index in (100, 150, 200, 250, 300, 350):
        prefix = replay_ob_zones("ASTOR", "1h", frame.iloc[:index + 1])
        for direction in ("up", "down"):
            assert zone_context(full, index, frame.close.iloc[index], atr.iloc[index], direction) == \
                   zone_context(prefix, index, frame.close.iloc[index], atr.iloc[index], direction)
