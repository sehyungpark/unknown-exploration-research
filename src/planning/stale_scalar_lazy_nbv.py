"""Stateful stale-scalar exact-lazy optimistic next-best-view baseline."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from src.candidates import reachable_known_free_candidates
from src.mapping import BeliefGrid
from src.sensing import optimistic_visible_unknown_cells
from src.utils import Coord

from .exhaustive_nbv import (
    SCORE_EPSILON,
    CandidateEvaluation,
    PlanStatus,
    candidate_rank_key,
    choose_best_candidate,
)
from .motion import dijkstra


@dataclass(frozen=True, slots=True)
class StaleLazyCandidateRecord:
    """Per-candidate diagnostics for one frozen planning snapshot.

    ``stale_upper_*`` records the cached bound at snapshot entry, before any
    current-cycle exact evaluation. A first-seen candidate therefore has
    ``None`` in those fields. Exact fields remain ``None`` when the candidate
    was certified without reevaluation.
    """

    candidate: Coord
    current_distance: float
    stale_upper_gain: int | None
    stale_upper_score: float | None
    exact_evaluated_this_cycle: bool
    exact_gain: int | None
    exact_score: float | None
    cache_refreshed: bool


@dataclass(frozen=True, slots=True)
class StaleLazyNBVResult:
    status: PlanStatus
    selected_candidate: Coord | None
    selected_gain: int
    selected_distance: float | None
    selected_score: float
    selected_path: tuple[Coord, ...]
    eligible_candidate_count: int
    exact_gain_evaluations: int
    bound_only_candidate_count: int
    certificate_reason: str
    candidate_records: tuple[StaleLazyCandidateRecord, ...]


def optimistic_rank_state(
    candidate: Coord,
    upper_gain: int,
    current_distance: float,
) -> CandidateEvaluation:
    """Represent a candidate's best admissible state in the frozen rank order."""

    if upper_gain < 0:
        raise ValueError("gain upper bound must be nonnegative")
    return CandidateEvaluation(
        candidate=candidate,
        visible_unknown=frozenset(),
        gain=upper_gain,
        distance=current_distance,
        score=upper_gain / (current_distance + SCORE_EPSILON),
    )


def tie_aware_rank_certificate(
    best_exact: CandidateEvaluation,
    remaining_optimistic: Iterable[CandidateEvaluation],
) -> bool:
    """Return whether an exact candidate strictly precedes every upper state."""

    best_key = candidate_rank_key(best_exact)
    return all(
        best_key < candidate_rank_key(optimistic)
        for optimistic in remaining_optimistic
    )


