"""Verify path outputs and rederive sampled paths in original price directions."""
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
from research.stabil_resistance_replay import ROOT, native_mirror, project_daily_at_bar_open, sha
from research.stabil_support_resistance_compare import LEGACY_MANIFEST, OUTPUT, REFLECTION, native_support_as_reflected_line
from research.stabil_support_resistance_paths import HORIZON, TICK


def direct_trace(i: int, side: str, close: np.ndarray, level: np.ndarray, ids: list[Any], regimes: list[str]) -> dict[str, Any]:
    """Independently rederive path semantics without reflected 4h prices."""
    start, ident0 = level[i], ids[i]
    is_support = side == "SUPPORT"
    def safe(price: float, line: float) -> bool:
        return price >= line if is_support else price <= line
    def movement(j: int) -> str | None:
        adverse = level[j] < start-TICK if is_support else level[j] > start+TICK
        favorable = level[j] > start+TICK if is_support else level[j] < start-TICK
        if adverse:
            return "LINE_ADVERSE_FIRST"
        if favorable:
            return "LINE_FAVORABLE_FIRST"
        return "IDENTITY_SAME_LEVEL_FIRST" if ids[j] != ident0 else None
    result: dict[str, Any] = {"first_path": "NEITHER", "first_step": None,
                              "line_first_price_side": None, "after_line_first": None,
                              "flat_step": None, "flat_price_side": None,
                              "after_flat_first": None, "after_price_first": None}
    first_i = None
    for j in range(i+1, i+HORIZON+1):
        if not np.isfinite(level[j]) or ids[j] is None:
            result.update(first_path="LEVEL_UNAVAILABLE", first_step=j-i)
            return result
        returned, moved = safe(close[j], start), movement(j)
        if returned and moved:
            result.update(first_path="AMBIGUOUS_SAME_BAR", first_step=j-i)
            return result
        if returned or moved:
            result.update(first_path="PRICE_RETURNS_FIXED_FIRST" if returned else moved, first_step=j-i)
            first_i = j
            break
    if first_i is None:
        return result
    if result["first_path"] == "PRICE_RETURNS_FIXED_FIRST":
        result["after_price_first"] = "NEITHER"
        for j in range(first_i+1, i+HORIZON+1):
            if not np.isfinite(level[j]) or ids[j] is None:
                result["after_price_first"] = "LEVEL_UNAVAILABLE"
                break
            breaks, moved = not safe(close[j], start), movement(j)
            if breaks and moved:
                result["after_price_first"] = "AMBIGUOUS_SAME_BAR"
                break
            if breaks or moved:
                result["after_price_first"] = "PRICE_BREAKS_FIXED_AGAIN" if breaks else moved
                break
    if result["first_path"] == "LINE_ADVERSE_FIRST":
        result["line_first_price_side"] = "SAFE_TO_NEW_LINE" if safe(close[first_i], level[first_i]) else "ADVERSE_TO_NEW_LINE"
        result["after_line_first"] = "NEITHER"
        step_id = ids[first_i]
        flat_i = None
        for j in range(first_i+1, i+HORIZON+1):
            if not np.isfinite(level[j]) or ids[j] is None:
                result["after_line_first"] = "LEVEL_UNAVAILABLE"
                break
            old_return = safe(close[j], start)
            changed = ids[j] != step_id
            flat = not changed and regimes[j] in ("HORIZONTAL_AFTER_DROP", "LONG_HORIZONTAL")
            if sum(int(x) for x in (old_return, changed, flat)) > 1:
                result["after_line_first"] = "AMBIGUOUS_SAME_BAR"
                break
            if old_return:
                result["after_line_first"] = "PRICE_RETURNS_OLD_FIRST"
                break
            if changed:
                result["after_line_first"] = "LINE_CHANGED_FIRST"
                break
            if flat:
                result.update(after_line_first="FLAT_PROXY_FIRST", flat_step=j-i)
                flat_i = j
                break
        if flat_i is not None:
            flat_safe = safe(close[flat_i], level[flat_i])
            result["flat_price_side"] = "SAFE_TO_NEW_LINE" if flat_safe else "ADVERSE_TO_NEW_LINE"
            result["after_flat_first"] = "NEITHER"
            for j in range(flat_i+1, i+HORIZON+1):
                if not np.isfinite(level[j]) or ids[j] is None:
                    result["after_flat_first"] = "LEVEL_UNAVAILABLE"
                    break
                crossing = safe(close[j], level[flat_i]) != flat_safe
                changed = ids[j] != ids[flat_i]
                if crossing and changed:
                    result["after_flat_first"] = "AMBIGUOUS_SAME_BAR"
                    break
                if crossing:
                    result["after_flat_first"] = "PRICE_CROSSES_NEW_LINE"
                    break
                if changed:
                    result["after_flat_first"] = "LINE_CHANGED_FIRST"
                    break
    return result


