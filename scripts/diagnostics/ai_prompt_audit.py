#!/usr/bin/env python3
"""Yerel promptları tarar; dört TF, replay ve kesit sınırlarını kontrol eder."""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import pandas as pd  # noqa: E402
from ai_prompt import build_from_local_cache, render_prompt  # noqa: E402
from data import mum_kapanis_ani  # noqa: E402


def check(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--data-dir", default=str(ROOT / "bot_data"))
    parser.add_argument("--main-tf", choices=("1h", "2h", "4h", "1d"), default="4h")
    parser.add_argument("--symbols", nargs="+")
    args = parser.parse_args()
    symbols = args.symbols or sorted(p.stem for p in Path(args.data_dir).glob("*.json")
                                    if not p.stem.endswith("_gunluk"))
    if not symbols:
        parser.error("yerel sembol bulunamadı")
    counts, sizes, failures = Counter(), [], []
    for symbol in symbols:
        try:
            packet = build_from_local_cache(symbol, as_of=args.as_of, main_tf=args.main_tf,
                                            data_dir=args.data_dir, research_mode="retrospective")
            text = render_prompt(packet)
            check("SWEEP" not in text and "geçiş başarısızlığı" not in text,
                  "çizilmeyen yapı olayı promptta")
            for item in packet["research"]:
                if item["id"] in text:
                    check(item["text"] in text and bool(item["source"]), "araştırma veya kaynak kaydı eksik")
            for tf, row in packet["timeframes"].items():
                check(f"{tf.upper()} GRAFİK" in text and row["status"] == "available", f"{tf}: veri yok")
                end = pd.Timestamp(row["last_close_time"])
                check(end <= pd.Timestamp(packet["as_of"]), f"{tf}: mum kesitten sonra")
                counts["tf"] += 1
                counts["bolge"] += len(row["zones"])
                counts["alinmayan_grafik_bolgesi"] += row["zone_selection_omitted"]
                for badge in row.get("chart_volume_badges", ()):
                    check(badge["direction"] in {"artis", "dusus"}, f"{tf}: geçersiz hacim rozeti")
                    check(pd.Timestamp(mum_kapanis_ani(badge["bar_open"], tf)) <= end, f"{tf}: rozet kesitten sonra")
                    check(f"×{badge['value']}" in text, f"{tf}: çizilen rozet promptta yok")
                for event in row.get("chart_events", ()):
                    check(event["type"] in {"BOS", "CHoCH"}, f"{tf}: grafikte gösterilmeyen olay")
                    if event["bar_open"]:
                        check(pd.Timestamp(mum_kapanis_ani(event["bar_open"], tf)) <= end, f"{tf}: olay kesitten sonra")
                for zone in row["replay"]["zones"]:
                    counts["replay_ok" if zone["replay_status"] == "ok" else "replay_bilinmiyor"] += 1
                    if zone["replay_status"] != "ok":
                        continue
                    check(pd.Timestamp(mum_kapanis_ani(zone["available_open"], tf)) <= end, f"{tf}: bölge kesitten sonra")
                    for episode in zone["recent_episodes"]:
                        closing_bars = list(episode["closes"])
                        if episode["next_bar_close"]:
                            closing_bars.append(episode["next_bar_close"])
                        for bar in closing_bars:
                            check(pd.Timestamp(mum_kapanis_ani(bar["bar_open"], tf)) <= end, f"{tf}: temas kesitten sonra")
                stabil = row["stabil_daily_replay"]
                counts["stabil_ok" if stabil["status"] == "ok" else "stabil_bilinmiyor"] += 1
                if stabil["status"] == "ok":
                    check(stabil["support_available_at"] is not None, f"{tf}: desteğin bilinir zamanı yok")
                    check(pd.Timestamp(stabil["support_available_at"]) <= end, f"{tf}: destek kesitten sonra")
                    for day in stabil["recent_touch_days"]:
                        check(pd.Timestamp(day["daily_close_time"]) <= end, f"{tf}: günlük temas kesitten sonra")
            counts["sembol"] += 1
            sizes.append((len(text), symbol))
        except (ValueError, OSError, KeyError, TypeError) as exc:
            failures.append((symbol, str(exc)))
    print(f"sonuç={dict(counts)}, karakter_aralığı={min(sizes) if sizes else None}..{max(sizes) if sizes else None}, hata={len(failures)}")
    for symbol, error in failures:
        print(f"{symbol}: {error}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
