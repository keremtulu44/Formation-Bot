from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd

from .models import EngineResult


class BaseEngine(ABC):
    """Common contract for replay and incremental/live engine implementations."""

    @abstractmethod
    def replay(self, frame: pd.DataFrame) -> list[EngineResult]:
        """Rebuild deterministic engine history from ordered canonical candles."""
        raise NotImplementedError

    @abstractmethod
    def update(self, bar: pd.Series | dict[str, Any]) -> EngineResult | None:
        """Advance engine state with one new candle."""
        raise NotImplementedError

    @abstractmethod
    def snapshot(self) -> EngineResult | None:
        """Return the current immutable public engine state."""
        raise NotImplementedError
