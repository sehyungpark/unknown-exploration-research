"""Belief/cache integration utilities for Algorithm C.

These helpers connect immutable atomic belief snapshots and the existing
optimistic visibility evaluator to :class:`ChangeAwareGainCache`. They do not
perform candidate generation, path planning, ranking, or selection.
"""

from typing import TypeAlias

from src.mapping import BeliefGrid
from src.sensing import optimistic_visible_unknown_cells
from src.utils import BeliefState, Coord

from .change_aware_cache import ChangeAwareGainCache

BeliefSnapshot: TypeAlias = tuple[tuple[BeliefState, ...], ...]


def _snapshot_shape(snapshot: BeliefSnapshot, *, name: str) -> tuple[int, int]:
    """Validate the immutable ``BeliefGrid.snapshot()`` representation."""

    if type(snapshot) is not tuple:
        raise TypeError(f"{name} must be an immutable tuple-of-tuples snapshot")
    if not snapshot:
        raise ValueError(f"{name} must contain at least one row")
    if any(type(row) is not tuple for row in snapshot):
        raise TypeError(f"{name} rows must be tuples")
    width = len(snapshot[0])
    if width == 0:
        raise ValueError(f"{name} rows must not be empty")
    if any(len(row) != width for row in snapshot):
        raise ValueError(f"{name} must be rectangular")
    if any(
        not isinstance(cell, BeliefState)
        for row in snapshot
        for cell in row
    ):
        raise TypeError(f"{name} cells must be BeliefState values")
    return len(snapshot), width


def newly_known_cells(
    previous_belief: BeliefSnapshot,
    current_belief: BeliefSnapshot,
) -> frozenset[Coord]:
    """Return legal UNKNOWN-to-known transitions between two snapshots.

    Both arguments must be temporal values in the immutable format
    returned by :meth:`BeliefGrid.snapshot`; passing mutable grid storage is
    rejected. Shapes must match. The only accepted transitions are unchanged
    states and UNKNOWN to FREE/OCCUPIED. Known-state reversion or switching
    raises ``ValueError`` instead of producing a partial delta.
    """

    previous_shape = _snapshot_shape(previous_belief, name="previous_belief")
    current_shape = _snapshot_shape(current_belief, name="current_belief")
    if previous_shape != current_shape:
        raise ValueError(
            "belief snapshot shapes must match: "
            f"{previous_shape} != {current_shape}"
        )

    delta: set[Coord] = set()
    for row in range(previous_shape[0]):
        for col in range(previous_shape[1]):
            previous = previous_belief[row][col]
            current = current_belief[row][col]
            if previous is current:
                continue
            if (
                previous is BeliefState.UNKNOWN
                and current in (BeliefState.FREE, BeliefState.OCCUPIED)
            ):
                delta.add((row, col))
                continue
            raise ValueError(
                "illegal non-monotone belief transition at "
                f"{(row, col)}: {previous.value} -> {current.value}"
            )
    return frozenset(delta)


def synchronize_revelations(
    cache: ChangeAwareGainCache,
    previous_belief: BeliefSnapshot,
    current_belief: BeliefSnapshot,
) -> frozenset[Coord]:
    """Extract and apply one atomic snapshot's UNKNOWN-to-known delta."""

    delta = newly_known_cells(previous_belief, current_belief)
    cache.apply_newly_known(delta)
    return delta


def exact_refresh_candidate(
    cache: ChangeAwareGainCache,
    belief: BeliefGrid,
    candidate: Coord,
    sensor_range: float = 8,
) -> frozenset[Coord]:
    """Compute current exact optimistic visibility and install it in cache."""

    visible_unknown = exact_visible_unknown_candidate(
        belief,
        candidate,
        sensor_range,
    )
    cache.install_exact(candidate, visible_unknown)
    return visible_unknown


def exact_visible_unknown_candidate(
    belief: BeliefGrid,
    candidate: Coord,
    sensor_range: float = 8,
) -> frozenset[Coord]:
    """Compute one candidate's exact set without mutating Algorithm C state."""

    return optimistic_visible_unknown_cells(
        belief,
        candidate,
        sensor_range,
    )
