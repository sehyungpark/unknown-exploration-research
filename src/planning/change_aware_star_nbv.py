"""Algorithm C*: lazy bitset change-aware exact-lazy optimistic NBV.

C* preserves Algorithm A's candidate domain, score, total order, motion semantics,
and exact visibility definition. It changes only how admissible gain upper bounds
are represented and refreshed:

* no eager per-revelation candidate decrements;
* persistent exact visible-UNKNOWN sets are Python-int bitsets;
* the global UNKNOWN bitmask is updated from explicit revelation deltas;
* first-seen candidates receive an exact sensor-footprint range upper bound;
* cached change-aware bounds are refreshed only when a candidate becomes
  competitive;
* the selected candidate is always current-exact.

This implementation intentionally does NOT include an occlusion exactness
certificate, shadow repair, or any shortcut that treats a cached bound as exact.
"""

from __future__ import annotations

from dataclasses import dataclass
import heapq

from src.candidates import reachable_known_free_candidates
from src.mapping import BeliefGrid
from src.sensing import optimistic_visible_unknown_cells
from src.utils import BeliefState, Coord

from .bitmask import (
    coord_bit,
    coords_to_mask,
    intersection_count,
    sensor_range_mask,
    unknown_mask_from_belief,
)
from .exhaustive_nbv import (
    SCORE_EPSILON,
    CandidateEvaluation,
    PlanStatus,
    candidate_rank_key,
    choose_best_candidate,
)
from .motion import dijkstra
from .stale_scalar_lazy_nbv import optimistic_rank_state, tie_aware_rank_certificate


@dataclass(slots=True)
class CStarCacheEntry:
    """Persistent per-candidate state."""

    visible_mask: int
    stale_upper_gain: int
    last_exact_revision: int
    last_bound_refresh_revision: int


@dataclass(frozen=True, slots=True)
class CStarCandidateRecord:
    candidate: Coord
    current_distance: float
    was_cached_at_entry: bool
    range_upper_gain: int
    stale_upper_gain_at_entry: int | None
    change_upper_gain_after_refresh: int | None
    lazy_bound_refreshed: bool
    exact_evaluated_this_cycle: bool
    current_exact_gain: int | None
    current_exact_score: float | None


@dataclass(frozen=True, slots=True)
class CStarCycleCounters:
    exact_visibility_evaluation_count: int
    first_seen_candidate_count: int
    first_seen_pruned_without_exact_count: int
    range_bound_evaluation_count: int
    range_bound_zero_prune_count: int
    lazy_bound_refresh_count: int
    stale_bound_pop_count: int
    stale_bound_refresh_reinsert_count: int
    current_bound_exact_escalation_count: int
    exact_cache_installation_count: int
    exact_cache_replacement_count: int
    unknown_mask_delta_cell_update_count: int
    priority_pop_count: int
    certificate_success_count: int


@dataclass(frozen=True, slots=True)
class CStarNBVResult:
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
    candidate_records: tuple[CStarCandidateRecord, ...]
    counters: CStarCycleCounters


@dataclass(frozen=True, slots=True)
class CStarAuditReport:
    cached_candidate_count: int
    exact_visibility_checks: int
    unknown_mask_matches_belief: bool


