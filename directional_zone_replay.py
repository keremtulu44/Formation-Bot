"""Offline, direction-aware touch/reaction replay for native OB and FVG zones.

This module is not imported by the live runner. It replays the unchanged domain
engines over completed local OHLCV frames and keeps measurement choices explicit.
"""
from __future__ import annotations

from collections import defaultdict
from copy import copy
from dataclasses import dataclass
import math
from typing import Any, Iterable, Mapping

import pandas as pd

# Predeclared descriptive thresholds; these are not tuned against replay outcomes.
HORIZONS = (10, 12)
FAVORABLE_ATR_THRESHOLDS = (0.5, 1.0, 1.5)
FVG_PROFILE = "Dengeli"


def classify_arrival(previous_close: float | None, lower: float, upper: float) -> tuple[str, str]:
    """Classify the last known close before a contact, separately from response."""
    if previous_close is None or not math.isfinite(float(previous_close)):
        return "NO_PREVIOUS_BAR", "UNKNOWN"
    value = float(previous_close)
    if value > upper:
        return "FROM_ABOVE", "DOWN_TOWARD_ZONE"
    if value < lower:
        return "FROM_BELOW", "UP_TOWARD_ZONE"
    if value == lower or value == upper:
        return "ON_ZONE_BOUNDARY", "AMBIGUOUS"
    return "INSIDE_ZONE", "AMBIGUOUS"


def directional_excursions(
    direction: str,
    lower: float,
    upper: float,
    future_bars: Iterable[Mapping[str, Any]],
    atr_at_touch: float | None,
) -> dict[str, float | None]:
    """Return post-contact max favorable/adverse OHLC excursion from native edges."""
    rows = list(future_bars)
    if not rows:
        return {
            "favorable_price": None,
            "adverse_price": None,
            "favorable_atr": None,
            "adverse_atr": None,
        }
    future_high = max(float(row["high"]) for row in rows)
    future_low = min(float(row["low"]) for row in rows)
    if direction.lower() == "bullish":
        favorable = max(0.0, future_high - float(upper))
        adverse = max(0.0, float(lower) - future_low)
    elif direction.lower() == "bearish":
        favorable = max(0.0, float(lower) - future_low)
        adverse = max(0.0, future_high - float(upper))
    else:
        raise ValueError("direction must be 'bullish' or 'bearish'")
    valid_atr = (
        atr_at_touch is not None
        and math.isfinite(float(atr_at_touch))
        and float(atr_at_touch) > 0
    )
    return {
        "favorable_price": favorable,
        "adverse_price": adverse,
        "favorable_atr": favorable / float(atr_at_touch) if valid_atr else None,
        "adverse_atr": adverse / float(atr_at_touch) if valid_atr else None,
    }


def classify_ob_removal(record: Any, row: Mapping[str, Any], fill_threshold: float) -> tuple[str, float]:
    """Mirror the current OB core removal conditions without changing the engine."""
    high, low = float(row["high"]), float(row["low"])
    if record.bullish and high < float(record.bottom):
        return "gap_through", float(record.fill_ratio)
    if not record.bullish and low > float(record.top):
        return "gap_through", float(record.fill_ratio)
    entered = low <= float(record.top) and high >= float(record.bottom)
    if not entered:
        return "native_lifecycle_removed", float(record.fill_ratio)
    height = float(record.top) - float(record.bottom)
    if height <= 0:
        return "native_lifecycle_removed", float(record.fill_ratio)
    if record.bullish:
        penetrated = max(float(record.bottom), min(float(record.top), low))
        boundary = min(float(record.fill_boundary), penetrated)
        ratio = (float(record.top) - boundary) / height
    else:
        penetrated = min(float(record.top), max(float(record.bottom), high))
        boundary = max(float(record.fill_boundary), penetrated)
        ratio = (boundary - float(record.bottom)) / height
    ratio = min(1.0, max(0.0, float(ratio)))
    if ratio >= fill_threshold:
        return "fill_cancel_threshold", ratio
    return "native_lifecycle_removed", ratio


