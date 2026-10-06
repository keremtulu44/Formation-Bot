from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum


class FvgDirection(IntEnum):
    NONE = 0
    BULLISH = 1
    BEARISH = -1


class FvgState(IntEnum):
    NONE = 1
    CANDIDATE = 2
    ACTIVE = 3
    FIRST_TEST = 4
    PARTIAL_FILL = 5
    DEEP_TEST = 6
    FULL_FILL = 7
    REACTION = 8
    FAILED_REACTION = 9
    INVALID = 10
    SUPERSEDED = 11


class EngulfingDirection(IntEnum):
    NONE = 0
    BULLISH = 1
    BEARISH = -1


class EngulfingState(IntEnum):
    NONE = 0
    ACTIVE = 1
    FIRST_TEST = 2
    PARTIAL_RETRACE = 3
    CONTINUATION_CONFIRMED = 4
    WEAKENED = 5
    INVALID = 6
    EXPIRED = 7


class SensitivityProfile(StrEnum):
    SENSITIVE = "Hassas"
    BALANCED = "Dengeli"
    SELECTIVE = "Seçici"


class FvgEngulfingDataQuality(StrEnum):
    OK = "OK"
    WARMUP = "WARMUP"
    INCOMPLETE_BAR = "INCOMPLETE_BAR"
    SOURCE_GAP = "SOURCE_GAP"
    UNSUPPORTED_TIMEFRAME = "UNSUPPORTED_TIMEFRAME"


SUPPORTED_TIMEFRAMES = frozenset({"2h", "4h", "1d"})

ATR_LENGTH = 14
FLOW_LENGTH = 4
LOCAL_CONTEXT_LENGTH = 4
MINIMUM_HISTORY_BARS = 100

SAFE_DENOMINATOR_FLOOR = 1e-10
FVG_CANDIDATE_SIZE_FACTOR = 0.70
FVG_CANDIDATE_QUALITY_OFFSET = 12.0
FVG_DISPLACEMENT_EXTRA_FACTOR = 1.25
FVG_PROGRESS_EXTRA_FACTOR = 1.15
FVG_SIZE_EXTRA_FACTOR = 1.10
FVG_REACTION_DISTANCE_FACTOR = 0.10
FVG_REACTION_FLOW_FACTOR = 0.50
FVG_TAKEOVER_AGE_FACTOR = 0.60
FVG_TAKEOVER_QUALITY_MARGIN = 4.0
FVG_TAKEOVER_DISTANCE_MARGIN = 0.20

ENGULFING_PARTIAL_RETRACE_THRESHOLD = 0.25
ENGULFING_DEEP_RETRACE_THRESHOLD = 0.50


@dataclass(frozen=True, slots=True)
class FvgEngulfingConfig:
    sensitivity: SensitivityProfile = SensitivityProfile.BALANCED
    timeframe: str = "4h"
    minimum_tick: float = 0.01

    def __post_init__(self) -> None:
        normalized = self.timeframe.lower()
        if normalized not in SUPPORTED_TIMEFRAMES:
            raise ValueError("FVG/Engulfing supports only 2h, 4h, or 1d")
        if self.minimum_tick <= 0:
            raise ValueError("minimum_tick must be positive")
        object.__setattr__(self, "timeframe", normalized)
