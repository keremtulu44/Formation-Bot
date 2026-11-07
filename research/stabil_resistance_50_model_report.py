"""Focused, 50-stock report for the user's support-to-resistance sequence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from domain_engines.stabil import prepare_causal_ohlcv
from research.arsiv import arsiv_koku, tf_frame
from research.stabil_arrow_context_replay import capture_cutoffs, closed_at_capture
from research.stabil_resistance_replay import ROOT, native_mirror, sha, write_csv_gz
from research.stabil_resistance_report import fmt, pct
from research.stabil_support_resistance_compare import LEGACY_MANIFEST, native_support_as_reflected_line

OUTPUT = ROOT / "docs/arastirma/stabil_direnc_50_model_testi_2026_11_06"


def select_check(output: Path, manifest: dict[str, Any]) -> list[str]:
    sel = json.loads((output/"selection.json").read_text(encoding="utf-8"))
    legacy_bytes = LEGACY_MANIFEST.read_bytes()
    if hashlib.sha256(legacy_bytes).hexdigest() != sel["universe_source_sha256"]:
        raise AssertionError("old support universe changed")
    previous = ROOT/"docs/arastirma/stabil_direnc_replay_2026_11_06/manifest.json"
    if sha(previous) != sel["previous_universe_sha256"]:
        raise AssertionError("prior resistance manifest changed")
    population = sorted(set(json.loads(legacy_bytes)["symbols"]) & set(json.loads(previous.read_text())["selected_symbols"]))
    selected = sorted(sorted(population, key=lambda sym: hashlib.sha256((sel["seed"]+sym).encode()).hexdigest())[:50])
    if len(population) != 100 or selected != sel["selected_symbols"] or selected != manifest["selected_symbols"]:
        raise AssertionError("50-stock selection differs from fixed rule or replay")
    return selected


def f01_groups(questions: pd.DataFrame) -> list[dict[str, Any]]:
    f01 = questions[questions.question == "F01"].copy()
    if not np.isfinite(f01.distance_safe_daily_atr.to_numpy(dtype=float)).all():
        raise AssertionError("F01 entry lacks a finite distance")
    f01["price_side"] = np.where(f01.distance_safe_daily_atr >= 0, "SAFE", "ADVERSE")
    rows = []
    for (period, side, bucket, price_side), group in f01.groupby(["period", "side", "bucket", "price_side"], sort=True):
        valid = group[group.status_8 == "VALID"]
        n = len(valid)
        counts = {key: int((valid.first_1atr_8 == key).sum()) for key in
                  ("REACTION_FIRST", "BREACH_SIDE_FIRST", "AMBIGUOUS_SAME_BAR", "NEITHER")}
        if sum(counts.values()) != n:
            raise AssertionError("unknown F01 outcome")
        rows.append({"period": period, "side": side, "candidate": bucket, "price_side": price_side,
                     "events": len(group), "valid": n, "symbols": int(valid.symbol.nunique()),
                     "counts": counts, "reaction_pct": pct(counts["REACTION_FIRST"], n),
                     "adverse_pct": pct(counts["BREACH_SIDE_FIRST"], n),
                     "ambiguous_pct": pct(counts["AMBIGUOUS_SAME_BAR"], n),
                     "neither_pct": pct(counts["NEITHER"], n)})
    return rows


def post_touch_close_groups(events: pd.DataFrame) -> list[dict[str, Any]]:
    """Separate later race outcomes after real-touch safe/adverse closes."""
    valid = events[(events.period == "Y2026") & (events.event == "TEST") & (events.status_8 == "VALID")]
    groups = []
    categories = ("REACTION_FIRST", "BREACH_SIDE_FIRST", "AMBIGUOUS_SAME_BAR", "NEITHER")
    for side in ("SUPPORT", "RESISTANCE"):
        for contact in ("TOUCH_CLOSE_SAFE", "TOUCH_CLOSE_BREACHED"):
            part = valid[(valid.side == side) & (valid.contact == contact)]
            counts = {key: int((part.first_1atr_8 == key).sum()) for key in categories}
            if sum(counts.values()) != len(part):
                raise AssertionError("unexpected future race result")
            groups.append({"side": side, "contact": contact, "n": len(part),
                           "symbols": int(part.symbol.nunique()), "counts": counts,
                           "pct": {key: pct(value, len(part)) for key, value in counts.items()}})
    return groups


def frozen_line_breached(side: str, level: float, future: np.ndarray) -> bool:
    if side not in {"SUPPORT", "RESISTANCE"} or not np.isfinite(level) or len(future) != 8 or not np.isfinite(future).all():
        raise ValueError("eight finite closes, level and valid side are required")
    return bool(np.any(future < level) if side == "SUPPORT" else np.any(future > level))


def b04_fixed_line_breaks(questions: pd.DataFrame) -> pd.DataFrame:
    """B04: eight future closes vs the line known at the original checkpoint."""
    q = questions[(questions.question == "B04") & (questions.status_8 == "VALID")]
    archive = arsiv_koku()
    rows: list[dict[str, Any]] = []
    for symbol, group in q.groupby("symbol", sort=True):
        capture = capture_cutoffs(symbol, str(archive))
        daily_raw = closed_at_capture(tf_frame(symbol, "1d", archive), "1d", capture["1d"])
        h4_raw = closed_at_capture(tf_frame(symbol, "4h", archive), "4h", capture["1h"])
        daily, de = prepare_causal_ohlcv(daily_raw, symbol=symbol, timeframe="1d")
        h4, he = prepare_causal_ohlcv(h4_raw, symbol=symbol, timeframe="4h")
        if de or he:
            raise AssertionError(f"{symbol}: malformed closed OHLC")
        _, supp_obs, _, _ = native_support_as_reflected_line(daily)
        _, resist_obs, _, _ = native_mirror(daily)
        times = pd.DatetimeIndex(h4.timestamp)
        daily_times = pd.DatetimeIndex(daily.timestamp)
        loc = np.searchsorted(daily_times.asi8, times.asi8, side="right")-1
        prices = h4.close.to_numpy(dtype=float)
        for event in group.to_dict("records"):
            i = int(event["bar_index"])
            if i+8 >= len(h4) or pd.Timestamp(event["event_close_time"]).value != times[i].value:
                raise AssertionError(f"{symbol}: checkpoint index/time changed")
            di = int(loc[i])
            observations = supp_obs if event["side"] == "SUPPORT" else resist_obs
            obs = observations[di]
            if obs.support_level is None:
                raise AssertionError(f"{symbol}: missing daily level")
            level = float(obs.support_level) if event["side"] == "SUPPORT" else -float(obs.support_level)
            if not np.isclose(level, float(event["line"]), rtol=1e-9, atol=1e-8):
                raise AssertionError(f"{symbol}: checkpoint level changed")
            if pd.Timestamp(event["daily_asof"]).value != daily_times[di].value:
                raise AssertionError(f"{symbol}: daily availability changed")
            safe_at_entry = prices[i] >= level if event["side"] == "SUPPORT" else prices[i] <= level
            if not safe_at_entry:
                raise AssertionError(f"{symbol}: B04 checkpoint not on safe side")
            future = prices[i+1:i+9]
            breached = frozen_line_breached(event["side"], level, future)
            rows.append({"symbol": symbol, "side": event["side"], "period": event["period"],
                         "bucket": event["bucket"], "bar_index": i, "event_close_time": event["event_close_time"],
                         "line": level, "close": prices[i], "future_close_breach_8": bool(breached)})
    return pd.DataFrame(rows)


def fmt_table(headers: list[str], rows: list[list[Any]], aligns: list[str] | None = None) -> str:
    if aligns is None:
        aligns = ["---"]+["---:"]*(len(headers)-1)
    return "| " + " | ".join(headers) + " |\n|" + "|".join(aligns) + "|\n" + "\n".join("| " + " | ".join(str(v) for v in row) + " |" for row in rows)


def run(output: Path) -> dict[str, Any]:
    manifest = json.loads((output/"manifest.json").read_text(encoding="utf-8"))
    if manifest["errors"] or manifest["successful_symbols"] != 50:
        raise AssertionError("50-stock replay incomplete")
    selected = select_check(output, manifest)
    for name, digest in manifest["outputs_sha256"].items():
        if sha(output/name) != digest:
            raise AssertionError(f"comparison events modified: {name}")
    am = json.loads((output/"analysis_manifest.json").read_text(encoding="utf-8"))
    if am["comparison_manifest_sha256"] != sha(output/"manifest.json"):
        raise AssertionError("analysis manifest does not match")
    for name, digest in am["generated_outputs_sha256"].items():
        if sha(output/name) != digest:
            raise AssertionError(f"summary changed: {name}")
    pm = json.loads((output/"path_manifest.json").read_text(encoding="utf-8"))
    if pm["comparison_manifest_sha256"] != sha(output/"manifest.json"):
        raise AssertionError("path manifest does not match")
    for name, digest in pm["outputs_sha256"].items():
        if sha(output/name) != digest:
            raise AssertionError(f"path output changed: {name}")
    fixed_manifest = json.loads((output/"fixed_line_manifest.json").read_text(encoding="utf-8"))
    if fixed_manifest["path_manifest_sha256"] != sha(output/"path_manifest.json"):
        raise AssertionError("fixed-line input path manifest does not match")
    for name, digest in fixed_manifest["outputs_sha256"].items():
        if sha(output/name) != digest:
            raise AssertionError(f"fixed-line output changed: {name}")
    if fixed_manifest["plan_sha256"] != sha(output/"EK_YOL_PLANI.md"):
        raise AssertionError("fixed-line plan changed")
    s = json.loads((output/"summary.json").read_text(encoding="utf-8"))
    paths = json.loads((output/"break_path_summary.json").read_text(encoding="utf-8"))
    fixed = json.loads((output/"fixed_line_summary.json").read_text(encoding="utf-8"))
    questions = pd.read_csv(output/"legacy_like_checkpoints.csv.gz", low_memory=False)
    f01 = f01_groups(questions)
    events = pd.read_csv(output/"events_4h.csv.gz", low_memory=False)
    post_touch = post_touch_close_groups(events)
    b04 = b04_fixed_line_breaks(questions)
    if b04.empty:
        raise AssertionError("no valid B04 checkpoints")
    write_csv_gz(b04, output/"b04_fixed_line_breaks.csv.gz")
    bgroups = []
    for (period, side, bucket), group in b04.groupby(["period", "side", "bucket"], sort=True):
        n = len(group)
        count = int(group.future_close_breach_8.sum())
        bgroups.append({"period": period, "side": side, "candidate": bucket, "n": n,
                        "symbols": int(group.symbol.nunique()), "breaches": count,
                        "breach_pct": pct(count, n)})
    main_rows = []
    for period, label in (("PRE_2026", "2025"), ("Y2026", "2026")):
        for side, name in (("SUPPORT", "Destek"), ("RESISTANCE", "Direnç")):
            x = s["main_test"][period]["8"][side]
            main_rows.append([f"{label} / {name}", x["valid"], x["symbols"], f"%{fmt(x['reaction_first_pct'])}",
                              f"%{fmt(x['breach_side_first_pct'])}", f"%{fmt(x['ambiguous_pct'])}", f"%{fmt(x['neither_pct'])}"])
    touch_rows = []
    for side, name in (("SUPPORT", "Destek"), ("RESISTANCE", "Direnç")):
        x = s["main_test"]["Y2026"]["8"][side]
        touch = s["real_touch_2026"][side]
        touch_rows.append([name, x["events"], x["valid"], x["real_touch"], x["real_touch_close_safe"],
                           f"%{fmt(x['real_touch_close_safe_pct'])}", f"%{fmt(touch['reaction_first_pct'])}"])
    post_touch_rows = []
    for row in post_touch:
        name = "Destek" if row["side"] == "SUPPORT" else "Direnç"
        contact_name = "Güvenli" if row["contact"] == "TOUCH_CLOSE_SAFE" else "İhlal"
        post_touch_rows.append([name, contact_name, row["n"], row["symbols"],
                                *[f"{row['counts'][key]} (%{fmt(row['pct'][key])})" for key in
                                  ("REACTION_FIRST", "BREACH_SIDE_FIRST", "AMBIGUOUS_SAME_BAR", "NEITHER")]])
    departure_rows = []
    for side, name in (("SUPPORT", "Destek"), ("RESISTANCE", "Direnç")):
        x = s["departure_2026"][side]["8"]
        departure_rows.append([name, x["valid"], x["symbols"], f"%{fmt(x['pct']['LEVEL_FOLLOWS_FAVORABLE_FIRST'])}",
                               f"%{fmt(x['pct']['PRICE_RETURNS_FIRST'])}", f"%{fmt(x['pct']['AMBIGUOUS_SAME_BAR'])}", f"%{fmt(x['pct']['NEITHER'])}"])
    first_rows, after_line_rows, after_price_rows = [], [], []
    for side, name in (("SUPPORT", "Destek"), ("RESISTANCE", "Direnç")):
        group = paths["groups"]["2026"][side]
        a, b, c = group["first"], group["after_line"], group["after_price"]
        first_rows.append([name, a["n"], a["symbols"], f"%{fmt(a['percent']['PRICE_RETURNS_FIXED_FIRST'])}",
                           f"%{fmt(a['percent']['LINE_ADVERSE_FIRST'])}", f"%{fmt(a['percent']['AMBIGUOUS_SAME_BAR'])}", f"%{fmt(a['percent']['NEITHER'])}"])
        after_line_rows.append([name, b["n"], b["symbols"], f"%{fmt(b['percent']['FLAT_PROXY_FIRST'])}",
                                f"%{fmt(b['percent']['PRICE_RETURNS_OLD_FIRST'])}", f"%{fmt(b['percent']['AMBIGUOUS_SAME_BAR'])}", f"%{fmt(b['percent']['NEITHER'])}"])
        after_price_rows.append([name, c["n"], c["symbols"], f"%{fmt(c['percent']['PRICE_BREAKS_FIXED_AGAIN'])}",
                                 f"%{fmt(c['percent']['LINE_ADVERSE_FIRST'])}", f"%{fmt(c['percent']['AMBIGUOUS_SAME_BAR'])}", f"%{fmt(c['percent']['NEITHER'])}"])
    f01_rows = []
    for side, name in (("SUPPORT", "Destek"), ("RESISTANCE", "Direnç")):
        for candidate, cname in (("ADVERSE_STEP_PROXY", "Ters basamak"), ("FLAT_AFTER_ADVERSE_PROXY", "Sonrası düz")):
            for price_side, pname in (("SAFE", "Güvenli"), ("ADVERSE", "İhlal")):
                d = next((r for r in f01 if r["period"] == "Y2026" and r["side"] == side and r["candidate"] == candidate and r["price_side"] == price_side), None)
                if d is None:
                    continue
                f01_rows.append([name, cname, pname, d["valid"], d["symbols"], f"%{fmt(d['reaction_pct'])}",
                                  f"%{fmt(d['adverse_pct'])}", f"%{fmt(d['ambiguous_pct'])}", f"%{fmt(d['neither_pct'])}"])
    b_rows = [[("Destek" if r["side"] == "SUPPORT" else "Direnç"),
               ("Yeni düz proxy" if r["candidate"] == "NEW_FLAT_AFTER_FAVORABLE" else "Uzun düz proxy"),
               r["n"], r["symbols"], r["breaches"], f"%{fmt(r['breach_pct'])}"] for r in bgroups if r["period"] == "Y2026"]
    r_fixed_adverse = next(x for x in fixed["groups"] if x["period"] == "Y2026" and x["side"] == "RESISTANCE" and x["initial_side"] == "ADVERSE")
    r_fixed_n = r_fixed_adverse["first"]["n"]
    r_fixed_safe = r_fixed_adverse["first"]["counts"]["PRICE_CROSSES_FIRST"]
    r_fixed_strict = r_fixed_adverse["strict_safe_first"]["counts"]["PRICE_CROSSES_FIRST"]
    r_fixed_again = r_fixed_adverse["after_safe_return"]["counts"]["PRICE_CROSSES_FIRST"]
    fixed_rows = []
    for side, name in (("SUPPORT", "Destek"), ("RESISTANCE", "Direnç")):
        for state, label in (("ADVERSE", "İhlal tarafında"), ("SAFE", "Güvenli tarafta")):
            item = next((x for x in fixed["groups"] if x["period"] == "Y2026" and x["side"] == side and x["initial_side"] == state), None)
            if item is not None:
                x = item["first"]
                fixed_rows.append([name, label, x["n"], x["symbols"], x["counts"]["PRICE_CROSSES_FIRST"],
                                   x["counts"]["LINE_CHANGED_FIRST"], x["counts"]["AMBIGUOUS_SAME_BAR"],
                                   x["counts"]["NEITHER"], x["counts"]["NO_REMAINING"]])
    a_rows = []
    for side, name in (("SUPPORT", "Destek"), ("RESISTANCE", "Direnç")):
        item = next((x for x in s["legacy_like_questions"]["A01"]["Y2026"][side] if x["group"] == "1..2_ATR"), None)
        if item is not None:
            a = item["path_24"]
            a_rows.append([name, a["valid"], a["symbols"], f"%{fmt(a['pct']['LINE_FAVORABLE_FIRST'])}",
                           f"%{fmt(a['pct']['PRICE_RETURN_FIRST'])}", f"%{fmt(a['pct']['LINE_ADVERSE_FIRST'])}",
                           f"%{fmt(a['pct']['AMBIGUOUS_SAME_BAR'])}", f"%{fmt(a['pct']['NEITHER'])}"])
    m = s["matched_2026"]
    matching = (f"{m['valid_pairs']} geçerli çift / {m['symbols']} hisse: destek %{fmt(m['support_reaction_pct'])}, direnç %{fmt(m['resistance_reaction_pct'])}; fark {fmt(m['difference_pp'], signed=True)} puan, hisse-kümeli %95 bootstrap {fmt(m['bootstrap_95_pp'][0], signed=True)}…{fmt(m['bootstrap_95_pp'][1], signed=True)} puan. Bu aralık denklik veya nedensellik kanıtı değildir." if m["valid_pairs"] else "Geçerli eşleşme yok.")
    main = fmt_table(["Dönem / taraf", "Geçerli", "Hisse", "Tepki önce", "Ters yön önce", "Aynı-bar", "Hiçbiri"], main_rows)
    contact = fmt_table(["Taraf", "Tüm TEST", "Geçerli", "Gerçek temas", "Temas & güvenli kapanış", "% / gerçek temas", "Sonraki tepki önce"], touch_rows)
    post_touch_table = fmt_table(["Taraf", "Temas mumunun kapanışı", "n", "Hisse", "Tepki önce", "Ters yön önce", "Aynı-bar", "Hiçbiri"], post_touch_rows,
                                 ["---", "---", "---:", "---:", "---:", "---:", "---:", "---:"])
    dep = fmt_table(["Taraf", "Geçerli", "Hisse", "Çizgi takip önce", "Fiyat eski çizgiye önce", "Aynı-bar", "Hiçbiri"], departure_rows)
    first = fmt_table(["Taraf", "Geçerli", "Hisse", "Fiyat eski çizgiye önce", "Ters çizgi basamağı önce", "Aynı-bar", "Hiçbiri"], first_rows)
    after_line = fmt_table(["Taraf", "Dal n", "Hisse", "Düz proxy önce", "Eski çizgiye dönüş önce", "Aynı-bar", "Hiçbiri"], after_line_rows)
    after_price = fmt_table(["Taraf", "Dal n", "Hisse", "Yeniden kırılma önce", "Çizgi ters basamak önce", "Aynı-bar", "Hiçbiri"], after_price_rows)
    ftable = fmt_table(["Taraf", "Aday rejim", "Fiyat/çizgi", "Geçerli", "Hisse", "Tepki önce", "Ters yön önce", "Aynı-bar", "Hiçbiri"], f01_rows, ["---", "---", "---", "---:", "---:", "---:", "---:", "---:", "---:"])
    btable = fmt_table(["Taraf", "Aday rejim", "Geçerli", "Hisse", "İhlal", "İhlal %"], b_rows, ["---", "---", "---:", "---:", "---:", "---:"])
    fixed_table = fmt_table(["Taraf", "İlk taşınmada fiyat", "n", "Hisse", "Fiyat geçişi önce", "Çizgi değişimi önce", "Aynı-bar", "Hiçbiri", "Kalan bar yok"], fixed_rows, ["---", "---", "---:", "---:", "---:", "---:", "---:", "---:", "---:"])
    atable = fmt_table(["Taraf", "Geçerli", "Hisse", "Takip önce", "Fiyat yaklaşma önce", "Ters basamak önce", "Aynı-bar", "Hiçbiri"], a_rows)
    report = f"""# Direnç, anlattığın destek yolunun tersi gibi çalışıyor mu? — 50 hisse

