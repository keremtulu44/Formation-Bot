"""Create deterministic, nonrepresentative visual examples for the replay report."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd

from domain_engines.stabil import prepare_causal_ohlcv
from research.arsiv import arsiv_koku, tf_frame
from research.stabil_arrow_context_replay import capture_cutoffs, closed_at_capture
from research.stabil_resistance_replay import DEFAULT_OUTPUT, ROOT, native_mirror, project_daily_at_bar_open


def pick_examples(events: pd.DataFrame) -> list[tuple[str, str, pd.Series]]:
    base = events.loc[(events.model == "MIRROR_P4") & (events.period == "Y2026") & (events.status_8 == "VALID")]
    choices = [
        ("01_test_red", "Temas / aşağı önce",
         base.loc[(base.event == "TEST") & (base.contact == "WICK_TOUCH_CLOSE_AT_OR_BELOW") &
                  (base.first_1atr_8 == "DOWN_FIRST")]),
        ("02_kirilim_tutunma", "Yukarı kırılım / sonraki temas üstte kapanış",
         base.loc[(base.event == "BREAK_UP") & (base.first_retest_8 == "TOUCH_CLOSE_ABOVE")]),
        ("03_kirilim_geri_donus", "Yukarı kırılım / sonraki temas çizgiye veya altına kapanış",
         base.loc[(base.event == "BREAK_UP") & (base.first_retest_8 == "TOUCH_CLOSE_AT_OR_BELOW")]),
    ]
    result = []
    for slug, title, subset in choices:
        if not subset.empty:
            # First chronological occurrence in this deliberately outcome-selected
            # class, not a random or representative example.
            chosen = subset.sort_values(["event_close_time", "symbol", "bar_index"]).iloc[0]
            result.append((slug, title, chosen))
    return result


def plot_example(slug: str, title: str, row: pd.Series, output: Path, archive: Path) -> dict:
    symbol, i = str(row.symbol), int(row.bar_index)
    cut = capture_cutoffs(symbol, str(archive))
    daily_raw = closed_at_capture(tf_frame(symbol, "1d", archive), "1d", cut["1d"])
    h4_raw = closed_at_capture(tf_frame(symbol, "4h", archive), "4h", cut["1h"])
    daily, err = prepare_causal_ohlcv(daily_raw, symbol=symbol, timeframe="1d")
    if err:
        raise ValueError(err)
    line, _, _, _ = native_mirror(daily)
    index = project_daily_at_bar_open(pd.DatetimeIndex(daily.timestamp), h4_raw.index)
    if index[i] < 0 or not np.isclose(line.level[index[i]], float(row.line), rtol=1e-8, atol=1e-8):
        raise AssertionError("example line differs from replay")
    if i+8 >= len(h4_raw):
        raise AssertionError("example lacks the complete 8-bar horizon")
    start, end = max(0, i-24), i+9
    bars = h4_raw.iloc[start:end]
    x = np.arange(len(bars))
    entry_x = i-start
    fig, ax = plt.subplots(figsize=(12, 5.3), dpi=135)
    fig.patch.set_facecolor("#f7f9fc")
    ax.set_facecolor("white")
    ax.axvspan(entry_x+0.5, len(bars)-.45, color="#edf3fc", zorder=0, label="Sonraki 8 bar")
    for k, (_, candle) in enumerate(bars.iterrows()):
        o, h, lo, c = (float(candle[col]) for col in ("open", "high", "low", "close"))
        color = "#15836e" if c >= o else "#ce5263"
        ax.vlines(k, lo, h, color=color, linewidth=1.15, zorder=2)
        bottom, height = min(o, c), abs(c-o)
        height = max(height, max(h-lo, .01)*.015)
        ax.add_patch(Rectangle((k-.29, bottom), .58, height, facecolor=color, edgecolor=color, zorder=3))
    old_y = [line.level[index[j]] if index[j] >= 0 else np.nan for j in range(start, i+1)]
    ax.step(x[:entry_x+1], old_y, where="post", color="#7652c8", linewidth=1.7, label="O ana kadar bilinen direnç")
    ax.hlines(float(row.line), entry_x, len(bars)-1, color="#7652c8", linewidth=1.7,
              linestyle="--", label="Olayda dondurulan direnç")
    ax.hlines(float(row.ceiling), entry_x, len(bars)-1, color="#e6a54b", linewidth=1,
              linestyle=":", label="Native ATR tavanı (donuk)")
    ax.axvline(entry_x, color="#466ca8", linewidth=1, alpha=.8)
    ticks = np.unique(np.linspace(0, len(bars)-1, min(7, len(bars))).astype(int))
    labels = [bars.index[k].tz_convert("Europe/Istanbul").strftime("%d.%m %H:%M") for k in ticks]
    ax.set_xticks(ticks, labels, rotation=25, ha="right", fontsize=8)
    ax.set_title(f"{symbol} · {title}\nOlay kapanışı {row.event_close_time} · sonraki 8 bar mavi alanda", fontsize=11, loc="left")
    ax.grid(axis="y", alpha=.15)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="upper left", fontsize=8, frameon=False, ncol=2)
    ax.set_ylabel("Fiyat")
    ax.set_xlabel("4s mum başlangıcı · İstanbul saati")
    fig.tight_layout()
    # The repo deliberately tracks documentation evidence under docs/gorseller;
    # generic *.png elsewhere is ignored. Custom outputs keep their own images.
    image_dir = (ROOT / "docs/gorseller/stabil_direnc_replay_2026_11_06/ornekler"
                 if output.resolve() == DEFAULT_OUTPUT.resolve() else output / "ornekler")
    dest = image_dir / f"{slug}.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dest)
    plt.close(fig)
    return {"slug": slug, "title": title, "symbol": symbol, "event": row.event,
            "event_close_time": row.event_close_time, "line": float(row.line), "ceiling": float(row.ceiling),
            "close": float(row.close), "atr_event": float(row.atr_event),
            "return_8_atr": float(row.return_atr_8), "first_1atr_8": row.first_1atr_8,
            "first_retest_8": None if pd.isna(row.first_retest_8) else row.first_retest_8,
            "image": Path(os.path.relpath(dest, output)).as_posix()}


def run(output: Path, archive: Path) -> list[dict]:
    events = pd.read_csv(output / "events_4h.csv.gz", low_memory=False)
    examples = [plot_example(slug, title, row, output, archive) for slug, title, row in pick_examples(events)]
    (output / "ornekler.json").write_text(json.dumps(examples, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = ["# Stabil direnç replay — somut örnekler", "",
          "Bu üç örnek farklı sonuç sınıflarının **ilk kronolojik örnekleridir**, rastgele veya temsili seçim değil."
          " Analiz çizgisi olay anında bilinen seviyedir; mavi bölgede 8 sonraki 4s mum vardır ve çizgi/tavan dondurulmuştur."
          " Olay mumunun kapanışından önce işlem yapıldığı varsayılmaz. Aynı mum içindeki eşik sırası bilinmez.", ""]
    for x in examples:
        md += [f"## {x['symbol']} — {x['title']}", "",
               f"Kapanış: {x['event_close_time']}; seviye {x['line']:.4f}, tavan {x['ceiling']:.4f}, "
               f"olay kapanışı {x['close']:.4f}, olay ATR {x['atr_event']:.4f}. "
               f"Sonraki 8-bar kapanış {x['return_8_atr']:+.2f} ATR; ilk ±1 ATR: {x['first_1atr_8']}; "
               f"ilk retest: {x['first_retest_8'] or 'uygulanmaz'}.", "",
               f"![{x['title']}]({x['image']})", ""]
    (output / "ornekler.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps(examples, ensure_ascii=False, indent=2))
    return examples


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--archive", type=Path, default=arsiv_koku())
    args = parser.parse_args()
    run(args.output, args.archive)


if __name__ == "__main__":
    main()