class StaleScalarLazyNBV:
    """Exact-lazy NBV using only the last exact scalar gain as a cache.

    A planner cache is valid only within one exploration episode under the
    frozen static-world and monotone-belief assumptions. Call :meth:`reset`
    before reusing an instance for a new environment, or create one planner
    instance per episode. A change to sensor geometry or range requires a new
    compatible planner/configuration rather than reuse of this stale cache.
    """

    def __init__(self, sensor_range: float = 8) -> None:
        if sensor_range < 0:
            raise ValueError("sensor range must be nonnegative")
        self._sensor_range = sensor_range
        self._cached_gains: dict[Coord, int] = {}

    @property
    def sensor_range(self) -> float:
        """Return the fixed range that is part of cached candidate identity."""

        return self._sensor_range

    @property
    def cached_gains(self) -> Mapping[Coord, int]:
        """Return a detached scalar-only snapshot of the persistent cache."""

        return dict(self._cached_gains)

    def reset(self) -> None:
        """Clear episode-specific stale gains while preserving configuration."""

        self._cached_gains.clear()

    def _validate_cache(self) -> None:
        for candidate, gain in self._cached_gains.items():
            if type(gain) is not int or gain < 0:
                raise RuntimeError(
                    f"invalid cached gain for {candidate}: expected nonnegative int, "
                    f"got {gain!r}"
                )

    def plan(self, belief: BeliefGrid, robot: Coord) -> StaleLazyNBVResult:
        """Select exactly under valid monotone snapshots without consulting A."""

        self._validate_cache()
        distance_result = dijkstra(belief, robot)
        candidates = reachable_known_free_candidates(
            belief, robot, distance_result.distances
        )
        distances = {
            candidate: distance_result.distances[candidate]
            for candidate in candidates
        }
        stale_at_entry = {
            candidate: self._cached_gains.get(candidate) for candidate in candidates
        }
        exact: dict[Coord, CandidateEvaluation] = {}
        refreshed: set[Coord] = set()

        def exact_evaluate(candidate: Coord) -> None:
            visible_unknown = optimistic_visible_unknown_cells(
                belief, candidate, self.sensor_range
            )
            gain = len(visible_unknown)
            old_gain = self._cached_gains.get(candidate)
            if old_gain is not None and gain > old_gain:
                raise RuntimeError(
                    f"stale gain bound violated for {candidate}: "
                    f"current {gain} > cached {old_gain}"
                )
            distance = distances[candidate]
            evaluation = CandidateEvaluation(
                candidate=candidate,
                visible_unknown=visible_unknown,
                gain=gain,
                distance=distance,
                score=gain / (distance + SCORE_EPSILON),
            )
            exact[candidate] = evaluation
            self._cached_gains[candidate] = gain
            refreshed.add(candidate)

        for candidate in candidates:
            if stale_at_entry[candidate] is None:
                exact_evaluate(candidate)

        remaining = set(candidates) - set(exact)

        def optimistic(candidate: Coord) -> CandidateEvaluation:
            return optimistic_rank_state(
                candidate,
                self._cached_gains[candidate],
                distances[candidate],
            )

        status: PlanStatus
        selected: CandidateEvaluation | None = None
        certificate_reason: str
        while True:
            if not candidates:
                status = PlanStatus.EXPLORATION_COMPLETE
                certificate_reason = "no_eligible_candidates"
                break

            if all(
                (
                    exact[candidate].gain
                    if candidate in exact
                    else self._cached_gains[candidate]
                )
                == 0
                for candidate in candidates
            ):
                status = PlanStatus.EXPLORATION_COMPLETE
                certificate_reason = "all_gain_upper_bounds_zero"
                break

            if not exact:
                next_candidate = min(
                    remaining,
                    key=lambda candidate: candidate_rank_key(optimistic(candidate)),
                )
                remaining.remove(next_candidate)
                exact_evaluate(next_candidate)
                continue

            best_exact = choose_best_candidate(tuple(exact.values()))
            remaining_optimistic = tuple(
                optimistic(candidate) for candidate in sorted(remaining)
            )
            if tie_aware_rank_certificate(best_exact, remaining_optimistic):
                status = PlanStatus.SELECTED
                selected = best_exact
                certificate_reason = "tie_aware_rank_dominance"
                break

            next_candidate = min(
                remaining,
                key=lambda candidate: candidate_rank_key(optimistic(candidate)),
            )
            remaining.remove(next_candidate)
            exact_evaluate(next_candidate)

        self._validate_cache()
        records = tuple(
            StaleLazyCandidateRecord(
                candidate=candidate,
                current_distance=distances[candidate],
                stale_upper_gain=stale_at_entry[candidate],
                stale_upper_score=(
                    None
                    if stale_at_entry[candidate] is None
                    else stale_at_entry[candidate]
                    / (distances[candidate] + SCORE_EPSILON)
                ),
                exact_evaluated_this_cycle=candidate in exact,
                exact_gain=(
                    exact[candidate].gain if candidate in exact else None
                ),
                exact_score=(
                    exact[candidate].score if candidate in exact else None
                ),
                cache_refreshed=candidate in refreshed,
            )
            for candidate in candidates
        )
        exact_count = len(exact)

        if selected is None:
            return StaleLazyNBVResult(
                status=status,
                selected_candidate=None,
                selected_gain=0,
                selected_distance=None,
                selected_score=0.0,
                selected_path=(),
                eligible_candidate_count=len(candidates),
                exact_gain_evaluations=exact_count,
                bound_only_candidate_count=len(candidates) - exact_count,
                certificate_reason=certificate_reason,
                candidate_records=records,
            )

        if selected.candidate not in exact:
            raise RuntimeError("selected candidate must be current-exact")
        return StaleLazyNBVResult(
            status=status,
            selected_candidate=selected.candidate,
            selected_gain=selected.gain,
            selected_distance=selected.distance,
            selected_score=selected.score,
            selected_path=distance_result.path_to(selected.candidate),
            eligible_candidate_count=len(candidates),
            exact_gain_evaluations=exact_count,
            bound_only_candidate_count=len(candidates) - exact_count,
            certificate_reason=certificate_reason,
            candidate_records=records,
        )
