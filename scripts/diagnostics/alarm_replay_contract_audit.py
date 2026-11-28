"""Read-only replay contract probes. Reports findings; changes no engine/rule.

Run: python -m scripts.diagnostics.alarm_replay_contract_audit --output var/contracts.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from research import arsiv, domain_alarm_replay as replay
from research.kayit import sembol_timeframe_gozlem


def synthetic_findings():
    times = pd.date_range("2026-11-02T10:00+03:00", periods=4, freq="h")
    frame = pd.DataFrame({"open": 10., "high": 10.2, "low": 9.8,
                          "close": 10., "volume": 100.}, index=times)
    bearish = {"event_type": "BOS", "confirmation_status": "CONFIRMED",
               "validity": "VALID", "relevance": "ACTIVE", "event_bar": 2,
               "direction": "DOWN"}
    emitted = replay.sembol_timeframe_tetikleri("TEST", "1h", frame, {"event": [bearish]})
    future_zone = {"direction": "BULLISH", "zone_lower": 9., "zone_upper": 11.,
                   "dogum_index": 20, "terminal_index": None}
    from types import SimpleNamespace
    from bot.domain_alarm_service import _yon_isareti
    mixed = _yon_isareti(SimpleNamespace(reasons=("BOS ↑", "OB ↓")))
    return {
        "live_mixed_direction_display": {"reasons": ["BOS ↑", "OB ↓"],
                                         "display": mixed, "problem_present": mixed != "◆"},
        "bearish_bos": {"event_direction": "DOWN", "replay_direction": emitted[0]["yon"],
                        "problem_present": emitted[0]["yon"] != -1},
        "future_zone_direction": {
            "zone_birth": 20, "anchor_index": 2,
            "direction_without_zone": replay._yon_tahmini([], [], 10., 1e-8, None),
            "direction_with_future_zone": replay._yon_tahmini([future_zone], [], 10., 1e-8, None),
            "problem_present": replay._yon_tahmini([future_zone], [], 10., 1e-8, None) != 0,
        },
    }


def prefix_probe(symbol, tf):
    frame = arsiv.tf_frame(symbol, tf, legacy_resample=False).tail(480)
    cutoff = 360
    full_obs = sembol_timeframe_gozlem(symbol, tf, frame)
    prefix_obs = sembol_timeframe_gozlem(symbol, tf, frame.iloc[:cutoff])
    full = replay.sembol_timeframe_tetikleri(symbol, tf, frame, full_obs)
    prefix = replay.sembol_timeframe_tetikleri(symbol, tf, frame.iloc[:cutoff], prefix_obs)
    def index(rows):
        return {r["bar_index"]: {"channels": r["kanallar"], "direction": r["yon"]}
                for r in rows if r["bar_index"] < cutoff}
    a, b = index(full), index(prefix)
    differences = [{"bar_index": k, "full": a.get(k), "prefix": b.get(k)}
                   for k in sorted(a.keys() | b.keys()) if a.get(k) != b.get(k)]
    arsiv._OBELLEK.clear()
    return {"symbol": symbol, "tf": tf, "full_bars": len(frame), "prefix_bars": cutoff,
            "full_past_events": len(a), "prefix_events": len(b),
            "differences": len(differences), "examples": differences[:12]}


def saved_results_check():
    """Recount committed rows; do not call them a new/current native replay."""
    from research.alarm_filter_audit import file_hash
    root = Path(__file__).resolve().parents[2]
    paths = [root / "docs/arastirma/sonuclar/bes_alarm_pilotu/OLAYLAR.csv.gz",
             root / "docs/arastirma/sonuclar/bes_alarm_pilotu/genis/ADAYLAR.csv.gz"]
    counts = {}
    for path in paths:
        frame = pd.read_csv(path)
        selections = [("F1", "aday"), ("F1", "teyit"), ("F2", "aday"), ("F2", "egim"),
                      ("S2", "geri_alis"), ("S2", "temiz80")]
        counts[str(path.relative_to(root))] = {
            "sha256": file_hash(path), "rows": len(frame),
            "groups": {f"{rule}/{group}": {
                "n": len(g), "up_first": int(g.bariyer.eq("LEHTE").sum()),
                "down_first": int(g.bariyer.eq("ALEYHTE").sum()),
                "ambiguous": int(g.bariyer.eq("BELIRSIZ").sum()),
                "neither": int(g.bariyer.eq("SURE").sum())}
                for rule, group in selections
                if len(g := frame.loc[frame.kural.eq(rule) & frame.grup.eq(group)])}
        }
    path = root / "docs/arastirma/sonuclar/kirilim_replay/manifest.json"
    manifest = json.loads(path.read_text())
    matches = []
    for symbol, timeframes in manifest["source_sha256"].items():
        for tf, expected in timeframes.items():
            archive = root / "backfill_data" / f"{symbol}_{tf}.csv.gz"
            matches.append(archive.exists() and file_hash(archive) == expected)
    candidates = pd.read_csv(path.parent / "adaylar.csv.gz", usecols=["anchor"])
    counts["recorded_kirilim_archive_check"] = {
        "checked_files": len(matches), "same_bytes": sum(matches),
        "latest_anchor": candidates.anchor.max(), "candidate_rows": len(candidates),
        "note": "Byte mismatch is provenance mismatch, not proof all price values changed."
    }
    return counts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    result = {"synthetic": synthetic_findings(), "saved_results": saved_results_check(), "prefix_probes": []}
    for symbol in ("THYAO", "ASELS"):
        for tf in ("1h", "2h", "4h", "1d"):
            row = prefix_probe(symbol, tf)
            result["prefix_probes"].append(row)
            print(symbol, tf, row["differences"], flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
