"""Validated finite deterministic ground-truth occupancy grids."""

from dataclasses import dataclass
from typing import Iterable, Iterator

from src.utils import Coord, TruthState


@dataclass(frozen=True, slots=True)
class GroundTruthGrid:
    """A finite rectangular FREE/OCCUPIED ground-truth grid."""

    cells: tuple[tuple[TruthState, ...], ...]

    def __post_init__(self) -> None:
        if not self.cells:
            raise ValueError("ground-truth grid must contain at least one row")
        width = len(self.cells[0])
        if width == 0:
            raise ValueError("ground-truth grid rows must not be empty")
        for row in self.cells:
            if len(row) != width:
                raise ValueError("ground-truth grid must be rectangular")
            if any(not isinstance(cell, TruthState) for cell in row):
                raise TypeError("ground-truth cells must be TruthState values")

    @classmethod
    def from_ascii(
        cls,
        rows: Iterable[str],
        *,
        free: str = ".",
        occupied: str = "#",
    ) -> "GroundTruthGrid":
        materialized = tuple(rows)
        if free == occupied:
            raise ValueError("FREE and OCCUPIED symbols must differ")
        parsed: list[tuple[TruthState, ...]] = []
        for row in materialized:
            parsed_row: list[TruthState] = []
            for symbol in row:
                if symbol == free:
                    parsed_row.append(TruthState.FREE)
                elif symbol == occupied:
                    parsed_row.append(TruthState.OCCUPIED)
                else:
                    raise ValueError(f"unsupported map symbol: {symbol!r}")
            parsed.append(tuple(parsed_row))
        return cls(tuple(parsed))

    @property
    def height(self) -> int:
        return len(self.cells)

    @property
    def width(self) -> int:
        return len(self.cells[0])

    @property
    def shape(self) -> tuple[int, int]:
        return self.height, self.width

    def in_bounds(self, coord: Coord) -> bool:
        row, col = coord
        return 0 <= row < self.height and 0 <= col < self.width

    def state(self, coord: Coord) -> TruthState:
        if not self.in_bounds(coord):
            raise IndexError(f"coordinate outside grid: {coord}")
        row, col = coord
        return self.cells[row][col]

    def iter_coords(self) -> Iterator[Coord]:
        for row in range(self.height):
            for col in range(self.width):
                yield row, col