class ChangeAwareStarNBV:
    """Episode-scoped Algorithm C* planner.

    The first call initializes the UNKNOWN bitmask from the supplied belief.
    Every later call must explicitly supply ``newly_known`` (an empty
    ``frozenset`` is valid). This avoids a production-path full snapshot diff.

    Missing revelations make bounds looser rather than unsound, but requiring
    an explicit delta prevents accidental silent lifecycle misuse. Reporting a
    still-UNKNOWN cell is rejected because clearing such a bit could create an
    unsafe underestimate.
    """

    def __init__(self, sensor_range: float = 8) -> None:
        if sensor_range < 0:
            raise ValueError("sensor range must be nonnegative")
        self._sensor_range = sensor_range
        self._shape: tuple[int, int] | None = None
        self._unknown_mask: int | None = None
        self._map_revision = 0
        self._cache: dict[Coord, CStarCacheEntry] = {}
        self._range_masks: dict[Coord, int] = {}

    @property
    def sensor_range(self) -> float:
        return self._sensor_range

    @property
    def shape(self) -> tuple[int, int] | None:
        return self._shape

    @property
    def map_revision(self) -> int:
        return self._map_revision

    @property
    def cached_candidate_count(self) -> int:
        return len(self._cache)

    @property
    def range_mask_cache_count(self) -> int:
        return len(self._range_masks)

    def reset(self) -> None:
        self._shape = None
        self._unknown_mask = None
        self._map_revision = 0
        self._cache.clear()
        self._range_masks.clear()

    def storage_counters(self) -> dict[str, int]:
        """Return deterministic structural storage counters for research logging.

        This diagnostic traversal is intentionally outside the production timing
        boundary. It does not mutate planner state.
        """

        return {
            "cached_candidate_count": len(self._cache),
            "cached_visible_membership_count": sum(
                entry.visible_mask.bit_count() for entry in self._cache.values()
            ),
            "range_mask_count": len(self._range_masks),
            "range_mask_membership_count": sum(
                mask.bit_count() for mask in self._range_masks.values()
            ),
        }

    def cached_entry(self, candidate: Coord) -> CStarCacheEntry | None:
        """Return a detached diagnostic copy without copying the whole cache."""

        entry = self._cache.get(candidate)
        if entry is None:
            return None
        return CStarCacheEntry(
            visible_mask=entry.visible_mask,
            stale_upper_gain=entry.stale_upper_gain,
            last_exact_revision=entry.last_exact_revision,
            last_bound_refresh_revision=entry.last_bound_refresh_revision,
        )

    def _require_shape(self, belief: BeliefGrid) -> tuple[int, int]:
        if self._shape is None:
            raise RuntimeError("planner has not been initialized")
        if belief.shape != self._shape:
            raise ValueError(
                f"belief shape changed within episode: {belief.shape} != {self._shape}"
            )
        return self._shape

    def _synchronize_unknown_mask(
        self,
        belief: BeliefGrid,
        newly_known: frozenset[Coord] | None,
    ) -> int:
        """Initialize once, then update only from explicit UNKNOWN->known deltas."""

        if self._shape is None:
            self._shape = belief.shape
            self._unknown_mask = unknown_mask_from_belief(belief)
            if newly_known is not None:
                if type(newly_known) is not frozenset:
                    raise TypeError("newly_known must be a frozenset or None")
                for cell in newly_known:
                    if belief.state(cell) is BeliefState.UNKNOWN:
                        raise ValueError(
                            f"reported newly-known cell is still UNKNOWN: {cell}"
                        )
            return 0

        self._require_shape(belief)
        if newly_known is None:
            raise ValueError(
                "subsequent C* planning calls require explicit newly_known delta; "
                "pass frozenset() when no cells changed"
            )
        if type(newly_known) is not frozenset:
            raise TypeError("newly_known must be a frozenset")
        assert self._unknown_mask is not None
        changed_bits = 0
        for cell in newly_known:
            if belief.state(cell) is BeliefState.UNKNOWN:
                raise ValueError(
                    f"reported newly-known cell is still UNKNOWN: {cell}"
                )
            bit = coord_bit(cell, self._shape)
            if self._unknown_mask & bit:
                self._unknown_mask &= ~bit
                changed_bits += 1
        if changed_bits:
            self._map_revision += 1
        return changed_bits

    def _range_mask(self, candidate: Coord) -> int:
        if self._shape is None:
            raise RuntimeError("planner has not been initialized")
        mask = self._range_masks.get(candidate)
        if mask is None:
            mask = sensor_range_mask(candidate, self._shape, self.sensor_range)
            self._range_masks[candidate] = mask
        return mask

    def _range_upper_gain(self, candidate: Coord) -> int:
        if self._unknown_mask is None:
            raise RuntimeError("planner has not been initialized")
        return intersection_count(self._range_mask(candidate), self._unknown_mask)

    def _fresh_change_bound(self, candidate: Coord) -> int:
        if self._unknown_mask is None:
            raise RuntimeError("planner has not been initialized")
        entry = self._cache[candidate]
        return intersection_count(entry.visible_mask, self._unknown_mask)

    def audit(self, belief: BeliefGrid) -> CStarAuditReport:
        """Expensive full audit for tests/debugging; never required by ``plan``."""

        shape = self._require_shape(belief)
        if self._unknown_mask is None:
            raise RuntimeError("planner has not been initialized")
        independent_unknown = unknown_mask_from_belief(belief)
        if independent_unknown != self._unknown_mask:
            raise RuntimeError("C* UNKNOWN mask does not match belief")
        exact_checks = 0
        for candidate, entry in self._cache.items():
            range_mask = sensor_range_mask(candidate, shape, self.sensor_range)
            if entry.visible_mask & ~range_mask:
                raise RuntimeError(
                    f"cached visibility escapes sensor range for {candidate}"
                )
            fresh = intersection_count(entry.visible_mask, independent_unknown)
            if fresh > entry.stale_upper_gain:
                raise RuntimeError(
                    f"stale bound underestimates fresh change bound for {candidate}"
                )
            exact_visible = optimistic_visible_unknown_cells(
                belief, candidate, self.sensor_range
            )
            exact_checks += 1
            exact_gain = len(exact_visible)
            range_gain = intersection_count(range_mask, independent_unknown)
            if exact_gain > fresh:
                raise RuntimeError(
                    f"change-aware bound violated for {candidate}: "
                    f"{exact_gain} > {fresh}"
                )
            if exact_gain > range_gain:
                raise RuntimeError(
                    f"range bound violated for {candidate}: "
                    f"{exact_gain} > {range_gain}"
                )
        return CStarAuditReport(
            cached_candidate_count=len(self._cache),
            exact_visibility_checks=exact_checks,
            unknown_mask_matches_belief=True,
        )

    def plan(
        self,
        belief: BeliefGrid,
        robot: Coord,
        *,
        newly_known: frozenset[Coord] | None = None,
    ) -> CStarNBVResult:
        """Select exactly with lazy bitset bounds and current distances."""

        delta_updates = self._synchronize_unknown_mask(belief, newly_known)
        assert self._unknown_mask is not None

        distance_result = dijkstra(belief, robot)
        candidates = reachable_known_free_candidates(
            belief, robot, distance_result.distances
        )
        distances = {
            candidate: distance_result.distances[candidate]
            for candidate in candidates
        }

        was_cached_at_entry = {
            candidate: candidate in self._cache for candidate in candidates
        }
        stale_at_entry = {
            candidate: (
                self._cache[candidate].stale_upper_gain
                if candidate in self._cache
                else None
            )
            for candidate in candidates
        }
        range_bounds = {
            candidate: self._range_upper_gain(candidate)
            for candidate in candidates
        }

        refreshed_gain: dict[Coord, int] = {}
        refreshed: set[Coord] = set()
        exact: dict[Coord, CandidateEvaluation] = {}
        exact_installations = 0
        exact_replacements = 0
        stale_pops = 0
        refresh_reinserts = 0
        current_bound_escalations = 0
        priority_pops = 0
        certificate_successes = 0

        remaining = set(candidates)
        generations = {candidate: 0 for candidate in candidates}
        heap: list[
            tuple[tuple[float, int, float, int, int], Coord, int]
        ] = []

        def upper_gain(candidate: Coord) -> int:
            range_gain = range_bounds[candidate]
            entry = self._cache.get(candidate)
            if entry is None:
                return range_gain
            return min(entry.stale_upper_gain, range_gain)

        def optimistic(candidate: Coord) -> CandidateEvaluation:
            return optimistic_rank_state(
                candidate,
                upper_gain(candidate),
                distances[candidate],
            )

        def push(candidate: Coord) -> None:
            heapq.heappush(
                heap,
                (
                    candidate_rank_key(optimistic(candidate)),
                    candidate,
                    generations[candidate],
                ),
            )

        for candidate in candidates:
            push(candidate)

        def peek_valid() -> Coord | None:
            while heap:
                _, candidate, generation = heap[0]
                if (
                    candidate not in remaining
                    or generations[candidate] != generation
                ):
                    heapq.heappop(heap)
                    continue
                return candidate
            return None

        def pop_valid() -> Coord:
            nonlocal priority_pops
            candidate = peek_valid()
            if candidate is None:
                raise RuntimeError("priority queue exhausted with remaining candidates")
            heapq.heappop(heap)
            priority_pops += 1
            return candidate

        def exact_evaluate(candidate: Coord) -> None:
            nonlocal exact_installations, exact_replacements
            nonlocal current_bound_escalations

            existing = self._cache.get(candidate)
            range_gain = range_bounds[candidate]
            if existing is None:
                admissible_before = range_gain
            else:
                fresh = self._fresh_change_bound(candidate)
                if fresh > existing.stale_upper_gain:
                    raise RuntimeError(
                        f"fresh bound increased for {candidate}: "
                        f"{fresh} > {existing.stale_upper_gain}"
                    )
                if fresh > range_gain:
                    raise RuntimeError(
                        f"cached visible set escaped range bound for {candidate}: "
                        f"{fresh} > {range_gain}"
                    )
                if existing.last_bound_refresh_revision != self._map_revision:
                    raise RuntimeError(
                        "cached candidate must receive current lazy bound refresh "
                        "before exact escalation"
                    )
                admissible_before = min(existing.stale_upper_gain, range_gain)
                current_bound_escalations += 1

            visible_unknown = optimistic_visible_unknown_cells(
                belief, candidate, self.sensor_range
            )
            visible_mask = coords_to_mask(visible_unknown, belief.shape)
            gain = len(visible_unknown)
            if visible_mask.bit_count() != gain:
                raise RuntimeError("exact visible bitmask count mismatch")
            if gain > admissible_before:
                raise RuntimeError(
                    f"C* admissible bound violated for {candidate}: "
                    f"exact {gain} > bound {admissible_before}"
                )

            distance = distances[candidate]
            exact[candidate] = CandidateEvaluation(
                candidate=candidate,
                visible_unknown=visible_unknown,
                gain=gain,
                distance=distance,
                score=gain / (distance + SCORE_EPSILON),
            )
            if existing is None:
                exact_installations += 1
            else:
                exact_replacements += 1
            self._cache[candidate] = CStarCacheEntry(
                visible_mask=visible_mask,
                stale_upper_gain=gain,
                last_exact_revision=self._map_revision,
                last_bound_refresh_revision=self._map_revision,
            )
            remaining.remove(candidate)

        status: PlanStatus
        selected: CandidateEvaluation | None = None
        certificate_reason: str

        while True:
            if not candidates:
                status = PlanStatus.EXPLORATION_COMPLETE
                certificate_reason = "no_eligible_candidates"
                break

            top_candidate = peek_valid()
            top_upper = (
                upper_gain(top_candidate) if top_candidate is not None else 0
            )
            best_exact = (
                choose_best_candidate(tuple(exact.values()))
                if exact
                else None
            )

            if top_candidate is None and best_exact is not None:
                status = PlanStatus.SELECTED
                selected = best_exact
                certificate_reason = "all_remaining_candidates_exact"
                certificate_successes += 1
                break

            if (
                top_upper == 0
                and (best_exact is None or best_exact.gain == 0)
            ):
                status = PlanStatus.EXPLORATION_COMPLETE
                certificate_reason = "all_gain_upper_bounds_zero"
                break

            if best_exact is not None and top_candidate is not None:
                if tie_aware_rank_certificate(
                    best_exact,
                    (optimistic(top_candidate),),
                ):
                    status = PlanStatus.SELECTED
                    selected = best_exact
                    certificate_reason = "tie_aware_rank_dominance"
                    certificate_successes += 1
                    break

            candidate = pop_valid()
            entry = self._cache.get(candidate)
            if entry is None:
                exact_evaluate(candidate)
                continue

            if entry.last_bound_refresh_revision != self._map_revision:
                stale_pops += 1
                old_bound = entry.stale_upper_gain
                fresh_bound = self._fresh_change_bound(candidate)
                if fresh_bound > old_bound:
                    raise RuntimeError(
                        f"fresh bound increased for {candidate}: "
                        f"{fresh_bound} > {old_bound}"
                    )
                if fresh_bound > range_bounds[candidate]:
                    raise RuntimeError(
                        f"fresh bound exceeds range bound for {candidate}: "
                        f"{fresh_bound} > {range_bounds[candidate]}"
                    )
                entry.stale_upper_gain = fresh_bound
                entry.last_bound_refresh_revision = self._map_revision
                refreshed_gain[candidate] = fresh_bound
                refreshed.add(candidate)
                generations[candidate] += 1
                push(candidate)
                refresh_reinserts += 1
                continue

            exact_evaluate(candidate)

        records = tuple(
            CStarCandidateRecord(
                candidate=candidate,
                current_distance=distances[candidate],
                was_cached_at_entry=was_cached_at_entry[candidate],
                range_upper_gain=range_bounds[candidate],
                stale_upper_gain_at_entry=stale_at_entry[candidate],
                change_upper_gain_after_refresh=refreshed_gain.get(candidate),
                lazy_bound_refreshed=candidate in refreshed,
                exact_evaluated_this_cycle=candidate in exact,
                current_exact_gain=(
                    exact[candidate].gain if candidate in exact else None
                ),
                current_exact_score=(
                    exact[candidate].score if candidate in exact else None
                ),
            )
            for candidate in candidates
        )

        first_seen = sum(not was_cached_at_entry[c] for c in candidates)
        first_seen_pruned = sum(
            (not was_cached_at_entry[c]) and c not in exact
            for c in candidates
        )
        range_zero_pruned = sum(
            range_bounds[c] == 0 and c not in exact
            for c in candidates
        )
        counters = CStarCycleCounters(
            exact_visibility_evaluation_count=len(exact),
            first_seen_candidate_count=first_seen,
            first_seen_pruned_without_exact_count=first_seen_pruned,
            range_bound_evaluation_count=len(candidates),
            range_bound_zero_prune_count=range_zero_pruned,
            lazy_bound_refresh_count=len(refreshed),
            stale_bound_pop_count=stale_pops,
            stale_bound_refresh_reinsert_count=refresh_reinserts,
            current_bound_exact_escalation_count=current_bound_escalations,
            exact_cache_installation_count=exact_installations,
            exact_cache_replacement_count=exact_replacements,
            unknown_mask_delta_cell_update_count=delta_updates,
            priority_pop_count=priority_pops,
            certificate_success_count=certificate_successes,
        )

        if selected is None:
            return CStarNBVResult(
                status=status,
                selected_candidate=None,
                selected_gain=0,
                selected_distance=None,
                selected_score=0.0,
                selected_path=(),
                eligible_candidate_count=len(candidates),
                exact_gain_evaluations=len(exact),
                bound_only_candidate_count=len(candidates) - len(exact),
                certificate_reason=certificate_reason,
                candidate_records=records,
                counters=counters,
            )

        if selected.candidate not in exact:
            raise RuntimeError("Algorithm C* selected candidate must be current-exact")
        return CStarNBVResult(
            status=status,
            selected_candidate=selected.candidate,
            selected_gain=selected.gain,
            selected_distance=selected.distance,
            selected_score=selected.score,
            selected_path=distance_result.path_to(selected.candidate),
            eligible_candidate_count=len(candidates),
            exact_gain_evaluations=len(exact),
            bound_only_candidate_count=len(candidates) - len(exact),
            certificate_reason=certificate_reason,
            candidate_records=records,
            counters=counters,
        )
