"""Guarded Experiment 1 measurement runner; Stage 10 must not execute it."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import tracemalloc
from typing import Any, Callable, Mapping, Sequence

from src.environment import GroundTruthGrid
from src.environment.fixtures import deterministic_fixtures
from src.mapping import BeliefGrid
from src.planning import (
    ChangeAwareGainBoundViolation,
    ChangeAwareLazyNBV,
    PlanStatus,
    StaleScalarLazyNBV,
)
from src.utils import BeliefState, Coord, belief_hash, ground_truth_hash

from .experiment_0_runner import (
    FIXTURE_CYCLE_LIMITS,
    _advance_shared_environment,
    _algorithm_state,
    _belief_counts,
    _belief_from_snapshot,
    _bound_decrement_count,
    _bound_validity,
    _candidate_artifact,
    _candidate_domains,
    _membership_counts,
    _tie_certificate_valid,
)
from .experiment_1_analysis import (
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    canonical_path_hash,
    canonical_sequence_hash,
)
from .experiment_1_dataset import (
    DATASET_VERSION,
    MASTER_SEED,
    regenerate_record,
    load_config,
)
from .experiment_1_failure import (
    FailureDescription,
    deterministic_failure_run_id,
    write_failure_artifact,
)
from .experiment_1_instrumentation import (
    VisibilityWork,
    decomposition,
    require_exact_call_match,
    visibility_work,
)
from .experiment_1_logging import (
    EPISODE_FIELDS,
    EXPERIMENT_NAME,
    EXPERIMENT_VERSION,
    MANIFEST_FIELDS,
    MEMORY_FIELDS,
    SNAPSHOT_FIELDS,
    TIMING_FIELDS,
    TIMING_ORDERS,
    Experiment1InvocationWriter,
    utc_now_text,
)
from .random_dataset import free_components
from .simulator import ExplorationSimulator


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPOSITORY_ROOT / "configs" / "experiment_1_efficiency_maps.json"
DEFAULT_OUTPUT_ROOT = REPOSITORY_ROOT / "results" / "experiment_1"
PRIMARY_SENSOR_RANGE = 8.0
SENSITIVITY_RANGES = (4.0, 8.0, 12.0)
ANCHOR_ORDER = tuple(FIXTURE_CYCLE_LIMITS)

ALGORITHM_IMPLEMENTATION_IDS: Mapping[str, str] = {
    "A": "src.planning.exhaustive_nbv:exhaustive_nbv",
    "B": "src.planning.stale_scalar_lazy_nbv:StaleScalarLazyNBV",
    "C": "src.planning.change_aware_lazy_nbv:ChangeAwareLazyNBV",
}


@dataclass(frozen=True, slots=True)
class Experiment1Case:
    dataset_kind: str
    map_id: str
    size: int
    density_label: str | None
    occupancy_probability: float | None
    map_seed: int | None
    map_hash: str
    ground_truth: GroundTruthGrid
    start: Coord
    cycle_limit: int


@dataclass(frozen=True, slots=True)
class DecisionReference:
    cycle_index: int
    belief_hash: str
    robot_coordinate: Coord
    status: str
    selected_candidate: Coord | None
    selected_gain: int
    selected_distance: float | None
    selected_score: float
    selected_path_hash: str


@dataclass(frozen=True, slots=True)
class EpisodeReference:
    map_id: str
    sensor_range: float
    snapshots: tuple[DecisionReference, ...]
    target_stop_sequence_hash: str


@dataclass(frozen=True, slots=True)
class SharedStructuralResult:
    reference: EpisodeReference
    episode_records: tuple[dict[str, Any], ...]
    snapshot_records: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class MethodEpisodeResult:
    episode_record: dict[str, Any]
    snapshot_records: tuple[dict[str, Any], ...]
    timing_record: dict[str, Any] | None = None
    memory_record: dict[str, Any] | None = None


class Experiment1RunFailure(RuntimeError):
    def __init__(self, classification: str, artifact_path: Path, phase: str) -> None:
        super().__init__(
            f"Experiment 1 failed: {classification}; artifact={artifact_path}"
        )
        self.classification = classification
        self.artifact_path = artifact_path
        self.failure_run_id = artifact_path.name
        self.phase = phase


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
) -> tuple[Experiment1Case, ...]:
    config = load_config(config_path)
    if config["dataset_version"] != DATASET_VERSION:
        raise ValueError("formal runner requires frozen Experiment 1 dataset")
    records = config["accepted_maps"]
    if len(records) != 27:
        raise ValueError("formal runner requires exactly 27 primary maps")
    cases = []
    for record in records:
        regenerated = regenerate_record(record)
        checks = {
            "id": regenerated.dataset_id == record["dataset_id"],
            "seed": regenerated.seed == record["seed"],
            "start": regenerated.start == tuple(record["start"]),
            "cycle_limit": regenerated.cycle_limit == record["cycle_limit"],
            "map_hash": regenerated.map_hash == record["map_hash"],
            "canonical_hash": ground_truth_hash(regenerated.ground_truth)
            == record["map_hash"],
        }
        failed = [name for name, valid in checks.items() if not valid]
        if failed:
            raise ValueError(f"frozen map {record['dataset_id']} failed {failed!r}")
        cases.append(
            Experiment1Case(
                dataset_kind="random",
                map_id=record["dataset_id"],
                size=record["size"],
                density_label=record["density_label"],
                occupancy_probability=record["p"],
                map_seed=record["seed"],
                map_hash=record["map_hash"],
                ground_truth=regenerated.ground_truth,
                start=regenerated.start,
                cycle_limit=regenerated.cycle_limit,
            )
        )
    return tuple(cases)


def build_anchor_cases() -> tuple[Experiment1Case, ...]:
    fixtures = deterministic_fixtures()
    if tuple(fixture.name for fixture in fixtures) != ANCHOR_ORDER:
        raise ValueError("fixture order differs from frozen anchor order")
    return tuple(
        Experiment1Case(
            dataset_kind="fixture",
            map_id=fixture.name,
            size=fixture.ground_truth.height,
            density_label=None,
            occupancy_probability=None,
            map_seed=None,
            map_hash=ground_truth_hash(fixture.ground_truth),
            ground_truth=fixture.ground_truth,
            start=fixture.start,
            cycle_limit=FIXTURE_CYCLE_LIMITS[fixture.name],
        )
        for fixture in fixtures
    )


def _coordinate(value: Coord | None) -> list[int] | None:
    return None if value is None else [value[0], value[1]]


def _ordered(fields: tuple[str, ...], values: Mapping[str, Any]) -> dict[str, Any]:
    missing = [field for field in fields if field not in values]
    if missing:
        raise RuntimeError(f"internal record builder missing fields: {missing!r}")
    return {field: values[field] for field in fields}


def _start_component(case: Experiment1Case) -> frozenset[Coord]:
    for component in free_components(case.ground_truth):
        if case.start in component:
            return component
    raise RuntimeError("frozen start is not in a FREE component")


def _coverage(belief: BeliefGrid, component: frozenset[Coord]) -> float:
    known = sum(belief.known_free(cell) for cell in component)
    return known / len(component)


def _update_coverage_thresholds(
    *,
    coverage: float,
    step_index: int,
    elapsed_ns: int | None,
    steps: dict[int, int | None],
    elapsed: dict[int, int | None],
) -> None:
    for threshold in (90, 95, 99):
        if steps[threshold] is None and coverage >= threshold / 100:
            steps[threshold] = step_index
            elapsed[threshold] = elapsed_ns


def timed_planner_call(
    planner_call: Callable[[], Any],
    *,
    wall_clock_ns: Callable[[], int] = time.perf_counter_ns,
    process_clock_ns: Callable[[], int] = time.process_time_ns,
) -> tuple[Any, int, int]:
    """Keep the primary timing boundary immediately around one planner call."""

    wall_start = wall_clock_ns()
    process_start = process_clock_ns()
    result = planner_call()
    process_elapsed = process_clock_ns() - process_start
    wall_elapsed = wall_clock_ns() - wall_start
    if wall_elapsed < 0 or process_elapsed < 0:
        raise RuntimeError("planner clock moved backwards")
    return result, wall_elapsed, process_elapsed


def _planner_call(
    method: str,
    simulator: ExplorationSimulator,
    planner_b: StaleScalarLazyNBV,
    planner_c: ChangeAwareLazyNBV,
) -> Callable[[], Any]:
    if method == "A":
        return simulator.plan
    if method == "B":
        return lambda: planner_b.plan(
            simulator.world.belief, simulator.world.robot
        )
    if method == "C":
        return lambda: planner_c.plan(
            simulator.world.belief, simulator.world.robot
        )
    raise ValueError("method must be A, B, or C")


def _storage(
    planner_b: StaleScalarLazyNBV,
    planner_c: ChangeAwareLazyNBV,
) -> dict[str, int]:
    cache = planner_c.cache
    cached_memberships = sum(
        len(cells) for cells in cache.cached_visible_unknown.values()
    )
    inverse_memberships = sum(
        len(candidates) for candidates in cache.inverse_incidence.values()
    )
    return {
        "b_cached_scalar_entry_count": len(planner_b.cached_gains),
        "c_cached_candidate_count": len(cache.cached_visible_unknown),
        "c_bound_entry_count": len(cache.bound_counts),
        "c_cached_membership_count": cached_memberships,
        "c_inverse_key_count": len(cache.inverse_incidence),
        "c_inverse_membership_count": inverse_memberships,
        "c_reported_known_count": len(cache.reported_known_cells),
    }


def _bound_measurements(method: str, oracle: Any, result: Any) -> list[dict[str, Any]]:
    if method == "A":
        return []
    exact = {record.candidate: record.gain for record in oracle.evaluations}
    measurements = []
    for record in result.candidate_records:
        upper = (
            record.stale_upper_gain
            if method == "B"
            else record.change_aware_upper_gain_at_entry
        )
        if upper is None:
            continue
        gain = exact[record.candidate]
        slack = upper - gain
        if slack < 0:
            raise RuntimeError(f"{method.lower()}_bound_violation")
        measurements.append(
            {
                "method": method,
                "candidate": _coordinate(record.candidate),
                "upper_bound": upper,
                "a_exact_gain": gain,
                "absolute_slack": slack,
                "normalized_slack": slack / max(1, upper),
                "tight": slack == 0,
            }
        )
    return sorted(measurements, key=lambda item: tuple(item["candidate"]))


def _c_maintenance(result: Any, pre_inverse: Mapping[Coord, frozenset[Coord]]) -> dict[str, int]:
    installations = sum(
        record.exact_evaluated_this_cycle
        and record.change_aware_upper_gain_at_entry is None
        for record in result.candidate_records
    )
    replacements = sum(
        record.exact_evaluated_this_cycle
        and record.change_aware_upper_gain_at_entry is not None
        for record in result.candidate_records
    )
    if installations + replacements != result.exact_gain_evaluations:
        raise RuntimeError("instrumentation_mismatch")
    return {
        "c_synchronized_newly_known_count": len(
            result.synchronized_newly_known_cells
        ),
        "c_bound_decrement_count": _bound_decrement_count(
            pre_inverse, result.synchronized_newly_known_cells
        ),
        "c_exact_cache_installation_count": installations,
        "c_exact_cache_replacement_count": replacements,
    }


def _comparison_failure(
    *,
    a: Any,
    b: Any,
    c: Any,
    planner_b: StaleScalarLazyNBV,
    planner_c: ChangeAwareLazyNBV,
) -> tuple[FailureDescription | None, dict[str, bool], int, int]:
    statuses = (a.status, b.status, c.status)
    if len(set(statuses)) != 1:
        return FailureDescription(
            "sequence_or_termination_mismatch", "A/B/C status differs"
        ), {}, 0, 0
    if len({a.selected_candidate, b.selected_candidate, c.selected_candidate}) != 1:
        return FailureDescription(
            "target_mismatch", "A/B/C selected target differs"
        ), {}, 0, 0
    domains = _candidate_domains(a, b, c)
    oracle = {record.candidate: record for record in a.evaluations}
    distance_match = all(
        record.candidate in oracle
        and record.current_distance == oracle[record.candidate].distance
        for result in (b, c)
        for record in result.candidate_records
    )
    if not (
        domains[0] == domains[1] == domains[2]
        and a.eligible_candidate_count == b.eligible_candidate_count
        == c.eligible_candidate_count == len(domains[0])
        and distance_match
    ):
        return FailureDescription(
            "candidate_domain_or_distance_mismatch",
            "candidate domain/order or current distance differs",
        ), {}, 0, 0
    if not (
        a.selected_gain == b.selected_gain == c.selected_gain
        and a.selected_distance == b.selected_distance == c.selected_distance
        and a.selected_score == b.selected_score == c.selected_score
        and a.selected_path == b.selected_path == c.selected_path
    ):
        return FailureDescription(
            "selected_value_or_path_mismatch",
            "selected gain/distance/score/path differs",
        ), {}, 0, 0
    bound_b, bound_c = _bound_validity(a, b, c, planner_b, planner_c)
    if not bound_b:
        return FailureDescription("b_bound_violation", "B bound is inadmissible"), {}, 0, 0
    if not bound_c:
        return FailureDescription("c_bound_violation", "C bound is inadmissible"), {}, 0, 0
    b_distances = {record.candidate: record.current_distance for record in b.candidate_records}
    c_distances = {record.candidate: record.current_distance for record in c.candidate_records}
    b_exact = frozenset(
        record.candidate for record in b.candidate_records
        if record.exact_evaluated_this_cycle
    )
    c_exact = frozenset(
        record.candidate for record in c.candidate_records
        if record.exact_evaluated_this_cycle
    )
    tie_b = _tie_certificate_valid(
        status=b.status, selected_candidate=b.selected_candidate,
        selected_gain=b.selected_gain, selected_distance=b.selected_distance,
        selected_score=b.selected_score, candidates=domains[1],
        distances=b_distances, exact_candidates=b_exact,
        maintained_bounds=planner_b.cached_gains,
    )
    tie_c = _tie_certificate_valid(
        status=c.status, selected_candidate=c.selected_candidate,
        selected_gain=c.selected_gain, selected_distance=c.selected_distance,
        selected_score=c.selected_score, candidates=domains[2],
        distances=c_distances, exact_candidates=c_exact,
        maintained_bounds=planner_c.cache.bound_counts,
    )
    if not tie_b:
        return FailureDescription(
            "b_tie_certificate_violation", "B external tie certificate failed"
        ), {}, 0, 0
    if not tie_c:
        return FailureDescription(
            "c_tie_certificate_violation", "C external tie certificate failed"
        ), {}, 0, 0
    cached, inverse, cache_valid = _membership_counts(planner_c)
    if not cache_valid or cached != inverse:
        return FailureDescription(
            "c_cache_index_invariant_failure", "C cache/index invariant failed"
        ), {}, cached, inverse
    return None, {
        "bound_valid_b": bound_b,
        "bound_valid_c": bound_c,
        "tie_certificate_valid_b": tie_b,
        "tie_certificate_valid_c": tie_c,
        "cache_index_invariant_valid_c": cache_valid,
    }, cached, inverse


def _failure_metadata(
    *,
    case: Experiment1Case,
    invocation_id: str,
    failure_run_id: str,
    phase: str,
    method: str | None,
    method_order: list[str] | None,
    method_order_position: int | None,
    repetition_index: int | None,
    sensor_range: float,
    cycle_index: int,
    robot: Coord,
    belief_before: BeliefGrid,
    revision: str,
    classification: str,
) -> dict[str, Any]:
    return {
        "experiment_version": EXPERIMENT_VERSION,
        "dataset_version": DATASET_VERSION,
        "invocation_id": invocation_id,
        "failure_run_id": failure_run_id,
        "phase": phase,
        "map_id": case.map_id,
        "method": method,
        "method_order": method_order,
        "method_order_position": method_order_position,
        "repetition_index": repetition_index,
        "sensor_range": sensor_range,
        "cycle_index": cycle_index,
        "robot_coordinate": _coordinate(robot),
        "map_hash": case.map_hash,
        "belief_hash": belief_hash(belief_before),
        "repository_revision": revision,
        "failure_classification": classification,
        "measurement_state": {},
    }


def _emit_failure(
    *,
    case: Experiment1Case,
    invocation_id: str,
    output_root: str | Path,
    revision: str,
    phase: str,
    sensor_range: float,
    cycle_index: int,
    simulator: ExplorationSimulator,
    belief_before: BeliefGrid,
    planner_b: StaleScalarLazyNBV,
    planner_c: ChangeAwareLazyNBV,
    description: FailureDescription,
    method: str | None = None,
    method_order: list[str] | None = None,
    method_order_position: int | None = None,
    repetition_index: int | None = None,
    a: Any = None,
    b: Any = None,
    c: Any = None,
    violation: ChangeAwareGainBoundViolation | None = None,
) -> None:
    failure_id = deterministic_failure_run_id(
        invocation_id=invocation_id,
        phase=phase,
        map_id=case.map_id,
        method=method,
        repetition_index=repetition_index,
        cycle_index=cycle_index,
        classification=description.classification,
    )
    metadata = _failure_metadata(
        case=case, invocation_id=invocation_id, failure_run_id=failure_id,
        phase=phase, method=method, method_order=method_order,
        method_order_position=method_order_position,
        repetition_index=repetition_index, sensor_range=sensor_range,
        cycle_index=cycle_index, robot=simulator.world.robot,
        belief_before=belief_before, revision=revision,
        classification=description.classification,
    )
    path = write_failure_artifact(
        output_root=output_root,
        failure_run_id=failure_id,
        metadata=metadata,
        ground_truth=case.ground_truth,
        belief_before=belief_before,
        candidates=_candidate_artifact(a, b, c, planner_b, planner_c),
        algorithm_state=_algorithm_state(planner_b, planner_c, violation),
        description=description,
    )
    raise Experiment1RunFailure(description.classification, path, phase)


def _snapshot_record(
    *,
    invocation_id: str,
    phase: str,
    case: Experiment1Case,
    sensor_range: float,
    method: str,
    repetition_index: int | None,
    cycle_index: int,
    robot: Coord,
    belief: BeliefGrid,
    result: Any,
    work: VisibilityWork | None,
    planner_wall_time_ns: int | None,
    process_time_ns: int | None,
    decomposition_values: Mapping[str, int] | None,
    c_maintenance: Mapping[str, int] | None,
    storage: Mapping[str, int],
    bound_measurements: list[dict[str, Any]],
    flags: Mapping[str, bool],
) -> dict[str, Any]:
    unknown, known_free, known_occupied = _belief_counts(belief.snapshot())
    decomposition_values = decomposition_values or {}
    c_maintenance = c_maintenance or {}
    structural = phase in {
        "primary_structural", "anchor_structural", "range_sensitivity"
    }
    storage_available = structural or phase == "memory"
    values = {
        "experiment_version": EXPERIMENT_VERSION,
        "invocation_id": invocation_id,
        "phase": phase,
        "map_id": case.map_id,
        "sensor_range": sensor_range,
        "method": method,
        "repetition_index": repetition_index,
        "cycle_index": cycle_index,
        "robot_coordinate": _coordinate(robot),
        "belief_hash": belief_hash(belief),
        "unknown_count": unknown,
        "known_free_count": known_free,
        "known_occupied_count": known_occupied,
        "map_cell_count": case.ground_truth.height * case.ground_truth.width,
        "eligible_candidate_count": result.eligible_candidate_count,
        "status": result.status.value,
        "selected_candidate": _coordinate(result.selected_candidate),
        "selected_gain": result.selected_gain,
        "selected_distance": result.selected_distance,
        "selected_score": result.selected_score,
        "selected_path_hash": canonical_path_hash(result.selected_path),
        "exact_gain_evaluation_count": result.exact_gain_evaluations,
        "visibility_ray_count": None if work is None else work.visibility_ray_count,
        "visibility_supercover_cell_count": None if work is None else work.visibility_supercover_cell_count,
        "visibility_interior_probe_count": None if work is None else work.visibility_interior_probe_count,
        "planner_wall_time_ns": planner_wall_time_ns,
        "process_time_ns": process_time_ns,
        "distance_time_ns": decomposition_values.get("distance_time_ns"),
        "visibility_time_ns": decomposition_values.get("visibility_time_ns"),
        "maintenance_time_ns": decomposition_values.get("maintenance_time_ns"),
        "other_time_ns": decomposition_values.get("other_time_ns"),
        "c_synchronized_newly_known_count": c_maintenance.get("c_synchronized_newly_known_count"),
        "c_bound_decrement_count": c_maintenance.get("c_bound_decrement_count"),
        "c_exact_cache_installation_count": c_maintenance.get("c_exact_cache_installation_count"),
        "c_exact_cache_replacement_count": c_maintenance.get("c_exact_cache_replacement_count"),
        "b_cached_scalar_entry_count": storage["b_cached_scalar_entry_count"] if method == "B" and storage_available else None,
        "c_cached_candidate_count": storage["c_cached_candidate_count"] if method == "C" and storage_available else None,
        "c_bound_entry_count": storage["c_bound_entry_count"] if method == "C" and storage_available else None,
        "c_cached_membership_count": storage["c_cached_membership_count"] if method == "C" and storage_available else None,
        "c_inverse_key_count": storage["c_inverse_key_count"] if method == "C" and storage_available else None,
        "c_inverse_membership_count": storage["c_inverse_membership_count"] if method == "C" and storage_available else None,
        "c_reported_known_count": storage["c_reported_known_count"] if method == "C" and storage_available else None,
        "bound_measurements": bound_measurements,
        "agreement_all": flags.get("agreement_all", True),
        "sequence_prefix_agreement_all": flags.get("sequence_prefix_agreement_all", True),
        "bound_valid_b": flags.get("bound_valid_b", True),
        "bound_valid_c": flags.get("bound_valid_c", True),
        "tie_certificate_valid_b": flags.get("tie_certificate_valid_b", True),
        "tie_certificate_valid_c": flags.get("tie_certificate_valid_c", True),
        "cache_index_invariant_valid_c": flags.get("cache_index_invariant_valid_c", True),
        "correctness_valid": flags.get("correctness_valid", True),
        "failure_run_id": None,
    }
    return _ordered(SNAPSHOT_FIELDS, values)


def _episode_record(
    *,
    invocation_id: str,
    phase: str,
    case: Experiment1Case,
    sensor_range: float,
    method: str,
    repetition_index: int | None,
    timed: bool,
    method_order: list[str] | None,
    method_order_position: int | None,
    snapshots: Sequence[Mapping[str, Any]],
    sequence: Sequence[Coord | None],
    path_length: float,
    coverage_steps: Mapping[int, int | None],
    coverage_elapsed: Mapping[int, int | None],
    peaks: Mapping[str, int],
) -> dict[str, Any]:
    structural = phase in {
        "primary_structural", "anchor_structural", "range_sensitivity"
    }
    decomposed = phase == "decomposition"
    timing = phase in {"timing_warmup", "primary_timing"}
    storage_available = structural or phase == "memory"
    method_snapshots = list(snapshots)
    sum_or_none = lambda field, enabled: (
        sum(record.get(field, 0) for record in method_snapshots) if enabled else None
    )
    values = {
        "experiment_version": EXPERIMENT_VERSION,
        "invocation_id": invocation_id,
        "phase": phase,
        "dataset_version": DATASET_VERSION,
        "dataset_kind": case.dataset_kind,
        "map_id": case.map_id,
        "size": case.size,
        "density_label": case.density_label,
        "occupancy_probability": case.occupancy_probability,
        "map_seed": case.map_seed,
        "map_hash": case.map_hash,
        "start": _coordinate(case.start),
        "sensor_range": sensor_range,
        "method": method,
        "repetition_index": repetition_index,
        "timed": timed,
        "method_order": method_order,
        "method_order_position": method_order_position,
        "cycle_limit": case.cycle_limit,
        "terminal_status": method_snapshots[-1]["status"],
        "correctness_valid": all(record["correctness_valid"] for record in method_snapshots),
        "failure_run_id": None,
        "planning_snapshot_count": len(method_snapshots),
        "selected_snapshot_count": sum(record["status"] == "SELECTED" for record in method_snapshots),
        "target_stop_sequence_hash": canonical_sequence_hash(sequence),
        "path_length": path_length,
        "coverage_90_step_index": coverage_steps[90],
        "coverage_95_step_index": coverage_steps[95],
        "coverage_99_step_index": coverage_steps[99],
        "coverage_90_elapsed_planning_ns": coverage_elapsed[90],
        "coverage_95_elapsed_planning_ns": coverage_elapsed[95],
        "coverage_99_elapsed_planning_ns": coverage_elapsed[99],
        "exact_gain_evaluation_count": sum(record["exact_gain_evaluation_count"] for record in method_snapshots),
        "visibility_ray_count": sum_or_none("visibility_ray_count", structural),
        "visibility_supercover_cell_count": sum_or_none("visibility_supercover_cell_count", structural),
        "visibility_interior_probe_count": sum_or_none("visibility_interior_probe_count", structural),
        "c_synchronized_newly_known_count": sum(
            record["c_synchronized_newly_known_count"] or 0 for record in method_snapshots
        ) if method == "C" and structural else None,
        "c_bound_decrement_count": sum(record["c_bound_decrement_count"] or 0 for record in method_snapshots) if method == "C" and structural else None,
        "c_exact_cache_installation_count": sum(record["c_exact_cache_installation_count"] or 0 for record in method_snapshots) if method == "C" and structural else None,
        "c_exact_cache_replacement_count": sum(record["c_exact_cache_replacement_count"] or 0 for record in method_snapshots) if method == "C" and structural else None,
        "b_peak_cached_scalar_entry_count": peaks.get("b_cached_scalar_entry_count") if method == "B" and storage_available else None,
        "c_peak_cached_candidate_count": peaks.get("c_cached_candidate_count") if method == "C" and storage_available else None,
        "c_peak_bound_entry_count": peaks.get("c_bound_entry_count") if method == "C" and storage_available else None,
        "c_peak_cached_membership_count": peaks.get("c_cached_membership_count") if method == "C" and storage_available else None,
        "c_peak_inverse_key_count": peaks.get("c_inverse_key_count") if method == "C" and storage_available else None,
        "c_peak_inverse_membership_count": peaks.get("c_inverse_membership_count") if method == "C" and storage_available else None,
        "c_peak_reported_known_count": peaks.get("c_reported_known_count") if method == "C" and storage_available else None,
        "planner_wall_time_ns": sum_or_none("planner_wall_time_ns", timing),
        "process_time_ns": sum_or_none("process_time_ns", timing),
        "distance_time_ns": sum_or_none("distance_time_ns", decomposed),
        "visibility_time_ns": sum_or_none("visibility_time_ns", decomposed),
        "maintenance_time_ns": sum_or_none("maintenance_time_ns", decomposed),
        "other_time_ns": sum_or_none("other_time_ns", decomposed),
        "decomposition_residual_ns": sum_or_none("decomposition_residual_ns", decomposed),
    }
    return _ordered(EPISODE_FIELDS, values)


def run_shared_structural_case(
    *,
    case: Experiment1Case,
    invocation_id: str,
    phase: str,
    output_root: str | Path,
    revision: str,
    sensor_range: float = PRIMARY_SENSOR_RANGE,
    writer: Experiment1InvocationWriter | None = None,
    result_transform: Callable[[str, Any], Any] | None = None,
    before_movement: Callable[[], None] | None = None,
) -> SharedStructuralResult:
    if phase not in {"primary_structural", "anchor_structural", "range_sensitivity"}:
        raise ValueError("shared structural runner received invalid phase")
    simulator = ExplorationSimulator(case.ground_truth, case.start, sensor_range)
    planner_b = StaleScalarLazyNBV(sensor_range)
    planner_c = ChangeAwareLazyNBV(sensor_range)
    component = _start_component(case)
    coverage_steps = {90: None, 95: None, 99: None}
    coverage_elapsed = {90: None, 95: None, 99: None}
    _update_coverage_thresholds(
        coverage=_coverage(simulator.world.belief, component), step_index=0,
        elapsed_ns=None, steps=coverage_steps, elapsed=coverage_elapsed,
    )
    sequences: dict[str, list[Coord | None]] = {method: [] for method in "ABC"}
    method_snapshots: dict[str, list[dict[str, Any]]] = {method: [] for method in "ABC"}
    peaks = {key: 0 for key in _storage(planner_b, planner_c)}
    references: list[DecisionReference] = []
    path_length = 0.0

    for cycle_index in range(case.cycle_limit):
        robot = simulator.world.robot
        frozen_snapshot = simulator.world.belief.snapshot()
        belief_before = _belief_from_snapshot(frozen_snapshot)
        pre_inverse: Mapping[Coord, frozenset[Coord]] | None = None
        results: dict[str, Any] = {}
        works: dict[str, VisibilityWork] = {}
        try:
            for method in "ABC":
                if method == "C":
                    # Capture immediately before C synchronizes its belief/cache.
                    pre_inverse = planner_c.cache.inverse_incidence
                with visibility_work() as work:
                    result = _planner_call(method, simulator, planner_b, planner_c)()
                if result_transform is not None:
                    result = result_transform(method, result)
                require_exact_call_match(work, result.exact_gain_evaluations)
                if simulator.world.robot != robot or simulator.world.belief.snapshot() != frozen_snapshot:
                    raise RuntimeError(f"Algorithm {method} mutated the frozen snapshot")
                results[method] = result
                works[method] = work
        except ChangeAwareGainBoundViolation as exc:
            _emit_failure(
                case=case, invocation_id=invocation_id, output_root=output_root,
                revision=revision, phase=phase, sensor_range=sensor_range,
                cycle_index=cycle_index, simulator=simulator,
                belief_before=belief_before, planner_b=planner_b,
                planner_c=planner_c,
                description=FailureDescription(
                    "supported_change_aware_gain_bound_violation",
                    "C exact gain exceeded maintained bound",
                    exc.old_bound, exc.exact_gain, type(exc).__name__, str(exc),
                ), a=results.get("A"), b=results.get("B"), violation=exc,
            )
        except RuntimeError as exc:
            classification = (
                "instrumentation_mismatch"
                if "instrumentation mismatch" in str(exc)
                else "unsupported_lifecycle_or_configuration"
            )
            _emit_failure(
                case=case, invocation_id=invocation_id, output_root=output_root,
                revision=revision, phase=phase, sensor_range=sensor_range,
                cycle_index=cycle_index, simulator=simulator,
                belief_before=belief_before, planner_b=planner_b,
                planner_c=planner_c,
                description=FailureDescription(
                    classification, "planner or instrumentation validation failed",
                    exception_class=type(exc).__name__, exception_message=str(exc),
                ), a=results.get("A"), b=results.get("B"), c=results.get("C"),
            )
        except Exception as exc:
            _emit_failure(
                case=case, invocation_id=invocation_id, output_root=output_root,
                revision=revision, phase=phase, sensor_range=sensor_range,
                cycle_index=cycle_index, simulator=simulator,
                belief_before=belief_before, planner_b=planner_b,
                planner_c=planner_c,
                description=FailureDescription(
                    "unexpected_exception", "planner evaluation raised unexpectedly",
                    exception_class=type(exc).__name__,
                    exception_message=str(exc),
                ), a=results.get("A"), b=results.get("B"), c=results.get("C"),
            )

        a, b, c = results["A"], results["B"], results["C"]
        failure, flags, _, _ = _comparison_failure(
            a=a, b=b, c=c, planner_b=planner_b, planner_c=planner_c
        )
        if failure is not None:
            _emit_failure(
                case=case, invocation_id=invocation_id, output_root=output_root,
                revision=revision, phase=phase, sensor_range=sensor_range,
                cycle_index=cycle_index, simulator=simulator,
                belief_before=belief_before, planner_b=planner_b,
                planner_c=planner_c, description=failure, a=a, b=b, c=c,
            )
        flags = dict(flags)
        flags.update(
            agreement_all=True,
            sequence_prefix_agreement_all=True,
            correctness_valid=True,
        )
        try:
            if pre_inverse is None:
                raise RuntimeError("C pre-plan inverse incidence was not captured")
            maintenance = _c_maintenance(c, pre_inverse)
        except RuntimeError as exc:
            _emit_failure(
                case=case, invocation_id=invocation_id, output_root=output_root,
                revision=revision, phase=phase, sensor_range=sensor_range,
                cycle_index=cycle_index, simulator=simulator,
                belief_before=belief_before, planner_b=planner_b,
                planner_c=planner_c,
                description=FailureDescription(
                    "instrumentation_mismatch",
                    "C maintenance counts do not match exact evaluations",
                    exception_class=type(exc).__name__,
                    exception_message=str(exc),
                ), a=a, b=b, c=c,
            )
        storage = _storage(planner_b, planner_c)
        if storage["c_cached_membership_count"] != storage["c_inverse_membership_count"]:
            _emit_failure(
                case=case, invocation_id=invocation_id, output_root=output_root,
                revision=revision, phase=phase, sensor_range=sensor_range,
                cycle_index=cycle_index, simulator=simulator,
                belief_before=belief_before, planner_b=planner_b,
                planner_c=planner_c,
                description=FailureDescription(
                    "c_cache_index_invariant_failure",
                    "cached and inverse membership totals differ",
                ), a=a, b=b, c=c,
            )
        for key, value in storage.items():
            peaks[key] = max(peaks[key], value)
        oracle = a
        for method, result in results.items():
            sequences[method].append(
                None if result.status is PlanStatus.EXPLORATION_COMPLETE
                else result.selected_candidate
            )
        flags["sequence_prefix_agreement_all"] = (
            sequences["A"] == sequences["B"] == sequences["C"]
        )
        if not flags["sequence_prefix_agreement_all"]:
            _emit_failure(
                case=case, invocation_id=invocation_id, output_root=output_root,
                revision=revision, phase=phase, sensor_range=sensor_range,
                cycle_index=cycle_index, simulator=simulator,
                belief_before=belief_before, planner_b=planner_b,
                planner_c=planner_c,
                description=FailureDescription(
                    "sequence_or_termination_mismatch",
                    "A/B/C target sequence prefixes differ",
                ), a=a, b=b, c=c,
            )
        for method, result in results.items():
            snapshot_record = _snapshot_record(
                invocation_id=invocation_id, phase=phase, case=case,
                sensor_range=sensor_range, method=method,
                repetition_index=None, cycle_index=cycle_index, robot=robot,
                belief=belief_before, result=result, work=works[method],
                planner_wall_time_ns=None, process_time_ns=None,
                decomposition_values=None,
                c_maintenance=maintenance if method == "C" else None,
                storage=storage,
                bound_measurements=_bound_measurements(method, oracle, result),
                flags=flags,
            )
            method_snapshots[method].append(snapshot_record)
            if writer is not None:
                try:
                    writer.append("snapshot", snapshot_record)
                except (TypeError, ValueError) as exc:
                    _emit_failure(
                        case=case, invocation_id=invocation_id,
                        output_root=output_root, revision=revision, phase=phase,
                        sensor_range=sensor_range, cycle_index=cycle_index,
                        simulator=simulator, belief_before=belief_before,
                        planner_b=planner_b, planner_c=planner_c,
                        description=FailureDescription(
                            "malformed_measurement_record",
                            "snapshot record validation failed",
                            exception_class=type(exc).__name__,
                            exception_message=str(exc),
                        ), a=a, b=b, c=c,
                    )
        references.append(
            DecisionReference(
                cycle_index=cycle_index,
                belief_hash=belief_hash(belief_before),
                robot_coordinate=robot,
                status=a.status.value,
                selected_candidate=a.selected_candidate,
                selected_gain=a.selected_gain,
                selected_distance=a.selected_distance,
                selected_score=a.selected_score,
                selected_path_hash=canonical_path_hash(a.selected_path),
            )
        )
        if a.status is PlanStatus.EXPLORATION_COMPLETE:
            episode_records = []
            for method in "ABC":
                record = _episode_record(
                    invocation_id=invocation_id, phase=phase, case=case,
                    sensor_range=sensor_range, method=method,
                    repetition_index=None, timed=False, method_order=None,
                    method_order_position=None,
                    snapshots=method_snapshots[method], sequence=sequences[method],
                    path_length=path_length, coverage_steps=coverage_steps,
                    coverage_elapsed=coverage_elapsed, peaks=peaks,
                )
                episode_records.append(record)
                if writer is not None:
                    try:
                        writer.append("episode", record)
                    except (TypeError, ValueError) as exc:
                        _emit_failure(
                            case=case, invocation_id=invocation_id,
                            output_root=output_root, revision=revision,
                            phase=phase, sensor_range=sensor_range,
                            cycle_index=cycle_index, simulator=simulator,
                            belief_before=belief_before, planner_b=planner_b,
                            planner_c=planner_c,
                            description=FailureDescription(
                                "malformed_measurement_record",
                                "episode record validation failed",
                                exception_class=type(exc).__name__,
                                exception_message=str(exc),
                            ), a=a, b=b, c=c,
                        )
            reference = EpisodeReference(
                map_id=case.map_id,
                sensor_range=sensor_range,
                snapshots=tuple(references),
                target_stop_sequence_hash=canonical_sequence_hash(sequences["A"]),
            )
            return SharedStructuralResult(
                reference=reference,
                episode_records=tuple(episode_records),
                snapshot_records=tuple(
                    record for method in "ABC" for record in method_snapshots[method]
                ),
            )
        if before_movement is not None:
            before_movement()
        if a.selected_distance is None:
            raise RuntimeError("selected decision has no distance")
        path_length += a.selected_distance
        _advance_shared_environment(simulator, a.selected_path)
        _update_coverage_thresholds(
            coverage=_coverage(simulator.world.belief, component),
            step_index=cycle_index + 1, elapsed_ns=None,
            steps=coverage_steps, elapsed=coverage_elapsed,
        )

    belief_before = _belief_from_snapshot(simulator.world.belief.snapshot())
    _emit_failure(
        case=case, invocation_id=invocation_id, output_root=output_root,
        revision=revision, phase=phase, sensor_range=sensor_range,
        cycle_index=case.cycle_limit, simulator=simulator,
        belief_before=belief_before, planner_b=planner_b, planner_c=planner_c,
        description=FailureDescription(
            "cycle_limit_exhaustion",
            "case reached cycle limit without terminal decision",
        ),
    )
    raise AssertionError("unreachable")


def _matches_reference(result: Any, reference: DecisionReference) -> bool:
    return (
        result.status.value == reference.status
        and result.selected_candidate == reference.selected_candidate
        and result.selected_gain == reference.selected_gain
        and result.selected_distance == reference.selected_distance
        and result.selected_score == reference.selected_score
        and canonical_path_hash(result.selected_path) == reference.selected_path_hash
    )


def run_reference_method_episode(
    *,
    case: Experiment1Case,
    method: str,
    reference: EpisodeReference,
    invocation_id: str,
    phase: str,
    output_root: str | Path,
    revision: str,
    repetition_index: int | None = None,
    method_order: list[str] | None = None,
    method_order_position: int | None = None,
    writer: Experiment1InvocationWriter | None = None,
    wall_clock_ns: Callable[[], int] = time.perf_counter_ns,
    process_clock_ns: Callable[[], int] = time.process_time_ns,
    before_movement: Callable[[], None] | None = None,
) -> MethodEpisodeResult:
    if phase not in {"timing_warmup", "primary_timing", "decomposition", "memory"}:
        raise ValueError("invalid method-only phase")
    sensor_range = reference.sensor_range
    simulator = ExplorationSimulator(case.ground_truth, case.start, sensor_range)
    planner_b = StaleScalarLazyNBV(sensor_range)
    planner_c = ChangeAwareLazyNBV(sensor_range)
    component = _start_component(case)
    coverage_steps = {90: None, 95: None, 99: None}
    coverage_elapsed = {90: None, 95: None, 99: None}
    elapsed_planning = 0
    _update_coverage_thresholds(
        coverage=_coverage(simulator.world.belief, component), step_index=0,
        elapsed_ns=0 if phase in {"timing_warmup", "primary_timing"} else None,
        steps=coverage_steps, elapsed=coverage_elapsed,
    )
    snapshots: list[dict[str, Any]] = []
    sequence: list[Coord | None] = []
    path_length = 0.0
    peaks = {key: 0 for key in _storage(planner_b, planner_c)}
    tracing = phase == "memory"
    traced_current = traced_peak = None
    if tracing:
        if tracemalloc.is_tracing():
            raise RuntimeError("tracemalloc already active before memory pass")
        tracemalloc.start()
    try:
        for cycle_index, expected in enumerate(reference.snapshots):
            robot = simulator.world.robot
            frozen = simulator.world.belief.snapshot()
            belief_before = _belief_from_snapshot(frozen)
            if (
                expected.cycle_index != cycle_index
                or expected.robot_coordinate != robot
                or expected.belief_hash != belief_hash(belief_before)
            ):
                _emit_failure(
                    case=case, invocation_id=invocation_id,
                    output_root=output_root, revision=revision, phase=phase,
                    sensor_range=sensor_range, cycle_index=cycle_index,
                    simulator=simulator, belief_before=belief_before,
                    planner_b=planner_b, planner_c=planner_c,
                    method=method, method_order=method_order,
                    method_order_position=method_order_position,
                    repetition_index=repetition_index,
                    description=FailureDescription(
                        "timing_protocol_violation",
                        "method episode entered a different frozen snapshot",
                    ),
                )
            call = _planner_call(method, simulator, planner_b, planner_c)
            wall = process = None
            decomposition_values = None
            try:
                if phase in {"timing_warmup", "primary_timing"}:
                    result, wall, process = timed_planner_call(
                        call, wall_clock_ns=wall_clock_ns,
                        process_clock_ns=process_clock_ns,
                    )
                    elapsed_planning += wall
                elif phase == "decomposition":
                    with decomposition(wall_clock_ns) as measured:
                        outcome = measured.measure(call)
                    result = outcome.result
                    decomposition_values = {
                        "distance_time_ns": outcome.distance_time_ns,
                        "visibility_time_ns": outcome.visibility_time_ns,
                        "maintenance_time_ns": outcome.maintenance_time_ns,
                        "other_time_ns": outcome.other_time_ns,
                        "decomposition_residual_ns": outcome.decomposition_residual_ns,
                    }
                else:
                    result = call()
            except ChangeAwareGainBoundViolation as exc:
                _emit_failure(
                    case=case, invocation_id=invocation_id,
                    output_root=output_root, revision=revision, phase=phase,
                    sensor_range=sensor_range, cycle_index=cycle_index,
                    simulator=simulator, belief_before=belief_before,
                    planner_b=planner_b, planner_c=planner_c, method=method,
                    method_order=method_order,
                    method_order_position=method_order_position,
                    repetition_index=repetition_index,
                    description=FailureDescription(
                        "supported_change_aware_gain_bound_violation",
                        "C exact gain exceeded maintained bound",
                        exc.old_bound, exc.exact_gain,
                        type(exc).__name__, str(exc),
                    ), violation=exc,
                )
            except RuntimeError as exc:
                timing_failure = (
                    "clock moved backwards" in str(exc)
                    or "components exceed total" in str(exc)
                )
                _emit_failure(
                    case=case, invocation_id=invocation_id,
                    output_root=output_root, revision=revision, phase=phase,
                    sensor_range=sensor_range, cycle_index=cycle_index,
                    simulator=simulator, belief_before=belief_before,
                    planner_b=planner_b, planner_c=planner_c, method=method,
                    method_order=method_order,
                    method_order_position=method_order_position,
                    repetition_index=repetition_index,
                    description=FailureDescription(
                        "timing_protocol_violation" if timing_failure
                        else "unsupported_lifecycle_or_configuration",
                        "method-only planner or measurement failed",
                        exception_class=type(exc).__name__,
                        exception_message=str(exc),
                    ),
                )
            except Exception as exc:
                _emit_failure(
                    case=case, invocation_id=invocation_id,
                    output_root=output_root, revision=revision, phase=phase,
                    sensor_range=sensor_range, cycle_index=cycle_index,
                    simulator=simulator, belief_before=belief_before,
                    planner_b=planner_b, planner_c=planner_c, method=method,
                    method_order=method_order,
                    method_order_position=method_order_position,
                    repetition_index=repetition_index,
                    description=FailureDescription(
                        "unexpected_exception",
                        "method-only planner raised unexpectedly",
                        exception_class=type(exc).__name__,
                        exception_message=str(exc),
                    ),
                )
            if simulator.world.robot != robot or simulator.world.belief.snapshot() != frozen:
                _emit_failure(
                    case=case, invocation_id=invocation_id,
                    output_root=output_root, revision=revision, phase=phase,
                    sensor_range=sensor_range, cycle_index=cycle_index,
                    simulator=simulator, belief_before=belief_before,
                    planner_b=planner_b, planner_c=planner_c, method=method,
                    method_order=method_order,
                    method_order_position=method_order_position,
                    repetition_index=repetition_index,
                    description=FailureDescription(
                        "unsupported_lifecycle_or_configuration",
                        "planner mutated frozen timing snapshot",
                    ),
                )
            if not _matches_reference(result, expected):
                _emit_failure(
                    case=case, invocation_id=invocation_id,
                    output_root=output_root, revision=revision, phase=phase,
                    sensor_range=sensor_range, cycle_index=cycle_index,
                    simulator=simulator, belief_before=belief_before,
                    planner_b=planner_b, planner_c=planner_c, method=method,
                    method_order=method_order,
                    method_order_position=method_order_position,
                    repetition_index=repetition_index,
                    description=FailureDescription(
                        "selected_value_or_path_mismatch",
                        "method episode diverged from structural reference",
                    ),
                )
            storage = _storage(planner_b, planner_c)
            for key, value in storage.items():
                peaks[key] = max(peaks[key], value)
            snapshot = _snapshot_record(
                invocation_id=invocation_id, phase=phase, case=case,
                sensor_range=sensor_range, method=method,
                repetition_index=repetition_index, cycle_index=cycle_index,
                robot=robot, belief=belief_before, result=result, work=None,
                planner_wall_time_ns=wall, process_time_ns=process,
                decomposition_values=decomposition_values,
                c_maintenance=None, storage=storage,
                bound_measurements=[],
                flags={"correctness_valid": True},
            )
            snapshots.append(snapshot)
            if writer is not None:
                try:
                    writer.append("snapshot", snapshot)
                except (TypeError, ValueError) as exc:
                    _emit_failure(
                        case=case, invocation_id=invocation_id,
                        output_root=output_root, revision=revision,
                        phase=phase, sensor_range=sensor_range,
                        cycle_index=cycle_index, simulator=simulator,
                        belief_before=belief_before, planner_b=planner_b,
                        planner_c=planner_c, method=method,
                        method_order=method_order,
                        method_order_position=method_order_position,
                        repetition_index=repetition_index,
                        description=FailureDescription(
                            "malformed_measurement_record",
                            "method-only snapshot validation failed",
                            exception_class=type(exc).__name__,
                            exception_message=str(exc),
                        ),
                    )
            sequence.append(
                None if result.status is PlanStatus.EXPLORATION_COMPLETE
                else result.selected_candidate
            )
            if result.status is PlanStatus.EXPLORATION_COMPLETE:
                break
            if before_movement is not None:
                before_movement()
            path_length += result.selected_distance
            _advance_shared_environment(simulator, result.selected_path)
            _update_coverage_thresholds(
                coverage=_coverage(simulator.world.belief, component),
                step_index=cycle_index + 1,
                elapsed_ns=elapsed_planning if phase in {"timing_warmup", "primary_timing"} else None,
                steps=coverage_steps, elapsed=coverage_elapsed,
            )
        if len(snapshots) != len(reference.snapshots) or canonical_sequence_hash(sequence) != reference.target_stop_sequence_hash:
            belief_before = _belief_from_snapshot(simulator.world.belief.snapshot())
            _emit_failure(
                case=case, invocation_id=invocation_id,
                output_root=output_root, revision=revision, phase=phase,
                sensor_range=sensor_range, cycle_index=len(snapshots),
                simulator=simulator, belief_before=belief_before,
                planner_b=planner_b, planner_c=planner_c, method=method,
                method_order=method_order,
                method_order_position=method_order_position,
                repetition_index=repetition_index,
                description=FailureDescription(
                    "sequence_or_termination_mismatch",
                    "complete method sequence differs from structural reference",
                ),
            )
        if tracing:
            traced_current, traced_peak = tracemalloc.get_traced_memory()
    finally:
        if tracing and tracemalloc.is_tracing():
            tracemalloc.stop()
            tracemalloc.clear_traces()

    timed = phase == "primary_timing"
    episode = _episode_record(
        invocation_id=invocation_id, phase=phase, case=case,
        sensor_range=sensor_range, method=method,
        repetition_index=repetition_index,
        timed=timed,
        method_order=method_order,
        method_order_position=method_order_position,
        snapshots=snapshots, sequence=sequence, path_length=path_length,
        coverage_steps=coverage_steps, coverage_elapsed=coverage_elapsed,
        peaks=peaks,
    )
    timing_record = None
    if phase in {"timing_warmup", "primary_timing"}:
        timing_values = {
            "experiment_version": EXPERIMENT_VERSION,
            "invocation_id": invocation_id,
            "dataset_version": DATASET_VERSION,
            "map_id": case.map_id,
            "method": method,
            "repetition_index": repetition_index,
            "timed": timed,
            "method_order": method_order,
            "method_order_position": method_order_position,
            "warmup_discarded": phase == "timing_warmup",
            "sensor_range": sensor_range,
            "episode_planner_wall_time_ns": episode["planner_wall_time_ns"],
            "episode_process_time_ns": episode["process_time_ns"],
            "planning_snapshot_count": len(snapshots),
            "target_stop_sequence_hash": canonical_sequence_hash(sequence),
            "correctness_valid": True,
            "failure_run_id": None,
        }
        timing_record = _ordered(TIMING_FIELDS, timing_values)
    memory_record = None
    if phase == "memory":
        memory_values = {
            "experiment_version": EXPERIMENT_VERSION,
            "invocation_id": invocation_id,
            "dataset_version": DATASET_VERSION,
            "map_id": case.map_id,
            "method": method,
            "sensor_range": sensor_range,
            "measurement_kind": "python_tracemalloc_separate_non_timed_pass",
            "tracemalloc_peak_bytes": traced_peak,
            "tracemalloc_current_bytes_at_stop": traced_current,
            "b_peak_cached_scalar_entry_count": peaks["b_cached_scalar_entry_count"] if method == "B" else None,
            "c_peak_cached_candidate_count": peaks["c_cached_candidate_count"] if method == "C" else None,
            "c_peak_bound_entry_count": peaks["c_bound_entry_count"] if method == "C" else None,
            "c_peak_cached_membership_count": peaks["c_cached_membership_count"] if method == "C" else None,
            "c_peak_inverse_key_count": peaks["c_inverse_key_count"] if method == "C" else None,
            "c_peak_inverse_membership_count": peaks["c_inverse_membership_count"] if method == "C" else None,
            "c_peak_reported_known_count": peaks["c_reported_known_count"] if method == "C" else None,
            "planning_snapshot_count": len(snapshots),
            "target_stop_sequence_hash": canonical_sequence_hash(sequence),
            "correctness_valid": True,
            "failure_run_id": None,
        }
        memory_record = _ordered(MEMORY_FIELDS, memory_values)
    if writer is not None:
        try:
            writer.append("episode", episode)
            if timing_record is not None:
                writer.append("timing", timing_record)
            if memory_record is not None:
                writer.append("memory", memory_record)
        except (TypeError, ValueError) as exc:
            _emit_failure(
                case=case, invocation_id=invocation_id,
                output_root=output_root, revision=revision, phase=phase,
                sensor_range=sensor_range, cycle_index=len(snapshots) - 1,
                simulator=simulator, belief_before=belief_before,
                planner_b=planner_b, planner_c=planner_c, method=method,
                method_order=method_order,
                method_order_position=method_order_position,
                repetition_index=repetition_index,
                description=FailureDescription(
                    "malformed_measurement_record",
                    "method-only episode record validation failed",
                    exception_class=type(exc).__name__,
                    exception_message=str(exc),
                ),
            )
    return MethodEpisodeResult(
        episode_record=episode,
        snapshot_records=tuple(snapshots),
        timing_record=timing_record,
        memory_record=memory_record,
    )


def execute_timing_schedule(
    *,
    case: Experiment1Case,
    reference: EpisodeReference,
    invocation_id: str,
    output_root: str | Path,
    revision: str,
    writer: Experiment1InvocationWriter | None = None,
    episode_runner: Callable[..., MethodEpisodeResult] = run_reference_method_episode,
) -> tuple[MethodEpisodeResult, ...]:
    results = []
    warmup_order = ["A", "B", "C"]
    for position, method in enumerate(warmup_order):
        results.append(
            episode_runner(
                case=case, method=method, reference=reference,
                invocation_id=invocation_id, phase="timing_warmup",
                output_root=output_root, revision=revision,
                repetition_index=0, method_order=warmup_order,
                method_order_position=position, writer=writer,
            )
        )
    for repetition, frozen_order in enumerate(TIMING_ORDERS, start=1):
        order = list(frozen_order)
        for position, method in enumerate(order):
            results.append(
                episode_runner(
                    case=case, method=method, reference=reference,
                    invocation_id=invocation_id, phase="primary_timing",
                    output_root=output_root, revision=revision,
                    repetition_index=repetition, method_order=order,
                    method_order_position=position, writer=writer,
                )
            )
    if len(results) != 21:
        raise RuntimeError("timing schedule must contain 3 warm-ups and 18 timed episodes")
    return tuple(results)


def _physical_cpu_count() -> int | None:
    if sys.platform.startswith("linux"):
        try:
            pairs = set()
            physical = core = None
            for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
                if line.startswith("physical id"):
                    physical = line.split(":", 1)[1].strip()
                elif line.startswith("core id"):
                    core = line.split(":", 1)[1].strip()
                    if physical is not None:
                        pairs.add((physical, core))
            return len(pairs) or None
        except OSError:
            return None
    return None


def _ram_bytes() -> int | None:
    try:
        if hasattr(os, "sysconf"):
            return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))
    except (OSError, ValueError):
        pass
    return None


def machine_metadata() -> dict[str, Any]:
    cpu_model = platform.processor() or None
    if cpu_model is None and sys.platform.startswith("linux"):
        try:
            cpu_model = next(
                line.split(":", 1)[1].strip()
                for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines()
                if line.startswith("model name")
            )
        except (OSError, StopIteration):
            cpu_model = None
    affinity = None
    if hasattr(os, "sched_getaffinity"):
        try:
            affinity = sorted(os.sched_getaffinity(0))
        except OSError:
            affinity = None
    frequency = None
    governor = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
    try:
        frequency = governor.read_text(encoding="utf-8").strip() if governor.exists() else None
    except OSError:
        frequency = None
    return {
        "os": platform.system() or None,
        "os_version": platform.version() or None,
        "cpu_model": cpu_model,
        "logical_cpu_count": os.cpu_count(),
        "physical_cpu_count": _physical_cpu_count(),
        "ram_bytes": _ram_bytes(),
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "process_architecture": platform.architecture()[0],
        "cpu_affinity": affinity,
        "frequency_control_state": frequency,
    }


def build_manifest(
    *,
    invocation_id: str,
    revision: str,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    metadata = machine_metadata()
    now = utc_now_text()
    values = {
        "experiment_name": EXPERIMENT_NAME,
        "experiment_version": EXPERIMENT_VERSION,
        "dataset_version": DATASET_VERSION,
        "invocation_id": invocation_id,
        "created_at_utc": now,
        "repository_commit": revision,
        "runner_version": EXPERIMENT_VERSION,
        "master_seed": MASTER_SEED,
        "primary_sensor_range": PRIMARY_SENSOR_RANGE,
        "sensitivity_sensor_ranges": list(SENSITIVITY_RANGES),
        "primary_map_ids": [record["dataset_id"] for record in config["accepted_maps"]],
        "anchor_fixture_ids": list(ANCHOR_ORDER),
        "timing_subset_map_ids": list(config["timing_subset_map_ids"]),
        "sensitivity_subset_map_ids": list(config["sensitivity_subset_map_ids"]),
        "timing_orders": [list(order) for order in TIMING_ORDERS],
        "warmup_repetitions": 1,
        "timed_repetitions": 6,
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "movement_semantics": "8-neighbor known-FREE; orthogonal=1; diagonal=sqrt(2); no corner cutting",
        "visibility_semantics": "corner-inclusive supercover; UNKNOWN-transparent optimistic; first-hit OCCUPIED physical",
        "sensing_semantics": "initial and arrival only; none while moving",
        "score_and_tie_rule_version": "candidate-rank-key-v1",
        **metadata,
        "status": "RUNNING",
        "started_at_utc": now,
        "completed_at_utc": None,
        "failure_run_ids": [],
    }
    return _ordered(MANIFEST_FIELDS, values)


def run_preregistered_experiment(
    *,
    invocation_id: str,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
) -> dict[str, Any]:
    """Execute all frozen passes. Stage 10 tests must never call this function."""

    revision = repository_revision()
    config = load_config(config_path)
    primary_cases = build_preregistered_cases(config_path)
    primary_by_id = {case.map_id: case for case in primary_cases}
    writer = Experiment1InvocationWriter(
        output_root,
        invocation_id,
        build_manifest(invocation_id=invocation_id, revision=revision, config=config),
    )
    failure_ids: list[str] = []
    try:
        references: dict[str, EpisodeReference] = {}
        for case in primary_cases:
            result = run_shared_structural_case(
                case=case, invocation_id=invocation_id,
                phase="primary_structural", output_root=output_root,
                revision=revision, writer=writer,
            )
            references[case.map_id] = result.reference
        for case in build_anchor_cases():
            run_shared_structural_case(
                case=case, invocation_id=invocation_id,
                phase="anchor_structural", output_root=output_root,
                revision=revision, writer=writer,
            )
        for map_id in config["timing_subset_map_ids"]:
            case = primary_by_id[map_id]
            reference = references[map_id]
            execute_timing_schedule(
                case=case, reference=reference, invocation_id=invocation_id,
                output_root=output_root, revision=revision, writer=writer,
            )
        for map_id in config["timing_subset_map_ids"]:
            case = primary_by_id[map_id]
            for method in "ABC":
                run_reference_method_episode(
                    case=case, method=method, reference=references[map_id],
                    invocation_id=invocation_id, phase="decomposition",
                    output_root=output_root, revision=revision, writer=writer,
                )
        for map_id in config["timing_subset_map_ids"]:
            case = primary_by_id[map_id]
            for method in "ABC":
                run_reference_method_episode(
                    case=case, method=method, reference=references[map_id],
                    invocation_id=invocation_id, phase="memory",
                    output_root=output_root, revision=revision, writer=writer,
                )
        for map_id in config["sensitivity_subset_map_ids"]:
            case = primary_by_id[map_id]
            for sensor_range in SENSITIVITY_RANGES:
                run_shared_structural_case(
                    case=case, invocation_id=invocation_id,
                    phase="range_sensitivity", output_root=output_root,
                    revision=revision, sensor_range=sensor_range, writer=writer,
                )
        return writer.finalize("PASS")
    except Experiment1RunFailure as exc:
        failure_ids.append(exc.failure_run_id)
        correctness_classes = {
            "target_mismatch", "sequence_or_termination_mismatch",
            "selected_value_or_path_mismatch",
            "candidate_domain_or_distance_mismatch", "b_bound_violation",
            "c_bound_violation", "b_tie_certificate_violation",
            "c_tie_certificate_violation", "c_cache_index_invariant_failure",
            "supported_change_aware_gain_bound_violation",
        }
        writer.finalize(
            "FAILED", failure_run_ids=failure_ids,
            primary_correctness_failed=(
                exc.phase == "primary_structural"
                and exc.classification in correctness_classes
            ),
        )
        raise
    except Exception:
        writer.finalize("FAILED", failure_run_ids=failure_ids)
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-preregistered", action="store_true")
    parser.add_argument("--invocation-id", required=True)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    args = parser.parse_args(argv)
    if not args.execute_preregistered:
        parser.error(
            "formal Experiment 1 is guarded; Stage 11 must explicitly pass "
            "--execute-preregistered"
        )
    try:
        run_preregistered_experiment(
            invocation_id=args.invocation_id,
            output_root=args.output_root,
            config_path=args.config,
        )
    except Experiment1RunFailure as exc:
        print(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ALGORITHM_IMPLEMENTATION_IDS", "ANCHOR_ORDER", "DEFAULT_CONFIG_PATH",
    "DEFAULT_OUTPUT_ROOT", "DecisionReference", "EpisodeReference",
    "Experiment1Case", "Experiment1RunFailure", "MethodEpisodeResult",
    "PRIMARY_SENSOR_RANGE", "SENSITIVITY_RANGES", "SharedStructuralResult",
    "build_anchor_cases", "build_manifest", "build_preregistered_cases",
    "execute_timing_schedule", "machine_metadata", "main",
    "repository_revision", "run_preregistered_experiment",
    "run_reference_method_episode", "run_shared_structural_case",
    "timed_planner_call",
]
