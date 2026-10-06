from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import pandas as pd

from .base import BaseEngine
from .models import Direction, EngineResult


@dataclass(frozen=True, slots=True)
class OrderBlockConfig:
    imbalance_max_candle: int = 5
    fill_cancel_threshold: float = 0.70
    minimum_tick: float = 0.01

    def __post_init__(self) -> None:
        if self.imbalance_max_candle not in {3, 4, 5}:
            raise ValueError("imbalance_max_candle must be 3, 4, or 5")
        if not 0.10 <= self.fill_cancel_threshold <= 1.0:
            raise ValueError("fill_cancel_threshold must be between 0.10 and 1.0")
        if self.minimum_tick <= 0:
            raise ValueError("minimum_tick must be positive")


@dataclass(frozen=True, slots=True)
class OrderBlockRecord:
    source_index: int
    source_time: Any
    top: float
    bottom: float
    bullish: bool
    base_score: int
    has_imbalance: bool
    anchor_high: float
    anchor_low: float
    imbalance_end_index: int
    fill_boundary: float

    @property
    def score(self) -> int:
        return self.base_score + (1 if self.has_imbalance else 0)

    @property
    def fill_ratio(self) -> float:
        height = self.top - self.bottom
        if height <= 0:
            return 0.0
        raw = (self.top - self.fill_boundary) / height if self.bullish else (self.fill_boundary - self.bottom) / height
        return min(1.0, max(0.0, raw))

    @property
    def active(self) -> bool:
        return self.has_imbalance and self.score == 3


