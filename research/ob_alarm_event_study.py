"""OB alarm study: zone occupancy versus a closed rejection of a known zone.

No price outcome labels or threshold fitting. Baseline channel snapshots come
from the existing causal v2 run; every native input and OB baseline is checked.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from bot.domain_alarm_service import _bolge_sebepleri, _kanallar_from_sebepler, _zaten_gonderildi
from directional_zone_replay import compute_wilder_atr
from research.domain_alarm_replay import baglam_satiri
from domain_engines.adapter import to_domain_frame
from domain_engines.order_block import OrderBlockEngine
from research.alarm_filter_audit import file_hash
from research.alarm_recall_study import closed_archive, assign_decisions, event_key, RULES


def reaction(previous, surviving, bar):
    """Study hypothesis: existing remaining zone touched + close back outside.

    A zone must pre-exist the decision bar and survive the native invalidation
    logic. No candle-colour/ATR/return threshold. At most nearest prior zone per
    side, matching the native export contract rather than all remote zones.
    """
    reasons, observations = [], []
    for side, sign in (("bull", 1), ("bear", -1)):
        zone = getattr(previous, side)
        if zone.source_bar is None or zone.top is None or zone.bottom is None:
            continue
        identity = (int(zone.source_bar), sign)
        if identity not in surviving:
            continue
        touched = bar["low"] <= zone.top and bar["high"] >= zone.bottom
        held = bar["close"] > zone.top if sign == 1 else bar["close"] < zone.bottom
        observations.append({"side": side, "source_index": int(zone.source_bar),
            "top_before": zone.top, "bottom_before": zone.bottom,
            "touched": bool(touched), "closed_back_outside": bool(held)})
        if touched and held:
            reasons.append(f"OB {'boğa' if sign == 1 else 'ayı'} bölge tepkisi")
    return sorted(reasons), observations


def series_rows(symbol, tf, frame, baseline):
    engine = OrderBlockEngine()
    rows = []
    adapted = to_domain_frame(frame)
    atrs = compute_wilder_atr(adapted)
    for index, bar in enumerate(adapted.to_dict("records")):
        before = engine.export
        engine.update(bar)
        if index < 29:
            continue
        results = {tf: {"order_block": {"export": engine.export, "data_quality": engine.last_data_quality}}}
        old = _bolge_sebepleri(results, tf, bar["close"])
        saved = baseline.get((symbol, tf, index))
        if old != sorted(r for r in (saved or {}).get("reasons", []) if r.startswith("OB ")):
            raise ValueError(f"Baseline OB mismatch {symbol}/{tf}/{index}")
        surviving = {(r.source_index, 1 if r.bullish else -1) for r in engine.active_records}
        new, observations = reaction(before, surviving, bar)
        results[tf]["order_block"]["details"] = {"reaction_context": engine.reaction_context}
        production = _bolge_sebepleri(results, tf, bar["close"], frame=frame.iloc[:index + 1])
        if production != new:
            raise ValueError(f"Production/hypothesis mismatch {symbol}/{tf}/{index}")
        if not old and not new:
            continue
        rows.append({"symbol": symbol, "timeframe": tf, "bar_index": index,
            "bar_time": pd.Timestamp(frame.index[index]).isoformat(),
            "open": bar["open"], "high": bar["high"], "low": bar["low"], "close": bar["close"],
            "old_ob": old, "event_ob": new, "observations": observations,
            "current_export": asdict(engine.export), **baglam_satiri(frame, index, atrs),
            "other_reasons": [r for r in (saved or {}).get("reasons", []) if not r.startswith("OB ")]})
    return rows


def live_decisions(rows, rule):
    """Use production cooldown with private in-memory slots, never a live store."""
    import config
    if config.YENI_DOMAIN_ALARM_COOLDOWN_BAR != 6:
        raise ValueError("This paired study requires the recorded six-bar cooldown")
    slots, decisions = {}, {}
    for row in sorted(rows, key=lambda r: (r["symbol"], r["timeframe"], r["bar_index"])):
        key = event_key(row)
        if not rule(row):
            decisions[key] = "policy_blocked"
            continue
        cand = SimpleNamespace(bar_open=row["bar_time"], bar_index=row["bar_index"],
                               recent_bar_opens=(), reasons=tuple(row["reasons"]))
        if _zaten_gonderildi(slots.get(key[:2]), cand):
            decisions[key] = "cooldown_blocked"
        else:
            decisions[key] = "selected"
            slots[key[:2]] = {"last_bar_open": row["bar_time"], "last_bar_index": row["bar_index"],
                             "reason_signature": "|".join(sorted(row["reasons"]))}
    return decisions


def compare_policies(baseline, event_rows, sessions):
    """Change only OB reasons; keep other channels/features and independent CDs.

    Outputs are domain channel candidates BEFORE Stabil support and dispatch.
    No future outcome is used; count changes are capacity effects, not success.
    """
    updated = {}
    evidence = {event_key(r): r for r in event_rows}
    for key in set(baseline) | set(evidence):
        before, proof = baseline.get(key), evidence.get(key)
        other = [s for s in (before or {}).get("reasons", []) if not s.startswith("OB ")]
        reasons = sorted(set(other + (proof or {}).get("event_ob", [])))
        if not reasons:
            continue
        row = dict(before or proof)
        row.update(reasons=reasons, kanallar=sorted(_kanallar_from_sebepler(reasons)))
        row.setdefault("hacim_tier", None)
        updated[key] = row
    versions = {"before": list(baseline.values()), "after": list(updated.values())}
    decisions = {label: {code: (assign_decisions(rows, rule) if label == "before" else live_decisions(rows, rule))
                        for code,rule in RULES.items()} for label,rows in versions.items()}
    unprotected = {code: assign_decisions(list(updated.values()), rule) for code,rule in RULES.items()}
    in_window = lambda r: pd.Timestamp(r["bar_time"]).tz_convert("Europe/Istanbul").strftime("%Y-%m-%d") in sessions
    window_keys = {key for key,row in {**baseline,**updated}.items() if in_window(row)}
    results = {}
    for code in RULES:
        selected = {version: {k for k in window_keys if mapping[code].get(k) == "selected"}
                    for version,mapping in decisions.items()}
        results[code] = {"before": len(selected["before"]), "after": len(selected["after"]),
            "before_per_session": len(selected["before"]) / len(sessions),
            "after_per_session": len(selected["after"]) / len(sessions),
            "same_bar_shared": len(selected["before"] & selected["after"]),
            "before_only": len(selected["before"] - selected["after"]),
            "after_only": len(selected["after"] - selected["before"]),
            "reaction_without_priority_selected": sum(unprotected[code].get(k) == "selected" for k in window_keys),
            "before_only_fate_after": dict(Counter(decisions["after"][code].get(k,"no_candidate")
                for k in selected["before"] - selected["after"])),
            "before_only_channel_combinations": dict(Counter("+".join(baseline[k]["kanallar"])
                for k in selected["before"] - selected["after"]))}
    return {"candidate_bars_before": sum(in_window(r) for r in baseline.values()),
            "candidate_bars_after": sum(in_window(r) for r in updated.values()),
            "policies_independent_6bar_cooldowns": results,
            "scope": "BEFORE Stabil support gate, scheduling and delivery; NOT messages or quality"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=Path("var/alarm_recall_v2_20261127"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists() and any(args.output.iterdir()):
        raise ValueError("New empty output required")
    manifest = json.loads((args.baseline / "summary.json").read_text())["manifest"]
    baseline = {(r["symbol"], r["timeframe"], r["bar_index"]): r for r in
                (json.loads(line) for line in (args.baseline / "events.jsonl").read_text().splitlines())}
    args.output.mkdir(parents=True, exist_ok=True)
    rows, probes = [], []
    for symbol in manifest["symbols"]:
        for tf in ("1h", "2h", "4h", "1d"):
            from research import arsiv
            name = f"{symbol}_{tf}.csv.gz"
            if file_hash(arsiv.arsiv_koku() / name) != manifest["archive_hashes"][name]:
                raise ValueError(f"Input changed: {name}")
            frame = closed_archive(symbol, tf, manifest["bars_per_series_max"])
            current = series_rows(symbol, tf, frame, baseline)
            cut = len(frame) * 3 // 4
            prefix = series_rows(symbol, tf, frame.iloc[:cut], baseline)
            if prefix != [r for r in current if r["bar_index"] < cut]:
                raise ValueError(f"Prefix mismatch {symbol}/{tf}")
            rows.extend(current)
            probes.append({"symbol": symbol, "timeframe": tf, "prefix_equal": True})
            print(f"{len(probes)}/200 {symbol}/{tf}", flush=True)
    with (args.output / "rows.jsonl").open("w") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    window = [r for r in rows if pd.Timestamp(r["bar_time"]).tz_convert("Europe/Istanbul").strftime("%Y-%m-%d") in manifest["sessions"]]
    groups = {}
    for label, predicate in (("same_direction_shared", lambda r: bool(set(r["old_ob"]) & set(r["event_ob"]))),
        ("both_present_different_direction", lambda r: r["old_ob"] and r["event_ob"] and not set(r["old_ob"]) & set(r["event_ob"])), 
        ("occupancy_only", lambda r: r["old_ob"] and not r["event_ob"]),
        ("closed_rejection_only", lambda r: r["event_ob"] and not r["old_ob"])):
        group = [r for r in window if predicate(r)]
        groups[label] = {"bars": len(group), "timeframes": dict(Counter(r["timeframe"] for r in group)),
            "other_channels_still_present": sum(bool(r["other_reasons"]) for r in group),
            "examples": sorted(group, key=lambda r:(r["bar_time"],r["symbol"],r["timeframe"]))[:5]}
    result = {"objective": "event_at_trigger_bar_not_future_win_rate", "groups": groups,
        "capacity_counterfactual": compare_policies(baseline, rows, manifest["sessions"]),
        "production_parity": "Every observed bar compared to independent pre-update zone hypothesis, including no-trigger bars",
        "prefix_probes": probes, "sessions": manifest["sessions"], "archive_hashes": manifest["archive_hashes"],
        "baseline_sha256": file_hash(args.baseline / "events.jsonl"), "code_sha256": file_hash(Path(__file__)),
        "code_hashes": {p: file_hash(Path(p)) for p in ("bot/domain_alarm_events.py", "bot/domain_alarm_service.py", "domain_engines/order_block/order_block.py", "domain_engines/runner.py", "research/alarm_recall_study.py", "research/alarm_politika.py", "config.py")},
        "limitations": ["domain channel before Stabil/policy/cooldown/delivery gates", "fixed-start480 native bars", "nearest prior active remaining OB per side only", "OB invalidated/fully used by native engine is not a surviving reaction", "not a future profitability label"]}
    (args.output / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k:{a:b for a,b in v.items() if a!='examples'} for k,v in groups.items()}, ensure_ascii=False),flush=True)


if __name__ == "__main__":
    main()
