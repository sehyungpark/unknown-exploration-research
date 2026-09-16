"""Formal shared-snapshot A/B/C runner for preregistered Experiment 0.

Stage 7 installs this infrastructure but does not execute the frozen 7+60 map
workload. The command line requires an explicit ``--execute-preregistered``
gate so accidental module invocation cannot create formal research output.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Any, Callable, Mapping, Sequence

from src.environment import GroundTruthGrid
from src.environment.fixtures import deterministic_fixtures
from src.mapping import BeliefGrid
from src.planning import (
    ChangeAwareGainBoundViolation,
    ChangeAwareLazyCandidateRecord,
    ChangeAwareLazyNBV,
    ChangeAwareLazyNBVResult,
    CandidateEvaluation,
    ExhaustiveNBVResult,
    PlanStatus,
    StaleLazyCandidateRecord,
    StaleLazyNBVResult,
    StaleScalarLazyNBV,
    optimistic_rank_state,
    tie_aware_rank_certificate,
)
from src.planning.exhaustive_nbv import SCORE_EPSILON, candidate_rank_key
from src.planning.motion import legal_neighbors
from src.sensing import physical_scan
from src.utils import (
    BeliefState,
    Coord,
    belief_hash,
    ground_truth_hash,
)

from .experiment_0_failure import (
    FailureDescription,
    deterministic_failure_run_id,
    write_failure_artifact,
)
from .experiment_0_logging import (
    CYCLE_RECORD_FIELDS,
    EXPERIMENT_VERSION,
    Experiment0InvocationWriter,
)
from .random_dataset import (
    DATASET_VERSION,
    SENSOR_RANGE,
    load_config,
    regenerate_record,
)
from .simulator import ExplorationSimulator


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPOSITORY_ROOT / "configs" / "experiment_0_random_maps.json"
DEFAULT_OUTPUT_ROOT = REPOSITORY_ROOT / "results" / "experiment_0"

FIXTURE_CYCLE_LIMITS: Mapping[str, int] = {
    "open": 64,
    "single_room": 64,
    "corridor": 64,
    "dead_end": 80,
    "separated_rooms": 96,
    "clutter": 96,
    "maze_like": 128,
}

FAILURE_CLASSIFICATIONS = (
    "target_mismatch",
    "status_or_termination_mismatch",
    "selected_gain_mismatch",
    "selected_distance_mismatch",
    "selected_score_mismatch",
    "selected_path_mismatch",
    "candidate_domain_mismatch",
    "candidate_distance_mismatch",
    "b_bound_violation",
    "c_bound_violation",
    "b_tie_certificate_violation",
    "c_tie_certificate_violation",
    "c_cache_index_invariant_failure",
    "supported_change_aware_gain_bound_violation",
    "unsupported_assumption_or_lifecycle_failure",
    "safety_limit_exhaustion",
    "malformed_cycle_record",
    "unexpected_exception",
)

ALGORITHM_IMPLEMENTATION_IDS: Mapping[str, str] = {
    "A": "src.planning.exhaustive_nbv:exhaustive_nbv",
    "B": "src.planning.stale_scalar_lazy_nbv:StaleScalarLazyNBV",
    "C": "src.planning.change_aware_lazy_nbv:ChangeAwareLazyNBV",
}


@dataclass(frozen=True, slots=True)
class Experiment0Case:
    dataset_type: str
    map_id: str
    map_seed: int | None
    map_hash: str
    ground_truth: GroundTruthGrid
    start: Coord
    cycle_limit: int


class Experiment0RunFailure(RuntimeError):
    def __init__(self, classification: str, artifact_path: Path) -> None:
        super().__init__(f"Experiment 0 failed: {classification}; artifact={artifact_path}")
        self.classification = classification
        self.artifact_path = artifact_path


def repository_revision() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    revision = result.stdout.strip()
    if len(revision) != 40:
        raise RuntimeError("git rev-parse HEAD did not return a full revision")
    return revision


def build_preregistered_cases(
    config_path: str | Path = DEFAULT_CONFIG_PATH,
) -> tuple[Experiment0Case, ...]:
    """Rebuild and reverify the frozen fixture-then-random execution order."""

    cases: list[Experiment0Case] = []
    fixtures = deterministic_fixtures()
    if tuple(fixture.name for fixture in fixtures) != tuple(FIXTURE_CYCLE_LIMITS):
        raise ValueError("fixture identity/order differs from the frozen order")
    for fixture in fixtures:
        cases.append(
            Experiment0Case(
                dataset_type="fixture",
                map_id=fixture.name,
                map_seed=None,
                map_hash=ground_truth_hash(fixture.ground_truth),
                ground_truth=fixture.ground_truth,
                start=fixture.start,
                cycle_limit=FIXTURE_CYCLE_LIMITS[fixture.name],
            )
        )

    config = load_config(config_path)
    if config["dataset_version"] != DATASET_VERSION:
        raise ValueError("formal runner requires the frozen random-v2 dataset")
    records = config["accepted_maps"]
    if len(records) != 60:
        raise ValueError("formal runner requires exactly 60 frozen random maps")
    for index, record in enumerate(records):
        regenerated = regenerate_record(record)
        expected_id = f"random-{index:03d}"
        checks = {
            "dataset_id": regenerated.dataset_id == expected_id == record["dataset_id"],
            "seed": regenerated.seed == record["seed"],
            "start": regenerated.start == tuple(record["start"]),
            "cycle_limit": regenerated.cycle_limit == record["cycle_limit"],
            "recorded_map_hash": regenerated.map_hash == record["map_hash"],
            "canonical_map_hash": ground_truth_hash(regenerated.ground_truth)
            == record["map_hash"],
        }
        failed = [name for name, valid in checks.items() if not valid]
        if failed:
            raise ValueError(f"frozen random record {expected_id} failed: {failed!r}")
        cases.append(
            Experiment0Case(
                dataset_type="random",
                map_id=expected_id,
                map_seed=record["seed"],
                map_hash=record["map_hash"],
                ground_truth=regenerated.ground_truth,
                start=regenerated.start,
                cycle_limit=regenerated.cycle_limit,
            )
        )
    return tuple(cases)


def _coordinate(value: Coord | None) -> list[int] | None:
    return None if value is None else [value[0], value[1]]


def _snapshot_json(snapshot: object) -> list[list[str]] | None:
    if snapshot is None:
        return None
    return [[cell.value for cell in row] for row in snapshot]  # type: ignore[union-attr]


def _belief_from_snapshot(snapshot: tuple[tuple[BeliefState, ...], ...]) -> BeliefGrid:
    return BeliefGrid([list(row) for row in snapshot])


def _belief_counts(snapshot: tuple[tuple[BeliefState, ...], ...]) -> tuple[int, int, int]:
    unknown = sum(cell is BeliefState.UNKNOWN for row in snapshot for cell in row)
    known_free = sum(cell is BeliefState.FREE for row in snapshot for cell in row)
    known_occupied = sum(
        cell is BeliefState.OCCUPIED for row in snapshot for cell in row
    )
    return unknown, known_free, known_occupied


def _same_status_target(left: object, right: object) -> bool:
    return (
        left.status is right.status
        and left.selected_candidate == right.selected_candidate
    )


def _candidate_domains(
    a: ExhaustiveNBVResult,
    b: StaleLazyNBVResult,
    c: ChangeAwareLazyNBVResult,
) -> tuple[tuple[Coord, ...], tuple[Coord, ...], tuple[Coord, ...]]:
    return (
        tuple(record.candidate for record in a.evaluations),
        tuple(record.candidate for record in b.candidate_records),
        tuple(record.candidate for record in c.candidate_records),
    )


def _bound_validity(
    a: ExhaustiveNBVResult,
    b: StaleLazyNBVResult,
    c: ChangeAwareLazyNBVResult,
    planner_b: StaleScalarLazyNBV,
    planner_c: ChangeAwareLazyNBV,
) -> tuple[bool, bool]:
    oracle = {record.candidate: record for record in a.evaluations}
    b_cache = planner_b.cached_gains
    c_bounds = planner_c.cache.bound_counts

    def b_record_valid(record: StaleLazyCandidateRecord) -> bool:
        candidate = record.candidate
        if candidate not in oracle or candidate not in b_cache:
            return False
        exact = oracle[candidate]
        entry = record.stale_upper_gain
        if entry is not None and (
            exact.gain > entry
            or record.stale_upper_score
            != entry / (record.current_distance + SCORE_EPSILON)
        ):
            return False
        if exact.gain > b_cache[candidate]:
            return False
        if record.exact_evaluated_this_cycle:
            return (
                record.cache_refreshed
                and record.exact_gain == exact.gain
                and record.exact_score == exact.score
                and b_cache[candidate] == exact.gain
            )
        return (
            entry is not None
            and not record.cache_refreshed
            and record.exact_gain is None
            and record.exact_score is None
            and b_cache[candidate] == entry
        )

    def c_record_valid(record: ChangeAwareLazyCandidateRecord) -> bool:
        candidate = record.candidate
        if candidate not in oracle or candidate not in c_bounds:
            return False
        exact = oracle[candidate]
        entry = record.change_aware_upper_gain_at_entry
        if entry is not None and (
            exact.gain > entry
            or record.change_aware_upper_score_at_entry
            != entry / (record.current_distance + SCORE_EPSILON)
        ):
            return False
        if exact.gain > c_bounds[candidate]:
            return False
        if record.exact_evaluated_this_cycle:
            return (
                record.cache_refreshed
                and record.current_exact_gain == exact.gain
                and record.current_exact_score == exact.score
                and c_bounds[candidate] == exact.gain
            )
        return (
            entry is not None
            and not record.cache_refreshed
            and record.current_exact_gain is None
            and record.current_exact_score is None
            and c_bounds[candidate] == entry
        )

    b_valid = (
        b.exact_gain_evaluations
        == sum(record.exact_evaluated_this_cycle for record in b.candidate_records)
        and b.bound_only_candidate_count
        == sum(not record.exact_evaluated_this_cycle for record in b.candidate_records)
        and all(b_record_valid(record) for record in b.candidate_records)
    )
    c_valid = (
        c.exact_gain_evaluations
        == sum(record.exact_evaluated_this_cycle for record in c.candidate_records)
        and c.bound_only_candidate_count
        == sum(not record.exact_evaluated_this_cycle for record in c.candidate_records)
        and all(c_record_valid(record) for record in c.candidate_records)
    )
    return b_valid, c_valid


def _tie_certificate_valid(
    *,
    status: PlanStatus,
    selected_candidate: Coord | None,
    selected_gain: int,
    selected_distance: float | None,
    selected_score: float,
    candidates: tuple[Coord, ...],
    distances: Mapping[Coord, float],
    exact_candidates: frozenset[Coord],
    maintained_bounds: Mapping[Coord, int],
) -> bool:
    if status is PlanStatus.EXPLORATION_COMPLETE:
        return not candidates or all(maintained_bounds.get(candidate) == 0 for candidate in candidates)
    if any(
        candidate not in distances or candidate not in maintained_bounds
        for candidate in candidates
    ):
        return False
    if (
        selected_candidate is None
        or selected_distance is None
        or selected_candidate not in exact_candidates
        or selected_candidate not in maintained_bounds
        or maintained_bounds[selected_candidate] != selected_gain
        or selected_score
        != selected_gain / (selected_distance + SCORE_EPSILON)
    ):
        return False
    selected = CandidateEvaluation(
        candidate=selected_candidate,
        visible_unknown=frozenset(),
        gain=selected_gain,
        distance=selected_distance,
        score=selected_score,
    )
    optimistic = tuple(
        optimistic_rank_state(candidate, maintained_bounds[candidate], distances[candidate])
        for candidate in candidates
        if candidate != selected_candidate and candidate in maintained_bounds
    )
    if len(optimistic) != len(candidates) - 1:
        return False
    return tie_aware_rank_certificate(selected, optimistic)


def _membership_counts(planner_c: ChangeAwareLazyNBV) -> tuple[int, int, bool]:
    cached = sum(len(cells) for cells in planner_c.cache.cached_visible_unknown.values())
    inverse = sum(len(candidates) for candidates in planner_c.cache.inverse_incidence.values())
    try:
        planner_c.cache.validate()
        valid = cached == inverse
    except (RuntimeError, TypeError, ValueError):
        valid = False
    return cached, inverse, valid


def _bound_decrement_count(
    inverse_before_plan: Mapping[Coord, frozenset[Coord]],
    synchronized_newly_known_cells: frozenset[Coord],
) -> int:
    """Count one maintained-bound decrement per pre-plan inverse membership."""

    return sum(
        len(inverse_before_plan.get(cell, ()))
        for cell in synchronized_newly_known_cells
    )


def _build_cycle_record(
    *,
    case: Experiment0Case,
    cycle_index: int,
    robot: Coord,
    belief_before: BeliefGrid,
    a: ExhaustiveNBVResult,
    b: StaleLazyNBVResult,
    c: ChangeAwareLazyNBVResult,
    planner_b: StaleScalarLazyNBV,
    planner_c: ChangeAwareLazyNBV,
    sequence_prefix_agreement: bool,
    bound_valid_b: bool,
    bound_valid_c: bool,
    tie_valid_b: bool,
    tie_valid_c: bool,
    cache_valid_c: bool,
    decrement_count_c: int,
    cached_membership_count_c: int,
    inverse_membership_count_c: int,
) -> dict[str, Any]:
    snapshot = belief_before.snapshot()
    unknown, known_free, known_occupied = _belief_counts(snapshot)
    agreement_ab = _same_status_target(a, b)
    agreement_ac = _same_status_target(a, c)
    agreement_bc = _same_status_target(b, c)
    record = {
        "experiment_version": EXPERIMENT_VERSION,
        "dataset_type": case.dataset_type,
        "map_id": case.map_id,
        "map_seed": case.map_seed,
        "map_hash": case.map_hash,
        "cycle_index": cycle_index,
        "robot_coordinate": _coordinate(robot),
        "belief_hash": belief_hash(belief_before),
        "unknown_count": unknown,
        "known_free_count": known_free,
        "known_occupied_count": known_occupied,
        "eligible_candidate_count": a.eligible_candidate_count,
        "a_status": a.status.value,
        "a_selected_candidate": _coordinate(a.selected_candidate),
        "a_selected_gain": a.selected_gain,
        "a_selected_distance": a.selected_distance,
        "a_selected_score": a.selected_score,
        "a_exact_gain_evaluation_count": a.exact_gain_evaluations,
        "b_status": b.status.value,
        "b_selected_candidate": _coordinate(b.selected_candidate),
        "b_selected_gain": b.selected_gain,
        "b_selected_distance": b.selected_distance,
        "b_selected_score": b.selected_score,
        "b_exact_gain_evaluation_count": b.exact_gain_evaluations,
        "b_bound_only_candidate_count": b.bound_only_candidate_count,
        "b_certificate_reason": b.certificate_reason,
        "c_status": c.status.value,
        "c_selected_candidate": _coordinate(c.selected_candidate),
        "c_selected_gain": c.selected_gain,
        "c_selected_distance": c.selected_distance,
        "c_selected_score": c.selected_score,
        "c_exact_gain_evaluation_count": c.exact_gain_evaluations,
        "c_bound_only_candidate_count": c.bound_only_candidate_count,
        "c_bound_decrement_count": decrement_count_c,
        "c_cached_membership_count": cached_membership_count_c,
        "c_inverse_membership_count": inverse_membership_count_c,
        "c_certificate_reason": c.certificate_reason,
        "agreement_a_b": agreement_ab,
        "agreement_a_c": agreement_ac,
        "agreement_b_c": agreement_bc,
        "agreement_all": agreement_ab and agreement_ac and agreement_bc,
        "sequence_prefix_agreement_all": sequence_prefix_agreement,
        "bound_valid_b": bound_valid_b,
        "bound_valid_c": bound_valid_c,
        "tie_certificate_valid_b": tie_valid_b,
        "tie_certificate_valid_c": tie_valid_c,
        "cache_index_invariant_valid_c": cache_valid_c,
    }
    if tuple(record) != CYCLE_RECORD_FIELDS:
        raise RuntimeError("internal cycle-record field order differs from frozen schema")
    return record


def _candidate_artifact(
    a: ExhaustiveNBVResult | None,
    b: StaleLazyNBVResult | None,
    c: ChangeAwareLazyNBVResult | None,
    planner_b: StaleScalarLazyNBV,
    planner_c: ChangeAwareLazyNBV,
) -> list[dict[str, Any]]:
    if a is None:
        return []
    b_records = {} if b is None else {record.candidate: record for record in b.candidate_records}
    c_records = {} if c is None else {record.candidate: record for record in c.candidate_records}
    b_bounds = planner_b.cached_gains
    c_bounds = planner_c.cache.bound_counts
    payload: list[dict[str, Any]] = []
    for oracle in a.evaluations:
        b_record = b_records.get(oracle.candidate)
        c_record = c_records.get(oracle.candidate)
        payload.append(
            {
                "candidate": _coordinate(oracle.candidate),
                "distance": oracle.distance,
                "a": {
                    "visible_unknown": [_coordinate(cell) for cell in sorted(oracle.visible_unknown)],
                    "gain": oracle.gain,
                    "score": oracle.score,
                    "rank_key": list(candidate_rank_key(oracle)),
                },
                "b": None
                if b_record is None
                else {
                    "upper_gain_at_entry": b_record.stale_upper_gain,
                    "upper_score_at_entry": b_record.stale_upper_score,
                    "maintained_upper_gain_after": b_bounds.get(oracle.candidate),
                    "exact_evaluated": b_record.exact_evaluated_this_cycle,
                    "exact_gain": b_record.exact_gain,
                    "exact_score": b_record.exact_score,
                    "post_refresh_bound": b_bounds.get(oracle.candidate),
                    "optimistic_rank_after": None
                    if oracle.candidate not in b_bounds
                    else list(
                        candidate_rank_key(
                            optimistic_rank_state(
                                oracle.candidate,
                                b_bounds[oracle.candidate],
                                oracle.distance,
                            )
                        )
                    ),
                },
                "c": None
                if c_record is None
                else {
                    "upper_gain_at_entry": c_record.change_aware_upper_gain_at_entry,
                    "upper_score_at_entry": c_record.change_aware_upper_score_at_entry,
                    "maintained_upper_gain_after": c_bounds.get(oracle.candidate),
                    "exact_evaluated": c_record.exact_evaluated_this_cycle,
                    "exact_gain": c_record.current_exact_gain,
                    "exact_score": c_record.current_exact_score,
                    "post_refresh_bound": c_bounds.get(oracle.candidate),
                    "optimistic_rank_after": None
                    if oracle.candidate not in c_bounds
                    else list(
                        candidate_rank_key(
                            optimistic_rank_state(
                                oracle.candidate,
                                c_bounds[oracle.candidate],
                                oracle.distance,
                            )
                        )
                    ),
                },
            }
        )
    return payload


def _algorithm_state(
    planner_b: StaleScalarLazyNBV,
    planner_c: ChangeAwareLazyNBV,
    violation: ChangeAwareGainBoundViolation | None = None,
) -> dict[str, Any]:
    cache = planner_c.cache
    state: dict[str, Any] = {
        "b": {
            "sensor_range": planner_b.sensor_range,
            "cached_gains": [
                {"candidate": _coordinate(candidate), "gain": gain}
                for candidate, gain in sorted(planner_b.cached_gains.items())
            ],
        },
        "c": {
            "sensor_range": planner_c.sensor_range,
            "cached_visible_unknown": [
                {
                    "candidate": _coordinate(candidate),
                    "cells": [_coordinate(cell) for cell in sorted(cells)],
                }
                for candidate, cells in sorted(cache.cached_visible_unknown.items())
            ],
            "bound_counts": [
                {"candidate": _coordinate(candidate), "bound": bound}
                for candidate, bound in sorted(cache.bound_counts.items())
            ],
            "inverse_incidence": [
                {
                    "cell": _coordinate(cell),
                    "candidates": [_coordinate(candidate) for candidate in sorted(candidates)],
                }
                for cell, candidates in sorted(cache.inverse_incidence.items())
            ],
            "reported_known_cells": [
                _coordinate(cell) for cell in sorted(cache.reported_known_cells)
            ],
            "last_synchronized_snapshot": _snapshot_json(
                planner_c.last_synchronized_snapshot
            ),
        },
        "change_aware_gain_bound_violation": None,
    }
    if violation is not None:
        state["change_aware_gain_bound_violation"] = {
            "candidate": _coordinate(violation.candidate),
            "old_bound": violation.old_bound,
            "exact_gain": violation.exact_gain,
            "exact_visible_unknown": [
                _coordinate(cell) for cell in sorted(violation.exact_visible_unknown)
            ],
            "cached_visible_unknown": [
                {
                    "candidate": _coordinate(candidate),
                    "cells": [_coordinate(cell) for cell in sorted(cells)],
                }
                for candidate, cells in violation.cached_visible_unknown
            ],
            "bound_counts": [
                {"candidate": _coordinate(candidate), "bound": bound}
                for candidate, bound in violation.bound_counts
            ],
            "inverse_incidence": [
                {
                    "cell": _coordinate(cell),
                    "candidates": [_coordinate(candidate) for candidate in sorted(candidates)],
                }
                for cell, candidates in violation.inverse_incidence
            ],
            "reported_known_cells": [
                _coordinate(cell) for cell in sorted(violation.reported_known_cells)
            ],
            "previous_synchronized_snapshot": _snapshot_json(
                violation.previous_synchronized_snapshot
            ),
            "current_belief_snapshot": _snapshot_json(
                violation.current_belief_snapshot
            ),
            "newly_known_delta": [
                _coordinate(cell) for cell in sorted(violation.newly_known_delta)
            ],
            "sensor_range": violation.sensor_range,
            "current_distance": violation.current_distance,
        }
    return state


def _failure_metadata(
    *,
    case: Experiment0Case,
    invocation_id: str,
    failure_run_id: str,
    cycle_index: int,
    robot: Coord,
    belief_before: BeliefGrid,
    revision: str,
    classification: str,
) -> dict[str, Any]:
    return {
        "experiment_version": EXPERIMENT_VERSION,
        "invocation_id": invocation_id,
        "failure_run_id": failure_run_id,
        "dataset_type": case.dataset_type,
        "map_id": case.map_id,
        "map_seed": case.map_seed,
        "map_hash": case.map_hash,
        "belief_hash": belief_hash(belief_before),
        "start": _coordinate(case.start),
        "cycle_index": cycle_index,
        "cycle_limit": case.cycle_limit,
        "robot_coordinate": _coordinate(robot),
        "sensor_config": {
            "range_cells": SENSOR_RANGE,
            "field_of_view_degrees": 360,
            "physical_first_occupied_visible": True,
            "planning_unknown_transparent": True,
        },
        "ray_config": {
            "model": "corner-inclusive endpoint-inclusive symmetric supercover",
            "outside_grid": "absent",
        },
        "motion_config": {
            "connectivity": 8,
            "orthogonal_cost": 1,
            "diagonal_cost": "sqrt(2)",
            "diagonal_corner_cutting": False,
            "sensing_en_route": False,
        },
        "score_epsilon": SCORE_EPSILON,
        "tie_definition": (
            "larger score, larger exact gain, smaller exact distance, "
            "lexicographically smaller coordinate"
        ),
        "repository_revision": revision,
        "algorithm_implementations": {
            name: {"implementation_id": identifier, "revision": revision}
            for name, identifier in ALGORITHM_IMPLEMENTATION_IDS.items()
        },
        "failure_classification": classification,
    }


def _emit_failure(
    *,
    case: Experiment0Case,
    cycle_index: int,
    simulator: ExplorationSimulator,
    belief_before: BeliefGrid,
    invocation_id: str,
    writer: Experiment0InvocationWriter,
    output_root: Path,
    revision: str,
    planner_b: StaleScalarLazyNBV,
    planner_c: ChangeAwareLazyNBV,
    description: FailureDescription,
    a: ExhaustiveNBVResult | None = None,
    b: StaleLazyNBVResult | None = None,
    c: ChangeAwareLazyNBVResult | None = None,
    violation: ChangeAwareGainBoundViolation | None = None,
    robot_before: Coord | None = None,
) -> None:
    run_id = deterministic_failure_run_id(
        invocation_id=invocation_id,
        dataset_type=case.dataset_type,
        map_id=case.map_id,
        cycle_index=cycle_index,
        classification=description.classification,
    )
    metadata = _failure_metadata(
        case=case,
        invocation_id=invocation_id,
        failure_run_id=run_id,
        cycle_index=cycle_index,
        robot=simulator.world.robot if robot_before is None else robot_before,
        belief_before=belief_before,
        revision=revision,
        classification=description.classification,
    )
    artifact = write_failure_artifact(
        output_root=output_root,
        failure_run_id=run_id,
        metadata=metadata,
        ground_truth=case.ground_truth,
        belief_before=belief_before,
        candidates=_candidate_artifact(a, b, c, planner_b, planner_c),
        algorithm_state=_algorithm_state(planner_b, planner_c, violation),
        description=description,
    )
    writer.finalize("FAILED", failure_run_id=run_id)
    raise Experiment0RunFailure(description.classification, artifact)


def _classify_comparison(
    *,
    a: ExhaustiveNBVResult,
    b: StaleLazyNBVResult,
    c: ChangeAwareLazyNBVResult,
    domains: tuple[tuple[Coord, ...], tuple[Coord, ...], tuple[Coord, ...]],
    distances_match: bool,
    bound_valid_b: bool,
    bound_valid_c: bool,
    tie_valid_b: bool,
    tie_valid_c: bool,
    cache_valid_c: bool,
) -> FailureDescription | None:
    statuses = (a.status.value, b.status.value, c.status.value)
    if len(set(statuses)) != 1:
        return FailureDescription(
            "status_or_termination_mismatch",
            "A/B/C statuses differ",
            a.status.value,
            {"b": b.status.value, "c": c.status.value},
        )
    targets = (a.selected_candidate, b.selected_candidate, c.selected_candidate)
    if len(set(targets)) != 1:
        return FailureDescription(
            "target_mismatch",
            "A/B/C selected targets differ",
            a.selected_candidate,
            {"b": b.selected_candidate, "c": c.selected_candidate},
        )
    if not (
        domains[0] == domains[1] == domains[2]
        and a.eligible_candidate_count == len(domains[0])
        and b.eligible_candidate_count == len(domains[1])
        and c.eligible_candidate_count == len(domains[2])
    ):
        return FailureDescription(
            "candidate_domain_mismatch",
            "candidate domain/order differs",
            domains[0],
            {"b": domains[1], "c": domains[2]},
        )
    if not distances_match:
        return FailureDescription(
            "candidate_distance_mismatch",
            "candidate current distances differ from A",
        )
    if not (a.selected_gain == b.selected_gain == c.selected_gain):
        return FailureDescription(
            "selected_gain_mismatch",
            "selected exact gains differ",
            a.selected_gain,
            {"b": b.selected_gain, "c": c.selected_gain},
        )
    if not (a.selected_distance == b.selected_distance == c.selected_distance):
        return FailureDescription(
            "selected_distance_mismatch",
            "selected exact distances differ",
            a.selected_distance,
            {"b": b.selected_distance, "c": c.selected_distance},
        )
    if not (a.selected_score == b.selected_score == c.selected_score):
        return FailureDescription(
            "selected_score_mismatch",
            "selected exact scores differ",
            a.selected_score,
            {"b": b.selected_score, "c": c.selected_score},
        )
    if not (a.selected_path == b.selected_path == c.selected_path):
        return FailureDescription(
            "selected_path_mismatch",
            "selected exact paths differ",
            a.selected_path,
            {"b": b.selected_path, "c": c.selected_path},
        )
    if not bound_valid_b:
        return FailureDescription("b_bound_violation", "B maintained bound is below A gain")
    if not bound_valid_c:
        return FailureDescription("c_bound_violation", "C maintained bound is below A gain")
    if not tie_valid_b:
        return FailureDescription(
            "b_tie_certificate_violation",
            "B direct external tie certificate failed",
        )
    if not tie_valid_c:
        return FailureDescription(
            "c_tie_certificate_violation",
            "C direct external tie certificate failed",
        )
    if not cache_valid_c:
        return FailureDescription(
            "c_cache_index_invariant_failure",
            "C external cache/index validation failed",
        )
    return None


def _advance_shared_environment(
    simulator: ExplorationSimulator,
    selected_path: tuple[Coord, ...],
) -> None:
    if not selected_path or selected_path[0] != simulator.world.robot:
        raise RuntimeError("selected path must start at the shared robot")
    belief = simulator.world.belief
    for source, target in zip(selected_path, selected_path[1:]):
        legal = {candidate for candidate, _ in legal_neighbors(belief, source)}
        if target not in legal:
            raise RuntimeError(f"selected path contains illegal step {source} -> {target}")
    simulator.world.robot = selected_path[-1]
    observations = physical_scan(
        simulator.world.ground_truth,
        simulator.world.robot,
        simulator.sensor_range,
    )
    simulator.world.belief.apply_observations(observations)
    simulator.scan_count += 1
    simulator.snapshot_index += 1


def run_case(
    *,
    case: Experiment0Case,
    invocation_id: str,
    writer: Experiment0InvocationWriter,
    output_root: str | Path,
    revision: str,
    planner_b: StaleScalarLazyNBV | None = None,
    planner_c: ChangeAwareLazyNBV | None = None,
    record_transform: Callable[[dict[str, Any]], Mapping[str, Any]] | None = None,
    before_movement: Callable[[], None] | None = None,
) -> int:
    """Run one case; any first failure writes evidence and raises immediately."""

    if ground_truth_hash(case.ground_truth) != case.map_hash:
        raise ValueError("case ground truth does not match its frozen map hash")
    output_root = Path(output_root)
    simulator = ExplorationSimulator(case.ground_truth, case.start, SENSOR_RANGE)
    planner_b = planner_b or StaleScalarLazyNBV(SENSOR_RANGE)
    planner_c = planner_c or ChangeAwareLazyNBV(SENSOR_RANGE)
    sequences: dict[str, list[Coord | None]] = {"a": [], "b": [], "c": []}

    for cycle_index in range(case.cycle_limit):
        robot_before = simulator.world.robot
        snapshot_before = simulator.world.belief.snapshot()
        belief_before = _belief_from_snapshot(snapshot_before)
        pre_c_inverse = planner_c.cache.inverse_incidence
        a: ExhaustiveNBVResult | None = None
        b: StaleLazyNBVResult | None = None
        c: ChangeAwareLazyNBVResult | None = None

        planner_stage = "A"
        try:
            a = simulator.plan()
            if (
                simulator.world.robot != robot_before
                or simulator.world.belief.snapshot() != snapshot_before
            ):
                raise RuntimeError("Algorithm A mutated the shared snapshot")
            planner_stage = "B"
            b = planner_b.plan(simulator.world.belief, simulator.world.robot)
            if (
                simulator.world.robot != robot_before
                or simulator.world.belief.snapshot() != snapshot_before
            ):
                raise RuntimeError("Algorithm B mutated the shared snapshot")
            planner_stage = "C"
            c = planner_c.plan(simulator.world.belief, simulator.world.robot)
            if (
                simulator.world.robot != robot_before
                or simulator.world.belief.snapshot() != snapshot_before
            ):
                raise RuntimeError("Algorithm C mutated the shared snapshot")
        except ChangeAwareGainBoundViolation as exc:
            _emit_failure(
                case=case,
                cycle_index=cycle_index,
                simulator=simulator,
                belief_before=belief_before,
                invocation_id=invocation_id,
                writer=writer,
                output_root=output_root,
                revision=revision,
                planner_b=planner_b,
                planner_c=planner_c,
                description=FailureDescription(
                    "supported_change_aware_gain_bound_violation",
                    "C exact gain exceeded its maintained historical bound",
                    exc.old_bound,
                    exc.exact_gain,
                    type(exc).__name__,
                    str(exc),
                ),
                a=a,
                b=b,
                c=c,
                violation=exc,
                robot_before=robot_before,
            )
        except (TypeError, ValueError, RuntimeError) as exc:
            message = str(exc)
            if "stale gain bound violated" in message:
                classification = "b_bound_violation"
            elif planner_stage == "C" and isinstance(exc, RuntimeError) and any(
                marker in message
                for marker in (
                    "cache",
                    "bound-count",
                    "bound accounting",
                    "inverse incidence",
                    "inverse membership",
                    "tight bound",
                )
            ):
                classification = "c_cache_index_invariant_failure"
            else:
                classification = "unsupported_assumption_or_lifecycle_failure"
            _emit_failure(
                case=case,
                cycle_index=cycle_index,
                simulator=simulator,
                belief_before=belief_before,
                invocation_id=invocation_id,
                writer=writer,
                output_root=output_root,
                revision=revision,
                planner_b=planner_b,
                planner_c=planner_c,
                description=FailureDescription(
                    classification,
                    "planner validation/lifecycle failure",
                    exception_class=type(exc).__name__,
                    exception_message=str(exc),
                ),
                a=a,
                b=b,
                c=c,
                robot_before=robot_before,
            )
        except Exception as exc:
            _emit_failure(
                case=case,
                cycle_index=cycle_index,
                simulator=simulator,
                belief_before=belief_before,
                invocation_id=invocation_id,
                writer=writer,
                output_root=output_root,
                revision=revision,
                planner_b=planner_b,
                planner_c=planner_c,
                description=FailureDescription(
                    "unexpected_exception",
                    "unexpected planner exception",
                    exception_class=type(exc).__name__,
                    exception_message=str(exc),
                ),
                a=a,
                b=b,
                c=c,
                robot_before=robot_before,
            )

        assert a is not None and b is not None and c is not None
        domains = _candidate_domains(a, b, c)
        a_by_candidate = {record.candidate: record for record in a.evaluations}
        distances_match = (
            all(
                record.candidate in a_by_candidate
                and record.current_distance == a_by_candidate[record.candidate].distance
                for record in b.candidate_records
            )
            and all(
                record.candidate in a_by_candidate
                and record.current_distance == a_by_candidate[record.candidate].distance
                for record in c.candidate_records
            )
        )
        bound_valid_b, bound_valid_c = _bound_validity(a, b, c, planner_b, planner_c)
        b_distances = {record.candidate: record.current_distance for record in b.candidate_records}
        c_distances = {record.candidate: record.current_distance for record in c.candidate_records}
        b_records_by_candidate = {
            record.candidate: record for record in b.candidate_records
        }
        c_records_by_candidate = {
            record.candidate: record for record in c.candidate_records
        }
        b_selected_record_valid = b.status is PlanStatus.EXPLORATION_COMPLETE or (
            b.selected_candidate in b_records_by_candidate
            and b_records_by_candidate[b.selected_candidate].exact_evaluated_this_cycle
            and b_records_by_candidate[b.selected_candidate].exact_gain == b.selected_gain
            and b_records_by_candidate[b.selected_candidate].exact_score == b.selected_score
            and b_records_by_candidate[b.selected_candidate].current_distance
            == b.selected_distance
        )
        c_selected_record_valid = c.status is PlanStatus.EXPLORATION_COMPLETE or (
            c.selected_candidate in c_records_by_candidate
            and c_records_by_candidate[c.selected_candidate].exact_evaluated_this_cycle
            and c_records_by_candidate[c.selected_candidate].current_exact_gain
            == c.selected_gain
            and c_records_by_candidate[c.selected_candidate].current_exact_score
            == c.selected_score
            and c_records_by_candidate[c.selected_candidate].current_distance
            == c.selected_distance
        )
        tie_valid_b = b_selected_record_valid and _tie_certificate_valid(
            status=b.status,
            selected_candidate=b.selected_candidate,
            selected_gain=b.selected_gain,
            selected_distance=b.selected_distance,
            selected_score=b.selected_score,
            candidates=domains[1],
            distances=b_distances,
            exact_candidates=frozenset(
                record.candidate
                for record in b.candidate_records
                if record.exact_evaluated_this_cycle
            ),
            maintained_bounds=planner_b.cached_gains,
        )
        tie_valid_c = c_selected_record_valid and _tie_certificate_valid(
            status=c.status,
            selected_candidate=c.selected_candidate,
            selected_gain=c.selected_gain,
            selected_distance=c.selected_distance,
            selected_score=c.selected_score,
            candidates=domains[2],
            distances=c_distances,
            exact_candidates=frozenset(
                record.candidate
                for record in c.candidate_records
                if record.exact_evaluated_this_cycle
            ),
            maintained_bounds=planner_c.cache.bound_counts,
        )
        cached_count, inverse_count, cache_valid_c = _membership_counts(planner_c)
        decrement_count = _bound_decrement_count(
            pre_c_inverse,
            c.synchronized_newly_known_cells,
        )

        for key, result in (("a", a), ("b", b), ("c", c)):
            sequences[key].append(
                None
                if result.status is PlanStatus.EXPLORATION_COMPLETE
                else result.selected_candidate
            )
        sequence_prefix_agreement = (
            sequences["a"] == sequences["b"] == sequences["c"]
        )
        comparison_failure = _classify_comparison(
            a=a,
            b=b,
            c=c,
            domains=domains,
            distances_match=distances_match,
            bound_valid_b=bound_valid_b,
            bound_valid_c=bound_valid_c,
            tie_valid_b=tie_valid_b,
            tie_valid_c=tie_valid_c,
            cache_valid_c=cache_valid_c,
        )
        record = _build_cycle_record(
            case=case,
            cycle_index=cycle_index,
            robot=robot_before,
            belief_before=belief_before,
            a=a,
            b=b,
            c=c,
            planner_b=planner_b,
            planner_c=planner_c,
            sequence_prefix_agreement=sequence_prefix_agreement,
            bound_valid_b=bound_valid_b,
            bound_valid_c=bound_valid_c,
            tie_valid_b=tie_valid_b,
            tie_valid_c=tie_valid_c,
            cache_valid_c=cache_valid_c,
            decrement_count_c=decrement_count,
            cached_membership_count_c=cached_count,
            inverse_membership_count_c=inverse_count,
        )
        if record_transform is not None:
            record = dict(record_transform(record))
        try:
            writer.append_cycle(
                record,
                map_cell_count=case.ground_truth.height * case.ground_truth.width,
            )
        except (TypeError, ValueError) as exc:
            description = comparison_failure or FailureDescription(
                "malformed_cycle_record",
                "cycle record failed pre-write validation",
                exception_class=type(exc).__name__,
                exception_message=str(exc),
            )
            _emit_failure(
                case=case,
                cycle_index=cycle_index,
                simulator=simulator,
                belief_before=belief_before,
                invocation_id=invocation_id,
                writer=writer,
                output_root=output_root,
                revision=revision,
                planner_b=planner_b,
                planner_c=planner_c,
                description=description,
                a=a,
                b=b,
                c=c,
                robot_before=robot_before,
            )

        if comparison_failure is not None:
            _emit_failure(
                case=case,
                cycle_index=cycle_index,
                simulator=simulator,
                belief_before=belief_before,
                invocation_id=invocation_id,
                writer=writer,
                output_root=output_root,
                revision=revision,
                planner_b=planner_b,
                planner_c=planner_c,
                description=comparison_failure,
                a=a,
                b=b,
                c=c,
                robot_before=robot_before,
            )

        if a.status is PlanStatus.EXPLORATION_COMPLETE:
            return cycle_index + 1
        try:
            if before_movement is not None:
                before_movement()
            _advance_shared_environment(simulator, a.selected_path)
        except Exception as exc:
            _emit_failure(
                case=case,
                cycle_index=cycle_index,
                simulator=simulator,
                belief_before=belief_before,
                invocation_id=invocation_id,
                writer=writer,
                output_root=output_root,
                revision=revision,
                planner_b=planner_b,
                planner_c=planner_c,
                description=FailureDescription(
                    "unexpected_exception",
                    "shared movement or arrival sensing failed after full agreement",
                    exception_class=type(exc).__name__,
                    exception_message=str(exc),
                ),
                a=a,
                b=b,
                c=c,
                robot_before=robot_before,
            )

    snapshot_before = simulator.world.belief.snapshot()
    belief_before = _belief_from_snapshot(snapshot_before)
    try:
        a = simulator.plan()
    except Exception:
        a = None
    _emit_failure(
        case=case,
        cycle_index=case.cycle_limit,
        simulator=simulator,
        belief_before=belief_before,
        invocation_id=invocation_id,
        writer=writer,
        output_root=output_root,
        revision=revision,
        planner_b=planner_b,
        planner_c=planner_c,
        description=FailureDescription(
            "safety_limit_exhaustion",
            "case reached its frozen cycle limit without common terminal status",
            "EXPLORATION_COMPLETE before limit",
            f"limit={case.cycle_limit}",
        ),
        a=a,
    )
    raise AssertionError("unreachable")


def run_preregistered_experiment(
    *,
    invocation_id: str,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    only_map: str | None = None,
    revision: str | None = None,
) -> dict[str, Any]:
    cases = build_preregistered_cases(config_path)
    if only_map is not None:
        cases = tuple(case for case in cases if case.map_id == only_map)
        if len(cases) != 1:
            raise ValueError(f"unknown or non-unique map ID: {only_map!r}")
    revision = revision or repository_revision()
    output_root = Path(output_root)
    writer = Experiment0InvocationWriter(
        output_root,
        invocation_id,
        {
            "mode": "preregistered",
            "dataset_version": DATASET_VERSION,
            "repository_revision": revision,
            "map_order": [case.map_id for case in cases],
            "only_map": only_map,
            "algorithm_implementations": {
                name: {"implementation_id": identifier, "revision": revision}
                for name, identifier in ALGORITHM_IMPLEMENTATION_IDS.items()
            },
        },
    )
    for case in cases:
        run_case(
            case=case,
            invocation_id=invocation_id,
            writer=writer,
            output_root=output_root,
            revision=revision,
        )
    return writer.finalize("PASSED")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-preregistered", action="store_true")
    parser.add_argument("--invocation-id", required=True)
    parser.add_argument("--only-map")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    args = parser.parse_args(argv)
    if not args.execute_preregistered:
        parser.error(
            "formal Experiment 0 is guarded; pass --execute-preregistered only in Stage 8"
        )
    try:
        run_preregistered_experiment(
            invocation_id=args.invocation_id,
            output_root=args.output_root,
            config_path=args.config,
            only_map=args.only_map,
        )
    except Experiment0RunFailure as exc:
        print(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ALGORITHM_IMPLEMENTATION_IDS",
    "DEFAULT_CONFIG_PATH",
    "DEFAULT_OUTPUT_ROOT",
    "Experiment0Case",
    "Experiment0RunFailure",
    "FAILURE_CLASSIFICATIONS",
    "FIXTURE_CYCLE_LIMITS",
    "build_preregistered_cases",
    "main",
    "repository_revision",
    "run_case",
    "run_preregistered_experiment",
]
