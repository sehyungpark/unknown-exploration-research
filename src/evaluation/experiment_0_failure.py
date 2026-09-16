"""Immutable, deterministic failure artifacts for Experiment 0."""

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

from .experiment_0_logging import canonical_json_text, write_text_exclusive


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
    dataset_type: str,
    map_id: str,
    cycle_index: int,
    classification: str,
) -> str:
    material = (
        f"{invocation_id}\n{dataset_type}\n{map_id}\n"
        f"{cycle_index}\n{classification}\n"
    )
    digest = sha256(material.encode("utf-8")).hexdigest()[:16]
    return f"failure-{map_id}-{cycle_index:04d}-{digest}"


def _failure_text(
    *,
    metadata: Mapping[str, Any],
    description: FailureDescription,
) -> str:
    reproduction_id = f"reproduce-{metadata['failure_run_id']}"
    command = (
        "python -m src.evaluation.experiment_0_runner "
        f"--execute-preregistered --only-map {metadata['map_id']} "
        f"--invocation-id {reproduction_id}"
    )
    robot = metadata["robot_coordinate"]
    return "\n".join(
        (
            f"classification: {description.classification}",
            f"map_id: {metadata['map_id']}",
            f"cycle_index: {metadata['cycle_index']}",
            f"robot_coordinate: {robot}",
            f"first_failure: {description.first_failure}",
            f"expected: {description.expected!r}",
            f"observed: {description.observed!r}",
            f"exception_class: {description.exception_class or 'none'}",
            f"exception_message: {description.exception_message or 'none'}",
            f"reproduction_command: {command}",
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
    """Create exactly six evidence files and never overwrite an existing artifact."""

    target = Path(output_root) / "failures" / failure_run_id
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", failure_run_id):
        raise ValueError("failure_run_id contains unsafe path characters")
    ground_truth_text = canonical_ground_truth_text(ground_truth)
    belief_text = canonical_belief_text(belief_before)
    if metadata.get("map_hash") != ground_truth_hash(ground_truth):
        raise ValueError("failure metadata map_hash does not match canonical ground truth")
    if metadata.get("belief_hash") != belief_hash(belief_before):
        raise ValueError("failure metadata belief_hash does not match canonical belief")
    if metadata.get("failure_run_id") != failure_run_id:
        raise ValueError("failure metadata run ID mismatch")
    if metadata.get("failure_classification") != description.classification:
        raise ValueError("failure metadata classification mismatch")

    ordered_candidates = sorted(
        (dict(record) for record in candidates),
        key=lambda record: tuple(record["candidate"]),
    )
    metadata_text = canonical_json_text(dict(metadata))
    candidates_text = canonical_json_text(ordered_candidates)
    algorithm_state_text = canonical_json_text(dict(algorithm_state))
    failure_text = _failure_text(metadata=metadata, description=description)

    target.mkdir(parents=True, exist_ok=False)
    write_text_exclusive(target / "metadata.json", metadata_text)
    write_text_exclusive(target / "ground_truth.txt", ground_truth_text)
    write_text_exclusive(target / "belief_before.txt", belief_text)
    write_text_exclusive(target / "candidates.json", candidates_text)
    write_text_exclusive(target / "algorithm_state.json", algorithm_state_text)
    write_text_exclusive(target / "failure.txt", failure_text)
    actual = frozenset(path.name for path in target.iterdir())
    if actual != FAILURE_ARTIFACT_FILES:
        raise RuntimeError(f"failure artifact layout mismatch: {sorted(actual)!r}")
    return target


__all__ = [
    "FAILURE_ARTIFACT_FILES",
    "FailureDescription",
    "deterministic_failure_run_id",
    "write_failure_artifact",
]
