"""Tarihsel, doğrulanmamış keşif pilotunu var/ altında yeniden üretir."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
(ROOT / "var").mkdir(exist_ok=True)
import json
import pandas as pd
from research.capraz_piyasa import (
    macro_load,
    macro_context,
    stock_symbols,
    read_frame,
    stock_events,
)
from research.arsiv import arsiv_koku

root = arsiv_koku()
macro, sources = macro_load(ROOT / "capraz_piyasa_data")
results = []
failures = {}
for symbol in stock_symbols():
    try:
        frame = read_frame(root / f"{symbol}_1d.csv.gz")
        days = pd.DatetimeIndex([pd.Timestamp(x.date()) for x in frame.index])
        split = days[int(len(days) * 0.7)]
        ctx = macro_context(
            {k: macro[k] for k in ("XU100", "BRENT")}, days, 0.5, assume_lag_days=2
        )
        event = stock_events(frame, 1.0, 5)
        joined = event.join(ctx[["XU100", "BRENT"]])
        condition = (joined.XU100 == "DOWN") & (joined.BRENT == "DOWN")
        for label, mask in [
            ("discovery", (joined.index < split) & (joined.end_day < split)),
            ("validation", joined.index >= split),
        ]:
            subset = joined[mask & condition]
            valid = subset[subset.outcome != "UNKNOWN"]
            base = joined[mask & (joined.outcome != "UNKNOWN")]
            # Aynı makro bar tekrarı ve örtüşen sonuç penceresi tek sayılır.
            kept = []
            last_end = None
            seen = set()
            for day, row in valid.iterrows():
                cutoff = day - pd.Timedelta(days=2)
                pair = tuple(
                    pd.DatetimeIndex(macro[k][0].index.date)[
                        int(
                            pd.DatetimeIndex(macro[k][0].index.date).searchsorted(
                                cutoff, side="right"
                            )
                            - 1
                        )
                    ]
                    for k in ("XU100", "BRENT")
                )
                if pair in seen or (last_end is not None and day <= last_end):
                    continue
                kept.append(day)
                seen.add(pair)
                last_end = row.end_day
            valid = valid.loc[kept]
            v = valid.outcome.value_counts()
            b = base.outcome.value_counts()
            n = len(valid)
            results.append(
                {
                    "symbol": symbol,
                    "period": label,
                    "split": str(split.date()),
                    "signal_rows": len(subset),
                    "n": n,
                    "up": int(v.get("UP", 0)),
                    "down": int(v.get("DOWN", 0)),
                    "flat": int(v.get("FLAT", 0)),
                    "up_pct": 100 * v.get("UP", 0) / n if n else None,
                    "down_pct": 100 * v.get("DOWN", 0) / n if n else None,
                    "baseline_n": len(base),
                    "baseline_up_pct": 100 * b.get("UP", 0) / len(base)
                    if len(base)
                    else None,
                    "baseline_down_pct": 100 * b.get("DOWN", 0) / len(base)
                    if len(base)
                    else None,
                    "first": str(valid.index.min().date()) if n else None,
                    "last": str(valid.index.max().date()) if n else None,
                }
            )
    except Exception as e:
        failures[symbol] = str(e)
df = pd.DataFrame(results)
df.to_csv(ROOT / "var/xu100_brent_tekil.csv", index=False)
print(
    "symbols", df.symbol.nunique(), "failures", json.dumps(failures, ensure_ascii=False)
)
print(
    "sources",
    json.dumps({k: sources[k] for k in ("XU100", "BRENT")}, ensure_ascii=False),
)
for period in ["discovery", "validation"]:
    d = df[(df.period == period) & (df.n > 0)]
    print("\n", period, "n", d.n.describe().to_dict(), "symbols", len(d))
    print("UP top 15")
    print(
        d.sort_values(["up_pct", "n"], ascending=False).head(15).to_string(index=False)
    )
    print("DOWN top 15")
    print(
        d.sort_values(["down_pct", "n"], ascending=False)
        .head(15)
        .to_string(index=False)
    )
