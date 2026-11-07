"""Create a symmetric, descriptive support/resistance research report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research.stabil_resistance_replay import HORIZONS, ROOT, sha, write_csv_gz
from research.stabil_resistance_report import BOOTSTRAPS, SEED, as_bool, fmt, matched_pairs, matched_summary, number, pct
from research.stabil_support_resistance_compare import LEGACY_MANIFEST, OUTPUT

FIRST_LABELS = ("REACTION_FIRST", "BREACH_SIDE_FIRST", "AMBIGUOUS_SAME_BAR", "NEITHER")
DEPART_LABELS = ("LEVEL_FOLLOWS_FAVORABLE_FIRST", "PRICE_RETURNS_FIRST", "AMBIGUOUS_SAME_BAR", "NEITHER", "LEVEL_UNAVAILABLE")
RACE24_LABELS = ("LINE_FAVORABLE_FIRST", "PRICE_RETURN_FIRST", "PRICE_RECLAIM_FIRST", "LINE_ADVERSE_FIRST", "AMBIGUOUS_SAME_BAR", "NEITHER", "LEVEL_UNAVAILABLE")


def counts(series: pd.Series) -> dict[str, int]:
    return {str(k): int(v) for k, v in series.value_counts(dropna=False).items()}


def describe(group: pd.DataFrame, horizon: int = 8) -> dict[str, Any]:
    valid = group.loc[group[f"status_{horizon}"] == "VALID"]
    n = len(valid)
    vc = {k: int((valid[f"first_1atr_{horizon}"] == k).sum()) for k in FIRST_LABELS}
    out: dict[str, Any] = {"events": len(group), "valid": n, "symbols": int(valid.symbol.nunique()),
                           "statuses": counts(group[f"status_{horizon}"]),
                           "right_censored_any": int(as_bool(group[f"right_censored_{horizon}"]).sum()),
                           "first_counts": vc, "reaction_first_pct": pct(vc["REACTION_FIRST"], n),
                           "breach_side_first_pct": pct(vc["BREACH_SIDE_FIRST"], n),
                           "ambiguous_pct": pct(vc["AMBIGUOUS_SAME_BAR"], n), "neither_pct": pct(vc["NEITHER"], n),
                           "median_reaction_return_atr": number(valid[f"reaction_return_atr_{horizon}"].median()) if n else None,
                           "equal_symbol_reaction_first_pct": number(valid.assign(_r=(valid[f"first_1atr_{horizon}"] == "REACTION_FIRST").astype(float)).groupby("symbol")["_r"].mean().mean()*100) if n else None}
    if n and sum(vc.values()) != n:
        raise AssertionError("valid observations have missing or unknown 1-ATR race label")
    if "contact" in valid:
        touch = valid.contact.isin(("TOUCH_CLOSE_SAFE", "TOUCH_CLOSE_BREACHED"))
        out.update({"contacts": counts(valid.contact), "real_touch": int(touch.sum()),
                    "real_touch_close_safe": int((valid.contact == "TOUCH_CLOSE_SAFE").sum()),
                    "real_touch_close_safe_pct": pct((valid.contact == "TOUCH_CLOSE_SAFE").sum(), touch.sum())})
    return out


def grouped(frame: pd.DataFrame, column: str, horizon: int = 8) -> list[dict[str, Any]]:
    return [{"group": "UNKNOWN" if pd.isna(key) else str(key), **describe(part, horizon)}
            for key, part in frame.groupby(column, sort=True, dropna=False)]


def descriptive_table(title: str, rows: list[dict[str, Any]]) -> str:
    header = ("| Grup | Tüm | Geçerli n | Hisse | Tepki yönü önce % | Ters yön önce % | Aynı-bar % | Hiçbiri % | Medyan tepki getirisi ATR |\n"
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    body = [f"| {r['group']} | {r['events']} | {r['valid']} | {r['symbols']} | {fmt(r['reaction_first_pct'])} | {fmt(r['breach_side_first_pct'])} | {fmt(r['ambiguous_pct'])} | {fmt(r['neither_pct'])} | {fmt(r['median_reaction_return_atr'], 2, signed=True)} |" for r in rows]
    return f"### {title}\n\n{header}\n" + "\n".join(body) + "\n"


def breakdown(group: pd.DataFrame, name: str, labels: tuple[str, ...], status: str) -> dict[str, Any]:
    valid = group.loc[group[status] == "VALID"]
    vc = {label: int((valid[name] == label).sum()) for label in labels}
    if len(valid) and sum(vc.values()) != len(valid):
        raise AssertionError(f"valid path observations lack known label: {name}")
    return {"events": len(group), "valid": len(valid), "symbols": int(valid.symbol.nunique()),
            "statuses": counts(group[status]), "counts": vc, "pct": {k: pct(v, len(valid)) for k, v in vc.items()}}


def matched_side_comparison(tests: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Reuse the pre-outcome resistance matcher with explicit direction conversion."""
    work = tests.copy()
    work["model"] = np.where(work.side == "SUPPORT", "MIRROR_P4", "OPPOSITE_SIDE")
    work["first_1atr_8"] = work.first_1atr_8.replace({"REACTION_FIRST": "DOWN_FIRST", "BREACH_SIDE_FIRST": "UP_FIRST"})
    work["return_atr_8"] = work.reaction_return_atr_8
    pairs = matched_pairs(work, "OPPOSITE_SIDE")
    metrics = matched_summary(pairs)
    if not pairs.empty:
        pairs = pairs.rename(columns={"target_bar": "support_bar", "control_bar": "resistance_bar",
                                      "target_time": "support_time", "control_time": "resistance_time",
                                      "target_gap_atr": "support_gap_atr", "control_gap_atr": "resistance_gap_atr",
                                      "target_prior_move_atr": "support_prior_move_atr", "control_prior_move_atr": "resistance_prior_move_atr",
                                      "target_status_8": "support_status_8", "control_status_8": "resistance_status_8",
                                      "target_first_8": "support_first_8", "control_first_8": "resistance_first_8",
                                      "target_return_8": "support_reaction_return_atr_8", "control_return_8": "resistance_reaction_return_atr_8"})
        for name in ("support_first_8", "resistance_first_8"):
            pairs[name] = pairs[name].replace({"DOWN_FIRST": "REACTION_FIRST", "UP_FIRST": "BREACH_SIDE_FIRST"})
    # matcher field names say down because its historical orientation was resistance;
    # copy to explicit names and delete the misleading aliases.
    for old, new in (("target_down_first", "support_reaction_first"), ("control_down_first", "resistance_reaction_first"),
                     ("target_down_pct", "support_reaction_pct"), ("control_down_pct", "resistance_reaction_pct"),
                     ("target_ambiguous", "support_ambiguous"), ("control_ambiguous", "resistance_ambiguous"),
                     ("target_median_return_atr", "support_median_reaction_return_atr"),
                     ("control_median_return_atr", "resistance_median_reaction_return_atr")):
        if old in metrics:
            metrics[new] = metrics.pop(old)
    return pairs, metrics


