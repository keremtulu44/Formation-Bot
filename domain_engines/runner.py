"""Independent replay runner for the four source domain engines.

All engines receive independent copies of the same adapted candle values. No
engine consumes another engine's output, and this module creates no shared
signal, decision, or score.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import logging
import threading
from typing import Any, Callable, Mapping

import pandas as pd

from .adapter import to_domain_frame
from .fvg import (
    FvgEngulfingConfig,
    FvgEngulfingDataQuality,
    FvgEngulfingEngine,
    SensitivityProfile,
)
from .incremental import IncrementalDecision, IncrementalEngineState
from .market_structure import MarketStructureConfig, MarketStructureEngine
from .order_block import OrderBlockEngine
from .volume_participation import VolumeParticipationEngine

logger = logging.getLogger(__name__)

FVG_TIMEFRAMES = frozenset({"2h", "4h", "1d"})
ALL_DOMAIN_TIMEFRAMES = frozenset({"1h", "2h", "4h", "1d"})


@dataclass(frozen=True, slots=True)
class DomainRunResult:
    """One engine's native output, kept separate from every other domain."""

    domain: str
    symbol: str
    timeframe: str
    result: Any = None
    export: Any = None
    data_quality: Any = None
    details: Mapping[str, Any] = field(default_factory=dict)
    skipped: bool = False
    reason: str | None = None
    error: str | None = None


_latest_lock = threading.RLock()
_latest_by_series: dict[tuple[str, str], dict[str, DomainRunResult]] = {}

# OB/FVG native state is process-local and independent by symbol/timeframe and
# domain. A changed engine configuration replaces only that domain's state.
_state_registry_lock = threading.RLock()
_incremental_states_by_series: dict[
    tuple[str, str],
    dict[str, tuple[tuple[Any, ...], IncrementalEngineState]],
] = {}
_series_state_locks: dict[tuple[str, str], threading.RLock] = {}


def _advance_incremental_engine(
    symbol: str,
    timeframe: str,
    domain: str,
    config_signature: tuple[Any, ...],
    frame: pd.DataFrame,
    engine_factory: Callable[[], Any],
) -> tuple[IncrementalEngineState, IncrementalDecision]:
    """Advance one in-memory engine cursor; serialize only its own series."""
    key = (symbol, timeframe)
    with _state_registry_lock:
        series_lock = _series_state_locks.setdefault(key, threading.RLock())
    with series_lock:
        with _state_registry_lock:
            states = _incremental_states_by_series.setdefault(key, {})
            stored = states.get(domain)
            if stored is None or stored[0] != config_signature:
                state = IncrementalEngineState(domain, engine_factory())
                states[domain] = (config_signature, state)
            else:
                state = stored[1]
        decision = state.advance(frame)
        logger.debug(
            "%s incremental processing for %s/%s: mode=%s updated_bars=%d reason=%s",
            domain,
            symbol,
            timeframe,
            decision.mode,
            decision.updated_bars,
            decision.reason,
        )
        return state, decision


def _execute_domain(
    domain: str,
    symbol: str,
    timeframe: str,
    execute: Callable[[], DomainRunResult],
) -> DomainRunResult:
    try:
        output = execute()
        state = getattr(output.result, "state", None)
        quality = getattr(output.data_quality, "value", output.data_quality)
        logger.debug(
            "%s domain result for %s/%s: state=%s data_quality=%s",
            domain,
            symbol,
            timeframe,
            state,
            quality,
        )
        return output
    except Exception as exc:
        logger.exception(
            "%s domain failed for %s/%s; other domains will continue",
            domain,
            symbol,
            timeframe,
        )
        return DomainRunResult(
            domain=domain,
            symbol=symbol,
            timeframe=timeframe,
            error=f"{type(exc).__name__}: {exc}",
        )


