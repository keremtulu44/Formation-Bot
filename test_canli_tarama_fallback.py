"""Canli tarama must analyze only frames accepted into its validated cache.

Every frame/cache here is synthetic and every filesystem write is confined to
pytest's tmp_path. The fetch function, pacer and lifecycle are fakes; no network
or repository bot_data is accessed.
"""

from datetime import datetime, timedelta

import pandas as pd
import pytest

import canli_tarama
import config
from data import StockDequeManager
from patterns.lifecycle import EngineSnapshot
from test_live_data_flow import FakePacer, sentetik_1h

IST = config.ISTANBUL_TZ


def _invalid_frame(case):
    frame = sentetik_1h(60, datetime.now(IST) - timedelta(hours=2), base=80.0)
    row = frame.index[-1]
    if case == "impossible_ohlc":
        frame.loc[row, "high"] = frame.loc[row, "low"] - 1.0
    elif case == "nan":
        frame.loc[row, "close"] = float("nan")
    elif case == "infinity":
        frame.loc[row, "volume"] = float("inf")
    elif case == "negative_price":
        frame.loc[row, "low"] = -1.0
    elif case == "negative_volume":
        frame.loc[row, "volume"] = -1.0
    elif case == "missing_column":
        frame = frame.drop(columns=["volume"])
    elif case == "empty":
        frame = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    else:  # pragma: no cover - test matrix typo guard
        raise AssertionError(case)
    return frame


class _RecordingLifecycle:
    def __init__(self):
        self.frames = []

    def scan(self, _key, frame):
        self.frames.append(frame.copy(deep=True))
        return EngineSnapshot(active=None, state="NONE")


def _run_scan(tmp_path, monkeypatch, manager, fetched):
    work_dir = tmp_path / "working-directory"
    work_dir.mkdir(exist_ok=True)
    monkeypatch.chdir(work_dir)
    monkeypatch.setattr(canli_tarama, "ACTIVE_STOCKS", ["THYAO"])
    monkeypatch.setattr(canli_tarama, "StockDequeManager", lambda: manager)
    lifecycle = _RecordingLifecycle()
    monkeypatch.setattr(canli_tarama, "PatternLifecycleManager", lambda: lifecycle)
    monkeypatch.setattr(canli_tarama, "YahooRequestPacer", lambda **_kwargs: FakePacer())
    monkeypatch.setattr(canli_tarama, "taze_veri_cek", lambda _stock: fetched.copy(deep=True))
    monkeypatch.setattr(manager, "gunluk_veri_eksik_mi", lambda _stock: False)
    resampled_inputs = []

    def record_resample(frame):
        resampled_inputs.append(frame.copy(deep=True))
        return {timeframe: frame for timeframe in canli_tarama.TFLER}

    monkeypatch.setattr(canli_tarama, "resample_all_timeframes", record_resample)
    monkeypatch.setattr(canli_tarama, "tamamlanmis_mumlar", lambda frame, _tf: frame)
    monkeypatch.setattr(canli_tarama.sys, "argv", ["canli_tarama.py"])
    canli_tarama.main()
    return resampled_inputs, lifecycle.frames


@pytest.mark.parametrize(
    "case",
    [
        "impossible_ohlc",
        "nan",
        "infinity",
        "negative_price",
        "negative_volume",
        "missing_column",
        "empty",
    ],
)
def test_rejected_successful_fetch_uses_validated_cache_only(
    tmp_path, monkeypatch, case
):
    manager = StockDequeManager(data_dir=str(tmp_path / "cache"))
    cached = sentetik_1h(60, datetime.now(IST) - timedelta(hours=3), base=100.0)
    assert manager.append_dataframe("THYAO", cached) is True
    before = manager.to_dataframe("THYAO").copy(deep=True)

    resampled_inputs, analyzed_inputs = _run_scan(
        tmp_path, monkeypatch, manager, _invalid_frame(case)
    )

    assert resampled_inputs, "rejected fetch should fall back to the existing cache"
    for frame in resampled_inputs + analyzed_inputs:
        pd.testing.assert_frame_equal(frame, before)
    pd.testing.assert_frame_equal(manager.to_dataframe("THYAO"), before)


@pytest.mark.parametrize(
    "case",
    [
        "impossible_ohlc",
        "nan",
        "infinity",
        "negative_price",
        "negative_volume",
        "missing_column",
        "empty",
    ],
)
def test_rejected_fetch_without_cache_never_reaches_resample_or_analysis(
    tmp_path, monkeypatch, case
):
    manager = StockDequeManager(data_dir=str(tmp_path / "empty-cache"))

    resampled_inputs, analyzed_inputs = _run_scan(
        tmp_path, monkeypatch, manager, _invalid_frame(case)
    )

    assert resampled_inputs == []
    assert analyzed_inputs == []
    assert manager.to_dataframe("THYAO") is None
