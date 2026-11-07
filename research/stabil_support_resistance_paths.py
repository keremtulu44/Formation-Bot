"""Trace each break through mutually exclusive line/price path branches."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from domain_engines.stabil import prepare_causal_ohlcv
from domain_engines.stabil.signals import _causal_atr14
from research.arsiv import arsiv_koku, ham_frame, tf_frame
from research.stabil_arrow_context_replay import bad_bars, capture_cutoffs, closed_at_capture
from research.stabil_resistance_replay import (
    Forward,
    ROOT,
    intraday_completeness,
    native_mirror,
    project_daily_at_bar_open,
    sha,
    write_csv_gz,
)
from research.stabil_resistance_report import as_bool, fmt, pct
from research.stabil_support_resistance_compare import (
    LEGACY_MANIFEST,
    OUTPUT,
    REFLECTION,
    full_window_status,
    native_support_as_reflected_line,
    reflect_prices,
    validate_previous_inputs,
)

HORIZON = 24
TICK = .01
FIRST = ("PRICE_RETURNS_FIXED_FIRST", "LINE_ADVERSE_FIRST", "LINE_FAVORABLE_FIRST",
         "IDENTITY_SAME_LEVEL_FIRST", "AMBIGUOUS_SAME_BAR", "LEVEL_UNAVAILABLE", "NEITHER")
AFTER_LINE = ("FLAT_PROXY_FIRST", "PRICE_RETURNS_OLD_FIRST", "LINE_CHANGED_FIRST",
              "AMBIGUOUS_SAME_BAR", "LEVEL_UNAVAILABLE", "NEITHER")
AFTER_FLAT = ("PRICE_CROSSES_NEW_LINE", "LINE_CHANGED_FIRST", "AMBIGUOUS_SAME_BAR", "LEVEL_UNAVAILABLE", "NEITHER")
AFTER_PRICE = ("PRICE_BREAKS_FIXED_AGAIN", "LINE_ADVERSE_FIRST", "LINE_FAVORABLE_FIRST",
               "IDENTITY_SAME_LEVEL_FIRST", "AMBIGUOUS_SAME_BAR", "LEVEL_UNAVAILABLE", "NEITHER")


def line_move(level: float, initial: float, identity: Any, initial_identity: Any) -> str | None:
    if level > initial+TICK:
        return "LINE_ADVERSE_FIRST"
    if level < initial-TICK:
        return "LINE_FAVORABLE_FIRST"
    if identity != initial_identity:
        return "IDENTITY_SAME_LEVEL_FIRST"
    return None


def trace_break(i: int, close: np.ndarray, levels: np.ndarray, identities: list[Any],
                regimes: list[str], horizon: int = HORIZON) -> dict[str, Any]:
    """Inputs use barrier-on-top orientation, regardless of real market side."""
    if i+horizon >= len(close):
        raise ValueError("complete observation horizon is required")
    if not np.isfinite(levels[i]) or identities[i] is None or close[i] <= levels[i]:
        raise ValueError("initial observation is not an adverse-side break")
    original, identity = levels[i], identities[i]
    out: dict[str, Any] = {"first_path": "NEITHER", "first_step": None,
                           "line_first_price_side": None, "after_line_first": None,
                           "flat_step": None, "flat_price_side": None,
                           "after_flat_first": None, "after_price_first": None}
    first_i = None
    for j in range(i+1, i+horizon+1):
        if not np.isfinite(levels[j]) or identities[j] is None:
            out.update(first_path="LEVEL_UNAVAILABLE", first_step=j-i)
            break
        returns = close[j] <= original
        moved = line_move(levels[j], original, identities[j], identity)
        if returns and moved:
            out.update(first_path="AMBIGUOUS_SAME_BAR", first_step=j-i)
            break
        if returns or moved:
            out.update(first_path="PRICE_RETURNS_FIXED_FIRST" if returns else moved, first_step=j-i)
            first_i = j
            break
    if out["first_path"] == "LINE_ADVERSE_FIRST":
        assert first_i is not None
        out["line_first_price_side"] = "SAFE_TO_NEW_LINE" if close[first_i] <= levels[first_i] else "ADVERSE_TO_NEW_LINE"
        first_identity = identities[first_i]
        out["after_line_first"] = "NEITHER"
        flat_i = None
        for j in range(first_i+1, i+horizon+1):
            if not np.isfinite(levels[j]) or identities[j] is None:
                out["after_line_first"] = "LEVEL_UNAVAILABLE"
                break
            price_returns_old = close[j] <= original
            changed = identities[j] != first_identity
            flat = not changed and regimes[j] in {"HORIZONTAL_AFTER_DROP", "LONG_HORIZONTAL"}
            if sum((price_returns_old, changed, flat)) > 1:
                out["after_line_first"] = "AMBIGUOUS_SAME_BAR"
                break
            if price_returns_old:
                out["after_line_first"] = "PRICE_RETURNS_OLD_FIRST"
                break
            if changed:
                out["after_line_first"] = "LINE_CHANGED_FIRST"
                break
            if flat:
                out["after_line_first"] = "FLAT_PROXY_FIRST"
                out["flat_step"] = j-i
                flat_i = j
                break
        if flat_i is not None:
            safe = close[flat_i] <= levels[flat_i]
            out["flat_price_side"] = "SAFE_TO_NEW_LINE" if safe else "ADVERSE_TO_NEW_LINE"
            out["after_flat_first"] = "NEITHER"
            for j in range(flat_i+1, i+horizon+1):
                if not np.isfinite(levels[j]) or identities[j] is None:
                    out["after_flat_first"] = "LEVEL_UNAVAILABLE"
                    break
                crosses = (close[j] > levels[flat_i]) if safe else (close[j] <= levels[flat_i])
                changed = identities[j] != identities[flat_i]
                if crosses and changed:
                    out["after_flat_first"] = "AMBIGUOUS_SAME_BAR"
                    break
                if crosses:
                    out["after_flat_first"] = "PRICE_CROSSES_NEW_LINE"
                    break
                if changed:
                    out["after_flat_first"] = "LINE_CHANGED_FIRST"
                    break
    elif out["first_path"] == "PRICE_RETURNS_FIXED_FIRST":
        assert first_i is not None
        out["after_price_first"] = "NEITHER"
        for j in range(first_i+1, i+horizon+1):
            if not np.isfinite(levels[j]) or identities[j] is None:
                out["after_price_first"] = "LEVEL_UNAVAILABLE"
                break
            breaks = close[j] > original
            moved = line_move(levels[j], original, identities[j], identity)
            if breaks and moved:
                out["after_price_first"] = "AMBIGUOUS_SAME_BAR"
                break
            if breaks or moved:
                out["after_price_first"] = "PRICE_BREAKS_FIXED_AGAIN" if breaks else moved
                break
    return out


def replay_path_symbol(symbol: str, archive: Path, meta: dict[str, Any], selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    captures = capture_cutoffs(symbol, str(archive))
    daily_raw = closed_at_capture(tf_frame(symbol, "1d", archive), "1d", captures["1d"])
    h4_raw = closed_at_capture(tf_frame(symbol, "4h", archive), "4h", captures["1h"])
    hourly = closed_at_capture(ham_frame(symbol, "1h", archive), "1h", captures["1h"])
    daily, d_err = prepare_causal_ohlcv(daily_raw, symbol=symbol, timeframe="1d")
    h4, h_err = prepare_causal_ohlcv(h4_raw, symbol=symbol, timeframe="4h")
    if d_err or h_err or len(daily) != meta["daily_bars"] or len(h4) != meta["h4_bars"]:
        raise AssertionError(f"{symbol}: archive/preparation counts changed")
    incomplete, gaps, quality = intraday_completeness(hourly, h4_raw, daily_raw, captures["1h"])
    daily_bad = bad_bars(daily)
    bad_dates = set(pd.DatetimeIndex(daily.timestamp)[daily_bad].tz_convert("Europe/Istanbul").date)
    suspect = np.asarray([t.date() in bad_dates for t in pd.DatetimeIndex(h4.timestamp)], dtype=bool)
    bad = bad_bars(h4) | incomplete | suspect
    checks = {"bad_daily_bars_including_30pct_jump": int(daily_bad.sum()),
              "bad_h4_bars_including_incomplete_and_30pct_jump": int(bad.sum()),
              "h4_bars_on_suspect_daily_date": int(suspect.sum()), **quality}
    if any(int(meta[k]) != value for k, value in checks.items()):
        raise AssertionError(f"{symbol}: data quality changed")
    loc = project_daily_at_bar_open(pd.DatetimeIndex(daily.timestamp), h4_raw.index)
    structural = np.zeros(len(h4), dtype=bool)
    valid_loc = loc >= 0
    structural[valid_loc] = (np.cumsum(daily_bad) > 0)[loc[valid_loc]]
    atr = _causal_atr14(*(h4[c].to_numpy(dtype=float) for c in ("high", "low", "close")))
    support, _, _, s_regimes = native_support_as_reflected_line(daily)
    resistance, _, _, r_regimes = native_mirror(daily)
    representations = {"SUPPORT": (reflect_prices(h4), support, s_regimes),
                       "RESISTANCE": (h4, resistance, r_regimes)}
    output = []
    for side in ("SUPPORT", "RESISTANCE"):
        frame, line, daily_regimes = representations[side]
        forward = Forward(frame, atr, bad, gaps, structural)
        levels = np.full(len(h4), np.nan)
        ids: list[Any] = [None]*len(h4)
        regs = ["UNAVAILABLE"]*len(h4)
        for j, di in enumerate(loc):
            if di >= 0:
                levels[j] = line.level[di]
                ids[j] = line.identity[di]
                regs[j] = daily_regimes[di].regime.value
        for event in selected:
            if event["side"] != side:
                continue
            i = int(event["bar_index"])
            real_level = REFLECTION-levels[i] if side == "SUPPORT" else levels[i]
            real_close = REFLECTION-forward.close[i] if side == "SUPPORT" else forward.close[i]
            if not (np.isclose(real_level, event["line"], rtol=1e-9, atol=1e-7)
                    and np.isclose(real_close, event["close"], rtol=1e-9, atol=1e-7)
                    and forward.close[i-1] <= levels[i] and forward.close[i] > levels[i]):
                raise AssertionError(f"{symbol} {side} {i}: prior break anchor changed")
            status = full_window_status(forward, i, HORIZON)
            row = {"symbol": symbol, "side": side, "bar_index": i, "event_close_time": event["event_close_time"],
                   "period": event["period"], "quarter": event["quarter"], "initial_line": real_level,
                   "break_close": real_close, "status_24": status,
                   "right_censored_24": bool(i+HORIZON >= len(h4))}
            if status == "VALID":
                row.update(trace_break(i, forward.close, levels, ids, regs))
            output.append(row)
    return output


def distribution(frame: pd.DataFrame, col: str, labels: tuple[str, ...]) -> dict[str, Any]:
    values = {k: int((frame[col] == k).sum()) for k in labels}
    if sum(values.values()) != len(frame):
        raise AssertionError(f"{col}: unexpected or missing path labels")
    return {"n": len(frame), "symbols": int(frame.symbol.nunique()), "counts": values,
            "percent": {k: pct(v, len(frame)) for k, v in values.items()}}


def render_table(title: str, rows: list[dict[str, Any]], labels: tuple[str, ...]) -> str:
    header = "| Grup | n | Hisse | " + " | ".join(labels) + " |\n|---|---:|---:|" + "---:|"*len(labels)
    body = [f"| {r['group']} | {r['n']} | {r['symbols']} | " +
            " | ".join(f"{r['counts'][k]} (%{fmt(r['percent'][k])})" for k in labels) + " |" for r in rows]
    return f"### {title}\n\n{header}\n" + "\n".join(body) + "\n"


def run(output: Path, workers: int) -> dict[str, Any]:
    manifest = json.loads((output/"manifest.json").read_text(encoding="utf-8"))
    for name, digest in manifest["outputs_sha256"].items():
        if sha(output/name) != digest:
            raise AssertionError(f"comparison output differs: {name}")
    archive = arsiv_koku()
    previous = validate_previous_inputs(archive, ROOT/"docs/arastirma/stabil_direnc_replay_2026_11_06")
    if sha(ROOT/"docs/arastirma/stabil_direnc_replay_2026_11_06/manifest.json") != manifest["prior_resistance_manifest_sha256"]:
        raise AssertionError("prior resistance manifest differs")
    events = pd.read_csv(output/"events_4h.csv.gz", low_memory=False)
    breaks = events[events.event == "BREAK_TO_ADVERSE_SIDE"].copy()
    selected = {s: part.to_dict("records") for s, part in breaks.groupby("symbol")}
    previous_meta = {m["symbol"]: m for m in previous["symbols"]}
    results: list[dict[str, Any]] = []
    errors = {}
    if workers == 1:
        for symbol in manifest["selected_symbols"]:
            try:
                results.extend(replay_path_symbol(symbol, archive, previous_meta[symbol], selected.get(symbol, [])))
            except Exception as exc:
                errors[symbol] = f"{type(exc).__name__}: {exc}"
            print(f"{symbol}: completed, errors={len(errors)}", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            pending = {pool.submit(replay_path_symbol, symbol, archive, previous_meta[symbol], selected.get(symbol, [])): symbol
                       for symbol in manifest["selected_symbols"]}
            done = 0
            for future in as_completed(pending):
                symbol = pending[future]
                try:
                    results.extend(future.result())
                except Exception as exc:
                    errors[symbol] = f"{type(exc).__name__}: {exc}"
                done += 1
                print(f"{symbol}: {done}/{len(pending)}, errors={len(errors)}", flush=True)
    if errors:
        raise RuntimeError(f"path replay failed closed; outputs not written: {errors}")
    paths = pd.DataFrame(results).sort_values(["side", "symbol", "bar_index"], kind="stable").reset_index(drop=True)
    if len(paths) != len(breaks):
        raise AssertionError("path replay omitted break events")
    write_csv_gz(paths, output/"break_paths_24.csv.gz")
    old = set(json.loads(LEGACY_MANIFEST.read_text(encoding="utf-8"))["symbols"])
    all_summaries: dict[str, Any] = {}
    lines = ["# Aynı kırılma epizodunda çizgi–fiyat yolu", "",
             "Bu analiz diğer sonuçları gördükten sonra planlanmış keşifsel araştırmadır. Her 4s kırılmanın ardından tam ve temiz 24 × 4s bar izlenir; 24 bar ek teyit/bekleme kuralı değildir. Farklı dallara ait yüzdelerin paydaları farklıdır, aynı hisse/gündeki gözlemler bağımsız değildir.", ""]
    for scope, subset in (("2026", paths[paths.period == "Y2026"]), ("2025", paths[paths.period == "PRE_2026"]),
                          ("OLD100_BOTH_PERIODS", paths[paths.symbol.isin(old)])):
        all_summaries[scope] = {}
        first_rows, second_rows, flat_rows, price_rows = [], [], [], []
        for side in ("SUPPORT", "RESISTANCE"):
            g = subset[subset.side == side]
            v = g[g.status_24 == "VALID"]
            line = v[v.first_path == "LINE_ADVERSE_FIRST"]
            flat = line[line.after_line_first == "FLAT_PROXY_FIRST"]
            price = v[v.first_path == "PRICE_RETURNS_FIXED_FIRST"]
            groups = {"all_events": len(g), "status_24": {str(k): int(n) for k, n in g.status_24.value_counts().items()},
                      "right_censored_any": int(as_bool(g.right_censored_24).sum()),
                      "first": distribution(v, "first_path", FIRST),
                      "line_first_price_side": {str(k): int(n) for k, n in line.line_first_price_side.value_counts().items()},
                      "after_line": distribution(line, "after_line_first", AFTER_LINE),
                      "flat_price_side": {str(k): int(n) for k, n in flat.flat_price_side.value_counts().items()},
                      "after_flat": distribution(flat, "after_flat_first", AFTER_FLAT),
                      "after_price": distribution(price, "after_price_first", AFTER_PRICE)}
            all_summaries[scope][side] = groups
            first_rows.append({"group": side, **groups["first"]})
            second_rows.append({"group": side, **groups["after_line"]})
            flat_rows.append({"group": side, **groups["after_flat"]})
            price_rows.append({"group": side, **groups["after_price"]})
        lines += [f"## {scope}", "", render_table("İlk yarış: eski çizgiye fiyat dönüşü veya çizginin hareketi", first_rows, FIRST),
                  render_table("Çizgi ters yönde ilk hareket eden dalın devamı", second_rows, AFTER_LINE),
                  "Aday yataylaşmaya aynı çizgi kimliğinde ulaşma, görsel teyit değildir. Aynı-bar çakışma ayrı; ilk aşamada bu dala girenler paydadır.", "",
                  render_table("Aday yataylaşma sonrası, kalan pencerede ilk değişim", flat_rows, AFTER_FLAT),
                  "Burada yalnız aday yataylaşmaya ulaşanlar paydadır. Fiyatın yataylaşma anındaki yeni çizgiye göre konumları makine özetinde; karşı tarafa kapanış, kalıcı davranış kanıtı değildir.", "",
                  render_table("Eski çizgiye fiyatın ilk döndüğü dalın devamı", price_rows, AFTER_PRICE),
                  "Bu son tablo yalnız önce fiyat dönenler için. İlk kapanıştan sonra kalan süre değişkendir; bunlar işlem getirisi değildir.", ""]
    summary = {"scope": "exploratory post-results path analysis, not blind or causal", "horizon_4h": HORIZON,
               "selected_symbols": len(manifest["selected_symbols"]), "path_rows": len(paths), "errors": errors,
               "groups": all_summaries}
    (output/"break_path_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    (output/"yol_bulgulari.md").write_text("\n".join(lines), encoding="utf-8")
    path_manifest = {"comparison_manifest_sha256": sha(output/"manifest.json"),
                     "input_events_sha256": sha(output/"events_4h.csv.gz"),
                     "source_sha256": {str(p.resolve().relative_to(ROOT)): sha(p) for p in (
                         ROOT/"research/stabil_support_resistance_paths.py", ROOT/"test_stabil_support_resistance_paths.py", output/"YOL_PLANI.md")},
                     "outputs_sha256": {name: sha(output/name) for name in ("break_paths_24.csv.gz", "break_path_summary.json", "yol_bulgulari.md")}}
    (output/"path_manifest.json").write_text(json.dumps(path_manifest, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"path_rows": len(paths), "Y2026": all_summaries["2026"]}, ensure_ascii=False, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    run(args.output, args.workers)


if __name__ == "__main__":
    main()
