import hashlib
import json

import pandas as pd

from research import capraz_piyasa as cp


def frame(rows=100):
    idx = pd.date_range("2024-01-01", periods=rows, tz="Europe/Istanbul")
    c = pd.Series([100.0 + x * .1 for x in range(rows)], index=idx)
    return pd.DataFrame({"open": c, "high": c + 1, "low": c - 1, "close": c, "volume": 10.0})


def test_strict_unverified_remains_unknown_and_gram_not_fabricated():
    f = frame()
    bad, invalid, atr = cp.quality(f)
    data = {"XAUUSD": (f, bad, invalid, atr)}
    days = pd.DatetimeIndex(["2024-03-01"])
    c = cp.macro_context(data, days, .5)
    assert c.loc[days[0], "XAUUSD"] == "UNKNOWN"
    assert c.loc[days[0], "XAU_GRAM_TRY"] == "UNKNOWN"


def test_assumed_lag_future_mutation_does_not_change_past():
    f = frame()
    def data(x):
        return {"XU100": (x, *cp.quality(x))}
    days = pd.DatetimeIndex(["2024-03-01"])
    a = cp.macro_context(data(f), days, .5, assume_lag_days=2)
    changed = f.copy()
    changed.loc[changed.index >= pd.Timestamp("2024-03-01", tz="Europe/Istanbul"), ["open", "high", "low", "close"]] *= 2
    b = cp.macro_context(data(changed), days, .5, assume_lag_days=2)
    assert a.loc[days[0], "XU100"] == b.loc[days[0], "XU100"]
    assert a.loc[days[0], "XU100"] != "UNKNOWN"


def test_bad_ohlc_and_subsequent_atr_are_unknown():
    f = frame()
    f.iloc[40, f.columns.get_loc("high")] = 90
    bad, invalid, _ = cp.quality(f)
    assert bad.iloc[40] and invalid.iloc[41] and invalid.iloc[50]
    assert not invalid.iloc[60]


def test_stock_horizon_and_boundary_purging():
    f = frame(100)
    events = cp.stock_events(f, .5, 5)
    day = pd.Timestamp("2024-02-01")
    assert events.loc[day, "end_day"] == pd.Timestamp("2024-02-05")
    assert events.iloc[-1].outcome == "UNKNOWN"
    assert events.iloc[-1].reason == "CENSORED"
    assert events.iloc[0].reason == "QUALITY"
    context = pd.DataFrame({"XU100": "UP"}, index=events.index)
    result = list(cp.cells(events, context, ("XU100",), pd.Timestamp("2024-02-03")))
    discovery = next(x for x in result if x["part"] == "discovery")
    assert discovery["last_day"] < "2024-01-31"


def test_all_combinations_and_checksum(tmp_path):
    assert len(list(cp.combinations(("A", "B", "C")))) == 7
    path = tmp_path / "XU100_1d.csv.gz"
    f = frame().reset_index().rename(columns={"index": "bar_time"})
    f.to_csv(path, index=False, compression="gzip")
    manifest = {"series": {"XU100": {"status": "ok", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}}}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    data, report = cp.macro_load(tmp_path)
    assert "XU100" in data
    path.write_bytes(b"tampered")
    data, report = cp.macro_load(tmp_path)
    assert "XU100" not in data and "checksum" in report["XU100"]["error"]


def test_supplied_availability_uses_strict_asof(tmp_path):
    f = frame()
    bad, invalid, atr = cp.quality(f)
    df = pd.DataFrame({"symbol": "XU100", "bar_time": f.index.astype(str),
                       "available_at": (f.index + pd.Timedelta(hours=18)).astype(str)})
    path = tmp_path / "times.csv"
    df.to_csv(path, index=False)
    available = cp.availability_load(path)
    days = pd.DatetimeIndex(["2024-03-01"])
    result = cp.macro_context({"XU100": (f, bad, invalid, atr)}, days, .5, availability=available)
    assert result.loc[days[0], "XU100"] != "UNKNOWN"
    # Post-decision values cannot affect this day.
    changed = f.copy()
    changed.loc[changed.index >= pd.Timestamp("2024-03-01", tz="Europe/Istanbul"), "close"] = 999
    bad2, invalid2, atr2 = cp.quality(changed)
    later = cp.macro_context({"XU100": (changed, bad2, invalid2, atr2)}, days, .5, availability=available)
    assert result.loc[days[0], "XU100"] == later.loc[days[0], "XU100"]


def test_availability_rejects_naive_timestamps(tmp_path):
    import pytest
    path = tmp_path / "naive.csv"
    path.write_text("symbol,bar_time,available_at\nXU100,2024-01-01,2024-01-02\n")
    with pytest.raises(ValueError, match="saat dilimi"):
        cp.availability_load(path)


def test_wilder_atr_is_reseeded_after_corrupt_bar():
    f = frame()
    altered = f.copy()
    f.iloc[40, f.columns.get_loc("high")] = 90
    altered.iloc[40, altered.columns.get_loc("high")] = 1
    _, mask_a, atr_a = cp.quality(f)
    _, mask_b, atr_b = cp.quality(altered)
    assert mask_a.iloc[52] and mask_b.iloc[52]
    assert atr_a.iloc[60] == atr_b.iloc[60]


def test_discovery_selection_does_not_optimize_on_validation(tmp_path):
    import csv
    fields = ["symbol", "horizon", "combination", "condition", "macro_atr", "stock_atr", "part",
              "condition_known", "n", "baseline_n", "up", "flat", "down", "baseline_up_pct",
              "baseline_flat_pct", "baseline_down_pct"]
    base = {"symbol": "ASTOR", "horizon": "5", "combination": "XU100", "macro_atr": "0.5",
            "stock_atr": "0.5", "condition_known": "True", "n": "40", "baseline_n": "100",
            "baseline_up_pct": "0.3", "baseline_flat_pct": "0.4", "baseline_down_pct": "0.3"}
    rows = [dict(base, part="discovery", condition="XU100=UP", up="25", flat="10", down="5"),
            dict(base, part="discovery", condition="XU100=DOWN", up="13", flat="15", down="12"),
            dict(base, part="validation", condition="XU100=UP", up="1", flat="10", down="29"),
            dict(base, part="validation", condition="XU100=DOWN", up="39", flat="1", down="0")]
    with (tmp_path / "cells.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    assert cp.select_discovery(tmp_path) == 1
    selected = pd.read_csv(tmp_path / "selected.csv")
    assert selected.iloc[0].condition == "XU100=UP"
    assert selected.iloc[0].status == "UNADJUSTED_EXPLORATORY"


def test_max_age_prevents_stale_macro_use():
    f = frame(40)
    data = {"XU100": (f, *cp.quality(f))}
    result = cp.macro_context(data, pd.DatetimeIndex(["2024-03-15"]), .5, assume_lag_days=2)
    assert result.iloc[0].XU100 == "UNKNOWN"
