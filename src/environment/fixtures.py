"""Small fixed deterministic ground-truth maps for correctness work."""

from dataclasses import dataclass

from src.utils import Coord, TruthState

from .grid import GroundTruthGrid

FIXTURE_SIZE = 20


@dataclass(frozen=True, slots=True)
class MapFixture:
    name: str
    ground_truth: GroundTruthGrid
    start: Coord

    def __post_init__(self) -> None:
        if self.ground_truth.state(self.start) is not TruthState.FREE:
            raise ValueError(f"fixture start must be FREE: {self.name}")


def _canvas(fill: str = ".") -> list[list[str]]:
    return [[fill for _ in range(FIXTURE_SIZE)] for _ in range(FIXTURE_SIZE)]


def _bordered_room() -> list[list[str]]:
    cells = _canvas()
    for index in range(FIXTURE_SIZE):
        cells[0][index] = "#"
        cells[-1][index] = "#"
        cells[index][0] = "#"
        cells[index][-1] = "#"
    return cells


def _to_grid(cells: list[list[str]]) -> GroundTruthGrid:
    return GroundTruthGrid.from_ascii("".join(row) for row in cells)


def open_fixture() -> MapFixture:
    return MapFixture("open", _to_grid(_canvas()), (10, 10))


def single_room_fixture() -> MapFixture:
    return MapFixture("single_room", _to_grid(_bordered_room()), (10, 10))


def corridor_fixture() -> MapFixture:
    cells = _canvas("#")
    for col in range(1, 19):
        cells[10][col] = "."
    return MapFixture("corridor", _to_grid(cells), (10, 1))


def dead_end_fixture() -> MapFixture:
    cells = _canvas("#")
    for col in range(1, 19):
        cells[10][col] = "."
    for row in range(4, 11):
        cells[row][12] = "."
    return MapFixture("dead_end", _to_grid(cells), (10, 1))


def separated_rooms_fixture() -> MapFixture:
    cells = _bordered_room()
    for row in range(1, 19):
        cells[row][10] = "#"
    cells[5][10] = "."
    cells[14][10] = "."
    return MapFixture("separated_rooms", _to_grid(cells), (10, 5))


def clutter_fixture() -> MapFixture:
    cells = _bordered_room()
    obstacles = {
        (3, 5), (3, 6), (4, 5),
        (6, 13), (7, 13), (8, 13),
        (9, 7), (9, 8), (10, 7), (10, 8),
        (13, 4), (14, 4), (14, 5),
        (14, 14), (14, 15), (15, 14), (15, 15),
    }
    for row, col in obstacles:
        cells[row][col] = "#"
    return MapFixture("clutter", _to_grid(cells), (2, 2))


def maze_like_fixture() -> MapFixture:
    cells = _bordered_room()
    for wall_index, col in enumerate((4, 8, 12, 16)):
        gap_row = 17 if wall_index % 2 == 0 else 2
        for row in range(1, 19):
            if row != gap_row:
                cells[row][col] = "#"
    return MapFixture("maze_like", _to_grid(cells), (1, 1))


def deterministic_fixtures() -> tuple[MapFixture, ...]:
    return (
        open_fixture(),
        single_room_fixture(),
        corridor_fixture(),
        dead_end_fixture(),
        separated_rooms_fixture(),
        clutter_fixture(),
        maze_like_fixture(),
    )