50 hisse, eski 100 hisselik destek örnekleminden sabit SHA256 sırasıyla ve tek tek sonuçlara bakılmadan seçildi. Aynı hisselerin aynı arşivinde normal native destek ve ters native direnç ölçüldü. Kullanıcının onayladığı karşıt yol esas alındı; sabit direnç ve yukarı takip eden direnç ayrı incelendi. Bu çalışma daha önce sonuçları görülmüş veriye dayandığından kör doğrulama değildir.

## 1. Temas ve sonraki tepki

TEST çizgiye yakınlık bandına girme olayıdır; gerçek temastan ayrı tutulur. Tepki yönü destekte yukarı, dirençte aşağıdır. Olaydan sonraki ilk ±1 **4s ATR**, 8 × 4s bar:

{main}

2026'da gerçek temas, aynı mumun güvenli kapanışı ve temas sonrası 8-bar yarışı:

{contact}

İlk sütundaki tüm olaylar ile geçerli olaylar farklıdır; yakınlık ve gap gerçek temas sayılmaz. Mum içindeki temas ve kapanışın sırası bilinmez. Yukarıdaki son sütunun paydası güvenli kapanışlar değil **tüm gerçek temaslar**dır.

Gerçek temasları aynı mum kapanışına göre ayırıp sonraki 8 × 4s ilk ±1 olay-4s-ATR yarışını ayrıca izleyince:

