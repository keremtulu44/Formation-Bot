"""Symmetric, research-only comparison of native Stabil support and resistance.

The normal support is computed by the unmodified native engine on original
prices. A fixed positive reflection is used only to reuse exactly the same 4h
measurement machinery as the previous resistance replay. See PLAN.md.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import platform
from typing import Any

import numpy as np
import pandas as pd

from domain_engines.stabil import (
    build_daily_support_observations,
    build_support_lifecycle_timeline,
    classify_candidate_support_regimes,
    prepare_causal_ohlcv,
)
from domain_engines.stabil.signals import _causal_atr14
from domain_engines.stabil.stabil_trend_engine import _atr
from research.arsiv import arsiv_koku, ham_frame, tf_frame
from research.stabil_arrow_context_replay import bad_bars, capture_cutoffs, closed_at_capture
from research.stabil_resistance_replay import (
    DEFAULT_OUTPUT as RESISTANCE_OUTPUT,
    EVENT_NAMES,
    HORIZONS,
    REGIME_NAMES,
    ROOT,
    SPLIT,
    Forward,
    Line,
    empty_line,
    intraday_completeness,
    native_mirror,
    project_daily_at_bar_open,
    replay_4h,
    sha,
    write_csv_gz,
)

OUTPUT = ROOT / "docs/arastirma/stabil_destek_direnc_karsilastirma_2026_11_06"
LEGACY_MANIFEST = ROOT / "docs/arastirma/stabil_100_sonuclar/STABIL_DAVRANIS_48_MANIFEST.json"
REFLECTION = 100_000.0
NATIVE_NAMES = {
    "RESISTANCE_CONFIRMED": "CONFIRMED",
    "RESISTANCE_TESTED": "TESTED",
    "RESISTANCE_HELD": "HELD",
    "RESISTANCE_BREACHED": "BREACHED",
    "RESISTANCE_CEILING_BROKEN": "BOUNDARY_BROKEN",
    "RESISTANCE_RETURN_BELOW": "RETURN_TO_SAFE_SIDE",
    "RESISTANCE_ABANDONED_HIGHER": "ABANDONED_ADVERSELY",
    "RESISTANCE_REBASED_HIGHER": "REBASED_ADVERSE",
    "RESISTANCE_REBASED_LOWER": "REBASED_FAVORABLE",
}
REGIME_CANONICAL = {
    "RESISTANCE_STEP_DOWN_PROXY": "FAVORABLE_STEP_PROXY",
    "RESISTANCE_STEP_UP_PROXY": "ADVERSE_STEP_PROXY",
    "FLAT_AFTER_RESISTANCE_DROP_PROXY": "FLAT_AFTER_FAVORABLE_PROXY",
    "FLAT_AFTER_RESISTANCE_RISE_PROXY": "FLAT_AFTER_ADVERSE_PROXY",
    "LONG_FLAT_PROXY": "LONG_FLAT_PROXY",
    "FLAT_BASE_PROXY": "FLAT_BASE_PROXY",
    "RESISTANCE_BREACHED_FIXED_PROXY": "BREACHED_FIXED_PROXY",
    "UNAVAILABLE": "UNAVAILABLE",
}
FIRST_NAMES = {"DOWN_FIRST": "REACTION_FIRST", "UP_FIRST": "BREACH_SIDE_FIRST",
               "AMBIGUOUS_SAME_BAR": "AMBIGUOUS_SAME_BAR", "NEITHER": "NEITHER"}
CONTACT_NAMES = {"NEAR_ONLY": "NEAR_ONLY", "GAP_ABOVE_NO_TOUCH": "GAP_INTO_BREACH_NO_TOUCH",
                 "TOUCH_CLOSE_ABOVE": "TOUCH_CLOSE_BREACHED", "WICK_TOUCH_CLOSE_AT_OR_BELOW": "TOUCH_CLOSE_SAFE"}
RETEST_NAMES = {"TOUCH_CLOSE_ABOVE": "TOUCH_CLOSE_BREACHED",
                "TOUCH_CLOSE_AT_OR_BELOW": "TOUCH_CLOSE_SAFE",
                "GAP_OR_OPEN_AT_BELOW_RECLAIM": "OPEN_SAFE_CLOSE_BREACHED",
                "GAP_OR_OPEN_AT_BELOW_FAIL": "OPEN_SAFE_CLOSE_SAFE", "NO_RETEST": "NO_RETEST"}
RACE_NAMES = {"LEVEL_FOLLOWS_DOWN_FIRST": "LEVEL_FOLLOWS_FAVORABLE_FIRST",
              "PRICE_RETURNS_FIRST": "PRICE_RETURNS_FIRST", "AMBIGUOUS_SAME_BAR": "AMBIGUOUS_SAME_BAR",
              "NEITHER": "NEITHER", "LEVEL_UNAVAILABLE": "LEVEL_UNAVAILABLE"}
FOUR_H_EVENTS = {"TEST": "TEST", "BREAK_UP": "BREAK_TO_ADVERSE_SIDE", "RETURN_DOWN": "RETURN_TO_SAFE_SIDE",
                 "DEPART_BELOW": "DEPART_FAVORABLE", "STATE_CROSS_UP": "STATE_TO_ADVERSE_SIDE",
                 "STATE_CROSS_DOWN": "STATE_TO_SAFE_SIDE"}


def reflect_prices(frame: pd.DataFrame) -> pd.DataFrame:
    """Reflect while preserving time/volume; never derive the constant from future prices."""
    if frame.empty:
        return frame.copy()
    if not np.isfinite(frame[["open", "high", "low", "close"]].to_numpy(dtype=float)).all():
        raise ValueError("non-finite OHLC cannot be reflected")
    if frame["high"].max() >= REFLECTION or frame["low"].min() <= 0:
        raise ValueError("OHLC outside fixed reflection coordinate")
    out = frame.copy()
    out["open"] = REFLECTION - frame["open"].astype(float)
    out["high"] = REFLECTION - frame["low"].astype(float)
    out["low"] = REFLECTION - frame["high"].astype(float)
    out["close"] = REFLECTION - frame["close"].astype(float)
    return out


def native_support_as_reflected_line(daily: pd.DataFrame) -> tuple[Line, tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
    """Calculate native support on original OHLC; only then reflect its outputs."""
    observations = build_daily_support_observations(daily)
    timeline = build_support_lifecycle_timeline(observations, include_prefix_events=False)
    regimes = classify_candidate_support_regimes(timeline)
    line = empty_line(len(daily))
    index_by_time = {pd.Timestamp(t).value: i for i, t in enumerate(daily["timestamp"])}
    for i, observation in enumerate(observations):
        if observation.support_level is None:
            continue
        line.level[i] = REFLECTION - float(observation.support_level)
        line.ceiling[i] = REFLECTION - float(observation.support_floor)
        line.origin[i] = observation.support_origin_index
        line.known[i] = observation.support_confirmed_index
        line.available[i] = index_by_time[pd.Timestamp(observation.support_available_at).value]
        line.age[i] = i - line.available[i]
        line.identity[i] = (int(line.origin[i]), int(line.known[i]), float(line.level[i]))
    return line, observations, timeline, regimes


def check_reflection_against_native(daily: pd.DataFrame, line: Line, timeline: tuple[Any, ...]) -> None:
    """Independent native run on reflected prices must yield the same level/timing."""
    reflected_line, _, reflected_timeline, _ = native_mirror(reflect_prices(daily))
    for field in ("level", "ceiling", "origin", "known", "available", "age"):
        if not np.allclose(getattr(line, field), getattr(reflected_line, field), equal_nan=True, rtol=0, atol=1e-8):
            raise AssertionError(f"support reflection mismatch: {field}")
    # Current code never uses the reflected timeline for classification. Tick-
    # boundary progression can differ under floating translation; validity must not.
    for direct, reflected in zip(timeline, reflected_timeline):
        if direct.validity != reflected.validity:
            raise AssertionError("reflected and direct native validity differ")


def verify_direct_event_selection(frame: pd.DataFrame, daily: pd.DataFrame, starts: pd.DatetimeIndex,
                                  observations: tuple[Any, ...], rows: list[dict[str, Any]]) -> dict[str, int]:
    """Re-derive the four research event anchors directly in original price units."""
    o, high, low, close = (frame[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close"))
    del o
    atr = _causal_atr14(high, low, close)
    loc = project_daily_at_bar_open(pd.DatetimeIndex(daily.timestamp), starts)
    actual = {(int(r["bar_index"]), r["event"]) for r in rows
              if r["event"] in {"TEST", "BREAK_UP", "RETURN_DOWN", "DEPART_BELOW"}}
    expected: set[tuple[int, str]] = set()
    for i in range(1, len(frame)):
        di = int(loc[i])
        if di < 0 or observations[di].support_level is None or not np.isfinite(atr[i-1]) or atr[i-1] <= 0:
            continue
        s, a = float(observations[di].support_level), float(atr[i-1])
        dist = (close[i-1] - s) / a
        if 0 <= dist <= 1.5 and low[i-1] > s+.25*a and low[i] <= s+.25*a:
            expected.add((i, "TEST"))
        if close[i-1] >= s and close[i] < s:
            expected.add((i, "BREAK_UP"))
        if close[i-1] < s and close[i] >= s:
            expected.add((i, "RETURN_DOWN"))
        if close[i-1] >= s and close[i-1] < s+1.5*a and close[i] >= s+1.5*a:
            expected.add((i, "DEPART_BELOW"))
    if actual != expected:
        missing = sorted(expected-actual)[:8]
        extra = sorted(actual-expected)[:8]
        raise AssertionError(f"direct support event mismatch: missing={missing} extra={extra}")
    return dict(Counter(kind for _, kind in actual))


def native_support_events(symbol: str, daily: pd.DataFrame, timeline: tuple[Any, ...],
                          regimes: tuple[Any, ...], bad: np.ndarray) -> list[dict[str, Any]]:
    """Actual native support events, in the same orientation as resistance events."""
    reflected = reflect_prices(daily)
    atr = np.asarray([np.nan if x is None else x for x in _atr(daily)], dtype=float)
    forward = Forward(reflected, atr, bad, np.zeros(len(daily), dtype=bool), np.cumsum(bad) > 0)
    by_time = {pd.Timestamp(t).value: i for i, t in enumerate(daily.timestamp)}
    rows: list[dict[str, Any]] = []
    for ev in timeline[-1].events:
        i = by_time[pd.Timestamp(ev.event_time).value]
        ts = pd.Timestamp(ev.event_time)
        line = None if ev.support_level is None else REFLECTION - float(ev.support_level)
        ceiling = None if ev.support_floor is None else REFLECTION - float(ev.support_floor)
        row: dict[str, Any] = {
            "symbol": symbol, "event": EVENT_NAMES[ev.event_type.value], "event_time": ts.isoformat(),
            "period": "PRE_2026" if ts < pd.Timestamp("2026-01-01", tz="Europe/Istanbul") else "Y2026",
            "quarter": f"{ts.year}Q{(ts.month-1)//3+1}", "event_index": i, "sequence": ev.sequence,
            "line": line, "ceiling": ceiling, "event_close": REFLECTION-float(ev.price),
            "atr_daily": float(ev.atr) if ev.atr is not None else None,
            "pivot_origin_time": pd.Timestamp(ev.origin_at).isoformat() if ev.origin_at is not None else None,
            "pivot_confirmed_time": pd.Timestamp(ev.confirmed_at).isoformat() if ev.confirmed_at is not None else None,
            "event_known_time": pd.Timestamp(ev.available_at).isoformat() if ev.available_at is not None else None,
            "known_age_daily_bars": ev.bars_since_support,
            "regime_proxy": REGIME_NAMES.get(regimes[i].regime.value, "UNKNOWN"),
        }
        row.update(forward.at(i))
        if line is not None and ceiling is not None:
            row.update(forward.line_outcomes(i, line, ceiling, "NATIVE"))
        rows.append(row)
    return rows



def legacy_daily_touch_sequence(observations: tuple[Any, ...], timeline: tuple[Any, ...]) -> tuple[np.ndarray, np.ndarray]:
    """C02's native daily touch count; first available episode remains unknown."""
    sequence = np.full(len(observations), -1, dtype=int)
    known = np.zeros(len(observations), dtype=bool)
    seen_first, active, previous_identity = False, False, None
    count = 0
    for i, (obs, snap) in enumerate(zip(observations, timeline)):
        identity = obs.support_identity
        if identity is None:
            previous_identity = None
            continue
        if identity != previous_identity:
            ep_known = seen_first
            seen_first = True
            previous_identity = identity
            active, count = False, 0
        known[i] = ep_known
        level = float(obs.support_level)
        atr = float(obs.atr) if obs.atr is not None and obs.atr > 0 else np.nan
        is_touch = float(obs.low) <= level <= float(obs.high) and not snap.close_below_support
        dist = (float(obs.close)-level)/atr if np.isfinite(atr) else 0.0
        if is_touch:
            if not active:
                count += 1
                active = True
        elif not snap.close_below_support and active and dist >= .35:
            active = False
        sequence[i] = count if ep_known else -1
    return sequence, known


