"""Causal multi-timeframe runtime adapter and bar projection for Stabil.

Preserves two strict boundaries:
1. `StabilTrendEngine` and `StabilSupportLifecycleEngine` run independently with
   full native snapshots, events, and history preserved. Ready daily support is
   never hidden behind trend warm-up.
2. Candle availability uses actual session close timestamps (`close_time <= cutoff`),
   completed calendar weeks derived from closed daily candles, and fail-closed
   foreign-market handling when certified close timestamps are absent.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
import math
from typing import Any, Mapping, Sequence

import pandas as pd

from .stabil_support_lifecycle import (
    DailySupportObservation,
    StabilSupportLifecycleEngine,
    StabilSupportLifecycleSnapshot,
    SupportDynamics,
    SupportProgression,
    SupportValidity,
    build_daily_support_observations,
    build_support_lifecycle_timeline,
)
from .stabil_trend_engine import (
    DailyTrendSnapshot,
    H4EvidenceStatus,
    H4TrendSnapshot,
    StabilTrendConfig,
    StabilTrendContext,
    StabilTrendEngine,
    WeeklyTrendSnapshot,
    build_daily_raw_trend_timeline,
    build_h4_trend_timeline,
    build_weekly_trend_timeline,
    compose_trend_context,
)


class StabilRoleStatus(StrEnum):
    READY = "READY"
    WARMUP = "WARMUP"
    UNAVAILABLE = "UNAVAILABLE"
    DATA_ERROR = "DATA_ERROR"


@dataclass(frozen=True, slots=True)
class StabilRoleReadiness:
    role: str
    status: StabilRoleStatus
    reason: str | None = None
    bar_count: int = 0
    as_of: Any | None = None


@dataclass(frozen=True, slots=True)
class SupportBarPoint:
    bar_index: int
    bar_close_time: Any
    daily_as_of: Any | None
    support_level: float | None
    validity: SupportValidity
    dynamics: SupportDynamics
    progression: SupportProgression
    color_role: str | None  # "above" (green) | "below" (red) | None


@dataclass(frozen=True, slots=True)
class StabilDomainOutput:
    symbol: str
    timeframe: str
    as_of_close: Any | None
    support_snapshot: StabilSupportLifecycleSnapshot
    support_observations: tuple[DailySupportObservation, ...]
    support_timeline: tuple[StabilSupportLifecycleSnapshot, ...]
    trend_context: StabilTrendContext
    role_readiness: Mapping[str, StabilRoleReadiness]
    bar_projection: tuple[SupportBarPoint, ...]
    latest_close: float | None
    latest_support_relation: str | None  # "destek üstünde" | "destek altında" | "destekte" | None


def _normalize_symbol(symbol: str) -> str:
    return str(symbol or "").strip().upper().replace(".IS", "")


def is_foreign_or_macro_symbol(symbol: str) -> bool:
    """Return True when BIST session close assumptions must NOT be applied."""
    try:
        import config

        clean = _normalize_symbol(symbol)
        return config.sembol_turu(clean) == "makro"
    except Exception:
        return False


def _to_istanbul_timestamp(value: Any) -> pd.Timestamp | None:
    if value is None:
        return None
    from config import ISTANBUL_TZ

    ts = pd.Timestamp(value)
    if pd.isna(ts):
        return None
    if ts.tzinfo is None:
        return ts.tz_localize(ISTANBUL_TZ)
    return ts.tz_convert(ISTANBUL_TZ)


def describe_price_vs_support(
    price: float | None,
    support_level: float | None,
    *,
    min_tick: float = 0.01,
) -> str | None:
    """Compare close price against causally known daily support without opinion."""
    if price is None or support_level is None:
        return None
    try:
        p = float(price)
        s = float(support_level)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(p) and math.isfinite(s)):
        return None
    tol = max(float(min_tick) * 0.5, 1e-9)
    diff = p - s
    if abs(diff) <= tol:
        return "destekte"
    return "destek üstünde" if diff > 0 else "destek altında"


def format_stabil_card_line(
    price: float | None,
    support_level: float | None,
    *,
    min_tick: float = 0.01,
) -> str | None:
    relation = describe_price_vs_support(price, support_level, min_tick=min_tick)
    if relation is None:
        return None
    return f"Stabil: {relation}"


def prepare_causal_ohlcv(
    frame: pd.DataFrame | None,
    *,
    symbol: str,
    timeframe: str,
    cutoff_close: Any | None = None,
    certified_closes: bool = False,
) -> tuple[pd.DataFrame, str | None]:
    """Convert raw/indexed OHLCV into a closed-only frame timestamped at `close_time`.

    For foreign/macro instruments without explicit `certified_closes=True` and a
    `close_time` column, returns an empty frame with an explicit reason instead
    of applying BIST 18:00/18:30 close rules.
    """
    if frame is None or len(frame) == 0:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "trade_date"]), "missing_frame"

    df = frame.copy()
    col_map = {c: str(c).lower() for c in df.columns}
    df = df.rename(columns=col_map)
    required = {"open", "high", "low", "close", "volume"}
    missing = required.difference(df.columns)
    if missing:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "trade_date"]), f"missing_columns:{','.join(sorted(missing))}"

    cutoff_ts = _to_istanbul_timestamp(cutoff_close)
    foreign = is_foreign_or_macro_symbol(symbol)

    if foreign and not (certified_closes and "close_time" in df.columns):
        return (
            pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "trade_date"]),
            "foreign_market_requires_certified_close_times",
        )

    if certified_closes and "close_time" in df.columns:
        close_times = pd.DatetimeIndex([_to_istanbul_timestamp(v) for v in df["close_time"]])
        if "timestamp" in df.columns:
            label_times = pd.DatetimeIndex([_to_istanbul_timestamp(v) for v in df["timestamp"]])
        elif isinstance(df.index, pd.DatetimeIndex):
            label_times = pd.DatetimeIndex([_to_istanbul_timestamp(v) for v in df.index])
        else:
            label_times = close_times
    else:
        from data import _istanbul_dizin, mum_kapanis_anlari

        if isinstance(df.index, pd.DatetimeIndex):
            raw_index = df.index
        elif "timestamp" in df.columns:
            raw_index = pd.DatetimeIndex(pd.to_datetime(df["timestamp"], utc=True))
        else:
            return (
                pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "trade_date"]),
                "missing_datetime_index",
            )
        label_times = _istanbul_dizin(raw_index)
        close_times = mum_kapanis_anlari(label_times, timeframe)

    out = pd.DataFrame(
        {
            "timestamp": close_times,
            "open": pd.to_numeric(df["open"], errors="coerce").to_numpy(dtype=float),
            "high": pd.to_numeric(df["high"], errors="coerce").to_numpy(dtype=float),
            "low": pd.to_numeric(df["low"], errors="coerce").to_numpy(dtype=float),
            "close": pd.to_numeric(df["close"], errors="coerce").to_numpy(dtype=float),
            "volume": pd.to_numeric(df["volume"], errors="coerce").fillna(0.0).to_numpy(dtype=float),
            "trade_date": [ts.date() for ts in label_times],
            "is_closed": True,
            "is_complete": True,
        }
    )
    out = out.dropna(subset=["timestamp", "open", "high", "low", "close"])
    if "is_closed" in df.columns:
        closed_mask = df["is_closed"].fillna(False).astype(bool).to_numpy()
        if len(closed_mask) == len(frame):
            out = out.loc[closed_mask[: len(out)]]
    if "is_complete" in df.columns:
        complete_mask = df["is_complete"].fillna(False).astype(bool).to_numpy()
        if len(complete_mask) == len(frame):
            out = out.loc[complete_mask[: len(out)]]

    out = out.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")
    if cutoff_ts is not None:
        out = out[out["timestamp"] <= cutoff_ts]
    out = out.reset_index(drop=True)
    if out.empty:
        return out, "no_completed_bars_at_cutoff"
    return out, None


def _week_last_bist_trading_day(monday: date) -> tuple[date | None, bool]:
    """Return `(last_trading_day, calendar_known)` for the Mon..Fri week starting at `monday`."""
    from bist_calendar import SessionStatus, bist_session_for
    from data import bist_tatil_adi

    last_trading: date | None = None
    for offset in range(5):
        day = monday + timedelta(days=offset)
        if bist_tatil_adi(day) is not None:
            continue
        session = bist_session_for(day)
        if session.status is SessionStatus.UNKNOWN:
            return None, False
        if session.status is SessionStatus.TRADING:
            last_trading = day
    return last_trading, True


def build_completed_weekly_from_daily(
    closed_daily: pd.DataFrame,
    *,
    symbol: str,
    cutoff_close: Any | None = None,
    certified_closes: bool = False,
) -> pd.DataFrame:
    """Derive completed calendar weeks causally from closed daily bars.

    A calendar week (Mon..Sun) is included ONLY when it is causally complete:
    - If a later calendar week already has at least one closed daily bar at/before
      `cutoff_close`, all earlier weeks with bars are necessarily completed.
    - For the latest (final) calendar week present in `closed_daily`, completion
      requires a known BIST session schedule for that week and the week's final
      trading day's daily close timestamp `<= cutoff_close` (or present in
      `closed_daily` when `cutoff_close` is omitted).
    """
    cols = ["timestamp", "open", "high", "low", "close", "volume", "is_closed", "is_complete"]
    if closed_daily is None or closed_daily.empty:
        return pd.DataFrame(columns=cols)

    cutoff_ts = _to_istanbul_timestamp(cutoff_close)
    foreign = is_foreign_or_macro_symbol(symbol)

    trade_dates: list[date]
    if "trade_date" in closed_daily.columns:
        trade_dates = [
            d if isinstance(d, date) and not isinstance(d, datetime) else pd.Timestamp(d).date()
            for d in closed_daily["trade_date"]
        ]
    else:
        trade_dates = [_to_istanbul_timestamp(ts).date() for ts in closed_daily["timestamp"]]

    mondays = [d - timedelta(days=d.weekday()) for d in trade_dates]
    work = closed_daily.copy()
    work["_monday"] = mondays
    work["_trade_date"] = trade_dates

    grouped_weeks = list(work.groupby("_monday", sort=True))
    rows: list[dict[str, Any]] = []
    total_groups = len(grouped_weeks)

    for idx, (monday, grp) in enumerate(grouped_weeks):
        has_later_closed_week = idx < total_groups - 1
        last_trading_day, calendar_known = (
            (None, False) if (foreign and not certified_closes) else _week_last_bist_trading_day(monday)
        )
        expected_week_close = None
        if calendar_known and last_trading_day is not None and not foreign:
            from data import mum_kapanis_ani

            expected_week_close = mum_kapanis_ani(pd.Timestamp(last_trading_day), "1d")

        if not has_later_closed_week:
            if foreign and not certified_closes:
                continue
            if not calendar_known or last_trading_day is None:
                continue
            last_bar_date = grp["_trade_date"].iloc[-1]
            if last_bar_date < last_trading_day:
                continue
            if cutoff_ts is not None and expected_week_close is not None:
                if cutoff_ts < expected_week_close:
                    continue

        week_close_ts = grp["timestamp"].iloc[-1]
        if expected_week_close is not None and expected_week_close > week_close_ts:
            if cutoff_ts is not None and cutoff_ts < expected_week_close:
                continue
            week_close_ts = expected_week_close

        rows.append(
            {
                "timestamp": week_close_ts,
                "open": float(grp["open"].iloc[0]),
                "high": float(grp["high"].max()),
                "low": float(grp["low"].min()),
                "close": float(grp["close"].iloc[-1]),
                "volume": float(grp["volume"].sum()),
                "is_closed": True,
                "is_complete": True,
            }
        )

    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows, columns=cols)


def support_validity_color_role(validity: SupportValidity, support_level: float | None) -> str | None:
    if support_level is None or validity is SupportValidity.NO_SUPPORT:
        return None
    if validity is SupportValidity.ACTIVE:
        return "above"
    if validity in {SupportValidity.BREACHED, SupportValidity.BELOW_FLOOR}:
        return "below"
    return None


def project_support_to_bar_closes(
    bar_close_times: Sequence[Any],
    daily_support_timeline: Sequence[StabilSupportLifecycleSnapshot],
) -> tuple[SupportBarPoint, ...]:
    """Causally project daily support snapshots onto target bars at `daily.as_of <= bar_close`."""
    if not bar_close_times:
        return ()
    valid_snaps = [snap for snap in daily_support_timeline if snap.as_of is not None]
    snap_times = [_to_istanbul_timestamp(snap.as_of) for snap in valid_snaps]

    points: list[SupportBarPoint] = []
    for idx, raw_close in enumerate(bar_close_times):
        close_ts = _to_istanbul_timestamp(raw_close)
        if close_ts is None or not snap_times:
            points.append(
                SupportBarPoint(
                    bar_index=idx,
                    bar_close_time=raw_close,
                    daily_as_of=None,
                    support_level=None,
                    validity=SupportValidity.NO_SUPPORT,
                    dynamics=SupportDynamics.UNAVAILABLE,
                    progression=SupportProgression.NONE,
                    color_role=None,
                )
            )
            continue
        pos = bisect_right(snap_times, close_ts) - 1
        if pos < 0:
            points.append(
                SupportBarPoint(
                    bar_index=idx,
                    bar_close_time=close_ts,
                    daily_as_of=None,
                    support_level=None,
                    validity=SupportValidity.NO_SUPPORT,
                    dynamics=SupportDynamics.UNAVAILABLE,
                    progression=SupportProgression.NONE,
                    color_role=None,
                )
            )
            continue
        snap = valid_snaps[pos]
        level = None if snap.support_level is None else float(snap.support_level)
        points.append(
            SupportBarPoint(
                bar_index=idx,
                bar_close_time=close_ts,
                daily_as_of=snap.as_of,
                support_level=level,
                validity=snap.validity,
                dynamics=snap.dynamics,
                progression=snap.progression,
                color_role=support_validity_color_role(snap.validity, level),
            )
        )
    return tuple(points)


def evaluate_stabil_symbol(
    symbol: str,
    timeframe: str,
    target_frame: pd.DataFrame | None,
    *,
    daily_frame: pd.DataFrame | None = None,
    h4_frame: pd.DataFrame | None = None,
    weekly_frame: pd.DataFrame | None = None,
    as_of_close: Any | None = None,
    config: StabilTrendConfig | None = None,
    certified_closes: bool = False,
    include_support_prefix_events: bool = False,
) -> StabilDomainOutput:
    """Run independent Stabil Support Lifecycle + Stabil Trend Context causally."""
    cfg = config or StabilTrendConfig()
    clean_symbol = _normalize_symbol(symbol)
    tf = str(timeframe or "1d").strip().lower()

    target_clean, target_err = prepare_causal_ohlcv(
        target_frame,
        symbol=clean_symbol,
        timeframe=tf,
        cutoff_close=as_of_close,
        certified_closes=certified_closes,
    )
    effective_cutoff = _to_istanbul_timestamp(as_of_close)
    if effective_cutoff is None and not target_clean.empty:
        effective_cutoff = _to_istanbul_timestamp(target_clean["timestamp"].iloc[-1])

    raw_daily_source = daily_frame if daily_frame is not None else (target_frame if tf == "1d" else None)
    daily_clean, daily_err = prepare_causal_ohlcv(
        raw_daily_source,
        symbol=clean_symbol,
        timeframe="1d",
        cutoff_close=effective_cutoff,
        certified_closes=certified_closes,
    )

    raw_h4_source = h4_frame if h4_frame is not None else (target_frame if tf == "4h" else None)
    if raw_h4_source is None and target_frame is not None and tf == "1h" and not is_foreign_or_macro_symbol(clean_symbol):
        try:
            from data import resample_ohlcv

            raw_h4_source = resample_ohlcv(target_frame, "4h")
        except Exception:
            raw_h4_source = None
    h4_clean, h4_err = prepare_causal_ohlcv(
        raw_h4_source,
        symbol=clean_symbol,
        timeframe="4h",
        cutoff_close=effective_cutoff,
        certified_closes=certified_closes,
    )

    if weekly_frame is not None:
        weekly_clean, weekly_err = prepare_causal_ohlcv(
            weekly_frame,
            symbol=clean_symbol,
            timeframe="1d",
            cutoff_close=effective_cutoff,
            certified_closes=certified_closes,
        )
    elif daily_err is not None and daily_clean.empty:
        weekly_clean = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "is_closed", "is_complete"])
        weekly_err = daily_err
    else:
        weekly_clean = build_completed_weekly_from_daily(
            daily_clean,
            symbol=clean_symbol,
            cutoff_close=effective_cutoff,
            certified_closes=certified_closes,
        )
        weekly_err = "no_completed_weeks" if weekly_clean.empty else None

    # 1. Independent Daily Support Lifecycle (NEVER gated on trend warm-up)
    if daily_clean.empty:
        support_observations: tuple[DailySupportObservation, ...] = ()
        support_timeline: tuple[StabilSupportLifecycleSnapshot, ...] = ()
        support_snapshot = StabilSupportLifecycleEngine(cfg).snapshot()
    else:
        support_observations = build_daily_support_observations(daily_clean, config=cfg)
        support_timeline = build_support_lifecycle_timeline(
            support_observations,
            min_tick=cfg.min_tick,
            include_prefix_events=include_support_prefix_events,
        )
        support_snapshot = (
            support_timeline[-1]
            if support_timeline
            else StabilSupportLifecycleEngine(cfg).snapshot()
        )

    # 2. Independent Multi-TF Trend Context
    trend_engine = StabilTrendEngine(cfg)
    trend_context = trend_engine.analyze(
        weekly_clean,
        daily_clean,
        h4_clean,
        as_of=effective_cutoff,
    )

    # 3. Role-level readiness / data-error accounting
    def _role_state(
        role: str,
        clean_df: pd.DataFrame,
        err: str | None,
        is_ready: bool,
        as_of_val: Any | None,
    ) -> StabilRoleReadiness:
        if err == "foreign_market_requires_certified_close_times":
            return StabilRoleReadiness(role, StabilRoleStatus.DATA_ERROR, err, 0, None)
        if err and err.startswith("missing_columns"):
            return StabilRoleReadiness(role, StabilRoleStatus.DATA_ERROR, err, 0, None)
        if clean_df.empty:
            return StabilRoleReadiness(role, StabilRoleStatus.UNAVAILABLE, err or "empty", 0, None)
        if is_ready:
            return StabilRoleReadiness(role, StabilRoleStatus.READY, None, len(clean_df), as_of_val)
        return StabilRoleReadiness(role, StabilRoleStatus.WARMUP, "insufficient_history_for_role", len(clean_df), as_of_val)

    role_readiness = {
        "daily_support": _role_state(
            "daily_support",
            daily_clean,
            daily_err,
            support_snapshot.support_level is not None,
            support_snapshot.as_of,
        ),
        "weekly_trend": _role_state(
            "weekly_trend",
            weekly_clean,
            weekly_err,
            trend_context.weekly.data_ready,
            trend_context.weekly.timestamp,
        ),
        "daily_trend": _role_state(
            "daily_trend",
            daily_clean,
            daily_err,
            trend_context.daily.data_ready,
            trend_context.daily.timestamp,
        ),
        "h4_trend": _role_state(
            "h4_trend",
            h4_clean,
            h4_err,
            trend_context.h4.data_ready,
            trend_context.h4.timestamp,
        ),
    }

    bar_closes = list(target_clean["timestamp"]) if not target_clean.empty else []
    bar_projection = project_support_to_bar_closes(bar_closes, support_timeline)

    latest_close = float(target_clean["close"].iloc[-1]) if not target_clean.empty else None
    latest_projected_support = (
        bar_projection[-1].support_level
        if bar_projection
        else support_snapshot.support_level
    )
    if target_err == "foreign_market_requires_certified_close_times":
        latest_relation = None
    else:
        latest_relation = describe_price_vs_support(
            latest_close,
            latest_projected_support,
            min_tick=cfg.min_tick,
        )

    return StabilDomainOutput(
        symbol=clean_symbol,
        timeframe=tf,
        as_of_close=effective_cutoff,
        support_snapshot=support_snapshot,
        support_observations=support_observations,
        support_timeline=support_timeline,
        trend_context=trend_context,
        role_readiness=role_readiness,
        bar_projection=bar_projection,
        latest_close=latest_close,
        latest_support_relation=latest_relation,
    )


@dataclass(frozen=True, slots=True)
class StabilSinglePassHistory:
    """Single-pass precomputed native timelines for fast O(N) causal replay."""

    symbol: str
    config: StabilTrendConfig
    daily_frame: pd.DataFrame
    weekly_frame: pd.DataFrame
    h4_frame: pd.DataFrame
    daily_close_times: tuple[pd.Timestamp, ...]
    weekly_close_times: tuple[pd.Timestamp, ...]
    h4_close_times: tuple[pd.Timestamp, ...]
    support_observations: tuple[DailySupportObservation, ...]
    support_timeline: tuple[StabilSupportLifecycleSnapshot, ...]
    all_support_events: tuple[Any, ...]
    weekly_timeline: tuple[WeeklyTrendSnapshot, ...]
    daily_raw_timeline: tuple[DailyTrendSnapshot, ...]
    h4_timeline: tuple[H4TrendSnapshot, ...]

    def support_at(self, cutoff_close: Any) -> tuple[int, StabilSupportLifecycleSnapshot]:
        ts = _to_istanbul_timestamp(cutoff_close)
        if ts is None or not self.daily_close_times:
            return -1, StabilSupportLifecycleEngine(self.config).snapshot()
        idx = bisect_right(self.daily_close_times, ts) - 1
        if idx < 0:
            return -1, StabilSupportLifecycleEngine(self.config).snapshot()
        return idx, self.support_timeline[idx]

    def trend_at(self, cutoff_close: Any) -> StabilTrendContext:
        ts = _to_istanbul_timestamp(cutoff_close)
        if ts is None:
            return StabilTrendContext(None, WeeklyTrendSnapshot(), DailyTrendSnapshot(), H4TrendSnapshot(), H4EvidenceStatus.NONE)
        w_idx = bisect_right(self.weekly_close_times, ts) - 1 if self.weekly_close_times else -1
        d_idx = bisect_right(self.daily_close_times, ts) - 1 if self.daily_close_times else -1
        h_idx = bisect_right(self.h4_close_times, ts) - 1 if self.h4_close_times else -1

        w_snap = self.weekly_timeline[w_idx] if w_idx >= 0 else WeeklyTrendSnapshot()
        d_raw = self.daily_raw_timeline[d_idx] if d_idx >= 0 else DailyTrendSnapshot()
        h_snap = self.h4_timeline[h_idx] if h_idx >= 0 else H4TrendSnapshot()
        return compose_trend_context(w_snap, d_raw, h_snap, self.config, as_of=ts)


def build_single_pass_history(
    symbol: str,
    daily_frame: pd.DataFrame,
    h4_frame: pd.DataFrame,
    *,
    config: StabilTrendConfig | None = None,
    certified_closes: bool = False,
    include_support_prefix_events: bool = True,
) -> StabilSinglePassHistory:
    """Build full symbol history once in O(N) for exact causal checkpoint queries."""
    cfg = config or StabilTrendConfig()
    clean_symbol = _normalize_symbol(symbol)

    d_clean, d_err = prepare_causal_ohlcv(
        daily_frame,
        symbol=clean_symbol,
        timeframe="1d",
        certified_closes=certified_closes,
    )
    if d_err and d_clean.empty:
        raise ValueError(f"Stabil daily frame unavailable for {clean_symbol}: {d_err}")

    h_clean, _ = prepare_causal_ohlcv(
        h4_frame,
        symbol=clean_symbol,
        timeframe="4h",
        certified_closes=certified_closes,
    )

    w_clean = build_completed_weekly_from_daily(
        d_clean,
        symbol=clean_symbol,
        certified_closes=certified_closes,
    )

    support_obs = build_daily_support_observations(d_clean, config=cfg)
    support_tl = build_support_lifecycle_timeline(
        support_obs,
        min_tick=cfg.min_tick,
        include_prefix_events=include_support_prefix_events,
    )
    all_events = support_tl[-1].events if support_tl else ()

    w_tl = build_weekly_trend_timeline(w_clean, cfg)
    d_raw_tl = build_daily_raw_trend_timeline(d_clean, cfg)
    h_tl = build_h4_trend_timeline(h_clean, cfg)

    return StabilSinglePassHistory(
        symbol=clean_symbol,
        config=cfg,
        daily_frame=d_clean,
        weekly_frame=w_clean,
        h4_frame=h_clean,
        daily_close_times=tuple(d_clean["timestamp"]),
        weekly_close_times=tuple(w_clean["timestamp"]) if not w_clean.empty else (),
        h4_close_times=tuple(h_clean["timestamp"]) if not h_clean.empty else (),
        support_observations=support_obs,
        support_timeline=support_tl,
        all_support_events=all_events,
        weekly_timeline=w_tl,
        daily_raw_timeline=d_raw_tl,
        h4_timeline=h_tl,
    )
