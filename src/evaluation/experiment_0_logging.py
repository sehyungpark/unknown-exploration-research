"""Canonical cycle records and non-overwriting Experiment 0 run logs."""

from __future__ import annotations

import json
import math
from pathlib import Path
import re
from typing import Any, Mapping


EXPERIMENT_VERSION = "experiment-0-runner-v1"

CYCLE_RECORD_FIELDS = (
    "experiment_version",
    "dataset_type",
    "map_id",
    "map_seed",
    "map_hash",
    "cycle_index",
    "robot_coordinate",
    "belief_hash",
    "unknown_count",
    "known_free_count",
    "known_occupied_count",
    "eligible_candidate_count",
    "a_status",
    "a_selected_candidate",
    "a_selected_gain",
    "a_selected_distance",
    "a_selected_score",
    "a_exact_gain_evaluation_count",
    "b_status",
    "b_selected_candidate",
    "b_selected_gain",
    "b_selected_distance",
    "b_selected_score",
    "b_exact_gain_evaluation_count",
    "b_bound_only_candidate_count",
    "b_certificate_reason",
    "c_status",
    "c_selected_candidate",
    "c_selected_gain",
    "c_selected_distance",
    "c_selected_score",
    "c_exact_gain_evaluation_count",
    "c_bound_only_candidate_count",
    "c_bound_decrement_count",
    "c_cached_membership_count",
    "c_inverse_membership_count",
    "c_certificate_reason",
    "agreement_a_b",
    "agreement_a_c",
    "agreement_b_c",
    "agreement_all",
    "sequence_prefix_agreement_all",
    "bound_valid_b",
    "bound_valid_c",
    "tie_certificate_valid_b",
    "tie_certificate_valid_c",
    "cache_index_invariant_valid_c",
)

_STATUS_VALUES = {"SELECTED", "EXPLORATION_COMPLETE"}
_HASH_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
_SAFE_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")