{post_touch_table}

Güvenli kapanış, destekte çizgiye eşit/üst, dirençte eşit/alt; ihlal kapanışı kesin ters taraftır. Tepki önce demek, garantili işlem başarısı veya sürekli düşüş/yükseliş demek değildir. Bu alt gruplama keşifseldir; eşleştirme yapılmamıştır.

{matching}

## 2. Fiyat uzaklaşırsa önce çizgi mi takip eder, fiyat mı eski çizgiye döner?

2026, fiyat başlangıç çizgisinden 1,5 **önceki 4s ATR** uzaklaşma eşiğini geçtikten sonraki 8 × 4s bar; dönüş eski çizgiye kapanış:

{dep}

Farklı eski A01 tarifinde fiyat 1–2 **günlük ATR** uzaktayken 24 × 4s yarışılır; burada fiyat dönüşü eski çizgiye 0,15 günlük ATR yakınlık demektir:

{atable}

Bunlar farklı ATR ve ufuk tanımlarıdır; yüzdeler birbirine çıkarılmaz. 24-bar checkpoint'ler birbirleriyle sıklıkla örtüşür. Kısa ufukta native 4 günlük pivot teyidi, çizgi takip olayını doğal olarak geciktirebilir.

## 3. Kırılma → sabit çizgiye dönüş veya çizginin takip etmesi

