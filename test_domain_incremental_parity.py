from __future__ import annotations

from copy import deepcopy
from dataclasses import fields, is_dataclass, replace
import math

import numpy as np
import pandas as pd

from domain_engines.fvg import FvgEngulfingConfig, FvgEngulfingEngine
from domain_engines.fvg.fvg_engulfing_final import (
    FvgEngulfingEngine as FullReplayFvgEngine,
)
from domain_engines.incremental import IncrementalEngineState
from domain_engines.order_block import OrderBlockEngine


def _ohlcv_frame(count: int, *, start: str = "2025-01-02 09:30", freq: str = "1h") -> pd.DataFrame:
    timestamps = pd.date_range(
        start,
        periods=count,
        freq=freq,
        tz="Europe/Istanbul",
        name="timestamp",
    )
    steps = np.arange(count, dtype=float)
    close = 50.0 + 0.025 * steps + 1.4 * np.sin(steps * 0.31)
    open_ = close + np.where(steps.astype(int) % 2 == 0, -0.16, 0.16)
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": open_,
            "high": np.maximum(open_, close) + 0.45,
            "low": np.minimum(open_, close) - 0.45,
            "close": close,
            "volume": 1_000_000.0 + (steps % 17.0) * 2_500.0,
        }
    )


def _fvg_lifecycle_frame(count: int = 180) -> pd.DataFrame:
    frame = _ohlcv_frame(count, freq="2h")
    # Deterministic native bullish FVG/reaction fixture also used by integration
    # tests: the three-bar imbalance occurs at rows 99-101.
    for index, candle in {
        99: {"open": 100.0, "high": 102.2, "low": 99.9, "close": 102.0},
        100: {"open": 102.9, "high": 103.2, "low": 102.8, "close": 103.0},
        101: {"open": 102.9, "high": 104.2, "low": 102.5, "close": 104.0},
        102: {"open": 104.0, "high": 104.2, "low": 103.8, "close": 104.1},
    }.items():
        for column, value in candle.items():
            frame.loc[index, column] = value
    return frame


def _assert_exact(left, right, path: str = "root") -> None:
    """Recursive equality with only NaN==NaN handling; no tolerance/normalization."""
    if isinstance(left, (float, np.floating)) and isinstance(right, (float, np.floating)):
        if math.isnan(float(left)) and math.isnan(float(right)):
            return
        assert float(left) == float(right), f"{path}: {left!r} != {right!r}"
        return
    if is_dataclass(left) and is_dataclass(right):
        assert type(left) is type(right), f"{path}: {type(left)} != {type(right)}"
        for field in fields(left):
            _assert_exact(getattr(left, field.name), getattr(right, field.name), f"{path}.{field.name}")
        return
    if isinstance(left, dict) and isinstance(right, dict):
        assert left.keys() == right.keys(), f"{path}: keys differ"
        for key in left:
            _assert_exact(left[key], right[key], f"{path}.{key}")
        return
    if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
        assert type(left) is type(right), f"{path}: {type(left)} != {type(right)}"
        assert len(left) == len(right), f"{path}: lengths differ ({len(left)} != {len(right)})"
        for index, (a, b) in enumerate(zip(left, right)):
            _assert_exact(a, b, f"{path}[{index}]")
        return
    assert left == right, f"{path}: {left!r} != {right!r}"


def _assert_fvg_native_state_equal(left, right) -> None:
    for attribute in (
        "_rows",
        "_valid",
        "snapshot",
        "last_data_quality",
        "export",
        "active_bullish_fvg",
        "active_bearish_fvg",
        "active_bullish_engulfing",
        "active_bearish_engulfing",
        "completed_fvg",
        "completed_engulfing",
        "fvg_formations",
        "engulfing_formations",
        "_bull_fvg_event",
        "_bear_fvg_event",
        "_bull_engulf_event",
        "_bear_engulf_event",
    ):
        _assert_exact(getattr(left, attribute), getattr(right, attribute), attribute)
    _assert_exact(left._calculate_atr_series(), right._calculate_atr_series(), "atr_series")
    _assert_exact(left._calculate_series(), right._calculate_series(), "detector_series")
    for index in range(len(left._rows)):
        _assert_exact(
            left._lifecycle_metrics(index),
            right._lifecycle_metrics(index),
            f"lifecycle_metrics[{index}]",
        )