def verify_sample(symbol: str, paths: pd.DataFrame, archive: Path) -> dict[str, int]:
    capture = capture_cutoffs(symbol, str(archive))
    daily_raw = closed_at_capture(tf_frame(symbol, "1d", archive), "1d", capture["1d"])
    h4_raw = closed_at_capture(tf_frame(symbol, "4h", archive), "4h", capture["1h"])
    daily, e = prepare_causal_ohlcv(daily_raw, symbol=symbol, timeframe="1d")
    h4, eh = prepare_causal_ohlcv(h4_raw, symbol=symbol, timeframe="4h")
    if e or eh:
        raise AssertionError(f"{symbol}: preparation error")
    support, _, _, sr = native_support_as_reflected_line(daily)
    resistance, _, _, rr = native_mirror(daily)
    location = project_daily_at_bar_open(pd.DatetimeIndex(daily.timestamp), h4_raw.index)
    close = h4.close.to_numpy(dtype=float)
    result = {}
    for side, line, reg in (("SUPPORT", support, sr), ("RESISTANCE", resistance, rr)):
        levels = np.full(len(h4), np.nan)
        identities: list[Any] = [None]*len(h4)
        regimes = ["UNAVAILABLE"]*len(h4)
        for j, di in enumerate(location):
            if di < 0:
                continue
            levels[j] = REFLECTION-line.level[di] if side == "SUPPORT" else line.level[di]
            identities[j] = line.identity[di]
            regimes[j] = reg[di].regime.value
        observations = paths[(paths.symbol == symbol) & (paths.side == side) & (paths.status_24 == "VALID")]
        for row in observations.to_dict("records"):
            expected = direct_trace(int(row["bar_index"]), side, close, levels, identities, regimes)
            for key, value in expected.items():
                recorded = row.get(key)
                if value is None:
                    if not pd.isna(recorded):
                        raise AssertionError(f"{symbol} {side} {row['bar_index']} {key}: {recorded} != None")
                elif recorded != value:
                    raise AssertionError(f"{symbol} {side} {row['bar_index']} {key}: {recorded} != {value}")
        result[side] = len(observations)
    return result


def run(output: Path) -> dict[str, Any]:
    manifest = json.loads((output/"path_manifest.json").read_text(encoding="utf-8"))
    if manifest["comparison_manifest_sha256"] != sha(output/"manifest.json") or manifest["input_events_sha256"] != sha(output/"events_4h.csv.gz"):
        raise AssertionError("input manifest/hash differs")
    for name, expected in manifest["source_sha256"].items():
        if sha(ROOT/name) != expected:
            raise AssertionError(f"path code or plan changed: {name}")
    for name, expected in manifest["outputs_sha256"].items():
        if sha(output/name) != expected:
            raise AssertionError(f"path output changed: {name}")
    events = pd.read_csv(output/"events_4h.csv.gz", low_memory=False)
    breaks = events[events.event == "BREAK_TO_ADVERSE_SIDE"]
    paths = pd.read_csv(output/"break_paths_24.csv.gz", low_memory=False)
    summary = json.loads((output/"break_path_summary.json").read_text(encoding="utf-8"))
    keys = ["symbol", "side", "bar_index"]
    check = paths.merge(breaks[keys], on=keys, how="outer", indicator=True, validate="one_to_one")
    if len(check) != len(breaks) or not (check._merge == "both").all():
        raise AssertionError("path inputs do not match comparison breaks")
    valid = paths[paths.status_24 == "VALID"]
    if valid.first_path.isna().any() or not (valid.first_step.dropna().between(1, HORIZON)).all():
        raise AssertionError("invalid first-path labels/timing")
    reached = valid[valid.after_line_first == "FLAT_PROXY_FIRST"]
    if reached.flat_step.isna().any() or not ((reached.flat_step > reached.first_step) & (reached.flat_step <= HORIZON)).all():
        raise AssertionError("candidate flat does not occur after line step")
    old = set(json.loads(LEGACY_MANIFEST.read_text(encoding="utf-8"))["symbols"])
    for scope, part in (("2026", paths[paths.period == "Y2026"]), ("2025", paths[paths.period == "PRE_2026"]),
                        ("OLD100_BOTH_PERIODS", paths[paths.symbol.isin(old)])):
        for side in ("SUPPORT", "RESISTANCE"):
            group = part[part.side == side]
            d = summary["groups"][scope][side]
            v = group[group.status_24 == "VALID"]
            if d["all_events"] != len(group) or d["first"]["n"] != len(v):
                raise AssertionError(f"summary counts mismatch: {scope}/{side}")
            subsets = (("first", v, "first_path"),
                       ("after_line", v[v.first_path == "LINE_ADVERSE_FIRST"], "after_line_first"),
                       ("after_flat", v[v.after_line_first == "FLAT_PROXY_FIRST"], "after_flat_first"),
                       ("after_price", v[v.first_path == "PRICE_RETURNS_FIXED_FIRST"], "after_price_first"))
            for name, sub, col in subsets:
                if d[name]["n"] != len(sub):
                    raise AssertionError(f"summary denominator mismatch: {scope}/{side}/{name}")
                for label, count in d[name]["counts"].items():
                    if count != int((sub[col] == label).sum()):
                        raise AssertionError(f"summary branch mismatch: {scope}/{side}/{name}/{label}")
    samples = {s: verify_sample(s, paths, arsiv_koku()) for s in ("AEFES", "DOCO", "YYAPI") if s in set(paths.symbol)}
    result = {"result": "OK", "path_manifest_sha256": sha(output/"path_manifest.json"),
              "verifier_sha256": sha(Path(__file__)), "break_events": len(breaks),
              "valid_24": len(valid), "flat_branches": len(reached), "direct_real_price_checks": samples}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    run(args.output)


if __name__ == "__main__":
    main()
