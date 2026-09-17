"""Canonical schemas and non-overwriting writers for Experiment 1."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
from typing import Any, Callable, Mapping

from .experiment_1_analysis import build_summary


EXPERIMENT_VERSION = "experiment-1-runner-v1"
DATASET_VERSION = "experiment-1-efficiency-v1"
EXPERIMENT_NAME = "Experiment 1 — Efficiency and Scaling Evaluation"

PHASES = frozenset(
    {
        "primary_structural",
        "anchor_structural",
        "timing_warmup",
        "primary_timing",
        "decomposition",
        "memory",
        "range_sensitivity",
    }
)
METHODS = frozenset({"A", "B", "C"})
STATUSES = frozenset({"SELECTED", "EXPLORATION_COMPLETE"})
TIMING_ORDERS = (
    ("A", "B", "C"),
    ("B", "C", "A"),
    ("C", "A", "B"),
    ("A", "C", "B"),
    ("C", "B", "A"),
    ("B", "A", "C"),
)

EPISODE_FIELDS = (
    "experiment_version", "invocation_id", "phase", "dataset_version",
    "dataset_kind", "map_id", "size", "density_label",
    "occupancy_probability", "map_seed", "map_hash", "start",
    "sensor_range", "method", "repetition_index", "timed", "method_order",
    "method_order_position", "cycle_limit", "terminal_status",
    "correctness_valid", "failure_run_id", "planning_snapshot_count",
    "selected_snapshot_count", "target_stop_sequence_hash", "path_length",
    "coverage_90_step_index", "coverage_95_step_index",
    "coverage_99_step_index", "coverage_90_elapsed_planning_ns",
    "coverage_95_elapsed_planning_ns", "coverage_99_elapsed_planning_ns",
    "exact_gain_evaluation_count", "visibility_ray_count",
    "visibility_supercover_cell_count", "visibility_interior_probe_count",
    "c_synchronized_newly_known_count", "c_bound_decrement_count",
    "c_exact_cache_installation_count", "c_exact_cache_replacement_count",
    "b_peak_cached_scalar_entry_count", "c_peak_cached_candidate_count",
    "c_peak_bound_entry_count", "c_peak_cached_membership_count",
    "c_peak_inverse_key_count", "c_peak_inverse_membership_count",
    "c_peak_reported_known_count", "planner_wall_time_ns", "process_time_ns",
    "distance_time_ns", "visibility_time_ns", "maintenance_time_ns",
    "other_time_ns", "decomposition_residual_ns",
)

SNAPSHOT_FIELDS = (
    "experiment_version", "invocation_id", "phase", "map_id", "sensor_range",
    "method", "repetition_index", "cycle_index", "robot_coordinate",
    "belief_hash", "unknown_count", "known_free_count",
    "known_occupied_count", "map_cell_count", "eligible_candidate_count",
    "status", "selected_candidate", "selected_gain", "selected_distance",
    "selected_score", "selected_path_hash", "exact_gain_evaluation_count",
    "visibility_ray_count", "visibility_supercover_cell_count",
    "visibility_interior_probe_count", "planner_wall_time_ns",
    "process_time_ns", "distance_time_ns", "visibility_time_ns",
    "maintenance_time_ns", "other_time_ns",
    "c_synchronized_newly_known_count", "c_bound_decrement_count",
    "c_exact_cache_installation_count", "c_exact_cache_replacement_count",
    "b_cached_scalar_entry_count", "c_cached_candidate_count",
    "c_bound_entry_count", "c_cached_membership_count", "c_inverse_key_count",
    "c_inverse_membership_count", "c_reported_known_count",
    "bound_measurements", "agreement_all", "sequence_prefix_agreement_all",
    "bound_valid_b", "bound_valid_c", "tie_certificate_valid_b",
    "tie_certificate_valid_c", "cache_index_invariant_valid_c",
    "correctness_valid", "failure_run_id",
)

BOUND_MEASUREMENT_FIELDS = (
    "method", "candidate", "upper_bound", "a_exact_gain",
    "absolute_slack", "normalized_slack", "tight",
)

TIMING_FIELDS = (
    "experiment_version", "invocation_id", "dataset_version", "map_id",
    "method", "repetition_index", "timed", "method_order",
    "method_order_position", "warmup_discarded", "sensor_range",
    "episode_planner_wall_time_ns", "episode_process_time_ns",
    "planning_snapshot_count", "target_stop_sequence_hash",
    "correctness_valid", "failure_run_id",
)

MEMORY_FIELDS = (
    "experiment_version", "invocation_id", "dataset_version", "map_id",
    "method", "sensor_range", "measurement_kind", "tracemalloc_peak_bytes",
    "tracemalloc_current_bytes_at_stop", "b_peak_cached_scalar_entry_count",
    "c_peak_cached_candidate_count", "c_peak_bound_entry_count",
    "c_peak_cached_membership_count", "c_peak_inverse_key_count",
    "c_peak_inverse_membership_count", "c_peak_reported_known_count",
    "planning_snapshot_count", "target_stop_sequence_hash",
    "correctness_valid", "failure_run_id",
)

MANIFEST_FIELDS = (
    "experiment_name", "experiment_version", "dataset_version",
    "invocation_id", "created_at_utc", "repository_commit", "runner_version",
    "master_seed", "primary_sensor_range", "sensitivity_sensor_ranges",
    "primary_map_ids", "anchor_fixture_ids", "timing_subset_map_ids",
    "sensitivity_subset_map_ids", "timing_orders", "warmup_repetitions",
    "timed_repetitions", "bootstrap_resamples", "bootstrap_seed",
    "movement_semantics", "visibility_semantics", "sensing_semantics",
    "score_and_tie_rule_version", "os", "os_version", "cpu_model",
    "logical_cpu_count", "physical_cpu_count", "ram_bytes",
    "python_implementation", "python_version", "process_architecture",
    "cpu_affinity", "frequency_control_state", "status", "started_at_utc",
    "completed_at_utc", "failure_run_ids",
)

SUMMARY_FIELDS = (
    "identity", "completion", "correctness", "work", "bound_tightness",
    "maintenance", "timing", "memory", "scaling", "sensitivity",
    "path_coverage_sanity", "decision",
)

_HASH_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
_SAFE_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
_STRUCTURAL_PHASES = {
    "primary_structural", "anchor_structural", "range_sensitivity"
}
_TIMING_PHASES = {"timing_warmup", "primary_timing"}
_WORK_FIELDS = (
    "visibility_ray_count", "visibility_supercover_cell_count",
    "visibility_interior_probe_count",
)
_DECOMPOSITION_FIELDS = (
    "distance_time_ns", "visibility_time_ns", "maintenance_time_ns",
    "other_time_ns", "decomposition_residual_ns",
)
_SNAPSHOT_DECOMPOSITION_FIELDS = _DECOMPOSITION_FIELDS[:-1]


def utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json_text(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ) + "\n"


def _exact_fields(record: Mapping[str, Any], fields: tuple[str, ...], name: str) -> None:
    if tuple(record) != fields:
        missing = [field for field in fields if field not in record]
        extra = [field for field in record if field not in fields]
        raise ValueError(f"{name} exact field/order mismatch: missing={missing!r}, extra={extra!r}")


def _nonnegative_int(value: object) -> bool:
    return type(value) is int and value >= 0


def _count(value: object, field: str, *, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    if not _nonnegative_int(value):
        raise ValueError(f"{field} must be a nonnegative integer")


def _number(value: object, field: str, *, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{field} must be a finite nonnegative number")


def _coordinate(value: object, field: str, *, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    if not (
        type(value) is list and len(value) == 2
        and all(_nonnegative_int(component) for component in value)
    ):
        raise ValueError(f"{field} must be a nonnegative [row,col]")


def _hash(value: object, field: str) -> None:
    if not isinstance(value, str) or not _HASH_PATTERN.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")


def _common(record: Mapping[str, Any]) -> None:
    if record["experiment_version"] != EXPERIMENT_VERSION:
        raise ValueError("unexpected experiment version")
    if record.get("dataset_version", DATASET_VERSION) != DATASET_VERSION:
        raise ValueError("unexpected dataset version")
    if record.get("phase") is not None and record["phase"] not in PHASES:
        raise ValueError("invalid phase")
    if record.get("method") is not None and record["method"] not in METHODS:
        raise ValueError("invalid method")
    canonical_json_text(record)


def _validate_timing_identity(record: Mapping[str, Any], *, phase: str) -> None:
    order = record["method_order"]
    position = record["method_order_position"]
    repetition = record["repetition_index"]
    if phase == "timing_warmup":
        if repetition != 0 or record["timed"] is not False:
            raise ValueError("warm-up repetition/timed fields are invalid")
        expected = ("A", "B", "C")
    else:
        if type(repetition) is not int or not 1 <= repetition <= 6:
            raise ValueError("timed repetition must be 1..6")
        if record["timed"] is not True:
            raise ValueError("primary timing record must be timed")
        expected = TIMING_ORDERS[repetition - 1]
    if order != list(expected):
        raise ValueError("method order differs from the frozen schedule")
    if position != expected.index(record["method"]):
        raise ValueError("method order position is inconsistent")


def validate_episode_record(record: Mapping[str, Any]) -> None:
    _exact_fields(record, EPISODE_FIELDS, "episode")
    _common(record)
    phase = record["phase"]
    if record["dataset_kind"] not in {"random", "fixture"}:
        raise ValueError("invalid dataset_kind")
    _coordinate(record["start"], "start")
    _hash(record["map_hash"], "map_hash")
    _number(record["sensor_range"], "sensor_range")
    _count(record["cycle_limit"], "cycle_limit")
    if record["terminal_status"] not in STATUSES:
        raise ValueError("invalid terminal_status")
    if type(record["correctness_valid"]) is not bool:
        raise ValueError("correctness_valid must be boolean")
    if type(record["timed"]) is not bool:
        raise ValueError("timed must be boolean")
    for field in (
        "planning_snapshot_count", "selected_snapshot_count",
        "exact_gain_evaluation_count",
    ):
        _count(record[field], field)
    _hash(record["target_stop_sequence_hash"], "target_stop_sequence_hash")
    _number(record["path_length"], "path_length")
    for field in EPISODE_FIELDS:
        if field.endswith("_count") or field.endswith("_time_ns"):
            if field not in {"exact_gain_evaluation_count", "planning_snapshot_count", "selected_snapshot_count"}:
                _count(record[field], field, nullable=True)
    for field in ("coverage_90_step_index", "coverage_95_step_index", "coverage_99_step_index"):
        _count(record[field], field, nullable=True)
    for field in (
        "coverage_90_elapsed_planning_ns",
        "coverage_95_elapsed_planning_ns",
        "coverage_99_elapsed_planning_ns",
    ):
        _count(record[field], field, nullable=True)
    _count(record["decomposition_residual_ns"], "decomposition_residual_ns", nullable=True)

    if phase in _TIMING_PHASES:
        _validate_timing_identity(record, phase=phase)
        _count(record["planner_wall_time_ns"], "planner_wall_time_ns")
        _count(record["process_time_ns"], "process_time_ns")
        if any(record[field] is not None for field in _WORK_FIELDS + _DECOMPOSITION_FIELDS):
            raise ValueError("timing phase contains forbidden work/decomposition data")
    else:
        if any(record[field] is not None for field in ("repetition_index", "method_order", "method_order_position")):
            raise ValueError("non-timing phase contains timing identity")
        if record["timed"] is not False:
            raise ValueError("non-timing phase cannot be timed")
        if record["planner_wall_time_ns"] is not None or record["process_time_ns"] is not None:
            raise ValueError("primary timing fields populated outside timing phase")
    if phase in _STRUCTURAL_PHASES:
        if any(record[field] is None for field in _WORK_FIELDS):
            raise ValueError("structural phase requires work counters")
        if any(record[field] is not None for field in _DECOMPOSITION_FIELDS):
            raise ValueError("structural phase contains decomposition timing")
    elif phase == "decomposition":
        if any(record[field] is None for field in _DECOMPOSITION_FIELDS):
            raise ValueError("decomposition phase requires component times")
        if any(record[field] is not None for field in _WORK_FIELDS):
            raise ValueError("decomposition phase contains work counters")
    elif phase in _TIMING_PHASES or phase == "memory":
        if any(record[field] is not None for field in _DECOMPOSITION_FIELDS):
            raise ValueError("phase contains forbidden decomposition timing")
        if phase == "memory" and any(record[field] is not None for field in _WORK_FIELDS):
            raise ValueError("memory phase contains work counters")

    c_maintenance = (
        "c_synchronized_newly_known_count", "c_bound_decrement_count",
        "c_exact_cache_installation_count", "c_exact_cache_replacement_count",
    )
    b_peaks = ("b_peak_cached_scalar_entry_count",)
    c_peaks = (
        "c_peak_cached_candidate_count", "c_peak_bound_entry_count",
        "c_peak_cached_membership_count", "c_peak_inverse_key_count",
        "c_peak_inverse_membership_count", "c_peak_reported_known_count",
    )
    if phase in _STRUCTURAL_PHASES:
        if record["method"] == "C":
            if any(record[field] is None for field in c_maintenance + c_peaks):
                raise ValueError("structural C episode requires maintenance/storage counts")
        elif any(record[field] is not None for field in c_maintenance + c_peaks):
            raise ValueError("non-C structural episode contains C-only counts")
        if (record["method"] == "B") != (record[b_peaks[0]] is not None):
            raise ValueError("B structural peak must be populated only for B")
    elif phase != "memory" and any(
        record[field] is not None for field in c_maintenance + b_peaks + c_peaks
    ):
        raise ValueError("non-structural episode contains structural storage data")


def validate_bound_measurement(record: Mapping[str, Any]) -> None:
    _exact_fields(record, BOUND_MEASUREMENT_FIELDS, "bound measurement")
    if record["method"] not in {"B", "C"}:
        raise ValueError("bound method must be B or C")
    _coordinate(record["candidate"], "candidate")
    for field in ("upper_bound", "a_exact_gain", "absolute_slack"):
        _count(record[field], field)
    _number(record["normalized_slack"], "normalized_slack")
    if record["absolute_slack"] != record["upper_bound"] - record["a_exact_gain"]:
        raise ValueError("bound slack is inconsistent or negative")
    expected = record["absolute_slack"] / max(1, record["upper_bound"])
    if record["normalized_slack"] != expected:
        raise ValueError("normalized slack is inconsistent")
    if type(record["tight"]) is not bool or record["tight"] is not (
        record["absolute_slack"] == 0
    ):
        raise ValueError("tight flag is inconsistent")


def validate_snapshot_record(record: Mapping[str, Any]) -> None:
    _exact_fields(record, SNAPSHOT_FIELDS, "snapshot")
    _common(record)
    phase = record["phase"]
    for field in (
        "cycle_index", "unknown_count", "known_free_count",
        "known_occupied_count", "map_cell_count", "eligible_candidate_count",
        "selected_gain", "exact_gain_evaluation_count",
    ):
        _count(record[field], field)
    if record["unknown_count"] + record["known_free_count"] + record["known_occupied_count"] != record["map_cell_count"]:
        raise ValueError("belief counts do not sum to map_cell_count")
    _coordinate(record["robot_coordinate"], "robot_coordinate")
    _hash(record["belief_hash"], "belief_hash")
    if record["status"] not in STATUSES:
        raise ValueError("invalid status")
    terminal = record["status"] == "EXPLORATION_COMPLETE"
    _coordinate(record["selected_candidate"], "selected_candidate", nullable=True)
    _number(record["selected_distance"], "selected_distance", nullable=True)
    _number(record["selected_score"], "selected_score")
    if terminal != (record["selected_candidate"] is None):
        raise ValueError("status/candidate semantics are inconsistent")
    if terminal != (record["selected_distance"] is None):
        raise ValueError("status/distance semantics are inconsistent")
    _hash(record["selected_path_hash"], "selected_path_hash")
    for field in SNAPSHOT_FIELDS:
        if field.endswith("_count") or field.endswith("_time_ns"):
            if field not in {
                "cycle_index", "unknown_count", "known_free_count",
                "known_occupied_count", "map_cell_count",
                "eligible_candidate_count", "selected_gain",
                "exact_gain_evaluation_count",
            }:
                _count(record[field], field, nullable=True)
    if type(record["bound_measurements"]) is not list:
        raise ValueError("bound_measurements must be a list")
    for measurement in record["bound_measurements"]:
        validate_bound_measurement(measurement)
        if measurement["method"] != record["method"]:
            raise ValueError("bound measurement belongs to another method")
    if record["bound_measurements"] != sorted(
        record["bound_measurements"], key=lambda item: tuple(item["candidate"])
    ):
        raise ValueError("bound_measurements must be coordinate sorted")
    if record["method"] == "A" and record["bound_measurements"]:
        raise ValueError("A snapshot cannot contain bound measurements")
    for field in (
        "agreement_all", "sequence_prefix_agreement_all", "bound_valid_b",
        "bound_valid_c", "tie_certificate_valid_b", "tie_certificate_valid_c",
        "cache_index_invariant_valid_c", "correctness_valid",
    ):
        if type(record[field]) is not bool:
            raise ValueError(f"{field} must be boolean")
    if phase in _STRUCTURAL_PHASES:
        if any(record[field] is None for field in _WORK_FIELDS):
            raise ValueError("structural snapshot requires work counters")
        if any(record[field] is not None for field in ("planner_wall_time_ns", "process_time_ns") + _SNAPSHOT_DECOMPOSITION_FIELDS):
            raise ValueError("structural snapshot contains timing data")
    elif phase in _TIMING_PHASES:
        if any(record[field] is not None for field in _WORK_FIELDS + _SNAPSHOT_DECOMPOSITION_FIELDS):
            raise ValueError("timing snapshot contains instrumentation data")
        _count(record["planner_wall_time_ns"], "planner_wall_time_ns")
        _count(record["process_time_ns"], "process_time_ns")
    elif phase == "decomposition":
        if any(record[field] is None for field in _SNAPSHOT_DECOMPOSITION_FIELDS):
            raise ValueError("decomposition snapshot requires component times")
        if any(record[field] is not None for field in _WORK_FIELDS + ("planner_wall_time_ns", "process_time_ns")):
            raise ValueError("decomposition snapshot contains forbidden fields")
    elif phase == "memory":
        if any(record[field] is not None for field in _WORK_FIELDS + ("planner_wall_time_ns", "process_time_ns") + _SNAPSHOT_DECOMPOSITION_FIELDS):
            raise ValueError("memory snapshot contains timing/work data")
    if phase in _TIMING_PHASES:
        repetition = record["repetition_index"]
        if phase == "timing_warmup" and repetition != 0:
            raise ValueError("warm-up snapshot repetition must be zero")
        if phase == "primary_timing" and (
            type(repetition) is not int or not 1 <= repetition <= 6
        ):
            raise ValueError("timed snapshot repetition must be 1..6")
    elif record["repetition_index"] is not None:
        raise ValueError("non-timing snapshot contains repetition index")

    c_maintenance = (
        "c_synchronized_newly_known_count", "c_bound_decrement_count",
        "c_exact_cache_installation_count", "c_exact_cache_replacement_count",
    )
    b_storage = ("b_cached_scalar_entry_count",)
    c_storage = (
        "c_cached_candidate_count", "c_bound_entry_count",
        "c_cached_membership_count", "c_inverse_key_count",
        "c_inverse_membership_count", "c_reported_known_count",
    )
    storage_phase = phase in _STRUCTURAL_PHASES or phase == "memory"
    if phase in _STRUCTURAL_PHASES and record["method"] == "C":
        if any(record[field] is None for field in c_maintenance):
            raise ValueError("structural C snapshot requires maintenance counts")
    elif any(record[field] is not None for field in c_maintenance):
        raise ValueError("snapshot contains unavailable C maintenance counts")
    if storage_phase and record["method"] == "B":
        if record[b_storage[0]] is None:
            raise ValueError("B snapshot requires its storage count")
    elif any(record[field] is not None for field in b_storage):
        raise ValueError("snapshot contains unavailable B storage count")
    if storage_phase and record["method"] == "C":
        if any(record[field] is None for field in c_storage):
            raise ValueError("C snapshot requires its storage counts")
        if record["c_cached_membership_count"] != record["c_inverse_membership_count"]:
            raise ValueError("C cached/inverse membership counts differ")
    elif any(record[field] is not None for field in c_storage):
        raise ValueError("snapshot contains unavailable C storage counts")


def validate_timing_record(record: Mapping[str, Any]) -> None:
    _exact_fields(record, TIMING_FIELDS, "timing repetition")
    _common(record)
    phase = "primary_timing" if record["timed"] else "timing_warmup"
    _validate_timing_identity(record, phase=phase)
    if record["warmup_discarded"] is not (not record["timed"]):
        raise ValueError("warmup_discarded is inconsistent")
    for field in (
        "episode_planner_wall_time_ns", "episode_process_time_ns",
        "planning_snapshot_count",
    ):
        _count(record[field], field)
    _hash(record["target_stop_sequence_hash"], "target_stop_sequence_hash")
    if type(record["correctness_valid"]) is not bool:
        raise ValueError("correctness_valid must be boolean")


def validate_memory_record(record: Mapping[str, Any]) -> None:
    _exact_fields(record, MEMORY_FIELDS, "memory")
    _common(record)
    if record["measurement_kind"] != "python_tracemalloc_separate_non_timed_pass":
        raise ValueError("invalid memory measurement kind")
    for field in MEMORY_FIELDS:
        if field.endswith("_count") or field.endswith("_bytes"):
            _count(record[field], field, nullable=True)
    _count(
        record["tracemalloc_current_bytes_at_stop"],
        "tracemalloc_current_bytes_at_stop",
    )
    _hash(record["target_stop_sequence_hash"], "target_stop_sequence_hash")
    if type(record["correctness_valid"]) is not bool:
        raise ValueError("correctness_valid must be boolean")
    b_fields = ("b_peak_cached_scalar_entry_count",)
    c_fields = (
        "c_peak_cached_candidate_count", "c_peak_bound_entry_count",
        "c_peak_cached_membership_count", "c_peak_inverse_key_count",
        "c_peak_inverse_membership_count", "c_peak_reported_known_count",
    )
    if record["method"] == "A" and any(
        record[field] is not None for field in b_fields + c_fields
    ):
        raise ValueError("A memory record contains B/C storage counts")
    if record["method"] == "B":
        if record[b_fields[0]] is None or any(record[field] is not None for field in c_fields):
            raise ValueError("B memory storage fields are inconsistent")
    if record["method"] == "C":
        if record[b_fields[0]] is not None or any(record[field] is None for field in c_fields):
            raise ValueError("C memory storage fields are inconsistent")


def validate_manifest(manifest: Mapping[str, Any]) -> None:
    _exact_fields(manifest, MANIFEST_FIELDS, "manifest")
    if manifest["experiment_name"] != EXPERIMENT_NAME:
        raise ValueError("unexpected experiment name")
    if manifest["experiment_version"] != EXPERIMENT_VERSION or manifest["runner_version"] != EXPERIMENT_VERSION:
        raise ValueError("unexpected runner version")
    if manifest["dataset_version"] != DATASET_VERSION:
        raise ValueError("unexpected dataset version")
    if manifest["status"] not in {"RUNNING", "PASS", "FAILED"}:
        raise ValueError("invalid manifest status")
    if manifest["timing_orders"] != [list(order) for order in TIMING_ORDERS]:
        raise ValueError("timing orders differ from preregistration")
    if manifest["warmup_repetitions"] != 1 or manifest["timed_repetitions"] != 6:
        raise ValueError("timing repetition counts differ from preregistration")
    if manifest["bootstrap_resamples"] != 10_000 or manifest["bootstrap_seed"] != 20260916:
        raise ValueError("bootstrap configuration differs from preregistration")
    canonical_json_text(manifest)


def serialize_record(record: Mapping[str, Any], kind: str) -> str:
    validators: dict[str, Callable[[Mapping[str, Any]], None]] = {
        "episode": validate_episode_record,
        "snapshot": validate_snapshot_record,
        "timing": validate_timing_record,
        "memory": validate_memory_record,
    }
    if kind not in validators:
        raise ValueError("unknown record kind")
    validators[kind](record)
    return canonical_json_text(record)


def _safe_identifier(value: str, name: str) -> None:
    if not isinstance(value, str) or not _SAFE_ID_PATTERN.fullmatch(value):
        raise ValueError(f"{name} contains unsafe path characters")


def _write_exclusive(path: Path, text: str) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


class Experiment1InvocationWriter:
    """Write only validated raw records and derive the sole summary."""

    _STREAMS = {
        "episode": "episodes.jsonl",
        "snapshot": "snapshots.jsonl",
        "timing": "timing_repetitions.jsonl",
        "memory": "memory.jsonl",
    }

    def __init__(
        self,
        output_root: str | Path,
        invocation_id: str,
        manifest: Mapping[str, Any],
    ) -> None:
        _safe_identifier(invocation_id, "invocation_id")
        payload = dict(manifest)
        if payload.get("invocation_id") != invocation_id:
            raise ValueError("manifest invocation ID mismatch")
        validate_manifest(payload)
        if payload["status"] != "RUNNING":
            raise ValueError("new invocation manifest must start RUNNING")
        self.invocation_id = invocation_id
        self.directory = Path(output_root) / "runs" / invocation_id
        self.directory.mkdir(parents=True, exist_ok=False)
        self._manifest = payload
        _write_exclusive(self.directory / "manifest.json", canonical_json_text(payload))
        for filename in self._STREAMS.values():
            _write_exclusive(self.directory / filename, "")
        self._finalized = False

    def append(self, kind: str, record: Mapping[str, Any]) -> None:
        if self._finalized:
            raise RuntimeError("cannot append to finalized invocation")
        if kind not in self._STREAMS:
            raise ValueError("unknown record kind")
        if record.get("invocation_id") != self.invocation_id:
            raise ValueError("record invocation ID mismatch")
        text = serialize_record(record, kind)
        with (self.directory / self._STREAMS[kind]).open(
            "a", encoding="utf-8", newline="\n"
        ) as handle:
            handle.write(text)

    def _read(self, kind: str) -> list[dict[str, Any]]:
        records = []
        with (self.directory / self._STREAMS[kind]).open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    records.append(json.loads(line))
        return records

    def finalize(
        self,
        status: str,
        *,
        failure_run_ids: list[str] | None = None,
        primary_correctness_failed: bool = False,
    ) -> dict[str, Any]:
        if self._finalized:
            raise RuntimeError("invocation already finalized")
        if status not in {"PASS", "FAILED"}:
            raise ValueError("final status must be PASS or FAILED")
        failure_run_ids = list(failure_run_ids or [])
        for value in failure_run_ids:
            _safe_identifier(value, "failure_run_id")
        episode_records = self._read("episode")
        snapshot_records = self._read("snapshot")
        timing_records = self._read("timing")
        memory_records = self._read("memory")
        summary = build_summary(
            invocation_id=self.invocation_id,
            episode_records=episode_records,
            snapshot_records=snapshot_records,
            timing_records=timing_records,
            memory_records=memory_records,
            invocation_complete=status == "PASS",
            invocation_status=status,
            primary_correctness_failed=primary_correctness_failed,
        )
        if tuple(summary) != SUMMARY_FIELDS:
            raise RuntimeError("derived summary field order differs from frozen schema")
        _write_exclusive(self.directory / "summary.json", canonical_json_text(summary))
        self._manifest["status"] = status
        self._manifest["completed_at_utc"] = utc_now_text()
        self._manifest["failure_run_ids"] = failure_run_ids
        validate_manifest(self._manifest)
        temporary = self.directory / ".manifest.json.tmp"
        _write_exclusive(temporary, canonical_json_text(self._manifest))
        temporary.replace(self.directory / "manifest.json")
        self._finalized = True
        return summary


__all__ = [
    "BOUND_MEASUREMENT_FIELDS", "DATASET_VERSION", "EPISODE_FIELDS",
    "EXPERIMENT_NAME", "EXPERIMENT_VERSION", "Experiment1InvocationWriter",
    "MANIFEST_FIELDS", "MEMORY_FIELDS", "METHODS", "PHASES",
    "SNAPSHOT_FIELDS", "STATUSES", "SUMMARY_FIELDS", "TIMING_FIELDS",
    "TIMING_ORDERS", "canonical_json_text", "serialize_record",
    "utc_now_text", "validate_bound_measurement", "validate_episode_record",
    "validate_manifest", "validate_memory_record", "validate_snapshot_record",
    "validate_timing_record",
]
