"""Core grid state types used by every simulator component."""

from enum import Enum
from typing import TypeAlias

Coord: TypeAlias = tuple[int, int]


class TruthState(Enum):
    FREE = "FREE"
    OCCUPIED = "OCCUPIED"


class BeliefState(Enum):
    UNKNOWN = "UNKNOWN"
    FREE = "FREE"
    OCCUPIED = "OCCUPIED"
