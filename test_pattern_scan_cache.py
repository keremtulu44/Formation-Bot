import pandas as pd

from patterns.lifecycle import ArgentEngine, EngineSnapshot, PatternLifecycleManager


def _frame():
    return pd.DataFrame(
        {
            "open": [10.0, 10.5],
            "high": [11.0, 11.5],
            "low": [9.5, 10.0],
            "close": [10.5, 11.0],
            "volume": [100.0, 120.0],
        },
        index=pd.date_range("2026-10-12 09:30", periods=2, freq="h", tz="Europe/Istanbul"),
    )


def test_exact_same_completed_frame_reuses_replay_and_value_change_replays(monkeypatch):
    calls = []

    def fake_process(self, frame, tam_yeniden=False):
        calls.append((frame.copy(deep=True), tam_yeniden))
        self._bars_done = len(frame)
        self._last_index_value = frame.index[-1]
        return EngineSnapshot(state=f"bars-{len(frame)}-run-{len(calls)}")

    monkeypatch.setattr(ArgentEngine, "process", fake_process)
    manager = PatternLifecycleManager()
    history_writes = []
    monkeypatch.setattr(manager, "_history_kaydet", lambda *args: history_writes.append(args[-1]))

    source = _frame()
    first = manager.scan_if_unchanged("THYAO_1h", source, tam_yeniden=True)
    second = manager.scan_if_unchanged("THYAO_1h", source.copy(deep=True), tam_yeniden=True)

    assert len(calls) == 1
    assert first.state == second.state == "bars-2-run-1"
    assert first is not second
    assert manager.last_scan_was_cached is True
    assert len(history_writes) == 2

    second.state = "caller mutation"
    unchanged = manager.scan_if_unchanged("THYAO_1h", source.copy(deep=True), tam_yeniden=True)
    assert len(calls) == 1
    assert unchanged.state == "bars-2-run-1"

    revised = source.copy(deep=True)
    revised.loc[revised.index[-1], "close"] += 0.25
    third = manager.scan_if_unchanged("THYAO_1h", revised, tam_yeniden=True)

    assert len(calls) == 2
    assert calls[-1][1] is True
    assert third.state == "bars-2-run-2"
    assert manager.last_scan_was_cached is False


def test_timeframe_change_invalidates_exact_frame_cache(monkeypatch):
    calls = []

    def fake_process(self, frame, tam_yeniden=False):
        calls.append(self.timeframe)
        self._bars_done = len(frame)
        self._last_index_value = frame.index[-1]
        return EngineSnapshot(state=f"run-{len(calls)}-{self.timeframe}")

    monkeypatch.setattr(ArgentEngine, "process", fake_process)
    manager = PatternLifecycleManager()
    monkeypatch.setattr(manager, "_history_kaydet", lambda *_args: None)

    source = _frame()
    manager.scan_if_unchanged("THYAO", source, timeframe="1h")
    result = manager.scan_if_unchanged("THYAO", source.copy(), timeframe="2h")

    assert calls == ["1h", "2h"]
    assert result.state == "run-2-2h"
    assert manager.last_scan_was_cached is False


def test_non_full_replay_path_does_not_use_exact_frame_cache(monkeypatch):
    calls = []

    def fake_process(self, frame, tam_yeniden=False):
        calls.append(tam_yeniden)
        self._bars_done = len(frame)
        self._last_index_value = frame.index[-1]
        return EngineSnapshot(state=f"run-{len(calls)}")

    monkeypatch.setattr(ArgentEngine, "process", fake_process)
    manager = PatternLifecycleManager()
    monkeypatch.setattr(manager, "_history_kaydet", lambda *_args: None)

    source = _frame()
    manager.scan_if_unchanged("THYAO_1h", source, tam_yeniden=True)
    result = manager.scan_if_unchanged("THYAO_1h", source.copy(), tam_yeniden=False)

    assert calls == [True, False]
    assert result.state == "run-2"
    assert manager.last_scan_was_cached is False