2026'da aynı kırılma epizodunu 24 × 4s izleyince ilk yol:

{first}

*Çizgi ters yönde önce taşınmışsa*, aynı çizgi kimliği altında hangi olay önce geldi? Payda yalnız bu dala giren olaylardır:

{after_line}

*Fiyat eski çizginin güvenli tarafına önce döndüyse*, kalan pencerede hangi olay önce geldi? Payda yalnız önce fiyatın döndüğü daldır:

{after_price}

Dalların kalan izleme süreleri eşit değildir. Tablo bazı nadir çizgi-kimliği/değişim sınıflarını sütunlara sığdırmaz; tam dağılım [yol tablolarında](yol_bulgulari.md). Fiyatın bir kez eski çizgiye dönmesi kalıcı tutunma veya işlem başarısı demek değildir.

**Sabit eski çizgi örneği — AKBNK:** 6 Ocak 2026 17:30 kapanışı 74,15 ile 73,65 direncinin üstündeydi. 7 Ocak 13:30 kapanışı aynı çizginin altında 73,40'a döndü; çizgi hâlâ 73,65 iken 9 Ocak 18:00 kapanışı 73,75 ile tekrar üzerine çıktı. Bu tek bir seçilmiş epizottur, genellenemez.

## 4. Fiyat çizginin hangi tarafındayken basamak / düz proxy?

