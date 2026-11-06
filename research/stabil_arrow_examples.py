"""Produce three historical Stabil replay examples using the normal chart path.

The second chart of each pair adds eight later 4h candles to a frozen snapshot;
no analysis layer is recomputed using those future candles. This is historical
research, not a signal or a recommendation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from data import mum_kapanis_anlari
import grafik
from research.arsiv import tf_frame
from research.replay_egitim import Soru, TFS, _sonuc_goruntusu, _soru_goruntusu

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs/gorseller/stabil_ok_replay_2026_11_05/ornekler"
EXAMPLES = (
    ("AKFGY", "2026-03-05 13:30:00+03:00", "up", "zayif_dusuk_hacim"),
    ("ALFAS", "2026-01-08 17:30:00+03:00", "up", "zayif_yakin_ob_fvg"),
    ("AEFES", "2025-07-17 17:30:00+03:00", "down", "dikey_uyari_sonrasi_yukselis"),
)


def create_examples(output: Path) -> list[dict]:
    output.mkdir(parents=True, exist_ok=True)
    cases = []
    for symbol, date, expected, slug in EXAMPLES:
        event_time = pd.Timestamp(date)
        frames = {tf: tf_frame(symbol, tf) for tf in TFS}
        closes = {tf: mum_kapanis_anlari(frame.index, tf).tz_convert("UTC") for tf, frame in frames.items()}
        positions = {tf: int(times.searchsorted(event_time.tz_convert("UTC"), side="right") - 1)
                     for tf, times in closes.items()}
        p = positions["4h"]
        if p < 0 or closes["4h"][p] != event_time.tz_convert("UTC") or p + 8 >= len(frames["4h"]):
            raise ValueError(f"missing complete event window: {symbol} {date}")
        question = Soru(symbol, frames, closes, positions, "REPORT", "4h", 8)
        before = _soru_goruntusu(question, "4h")
        layer = before.get("stabil") or {}
        event_in_view = len(before["zamanlar"]) - 1
        up = set(layer.get("reclaim_barlar") or ()) | set(layer.get("momentum_barlar") or ())
        down = set(layer.get("dikey_deneme_barlar") or ())
        if expected == "up" and (event_in_view not in up or event_in_view in down):
            raise AssertionError(f"historical upward arrow missing: {symbol} {date}")
        if expected == "down" and (event_in_view not in down or event_in_view in up):
            raise AssertionError(f"historical vertical warning missing: {symbol} {date}")
        after = _sonuc_goruntusu(question, "4h", p + 8)
        entries = {}
        for stage, snapshot in (("olay", before), ("sonuc_8bar", after)):
            path = output / f"{symbol}_{slug}_{stage}.png"
            written, meta = grafik.ciz(snapshot, "4h", secenekler={
                "cikti": str(path), "etiket_detay": False, "serit": None,
            })
            if not written or not (meta.get("cizgiler") or {}).get("stabil", {}).get("cizildi"):
                raise RuntimeError(f"Stabil chart missing: {symbol} {stage}")
            entries[stage] = path.name
        cases.append({"symbol": symbol, "event_close_time": date, "expected_marker": expected,
                      "future_bars": 8, "signal_index_in_chart": event_in_view, "files": entries})
        print(f"{symbol} {date}: {expected}, two historical charts", flush=True)
    (output / "ornekler.json").write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    create_examples(parser.parse_args().output)


if __name__ == "__main__":
    main()