def full_window_status(forward: Forward, i: int, horizon: int) -> str:
    if i < 20 or not np.isfinite(forward.atr[i]) or forward.atr[i] <= 0:
        return "NO_HISTORY_OR_ATR"
    if forward.structural_bad[i]:
        return "BAD_DAILY_SOURCE_HISTORY"
    if forward.bad[i-19:i+1].any() or forward.gaps[i-18:i+1].any():
        return "BAD_HISTORY_OR_MISSING"
    if i+horizon >= len(forward.close):
        return "RIGHT_CENSORED"
    if forward.bad[i+1:i+horizon+1].any() or forward.gaps[i+1:i+horizon+1].any():
        return "BAD_FUTURE_OR_MISSING"
    if forward.structural_bad[i+horizon]:
        return "BAD_DAILY_SOURCE_FUTURE"
    if forward.times[i] < SPLIT <= forward.times[i+horizon]:
        return "CROSS_SPLIT"
    return "VALID"


def checkpoint_race_24(i: int, forward: Forward, levels: np.ndarray) -> tuple[str, str | None]:
    """Legacy A01/F01 competing race, with a strictly complete 24-bar window."""
    status = full_window_status(forward, i, 24)
    if status != "VALID":
        return status, None
    level, atr, close = levels[i], forward.atr[i], forward.close[i]
    if not np.isfinite(level):
        return "NO_LEVEL", None
    above = close >= level
    for j in range(i+1, i+25):
        future_level = levels[j]
        if not np.isfinite(future_level):
            return "VALID", "LEVEL_UNAVAILABLE"
        rebase_up = future_level > level + .01
        rebase_down = future_level < level - .01
        price_touch = above and forward.low[j] <= level + .15*atr
        price_reclaim = not above and forward.close[j] >= level
        if above:
            if rebase_up and price_touch:
                return "VALID", "AMBIGUOUS_SAME_BAR"
            if rebase_up:
                return "VALID", "LINE_FAVORABLE_FIRST"
            if price_touch:
                return "VALID", "PRICE_RETURN_FIRST"
            if rebase_down:
                return "VALID", "LINE_ADVERSE_FIRST"
        else:
            if rebase_down and price_reclaim:
                return "VALID", "AMBIGUOUS_SAME_BAR"
            if price_reclaim:
                return "VALID", "PRICE_RECLAIM_FIRST"
            if rebase_down:
                return "VALID", "LINE_ADVERSE_FIRST"
    return "VALID", "NEITHER"


