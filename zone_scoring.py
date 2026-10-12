"""Isolated FVG/OB measurement prototype; not wired into the live scan path.

Input frames must already contain completed OHLCV bars (normally the output of
Formation-Bot's existing ``tamamlanmis_mumlar`` filter). This module clips bars
later than ``as_of``, replays the existing domain engines without changing them,
and measures descriptive zone components. It performs no I/O, fetch, alert, or
persistence operation.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Any, Mapping

import pandas as pd


SUPPORTED_TIMEFRAMES = ("1h", "2h", "4h", "1d")
FVG_TIMEFRAMES = frozenset({"2h", "4h", "1d"})
ATR_LENGTH = 14
DEFAULT_REACTION_HORIZON_BARS = 10
ISTANBUL_TZ = "Europe/Istanbul"


@dataclass(frozen=True, slots=True)
class ReactionSample:
    """One completed touch-response observation, measured only after the touch."""

    touch_start: pd.Timestamp
    touch_end: pd.Timestamp
    bars_observed: int
    favorable_excursion_atr: float
    adverse_excursion_atr: float
    window_end_reason: str


@dataclass(frozen=True, slots=True)
class ZoneMetrics:
    """One native FVG/OB region plus separate, non-probabilistic measurements."""

    zone_id: str
    symbol: str
    zone_type: str
    timeframe: str
    direction: str
    lower: float
    upper: float
    original_lower: float
    original_upper: float
    formation_time: pd.Timestamp | None
    available_at: pd.Timestamp | None
    native_status: str
    native_active: bool
    invalidated: bool | None
    terminal_at: pd.Timestamp | None
    terminal_reason: str | None
    current_price: float | None
    atr: float | None
    distance_atr: float | None
    touch_count: int
    reaction_sample_count: int
    censored_touch_count: int
    median_favorable_excursion_atr: float | None
    median_adverse_excursion_atr: float | None
    max_favorable_excursion_atr: float | None
    reaction_samples: tuple[ReactionSample, ...]
    sample_status: str
    proximity_rank_percentile: float | None = None
    proximity_rank_n: int = 0
    probability: float | None = None
    probability_status: str = "NOT_CALIBRATED"


@dataclass(frozen=True, slots=True)
class TimeframeReadiness:
    timeframe: str
    completed_bar_count: int
    first_bar: pd.Timestamp | None
    last_bar: pd.Timestamp | None
    fvg_status: str
    fvg_zone_count: int
    ob_status: str
    ob_zone_count: int
    ob_active_zone_count: int


@dataclass(frozen=True, slots=True)
class MtfOverlap:
    symbol: str
    left_zone_id: str
    right_zone_id: str
    left_type: str
    right_type: str
    left_timeframe: str
    right_timeframe: str
    direction_agrees: bool
    intersection_over_union: float
    interval_gap: float
    normalized_gap_atr: float | None
    normalized_center_distance_atr: float | None
    same_price_region: bool


@dataclass(frozen=True, slots=True)
class TimeframeStrength:
    timeframe: str
    zone_type: str
    active_zone_count: int
    touch_count: int
    completed_reaction_samples: int
    median_favorable_excursion_atr: float | None
    median_adverse_excursion_atr: float | None
    sample_status: str


@dataclass(frozen=True, slots=True)
class SymbolZoneAnalysis:
    symbol: str
    as_of: pd.Timestamp
    current_price: float | None
    readiness: tuple[TimeframeReadiness, ...]
    zones: tuple[ZoneMetrics, ...]


@dataclass(frozen=True, slots=True)
class UniverseZoneAnalysis:
    as_of: pd.Timestamp
    symbols: tuple[str, ...]
    symbol_analyses: tuple[SymbolZoneAnalysis, ...]
    zones: tuple[ZoneMetrics, ...]
    mtf_overlaps: tuple[MtfOverlap, ...]
    timeframe_strength: tuple[TimeframeStrength, ...]
    component_policy: str = "SEPARATE_DESCRIPTIVE_COMPONENTS_NO_COMPOSITE_NO_PROBABILITY"


@dataclass(slots=True)
class _ZoneBuilder:
    zone_id: str
    symbol: str
    zone_type: str
    timeframe: str
    direction: str
    original_lower: float
    original_upper: float
    formation_time: pd.Timestamp | None
    available_index: int
    native_status: str
    native_active: bool = True
    invalidated: bool | None = None
    terminal_index: int | None = None
    terminal_reason: str | None = None
    current_lower: float | None = None
    current_upper: float | None = None


@dataclass(frozen=True, slots=True)
class _TouchEpisode:
    start_index: int
    end_index: int


def _as_istanbul(value: Any) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        raise ValueError("timestamp cannot be NaT")
    if timestamp.tzinfo is None:
        return timestamp.tz_localize(ISTANBUL_TZ)
    return timestamp.tz_convert(ISTANBUL_TZ)


def _is_true_flag(value: Any) -> bool:
    try:
        return bool(value == True)  # noqa: E712 - accepts Python/numpy boolean flags
    except (TypeError, ValueError):
        return False


def _normalize_completed_frame(
    frame: pd.DataFrame,
    *,
    as_of: pd.Timestamp,
    symbol: str,
    timeframe: str,
) -> pd.DataFrame:
    """Copy/validate OHLCV, sort by timestamp, and remove post-as-of rows.

    The caller is responsible for applying the repository's completed-bar
    filter first. This function cannot infer whether a provider's same-date
    daily candle is final from OHLCV values alone.
    """
    if not isinstance(frame, pd.DataFrame):
        raise TypeError(f"{symbol}/{timeframe}: expected a pandas DataFrame")
    data = frame.copy(deep=True)
    renamed = {
        column: column.lower()
        for column in data.columns
        if isinstance(column, str) and column != column.lower()
    }
    if renamed:
        data = data.rename(columns=renamed)
    if data.columns.has_duplicates:
        raise ValueError(f"{symbol}/{timeframe}: duplicate columns after lowercase mapping")

    if "timestamp" in data.columns:
        raw_timestamps = data["timestamp"].tolist()
    elif isinstance(data.index, pd.DatetimeIndex) or data.index.name == "timestamp":
        raw_timestamps = data.index.tolist()
    else:
        raise ValueError(f"{symbol}/{timeframe}: timestamp column or DatetimeIndex required")

    required = ("open", "high", "low", "close", "volume")
    missing = [column for column in required if column not in data.columns]
    if missing:
        raise ValueError(f"{symbol}/{timeframe}: missing OHLCV fields: {', '.join(missing)}")

    timestamps = (
        pd.DatetimeIndex([_as_istanbul(value) for value in raw_timestamps])
        if raw_timestamps
        else pd.DatetimeIndex([], tz=ISTANBUL_TZ)
    )
    data = data.reset_index(drop=True)
    data["timestamp"] = timestamps
    data = data.sort_values("timestamp", kind="stable").reset_index(drop=True)
    # Apply the point-in-time boundary before inspecting any OHLCV values so a
    # future candle cannot affect validation, lifecycle state, or measurements.
    data = data.loc[data["timestamp"] <= as_of].reset_index(drop=True)
    if data["timestamp"].duplicated().any():
        raise ValueError(f"{symbol}/{timeframe}: duplicate timestamps are not scoreable")
    for flag in ("is_closed", "is_complete"):
        if flag in data.columns and not data[flag].map(_is_true_flag).all():
            raise ValueError(f"{symbol}/{timeframe}: input contains a non-completed {flag} bar")

    data = data.loc[:, ["timestamp", *required]].copy()
    for column in required:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    try:
        finite_ohlcv = all(
            math.isfinite(float(value))
            for column in required
            for value in data[column].tolist()
        )
    except (TypeError, ValueError, OverflowError):
        finite_ohlcv = False
    if not finite_ohlcv:
        raise ValueError(f"{symbol}/{timeframe}: non-finite OHLCV row")
    invalid_geometry = (
        (data["high"] < data[["open", "close"]].max(axis=1))
        | (data["low"] > data[["open", "close"]].min(axis=1))
        | (data["high"] < data["low"])
        | (data[["open", "high", "low", "close"]].min(axis=1) <= 0)
        | (data["volume"] < 0)
    )
    if invalid_geometry.any():
        raise ValueError(f"{symbol}/{timeframe}: invalid OHLCV geometry")

    return data.loc[data["timestamp"] <= as_of].reset_index(drop=True)


def wilder_atr(frame: pd.DataFrame, length: int = ATR_LENGTH) -> tuple[float | None, ...]:
    """Calculate the existing FVG engine's SMA-seeded Wilder RMA of true range."""
    if length < 1:
        raise ValueError("ATR length must be positive")
    if frame.empty:
        return ()
    high = frame["high"].astype(float).tolist()
    low = frame["low"].astype(float).tolist()
    close = frame["close"].astype(float).tolist()
    true_ranges: list[float] = []
    for index, (bar_high, bar_low) in enumerate(zip(high, low)):
        value = bar_high - bar_low
        if index:
            value = max(value, abs(bar_high - close[index - 1]), abs(bar_low - close[index - 1]))
        true_ranges.append(max(value, 0.0))

    result: list[float | None] = [None] * len(true_ranges)
    seed: list[float] = []
    previous: float | None = None
    for index, value in enumerate(true_ranges):
        if previous is None:
            seed.append(value)
            if len(seed) < length:
                continue
            previous = sum(seed[-length:]) / length
            result[index] = previous
        else:
            previous = (previous * (length - 1) + value) / length
            result[index] = previous
    return tuple(result)