def _run_market_structure(
    symbol: str,
    timeframe: str,
    frame: pd.DataFrame,
    profile: str,
) -> DomainRunResult:
    engine = MarketStructureEngine(config=MarketStructureConfig(profile=profile))
    engine.replay(frame)
    result = engine.snapshot()
    export = engine.export_contract
    return DomainRunResult(
        domain="market_structure",
        symbol=symbol,
        timeframe=timeframe,
        result=result,
        export=export,
        details={
            "external_swings": engine.external_swings,
            "internal_swings": engine.internal_swings,
            "external_candidates": engine.external_candidates,
            "internal_candidates": engine.internal_candidates,
            "event_history": engine.event_history,
            "latest_external_event": engine.latest_external_event,
            "latest_internal_event": engine.latest_internal_event,
            "external_context": engine.external_context,
            "internal_context": engine.internal_context,
        },
    )


def _run_volume(
    symbol: str,
    timeframe: str,
    frame: pd.DataFrame,
) -> DomainRunResult:
    engine = VolumeParticipationEngine()
    engine.replay(frame)
    metrics = engine.metrics_history[-1] if engine.metrics_history else None
    result = engine.snapshot()
    final_export = engine.final_export

    if metrics is None or not metrics.data_ready:
        logger.info(
            "Volume warm-up/not-ready for %s/%s: bars=%d minimum_history=%d "
            "volume_usable=%s capital_usable=%s",
            symbol,
            timeframe,
            len(frame),
            engine.config.minimum_history,
            metrics.volume_usable if metrics is not None else False,
            metrics.capital_usable if metrics is not None else False,
        )

    return DomainRunResult(
        domain="volume_participation",
        symbol=symbol,
        timeframe=timeframe,
        result=result,
        export=final_export,
        data_quality=final_export.state,
        details={
            "latest_metrics": metrics,
            "metrics_history": engine.metrics_history,
            "core_export": engine.export_contract,
            "lifecycle_export": engine.lifecycle_export,
        },
    )


def _run_fvg(
    symbol: str,
    timeframe: str,
    frame: pd.DataFrame,
    profile: str,
) -> DomainRunResult:
    sensitivity = SensitivityProfile(profile)
    config = FvgEngulfingConfig(sensitivity=sensitivity, timeframe=timeframe)
    state, _ = _advance_incremental_engine(
        symbol,
        timeframe,
        "fvg",
        (sensitivity.value, timeframe),
        frame,
        lambda: FvgEngulfingEngine(config=config),
    )
    engine = state.engine
    # The last engine result retains the native timestamp even when the frame
    # was unchanged; never substitute frame[-1] or manufacture one here.
    result = state.last_result
    export = deepcopy(engine.export)
    data_quality = engine.last_data_quality

    if data_quality is FvgEngulfingDataQuality.WARMUP:
        logger.info(
            "FVG warm-up for %s/%s: bars=%d minimum_history=100",
            symbol,
            timeframe,
            len(frame),
        )
    elif data_quality is not FvgEngulfingDataQuality.OK:
        logger.info(
            "FVG data quality for %s/%s: %s",
            symbol,
            timeframe,
            data_quality.value,
        )

    return DomainRunResult(
        domain="fvg",
        symbol=symbol,
        timeframe=timeframe,
        result=result,
        export=export,
        data_quality=data_quality,
        details={
            "fvg_formations": deepcopy(engine.fvg_formations),
            "engulfing_formations": deepcopy(engine.engulfing_formations),
            "active_bullish_fvg": deepcopy(engine.active_bullish_fvg),
            "active_bearish_fvg": deepcopy(engine.active_bearish_fvg),
            "completed_fvg": deepcopy(engine.completed_fvg),
            "completed_engulfing": deepcopy(engine.completed_engulfing),
        },
    )