Aynı tarihte bilinen, eski F01'e yakın örnek: son 4 × 4s hareket tepki yönünde >0,3 günlük ATR. Gelecek 8 × 4s ilk ±1 **günlük** ATR; 2026. Güvenli taraf = destekte çizgiye eşit/üstü, dirençte çizgiye eşit/altı; ihlal kapanışı kesin ters taraftadır:

{ftable}

Bu karşılaştırmada aynı-bar ve hiçbiri paydada. "Ters basamak" destek aşağı / direnç yukarıdır. Rejimler grafikteki dikey/yatayın doğrulanmış karşılığı **değil**. Özellikle düz proxy, ilgili native günlük kapanışın güvenli tarafta olmasını içerir; bu ilişkiyi bağımsız kanıt diye okumamak gerekir. 2026'da aday düzken fiyatın ihlal tarafında olduğu direnç grubu yalnız **6 checkpoint / 5 hisse**, destek grubu 10 checkpoint / 8 hisse; kullanıcının tarifindeki durumu bunlarla kesinleştiremeyiz. Alt gruplar ve checkpoint'ler bağımsız değildir.

## 5. Fiyat koşuluna bağlamadan yeni sabit çizgiyi izleme

Kırılmadan sonra çizgi ters yönde **önce** taşındığında, aday yatay rejimi filtrelemeden aynı native çizgi kimliği ve fiyatın konumu izlendi. İlk taşınmadan sonraki kalan 24-bar pencerede fiyatın yeni çizgiye göre güvenli/ihlal durumunun değişmesi / çizgi kimliğinin önce değişmesi (güvenli tarafa dönüş çizgiye eşit kapanışı da içerir):

