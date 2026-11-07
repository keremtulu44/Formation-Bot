"""Trace newly confirmed fixed lines without a price-dependent flat regime."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from domain_engines.stabil import prepare_causal_ohlcv
from research.arsiv import arsiv_koku, tf_frame
from research.stabil_arrow_context_replay import capture_cutoffs, closed_at_capture
from research.stabil_resistance_replay import ROOT, native_mirror, project_daily_at_bar_open, sha, write_csv_gz
from research.stabil_resistance_report import fmt, pct
from research.stabil_support_resistance_compare import native_support_as_reflected_line

OUTPUT = ROOT/"docs/arastirma/stabil_direnc_50_model_testi_2026_11_06"
FIRST = ("PRICE_CROSSES_FIRST", "LINE_CHANGED_FIRST", "AMBIGUOUS_SAME_BAR", "LEVEL_UNAVAILABLE", "NEITHER", "NO_REMAINING")


def trace_fixed(side: str, start: int, end: int, close: np.ndarray, levels: np.ndarray,
                identities: list[Any]) -> dict[str, Any]:
    if side not in {"SUPPORT", "RESISTANCE"} or start > end or end >= len(close):
        raise ValueError("invalid path bounds/side")
    level, identity = levels[start], identities[start]
    if not np.isfinite(level) or identity is None:
        raise ValueError("initial line unavailable")
    def safe(price: float) -> bool:
        return price >= level if side == "SUPPORT" else price <= level
    start_safe = safe(close[start])
    result: dict[str, Any] = {"price_side_at_step": "SAFE" if start_safe else "ADVERSE",
                              "remaining_at_step": end-start,
                              "first": "NO_REMAINING" if start == end else "NEITHER",
                              "first_step": None, "first_cross_position": None,
                              "strict_safe_first": None, "after_safe_return": None,
                              "remaining_after_safe_return": None}
    crossing_i = None
    for j in range(start+1, end+1):
        if not np.isfinite(levels[j]) or identities[j] is None:
            result.update(first="LEVEL_UNAVAILABLE", first_step=j-start)
            break
        changed = identities[j] != identity
        if not changed and not np.isclose(levels[j], level, rtol=0, atol=1e-8):
            raise AssertionError("same native identity has a different level")
        crosses = safe(close[j]) != start_safe
        if crosses and changed:
            result.update(first="AMBIGUOUS_SAME_BAR", first_step=j-start)
            break
        if crosses:
            result.update(first="PRICE_CROSSES_FIRST", first_step=j-start,
                          first_cross_position="EQUAL" if close[j] == level else "STRICT")
            crossing_i = j
            break
        if changed:
            result.update(first="LINE_CHANGED_FIRST", first_step=j-start)
            break
    if not start_safe:
        result["strict_safe_first"] = "NO_REMAINING" if start == end else "NEITHER"
        for j in range(start+1, end+1):
            if not np.isfinite(levels[j]) or identities[j] is None:
                result["strict_safe_first"] = "LEVEL_UNAVAILABLE"
                break
            changed = identities[j] != identity
            strictly_safe = close[j] > level if side == "SUPPORT" else close[j] < level
            if changed and strictly_safe:
                result["strict_safe_first"] = "AMBIGUOUS_SAME_BAR"
                break
            if strictly_safe:
                result["strict_safe_first"] = "PRICE_CROSSES_FIRST"
                break
            if changed:
                result["strict_safe_first"] = "LINE_CHANGED_FIRST"
                break
    if not start_safe and crossing_i is not None:
        result["remaining_after_safe_return"] = end-crossing_i
        result["after_safe_return"] = "NO_REMAINING" if crossing_i == end else "NEITHER"
        for j in range(crossing_i+1, end+1):
            if not np.isfinite(levels[j]) or identities[j] is None:
                result["after_safe_return"] = "LEVEL_UNAVAILABLE"
                break
            changed = identities[j] != identity
            crosses = not safe(close[j])
            if changed and crosses:
                result["after_safe_return"] = "AMBIGUOUS_SAME_BAR"
                break
            if crosses:
                result["after_safe_return"] = "PRICE_CROSSES_FIRST"
                break
            if changed:
                result["after_safe_return"] = "LINE_CHANGED_FIRST"
                break
    return result


def replay_symbol(symbol: str, paths: pd.DataFrame) -> list[dict[str, Any]]:
    archive = arsiv_koku()
    cap = capture_cutoffs(symbol, str(archive))
    d_raw = closed_at_capture(tf_frame(symbol, "1d", archive), "1d", cap["1d"])
    h_raw = closed_at_capture(tf_frame(symbol, "4h", archive), "4h", cap["1h"])
    daily, de = prepare_causal_ohlcv(d_raw, symbol=symbol, timeframe="1d")
    h4, he = prepare_causal_ohlcv(h_raw, symbol=symbol, timeframe="4h")
    if de or he or len(h4) != len(h_raw) or len(daily) != len(d_raw):
        raise AssertionError(f"{symbol}: data preparation mismatch")
    support, s_obs, _, _ = native_support_as_reflected_line(daily)
    resistance, r_obs, _, _ = native_mirror(daily)
    loc = project_daily_at_bar_open(pd.DatetimeIndex(daily.timestamp), h_raw.index)
    price = h4.close.to_numpy(dtype=float)
    times = pd.DatetimeIndex(h4.timestamp)
    out = []
    for side, model, obs in (("SUPPORT", support, s_obs), ("RESISTANCE", resistance, r_obs)):
        levels = np.full(len(h4), np.nan)
        ids: list[Any] = [None]*len(h4)
        for i, di in enumerate(loc):
            if di < 0 or obs[di].support_level is None:
                continue
            levels[i] = float(obs[di].support_level) if side == "SUPPORT" else -float(obs[di].support_level)
            ids[i] = model.identity[di]
        for record in paths[paths.side == side].to_dict("records"):
            i = int(record["bar_index"])
            j = i+int(record["first_step"])
            end = i+24
            if j > end or end >= len(h4) or ids[j] is None:
                raise AssertionError(f"{symbol}/{side}: incomplete first-line step")
            original = float(record["initial_line"])
            if not np.isclose(levels[i], original, rtol=1e-9, atol=1e-8):
                raise AssertionError(f"{symbol}/{side}: initial line mismatch")
            moved = levels[j] < levels[i]-.01 if side == "SUPPORT" else levels[j] > levels[i]+.01
            not_old_returned = price[j] < levels[i] if side == "SUPPORT" else price[j] > levels[i]
            if not moved or not not_old_returned:
                raise AssertionError(f"{symbol}/{side}: event not line-adverse-first")
            if pd.Timestamp(daily.timestamp.iloc[int(loc[j])]) > pd.Timestamp(h_raw.index[j]):
                raise AssertionError(f"{symbol}/{side}: line not known before bar")
            result = trace_fixed(side, j, end, price, levels, ids)
            expected = "SAFE_TO_NEW_LINE" if result["price_side_at_step"] == "SAFE" else "ADVERSE_TO_NEW_LINE"
            if expected != record["line_first_price_side"]:
                raise AssertionError(f"{symbol}/{side}: first price side mismatch")
            out.append({"symbol": symbol, "side": side, "period": record["period"],
                        "break_index": i, "break_time": record["event_close_time"],
                        "line_move_index": j, "line_move_close_time": times[j].isoformat(),
                        "old_line": levels[i], "new_line": levels[j], "close_at_move": price[j], **result})
    return out


def distribution(frame: pd.DataFrame, column: str) -> dict[str, Any]:
    c = {k: int((frame[column] == k).sum()) for k in FIRST}
    if sum(c.values()) != len(frame):
        raise AssertionError(f"unknown path value in {column}")
    return {"n": len(frame), "symbols": int(frame.symbol.nunique()), "counts": c,
            "pct": {k: pct(v, len(frame)) for k, v in c.items()}}


def run(output: Path) -> dict[str, Any]:
    pm = json.loads((output/"path_manifest.json").read_text(encoding="utf-8"))
    if sha(output/"manifest.json") != pm["comparison_manifest_sha256"]:
        raise AssertionError("previous replay manifest changed")
    for name, digest in pm["outputs_sha256"].items():
        if sha(output/name) != digest:
            raise AssertionError(f"path input differs: {name}")
    paths = pd.read_csv(output/"break_paths_24.csv.gz", low_memory=False)
    sub = paths[(paths.status_24 == "VALID") & (paths.first_path == "LINE_ADVERSE_FIRST")]
    records = [row for symbol, group in sub.groupby("symbol", sort=True) for row in replay_symbol(symbol, group)]
    df = pd.DataFrame(records).sort_values(["side", "symbol", "break_index"], kind="stable").reset_index(drop=True)
    if len(df) != len(sub):
        raise AssertionError("rebase path event omitted")
    write_csv_gz(df, output/"fixed_line_paths.csv.gz")
    groups = []
    for (period, side, initial), group in df.groupby(["period", "side", "price_side_at_step"], sort=True):
        groups.append({"period": period, "side": side, "initial_side": initial,
                       "first": distribution(group, "first"),
                       "first_cross_position_counts": {value: int((group.first_cross_position == value).sum()) for value in ("EQUAL", "STRICT")},
                       "strict_safe_first": distribution(group[group.strict_safe_first.notna()], "strict_safe_first"),
                       "after_safe_return": distribution(group[group.after_safe_return.notna()], "after_safe_return")})
    summary = {"scope": "post-results exploratory fixed-native-line paths, not visual horizontal confirmation",
               "paths": len(df), "groups": groups}
    (output/"fixed_line_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    header = ("| Dönem / taraf | İlk taşınmada fiyat | n | Hisse | Fiyat karşı tarafa önce | Çizgi kimliği değişimi önce | Aynı-bar | Hiçbiri | Kalan bar yok |\n"
              "|---|---|---:|---:|---:|---:|---:|---:|---:|")
    rendered = []
    for row in groups:
        x = row["first"]
        name = ("Destek" if row["side"] == "SUPPORT" else "Direnç")
        initial = "Güvenli" if row["initial_side"] == "SAFE" else "İhlal"
        rendered.append(f"| {row['period']} / {name} | {initial} | {x['n']} | {x['symbols']} | " +
                        " | ".join(f"{x['counts'][k]} (%{fmt(x['pct'][k])})" for k in
                                   ("PRICE_CROSSES_FIRST", "LINE_CHANGED_FIRST", "AMBIGUOUS_SAME_BAR", "NEITHER", "NO_REMAINING")) + " |")
    r_adverse = next(x for x in groups if x["period"] == "Y2026" and x["side"] == "RESISTANCE" and x["initial_side"] == "ADVERSE")
    first = r_adverse["first"]
    strict = r_adverse["strict_safe_first"]
    after = r_adverse["after_safe_return"]
    detail = (f"2026'da yeni direncin ilk taşınmasında fiyat üstünde olan {first['n']} olayın "
              f"{first['counts']['PRICE_CROSSES_FIRST']} tanesinde fiyat çizgiye eşit/alt kapandı; "
              f"çizgi kimliği değişmeden kesin alt kapanış {strict['counts']['PRICE_CROSSES_FIRST']} tanesinde görüldü. "
              f"İlk eşit/alt kapanış sonrası {after['counts']['PRICE_CROSSES_FIRST']} olayda fiyat kalan pencerede önce tekrar üstte kapandı. "
              "Bu küçük sayı bir başarı oranı değildir.")
    report = "\n".join(["# Fiyat koşulundan bağımsız sabit çizgi yolu — 50 hisse", "",
              "Bu keşifsel ek test, aynı tam/temiz 24 × 4s kırılma epizotlarında önce çizginin ters yönde taşındığı olaylarla sınırlıdır. Çizgi aday yatay sınıfına veya fiyatın günlük taraftaki konumuna göre seçilmez. Güvenli taraf destekte çizgiye eşit/üstü, dirençte çizgiye eşit/altıdır. İhlal kesin olarak destekte alt, dirençte üst kapanıştır.", "", header, *rendered, "",
              detail, "", "Bu bir native çizgi **kimliğinin sabit kalması** ölçümüdür; sabit stepline segmenti kullanıcı tarifindeki görsel yatay rejimle aynı ilan edilmez. Fiyatın ilk taşınma anındaki konumu farklı yolları ayırır. Kalan pencere olay başına farklı uzunluktadır; 0 bar kalanlar ayrı. İlk aşağı/yukarı dönüş, kalıcı tutunma demek değildir.", "",
              "İlk güvenli kapanış eşitlik de olabilir; kesin alt/üst kapanış ve ihlal tarafından fiyat önce güvenli tarafa geçen alt dalın sonraki sonuçları [makine özetinde](fixed_line_summary.json), tüm olaylar [CSV'dedir](fixed_line_paths.csv.gz). Seçim, [ek planda](EK_YOL_PLANI.md) açıklandığı gibi önceki sonuçlar görüldükten sonra yapılmış keşifsel analizdir.", ""])
    (output/"sabit_cizgi_yollari.md").write_text(report, encoding="utf-8")
    proof = {"path_manifest_sha256": sha(output/"path_manifest.json"), "plan_sha256": sha(output/"EK_YOL_PLANI.md"),
             "script_sha256": sha(Path(__file__)), "test_sha256": sha(ROOT/"test_stabil_resistance_50_fixed_line_paths.py"),
             "outputs_sha256": {name: sha(output/name) for name in ("fixed_line_paths.csv.gz", "fixed_line_summary.json", "sabit_cizgi_yollari.md")}}
    (output/"fixed_line_manifest.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    run(args.output)


if __name__ == "__main__":
    main()