def _zone_key_from_fvg(record: Any) -> tuple[Any, ...]:
    direction = int(record.direction)
    return (
        direction,
        int(record.formation_index),
        float(record.lower_boundary),
        float(record.upper_boundary),
    )


def _fvg_remaining_bounds(record: Any) -> tuple[float, float]:
    lower = float(record.lower_boundary)
    upper = float(record.upper_boundary)
    fill = min(1.0, max(0.0, float(record.maximum_fill_ratio)))
    if int(record.direction) > 0:
        return lower, max(lower, upper - float(record.gap_size) * fill)
    return min(upper, lower + float(record.gap_size) * fill), upper


def _zone_id(
    symbol: str,
    kind: str,
    timeframe: str,
    direction: str,
    available_index: int,
    lower: float,
    upper: float,
) -> str:
    return (
        f"{symbol}|{kind}|{timeframe}|{direction}|{available_index}|"
        f"{lower:.12g}|{upper:.12g}"
    )


def _capture_fvg_zones(
    symbol: str,
    timeframe: str,
    frame: pd.DataFrame,
    profile: str,
) -> tuple[list[_ZoneBuilder], str]:
    from domain_engines.fvg import (
        FvgEngulfingConfig,
        FvgEngulfingEngine,
        SensitivityProfile,
    )

    engine = FvgEngulfingEngine(
        FvgEngulfingConfig(
            timeframe=timeframe,
            sensitivity=SensitivityProfile(profile),
        )
    )
    builders: dict[tuple[Any, ...], _ZoneBuilder] = {}
    completed_seen: set[tuple[Any, ...]] = set()
    for index, row in enumerate(frame.to_dict("records")):
        engine.update(row)
        active_records = (engine.active_bullish_fvg, engine.active_bearish_fvg)
        for record in active_records:
            if record is None:
                continue
            key = _zone_key_from_fvg(record)
            direction = "bullish" if int(record.direction) > 0 else "bearish"
            if key not in builders:
                lower = float(record.lower_boundary)
                upper = float(record.upper_boundary)
                builders[key] = _ZoneBuilder(
                    zone_id=_zone_id(symbol, "FVG", timeframe, direction, index, lower, upper),
                    symbol=symbol,
                    zone_type="FVG",
                    timeframe=timeframe,
                    direction=direction,
                    original_lower=lower,
                    original_upper=upper,
                    formation_time=_as_istanbul(record.formation_time),
                    available_index=index,
                    native_status=record.state.name,
                    current_lower=lower,
                    current_upper=upper,
                )
            builder = builders[key]
            builder.native_active = True
            builder.native_status = record.state.name
            builder.current_lower, builder.current_upper = _fvg_remaining_bounds(record)
            builder.invalidated = bool(record.invalid)

        for record in engine.completed_fvg:
            key = _zone_key_from_fvg(record)
            if key in completed_seen:
                continue
            completed_seen.add(key)
            direction = "bullish" if int(record.direction) > 0 else "bearish"
            if key not in builders:
                lower = float(record.lower_boundary)
                upper = float(record.upper_boundary)
                builders[key] = _ZoneBuilder(
                    zone_id=_zone_id(symbol, "FVG", timeframe, direction, index, lower, upper),
                    symbol=symbol,
                    zone_type="FVG",
                    timeframe=timeframe,
                    direction=direction,
                    original_lower=lower,
                    original_upper=upper,
                    formation_time=_as_istanbul(record.formation_time),
                    available_index=index,
                    native_status=record.state.name,
                    native_active=False,
                    current_lower=lower,
                    current_upper=upper,
                )
            builder = builders[key]
            builder.native_active = False
            builder.native_status = record.state.name
            builder.invalidated = bool(record.invalid)
            builder.terminal_index = index
            builder.terminal_reason = str(record.invalid_reason or record.state.name)
            builder.current_lower = builder.original_lower
            builder.current_upper = builder.original_upper

    return list(builders.values()), engine.last_data_quality.value