{fixed_table}

Bu, mevcut native seviyenin sabit kalmasıdır; çizginin grafikte kullanıcının kastettiği "yatay" duruma geçtiğini ispatlamaz. Fiyat yeni direncin üstündeyken taşınan **{r_fixed_n}** olayın {r_fixed_safe} tanesinde fiyat kalan pencerede eşit/alt, {r_fixed_strict} tanesinde kesin alt kapandı; ilk eşit/alt kapanışın ardından {r_fixed_again} tanesinde çizgi kimliği değişmeden önce tekrar üstte kapandı. Bu küçük gruptan genel oran çıkarılmamalıdır. Aşamalardaki süreler farklı, aynı-bar ve kalan süre olmaması ayrı. Ayrıntı [sabit çizgi yollarında](sabit_cizgi_yollari.md).

**Somut örnek — EFOR:** 23 Temmuz 2026 17:30'da kapanış 17,76 iken eski direnç 17,70'ti. 28 Temmuz 13:30'da yeni teyitli çizgi 19,53, kapanış 19,80 idi. Çizgi kimliği korunurken 3 Ağustos 13:30 kapanışı 19,05 ile kesin altına geçti; özgün 24-bar pencere bitene kadar yeni çizginin üstünde kapanış görülmedi. Bu bir fiyat/çizgi yolu örneğidir; görsel "yatay" teyidi veya işlem önerisi değildir.