def legacy_like_checkpoints(symbol: str, side: str, h4: pd.DataFrame, h4_opens: pd.DatetimeIndex,
                            daily: pd.DataFrame, observations: tuple[Any, ...], timeline: tuple[Any, ...],
                            regimes: tuple[Any, ...], bad: np.ndarray, gaps: np.ndarray,
                            daily_bad: np.ndarray) -> list[dict[str, Any]]:
    """A01/B04/C02/F01 cohorts from the recorded definitions, mirrored by side."""
    favorable = h4 if side == "SUPPORT" else reflect_prices(h4)
    closes = pd.DatetimeIndex(h4.timestamp)
    d_times = pd.DatetimeIndex(daily.timestamp)
    loc = project_daily_at_bar_open(d_times, closes)  # close-known checkpoint; no event-bar high/low in F01/A01/B04
    loc_at_open = project_daily_at_bar_open(d_times, h4_opens)
    seq, known = legacy_daily_touch_sequence(observations, timeline)
    lvls = np.full(len(h4), np.nan)
    atrs = np.full(len(h4), np.nan)
    structural = np.zeros(len(h4), dtype=bool)
    ever_bad = np.cumsum(daily_bad) > 0
    for i, di in enumerate(loc):
        if di < 0:
            continue
        structural[i] = ever_bad[di]
        obs = observations[di]
        if obs.support_level is not None and obs.atr is not None and obs.atr > 0:
            lvls[i] = float(obs.support_level) + (REFLECTION if side == "RESISTANCE" else 0.0)
            atrs[i] = float(obs.atr)
    forward = Forward(favorable, atrs, bad, gaps, structural)
    price = forward.close
    race_cache: dict[int, tuple[str, str | None]] = {}
    result: list[dict[str, Any]] = []
    first_map = {"UP_FIRST": "REACTION_FIRST", "DOWN_FIRST": "BREACH_SIDE_FIRST",
                 "AMBIGUOUS_SAME_BAR": "AMBIGUOUS_SAME_BAR", "NEITHER": "NEITHER"}
    for i in range(len(h4)):
        di = int(loc[i])
        if di < 0 or not np.isfinite(lvls[i]) or not np.isfinite(atrs[i]) or atrs[i] <= 0:
            continue
        level, atr, c = lvls[i], atrs[i], price[i]
        dist = (c-level)/atr
        regime = regimes[di].regime.value
        cohorts: list[tuple[str, str]] = []
        if c >= level and dist >= 1:
            bucket = "1..2_ATR" if dist < 2 else "2..3.5_ATR" if dist < 3.5 else "3.5+_ATR"
            cohorts.append(("A01", bucket))
        if c >= level and 0 <= dist <= 2.5 and known[di] and regime in {"NEWLY_FLATTENED_AFTER_RISE", "LONG_HORIZONTAL"}:
            cohorts.append(("B04", "NEW_FLAT_AFTER_FAVORABLE" if regime == "NEWLY_FLATTENED_AFTER_RISE" else "LONG_FLAT"))
        # The old C02 uses daily touch ordinal at a 4h checkpoint, not a new
        # independent 4h touch every time. Require the daily ATR/line at open.
        if int(loc_at_open[i]) == di and c >= level and forward.low[i] <= level+.05*atr:
            bucket = "UNKNOWN" if seq[di] < 0 else "FIRST" if seq[di] == 1 else "SECOND" if seq[di] == 2 else "THIRD_PLUS" if seq[di] >= 3 else "ZERO"
            cohorts.append(("C02", bucket))
        past4 = (c-price[i-4])/atr if i >= 4 else np.nan
        if np.isfinite(past4) and past4 > .3 and regime in {"STEPPING_DOWN", "HORIZONTAL_AFTER_DROP"}:
            cohorts.append(("F01", "ADVERSE_STEP_PROXY" if regime == "STEPPING_DOWN" else "FLAT_AFTER_ADVERSE_PROXY"))
        if not cohorts:
            continue
        metrics = forward.at(i)
        if i not in race_cache:
            race_cache[i] = checkpoint_race_24(i, forward, lvls)
        status24, race24 = race_cache[i]
        time = closes[i]
        for question, bucket in cohorts:
            row: dict[str, Any] = {
                "symbol": symbol, "side": side, "question": question, "bucket": bucket,
                "bar_index": i, "event_close_time": time.isoformat(),
                "period": "PRE_2026" if time < SPLIT else "Y2026",
                "quarter": f"{time.year}Q{(time.month-1)//3+1}",
                "daily_asof": pd.Timestamp(daily.iloc[di].timestamp).isoformat(),
                "line": level if side == "SUPPORT" else REFLECTION-level,
                "close": c if side == "SUPPORT" else REFLECTION-c,
                "daily_atr": atr, "distance_safe_daily_atr": dist,
                "past4_reaction_daily_atr": past4 if np.isfinite(past4) else None,
                "daily_touch_seq": int(seq[di]) if seq[di] >= 0 else None,
                "episode_known": bool(known[di]), "regime_native_proxy": regime,
                "race_status_24": status24, "race_first_24": race24,
            }
            for horizon in HORIZONS:
                row[f"status_{horizon}"] = metrics[f"status_{horizon}"]
                row[f"right_censored_{horizon}"] = metrics[f"right_censored_{horizon}"]
                row[f"first_1atr_{horizon}"] = first_map.get(metrics[f"first_1atr_{horizon}"])
                row[f"reaction_return_atr_{horizon}"] = metrics[f"return_atr_{horizon}"]
                row[f"reaction_excursion_atr_{horizon}"] = metrics[f"up_excursion_atr_{horizon}"]
                row[f"adverse_excursion_atr_{horizon}"] = metrics[f"down_excursion_atr_{horizon}"]
            result.append(row)
    return result

