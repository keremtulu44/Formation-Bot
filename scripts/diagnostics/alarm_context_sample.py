#!/usr/bin/env python3
"""Rebuild a no-lookahead ASTOR 4h context sample for 2026-10-16 13:30 +03."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from alarm_context_packet import build_context_packet, packet_json  # noqa: E402
from config import ISTANBUL_TZ  # noqa: E402
from data import mum_kapanis_anlari  # noqa: E402
from domain_engines.runner import run_domain_engines, run_stabil_domain  # noqa: E402
from research.arsiv import tf_frame  # noqa: E402

SYMBOL = "ASTOR"
TIMEFRAME = "4h"
AS_OF = pd.Timestamp("2026-10-16T13:30:00+03:00")
GENERATED_AT = pd.Timestamp("2026-11-04T10:00:00+03:00")
CANDIDATE_FILE = ROOT / "docs/arastirma/sonuclar/kirilim_replay/adaylar.csv.gz"


def build_sample() -> tuple[dict, str]:
    daily = tf_frame(SYMBOL, "1d")
    h4 = tf_frame(SYMBOL, TIMEFRAME)
    h4_close_times = pd.DatetimeIndex(
        mum_kapanis_anlari(h4.index.tz_convert(ISTANBUL_TZ), TIMEFRAME)
    )
    closed_h4 = h4.loc[h4_close_times <= AS_OF].copy()
    if closed_h4.empty:
        raise RuntimeError("No completed ASTOR 4h bar exists at the selected cutoff")
    if h4_close_times[closed_h4.shape[0] - 1] != AS_OF:
        raise RuntimeError("The last selected ASTOR 4h bar does not close exactly at the cutoff")

    domain_results = run_domain_engines(SYMBOL, TIMEFRAME, closed_h4, isolated=True)
    domain_results["stabil"] = run_stabil_domain(
        SYMBOL,
        TIMEFRAME,
        h4,
        daily_frame=daily,
        h4_frame=h4,
        as_of_close=AS_OF,
        isolated=True,
    )

    # Read only the candidate row's anchor label. The result/outcome columns are
    # intentionally not loaded into this historical context sample.
    candidates = pd.read_csv(
        CANDIDATE_FILE,
        compression="gzip",
        usecols=["symbol", "tf", "anchor"],
    )
    row = candidates.loc[
        candidates["symbol"].eq(SYMBOL)
        & candidates["tf"].eq(TIMEFRAME)
        & candidates["anchor"].eq("2026-10-16 13:30:00+03:00")
    ]
    if len(row) != 1:
        raise RuntimeError(f"Expected one ASTOR candidate anchor, found {len(row)}")
    candidate_open = pd.Timestamp(row.iloc[0]["anchor"])
    candidate_position = h4.index.get_indexer([candidate_open.tz_convert("UTC")])[0]
    if candidate_position < 0:
        raise RuntimeError("Candidate anchor does not match a row in the local 4h archive")
    candidate_bar_close = h4_close_times[candidate_position]
    if candidate_bar_close <= AS_OF:
        raise RuntimeError(
            "Candidate bar is no longer after the selected cutoff; re-audit the sample boundary"
        )

    packet = build_context_packet(
        symbol=SYMBOL,
        timeframe=TIMEFRAME,
        as_of=AS_OF,
        # This is an on-demand historical context at the cutoff, not a claim that
        # a replay candidate row was already observable at that time.
        domain_results=domain_results,
        trigger=None,
        context_kind="historical_sample",
        generated_at=GENERATED_AT,
        reference_price=float(closed_h4.iloc[-1]["close"]),
        price_time=AS_OF,
        closed_bar_count=len(closed_h4),
        data_source="backfill_data/ASTOR_1h.csv.gz + ASTOR_1d.csv.gz (4h derived)",
    )

    note = "\n".join(
        [
            "# Reproducible ASTOR context sample",
            "",
            f"- Snapshot cutoff: `{AS_OF.isoformat()}`; last completed H4 close: `{packet['snapshot']['reference_price']:.2f}`.",
            f"- The selected H4 archive contains `{len(closed_h4)}` completed bars through the cutoff; later bars are not passed to the four standard domain engines.",
            f"- Stabil receives the archive frames with `as_of_close={AS_OF.isoformat()}` and returns its native as-of output.",
            f"- The replay candidate anchor is a bar-open label at `{candidate_open.isoformat()}`; its candle closes at `{candidate_bar_close.isoformat()}`, after the cutoff.",
            "- Therefore no replay trigger, strength/quality fields, confirmation, or outcome from that candidate row is included in this packet.",
            "- Replay findings below are separate research knowledge. Each one is labeled with report/data timing; post-cutoff findings were not knowable at this snapshot.",
            "- `trigger` is intentionally null: this example demonstrates an on-demand historical request, not a delivered alarm.",
            "",
            "## Readable context packet",
            "",
            packet["readable_text"],
            "",
        ]
    )
    return packet, note


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--text-output",
        type=Path,
        help="Optional path for the readable Markdown sample; defaults to stdout.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="Optional path for the complete JSON packet (about 7 MB for this sample).",
    )
    args = parser.parse_args()

    packet, sample_text = build_sample()
    if args.text_output:
        args.text_output.parent.mkdir(parents=True, exist_ok=True)
        args.text_output.write_text(sample_text, encoding="utf-8")
        print(f"Wrote readable sample: {args.text_output}")
    else:
        print(sample_text)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(packet_json(packet), encoding="utf-8")
        print(f"Wrote complete JSON packet: {args.json_output}")


if __name__ == "__main__":
    main()