## 6. Yeni/uzun düz aday çizginin kırılması

2026, güvenli tarafta ve aynı 0–2,5 günlük ATR mesafe bandındaki eski B04'e yakın checkpoint'ler: başlangıçta dondurulan çizginin sonraki 8 × 4s barın **herhangi birinde kapanışla** ihlali:

{btable}

Yeni-düz ve uzun-düz mevcut araştırma sınıflandırıcısının yaşa dayalı proxy'leridir; bu sınıfları yeni canlı bekleme/teyit kuralı yapmak istenmiyor. Özellikle küçük hisse sayılı gruplardan kesin sonuç çıkarılmaz; fiyat mesafesi ve geçmiş yolu tamamen eşleştirilmiş değildir.

## Sonuç nasıl kullanılmalı?

- Sayısal karşılaştırma, hangi ters davranışın **görüldüğünü ve nerede ayrıştığını** gösterir; tek başına tüm dönemlerde simetri veya işlem avantajı kanıtı değildir.
- Bu 50 hisse önceki sonuçları da görülmüş eski 100 hisselik kolayda örneklemden seçildi; kör/bağımsız dış doğrulama yok. Tekrarlanan olaylar ve ortak piyasa günleri bağımsız değildir.
- Ters günlük çekirdek ile kullanıcı görselindeki dikey/yatay eşleşmesi henüz doğrulanmadı; küçük görsel deney kullanıcı daha sonra istediğinde ayrıca yapılabilir. Native teyide keyfî 2/3/5 bar bekleme eklenmedi.
- **Direnç canlıda aktifleştirilmedi.** Yeni grafik, alarm veya Telegram değişikliği yok; sonuç ve sınırlamalar kullanıcıyla değerlendirildikten sonra ayrıca karar gerekir.

