"""Single-pass O(N) causal replay dataset builder for Stabil behavioral analysis.

Architecture:
1. Reads native `1d` and `1h` (`-> 4h`) archive series per symbol without writing
   to any live cache or external provider.
2. Runs `build_single_pass_history` ONCE per symbol (zero O(N^2) prefix reruns).
3. Evaluates every closed `4h` checkpoint causally (`daily_close <= h4_close`,
   `weekly_close <= h4_close`), tracks `SupportLifecycleEvent.sequence` on a
   strict first-seen basis, freezes entry daily ATR, computes multi-horizon
   (`1, 4, 8, 10, 12, 16` x `4h` bars) MFE/MAE/retained-close/first-hit paths
   with explicit right-censoring and `UNKNOWN` initial-episode provenance.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
import math
import time
from typing import Any, Sequence

import numpy as np
import pandas as pd

from config import sembol_turu
from domain_engines.stabil import (
    CandidateLineRegime,
    StabilTrendConfig,
    SupportLifecycleEventType,
    SupportProgression,
    SupportValidity,
    build_single_pass_history,
    classify_candidate_support_regimes,
    prepare_causal_ohlcv,
)
from research.arsiv import HAVUZ_DISI_SEMBOLLER, arsiv_sembolleri, tf_frame

HORIZONS_4H: tuple[int, ...] = (1, 4, 8, 10, 12, 16)


@dataclass(frozen=True, slots=True)
class SymbolReplayResult:
    symbol: str
    elapsed_sec: float
    daily_bars: int
    weekly_bars: int
    h4_bars: int
    checkpoint_df: pd.DataFrame
    first_seen_events_df: pd.DataFrame


def select_bist_equity_universe(limit: int = 100, *, kok: Any = None) -> list[str]:
    """Select deterministic sorted BIST equity symbols from the local archive."""
    all_syms = arsiv_sembolleri(kok)
    equities = [
        sym
        for sym in all_syms
        if sembol_turu(sym) == "hisse" and sym not in HAVUZ_DISI_SEMBOLLER
    ]
    return sorted(equities)[: int(limit)]


def build_xu100_regime_lookup(*, kok: Any = None) -> tuple[tuple[pd.Timestamp, ...], tuple[str, ...]]:
    """Build causal XU100 daily regime (`UP` / `DOWN` / `WARMUP`) indexed by daily close."""
    try:
        xu_raw = tf_frame("XU100", "1d", kok)
    except Exception:
        return (), ()
    xu_clean, err = prepare_causal_ohlcv(xu_raw, symbol="XU100", timeframe="1d")
    if err or xu_clean.empty:
        return (), ()
    closes = xu_clean["close"].astype(float)
    ema34 = closes.ewm(span=34, adjust=False).mean()
    states: list[str] = []
    for i in range(len(xu_clean)):
        if i < 34:
            states.append("WARMUP")
        else:
            states.append("XU100_ABOVE_EMA34" if float(closes.iloc[i]) >= float(ema34.iloc[i]) else "XU100_BELOW_EMA34")
    return tuple(xu_clean["timestamp"]), tuple(states)


def _compute_forward_excursions(
    h4_high: np.ndarray,
    h4_low: np.ndarray,
    h4_close: np.ndarray,
    atr_at_entry: np.ndarray,
    horizons: Sequence[int] = HORIZONS_4H,
) -> dict[str, np.ndarray]:
    """Vectorized/linear forward path metrics in fixed initial-daily-ATR units."""
    m = len(h4_close)
    max_h = max(horizons)
    out: dict[str, np.ndarray] = {}
    for h in horizons:
        out[f"censored_{h}"] = np.ones(m, dtype=bool)
        out[f"ret_atr_{h}"] = np.full(m, np.nan, dtype=float)
        out[f"mfe_atr_{h}"] = np.full(m, np.nan, dtype=float)
        out[f"mae_atr_{h}"] = np.full(m, np.nan, dtype=float)
        out[f"first_1atr_{h}"] = np.full(m, "CENSORED", dtype=object)

    for j in range(m):
        atr0 = atr_at_entry[j]
        entry = h4_close[j]
        atr_ok = math.isfinite(atr0) and atr0 > 1e-12 and math.isfinite(entry)
        limit = min(m - 1, j + max_h)
        if limit <= j:
            continue

        up_hit_step: int | None = None
        down_hit_step: int | None = None
        ambiguous_step: int | None = None
        run_high = -math.inf
        run_low = math.inf
        target_up = entry + atr0 if atr_ok else math.inf
        target_dn = entry - atr0 if atr_ok else -math.inf

        horizon_set = set(horizons)
        for step in range(1, limit - j + 1):
            hi = h4_high[j + step]
            lo = h4_low[j + step]
            if hi > run_high:
                run_high = hi
            if lo < run_low:
                run_low = lo

            if atr_ok and up_hit_step is None and down_hit_step is None and ambiguous_step is None:
                hit_u = hi >= target_up
                hit_d = lo <= target_dn
                if hit_u and hit_d:
                    ambiguous_step = step
                elif hit_u:
                    up_hit_step = step
                elif hit_d:
                    down_hit_step = step

            if step in horizon_set:
                out[f"censored_{step}"][j] = False
                if atr_ok:
                    end_c = h4_close[j + step]
                    out[f"ret_atr_{step}"][j] = (end_c - entry) / atr0
                    out[f"mfe_atr_{step}"][j] = max(0.0, (run_high - entry) / atr0)
                    out[f"mae_atr_{step}"][j] = max(0.0, (entry - run_low) / atr0)
                    if ambiguous_step is not None and ambiguous_step <= step:
                        out[f"first_1atr_{step}"][j] = "AMBIGUOUS_SAME_BAR"
                    elif up_hit_step is not None and up_hit_step <= step:
                        out[f"first_1atr_{step}"][j] = "UP_FIRST"
                    elif down_hit_step is not None and down_hit_step <= step:
                        out[f"first_1atr_{step}"][j] = "DOWN_FIRST"
                    else:
                        out[f"first_1atr_{step}"][j] = "NEITHER"
                else:
                    out[f"first_1atr_{step}"][j] = "NO_ATR"
    return out


def replay_single_symbol(
    symbol: str,
    *,
    kok: Any = None,
    config: StabilTrendConfig | None = None,
    xu100_lookup: tuple[tuple[pd.Timestamp, ...], tuple[str, ...]] | None = None,
    user_confirmed_regime: bool = False,
) -> SymbolReplayResult:
    """Run full single-pass causal replay for one BIST equity symbol."""
    t0 = time.perf_counter()
    cfg = config or StabilTrendConfig()
    d_raw = tf_frame(symbol, "1d", kok)
    h4_raw = tf_frame(symbol, "4h", kok)

    history = build_single_pass_history(
        symbol,
        d_raw,
        h4_raw,
        config=cfg,
        include_support_prefix_events=False,
    )
    d_df = history.daily_frame
    h4_df = history.h4_frame
    d_times = history.daily_close_times
    w_times = history.weekly_close_times
    h4_times = history.h4_close_times
    m = len(h4_df)

    # Candidate vertical/horizontal classification on daily timeline (modular & flagged)
    cand_regimes = classify_candidate_support_regimes(
        history.support_timeline,
        config=cfg,
        user_confirmed=user_confirmed_regime,
    )

    # Simple control baselines on daily frame (fixed upfront for H01/H02):
    d_closes = d_df["close"].to_numpy(dtype=float)
    d_lows = d_df["low"].to_numpy(dtype=float)
    d_opens = d_df["open"].to_numpy(dtype=float)
    d_ema34 = pd.Series(d_closes).ewm(span=34, adjust=False).mean().to_numpy(dtype=float)
    d_roll20_low = pd.Series(d_lows).rolling(20).min().shift(1).to_numpy(dtype=float)

    # Provenance of daily support episodes (first observed support has unknown pre-archive history)
    n_d = len(d_df)
    ep_id = np.full(n_d, -1, dtype=int)
    ep_known_start = np.zeros(n_d, dtype=bool)
    ep_touch_seq = np.full(n_d, -1, dtype=int)
    ep_failed_bounces = np.zeros(n_d, dtype=int)
    ep_last_bounce_atr = np.full(n_d, np.nan, dtype=float)
    ep_prev_bounce_atr = np.full(n_d, np.nan, dtype=float)
    prior_lost_supports = np.zeros(n_d, dtype=int)
    prev_support_level_arr = np.full(n_d, np.nan, dtype=float)
    prev_rise_bars_arr = np.zeros(n_d, dtype=int)
    prev_rise_gain_atr_arr = np.full(n_d, np.nan, dtype=float)

    seen_first_usable = False
    cur_identity = None
    cur_ep = 0
    cur_ep_known = False
    touch_active = False
    touch_count = 0
    failed_bounces = 0
    peak_since_touch = 0.0
    last_completed_bounce = math.nan
    prev_completed_bounce = math.nan
    lost_counter = 0
    last_support_val = math.nan
    rise_streak_bars = 0
    rise_start_support = math.nan
    rise_start_atr = math.nan
    frozen_prev_rise_bars = 0
    frozen_prev_rise_gain_atr = math.nan

    # Index native events by daily timestamp for O(1) lookup
    events_by_time: dict[Any, list[Any]] = {}
    for ev in history.all_support_events:
        events_by_time.setdefault(ev.available_at, []).append(ev)

    for di, (obs, snap) in enumerate(zip(history.support_observations, history.support_timeline)):
        day_events = events_by_time.get(obs.timestamp, [])
        for ev in day_events:
            if ev.event_type is SupportLifecycleEventType.SUPPORT_LOST:
                lost_counter += 1
        prior_lost_supports[di] = lost_counter

        ident = obs.support_identity
        if ident is None:
            cur_identity = None
            seen_first_usable = seen_first_usable or False
            continue

        if ident != cur_identity:
            if not seen_first_usable:
                seen_first_usable = True
                cur_ep_known = False  # First support in archive: pre-archive age/episode unknown
            else:
                cur_ep_known = True
            if snap.progression is SupportProgression.REBASED_HIGHER:
                if math.isnan(rise_start_support):
                    rise_start_support = last_support_val if math.isfinite(last_support_val) else float(obs.support_level)
                    rise_start_atr = float(obs.atr) if obs.atr else math.nan
                frozen_prev_rise_bars = rise_streak_bars
                if math.isfinite(rise_start_support) and obs.atr and obs.atr > 0:
                    frozen_prev_rise_gain_atr = (float(obs.support_level) - rise_start_support) / float(obs.atr)
            else:
                rise_streak_bars = 0
                rise_start_support = float(obs.support_level)
                rise_start_atr = float(obs.atr) if obs.atr else math.nan

            if cur_identity is not None and snap.support_level is not None:
                last_support_val = float(history.support_timeline[di - 1].support_level or math.nan) if di > 0 else math.nan
            cur_identity = ident
            cur_ep += 1
            touch_active = False
            touch_count = 0
            failed_bounces = 0
            peak_since_touch = 0.0
            last_completed_bounce = math.nan
            prev_completed_bounce = math.nan

        if snap.validity is SupportValidity.ACTIVE:
            rise_streak_bars += 1
        prev_support_level_arr[di] = last_support_val
        prev_rise_bars_arr[di] = frozen_prev_rise_bars
        prev_rise_gain_atr_arr[di] = frozen_prev_rise_gain_atr
        ep_id[di] = cur_ep
        ep_known_start[di] = cur_ep_known

        # Causal touch & completed bounce tracking
        sup = float(snap.support_level)
        atr_d = float(obs.atr) if obs.atr and obs.atr > 0 else math.nan
        is_touch = (obs.low <= sup <= obs.high) and not snap.close_below_support
        dist_atr_now = (obs.close - sup) / atr_d if math.isfinite(atr_d) else 0.0
        if is_touch:
            if not touch_active:
                if touch_count >= 1 and math.isfinite(peak_since_touch):
                    prev_completed_bounce = last_completed_bounce
                    last_completed_bounce = peak_since_touch
                    if peak_since_touch < 0.75:
                        failed_bounces += 1
                touch_count += 1
                touch_active = True
                peak_since_touch = max(0.0, dist_atr_now)
        elif not snap.close_below_support:
            if touch_active and dist_atr_now >= 0.35:
                touch_active = False
            if touch_count >= 1:
                peak_since_touch = max(peak_since_touch, dist_atr_now)

        ep_touch_seq[di] = touch_count if cur_ep_known else -1
        ep_failed_bounces[di] = failed_bounces if cur_ep_known else -1
        ep_last_bounce_atr[di] = last_completed_bounce
        ep_prev_bounce_atr[di] = prev_completed_bounce

    # Build 4H checkpoint table causally
    h4_open = h4_df["open"].to_numpy(dtype=float)
    h4_high = h4_df["high"].to_numpy(dtype=float)
    h4_low = h4_df["low"].to_numpy(dtype=float)
    h4_close = h4_df["close"].to_numpy(dtype=float)

    xu_times, xu_states = xu100_lookup if xu100_lookup is not None else ((), ())

    rows: list[dict[str, Any]] = []
    first_seen_rows: list[dict[str, Any]] = []
    seen_event_seq = 0
    all_events = history.all_support_events
    total_events = len(all_events)
    ev_cursor = 0

    entry_daily_atr = np.full(m, np.nan, dtype=float)
    d_ptr = -1
    w_ptr = -1
    xu_ptr = -1

    # Track causal breach episode depth & attempts on 4H checkpoints
    breach_ep_active = False
    breach_ep_known = False
    breach_max_depth_atr = 0.0
    breach_bars_4h = 0
    breach_start_drop_1bar_atr = 0.0
    breach_reclaim_attempts = 0
    in_attempt = False
    breach_floor_touched = False
    breach_gap_open = False
    last_support_seen_4h = math.nan

    for j in range(m):
        cp_ts = h4_times[j]
        while d_ptr + 1 < len(d_times) and d_times[d_ptr + 1] <= cp_ts:
            d_ptr += 1
        while w_ptr + 1 < len(w_times) and w_times[w_ptr + 1] <= cp_ts:
            w_ptr += 1
        while xu_ptr + 1 < len(xu_times) and xu_times[xu_ptr + 1] <= cp_ts:
            xu_ptr += 1

        if d_ptr < 0:
            rows.append(
                {
                    "symbol": symbol,
                    "cp_index": j,
                    "cp_time": cp_ts,
                    "daily_index": -1,
                    "h4_open": h4_open[j],
                    "h4_high": h4_high[j],
                    "h4_low": h4_low[j],
                    "h4_close": h4_close[j],
                    "support_ready": False,
                    "support_level": math.nan,
                    "support_floor": math.nan,
                    "daily_atr": math.nan,
                    "validity": SupportValidity.NO_SUPPORT.value,
                    "dynamics": "UNAVAILABLE",
                    "progression": SupportProgression.NONE.value,
                    "candidate_regime": CandidateLineRegime.UNAVAILABLE.value,
                    "regime_provisional": not user_confirmed_regime,
                    "episode_known": False,
                    "bars_since_support": -1,
                    "bars_above_support": 0,
                    "bars_below_support": 0,
                    "dist_atr_4h": math.nan,
                    "dist_pct_4h": math.nan,
                    "price_delta_4h_atr": math.nan,
                    "support_delta_4h_atr": math.nan,
                    "breach_depth_max_atr": math.nan,
                    "breach_bars_4h": 0,
                    "breach_drop_1bar_atr": math.nan,
                    "breach_attempts": 0,
                    "breach_floor_seen": False,
                    "breach_gap_open": False,
                    "touch_seq": -1,
                    "failed_bounces": -1,
                    "last_bounce_atr": math.nan,
                    "prev_bounce_atr": math.nan,
                    "prior_lost_supports": 0,
                    "prev_support_level": math.nan,
                    "prev_rise_bars": 0,
                    "prev_rise_gain_atr": math.nan,
                    "weekly_state": "WEEKLY_PENDING",
                    "daily_trend_state": "DAILY_PENDING",
                    "h4_state": "H4_PENDING",
                    "h4_volume_pass": False,
                    "h4_bull_disp": False,
                    "xu100_regime": xu_states[xu_ptr] if xu_ptr >= 0 else "UNKNOWN",
                    "ctrl_above_ema34": False,
                    "ctrl_near_roll20_low": False,
                    "first_seen_event_count": 0,
                    "first_seen_event_types": "",
                }
            )
            continue

        s_snap = history.support_timeline[d_ptr]
        s_obs = history.support_observations[d_ptr]
        c_reg = cand_regimes[d_ptr]
        w_snap = history.weekly_timeline[w_ptr] if w_ptr >= 0 else None
        d_raw_snap = history.daily_raw_timeline[d_ptr]
        h_snap = history.h4_timeline[j]
        t_ctx = history.trend_at(cp_ts)

        atr_val = float(s_obs.atr) if s_obs.atr is not None and s_obs.atr > 0 else math.nan
        entry_daily_atr[j] = atr_val
        sup_val = float(s_snap.support_level) if s_snap.support_level is not None else math.nan
        flr_val = float(s_snap.support_floor) if s_snap.support_floor is not None else math.nan
        sup_ready = math.isfinite(sup_val) and s_snap.validity is not SupportValidity.NO_SUPPORT

        dist_atr_4h = (h4_close[j] - sup_val) / atr_val if (sup_ready and math.isfinite(atr_val)) else math.nan
        dist_pct_4h = (h4_close[j] - sup_val) / sup_val * 100.0 if (sup_ready and sup_val > 0) else math.nan

        prev_c = h4_close[j - 1] if j > 0 else math.nan
        price_delta_atr = (h4_close[j] - prev_c) / atr_val if (j > 0 and math.isfinite(atr_val)) else math.nan
        support_delta_atr = (
            (sup_val - last_support_seen_4h) / atr_val
            if (sup_ready and math.isfinite(last_support_seen_4h) and math.isfinite(atr_val))
            else 0.0
        )

        # Update causal 4H breach tracker relative to currently known support
        rebased_4h = sup_ready and math.isfinite(last_support_seen_4h) and abs(sup_val - last_support_seen_4h) > cfg.min_tick
        if not sup_ready or rebased_4h:
            breach_ep_active = False
            breach_max_depth_atr = 0.0
            breach_bars_4h = 0
            breach_reclaim_attempts = 0
            in_attempt = False
            breach_floor_touched = False
            breach_gap_open = False

        if sup_ready:
            below_now_4h = h4_close[j] < sup_val
            if below_now_4h:
                if not breach_ep_active:
                    breach_ep_active = True
                    breach_ep_known = bool(ep_known_start[d_ptr]) and j > 0
                    breach_max_depth_atr = max(0.0, (sup_val - h4_low[j]) / atr_val) if math.isfinite(atr_val) else 0.0
                    breach_bars_4h = 1
                    breach_start_drop_1bar_atr = (prev_c - h4_close[j]) / atr_val if (j > 0 and math.isfinite(atr_val)) else 0.0
                    breach_reclaim_attempts = 0
                    in_attempt = False
                    breach_floor_touched = math.isfinite(flr_val) and h4_close[j] < flr_val
                    breach_gap_open = j > 0 and prev_c >= sup_val and h4_open[j] < sup_val and (
                        math.isfinite(atr_val) and (prev_c - h4_open[j]) >= 0.15 * atr_val
                    )
                else:
                    breach_bars_4h += 1
                    if math.isfinite(atr_val):
                        breach_max_depth_atr = max(breach_max_depth_atr, max(0.0, (sup_val - h4_low[j]) / atr_val))
                    if math.isfinite(flr_val) and h4_close[j] < flr_val:
                        breach_floor_touched = True
                    # Intraday wick/attempt toward support that still failed to close above
                    near_or_wick = h4_high[j] >= sup_val - (0.10 * atr_val if math.isfinite(atr_val) else 0.0)
                    if near_or_wick and not in_attempt:
                        breach_reclaim_attempts += 1
                        in_attempt = True
                    elif not near_or_wick:
                        in_attempt = False
            else:
                # If closing back above right after breach, keep snapshot of just-finished breach on this bar, reset next
                pass

        # Collect newly available native daily lifecycle events at this 4H checkpoint (first-seen by sequence)
        new_ev_types: list[str] = []
        while ev_cursor < total_events and all_events[ev_cursor].available_at <= cp_ts:
            ev = all_events[ev_cursor]
            ev_cursor += 1
            if ev.sequence <= seen_event_seq:
                continue
            seen_event_seq = ev.sequence
            new_ev_types.append(ev.event_type.value)
            first_seen_rows.append(
                {
                    "symbol": symbol,
                    "sequence": ev.sequence,
                    "event_type": ev.event_type.value,
                    "event_time": ev.event_time,
                    "first_seen_cp_index": j,
                    "first_seen_cp_time": cp_ts,
                    "support_level": ev.support_level,
                    "support_floor": ev.support_floor,
                    "previous_support": ev.previous_support,
                    "new_support": ev.new_support,
                    "daily_price": ev.price,
                    "h4_entry_close": h4_close[j],
                    "daily_atr": atr_val,
                    "progression": ev.progression.value,
                    "bars_below_support": ev.bars_below_support,
                    "bars_above_support": ev.bars_above_support,
                    "reclaim_count": ev.reclaim_count,
                }
            )

        d_c = d_closes[d_ptr]
        r20 = d_roll20_low[d_ptr]
        ctrl_near_r20 = bool(math.isfinite(r20) and math.isfinite(atr_val) and abs(h4_close[j] - r20) <= 0.5 * atr_val)

        rows.append(
            {
                "symbol": symbol,
                "cp_index": j,
                "cp_time": cp_ts,
                "daily_index": d_ptr,
                "h4_open": h4_open[j],
                "h4_high": h4_high[j],
                "h4_low": h4_low[j],
                "h4_close": h4_close[j],
                "support_ready": sup_ready,
                "support_level": sup_val,
                "support_floor": flr_val,
                "daily_atr": atr_val,
                "validity": s_snap.validity.value,
                "dynamics": s_snap.dynamics.value,
                "progression": s_snap.progression.value,
                "candidate_regime": c_reg.regime.value,
                "regime_provisional": c_reg.provisional,
                "episode_known": bool(ep_known_start[d_ptr]),
                "bars_since_support": int(s_snap.bars_since_support) if (s_snap.bars_since_support is not None and ep_known_start[d_ptr]) else -1,
                "bars_above_support": int(s_snap.bars_above_support),
                "bars_below_support": int(s_snap.bars_below_support),
                "dist_atr_4h": dist_atr_4h,
                "dist_pct_4h": dist_pct_4h,
                "price_delta_4h_atr": price_delta_atr,
                "support_delta_4h_atr": support_delta_atr,
                "breach_depth_max_atr": breach_max_depth_atr if breach_ep_active else math.nan,
                "breach_bars_4h": breach_bars_4h if breach_ep_active else 0,
                "breach_drop_1bar_atr": breach_start_drop_1bar_atr if breach_ep_active else math.nan,
                "breach_attempts": breach_reclaim_attempts if (breach_ep_active and breach_ep_known) else (-1 if breach_ep_active else 0),
                "breach_floor_seen": breach_floor_touched if breach_ep_active else False,
                "breach_gap_open": breach_gap_open if breach_ep_active else False,
                "touch_seq": int(ep_touch_seq[d_ptr]),
                "failed_bounces": int(ep_failed_bounces[d_ptr]),
                "last_bounce_atr": float(ep_last_bounce_atr[d_ptr]),
                "prev_bounce_atr": float(ep_prev_bounce_atr[d_ptr]),
                "prior_lost_supports": int(prior_lost_supports[d_ptr]),
                "prev_support_level": float(prev_support_level_arr[d_ptr]),
                "prev_rise_bars": int(prev_rise_bars_arr[d_ptr]),
                "prev_rise_gain_atr": float(prev_rise_gain_atr_arr[d_ptr]),
                "weekly_state": w_snap.state.value if w_snap is not None else "WEEKLY_PENDING",
                "daily_trend_state": t_ctx.daily.state.value,
                "h4_state": h_snap.state.value,
                "h4_volume_pass": bool(h_snap.volume_pass and h_snap.volume_usable),
                "h4_bull_disp": bool(h_snap.bull_displacement),
                "xu100_regime": xu_states[xu_ptr] if xu_ptr >= 0 else "UNKNOWN",
                "ctrl_above_ema34": bool(math.isfinite(d_ema34[d_ptr]) and d_c >= d_ema34[d_ptr]),
                "ctrl_near_roll20_low": ctrl_near_r20,
                "first_seen_event_count": len(new_ev_types),
                "first_seen_event_types": ",".join(new_ev_types),
            }
        )

        # Reset 4H breach tracker once price closes back above support
        if sup_ready and h4_close[j] >= sup_val and breach_ep_active:
            # Record just-reclaimed metadata onto the current row before resetting
            rows[-1]["reclaimed_4h_now"] = True
            rows[-1]["reclaimed_prev_depth_atr"] = breach_max_depth_atr
            rows[-1]["reclaimed_prev_bars_4h"] = breach_bars_4h
            rows[-1]["reclaimed_prev_drop_1bar_atr"] = breach_start_drop_1bar_atr
            rows[-1]["reclaimed_prev_attempts"] = breach_reclaim_attempts if breach_ep_known else -1
            rows[-1]["reclaimed_prev_floor_seen"] = breach_floor_touched
            rows[-1]["reclaimed_prev_gap_open"] = breach_gap_open
            breach_ep_active = False
            breach_max_depth_atr = 0.0
            breach_bars_4h = 0
            breach_reclaim_attempts = 0
            in_attempt = False
            breach_floor_touched = False
            breach_gap_open = False
        else:
            rows[-1]["reclaimed_4h_now"] = False
            rows[-1]["reclaimed_prev_depth_atr"] = math.nan
            rows[-1]["reclaimed_prev_bars_4h"] = 0
            rows[-1]["reclaimed_prev_drop_1bar_atr"] = math.nan
            rows[-1]["reclaimed_prev_attempts"] = 0
            rows[-1]["reclaimed_prev_floor_seen"] = False
            rows[-1]["reclaimed_prev_gap_open"] = False

        if sup_ready:
            last_support_seen_4h = sup_val
        else:
            last_support_seen_4h = math.nan

    cp_df = pd.DataFrame(rows)
    excursions = _compute_forward_excursions(h4_high, h4_low, h4_close, entry_daily_atr, HORIZONS_4H)
    for col_name, values in excursions.items():
        cp_df[col_name] = values

    # Competing next-outcome race within next 24 x 4H bars (~6 trading days) for race questions (A01, E02, etc.)
    race_window = 24
    sup_arr = cp_df["support_level"].to_numpy(dtype=float)
    ready_arr = cp_df["support_ready"].to_numpy(dtype=bool)
    next_race = np.full(m, "NO_SUPPORT", dtype=object)
    bars_to_retest_24 = np.full(m, -1, dtype=int)
    for j in range(m):
        if not ready_arr[j]:
            continue
        s0 = sup_arr[j]
        a0 = entry_daily_atr[j]
        end_j = min(m - 1, j + race_window)
        if end_j == j:
            next_race[j] = "CENSORED"
            continue
        above0 = h4_close[j] >= s0
        outcome = "CENSORED" if (j + race_window >= m) else "NEITHER_WITHIN_24"
        for k in range(j + 1, end_j + 1):
            sk = sup_arr[k]
            rebased_up = ready_arr[k] and sk > s0 + cfg.min_tick
            rebased_dn = ready_arr[k] and sk < s0 - cfg.min_tick
            touched_back = above0 and h4_low[k] <= s0 + (0.15 * a0 if math.isfinite(a0) else 0.0)
            reclaimed_up = (not above0) and h4_close[k] >= s0
            if above0:
                if rebased_up and touched_back:
                    outcome = "SAME_CHECKPOINT"
                    break
                if rebased_up:
                    outcome = "SUPPORT_UP_FIRST"
                    break
                if touched_back:
                    outcome = "PRICE_RETURN_FIRST"
                    bars_to_retest_24[j] = k - j
                    break
                if rebased_dn:
                    outcome = "SUPPORT_DOWN_FIRST"
                    break
            else:
                if rebased_dn and reclaimed_up:
                    outcome = "SAME_CHECKPOINT"
                    break
                if reclaimed_up:
                    outcome = "PRICE_RECLAIM_FIRST"
                    break
                if rebased_dn:
                    outcome = "SUPPORT_DOWN_FIRST"
                    break
        next_race[j] = outcome
        if bars_to_retest_24[j] < 0 and above0:
            for k in range(j + 1, end_j + 1):
                if h4_low[k] <= s0 + (0.15 * a0 if math.isfinite(a0) else 0.0):
                    bars_to_retest_24[j] = k - j
                    break
    cp_df["next_race_24"] = next_race
    cp_df["bars_to_retest_24"] = bars_to_retest_24

    ev_df = pd.DataFrame(first_seen_rows)
    if not ev_df.empty:
        ev_idx = ev_df["first_seen_cp_index"].to_numpy(dtype=int)
        for h in HORIZONS_4H:
            ev_df[f"censored_{h}"] = cp_df[f"censored_{h}"].to_numpy()[ev_idx]
            ev_df[f"ret_atr_{h}"] = cp_df[f"ret_atr_{h}"].to_numpy()[ev_idx]
            ev_df[f"mfe_atr_{h}"] = cp_df[f"mfe_atr_{h}"].to_numpy()[ev_idx]
            ev_df[f"mae_atr_{h}"] = cp_df[f"mae_atr_{h}"].to_numpy()[ev_idx]
            ev_df[f"first_1atr_{h}"] = cp_df[f"first_1atr_{h}"].to_numpy()[ev_idx]

    elapsed = time.perf_counter() - t0
    return SymbolReplayResult(
        symbol=symbol,
        elapsed_sec=elapsed,
        daily_bars=len(d_df),
        weekly_bars=len(history.weekly_frame),
        h4_bars=m,
        checkpoint_df=cp_df,
        first_seen_events_df=ev_df,
    )
