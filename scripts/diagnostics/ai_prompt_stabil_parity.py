#!/usr/bin/env python3
"""Yerel günlük arşivde Stabil temas sırasını araştırma referansıyla karşılaştır.

İleri sonuç üretmez veya ağ kullanmaz. Yalnız sırası güvenle bilinen
kesitler karşılaştırılır; diğerleri ayrı sayılır. `backfill_data/` gerekli.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
from ai_prompt.stabil_replay import daily_support_replay  # noqa: E402
from domain_engines.stabil.runtime import prepare_causal_ohlcv  # noqa: E402
from domain_engines.stabil.stabil_support_lifecycle import (  # noqa: E402
    build_daily_support_observations, build_support_lifecycle_timeline,
)
from research.arsiv import tf_frame  # noqa: E402
from research.stabil_support_resistance_compare import legacy_daily_touch_sequence  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", required=True, help="Zaman dilimli kesit")
    parser.add_argument("--archive", default=str(ROOT / "backfill_data"))
    parser.add_argument("--symbols", nargs="+", default=None,
                        help="Semboller; verilmezse bot_data saatlik JSON'ları")
    args = parser.parse_args()
    cutoff = pd.Timestamp(args.as_of)
    if pd.isna(cutoff) or cutoff.tzinfo is None:
        parser.error("--as-of zaman dilimli olmalı")
    symbols = args.symbols or sorted(p.stem for p in (ROOT / "bot_data").glob("*.json")
                                    if not p.stem.endswith("_gunluk"))
    if not symbols:
        parser.error("sembol bulunamadı")
    prefixes = known_count = touch_days = 0
    failures = []
    for symbol in symbols:
        try:
            daily = tf_frame(symbol, "1d", kok=args.archive)
            clean, err = prepare_causal_ohlcv(daily, symbol=symbol, timeframe="1d", cutoff_close=cutoff)
            if err:
                raise ValueError(err)
            observations = build_daily_support_observations(clean)
            timeline = build_support_lifecycle_timeline(observations, include_prefix_events=False)
            expected, known = legacy_daily_touch_sequence(observations, timeline)
            for i in range(len(observations)):
                result = daily_support_replay(observations[:i + 1], timeline[:i + 1])
                prefixes += 1
                if result["status"] != "ok" or not result["sequence_known"]:
                    continue
                known_count += 1
                if not known[i] or expected[i] != result["observed_count"]:
                    raise AssertionError(f"{observations[i].timestamp}: referans={expected[i]}, yeni={result['observed_count']}")
                if result["recent_touch_days"] and result["recent_touch_days"][-1]["daily_close_time"] == str(observations[i].timestamp):
                    touch_days += 1
        except (ValueError, OSError, AssertionError) as exc:
            failures.append((symbol, str(exc)))
    print(f"sembol={len(symbols)}, günlük_kesit={prefixes}, sırası_bilinen={known_count}, "
          f"temas_günü={touch_days}, hata={len(failures)}")
    for symbol, error in failures:
        print(f"{symbol}: {error}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
