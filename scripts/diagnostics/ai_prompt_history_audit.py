#!/usr/bin/env python3
"""Özet verisinin yaşını her TF'nin kapanmış bar sayısıyla ölç (yerel/offline)."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import pandas as pd  # noqa: E402
import grafik  # noqa: E402
from ai_prompt import build_from_local_cache  # noqa: E402
from ai_prompt.compact import _event_selection  # noqa: E402


def _age(frame, timestamp):
    if timestamp is None:
        return None
    try:
        t = pd.Timestamp(timestamp)
        if t.tzinfo is None or pd.isna(t):
            return None
        loc = frame.index.get_indexer([t])[0]
        return len(frame) - 1 - int(loc) if loc >= 0 else None
    except (ValueError, TypeError, OverflowError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--data-dir", default=str(ROOT / "bot_data"))
    parser.add_argument("--symbols", nargs="+")
    parser.add_argument("--json", type=Path, help="mevcut olmayan çıktı dosyası")
    args = parser.parse_args()
    symbols = args.symbols or sorted(p.stem for p in Path(args.data_dir).glob("*.json") if not p.stem.endswith("_gunluk"))
    if not symbols:
        parser.error("sembol bulunamadı")
    buckets = defaultdict(list)
    missing = Counter()
    cases = {}
    original = grafik.anlik_goruntu
    failures = []
    for symbol in symbols:
        captured = {}
        def capture(candidate, tf, frame, **kwargs):
            captured[tf] = frame
            return original(candidate, tf, frame, **kwargs)
        grafik.anlik_goruntu = capture
        try:
            packet = build_from_local_cache(symbol, as_of=args.as_of, main_tf="4h",
                                            data_dir=args.data_dir, research_mode="retrospective")
            case = {}
            for tf, row in packet["timeframes"].items():
                if row["status"] != "available":
                    raise ValueError(f"{tf}: {row['status']}")
                frame = captured[tf]
                def record(kind, timestamp):
                    age = _age(frame, timestamp)
                    if age is None:
                        missing[(tf, kind)] += 1
                    else:
                        buckets[(tf, kind)].append(age)
                    return age
                events = row.get("chart_events", [])
                selected, _ = _event_selection(events)
                for e in events:
                    age = record("olay_tumu", e.get("bar_open"))
                    if age != e.get("age_bars"):
                        raise ValueError(f"{tf}: olay bar yaşı eşleşmiyor")
                for e in selected:
                    record("olay_ozet", e.get("bar_open"))
                for b in row.get("chart_volume_badges", []):
                    age = record("hacim_rozeti", b.get("bar_open"))
                    if age != b.get("age_bars"):
                        raise ValueError(f"{tf}: hacim bar yaşı eşleşmiyor")
                for z in row.get("zones", []):
                    record("bolge_kaynak", z.get("source_open"))
                ep_ages = []
                for z in row.get("replay", {}).get("zones", []):
                    for ep in z.get("recent_episodes", []):
                        age = record("replay_son_temas", ep.get("end_open"))
                        if age != ep.get("end_age_bars"):
                            raise ValueError(f"{tf}: replay bar yaşı eşleşmiyor")
                        ep_ages.append(age)
                case[tf] = {"bars": len(frame), "olay_yas": [_age(frame, e.get("bar_open")) for e in selected],
                            "rozet_yas": [_age(frame, b.get("bar_open")) for b in row.get("chart_volume_badges", [])],
                            "replay_yas": ep_ages}
            cases[symbol] = case
        except (OSError, ValueError, TypeError, KeyError) as e:
            failures.append((symbol, str(e)))
        finally:
            grafik.anlik_goruntu = original
    summary = {}
    for tf, kind in sorted(set(buckets) | set(missing)):
        xs = buckets[(tf, kind)]
        summary[f"{tf}/{kind}"] = {"sayi": len(xs), "medyan": statistics.median(xs) if xs else None,
            "maks": max(xs) if xs else None, "30_ustu": sum(x > 30 for x in xs),
            "60_ustu": sum(x > 60 for x in xs), "90_ustu": sum(x > 90 for x in xs),
            "yas_bilinmiyor": missing[(tf, kind)]}
    result = {"as_of": args.as_of, "symbols": len(cases), "summary": summary, "cases": cases, "failures": failures}
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        with args.json.open("x", encoding="utf-8") as f:
            f.write(text + "\n")
    else:
        print(text)
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
