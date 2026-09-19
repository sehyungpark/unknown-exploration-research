"""Immutable six-file failure evidence for Experiment 2."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from src.environment import GroundTruthGrid
from src.mapping import BeliefGrid
from src.utils import (
    belief_hash,
    canonical_belief_text,
    canonical_ground_truth_text,
    ground_truth_hash,
)

from .experiment_2_logging import canonical_json_text


FAILURE_ARTIFACT_FILES = frozenset(
    {
        "metadata.json",
        "ground_truth.txt",
        "belief_before.txt",
        "candidates.json",
        "algorithm_state.json",
        "failure.txt",
    }
)

FAILURE_CLASSIFICATIONS = (
    "target_mismatch",
    "sequence_or_termination_mismatch",
    "selected_value_or_path_mismatch",
    "candidate_domain_or_distance_mismatch",
    "b_bound_violation",
    "c_bound_violation",
    "b_tie_certificate_violation",
    "c_tie_certificate_violation",
    "c_cache_index_invariant_failure",
    "cstar_bound_violation",
    "cstar_audit_failure",
    "supported_change_aware_gain_bound_violation",
    "unsupported_lifecycle_or_configuration",
    "cycle_limit_exhaustion",
    "malformed_measurement_record",
    "instrumentation_mismatch",
    "timing_protocol_violation",
    "unexpected_exception",
)

REQUIRED_METADATA_FIELDS = frozenset(
    {
        "experiment_version", "dataset_version", "invocation_id",
        "failure_run_id", "phase", "map_id", "method", "method_order",
        "method_order_position", "repetition_index", "sensor_range",
        "cycle_index", "robot_coordinate", "map_hash", "belief_hash",
        "repository_revision", "failure_classification",
    }
)


@dataclass(frozen=True, slots=True)
class FailureDescription:
    classification: str
    first_failure: str
    expected: Any = None
    observed: Any = None
    exception_class: str | None = None
    exception_message: str | None = None


def deterministic_failure_run_id(
    *,
    invocation_id: str,
    phase: str,
    map_id: str,
    method: str | None,
    repetition_index: int | None,
    cycle_index: int,
    classification: str,
) -> str:
    material = "\n".join(
        (
            invocation_id,
            phase,
            map_id,
            method or "shared",
            "none" if repetition_index is None else str(repetition_index),
            str(cycle_index),
            classification,
            "",
        )
    )
    digest = sha256(material.encode("utf-8")).hexdigest()[:20]
    safe_map = re.sub(r"[^A-Za-z0-9._-]", "-", map_id)
    safe_method = method or "shared"
    repetition = "none" if repetition_index is None else f"{repetition_index:02d}"
    return (
        f"failure-{phase}-{safe_map}-{safe_method}-r{repetition}-"
        f"c{cycle_index:04d}-{digest}"
    )


def _write_exclusive(path: Path, text: str) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _failure_text(
    metadata: Mapping[str, Any], description: FailureDescription
) -> str:
    reproduction = (
        "python -m src.evaluation.experiment_2_runner --execute-preregistered "
        f"--invocation-id reproduce-{metadata['failure_run_id']}"
    )
    return "\n".join(
        (
            f"classification: {description.classification}",
            f"phase: {metadata['phase']}",
            f"map_id: {metadata['map_id']}",
            f"method: {metadata['method'] or 'shared'}",
            f"repetition_index: {metadata['repetition_index']}",
            f"cycle_index: {metadata['cycle_index']}",
            f"first_failure: {description.first_failure}",
            f"expected: {description.expected!r}",
            f"observed: {description.observed!r}",
            f"exception_class: {description.exception_class or 'none'}",
            f"exception_message: {description.exception_message or 'none'}",
            f"reproduction_command: {reproduction}",
            "",
        )
    )


def write_failure_artifact(
    *,
    output_root: str | Path,
    failure_run_id: str,
    metadata: Mapping[str, Any],
    ground_truth: GroundTruthGrid,
    belief_before: BeliefGrid,
    candidates: Sequence[Mapping[str, Any]],
    algorithm_state: Mapping[str, Any],
    description: FailureDescription,
) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", failure_run_id):
        raise ValueError("failure_run_id contains unsafe path characters")
    if not REQUIRED_METADATA_FIELDS.issubset(metadata):
        raise ValueError("failure metadata is missing required context")
    if description.classification not in FAILURE_CLASSIFICATIONS:
        raise ValueError("unknown Experiment 2 failure classification")
    if metadata["failure_run_id"] != failure_run_id:
        raise ValueError("failure metadata run ID mismatch")
    if metadata["failure_classification"] != description.classification:
        raise ValueError("failure classification mismatch")
    if metadata["map_hash"] != ground_truth_hash(ground_truth):
        raise ValueError("failure map hash mismatch")
    if metadata["belief_hash"] != belief_hash(belief_before):
        raise ValueError("failure belief hash mismatch")

    ordered_candidates = sorted(
        (dict(record) for record in candidates),
        key=lambda record: tuple(record["candidate"]),
    )
    texts = {
        "metadata.json": canonical_json_text(dict(metadata)),
        "ground_truth.txt": canonical_ground_truth_text(ground_truth),
        "belief_before.txt": canonical_belief_text(belief_before),
        "candidates.json": canonical_json_text(ordered_candidates),
        "algorithm_state.json": canonical_json_text(dict(algorithm_state)),
        "failure.txt": _failure_text(metadata, description),
    }
    target = Path(output_root) / "failures" / failure_run_id
    target.mkdir(parents=True, exist_ok=False)
    for filename, text in texts.items():
        _write_exclusive(target / filename, text)
    actual = frozenset(path.name for path in target.iterdir())
    if actual != FAILURE_ARTIFACT_FILES:
        raise RuntimeError("failure artifact layout differs from frozen schema")
    return target


__all__ = [
    "FAILURE_ARTIFACT_FILES",
    "FAILURE_CLASSIFICATIONS",
    "FailureDescription",
    "REQUIRED_METADATA_FIELDS",
    "deterministic_failure_run_id",
    "write_failure_artifact",
]
