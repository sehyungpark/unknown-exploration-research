"""Certified change-aware exact-lazy optimistic next-best-view planner."""

from dataclasses import dataclass

from src.candidates import reachable_known_free_candidates
from src.mapping import BeliefGrid
from src.utils import BeliefState, Coord

from .change_aware_cache import ChangeAwareGainCache
from .change_aware_integration import (
    BeliefSnapshot,
    exact_refresh_candidate,
    synchronize_revelations,
)
from .exhaustive_nbv import (
    SCORE_EPSILON,
    CandidateEvaluation,
    PlanStatus,
    candidate_rank_key,
    choose_best_candidate,
)
from .motion import dijkstra
from .stale_scalar_lazy_nbv import (
    optimistic_rank_state,
    tie_aware_rank_certificate,
)


@dataclass(frozen=True, slots=True)
class ChangeAwareLazyCandidateRecord:
    """One eligible candidate's diagnostics for a frozen snapshot.

    Entry bounds are captured after belief synchronization and before any
    current-snapshot exact refresh. They remain ``None`` for first-seen
    candidates, even though those candidates are then initialized exactly.
    """

    candidate: Coord
    current_distance: float
    change_aware_upper_gain_at_entry: int | None
    change_aware_upper_score_at_entry: float | None
    exact_evaluated_this_cycle: bool
    current_exact_gain: int | None
    current_exact_score: float | None
    cache_refreshed: bool


@dataclass(frozen=True, slots=True)
class ChangeAwareLazyNBVResult:
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
    synchronized_newly_known_cells: frozenset[Coord]
    candidate_records: tuple[ChangeAwareLazyCandidateRecord, ...]


def _all_unknown_baseline(snapshot: BeliefSnapshot) -> BeliefSnapshot:
    """Return the pre-observation baseline for a planner's first snapshot."""

    return tuple(
        tuple(BeliefState.UNKNOWN for _ in row)
        for row in snapshot
    )


class ChangeAwareLazyNBV:
    """Episode-scoped exact-lazy NBV using maintained cached-set bounds.

    ``sensor_range`` is fixed for the instance because it is part of cached
    viewpoint identity. Call :meth:`reset` before reusing the planner for a
    different environment. No automatic episode detection or reset occurs.
    """

    def __init__(self, sensor_range: float = 8) -> None:
        if sensor_range < 0:
            raise ValueError("sensor range must be nonnegative")
        self._sensor_range = sensor_range
        self._cache = ChangeAwareGainCache()
        self._last_synchronized_snapshot: BeliefSnapshot | None = None

    @property
    def sensor_range(self) -> float:
        """Return the fixed range that is part of cached candidate identity."""

        return self._sensor_range

    @property
    def cache(self) -> ChangeAwareGainCache:
        """Return the planner-owned cache for read-oriented diagnostics."""

        return self._cache

    @property
    def last_synchronized_snapshot(self) -> BeliefSnapshot | None:
        """Return the immutable last synchronized belief snapshot, if any."""

        return self._last_synchronized_snapshot

    def reset(self) -> None:
        """Clear every episode-specific cache and synchronization state."""

        self._cache.reset()
        self._last_synchronized_snapshot = None

    def _synchronize_belief(self, belief: BeliefGrid) -> frozenset[Coord]:
        current_snapshot = belief.snapshot()
        previous_snapshot = self._last_synchronized_snapshot
        if previous_snapshot is None:
            previous_snapshot = _all_unknown_baseline(current_snapshot)
        delta = synchronize_revelations(
            self._cache,
            previous_snapshot,
            current_snapshot,
        )
        self._last_synchronized_snapshot = current_snapshot
        return delta

    def plan(self, belief: BeliefGrid, robot: Coord) -> ChangeAwareLazyNBVResult:
        """Select with a tie-aware certificate on one synchronized snapshot."""

        synchronized_delta = self._synchronize_belief(belief)
        distance_result = dijkstra(belief, robot)
        candidates = reachable_known_free_candidates(
            belief,
            robot,
            distance_result.distances,
        )
        distances = {
            candidate: distance_result.distances[candidate]
            for candidate in candidates
        }

        synchronized_bounds = self._cache.bound_counts
        bound_at_entry = {
            candidate: synchronized_bounds.get(candidate)
            for candidate in candidates
        }
        exact: dict[Coord, CandidateEvaluation] = {}
        refreshed: set[Coord] = set()

        def exact_evaluate(candidate: Coord) -> None:
            visible_unknown = exact_refresh_candidate(
                self._cache,
                belief,
                candidate,
                self.sensor_range,
            )
            gain = len(visible_unknown)
            if self._cache.bound_counts[candidate] != gain:
                raise RuntimeError(
                    f"exact refresh did not produce a tight bound for {candidate}"
                )
            distance = distances[candidate]
            exact[candidate] = CandidateEvaluation(
                candidate=candidate,
                visible_unknown=visible_unknown,
                gain=gain,
                distance=distance,
                score=gain / (distance + SCORE_EPSILON),
            )
            refreshed.add(candidate)

        for candidate in candidates:
            if bound_at_entry[candidate] is None:
                exact_evaluate(candidate)

        remaining = set(candidates) - set(exact)

        def optimistic(candidate: Coord) -> CandidateEvaluation:
            return optimistic_rank_state(
                candidate,
                self._cache.bound_counts[candidate],
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

            if all(self._cache.bound_counts[candidate] == 0 for candidate in candidates):
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

        self._cache.validate()
        records = tuple(
            ChangeAwareLazyCandidateRecord(
                candidate=candidate,
                current_distance=distances[candidate],
                change_aware_upper_gain_at_entry=bound_at_entry[candidate],
                change_aware_upper_score_at_entry=(
                    None
                    if bound_at_entry[candidate] is None
                    else bound_at_entry[candidate]
                    / (distances[candidate] + SCORE_EPSILON)
                ),
                exact_evaluated_this_cycle=candidate in exact,
                current_exact_gain=(
                    exact[candidate].gain if candidate in exact else None
                ),
                current_exact_score=(
                    exact[candidate].score if candidate in exact else None
                ),
                cache_refreshed=candidate in refreshed,
            )
            for candidate in candidates
        )
        exact_count = len(exact)

        if selected is None:
            return ChangeAwareLazyNBVResult(
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
                synchronized_newly_known_cells=synchronized_delta,
                candidate_records=records,
            )

        if selected.candidate not in exact:
            raise RuntimeError("selected candidate must be current-exact")
        return ChangeAwareLazyNBVResult(
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
            synchronized_newly_known_cells=synchronized_delta,
            candidate_records=records,
        )
