#!/usr/bin/env python3
"""Kompakt promptun grafik, seçim, zaman ve bütçe sözleşmesini yerelde denetle."""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import pandas as pd  # noqa: E402
from ai_prompt import build_from_local_cache, render_compact_prompt  # noqa: E402
from ai_prompt.builder import TF_ORDER, _fmt  # noqa: E402
from ai_prompt.compact import _event_selection, _range, _size, _time, _zone  # noqa: E402
from data import mum_kapanis_ani  # noqa: E402


def check(test: bool, message: str) -> None:
    if not test:
        raise ValueError(message)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--as-of", required=True)
    p.add_argument("--main-tf", choices=TF_ORDER, default="4h")
    p.add_argument("--data-dir", default=str(ROOT / "bot_data"))
    p.add_argument("--symbols", nargs="+")
    p.add_argument("--research-mode", choices=("strict", "retrospective"), default="retrospective")
    p.add_argument("--history-bars", type=int, default=60, help="Deneysel TF başına mum penceresi")
    args = p.parse_args()
    symbols = args.symbols or sorted(x.stem for x in Path(args.data_dir).glob("*.json") if not x.stem.endswith("_gunluk"))
    if not symbols:
        p.error("sembol bulunamadı")
    counts, sizes, failures = Counter(), [], []
    for symbol in symbols:
        try:
            packet = build_from_local_cache(symbol, as_of=args.as_of, main_tf=args.main_tf,
                                            data_dir=args.data_dir, research_mode=args.research_mode)
            text = render_compact_prompt(packet, history_bars=args.history_bars)
            check(_size(text) <= 4500, "Unicode/UTF-16 üst sınırı aşıldı")
            year = pd.Timestamp(packet["as_of"]).tz_convert("Europe/Istanbul").year
            counts["hedef_4000" if len(text) <= 4000 else "4001_4500"] += 1
            for i, tf in enumerate(TF_ORDER):
                row = packet["timeframes"][tf]
                check(f"{tf.upper()} GRAFİK" in text, f"{tf} başlığı eksik")
                next_section = f"{TF_ORDER[i+1].upper()} GRAFİK" if i < len(TF_ORDER) - 1 else f"{packet['main_tf'].upper()} REPLAY"
                section = text.split(f"{tf.upper()} GRAFİK", 1)[1].split(next_section, 1)[0]
                if row["status"] != "available":
                    check("bilinmiyor" in section, f"{tf}: çizim hatası gizlendi")
                    continue
                end = pd.Timestamp(row["last_close_time"])
                check(end <= pd.Timestamp(packet["as_of"]), f"{tf}: kesit sonrası kapanış")
                counts["tf"] += 1
                all_events = row["chart_events"]
                chosen, omitted = _event_selection(all_events, history_bars=args.history_bars)
                if args.history_bars is not None:
                    counts["korunan_eski_olay"] += sum(isinstance(e.get("age_bars"), int) and e["age_bars"] >= args.history_bars for e in chosen)
                counts["olay"] += len(all_events)
                counts["bos"] += sum(e["type"] == "BOS" for e in all_events)
                counts["choch"] += sum(e["type"] == "CHoCH" for e in all_events)
                counts["3_veya_ustu_bos_tf"] += sum(e["type"] == "BOS" for e in all_events) >= 3
                counts["olay_ozet_disi"] += omitted
                if omitted:
                    check(f"{omitted} diğer grafik olayı özet dışı" in section, f"{tf}: olay atlaması gizlendi")
                for event in chosen:
                    arrow = {"yukarı": "↑", "aşağı": "↓"}.get(event.get("direction"), "?")
                    label = f"{_time(event.get('bar_open'), year)} {event.get('type')} {arrow}{_fmt(event.get('level'))}"
                    check(label in section, f"{tf}: seçilen olay eksik {label}")
                    if event.get("bar_open"):
                        check(pd.Timestamp(mum_kapanis_ani(event["bar_open"], tf)) <= end, f"{tf}: olay gelecek")
                for zone in row["zones"]:
                    check(_zone(zone) in section, f"{tf}: grafik bölgesi eksik {_range(zone)}")
                    counts["grafik_bolgesi"] += 1
                badges = row["chart_volume_badges"]
                shown = 0
                for b in badges:
                    label = f"{_time(b['bar_open'], year)} {'A' if b['direction'] == 'artis' else 'K'}×{b['value']}"
                    shown += label in section
                    check(pd.Timestamp(mum_kapanis_ani(b['bar_open'], tf)) <= end, f"{tf}: rozet gelecek")
                omitted_badges = len(badges) - shown
                counts["hacim_rozeti"] += len(badges)
                counts["hacim_ozet_disi"] += omitted_badges
                if omitted_badges:
                    check(f"{omitted_badges} diğer grafik rozeti özette yok" in section, f"{tf}: hacim atlaması gizlendi")
            main = packet["timeframes"][packet["main_tf"]]
            replay = text.split(f"{packet['main_tf'].upper()} REPLAY", 1)[1]
            if main["status"] == "available":
                for zone in main["replay"]["zones"]:
                    check(_zone(zone) in replay, f"ana TF replay bölgesi eksik {_range(zone)}")
                    counts["replay_bolgesi"] += 1
                    if zone["replay_status"] == "ok":
                        check(f"{_zone(zone)}: {zone['episodes']} grup" in replay, "replay temas sayısı eksik")
                        check(pd.Timestamp(mum_kapanis_ani(zone['available_open'], packet['main_tf'])) <= pd.Timestamp(main['last_close_time']), "replay bölgesi gelecek")
                        for ep in zone["recent_episodes"]:
                            bars = ep["closes"] + ([ep["next_bar_close"]] if ep["next_bar_close"] else [])
                            for bar in bars:
                                check(pd.Timestamp(mum_kapanis_ani(bar['bar_open'], packet['main_tf'])) <= pd.Timestamp(main['last_close_time']), "replay kapanışı gelecek")
            if args.history_bars is not None:
                counts["replay_eski_detay_ozet_disi"] += sum(int(n) for n in re.findall(r"(\d+) eski temasın kapanış ayrıntısı özet dışında", text))
            if args.research_mode == "strict":
                for item in packet["research"]:
                    if not item["included"]:
                        check(item["text"] not in text, "kesit sonrası bulgu strict promptta")
            counts["sembol"] += 1
            sizes.append((len(text), symbol))
        except (ValueError, OSError, KeyError, TypeError, IndexError) as exc:
            failures.append((symbol, str(exc)))
    print(f"sonuç={dict(counts)}, karakter_aralığı={min(sizes) if sizes else None}..{max(sizes) if sizes else None}, hata={len(failures)}")
    for symbol, error in failures:
        print(f"{symbol}: {error}", file=sys.stderr)
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