def replay_support_symbol(symbol: str, archive: str, previous_meta: dict[str, Any]) -> dict[str, Any]:
    root = Path(archive)
    captures = capture_cutoffs(symbol, archive)
    daily_raw = closed_at_capture(tf_frame(symbol, "1d", root), "1d", captures["1d"])
    h4_raw = closed_at_capture(tf_frame(symbol, "4h", root), "4h", captures["1h"])
    hourly = closed_at_capture(ham_frame(symbol, "1h", root), "1h", captures["1h"])
    daily, error_d = prepare_causal_ohlcv(daily_raw, symbol=symbol, timeframe="1d")
    h4, error_h = prepare_causal_ohlcv(h4_raw, symbol=symbol, timeframe="4h")
    if error_d or error_h or len(daily) != len(daily_raw) or len(h4) != len(h4_raw):
        raise ValueError(f"closed frame preparation error: {error_d}, {error_h}")
    incomplete, gaps, quality = intraday_completeness(hourly, h4_raw, daily_raw, captures["1h"])
    daily_bad = bad_bars(daily)
    suspect_dates = set(pd.DatetimeIndex(daily.timestamp)[daily_bad].tz_convert("Europe/Istanbul").date)
    on_suspect_date = np.asarray([t.date() in suspect_dates for t in pd.DatetimeIndex(h4.timestamp)], dtype=bool)
    h4_bad = bad_bars(h4) | incomplete | on_suspect_date
    checks = {"daily_bars": len(daily), "h4_bars": len(h4),
              "bad_daily_bars_including_30pct_jump": int(daily_bad.sum()),
              "bad_h4_bars_including_incomplete_and_30pct_jump": int(h4_bad.sum()),
              "h4_bars_on_suspect_daily_date": int(on_suspect_date.sum()), **quality}
    for key, value in checks.items():
        if int(previous_meta[key]) != value:
            raise AssertionError(f"previous resistance quality mismatch {symbol} {key}: {value} != {previous_meta[key]}")
    line, observations, timeline, regimes = native_support_as_reflected_line(daily)
    check_reflection_against_native(daily, line, timeline)
    reflected_h4 = reflect_prices(h4)
    actual_atr = _causal_atr14(h4.high.to_numpy(), h4.low.to_numpy(), h4.close.to_numpy())
    reflected_atr = _causal_atr14(reflected_h4.high.to_numpy(), reflected_h4.low.to_numpy(), reflected_h4.close.to_numpy())
    if not np.allclose(actual_atr, reflected_atr, rtol=1e-8, atol=1e-8, equal_nan=True):
        raise AssertionError("reflected 4h ATR differs")
    events, coverage = replay_4h(symbol, reflected_h4, daily, h4_raw.index,
                                 {"MIRROR_P4": line}, timeline, regimes, h4_bad, gaps, daily_bad)
    event_checks = verify_direct_event_selection(h4, daily, h4_raw.index, observations, events)
    native_events = native_support_events(symbol, daily, timeline, regimes, daily_bad)
    _, resistance_obs, resistance_timeline, resistance_regimes = native_mirror(daily)
    questions = legacy_like_checkpoints(symbol, "SUPPORT", h4, h4_raw.index, daily, observations, timeline, regimes,
                                        h4_bad, gaps, daily_bad)
    questions += legacy_like_checkpoints(symbol, "RESISTANCE", h4, h4_raw.index, daily, resistance_obs,
                                         resistance_timeline, resistance_regimes, h4_bad, gaps, daily_bad)
    return {"symbol": symbol, "checks": checks, "event_checks": event_checks,
            "coverage": coverage, "events": events, "native_events": native_events,
            "question_checkpoints": questions}


