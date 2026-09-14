"""Candidate generation from exact current reachability."""

from collections.abc import Mapping

from src.mapping import BeliefGrid
from src.utils import Coord


def reachable_known_free_candidates(
    belief: BeliefGrid,
    robot: Coord,
    distances: Mapping[Coord, float],
) -> tuple[Coord, ...]:
    """Return all and only reachable known-FREE cells except the robot cell."""

    if not belief.known_free(robot):
        raise ValueError("robot cell must be known FREE")
    return tuple(
        coord
        for coord in sorted(distances)
        if coord != robot and belief.known_free(coord)
    )
