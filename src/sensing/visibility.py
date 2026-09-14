"""Physical ground-truth sensing and optimistic belief visibility."""

from collections.abc import Iterator
from math import ceil

from src.environment.grid import GroundTruthGrid
from src.mapping import BeliefGrid
from src.utils import BeliefState, Coord, TruthState

from .supercover import supercover_line


def cells_within_range(
    origin: Coord, shape: tuple[int, int], sensor_range: float
) -> Iterator[Coord]:
    """Yield in-grid target cells in lexicographic order within Euclidean range."""

    if sensor_range < 0:
        raise ValueError("sensor range must be nonnegative")
    height, width = shape
    if height <= 0 or width <= 0:
        raise ValueError("grid dimensions must be positive")
    origin_row, origin_col = origin
    if not (0 <= origin_row < height and 0 <= origin_col < width):
        raise ValueError(f"origin outside grid: {origin}")

    radius = ceil(sensor_range)
    range_squared = sensor_range * sensor_range
    for row in range(max(0, origin_row - radius), min(height, origin_row + radius + 1)):
        for col in range(
            max(0, origin_col - radius), min(width, origin_col + radius + 1)
        ):
            squared_distance = (row - origin_row) ** 2 + (col - origin_col) ** 2
            if squared_distance <= range_squared:
                yield row, col


def physical_visible_cells(
    ground_truth: GroundTruthGrid,
    origin: Coord,
    sensor_range: float = 8,
) -> frozenset[Coord]:
    """Return physically visible target cells under first-hit OCCUPIED occlusion."""

    if ground_truth.state(origin) is not TruthState.FREE:
        raise ValueError("physical sensor origin must be ground-truth FREE")

    visible: set[Coord] = set()
    for target in cells_within_range(origin, ground_truth.shape, sensor_range):
        line = supercover_line(origin, target)
        if any(
            ground_truth.state(cell) is TruthState.OCCUPIED
            for cell in line[1:-1]
        ):
            continue
        visible.add(target)
    return frozenset(visible)


def physical_scan(
    ground_truth: GroundTruthGrid,
    origin: Coord,
    sensor_range: float = 8,
) -> dict[Coord, TruthState]:
    """Return deterministic correct observations for one physical scan."""

    return {
        coord: ground_truth.state(coord)
        for coord in sorted(physical_visible_cells(ground_truth, origin, sensor_range))
    }


def optimistic_visible_unknown_cells(
    belief: BeliefGrid,
    origin: Coord,
    sensor_range: float = 8,
) -> frozenset[Coord]:
    """Return exact A_t(v): visible UNKNOWN cells with UNKNOWN transparent."""

    if not belief.known_free(origin):
        raise ValueError("planning visibility origin must be known FREE")

    visible_unknown: set[Coord] = set()
    for target in cells_within_range(origin, belief.shape, sensor_range):
        if belief.state(target) is not BeliefState.UNKNOWN:
            continue
        line = supercover_line(origin, target)
        if any(
            belief.state(cell) is BeliefState.OCCUPIED for cell in line[1:-1]
        ):
            continue
        visible_unknown.add(target)
    return frozenset(visible_unknown)