def _ob_key(record: Any) -> tuple[Any, ...]:
    return (int(record.source_index), bool(record.bullish), float(record.top), float(record.bottom))


def _ordered_bounds(first: float, second: float) -> tuple[float, float]:
    """Convert the OB facade's (active_top, active_bottom) pair to low/high."""
    return min(float(first), float(second)), max(float(first), float(second))


def _ob_removal_reason(record: Any, row: Mapping[str, Any], fill_threshold: float) -> str:
    high = float(row["high"])
    low = float(row["low"])
    if record.bullish and high < float(record.bottom):
        return "gap_through"
    if not record.bullish and low > float(record.top):
        return "gap_through"
    entered = low <= float(record.top) and high >= float(record.bottom)
    if not entered:
        return "native_lifecycle_removed"
    if record.bullish:
        penetrated = max(float(record.bottom), min(float(record.top), low))
        boundary = min(float(record.fill_boundary), penetrated)
        ratio = (float(record.top) - boundary) / (float(record.top) - float(record.bottom))
    else:
        penetrated = min(float(record.top), max(float(record.bottom), high))
        boundary = max(float(record.fill_boundary), penetrated)
        ratio = (boundary - float(record.bottom)) / (float(record.top) - float(record.bottom))
    if ratio >= fill_threshold:
        return "fill_cancel_threshold"
    return "native_lifecycle_removed"


