"""Re-read a completed v2 study for direction/TF/channel and delayed-form detail.

No new thresholds; no outcomes enter policy decisions. Large rows stay in var/.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path

import pandas as pd

from research.alarm_filter_audit import file_hash
from research.alarm_recall_study import cohort_metrics, event_key, assign_decisions, RULES
from research.causal_alarm_replay import VERSION


def information_signature(row):
    """Observable categorical changes only, NOT proof of a new market event.

    Zone IDs/bounds and MS event identities are absent in the saved candidate
    schema. Equal signatures can therefore hide a new zone/break at a new level.
    """
    formation = row.get("formation") or {}
    return (row["source_direction"], tuple(sorted(row["reasons"])),
            formation.get("formation_id"), formation.get("notification_state"),
            formation.get("break_dir"), row.get("hacim_tier"),
            row.get("suspect_volume"))


def cooldown_information(rows, decisions, sessions):
    """Compare each cooldown-blocked snapshot to that policy's last selection."""
    previous, buckets = {}, defaultdict(list)
    for row in sorted(rows, key=lambda r: (r["symbol"], r["timeframe"], r["bar_index"])):
        series = row["symbol"], row["timeframe"]
        label = decisions[event_key(row)]
        if label == "selected":
            previous[series] = row
        elif label == "cooldown_blocked":
            prior = previous.get(series)
            if prior is None:
                raise ValueError("Cooldown block without prior selection")
            date = pd.Timestamp(row["bar_time"]).tz_convert("Europe/Istanbul").strftime("%Y-%m-%d")
            if date in sessions:
                changed = information_signature(row) != information_signature(prior)
                buckets["categorical_change" if changed else "same_categorical_signature"].append(row)
    return {label: cohort_metrics(buckets[label], sessions)
            for label in ("categorical_change", "same_categorical_signature")}


def breakdown(source):
    source = Path(source)
    summary = json.loads((source / "summary.json").read_text())
    if summary["manifest"]["schema"] != VERSION:
        raise ValueError("Requires completed causal v2 study")
    rows = [json.loads(line) for line in (source / "events.jsonl").read_text().splitlines() if line]
    if len({event_key(r) for r in rows}) != len(rows):
        raise ValueError("Duplicate events")
    decisions = {name: assign_decisions(rows, rule) for name, rule in RULES.items()}
    sessions = summary["manifest"]["sessions"]
    window = [r for r in rows if pd.Timestamp(r["bar_time"]).tz_convert("Europe/Istanbul").strftime("%Y-%m-%d") in sessions]
    groups = []
    for policy in ("P0", "P6"):
        for label in ("selected", "policy_blocked", "cooldown_blocked"):
            cohort = [r for r in window if decisions[policy][event_key(r)] == label]
            for feature, key in (("direction", lambda r: r["source_direction"]),
                                 ("timeframe", lambda r: r["timeframe"]),
                                 ("channel_combination", lambda r: "+".join(r["kanallar"]))):
                buckets = defaultdict(list)
                for row in cohort:
                    buckets[str(key(row))].append(row)
                for bucket, values in sorted(buckets.items()):
                    groups.append({"policy": policy, "cohort": label, "feature": feature,
                                   "bucket": bucket, **cohort_metrics(values, sessions)})
    by_formation = defaultdict(list)
    for row in rows:
        if row.get("formation") and row["source_direction"] and decisions["P6"][event_key(row)] == "selected":
            by_formation[(row["symbol"], row["timeframe"], row["formation"]["formation_id"], row["source_direction"])].append(row)
    delays, examples = [], []
    for row in sorted(window, key=lambda r: (r["bar_time"], r["symbol"], r["timeframe"])):
        key = event_key(row)
        if row.get("formation") and row["source_direction"] and decisions["P6"][key] != "selected":
            future = by_formation.get((row["symbol"], row["timeframe"], row["formation"]["formation_id"], row["source_direction"]), [])
            matches = [r for r in future if 0 < r["bar_index"] - row["bar_index"] <= 6]
            if matches:
                later = min(matches, key=lambda r: r["bar_index"])
                delay = later["bar_index"] - row["bar_index"]
                outcome = row["outcome_12"]
                delays.append({"symbol": row["symbol"], "timeframe": row["timeframe"],
                    "blocked_bar_time": row["bar_time"], "selected_bar_time": later["bar_time"],
                    "delay_bars": delay, "blocked_reason": decisions["P6"][key],
                    "favorable_first_already_reached": outcome["status"] == "VALID"
                        and outcome["first_touch"] == "FAVORABLE_FIRST" and outcome["touch_delay_bars"] <= delay})
        outcome = row["outcome_12"]
        if decisions["P0"][key] == "selected" and decisions["P6"][key] != "selected" and outcome["status"] == "VALID":
            # Deterministic first three per outcome class, not a best-chart search.
            if sum(e["first_touch"] == outcome["first_touch"] for e in examples) < 3:
                examples.append({"symbol": row["symbol"], "timeframe": row["timeframe"],
                    "bar_time": row["bar_time"], "direction": row["source_direction"],
                    "reasons": " | ".join(row["reasons"]), "P6_reason": decisions["P6"][key],
                    "run6_atr": row["bagl_gunici_kosu"], "range10_50": row["bagl_sikisma"], **outcome})
    return {"schema": VERSION, "groups": groups,
            "cooldown_information_proxy": {
                "note": "Categorical changes versus last selected snapshot, not event identity or deduplication proof; same labels can hide new MS/zone levels.",
                "policies": {code: cooldown_information(rows, decisions[code], sessions) for code in ("P0", "P6")}},
            "delayed_same_formation": {"blocked_rows": len(delays),
                "median_delay_bars": float(pd.Series([d["delay_bars"] for d in delays]).median()) if delays else None,
                "distinct_later_events_with_prior_favorable_touch": len({(d["symbol"], d["timeframe"], d["selected_bar_time"]) for d in delays if d["favorable_first_already_reached"]}),
                "by_block_reason": {reason: {"rows": sum(d["blocked_reason"] == reason for d in delays),
                    "prior_favorable_touch_rows": sum(d["blocked_reason"] == reason and d["favorable_first_already_reached"] for d in delays)}
                    for reason in ("policy_blocked", "cooldown_blocked")},
                "distinct_later_events": len({(d["symbol"], d["timeframe"], d["selected_bar_time"]) for d in delays}),
                "favorable_first_reached_by_later_close_rows": sum(d["favorable_first_already_reached"] for d in delays),
                "note": "Rows can share the same later alert/move; this is not a count of independent missed trades.",
                "examples": delays[:12]},
            "provenance": {"code_sha256": file_hash(Path(__file__)),
                "input_hashes": {p: file_hash(source / p) for p in ("summary.json", "events.jsonl")}}}, examples


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result, examples = breakdown(args.input)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "breakdown.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    pd.DataFrame(examples).to_csv(args.output / "examples.csv", index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
