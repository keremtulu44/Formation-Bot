"""Safe append/rolling-window state management for the OB and FVG engines.

The engines remain the sole owners of their native detection and lifecycle
rules. This module only decides whether their existing ``update`` path is safe,
rebases OB frame-relative indexes when an exact rolling prefix is removed, and
falls back to full replay whenever the input state cannot be proven compatible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import pandas as pd

from .adapter import to_domain_frame


DomainName = Literal["fvg", "order_block"]


@dataclass(frozen=True, slots=True)
class IncrementalDecision:
    mode: str
    reason: str | None
    updated_bars: int


class IncrementalEngineState:
    """One independent engine cursor for one caller-owned symbol/timeframe key.

    The runner owns the map keyed by ``(symbol, timeframe, engine config)``;
    this object owns only one OB or FVG engine and its last verified frame.
    It is deliberately in-memory: after restart, a new object cold-replays the
    available completed frame instead of restoring an unverified checkpoint.
    """

    def __init__(self, domain: DomainName, engine: Any) -> None:
        if domain not in ("fvg", "order_block"):
            raise ValueError(f"incremental state is not supported for {domain!r}")
        self.domain = domain
        self.engine = engine
        self.last_frame: pd.DataFrame | None = None
        self.last_decision: IncrementalDecision | None = None
        self.last_result: Any = None
        self.full_replay_count = 0
        self.incremental_update_count = 0
        self.window_slide_count = 0
        self._incremental_safe = True

    def advance(self, frame: pd.DataFrame) -> IncrementalDecision:
        """Advance safely; if engine code raises, never trust its partial state."""
        try:
            return self._advance(frame)
        except Exception:
            self._incremental_safe = False
            raise

    def _advance(self, frame: pd.DataFrame) -> IncrementalDecision:
        """Advance to ``frame`` without changing engine math or inventing bars."""
        incoming = to_domain_frame(frame)
        prepared, conflicting_duplicate = _drop_identical_timestamp_duplicates(incoming)

        if conflicting_duplicate:
            return self._replay(
                incoming,
                "full_replay_conflicting_timestamp",
                "duplicate timestamp cannot be verified or carries different OHLCV",
                incremental_safe=False,
            )

        if self.last_frame is None:
            return self._replay(prepared, "cold_full_replay", "no in-memory engine state")

        if not self._incremental_safe:
            return self._replay(
                prepared,
                "full_replay_untrusted_state",
                "previous replay contained bars the engine could not incrementally retain",
            )

        if _frames_equal(self.last_frame, prepared):
            return self._record_decision("unchanged_frame", None, 0)

        if _is_prefix(self.last_frame, prepared):
            new_rows = prepared.iloc[len(self.last_frame):].reset_index(drop=True)
            updated = self._update_rows(new_rows)
            if updated is None:
                return self._replay(
                    prepared,
                    "full_replay_update_mismatch",
                    "engine did not append every supplied completed row",
                )
            return self._finish_incremental(prepared, "append", updated)

        overlap = _suffix_prefix_overlap(self.last_frame, prepared)
        if self.domain == "order_block" and overlap > 0:
            dropped = len(self.last_frame) - overlap
            new_rows = prepared.iloc[overlap:].reset_index(drop=True)
            if dropped > 0 and len(new_rows) >= dropped:
                updated = self._advance_order_block_window(new_rows, dropped)
                if updated is not None and _engine_window_matches(self.engine, prepared, self.domain):
                    self.last_frame = prepared.copy(deep=True)
                    return self._finish_incremental(prepared, "rolling_window_update", updated)
                return self._replay(
                    prepared,
                    "full_replay_ob_window_mismatch",
                    "rebased OB state did not match the requested frame",
                )

        if self.domain == "fvg" and overlap > 0:
            dropped = len(self.last_frame) - overlap
            new_rows = prepared.iloc[overlap:].reset_index(drop=True)
            if dropped > 0 and len(new_rows) >= dropped and len(new_rows) > 0:
                updated = self._replay_fvg_window_steps(new_rows, dropped)
                if updated is not None and _engine_window_matches(self.engine, prepared, self.domain):
                    self.last_frame = prepared.copy(deep=True)
                    return self._finish_incremental(prepared, "rolling_window_replay_fallback", updated)

        return self._replay(
            prepared,
            "full_replay_frame_mismatch",
            "prefix/rolling overlap could not be verified exactly",
        )

    def _update_rows(self, rows: pd.DataFrame) -> int | None:
        updated = 0
        for row in rows.to_dict("records"):
            before = len(getattr(self.engine, "_rows", ()))
            self.last_result = self.engine.update(row)
            after = len(getattr(self.engine, "_rows", ()))
            if after != before + 1:
                return None
            updated += 1
        return updated

    def _advance_order_block_window(self, rows: pd.DataFrame, dropped: int) -> int | None:
        updated = 0
        for position, row in enumerate(rows.to_dict("records")):
            if position < dropped:
                try:
                    self.engine.slide_window(1)
                except (TypeError, ValueError, IndexError):
                    return None
                self.window_slide_count += 1
            before = len(getattr(self.engine, "_rows", ()))
            self.last_result = self.engine.update(row)
            after = len(getattr(self.engine, "_rows", ()))
            if after != before + 1:
                return None
            updated += 1
        return updated

    def _replay_fvg_window_steps(self, rows: pd.DataFrame, dropped: int) -> int | None:
        """Replay each missed rolling FVG window in bar order.

        The left-edge ATR seed is frame-relative. On a shifted window it is not
        safe to carry the old RMA/lifecycle state. Each newly observed bar is
        therefore replayed against its exact intermediate frame; the optimized
        detector cache makes each such replay linear in that frame.
        """
        assert self.last_frame is not None
        previous = self.last_frame.copy(deep=True)
        updated = 0
        for position in range(len(rows)):
            drop_before = min(position + 1, dropped)
            step = pd.concat(
                [
                    previous.iloc[drop_before:].reset_index(drop=True),
                    rows.iloc[:position + 1].reset_index(drop=True),
                ],
                ignore_index=True,
            )
            replay_results = self.engine.replay(step)
            self.last_result = replay_results[-1] if replay_results else None
            self.full_replay_count += 1
            if len(getattr(self.engine, "_rows", ())) != len(step):
                return None
            updated += 1
        return updated

    def _finish_incremental(
        self,
        frame: pd.DataFrame,
        mode: str,
        updated: int,
    ) -> IncrementalDecision:
        self.last_frame = frame.copy(deep=True)
        if mode != "rolling_window_replay_fallback":
            self.incremental_update_count += updated
        self._incremental_safe = _engine_window_matches(self.engine, frame, self.domain)
        if not self._incremental_safe:
            return self._replay(
                frame,
                "full_replay_state_unverified",
                "engine row window differs from the canonical completed frame",
            )
        return self._record_decision(mode, None, updated)

    def _replay(
        self,
        frame: pd.DataFrame,
        mode: str,
        reason: str | None,
        *,
        incremental_safe: bool = True,
    ) -> IncrementalDecision:
        replay_results = self.engine.replay(frame.copy(deep=True))
        self.last_result = replay_results[-1] if replay_results else None
        self.full_replay_count += 1
        self.last_frame = frame.copy(deep=True)
        self._incremental_safe = incremental_safe and _engine_window_matches(self.engine, frame, self.domain)
        if not self._incremental_safe and reason is None:
            reason = "replay state does not map one-to-one to input rows"
        return self._record_decision(mode, reason, len(getattr(self.engine, "_rows", ())))

    def _record_decision(self, mode: str, reason: str | None, updated: int) -> IncrementalDecision:
        decision = IncrementalDecision(mode, reason, updated)
        self.last_decision = decision
        return decision


def _drop_identical_timestamp_duplicates(frame: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    """Drop exact duplicate completed candles; flag same-time OHLCV conflicts."""
    if "timestamp" not in frame.columns or not frame["timestamp"].duplicated().any():
        return frame.reset_index(drop=True), False

    required = ("open", "high", "low", "close", "volume")
    if any(name not in frame.columns for name in required):
        # An absent OHLCV component means duplicate identity cannot be proven.
        return frame.reset_index(drop=True), True
    keep_positions: list[int] = []
    first_by_timestamp: dict[Any, int] = {}
    conflict = False
    for position, row in enumerate(frame.to_dict("records")):
        timestamp = row["timestamp"]
        first_position = first_by_timestamp.get(timestamp)
        if first_position is None:
            first_by_timestamp[timestamp] = position
            keep_positions.append(position)
            continue
        first_row = frame.iloc[first_position]
        first_values = [first_row[name] for name in required]
        duplicate_values = [row[name] for name in required]
        if any(_is_missing(value) for value in (*first_values, *duplicate_values)) or not _same_values(
            first_values,
            duplicate_values,
        ):
            conflict = True
            # Keep the original duplicate frame intact for deterministic replay.
            return frame.reset_index(drop=True), True
    return frame.iloc[keep_positions].reset_index(drop=True), conflict


def _is_missing(value: Any) -> bool:
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _same_values(left: list[Any], right: list[Any]) -> bool:
    if len(left) != len(right):
        return False
    for a, b in zip(left, right):
        try:
            a_missing = bool(pd.isna(a))
            b_missing = bool(pd.isna(b))
        except (TypeError, ValueError):
            a_missing = b_missing = False
        if a_missing or b_missing or a != b:
            return False
    return True


def _frames_equal(left: pd.DataFrame, right: pd.DataFrame) -> bool:
    return left.reset_index(drop=True).equals(right.reset_index(drop=True))


def _is_prefix(prefix: pd.DataFrame, frame: pd.DataFrame) -> bool:
    if len(prefix) > len(frame) or list(prefix.columns) != list(frame.columns):
        return False
    return _frames_equal(prefix, frame.iloc[:len(prefix)])


def _suffix_prefix_overlap(old: pd.DataFrame, new: pd.DataFrame) -> int:
    if list(old.columns) != list(new.columns):
        return 0
    limit = min(len(old), len(new))
    for overlap in range(limit, 0, -1):
        if _frames_equal(old.iloc[-overlap:], new.iloc[:overlap]):
            return overlap
    return 0


def _engine_window_matches(engine: Any, frame: pd.DataFrame, domain: DomainName) -> bool:
    rows = getattr(engine, "_rows", None)
    if rows is None or len(rows) != len(frame):
        return False
    expected_columns = ("timestamp", "open", "high", "low", "close", "volume")
    for index, expected in enumerate(frame.to_dict("records")):
        actual = rows[index]
        for column in expected_columns:
            if column not in actual:
                return False
            if column not in expected:
                if column == "volume" and domain == "fvg":
                    expected_value = 0.0
                else:
                    return False
            else:
                expected_value = expected[column]
            if not _same_values([actual[column]], [expected_value]):
                return False
    return True