def _capture_ob_zones(
    symbol: str,
    timeframe: str,
    frame: pd.DataFrame,
) -> list[_ZoneBuilder]:
    from domain_engines.order_block import OrderBlockEngine

    engine = OrderBlockEngine()
    builders: dict[tuple[Any, ...], _ZoneBuilder] = {}
    previously_active: dict[tuple[Any, ...], Any] = {}
    for index, row in enumerate(frame.to_dict("records")):
        engine.update(row)
        current_active = {_ob_key(record): record for record in engine.active_records}

        for key, record in current_active.items():
            direction = "bullish" if record.bullish else "bearish"
            if key not in builders:
                lower = float(record.bottom)
                upper = float(record.top)
                builders[key] = _ZoneBuilder(
                    zone_id=_zone_id(symbol, "OB", timeframe, direction, index, lower, upper),
                    symbol=symbol,
                    zone_type="OB",
                    timeframe=timeframe,
                    direction=direction,
                    original_lower=lower,
                    original_upper=upper,
                    formation_time=(
                        _as_istanbul(record.source_time)
                        if record.source_time is not None else None
                    ),
                    available_index=index,
                    native_status="ACTIVE_OB",
                    current_lower=lower,
                    current_upper=upper,
                )
            builder = builders[key]
            builder.native_active = True
            builder.native_status = "ACTIVE_OB"
            builder.invalidated = False
            native_top, native_bottom = engine._active_remaining_zone(record)
            builder.current_lower, builder.current_upper = _ordered_bounds(native_top, native_bottom)

        for key, record in previously_active.items():
            if key in current_active:
                continue
            builder = builders[key]
            builder.native_active = False
            builder.invalidated = True
            builder.native_status = "REMOVED_BY_NATIVE_LIFECYCLE"
            builder.terminal_index = index
            builder.terminal_reason = _ob_removal_reason(
                record, row, engine.config.fill_cancel_threshold
            )
            builder.current_lower = builder.original_lower
            builder.current_upper = builder.original_upper

        previously_active = current_active

    return list(builders.values())


