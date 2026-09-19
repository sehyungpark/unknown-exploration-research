"""Guarded local-machine Experiment 2 runner for A/B/C/C*.

The primary protocol mirrors Experiment 1:
- 27 structural holdout maps at R=8;
- seven deterministic anchors;
- nine-map timing subset;
- one warm-up + six timed repetitions per method;
- separate decomposition and tracemalloc passes;
- three-map R=4/8/12 sensitivity pass.

C* adds one separate descriptive audit pass.  Audit time is never included in
primary planner timing.

Formal execution requires a clean git worktree and an already committed frozen
Experiment 2 dataset config.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import platform
import subprocess
import time
import tracemalloc
from typing import Any, Callable, Mapping, Sequence

from src.environment import GroundTruthGrid
from src.environment.fixtures import deterministic_fixtures
from src.mapping import BeliefGrid
from src.planning import (
    ChangeAwareLazyNBV,
    ChangeAwareStarNBV,
    PlanStatus,
    StaleScalarLazyNBV,
)
from src.planning.motion import legal_neighbors
from src.sensing import physical_scan
from src.utils import BeliefState, Coord, belief_hash, ground_truth_hash

from .experiment_0_runner import FIXTURE_CYCLE_LIMITS
from .experiment_2_analysis import BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED
from .experiment_2_dataset import (
    DATASET_VERSION,
    MASTER_SEED,
    load_config,
    regenerate_record,
)
from .experiment_2_instrumentation import (
    decomposition,
    require_exact_call_match,
    visibility_work,
)
from .experiment_2_logging import (
    EXPERIMENT_NAME,
    EXPERIMENT_VERSION,
    Experiment2InvocationWriter,
    METHODS,
    TIMING_ORDERS,
    WARMUP_ORDER,
)
from .random_dataset import free_components
from .simulator import ExplorationSimulator

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPOSITORY_ROOT / "configs" / "experiment_2_cstar_maps.json"
DEFAULT_OUTPUT_ROOT = REPOSITORY_ROOT / "results" / "experiment_2"
PRIMARY_SENSOR_RANGE = 8.0
SENSITIVITY_RANGES = (4.0, 8.0, 12.0)

ALGORITHM_IMPLEMENTATION_IDS: Mapping[str, str] = {
    "A": "src.planning.exhaustive_nbv:exhaustive_nbv",
    "B": "src.planning.stale_scalar_lazy_nbv:StaleScalarLazyNBV",
    "C": "src.planning.change_aware_lazy_nbv:ChangeAwareLazyNBV",
    "C*": "src.planning.change_aware_star_nbv:ChangeAwareStarNBV",
}


@dataclass(frozen=True, slots=True)
class Experiment2Case:
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
class ReferenceDecision:
    cycle_index: int
    belief_hash: str
    robot: Coord
    status: str
    candidate: Coord | None
    gain: int
    distance: float | None
    score: float
    path: tuple[Coord, ...]


@dataclass(frozen=True, slots=True)
class EpisodeReference:
    map_id: str
    sensor_range: float
    decisions: tuple[ReferenceDecision, ...]


def repository_revision() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def require_clean_worktree() -> None:
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if status.strip():
        raise RuntimeError(
            "formal Experiment 2 requires a clean git worktree before execution"
        )


def build_cases(config_path: str | Path = DEFAULT_CONFIG_PATH) -> tuple[Experiment2Case, ...]:
    config = load_config(config_path)
    cases = []
    for record in config["accepted_maps"]:
        regenerated = regenerate_record(record)
        if regenerated.map_hash != record["map_hash"]:
            raise RuntimeError("frozen Experiment 2 map hash mismatch")
        if regenerated.start != tuple(record["start"]):
            raise RuntimeError("frozen Experiment 2 start mismatch")
        cases.append(
            Experiment2Case(
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


def build_anchor_cases() -> tuple[Experiment2Case, ...]:
    return tuple(
        Experiment2Case(
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
        for fixture in deterministic_fixtures()
    )


def _start_component(case: Experiment2Case) -> frozenset[Coord]:
    return next(component for component in free_components(case.ground_truth) if case.start in component)


def _coverage(belief: BeliefGrid, component: frozenset[Coord]) -> float:
    return sum(belief.known_free(cell) for cell in component) / len(component)


def _advance(
    simulator: ExplorationSimulator,
    selected_path: tuple[Coord, ...],
) -> frozenset[Coord]:
    if not selected_path or selected_path[0] != simulator.world.robot:
        raise RuntimeError("selected path must start at current robot")
    belief = simulator.world.belief
    for source, target in zip(selected_path, selected_path[1:]):
        legal = {coord for coord, _ in legal_neighbors(belief, source)}
        if target not in legal:
            raise RuntimeError(f"illegal selected path step {source}->{target}")
    simulator.world.robot = selected_path[-1]
    observations = physical_scan(
        simulator.world.ground_truth,
        simulator.world.robot,
        simulator.sensor_range,
    )
    changed = simulator.world.belief.apply_observations(observations)
    simulator.scan_count += 1
    simulator.snapshot_index += 1
    return changed


def _planners(sensor_range: float) -> tuple[StaleScalarLazyNBV, ChangeAwareLazyNBV, ChangeAwareStarNBV]:
    return (
        StaleScalarLazyNBV(sensor_range),
        ChangeAwareLazyNBV(sensor_range),
        ChangeAwareStarNBV(sensor_range),
    )


def _call(
    method: str,
    simulator: ExplorationSimulator,
    planner_b: StaleScalarLazyNBV,
    planner_c: ChangeAwareLazyNBV,
    planner_star: ChangeAwareStarNBV,
    pending_delta_star: frozenset[Coord] | None,
) -> Any:
    if method == "A":
        return simulator.plan()
    if method == "B":
        return planner_b.plan(simulator.world.belief, simulator.world.robot)
    if method == "C":
        return planner_c.plan(simulator.world.belief, simulator.world.robot)
    if method == "C*":
        return planner_star.plan(
            simulator.world.belief,
            simulator.world.robot,
            newly_known=pending_delta_star,
        )
    raise ValueError(f"unknown method {method}")


def _decision_tuple(result: Any) -> tuple[Any, ...]:
    return (
        result.status.value,
        result.selected_candidate,
        result.selected_gain,
        result.selected_distance,
        result.selected_score,
        tuple(result.selected_path),
    )


def _matches_reference(result: Any, expected: ReferenceDecision) -> bool:
    return _decision_tuple(result) == (
        expected.status,
        expected.candidate,
        expected.gain,
        expected.distance,
        expected.score,
        expected.path,
    )


def _storage(
    planner_b: StaleScalarLazyNBV,
    planner_c: ChangeAwareLazyNBV,
    planner_star: ChangeAwareStarNBV,
) -> dict[str, int]:
    cache = planner_c.cache
    c_cached = cache.cached_visible_unknown
    c_inverse = cache.inverse_incidence
    star = planner_star.storage_counters()
    return {
        "b_cached_scalar_entry_count": len(planner_b.cached_gains),
        "c_cached_candidate_count": len(c_cached),
        "c_bound_entry_count": len(cache.bound_counts),
        "c_cached_membership_count": sum(len(v) for v in c_cached.values()),
        "c_inverse_key_count": len(c_inverse),
        "c_inverse_membership_count": sum(len(v) for v in c_inverse.values()),
        "c_reported_known_count": len(cache.reported_known_cells),
        "cstar_cached_candidate_count": star["cached_candidate_count"],
        "cstar_cached_visible_membership_count": star["cached_visible_membership_count"],
        "cstar_range_mask_count": star["range_mask_count"],
        "cstar_range_mask_membership_count": star["range_mask_membership_count"],
    }


def _c_bound_decrements(
    pre_inverse: Mapping[Coord, frozenset[Coord]],
    newly_known: frozenset[Coord],
) -> int:
    return sum(len(pre_inverse.get(cell, ())) for cell in newly_known)


def _bound_slacks(method: str, oracle: Any, result: Any) -> list[int]:
    if method == "A":
        return []
    exact = {item.candidate: item.gain for item in oracle.evaluations}
    slacks = []
    for record in result.candidate_records:
        if method == "B":
            upper = record.stale_upper_gain
        elif method == "C":
            upper = record.change_aware_upper_gain_at_entry
        else:
            upper = record.range_upper_gain
            if record.stale_upper_gain_at_entry is not None:
                upper = min(upper, record.stale_upper_gain_at_entry)
        if upper is None:
            continue
        slack = int(upper) - int(exact[record.candidate])
        if slack < 0:
            raise RuntimeError(f"{method} upper bound violated")
        slacks.append(slack)
    return slacks


def _slack_stats(values: Sequence[int]) -> dict[str, Any]:
    if not values:
        return {
            "observation_count": 0,
            "mean": None,
            "median": None,
            "p95_nearest_rank": None,
            "tight_fraction": None,
        }
    ordered = sorted(values)
    rank = max(1, int((0.95 * len(ordered) + 0.9999999999)))
    mid = len(ordered) // 2
    med = (
        ordered[mid]
        if len(ordered) % 2
        else (ordered[mid - 1] + ordered[mid]) / 2
    )
    return {
        "observation_count": len(ordered),
        "mean": sum(ordered) / len(ordered),
        "median": med,
        "p95_nearest_rank": ordered[rank - 1],
        "tight_fraction": sum(value == 0 for value in ordered) / len(ordered),
    }


def run_shared_structural(
    *,
    case: Experiment2Case,
    invocation_id: str,
    phase: str,
    sensor_range: float,
    writer: Experiment2InvocationWriter | None,
) -> EpisodeReference:
    simulator = ExplorationSimulator(case.ground_truth, case.start, sensor_range)
    planner_b, planner_c, planner_star = _planners(sensor_range)
    pending_delta_star: frozenset[Coord] | None = None
    sequences = {method: [] for method in METHODS}
    work_totals = {
        method: {
            "exact_gain_evaluation_count": 0,
            "visibility_ray_count": 0,
            "visibility_supercover_cell_count": 0,
            "visibility_interior_probe_count": 0,
        }
        for method in METHODS
    }
    c_maintenance = {
        "synchronized_newly_known_count": 0,
        "bound_decrement_count": 0,
        "exact_cache_installation_count": 0,
        "exact_cache_replacement_count": 0,
    }
    cstar_counters: dict[str, int] = {}
    peaks = {key: 0 for key in _storage(planner_b, planner_c, planner_star)}
    slacks = {"B": [], "C": [], "C*": []}
    references: list[ReferenceDecision] = []
    component = _start_component(case)
    coverage_steps = {90: None, 95: None, 99: None}
    path_length = 0.0

    for cycle in range(case.cycle_limit):
        robot = simulator.world.robot
        frozen_hash = belief_hash(simulator.world.belief)
        results: dict[str, Any] = {}
        works: dict[str, Any] = {}
        pre_inverse = planner_c.cache.inverse_incidence
        for method in METHODS:
            with visibility_work() as work:
                result = _call(
                    method, simulator, planner_b, planner_c, planner_star,
                    pending_delta_star,
                )
            require_exact_call_match(work, result.exact_gain_evaluations)
            if simulator.world.robot != robot or belief_hash(simulator.world.belief) != frozen_hash:
                raise RuntimeError(f"{method} mutated shared planning snapshot")
            results[method] = result
            works[method] = work

        oracle = results["A"]
        for method in METHODS[1:]:
            if _decision_tuple(results[method]) != _decision_tuple(oracle):
                raise RuntimeError(
                    f"correctness mismatch {case.map_id} cycle={cycle} method={method}"
                )
        for method in METHODS:
            sequences[method].append(
                None if oracle.status is PlanStatus.EXPLORATION_COMPLETE
                else results[method].selected_candidate
            )
            work_totals[method]["exact_gain_evaluation_count"] += result.exact_gain_evaluations if False else results[method].exact_gain_evaluations
            work_totals[method]["visibility_ray_count"] += works[method].visibility_ray_count
            work_totals[method]["visibility_supercover_cell_count"] += works[method].visibility_supercover_cell_count
            work_totals[method]["visibility_interior_probe_count"] += works[method].visibility_interior_probe_count
            if method != "A":
                slacks[method].extend(_bound_slacks(method, oracle, results[method]))

        c_result = results["C"]
        c_maintenance["synchronized_newly_known_count"] += len(c_result.synchronized_newly_known_cells)
        c_maintenance["bound_decrement_count"] += _c_bound_decrements(
            pre_inverse, c_result.synchronized_newly_known_cells
        )
        c_maintenance["exact_cache_installation_count"] += sum(
            record.exact_evaluated_this_cycle
            and record.change_aware_upper_gain_at_entry is None
            for record in c_result.candidate_records
        )
        c_maintenance["exact_cache_replacement_count"] += sum(
            record.exact_evaluated_this_cycle
            and record.change_aware_upper_gain_at_entry is not None
            for record in c_result.candidate_records
        )
        for name in c_result.candidate_records[:0]:
            pass
        for name, value in vars(results["C*"].counters).items() if hasattr(results["C*"].counters, "__dict__") else []:
            cstar_counters[name] = cstar_counters.get(name, 0) + int(value)
        # slots dataclass has no __dict__; enumerate declared fields deterministically.
        for name in results["C*"].counters.__dataclass_fields__:
            value = getattr(results["C*"].counters, name)
            cstar_counters[name] = cstar_counters.get(name, 0) + int(value)

        current_storage = _storage(planner_b, planner_c, planner_star)
        for key, value in current_storage.items():
            peaks[key] = max(peaks[key], value)

        references.append(
            ReferenceDecision(
                cycle_index=cycle,
                belief_hash=frozen_hash,
                robot=robot,
                status=oracle.status.value,
                candidate=oracle.selected_candidate,
                gain=oracle.selected_gain,
                distance=oracle.selected_distance,
                score=oracle.selected_score,
                path=tuple(oracle.selected_path),
            )
        )

        if oracle.status is PlanStatus.EXPLORATION_COMPLETE:
            for method in METHODS:
                if sequences[method] != sequences["A"]:
                    raise RuntimeError("target/STOP sequence mismatch")
                record = {
                    "invocation_id": invocation_id,
                    "phase": phase,
                    "dataset_version": DATASET_VERSION,
                    "map_id": case.map_id,
                    "size": case.size,
                    "density_label": case.density_label,
                    "sensor_range": sensor_range,
                    "method": method,
                    "correctness_valid": True,
                    "planning_snapshot_count": len(references),
                    "path_length": path_length,
                    "coverage_90_step_index": coverage_steps[90],
                    "coverage_95_step_index": coverage_steps[95],
                    "coverage_99_step_index": coverage_steps[99],
                    **work_totals[method],
                    "bound_slack": _slack_stats(slacks[method]) if method != "A" else None,
                    "c_maintenance": c_maintenance if method == "C" else None,
                    "cstar_counters": cstar_counters if method == "C*" else None,
                    "storage_peaks": {
                        key: value for key, value in peaks.items()
                        if (
                            (method == "B" and key.startswith("b_"))
                            or (method == "C" and key.startswith("c_") and not key.startswith("cstar_"))
                            or (method == "C*" and key.startswith("cstar_"))
                        )
                    },
                }
                if writer is not None:
                    writer.append("structural", record)
            return EpisodeReference(case.map_id, sensor_range, tuple(references))

        if oracle.selected_distance is None:
            raise RuntimeError("selected result missing distance")
        path_length += oracle.selected_distance
        changed = _advance(simulator, oracle.selected_path)
        pending_delta_star = changed
        coverage = _coverage(simulator.world.belief, component)
        for threshold in (90, 95, 99):
            if coverage_steps[threshold] is None and coverage >= threshold / 100:
                coverage_steps[threshold] = cycle + 1

    raise RuntimeError(f"cycle limit exhausted for {case.map_id}")


def run_method_episode(
    *,
    case: Experiment2Case,
    method: str,
    reference: EpisodeReference,
    invocation_id: str,
    phase: str,
    repetition_index: int | None = None,
    method_order: Sequence[str] | None = None,
    method_order_position: int | None = None,
    writer: Experiment2InvocationWriter | None = None,
) -> dict[str, Any]:
    simulator = ExplorationSimulator(case.ground_truth, case.start, reference.sensor_range)
    planner_b, planner_c, planner_star = _planners(reference.sensor_range)
    pending_delta_star: frozenset[Coord] | None = None
    wall_total = 0
    process_total = 0
    distance_total = visibility_total = maintenance_total = other_total = 0
    audit_total = 0
    tracing = phase == "memory"
    if tracing:
        tracemalloc.start()

    try:
        for expected in reference.decisions:
            if (
                simulator.world.robot != expected.robot
                or belief_hash(simulator.world.belief) != expected.belief_hash
            ):
                raise RuntimeError("method episode diverged before planning")
            call = lambda: _call(
                method, simulator, planner_b, planner_c, planner_star,
                pending_delta_star,
            )
            if phase in {"timing_warmup", "primary_timing"}:
                wall_start = time.perf_counter_ns()
                process_start = time.process_time_ns()
                result = call()
                process_total += time.process_time_ns() - process_start
                wall_total += time.perf_counter_ns() - wall_start
            elif phase == "decomposition":
                with decomposition() as measured:
                    outcome = measured.measure(call)
                result = outcome.result
                distance_total += outcome.distance_time_ns
                visibility_total += outcome.visibility_time_ns
                maintenance_total += outcome.maintenance_time_ns
                other_total += outcome.other_time_ns
            else:
                result = call()

            if not _matches_reference(result, expected):
                raise RuntimeError(
                    f"{method} diverged from structural reference at cycle {expected.cycle_index}"
                )
            if phase == "audit" and method == "C*":
                start = time.perf_counter_ns()
                planner_star.audit(simulator.world.belief)
                audit_total += time.perf_counter_ns() - start

            if result.status is PlanStatus.EXPLORATION_COMPLETE:
                break
            changed = _advance(simulator, result.selected_path)
            pending_delta_star = changed
        else:
            raise RuntimeError("reference ended without terminal decision")
    finally:
        if tracing:
            current_bytes, peak_bytes = tracemalloc.get_traced_memory()
            tracemalloc.stop()
        else:
            current_bytes = peak_bytes = None

    record = {
        "invocation_id": invocation_id,
        "phase": phase,
        "dataset_version": DATASET_VERSION,
        "map_id": case.map_id,
        "method": method,
        "sensor_range": reference.sensor_range,
        "repetition_index": repetition_index,
        "timed": phase == "primary_timing",
        "method_order": list(method_order) if method_order is not None else None,
        "method_order_position": method_order_position,
        "planner_wall_time_ns": wall_total if phase in {"timing_warmup", "primary_timing"} else None,
        "process_time_ns": process_total if phase in {"timing_warmup", "primary_timing"} else None,
        "distance_time_ns": distance_total if phase == "decomposition" else None,
        "visibility_time_ns": visibility_total if phase == "decomposition" else None,
        "maintenance_time_ns": maintenance_total if phase == "decomposition" else None,
        "other_time_ns": other_total if phase == "decomposition" else None,
        "tracemalloc_current_bytes": current_bytes,
        "tracemalloc_peak_bytes": peak_bytes,
        "audit_time_ns": audit_total if phase == "audit" else None,
        "planning_snapshot_count": len(reference.decisions),
        "correctness_valid": True,
    }
    if writer is not None:
        stream = {
            "timing_warmup": "timing",
            "primary_timing": "timing",
            "decomposition": "decomposition",
            "memory": "memory",
            "audit": "audit",
        }[phase]
        writer.append(stream, record)
    return record


def timing_schedule(
    *,
    case: Experiment2Case,
    reference: EpisodeReference,
    invocation_id: str,
    writer: Experiment2InvocationWriter | None,
) -> None:
    for position, method in enumerate(WARMUP_ORDER):
        run_method_episode(
            case=case, method=method, reference=reference,
            invocation_id=invocation_id, phase="timing_warmup",
            repetition_index=0, method_order=WARMUP_ORDER,
            method_order_position=position, writer=writer,
        )
    for repetition, order in enumerate(TIMING_ORDERS, start=1):
        for position, method in enumerate(order):
            run_method_episode(
                case=case, method=method, reference=reference,
                invocation_id=invocation_id, phase="primary_timing",
                repetition_index=repetition, method_order=order,
                method_order_position=position, writer=writer,
            )


def machine_metadata() -> dict[str, Any]:
    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "cpu_model": platform.processor() or None,
        "logical_cpu_count": os.cpu_count(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "process_architecture": platform.architecture()[0],
    }


def build_manifest(
    invocation_id: str,
    revision: str,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "experiment_name": EXPERIMENT_NAME,
        "experiment_version": EXPERIMENT_VERSION,
        "dataset_version": DATASET_VERSION,
        "invocation_id": invocation_id,
        "repository_commit": revision,
        "master_seed": MASTER_SEED,
        "primary_sensor_range": PRIMARY_SENSOR_RANGE,
        "sensitivity_sensor_ranges": list(SENSITIVITY_RANGES),
        "primary_map_ids": [record["dataset_id"] for record in config["accepted_maps"]],
        "timing_subset_map_ids": list(config["timing_subset_map_ids"]),
        "sensitivity_subset_map_ids": list(config["sensitivity_subset_map_ids"]),
        "methods": list(METHODS),
        "algorithm_implementations": dict(ALGORITHM_IMPLEMENTATION_IDS),
        "warmup_order": list(WARMUP_ORDER),
        "timing_orders": [list(order) for order in TIMING_ORDERS],
        "warmup_repetitions": 1,
        "timed_repetitions": 6,
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "movement_semantics": "8-neighbor known-FREE; orthogonal=1; diagonal=sqrt(2); no corner cutting",
        "visibility_semantics": "corner-inclusive supercover; UNKNOWN-transparent optimistic; first-hit OCCUPIED physical",
        "sensing_semantics": "initial and arrival only; none while moving",
        "primary_decision_comparison": "C*/B",
        **machine_metadata(),
    }


def run_preregistered_experiment(
    *,
    invocation_id: str,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
) -> dict[str, Any]:
    require_clean_worktree()
    revision = repository_revision()
    config = load_config(config_path)
    cases = build_cases(config_path)
    by_id = {case.map_id: case for case in cases}
    writer = Experiment2InvocationWriter(
        output_root, invocation_id,
        build_manifest(invocation_id, revision, config),
    )
    try:
        references: dict[str, EpisodeReference] = {}
        for case in cases:
            references[case.map_id] = run_shared_structural(
                case=case, invocation_id=invocation_id,
                phase="primary_structural", sensor_range=PRIMARY_SENSOR_RANGE,
                writer=writer,
            )
        for case in build_anchor_cases():
            run_shared_structural(
                case=case, invocation_id=invocation_id,
                phase="anchor_structural", sensor_range=PRIMARY_SENSOR_RANGE,
                writer=writer,
            )
        for map_id in config["timing_subset_map_ids"]:
            timing_schedule(
                case=by_id[map_id], reference=references[map_id],
                invocation_id=invocation_id, writer=writer,
            )
        for map_id in config["timing_subset_map_ids"]:
            case = by_id[map_id]
            reference = references[map_id]
            for method in METHODS:
                run_method_episode(
                    case=case, method=method, reference=reference,
                    invocation_id=invocation_id, phase="decomposition",
                    writer=writer,
                )
        for map_id in config["timing_subset_map_ids"]:
            case = by_id[map_id]
            reference = references[map_id]
            for method in METHODS:
                run_method_episode(
                    case=case, method=method, reference=reference,
                    invocation_id=invocation_id, phase="memory",
                    writer=writer,
                )
        for map_id in config["timing_subset_map_ids"]:
            run_method_episode(
                case=by_id[map_id], method="C*", reference=references[map_id],
                invocation_id=invocation_id, phase="audit", writer=writer,
            )
        for map_id in config["sensitivity_subset_map_ids"]:
            case = by_id[map_id]
            for sensor_range in SENSITIVITY_RANGES:
                run_shared_structural(
                    case=case, invocation_id=invocation_id,
                    phase="range_sensitivity", sensor_range=sensor_range,
                    writer=writer,
                )
        return writer.finalize("PASS")
    except Exception as exc:
        writer.write_failure(
            {
                "invocation_id": invocation_id,
                "repository_commit": revision,
                "exception_class": type(exc).__name__,
                "message": str(exc),
            }
        )
        writer.finalize("FAILED")
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-preregistered", action="store_true")
    parser.add_argument("--invocation-id", required=True)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    args = parser.parse_args(argv)
    if not args.execute_preregistered:
        parser.error("formal Experiment 2 requires --execute-preregistered")
    run_preregistered_experiment(
        invocation_id=args.invocation_id,
        output_root=args.output_root,
        config_path=args.config,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
