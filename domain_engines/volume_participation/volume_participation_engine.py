from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import sqrt
from typing import Any

import pandas as pd

from .base import BaseEngine
from .models import Direction, EngineResult


class VolumeLevel(StrEnum):
    UNAVAILABLE = "UNAVAILABLE"
    VERY_LOW = "VERY_LOW"
    LOW = "LOW"
    NORMAL = "NORMAL"
    RISING = "RISING"
    HIGH = "HIGH"
    ABNORMAL = "ABNORMAL"


class ParticipationState(StrEnum):
    PENDING = "PARTICIPATION_PENDING"
    VOLUME_UNAVAILABLE = "PARTICIPATION_VOLUME_UNAVAILABLE"
    NEUTRAL = "PARTICIPATION_NEUTRAL"
    UP_CANDIDATE = "PARTICIPATION_UP_CANDIDATE"
    DOWN_CANDIDATE = "PARTICIPATION_DOWN_CANDIDATE"
    UP_CONFIRMED = "PARTICIPATION_UP_CONFIRMED"
    DOWN_CONFIRMED = "PARTICIPATION_DOWN_CONFIRMED"
    CONFLICT = "PARTICIPATION_CONFLICT"


class EffortResultClass(StrEnum):
    NEUTRAL = "NEUTRAL"
    RISING_EFFORT_STRONG_RESULT = "RISING_EFFORT_STRONG_RESULT"
    HIGH_EFFORT_STRONG_RESULT = "HIGH_EFFORT_STRONG_RESULT"
    HIGH_EFFORT_WEAK_RESULT = "HIGH_EFFORT_WEAK_RESULT"
    VERY_HIGH_EFFORT_WEAK_RESULT = "VERY_HIGH_EFFORT_WEAK_RESULT"


@dataclass(frozen=True, slots=True)
class VolumeParticipationConfig:
    minimum_history: int = 150
    atr_length: int = 14
    volume_short_length: int = 5
    volume_average_length: int = 20
    volume_long_length: int = 50
    percentile_length: int = 100
    slope_lookback: int = 3
    persistence_length: int = 5
    flow_short_length: int = 5
    flow_medium_length: int = 10
    progress_lookback: int = 3
    minimum_nonzero_volume_share: float = 0.70

    very_low_rvol: float = 0.60
    low_rvol: float = 0.75
    rising_rvol: float = 1.20
    high_rvol: float = 1.50
    abnormal_rvol: float = 2.25
    high_volume_z: float = 1.25
    abnormal_volume_z: float = 2.25
    high_percent_rank: float = 80.0
    abnormal_percent_rank: float = 95.0
    minimum_volume_slope: float = 0.025

    very_low_rtv: float = 0.60
    low_rtv: float = 0.75
    rising_rtv: float = 1.16
    high_rtv: float = 1.48
    abnormal_rtv: float = 2.20
    high_capital_z: float = 1.20
    abnormal_capital_z: float = 2.20
    minimum_capital_slope: float = 0.025

    minimum_capital_pressure: float = 0.13
    minimum_directional_share: float = 0.60
    minimum_progress_atr: float = 0.45
    minimum_efficiency: float = 0.52
    minimum_body_atr: float = 0.40
    up_close_location: float = 0.65
    down_close_location: float = 0.35
    maximum_directional_wick_ratio: float = 0.30
    minimum_directional_close_share: float = 0.60
    participation_minimum_evidence: int = 6
    participation_confirmation_bars: int = 2
    confirmation_minimum_rvol: float = 0.92
    confirmation_minimum_rtv: float = 0.92
    weak_result_progress_limit: float = 0.28
    weak_result_efficiency_limit: float = 0.38


