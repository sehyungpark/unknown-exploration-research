"""Episode-scoped state foundation for the future change-aware NBV method."""

from collections.abc import Mapping
from types import MappingProxyType

from src.utils import Coord


def _is_grid_coord(value: object) -> bool:
    return (
        type(value) is tuple
        and len(value) == 2
        and all(type(component) is int and component >= 0 for component in value)
    )


class ChangeAwareGainCache:
    """Store Algorithm C cache/index state without selection or update logic.

    State is valid only within one exploration episode under the frozen
    static-world, monotone-belief, and immutable-viewpoint assumptions. Reuse
    for a new environment requires :meth:`reset`, or a new state instance.
    Sensor geometry and candidate-identity configuration are external to this
    Stage 1 state object and must remain compatible for the whole episode.

    Stage 1 deliberately exposes no cache installation, removal, exact
    refresh, observation-delta, decrement, or selection operation. Later
    stages must add those operations without exposing raw mutable state.
    """

    def __init__(self) -> None:
        self._cached_visible_unknown: dict[Coord, frozenset[Coord]] = {}
        self._bound_counts: dict[Coord, int] = {}
        self._inverse_incidence: dict[Coord, set[Coord]] = {}

    @property
    def cached_visible_unknown(self) -> Mapping[Coord, frozenset[Coord]]:
        """Return a read-only detached candidate-to-exact-cache snapshot."""

        return MappingProxyType(dict(self._cached_visible_unknown))

    @property
    def bound_counts(self) -> Mapping[Coord, int]:
        """Return a read-only detached candidate-to-bound snapshot."""

        return MappingProxyType(dict(self._bound_counts))

    @property
    def inverse_incidence(self) -> Mapping[Coord, frozenset[Coord]]:
        """Return a deeply safe cell-to-candidate membership snapshot."""

        detached = {
            cell: frozenset(candidates)
            for cell, candidates in self._inverse_incidence.items()
        }
        return MappingProxyType(detached)

    def reset(self) -> None:
        """Clear all episode-specific cached sets, bounds, and incidence."""

        self._cached_visible_unknown.clear()
        self._bound_counts.clear()
        self._inverse_incidence.clear()

    def validate(self, *, require_fresh_bounds: bool = False) -> None:
        """Raise ``RuntimeError`` when stored cache/index state is malformed.

        A maintained bound may be smaller than its exact cached-set size after
        future revelation processing, but it may never be negative or larger.
        ``require_fresh_bounds=True`` additionally checks the state immediately
        after a future exact installation, where both values must be equal.
        """

        cached_candidates = set(self._cached_visible_unknown)
        bound_candidates = set(self._bound_counts)
        if cached_candidates != bound_candidates:
            raise RuntimeError(
                "cached-set and bound-count candidate keys must match"
            )

        expected_inverse: dict[Coord, set[Coord]] = {}
        for candidate, visible_unknown in self._cached_visible_unknown.items():
            if not _is_grid_coord(candidate):
                raise RuntimeError(f"invalid cached candidate coordinate: {candidate!r}")
            if type(visible_unknown) is not frozenset:
                raise RuntimeError(
                    f"cached visible-UNKNOWN set for {candidate} must be frozenset"
                )
            for cell in visible_unknown:
                if not _is_grid_coord(cell):
                    raise RuntimeError(
                        f"invalid cached visible-UNKNOWN coordinate: {cell!r}"
                    )
                expected_inverse.setdefault(cell, set()).add(candidate)

        for candidate, bound in self._bound_counts.items():
            if not _is_grid_coord(candidate):
                raise RuntimeError(f"invalid bound candidate coordinate: {candidate!r}")
            if type(bound) is not int or bound < 0:
                raise RuntimeError(
                    f"invalid bound for {candidate}: expected nonnegative int, "
                    f"got {bound!r}"
                )
            cached_size = len(self._cached_visible_unknown[candidate])
            if bound > cached_size:
                raise RuntimeError(
                    f"bound for {candidate} exceeds cached-set size: "
                    f"{bound} > {cached_size}"
                )
            if require_fresh_bounds and bound != cached_size:
                raise RuntimeError(
                    f"fresh bound for {candidate} must equal cached-set size: "
                    f"{bound} != {cached_size}"
                )

        actual_inverse: dict[Coord, set[Coord]] = {}
        for cell, candidates in self._inverse_incidence.items():
            if not _is_grid_coord(cell):
                raise RuntimeError(f"invalid inverse cell coordinate: {cell!r}")
            if type(candidates) is not set:
                if isinstance(candidates, (list, tuple)):
                    try:
                        if len(candidates) != len(set(candidates)):
                            raise RuntimeError(
                                f"duplicate inverse membership for cell {cell}"
                            )
                    except TypeError:
                        pass
                raise RuntimeError(
                    f"inverse memberships for {cell} must be a set"
                )
            if not candidates:
                raise RuntimeError(f"inverse membership for {cell} must not be empty")
            actual_inverse[cell] = set()
            for candidate in candidates:
                if not _is_grid_coord(candidate):
                    raise RuntimeError(
                        f"invalid inverse candidate coordinate: {candidate!r}"
                    )
                if candidate not in cached_candidates:
                    raise RuntimeError(
                        f"inverse membership references uninitialized candidate: "
                        f"{candidate}"
                    )
                actual_inverse[cell].add(candidate)

        if actual_inverse != expected_inverse:
            raise RuntimeError(
                "inverse incidence must exactly match cached visible-UNKNOWN membership"
            )
