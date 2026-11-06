"""Reproduce Stabil arrows and known-at-close context from the local archive.

This is observational research, NOT trading advice. The future is used only for
explicit outcome columns; all features come from engines advanced through the
closed signal bar. Run with ``python -m research.stabil_arrow_context_replay``.
The compact per-symbol checkpoints live outside the repository by default, so a
long run can be resumed safely after interruption without touching live bot state.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import tempfile
from typing import Any

import numpy as np
import pandas as pd

from data import mum_kapanis_anlari
from domain_engines.fvg import FvgEngulfingConfig, FvgEngulfingEngine, SensitivityProfile
from domain_engines.fvg.fvg_engulfing_models import FvgState
from domain_engines.market_structure import MarketStructureEngine
from domain_engines.order_block import OrderBlockEngine
from domain_engines.stabil import build_single_pass_history, evaluate_bar_behaviors, project_support_to_bar_closes
from domain_engines.stabil.signals import _causal_atr14, _causal_vol_ratio20
from domain_engines.volume_participation import VolumeParticipationEngine
from research.arsiv import arsiv_koku, manifest_oku, tf_frame
from research.stabil_replay import select_bist_equity_universe

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/arastirma/stabil_ok_replay_2026_11_05"
CACHE = Path.home() / "formation-stabil-arrow-replay"
HORIZONS = (4, 8, 16)
# Version this string when changing measurement or checkpoint schema.
REPLAY_VERSION = "2026-11-05-v2-capture-cutoff"
SOURCE_FILES = (
    "research/stabil_arrow_context_replay.py", "research/arsiv.py", "research/stabil_replay.py",
    "config.py", "bist_calendar.py", "domain_engines/05_stabil.txt", "scripts/backfill/yahoo_backfill.py",
)
SOURCE_DIRS = (
    "data", "domain_engines/stabil", "domain_engines/order_block", "domain_engines/fvg",
    "domain_engines/market_structure", "domain_engines/volume_participation",
)



def finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def bad_bars(frame: pd.DataFrame) -> np.ndarray:
    """Invalid OHLCV or >30% close discontinuity; not a corporate-action oracle."""
    o, h, lo, c, v = (pd.to_numeric(frame[col], errors="coerce").to_numpy(dtype=float)
                       for col in ("open", "high", "low", "close", "volume"))
    bad = (~np.isfinite(o) | ~np.isfinite(h) | ~np.isfinite(lo) | ~np.isfinite(c) |
           ~np.isfinite(v) | (v < 0) | (lo <= 0) | (o <= 0) | (c <= 0) |
           (h < lo) | (h < o) | (h < c) | (lo > o) | (lo > c))
    with np.errstate(divide="ignore", invalid="ignore"):
        bad[1:] |= np.abs(c[1:] / c[:-1] - 1) > .30
    return bad


def forward_metrics(frame: pd.DataFrame, index: int, atr: float | None,
                    bad: np.ndarray, horizons: tuple[int, ...] = HORIZONS) -> dict[str, Any]:
    """Measure only bars strictly after entry, censor incomplete/invalid windows."""
    out: dict[str, Any] = {}
    entry = finite(frame.iloc[index]["close"])
    for horizon in horizons:
        suffix = str(horizon)
        status = "VALID"
        if atr is None or atr <= 0 or entry is None:
            status = "NO_ATR"
        elif index < 20 or bad[max(0, index - 19):index + 1].any():
            status = "BAD_HISTORY"
        elif index + horizon >= len(frame):
            status = "RIGHT_CENSORED"
        elif bad[index + 1:index + horizon + 1].any():
            status = "BAD_FUTURE"
        values: dict[str, Any] = {"status": status, "right_censored": index + horizon >= len(frame),
                                  "mfe_atr": None, "mae_atr": None, "return_atr": None,
                                  "weak_mfe": None, "first_1atr": None}
        if status == "VALID":
            future = frame.iloc[index + 1:index + horizon + 1]
            highs = future["high"].to_numpy(dtype=float)
            lows = future["low"].to_numpy(dtype=float)
            values["mfe_atr"] = max(0.0, float((max(highs) - entry) / atr))
            values["mae_atr"] = max(0.0, float((entry - min(lows)) / atr))
            values["return_atr"] = float((float(future.iloc[-1]["close"]) - entry) / atr)
            values["weak_mfe"] = values["mfe_atr"] < 0.5
            first = "NEITHER"
            for high, low in zip(highs, lows):
                up = high >= entry + atr
                down = low <= entry - atr
                if up and down:
                    first = "AMBIGUOUS_SAME_BAR"
                    break
                if up or down:
                    first = "UP_FIRST" if up else "DOWN_FIRST"
                    break
            values["first_1atr"] = first
        out.update({f"{key}_{suffix}": value for key, value in values.items()})
    return out


def _zone_bucket(distance: float | None, known: bool) -> str:
    if not known:
        return "UNKNOWN"
    if distance is None:
        return "NONE_AHEAD"
    return "NEAR_1ATR" if distance <= 1.0 else "FAR_OVER_1ATR"


def _native_context(engines: dict[str, Any], errors: dict[str, str], index: int,
                    price: float, atr: float | None) -> dict[str, Any]:
    """Capture native state immediately after this bar, never terminal state."""
    output: dict[str, Any] = {}
    enough = index >= 99 and atr is not None and atr > 0
    ob_known = enough and "OB" not in errors
    ob = engines["OB"]
    candidates = []
    if ob_known:
        for record in ob.active_records:
            if record.bullish:
                continue
            a, b = ob._active_remaining_zone(record)
            lower, upper = min(float(a), float(b)), max(float(a), float(b))
            if upper < price:
                continue
            distance = max(0.0, lower - price) / atr
            candidates.append((distance, -int(record.source_index), lower, upper, record))
    selected = min(candidates, key=lambda item: (item[0], item[1])) if candidates else None
    ob_distance = selected[0] if selected else None
    output.update({"ob_ahead": _zone_bucket(ob_distance, ob_known), "ob_distance_atr": ob_distance,
                   "ob_remaining_low": selected[2] if selected else None,
                   "ob_remaining_high": selected[3] if selected else None,
                   "ob_score": selected[4].score if selected else None,
                   "ob_fill_ratio": selected[4].fill_ratio if selected else None,
                   "ob_source_index": selected[4].source_index if selected else None})

    fvg = engines["FVG"]
    fvg_known = enough and "FVG" not in errors and str(fvg.last_data_quality) == "OK"
    record = fvg.active_bearish_fvg if fvg_known else None
    if record is not None and (record.state is FvgState.CANDIDATE or record.invalid or record.full_fill):
        record = None
    fvg_distance = lower = upper = None
    if record is not None:
        upper = float(record.upper_boundary)
        lower = min(upper, float(record.lower_boundary) + float(record.gap_size) * float(record.maximum_fill_ratio))
        if upper < price:
            record = None
            lower = upper = None
        else:
            fvg_distance = max(0.0, lower - price) / atr
    output.update({"fvg_ahead": _zone_bucket(fvg_distance, fvg_known), "fvg_distance_atr": fvg_distance,
                   "fvg_remaining_low": lower, "fvg_remaining_high": upper,
                   "fvg_quality": float(record.quality) if record is not None else None,
                   "fvg_state": record.state.name if record is not None else None,
                   "fvg_fill_ratio": float(record.maximum_fill_ratio) if record is not None else None,
                   "fvg_formation_index": record.formation_index if record is not None else None})

    vp = engines["VOLUME"]
    metrics = vp.metrics_history[-1] if "VOLUME" not in errors and vp.metrics_history else None
    vready = bool(metrics and metrics.data_ready and metrics.volume_usable)
    export = vp.final_export
    output.update({"volume_domain_ready": vready,
                   "volume_domain_rvol": finite(metrics.rvol) if vready else None,
                   "volume_domain_level": str(metrics.volume_level) if vready else "UNKNOWN",
                   "volume_participation_state": export.state if vready else "UNKNOWN",
                   "volume_pressure_5": finite(metrics.directional_value_pressure_5) if vready else None,
                   "volume_up_confirmed": bool(metrics.up_confirmed) if vready else None})

    ms = engines["MS"]
    known = enough and "MS" not in errors and ms.external_context.valid
    context = ms.external_context
    output.update({"ms_known": bool(known), "ms_external_state": context.state if known else "UNKNOWN",
                   "ms_external_direction": context.direction if known else None,
                   "ms_quality": finite(context.quality) if known else None,
                   "ms_conflict": bool(context.conflict_text) if known else None,
                   "domain_errors": dict(errors)})
    return output


def context_snapshots(frame: pd.DataFrame, indices: set[int], atrs: np.ndarray) -> dict[int, dict[str, Any]]:
    """Run each native 4h domain incrementally and capture only requested bars."""
    if not indices:
        return {}
    engines = {"OB": OrderBlockEngine(),
               "FVG": FvgEngulfingEngine(FvgEngulfingConfig(timeframe="4h", sensitivity=SensitivityProfile.BALANCED)),
               "VOLUME": VolumeParticipationEngine(), "MS": MarketStructureEngine()}
    errors: dict[str, str] = {}
    snapshots: dict[int, dict[str, Any]] = {}
    stop = max(indices)
    for index, row in enumerate(frame.iloc[:stop + 1].to_dict("records")):
        for name, engine in engines.items():
            if name in errors:
                continue
            try:
                engine.update(row)
            except Exception as exc:
                # Once broken, that domain is UNKNOWN for the rest of this symbol.
                errors[name] = f"{type(exc).__name__}: {str(exc)[:160]}"
        if index in indices:
            snapshots[index] = _native_context(engines, errors, index, float(row["close"]), finite(atrs[index]))
    return snapshots


def capture_cutoffs(symbol: str, archive_root: str | None = None) -> dict[str, pd.Timestamp]:
    """Conservative request-start bound, derived from the archive's own manifest.

    The timestamp is written after downloading. Subtracting the recorded full
    elapsed time plus one second (timestamp is rounded to seconds) avoids using
    a candle that might still have been open when the request started. Missing
    or malformed provenance fails closed rather than inventing a capture time.
    """
    records = manifest_oku(archive_root).get("kayitlar") or {}
    result = {}
    for tf in ("1h", "1d"):
        record = records.get(f"{symbol}:{tf}")
        if not isinstance(record, dict) or record.get("durum") != "ok" or record.get("dosya") != f"{symbol}_{tf}.csv.gz":
            raise ValueError(f"archive capture record missing or invalid: {symbol} {tf}")
        try:
            stamp = pd.Timestamp(record["zaman"])
            elapsed = float(record["sure_sn"])
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"archive capture time missing or invalid: {symbol} {tf}") from exc
        if pd.isna(stamp) or stamp.tzinfo is None or not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError(f"archive capture time missing or invalid: {symbol} {tf}")
        result[tf] = stamp.tz_convert("UTC") - pd.Timedelta(seconds=elapsed + 1)
    return result


def closed_at_capture(frame: pd.DataFrame, tf: str, capture: pd.Timestamp) -> pd.DataFrame:
    """Exclude bars whose scheduled close is after the archive capture bound."""
    return frame.loc[mum_kapanis_anlari(frame.index, tf) <= capture].copy()


def replay_symbol(symbol: str, archive_root: str | None = None) -> dict[str, Any]:
    captures = capture_cutoffs(symbol, archive_root)
    daily_all = tf_frame(symbol, "1d", archive_root)
    h4_all = tf_frame(symbol, "4h", archive_root)
    daily = closed_at_capture(daily_all, "1d", captures["1d"])
    h4 = closed_at_capture(h4_all, "4h", captures["1h"])
    hist = build_single_pass_history(symbol, daily, h4, include_support_prefix_events=False)
    frame = hist.h4_frame
    points = project_support_to_bar_closes(hist.h4_close_times, hist.support_timeline)
    behaviors = evaluate_bar_behaviors(symbol, "4h", frame, points, hist.support_timeline)
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    close = frame["close"].to_numpy(dtype=float)
    volume = frame["volume"].to_numpy(dtype=float)
    atrs = _causal_atr14(high, low, close)
    volumes = _causal_vol_ratio20(volume)
    invalid = bad_bars(frame)
    indices = {i for i, b in enumerate(behaviors) if b.reclaim_kind or b.momentum_kind or b.vertical_attempt_kind}
    contexts = context_snapshots(frame, indices, atrs)
    events: list[dict[str, Any]] = []
    last_nonoverlap = -100000
    for index in sorted(indices):
        b = behaviors[index]
        if b.reclaim_kind or b.momentum_kind:
            event_class = "UP_ARROW"
            kind = b.reclaim_kind or b.momentum_kind
        elif b.vertical_attempt_kind in {"close_reclaim", "intrabar_sweep_reclaim", "upward_rebase_momentum", "long_base_breakout"}:
            event_class = "VERTICAL_SUPPRESSED_PREVIOUS_UP_CANDIDATE"
            kind = b.vertical_attempt_kind
        else:
            event_class = "VERTICAL_OTHER_WARNING"
            kind = b.vertical_attempt_kind
        nonoverlap = event_class == "UP_ARROW" and index - last_nonoverlap >= 8
        if nonoverlap:
            last_nonoverlap = index
        atr = finite(atrs[index])
        relvol = finite(volumes[index])
        vol_bucket = ("UNKNOWN" if relvol is None else "LOW_LT_0.8" if relvol < 0.8 else
                      "MID_0.8_TO_1.2" if relvol < 1.2 else "HIGH_GE_1.2")
        daily_index, _ = hist.support_at(hist.h4_close_times[index])
        daily_trend = hist.daily_raw_timeline[daily_index] if daily_index >= 0 else None
        h4_trend = hist.h4_timeline[index]
        event = {"symbol": symbol, "timeframe": "4h", "event_close_time": str(hist.h4_close_times[index]),
                 "bar_index": index, "event_class": event_class, "kind": kind,
                 "support": b.support_level, "price": b.close_price,
                 "open": float(frame.iloc[index]["open"]), "high": float(high[index]), "low": float(low[index]),
                 "volume": float(volume[index]), "regime_proxy": b.regime,
                 "stabil_daily_raw_state": daily_trend.raw_state.value if daily_trend and daily_trend.data_ready else "UNKNOWN",
                 "stabil_h4_state": h4_trend.state.value if h4_trend.data_ready else "UNKNOWN",
                 "stabil_h4_volume_pass": bool(h4_trend.volume_pass) if h4_trend.data_ready and h4_trend.volume_usable else None,
                 "vertical_proxy": b.vertical_support, "fixed_support": b.fixed_support,
                 "touch_count": b.touch_count, "body_atr": b.body_atr, "distance_atr": b.dist_atr,
                 "atr14_4h": atr, "volume_ratio20": relvol, "volume_bucket": vol_bucket,
                 "nonoverlap_8": nonoverlap}
        event.update(contexts[index])
        event.update(forward_metrics(frame, index, atr, invalid))
        events.append(event)
    return {"symbol": symbol, "bars_1d": len(hist.daily_frame), "bars_4h": len(frame),
            "capture_start_bound_utc": {tf: timestamp.isoformat() for tf, timestamp in captures.items()},
            "excluded_unclosed_1d": len(daily_all) - len(daily),
            "excluded_unclosed_4h": len(h4_all) - len(h4),
            "first_4h_close": str(hist.h4_close_times[0]) if len(frame) else None,
            "last_4h_close": str(hist.h4_close_times[-1]) if len(frame) else None,
            "events": events}


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as inp:
        for block in iter(lambda: inp.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_hashes() -> dict[str, str]:
    paths = [ROOT / name for name in SOURCE_FILES]
    paths.extend(path for directory in SOURCE_DIRS for path in (ROOT / directory).rglob("*.py"))
    return {str(path.relative_to(ROOT)): file_hash(path) for path in sorted(set(paths))}


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(value, output, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def cached_symbol(symbol: str, archive_root: str, cache_root: str, sources: dict[str, str]) -> dict[str, Any]:
    input_hashes = {f"{symbol}_{tf}.csv.gz": file_hash(Path(archive_root) / f"{symbol}_{tf}.csv.gz")
                    for tf in ("1h", "1d")}
    input_hashes["manifest.json"] = file_hash(Path(archive_root) / "manifest.json")
    signature = hashlib.sha256(json.dumps({"version": REPLAY_VERSION, "source": sources,
                                           "input": input_hashes}, sort_keys=True).encode()).hexdigest()
    cache_path = Path(cache_root) / f"{symbol}.json"
    if cache_path.exists():
        try:
            value = json.loads(cache_path.read_text(encoding="utf-8"))
            if value.get("signature") == signature:
                return value
        except (ValueError, OSError):
            pass
    value = {"signature": signature, "input_hashes": input_hashes, "result": replay_symbol(symbol, archive_root)}
    _atomic_json(cache_path, value)
    return value


def _serialize_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if rows:
        frame = pd.DataFrame(rows).sort_values(["symbol", "bar_index"], kind="stable")
        frame["domain_errors"] = frame["domain_errors"].map(lambda x: json.dumps(x, ensure_ascii=False, sort_keys=True))
    else:
        frame = pd.DataFrame(columns=["symbol", "bar_index", "event_close_time", "event_class"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as zipped:
            with io.TextIOWrapper(zipped, encoding="utf-8", newline="") as text:
                frame.to_csv(text, index=False, lineterminator="\n")


def _group_rows(frame: pd.DataFrame, column: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for key, group in frame.groupby(column, dropna=False, sort=True):
        valid = group[group["status_8"] == "VALID"]
        n = len(valid)
        results.append({"group": str(key), "all_events": len(group), "valid_8": n,
                        "symbols_valid": int(valid.symbol.nunique()),
                        "weak_mfe_n": int(valid.weak_mfe_8.sum()) if n else 0,
                        "weak_mfe_rate": float(valid.weak_mfe_8.mean()) if n else None,
                        "nonpositive_close_rate": float((valid.return_atr_8 <= 0).mean()) if n else None,
                        "median_return_atr": float(valid.return_atr_8.median()) if n else None,
                        "up_first_rate": float((valid.first_1atr_8 == "UP_FIRST").mean()) if n else None,
                        "down_first_rate": float((valid.first_1atr_8 == "DOWN_FIRST").mean()) if n else None,
                        "same_bar_ambiguous_n": int((valid.first_1atr_8 == "AMBIGUOUS_SAME_BAR").sum()),
                        "right_censored_n": int((group.status_8 == "RIGHT_CENSORED").sum())})
    return results


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"event_class_counts": {}, "symbols_with_arrow": 0, "arrow_status_8_counts": {},
                "valid_arrows_8": 0, "weak_mfe_arrows_8": 0, "nonpositive_close_arrows_8": 0,
                "nonoverlap_arrows_8": 0, "comparisons": {}, "nonoverlap_comparisons": {}}
    frame = pd.DataFrame(rows)
    arrows = frame[frame.event_class == "UP_ARROW"].copy()
    valid = arrows[arrows.status_8 == "VALID"]
    comparisons = {}
    for name in ("kind", "volume_bucket", "ob_ahead", "fvg_ahead", "ms_external_state", "regime_proxy",
                 "stabil_daily_raw_state", "stabil_h4_state"):
        comparisons[name] = _group_rows(arrows, name)
    comparison_nonoverlap = {name: _group_rows(arrows[arrows.nonoverlap_8], name)
                             for name in ("kind", "volume_bucket", "ob_ahead", "fvg_ahead")}
    return {"event_class_counts": frame.event_class.value_counts().to_dict(),
            "symbols_with_arrow": int(arrows.symbol.nunique()),
            "arrow_status_8_counts": arrows.status_8.value_counts().to_dict(),
            "valid_arrows_8": len(valid), "weak_mfe_arrows_8": int(valid.weak_mfe_8.sum()),
            "nonpositive_close_arrows_8": int((valid.return_atr_8 <= 0).sum()),
            "nonoverlap_arrows_8": int(arrows.nonoverlap_8.sum()),
            "comparisons": comparisons, "nonoverlap_comparisons": comparison_nonoverlap}


def run(args: argparse.Namespace) -> int:
    root = str(arsiv_koku(args.archive).resolve())
    symbols = select_bist_equity_universe(args.limit, kok=root)
    if args.symbol:
        requested = {s.upper() for s in args.symbol}
        symbols = [s for s in symbols if s in requested]
        missing = requested - set(symbols)
        if missing:
            raise ValueError(f"unknown/excluded symbols: {sorted(missing)}")
    if not symbols:
        raise ValueError("no eligible archive symbols")
    hashes = source_hashes()
    done: dict[str, dict[str, Any]] = {}
    failures: dict[str, str] = {}
    # Per-symbol cache is atomically checkpointed by the worker. A failed symbol
    # is reported as unknown instead of silently excluded from the manifest.
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        tasks = {pool.submit(cached_symbol, sym, root, args.cache, hashes): sym for sym in symbols}
        for task in as_completed(tasks):
            sym = tasks[task]
            try:
                done[sym] = task.result()
                print(f"[{len(done) + len(failures)}/{len(symbols)}] {sym}: "
                      f"{len(done[sym]['result']['events'])} events", flush=True)
            except Exception as exc:
                failures[sym] = f"{type(exc).__name__}: {str(exc)[:200]}"
                print(f"[{len(done) + len(failures)}/{len(symbols)}] {sym}: ERROR {failures[sym]}", flush=True)
    if not done:
        raise RuntimeError(f"all symbols failed: {failures}")
    rows = [ev for sym in sorted(done) for ev in done[sym]["result"]["events"]]
    args.output.mkdir(parents=True, exist_ok=True)
    _serialize_csv(args.output / "events.csv.gz", rows)
    summary = aggregate(rows)
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    manifest = {"version": REPLAY_VERSION, "generated_utc": datetime.now(timezone.utc).isoformat(),
                "git_head_at_run": commit, "python": platform.python_version(), "pandas": pd.__version__,
                "numpy": np.__version__, "source_sha256": hashes, "archive_root_label": "backfill_data",
                "input_sha256": {k: v for sym in sorted(done) for k, v in done[sym]["input_hashes"].items()},
                "selection": "sorted BIST equities with local 1h archive", "symbols_requested": symbols,
                "symbols_successful": sorted(done), "symbols_failed": failures,
                "symbol_coverage": [{k: v for k, v in done[sym]["result"].items() if k != "events"}
                                    for sym in sorted(done)],
                "definition": {"event": "closed 4h Stabil signal; post-policy arrows and separate vertical attempts",
                               "capture_cutoff": "scheduled bar close <= manifest timestamp minus recorded fetch duration and one second",
                               "atr": "causal Wilder ATR14 in 4h bars, frozen at event close",
                               "weak_reaction": "full next 8 bars MFE < 0.5 ATR; not inferred for censored/invalid windows",
                               "return": "8th later bar close minus signal close, in frozen ATR units",
                               "race": "first high >= entry+ATR or low <= entry-ATR; both on same bar is ambiguous",
                               "invalid": "bad OHLCV or >30 percent close gap in last 20 or outcome horizon",
                               "overlap": "all signals retained; independent comparison keeps first per symbol >=8 bars apart",
                               "ob": "nearest confirmed active bearish OB remaining zone at/above close",
                               "fvg": "selected native active bearish FVG remaining zone at/above close; candidate excluded",
                               "volume": "event volume / mean of up to previous 20 positive 4h volumes; >=5 required",
                               "regime": "unconfirmed vertical/horizontal candidate proxy, not visual ground truth"},
                "summary": summary}
    (args.output / "summary.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} events from {len(done)}/{len(symbols)} symbols to {args.output}", flush=True)
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10000, help="number of sorted equity symbols; default all")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--symbol", action="append", help="repeat to restrict to specific eligible symbols")
    parser.add_argument("--archive", default=None)
    parser.add_argument("--cache", default=str(CACHE))
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    if args.workers < 1 or args.limit < 1:
        parser.error("--workers and --limit must be positive")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