def classify_fvg_terminal(state: str | None, reason: str | None) -> str:
    """Separate native price breach, full fill, reaction and non-price endings."""
    state = (state or "").upper()
    reason = reason or ""
    if state == "FULL_FILL" or reason == "Tam dolum":
        return "FULL_FILL"
    if state == "INVALID" and reason == "Kapanışla geçersizlik":
        return "CLOSE_INVALIDATION"
    if state == "INVALID" and reason == "Yaş sınırı":
        return "AGE_EXPIRY_NOT_PRICE_BREACH"
    if state == "INVALID" and reason == "Kalite yetersizliği":
        return "QUALITY_INVALIDATION"
    if state == "REACTION" or reason == "Tepki üretti":
        return "NATIVE_REACTION_TERMINAL"
    if state == "SUPERSEDED" or "devralındı" in reason.lower():
        return "SUPERSEDED_NOT_PRICE_BREACH"
    if not state and not reason:
        return "ACTIVE_AT_ASOF"
    return "OTHER_NATIVE_TERMINAL"


def _normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy(deep=True)
    if "timestamp" not in data.columns:
        if isinstance(data.index, pd.DatetimeIndex) or data.index.name == "timestamp":
            data = data.reset_index()
            if "index" in data.columns:
                data = data.rename(columns={"index": "timestamp"})
        else:
            raise ValueError("frame requires a timestamp column or DatetimeIndex")
    data.columns = [str(column).lower() for column in data.columns]
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    if not required.issubset(data.columns):
        raise ValueError(f"frame is missing {sorted(required - set(data.columns))}")
    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True).dt.tz_convert("Europe/Istanbul")
    data = data.sort_values("timestamp", kind="stable").reset_index(drop=True)
    return data


def _zone_id(symbol: str, family: str, timeframe: str, direction: str, origin: int, lower: float, upper: float) -> str:
    return f"{symbol}|{family}|{timeframe}|{direction}|{origin}|{lower:.12g}|{upper:.12g}"


def _ordered(first: float, second: float) -> tuple[float, float]:
    return min(float(first), float(second)), max(float(first), float(second))


def _remaining_fvg_bounds(record: Any) -> tuple[float, float]:
    lower, upper = float(record.lower_boundary), float(record.upper_boundary)
    gap = float(record.gap_size)
    fill = min(1.0, max(0.0, float(record.maximum_fill_ratio)))
    if int(record.direction) > 0:
        return lower, max(lower, upper - gap * fill)
    return min(upper, lower + gap * fill), upper


def _new_zone(
    *, symbol: str, family: str, timeframe: str, direction: str,
    origin_index: int, origin_time: Any, available_index: int,
    lower: float, upper: float, native_status: str,
) -> dict[str, Any]:
    return {
        "zone_id": _zone_id(symbol, family, timeframe, direction, origin_index, lower, upper),
        "symbol": symbol,
        "family": family,
        "timeframe": timeframe,
        "direction": direction,
        "expected_reaction_direction": "UP" if direction == "bullish" else "DOWN",
        "origin_index": int(origin_index),
        "origin_time": origin_time,
        "available_index": int(available_index),
        "available_at": None,
        "zone_lower": float(lower),
        "zone_upper": float(upper),
        "native_status_at_asof": native_status,
        "native_terminal_index": None,
        "native_terminal_at": None,
        "native_terminal_state": None,
        "native_terminal_reason": None,
        "native_terminal_category": "ACTIVE_AT_ASOF",
        "native_price_violation": False,
        "native_full_fill": False,
        "native_fill_ratio_at_terminal_or_asof": None,
        "current_remaining_lower": float(lower),
        "current_remaining_upper": float(upper),
        "contact_bars": [],
        "active_at_asof": True,
    }


def _timestamp(frame: pd.DataFrame, index: int) -> pd.Timestamp:
    return pd.Timestamp(frame.at[index, "timestamp"])