def _assert_ob_native_state_equal(left, right) -> None:
    _assert_exact(left._rows, right._rows, "rows")
    _assert_exact(left.records, right.records, "records")
    _assert_exact(left.active_records, right.active_records, "active_records")
    _assert_exact(left.snapshot(), right.snapshot(), "snapshot")
    _assert_exact(left.export, right.export, "export")
    _assert_exact(left.last_data_quality, right.last_data_quality, "data_quality")


def test_fvg_cached_detector_and_lifecycle_match_uncached_full_replay_and_updates():
    frame = _fvg_lifecycle_frame()
    # Explicit source-gap behavior is part of the native contract and must reset
    # the same Wilder-RMA chain in both implementations.
    frame["is_complete"] = True
    frame.loc[150, "is_complete"] = False
    config = FvgEngulfingConfig(timeframe="2h")

    reference = FullReplayFvgEngine(config)
    expected_results = reference.replay(frame)

    # Exercise a warm-up prefix followed by one-bar updates, not just .replay().
    incremental = FvgEngulfingEngine(config)
    split = 117
    actual_results = incremental.replay(frame.iloc[:split].copy())
    for candle in frame.iloc[split:].to_dict("records"):
        actual_results.append(incremental.update(candle))

    _assert_exact(expected_results, actual_results, "per_bar_results")
    _assert_fvg_native_state_equal(reference, incremental)
    assert len(incremental.completed_fvg) > 0


def test_order_block_single_bar_updates_match_full_replay_field_for_field():
    frame = _ohlcv_frame(360)
    reference = OrderBlockEngine()
    expected_results = reference.replay(frame)

    incremental = OrderBlockEngine()
    split = 173
    actual_results = incremental.replay(frame.iloc[:split].copy())
    for candle in frame.iloc[split:].to_dict("records"):
        actual_results.append(incremental.update(candle))

    _assert_exact(expected_results, actual_results, "per_bar_results")
    _assert_ob_native_state_equal(reference, incremental)


def test_order_block_360_bar_roll_rebases_source_and_imbalance_indexes():
    source = _ohlcv_frame(366)
    first_window = source.iloc[:360].reset_index(drop=True)
    final_window = source.iloc[3:363].reset_index(drop=True)

    incremental_state = IncrementalEngineState("order_block", OrderBlockEngine())
    assert incremental_state.advance(first_window).mode == "cold_full_replay"
    decision = incremental_state.advance(final_window)
    assert decision.mode == "rolling_window_update"
    assert decision.updated_bars == 3
    assert incremental_state.window_slide_count == 3

    reference = OrderBlockEngine()
    reference.replay(final_window)
    _assert_ob_native_state_equal(reference, incremental_state.engine)
    assert all(0 <= record.source_index < len(final_window) for record in reference.records)
    for record in reference.records:
        assert record.source_time == final_window.iloc[record.source_index]["timestamp"]


def test_ob_source_index_mismatch_aborts_rebase_and_full_replays():
    source = _ohlcv_frame(366)
    first_window = source.iloc[:360].reset_index(drop=True)
    rolling_window = source.iloc[1:361].reset_index(drop=True)
    state = IncrementalEngineState("order_block", OrderBlockEngine())
    assert state.advance(first_window).mode == "cold_full_replay"
    assert state.engine._records

    record = state.engine._records[0]
    state.engine._records[0] = replace(record, source_index=record.source_index + 1)
    decision = state.advance(rolling_window)
    assert decision.mode == "full_replay_ob_window_mismatch"

    reference = OrderBlockEngine()
    reference.replay(rolling_window)
    _assert_ob_native_state_equal(reference, state.engine)


