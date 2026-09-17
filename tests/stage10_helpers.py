from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from src.environment import GroundTruthGrid
from src.evaluation.experiment_1_analysis import (
    canonical_path_hash,
    canonical_sequence_hash,
)
from src.evaluation.experiment_1_logging import (
    DATASET_VERSION,
    EPISODE_FIELDS,
    EXPERIMENT_VERSION,
    MEMORY_FIELDS,
    SNAPSHOT_FIELDS,
    TIMING_FIELDS,
    TIMING_ORDERS,
)
from src.evaluation.experiment_1_runner import (
    Experiment1Case,
    build_manifest,
)
from src.utils import ground_truth_hash


REVISION = "a" * 40
ZERO_HASH = "0" * 64


def smoke_case(*, cycle_limit: int = 16) -> Experiment1Case:
    grid = GroundTruthGrid.from_ascii(("." * 20,))
    return Experiment1Case(
        dataset_kind="fixture",
        map_id="stage10-smoke",
        size=20,
        density_label=None,
        occupancy_probability=None,
        map_seed=None,
        map_hash=ground_truth_hash(grid),
        ground_truth=grid,
        start=(0, 0),
        cycle_limit=cycle_limit,
    )


def manifest(invocation_id: str) -> dict[str, Any]:
    config = {
        "accepted_maps": [{"dataset_id": "synthetic-map"}],
        "timing_subset_map_ids": ["synthetic-map"],
        "sensitivity_subset_map_ids": ["synthetic-map"],
    }
    return build_manifest(
        invocation_id=invocation_id,
        revision=REVISION,
        config=config,
    )


def episode_record(
    *,
    method: str = "A",
    phase: str = "primary_structural",
    invocation_id: str = "synthetic",
) -> dict[str, Any]:
    structural = phase in {
        "primary_structural", "anchor_structural", "range_sensitivity"
    }
    timing = phase in {"timing_warmup", "primary_timing"}
    decomposed = phase == "decomposition"
    values: dict[str, Any] = {
        "experiment_version": EXPERIMENT_VERSION,
        "invocation_id": invocation_id,
        "phase": phase,
        "dataset_version": DATASET_VERSION,
        "dataset_kind": "random",
        "map_id": "synthetic-map",
        "size": 20,
        "density_label": "sparse",
        "occupancy_probability": 0.1,
        "map_seed": 1,
        "map_hash": ZERO_HASH,
        "start": [0, 0],
        "sensor_range": 8.0,
        "method": method,
        "repetition_index": 1 if phase == "primary_timing" else (0 if phase == "timing_warmup" else None),
        "timed": phase == "primary_timing",
        "method_order": list(TIMING_ORDERS[0]) if timing else None,
        "method_order_position": TIMING_ORDERS[0].index(method) if timing else None,
        "cycle_limit": 64,
        "terminal_status": "EXPLORATION_COMPLETE",
        "correctness_valid": True,
        "failure_run_id": None,
        "planning_snapshot_count": 1,
        "selected_snapshot_count": 0,
        "target_stop_sequence_hash": canonical_sequence_hash([None]),
        "path_length": 0.0,
        "coverage_90_step_index": 0,
        "coverage_95_step_index": 0,
        "coverage_99_step_index": 0,
        "coverage_90_elapsed_planning_ns": 10 if timing else None,
        "coverage_95_elapsed_planning_ns": 10 if timing else None,
        "coverage_99_elapsed_planning_ns": 10 if timing else None,
        "exact_gain_evaluation_count": 0,
        "visibility_ray_count": 0 if structural else None,
        "visibility_supercover_cell_count": 0 if structural else None,
        "visibility_interior_probe_count": 0 if structural else None,
        "c_synchronized_newly_known_count": 0 if structural and method == "C" else None,
        "c_bound_decrement_count": 0 if structural and method == "C" else None,
        "c_exact_cache_installation_count": 0 if structural and method == "C" else None,
        "c_exact_cache_replacement_count": 0 if structural and method == "C" else None,
        "b_peak_cached_scalar_entry_count": 0 if method == "B" and (structural or phase == "memory") else None,
        "c_peak_cached_candidate_count": 0 if method == "C" and (structural or phase == "memory") else None,
        "c_peak_bound_entry_count": 0 if method == "C" and (structural or phase == "memory") else None,
        "c_peak_cached_membership_count": 0 if method == "C" and (structural or phase == "memory") else None,
        "c_peak_inverse_key_count": 0 if method == "C" and (structural or phase == "memory") else None,
        "c_peak_inverse_membership_count": 0 if method == "C" and (structural or phase == "memory") else None,
        "c_peak_reported_known_count": 0 if method == "C" and (structural or phase == "memory") else None,
        "planner_wall_time_ns": 10 if timing else None,
        "process_time_ns": 9 if timing else None,
        "distance_time_ns": 2 if decomposed else None,
        "visibility_time_ns": 3 if decomposed else None,
        "maintenance_time_ns": 0 if decomposed else None,
        "other_time_ns": 5 if decomposed else None,
        "decomposition_residual_ns": 0 if decomposed else None,
    }
    return {field: values[field] for field in EPISODE_FIELDS}