def group_table_rows(frame: pd.DataFrame, column: str) -> list[dict[str, Any]]:
    out = []
    for side in ("SUPPORT", "RESISTANCE"):
        for row in grouped(frame.loc[frame.side == side], column):
            row["group"] = f"{side} / {row['group']}"
            out.append(row)
    return out


def race_table(title: str, rows: list[dict[str, Any]], labels: tuple[str, ...]) -> str:
    header = "| Grup | Tüm | Geçerli n | Hisse | " + " | ".join(labels) + " |\n"
    header += "|---|---:|---:|---:|" + "---:|"*len(labels)
    body = [f"| {r['group']} | {r['events']} | {r['valid']} | {r['symbols']} | "
            + " | ".join(f"{r['counts'][k]} (%{fmt(r['pct'][k])})" for k in labels) + " |" for r in rows]
    return f"### {title}\n\n{header}\n" + "\n".join(body) + "\n"


def run(output: Path) -> dict[str, Any]:
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    for filename, digest in manifest["outputs_sha256"].items():
        if sha(output/filename) != digest:
            raise ValueError(f"input output hash mismatch: {filename}")
    for name, digest in manifest["source_sha256"].items():
        if sha(ROOT/name) != digest:
            raise ValueError(f"source changed after the comparison replay: {name}")
    if sha(LEGACY_MANIFEST) != manifest["legacy_support_manifest_sha256"]:
        raise ValueError("legacy universe manifest changed")
    events = pd.read_csv(output/"events_4h.csv.gz", low_memory=False)
    native = pd.read_csv(output/"events_native_daily.csv.gz", low_memory=False)
    questions = pd.read_csv(output/"legacy_like_checkpoints.csv.gz", low_memory=False)
    if len(events) != manifest["events_4h"] or len(native) != manifest["events_native_daily"] or len(questions) != manifest["legacy_like_checkpoint_rows"]:
        raise ValueError("manifest row counts differ")
    legacy = json.loads(LEGACY_MANIFEST.read_text(encoding="utf-8"))
    old_symbols = set(legacy["symbols"])
    selected_old = sorted(old_symbols.intersection(manifest["selected_symbols"]))
    tests = events[events.event == "TEST"].copy()
    current = tests[tests.period == "Y2026"].copy()
    main: dict[str, Any] = {}
    for period in ("PRE_2026", "Y2026"):
        main[period] = {str(h): {side: describe(tests[(tests.period == period) & (tests.side == side)], h)
                                 for side in ("SUPPORT", "RESISTANCE")} for h in HORIZONS}
    touch = current[current.contact.isin(("TOUCH_CLOSE_SAFE", "TOUCH_CLOSE_BREACHED"))]
    touch_summary = {side: describe(touch[touch.side == side]) for side in ("SUPPORT", "RESISTANCE")}
    event_groups: dict[str, Any] = {}
    for name in ("BREAK_TO_ADVERSE_SIDE", "RETURN_TO_SAFE_SIDE", "DEPART_FAVORABLE", "STATE_TO_ADVERSE_SIDE", "STATE_TO_SAFE_SIDE"):
        frame = events[(events.event == name) & (events.period == "Y2026")].copy()
        event_groups[name] = {side: describe(frame[frame.side == side]) for side in ("SUPPORT", "RESISTANCE")}
    break_details: dict[str, Any] = {}
    return_details: dict[str, Any] = {}
    state_causes: dict[str, Any] = {}
    departure: dict[str, Any] = {}
    for side in ("SUPPORT", "RESISTANCE"):
        br = events[(events.side == side) & (events.event == "BREAK_TO_ADVERSE_SIDE") & (events.period == "Y2026")]
        b = br[br.status_8 == "VALID"]
        break_details[side] = {"summary": describe(br), "returned_safe_within_8": int(as_bool(b.future_close_safe_8).sum()),
                               "returned_safe_pct": pct(as_bool(b.future_close_safe_8).sum(), len(b)),
                               "gap_open_to_adverse": int(as_bool(b.gap_open_to_adverse_side).sum()),
                               "first_retest_8": counts(b.first_retest_8)}
        rt = events[(events.side == side) & (events.event == "RETURN_TO_SAFE_SIDE") & (events.period == "Y2026")].copy()
        depth = rt.adverse_max_depth_atr
        rt["depth"] = np.where(depth.isna(), "UNKNOWN", np.where(depth <= .5, "0..0.5", np.where(depth <= 1.2, "0.5..1.2", ">1.2")))
        return_details[side] = grouped(rt, "depth")
        for direction in ("STATE_TO_ADVERSE_SIDE", "STATE_TO_SAFE_SIDE"):
            st = events[(events.side == side) & (events.event == direction) & (events.period == "Y2026")]
            sv = st[st.status_8 == "VALID"]
            state_causes[f"{side}/{direction}"] = {"events": len(st), "valid_8": len(sv), "counts": counts(sv.cross_cause)}
        dep = events[(events.side == side) & (events.event == "DEPART_FAVORABLE") & (events.period == "Y2026")]
        departure[side] = {str(h): breakdown(dep, f"first_follow_or_return_{h}", DEPART_LABELS, f"status_{h}") for h in HORIZONS}
    pairs, match = matched_side_comparison(tests)
    write_csv_gz(pairs, output/"matched_support_resistance.csv.gz")
    proxy_tables: dict[str, Any] = {}
    old100: dict[str, Any] = {}
    for question in ("A01", "B04", "C02", "F01"):
        q = questions[questions.question == question]
        proxy_tables[question] = {}
        for period in ("PRE_2026", "Y2026"):
            proxy_tables[question][period] = {}
            for side in ("SUPPORT", "RESISTANCE"):
                buckets = []
                qq = q[(q.side == side) & (q.period == period)]
                for bucket, sub in qq.groupby("bucket", sort=True, dropna=False):
                    buckets.append({"group": str(bucket), "result_8": describe(sub),
                                    "path_24": breakdown(sub, "race_first_24", RACE24_LABELS, "race_status_24")})
                proxy_tables[question][period][side] = buckets
        qold = q[q.symbol.isin(selected_old)]
        old100[question] = {}
        for side in ("SUPPORT", "RESISTANCE"):
            old100[question][side] = [{"group": str(bucket), "result_8": describe(sub),
                                      "path_24": breakdown(sub, "race_first_24", RACE24_LABELS, "race_status_24")}
                                     for bucket, sub in qold[qold.side == side].groupby("bucket", sort=True, dropna=False)]
    native_groups = group_table_rows(native[(native.period == "Y2026") & (native.event.isin(("TESTED", "HELD", "BREACHED", "RETURN_TO_SAFE_SIDE", "BOUNDARY_BROKEN", "REBASED_FAVORABLE", "REBASED_ADVERSE")))], "event")
    current = current.copy()
    current["observed_test_order"] = np.where(current.history_of_tests == "UNKNOWN", "UNKNOWN", np.where(current.test_ordinal == 1, "FIRST_OBSERVED", np.where(current.test_ordinal == 2, "SECOND_OBSERVED", "THIRD_PLUS_OBSERVED")))
    group_details: dict[str, list[dict[str, Any]]] = {}
    for col in ("quarter", "native_regime_proxy", "observed_test_order", "contact"):
        group_details[col] = group_table_rows(current, col)
    nonoverlap = current[as_bool(current.nonoverlap_8)]
    group_details["nonoverlap_8"] = [{"group": f"{side} / {subset}", **describe(part)}
                                     for side in ("SUPPORT", "RESISTANCE")
                                     for subset, part in (("ALL", current[current.side == side]),
                                                          ("NONOVERLAP_8", nonoverlap[nonoverlap.side == side]))]
    old_support = pd.read_csv(ROOT/"docs/arastirma/stabil_100_sonuclar/STABIL_DAVRANIS_48_TABLO.csv")
    historical = old_support[old_support.question_id.isin([f"STB-BHV-{q}" for q in ("A01", "B04", "C02", "F01")]) & (old_support.horizon_4h == 8)]
    historical_rows = json.loads(historical.to_json(orient="records"))
    summary: dict[str, Any] = {"scope": "historical descriptive, pre-explored archive, not blind or causal, not trading performance",
        "selected_symbols": len(manifest["selected_symbols"]), "old_support_symbols_in_current_universe": len(selected_old),
        "old_support_universe_missing": sorted(old_symbols-set(selected_old)),
        "main_test": main, "real_touch_2026": touch_summary, "event_groups_2026": event_groups,
        "break_2026": break_details, "return_by_depth_2026": return_details, "state_cross_causes_2026": state_causes,
        "departure_2026": departure, "matched_2026": match, "native_daily_2026": native_groups,
        "test_subgroups_2026": group_details, "legacy_like_questions": proxy_tables,
        "legacy_like_old100_current_data": old100, "previously_saved_old_support_rows": historical_rows,
        "bootstrap": {"seed": SEED, "replicates": BOOTSTRAPS}}
    (output/"summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")

    lines = ["# Destek–direnç eş-kural karşılaştırması — bütün tablolar", "",
             "Tepki yönü destekte yukarı, dirençte aşağıdır; ters yön bunun karşıtıdır. Payda tam ufuklu geçerli olaydır; aynı-bar ve hiçbiri paydada kalır. 4s ve günlük tablolar birleştirilmez. Aynı hisse ve piyasa günündeki gözlemler bağımsız değildir.", ""]
    lines.append(descriptive_table("Ana 4s TEST: dönem ve ufuk", [{"group": f"{period} / {side} / {h} bar", **main[period][str(h)][side]}
                  for period in ("PRE_2026", "Y2026") for h in HORIZONS for side in ("SUPPORT", "RESISTANCE")]))
    lines.append(descriptive_table("Gerçek temas eden 4s TEST — 2026 / 8 bar", [{"group": side, **touch_summary[side]} for side in ("SUPPORT", "RESISTANCE")]))
    for col, title in (("quarter", "TEST / çeyrek"), ("native_regime_proxy", "TEST / önceden bilinen aday rejim"),
                       ("observed_test_order", "TEST / gözlenen yaklaşım sırası"), ("contact", "TEST / yaklaşma ve gerçek temas"),
                       ("nonoverlap_8", "TEST / örtüşme duyarlılığı")):
        lines.append(descriptive_table(title, group_details[col]))
    lines += ["Sıra, seviye kimliği belirlendikten sonraki 4s zone yaklaşımıdır; `UNKNOWN` başlangıcı gözlenmemiş epizottur. Bu tanım C02'nin günlük temas sırasıyla aynı değildir.", ""]
    lines.append(descriptive_table("Kırılma ve geri dönme olayları — 2026 / 8 bar", [{"group": f"{name} / {side}", **event_groups[name][side]}
                  for name in ("BREAK_TO_ADVERSE_SIDE", "RETURN_TO_SAFE_SIDE") for side in ("SUPPORT", "RESISTANCE")]))
    lines += ["### Kırılmanın ardından dondurulan ilk çizgiye dönüş ve ilk retest", ""]
    for side, detail in break_details.items():
        lines.append(f"- **{side}:** {detail['summary']['events']} olay, {detail['summary']['valid']} geçerli; 8 bar içinde kapanışla güvenli tarafa en az bir kez dönen {detail['returned_safe_within_8']} (%{fmt(detail['returned_safe_pct'])}); gap ile ters tarafta açılan {detail['gap_open_to_adverse']}. İlk retest sınıfları: `{json.dumps(detail['first_retest_8'], ensure_ascii=False)}`.")
    lines += ["", "İlk kez dönme kalıcı tutunma veya kârlı işlem anlamına gelmez. Açılış/temas ayrımı aynı bar içi sıralama sağlamaz.", ""]
    for side in ("SUPPORT", "RESISTANCE"):
        lines.append(descriptive_table(f"Güvenli tarafa dönüşte geçmiş taşma derinliği / {side}", return_details[side]))
    lines += ["Bilinmeyen derinlik; aynı çizgi kimliğinde kırılma başlangıcı görülmeyen veya eksik/hatalı geçmişi olan epizottur.", ""]
    lines.append(race_table("1,5 önceki 4s ATR uzaklaşmadan sonra çizgi–fiyat yarışı / 2026", [{"group": f"{side} / {h} bar", **departure[side][str(h)]} for h in HORIZONS for side in ("SUPPORT", "RESISTANCE")], DEPART_LABELS))
    lines += ["Çizginin takip yönünde >0,01 güncellenmesi ile kapanışın eski çizgiye dönmesi yarışır. Doğal dört-günlük pivot teyidi kısa ufukta çizgi güncellemesini mekanik olarak geciktirebilir.", "", "### Fiyat/çizgi taraf değişimi — 2026, temiz 8-bar altkümesi", "", "| Taraf / değişim | Toplam | Geçerli | Counterfactual sebep sayıları |", "|---|---:|---:|---|"]
    for group, values in state_causes.items():
        lines.append(f"| {group} | {values['events']} | {values['valid_8']} | {json.dumps(values['counts'], ensure_ascii=False)} |")
    lines += ["", "PRICE_ONLY, LINE_ONLY, BOTH_REQUIRED, EITHER_SUFFICIENT yalnız iki karşı-olgusal aritmetik karşılaştırmadır; piyasa nedenselliği değildir.", ""]
    lines.append(descriptive_table("Native günlük lifecycle: sonraki 8 günlük bar / 2026", native_groups))
    lines += ["Burada ±1 **günlük** ATR ve 8 **günlük** bar vardır; 4s TEST ile eşitlenmez. Bir günlük mumdaki birden çok olayın intrabar sırası bilinmez.", "", "## Eski soru tariflerine yakın ortak günlük-ATR ölçümü", "", "Eski A01/B04/C02/F01 seçimlerini iki yönde tekrar uygular; bu 48 sorunun tam replikasyonu değildir. 8-bar getiri/±1 ATR'de günlük ATR; 24-bar yarışta tam ve temiz gözlem şartı. C02 ZERO/UNKNOWN önceki cevabın geçerli temas kovası değildir. Yeni günlük seviye/ATR mum başında bilinmeden C02 mum aralığı değerlendirilmez. Tekrarlanan checkpoint'ler bağımsız olay değildir.", ""]
    for question in ("A01", "B04", "C02", "F01"):
        for period in ("PRE_2026", "Y2026"):
            raw = [{"group": f"{side} / {item['group']}", **item["result_8"]} for side in ("SUPPORT", "RESISTANCE") for item in proxy_tables[question][period][side]]
            lines.append(descriptive_table(f"{question} / {period} / 8 × 4s, günlük ATR", raw))
        if question in ("A01", "F01"):
            raw_path = [{"group": f"{side} / {item['group']}", **item["path_24"]} for side in ("SUPPORT", "RESISTANCE") for item in proxy_tables[question]["Y2026"][side]]
            lines.append(race_table(f"{question} / 2026 / eski çizgi–fiyat yarışı, 24 × 4s", raw_path, RACE24_LABELS))
        old_rows = [{"group": f"{side} / {item['group']}", **item["result_8"]} for side in ("SUPPORT", "RESISTANCE") for item in old100[question][side]]
        lines.append(descriptive_table(f"{question} / eski 100 hisse kesişimi / yeni veri, iki dönem birlikte", old_rows))
    lines += ["## Eşleştirme — destek TEST ile direnç TEST", ""]
    if match["valid_pairs"]:
        lo, hi = match["bootstrap_95_pp"]
        lines += [f"Sonuç görülmeden {match['pairs_before_censor']} çift, ikisi de 8 bar tam/geçerli {match['valid_pairs']} çift ({match['symbols']} hisse); {match['censored_pairs']} çift dışlandı.",
                  f"Destek yukarı-önce **{match['support_reaction_first']}/{match['valid_pairs']} (%{fmt(match['support_reaction_pct'])})**, direnç aşağı-önce **{match['resistance_reaction_first']}/{match['valid_pairs']} (%{fmt(match['resistance_reaction_pct'])})**; destek−direnç farkı **{fmt(match['difference_pp'], signed=True)} yüzde puan**, hisse-kümeli %95 bootstrap **{fmt(lo, signed=True)}…{fmt(hi, signed=True)}**. Aynı-bar belirsiz destek/direnç: {match['support_ambiguous']}/{match['resistance_ambiguous']}. Mesafe/önceki hareket mutlak farkı medyanı {fmt(match['median_abs_gap_difference_atr'], 2)}/{fmt(match['median_abs_prior_move_difference_atr'], 2)} ATR."]
    else:
        lines += ["Yeterli geçerli eş yok."]
    lines += ["", "Aynı hisse, çeyrek, seans, başlangıç çizgi mesafesi kovası ve tepki yönüne göre önceki 4-bar hareket kovasında; aralarında en az 8 bar, en yakın zamanda ve direnç tarafında tekrarsız. Eşler sonuçlara bakılmadan seçilir, sonra sansürlenir. Aralık ortak gün etkisi, artık trend/kova farkları ve çoklu denemeleri düzeltmez; nedensel değildir.", ""]
    (output/"toplu_bulgular.md").write_text("\n".join(lines), encoding="utf-8")

    s, r = main["Y2026"]["8"]["SUPPORT"], main["Y2026"]["8"]["RESISTANCE"]
    st, rt = touch_summary["SUPPORT"], touch_summary["RESISTANCE"]
    b1, b2 = break_details["SUPPORT"], break_details["RESISTANCE"]
    def path_summary(side: str) -> str:
        x = departure[side]["8"]
        return (f"{x['valid']} geçerli olayda çizgi takip önce {x['counts']['LEVEL_FOLLOWS_FAVORABLE_FIRST']} "
                f"(%{fmt(x['pct']['LEVEL_FOLLOWS_FAVORABLE_FIRST'])}), fiyat eski çizgiye dönüş önce {x['counts']['PRICE_RETURNS_FIRST']} "
                f"(%{fmt(x['pct']['PRICE_RETURNS_FIRST'])}), aynı-bar {x['counts']['AMBIGUOUS_SAME_BAR']}, hiçbiri {x['counts']['NEITHER']}")
    match_text = (f"{match['valid_pairs']} geçerli çiftte destek %{fmt(match['support_reaction_pct'])}, direnç %{fmt(match['resistance_reaction_pct'])}; destek−direnç **{fmt(match['difference_pp'], signed=True)} puan**, hisse-kümeli %95 bootstrap **{fmt(match['bootstrap_95_pp'][0], signed=True)}…{fmt(match['bootstrap_95_pp'][1], signed=True)}**" if match["valid_pairs"] else "yeterli geçerli eş yok")
    def question_item(question: str, side: str, bucket: str) -> dict[str, Any] | None:
        return next((x for x in proxy_tables[question]["Y2026"][side] if x["group"] == bucket), None)
    def old_a01_path(side: str) -> str:
        item = question_item("A01", side, "1..2_ATR")
        if item is None:
            return "uygun gözlem yok"
        path = item["path_24"]
        return (f"n={path['valid']}, çizgi takip önce %{fmt(path['pct']['LINE_FAVORABLE_FIRST'])}, "
                f"fiyat dönüşü önce %{fmt(path['pct']['PRICE_RETURN_FIRST'])}, "
                f"ters basamak önce %{fmt(path['pct']['LINE_ADVERSE_FIRST'])}, "
                f"aynı-bar %{fmt(path['pct']['AMBIGUOUS_SAME_BAR'])}, hiçbiri %{fmt(path['pct']['NEITHER'])}")
    def f01_row(side: str, bucket: str, caption: str) -> str:
        item = question_item("F01", side, bucket)
        if item is None:
            return f"| {caption} | 0 | — | — |"
        val = item["result_8"]
        return f"| {caption} | {val['valid']} | %{fmt(val['reaction_first_pct'])} | %{fmt(val['breach_side_first_pct'])} |"
    f01_rows = "\n".join((f01_row("SUPPORT", "ADVERSE_STEP_PROXY", "Destek: aşağı basamak proxy"),
                          f01_row("SUPPORT", "FLAT_AFTER_ADVERSE_PROXY", "Destek: iniş sonrası düz proxy"),
                          f01_row("RESISTANCE", "ADVERSE_STEP_PROXY", "Direnç: yukarı basamak proxy"),
                          f01_row("RESISTANCE", "FLAT_AFTER_ADVERSE_PROXY", "Direnç: çıkış sonrası düz proxy")))
    report = f"""# Normal Stabil desteği ile ters direnç gerçekten benzer mi?

**Kısa sonuç:** Bu kez iki taraf {len(manifest['selected_symbols'])} hissenin **aynı arşivinde, aynı olay ve ufuk tanımıyla** yeniden karşılaştırıldı. Aşağıdaki oranlar betimleyicidir; ham farklar farklı olayları, eşleştirilmiş fark ise yalnız eşlenebilen alt grubu gösterir. Desteğin bazı eski rakamları ile önceki direnç raporunun farklı ATR ve olay tanımları **doğrudan çıkarılmamalıdır**.

## Aynı 4s kuralıyla temel karşılaştırma — 2026

TEST; çizgi önceden bilinirken fiyatın yakınlık bandına girişidir, mutlaka gerçek temas değildir. Olaydan sonraki **8 kapalı 4s barda**, ilk ±1 olay-4s-ATR yarışı:

| Taraf | Tüm TEST | Geçerli n / hisse | Tepki yönü önce | Ters yön önce | Aynı-bar | Hiçbiri |
|---|---:|---:|---:|---:|---:|---:|
| Normal native destek | {s['events']} | {s['valid']} / {s['symbols']} | %{fmt(s['reaction_first_pct'])} yukarı | %{fmt(s['breach_side_first_pct'])} aşağı | %{fmt(s['ambiguous_pct'])} | %{fmt(s['neither_pct'])} |
| Aynalanmış native direnç | {r['events']} | {r['valid']} / {r['symbols']} | %{fmt(r['reaction_first_pct'])} aşağı | %{fmt(r['breach_side_first_pct'])} yukarı | %{fmt(r['ambiguous_pct'])} | %{fmt(r['neither_pct'])} |

**Gerçek temas:** Destekte {s['real_touch']} geçerli TEST çizgiyi gerçekten kesti; bunların {s['real_touch_close_safe']}'i (%{fmt(s['real_touch_close_safe_pct'])}) aynı mumda destek üzerinde/çizgide kapandı. Dirençte {r['real_touch']} gerçek temasın {r['real_touch_close_safe']}'i (%{fmt(r['real_touch_close_safe_pct'])}) çizgide/altında kapandı. Yalnız bu gerçek temasların sonraki 8 barda tepki-yönü-önce oranı destek **%{fmt(st['reaction_first_pct'])}** (n={st['valid']}) ve direnç **%{fmt(rt['reaction_first_pct'])}** (n={rt['valid']}). Aynı mumdaki temas ve kapanışın sırası bilinmez.

**Eşleştirilmiş alt küme:** {match_text}. Aynı hisse/çeyrek/seans, mesafe ve önceki hareket kovasıyla, en az 8 bar aralıklı, tekrarsız eşleme uygulanır. Ortak piyasa günü, trend, kova içi farklar ve çoklu karşılaştırmalar bu aralıkta giderilmez.

## Çizgi–fiyat yolu

- **Uzaklaşma → çizgi takip / eski çizgiye fiyat dönüşü:** Destek için {path_summary('SUPPORT')}; direnç için {path_summary('RESISTANCE')}. Başlangıç 1,5 önceki **4s ATR**, çizgi takibi >0,01 fiyat birimi ve dönüş başlangıç çizgisine kapanıştır. Aynı-bar sonuçları ayrıdır; yalnız 8 barı değil 4/8/16 bar sonuçları da tabloda. Günlük pivotun 4 bar teyidi özellikle kısa yarışta mekanik gecikme yaratır.
- **Kırılma → ilk çizgiye dönüş:** Destekte {b1['summary']['valid']} geçerli aşağı kapanış kırılımının {b1['returned_safe_within_8']}'inde (%{fmt(b1['returned_safe_pct'])}), dirençte {b2['summary']['valid']} geçerli yukarı kırılımın {b2['returned_safe_within_8']}'inde (%{fmt(b2['returned_safe_pct'])}) sonraki 8 barda eski çizginin güvenli tarafında en az bir kapanış görüldü. Bu kalıcı başarı değildir. İlk retest, gap ve bilinen önceki taşma derinliği ayrı sayıldı.
- **Fiyat mı çizgi mi taraf değiştiriyor?** Fiyatın tek başına, çizginin tek başına, ikisinin birlikte gerekli veya ayrı ayrı yeterli olduğu durumlar ayrı. Sayılar [toplu tabloda](toplu_bulgular.md); bunlar mekanik karşı-olgusal etiketlerdir.
- **Basamak, yataylaşma ve temas sırası:** Aday rejim ve ilk/sonraki gözlenen temas grupları, sayı ve hisse sayılarıyla toplu tabloda. Görsel “dikey/yatay” eşlemesi **henüz kullanıcı grafiğiyle doğrulanmadı**; stepline'ın dikey bağlantı çizgisi tek başına kalıcı dikey rejim değildir.

## Eski 100 hisse sonuçlarıyla dürüst kıyas

Eski raporun **A01, B04, C02 ve F01** tarifleri ayrıca iki yönde çalıştırıldı: aynı günlük ATR, ilgili eski mesafe/son-dört-bar/temas tanımları ve aynı 4s ufuklar. 2026, 2025 ve eski 100 hissenin mevcut evrendeki {len(selected_old)} hisselik kesişimi [ayrı tablolarda](toplu_bulgular.md). C02 eski kodda günlük temas sırasını 4s checkpoint'e taşıyor; her 4s gözlem bağımsız yeni temas değil. Bunlar eski **48 sorunun tamamının** replikasyonu değildir.

**Eski A01'e yakın ortak tarif:** Fiyat güvenli tarafta 1–2 **günlük ATR** uzaklıktayken 24 × 4s pencerede, eski çizginin takip etmesi / fiyatın eski çizgiye yaklaşması / ters basamak yarışı: destek için {old_a01_path('SUPPORT')}; direnç için {old_a01_path('RESISTANCE')}. Burada fiyatın dönmesi çizgiye 0,15 günlük ATR'ye kadar yaklaşmadır; yukarıdaki 1,5 dört-saat-ATR / kapanış-dönüş yarışıyla aynı değildir. Aynı çizginin ardışık checkpoint'leri örtüşür.

**Eski F01'e yakın karşılıklı tarif:** Önceki 4 × 4s harekette tepki yönünde >0,3 günlük ATR hareket varsa, sonraki 8 × 4s içinde ±1 **günlük ATR**'ye ilk ulaşma:

| Aday durum | Geçerli n | Tepki yönü önce | Ters yön önce |
|---|---:|---:|---:|
{f01_rows}

Aynı-bar ve hiçbiri bu yüzdelerin paydasındadır; bütün kategoriler ve hisse sayıları tabloda. Bunlar native aday rejim etiketleri olup görsel dikey/yatay teyidi değildir; aynı checkpoint'ler bağımsız sayılmaz.

Örneğin eski A01 1–2 **günlük ATR** kovasındaki %33,49 çizgi-takip / %31,74 fiyat-dönüş oranlarını, önceki direnç raporundaki 1,5 **4s ATR** ve 8-bar yarışından çıkarmak doğru olmaz. Eski kayıt daha gevşek son-bar/kalite koşullarına sahipti; bu koşuda her iki tarafa aynı kapalı ve temiz veri, 24-bar yarışına tam pencere koşulu uygulandı. Önceki 100 hisselik bulgular silinmemiştir; hangi karşılaştırmanın yeniden yapıldığı ve farkları açıktır.

## Yöntem ve sınırlar

- Normal destek, gerçek günlük OHLC üzerinden değiştirilmemiş native günlük destek/pivot ve lifecycle ile hesaplandı. Direnç aynı çekirdeğin `O'=-O, H'=-L, L'=-H, C'=-C` matematiksel tersidir. Sabit `100.000−fiyat` koordinatı yalnız destek ölçümünü mevcut araştırma kodunda ters yönde yürütmek için kullanıldı; çıktıdaki fiyatlar gerçek fiyattır. Canlı 4s ok/alarm motorunun terslenmiş hali iddia edilmez.
- Şüpheli günlük bar sonrası geçmiş de muhafazakâr dışlanır; eksik 4s bileşenler, eksik kovalar, 20-bar geçmiş, son açık bar, aynı-bar belirsizlikleri ve 2025/2026 sınırından taşan ufuklar kaydedilir. [Manifest](manifest.json) ve [doğrulama](DOGRULAMA.md) ayrıntıları içerir.
- Bu koşunun planı önceki direnç sonuçları görüldükten sonra hazırlandı; arşiv daha önce araştırıldı. Dolayısıyla 2026 kör veya bağımsız bir doğrulama değildir. Olaylar aynı hisse ve gün içinde kümelenebilir; oranlar işlem getirisi, kârlılık ya da kanıtlanmış nedensellik değildir.
- Native teyidin üzerine keyfî 2/3/5 bar bekleme eklenmedi; üretim, Telegram, canlı alarm veya kural değiştirilmedi.

[Plan](PLAN.md) · [Bütün tablolar](toplu_bulgular.md) · [Makine özeti](summary.json) · [4s olaylar](events_4h.csv.gz) · [Native günlük olaylar](events_native_daily.csv.gz) · [Eski soru checkpointleri](legacy_like_checkpoints.csv.gz) · [Eşleşen çiftler](matched_support_resistance.csv.gz) · [Manifest](manifest.json) · [Doğrulama](DOGRULAMA.md) · [Önceki direnç raporu](../stabil_direnc_replay_2026_11_06/RAPOR.md)
"""
    (output/"RAPOR.md").write_text(report, encoding="utf-8")
    analysis_manifest = {"comparison_manifest_sha256": sha(output/"manifest.json"),
                         "summary_script_sha256": sha(Path(__file__)),
                         "legacy_table_sha256": sha(ROOT/"docs/arastirma/stabil_100_sonuclar/STABIL_DAVRANIS_48_TABLO.csv"),
                         "generated_outputs_sha256": {name: sha(output/name) for name in
                             ("summary.json", "RAPOR.md", "toplu_bulgular.md", "matched_support_resistance.csv.gz")}}
    (output/"analysis_manifest.json").write_text(json.dumps(analysis_manifest, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"main_2026_8": main["Y2026"]["8"], "matched": match,
                      "break": break_details, "departure": departure}, ensure_ascii=False, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    run(args.output)


if __name__ == "__main__":
    main()