def test_fvg_rolling_window_replays_each_missed_bar_with_current_window_seed():
    source = _fvg_lifecycle_frame(366)
    first_window = source.iloc[:360].reset_index(drop=True)
    final_window = source.iloc[3:363].reset_index(drop=True)
    config = FvgEngulfingConfig(timeframe="2h")

    incremental_state = IncrementalEngineState("fvg", FvgEngulfingEngine(config))
    assert incremental_state.advance(first_window).mode == "cold_full_replay"
    before_replays = incremental_state.full_replay_count
    decision = incremental_state.advance(final_window)
    assert decision.mode == "rolling_window_replay_fallback"
    assert decision.updated_bars == 3
    assert incremental_state.full_replay_count - before_replays == 3

    reference = FullReplayFvgEngine(config)
    reference.replay(final_window)
    _assert_fvg_native_state_equal(reference, incremental_state.engine)


def test_incremental_state_duplicate_revision_catchup_and_restart_fallbacks():
    source = _ohlcv_frame(370)
    state = IncrementalEngineState("order_block", OrderBlockEngine())
    assert state.advance(source.iloc[:360]).mode == "cold_full_replay"

    # Identical timestamp + OHLCV is idempotent, including a duplicate row in the
    # input frame; it is not passed to update a second time.
    exact_duplicate = pd.concat(
        [source.iloc[:360], source.iloc[[359]]], ignore_index=True
    )
    duplicate_decision = state.advance(exact_duplicate)
    assert duplicate_decision.mode == "unchanged_frame"
    assert duplicate_decision.updated_bars == 0

    # Several missed completed bars are fed in timestamp order, one update each.
    catchup = state.advance(source.iloc[:363])
    assert catchup.mode == "append"
    assert catchup.updated_bars == 3
    assert [row["timestamp"] for row in state.engine._rows[-3:]] == source.iloc[360:363]["timestamp"].tolist()

    # A revised historical value invalidates the overlap and must cold-replay.
    revised = source.iloc[:363].copy()
    revised.loc[100, "close"] += 0.25
    revision_decision = state.advance(revised)
    assert revision_decision.mode == "full_replay_frame_mismatch"
    reference = OrderBlockEngine()
    reference.replay(revised.reset_index(drop=True))
    _assert_ob_native_state_equal(reference, state.engine)

    # A same-timestamp conflicting duplicate also forces full replay and disables
    # append trust until a later clean, verified frame is replayed.
    conflict = pd.concat([revised, revised.iloc[[100]].assign(close=revised.iloc[100]["close"] + 1.0)], ignore_index=True)
    conflict_decision = state.advance(conflict)
    assert conflict_decision.mode == "full_replay_conflicting_timestamp"
    assert state.advance(revised).mode == "full_replay_untrusted_state"

    # A fresh process has no trustworthy engine checkpoint and starts by replay.
    restarted = IncrementalEngineState("order_block", OrderBlockEngine())
    restart_decision = restarted.advance(revised)
    assert restart_decision.mode == "cold_full_replay"
    _assert_ob_native_state_equal(reference, restarted.engine)


def test_fvg_duplicate_without_complete_ohlcv_is_not_deduplicated():
    frame = _ohlcv_frame(8).drop(columns=["volume"])
    state = IncrementalEngineState("fvg", FvgEngulfingEngine(FvgEngulfingConfig(timeframe="2h")))
    assert state.advance(frame.iloc[:7]).mode == "cold_full_replay"
    duplicate = pd.concat([frame.iloc[:7], frame.iloc[[6]]], ignore_index=True)
    decision = state.advance(duplicate)
    assert decision.mode == "full_replay_conflicting_timestamp"
    assert not state._incremental_safe
    assert len(state.engine._rows) == 8


def test_unverifiable_nonfinite_ohlcv_keeps_incremental_path_disabled():
    frame = _ohlcv_frame(8)
    frame.loc[3, "close"] = np.nan
    state = IncrementalEngineState("fvg", FvgEngulfingEngine(FvgEngulfingConfig(timeframe="2h")))
    assert state.advance(frame.iloc[:7]).mode == "cold_full_replay"
    assert not state._incremental_safe
    decision = state.advance(frame)
    assert decision.mode == "full_replay_untrusted_state"
    assert not state._incremental_safe


