"""Episode-scoped cache/index state for the future change-aware NBV method."""

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
    """Store Algorithm C exact cached sets, bounds, and inverse incidence.

    State is valid only within one exploration episode under the frozen
    static-world, monotone-belief, and immutable-viewpoint assumptions. Reuse
    for a new environment requires :meth:`reset`, or a new state instance.
    Sensor geometry and candidate-identity configuration are external to this
    cache object and must remain compatible for the whole episode.

    Stage 2 supports only atomic first installation and exact replacement of
    an already-computed visible-UNKNOWN set. It deliberately performs no
    raycasting, observation-delta processing, bound decrement, or selection.
    The inverse index always represents the complete installed cached set;
    later bound decrements must not remove those historical memberships.
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

    def install_exact(
        self,
        candidate: Coord,
        visible_unknown: frozenset[Coord],
    ) -> None:
        """Atomically install or replace one candidate's exact cached set.

        ``visible_unknown`` must already have been computed exactly by the
        caller. Replacement removes memberships using the complete old cached
        set, installs the new memberships, and resets the maintained bound to
        the new exact-set size. Input or state validation failures leave the
        prior state unchanged.
        """

        if not _is_grid_coord(candidate):
            raise ValueError(f"invalid candidate coordinate: {candidate!r}")
        if type(visible_unknown) is not frozenset:
            raise TypeError("visible_unknown must be a frozenset")
        for cell in visible_unknown:
            if not _is_grid_coord(cell):
                raise ValueError(
                    f"invalid visible-UNKNOWN coordinate: {cell!r}"
                )

        # Work transactionally so callers never observe a half-replaced
        # candidate, even if the pre-existing state is malformed.
        self.validate()
        next_cached = dict(self._cached_visible_unknown)
        next_bounds = dict(self._bound_counts)
        next_inverse = {
            cell: set(candidates)
            for cell, candidates in self._inverse_incidence.items()
        }

        old_visible_unknown = next_cached.get(candidate, frozenset())
        for cell in old_visible_unknown:
            candidates = next_inverse[cell]
            candidates.remove(candidate)
            if not candidates:
                del next_inverse[cell]

        next_cached[candidate] = visible_unknown
        next_bounds[candidate] = len(visible_unknown)
        for cell in visible_unknown:
            next_inverse.setdefault(cell, set()).add(candidate)

        self._validate_state(next_cached, next_bounds, next_inverse)
        if next_bounds[candidate] != len(next_cached[candidate]):
            raise RuntimeError("exact installation must create a fresh bound")

        self._cached_visible_unknown = next_cached
        self._bound_counts = next_bounds
        self._inverse_incidence = next_inverse

    def validate(self, *, require_fresh_bounds: bool = False) -> None:
        """Raise ``RuntimeError`` when stored cache/index state is malformed.

        A maintained bound may be smaller than its exact cached-set size after
        future revelation processing, but it may never be negative or larger.
        ``require_fresh_bounds=True`` additionally checks the state immediately
        after a future exact installation, where both values must be equal.
        """

        self._validate_state(
            self._cached_visible_unknown,
            self._bound_counts,
            self._inverse_incidence,
            require_fresh_bounds=require_fresh_bounds,
        )

    @staticmethod
    def _validate_state(
        cached_visible_unknown: dict[Coord, frozenset[Coord]],
        bound_counts: dict[Coord, int],
        inverse_incidence: dict[Coord, set[Coord]],
        *,
        require_fresh_bounds: bool = False,
    ) -> None:
        cached_candidates = set(cached_visible_unknown)
        bound_candidates = set(bound_counts)
        if cached_candidates != bound_candidates:
            raise RuntimeError(
                "cached-set and bound-count candidate keys must match"
            )

        expected_inverse: dict[Coord, set[Coord]] = {}
        for candidate, visible_unknown in cached_visible_unknown.items():
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

        for candidate, bound in bound_counts.items():
            if not _is_grid_coord(candidate):
                raise RuntimeError(f"invalid bound candidate coordinate: {candidate!r}")
            if type(bound) is not int or bound < 0:
                raise RuntimeError(
                    f"invalid bound for {candidate}: expected nonnegative int, "
                    f"got {bound!r}"
                )
            cached_size = len(cached_visible_unknown[candidate])
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
        for cell, candidates in inverse_incidence.items():
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