def _run_order_block(
    symbol: str,
    timeframe: str,
    frame: pd.DataFrame,
) -> DomainRunResult:
    state, _ = _advance_incremental_engine(
        symbol,
        timeframe,
        "order_block",
        (),
        frame,
        OrderBlockEngine,
    )
    engine = state.engine
    result = engine.snapshot()
    export = deepcopy(engine.export)
    data_quality = engine.last_data_quality

    if data_quality.value != "OK":
        logger.info(
            "Order Block data quality for %s/%s: %s",
            symbol,
            timeframe,
            data_quality.value,
        )

    return DomainRunResult(
        domain="order_block",
        symbol=symbol,
        timeframe=timeframe,
        result=result,
        export=export,
        data_quality=data_quality,
        details={
            "records": deepcopy(engine.records),
            "active_records": deepcopy(engine.active_records),
        },
    )


def _run_domain_engines_locked(
    symbol: str,
    timeframe: str,
    frame: pd.DataFrame,
    *,
    profile: str = "Dengeli",
) -> dict[str, DomainRunResult]:
    """Run each applicable domain independently on one symbol/timeframe.

    Market Structure and Volume retain their replay contract. OB and FVG keep
    isolated in-memory cursors per symbol/timeframe and use safe updates only
    when their current native frame alignment is verified; otherwise they replay
    the supplied frame. The caller remains responsible for completed bars; this
    function never fetches data or resamples it.
    """
    tf = str(timeframe).strip().lower()
    if tf not in ALL_DOMAIN_TIMEFRAMES:
        raise ValueError(f"unsupported Formation-Bot timeframe: {timeframe!r}")

    # The shared shape adapter is the only common input operation. A failure
    # here means the frame itself cannot satisfy the engines' timestamp contract.
    domain_frame = to_domain_frame(frame)
    output: dict[str, DomainRunResult] = {}

    output["market_structure"] = _execute_domain(
        "market_structure",
        symbol,
        tf,
        lambda: _run_market_structure(symbol, tf, domain_frame.copy(deep=True), profile),
    )
    output["volume_participation"] = _execute_domain(
        "volume_participation",
        symbol,
        tf,
        lambda: _run_volume(symbol, tf, domain_frame.copy(deep=True)),
    )

    if tf in FVG_TIMEFRAMES:
        output["fvg"] = _execute_domain(
            "fvg",
            symbol,
            tf,
            lambda: _run_fvg(symbol, tf, domain_frame.copy(deep=True), profile),
        )
    else:
        logger.debug("FVG skipped for unsupported timeframe %s/%s", symbol, tf)
        output["fvg"] = DomainRunResult(
            domain="fvg",
            symbol=symbol,
            timeframe=tf,
            skipped=True,
            reason="source supports only 2h, 4h, and 1d",
        )

    output["order_block"] = _execute_domain(
        "order_block",
        symbol,
        tf,
        lambda: _run_order_block(symbol, tf, domain_frame.copy(deep=True)),
    )

    with _latest_lock:
        _latest_by_series[(symbol, tf)] = dict(output)
    return dict(output)



def run_domain_engines(
    symbol: str,
    timeframe: str,
    frame: pd.DataFrame,
    *,
    profile: str = "Dengeli",
) -> dict[str, DomainRunResult]:
    """Run all domains as one serialized update for a symbol/timeframe."""
    tf = str(timeframe).strip().lower()
    if tf not in ALL_DOMAIN_TIMEFRAMES:
        raise ValueError(f"unsupported Formation-Bot timeframe: {timeframe!r}")
    key = (symbol, tf)
    with _state_registry_lock:
        series_lock = _series_state_locks.setdefault(key, threading.RLock())
    with series_lock:
        return _run_domain_engines_locked(symbol, tf, frame, profile=profile)


def get_latest_domain_results(
    symbol: str,
    timeframe: str,
) -> dict[str, DomainRunResult] | None:
    """Return a shallow copy of the latest independent outputs for one series."""
    key = (symbol, str(timeframe).strip().lower())
    with _latest_lock:
        result = _latest_by_series.get(key)
        return dict(result) if result is not None else None


def get_all_latest_domain_results() -> dict[tuple[str, str], dict[str, DomainRunResult]]:
    """Return a shallow copy of the in-memory, per-series result registry."""
    with _latest_lock:
        return {key: dict(value) for key, value in _latest_by_series.items()}