@dataclass(frozen=True, slots=True)
class VolumeParticipationMetrics:
    data_ready: bool = False
    volume_usable: bool = False
    capital_usable: bool = False
    rvol: float | None = None
    volume_z_score: float | None = None
    volume_percent_rank: float | None = None
    volume_slope: float | None = None
    volume_regime: int = 0
    volume_level: VolumeLevel = VolumeLevel.UNAVAILABLE
    rtv: float | None = None
    capital_z_score: float | None = None
    capital_percent_rank: float | None = None
    capital_slope: float | None = None
    capital_regime: int = 0
    capital_level: VolumeLevel = VolumeLevel.UNAVAILABLE
    up_volume_share_5: float | None = None
    down_volume_share_5: float | None = None
    up_capital_share_10: float | None = None
    down_capital_share_10: float | None = None
    directional_value_pressure_5: float | None = None
    directional_value_pressure_10: float | None = None
    net_progress_atr: float | None = None
    path_distance_atr: float | None = None
    directional_efficiency: float | None = None
    volume_result_efficiency: float | None = None
    capital_result_efficiency: float | None = None
    effort_result_class: EffortResultClass = EffortResultClass.NEUTRAL
    up_evidence_count: int = 0
    down_evidence_count: int = 0
    up_candidate: bool = False
    down_candidate: bool = False
    up_confirmed: bool = False
    down_confirmed: bool = False


@dataclass(frozen=True, slots=True)
class ParticipationExport:
    state: str | None = None
    direction: int = 0
    quality: float | None = None
    magnitude_quality: float | None = None
    rvol: float | None = None
    volume_level: str | None = None
    volume_regime: int = 0
    relative_traded_value: float | None = None
    capital_level: str | None = None
    capital_regime: int = 0
    directional_value_pressure_5: float | None = None
    directional_value_pressure_10: float | None = None
    up_capital_share_10: float | None = None
    down_capital_share_10: float | None = None
    net_progress_atr: float | None = None
    directional_efficiency: float | None = None
    volume_result_efficiency: float | None = None
    capital_result_efficiency: float | None = None
    effort_result_class: str | None = None
    up_evidence_count: int = 0
    down_evidence_count: int = 0


def _safe_div(num: float, den: float, default: float = 0.0) -> float:
    return default if abs(den) <= 1e-12 else num / den


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _sma(values: list[float], length: int) -> float | None:
    if len(values) < length:
        return None
    return sum(values[-length:]) / length


def _ema_series(values: list[float], length: int) -> list[float]:
    if not values:
        return []
    alpha = 2.0 / (length + 1.0)
    out = [values[0]]
    for value in values[1:]:
        out.append(alpha * value + (1.0 - alpha) * out[-1])
    return out


def _population_std(values: list[float], length: int) -> float | None:
    if len(values) < length:
        return None
    sample = values[-length:]
    mean = sum(sample) / length
    return sqrt(sum((value - mean) ** 2 for value in sample) / length)


def _percent_rank(values: list[float], length: int) -> float | None:
    if len(values) < length:
        return None
    sample = values[-length:]
    current = sample[-1]
    if length <= 1:
        return 100.0
    count = sum(1 for value in sample[:-1] if value <= current)
    return count / (length - 1) * 100.0


def _rma(values: list[float], length: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) < length:
        return out
    seed = sum(values[:length]) / length
    out[length - 1] = seed
    previous = seed
    for index in range(length, len(values)):
        previous = (previous * (length - 1) + values[index]) / length
        out[index] = previous
    return out


def _rolling_relative(values: list[float], length: int) -> list[float | None]:
    """Reference batch implementation kept for parity tests and audit."""

    out: list[float | None] = []
    for end in range(1, len(values) + 1):
        average = _sma(values[:end], length)
        out.append(_safe_div(values[end - 1], average) if average else None)
    return out


def _classify_level(
    value: float,
    slope: float,
    z_score: float,
    percentile: float,
    *,
    very_low: float,
    low: float,
    rising: float,
    high: float,
    abnormal: float,
    high_z: float,
    abnormal_z: float,
    high_percentile: float,
    abnormal_percentile: float,
    minimum_slope: float,
) -> VolumeLevel:
    if value >= abnormal and (z_score >= abnormal_z or percentile >= abnormal_percentile):
        return VolumeLevel.ABNORMAL
    if value >= high and (z_score >= high_z or percentile >= high_percentile):
        return VolumeLevel.HIGH
    if value >= rising and slope >= minimum_slope:
        return VolumeLevel.RISING
    if value < very_low:
        return VolumeLevel.VERY_LOW
    if value < low:
        return VolumeLevel.LOW
    return VolumeLevel.NORMAL