def validate_previous_inputs(archive: Path, resistance: Path) -> dict[str, Any]:
    manifest = json.loads((resistance / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("errors") or manifest.get("successful_symbols") != len(manifest.get("selected_symbols", [])):
        raise ValueError("previous resistance replay incomplete")
    for name, digest in manifest["archive_sha256"].items():
        if not (archive / name).exists() or sha(archive / name) != digest:
            raise ValueError(f"archive differs from resistance replay: {name}")
    for name, digest in manifest["outputs_sha256"].items():
        if sha(resistance / name) != digest:
            raise ValueError(f"resistance events changed: {name}")
    # Only computational sources must be bit-identical. The preceding study's
    # report/plot scripts were documented as presentation-only amendments.
    sources = ("research/stabil_resistance_replay.py", "domain_engines/stabil/stabil_support_lifecycle.py",
               "domain_engines/stabil/stabil_trend_engine.py", "domain_engines/stabil/candidate_regime.py",
               "domain_engines/stabil/runtime.py", "domain_engines/stabil/signals.py", "research/arsiv.py",
               "research/stabil_arrow_context_replay.py", "data/replay.py", "bist_calendar.py", "config.py")
    for name in sources:
        if sha(ROOT / name) != manifest["source_sha256"][name]:
            raise ValueError(f"computational source differs from resistance replay: {name}")
    return manifest


def normalize_four_hour(frame: pd.DataFrame, side: str) -> pd.DataFrame:
    """Expose real prices and orientation-free names, never synthetic prices as TL."""
    out = frame.copy()
    out["side"] = side
    if side == "SUPPORT":
        for name in ("line", "ceiling", "prior_close", "open", "close"):
            out[name] = REFLECTION-out[name]
        old_high = out["high"].copy()
        out["high"] = REFLECTION-out["low"]
        out["low"] = REFLECTION-old_high
    out["event"] = out["event"].map(FOUR_H_EVENTS)
    out["native_regime_proxy"] = out["native_regime_proxy"].map(REGIME_CANONICAL).fillna("UNKNOWN")
    out["contact"] = out["contact"].map(CONTACT_NAMES)
    for h in HORIZONS:
        out[f"first_1atr_{h}"] = out[f"first_1atr_{h}"].map(FIRST_NAMES)
        out[f"reaction_return_atr_{h}"] = -out[f"return_atr_{h}"]
        out[f"reaction_excursion_atr_{h}"] = out[f"down_excursion_atr_{h}"]
        out[f"adverse_excursion_atr_{h}"] = out[f"up_excursion_atr_{h}"]
        out[f"first_retest_{h}"] = out[f"first_retest_{h}"].map(RETEST_NAMES)
        out[f"first_follow_or_return_{h}"] = out[f"first_follow_or_return_{h}"].map(RACE_NAMES)
        out = out.drop(columns=[f"return_atr_{h}", f"down_excursion_atr_{h}", f"up_excursion_atr_{h}"])
    return out.rename(columns={"ceiling": "boundary", "event_body_atr": "body_toward_adverse_atr",
                               "close_above_ceiling": "close_beyond_boundary",
                               "gap_open_above_line": "gap_open_to_adverse_side",
                               "native_validity_mirrored": "native_validity",
                               "above_bars_before_return": "adverse_bars_before_return",
                               "above_max_depth_atr": "adverse_max_depth_atr",
                               **{f"future_close_above_line_{h}": f"future_close_adverse_{h}" for h in HORIZONS},
                               **{f"future_close_above_ceiling_{h}": f"future_close_beyond_boundary_{h}" for h in HORIZONS},
                               **{f"future_return_below_{h}": f"future_close_safe_{h}" for h in HORIZONS}})


def normalize_native(frame: pd.DataFrame, side: str) -> pd.DataFrame:
    out = frame.copy()
    out["side"] = side
    if side == "SUPPORT":
        for name in ("line", "ceiling", "event_close"):
            out[name] = REFLECTION-out[name]
    out["event"] = out["event"].map(NATIVE_NAMES)
    out["regime_proxy"] = out["regime_proxy"].map(REGIME_CANONICAL).fillna("UNKNOWN")
    for h in HORIZONS:
        out[f"first_1atr_{h}"] = out[f"first_1atr_{h}"].map(FIRST_NAMES)
        out[f"reaction_return_atr_{h}"] = -out[f"return_atr_{h}"]
        out[f"reaction_excursion_atr_{h}"] = out[f"down_excursion_atr_{h}"]
        out[f"adverse_excursion_atr_{h}"] = out[f"up_excursion_atr_{h}"]
        out = out.drop(columns=[f"return_atr_{h}", f"down_excursion_atr_{h}", f"up_excursion_atr_{h}"])
    return out.rename(columns={"ceiling": "boundary",
                               **{f"future_close_above_line_{h}": f"future_close_adverse_{h}" for h in HORIZONS},
                               **{f"future_close_above_ceiling_{h}": f"future_close_beyond_boundary_{h}" for h in HORIZONS},
                               **{f"future_return_below_{h}": f"future_close_safe_{h}" for h in HORIZONS}})


def run(archive: Path, resistance: Path, output: Path, symbols: list[str] | None, workers: int) -> dict[str, Any]:
    previous = validate_previous_inputs(archive, resistance)
    meta_by_symbol = {x["symbol"]: x for x in previous["symbols"]}
    selected = sorted(set(symbols)) if symbols else previous["selected_symbols"]
    if not selected or set(selected)-set(meta_by_symbol):
        raise ValueError("requested symbols not in previous resistance universe")
    results: list[dict[str, Any]] = []
    errors: dict[str, str] = {}
    if workers == 1:
        for symbol in selected:
            try:
                results.append(replay_support_symbol(symbol, str(archive), meta_by_symbol[symbol]))
            except Exception as exc:
                errors[symbol] = f"{type(exc).__name__}: {exc}"
            print(f"{symbol}: {len(results)}/{len(selected)} ok, {len(errors)} errors", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            pending = {pool.submit(replay_support_symbol, s, str(archive), meta_by_symbol[s]): s for s in selected}
            for future in as_completed(pending):
                symbol = pending[future]
                try:
                    results.append(future.result())
                except Exception as exc:
                    errors[symbol] = f"{type(exc).__name__}: {exc}"
                print(f"{symbol}: {len(results)}/{len(selected)} ok, {len(errors)} errors", flush=True)
    if errors:
        raise RuntimeError(f"support replay fail-closed, no report written: {errors}")
    results.sort(key=lambda r: r["symbol"])
    support = pd.DataFrame([row for x in results for row in x["events"]])
    native = pd.DataFrame([row for x in results for row in x["native_events"]])
    questions = pd.DataFrame([row for x in results for row in x["question_checkpoints"]])
    resistance_all = pd.read_csv(resistance / "events_4h.csv.gz", low_memory=False)
    resistance_main = resistance_all.loc[(resistance_all.model == "MIRROR_P4") & resistance_all.symbol.isin(selected)].copy()
    native_all = pd.read_csv(resistance / "native_daily_events.csv.gz", low_memory=False)
    native_resistance = native_all.loc[native_all.symbol.isin(selected)].copy()
    # Status depends only on the shared raw bars/quality/cutoff, not the chosen
    # line. Check all same-candle intersections across the two independently
    # generated sides before comparing outcomes.
    for h in HORIZONS:
        a = support[["symbol", "bar_index", f"status_{h}"]].drop_duplicates()
        b = resistance_main[["symbol", "bar_index", f"status_{h}"]].drop_duplicates()
        combined = a.merge(b, on=["symbol", "bar_index"], suffixes=("_support", "_resistance"))
        if not (combined[f"status_{h}_support"] == combined[f"status_{h}_resistance"]).all():
            raise AssertionError(f"different quality/censor status on shared 4h bars h={h}")
    output.mkdir(parents=True, exist_ok=True)
    normalized = pd.concat([normalize_four_hour(support, "SUPPORT"), normalize_four_hour(resistance_main, "RESISTANCE")], ignore_index=True)
    normalized = normalized.sort_values(["side", "symbol", "bar_index", "event"], kind="stable").reset_index(drop=True)
    normalized_native = pd.concat([normalize_native(native, "SUPPORT"), normalize_native(native_resistance, "RESISTANCE")], ignore_index=True)
    normalized_native = normalized_native.sort_values(["side", "symbol", "event_index", "sequence"], kind="stable").reset_index(drop=True)
    write_csv_gz(normalized, output / "events_4h.csv.gz")
    write_csv_gz(normalized_native, output / "events_native_daily.csv.gz")
    questions = questions.sort_values(["side", "symbol", "bar_index", "question"], kind="stable").reset_index(drop=True)
    write_csv_gz(questions, output / "legacy_like_checkpoints.csv.gz")
    manifest: dict[str, Any] = {
        "scope": "research-only, prior resistance outcomes were already observed; no independent blind holdout",
        "reflection_constant_for_measurement": REFLECTION,
        "selected_symbols": selected, "successful_symbols": len(results), "errors": errors,
        "events_4h": len(normalized), "events_native_daily": len(normalized_native),
        "legacy_like_checkpoint_rows": len(questions),
        "support_4h_events": len(support), "resistance_4h_events": len(resistance_main),
        "support_native_events": len(native), "resistance_native_events": len(native_resistance),
        "legacy_support_manifest_sha256": sha(LEGACY_MANIFEST),
        "prior_resistance_manifest_sha256": sha(resistance / "manifest.json"),
        "prior_resistance_event_hashes": previous["outputs_sha256"],
        "prior_input_files_verified": len(previous["archive_sha256"]),
        "source_sha256": {str(p.relative_to(ROOT)): sha(p) for p in (
            ROOT/"research/stabil_support_resistance_compare.py", ROOT/"research/stabil_support_resistance_report.py",
            ROOT/"research/stabil_support_resistance_verify.py", ROOT/"research/stabil_replay.py", ROOT/"research/stabil_bhv48.py",
            ROOT/"research/stabil_resistance_replay.py", ROOT/"research/stabil_resistance_report.py",
            ROOT/"test_stabil_support_resistance_compare.py", output/"PLAN.md") if p.exists()},
        "outputs_sha256": {name: sha(output/name) for name in ("events_4h.csv.gz", "events_native_daily.csv.gz", "legacy_like_checkpoints.csv.gz")},
        "environment": {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__,
                        "exchange_calendars": __import__("exchange_calendars").__version__},
        "symbols": [{k: v for k, v in r.items() if k not in {"events", "native_events", "question_checkpoints"}} for r in results],
    }
    (output/"manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=arsiv_koku())
    parser.add_argument("--resistance", type=Path, default=RESISTANCE_OUTPUT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--symbol", action="append")
    args = parser.parse_args()
    result = run(args.archive, args.resistance, args.output, args.symbol, max(1, args.workers))
    print(json.dumps({k: result[k] for k in ("successful_symbols", "errors", "events_4h", "events_native_daily")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
