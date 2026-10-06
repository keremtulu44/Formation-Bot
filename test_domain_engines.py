from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from domain_engines.adapter import to_domain_frame
from domain_engines.fvg import (
    FvgEngulfingConfig,
    FvgEngulfingDataQuality,
    FvgEngulfingEngine,
    FvgEngulfingExport,
    SensitivityProfile,
)
from domain_engines.market_structure import MarketStructureEngine
from domain_engines.order_block import OrderBlockEngine, OrderBlockExport
from domain_engines.runner import (
    DomainRunResult,
    get_latest_domain_results,
    run_domain_engines,
)
from domain_engines.volume_participation import (
    VolumeParticipationEngine,
    VolumeParticipationMetrics,
)


def _ohlcv_frame(count: int = 180) -> pd.DataFrame:
    index = pd.date_range(
        "2025-01-02 09:30",
        periods=count,
        freq="1h",
        tz="Europe/Istanbul",
        name="timestamp",
    )
    steps = np.arange(count, dtype=float)
    close = 50.0 + 0.025 * steps + 1.4 * np.sin(steps * 0.31)
    open_ = close + np.where(steps.astype(int) % 2 == 0, -0.16, 0.16)
    high = np.maximum(open_, close) + 0.45
    low = np.minimum(open_, close) - 0.45
    volume = 1_000_000.0 + (steps % 17.0) * 2_500.0
    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=index,
    )


def _ob_fill_frame() -> pd.DataFrame:
    index = pd.date_range(
        "2025-02-03 09:30",
        periods=4,
        freq="1h",
        tz="Europe/Istanbul",
        name="timestamp",
    )
    return pd.DataFrame(
        [
            {"open": 10.0, "high": 10.2, "low": 8.8, "close": 9.0, "volume": 1000.0},
            {"open": 9.1, "high": 10.3, "low": 9.0, "close": 10.1, "volume": 1100.0},
            {"open": 10.4, "high": 11.2, "low": 10.4, "close": 11.0, "volume": 1200.0},
            {"open": 9.4, "high": 9.8, "low": 9.0, "close": 9.3, "volume": 1300.0},
        ],
        index=index,
    )


def test_adapter_exposes_existing_datetime_index_without_changing_bars():
    frame = _ohlcv_frame(12).iloc[::-1]
    original_values = frame[["open", "high", "low", "close", "volume"]].copy(deep=True)
    original_index = frame.index.copy()

    adapted = to_domain_frame(frame)

    assert adapted["timestamp"].tolist() == sorted(original_index.tolist())
    assert adapted.columns.tolist() == ["timestamp", "open", "high", "low", "close", "volume"]
    np.testing.assert_array_equal(
        adapted[["open", "high", "low", "close", "volume"]].to_numpy(),
        original_values.sort_index().to_numpy(),
    )
    pd.testing.assert_frame_equal(frame[["open", "high", "low", "close", "volume"]], original_values)
    assert frame.index.equals(original_index)


def test_adapter_refuses_to_invent_timestamp():
    frame = pd.DataFrame({"open": [1.0], "high": [2.0], "low": [0.5], "close": [1.5]})
    with pytest.raises(ValueError, match="timestamp"):
        to_domain_frame(frame)


def test_market_structure_public_integrated_engine_replays_and_exports():
    engine = MarketStructureEngine()
    replay_results = engine.replay(to_domain_frame(_ohlcv_frame(180)))

    assert len(replay_results) == 180
    assert engine.snapshot() is not None
    assert engine.export_contract is not None
    assert engine.export_contract.contract_version == 3
    assert engine.external_swings
    assert engine.internal_swings


def test_volume_minimum_history_and_data_readiness():
    short_engine = VolumeParticipationEngine()
    short_engine.replay(to_domain_frame(_ohlcv_frame(149)))
    assert len(short_engine.metrics_history) == 149
    assert isinstance(short_engine.metrics_history[-1], VolumeParticipationMetrics)
    assert not short_engine.metrics_history[-1].data_ready

    ready_engine = VolumeParticipationEngine()
    ready_engine.replay(to_domain_frame(_ohlcv_frame(180)))
    latest = ready_engine.metrics_history[-1]
    assert latest.data_ready
    assert latest.volume_usable
    assert latest.capital_usable
    assert ready_engine.final_export.state is not None


def test_volume_zero_volume_remains_unusable_and_motor_has_no_provider_imports():
    frame = _ohlcv_frame(180)
    frame["volume"] = 0.0
    engine = VolumeParticipationEngine()
    engine.replay(to_domain_frame(frame))
    latest = engine.metrics_history[-1]
    assert not latest.volume_usable
    assert not latest.data_ready

    provider_modules = {"yfinance", "tvdatafeed", "requests", "httpx", "urllib"}
    package_dir = Path(__file__).parent / "domain_engines" / "volume_participation"
    imported_modules = set()
    for path in package_dir.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module.split(".", 1)[0])
    assert provider_modules.isdisjoint(imported_modules)