def _touch_episodes(
    frame: pd.DataFrame,
    lower: float,
    upper: float,
    *,
    first_index: int,
    last_index: int,
) -> tuple[_TouchEpisode, ...]:
    episodes: list[_TouchEpisode] = []
    start: int | None = None
    end: int | None = None
    for index in range(max(0, first_index), min(last_index, len(frame) - 1) + 1):
        touched = float(frame.at[index, "low"]) <= upper and float(frame.at[index, "high"]) >= lower
        if touched:
            if start is None:
                start = index
            end = index
        elif start is not None and end is not None:
            episodes.append(_TouchEpisode(start, end))
            start = end = None
    if start is not None and end is not None:
        episodes.append(_TouchEpisode(start, end))
    return tuple(episodes)


def _reaction_samples(
    frame: pd.DataFrame,
    atr: tuple[float | None, ...],
    builder: _ZoneBuilder,
    *,
    horizon: int,
) -> tuple[tuple[ReactionSample, ...], int, int]:
    last_index = builder.terminal_index if builder.terminal_index is not None else len(frame) - 1
    episodes = _touch_episodes(
        frame,
        builder.original_lower,
        builder.original_upper,
        first_index=builder.available_index + 1,
        last_index=last_index,
    )
    samples: list[ReactionSample] = []
    censored = 0
    for episode_index, episode in enumerate(episodes):
        reaction_start = episode.end_index + 1
        if reaction_start >= len(frame):
            censored += 1
            continue
        horizon_end = episode.end_index + horizon
        window_end = min(horizon_end, len(frame) - 1)
        reason = "horizon"
        terminal = builder.terminal_index
        if terminal is not None and terminal >= reaction_start and terminal < window_end:
            window_end = terminal
            reason = builder.terminal_reason or "native_terminal"
        next_touch = (
            episodes[episode_index + 1].start_index
            if episode_index + 1 < len(episodes) else None
        )
        if next_touch is not None and next_touch <= window_end:
            window_end = next_touch - 1
            reason = "next_touch"
        observed = window_end - reaction_start + 1
        atr_at_touch = atr[episode.end_index] if episode.end_index < len(atr) else None
        if observed <= 0 or atr_at_touch is None or not math.isfinite(atr_at_touch) or atr_at_touch <= 0:
            censored += 1
            continue

        complete = observed >= horizon or reason != "horizon"
        if not complete:
            censored += 1
            continue
        future = frame.iloc[reaction_start : window_end + 1]
        future_high = float(future["high"].max())
        future_low = float(future["low"].min())
        if builder.direction == "bullish":
            favorable = max(0.0, future_high - builder.original_upper) / atr_at_touch
            adverse = max(0.0, builder.original_lower - future_low) / atr_at_touch
        else:
            favorable = max(0.0, builder.original_lower - future_low) / atr_at_touch
            adverse = max(0.0, future_high - builder.original_upper) / atr_at_touch
        samples.append(
            ReactionSample(
                touch_start=_as_istanbul(frame.at[episode.start_index, "timestamp"]),
                touch_end=_as_istanbul(frame.at[episode.end_index, "timestamp"]),
                bars_observed=observed,
                favorable_excursion_atr=float(favorable),
                adverse_excursion_atr=float(adverse),
                window_end_reason=reason,
            )
        )
    return tuple(samples), len(episodes), censored


def _median(values: list[float]) -> float | None:
    return float(pd.Series(values, dtype="float64").median()) if values else None


