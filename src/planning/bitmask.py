"""Compact row-major bitset helpers for Algorithm C*."""

from collections.abc import Iterable

from src.mapping import BeliefGrid
from src.sensing import cells_within_range
from src.utils import BeliefState, Coord


def _validate_shape(shape: tuple[int, int]) -> tuple[int, int]:
    height, width = shape
    if height <= 0 or width <= 0:
        raise ValueError("grid dimensions must be positive")
    return height, width


def coord_index(coord: Coord, shape: tuple[int, int]) -> int:
    """Return the row-major bit index for one in-grid coordinate."""

    height, width = _validate_shape(shape)
    row, col = coord
    if not (0 <= row < height and 0 <= col < width):
        raise IndexError(f"coordinate outside grid: {coord}")
    return row * width + col


def index_coord(index: int, shape: tuple[int, int]) -> Coord:
    """Invert :func:`coord_index` for diagnostics and tests."""

    height, width = _validate_shape(shape)
    if type(index) is not int or not (0 <= index < height * width):
        raise IndexError(f"bit index outside grid: {index!r}")
    return divmod(index, width)


def coord_bit(coord: Coord, shape: tuple[int, int]) -> int:
    return 1 << coord_index(coord, shape)


def coords_to_mask(coords: Iterable[Coord], shape: tuple[int, int]) -> int:
    """Encode coordinates exactly as one Python arbitrary-precision integer."""

    mask = 0
    for coord in coords:
        mask |= coord_bit(coord, shape)
    return mask


def mask_to_coords(mask: int, shape: tuple[int, int]) -> frozenset[Coord]:
    """Decode an in-grid mask for diagnostics and tests."""

    if type(mask) is not int or mask < 0:
        raise ValueError("mask must be a nonnegative int")
    height, width = _validate_shape(shape)
    if mask >> (height * width):
        raise ValueError("mask contains bits outside grid")
    cells: set[Coord] = set()
    bits = mask
    while bits:
        least = bits & -bits
        index = least.bit_length() - 1
        cells.add(index_coord(index, shape))
        bits ^= least
    return frozenset(cells)


def unknown_mask_from_belief(belief: BeliefGrid) -> int:
    """Encode exactly the UNKNOWN cells in one belief snapshot."""

    return coords_to_mask(
        (
            coord
            for coord in belief.iter_coords()
            if belief.state(coord) is BeliefState.UNKNOWN
        ),
        belief.shape,
    )


def sensor_range_mask(
    origin: Coord,
    shape: tuple[int, int],
    sensor_range: float,
) -> int:
    """Encode the exact canonical Euclidean sensor footprint."""

    return coords_to_mask(
        cells_within_range(origin, shape, sensor_range),
        shape,
    )


def intersection_count(left: int, right: int) -> int:
    if type(left) is not int or left < 0:
        raise ValueError("left mask must be a nonnegative int")
    if type(right) is not int or right < 0:
        raise ValueError("right mask must be a nonnegative int")
    return (left & right).bit_count()
