from collections.abc import Iterable

from src.mapping import BeliefGrid
from src.utils import BeliefState, TruthState


def belief_from_ascii(rows: Iterable[str]) -> BeliefGrid:
    materialized = tuple(rows)
    if not materialized:
        raise ValueError("rows must not be empty")
    belief = BeliefGrid.unknown(len(materialized), len(materialized[0]))
    observations = {}
    for row_index, row in enumerate(materialized):
        if len(row) != belief.width:
            raise ValueError("rows must be rectangular")
        for col_index, symbol in enumerate(row):
            if symbol == ".":
                observations[(row_index, col_index)] = TruthState.FREE
            elif symbol == "#":
                observations[(row_index, col_index)] = TruthState.OCCUPIED
            elif symbol != "?":
                raise ValueError(f"unsupported belief symbol: {symbol!r}")
    belief.apply_observations(observations)
    return belief


def opaque_visible_unknown_cells(
    belief: BeliefGrid,
    origin: tuple[int, int],
    supercover,
) -> frozenset[tuple[int, int]]:
    """Test-only alternative rule demonstrating the opaque-UNKNOWN counterexample."""

    visible = set()
    for target in belief.iter_coords():
        if belief.state(target) is not BeliefState.UNKNOWN:
            continue
        line = supercover(origin, target)
        if any(
            belief.state(cell) in (BeliefState.UNKNOWN, BeliefState.OCCUPIED)
            for cell in line[1:-1]
        ):
            continue
        visible.add(target)
    return frozenset(visible)
