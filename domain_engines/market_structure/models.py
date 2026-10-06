from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class Direction(IntEnum):
    DOWN = -1
    NEUTRAL = 0
    UP = 1


@dataclass(frozen=True, slots=True)
class EngineResult:
    engine: str
    state: str
    timestamp: Any
    direction: Direction = Direction.NEUTRAL
    score: float | None = None
    quality: float | None = None
    levels: dict[str, float] = field(default_factory=dict)
    events: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    is_confirmed: bool = True