@pytest.mark.parametrize("timeframe", ["2h", "4h", "1d"])
def test_fvg_source_config_accepts_only_supported_timeframes(timeframe):
    config = FvgEngulfingConfig(
        sensitivity=SensitivityProfile.BALANCED,
        timeframe=timeframe,
    )
    assert config.timeframe == timeframe


def test_fvg_rejects_1h_and_public_fvg_engulfing_chain_runs():
    with pytest.raises(ValueError, match="only 2h, 4h, or 1d"):
        FvgEngulfingConfig(timeframe="1h")

    engine = FvgEngulfingEngine(FvgEngulfingConfig(timeframe="4h"))
    replay_results = engine.replay(to_domain_frame(_ohlcv_frame(150)))

    assert len(replay_results) == 150
    assert engine.last_data_quality is FvgEngulfingDataQuality.OK
    assert isinstance(engine.export, FvgEngulfingExport)
    assert hasattr(engine.export, "bull_fvg")
    assert hasattr(engine.export, "bull_engulf")
    assert engine.fvg_formations is not None
    assert engine.engulfing_formations is not None


def test_order_block_replay_export_and_fill_lifecycle():
    source_frame = to_domain_frame(_ob_fill_frame())
    engine = OrderBlockEngine()

    first_results = engine.replay(source_frame.iloc[:3].copy())
    assert len(first_results) == 3
    assert isinstance(engine.export, OrderBlockExport)
    assert any(record.bullish for record in engine.active_records)
    assert engine.export.bull.state == 1.0

    engine.update(source_frame.iloc[3].to_dict())
    assert not any(record.bullish for record in engine.active_records)
    assert engine.export.bull.state is None


def test_runner_keeps_domain_outputs_separate_and_skips_fvg_on_1h():
    outputs = run_domain_engines("TEST", "1h", _ohlcv_frame(180))

    assert set(outputs) == {"market_structure", "volume_participation", "fvg", "order_block"}
    assert outputs["market_structure"].error is None
    assert outputs["volume_participation"].error is None
    assert outputs["order_block"].error is None
    assert outputs["fvg"].skipped
    assert outputs["fvg"].reason == "source supports only 2h, 4h, and 1d"
    assert get_latest_domain_results("TEST", "1h") == outputs


def test_runner_gives_each_domain_an_independent_copy_of_the_same_bars(monkeypatch):
    import domain_engines.runner as runner

    source = _ohlcv_frame(180)
    original = to_domain_frame(source)
    received = {}

    def stub(domain):
        def execute(symbol, timeframe, frame, *args):
            received[domain] = frame
            if domain == "market_structure":
                frame.loc[0, "open"] = -999.0
            return DomainRunResult(domain=domain, symbol=symbol, timeframe=timeframe)
        return execute

    monkeypatch.setattr(runner, "_run_market_structure", stub("market_structure"))
    monkeypatch.setattr(runner, "_run_volume", stub("volume_participation"))
    monkeypatch.setattr(runner, "_run_fvg", stub("fvg"))
    monkeypatch.setattr(runner, "_run_order_block", stub("order_block"))

    outputs = runner.run_domain_engines("TEST", "2h", source)

    assert all(output.error is None for output in outputs.values())
    assert len({id(frame) for frame in received.values()}) == 4
    pd.testing.assert_frame_equal(received["volume_participation"], original)
    pd.testing.assert_frame_equal(received["fvg"], original)
    pd.testing.assert_frame_equal(received["order_block"], original)
    assert source["open"].tolist() == _ohlcv_frame(180)["open"].tolist()


def test_main_domain_hook_isolates_timeframes(monkeypatch):
    import main as main_module

    calls = []
    frame = _ohlcv_frame(10)

    def broken_first_timeframe(symbol, timeframe, received_frame, *, profile):
        calls.append((symbol, timeframe, received_frame, profile))
        if timeframe == "1h":
            raise RuntimeError("isolated scanner-hook failure")

    monkeypatch.setattr(main_module, "_load_domain_runner", lambda: broken_first_timeframe)
    main_module._run_domain_engines_for_symbol(
        "HOOK_TEST",
        {"1h": frame, "2h": frame.copy(), "4h": None},
    )

    assert [call[1] for call in calls] == ["1h", "2h"]
    assert all(call[0] == "HOOK_TEST" for call in calls)
    assert all(call[3] == main_module.PROFILE for call in calls)


def test_runner_continues_when_one_domain_fails(monkeypatch):
    import domain_engines.runner as runner

    class BrokenMarketStructureEngine:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("isolated test failure")

    monkeypatch.setattr(runner, "MarketStructureEngine", BrokenMarketStructureEngine)
    outputs = runner.run_domain_engines("TEST", "1h", _ohlcv_frame(180))

    assert outputs["market_structure"].error is not None
    assert outputs["volume_participation"].error is None
    assert outputs["order_block"].error is None
    assert outputs["fvg"].skipped
