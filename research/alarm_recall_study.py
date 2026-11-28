"""Offline causal replay + accepted/rejected cohort study, not alert minimization.

python -m research.alarm_recall_study --output var/recall_v2
The output directory must be new/empty. No live state, provider or delivery API.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import time

import pandas as pd

import config
from data import mum_kapanis_anlari
from research import arsiv
from research.alarm_filter_audit import file_hash
from research.alarm_politika import POLITIKALAR
from research.causal_alarm_replay import VERSION, TIMEFRAMES, decision_snapshots, measure_snapshots

RULES = {code: rule for code, _, rule in POLITIKALAR if code in {"P0", "P6", "P4", "P7"}}
ROOT = Path(__file__).resolve().parents[1]


def closed_archive(symbol, tf, bars):
    record = (arsiv.manifest_oku().get("kayitlar") or {}).get(f"{symbol}:{tf}", {})
    if record.get("durum") != "ok" or record.get("dosya") != f"{symbol}_{tf}.csv.gz" or not record.get("native"):
        raise ValueError(f"Missing native capture provenance: {symbol}/{tf}")
    stamp = pd.Timestamp(record["zaman"])
    elapsed = float(record["sure_sn"])
    if pd.isna(stamp) or stamp.tzinfo is None or not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError("Invalid capture timestamp/duration")
    cutoff = stamp - pd.Timedelta(seconds=elapsed + 1)
    raw = arsiv.tf_frame(symbol, tf, legacy_resample=False)
    frame = raw.loc[mum_kapanis_anlari(raw.index, tf) <= cutoff].copy()
    return frame.tail(bars) if bars else frame


def assign_decisions(rows, rule, cooldown=6):
    """Counterfactual policies share candidates, not cooldown state or outcomes."""
    last = {}
    result = {}
    for row in sorted(rows, key=lambda r: (r["symbol"], r["timeframe"], r["bar_index"])):
        key = row["symbol"], row["timeframe"]
        event = (*key, row["bar_index"])
        if not rule(row):
            reason = "policy_blocked"
        elif key in last and row["bar_index"] - last[key] < cooldown:
            reason = "cooldown_blocked"
        else:
            reason = "selected"
            last[key] = row["bar_index"]
        result[event] = reason
    return result


def event_key(row):
    return row["symbol"], row["timeframe"], row["bar_index"]


def cohort_metrics(rows, sessions):
    statuses = Counter(r["outcome_12"]["status"] for r in rows)
    valid = [r["outcome_12"] for r in rows if r["outcome_12"]["status"] == "VALID"]
    first = Counter(o["first_touch"] for o in valid)
    daily = Counter(pd.Timestamp(r["bar_time"]).tz_convert("Europe/Istanbul").strftime("%Y-%m-%d") for r in rows)
    counts = pd.Series([daily[d] for d in sessions], dtype=float)
    n = len(valid)
    return {"events": len(rows), "per_session": len(rows) / len(sessions),
            "daily_median": float(counts.median()), "daily_p90": float(counts.quantile(.9)),
            "daily_max": int(counts.max()), "statuses": dict(statuses), "measured_directional": n,
            "favorable_first": first["FAVORABLE_FIRST"], "adverse_first": first["ADVERSE_FIRST"],
            "ambiguous": first["AMBIGUOUS_SAME_BAR"], "neither": first["NEITHER"],
            "favorable_first_rate": first["FAVORABLE_FIRST"] / n if n else None,
            "close_ge_half_atr": sum(o["close_atr"] >= .5 for o in valid),
            "median_close_atr": float(pd.Series([o["close_atr"] for o in valid]).median()) if n else None,
            "median_mae_atr": float(pd.Series([o["mae_atr"] for o in valid]).median()) if n else None,
            "unknown_direction": sum(r["source_direction"] == 0 for r in rows),
            "partial_domain_events": sum(bool(r["unknown_domains"]) for r in rows)}


def analyze(rows, sessions):
    if not sessions:
        raise ValueError("No common sessions")
    window = [r for r in rows if pd.Timestamp(r["bar_time"]).tz_convert("Europe/Istanbul").strftime("%Y-%m-%d") in sessions]
    policies, decisions = {}, {}
    for code, rule in RULES.items():
        decisions[code] = assign_decisions(rows, rule)
        policies[code] = {label: cohort_metrics([r for r in window if decisions[code][event_key(r)] == label], sessions)
                          for label in ("selected", "policy_blocked", "cooldown_blocked")}
    # Compare to P0 after its own cooldown: no summing overlapping raw signals.
    transitions = {}
    for code in RULES:
        if code == "P0":
            continue
        transitions[code] = {}
        for label, base_on, other_on in [("shared", True, True), ("P0_only", True, False), ("policy_only", False, True)]:
            subset = [r for r in window if (decisions["P0"][event_key(r)] == "selected") == base_on
                      and (decisions[code][event_key(r)] == "selected") == other_on]
            transitions[code][label] = cohort_metrics(subset, sessions)
    selected = [r for r in rows if decisions["P6"][event_key(r)] == "selected"]
    delays = []
    for row in window:
        formation = row.get("formation")
        if (not formation or row["source_direction"] == 0 or decisions["P6"][event_key(row)] == "selected"):
            continue
        matches = [r for r in selected if r["symbol"] == row["symbol"] and r["timeframe"] == row["timeframe"]
                   and r.get("formation") and r["formation"]["formation_id"] == formation["formation_id"]
                   and r["source_direction"] == row["source_direction"]
                   and 0 < r["bar_index"] - row["bar_index"] <= 6]
        if matches:
            later = min(matches, key=lambda r: r["bar_index"])
            delays.append({"symbol": row["symbol"], "timeframe": row["timeframe"], "bar_time": row["bar_time"],
                           "later_bar_time": later["bar_time"], "delay_bars": later["bar_index"] - row["bar_index"],
                           "formation_id": formation["formation_id"]})
    daily = []
    for date in sessions:
        day = [r for r in window if pd.Timestamp(r["bar_time"]).tz_convert("Europe/Istanbul").strftime("%Y-%m-%d") == date]
        daily.append({"session": date, **{code: sum(decisions[code][event_key(r)] == "selected" for r in day) for code in RULES}})
    splits = {}
    mid = len(sessions) // 2
    for label, dates in (("first_half", sessions[:mid]), ("second_half", sessions[mid:])):
        if dates:
            splits[label] = {code: cohort_metrics([r for r in window if decisions[code][event_key(r)] == "selected"
                            and pd.Timestamp(r["bar_time"]).tz_convert("Europe/Istanbul").strftime("%Y-%m-%d") in dates], dates)
                            for code in RULES}
    return {"policies": policies, "vs_P0_after_cooldown": transitions,
            "same_formation_later_P6_within6": {"blocked_rows_with_later_match": len(delays),
                "distinct_later_events": len({(d["symbol"], d["timeframe"], d["later_bar_time"]) for d in delays}),
                "examples": delays[:12]}, "chronological_sensitivity_NOT_holdout": splits}, daily, decisions


def run(symbols, output, *, bars=480, first="2026-10-19", last="2026-11-18"):
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a new empty output directory; v1/v2 and incomplete runs must not mix")
    output.mkdir(parents=True, exist_ok=True)
    rows, metas, probes, hashes = [], [], [], {}
    start = time.monotonic()
    with (output / "events.jsonl").open("w") as stream:
        for symbol in symbols:
            for tf in TIMEFRAMES:
                frame = closed_archive(symbol, tf, bars)
                if len(frame) < 100:
                    raise ValueError(f"Insufficient history {symbol}/{tf}")
                snapshots, errors = decision_snapshots(symbol, tf, frame)
                cutoff = int(len(frame) * .75)
                prefix, prefix_errors = decision_snapshots(symbol, tf, frame.iloc[:cutoff])
                actual = [r for r in snapshots if r["bar_index"] < cutoff]
                equal = actual == prefix
                probes.append({"symbol": symbol, "timeframe": tf, "cutoff": cutoff,
                               "prefix_equal": equal, "full_events_before_cut": len(actual), "prefix_events": len(prefix)})
                if not equal:
                    raise ValueError(f"Prefix mismatch: {symbol}/{tf}")
                # Errors remain explicit; a degraded candidate stream is not published as complete.
                if errors or prefix_errors:
                    (output / "domain_errors.json").write_text(json.dumps({"symbol": symbol, "tf": tf, "errors": errors, "prefix_errors": prefix_errors}))
                    raise ValueError(f"Domain failure: {symbol}/{tf}; no complete-universe report")
                measured = measure_snapshots(frame, snapshots)
                for row in measured:
                    stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
                rows.extend(measured)
                counts = frame.index.tz_convert("Europe/Istanbul").strftime("%Y-%m-%d").value_counts().to_dict()
                metas.append({"symbol": symbol, "timeframe": tf, "bars": len(frame), "session_bars": counts})
                path = arsiv.arsiv_koku() / f"{symbol}_{tf}.csv.gz"
                hashes[path.name] = file_hash(path)
                arsiv._OBELLEK.clear()
                print(f"{len(metas)}/{len(symbols)*4} {symbol} {tf} events={len(measured)} prefix=OK", flush=True)
    sessions = sorted(d for d in set.intersection(*(set(m["session_bars"]) for m in metas)) if first <= d <= last)
    result, daily, decisions = analyze(rows, sessions)
    result["manifest"] = {
        "schema": VERSION, "objective": "retain_meaningful_events_not_minimize_count",
        "symbols": list(symbols), "series": len(metas), "bars_per_series_max": bars,
        "first": sessions[0], "last": sessions[-1], "sessions": sessions, "archive_hashes": hashes,
        "archive_manifest_sha256": file_hash(arsiv.arsiv_koku() / "manifest.json"),
        "code_hashes": {str(p.relative_to(ROOT)): file_hash(p) for p in sorted((ROOT / "domain_engines").rglob("*.py"))
                        + sorted((ROOT / "patterns").rglob("*.py"))
                        + [ROOT / "research/causal_alarm_replay.py", ROOT / "research/alarm_recall_study.py",
                           ROOT / "research/domain_alarm_replay.py", ROOT / "research/alarm_politika.py",
                           ROOT / "bot/domain_alarm_service.py", ROOT / "config.py"]},
        "config_not_production_proof": {name: getattr(config, name) for name in (
            "PROFILE", "ALERT_MIN_QUALITY", "YENI_DOMAIN_ALARM_IMMEDIATE_TEKRAR", "YENI_DOMAIN_ALARM_POLITIKA",
            "YENI_DOMAIN_ALARM_HACIM_5X", "YENI_DOMAIN_ALARM_HACIM_10X", "YENI_DOMAIN_ALARM_HACIM_SUPHE")},
        "prefix_probes": probes, "domain_errors": 0, "elapsed_seconds": round(time.monotonic() - start, 2),
        "limitations": ["domain-channel candidates BEFORE live Stabil support/distance gate",
                        "not main formation + Stabil reclaim + live schedule/delivery parity",
                        "fixed-start native480 replay, not rolling-window production history",
                        "snapshot form state lacks scan-level invalidation notification alias",
                        "no transaction costs, no causal market effect, correlated repeated/overlapping events",
                        "positive first-touch criterion is operational, not a trade-profit label",
                        "chronological split is sensitivity on an already researched period, not blind holdout"],
    }
    (output / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    (output / "meta.json").write_text(json.dumps(metas, ensure_ascii=False, indent=2) + "\n")
    pd.DataFrame(daily).to_csv(output / "daily.csv", index=False)
    # Full per-event decision ledger stays outside Git with the large raw dataset.
    with (output / "decisions.jsonl").open("w") as stream:
        for row in rows:
            stream.write(json.dumps({"symbol": row["symbol"], "timeframe": row["timeframe"],
                "bar_time": row["bar_time"], **{code: mapping[event_key(row)] for code, mapping in decisions.items()}}, ensure_ascii=False) + "\n")
    print("Completed",len(metas),"series",len(sessions),"sessions",flush=True)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--symbols", default="")
    parser.add_argument("--bars", type=int, default=480)
    parser.add_argument("--first", default="2026-10-19")
    parser.add_argument("--last", default="2026-11-18")
    args = parser.parse_args(argv)
    if args.bars < 0:
        parser.error("--bars must be >= 0")
    native = set(arsiv.arsiv_sembolleri(native_only=True))
    if args.symbols:
        symbols = sorted(set(args.symbols.upper().split(",")))
        if not set(symbols) <= native:
            parser.error("Missing native symbol")
    else:
        symbols = sorted(set(config.ACTIVE_STOCKS) & native)
    if not symbols:
        parser.error("Empty universe")
    run(symbols, args.output, bars=args.bars, first=args.first, last=args.last)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
