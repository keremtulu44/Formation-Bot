#!/usr/bin/env python3
"""Yerel grafik verisi ve replay'den AI'a yapıştırılabilir prompt üret (ağ yok)."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ai_prompt import build_from_local_cache, render_prompt, render_compact_prompt  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("symbol", help="Yerel JSON sembolü, ör. BIMAS")
    parser.add_argument("--as-of", required=True, help="Zaman dilimli kesim, ör. 2026-09-25T18:30:00+03:00")
    parser.add_argument("--main-tf", choices=("1h", "2h", "4h", "1d"), default="4h")
    parser.add_argument("--data-dir", default=str(ROOT / "bot_data"))
    parser.add_argument("--research-mode", choices=("strict", "retrospective"), default="strict")
    parser.add_argument("--format", choices=("compact", "full"), default="compact",
                        help="Kompakt: hedef 4000, en fazla 4500; full: eksiksiz eski biçim")
    parser.add_argument("--history-bars", type=int, help="Deneysel: her TF için son N kapanmış mum öncelikli")
    parser.add_argument("--output", type=Path, help="İsteğe bağlı UTF-8 çıktı dosyası; yoksa stdout")
    args = parser.parse_args()
    if args.history_bars is not None and args.format == "full":
        parser.error("--history-bars sadece compact biçiminde kullanılabilir")
    try:
        packet = build_from_local_cache(args.symbol, as_of=args.as_of, main_tf=args.main_tf,
                                        data_dir=args.data_dir, research_mode=args.research_mode)
        prompt = (render_compact_prompt(packet, **({"history_bars": args.history_bars}
                                                  if args.history_bars is not None else {}))
                  if args.format == "compact" else render_prompt(packet))
    except (ValueError, OSError) as exc:
        print(f"Prompt hazırlanamadı: {exc}", file=sys.stderr)
        return 2
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        try:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(prompt)
        except OSError as exc:
            print(f"Çıktı oluşturulamadı (mevcut dosya üzerine yazılmaz): {exc}", file=sys.stderr)
            return 2
        print(f"{args.output}: {len(prompt)} karakter", file=sys.stderr)
    else:
        print(prompt, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
