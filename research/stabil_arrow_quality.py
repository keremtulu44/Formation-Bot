"""Inspect raw local archive rows used by the Stabil arrow study.

This is not a trading-session completeness or corporate-action audit. Zero
volume is counted but not treated as an OHLC error.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.arsiv import arsiv_koku
from research.stabil_replay import select_bist_equity_universe

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs/arastirma/stabil_ok_replay_2026_11_05/veri_kalite.json"


def audit_file(path: Path) -> dict[str, int]:
    frame = pd.read_csv(path)
    o, h, low, close = (pd.to_numeric(frame[name], errors="coerce")
                        for name in ("open", "high", "low", "close"))
    volume = pd.to_numeric(frame["volume"], errors="coerce")
    times = pd.to_datetime(frame["bar_time"], utc=True, errors="coerce")
    return {
        "rows": len(frame),
        "nan_ohlc_rows": int((o.isna() | h.isna() | low.isna() | close.isna()).sum()),
        "nonfinite_ohlc_rows": int((~np.isfinite(o) | ~np.isfinite(h) | ~np.isfinite(low) | ~np.isfinite(close)).sum()),
        "nonpositive_ohlc_rows": int(((o <= 0) | (h <= 0) | (low <= 0) | (close <= 0)).sum()),
        "invalid_ohlc_rows": int(((h < low) | (h < o) | (h < close) | (low > o) | (low > close)).sum()),
        "negative_or_nonfinite_volume_rows": int(((volume < 0) | ~np.isfinite(volume)).sum()),
        "zero_volume_rows": int((volume == 0).sum()),
        "invalid_timestamp_rows": int(times.isna().sum()),
        "duplicate_timestamp_rows": int(times[times.notna()].duplicated().sum()),
    }


def audit(root: Path) -> dict:
    symbols = select_bist_equity_universe(10000, kok=root)
    if not symbols:
        raise ValueError("no eligible archive symbols")
    result = {"symbols": len(symbols), "files": 0, "per_file_with_invalid": {}}
    for symbol in symbols:
        for tf in ("1h", "1d"):
            path = root / f"{symbol}_{tf}.csv.gz"
            counts = audit_file(path)
            result["files"] += 1
            for key, value in counts.items():
                result[key] = result.get(key, 0) + value
            bad = {key: value for key, value in counts.items() if value and key not in ("rows", "zero_volume_rows")}
            if bad:
                result["per_file_with_invalid"][path.name] = bad
    result["scope"] = "raw archive rows, including bars excluded by capture cutoff; not a session completeness audit"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=arsiv_koku())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = audit(args.archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