def test_fvg_rolling_replay_detects_revised_ohlcv_and_restart_state_loss():
    frame = _fvg_lifecycle_frame(180)
    config = FvgEngulfingConfig(timeframe="2h")
    state = IncrementalEngineState("fvg", FvgEngulfingEngine(config))
    assert state.advance(frame).mode == "cold_full_replay"

    revised = frame.copy()
    revised.loc[120, "close"] += 0.125
    decision = state.advance(revised)
    assert decision.mode == "full_replay_frame_mismatch"

    reference = FullReplayFvgEngine(config)
    reference.replay(revised.reset_index(drop=True))
    _assert_fvg_native_state_equal(reference, state.engine)

    restarted = IncrementalEngineState("fvg", FvgEngulfingEngine(config))
    assert restarted.advance(revised).mode == "cold_full_replay"
    _assert_fvg_native_state_equal(reference, restarted.engine)


def test_production_runner_reuses_isolated_ob_fvg_state_and_falls_back_exactly():
    import domain_engines.runner as runner

    symbol = "PHASE2_STATE_ISOLATION"
    source = _ohlcv_frame(366, freq="2h")
    initial_window = source.iloc[:360].reset_index(drop=True)
    rolling_window = source.iloc[1:361].reset_index(drop=True)
    caught_up = source.iloc[1:364].reset_index(drop=True)

    first = runner.run_domain_engines(symbol, "4h", initial_window)
    states = runner._incremental_states_by_series[(symbol, "4h")]
    fvg_state = states["fvg"][1]
    ob_state = states["order_block"][1]
    assert fvg_state.last_decision.mode == "cold_full_replay"
    assert ob_state.last_decision.mode == "cold_full_replay"
    assert fvg_state.engine is not ob_state.engine

    # Outputs returned to callers are snapshots, not aliases to live lifecycle
    # records that a later update could mutate.
    first_fvg_details = deepcopy(first["fvg"].details)
    first_ob_details = deepcopy(first["order_block"].details)

    unchanged = runner.run_domain_engines(symbol, "4h", initial_window)
    assert fvg_state.last_decision.mode == "unchanged_frame"
    assert ob_state.last_decision.mode == "unchanged_frame"
    _assert_exact(unchanged["fvg"].result, first["fvg"].result, "unchanged_fvg_result")
    _assert_exact(unchanged["order_block"].export, first["order_block"].export, "unchanged_ob_export")

    rolling = runner.run_domain_engines(symbol, "4h", rolling_window)
    assert ob_state.last_decision.mode == "rolling_window_update"
    assert ob_state.last_decision.updated_bars == 1
    assert fvg_state.last_decision.mode == "rolling_window_replay_fallback"
    assert fvg_state.last_decision.updated_bars == 1
    ob_reference = OrderBlockEngine()
    ob_reference.replay(rolling_window)
    _assert_ob_native_state_equal(ob_reference, ob_state.engine)
    fvg_reference = FvgEngulfingEngine(FvgEngulfingConfig(timeframe="4h"))
    fvg_reference.replay(rolling_window)
    _assert_fvg_native_state_equal(fvg_reference, fvg_state.engine)
    _assert_exact(rolling["fvg"].export, fvg_reference.export, "runner_fvg_export")
    _assert_exact(rolling["order_block"].export, ob_reference.export, "runner_ob_export")

    advanced = runner.run_domain_engines(symbol, "4h", caught_up)
    assert ob_state.last_decision.mode == "append"
    assert fvg_state.last_decision.mode == "append"
    assert ob_state.last_decision.updated_bars == fvg_state.last_decision.updated_bars == 3
    _assert_exact(first["fvg"].details, first_fvg_details, "old_fvg_output_stays_immutable")
    _assert_exact(first["order_block"].details, first_ob_details, "old_ob_output_stays_immutable")

    # Revising an existing candle cannot be continued from retained state.
    revised = caught_up.copy()
    revised.loc[150, "close"] += 0.25
    revised_output = runner.run_domain_engines(symbol, "4h", revised)
    assert ob_state.last_decision.mode == "full_replay_frame_mismatch"
    assert fvg_state.last_decision.mode == "full_replay_frame_mismatch"
    ob_reference.replay(revised)
    expected_fvg_results = fvg_reference.replay(revised)
    _assert_ob_native_state_equal(ob_reference, ob_state.engine)
    _assert_fvg_native_state_equal(fvg_reference, fvg_state.engine)
    _assert_exact(revised_output["fvg"].result, expected_fvg_results[-1], "revised_fvg_result")

    # A distinct symbol/timeframe receives independent cold state. A profile
    # change replaces only the FVG cursor for its original symbol/timeframe.
    runner.run_domain_engines(symbol + "_OTHER", "4h", initial_window)
    other_states = runner._incremental_states_by_series[(symbol + "_OTHER", "4h")]
    assert other_states["fvg"][1] is not fvg_state
    assert other_states["order_block"][1] is not ob_state

    runner.run_domain_engines(symbol, "2h", initial_window)
    timeframe_states = runner._incremental_states_by_series[(symbol, "2h")]
    assert timeframe_states["fvg"][1] is not fvg_state
    assert timeframe_states["order_block"][1] is not ob_state

    runner.run_domain_engines(symbol, "4h", revised, profile="Hassas")
    replacement_fvg = runner._incremental_states_by_series[(symbol, "4h")]["fvg"][1]
    assert replacement_fvg is not fvg_state
    assert replacement_fvg.last_decision.mode == "cold_full_replay"
    assert runner._incremental_states_by_series[(symbol, "4h")]["order_block"][1] is ob_state
    assert ob_state.last_decision.mode == "unchanged_frame"


