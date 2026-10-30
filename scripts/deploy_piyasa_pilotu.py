"""Tarihsel, doğrulanmamış keşif pilotunu var/ altında yeniden üretir."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from itertools import combinations, product
from collections import Counter
import csv, hashlib, json
import pandas as pd
from config import BIST_50, sembol_turu
from research.capraz_piyasa import (
    MACRO,
    macro_load,
    macro_context,
    read_frame,
    stock_events,
)

archive = ROOT / "backfill_data"
data, diagnostics = macro_load(ROOT / "capraz_piyasa_data")
stocks = [s for s in BIST_50 if sembol_turu(s) == "hisse"]
if len(sys.argv) > 1:
    requested = [s.strip().upper() for s in sys.argv[1].split(",") if s.strip()]
    if not requested or any(s not in stocks for s in requested):
        raise SystemExit(
            "Yalnız varsayılan deploy hisselerinden virgülle seçim yapılabilir"
        )
    stocks = requested
macro_names = list(MACRO)
subsets = [(s,) for s in macro_names] + list(combinations(macro_names, 2))
output = ROOT / "var/deploy_piyasa_pilotu/DEPLOY_PIYASA_PILOT.csv"
output.parent.mkdir(parents=True, exist_ok=True)
fields = [
    "symbol",
    "macro_symbols",
    "condition",
    "horizon",
    "period",
    "stock_split",
    "raw_condition_n",
    "unknown_condition_n",
    "quality_unknown_n",
    "censored_n",
    "n",
    "up",
    "flat",
    "down",
    "up_pct",
    "flat_pct",
    "down_pct",
    "baseline_n",
    "baseline_up_pct",
    "baseline_flat_pct",
    "baseline_down_pct",
    "first",
    "last",
]
meta = {
    "stocks": stocks,
    "stock_count": len(stocks),
    "stock_universe_source": "config.BIST_50 default, observed recent Supabase daily caches; STOCK_UNIVERSE env may override",
    "macro": macro_names,
    "thresholds": {"macro_atr": 0.5, "stock_atr": 1.0},
    "horizons": [1, 5, 10],
    "assumed_lag_days": 2,
    "mode": "UNVERIFIED_EXPLORATION",
    "sources": diagnostics,
    "skipped": {},
    "stock_sha256": {},
    "cells": 0,
}
cache = {}
with output.open("w", newline="", encoding="utf-8-sig") as file:
    writer = csv.DictWriter(file, fieldnames=fields)
    writer.writeheader()
    for symbol in stocks:
        try:
            path = archive / f"{symbol}_1d.csv.gz"
            f = read_frame(path)
            idx = pd.DatetimeIndex([pd.Timestamp(t.date()) for t in f.index])
            if idx.has_duplicates:
                raise ValueError("duplicate days")
            split = idx[int(len(idx) * 0.7)]
            key = tuple(idx)
            if key not in cache:
                ctx = macro_context(data, idx, 0.5, assume_lag_days=2)
                # Date labels from each independently last available bar under lag assumption.
                for name in macro_names:
                    if name in data:
                        dates = pd.DatetimeIndex(data[name][0].index.date)
                        positions = (
                            dates.searchsorted(idx - pd.Timedelta(days=2), side="right")
                            - 1
                        )
                        ctx["@" + name] = [
                            str(dates[p].date()) if p >= 0 else "" for p in positions
                        ]
                    else:
                        ctx["@" + name] = ""
                cache[key] = ctx
            ctx = cache[key]
            for h in (1, 5, 10):
                joined = stock_events(f, 1.0, h).join(ctx)
                for period in ("discovery", "validation"):
                    part = (
                        joined[(joined.index < split) & (joined.end_day < split)]
                        if period == "discovery"
                        else joined[joined.index >= split]
                    )
                    base = part[part.outcome != "UNKNOWN"]
                    # A regular nonoverlapping reference grid per stock and period.
                    kept = []
                    last = None
                    for day, row in base.iterrows():
                        if last is not None and day <= last:
                            continue
                        kept.append(day)
                        last = row.end_day
                    b = base.loc[kept].outcome.value_counts()
                    bn = len(kept)
                    for subset in subsets:
                        unknown = int(
                            part[list(subset)].eq("UNKNOWN").any(axis=1).sum()
                        )
                        known = part[~part[list(subset)].eq("UNKNOWN").any(axis=1)]
                        grouped = {
                            k if isinstance(k, tuple) else (k,): g
                            for k, g in known.groupby(
                                list(subset), sort=False, dropna=False
                            )
                        }
                        for state in product(
                            ("UP", "FLAT", "DOWN"), repeat=len(subset)
                        ):
                            g = grouped.get(state)
                            counts = Counter()
                            raw = quality = censored = 0
                            first = last_day = None
                            last_end = None
                            seen = set()
                            if g is not None:
                                raw = len(g)
                                quality = int((g.reason == "QUALITY").sum())
                                censored = int((g.reason == "CENSORED").sum())
                                for day, row in g[g.outcome != "UNKNOWN"].iterrows():
                                    used = tuple(row["@" + k] for k in subset)
                                    if used in seen or (
                                        last_end is not None and day <= last_end
                                    ):
                                        continue
                                    seen.add(used)
                                    last_end = row.end_day
                                    counts[row.outcome] += 1
                                    if first is None:
                                        first = day
                                    last_day = day
                            n = sum(counts.values())
                            row = {
                                "symbol": symbol,
                                "macro_symbols": "+".join(subset),
                                "condition": " & ".join(
                                    f"{s}={v}" for s, v in zip(subset, state)
                                ),
                                "horizon": h,
                                "period": period,
                                "stock_split": str(split.date()),
                                "raw_condition_n": raw,
                                "unknown_condition_n": unknown,
                                "quality_unknown_n": quality,
                                "censored_n": censored,
                                "n": n,
                                "up": counts["UP"],
                                "flat": counts["FLAT"],
                                "down": counts["DOWN"],
                                "up_pct": 100 * counts["UP"] / n if n else "",
                                "flat_pct": 100 * counts["FLAT"] / n if n else "",
                                "down_pct": 100 * counts["DOWN"] / n if n else "",
                                "baseline_n": bn,
                                "baseline_up_pct": 100 * b.get("UP", 0) / bn
                                if bn
                                else "",
                                "baseline_flat_pct": 100 * b.get("FLAT", 0) / bn
                                if bn
                                else "",
                                "baseline_down_pct": 100 * b.get("DOWN", 0) / bn
                                if bn
                                else "",
                                "first": str(first.date()) if first is not None else "",
                                "last": str(last_day.date())
                                if last_day is not None
                                else "",
                            }
                            writer.writerow(row)
                            meta["cells"] += 1
            meta["stock_sha256"][symbol] = hashlib.sha256(path.read_bytes()).hexdigest()
            print(symbol, "ok", flush=True)
        except (ValueError, OSError, KeyError) as e:
            meta["skipped"][symbol] = str(e)
            print(symbol, "error", e, flush=True)
(output.parent / "DEPLOY_PIYASA_PILOT_META.json").write_text(
    json.dumps(meta, ensure_ascii=False, indent=2)
)
print("Total cells", meta["cells"], "errors", meta["skipped"])
