from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import pandas as pd

from .models import EngineResult
from .order_block_engine import (
    OrderBlockConfig,
    OrderBlockEngine as _CoreOrderBlockEngine,
    OrderBlockRecord,
)


class OrderBlockDataQuality(StrEnum):
    """Python-side audit status; deliberately separate from Pine OB math."""

    OK = "OK"
    INCOMPLETE_BAR = "INCOMPLETE_BAR"
    SOURCE_GAP = "SOURCE_GAP"


@dataclass(frozen=True, slots=True)
class OrderBlockSideExport:
    state: float | None = None
    top: float | None = None
    bottom: float | None = None
    fill: float | None = None
    source_bar: float | None = None


@dataclass(frozen=True, slots=True)
class OrderBlockExport:
    """ARGENT Export Contract v1: nearest active OB snapshot per direction."""

    bull: OrderBlockSideExport = OrderBlockSideExport()
    bear: OrderBlockSideExport = OrderBlockSideExport()


class OrderBlockEngine(_CoreOrderBlockEngine):
    """Final v0.4.23 engine facade with the persistent v0.4.22 export contract.

    The supplied v0.4.23 TIME FIX source changes drawing coordinates to source
    time but contains no physical export block despite its EXPORT title. The
    export contract therefore comes only from the supplied v0.4.22 FINAL
    EXPORT source/diff and is applied to the unchanged v0.4.23 lifecycle.

    Export rules are source-faithful:
    - only confirmed 3-evidence, not-fully-used records are eligible;
    - bullish and bearish sides are selected independently;
    - distance is measured to the ACTIVE REMAINING zone;
    - nearest wins; ties within minimum_tick choose newer source_index;
    - open/incomplete bars freeze the last confirmed export snapshot.
    """

    def __init__(self, config: OrderBlockConfig | None = None) -> None:
        super().__init__(config)
        self._export = OrderBlockExport()
        self._last_data_quality = OrderBlockDataQuality.OK

    @property
    def export(self) -> OrderBlockExport:
        return self._export

    @property
    def last_data_quality(self) -> OrderBlockDataQuality:
        return self._last_data_quality

    def _reset(self) -> None:
        super()._reset()
        self._export = OrderBlockExport()
        self._last_data_quality = OrderBlockDataQuality.OK

    def update(self, bar: pd.Series | dict[str, Any]) -> EngineResult | None:
        row = dict(bar)
        if not bool(row.get("is_closed", True)):
            self._last_data_quality = OrderBlockDataQuality.INCOMPLETE_BAR
            return self.snapshot()
        if not bool(row.get("is_complete", True)):
            self._last_data_quality = OrderBlockDataQuality.SOURCE_GAP
            return self.snapshot()

        result = super().update(row)
        self._last_data_quality = OrderBlockDataQuality.OK
        self._export = self._select_export(float(row["close"]))
        return result

    def _select_export(self, close: float) -> OrderBlockExport:
        best_bull: tuple[float, int, OrderBlockSideExport] | None = None
        best_bear: tuple[float, int, OrderBlockSideExport] | None = None

        for record in self.records:
            if not record.active or record.fill_ratio >= self.config.fill_cancel_threshold:
                continue

            active_top, active_bottom = self._active_remaining_zone(record)
            distance = close - active_top if close > active_top else active_bottom - close if close < active_bottom else 0.0
            side = OrderBlockSideExport(
                state=1.0 if record.bullish else -1.0,
                top=active_top,
                bottom=active_bottom,
                fill=record.fill_ratio,
                source_bar=float(record.source_index),
            )
            candidate = (distance, record.source_index, side)

            if record.bullish:
                if self._is_better(candidate, best_bull):
                    best_bull = candidate
            elif self._is_better(candidate, best_bear):
                best_bear = candidate

        return OrderBlockExport(
            bull=best_bull[2] if best_bull is not None else OrderBlockSideExport(),
            bear=best_bear[2] if best_bear is not None else OrderBlockSideExport(),
        )

    def _is_better(
        self,
        candidate: tuple[float, int, OrderBlockSideExport],
        incumbent: tuple[float, int, OrderBlockSideExport] | None,
    ) -> bool:
        if incumbent is None:
            return True
        distance, source_index, _ = candidate
        best_distance, best_source_index, _ = incumbent
        if distance < best_distance:
            return True
        tie = abs(distance - best_distance) <= self.config.minimum_tick
        return tie and source_index > best_source_index

    @staticmethod
    def _active_remaining_zone(record: OrderBlockRecord) -> tuple[float, float]:
        if record.bullish:
            return record.fill_boundary, record.bottom
        return record.top, record.fill_boundary
