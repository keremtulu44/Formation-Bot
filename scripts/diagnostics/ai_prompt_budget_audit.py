#!/usr/bin/env python3
"""BIST evreni üzerinde tüm AI prompt ailelerinin karakter/UTF-16/token bütçe denetimi.

Örnek kullanım:
    .venv/bin/python scripts/diagnostics/ai_prompt_budget_audit.py
    .venv/bin/python scripts/diagnostics/ai_prompt_budget_audit.py --dates 2026-09-25 2026-09-23
    .venv/bin/python scripts/diagnostics/ai_prompt_budget_audit.py --symbols BIMAS TAVHL THYAO --json
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ai_prompt import (  # noqa: E402
    API_EXTENDED_BUDGET,
    API_STANDARD_BUDGET,
    COMPACT_PASTE_BUDGET,
    build_api_prompt,
    build_from_local_cache,
    estimate_tokens,
    render_compact_prompt,
    render_prompt,
    utf16_len,
)
from ai_prompt.api_messages import _build_system_prompt  # noqa: E402
from ai_prompt.builder import ROOT as PROMPT_ROOT, _research as build_research  # noqa: E402
from ai_prompt.kap_bridge import KAP_SYNTHESIS_INSTRUCTION  # noqa: E402
from ai_prompt.verdict import HIDDEN_VERDICT_INSTRUCTION  # noqa: E402

DEFAULT_DATES = ("2026-09-25", "2026-09-23")


def _discover_symbols(bot_data_dir: Path) -> list[str]:
    symbols = []
    for path in sorted(bot_data_dir.glob("*.json")):
        stem = path.stem
        if stem.endswith("_gunluk") or stem.startswith("ai_"):
            continue
        symbols.append(stem)
    return symbols


def _worst_kap_context(symbol: str, cut_date: str) -> dict[str, Any]:
    return {
        "durum": "var",
        "baglam": {
            "konu": "satis_sozlesmesi",
            "yayin_zamani": f"{cut_date}T05:15:00Z",
            "seans_durumu": "seans_oncesi",
            "olay": (
                f"{symbol} yüksek tutarlı uzun vadeli sözleşme imzalandığını duyurdu (tutar 185 mn EUR); "
                "teslimatlar 2026-2028 dönemine yayılacak, döviz bazlı gelir katkısı bekleniyor ve "
                "kapasite kullanım oranında artış öngörülüyor. " + ("Ayrıntı notu. " * 22)
            ),
            "onemi": "Sözleşme tutarı / son 12 ay konsolide satış geliri oranı %18,4; kur tahmini yapılmadı.",
            "mali_tablo": {
                "donem_sonu": "2026-06-30",
                "yayin_zamani": "2026-08-14T16:30:00Z",
                "kaynak": "KAP resmi konsolide finansal rapor",
            },
            "revizyon": {"onceki_id": 123456},
            "kaynak": "kap_resmi",
        },
        "sirket_profili": {
            "aliskanlik": "seyrek",
            "son_30_gun_bildirim_sayisi": 1,
        },
        "bekleyen_bildirim": {
            "yayin_zamani": f"{cut_date}T14:40:00Z",
        },
    }


def _kap_yok_context(symbol: str) -> dict[str, Any]:
    del symbol
    return {
        "durum": "yok",
        "neden": "uygun_gelisme_yok",
        "sessizlik": {"sessizlik_gun": 45},
        "sirket_profili": {
            "aliskanlik": "seyrek",
            "son_30_gun_bildirim_sayisi": 0,
        },
    }


def _worst_trigger(cut_date: str) -> dict[str, Any]:
    return {
        "kind": "FORMASYON_KIRILIM",
        "channel": "telegram_main",
        "timeframe": "4h",
        "state": "KIRILIM_TEYITLI",
        "pattern_name": "Simetrik Üçgen",
        "direction": "yukarı",
        "bar_open": f"{cut_date}T13:00:00+03:00",
        "bar_close": f"{cut_date}T17:00:00+03:00",
        "summary": "4H üst bant üzerinde hacimli kapanış ile kırılım teyidi alındı.",
        "reasons": ["Üst bant üstü kapanış", "RVOL > 1,5x", "Dış yapı uyumlu"],
    }


def _percentile(values: list[int], q: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, math.ceil(q * len(ordered)) - 1))
    return ordered[idx]


def _summarize(entries: list[tuple[int, str]], hard_max: int | None = None) -> dict[str, Any]:
    vals = [v for v, _ in entries]
    if not vals:
        return {}
    max_val, max_label = max(entries, key=lambda x: x[0])
    min_val, min_label = min(entries, key=lambda x: x[0])
    p50 = int(round(statistics.median(vals)))
    p95 = _percentile(vals, 0.95)
    summary: dict[str, Any] = {
        "count": len(vals),
        "min": min_val,
        "min_case": min_label,
        "p50": p50,
        "p95": p95,
        "max": max_val,
        "max_case": max_label,
        "p50_est_tokens": estimate_tokens("x" * p50),
        "max_est_tokens": estimate_tokens("x" * max_val),
    }
    if hard_max is not None:
        summary["hard_max"] = hard_max
        summary["max_margin"] = hard_max - max_val
        summary["max_utilization_pct"] = round(max_val / hard_max * 100, 1)
    return summary


def run_audit(
    symbols: list[str],
    dates: list[str],
    *,
    main_tf: str = "4h",
    bot_data_dir: Path | None = None,
) -> dict[str, Any]:
    data_dir = bot_data_dir or (REPO_ROOT / "bot_data")
    static_blocks = {
        "talimat_txt": utf16_len((PROMPT_ROOT / "talimat.txt").read_text(encoding="utf-8").strip()),
        "talimat_kisa_txt": utf16_len((PROMPT_ROOT / "talimat_kisa.txt").read_text(encoding="utf-8").strip()),
        "talimat_api_txt": utf16_len((PROMPT_ROOT / "talimat_api.txt").read_text(encoding="utf-8").strip()),
        "kap_synthesis_instruction": utf16_len(KAP_SYNTHESIS_INSTRUCTION),
        "hidden_verdict_instruction": utf16_len(HIDDEN_VERDICT_INSTRUCTION),
    }

    system_variants = {}
    failures: list[str] = []
    for name, modality, verdict, kap_rules in (
        ("text_only_plain", "text_only", False, False),
        ("text_only_verdict", "text_only", True, False),
        ("text_only_verdict_kap_var", "text_only", True, True),
        ("multimodal_verdict_kap_var", "multimodal", True, True),
    ):
        txt = _build_system_prompt(modality, include_hidden_verdict=verdict, include_kap_rules=kap_rules)
        u16 = utf16_len(txt)
        system_variants[name] = {
            "utf16": u16,
            "chars": len(txt),
            "est_tokens": estimate_tokens(txt),
            "target": API_STANDARD_BUDGET.system_target,
            "hard_max": API_STANDARD_BUDGET.system_hard_max,
            "within_target": u16 <= API_STANDARD_BUDGET.system_target,
            "within_hard_cap": u16 <= API_STANDARD_BUDGET.system_hard_max,
        }
        if u16 > API_STANDARD_BUDGET.system_hard_max:
            failures.append(f"system.{name}={u16} > {API_STANDARD_BUDGET.system_hard_max}")

    buckets: dict[str, list[tuple[int, str]]] = {
        "full_strict": [],
        "compact_strict": [],
        "compact_retro": [],
        "api_plain_strict_user": [],
        "api_plain_retro_user": [],
        "api_yok_retro_user": [],
        "api_worst_retro_user": [],
        "api_worst_retro_total_text": [],
        "api_worst_retro_total_mm": [],
    }
    section_samples: dict[str, list[tuple[int, str]]] = {
        k: []
        for k in (
            "meta",
            "tetikleyici",
            "grafikler",
            "replay",
            "genel_arastirma",
            "kap_baglam",
            "xml_overhead",
        )
    }
    compaction_stages: dict[int, int] = {}

    for cut_date in dates:
        as_of_str = f"{cut_date} 18:05+03:00"
        as_of_ts = pd.Timestamp(as_of_str)
        retro_research = build_research(as_of_ts, "retrospective")
        trigger = _worst_trigger(cut_date)

        for sym in symbols:
            case = f"{sym}@{cut_date}"
            strict_pkt = build_from_local_cache(
                sym,
                as_of=as_of_str,
                main_tf=main_tf,
                research_mode="strict",
                data_dir=str(data_dir),
            )
            retro_pkt = copy.copy(strict_pkt)
            retro_pkt["research_mode"] = "retrospective"
            retro_pkt["research"] = retro_research

            # 1) Full prompt
            buckets["full_strict"].append((utf16_len(render_prompt(strict_pkt)), case))

            # 2) Compact paste prompt (strict & retro)
            for label, pkt in (("compact_strict", strict_pkt), ("compact_retro", retro_pkt)):
                try:
                    c_txt = render_compact_prompt(pkt)
                    c_u16 = utf16_len(c_txt)
                    buckets[label].append((c_u16, case))
                    if c_u16 > COMPACT_PASTE_BUDGET.user_hard_max:
                        failures.append(f"{label} {case}: {c_u16} > {COMPACT_PASTE_BUDGET.user_hard_max}")
                except Exception as exc:
                    failures.append(f"{label} {case}: {exc}")

            # 3) API prompt variants
            try:
                b_ps = build_api_prompt(strict_pkt, include_hidden_verdict=True)
                buckets["api_plain_strict_user"].append((b_ps["user_size"], case))

                b_pr = build_api_prompt(retro_pkt, include_hidden_verdict=True)
                buckets["api_plain_retro_user"].append((b_pr["user_size"], case))

                b_yok = build_api_prompt(
                    retro_pkt,
                    include_hidden_verdict=True,
                    kap_context=_kap_yok_context(sym),
                )
                buckets["api_yok_retro_user"].append((b_yok["user_size"], case))

                b_worst = build_api_prompt(
                    retro_pkt,
                    include_hidden_verdict=True,
                    kap_context=_worst_kap_context(sym, cut_date),
                    trigger=trigger,
                )
                buckets["api_worst_retro_user"].append((b_worst["user_size"], case))
                buckets["api_worst_retro_total_text"].append((b_worst["budget"]["total"]["utf16"], case))

                b_worst_mm = build_api_prompt(
                    retro_pkt,
                    modality="multimodal",
                    include_hidden_verdict=True,
                    kap_context=_worst_kap_context(sym, cut_date),
                    trigger=trigger,
                )
                buckets["api_worst_retro_total_mm"].append((b_worst_mm["budget"]["total"]["utf16"], case))

                stage = int(b_worst["budget"]["compaction_stage"])
                compaction_stages[stage] = compaction_stages.get(stage, 0) + 1

                for sec_name in section_samples:
                    section_samples[sec_name].append((b_worst["budget"]["sections"][sec_name], case))

                for lbl, bnd in (("api_plain_strict", b_ps), ("api_worst_retro", b_worst), ("api_worst_mm", b_worst_mm)):
                    if not bnd["budget"]["within_hard_cap"]:
                        failures.append(f"{lbl} {case}: hard cap breached")
            except Exception as exc:
                failures.append(f"api {case}: {exc}")

    return {
        "meta": {
            "symbols_count": len(symbols),
            "dates": list(dates),
            "snapshots_total": len(symbols) * len(dates),
            "main_tf": main_tf,
        },
        "budgets": {
            "compact_paste": {
                "target": COMPACT_PASTE_BUDGET.user_target,
                "hard_max": COMPACT_PASTE_BUDGET.user_hard_max,
            },
            "api_standard": {
                "system_target": API_STANDARD_BUDGET.system_target,
                "system_hard_max": API_STANDARD_BUDGET.system_hard_max,
                "user_target": API_STANDARD_BUDGET.user_target,
                "user_hard_max": API_STANDARD_BUDGET.user_hard_max,
                "total_hard_max": API_STANDARD_BUDGET.total_hard_max,
            },
            "api_extended": {
                "system_target": API_EXTENDED_BUDGET.system_target,
                "system_hard_max": API_EXTENDED_BUDGET.system_hard_max,
                "user_target": API_EXTENDED_BUDGET.user_target,
                "user_hard_max": API_EXTENDED_BUDGET.user_hard_max,
                "total_hard_max": API_EXTENDED_BUDGET.total_hard_max,
            },
        },
        "static_blocks_utf16": static_blocks,
        "system_variants": system_variants,
        "distributions": {
            "full_strict": _summarize(buckets["full_strict"]),
            "compact_strict": _summarize(buckets["compact_strict"], COMPACT_PASTE_BUDGET.user_hard_max),
            "compact_retro": _summarize(buckets["compact_retro"], COMPACT_PASTE_BUDGET.user_hard_max),
            "api_plain_strict_user": _summarize(buckets["api_plain_strict_user"], API_STANDARD_BUDGET.user_hard_max),
            "api_plain_retro_user": _summarize(buckets["api_plain_retro_user"], API_STANDARD_BUDGET.user_hard_max),
            "api_yok_retro_user": _summarize(buckets["api_yok_retro_user"], API_STANDARD_BUDGET.user_hard_max),
            "api_worst_retro_user": _summarize(buckets["api_worst_retro_user"], API_STANDARD_BUDGET.user_hard_max),
            "api_worst_retro_total_text": _summarize(buckets["api_worst_retro_total_text"], API_STANDARD_BUDGET.total_hard_max),
            "api_worst_retro_total_mm": _summarize(buckets["api_worst_retro_total_mm"], API_STANDARD_BUDGET.total_hard_max),
        },
        "worst_case_sections": {
            sec: _summarize(rows, API_STANDARD_BUDGET.section_targets.get(sec))
            for sec, rows in section_samples.items()
        },
        "worst_case_compaction_stages": compaction_stages,
        "failures": failures,
        "ok": len(failures) == 0,
    }


def _print_report(report: dict[str, Any]) -> None:
    meta = report["meta"]
    print(
        f"=== AI PROMPT BÜTÇE DENETİMİ ({meta['symbols_count']} sembol × "
        f"{len(meta['dates'])} tarih = {meta['snapshots_total']} kesit, ana_tf={meta['main_tf']}) ==="
    )
    print("\n1) Statik Talimat Blokları (UTF-16):")
    for k, v in report["static_blocks_utf16"].items():
        print(f"  {k:28s}: {v:5d} u16 (~{estimate_tokens('x' * v):4d} tok)")

    print(
        f"\n2) API System Prompt Varyantları (hedef <={API_STANDARD_BUDGET.system_target}, "
        f"sert tavan <={API_STANDARD_BUDGET.system_hard_max} u16):"
    )
    for k, v in report["system_variants"].items():
        status = "OK-HEDEF" if v["within_target"] else ("OK-TAVAN" if v["within_hard_cap"] else "AŞIM")
        print(
            f"  {k:28s}: {v['utf16']:5d} u16 (~{v['est_tokens']:4d} tok)  "
            f"[{status}, marj={v['hard_max'] - v['utf16']:+d}]"
        )

    print("\n3) Gerçek BIST Evreni Dağılımları (UTF-16):")
    header = f"  {'Profil':28s} {'Min':>6s} {'P50':>6s} {'P95':>6s} {'Max':>6s} {'~Tok':>6s} {'Tavan':>6s} {'Marj':>6s}  En Büyük"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for name, s in report["distributions"].items():
        cap = f"{s['hard_max']:6d}" if "hard_max" in s else "     -"
        margin = f"{s['max_margin']:+6d}" if "max_margin" in s else "     -"
        print(
            f"  {name:28s} {s['min']:6d} {s['p50']:6d} {s['p95']:6d} {s['max']:6d} "
            f"{s['max_est_tokens']:6d} {cap} {margin}  {s['max_case']}"
        )

    print("\n4) En Ağır Senaryo (retro + 3 KAP haber + mali tablo + tetikleyici) Bölüm Dağılımı:")
    for sec, s in report["worst_case_sections"].items():
        tgt = f"hedef={s['hard_max']:4d}" if "hard_max" in s else "hedef=   -"
        print(
            f"  {sec:18s}: min={s['min']:4d} p50={s['p50']:4d} p95={s['p95']:4d} "
            f"max={s['max']:4d} ({tgt}, en büyük={s['max_case']})"
        )
    print(f"  Sıkıştırma kademeleri: {report['worst_case_compaction_stages']}")

    if report["failures"]:
        print(f"\nHATA ({len(report['failures'])} adet):")
        for f in report["failures"]:
            print(f"  - {f}")
    else:
        print("\nSONUÇ: TÜM BÜTÇE TAVANLARI %100 GEÇTİ (0 ihlal).")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI prompt karakter/UTF-16/token bütçe denetimi")
    parser.add_argument("--symbols", nargs="*", help="Denetlenecek semboller (boşsa tüm bot_data)")
    parser.add_argument("--dates", nargs="+", default=list(DEFAULT_DATES), help="Kesit tarihleri (YYYY-MM-DD)")
    parser.add_argument("--main-tf", default="4h", help="Ana zaman dilimi (varsayılan: 4h)")
    parser.add_argument("--json", action="store_true", help="JSON çıktısı ver")
    args = parser.parse_args(argv)

    bot_data_dir = REPO_ROOT / "bot_data"
    symbols = [s.upper() for s in args.symbols] if args.symbols else _discover_symbols(bot_data_dir)
    report = run_audit(symbols, list(args.dates), main_tf=args.main_tf, bot_data_dir=bot_data_dir)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_report(report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
