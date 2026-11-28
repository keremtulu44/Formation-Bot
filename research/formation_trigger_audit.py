"""Audit WHEN formation alerts become eligible, not future trade returns.

Private engines and live close/level helpers; no notifier, state store or API.
This is fixed-start lifecycle replay, not rolling live scan/delivery parity.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
from types import MethodType

import pandas as pd

import config
from bot.lifecycle_events import _closed_formation_event_confirmed
from bot.security import _alert_break_level
from patterns import ArgentEngine
from patterns.mathutil import f_line_price
from research.alarm_filter_audit import file_hash
from research.alarm_recall_study import closed_archive
from research import arsiv


def finite(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def snapshots(symbol, tf, frame):
    engine = ArgentEngine(profile=config.PROFILE, timeframe=tf)
    engine._key = None  # Never access live formation identity stores.
    original = engine._process_bar
    rows = []

    def observe(self, index):
        previous = self.pattern_state
        original(index)
        snap = self._snapshot(previous, self.events, frame.iloc[:index + 1])
        active = snap.active
        # Invalidation is a separate delivered-confirmation-dependent path.
        if active is None or snap.state not in {"KIRILIM_TEYITLI", "RETEST_BASARILI"}:
            return
        level = finite(_alert_break_level(active, snap.break_dir, snap.state))
        projected = finite(f_line_price(self.break_line_x1, self.break_line_y1,
                                       self.break_line_x2, self.break_line_y2, index))
        price = float(frame.close.iloc[index])
        q = finite(snap.effective_quality if snap.effective_quality is not None else active.raw_quality)
        minimum = float(config.ALERT_MIN_QUALITY.get(tf, config.ALERT_MIN_QUALITY_GLOBAL))
        close_pass = _closed_formation_event_confirmed(snap.state, snap.break_dir, price, level)
        event_level = finite(_alert_break_level(active, snap.break_dir, snap.state, bar_index=index))
        projected_pass = _closed_formation_event_confirmed(snap.state, snap.break_dir, price, projected)
        event_pass = _closed_formation_event_confirmed(snap.state, snap.break_dir, price, event_level)
        if event_level is None or projected is None or not math.isclose(event_level, projected, rel_tol=1e-12, abs_tol=1e-9):
            raise ValueError(f"Alert boundary differs from engine line: {symbol}/{tf}/{index}")
        atr = finite(self.safe_atr)
        rows.append({"symbol": symbol, "timeframe": tf, "bar_index": index,
            "bar_time": pd.Timestamp(frame.index[index]).isoformat(),
            "formation": f"{symbol}|{tf}|{active.identity}", "pattern": str(active.pattern_type),
            "state": snap.state, "state_start": self.pattern_state_bar,
            "candidate_bar": self.break_candidate_bar, "confirmed_bar": self.break_confirmed_bar,
            "state_age_bars": index - self.pattern_state_bar,
            "candidate_age_bars": index - self.break_candidate_bar,
            "direction": int(snap.break_dir), "quality": q, "minimum": minimum,
            "close": price, "level_used": level, "line_at_current_bar": projected,
            "atr": atr, "quality_pass": q is not None and q >= minimum,
            "legacy_fixed_close_pass": close_pass, "projected_close_pass": projected_pass,
            "event_bar_level": event_level, "event_bar_close_pass": event_pass,
            "eligible_before_delivery": q is not None and q >= minimum and close_pass,
            "eligible_after_alignment": q is not None and q >= minimum and event_pass,
            "distance_from_line_atr": snap.break_dir * (price - projected) / atr if atr and atr > 0 and projected is not None else None})

    engine._process_bar = MethodType(observe, engine)
    engine.process(frame, tam_yeniden=True)
    return rows


def summarize(rows, first, last):
    def in_window(row):
        date = pd.Timestamp(row["bar_time"]).tz_convert("Europe/Istanbul").strftime("%Y-%m-%d")
        return first <= date <= last
    window = [r for r in rows if in_window(r)]
    episodes = defaultdict(list)
    for row in rows:
        episodes[(row["formation"], row["state"], row["state_start"])].append(row)
    first_eligible, aligned_eligible, onsets, blocked, rescued, earlier, lost = [], [], [], [], [], [], []
    for group in episodes.values():
        onset = group[0]
        if in_window(onset):
            onsets.append(onset)
            if not any(r["eligible_before_delivery"] for r in group):
                blocked.append(onset)
        eligible = next((r for r in group if r["eligible_before_delivery"]), None)
        if eligible and in_window(eligible):
            first_eligible.append(eligible)
        aligned = next((r for r in group if r["eligible_after_alignment"]), None)
        if aligned and in_window(aligned):
            aligned_eligible.append(aligned)
            if eligible is None:
                rescued.append(aligned)
            elif aligned["bar_index"] < eligible["bar_index"]:
                earlier.append({"symbol": aligned["symbol"], "timeframe": aligned["timeframe"],
                    "state": aligned["state"], "bar_time": aligned["bar_time"],
                    "legacy_bar_time": eligible["bar_time"],
                    "bars_earlier": eligible["bar_index"] - aligned["bar_index"]})
        if eligible and in_window(eligible) and aligned is None:
            lost.append(eligible)
    def stats(group):
        distances = [r["distance_from_line_atr"] for r in group if r["distance_from_line_atr"] is not None]
        return {"episodes": len(group), "states": dict(Counter(r["state"] for r in group)),
            "state_age_bars": dict(sorted(Counter(r["state_age_bars"] for r in group).items())),
            "candidate_age_bars": dict(sorted(Counter(r["candidate_age_bars"] for r in group).items())),
            "median_distance_from_line_atr": float(pd.Series(distances).median()) if distances else None,
            "distance_gt_1atr_descriptive_only": sum(d > 1 for d in distances)}
    mismatch = [r for r in window if r["legacy_fixed_close_pass"] != r["projected_close_pass"]]
    return {"window_state_rows": len(window), "state_onsets": stats(onsets),
        "first_eligible_legacy_before_delivery": stats(first_eligible),
        "first_eligible_aligned_before_delivery": stats(aligned_eligible),
        "alignment_effect": {"rescued_state_episodes": stats(rescued),
            "earlier_state_episodes": len(earlier), "earlier_examples": earlier[:12],
            "lost_state_episodes": len(lost), "rescued_examples": rescued[:12]},
        "episodes_never_eligible_in_observed_state": stats(blocked),
        "close_gate_disagreement_rows": len(mismatch),
        "quality_passing_close_gate_disagreement_rows": sum(r["quality_pass"] for r in mismatch),
        "disagreement_direction": dict(Counter("fixed_pass_line_fail" if r["legacy_fixed_close_pass"] else "fixed_fail_line_pass" for r in mismatch)),
        "first_eligible_examples": first_eligible[:12], "mismatch_examples": mismatch[:12]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--symbols", default="")
    parser.add_argument("--first", default="2026-10-19")
    parser.add_argument("--last", default="2026-11-18")
    args = parser.parse_args(argv)
    if args.output.exists() and any(args.output.iterdir()):
        raise ValueError("New empty output directory required")
    args.output.mkdir(parents=True, exist_ok=True)
    symbols = sorted(set(args.symbols.split(","))) if args.symbols else sorted(set(config.ACTIVE_STOCKS) & set(arsiv.arsiv_sembolleri(native_only=True)))
    rows, probes, hashes = [], [], {}
    for symbol in symbols:
        for tf in ("1h", "2h", "4h", "1d"):
            frame = closed_archive(symbol, tf, 480)
            if len(frame) < 100:
                raise ValueError(f"Insufficient bars {symbol}/{tf}")
            current = snapshots(symbol, tf, frame)
            cut = len(frame) * 3 // 4
            prefix = snapshots(symbol, tf, frame.iloc[:cut])
            if [r for r in current if r["bar_index"] < cut] != prefix:
                raise ValueError(f"Noncausal {symbol}/{tf}")
            probes.append({"symbol": symbol, "timeframe": tf, "cut": cut, "prefix_equal": True})
            rows.extend(current)
            name = f"{symbol}_{tf}.csv.gz"
            hashes[name] = file_hash(arsiv.arsiv_koku() / name)
            print(f"{len(probes)}/{len(symbols)*4} {symbol} {tf}", flush=True)
    with (args.output / "rows.jsonl").open("w") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    result = summarize(rows, args.first, args.last)
    result["manifest"] = {"first": args.first, "last": args.last, "symbols": symbols,
        "prefix_probes": probes, "archive_hashes": hashes,
        "code_hashes": {p: file_hash(Path(p)) for p in ("research/formation_trigger_audit.py", "patterns/lifecycle.py", "patterns/candidate.py", "patterns/mathutil.py", "bot/security.py", "bot/scan.py", "bot/lifecycle_events.py", "tutarlilik.py", "config.py")},
        "limitations": ["fixed-start480 native bars, not rolling production replay",
            "quality + live boundary gates only, not delivered notifications",
            "no scan schedule, macro permission, notifier continuity/MTF/rate/repeat gates",
            "invalidation and Stabil/domain paths are separate, not counted here",
            "state episodes can overlap in price; no trade returns or win-rate optimization"]}
    (args.output / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: v for k,v in result.items() if k not in {"manifest", "first_eligible_examples", "mismatch_examples"}}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