def canonical_json_text(value: Any) -> str:
    """Return deterministic compact JSON with one final LF and no non-finite values."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ) + "\n"


def _is_nonnegative_int(value: object) -> bool:
    return type(value) is int and value >= 0


def _validate_coordinate(value: object, *, nullable: bool, field: str) -> None:
    if value is None and nullable:
        return
    if not (
        type(value) is list
        and len(value) == 2
        and all(_is_nonnegative_int(component) for component in value)
    ):
        raise ValueError(f"{field} must be a nonnegative [row,col] coordinate")


def _validate_number(value: object, *, nullable: bool, field: str) -> None:
    if value is None and nullable:
        return
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{field} must be a finite number")


def _validate_algorithm_fields(record: Mapping[str, Any], prefix: str) -> None:
    status = record[f"{prefix}_status"]
    if status not in _STATUS_VALUES:
        raise ValueError(f"{prefix}_status is invalid")
    terminal = status == "EXPLORATION_COMPLETE"
    _validate_coordinate(
        record[f"{prefix}_selected_candidate"],
        nullable=True,
        field=f"{prefix}_selected_candidate",
    )
    if terminal != (record[f"{prefix}_selected_candidate"] is None):
        raise ValueError(f"{prefix} status/candidate semantics are inconsistent")
    if not _is_nonnegative_int(record[f"{prefix}_selected_gain"]):
        raise ValueError(f"{prefix}_selected_gain must be a nonnegative integer")
    _validate_number(
        record[f"{prefix}_selected_distance"],
        nullable=True,
        field=f"{prefix}_selected_distance",
    )
    if terminal != (record[f"{prefix}_selected_distance"] is None):
        raise ValueError(f"{prefix} status/distance semantics are inconsistent")
    _validate_number(
        record[f"{prefix}_selected_score"],
        nullable=False,
        field=f"{prefix}_selected_score",
    )
    if terminal and (
        record[f"{prefix}_selected_gain"] != 0
        or record[f"{prefix}_selected_score"] != 0.0
    ):
        raise ValueError(f"{prefix} terminal gain and score must be zero")
    if not _is_nonnegative_int(record[f"{prefix}_exact_gain_evaluation_count"]):
        raise ValueError(
            f"{prefix}_exact_gain_evaluation_count must be a nonnegative integer"
        )


def _status_target(record: Mapping[str, Any], prefix: str) -> tuple[object, object]:
    return record[f"{prefix}_status"], record[f"{prefix}_selected_candidate"]


def validate_cycle_record(
    record: Mapping[str, Any],
    *,
    map_cell_count: int,
) -> None:
    """Validate the exact frozen field set and every locally checkable invariant."""

    if set(record) != set(CYCLE_RECORD_FIELDS) or len(record) != len(CYCLE_RECORD_FIELDS):
        missing = [field for field in CYCLE_RECORD_FIELDS if field not in record]
        extra = [field for field in record if field not in CYCLE_RECORD_FIELDS]
        raise ValueError(
            "cycle record field/order mismatch: "
            f"missing={missing!r}, extra={extra!r}"
        )
    if record["experiment_version"] != EXPERIMENT_VERSION:
        raise ValueError("unexpected experiment version")
    if record["dataset_type"] not in {"fixture", "random"}:
        raise ValueError("dataset_type must be fixture or random")
    if not isinstance(record["map_id"], str) or not record["map_id"]:
        raise ValueError("map_id must be a nonempty string")
    map_seed = record["map_seed"]
    if record["dataset_type"] == "fixture":
        if map_seed is not None:
            raise ValueError("fixture map_seed must be null")
    elif type(map_seed) is not int or map_seed < 0:
        raise ValueError("random map_seed must be a nonnegative integer")
    for field in ("map_hash", "belief_hash"):
        if not isinstance(record[field], str) or not _HASH_PATTERN.fullmatch(record[field]):
            raise ValueError(f"{field} must be a lowercase SHA-256 hex digest")
    if not _is_nonnegative_int(record["cycle_index"]):
        raise ValueError("cycle_index must be a nonnegative integer")
    _validate_coordinate(record["robot_coordinate"], nullable=False, field="robot_coordinate")

    count_fields = (
        "unknown_count",
        "known_free_count",
        "known_occupied_count",
        "eligible_candidate_count",
        "b_bound_only_candidate_count",
        "c_bound_only_candidate_count",
        "c_bound_decrement_count",
        "c_cached_membership_count",
        "c_inverse_membership_count",
    )
    for field in count_fields:
        if not _is_nonnegative_int(record[field]):
            raise ValueError(f"{field} must be a nonnegative integer")
    if type(map_cell_count) is not int or map_cell_count <= 0:
        raise ValueError("map_cell_count must be a positive integer")
    if (
        record["unknown_count"]
        + record["known_free_count"]
        + record["known_occupied_count"]
        != map_cell_count
    ):
        raise ValueError("belief counts do not sum to the map cell count")

    for prefix in ("a", "b", "c"):
        _validate_algorithm_fields(record, prefix)
    for prefix in ("b", "c"):
        if not isinstance(record[f"{prefix}_certificate_reason"], str) or not record[
            f"{prefix}_certificate_reason"
        ]:
            raise ValueError(f"{prefix}_certificate_reason must be nonempty")
        if (
            record[f"{prefix}_exact_gain_evaluation_count"]
            + record[f"{prefix}_bound_only_candidate_count"]
            != record["eligible_candidate_count"]
        ):
            raise ValueError(f"{prefix} exact/bound-only counts are inconsistent")
    if record["a_exact_gain_evaluation_count"] != record["eligible_candidate_count"]:
        raise ValueError("Algorithm A must evaluate every eligible candidate")
    flag_fields = CYCLE_RECORD_FIELDS[CYCLE_RECORD_FIELDS.index("agreement_a_b") :]
    for field in flag_fields:
        if type(record[field]) is not bool:
            raise ValueError(f"{field} must be boolean")
    agreement_ab = _status_target(record, "a") == _status_target(record, "b")
    agreement_ac = _status_target(record, "a") == _status_target(record, "c")
    agreement_bc = _status_target(record, "b") == _status_target(record, "c")
    if record["agreement_a_b"] is not agreement_ab:
        raise ValueError("agreement_a_b is inconsistent with status/target")
    if record["agreement_a_c"] is not agreement_ac:
        raise ValueError("agreement_a_c is inconsistent with status/target")
    if record["agreement_b_c"] is not agreement_bc:
        raise ValueError("agreement_b_c is inconsistent with status/target")
    if record["agreement_all"] is not (agreement_ab and agreement_ac and agreement_bc):
        raise ValueError("agreement_all is inconsistent with pairwise flags")
    if (
        record["c_cached_membership_count"]
        != record["c_inverse_membership_count"]
        and record["cache_index_invariant_valid_c"]
    ):
        raise ValueError(
            "cache_index_invariant_valid_c cannot be true when membership totals differ"
        )

    # Force JSON conversion now so NaN/Infinity and unsupported objects fail before I/O.
    canonical_json_text(record)


def serialize_cycle_record(record: Mapping[str, Any], *, map_cell_count: int) -> str:
    validate_cycle_record(record, map_cell_count=map_cell_count)
    return canonical_json_text(record)


def _validate_identifier(value: str, *, name: str) -> None:
    if not isinstance(value, str) or not _SAFE_ID_PATTERN.fullmatch(value):
        raise ValueError(f"{name} must match {_SAFE_ID_PATTERN.pattern!r}")


def write_text_exclusive(path: Path, text: str) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


class Experiment0InvocationWriter:
    """Append validated JSONL records inside one immutable invocation directory."""

    def __init__(
        self,
        output_root: str | Path,
        invocation_id: str,
        manifest: Mapping[str, Any],
    ) -> None:
        _validate_identifier(invocation_id, name="invocation_id")
        self.invocation_id = invocation_id
        self.directory = Path(output_root) / "runs" / invocation_id
        self.directory.mkdir(parents=True, exist_ok=False)
        self.cycles_path = self.directory / "cycles.jsonl"
        write_text_exclusive(self.cycles_path, "")
        manifest_payload = dict(manifest)
        manifest_payload["experiment_version"] = EXPERIMENT_VERSION
        manifest_payload["invocation_id"] = invocation_id
        write_text_exclusive(
            self.directory / "manifest.json",
            canonical_json_text(manifest_payload),
        )
        self._finalized = False

    def append_cycle(self, record: Mapping[str, Any], *, map_cell_count: int) -> None:
        if self._finalized:
            raise RuntimeError("cannot append to a finalized invocation")
        text = serialize_cycle_record(record, map_cell_count=map_cell_count)
        with self.cycles_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(text)

    def _read_cycles(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        with self.cycles_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    records.append(json.loads(line))
        return records

    def finalize(
        self,
        status: str,
        *,
        failure_run_id: str | None = None,
    ) -> dict[str, Any]:
        if self._finalized:
            raise RuntimeError("invocation is already finalized")
        if status not in {"PASSED", "FAILED"}:
            raise ValueError("invocation status must be PASSED or FAILED")
        records = self._read_cycles()
        summary = {
            "experiment_version": EXPERIMENT_VERSION,
            "invocation_id": self.invocation_id,
            "status": status,
            "failure_run_id": failure_run_id,
            "planning_snapshot_count": len(records),
            "map_count_with_records": len({record["map_id"] for record in records}),
            "selected_snapshot_count": sum(
                record["a_status"] == "SELECTED" for record in records
            ),
            "terminal_snapshot_count": sum(
                record["a_status"] == "EXPLORATION_COMPLETE" for record in records
            ),
            "all_records_agree": all(record["agreement_all"] for record in records),
            "all_sequence_prefixes_agree": all(
                record["sequence_prefix_agreement_all"] for record in records
            ),
            "a_exact_gain_evaluation_count": sum(
                record["a_exact_gain_evaluation_count"] for record in records
            ),
            "b_exact_gain_evaluation_count": sum(
                record["b_exact_gain_evaluation_count"] for record in records
            ),
            "c_exact_gain_evaluation_count": sum(
                record["c_exact_gain_evaluation_count"] for record in records
            ),
        }
        write_text_exclusive(
            self.directory / "summary.json",
            canonical_json_text(summary),
        )
        self._finalized = True
        return summary


__all__ = [
    "CYCLE_RECORD_FIELDS",
    "EXPERIMENT_VERSION",
    "Experiment0InvocationWriter",
    "canonical_json_text",
    "serialize_cycle_record",
    "validate_cycle_record",
    "write_text_exclusive",
]
