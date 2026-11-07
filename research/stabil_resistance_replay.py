"""Research-only, causal resistance replay; never imported by the live bot.

See docs/arastirma/stabil_direnc_replay_2026_11_06/PLAN.md.  The primary
candidate is literally the native daily support lifecycle evaluated on negated
OHLC and transformed back; the 4h event rules are separate research measures.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import platform
from typing import Any

import numpy as np
import pandas as pd

from data import mum_kapanis_anlari
from bist_calendar import SessionStatus, bist_session_for
from data.replay import _gun_kapanis_damgalari
from domain_engines.stabil import (
    StabilTrendConfig,
    build_daily_support_observations,
    build_support_lifecycle_timeline,
    classify_candidate_support_regimes,
    prepare_causal_ohlcv,
)
from domain_engines.stabil.signals import _causal_atr14, _causal_vol_ratio20
from domain_engines.stabil.stabil_trend_engine import _atr, _confirmed_pivots
from research.arsiv import arsiv_koku, ham_frame, tf_frame
from research.stabil_arrow_context_replay import bad_bars, capture_cutoffs, closed_at_capture
from research.stabil_arrow_quality import audit_file
from research.stabil_replay import select_bist_equity_universe

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs/arastirma/stabil_direnc_replay_2026_11_06"
SPLIT = pd.Timestamp("2026-01-01", tz="Europe/Istanbul")
HORIZONS = (4, 8, 16)
MODEL_NAMES = (
    "MIRROR_P4", "P2", "P3", "P6", "P8", "BODY_P4", "P4_MAX3",
    "P4_MEDIAN3", "P4_DOUBLE", "P4_ACTIVE", "P4_CEILING", "ROLL10",
    "ROLL20", "ROLL55", "ROLL20_CLOSE", "EMA20", "SHIFT_UP", "SHIFT_DOWN",
    "P4_ZONE0", "P4_ZONE50",
)
ZONE_WIDTH = {"P4_ZONE0": 0.0, "P4_ZONE50": 0.50}
REGIME_NAMES = {
    "UNAVAILABLE": "UNAVAILABLE",
    "STEPPING_UP": "RESISTANCE_STEP_DOWN_PROXY",
    "STEPPING_DOWN": "RESISTANCE_STEP_UP_PROXY",
    "BREACHED_FIXED_SUPPORT": "RESISTANCE_BREACHED_FIXED_PROXY",
    "NEWLY_FLATTENED_AFTER_RISE": "FLAT_AFTER_RESISTANCE_DROP_PROXY",
    "HORIZONTAL_AFTER_DROP": "FLAT_AFTER_RESISTANCE_RISE_PROXY",
    "LONG_HORIZONTAL": "LONG_FLAT_PROXY",
    "HORIZONTAL_BASE": "FLAT_BASE_PROXY",
}
EVENT_NAMES = {
    "SUPPORT_CONFIRMED": "RESISTANCE_CONFIRMED",
    "SUPPORT_TESTED": "RESISTANCE_TESTED",
    "SUPPORT_HELD": "RESISTANCE_HELD",
    "SUPPORT_BREACHED": "RESISTANCE_BREACHED",
    "SUPPORT_FLOOR_BROKEN": "RESISTANCE_CEILING_BROKEN",
    "SUPPORT_RECLAIMED": "RESISTANCE_RETURN_BELOW",
    "SUPPORT_LOST": "RESISTANCE_ABANDONED_HIGHER",
    "SUPPORT_REBASED_HIGHER": "RESISTANCE_REBASED_LOWER",
    "SUPPORT_REBASED_LOWER": "RESISTANCE_REBASED_HIGHER",
}


def reverse_ohlc(frame: pd.DataFrame) -> pd.DataFrame:
    """Exact sign inversion: negative OHLC remains valid for the native engine."""
    out = frame.copy()
    out["open"] = -frame["open"].astype(float)
    out["high"] = -frame["low"].astype(float)
    out["low"] = -frame["high"].astype(float)
    out["close"] = -frame["close"].astype(float)
    return out


@dataclass
class Line:
    level: np.ndarray
    ceiling: np.ndarray
    origin: np.ndarray
    known: np.ndarray
    available: np.ndarray
    age: np.ndarray
    identity: list[Any]


def empty_line(n: int) -> Line:
    return Line(*(np.full(n, np.nan) for _ in range(6)), [None] * n)


def _set_pivot(line: Line, i: int, pivot: Any, available: int) -> None:
    line.level[i] = pivot.price
    line.ceiling[i] = pivot.price + 0.35 * pivot.atr_at_origin
    line.origin[i], line.known[i], line.available[i] = pivot.origin_index, pivot.known_index, available
    line.age[i] = i - available
    line.identity[i] = (int(pivot.origin_index), int(pivot.known_index), float(pivot.price))


def pivot_lines(frame: pd.DataFrame, span: int, *, body: bool = False) -> dict[str, Line]:
    """Independent positive-price candidate construction, using native pivot rules."""
    atr = _atr(frame)
    pivot_frame = frame.copy()
    if body:
        pivot_frame["high"] = np.maximum(frame["open"], frame["close"])
        pivot_frame["low"] = np.minimum(frame["open"], frame["close"])
    highs, lows = _confirmed_pivots(pivot_frame, span, atr)
    result = {k: empty_line(len(frame)) for k in ("latest", "max3", "median3", "double")}
    h = low = 0
    last_id: dict[str, Any] = {}
    since: dict[str, int] = {}
    for i in range(len(frame)):
        while h < len(highs) and highs[h].known_index <= i:
            h += 1
        while low < len(lows) and lows[low].known_index <= i:
            low += 1
        if h < 2 or low < 2:
            continue
        if not (highs[h-1].origin_index > highs[h-2].origin_index and
                lows[low-1].origin_index > lows[low-2].origin_index):
            continue
        newest = highs[h-1]
        choices: dict[str, Any] = {"latest": newest}
        if h >= 3:
            ordered = sorted(highs[h-3:h], key=lambda p: (p.price, p.origin_index))
            choices.update(max3=ordered[-1], median3=ordered[1])
        if abs(newest.price - highs[h-2].price) <= .5 * newest.atr_at_origin:
            choices["double"] = newest
        for key in result:
            pivot = choices.get(key)
            if pivot is None:
                last_id[key] = None
                continue
            identity = (pivot.origin_index, pivot.known_index, pivot.price)
            if identity != last_id.get(key):
                since[key] = i
                last_id[key] = identity
            _set_pivot(result[key], i, pivot, since[key])
    return result


def native_mirror(frame: pd.DataFrame) -> tuple[Line, tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
    """Run the actual native builder and lifecycle; do not reimplement their logic."""
    obs = build_daily_support_observations(reverse_ohlc(frame), config=StabilTrendConfig())
    timeline = build_support_lifecycle_timeline(obs, include_prefix_events=False)
    regimes = classify_candidate_support_regimes(timeline)
    line = empty_line(len(frame))
    time_index = {pd.Timestamp(t).value: i for i, t in enumerate(frame["timestamp"])}
    for i, item in enumerate(obs):
        if item.support_level is None:
            continue
        line.level[i] = -float(item.support_level)
        line.ceiling[i] = -float(item.support_floor)
        line.origin[i] = item.support_origin_index
        line.known[i] = item.support_confirmed_index
        line.available[i] = time_index[pd.Timestamp(item.support_available_at).value]
        line.age[i] = i - line.available[i]
        line.identity[i] = (int(item.support_origin_index), int(item.support_confirmed_index), -float(item.support_level))
    return line, obs, timeline, regimes


def _copy_line(line: Line) -> Line:
    return Line(line.level.copy(), line.ceiling.copy(), line.origin.copy(), line.known.copy(),
                line.available.copy(), line.age.copy(), list(line.identity))


def rolling_line(frame: pd.DataFrame, window: int, column: str) -> Line:
    out = empty_line(len(frame))
    values = frame[column].to_numpy(dtype=float)
    atr = _atr(frame)
    last_origin = None
    available = 0
    for i in range(window - 1, len(frame)):
        sample = values[i-window+1:i+1]
        # Pick the most recent maximum on equal values; no future rows involved.
        origin = i - int(np.argmax(sample[::-1]))
        if atr[origin] is None or float(atr[origin]) <= 0:
            continue
        if origin != last_origin:
            available, last_origin = i, origin
        out.level[i] = values[origin]
        out.ceiling[i] = values[origin] + .35 * float(atr[origin])
        out.origin[i], out.known[i], out.available[i], out.age[i] = origin, i, available, i-available
        out.identity[i] = (origin, float(values[origin]))
    return out


def ema_line(frame: pd.DataFrame, window: int = 20) -> Line:
    out = empty_line(len(frame))
    values = frame["close"].astype(float).ewm(span=window, adjust=False, min_periods=window).mean().to_numpy()
    atr = _atr(frame)
    for i, value in enumerate(values):
        if math.isfinite(value) and atr[i] is not None and float(atr[i]) > 0:
            out.level[i], out.ceiling[i] = value, value + .35*float(atr[i])
            out.origin[i] = out.known[i] = out.available[i] = i
            out.age[i] = 0
            out.identity[i] = ("ema", i)
    return out


def build_models(frame: pd.DataFrame) -> tuple[dict[str, Line], tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
    base, obs, timeline, regimes = native_mirror(frame)
    p4 = pivot_lines(frame, 4)
    # A separately implemented positive-price high-pivot mirror must coincide
    # at *every* daily prefix, including readiness/available time.
    for attr in ("level", "ceiling", "origin", "known", "available", "age"):
        if not np.allclose(getattr(base, attr), getattr(p4["latest"], attr), equal_nan=True, rtol=1e-10, atol=1e-10):
            raise AssertionError(f"native mirror vs independent high-pivot mismatch: {attr}")
    models: dict[str, Line] = {"MIRROR_P4": base}
    for span in (2, 3, 6, 8):
        models[f"P{span}"] = pivot_lines(frame, span)["latest"]
    models["BODY_P4"] = pivot_lines(frame, 4, body=True)["latest"]
    models.update(P4_MAX3=p4["max3"], P4_MEDIAN3=p4["median3"], P4_DOUBLE=p4["double"])
    active = _copy_line(base)
    for i, snap in enumerate(timeline):
        if str(snap.validity) != "ACTIVE":
            active.level[i] = active.ceiling[i] = np.nan
            active.identity[i] = None
    models["P4_ACTIVE"] = active
    ceiling = _copy_line(base)
    ceiling.level = base.ceiling.copy()
    ceiling.ceiling = base.ceiling + (base.ceiling - base.level)
    models["P4_CEILING"] = ceiling
    for window in (10, 20, 55):
        models[f"ROLL{window}"] = rolling_line(frame, window, "high")
    models["ROLL20_CLOSE"] = rolling_line(frame, 20, "close")
    models["EMA20"] = ema_line(frame)
    for key, sign in (("SHIFT_UP", 1), ("SHIFT_DOWN", -1)):
        alt = _copy_line(base)
        delta = sign * .5 * (base.ceiling - base.level) / .35
        alt.level = base.level + delta
        alt.ceiling = base.ceiling + delta
        models[key] = alt
    models["P4_ZONE0"] = base
    models["P4_ZONE50"] = base
    assert tuple(models) == MODEL_NAMES
    return models, obs, timeline, regimes


def project_daily_at_bar_open(daily_times: pd.DatetimeIndex, opens: pd.DatetimeIndex) -> np.ndarray:
    """Project only levels available by the opening instant of each 4h bar."""
    return np.searchsorted(daily_times.asi8, opens.asi8, side="right") - 1


def intraday_completeness(hourly: pd.DataFrame, h4: pd.DataFrame, daily: pd.DataFrame,
                          capture: pd.Timestamp) -> tuple[np.ndarray, np.ndarray, dict[str, int]]:
    """Detect missing constituents and whole 4h buckets on observed daily sessions.

    This cannot detect a trading day missing from BOTH the daily and intraday
    sources or a mistaken/unscheduled calendar closure.
    """
    raw = set(hourly.index.asi8.tolist())
    h4_open = h4.index.tz_convert("Europe/Istanbul")
    closes = mum_kapanis_anlari(h4_open, "4h")
    incomplete = np.zeros(len(h4), dtype=bool)
    for i, (start, end) in enumerate(zip(h4_open, closes)):
        t = start
        while t < end:
            if t.value not in raw:
                incomplete[i] = True
                break
            t += pd.Timedelta(hours=1)
    date_set = set(daily.index.tz_convert("Europe/Istanbul").date) | set(h4_open.date)
    dates = sorted(d for d in date_set if h4_open[0].date() <= d <= h4_open[-1].date())
    expected: list[int] = []
    for day in dates:
        midnight = pd.Timestamp(day, tz="Europe/Istanbul")
        first = midnight + pd.Timedelta(hours=9, minutes=30)
        session_end = _gun_kapanis_damgalari(pd.DatetimeIndex([first]), gunluk=False)[0]
        session = bist_session_for(day)
        if session.status is SessionStatus.TRADING and session.is_half_day:
            calendar_end = midnight + pd.Timedelta(hours=session.close_time.hour, minutes=session.close_time.minute)
            session_end = min(session_end, calendar_end)
        for offset in (0, 4, 8):
            start = first + pd.Timedelta(hours=offset)
            if start >= session_end or start < h4_open[0] or start > h4_open[-1]:
                continue
            if mum_kapanis_anlari(pd.DatetimeIndex([start]), "4h")[0] <= capture:
                expected.append(start.value)
    expected.sort()
    expected_pos = {x: i for i, x in enumerate(expected)}
    gaps = np.zeros(len(h4), dtype=bool)
    missing_entire = 0
    for i in range(1, len(h4)):
        a = expected_pos.get(h4_open[i-1].value)
        b = expected_pos.get(h4_open[i].value)
        if a is None or b is None:
            gaps[i] = True
        elif b > a + 1:
            gaps[i] = True
            missing_entire += b-a-1
    return incomplete, gaps, {"incomplete_h4_buckets": int(incomplete.sum()),
                              "missing_whole_h4_buckets": missing_entire}


def first_hit(high: np.ndarray, low: np.ndarray, entry: float, atr: float) -> str:
    """±1 ATR first-hit race; both within one OHLC bar remains ambiguous."""
    for h, lo in zip(high, low):
        up, down = h >= entry + atr, lo <= entry - atr
        if up and down:
            return "AMBIGUOUS_SAME_BAR"
        if up:
            return "UP_FIRST"
        if down:
            return "DOWN_FIRST"
    return "NEITHER"


class Forward:
    def __init__(self, frame: pd.DataFrame, atr: np.ndarray, bad: np.ndarray, gaps: np.ndarray,
                 structural_bad: np.ndarray | None = None):
        self.frame = frame
        self.close = frame["close"].to_numpy(dtype=float)
        self.high = frame["high"].to_numpy(dtype=float)
        self.low = frame["low"].to_numpy(dtype=float)
        self.open = frame["open"].to_numpy(dtype=float)
        self.atr = atr
        self.bad = bad
        self.gaps = gaps
        self.structural_bad = structural_bad if structural_bad is not None else np.zeros(len(frame), dtype=bool)
        self.times = pd.DatetimeIndex(frame["timestamp"])
        self.cache: dict[int, dict[str, Any]] = {}

    def at(self, i: int) -> dict[str, Any]:
        if i in self.cache:
            return self.cache[i]
        out: dict[str, Any] = {}
        for h in HORIZONS:
            status = "VALID"
            if i < 20 or not math.isfinite(self.atr[i]) or self.atr[i] <= 0:
                status = "NO_HISTORY_OR_ATR"
            elif self.structural_bad[i]:
                status = "BAD_DAILY_SOURCE_HISTORY"
            elif self.bad[i-19:i+1].any() or self.gaps[i-18:i+1].any():
                status = "BAD_HISTORY_OR_MISSING"
            elif i+h >= len(self.close):
                status = "RIGHT_CENSORED"
            elif self.bad[i+1:i+h+1].any() or self.gaps[i+1:i+h+1].any():
                status = "BAD_FUTURE_OR_MISSING"
            elif self.structural_bad[i+h]:
                status = "BAD_DAILY_SOURCE_FUTURE"
            elif self.times[i] < SPLIT <= self.times[i+h]:
                status = "CROSS_SPLIT"
            out[f"status_{h}"] = status
            out[f"right_censored_{h}"] = i+h >= len(self.close)
            out[f"cross_split_{h}"] = bool(i+h < len(self.close) and self.times[i] < SPLIT <= self.times[i+h])
            out[f"return_atr_{h}"] = out[f"up_excursion_atr_{h}"] = out[f"down_excursion_atr_{h}"] = None
            out[f"first_1atr_{h}"] = None
            if status == "VALID":
                hi, lo = self.high[i+1:i+h+1], self.low[i+1:i+h+1]
                entry, atr = self.close[i], self.atr[i]
                out[f"return_atr_{h}"] = (self.close[i+h] - entry) / atr
                out[f"up_excursion_atr_{h}"] = max(0.0, (float(np.max(hi)) - entry) / atr)
                out[f"down_excursion_atr_{h}"] = max(0.0, (entry - float(np.min(lo))) / atr)
                out[f"first_1atr_{h}"] = first_hit(hi, lo, entry, atr)
        self.cache[i] = out
        return out

    def line_outcomes(self, i: int, level: float, ceiling: float, kind: str) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for h in HORIZONS:
            for k in ("future_close_above_line", "future_close_above_ceiling", "future_return_below",
                      "first_retest", "first_retest_bar"):
                out[f"{k}_{h}"] = None
            if self.at(i)[f"status_{h}"] != "VALID":
                continue
            cs = self.close[i+1:i+h+1]
            out[f"future_close_above_line_{h}"] = bool(np.any(cs > level))
            out[f"future_close_above_ceiling_{h}"] = bool(np.any(cs > ceiling))
            out[f"future_return_below_{h}"] = bool(np.any(cs <= level))
            if kind == "BREAK_UP":
                outcome, first = "NO_RETEST", None
                for j in range(i+1, i+h+1):
                    if self.low[j] <= level:
                        first = j-i
                        if self.open[j] <= level:
                            outcome = "GAP_OR_OPEN_AT_BELOW_RECLAIM" if self.close[j] > level else "GAP_OR_OPEN_AT_BELOW_FAIL"
                        else:
                            outcome = "TOUCH_CLOSE_ABOVE" if self.close[j] > level else "TOUCH_CLOSE_AT_OR_BELOW"
                        break
                out[f"first_retest_{h}"], out[f"first_retest_bar_{h}"] = outcome, first
        return out



def classify_contact(high: float, low: float, close: float, level: float) -> str:
    """Keep a gap entirely above the line distinct from an actual OHLC touch."""
    if high < level:
        return "NEAR_ONLY"
    if low > level:
        return "GAP_ABOVE_NO_TOUCH"
    if close > level:
        return "TOUCH_CLOSE_ABOVE"
    return "WICK_TOUCH_CLOSE_AT_OR_BELOW"


def crossing_cause(previous_price: float, price: float, old_line: float, new_line: float) -> tuple[str, str] | None:
    """Decompose a location change into counterfactual price/line contributions."""
    if previous_price <= old_line and price > new_line:
        direction = "UP"
        price_only, line_only = price > old_line, previous_price > new_line
    elif previous_price > old_line and price <= new_line:
        direction = "DOWN"
        price_only, line_only = price <= old_line, previous_price <= new_line
    else:
        return None
    if price_only and line_only:
        cause = "EITHER_SUFFICIENT"
    elif price_only:
        cause = "PRICE_ONLY"
    elif line_only:
        cause = "LINE_ONLY"
    else:
        cause = "BOTH_REQUIRED"
    return direction, cause


def _period(t: pd.Timestamp) -> str:
    return "PRE_2026" if t < SPLIT else "Y2026"


def _float(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def replay_4h(symbol: str, frame: pd.DataFrame, daily: pd.DataFrame, starts: pd.DatetimeIndex,
              models: dict[str, Line], timeline: tuple[Any, ...], regimes: tuple[Any, ...],
              bad: np.ndarray, gaps: np.ndarray, daily_bad: np.ndarray | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    o, h, lo, c, vol = (frame[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close", "volume"))
    atr = _causal_atr14(h, lo, c)
    vr = _causal_vol_ratio20(vol)
    loc = project_daily_at_bar_open(pd.DatetimeIndex(daily["timestamp"]), starts)
    structural_bad = np.zeros(len(frame), dtype=bool)
    if daily_bad is not None:
        cumulative_bad = np.cumsum(daily_bad) > 0
        valid_loc = loc >= 0
        structural_bad[valid_loc] = cumulative_bad[loc[valid_loc]]
    fwd = Forward(frame, atr, bad, gaps, structural_bad)
    times = pd.DatetimeIndex(frame["timestamp"])
    periods = [_period(t) for t in times]
    history_ok = np.zeros(len(frame), dtype=bool)
    for j in range(20, len(frame)):
        history_ok[j] = not structural_bad[j] and not (bad[j-19:j+1].any() or gaps[j-18:j+1].any())
    rows: list[dict[str, Any]] = []
    coverage: dict[str, Any] = {"_eligible": {p: int(sum(ok and period == p for ok, period in zip(history_ok, periods)))
                                              for p in ("PRE_2026", "Y2026")}}
    for name, model in models.items():
        zone = ZONE_WIDTH.get(name, .25)
        last_identity: Any = None
        touch_unknown, touch_count = True, 0
        # A breach episode begins only when the crossing itself is observed.
        episode: dict[str, Any] | None = None
        last_nonoverlap: dict[str, int] = {}
        counts = Counter()
        for i in range(1, len(frame)):
            di = int(loc[i])
            if di < 0:
                last_identity, episode, touch_unknown = None, None, True
                continue
            level, ceiling = _float(model.level[di]), _float(model.ceiling[di])
            if level is None or ceiling is None or level <= 0:
                last_identity, episode, touch_unknown = None, None, True
                continue
            ident = model.identity[di]
            if ident != last_identity:
                # If already known at the beginning of the 4h archive, earlier
                # touches/breaks are left-censored. New identities are observable.
                touch_unknown = i == 1 and int(loc[0]) >= 0 and model.identity[int(loc[0])] == ident
                touch_count = 0
                episode = None
                last_identity = ident
            if bad[i] or gaps[i]:
                touch_unknown, episode = True, None
            if history_ok[i]:
                counts["eligible_bars"] += 1
                counts[f"eligible_{periods[i]}"] += 1
            else:
                counts["known_but_history_bad_or_warmup"] += 1
            pa = _float(atr[i-1])
            if pa is None or pa <= 0:
                continue
            dist = (level-c[i-1])/pa
            if 0 <= dist <= 1.5:
                counts["below_within_1_5_atr"] += 1
            test = 0 <= dist <= 1.5 and h[i-1] < level-zone*pa and h[i] >= level-zone*pa
            up = c[i-1] <= level and c[i] > level
            down = c[i-1] > level and c[i] <= level
            kinds = []
            if test:
                touch_count += 1
                kinds.append("TEST")
            if up:
                kinds.append("BREAK_UP")
            if down:
                kinds.append("RETURN_DOWN")
            # Research proxy for the user's departure -> line-follow / price-return path.
            # The same previously known level and previous ATR define both sides.
            depart = name == "MIRROR_P4" and c[i-1] <= level and c[i-1] > level-1.5*pa and c[i] <= level-1.5*pa
            if depart:
                kinds.append("DEPART_BELOW")
            cause = None
            prev_di = int(loc[i-1])
            if name == "MIRROR_P4" and prev_di >= 0:
                old_level = _float(model.level[prev_di])
                if old_level is not None and old_level > 0:
                    cause = crossing_cause(c[i-1], c[i], old_level, level)
                    if cause:
                        kinds.append("STATE_CROSS_" + cause[0])
            episode_before = episode
            if up and _float(atr[i]) is not None and atr[i] > 0 and not bad[i]:
                episode = {"break_index": i, "bars_above": 1, "max_high": max(level, h[i]), "atr": atr[i]}
            elif c[i] > level:
                if episode is not None:
                    episode["bars_above"] += 1
                    episode["max_high"] = max(episode["max_high"], h[i])
            elif not down:
                episode = None
            if not kinds:
                continue
            level_age = _float(model.age[di])
            close_ts = times[i]
            prior4 = (c[i-1] - c[i-5]) / pa if i >= 5 else None
            for kind in kinds:
                counts[kind] += 1
                take_nonoverlap = i - last_nonoverlap.get(kind, -10**9) >= 8
                if take_nonoverlap:
                    last_nonoverlap[kind] = i
                contact = classify_contact(h[i], lo[i], c[i], level)
                row: dict[str, Any] = {
                    "symbol": symbol, "model": name, "event": kind, "bar_index": i,
                    "event_open_time": starts[i].isoformat(), "event_close_time": close_ts.isoformat(),
                    "period": _period(close_ts), "quarter": f"{close_ts.year}Q{(close_ts.month-1)//3+1}",
                    "session_close": close_ts.strftime("%H:%M"),
                    "line": level, "ceiling": ceiling, "daily_asof": pd.Timestamp(daily.iloc[di]["timestamp"]).isoformat(),
                    "origin_time": pd.Timestamp(daily.iloc[int(model.origin[di])]["timestamp"]).isoformat() if np.isfinite(model.origin[di]) else None,
                    "confirmed_time": pd.Timestamp(daily.iloc[int(model.known[di])]["timestamp"]).isoformat() if np.isfinite(model.known[di]) else None,
                    "first_available_time": pd.Timestamp(daily.iloc[int(model.available[di])]["timestamp"]).isoformat() if np.isfinite(model.available[di]) else None,
                    "known_age_daily_bars": int(level_age) if level_age is not None else None,
                    "native_regime_proxy": REGIME_NAMES.get(regimes[di].regime.value, "UNKNOWN") if name in {"MIRROR_P4", "P4_ZONE0", "P4_ZONE50"} else "NOT_APPLICABLE",
                    "native_validity_mirrored": str(timeline[di].validity) if name in {"MIRROR_P4", "P4_ZONE0", "P4_ZONE50"} else "NOT_APPLICABLE",
                    "prior_close": c[i-1], "open": o[i], "high": h[i], "low": lo[i], "close": c[i],
                    "atr_before": pa, "atr_event": _float(atr[i]), "gap_to_line_atr": dist,
                    "prior_4bar_move_atr": prior4, "event_body_atr": (c[i]-o[i])/atr[i] if atr[i] > 0 else None,
                    "volume_ratio_prior20": _float(vr[i]), "contact": contact,
                    "close_above_ceiling": bool(c[i] > ceiling), "gap_open_above_line": bool(o[i] > level and c[i-1] <= level),
                    "test_ordinal": None if touch_unknown else touch_count,
                    "history_of_tests": "UNKNOWN" if touch_unknown else "OBSERVED_SINCE_IDENTITY_AVAILABLE",
                    "nonoverlap_8": take_nonoverlap,
                    "cross_cause": cause[1] if kind.startswith("STATE_CROSS_") and cause else None,
                    "episode_known": bool(episode_before is not None) if kind == "RETURN_DOWN" else None,
                    "above_bars_before_return": episode_before["bars_above"] if kind == "RETURN_DOWN" and episode_before is not None else None,
                    "above_max_depth_atr": (episode_before["max_high"]-level)/episode_before["atr"] if kind == "RETURN_DOWN" and episode_before is not None else None,
                    "break_bar_index": episode_before["break_index"] if kind == "RETURN_DOWN" and episode_before is not None else None,
                }
                row.update(fwd.at(i))
                if kind in {"TEST", "BREAK_UP", "RETURN_DOWN"}:
                    row.update(fwd.line_outcomes(i, level, ceiling, kind))
                if kind == "DEPART_BELOW":
                    for horizon in HORIZONS:
                        race = None
                        if row[f"status_{horizon}"] == "VALID":
                            race = "NEITHER"
                            for j in range(i+1, i+horizon+1):
                                future_di = int(loc[j])
                                future_level = _float(model.level[future_di]) if future_di >= 0 else None
                                if future_level is None:
                                    race = "LEVEL_UNAVAILABLE"
                                    break
                                follows = future_level < level - .01
                                returns = c[j] >= level
                                if follows and returns:
                                    race = "AMBIGUOUS_SAME_BAR"
                                    break
                                if follows or returns:
                                    race = "LEVEL_FOLLOWS_DOWN_FIRST" if follows else "PRICE_RETURNS_FIRST"
                                    break
                        row[f"first_follow_or_return_{horizon}"] = race
                rows.append(row)
            if down:
                episode = None
        coverage[name] = dict(counts)
    return rows, coverage


def replay_native_daily(symbol: str, daily: pd.DataFrame, timeline: tuple[Any, ...],
                        regimes: tuple[Any, ...], bad: np.ndarray) -> list[dict[str, Any]]:
    if not timeline:
        return []
    atr = np.asarray([np.nan if x is None else x for x in _atr(daily)], dtype=float)
    fwd = Forward(daily, atr, bad, np.zeros(len(daily), dtype=bool), np.cumsum(bad) > 0)
    by_time = {pd.Timestamp(t).value: i for i, t in enumerate(daily["timestamp"])}
    result = []
    for ev in timeline[-1].events:
        i = by_time[pd.Timestamp(ev.event_time).value]
        level = None if ev.support_level is None else -float(ev.support_level)
        ceiling = None if ev.support_floor is None else -float(ev.support_floor)
        t = pd.Timestamp(ev.event_time)
        row = {"symbol": symbol, "event": EVENT_NAMES[ev.event_type.value], "event_time": t.isoformat(),
               "period": _period(t), "quarter": f"{t.year}Q{(t.month-1)//3+1}",
               "event_index": i, "sequence": ev.sequence, "line": level, "ceiling": ceiling,
               "event_close": -float(ev.price), "atr_daily": _float(ev.atr),
               "pivot_origin_time": pd.Timestamp(ev.origin_at).isoformat() if ev.origin_at is not None else None,
               "pivot_confirmed_time": pd.Timestamp(ev.confirmed_at).isoformat() if ev.confirmed_at is not None else None,
               "event_known_time": pd.Timestamp(ev.available_at).isoformat() if ev.available_at is not None else None,
               "known_age_daily_bars": ev.bars_since_support,
               "regime_proxy": REGIME_NAMES.get(regimes[i].regime.value, "UNKNOWN")}
        row.update(fwd.at(i))
        if level is not None and ceiling is not None:
            row.update(fwd.line_outcomes(i, level, ceiling, "NATIVE"))
        result.append(row)
    return result


def replay_symbol(symbol: str, archive: str | None = None) -> dict[str, Any]:
    root = arsiv_koku(archive)
    audits = {}
    for tf in ("1h", "1d"):
        stats = audit_file(root / f"{symbol}_{tf}.csv.gz")
        audits[tf] = stats
        invalid = {k: v for k, v in stats.items() if v and k not in {"rows", "zero_volume_rows"}}
        if invalid:
            raise ValueError(f"raw quality failure {symbol} {tf}: {invalid}")
    capture = capture_cutoffs(symbol, str(root))
    daily_all = tf_frame(symbol, "1d", root)
    h4_all = tf_frame(symbol, "4h", root)
    hourly = closed_at_capture(ham_frame(symbol, "1h", root), "1h", capture["1h"])
    daily_raw = closed_at_capture(daily_all, "1d", capture["1d"])
    h4_raw = closed_at_capture(h4_all, "4h", capture["1h"])
    if daily_raw.empty or h4_raw.empty:
        raise ValueError("no closed daily or 4h archive bars")
    daily, daily_error = prepare_causal_ohlcv(daily_raw, symbol=symbol, timeframe="1d")
    h4, h4_error = prepare_causal_ohlcv(h4_raw, symbol=symbol, timeframe="4h")
    if daily_error or h4_error or len(daily) != len(daily_raw) or len(h4) != len(h4_raw):
        raise ValueError(f"preparation lost rows or failed: {daily_error}, {h4_error}")
    incomplete, gaps, completeness = intraday_completeness(hourly, h4_raw, daily_raw, capture["1h"])
    daily_bad = bad_bars(daily)
    suspect_dates = set(pd.DatetimeIndex(daily.timestamp)[daily_bad].tz_convert("Europe/Istanbul").date)
    h4_on_bad_daily_date = np.asarray([t.date() in suspect_dates for t in pd.DatetimeIndex(h4.timestamp)], dtype=bool)
    h4_bad = bad_bars(h4) | incomplete | h4_on_bad_daily_date
    models, obs, timeline, regimes = build_models(daily)
    events, coverage = replay_4h(symbol, h4, daily, h4_raw.index, models, timeline, regimes, h4_bad, gaps, daily_bad)
    native_events = replay_native_daily(symbol, daily, timeline, regimes, daily_bad)
    meta = {"symbol": symbol, "daily_bars": len(daily), "h4_bars": len(h4),
            "first_h4_close": str(h4.iloc[0]["timestamp"]), "last_h4_close": str(h4.iloc[-1]["timestamp"]),
            "first_daily_close": str(daily.iloc[0]["timestamp"]), "last_daily_close": str(daily.iloc[-1]["timestamp"]),
            "capture_start_bound_utc": {k: str(v) for k, v in capture.items()},
            "excluded_unclosed_daily": len(daily_all)-len(daily_raw), "excluded_unclosed_h4": len(h4_all)-len(h4_raw),
            "bad_daily_bars_including_30pct_jump": int(daily_bad.sum()),
            "bad_h4_bars_including_incomplete_and_30pct_jump": int(h4_bad.sum()),
            "h4_bars_on_suspect_daily_date": int(h4_on_bad_daily_date.sum()),
            "raw_audit": audits, **completeness, "coverage": coverage}
    return {"meta": meta, "events": events, "native_events": native_events}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv_gz(frame: pd.DataFrame, path: Path) -> None:
    # Deterministic gzip header, sorted rows and stable float format.
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as text:
                frame.to_csv(text, index=False, float_format="%.10g", lineterminator="\n")


def run(archive: Path, output: Path, symbols: list[str], workers: int) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    if not symbols:
        raise ValueError("no equity symbols selected")
    results: list[dict[str, Any]] = []
    errors: dict[str, str] = {}
    if workers == 1:
        for symbol in symbols:
            try:
                results.append(replay_symbol(symbol, str(archive)))
            except Exception as exc:
                errors[symbol] = f"{type(exc).__name__}: {exc}"
            print(f"{symbol}: {len(results)}/{len(symbols)} ok, {len(errors)} errors", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(replay_symbol, symbol, str(archive)): symbol for symbol in symbols}
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    results.append(future.result())
                except Exception as exc:
                    errors[symbol] = f"{type(exc).__name__}: {exc}"
                print(f"{symbol}: {len(results)}/{len(symbols)} ok, {len(errors)} errors", flush=True)
    if not results:
        raise RuntimeError(f"no symbols succeeded: {errors}")
    results.sort(key=lambda r: r["meta"]["symbol"])
    events = pd.DataFrame([row for result in results for row in result["events"]])
    native = pd.DataFrame([row for result in results for row in result["native_events"]])
    if len(events):
        events = events.sort_values(["symbol", "model", "bar_index", "event"], kind="stable").reset_index(drop=True)
    if len(native):
        native = native.sort_values(["symbol", "event_index", "sequence"], kind="stable").reset_index(drop=True)
    write_csv_gz(events, output / "events_4h.csv.gz")
    write_csv_gz(native, output / "native_daily_events.csv.gz")
    source_paths = ["research/stabil_resistance_replay.py", "research/stabil_resistance_report.py",
                    "research/stabil_resistance_examples.py",
                    "domain_engines/stabil/stabil_support_lifecycle.py", "domain_engines/stabil/stabil_trend_engine.py",
                    "domain_engines/stabil/candidate_regime.py", "domain_engines/stabil/runtime.py",
                    "domain_engines/stabil/signals.py", "research/arsiv.py", "research/stabil_replay.py", "research/stabil_arrow_context_replay.py",
                    "research/stabil_arrow_quality.py", "data/replay.py", "bist_calendar.py", "config.py",
                    "test_stabil_resistance_replay.py", "requirements.txt", "requirements-dev.txt",
                    "docs/arastirma/stabil_direnc_replay_2026_11_06/PLAN.md"]
    manifest = {"scope": "research-only; daily native and session-aligned 4h; no live policy changes",
                "split_istanbul": SPLIT.isoformat(), "models": MODEL_NAMES, "horizons": HORIZONS,
                "selected_symbols": symbols, "successful_symbols": len(results), "errors": errors,
                "events_4h": len(events), "events_native_daily": len(native),
                "environment": {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__,
                                "exchange_calendars": __import__("exchange_calendars").__version__,
                                "pytz": __import__("pytz").__version__},
                "source_sha256": {p: sha(ROOT / p) for p in source_paths if (ROOT / p).exists()},
                "archive_sha256": {p.name: sha(p) for p in [archive / "manifest.json"] +
                                   [archive / f"{s}_{tf}.csv.gz" for s in symbols for tf in ("1h", "1d")] if p.exists()},
                "outputs_sha256": {"events_4h.csv.gz": sha(output / "events_4h.csv.gz"),
                                   "native_daily_events.csv.gz": sha(output / "native_daily_events.csv.gz")},
                "symbols": [r["meta"] for r in results]}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=arsiv_koku())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--symbol", action="append", help="repeat for a focused run")
    args = parser.parse_args()
    symbols = sorted(set(args.symbol)) if args.symbol else select_bist_equity_universe(10000, kok=args.archive)
    result = run(args.archive, args.output, symbols, max(1, args.workers))
    print(json.dumps({k: result[k] for k in ("successful_symbols", "errors", "events_4h", "events_native_daily")}, ensure_ascii=False))
    if result["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
