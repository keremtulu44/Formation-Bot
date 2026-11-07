"""Aggregate the fixed resistance replay plan into transparent Turkish results."""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research.stabil_resistance_replay import DEFAULT_OUTPUT, HORIZONS, MODEL_NAMES, write_csv_gz

SEED = 20261106
BOOTSTRAPS = 2000


def pct(num: int | float, den: int | float) -> float | None:
    return 100.0 * float(num) / float(den) if den else None


def number(x: Any) -> float | None:
    if x is None or pd.isna(x):
        return None
    value = float(x)
    return value if math.isfinite(value) else None


def fmt(x: Any, digits: int = 1, *, signed: bool = False) -> str:
    n = number(x)
    return "—" if n is None else f"{n:+.{digits}f}" if signed else f"{n:.{digits}f}"


def as_bool(s: pd.Series) -> pd.Series:
    return s.astype(str).str.lower().isin(("true", "1"))


def describe(group: pd.DataFrame, horizon: int = 8) -> dict[str, Any]:
    valid = group.loc[group[f"status_{horizon}"] == "VALID"]
    n = len(valid)
    first = valid[f"first_1atr_{horizon}"]
    counts = {k: int((first == k).sum()) for k in ("DOWN_FIRST", "UP_FIRST", "AMBIGUOUS_SAME_BAR", "NEITHER")}
    result: dict[str, Any] = {
        "events": len(group), "valid": n, "symbols": int(valid["symbol"].nunique()),
        "statuses": {str(k): int(v) for k, v in group[f"status_{horizon}"].value_counts(dropna=False).items()},
        "right_censored_any": int(as_bool(group[f"right_censored_{horizon}"]).sum()),
        "cross_split_any": int(as_bool(group[f"cross_split_{horizon}"]).sum()),
        "first_counts": counts,
        "down_first_pct": pct(counts["DOWN_FIRST"], n), "up_first_pct": pct(counts["UP_FIRST"], n),
        "ambiguous_pct": pct(counts["AMBIGUOUS_SAME_BAR"], n), "neither_pct": pct(counts["NEITHER"], n),
        "median_return_atr": number(valid[f"return_atr_{horizon}"].median()) if n else None,
        "median_down_excursion_atr": number(valid[f"down_excursion_atr_{horizon}"].median()) if n else None,
        "median_up_excursion_atr": number(valid[f"up_excursion_atr_{horizon}"].median()) if n else None,
        "equal_symbol_down_first_pct": number(valid.assign(_down=(first == "DOWN_FIRST").astype(float))
                                                    .groupby("symbol")["_down"].mean().mean()*100) if n else None,
    }
    if "contact" in valid:
        contact = valid["contact"]
        real_touch = contact.isin(("WICK_TOUCH_CLOSE_AT_OR_BELOW", "TOUCH_CLOSE_ABOVE"))
        result.update({"near_only": int((contact == "NEAR_ONLY").sum()),
                       "gap_above_no_touch": int((contact == "GAP_ABOVE_NO_TOUCH").sum()),
                       "real_touch": int(real_touch.sum()),
                       "wick_reject": int((contact == "WICK_TOUCH_CLOSE_AT_OR_BELOW").sum()),
                       "close_above": int((valid["close"] > valid["line"]).sum()),
                       "wick_reject_pct_of_real_touch": pct((contact == "WICK_TOUCH_CLOSE_AT_OR_BELOW").sum(), real_touch.sum()),
                       "close_above_ceiling_event": int(as_bool(valid["close_above_ceiling"]).sum()),
                       "future_above_ceiling_pct": pct(as_bool(valid[f"future_close_above_ceiling_{horizon}"]).sum(), n),
                       "gap_open_above_line": int(as_bool(valid["gap_open_above_line"]).sum())})
    return result


def gap_bucket(x: Any) -> int | None:
    x = number(x)
    if x is None or x < 0 or x > 1.5:
        return None
    return 0 if x < .5 else 1 if x < 1 else 2


def move_bucket(x: Any) -> int | None:
    x = number(x)
    if x is None:
        return None
    return 0 if x < -1 else 1 if x < 0 else 2 if x < 1 else 3


