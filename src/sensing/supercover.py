"""Corner-inclusive supercover lines between integer grid-cell centers.

The result includes both endpoints. When the center-to-center segment passes
exactly through a grid corner, both side-adjacent cells and then the diagonal
cell are included. Side cells are emitted in lexicographic order. This gives a
deterministic traversal and a direction-symmetric set of covered cells.
"""

from fractions import Fraction

from src.utils import Coord


def _sign(value: int) -> int:
    return (value > 0) - (value < 0)


def supercover_line(start: Coord, end: Coord) -> tuple[Coord, ...]:
    """Return every cell touched by the closed center-to-center segment."""

    start_row, start_col = start
    end_row, end_col = end
    if start == end:
        return (start,)

    row_delta = end_row - start_row
    col_delta = end_col - start_col
    row_step = _sign(row_delta)
    col_step = _sign(col_delta)
    row_crossing = (
        Fraction(1, 2 * abs(row_delta)) if row_delta else None
    )
    col_crossing = (
        Fraction(1, 2 * abs(col_delta)) if col_delta else None
    )
    row_increment = Fraction(1, abs(row_delta)) if row_delta else None
    col_increment = Fraction(1, abs(col_delta)) if col_delta else None

    row, col = start
    covered: list[Coord] = [start]

    def append_once(coord: Coord) -> None:
        if coord not in covered:
            covered.append(coord)

    while (row, col) != end:
        if row_crossing is None:
            col += col_step
            assert col_increment is not None
            col_crossing += col_increment  # type: ignore[operator]
            append_once((row, col))
        elif col_crossing is None:
            row += row_step
            assert row_increment is not None
            row_crossing += row_increment
            append_once((row, col))
        elif row_crossing < col_crossing:
            row += row_step
            row_crossing += row_increment  # type: ignore[operator]
            append_once((row, col))
        elif col_crossing < row_crossing:
            col += col_step
            col_crossing += col_increment  # type: ignore[operator]
            append_once((row, col))
        else:
            side_cells = sorted(((row + row_step, col), (row, col + col_step)))
            for cell in side_cells:
                append_once(cell)
            row += row_step
            col += col_step
            row_crossing += row_increment  # type: ignore[operator]
            col_crossing += col_increment  # type: ignore[operator]
            append_once((row, col))

    return tuple(covered)