def _zone_metrics(
    builder: _ZoneBuilder,
    frame: pd.DataFrame,
    atr: tuple[float | None, ...],
    *,
    current_price: float | None,
    horizon: int,
) -> ZoneMetrics:
    samples, touch_count, censored = _reaction_samples(frame, atr, builder, horizon=horizon)
    last_atr = atr[-1] if atr else None
    if last_atr is None or not math.isfinite(last_atr) or last_atr <= 0:
        last_atr = None
    if builder.native_active:
        lower = builder.current_lower if builder.current_lower is not None else builder.original_lower
        upper = builder.current_upper if builder.current_upper is not None else builder.original_upper
    else:
        lower, upper = builder.original_lower, builder.original_upper
    if current_price is None or last_atr is None:
        distance = None
    else:
        gap = max(lower - current_price, current_price - upper, 0.0)
        distance = float(gap / last_atr)
    favorable = [sample.favorable_excursion_atr for sample in samples]
    adverse = [sample.adverse_excursion_atr for sample in samples]
    return ZoneMetrics(
        zone_id=builder.zone_id,
        symbol=builder.symbol,
        zone_type=builder.zone_type,
        timeframe=builder.timeframe,
        direction=builder.direction,
        lower=float(lower),
        upper=float(upper),
        original_lower=float(builder.original_lower),
        original_upper=float(builder.original_upper),
        formation_time=builder.formation_time,
        available_at=(
            _as_istanbul(frame.at[builder.available_index, "timestamp"])
            if 0 <= builder.available_index < len(frame) else None
        ),
        native_status=builder.native_status,
        native_active=builder.native_active,
        invalidated=builder.invalidated,
        terminal_at=(
            _as_istanbul(frame.at[builder.terminal_index, "timestamp"])
            if builder.terminal_index is not None and 0 <= builder.terminal_index < len(frame)
            else None
        ),
        terminal_reason=builder.terminal_reason,
        current_price=current_price,
        atr=last_atr,
        distance_atr=distance,
        touch_count=touch_count,
        reaction_sample_count=len(samples),
        censored_touch_count=censored,
        median_favorable_excursion_atr=_median(favorable),
        median_adverse_excursion_atr=_median(adverse),
        max_favorable_excursion_atr=max(favorable) if favorable else None,
        reaction_samples=samples,
        sample_status="NO_COMPLETED_REACTION_SAMPLES" if not samples else "DESCRIPTIVE_ONLY",
    )


def _current_price(frames: Mapping[str, pd.DataFrame]) -> float | None:
    hourly = frames.get("1h")
    if hourly is not None and not hourly.empty:
        return float(hourly["close"].iloc[-1])
    latest = [frame for frame in frames.values() if not frame.empty]
    if not latest:
        return None
    last_frame = max(latest, key=lambda frame: frame["timestamp"].iloc[-1])
    return float(last_frame["close"].iloc[-1])