def matched_pairs(events: pd.DataFrame, control_model: str) -> pd.DataFrame:
    """Greedy pre-outcome matching, no same candle and no overlapping 8-bar windows."""
    tests = events.loc[(events.event == "TEST") & (events.period == "Y2026") &
                       events.model.isin(["MIRROR_P4", control_model])].copy()
    tests["gap_bin"] = tests.gap_to_line_atr.map(gap_bucket)
    tests["move_bin"] = tests.prior_4bar_move_atr.map(move_bucket)
    tests = tests.dropna(subset=["gap_bin", "move_bin"]).sort_values(["symbol", "bar_index", "model"])
    controls: dict[tuple[Any, ...], list[Any]] = defaultdict(list)
    for row in tests.loc[tests.model == control_model].itertuples(index=False):
        controls[(row.symbol, row.quarter, row.session_close, row.gap_bin, row.move_bin)].append(row)
    used: set[tuple[str, int]] = set()
    pairs = []
    for target in tests.loc[tests.model == "MIRROR_P4"].itertuples(index=False):
        key = (target.symbol, target.quarter, target.session_close, target.gap_bin, target.move_bin)
        possible = [r for r in controls.get(key, []) if abs(r.bar_index-target.bar_index) >= 8
                    and (r.symbol, r.bar_index) not in used]
        if not possible:
            continue
        control = min(possible, key=lambda r: (abs(r.bar_index-target.bar_index), r.bar_index))
        used.add((control.symbol, control.bar_index))
        pairs.append({"control_model": control_model, "symbol": target.symbol, "quarter": target.quarter,
                      "session_close": target.session_close, "gap_bin": int(target.gap_bin),
                      "prior_move_bin": int(target.move_bin), "target_bar": target.bar_index,
                      "control_bar": control.bar_index, "target_time": target.event_close_time,
                      "control_time": control.event_close_time, "target_gap_atr": target.gap_to_line_atr,
                      "control_gap_atr": control.gap_to_line_atr,
                      "target_prior_move_atr": target.prior_4bar_move_atr,
                      "control_prior_move_atr": control.prior_4bar_move_atr,
                      "target_status_8": target.status_8, "control_status_8": control.status_8,
                      "target_first_8": target.first_1atr_8, "control_first_8": control.first_1atr_8,
                      "target_return_8": target.return_atr_8, "control_return_8": control.return_atr_8})
    return pd.DataFrame(pairs)


def matched_summary(pairs: pd.DataFrame) -> dict[str, Any]:
    if pairs.empty:
        return {"pairs_before_censor": 0, "valid_pairs": 0, "symbols": 0}
    valid = pairs.loc[(pairs.target_status_8 == "VALID") & (pairs.control_status_8 == "VALID")].copy()
    n = len(valid)
    result: dict[str, Any] = {"pairs_before_censor": len(pairs), "valid_pairs": n,
                              "symbols": int(valid.symbol.nunique()), "censored_pairs": len(pairs)-n}
    if not n:
        return result
    a = (valid.target_first_8 == "DOWN_FIRST").astype(int)
    b = (valid.control_first_8 == "DOWN_FIRST").astype(int)
    aa = (valid.target_first_8 == "AMBIGUOUS_SAME_BAR").astype(int)
    ba = (valid.control_first_8 == "AMBIGUOUS_SAME_BAR").astype(int)
    diff = a-b
    grouped = valid.assign(_diff=diff).groupby("symbol")["_diff"].agg(["sum", "count"])
    rng = np.random.default_rng(SEED)
    if len(grouped) > 1:
        samples = rng.integers(0, len(grouped), size=(BOOTSTRAPS, len(grouped)))
        numerators = grouped["sum"].to_numpy()[samples].sum(axis=1)
        denominators = grouped["count"].to_numpy()[samples].sum(axis=1)
        bounds = np.percentile(100*numerators/denominators, [2.5, 97.5]).tolist()
    else:
        bounds = [None, None]
    result.update({"target_down_first": int(a.sum()), "control_down_first": int(b.sum()),
                   "target_ambiguous": int(aa.sum()), "control_ambiguous": int(ba.sum()),
                   "target_down_pct": pct(a.sum(), n), "control_down_pct": pct(b.sum(), n),
                   "difference_pp": 100*float(diff.mean()), "bootstrap_95_pp": bounds,
                   "worst_case_same_bar_difference_pp": [100*(float(a.mean())-float((b+ba).mean())),
                                                          100*(float((a+aa).mean())-float(b.mean()))],
                   "target_median_return_atr": number(valid.target_return_8.median()),
                   "control_median_return_atr": number(valid.control_return_8.median()),
                   "median_abs_gap_difference_atr": number((valid.target_gap_atr-valid.control_gap_atr).abs().median()),
                   "median_abs_prior_move_difference_atr": number((valid.target_prior_move_atr-valid.control_prior_move_atr).abs().median())})
    return result


def grouped_descriptions(frame: pd.DataFrame, column: str, horizon: int = 8) -> list[dict[str, Any]]:
    rows = []
    for key, group in frame.groupby(column, dropna=False, sort=True):
        label = "UNKNOWN" if pd.isna(key) else str(key)
        rows.append({"group": label, **describe(group, horizon)})
    return rows


def summary_row(label: str, x: dict[str, Any]) -> str:
    return (f"| {label} | {x['events']} | {x['valid']} | {x['symbols']} | "
            f"{fmt(x['down_first_pct'])} | {fmt(x['up_first_pct'])} | "
            f"{fmt(x['ambiguous_pct'])} | {fmt(x['neither_pct'])} | {fmt(x['median_return_atr'], 2, signed=True)} |")


