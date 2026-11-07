"""Independent checks for the symmetric support/resistance research artefacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from data import mum_kapanis_anlari
from research.arsiv import arsiv_koku, tf_frame
from research.stabil_arrow_context_replay import capture_cutoffs, closed_at_capture
from research.stabil_bhv48 import _build_question_specs, _enrich_features
from research.stabil_replay import replay_single_symbol
from research.stabil_resistance_replay import (
    DEFAULT_OUTPUT as RESISTANCE_OUTPUT,
    ROOT,
    native_mirror,
    project_daily_at_bar_open,
    sha,
)
from research.stabil_support_resistance_compare import (
    OUTPUT,
    native_support_as_reflected_line,
    normalize_four_hour,
    normalize_native,
    validate_previous_inputs,
)
from research.stabil_support_resistance_report import describe, matched_side_comparison
from domain_engines.stabil import prepare_causal_ohlcv

BUCKETS = {
    "A01": {"1.0-2.0_ATR_uzak": "1..2_ATR", "2.0-3.5_ATR_uzak": "2..3.5_ATR", "3.5+_ATR_uzak": "3.5+_ATR"},
    "B04": {"NEWLY_FLATTENED_AFTER_RISE": "NEW_FLAT_AFTER_FAVORABLE", "LONG_HORIZONTAL": "LONG_FLAT"},
    "C02": {"birinci_temas": "FIRST", "ikinci_temas": "SECOND", "uc_ve_uzeri_temas": "THIRD_PLUS"},
    "F01": {"STEPPING_DOWN": "ADVERSE_STEP_PROXY", "HORIZONTAL_AFTER_DROP": "FLAT_AFTER_ADVERSE_PROXY"},
}
RACES = {"SUPPORT_UP_FIRST": "LINE_FAVORABLE_FIRST", "PRICE_RETURN_FIRST": "PRICE_RETURN_FIRST",
         "SUPPORT_DOWN_FIRST": "LINE_ADVERSE_FIRST", "PRICE_RECLAIM_FIRST": "PRICE_RECLAIM_FIRST",
         "SAME_CHECKPOINT": "AMBIGUOUS_SAME_BAR", "NEITHER_WITHIN_24": "NEITHER"}
FIRST = {"UP_FIRST": "REACTION_FIRST", "DOWN_FIRST": "BREACH_SIDE_FIRST",
         "AMBIGUOUS_SAME_BAR": "AMBIGUOUS_SAME_BAR", "NEITHER": "NEITHER"}


def check_prior_resistance(events: pd.DataFrame, native: pd.DataFrame, output: Path) -> dict[str, int]:
    prior = pd.read_csv(RESISTANCE_OUTPUT/"events_4h.csv.gz", low_memory=False)
    selected = set(events.symbol.unique())
    expected = normalize_four_hour(prior[(prior.model == "MIRROR_P4") & prior.symbol.isin(selected)].copy(), "RESISTANCE")
    actual = events[events.side == "RESISTANCE"]
    keys = ["symbol", "bar_index", "event"]
    comparison = actual.merge(expected, on=keys, suffixes=("_actual", "_expected"), how="outer", indicator=True, validate="one_to_one")
    if not (comparison._merge == "both").all():
        raise AssertionError("resistance event set differs from verified previous replay")
    for name in ("status_4", "status_8", "status_16", "first_1atr_4", "first_1atr_8", "first_1atr_16", "contact"):
        a, b = comparison[f"{name}_actual"], comparison[f"{name}_expected"]
        if not (a.eq(b) | (a.isna() & b.isna())).all():
            raise AssertionError(f"prior resistance event label changed: {name}")
    for name in ("line", "open", "high", "low", "close", "atr_event", "reaction_return_atr_8"):
        if not np.allclose(comparison[f"{name}_actual"], comparison[f"{name}_expected"], rtol=1e-9, atol=1e-8, equal_nan=True):
            raise AssertionError(f"prior resistance price/outcome changed: {name}")
    prior_native = pd.read_csv(RESISTANCE_OUTPUT/"native_daily_events.csv.gz", low_memory=False)
    expected_native = normalize_native(prior_native[prior_native.symbol.isin(selected)].copy(), "RESISTANCE")
    actual_native = native[native.side == "RESISTANCE"]
    comp = actual_native.merge(expected_native, on=["symbol", "sequence", "event"], how="outer", indicator=True, validate="one_to_one")
    if not (comp._merge == "both").all():
        raise AssertionError("prior native resistance daily event set changed")
    return {"prior_resistance_4h_rows": len(comparison), "prior_resistance_daily_rows": len(comp)}


def check_legacy_symbol(symbol: str, questions: pd.DataFrame, archive: Path) -> dict[str, Any]:
    """Compare all four cohorts with the actual earlier evaluator, not a copy."""
    old = _enrich_features(replay_single_symbol(symbol, kok=archive).checkpoint_df)
    fresh = questions[(questions.symbol == symbol) & (questions.side == "SUPPORT")]
    captures = capture_cutoffs(symbol, str(archive))
    raw = closed_at_capture(tf_frame(symbol, "4h", archive), "4h", captures["1h"])
    daily_raw = closed_at_capture(tf_frame(symbol, "1d", archive), "1d", captures["1d"])
    daily_times = pd.DatetimeIndex(mum_kapanis_anlari(daily_raw.index, "1d"))
    h4_times = pd.DatetimeIndex(mum_kapanis_anlari(raw.index, "4h"))
    loc_open = project_daily_at_bar_open(daily_times, raw.index)
    loc_close = project_daily_at_bar_open(daily_times, h4_times)
    specs = _build_question_specs()
    metrics: dict[str, Any] = {}
    for question, bucket_map in BUCKETS.items():
        spec = next(x for x in specs if x.qid.endswith(question))
        old_group = spec.builder(old)[0]
        old_group = old_group[old_group.cp_index < len(raw)].copy()
        if question == "C02":
            old_group = old_group[old_group.cp_index.map(lambda i: loc_open[i] == loc_close[i])]
        old_group["_bucket"] = old_group["_bucket"].map(bucket_map)
        new_group = fresh[(fresh.question == question) & (~fresh.bucket.isin(["ZERO", "UNKNOWN"]))]
        left = set(zip(old_group.cp_index, old_group._bucket))
        right = set(zip(new_group.bar_index, new_group.bucket))
        if left != right:
            raise AssertionError(f"{symbol} {question}: old/new cohort mismatch: old-only {list(left-right)[:3]} new-only {list(right-left)[:3]}")
        joined = new_group.merge(old_group, left_on="bar_index", right_on="cp_index", suffixes=("_new", "_old"), validate="one_to_one")
        good8 = joined[joined.status_8 == "VALID"]
        if not (good8.first_1atr_8_new == good8.first_1atr_8_old.map(FIRST)).all():
            raise AssertionError(f"{symbol} {question}: old 8-bar first hit mismatch")
        if not np.allclose(good8.reaction_return_atr_8, good8.ret_atr_8, atol=1e-7, rtol=1e-8):
            raise AssertionError(f"{symbol} {question}: old 8-bar return mismatch")
        good24 = joined[joined.race_status_24 == "VALID"]
        if not (good24.race_first_24 == good24.next_race_24.map(RACES)).all():
            raise AssertionError(f"{symbol} {question}: old 24-bar path mismatch")
        metrics[question] = {"cohort_rows": len(left), "valid_8_checked": len(good8), "valid_24_checked": len(good24), "differences": 0}
    daily, error = prepare_causal_ohlcv(daily_raw, symbol=symbol, timeframe="1d")
    if error:
        raise AssertionError(error)
    complete_support, _, _, _ = native_support_as_reflected_line(daily)
    complete_resistance, _, _, _ = native_mirror(daily)
    prefixes = sorted(set((len(daily)//3, len(daily)*2//3, len(daily)-1)))
    for end in prefixes:
        subset = daily.iloc[:end].reset_index(drop=True)
        prefix_support, _, _, _ = native_support_as_reflected_line(subset)
        prefix_resistance, _, _, _ = native_mirror(subset)
        for candidate, full in ((prefix_support, complete_support), (prefix_resistance, complete_resistance)):
            for key in ("level", "ceiling", "origin", "known", "available", "age"):
                if not np.allclose(getattr(candidate, key), getattr(full, key)[:end], equal_nan=True, rtol=0, atol=1e-8):
                    raise AssertionError(f"{symbol}: prefix causality mismatch {key} at {end}")
    metrics["causal_prefix_lengths"] = prefixes
    return metrics


def run(output: Path) -> dict[str, Any]:
    manifest = json.loads((output/"manifest.json").read_text(encoding="utf-8"))
    if manifest["errors"] or manifest["successful_symbols"] != len(manifest["selected_symbols"]):
        raise AssertionError("incomplete comparison replay")
    for name, digest in manifest["source_sha256"].items():
        if sha(ROOT/name) != digest:
            raise AssertionError(f"source hash differs: {name}")
    for name, digest in manifest["outputs_sha256"].items():
        if sha(output/name) != digest:
            raise AssertionError(f"output hash differs: {name}")
    am = json.loads((output/"analysis_manifest.json").read_text(encoding="utf-8"))
    if am["comparison_manifest_sha256"] != sha(output/"manifest.json"):
        raise AssertionError("analysis references a different comparison replay")
    if am["summary_script_sha256"] != sha(ROOT/"research/stabil_support_resistance_report.py"):
        raise AssertionError("analysis script differs")
    for name, digest in am["generated_outputs_sha256"].items():
        if sha(output/name) != digest:
            raise AssertionError(f"analysis output hash differs: {name}")
    if am["legacy_table_sha256"] != sha(ROOT/"docs/arastirma/stabil_100_sonuclar/STABIL_DAVRANIS_48_TABLO.csv"):
        raise AssertionError("previous support summary table differs")
    archive = arsiv_koku()
    previous = validate_previous_inputs(archive, RESISTANCE_OUTPUT)
    if sha(RESISTANCE_OUTPUT/"manifest.json") != manifest["prior_resistance_manifest_sha256"]:
        raise AssertionError("resistance manifest changed")
    events = pd.read_csv(output/"events_4h.csv.gz", low_memory=False)
    native = pd.read_csv(output/"events_native_daily.csv.gz", low_memory=False)
    questions = pd.read_csv(output/"legacy_like_checkpoints.csv.gz", low_memory=False)
    if (len(events), len(native), len(questions)) != (manifest["events_4h"], manifest["events_native_daily"], manifest["legacy_like_checkpoint_rows"]):
        raise AssertionError("row counts differ")
    results: dict[str, Any] = {"archive_files_verified": len(previous["archive_sha256"]),
                               "source_hashes_verified": len(manifest["source_sha256"]),
                               "symbols": manifest["successful_symbols"],
                               "events_4h": len(events), "events_native_daily": len(native),
                               "legacy_like_checkpoints": len(questions)}
    results.update(check_prior_resistance(events, native, output))
    samples = [s for s in ("AEFES", "DOCO", "YYAPI") if s in manifest["selected_symbols"]]
    results["legacy_and_prefix_checks"] = {s: check_legacy_symbol(s, questions, archive) for s in samples}
    recomputed_pairs, recomputed_match = matched_side_comparison(events[events.event == "TEST"])
    stored_pairs = pd.read_csv(output/"matched_support_resistance.csv.gz", low_memory=False)
    if len(recomputed_pairs) != len(stored_pairs):
        raise AssertionError("matched pair count mismatch")
    for col in ("symbol", "support_bar", "resistance_bar", "support_first_8", "resistance_first_8"):
        a, b = recomputed_pairs[col].reset_index(drop=True), stored_pairs[col].reset_index(drop=True)
        if not (a.eq(b) | (a.isna() & b.isna())).all():
            raise AssertionError(f"matched pairs disagree: {col}")
    if not ((stored_pairs.support_bar-stored_pairs.resistance_bar).abs() >= 8).all():
        raise AssertionError("matched windows overlap")
    if stored_pairs.duplicated(["symbol", "resistance_bar"]).any():
        raise AssertionError("matched resistance observation reused")
    summary = json.loads((output/"summary.json").read_text(encoding="utf-8"))
    if recomputed_match != summary["matched_2026"]:
        raise AssertionError("matched summary differs on recomputation")
    for side in ("SUPPORT", "RESISTANCE"):
        part = events[(events.event == "TEST") & (events.period == "Y2026") & (events.side == side)]
        if describe(part) != summary["main_test"]["Y2026"]["8"][side]:
            raise AssertionError(f"main summary differs: {side}")
    results["matched_pairs_before_censor"] = len(stored_pairs)
    results["matched_valid_pairs"] = summary["matched_2026"]["valid_pairs"]
    results["result"] = "OK"
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    run(args.output)


if __name__ == "__main__":
    main()