def test_order_block_rolling_boundary_uses_retained_native_pair_history():
    """Prune evicted-pair sources, but keep a source reproducible in rows 0/1."""
    timestamps = pd.date_range(
        "2025-01-02 09:30",
        periods=10,
        freq="h",
        tz="Europe/Istanbul",
        name="timestamp",
    )

    def candles(*, pair_is_inside_window: bool) -> pd.DataFrame:
        rows = []
        for index, timestamp in enumerate(timestamps):
            price = 10.0 if index < 5 else 11.3
            rows.append(
                {
                    "timestamp": timestamp,
                    "open": price,
                    "high": price + 0.5,
                    "low": price - 0.5,
                    "close": price,
                    "volume": 1_000_000.0,
                }
            )

        if pair_is_inside_window:
            # Rows 3/4 make the same bullish source at row 3 using a pair that
            # remains available after the three-bar prefix is discarded.
            rows[3].update(open=10.0, high=11.0, low=8.0, close=9.0)
            rows[4].update(open=9.0, high=10.5, low=8.5, close=10.0)
        else:
            # Rows 2/3 make a bullish source at row 3 using row 2, which rolls
            # out. Row 4 is a doji, so the retained pair cannot recreate it.
            rows[2].update(open=10.0, high=10.5, low=8.5, close=9.0)
            rows[3].update(open=9.0, high=11.0, low=8.0, close=10.0)

        # Confirm imbalance for the row-3 source without filling its zone.
        rows[5].update(open=11.2, high=11.6, low=11.1, close=11.4)
        return pd.DataFrame(rows)

    for pair_is_inside_window, expected_records in ((False, 0), (True, 1)):
        source = candles(pair_is_inside_window=pair_is_inside_window)
        old_window = source.iloc[:7].reset_index(drop=True)
        new_window = source.iloc[3:].reset_index(drop=True)

        state = IncrementalEngineState("order_block", OrderBlockEngine())
        assert state.advance(old_window).mode == "cold_full_replay"
        decision = state.advance(new_window)
        assert decision.mode == "rolling_window_update"
        assert decision.updated_bars == 3

        reference = OrderBlockEngine()
        expected_results = reference.replay(new_window)
        _assert_ob_native_state_equal(reference, state.engine)
        _assert_exact(expected_results[-1], state.last_result, "rolling_boundary_result")
        assert len(reference.records) == expected_records
        for record in state.engine.records:
            assert record.source_time == new_window.iloc[record.source_index]["timestamp"]