def analyze_symbol_completed_frames(
    symbol: str,
    completed_frames: Mapping[str, pd.DataFrame],
    *,
    as_of: Any | None = None,
    reaction_horizon_bars: int = DEFAULT_REACTION_HORIZON_BARS,
    fvg_profile: str = "Dengeli",
) -> SymbolZoneAnalysis:
    """Replay existing native FVG/OB engines over completed frames for one symbol.

    ``completed_frames`` must be prefiltered with the repository's current
    ``tamamlanmis_mumlar`` rules. ``as_of`` is an additional point-in-time cap;
    later timestamps are discarded before engine replay and reaction measurement.
    The default reaction window is at most ten bars of the zone's own timeframe.
    """
    if reaction_horizon_bars < 1:
        raise ValueError("reaction_horizon_bars must be at least 1")
    normalized_timeframes = {str(tf).lower(): frame for tf, frame in completed_frames.items()}
    unknown = sorted(set(normalized_timeframes) - set(SUPPORTED_TIMEFRAMES))
    if unknown:
        raise ValueError(f"unsupported Formation-Bot timeframe(s): {', '.join(unknown)}")

    prelim: dict[str, pd.DataFrame] = {
        tf: _normalize_completed_frame(
            frame,
            as_of=_as_istanbul(as_of) if as_of is not None else pd.Timestamp.max.tz_localize(ISTANBUL_TZ),
            symbol=symbol,
            timeframe=tf,
        )
        for tf, frame in normalized_timeframes.items()
    }
    if as_of is None:
        all_last = [frame["timestamp"].iloc[-1] for frame in prelim.values() if not frame.empty]
        if not all_last:
            raise ValueError(f"{symbol}: no completed OHLCV bars were supplied")
        cutoff = max(all_last)
    else:
        cutoff = _as_istanbul(as_of)

    frames = {
        tf: frame.loc[frame["timestamp"] <= cutoff].reset_index(drop=True)
        for tf, frame in prelim.items()
    }
    price = _current_price(frames)
    all_builders: list[_ZoneBuilder] = []
    readiness: list[TimeframeReadiness] = []
    atr_by_tf: dict[str, tuple[float | None, ...]] = {}

    for timeframe in SUPPORTED_TIMEFRAMES:
        frame = frames.get(timeframe)
        if frame is None:
            continue
        atr = wilder_atr(frame)
        atr_by_tf[timeframe] = atr
        fvg_status = "UNSUPPORTED_TIMEFRAME"
        fvg_count = 0
        if timeframe in FVG_TIMEFRAMES:
            fvg_builders, fvg_status = _capture_fvg_zones(symbol, timeframe, frame, fvg_profile)
            fvg_count = len(fvg_builders)
            all_builders.extend(fvg_builders)
        ob_builders = _capture_ob_zones(symbol, timeframe, frame)
        all_builders.extend(ob_builders)
        readiness.append(
            TimeframeReadiness(
                timeframe=timeframe,
                completed_bar_count=len(frame),
                first_bar=frame["timestamp"].iloc[0] if not frame.empty else None,
                last_bar=frame["timestamp"].iloc[-1] if not frame.empty else None,
                fvg_status=fvg_status,
                fvg_zone_count=fvg_count,
                ob_status="NO_BARS" if frame.empty else "ENGINE_HAS_NO_MINIMUM_HISTORY_GATE",
                ob_zone_count=len(ob_builders),
                ob_active_zone_count=sum(builder.native_active for builder in ob_builders),
            )
        )

    by_timeframe = {tf: frames[tf] for tf in frames}
    metrics: list[ZoneMetrics] = []
    for builder in all_builders:
        frame = by_timeframe[builder.timeframe]
        metrics.append(
            _zone_metrics(
                builder,
                frame,
                atr_by_tf[builder.timeframe],
                current_price=price,
                horizon=reaction_horizon_bars,
            )
        )
    if as_of is None:
        resolved_as_of = cutoff
    else:
        resolved_as_of = cutoff
    return SymbolZoneAnalysis(
        symbol=symbol,
        as_of=resolved_as_of,
        current_price=price,
        readiness=tuple(readiness),
        zones=tuple(metrics),
    )


def _proximity_ranks(zones: tuple[ZoneMetrics, ...]) -> tuple[ZoneMetrics, ...]:
    groups: dict[tuple[str, str, str], list[int]] = {}
    for index, zone in enumerate(zones):
        if zone.native_active and zone.distance_atr is not None:
            groups.setdefault((zone.zone_type, zone.timeframe, zone.direction), []).append(index)
    ranked = list(zones)
    for indices in groups.values():
        values = [float(zones[index].distance_atr) for index in indices]
        population = len(values)
        for index, value in zip(indices, values):
            if population < 2:
                percentile = None
            else:
                below = sum(other < value for other in values)
                equal = sum(other == value for other in values)
                ascending_midrank = below + (equal - 1) / 2.0
                percentile = 100.0 * (1.0 - ascending_midrank / (population - 1))
            ranked[index] = replace(
                zones[index],
                proximity_rank_percentile=percentile,
                proximity_rank_n=population,
            )
    return tuple(ranked)


