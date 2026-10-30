#!/usr/bin/env python3
"""Arşivden çevrimdışı çapraz piyasa hücre raporu üretir."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research.capraz_piyasa import GRAM, MACRO, run, select_discovery, stock_symbols  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--symbols", help="virgülle ayrılmış arşiv hisseleri; yoksa tüm hisseler")
    p.add_argument("--macro", default=",".join(MACRO + GRAM), help="virgülle ayrılmış makro semboller")
    p.add_argument("--order", type=int, help="birleşim üst derecesi; yoksa tümü (çok pahalı)")
    p.add_argument("--assume-lag-days", type=int, help="yalnız doğrulanmamış keşif: en az 2 gün gecikme varsay")
    p.add_argument("--availability", type=Path, help="symbol,bar_time,available_at içeren saat dilimli CSV")
    p.add_argument("--select", action="store_true", help="keşifte aday seç; doğrulama eşleşmesini ayrı yaz (çoklu test düzeltilmez)")
    p.add_argument("--output", type=Path, default=ROOT / "var/capraz_piyasa")
    args = p.parse_args()
    symbols = [x.strip().upper() for x in args.symbols.split(",") if x.strip()] if args.symbols else stock_symbols()
    names = tuple(x.strip().upper() for x in args.macro.split(",") if x.strip())
    if not names or not symbols: p.error("En az bir hisse ve makro seri gerekli")
    result = run(symbols, args.output, names=names, assume_lag_days=args.assume_lag_days,
                 max_order=args.order, availability_path=args.availability)
    if args.select:
        print(f"Keşif adayı: {select_discovery(args.output)}; selected.csv kesinleşmiş bulgu değildir")
    print(f"Mod: {result['mode']} · hisse: {len(symbols)} · kombinasyon: {result['all_subset_count']}")
    print(f"Çıktı: {args.output}; UNKNOWN ve sansür ayrı, araştırma ≠ canlı sinyal")


if __name__ == "__main__":
    main()