class OrderBlockEngine(BaseEngine):
    """Source-faithful Tur-1 port of ORDER BLOCK Fill Debug v0.4.23.

    Scope is intentionally limited to the supplied Pine contract:
    A/B source selection, wick replacement, source-local 3rd-5th candle
    imbalance search, pre-confirm fill accumulation, and fill cancellation.
    No BOS/CHoCH, trend, pivot, liquidity, AL/SAT, MTF, or time deletion is
    introduced.
    """

    def __init__(self, config: OrderBlockConfig | None = None) -> None:
        self.config = config or OrderBlockConfig()
        self._rows: list[dict[str, Any]] = []
        self._records: list[OrderBlockRecord] = []
        self._snapshot: EngineResult | None = None

    @staticmethod
    def _normalize_bar(bar: pd.Series | dict[str, Any]) -> dict[str, Any]:
        row = dict(bar)
        for key in ("open", "high", "low", "close", "volume"):
            if key not in row:
                raise ValueError(f"missing required field: {key}")
        row.setdefault("is_closed", True)
        row.setdefault("is_complete", True)
        return row

    @property
    def records(self) -> tuple[OrderBlockRecord, ...]:
        return tuple(self._records)

    @property
    def active_records(self) -> tuple[OrderBlockRecord, ...]:
        return tuple(record for record in self._records if record.active)

    def _reset(self) -> None:
        self._rows = []
        self._records = []
        self._snapshot = None

    def replay(self, frame: pd.DataFrame) -> list[EngineResult]:
        self._reset()
        out: list[EngineResult] = []
        for bar in frame.sort_values("timestamp", kind="stable").to_dict("records"):
            before = len(self._rows)
            result = self.update(bar)
            if len(self._rows) > before and result is not None:
                out.append(result)
        return out

    def snapshot(self) -> EngineResult | None:
        return self._snapshot

    def update(self, bar: pd.Series | dict[str, Any]) -> EngineResult | None:
        row = self._normalize_bar(bar)
        if not bool(row.get("is_closed", True)) or not bool(row.get("is_complete", True)):
            return self._snapshot

        self._rows.append(row)
        index = len(self._rows) - 1

        # Pine order is exact: update existing candidates/OBs first, then create
        # a new A/B candidate from [1]/[0].
        self._update_existing(index, row)
        self._create_from_pair(index)
        self._snapshot = self._build_result(row.get("timestamp"))
        return self._snapshot

    def _update_existing(self, index: int, row: dict[str, Any]) -> None:
        updated: list[OrderBlockRecord] = []
        for record in self._records:
            current = record
            remove = False
            zone_height = current.top - current.bottom
            fill_start = current.source_index + 2

            if index >= fill_start and zone_height > 0:
                bullish_gap_through = current.bullish and float(row["high"]) < current.bottom
                bearish_gap_through = (not current.bullish) and float(row["low"]) > current.top
                if bullish_gap_through or bearish_gap_through:
                    remove = True
                else:
                    entered = float(row["low"]) <= current.top and float(row["high"]) >= current.bottom
                    if entered:
                        if current.bullish:
                            penetrated_low = max(current.bottom, min(current.top, float(row["low"])))
                            boundary = min(current.fill_boundary, penetrated_low)
                        else:
                            penetrated_high = min(current.top, max(current.bottom, float(row["high"])))
                            boundary = max(current.fill_boundary, penetrated_high)
                        if boundary != current.fill_boundary:
                            current = replace(current, fill_boundary=boundary)
                        if current.fill_ratio >= self.config.fill_cancel_threshold:
                            remove = True

            imbalance_start = current.source_index + 2
            if (
                not remove
                and not current.has_imbalance
                and imbalance_start <= index <= current.imbalance_end_index
            ):
                bullish_gap = current.bullish and float(row["low"]) - current.anchor_high >= self.config.minimum_tick
                bearish_gap = (not current.bullish) and current.anchor_low - float(row["high"]) >= self.config.minimum_tick
                if bullish_gap or bearish_gap:
                    current = replace(current, has_imbalance=True)

            if not remove and current.has_imbalance and current.fill_ratio >= self.config.fill_cancel_threshold:
                remove = True

            if not remove and not current.has_imbalance and index > current.imbalance_end_index:
                remove = True

            if not remove:
                updated.append(current)

        self._records = updated

    def _create_from_pair(self, index: int) -> None:
        if index < 1:
            return
        previous = self._rows[index - 1]
        current = self._rows[index]

        bearish_pair = float(previous["close"]) > float(previous["open"]) and float(current["close"]) < float(current["open"])
        if bearish_pair:
            protected = float(current["high"]) <= float(previous["high"])
            self._append_candidate(
                source_index=index - 1 if protected else index,
                bullish=False,
                source=previous if protected else current,
            )

        bullish_pair = float(previous["close"]) < float(previous["open"]) and float(current["close"]) > float(current["open"])
        if bullish_pair:
            protected = float(current["low"]) >= float(previous["low"])
            self._append_candidate(
                source_index=index - 1 if protected else index,
                bullish=True,
                source=previous if protected else current,
            )

    def _append_candidate(self, *, source_index: int, bullish: bool, source: dict[str, Any]) -> None:
        if any(r.source_index == source_index and r.bullish == bullish for r in self._records):
            return
        top = float(source["high"])
        bottom = float(source["low"])
        record = OrderBlockRecord(
            source_index=source_index,
            source_time=source.get("timestamp"),
            top=top,
            bottom=bottom,
            bullish=bullish,
            base_score=2,
            has_imbalance=False,
            anchor_high=top,
            anchor_low=bottom,
            imbalance_end_index=source_index + self.config.imbalance_max_candle - 1,
            fill_boundary=top if bullish else bottom,
        )
        self._records.append(record)

    def _build_result(self, timestamp: Any) -> EngineResult:
        active = self.active_records
        bull = sum(1 for r in active if r.bullish)
        bear = sum(1 for r in active if not r.bullish)
        candidates = len(self._records) - len(active)
        direction = Direction.UP if bull and not bear else Direction.DOWN if bear and not bull else Direction.NEUTRAL
        state = "ACTIVE_OB" if active else "CANDIDATE_ONLY" if self._records else "NO_OB"
        return EngineResult(
            engine="ORDER_BLOCK",
            state=state,
            timestamp=timestamp,
            direction=direction,
            score=None,
            quality=None,
            levels={},
            events=(),
            reasons=(f"active_bull={bull}", f"active_bear={bear}", f"candidates={candidates}"),
            is_confirmed=True,
        )