GROUP_HEADER = ("| Grup | Tüm olay | Geçerli n | Hisse | −1 ATR önce % | +1 ATR önce % | "
                "Aynı-bar % | Hiçbiri % | Medyan 8-bar kapanış ATR |\n"
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|")


def result_table(title: str, rows: list[dict[str, Any]]) -> str:
    return f"### {title}\n\n{GROUP_HEADER}\n" + "\n".join(summary_row(r["group"], r) for r in rows) + "\n"


def run(output: Path) -> dict[str, Any]:
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    events = pd.read_csv(output / "events_4h.csv.gz", low_memory=False)
    native = pd.read_csv(output / "native_daily_events.csv.gz", low_memory=False)
    tests = events.loc[events.event == "TEST"].copy()
    current = tests.loc[tests.period == "Y2026"].copy()
    main = current.loc[current.model == "MIRROR_P4"].copy()
    main["age_group"] = pd.cut(main.known_age_daily_bars, [-1, 4, 20, np.inf],
                               labels=["0–4 gün", "5–20 gün", "21+ gün"]).astype(object).fillna("UNKNOWN")
    main["touch_order"] = np.where(main.history_of_tests == "UNKNOWN", "UNKNOWN",
                                   np.where(main.test_ordinal == 1, "ilk gözlenen", "2+ gözlenen"))
    main["approach"] = main.prior_4bar_move_atr.map(lambda x: "UNKNOWN" if pd.isna(x) else
                                                     "<−1 ATR" if x < -1 else "−1..0 ATR" if x < 0 else
                                                     "0..1 ATR" if x < 1 else "≥1 ATR")
    main["volume_group"] = main.volume_ratio_prior20.map(lambda x: "UNKNOWN" if pd.isna(x) else
                                                           "<0,8" if x < .8 else "0,8..1,2" if x < 1.2 else "≥1,2")
    summaries = {model: {period: {str(h): describe(tests.loc[(tests.model == model) & (tests.period == period)], h)
                                    for h in HORIZONS} for period in ("PRE_2026", "Y2026")}
                 for model in MODEL_NAMES}
    groups = {col: grouped_descriptions(main, col) for col in
              ("quarter", "session_close", "age_group", "native_regime_proxy", "touch_order", "approach", "volume_group", "contact")}
    main_nonoverlap = main.loc[as_bool(main.nonoverlap_8)]
    groups["nonoverlap"] = [{"group": "Tüm TEST", **describe(main)},
                            {"group": "En az 8 bar aralıklı TEST", **describe(main_nonoverlap)}]
    valid_main = main.loc[main.status_8 == "VALID"].copy()
    per_symbol = valid_main.assign(_down=(valid_main.first_1atr_8 == "DOWN_FIRST").astype(int)).groupby("symbol")["_down"].agg(["count", "sum"])
    total_down = int(per_symbol["sum"].sum())
    loo = [100 * (total_down-int(r["sum"])) / (len(valid_main)-int(r["count"]))
           for _, r in per_symbol.iterrows() if len(valid_main)-int(r["count"]) > 0]
    top = per_symbol.sort_values("count", ascending=False)
    concentration = {"top_5_symbols_events": int(top.head(5)["count"].sum()),
                     "top_5_symbols_share_pct": pct(top.head(5)["count"].sum(), len(valid_main)),
                     "max_symbol_events": int(top.iloc[0]["count"]) if len(top) else 0,
                     "leave_one_symbol_out_down_pct_range": [min(loo), max(loo)] if loo else [None, None]}
    native_current = native.loc[native.period == "Y2026"]
    native_groups = grouped_descriptions(native_current, "event")
    break_group = events.loc[(events.model == "MIRROR_P4") & (events.event == "BREAK_UP") &
                             (events.period == "Y2026")].copy()
    break_valid = break_group.loc[break_group.status_8 == "VALID"]
    retests = {str(k): int(v) for k, v in break_valid.first_retest_8.value_counts(dropna=False).items()}
    break_group["break_open_type"] = np.where(as_bool(break_group.gap_open_above_line),
                                                 "GAP_AÇILIŞ ÜSTÜ", "AÇILIŞ ÇİZGİDE/ALTINDA")
    break_open_groups = grouped_descriptions(break_group, "break_open_type")
    break_detail = {"summary": describe(break_group), "first_retest_8": retests,
                    "by_gap_open": break_open_groups,
                    "gap_open_above_count": int(as_bool(break_valid.gap_open_above_line).sum()),
                    "returned_below_within_8": int(as_bool(break_valid.future_return_below_8).sum()),
                    "above_native_ceiling_at_event": int(as_bool(break_valid.close_above_ceiling).sum())}
    returns = events.loc[(events.model == "MIRROR_P4") & (events.event == "RETURN_DOWN") &
                         (events.period == "Y2026")].copy()
    returns["depth_group"] = returns.above_max_depth_atr.map(lambda x: "UNKNOWN" if pd.isna(x) else
                                                              "0..0,5 ATR" if x <= .5 else
                                                              "0,5..1 ATR" if x <= 1 else ">1 ATR")
    return_groups = grouped_descriptions(returns, "depth_group")
    crossings = events.loc[(events.model == "MIRROR_P4") & (events.event.str.startswith("STATE_CROSS_")) &
                           (events.period == "Y2026")]
    crossing_counts = {str(k): int(v) for k, v in crossings.cross_cause.value_counts().items()}
    departure = events.loc[(events.model == "MIRROR_P4") & (events.event == "DEPART_BELOW") &
                           (events.period == "Y2026")]
    departure_summary: dict[str, Any] = {}
    for horizon in HORIZONS:
        valid = departure.loc[departure[f"status_{horizon}"] == "VALID"]
        departure_summary[str(horizon)] = {"events": len(departure), "valid": len(valid),
            "symbols": int(valid.symbol.nunique()),
            "race": {str(k): int(v) for k, v in valid[f"first_follow_or_return_{horizon}"].value_counts().items()}}
    pairs_all = [matched_pairs(events, x) for x in ("SHIFT_UP", "SHIFT_DOWN")]
    pairs = pd.concat(pairs_all, ignore_index=True)
    if len(pairs):
        pairs = pairs.sort_values(["control_model", "symbol", "target_bar"]).reset_index(drop=True)
    write_csv_gz(pairs, output / "matched_controls.csv.gz")
    matched = {name: matched_summary(frame) for name, frame in zip(("SHIFT_UP", "SHIFT_DOWN"), pairs_all)}
    metas = manifest["symbols"]
    total_eligible = sum(x["coverage"]["_eligible"].get("Y2026", 0) for x in metas)
    coverage = {m: {"eligible_y2026": sum(x["coverage"].get(m, {}).get("eligible_Y2026", 0) for x in metas),
                    "all_eligible_y2026": total_eligible} for m in MODEL_NAMES}
    quality = {
        "selected_symbols": len(manifest["selected_symbols"]), "successful_symbols": manifest["successful_symbols"],
        "errors": manifest["errors"], "h4_bars": sum(x["h4_bars"] for x in metas),
        "daily_bars": sum(x["daily_bars"] for x in metas),
        "first_h4_close": min(x["first_h4_close"] for x in metas),
        "last_h4_close": max(x["last_h4_close"] for x in metas),
        "excluded_unclosed_daily": sum(x["excluded_unclosed_daily"] for x in metas),
        "excluded_unclosed_h4": sum(x["excluded_unclosed_h4"] for x in metas),
        "bad_daily": sum(x["bad_daily_bars_including_30pct_jump"] for x in metas),
        "symbols_bad_daily": sum(x["bad_daily_bars_including_30pct_jump"] > 0 for x in metas),
        "bad_h4": sum(x["bad_h4_bars_including_incomplete_and_30pct_jump"] for x in metas),
        "incomplete_h4": sum(x["incomplete_h4_buckets"] for x in metas),
        "h4_on_suspect_daily_date": sum(x["h4_bars_on_suspect_daily_date"] for x in metas),
        "missing_whole_h4": sum(x["missing_whole_h4_buckets"] for x in metas),
        "zero_volume_hourly_rows_raw": sum(x["raw_audit"]["1h"]["zero_volume_rows"] for x in metas),
    }
    summary = {"quality": quality, "coverage": coverage, "models": summaries, "main_groups": groups,
               "main_concentration": concentration,
               "native_daily_events_2026": native_groups, "break_2026": break_detail,
               "returns_by_above_depth_2026": return_groups, "state_cross_causes_2026": crossing_counts,
               "departure_follow_or_return_2026": departure_summary,
               "matched_controls_2026": matched, "bootstrap": {"seed": SEED, "replicates": BOOTSTRAPS},
               "scope": "descriptive historical research; not a live trading strategy or independent validation"}
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    model_rows = []
    for name in MODEL_NAMES:
        x = summaries[name]["Y2026"]["8"]
        available = pct(coverage[name]["eligible_y2026"], total_eligible)
        model_rows.append((f"| {name} | {fmt(available)} | {x['events']} | {x['valid']} | {x['symbols']} | "
                           f"{fmt(x['down_first_pct'])} | {fmt(x['up_first_pct'])} | {fmt(x['ambiguous_pct'])} | "
                           f"{fmt(x['neither_pct'])} | {fmt(x['median_return_atr'], 2, signed=True)} |"))
    toplu = ["# Stabil direnç replay — toplu bulgular", "",
             "Plan önceden sabittir; yüzdeler geçerli tam ufuklu olayların payıdır. Aynı bar belirsiz ve hiçbiri paydada kalır. Tablolar betimseldir, modeller aynı olayları seçmez.", "",
             "## 20 aday/referans — 2026, TEST sonrası 8 adet 4s bar", "",
             "| Aday | Hazır bar % | Tüm TEST | Geçerli n | Hisse | −1 ATR önce % | +1 ATR önce % | Aynı-bar % | Hiçbiri % | Medyan kapanış ATR |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|", *model_rows, "",
             "Hazır bar %, 20 barı sağlam ve günlük kaynak geçmişi geçerli olan 2026 4s barlarında seviyenin bilinmesi oranıdır; olay yüzdesi değildir. EMA20 dinamik bir kıyas, SHIFT seviyeleri sentetiktir.", ""]
    toplu += [f"Ana TEST için eşit-hisse ağırlıklı aşağı-önce oranı **%{fmt(summaries['MIRROR_P4']['Y2026']['8']['equal_symbol_down_first_pct'])}**; en yoğun beş hisse geçerli olayların **%{fmt(concentration['top_5_symbols_share_pct'])}** bölümünü taşır. Tek bir hisseyi sırayla çıkarınca oran **%{fmt(concentration['leave_one_symbol_out_down_pct_range'][0])}…%{fmt(concentration['leave_one_symbol_out_down_pct_range'][1])}** olur. Ortak gün/olay korelasyonu bu kontrollerde giderilmez.", ""]
    period_rows = [{"group": f"{model} / {period}", **summaries[model][period]["8"]}
                   for model in ("MIRROR_P4", "ROLL20", "SHIFT_UP", "SHIFT_DOWN")
                   for period in ("PRE_2026", "Y2026")]
    toplu.append(result_table("Önceki ve sonraki takvim dilimi — 8 bar", period_rows))
    toplu += ["Bu dilimler bağımsız/kör dış örnek değildir; PRE_2026 için ufku 2026 sınırını aşan olaylar ilgili ufuktan çıkarıldı.", ""]
    for col, title in (("quarter", "Takvim çeyreği"), ("session_close", "Seans kapanış saati"),
                       ("age_group", "O ana kadar bilinen seviye yaşı"),
                       ("native_regime_proxy", "Terslenmiş native aday rejim proxy'si"),
                       ("touch_order", "Temas sırası — geçmişi bilinmeyen ayrı"),
                       ("approach", "Önceki 4 bar hareketi"), ("volume_group", "Önceki 20 bara göre hacim"),
                       ("contact", "TEST anı: zone yaklaşımı / gerçek temas / kapanış"),
                       ("nonoverlap", "Örtüşme duyarlılığı")):
        toplu.append(result_table(title, groups[col]))
    toplu += ["## Native günlük lifecycle olayları — 2026, olay sonrası 8 günlük bar", "", GROUP_HEADER,
              *[summary_row(x["group"], x) for x in native_groups], "",
              "Bunlar 4s olaylarla birleştirilmez. Native olay adı ters yön anlamındadır; aynı günlük bar içindeki birden çok olayın işlem sırası bilinmez.", "",
              "## Yukarı kırılmadan sonra ilk 4s retest — 2026 / 8 bar", "",
              f"Kırılma tüm/geçerli: **{len(break_group)}/{len(break_valid)}**. İlk-retest sınıfları, tüm geçerli kırılmaları payda alır:", "",
              "| Sınıf | n | % |", "|---|---:|---:|",
              *[f"| {k} | {v} | {fmt(pct(v, len(break_valid)))} |" for k, v in sorted(retests.items())], "",
              f"İzleyen 8 barda en az bir kapanışla çizgiye/altına dönen: **{break_detail['returned_below_within_8']}/{len(break_valid)}**. Kırılma mumunun açılışı çizgi üzerinde olan: **{break_detail['gap_open_above_count']}**; bunlar seans içi kesintisiz geçiş değildir.", "",
              result_table("Kırılmada gap / çizgide veya altında açılış", break_open_groups),
              result_table("Üstten aşağı dönüş — önceki yukarı taşma derinliği", return_groups),
              "UNKNOWN: aynı seviye kimliği altında yukarı kırılma ve önceki tüm yol arşivde gözlenmedi veya arada eksik/hatalı bar var. Derinlik kırılma anında sabitlenmiş 4s ATR cinsindendir.", "",
              "## Fiyat dirençten aşağı uzaklaştığında ilk yol", "",
              "Başlangıç: fiyat, önceden bilinen ve değişmeyen referansa göre aşağı yönde 1,5 önceki 4s ATR mesafesine ilk geçer. Takip: direnç eski seviyeden >0,01 aşağı güncellenir. Dönüş: fiyat kapanışı eski dirençte/üstte. Aynı 4s checkpoint'te ikisi de varsa belirsiz; ek süre koşulu yok.", "",
              "| Ufuk | Olay | Geçerli n | Hisse | Çizgi aşağı takip önce | Fiyat dönüş önce | Aynı-bar belirsiz | Hiçbiri | Seviye yok |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
              *[f"| {h} × 4s | {x['events']} | {x['valid']} | {x['symbols']} | {x['race'].get('LEVEL_FOLLOWS_DOWN_FIRST', 0)} | {x['race'].get('PRICE_RETURNS_FIRST', 0)} | {x['race'].get('AMBIGUOUS_SAME_BAR', 0)} | {x['race'].get('NEITHER', 0)} | {x['race'].get('LEVEL_UNAVAILABLE', 0)} |" for h, x in departure_summary.items()], "",
              "Bu mekanik uzaklaşma/izleme yarışı görsel dikey-yatay eşlemesi değildir. Native pivotun dört günlük teyit geometrisi sebebiyle özellikle kısa ufukta yeni çizgi basamağı zaten gecikebilir; bu tablo tek başına fiyatın çizgiyi öngördüğünü göstermez. 1,5 ATR eşiği tek-sembollü teknik pilot sonrasında, tüm evren replay'i öncesinde sabitlendi.", "",
              "## Çizgi / fiyat katkısına göre üst-alt değişimleri", "",
              "| Karşı olgusal neden | n |", "|---|---:|",
              *[f"| {k} | {v} |" for k, v in sorted(crossing_counts.items())], "",
              "PRICE_ONLY: fiyat tek başına yeterli; LINE_ONLY: çizgi tek başına yeterli; BOTH_REQUIRED: birlikte gerekli; EITHER_SUFFICIENT: ikisi de tek başına yeterli. Bu bir fiyat-tepkisi veya nedensel piyasa etkisi ölçümü değildir.", "",
              "## Yakındaki sahte-seviye eşleşmeleri — 2026", ""]
    for name, m in matched.items():
        toplu.append(f"- **{name}:** sonuç görülmeden eşleşen {m['pairs_before_censor']} çift; ikisi de tam/geçerli {m['valid_pairs']} çift, {m['symbols']} hisse; {m.get('censored_pairs', 0)} çift dışlandı.")
        if m["valid_pairs"]:
            lo, hi = m["bootstrap_95_pp"]
            wl, wh = m["worst_case_same_bar_difference_pp"]
            toplu.append(f"  Ana/sahte −1 ATR önce: **{m['target_down_first']}/{m['valid_pairs']} (%{fmt(m['target_down_pct'])}) / {m['control_down_first']}/{m['valid_pairs']} (%{fmt(m['control_down_pct'])})**; fark **{fmt(m['difference_pp'], 1, signed=True)} puan**, hisse-kümeli %95 bootstrap **{fmt(lo, 1, signed=True)}…{fmt(hi, 1, signed=True)}**. Aynı-bar belirsizler ana/kontrol {m['target_ambiguous']}/{m['control_ambiguous']}; bunların uç atamalarıyla fark aralığı **{fmt(wl, 1, signed=True)}…{fmt(wh, 1, signed=True)}** puan. Eşlerde medyan mutlak mesafe farkı {fmt(m['median_abs_gap_difference_atr'], 2)} ATR, önceki hareket farkı {fmt(m['median_abs_prior_move_difference_atr'], 2)} ATR.")
    toplu += ["", "Eşler aynı hisse/çeyrek/seans/mesafe ve önceki 4-bar hareket kovasında; aralarında ≥8 bar, tekrarsız ve en yakın zamanlıdır. Önce yalnız bilinen koşullarla eşleşir, sonra sansür uygulanır. Ortak gün şokları ve çoklu deneme düzeltilmediğinden aralık nedensel güven aralığı değildir.", ""]
    (output / "toplu_bulgular.md").write_text("\n".join(toplu), encoding="utf-8")

    primary = summaries["MIRROR_P4"]["Y2026"]["8"]
    ref = summaries["ROLL20"]["Y2026"]["8"]
    refs = []
    for name in ("SHIFT_UP", "SHIFT_DOWN"):
        m = matched[name]
        if m.get("valid_pairs"):
            lo, hi = m["bootstrap_95_pp"]
            refs.append(f"{name} eşleşmesinde fark {fmt(m['difference_pp'], 1, signed=True)} puan (n={m['valid_pairs']}; hisse-kümeli %95 {fmt(lo, 1, signed=True)}…{fmt(hi, 1, signed=True)})")
    statuses = ", ".join(f"{k}: {v}" for k, v in primary["statuses"].items())
    native_test = next((r for r in native_groups if r["group"] == "RESISTANCE_TESTED"), None)
    previous_main = summaries["MIRROR_P4"]["PRE_2026"]["8"]
    horizon_line = "; ".join(f"{h} bar: n={summaries['MIRROR_P4']['Y2026'][str(h)]['valid']}, −1 önce %{fmt(summaries['MIRROR_P4']['Y2026'][str(h)]['down_first_pct'])}, +1 önce %{fmt(summaries['MIRROR_P4']['Y2026'][str(h)]['up_first_pct'])}" for h in HORIZONS)
    report = f"""# Stabil desteğinin karşıtı direnç olur mu? — tarihsel replay

**Kısa cevap:** Destek hesabının matematiksel karşıtı olan teyitli tepe çizgisi
oluşturulup test edildi; aşağıdaki sayılar direnç etrafındaki **gözlenen davranışı**
gösterir. Tek başına çizginin düşüşe neden olduğunu, işlem avantajı veya canlı
alarm başarısı sağladığını kanıtlamaz. 20 aday ve referansın tamamı
[plana](PLAN.md) göre aynı arşivde çalıştırıldı; en iyi sonuca bakıp yeni canlı
kural seçilmedi. İlk tam koşu denetiminde gap ile temas ayrımı ve şüpheli gün
sansürü düzeltildi, ardından tüm arşiv yeniden çalıştırıldı.

## En önemli sonuçlar — 2026, testten sonraki 8 adet 4s bar

- **Birebir terslenmiş çizgi:** {primary['events']} TEST olayının {primary['valid']}'i geçerli ({primary['symbols']} hisse); olay kapanışından sonraki ±1 ATR yarışında **aşağı önce %{fmt(primary['down_first_pct'])}**, **yukarı önce %{fmt(primary['up_first_pct'])}**, aynı-bar belirsiz %{fmt(primary['ambiguous_pct'])}, hiçbiri %{fmt(primary['neither_pct'])}. Medyan son kapanış **{fmt(primary['median_return_atr'], 2, signed=True)} 4s ATR**; 8 barda medyan aşağı/yukarı uç hareket {fmt(primary['median_down_excursion_atr'], 2)}/{fmt(primary['median_up_excursion_atr'], 2)} ATR. Bunlar işlem getirisi değil.
- Bu geçerli TEST'lerin {primary.get('near_only', 0)}'i yalnız yaklaşma bandına girdi; {primary.get('gap_above_no_touch', 0)} tanesinde gap sonrası mumun tamamı çizgi üzerinde kaldı. **Tepe seviyesi mumun yüksek–düşük aralığında olan {primary.get('real_touch', 0)} olayın {primary.get('wick_reject', 0)}'i (%{fmt(primary.get('wick_reject_pct_of_real_touch'))}) aynı mumda çizgide/altında kapandı**. Mum içi önce-sonra bilinmiyor.
- **Basit 20 günlük tepe referansı:** {ref['valid']} geçerli TEST'te aşağı/yukarı önce %{fmt(ref['down_first_pct'])}/%{fmt(ref['up_first_pct'])}. Olay kümesi ve seviye mesafesi farklı olduğu için bu ham tablo doğrudan üstünlük veya nedensel etki göstermez.
- **Eşleştirilmiş yakın sahte çizgiler:** {'; '.join(refs) if refs else 'yeterli geçerli eş bulunmadı'}. Bu aralıklar ortak piyasa günlerini, kalıntı kovaiçi farkları, çoklu hipotezleri ve önceden incelenmiş arşivi düzeltmez.
- **Dönem karşılaştırması:** 2025 kesitindeki {previous_main['valid']} geçerli TEST'te aşağı/yukarı önce %{fmt(previous_main['down_first_pct'])}/%{fmt(previous_main['up_first_pct'])}; bu da bağımsız yeni veri değil.
- **Ufuk duyarlılığı:** {horizon_line}. Geçerli n ve dört sonuç sınıfı [toplu tabloda](toplu_bulgular.md).
- **Native günlük gerçek TESTED olayı:** {native_test['valid'] if native_test else 0} geçerli olayda sonraki 8 **günlük** barda aşağı/yukarı önce %{fmt(native_test['down_first_pct'] if native_test else None)}/%{fmt(native_test['up_first_pct'] if native_test else None)}. Bu grup 4s yaklaşma bandından ayrı tanımlanır.

## Kullanıcının fiyat/çizgi yolu ve native karşılık

[Kullanıcı davranış dosyası](../STABIL_DAVRANIS_MODELI.md) eski özgün belge
bulunamadığı için konuşmadan yeniden kaydedilmiştir. Onun `uzaklaşma → çizgi
takibi → yataylaşma → test/kırılma → dönüş` sırası, ters yönde TEST, üstte
kapanış, retest ve aşağı dönüş olarak ölçüldü. Görsel “dikey/yatay” ile bu
kodun rejim etiketleri henüz birebir eşlenmedi; tablolar **proxy**, onaylı görsel
tanım değil. Native teyide keyfî 2/3/5 mum bekleme eklenmedi.

Tersleme değiştirilmemiş native günlük destek çekirdeğine `O'=-O, H'=-L,
L'=-H, C'=-C` girdisi verip sonucu tekrar tersleyerek yapılır: son teyitli günlük
tepe, iki tepe + iki dip yapısı ve `tavan=tepe+0,35 × köken günlük ATR`.
Ayrıca günlük native TESTED/HELD/BREACHED/tavan kırımı/geri dönüş olayları
ters anlamla ve **günlük** ufukla hesaplanmıştır. 4s TEST tanımı ve diğer 19
aday araştırma ölçümüdür; canlı 4s ok/alarm kurallarının birebir ters çevrilip
uygulandığı iddia edilmez.

**Kırılma ve dönüş:** {break_detail['summary']['valid']} geçerli yukarı kapanış
kırılmasının {break_detail['returned_below_within_8']} tanesinde (%{fmt(pct(break_detail['returned_below_within_8'], break_detail['summary']['valid']))}) sonraki 8 barda
çizgiye/altına kapanış görüldü. İlk retestlerin gap/açılış ile temiz üstten
temas ayrımı ve önceden bilinen taşma derinliği grupları
[toplu tablodadır](toplu_bulgular.md). Fiyatın çizgiye göre taraf değiştirmesi
fiyatın hareketinden, çizginin güncellenmesinden veya ikisinden kaynaklanabilir;
bu katkılar da ayrı sayıldı. İlk gözlenen çizginin eski temas sayısı ve kırılma
süresi bilinmiyorsa UNKNOWN bırakıldı. 1,5 ATR uzaklaşma sonrası eski çizgiye
fiyat dönüşü / çizginin fiyatı takip yarışı da ölçüldü; kısa ufukta 4 günlük
pivot teyidinin doğal gecikmesi özellikle dikkate alınmalı.

## Veri, sansür ve dürüst sınırlar

- {quality['successful_symbols']}/{quality['selected_symbols']} uygun hisse; hata **{len(quality['errors'])}**. {quality['daily_bars']} kapalı native günlük, {quality['h4_bars']} kapalı 4s bar; 4s kapsamı {quality['first_h4_close']} → {quality['last_h4_close']} (İstanbul).
- İndirme anında henüz kapanmamış {quality['excluded_unclosed_daily']} günlük ve {quality['excluded_unclosed_h4']} adet 4s bar çıkarıldı. {quality['incomplete_h4']} eksik saatlik bileşenli 4s kova, günlük oturumlarla karşılaştırmada {quality['missing_whole_h4']} beklenen ama görünmeyen 4s kova; {quality['symbols_bad_daily']} hissede {quality['bad_daily']} şüpheli günlük bar (> %30 sıçrama dahil) saptandı. Şüpheli günlük bar sonrasındaki tüm ufuklar da ATR/pivot geçmişi korunamadığı için ihtiyatla dışlandı. Geçersiz geçmiş/gelecek ve tamamlanmamış ufuk dışlandı; ana 8-bar durumları: {statuses}. Bu durum önceliklerinden bağımsız olarak sağdan sansürlü olay: {primary['right_censored_any']}.
- Daily seviye, 4s mumun yalnız kapanışında değil **başında** biliniyorsa o mumun OHLC testi yapılır. Pivot kökeni teyit zamanı değildir. Veri eksikliği, ücretsiz arşiv fiyat düzeltmeleri, aynı anda çift eşik, kısa seans-sonu hacmi ve gün/hisse korelasyonu sonuçları etkiler. 4s ATR'nin Wilder yumuşatmasında 20 bar öncesindeki bir şokun etkisi tamamen sıfırlanmaz. Günlük ve saatlik kaynakta birlikte eksik bir seans ve bütün kurumsal işlemler bağımsız doğrulanmış değildir.
- `PRE_2026` ve `Y2026` takvim karşılaştırmasıdır; arşiv daha önce araştırıldığından gerçek bağımsız/kör örnek değildir. Çok sayıda varyant karşılaştırıldı; yüksek yüzdeli adayı seçip doğrulanmış ilan etmeyin. İleri tarihte, aynı tanımlarla, görsel etiket ve gerçek işlem maliyetiyle yeni test gerekir.

## Dosyalar ve yeniden üretim

[Ön kayıt ve 20 adayın tanımı](PLAN.md) · [Tüm paydalı tablolar](toplu_bulgular.md) · [somut grafik örnekleri](ornekler.md) · [doğrulama](DOGRULAMA.md) · [makine özeti](summary.json) · [4s olaylar](events_4h.csv.gz) · [native günlük olaylar](native_daily_events.csv.gz) · [eşleştirilmiş kontroller](matched_controls.csv.gz) · [veri/kod hash ve kalite manifesti](manifest.json).

```bash
python -m research.stabil_resistance_replay --workers 4
python -m research.stabil_resistance_report
python -m research.stabil_resistance_examples
python -m research.stabil_resistance_verify
pytest -q test_stabil_resistance_replay.py
```

Çalışma yalnız yerel arşiv ve araştırma dosyalarını kullanır; canlı bot, Telegram,
üretim filtresi ve grafik kodu değiştirilmemiştir.
"""
    (output / "RAPOR.md").write_text(report, encoding="utf-8")
    print(json.dumps({"quality": quality, "mirror_2026_8": primary, "matched_controls": matched}, ensure_ascii=False, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    run(args.output)


if __name__ == "__main__":
    main()