def snapshot_record(
    *, method: str = "A", invocation_id: str = "synthetic"
) -> dict[str, Any]:
    values: dict[str, Any] = {
        "experiment_version": EXPERIMENT_VERSION,
        "invocation_id": invocation_id,
        "phase": "primary_structural",
        "map_id": "synthetic-map",
        "sensor_range": 8.0,
        "method": method,
        "repetition_index": None,
        "cycle_index": 0,
        "robot_coordinate": [0, 0],
        "belief_hash": ZERO_HASH,
        "unknown_count": 0,
        "known_free_count": 1,
        "known_occupied_count": 0,
        "map_cell_count": 1,
        "eligible_candidate_count": 0,
        "status": "EXPLORATION_COMPLETE",
        "selected_candidate": None,
        "selected_gain": 0,
        "selected_distance": None,
        "selected_score": 0.0,
        "selected_path_hash": canonical_path_hash([]),
        "exact_gain_evaluation_count": 0,
        "visibility_ray_count": 0,
        "visibility_supercover_cell_count": 0,
        "visibility_interior_probe_count": 0,
        "planner_wall_time_ns": None,
        "process_time_ns": None,
        "distance_time_ns": None,
        "visibility_time_ns": None,
        "maintenance_time_ns": None,
        "other_time_ns": None,
        "c_synchronized_newly_known_count": 0 if method == "C" else None,
        "c_bound_decrement_count": 0 if method == "C" else None,
        "c_exact_cache_installation_count": 0 if method == "C" else None,
        "c_exact_cache_replacement_count": 0 if method == "C" else None,
        "b_cached_scalar_entry_count": 0 if method == "B" else None,
        "c_cached_candidate_count": 0 if method == "C" else None,
        "c_bound_entry_count": 0 if method == "C" else None,
        "c_cached_membership_count": 0 if method == "C" else None,
        "c_inverse_key_count": 0 if method == "C" else None,
        "c_inverse_membership_count": 0 if method == "C" else None,
        "c_reported_known_count": 0 if method == "C" else None,
        "bound_measurements": [],
        "agreement_all": True,
        "sequence_prefix_agreement_all": True,
        "bound_valid_b": True,
        "bound_valid_c": True,
        "tie_certificate_valid_b": True,
        "tie_certificate_valid_c": True,
        "cache_index_invariant_valid_c": True,
        "correctness_valid": True,
        "failure_run_id": None,
    }
    return {field: values[field] for field in SNAPSHOT_FIELDS}


def timing_record(
    *,
    map_id: str = "synthetic-map",
    method: str = "A",
    repetition: int = 1,
    valid: bool = True,
    wall_ns: int = 10,
    invocation_id: str = "synthetic",
) -> dict[str, Any]:
    order = list(TIMING_ORDERS[repetition - 1])
    values = {
        "experiment_version": EXPERIMENT_VERSION,
        "invocation_id": invocation_id,
        "dataset_version": DATASET_VERSION,
        "map_id": map_id,
        "method": method,
        "repetition_index": repetition,
        "timed": True,
        "method_order": order,
        "method_order_position": order.index(method),
        "warmup_discarded": False,
        "sensor_range": 8.0,
        "episode_planner_wall_time_ns": wall_ns,
        "episode_process_time_ns": wall_ns,
        "planning_snapshot_count": 1,
        "target_stop_sequence_hash": canonical_sequence_hash([None]),
        "correctness_valid": valid,
        "failure_run_id": None,
    }
    return {field: values[field] for field in TIMING_FIELDS}


def memory_record(
    *, method: str = "A", invocation_id: str = "synthetic"
) -> dict[str, Any]:
    values = {
        "experiment_version": EXPERIMENT_VERSION,
        "invocation_id": invocation_id,
        "dataset_version": DATASET_VERSION,
        "map_id": "synthetic-map",
        "method": method,
        "sensor_range": 8.0,
        "measurement_kind": "python_tracemalloc_separate_non_timed_pass",
        "tracemalloc_peak_bytes": 100,
        "tracemalloc_current_bytes_at_stop": 50,
        "b_peak_cached_scalar_entry_count": 0 if method == "B" else None,
        "c_peak_cached_candidate_count": 0 if method == "C" else None,
        "c_peak_bound_entry_count": 0 if method == "C" else None,
        "c_peak_cached_membership_count": 0 if method == "C" else None,
        "c_peak_inverse_key_count": 0 if method == "C" else None,
        "c_peak_inverse_membership_count": 0 if method == "C" else None,
        "c_peak_reported_known_count": 0 if method == "C" else None,
        "planning_snapshot_count": 1,
        "target_stop_sequence_hash": canonical_sequence_hash([None]),
        "correctness_valid": True,
        "failure_run_id": None,
    }
    return {field: values[field] for field in MEMORY_FIELDS}


def clone(record: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(record)
