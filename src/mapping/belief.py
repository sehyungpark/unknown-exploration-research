"""UNKNOWN/FREE/OCCUPIED belief grids with monotone updates only."""

from collections.abc import Iterator, Mapping

from src.utils import BeliefState, Coord, TruthState


class BeliefGrid:
    """Mutable belief state whose known cells can never revert or switch."""

    def __init__(self, cells: list[list[BeliefState]]) -> None:
        if not cells:
            raise ValueError("belief grid must contain at least one row")
        width = len(cells[0])
        if width == 0:
            raise ValueError("belief grid rows must not be empty")
        if any(len(row) != width for row in cells):
            raise ValueError("belief grid must be rectangular")
        if any(not isinstance(cell, BeliefState) for row in cells for cell in row):
            raise TypeError("belief cells must be BeliefState values")
        self._cells = [row.copy() for row in cells]

    @classmethod
    def unknown(cls, height: int, width: int) -> "BeliefGrid":
        if height <= 0 or width <= 0:
            raise ValueError("belief dimensions must be positive")
        return cls([[BeliefState.UNKNOWN for _ in range(width)] for _ in range(height)])

    @property
    def height(self) -> int:
        return len(self._cells)

    @property
    def width(self) -> int:
        return len(self._cells[0])

    @property
    def shape(self) -> tuple[int, int]:
        return self.height, self.width

    def in_bounds(self, coord: Coord) -> bool:
        row, col = coord
        return 0 <= row < self.height and 0 <= col < self.width

    def state(self, coord: Coord) -> BeliefState:
        if not self.in_bounds(coord):
            raise IndexError(f"coordinate outside belief grid: {coord}")
        row, col = coord
        return self._cells[row][col]

    def iter_coords(self) -> Iterator[Coord]:
        for row in range(self.height):
            for col in range(self.width):
                yield row, col

    def known_free(self, coord: Coord) -> bool:
        return self.in_bounds(coord) and self.state(coord) is BeliefState.FREE

    def unknown_cells(self) -> frozenset[Coord]:
        return frozenset(
            coord for coord in self.iter_coords() if self.state(coord) is BeliefState.UNKNOWN
        )

    def apply_observations(
        self, observations: Mapping[Coord, TruthState]
    ) -> frozenset[Coord]:
        """Apply a correct observation batch atomically and monotonically."""

        pending: list[tuple[Coord, BeliefState]] = []
        for coord, truth_state in observations.items():
            if not self.in_bounds(coord):
                raise IndexError(f"observation outside belief grid: {coord}")
            if not isinstance(truth_state, TruthState):
                raise TypeError("observations must contain TruthState values")
            new_state = (
                BeliefState.FREE
                if truth_state is TruthState.FREE
                else BeliefState.OCCUPIED
            )
            old_state = self.state(coord)
            if old_state is BeliefState.UNKNOWN:
                pending.append((coord, new_state))
            elif old_state is not new_state:
                raise ValueError(
                    f"non-monotone or contradictory update at {coord}: "
                    f"{old_state.value} -> {new_state.value}"
                )

        for (row, col), new_state in pending:
            self._cells[row][col] = new_state
        return frozenset(coord for coord, _ in pending)

    def snapshot(self) -> tuple[tuple[BeliefState, ...], ...]:
        return tuple(tuple(row) for row in self._cells)
