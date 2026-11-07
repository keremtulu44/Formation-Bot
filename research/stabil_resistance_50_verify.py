"""Audit 50-stock selection, summaries and independently sample fixed-line paths."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from domain_engines.stabil import prepare_causal_ohlcv
from research.arsiv import arsiv_koku, tf_frame
from research.stabil_arrow_context_replay import capture_cutoffs, closed_at_capture
from research.stabil_resistance_50_model_report import OUTPUT, f01_groups, select_check
from research.stabil_resistance_replay import ROOT, native_mirror, project_daily_at_bar_open, sha
from research.stabil_support_resistance_compare import native_support_as_reflected_line


def verify_symbol(symbol: str, b04: pd.DataFrame, fixed: pd.DataFrame) -> dict[str, int]:
    archive = arsiv_koku()
    cap = capture_cutoffs(symbol, str(archive))
    dr = closed_at_capture(tf_frame(symbol, "1d", archive), "1d", cap["1d"])
    hr = closed_at_capture(tf_frame(symbol, "4h", archive), "4h", cap["1h"])
    daily, de = prepare_causal_ohlcv(dr, symbol=symbol, timeframe="1d")
    h4, he = prepare_causal_ohlcv(hr, symbol=symbol, timeframe="4h")
    if de or he:
        raise AssertionError("symbol source data preparation failed")
    _, sobs, _, _ = native_support_as_reflected_line(daily)
    _, robs, _, _ = native_mirror(daily)
    loc_open = project_daily_at_bar_open(pd.DatetimeIndex(daily.timestamp), hr.index)
    close_loc = np.searchsorted(pd.DatetimeIndex(daily.timestamp).asi8, pd.DatetimeIndex(h4.timestamp).asi8, side="right")-1
    close = h4.close.to_numpy(dtype=float)
    checked_b04 = b04[b04.symbol == symbol]
    for row in checked_b04.to_dict("records"):
        i = int(row["bar_index"])
        obs = sobs if row["side"] == "SUPPORT" else robs
        level = float(obs[close_loc[i]].support_level) * (1 if row["side"] == "SUPPORT" else -1)
        if not np.isclose(level, row["line"], rtol=1e-9, atol=1e-8):
            raise AssertionError("B04 line mismatch")
        actual = any(p < level for p in close[i+1:i+9]) if row["side"] == "SUPPORT" else any(p > level for p in close[i+1:i+9])
        if actual != bool(row["future_close_breach_8"]):
            raise AssertionError("B04 future close classification mismatch")
    checked_fixed = fixed[fixed.symbol == symbol]
    for row in checked_fixed.to_dict("records"):
        side, j, end = row["side"], int(row["line_move_index"]), int(row["break_index"])+24
        obs = sobs if side == "SUPPORT" else robs
        d = obs[loc_open[j]]
        level = float(d.support_level) * (1 if side == "SUPPORT" else -1)
        identity = d.support_identity
        if not np.isclose(level, row["new_line"], rtol=1e-9, atol=1e-8):
            raise AssertionError("fixed-level value differs")
        def safe(value: float) -> bool:
            return value >= level if side == "SUPPORT" else value <= level
        was_safe = safe(close[j])
        if row["price_side_at_step"] != ("SAFE" if was_safe else "ADVERSE"):
            raise AssertionError("fixed-level initial side differs")
        result = "NO_REMAINING" if j == end else "NEITHER"
        crossing = None
        for k in range(j+1, end+1):
            di = int(loc_open[k])
            if di < 0 or obs[di].support_identity is None:
                result = "LEVEL_UNAVAILABLE"
                break
            changed = obs[di].support_identity != identity
            crossed = safe(close[k]) != was_safe
            if crossed and changed:
                result = "AMBIGUOUS_SAME_BAR"
                break
            if crossed:
                result, crossing = "PRICE_CROSSES_FIRST", k
                break
            if changed:
                result = "LINE_CHANGED_FIRST"
                break
        if result != row["first"]:
            raise AssertionError("fixed-level first result differs")
        if crossing is not None:
            position = "EQUAL" if close[crossing] == level else "STRICT"
            if row["first_cross_position"] != position:
                raise AssertionError(f"{symbol} first price equality differs")
        if not was_safe:
            strict = "NO_REMAINING" if j == end else "NEITHER"
            for k in range(j+1, end+1):
                di = int(loc_open[k])
                if di < 0 or obs[di].support_identity is None:
                    strict = "LEVEL_UNAVAILABLE"
                    break
                changed = obs[di].support_identity != identity
                strict_cross = close[k] > level if side == "SUPPORT" else close[k] < level
                if strict_cross and changed:
                    strict = "AMBIGUOUS_SAME_BAR"
                    break
                if strict_cross:
                    strict = "PRICE_CROSSES_FIRST"
                    break
                if changed:
                    strict = "LINE_CHANGED_FIRST"
                    break
            if row["strict_safe_first"] != strict:
                raise AssertionError(f"{symbol} strict-side result differs")
        if not was_safe and crossing is not None:
            later = "NO_REMAINING" if crossing == end else "NEITHER"
            for k in range(crossing+1, end+1):
                di = int(loc_open[k])
                if di < 0 or obs[di].support_identity is None:
                    later = "LEVEL_UNAVAILABLE"
                    break
                changed = obs[di].support_identity != identity
                crosses = not safe(close[k])
                if changed and crosses:
                    later = "AMBIGUOUS_SAME_BAR"
                    break
                if crosses:
                    later = "PRICE_CROSSES_FIRST"
                    break
                if changed:
                    later = "LINE_CHANGED_FIRST"
                    break
            if row["after_safe_return"] != later:
                raise AssertionError("fixed-level second result differs")
    return {"b04_future_closes": len(checked_b04), "fixed_line_paths": len(checked_fixed)}


def run(output: Path) -> dict[str, Any]:
    comparison = json.loads((output/"manifest.json").read_text(encoding="utf-8"))
    selected = select_check(output, comparison)
    focused = json.loads((output/"focused_manifest.json").read_text(encoding="utf-8"))
    checks = (("selection_sha256", output/"selection.json"), ("plan_sha256", output/"PLAN.md"),
              ("comparison_manifest_sha256", output/"manifest.json"), ("path_manifest_sha256", output/"path_manifest.json"),
              ("fixed_line_manifest_sha256", output/"fixed_line_manifest.json"),
              ("focused_script_sha256", ROOT/"research/stabil_resistance_50_model_report.py"),
              ("focused_tests_sha256", ROOT/"test_stabil_resistance_50_model_report.py"))
    for key, path in checks:
        if focused[key] != sha(path):
            raise AssertionError(f"focused input changed: {key}")
    for name, digest in focused["output_sha256"].items():
        if sha(output/name) != digest:
            raise AssertionError(f"focused output changed: {name}")
    fixed_manifest = json.loads((output/"fixed_line_manifest.json").read_text(encoding="utf-8"))
    for key, path in (("path_manifest_sha256", output/"path_manifest.json"), ("plan_sha256", output/"EK_YOL_PLANI.md"),
                      ("script_sha256", ROOT/"research/stabil_resistance_50_fixed_line_paths.py"),
                      ("test_sha256", ROOT/"test_stabil_resistance_50_fixed_line_paths.py")):
        if fixed_manifest[key] != sha(path):
            raise AssertionError(f"fixed-line input changed: {key}")
    for name, digest in fixed_manifest["outputs_sha256"].items():
        if sha(output/name) != digest:
            raise AssertionError(f"fixed-line output changed: {name}")
    q = pd.read_csv(output/"legacy_like_checkpoints.csv.gz", low_memory=False)
    b04 = pd.read_csv(output/"b04_fixed_line_breaks.csv.gz", low_memory=False)
    fixed = pd.read_csv(output/"fixed_line_paths.csv.gz", low_memory=False)
    paths = pd.read_csv(output/"break_paths_24.csv.gz", low_memory=False)
    result = json.loads((output/"focused_summary.json").read_text(encoding="utf-8"))
    if f01_groups(q) != result["f01_price_side_groups"]:
        raise AssertionError("F01 grouped results mismatch")
    events = pd.read_csv(output/"events_4h.csv.gz", low_memory=False)
    for g in result["post_touch_close_2026"]:
        part = events[(events.period == "Y2026") & (events.event == "TEST") & (events.status_8 == "VALID") &
                      (events.side == g["side"]) & (events.contact == g["contact"])]
        if len(part) != g["n"] or int(part.symbol.nunique()) != g["symbols"]:
            raise AssertionError("post-touch denominator mismatch")
        for key, count in g["counts"].items():
            if int((part.first_1atr_8 == key).sum()) != count:
                raise AssertionError("post-touch outcome mismatch")
    qvalid = q[(q.question == "B04") & (q.status_8 == "VALID")]
    keys = ["symbol", "side", "bar_index"]
    joined = qvalid.merge(b04, on=keys, how="outer", indicator=True, validate="one_to_one")
    if len(joined) != len(qvalid) or not (joined._merge == "both").all():
        raise AssertionError("B04 event set mismatch")
    for row in result["b04_fixed_break_groups"]:
        part = b04[(b04.period == row["period"]) & (b04.side == row["side"]) & (b04.bucket == row["candidate"])]
        if len(part) != row["n"] or int(part.future_close_breach_8.sum()) != row["breaches"]:
            raise AssertionError("B04 aggregate mismatch")
    valid_paths = paths[(paths.status_24 == "VALID") & (paths.first_path == "LINE_ADVERSE_FIRST")]
    pkeys = ["symbol", "side", "break_index"]
    a = valid_paths.rename(columns={"bar_index": "break_index"})[pkeys+ ["first_step"]]
    merged = a.merge(fixed, on=pkeys, how="outer", indicator=True, validate="one_to_one")
    if len(merged) != len(valid_paths) or not (merged._merge == "both").all():
        raise AssertionError("fixed line path set mismatch")
    if not (merged.line_move_index == merged.break_index+merged.first_step_x).all():
        raise AssertionError("fixed line event timing mismatch")
    for g in result["fixed_line_groups"]:
        part = fixed[(fixed.period == g["period"]) & (fixed.side == g["side"]) & (fixed.price_side_at_step == g["initial_side"])]
        for column, key in (("first", "first"), ("strict_safe_first", "strict_safe_first"), ("after_safe_return", "after_safe_return")):
            subset = part[part[column].notna()]
            if len(subset) != g[key]["n"] or int(subset.symbol.nunique()) != g[key]["symbols"]:
                raise AssertionError(f"fixed-line aggregate denominator mismatch: {key}")
            for category, count in g[key]["counts"].items():
                if int((subset[column] == category).sum()) != count:
                    raise AssertionError(f"fixed-line aggregate count mismatch: {key}/{category}")
        for category, count in g["first_cross_position_counts"].items():
            if int((part.first_cross_position == category).sum()) != count:
                raise AssertionError("fixed-line equality aggregate mismatch")
    sample = verify_symbol("DOCO", b04, fixed) if "DOCO" in selected else {}
    r6 = fixed[(fixed.period == "Y2026") & (fixed.side == "RESISTANCE") & (fixed.price_side_at_step == "ADVERSE")]
    six_checks = {symbol: verify_symbol(symbol, b04.iloc[0:0], fixed[fixed.index.isin(r6.index)]) for symbol in sorted(r6.symbol.unique())}
    output_json = {"result": "OK", "selected_symbols": len(selected), "f01_groups_checked": len(result["f01_price_side_groups"]),
                   "post_touch_close_groups_checked": len(result["post_touch_close_2026"]),
                   "b04_checkpoint_rows": len(b04), "fixed_line_path_rows": len(fixed),
                   "independent_original_price_checks_DOCO": sample,
                   "independent_original_price_checks_six_resistance_paths": six_checks,
                   "focused_manifest_sha256": sha(output/"focused_manifest.json"),
                   "fixed_line_manifest_sha256": sha(output/"fixed_line_manifest.json"),
                   "verifier_sha256": sha(Path(__file__))}
    print(json.dumps(output_json, ensure_ascii=False, indent=2))
    return output_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    run(args.output)


if __name__ == "__main__":
    main()