def _regime(short_long_ratio: float, slope: float, minimum_slope: float) -> int:
    if short_long_ratio >= 1.20 and slope > 0.0:
        return 2
    if short_long_ratio >= 1.05 or slope > minimum_slope:
        return 1
    if short_long_ratio <= 0.85 and slope < 0.0:
        return -2
    if short_long_ratio < 0.95 or slope < -minimum_slope:
        return -1
    return 0


class VolumeParticipationEngine(BaseEngine):
    name = "volume_participation_absorption"

    def __init__(self, config: VolumeParticipationConfig | None = None) -> None:
        self.config = config or VolumeParticipationConfig()
        self._rows: list[dict[str, Any]] = []
        self._metrics_history: list[VolumeParticipationMetrics] = []
        self._snapshot: EngineResult | None = None
        self.export_contract = ParticipationExport()
        self._reset_runtime_series()

    def _reset_runtime_series(self) -> None:
        self._open_values: list[float] = []
        self._high_values: list[float] = []
        self._low_values: list[float] = []
        self._close_values: list[float] = []
        self._volume_values: list[float] = []
        self._traded_values: list[float] = []
        self._true_range_values: list[float] = []
        self._atr_values: list[float | None] = []
        self._volume_ema_values: list[float] = []
        self._capital_ema_values: list[float] = []
        self._rvol_values: list[float | None] = []
        self._rtv_values: list[float | None] = []
        self._nonzero_volume_flags: list[float] = []
        self._close_locations: list[float] = []
        self._signed_traded_values: list[float] = []
        self._up_volume_values: list[float] = []
        self._down_volume_values: list[float] = []
        self._up_capital_values: list[float] = []
        self._down_capital_values: list[float] = []
        self._higher_close_flags: list[float] = []
        self._lower_close_flags: list[float] = []

    def _reset(self) -> None:
        self._rows = []
        self._metrics_history = []
        self._snapshot = None
        self.export_contract = ParticipationExport()
        self._reset_runtime_series()

    @staticmethod
    def _append_ema(history: list[float], value: float, length: int) -> None:
        if not history:
            history.append(value)
            return
        alpha = 2.0 / (length + 1.0)
        history.append(alpha * value + (1.0 - alpha) * history[-1])

    @staticmethod
    def _append_relative(history: list[float | None], values: list[float], length: int) -> None:
        average = _sma(values, length)
        history.append(_safe_div(values[-1], average) if average else None)

    def _append_runtime_series(self, row: dict[str, Any]) -> None:
        open_ = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        volume = float(row["volume"])
        previous_close = self._close_values[-1] if self._close_values else None

        self._open_values.append(open_)
        self._high_values.append(high)
        self._low_values.append(low)
        self._close_values.append(close)
        self._volume_values.append(volume)

        traded_value = volume * ((high + low + close) / 3.0)
        self._traded_values.append(traded_value)

        tr = high - low
        if previous_close is not None:
            tr = max(tr, abs(high - previous_close), abs(low - previous_close))
        self._true_range_values.append(tr)

        atr_length = self.config.atr_length
        count = len(self._true_range_values)
        if count < atr_length:
            atr = None
        elif count == atr_length:
            atr = sum(self._true_range_values[:atr_length]) / atr_length
        else:
            previous_atr = self._atr_values[-1]
            if previous_atr is None:
                atr = sum(self._true_range_values[-atr_length:]) / atr_length
            else:
                atr = (previous_atr * (atr_length - 1) + tr) / atr_length
        self._atr_values.append(atr)

        self._append_ema(self._volume_ema_values, volume, self.config.volume_short_length)
        self._append_ema(self._capital_ema_values, traded_value, self.config.volume_short_length)
        self._append_relative(self._rvol_values, self._volume_values, self.config.volume_average_length)
        self._append_relative(self._rtv_values, self._traded_values, self.config.volume_average_length)
        self._nonzero_volume_flags.append(1.0 if volume > 0.0 else 0.0)

        close_location = _safe_div(close - low, high - low, 0.5)
        self._close_locations.append(close_location)
        self._signed_traded_values.append(
            traded_value * _clamp(close_location * 2.0 - 1.0, -1.0, 1.0)
        )

        up = previous_close is not None and close > previous_close
        down = previous_close is not None and close < previous_close
        self._up_volume_values.append(volume if up else 0.0)
        self._down_volume_values.append(volume if down else 0.0)
        self._up_capital_values.append(traded_value if up else 0.0)
        self._down_capital_values.append(traded_value if down else 0.0)
        self._higher_close_flags.append(1.0 if up else 0.0)
        self._lower_close_flags.append(1.0 if down else 0.0)

    def _calculate(self) -> VolumeParticipationMetrics:
        c = self.config
        n = len(self._rows)
        if not n:
            return VolumeParticipationMetrics()

        opens = self._open_values
        highs = self._high_values
        lows = self._low_values
        closes = self._close_values
        volumes = self._volume_values
        traded_values = self._traded_values
        atr_series = self._atr_values
        volume_ema = self._volume_ema_values
        capital_ema = self._capital_ema_values
        rvol_series = self._rvol_values
        rtv_series = self._rtv_values

        atr = atr_series[-1]
        prior_atr = atr_series[-2] if n > 1 else None

        volume_average = _sma(volumes, c.volume_average_length)
        volume_long_average = _sma(volumes, c.volume_long_length)
        volume_std = _population_std(volumes, c.volume_long_length)
        volume_percentile = _percent_rank(volumes, c.percentile_length)
        volume_slope = (
            None
            if not volume_average or len(volume_ema) <= c.slope_lookback
            else _safe_div(volume_ema[-1] - volume_ema[-1 - c.slope_lookback], volume_average)
        )
        nonzero_share = _sma(self._nonzero_volume_flags, c.volume_average_length)
        volume_usable = bool(
            volume_average
            and volume_average > 0.0
            and nonzero_share is not None
            and nonzero_share >= c.minimum_nonzero_volume_share
        )

        capital_average = _sma(traded_values, c.volume_average_length)
        capital_long_average = _sma(traded_values, c.volume_long_length)
        capital_std = _population_std(traded_values, c.volume_long_length)
        capital_percentile = _percent_rank(traded_values, c.percentile_length)
        capital_slope = (
            None
            if not capital_average or len(capital_ema) <= c.slope_lookback
            else _safe_div(capital_ema[-1] - capital_ema[-1 - c.slope_lookback], capital_average)
        )
        capital_usable = bool(
            volume_usable
            and capital_average
            and capital_average > 0.0
            and capital_long_average
            and capital_long_average > 0.0
        )

        history_ready = (
            n >= c.minimum_history
            and atr is not None
            and prior_atr is not None
            and n > c.progress_lookback
        )
        metrics_ready = all(
            value is not None
            for value in (
                volume_average,
                volume_long_average,
                volume_std,
                volume_percentile,
                volume_slope,
                capital_average,
                capital_long_average,
                capital_std,
                capital_percentile,
                capital_slope,
            )
        )
        data_ready = bool(history_ready and metrics_ready and volume_usable and capital_usable)
        if not data_ready:
            return VolumeParticipationMetrics(
                volume_usable=volume_usable,
                capital_usable=capital_usable,
            )

        assert volume_average is not None
        assert volume_long_average is not None
        assert volume_std is not None
        assert volume_percentile is not None
        assert volume_slope is not None
        assert capital_average is not None
        assert capital_long_average is not None
        assert capital_std is not None
        assert capital_percentile is not None
        assert capital_slope is not None
        assert atr is not None and prior_atr is not None

        rvol = rvol_series[-1] or 0.0
        rtv = rtv_series[-1] or 0.0
        volume_z = _safe_div(volumes[-1] - volume_long_average, volume_std) if volume_std > 1e-12 else 0.0
        capital_z = _safe_div(traded_values[-1] - capital_long_average, capital_std) if capital_std > 1e-12 else 0.0
        volume_short_long = _safe_div(volume_ema[-1], volume_long_average)
        capital_short_long = _safe_div(capital_ema[-1], capital_long_average)

        volume_level = _classify_level(
            rvol,
            volume_slope,
            volume_z,
            volume_percentile,
            very_low=c.very_low_rvol,
            low=c.low_rvol,
            rising=c.rising_rvol,
            high=c.high_rvol,
            abnormal=c.abnormal_rvol,
            high_z=c.high_volume_z,
            abnormal_z=c.abnormal_volume_z,
            high_percentile=c.high_percent_rank,
            abnormal_percentile=c.abnormal_percent_rank,
            minimum_slope=c.minimum_volume_slope,
        )
        capital_level = _classify_level(
            rtv,
            capital_slope,
            capital_z,
            capital_percentile,
            very_low=c.very_low_rtv,
            low=c.low_rtv,
            rising=c.rising_rtv,
            high=c.high_rtv,
            abnormal=c.abnormal_rtv,
            high_z=c.high_capital_z,
            abnormal_z=c.abnormal_capital_z,
            high_percentile=c.high_percent_rank,
            abnormal_percentile=c.abnormal_percent_rank,
            minimum_slope=c.minimum_capital_slope,
        )
        volume_regime = _regime(volume_short_long, volume_slope, c.minimum_volume_slope)
        capital_regime = _regime(capital_short_long, capital_slope, c.minimum_capital_slope)

        volume5 = _sma(volumes, c.flow_short_length) or 0.0
        capital5 = _sma(traded_values, c.flow_short_length) or 0.0
        capital10 = _sma(traded_values, c.flow_medium_length) or 0.0
        up_volume_share5 = _safe_div(
            _sma(self._up_volume_values, c.flow_short_length) or 0.0,
            volume5,
            0.50,
        )
        down_volume_share5 = _safe_div(
            _sma(self._down_volume_values, c.flow_short_length) or 0.0,
            volume5,
            0.50,
        )
        up_capital_share10 = _safe_div(
            _sma(self._up_capital_values, c.flow_medium_length) or 0.0,
            capital10,
            0.50,
        )
        down_capital_share10 = _safe_div(
            _sma(self._down_capital_values, c.flow_medium_length) or 0.0,
            capital10,
            0.50,
        )
        pressure5 = _clamp(
            _safe_div(_sma(self._signed_traded_values, c.flow_short_length) or 0.0, capital5),
            -1.0,
            1.0,
        )
        pressure10 = _clamp(
            _safe_div(_sma(self._signed_traded_values, c.flow_medium_length) or 0.0, capital10),
            -1.0,
            1.0,
        )

        recent_atrs = [value for value in atr_series[-c.progress_lookback :] if value is not None]
        progress_atr_reference = (
            sum(recent_atrs) / len(recent_atrs) if recent_atrs else prior_atr
        )
        net_progress = closes[-1] - closes[-1 - c.progress_lookback]
        net_progress_atr = _safe_div(net_progress, progress_atr_reference)
        absolute_path = sum(
            abs(closes[i] - closes[i - 1])
            for i in range(n - c.progress_lookback, n)
        )
        path_distance_atr = _safe_div(absolute_path, progress_atr_reference)
        directional_efficiency = _clamp(
            _safe_div(abs(net_progress), absolute_path),
            0.0,
            1.0,
        )

        progress_rvol_values = [
            value for value in rvol_series[-c.progress_lookback :] if value is not None
        ]
        progress_rtv_values = [
            value for value in rtv_series[-c.progress_lookback :] if value is not None
        ]
        progress_rvol = (
            sum(progress_rvol_values) / len(progress_rvol_values)
            if progress_rvol_values
            else rvol
        )
        progress_rtv = (
            sum(progress_rtv_values) / len(progress_rtv_values)
            if progress_rtv_values
            else rtv
        )
        volume_result_efficiency = _safe_div(abs(net_progress_atr), max(progress_rvol, 0.10))
        capital_result_efficiency = _safe_div(abs(net_progress_atr), max(progress_rtv, 0.10))

        close_location = self._close_locations[-1]
        total_range = highs[-1] - lows[-1]
        body_to_atr = _safe_div(abs(closes[-1] - opens[-1]), prior_atr)
        upper_wick_ratio = _safe_div(highs[-1] - max(opens[-1], closes[-1]), total_range)
        lower_wick_ratio = _safe_div(min(opens[-1], closes[-1]) - lows[-1], total_range)
        higher_close_share = _sma(self._higher_close_flags, c.flow_short_length) or 0.0
        lower_close_share = _sma(self._lower_close_flags, c.flow_short_length) or 0.0

        up_progress = net_progress_atr >= c.minimum_progress_atr
        down_progress = net_progress_atr <= -c.minimum_progress_atr
        efficiency_ok = directional_efficiency >= c.minimum_efficiency
        up_close = close_location >= c.up_close_location
        down_close = close_location <= c.down_close_location
        bullish = closes[-1] > opens[-1]
        bearish = closes[-1] < opens[-1]
        body_strong = body_to_atr >= c.minimum_body_atr
        limited_upper = upper_wick_ratio <= c.maximum_directional_wick_ratio
        limited_lower = lower_wick_ratio <= c.maximum_directional_wick_ratio
        higher_persistence = higher_close_share >= c.minimum_directional_close_share
        lower_persistence = lower_close_share >= c.minimum_directional_close_share
        positive_slope = net_progress > 0.0
        negative_slope = net_progress < 0.0
        up_proxy = (
            up_capital_share10 >= c.minimum_directional_share
            and pressure5 >= c.minimum_capital_pressure
        )
        down_proxy = (
            down_capital_share10 >= c.minimum_directional_share
            and pressure5 <= -c.minimum_capital_pressure
        )

        up_direction_group = (
            net_progress_atr > 0.0
            and (up_progress or higher_persistence)
            and positive_slope
        )
        down_direction_group = (
            net_progress_atr < 0.0
            and (down_progress or lower_persistence)
            and negative_slope
        )
        up_candle_group = (
            up_close
            and (bullish or closes[-1] > closes[-2])
            and (limited_upper or body_strong)
        )
        down_candle_group = (
            down_close
            and (bearish or closes[-1] < closes[-2])
            and (limited_lower or body_strong)
        )
        up_efficiency_group = efficiency_ok and (
            up_progress or path_distance_atr >= c.minimum_progress_atr
        )
        down_efficiency_group = efficiency_ok and (
            down_progress or path_distance_atr >= c.minimum_progress_atr
        )

        up_evidence = sum(
            bool(value)
            for value in (
                up_progress,
                efficiency_ok,
                up_close,
                bullish,
                body_strong,
                limited_upper,
                higher_persistence,
                positive_slope,
                up_proxy,
            )
        )
        down_evidence = sum(
            bool(value)
            for value in (
                down_progress,
                efficiency_ok,
                down_close,
                bearish,
                body_strong,
                limited_lower,
                lower_persistence,
                negative_slope,
                down_proxy,
            )
        )

        persistence_window = [
            value for value in rvol_series[-c.persistence_length :] if value is not None
        ]
        elevated_share = sum(
            1 for value in persistence_window if value >= c.rising_rvol
        ) / max(len(persistence_window), 1)
        volume_persistence = (
            len(persistence_window) == c.persistence_length
            and elevated_share >= 0.60
            and volume_slope >= -c.minimum_volume_slope
        )
        participation_magnitude_rising = (
            volume_level in {VolumeLevel.RISING, VolumeLevel.HIGH, VolumeLevel.ABNORMAL}
            or volume_persistence
        )

        up_candidate = (
            participation_magnitude_rising
            and up_direction_group
            and up_candle_group
            and up_efficiency_group
            and up_proxy
            and up_evidence >= c.participation_minimum_evidence
            and down_evidence < c.participation_minimum_evidence
        )
        down_candidate = (
            participation_magnitude_rising
            and down_direction_group
            and down_candle_group
            and down_efficiency_group
            and down_proxy
            and down_evidence >= c.participation_minimum_evidence
            and up_evidence < c.participation_minimum_evidence
        )
        if up_candidate and down_candidate:
            if up_evidence > down_evidence and net_progress_atr > 0.0:
                down_candidate = False
            elif down_evidence > up_evidence and net_progress_atr < 0.0:
                up_candidate = False
            else:
                up_candidate = False
                down_candidate = False

        previous_candidates = (
            self._metrics_history[-(c.participation_confirmation_bars - 1) :]
            if c.participation_confirmation_bars > 1
            else []
        )
        up_consecutive = (
            up_candidate
            and len(previous_candidates) == c.participation_confirmation_bars - 1
            and all(metrics.up_candidate for metrics in previous_candidates)
        )
        down_consecutive = (
            down_candidate
            and len(previous_candidates) == c.participation_confirmation_bars - 1
            and all(metrics.down_candidate for metrics in previous_candidates)
        )
        strong_counter_down = bearish and body_strong and down_close
        strong_counter_up = bullish and body_strong and up_close
        up_retention = (
            net_progress_atr > 0.0
            and directional_efficiency >= c.minimum_efficiency * 0.75
            and rvol >= c.confirmation_minimum_rvol
            and rtv >= c.confirmation_minimum_rtv
            and close_location >= 0.50
            and pressure5 >= -c.minimum_capital_pressure * 0.25
            and not strong_counter_down
        )
        down_retention = (
            net_progress_atr < 0.0
            and directional_efficiency >= c.minimum_efficiency * 0.75
            and rvol >= c.confirmation_minimum_rvol
            and rtv >= c.confirmation_minimum_rtv
            and close_location <= 0.50
            and pressure5 <= c.minimum_capital_pressure * 0.25
            and not strong_counter_up
        )
        up_confirmed = up_consecutive and up_retention
        down_confirmed = down_consecutive and down_retention
        if up_confirmed and down_confirmed:
            up_confirmed = False
            down_confirmed = False

        result_weak = (
            abs(net_progress_atr) <= c.weak_result_progress_limit
            or directional_efficiency <= c.weak_result_efficiency_limit
        )
        effort_rising = progress_rvol >= c.rising_rvol
        effort_high = progress_rvol >= c.high_rvol
        effort_very_high = effort_high and progress_rtv >= c.high_rtv
        strong_result = (
            up_direction_group and up_candle_group and up_efficiency_group
        ) or (
            down_direction_group and down_candle_group and down_efficiency_group
        )
        if effort_very_high and result_weak:
            effort_class = EffortResultClass.VERY_HIGH_EFFORT_WEAK_RESULT
        elif effort_high and result_weak:
            effort_class = EffortResultClass.HIGH_EFFORT_WEAK_RESULT
        elif effort_high and strong_result:
            effort_class = EffortResultClass.HIGH_EFFORT_STRONG_RESULT
        elif effort_rising and strong_result:
            effort_class = EffortResultClass.RISING_EFFORT_STRONG_RESULT
        else:
            effort_class = EffortResultClass.NEUTRAL

        return VolumeParticipationMetrics(
            data_ready=True,
            volume_usable=True,
            capital_usable=True,
            rvol=rvol,
            volume_z_score=volume_z,
            volume_percent_rank=volume_percentile,
            volume_slope=volume_slope,
            volume_regime=volume_regime,
            volume_level=volume_level,
            rtv=rtv,
            capital_z_score=capital_z,
            capital_percent_rank=capital_percentile,
            capital_slope=capital_slope,
            capital_regime=capital_regime,
            capital_level=capital_level,
            up_volume_share_5=up_volume_share5,
            down_volume_share_5=down_volume_share5,
            up_capital_share_10=up_capital_share10,
            down_capital_share_10=down_capital_share10,
            directional_value_pressure_5=pressure5,
            directional_value_pressure_10=pressure10,
            net_progress_atr=net_progress_atr,
            path_distance_atr=path_distance_atr,
            directional_efficiency=directional_efficiency,
            volume_result_efficiency=volume_result_efficiency,
            capital_result_efficiency=capital_result_efficiency,
            effort_result_class=effort_class,
            up_evidence_count=up_evidence,
            down_evidence_count=down_evidence,
            up_candidate=up_candidate,
            down_candidate=down_candidate,
            up_confirmed=up_confirmed,
            down_confirmed=down_confirmed,
        )

    @staticmethod
    def _resolve(metrics: VolumeParticipationMetrics) -> tuple[ParticipationState, Direction]:
        if not metrics.data_ready:
            if metrics.volume_usable or metrics.capital_usable:
                return ParticipationState.PENDING, Direction.NEUTRAL
            return ParticipationState.VOLUME_UNAVAILABLE, Direction.NEUTRAL
        if metrics.up_confirmed and metrics.down_confirmed:
            return ParticipationState.CONFLICT, Direction.NEUTRAL
        if metrics.up_confirmed:
            return ParticipationState.UP_CONFIRMED, Direction.UP
        if metrics.down_confirmed:
            return ParticipationState.DOWN_CONFIRMED, Direction.DOWN
        if metrics.up_candidate and metrics.down_candidate:
            return ParticipationState.CONFLICT, Direction.NEUTRAL
        if metrics.up_candidate:
            return ParticipationState.UP_CANDIDATE, Direction.NEUTRAL
        if metrics.down_candidate:
            return ParticipationState.DOWN_CANDIDATE, Direction.NEUTRAL
        return ParticipationState.NEUTRAL, Direction.NEUTRAL

    def _quality(self, metrics: VolumeParticipationMetrics) -> tuple[float, float]:
        if not metrics.data_ready or metrics.rvol is None or metrics.rtv is None:
            return 0.0, 0.0
        dominant = max(metrics.up_evidence_count, metrics.down_evidence_count)
        separation = abs(metrics.up_evidence_count - metrics.down_evidence_count)
        quality = _clamp(
            dominant / 9.0 * 70.0 + separation / 9.0 * 30.0,
            0.0,
            100.0,
        )
        magnitude = _clamp(
            metrics.rvol / self.config.high_rvol * 70.0
            + metrics.rtv / self.config.high_rtv * 20.0,
            0.0,
            100.0,
        )
        return quality, magnitude

    def update(self, bar: Any) -> EngineResult | None:
        row = dict(bar) if not isinstance(bar, dict) else bar.copy()
        if row.get("is_closed") is False or row.get("is_complete") is False:
            return self._snapshot
        required = ("open", "high", "low", "close", "volume")
        if any(key not in row or pd.isna(row[key]) for key in required):
            raise ValueError("volume participation engine requires complete OHLCV bars")

        self._rows.append(row)
        self._append_runtime_series(row)
        metrics = self._calculate()
        self._metrics_history.append(metrics)
        state, direction = self._resolve(metrics)
        quality, magnitude_quality = self._quality(metrics)

        result = EngineResult(
            engine=self.name,
            state=state.value,
            timestamp=row.get("timestamp"),
            direction=direction,
            score=quality,
            quality=quality,
            levels={},
            events=(),
            reasons=(
                f"RVOL={metrics.rvol:.3f}" if metrics.rvol is not None else "RVOL unavailable",
                f"RTV={metrics.rtv:.3f}" if metrics.rtv is not None else "RTV unavailable",
                f"evidence up/down={metrics.up_evidence_count}/{metrics.down_evidence_count}",
                f"effort_result={metrics.effort_result_class.value}",
            ),
            is_confirmed=True,
        )
        self._snapshot = result
        self.export_contract = ParticipationExport(
            state=state.value,
            direction=int(direction),
            quality=quality,
            magnitude_quality=magnitude_quality,
            rvol=metrics.rvol,
            volume_level=metrics.volume_level.value,
            volume_regime=metrics.volume_regime,
            relative_traded_value=metrics.rtv,
            capital_level=metrics.capital_level.value,
            capital_regime=metrics.capital_regime,
            directional_value_pressure_5=metrics.directional_value_pressure_5,
            directional_value_pressure_10=metrics.directional_value_pressure_10,
            up_capital_share_10=metrics.up_capital_share_10,
            down_capital_share_10=metrics.down_capital_share_10,
            net_progress_atr=metrics.net_progress_atr,
            directional_efficiency=metrics.directional_efficiency,
            volume_result_efficiency=metrics.volume_result_efficiency,
            capital_result_efficiency=metrics.capital_result_efficiency,
            effort_result_class=metrics.effort_result_class.value,
            up_evidence_count=metrics.up_evidence_count,
            down_evidence_count=metrics.down_evidence_count,
        )
        return result

    def replay(self, data: pd.DataFrame) -> list[EngineResult | None]:
        self._reset()
        return [self.update(row) for row in data.to_dict("records")]

    def snapshot(self) -> EngineResult | None:
        return self._snapshot

    @property
    def metrics_history(self) -> tuple[VolumeParticipationMetrics, ...]:
        return tuple(self._metrics_history)
