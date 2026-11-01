"""Canlı deploy evreni (`config.BIST_50`) üzerinde Stabil güçlü geri alım sistematiği doğrulaması.

Bu modül, üretimde (`domain_engines/stabil/signals.py`) çalışan `evaluate_bar_behaviors`
fonksiyonunu BİREBİR çağırarak canlı semboller üzerinde nedensel 4S replay yapar;
haftalık sinyal/mesaj temposunu, sembol dağılımını, endeks (`XU100`, `XU30`) başarısını
ve ileri bar getirilerini ölçer.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import config
from domain_engines.stabil import (
    StabilTrendConfig,
    build_single_pass_history,
    evaluate_bar_behaviors,
    project_support_to_bar_closes,
)
from research.arsiv import arsiv_sembolleri, tf_frame


def _median(vals: list[float]) -> float | None:
    return float(np.median(vals)) if vals else None


def _mean(vals: list[float]) -> float | None:
    return float(np.mean(vals)) if vals else None


def run_live_universe_validation(
    cooldown_bars: int = 6,
    burst_cap_single: int = 3,
) -> dict[str, Any]:
    cfg = StabilTrendConfig()
    archive_set = set(arsiv_sembolleri())

    live_non_macro = [s for s in config.BIST_50 if config.sembol_turu(s) != "makro"]
    available = [s for s in live_non_macro if s in archive_set]
    missing_in_archive = [s for s in live_non_macro if s not in archive_set]

    all_events: list[dict[str, Any]] = []
    min_date = None
    max_date = None

    for sym in available:
        df_1d = tf_frame(sym, "1d")
        df_4h = tf_frame(sym, "4h")
        if df_1d.empty or df_4h.empty:
            continue

        hist = build_single_pass_history(sym, df_1d, df_4h, config=cfg)
        h4_clean = hist.h4_frame
        if h4_clean.empty:
            continue

        bar_proj = project_support_to_bar_closes(
            list(h4_clean["timestamp"]),
            hist.support_timeline,
        )
        bhvs = evaluate_bar_behaviors(
            sym,
            "4h",
            h4_clean,
            bar_proj,
            hist.support_timeline,
            min_tick=cfg.min_tick,
        )

        closes = h4_clean["close"].to_numpy(dtype=float)
        highs = h4_clean["high"].to_numpy(dtype=float)
        lows = h4_clean["low"].to_numpy(dtype=float)
        ts_arr = list(h4_clean["timestamp"])
        n = len(bhvs)

        if ts_arr:
            d0, d1 = ts_arr[0].date(), ts_arr[-1].date()
            min_date = d0 if min_date is None else min(min_date, d0)
            max_date = d1 if max_date is None else max(max_date, d1)

        # Causal 14-bar ATR for forward measurement in ATR units
        from domain_engines.stabil.signals import _causal_atr14

        atr_arr = _causal_atr14(highs[:n], lows[:n], closes[:n], period=14)
        last_sent_idx = -999

        for i, b in enumerate(bhvs):
            if b.reclaim_kind is None:
                continue
            if i - last_sent_idx < cooldown_bars:
                continue
            last_sent_idx = i

            atr = float(atr_arr[i]) if math.isfinite(float(atr_arr[i])) and atr_arr[i] > 0 else np.nan
            sup = float(b.support_level) if b.support_level is not None else np.nan
            c0 = float(closes[i])

            next_hold = (
                bool(closes[i + 1] >= sup - 1e-6)
                if (i + 1 < n and math.isfinite(sup))
                else None
            )
            ret_4 = (
                float((closes[i + 4] - c0) / atr)
                if (i + 4 < n and math.isfinite(atr))
                else None
            )
            ret_8 = (
                float((closes[i + 8] - c0) / atr)
                if (i + 8 < n and math.isfinite(atr))
                else None
            )
            ret_16 = (
                float((closes[i + 16] - c0) / atr)
                if (i + 16 < n and math.isfinite(atr))
                else None
            )
            mfe_8 = (
                float((np.max(highs[i + 1 : i + 9]) - c0) / atr)
                if (i + 8 < n and math.isfinite(atr))
                else None
            )
            mae_8 = (
                float((c0 - np.min(lows[i + 1 : i + 9])) / atr)
                if (i + 8 < n and math.isfinite(atr))
                else None
            )

            all_events.append(
                {
                    "symbol": sym,
                    "symbol_type": config.sembol_turu(sym),
                    "timestamp": str(ts_arr[i]),
                    "date": str(ts_arr[i].date()),
                    "iso_week": f"{ts_arr[i].isocalendar().year}-W{ts_arr[i].isocalendar().week:02d}",
                    "kind": b.reclaim_kind,
                    "rank_score": b.rank_score,
                    "unchanged_days": b.unchanged_days,
                    "touch_count": b.touch_count,
                    "next_hold": next_hold,
                    "ret_4_atr": ret_4,
                    "ret_8_atr": ret_8,
                    "ret_16_atr": ret_16,
                    "hit_plus_1atr_8": (mfe_8 >= 1.0) if mfe_8 is not None else None,
                    "hit_minus_1atr_8": (mae_8 >= 1.0) if mae_8 is not None else None,
                }
            )

    # Group by exact 4H bar timestamp to measure burst rule (>3 -> 2 cards + 1 summary = 3 messages)
    by_bar: dict[str, list[dict[str, Any]]] = {}
    for ev in all_events:
        by_bar.setdefault(ev["timestamp"], []).append(ev)

    total_messages = 0
    burst_bars = 0
    for _, bar_evs in by_bar.items():
        if len(bar_evs) <= burst_cap_single:
            total_messages += len(bar_evs)
        else:
            total_messages += 3  # Top 2 single cards + 1 consolidated summary
            burst_bars += 1

    trading_days = len({ev["date"] for ev in all_events})
    # Span weeks across full archive calendar
    span_weeks = (
        max(1.0, ((max_date - min_date).days + 1) / 7.0)
        if (min_date is not None and max_date is not None)
        else 73.0
    )

    def _summarize_subset(evs: list[dict[str, Any]]) -> dict[str, Any]:
        nh = [1.0 if e["next_hold"] else 0.0 for e in evs if e["next_hold"] is not None]
        r4 = [e["ret_4_atr"] for e in evs if e["ret_4_atr"] is not None]
        r8 = [e["ret_8_atr"] for e in evs if e["ret_8_atr"] is not None]
        r16 = [e["ret_16_atr"] for e in evs if e["ret_16_atr"] is not None]
        p1 = [1.0 if e["hit_plus_1atr_8"] else 0.0 for e in evs if e["hit_plus_1atr_8"] is not None]
        m1 = [1.0 if e["hit_minus_1atr_8"] else 0.0 for e in evs if e["hit_minus_1atr_8"] is not None]

        by_sym: dict[str, list[float]] = {}
        for e in evs:
            if e["ret_8_atr"] is not None:
                by_sym.setdefault(e["symbol"], []).append(e["ret_8_atr"])
        sym_meds = [float(np.median(v)) for v in by_sym.values() if v]

        # Early vs late half stability
        sorted_evs = sorted(evs, key=lambda x: x["timestamp"])
        mid = len(sorted_evs) // 2
        early_r8 = [e["ret_8_atr"] for e in sorted_evs[:mid] if e["ret_8_atr"] is not None]
        late_r8 = [e["ret_8_atr"] for e in sorted_evs[mid:] if e["ret_8_atr"] is not None]

        return {
            "count": len(evs),
            "per_week": round(len(evs) / span_weeks, 2),
            "symbols_triggered": len({e["symbol"] for e in evs}),
            "next_bar_hold_pct": round(100.0 * float(np.mean(nh)), 1) if nh else None,
            "ret_4_med_atr": round(_median(r4), 3) if r4 else None,
            "ret_8_med_atr": round(_median(r8), 3) if r8 else None,
            "ret_8_mean_atr": round(_mean(r8), 3) if r8 else None,
            "ret_8_eq_sym_med_atr": round(_mean(sym_meds), 3) if sym_meds else None,
            "ret_16_med_atr": round(_median(r16), 3) if r16 else None,
            "ret_16_mean_atr": round(_mean(r16), 3) if r16 else None,
            "plus_1atr_8_pct": round(100.0 * float(np.mean(p1)), 1) if p1 else None,
            "minus_1atr_8_pct": round(100.0 * float(np.mean(m1)), 1) if m1 else None,
            "early_half_r8_med": round(_median(early_r8), 3) if early_r8 else None,
            "late_half_r8_med": round(_median(late_r8), 3) if late_r8 else None,
        }

    sym_counts: dict[str, int] = {}
    for ev in all_events:
        sym_counts[ev["symbol"]] = sym_counts.get(ev["symbol"], 0) + 1
    top_syms = sorted(sym_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:10]

    return {
        "live_non_macro_count": len(live_non_macro),
        "archive_tested_count": len(available),
        "missing_in_archive": missing_in_archive,
        "date_span": f"{min_date} .. {max_date}",
        "span_weeks": round(span_weeks, 1),
        "cooldown_bars": cooldown_bars,
        "burst_cap_single": burst_cap_single,
        "total_signals": len(all_events),
        "signals_per_week_50": round(len(all_events) / span_weeks, 2),
        "est_signals_per_week_53": round((len(all_events) / span_weeks) * (len(live_non_macro) / max(1, len(available))), 2),
        "total_messages_after_burst_cap": total_messages,
        "messages_per_week_50": round(total_messages / span_weeks, 2),
        "est_messages_per_week_53": round((total_messages / span_weeks) * (len(live_non_macro) / max(1, len(available))), 2),
        "burst_4h_bars": burst_bars,
        "overall": _summarize_subset(all_events),
        "close_reclaim": _summarize_subset([e for e in all_events if e["kind"] == "close_reclaim"]),
        "intrabar_sweep_reclaim": _summarize_subset([e for e in all_events if e["kind"] == "intrabar_sweep_reclaim"]),
        "indices_only": _summarize_subset([e for e in all_events if e["symbol_type"] == "endeks"]),
        "equities_only": _summarize_subset([e for e in all_events if e["symbol_type"] == "hisse"]),
        "top_symbols": top_syms,
    }


if __name__ == "__main__":
    summary = run_live_universe_validation()
    out_path = Path("docs/arastirma/stabil_live_systematic_results.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
