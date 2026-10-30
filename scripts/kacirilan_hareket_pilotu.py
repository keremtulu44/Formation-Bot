#!/usr/bin/env python3
"""Küçük fiyat merkezli as-of Replay deneyini yeniden üret."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd  # noqa: E402
from research.kacirilan_pilot import series, summarize  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", default="ASTOR,THYAO,AKBNK,GARAN,TUPRS")
    parser.add_argument("--output", type=Path, default=ROOT / "var/kacirilan_pilot")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows, meta = [], {}
    for name in (s.strip().upper() for s in args.symbols.split(",") if s.strip()):
        if not name.isascii() or not name.isalnum(): raise ValueError("geçersiz sembol")
        for tf, limit in (("1d", 400), ("1h", 800)):
            key = f"{name}:{tf}"
            try:
                data, info = series(name, tf, ROOT / "backfill_data" / f"{name}_{tf}.csv.gz", limit)
                rows.extend(data)
                meta[key] = info
                print(key, len(data), "pencere")
            except (ValueError, OSError, KeyError) as e:
                meta[key] = {"error": str(e)}
                print(key, "HATA", str(e))
    if not rows: raise SystemExit("Geçerli pilot penceresi yok")
    df = pd.DataFrame(rows)
    df.to_csv(args.output / "windows.csv", index=False)
    summarize(df).to_csv(args.output / "summary.csv", index=False)
    (args.output / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    print("Çıktı:", args.output, "· canlı alarm teslimi ölçülmedi")


if __name__ == "__main__":
    main()