def replay_ob_zones(symbol: str, timeframe: str, frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Causally replay native OB state and record native-rule contact bars."""
    from domain_engines.order_block import OrderBlockEngine

    data = _normalize_frame(frame)
    engine = OrderBlockEngine()
    zones: dict[tuple[Any, ...], dict[str, Any]] = {}
    for index, row in enumerate(data.to_dict("records")):
        pre_active = {_ob_key(record): record for record in engine.active_records}
        for key, record in pre_active.items():
            zone = zones.get(key)
            if zone is None or index <= zone["available_index"]:
                continue
            # This is the core OB engine's entry test: overlap with original top/bottom.
            touched = float(row["low"]) <= float(record.top) and float(row["high"]) >= float(record.bottom)
            if touched:
                rem_a, rem_b = engine._active_remaining_zone(record)
                rem_lower, rem_upper = _ordered(rem_a, rem_b)
                zone["contact_bars"].append({
                    "index": index,
                    "remaining_lower": rem_lower,
                    "remaining_upper": rem_upper,
                    "fill_ratio_before_bar": float(record.fill_ratio),
                })
        engine.update(row)
        post_active = {_ob_key(record): record for record in engine.active_records}
        for key, record in post_active.items():
            if key not in zones:
                direction = "bullish" if record.bullish else "bearish"
                lower, upper = float(record.bottom), float(record.top)
                zone = _new_zone(
                    symbol=symbol, family="OB", timeframe=timeframe, direction=direction,
                    origin_index=record.source_index, origin_time=record.source_time,
                    available_index=index, lower=lower, upper=upper, native_status="ACTIVE_OB",
                )
                zone["available_at"] = _timestamp(data, index)
                zones[key] = zone
            zone = zones[key]
            zone["native_status_at_asof"] = "ACTIVE_OB"
            rem_a, rem_b = engine._active_remaining_zone(record)
            zone["current_remaining_lower"], zone["current_remaining_upper"] = _ordered(rem_a, rem_b)
            zone["native_fill_ratio_at_terminal_or_asof"] = float(record.fill_ratio)
            zone["active_at_asof"] = True
        for key, record in pre_active.items():
            if key in post_active:
                continue
            zone = zones.get(key)
            if zone is None:
                continue
            reason, fill_ratio = classify_ob_removal(record, row, engine.config.fill_cancel_threshold)
            zone.update({
                "active_at_asof": False,
                "native_status_at_asof": "REMOVED_BY_NATIVE_LIFECYCLE",
                "native_terminal_index": index,
                "native_terminal_at": _timestamp(data, index),
                "native_terminal_state": "REMOVED_BY_NATIVE_LIFECYCLE",
                "native_terminal_reason": reason,
                "native_terminal_category": reason.upper(),
                "native_price_violation": reason in {"gap_through", "fill_cancel_threshold"},
                "native_full_fill": False,
                "native_fill_ratio_at_terminal_or_asof": fill_ratio,
                "current_remaining_lower": zone["zone_lower"],
                "current_remaining_upper": zone["zone_upper"],
            })
    return _finalize_zones(zones.values(), data)


def _ob_key(record: Any) -> tuple[Any, ...]:
    return (int(record.source_index), bool(record.bullish), float(record.top), float(record.bottom))


def replay_fvg_zones(
    symbol: str,
    timeframe: str,
    frame: pd.DataFrame,
    *,
    profile: str = FVG_PROFILE,
) -> tuple[list[dict[str, Any]], str, int]:
    """Causally replay promoted native FVG zones; candidate-only records are excluded."""
    from domain_engines.fvg import FvgEngulfingConfig, FvgEngulfingEngine, SensitivityProfile
    from domain_engines.fvg.fvg_engulfing_models import FvgState

    data = _normalize_frame(frame)
    engine = FvgEngulfingEngine(FvgEngulfingConfig(timeframe=timeframe, sensitivity=SensitivityProfile(profile)))
    zones: dict[tuple[Any, ...], dict[str, Any]] = {}
    candidate_keys: set[tuple[Any, ...]] = set()
    for index, row in enumerate(data.to_dict("records")):
        pre_records = [copy(r) for r in (engine.active_bullish_fvg, engine.active_bearish_fvg) if r is not None]
        pre_keys = set()
        for record in pre_records:
            key = _fvg_key(record)
            pre_keys.add(key)
            if record.state is FvgState.CANDIDATE:
                candidate_keys.add(key)
                continue
            zone = zones.get(key)
            if zone is None or index <= zone["available_index"]:
                continue
            # Match the native lifecycle's FVG test trigger (not an invented close rule).
            bullish = int(record.direction) > 0
            touched = float(row["low"]) <= float(record.upper_boundary) if bullish else float(row["high"]) >= float(record.lower_boundary)
            if touched:
                rem_lower, rem_upper = _remaining_fvg_bounds(record)
                zone["contact_bars"].append({
                    "index": index,
                    "remaining_lower": rem_lower,
                    "remaining_upper": rem_upper,
                    "fill_ratio_before_bar": float(record.maximum_fill_ratio),
                })
        engine.update(row)
        post_records = [r for r in (engine.active_bullish_fvg, engine.active_bearish_fvg) if r is not None]
        post_by_key = {_fvg_key(record): record for record in post_records}
        for key, record in post_by_key.items():
            if record.state is FvgState.CANDIDATE:
                candidate_keys.add(key)
                continue
            if key not in zones:
                direction = "bullish" if int(record.direction) > 0 else "bearish"
                lower, upper = float(record.lower_boundary), float(record.upper_boundary)
                zone = _new_zone(
                    symbol=symbol, family="FVG", timeframe=timeframe, direction=direction,
                    origin_index=record.formation_index, origin_time=record.formation_time,
                    available_index=index, lower=lower, upper=upper, native_status=record.state.name,
                )
                zone["available_at"] = _timestamp(data, index)
                zones[key] = zone
            zone = zones[key]
            zone["native_status_at_asof"] = record.state.name
            zone["native_fill_ratio_at_terminal_or_asof"] = float(record.maximum_fill_ratio)
            zone["current_remaining_lower"], zone["current_remaining_upper"] = _remaining_fvg_bounds(record)
            zone["active_at_asof"] = True
        completed_by_key = {_fvg_key(record): record for record in engine.completed_fvg}
        for key in pre_keys:
            if key in post_by_key:
                continue
            zone = zones.get(key)
            record = completed_by_key.get(key)
            if zone is None or record is None or zone["native_terminal_index"] is not None:
                continue
            category = classify_fvg_terminal(record.state.name, record.invalid_reason)
            zone.update({
                "active_at_asof": False,
                "native_status_at_asof": record.state.name,
                "native_terminal_index": index,
                "native_terminal_at": _timestamp(data, index),
                "native_terminal_state": record.state.name,
                "native_terminal_reason": record.invalid_reason,
                "native_terminal_category": category,
                "native_price_violation": category == "CLOSE_INVALIDATION",
                "native_full_fill": category == "FULL_FILL",
                "native_fill_ratio_at_terminal_or_asof": float(record.maximum_fill_ratio),
                "current_remaining_lower": zone["zone_lower"],
                "current_remaining_upper": zone["zone_upper"],
            })
    finalized = _finalize_zones(zones.values(), data)
    excluded_candidate_count = len(candidate_keys - set(zones))
    return finalized, engine.last_data_quality.value, excluded_candidate_count


def _fvg_key(record: Any) -> tuple[Any, ...]:
    return (int(record.formation_index), int(record.direction), float(record.lower_boundary), float(record.upper_boundary))


def _finalize_zones(zones: Iterable[dict[str, Any]], frame: pd.DataFrame) -> list[dict[str, Any]]:
    finalized = []
    for zone in zones:
        zone["available_at"] = zone["available_at"] or _timestamp(frame, zone["available_index"])
        zone["formation_time"] = zone["origin_time"]
        zone["native_terminal_category"] = zone["native_terminal_category"] or "ACTIVE_AT_ASOF"
        zone["touch_bars"] = sorted(zone["contact_bars"], key=lambda x: x["index"])
        finalized.append(zone)
    return finalized


def build_touch_episodes(zones: Iterable[dict[str, Any]], frames: Mapping[tuple[str, str], pd.DataFrame]) -> list[dict[str, Any]]:
    """Split repeated native-rule contact bars into distinct episodes per zone."""
    episodes: list[dict[str, Any]] = []
    for zone in zones:
        bars = zone["touch_bars"]
        if not bars:
            continue
        groups: list[list[dict[str, Any]]] = []
        current = [bars[0]]
        for bar in bars[1:]:
            if bar["index"] == current[-1]["index"] + 1:
                current.append(bar)
            else:
                groups.append(current)
                current = [bar]
        groups.append(current)
        frame = frames[(zone["symbol"], zone["timeframe"])]
        for number, group in enumerate(groups, 1):
            start, end = group[0]["index"], group[-1]["index"]
            previous_close = float(frame.at[start - 1, "close"]) if start > 0 else None
            arrival_side, approach_direction = classify_arrival(previous_close, zone["zone_lower"], zone["zone_upper"])
            episodes.append({
                "episode_id": f"{zone['zone_id']}|touch{number}|{_timestamp(frame, start).isoformat()}",
                "zone_id": zone["zone_id"],
                "symbol": zone["symbol"],
                "family": zone["family"],
                "timeframe": zone["timeframe"],
                "direction": zone["direction"],
                "expected_reaction_direction": zone["expected_reaction_direction"],
                "touch_number_for_zone": number,
                "touch_start_index": start,
                "touch_end_index": end,
                "touch_start": _timestamp(frame, start),
                "touch_end": _timestamp(frame, end),
                "touch_bar_count": len(group),
                "arrival_previous_close": previous_close,
                "arrival_side": arrival_side,
                "approach_direction": approach_direction,
                "native_touch_rule": (
                    "OHLC_OVERLAP_ORIGINAL_OB_BOUNDS"
                    if zone["family"] == "OB"
                    else "BULLISH_LOW_LE_ORIGINAL_FVG_UPPER_OR_BEARISH_HIGH_GE_ORIGINAL_FVG_LOWER"
                ),
                "zone_lower": zone["zone_lower"],
                "zone_upper": zone["zone_upper"],
                "remaining_lower_at_touch_end": group[-1]["remaining_lower"],
                "remaining_upper_at_touch_end": group[-1]["remaining_upper"],
                "fill_ratio_before_touch_end_bar": group[-1]["fill_ratio_before_bar"],
                "available_at": zone["available_at"],
                "native_terminal_index": zone["native_terminal_index"],
                "native_terminal_at": zone["native_terminal_at"],
                "native_terminal_state": zone["native_terminal_state"],
                "native_terminal_reason": zone["native_terminal_reason"],
                "native_terminal_category": zone["native_terminal_category"],
                "native_price_violation": zone["native_price_violation"],
                "native_full_fill": zone["native_full_fill"],
                "native_terminal_at_touch": zone["native_terminal_index"] == end,
                "_next_episode_start_index": None,
            })
    episodes.sort(key=lambda x: (x["symbol"], x["family"], x["timeframe"], x["zone_id"], x["touch_start_index"]))
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ep in episodes:
        grouped[ep["zone_id"]].append(ep)
    for values in grouped.values():
        for current, nxt in zip(values, values[1:]):
            current["_next_episode_start_index"] = nxt["touch_start_index"]
    return episodes


def build_window_rows(
    episodes: Iterable[dict[str, Any]],
    zones_by_id: Mapping[str, dict[str, Any]],
    frames: Mapping[tuple[str, str], pd.DataFrame],
    atr_by_series: Mapping[tuple[str, str], tuple[float | None, ...]],
) -> list[dict[str, Any]]:
    """Build fixed N-bar event windows; incomplete data are retained as censored."""
    rows: list[dict[str, Any]] = []
    for episode in episodes:
        zone = zones_by_id[episode["zone_id"]]
        key = (episode["symbol"], episode["timeframe"])
        frame, atr = frames[key], atr_by_series[key]
        touch_end = int(episode["touch_end_index"])
        for horizon in HORIZONS:
            start = touch_end + 1
            observed = max(0, min(horizon, len(frame) - start))
            complete = observed == horizon
            end = start + horizon - 1
            atr_value = atr[touch_end] if touch_end < len(atr) else None
            atr_ok = atr_value is not None and math.isfinite(float(atr_value)) and float(atr_value) > 0
            future_all = frame.iloc[start:start + observed].to_dict("records") if observed else []
            full_metrics = directional_excursions(episode["direction"], episode["zone_lower"], episode["zone_upper"], future_all, atr_value) if complete else {
                "favorable_price": None, "adverse_price": None, "favorable_atr": None, "adverse_atr": None,
            }
            terminal = zone["native_terminal_index"]
            terminal_at_touch = terminal is not None and int(terminal) <= touch_end
            terminal_within_observed = terminal is not None and touch_end < int(terminal) <= touch_end + observed
            terminal_within_full = terminal is not None and touch_end < int(terminal) <= end and complete
            terminal_row = frame.iloc[int(terminal)].to_dict() if terminal_within_observed else None
            terminal_metrics = directional_excursions(episode["direction"], episode["zone_lower"], episode["zone_upper"], [terminal_row], atr_value) if terminal_row is not None else None
            if terminal_at_touch:
                before_terminal_rows: list[dict[str, Any]] = []
            elif terminal is not None and start <= int(terminal) <= end:
                before_terminal_rows = frame.iloc[start:int(terminal)].to_dict("records")
            else:
                before_terminal_rows = future_all if complete else []
            before_metrics = directional_excursions(episode["direction"], episode["zone_lower"], episode["zone_upper"], before_terminal_rows, atr_value) if before_terminal_rows else None
            if terminal_at_touch:
                after_terminal_rows = future_all
            elif terminal_within_observed:
                after_terminal_rows = frame.iloc[int(terminal) + 1:start + observed].to_dict("records")
            else:
                after_terminal_rows = []
            after_metrics = directional_excursions(episode["direction"], episode["zone_lower"], episode["zone_upper"], after_terminal_rows, atr_value) if after_terminal_rows else None
            preterminal_bars = len(before_terminal_rows)
            active_target_eligible = complete and atr_ok and preterminal_bars > 0
            if not complete:
                status = "RIGHT_CENSORED_DATA_END"
            elif not atr_ok:
                status = "ATR14_UNAVAILABLE_AT_TOUCH"
            elif terminal_at_touch:
                status = "NATIVE_TERMINAL_ON_TOUCH"
            else:
                status = "COMPLETE"
            row = {k: v for k, v in episode.items() if not k.startswith("_")}
            row.update({
                "horizon_bars": horizon,
                "reaction_start": _timestamp(frame, start) if start < len(frame) else None,
                "reaction_window_end": _timestamp(frame, min(end, len(frame) - 1)) if observed else None,
                "observed_post_touch_bars": observed,
                "window_complete": complete,
                "atr14_at_touch_end": float(atr_value) if atr_ok else None,
                "window_status": status,
                "full_window_favorable_excursion_price": full_metrics["favorable_price"],
                "full_window_favorable_excursion_atr": full_metrics["favorable_atr"],
                "full_window_adverse_excursion_price": full_metrics["adverse_price"],
                "full_window_adverse_excursion_atr": full_metrics["adverse_atr"],
                "favorable_excursion_before_native_terminal_atr": before_metrics["favorable_atr"] if before_metrics else None,
                "adverse_excursion_before_native_terminal_atr": before_metrics["adverse_atr"] if before_metrics else None,
                "favorable_excursion_on_terminal_bar_atr": terminal_metrics["favorable_atr"] if terminal_metrics else None,
                "favorable_excursion_after_native_terminal_atr": after_metrics["favorable_atr"] if after_metrics else None,
                "preterminal_post_touch_bars": preterminal_bars,
                "active_target_eligible": active_target_eligible,
                "native_terminal_within_observed_window": bool(terminal_within_observed),
                "native_terminal_within_full_horizon": bool(terminal_within_full),
                "native_terminal_at_or_before_touch": bool(terminal_at_touch),
                "native_price_violation_within_observed_window": bool(terminal_within_observed and zone["native_price_violation"]),
                "native_price_violation_within_full_horizon": bool(terminal_within_full and zone["native_price_violation"]),
                "native_full_fill_within_observed_window": bool(terminal_within_observed and zone["native_full_fill"]),
                "native_full_fill_within_full_horizon": bool(terminal_within_full and zone["native_full_fill"]),
                "native_terminal_reason_in_window": zone["native_terminal_reason"] if terminal_within_observed else None,
                "next_same_zone_touch_in_window": bool(
                    episode.get("_next_episode_start_index") is not None
                    and touch_end < int(episode["_next_episode_start_index"]) <= end
                ) if complete else False,
            })
            for threshold in FAVORABLE_ATR_THRESHOLDS:
                tag = str(threshold).replace(".", "p")
                full_hit = complete and atr_ok and full_metrics["favorable_atr"] is not None and full_metrics["favorable_atr"] >= threshold
                before_hit = active_target_eligible and before_metrics is not None and before_metrics["favorable_atr"] is not None and before_metrics["favorable_atr"] >= threshold
                same_bar_hit = terminal_within_full and terminal_metrics is not None and terminal_metrics["favorable_atr"] is not None and terminal_metrics["favorable_atr"] >= threshold
                after_only = bool(full_hit and not before_hit and not same_bar_hit)
                if not (complete and atr_ok):
                    category = "NOT_EVALUABLE"
                elif before_hit:
                    category = "HIT_BEFORE_NATIVE_TERMINAL"
                elif same_bar_hit:
                    category = "AMBIGUOUS_ON_TERMINAL_BAR"
                elif after_only:
                    category = "HIT_ONLY_AFTER_NATIVE_TERMINAL"
                else:
                    category = "NOT_REACHED"
                row[f"target_{tag}_atr_hit_full_window"] = bool(full_hit) if complete and atr_ok else None
                row[f"target_{tag}_atr_hit_before_native_terminal"] = bool(before_hit) if active_target_eligible else None
                row[f"target_{tag}_atr_possible_on_terminal_bar"] = bool(same_bar_hit) if terminal_within_full and atr_ok else None
                row[f"target_{tag}_atr_hit_only_after_terminal"] = after_only if complete and atr_ok else None
                row[f"target_{tag}_atr_active_zone_category"] = category
            rows.append(row)
    return rows


def compute_wilder_atr(frame: pd.DataFrame, length: int = 14) -> tuple[float | None, ...]:
    """SMA-seeded Wilder ATR used by the offline zone scoring helper."""
    data = _normalize_frame(frame)
    if length < 1:
        raise ValueError("length must be positive")
    high, low, close = data.high.astype(float).tolist(), data.low.astype(float).tolist(), data.close.astype(float).tolist()
    trs = []
    for i, (h, l) in enumerate(zip(high, low)):
        value = h - l
        if i:
            value = max(value, abs(h - close[i - 1]), abs(l - close[i - 1]))
        trs.append(max(0.0, value))
    out: list[float | None] = [None] * len(trs)
    seed: list[float] = []
    previous = None
    for i, value in enumerate(trs):
        if previous is None:
            seed.append(value)
            if len(seed) < length:
                continue
            previous = sum(seed[-length:]) / length
            out[i] = previous
        else:
            previous = (previous * (length - 1) + value) / length
            out[i] = previous
    return tuple(out)


def _episode_groups_by_zone(episodes: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for episode in episodes:
        out[episode["zone_id"]].append(episode)
    return out