[Plan](PLAN.md) · [50 hisse seçimi](selection.json) · [Tüm eş-kural tabloları](toplu_bulgular.md) · [Aynı epizot yol tabloları](yol_bulgulari.md) · [Sabit çizgi yolları](sabit_cizgi_yollari.md) · [Seçilmiş DOCO örnekleri](../stabil_destek_direnc_karsilastirma_2026_11_06/ORNEK_YOLLAR.md) · [Makine özeti](focused_summary.json) · [Doğrulama](DOGRULAMA.md)
"""
    (output/"RAPOR_50.md").write_text(report, encoding="utf-8")
    result = {"selected_symbols": selected, "main_test": s["main_test"], "real_touch_2026": s["real_touch_2026"],
              "post_touch_close_2026": post_touch,
              "matched_2026": m, "departure_2026": s["departure_2026"], "break_paths": paths["groups"],
              "f01_price_side_groups": f01, "b04_fixed_break_groups": bgroups, "fixed_line_groups": fixed["groups"]}
    (output/"focused_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    stamps = {"selection_sha256": sha(output/"selection.json"), "plan_sha256": sha(output/"PLAN.md"),
              "comparison_manifest_sha256": sha(output/"manifest.json"), "path_manifest_sha256": sha(output/"path_manifest.json"),
              "fixed_line_manifest_sha256": sha(output/"fixed_line_manifest.json"),
              "focused_script_sha256": sha(Path(__file__)),
              "focused_tests_sha256": sha(ROOT/"test_stabil_resistance_50_model_report.py"),
              "output_sha256": {name: sha(output/name) for name in ("RAPOR_50.md", "focused_summary.json", "b04_fixed_line_breaks.csv.gz")}}
    (output/"focused_manifest.json").write_text(json.dumps(stamps, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"symbols": len(selected), "test_2026": s["main_test"]["Y2026"]["8"],
                      "matched": m, "b04": bgroups, "f01": f01}, ensure_ascii=False, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    run(args.output)


if __name__ == "__main__":
    main()