def _mtf_overlaps(zones: tuple[ZoneMetrics, ...]) -> tuple[MtfOverlap, ...]:
    active = [zone for zone in zones if zone.native_active]
    output: list[MtfOverlap] = []
    for left_index, left in enumerate(active):
        for right in active[left_index + 1 :]:
            if left.symbol != right.symbol or left.timeframe == right.timeframe:
                continue
            lower = max(left.lower, right.lower)
            upper = min(left.upper, right.upper)
            intersection = max(0.0, upper - lower)
            union = max(left.upper, right.upper) - min(left.lower, right.lower)
            overlap = intersection / union if union > 0 else 0.0
            gap = max(0.0, max(left.lower, right.lower) - min(left.upper, right.upper))
            scale = (
                math.sqrt(left.atr * right.atr)
                if left.atr is not None and right.atr is not None and left.atr > 0 and right.atr > 0
                else None
            )
            left_mid = (left.lower + left.upper) / 2.0
            right_mid = (right.lower + right.upper) / 2.0
            output.append(
                MtfOverlap(
                    symbol=left.symbol,
                    left_zone_id=left.zone_id,
                    right_zone_id=right.zone_id,
                    left_type=left.zone_type,
                    right_type=right.zone_type,
                    left_timeframe=left.timeframe,
                    right_timeframe=right.timeframe,
                    direction_agrees=left.direction == right.direction,
                    intersection_over_union=float(overlap),
                    interval_gap=float(gap),
                    normalized_gap_atr=float(gap / scale) if scale else None,
                    normalized_center_distance_atr=(
                        float(abs(left_mid - right_mid) / scale) if scale else None
                    ),
                    same_price_region=intersection > 0,
                )
            )
    return tuple(output)


def _timeframe_strength(zones: tuple[ZoneMetrics, ...]) -> tuple[TimeframeStrength, ...]:
    keys = sorted({(zone.timeframe, zone.zone_type) for zone in zones})
    output: list[TimeframeStrength] = []
    for timeframe, zone_type in keys:
        selected = [zone for zone in zones if zone.timeframe == timeframe and zone.zone_type == zone_type]
        samples = [sample for zone in selected for sample in zone.reaction_samples]
        output.append(
            TimeframeStrength(
                timeframe=timeframe,
                zone_type=zone_type,
                active_zone_count=sum(zone.native_active for zone in selected),
                touch_count=sum(zone.touch_count for zone in selected),
                completed_reaction_samples=len(samples),
                median_favorable_excursion_atr=_median(
                    [sample.favorable_excursion_atr for sample in samples]
                ),
                median_adverse_excursion_atr=_median(
                    [sample.adverse_excursion_atr for sample in samples]
                ),
                sample_status="NO_COMPLETED_REACTION_SAMPLES" if not samples else "DESCRIPTIVE_ONLY",
            )
        )
    return tuple(output)


def analyze_universe_completed_frames(
    frames_by_symbol: Mapping[str, Mapping[str, pd.DataFrame]],
    *,
    as_of: Any | None = None,
    reaction_horizon_bars: int = DEFAULT_REACTION_HORIZON_BARS,
    fvg_profile: str = "Dengeli",
) -> UniverseZoneAnalysis:
    """Analyze explicitly supplied symbols at one common cutoff.

    This API never reads ``ACTIVE_STOCKS`` and requires a shared ``as_of`` so
    cross-symbol ranks cannot silently compare different dates.
    """
    if not frames_by_symbol:
        raise ValueError("frames_by_symbol cannot be empty")
    if as_of is None:
        raise ValueError("a common as_of timestamp is required for universe analysis")
    analyses = tuple(
        analyze_symbol_completed_frames(
            symbol,
            frames,
            as_of=as_of,
            reaction_horizon_bars=reaction_horizon_bars,
            fvg_profile=fvg_profile,
        )
        for symbol, frames in frames_by_symbol.items()
    )
    all_zones = _proximity_ranks(
        tuple(zone for analysis in analyses for zone in analysis.zones)
    )
    ranked_by_id = {zone.zone_id: zone for zone in all_zones}
    ranked_analyses = tuple(
        replace(
            analysis,
            zones=tuple(ranked_by_id[zone.zone_id] for zone in analysis.zones),
        )
        for analysis in analyses
    )
    return UniverseZoneAnalysis(
        as_of=_as_istanbul(as_of),
        symbols=tuple(analysis.symbol for analysis in ranked_analyses),
        symbol_analyses=ranked_analyses,
        zones=all_zones,
        mtf_overlaps=_mtf_overlaps(all_zones),
        timeframe_strength=_timeframe_strength(all_zones),
    )
