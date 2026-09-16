"""Structural-only frozen random-map construction for Experiment 1.

This module deliberately performs no sensing, planning, timing, memory tracing,
or algorithm execution.  It reuses only Experiment 0's deterministic Bernoulli
map and structural component/start utilities.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, replace
import json
from pathlib import Path
import random
from typing import Any, Mapping, Sequence

from src.environment import GroundTruthGrid
from src.utils import Coord, ground_truth_hash

from .random_dataset import (
    GENERATOR_VERSION,
    MIN_LARGEST_COMPONENT_FRACTION,
    generate_ground_truth,
    random_cycle_limit,
    select_start,
)

EXPERIMENT_NAME = "Experiment 1 — Efficiency and Scaling Evaluation"
DATASET_VERSION = "experiment-1-efficiency-v1"
MASTER_SEED = 20260916
SIZES = (20, 30, 40)
DENSITIES: tuple[tuple[str, float], ...] = (
    ("sparse", 0.10),
    ("medium", 0.20),
    ("dense", 0.30),
)
ACCEPTED_PER_STRATUM = 3
SENSOR_RANGE = 8.0


@dataclass(frozen=True, slots=True)
class AcceptedEfficiencyMap:
    dataset_index: int
    candidate_index: int
    dataset_id: str
    stratum_index: int
    accepted_index_in_stratum: int
    size: int
    density_label: str
    p: float
    seed: int
    start: Coord
    largest_free_component_size: int
    largest_free_component_fraction: float
    cycle_limit: int
    map_hash: str
    ground_truth: GroundTruthGrid


@dataclass(frozen=True, slots=True)
class RejectedEfficiencyMap:
    candidate_index: int
    stratum_index: int
    size: int
    density_label: str
    p: float
    seed: int
    reason: str
    start: Coord | None
    largest_free_component_size: int
    largest_free_component_fraction: float
    cycle_limit: int
    map_hash: str


@dataclass(frozen=True, slots=True)
class Experiment1Dataset:
    accepted: tuple[AcceptedEfficiencyMap, ...]
    rejected: tuple[RejectedEfficiencyMap, ...]


def dataset_id(size: int, density_label: str, accepted_index: int) -> str:
    """Return the frozen stable identity for one accepted stratum member."""

    return f"efficiency-{size}x{size}-{density_label}-{accepted_index:02d}"


def evaluate_structural_candidate(
    *, candidate_index: int, stratum_index: int, size: int,
    density_label: str, p: float, seed: int,
) -> AcceptedEfficiencyMap | RejectedEfficiencyMap:
    """Apply only the preregistered structural acceptance checks."""

    grid = generate_ground_truth(size, p, seed)
    start, component_size, _ = select_start(grid)
    total_cells = grid.height * grid.width
    fraction = component_size / total_cells
    cycle_limit = random_cycle_limit(component_size)
    digest = ground_truth_hash(grid)

    reason: str | None = None
    if component_size == 0:
        reason = "no_free_cell"
    elif start is None:
        reason = "no_start_cell"
    elif fraction < MIN_LARGEST_COMPONENT_FRACTION:
        reason = "largest_component_fraction_below_0.35"

    if reason is not None:
        return RejectedEfficiencyMap(
            candidate_index=candidate_index,
            stratum_index=stratum_index,
            size=size,
            density_label=density_label,
            p=p,
            seed=seed,
            reason=reason,
            start=start,
            largest_free_component_size=component_size,
            largest_free_component_fraction=fraction,
            cycle_limit=cycle_limit,
            map_hash=digest,
        )

    assert start is not None
    return AcceptedEfficiencyMap(
        dataset_index=-1,
        candidate_index=candidate_index,
        dataset_id="",
        stratum_index=stratum_index,
        accepted_index_in_stratum=-1,
        size=size,
        density_label=density_label,
        p=p,
        seed=seed,
        start=start,
        largest_free_component_size=component_size,
        largest_free_component_fraction=fraction,
        cycle_limit=cycle_limit,
        map_hash=digest,
        ground_truth=grid,
    )


def materialize_dataset(master_seed: int = MASTER_SEED) -> Experiment1Dataset:
    """Produce 27 accepted maps while retaining every rejected seed attempt."""

    master_rng = random.Random(master_seed)
    accepted: list[AcceptedEfficiencyMap] = []
    rejected: list[RejectedEfficiencyMap] = []
    candidate_index = 0

    for size in SIZES:
        for stratum_index, (density_label, p) in enumerate(DENSITIES):
            accepted_in_stratum = 0
            while accepted_in_stratum < ACCEPTED_PER_STRATUM:
                seed = master_rng.getrandbits(63)
                candidate = evaluate_structural_candidate(
                    candidate_index=candidate_index,
                    stratum_index=stratum_index,
                    size=size,
                    density_label=density_label,
                    p=p,
                    seed=seed,
                )
                candidate_index += 1
                if isinstance(candidate, RejectedEfficiencyMap):
                    rejected.append(candidate)
                    continue
                accepted_in_stratum += 1
                accepted.append(
                    replace(
                        candidate,
                        dataset_index=len(accepted),
                        dataset_id=dataset_id(
                            size, density_label, accepted_in_stratum
                        ),
                        accepted_index_in_stratum=accepted_in_stratum,
                    )
                )

    return Experiment1Dataset(tuple(accepted), tuple(rejected))


def _accepted_record(item: AcceptedEfficiencyMap) -> dict[str, Any]:
    return {
        "dataset_index": item.dataset_index,
        "candidate_index": item.candidate_index,
        "dataset_id": item.dataset_id,
        "stratum_index": item.stratum_index,
        "accepted_index_in_stratum": item.accepted_index_in_stratum,
        "size": item.size,
        "density_label": item.density_label,
        "p": item.p,
        "seed": item.seed,
        "accepted": True,
        "rejection_reason": None,
        "start": list(item.start),
        "largest_free_component_size": item.largest_free_component_size,
        "largest_free_component_fraction": item.largest_free_component_fraction,
        "cycle_limit": item.cycle_limit,
        "map_hash": item.map_hash,
    }


def _rejected_record(item: RejectedEfficiencyMap) -> dict[str, Any]:
    return {
        "candidate_index": item.candidate_index,
        "stratum_index": item.stratum_index,
        "size": item.size,
        "density_label": item.density_label,
        "p": item.p,
        "seed": item.seed,
        "accepted": False,
        "rejection_reason": item.reason,
        "start": list(item.start) if item.start is not None else None,
        "largest_free_component_size": item.largest_free_component_size,
        "largest_free_component_fraction": item.largest_free_component_fraction,
        "cycle_limit": item.cycle_limit,
        "map_hash": item.map_hash,
    }


def timing_subset_ids(accepted: Sequence[AcceptedEfficiencyMap]) -> list[str]:
    """Choose the first accepted map in every size-density stratum."""

    return [
        next(
            item.dataset_id
            for item in accepted
            if item.size == size and item.density_label == density
        )
        for size in SIZES
        for density, _ in DENSITIES
    ]


def sensitivity_subset_ids(accepted: Sequence[AcceptedEfficiencyMap]) -> list[str]:
    """Choose the first accepted 30x30 map in every density stratum."""

    return [
        next(
            item.dataset_id
            for item in accepted
            if item.size == 30 and item.density_label == density
        )
        for density, _ in DENSITIES
    ]


def dataset_config(
    dataset: Experiment1Dataset, master_seed: int = MASTER_SEED
) -> dict[str, Any]:
    accepted = dataset.accepted
    rejected = dataset.rejected
    stratum_counts = Counter(
        f"{item.size}x{item.size}/{item.density_label}" for item in accepted
    )
    reason_counts = Counter(item.reason for item in rejected)
    return {
        "experiment_name": EXPERIMENT_NAME,
        "dataset_version": DATASET_VERSION,
        "status": "frozen and preregistered; not executed",
        "master_seed": master_seed,
        "generator": {
            "version": GENERATOR_VERSION,
            "rng": "random.Random",
            "seed_derivation": "master_rng.getrandbits(63) per candidate attempt; rejected candidates consume stream positions",
            "cell_rule": "OCCUPIED iff local_rng.random() < p, row-major",
            "generation_order": "size ascending, then density sparse/medium/dense, until three accepted per stratum",
            "sizes": list(SIZES),
            "densities": {label: p for label, p in DENSITIES},
            "accepted_per_stratum": ACCEPTED_PER_STRATUM,
        },
        "acceptance": {
            "kind": "structural only; no sensing or planner execution",
            "connectivity": "8-neighbor with no diagonal corner cutting",
            "minimum_largest_free_component_fraction": MIN_LARGEST_COMPONENT_FRACTION,
            "component_fraction_denominator": "height * width (total grid-cell count)",
            "component_tie": "lexicographically smallest cell in component",
        },
        "start_selection": {
            "component": "deterministically selected largest FREE component",
            "cell": "minimum squared Euclidean distance to geometric grid center; lexicographic tie",
        },
        "cycle_limit": "max(64, 2 * largest_free_component_size)",
        "hashing": {
            "algorithm": "SHA-256",
            "ground_truth_symbols": {"FREE": ".", "OCCUPIED": "#"},
            "encoding": "UTF-8",
            "row_order": "top-to-bottom, left-to-right",
            "line_ending": "LF after every row, including the final row",
        },
        "counts": {
            "accepted_total": len(accepted),
            "rejected_total": len(rejected),
            "accepted_by_stratum": dict(sorted(stratum_counts.items())),
        },
        "timing_subset_map_ids": timing_subset_ids(accepted),
        "sensitivity_subset_map_ids": sensitivity_subset_ids(accepted),
        "accepted_maps": [_accepted_record(item) for item in accepted],
        "rejected_candidates": [_rejected_record(item) for item in rejected],
        "rejected_summary": dict(sorted(reason_counts.items())),
    }


def validate_config_schema(config: Mapping[str, Any]) -> None:
    required = {
        "experiment_name", "dataset_version", "status", "master_seed",
        "generator", "acceptance", "start_selection", "cycle_limit",
        "hashing", "counts", "timing_subset_map_ids",
        "sensitivity_subset_map_ids", "accepted_maps",
        "rejected_candidates", "rejected_summary",
    }
    if set(config) != required:
        raise ValueError("Experiment 1 dataset config top-level schema mismatch")
    if config["experiment_name"] != EXPERIMENT_NAME:
        raise ValueError("unexpected experiment name")
    if config["dataset_version"] != DATASET_VERSION:
        raise ValueError("unexpected dataset version")
    if config["status"] != "frozen and preregistered; not executed":
        raise ValueError("unexpected execution status")
    if config["master_seed"] != MASTER_SEED:
        raise ValueError("unexpected master seed")
    generator = config["generator"]
    if (
        generator.get("version") != GENERATOR_VERSION
        or generator.get("rng") != "random.Random"
        or generator.get("sizes") != list(SIZES)
        or generator.get("densities") != dict(DENSITIES)
        or generator.get("accepted_per_stratum") != ACCEPTED_PER_STRATUM
    ):
        raise ValueError("generator parameters differ from the freeze")
    acceptance = config["acceptance"]
    if (
        acceptance.get("kind")
        != "structural only; no sensing or planner execution"
        or acceptance.get("minimum_largest_free_component_fraction")
        != MIN_LARGEST_COMPONENT_FRACTION
        or acceptance.get("component_fraction_denominator")
        != "height * width (total grid-cell count)"
    ):
        raise ValueError("acceptance rule differs from the freeze")

    accepted = config["accepted_maps"]
    rejected = config["rejected_candidates"]
    if not isinstance(accepted, list) or not isinstance(rejected, list):
        raise TypeError("accepted_maps and rejected_candidates must be lists")
    if len(accepted) != 27:
        raise ValueError("frozen dataset must contain exactly 27 accepted maps")

    accepted_required = {
        "dataset_index", "candidate_index", "dataset_id", "stratum_index",
        "accepted_index_in_stratum", "size", "density_label", "p", "seed",
        "accepted", "rejection_reason", "start",
        "largest_free_component_size", "largest_free_component_fraction",
        "cycle_limit", "map_hash",
    }
    expected_ids: list[str] = []
    expected_strata: Counter[str] = Counter()
    previous_candidate_index = -1
    for index, record in enumerate(accepted):
        if set(record) != accepted_required:
            raise ValueError(f"accepted record schema mismatch at {index}")
        if record["dataset_index"] != index:
            raise ValueError(f"noncanonical dataset index at {index}")
        if record["candidate_index"] <= previous_candidate_index:
            raise ValueError(f"nonmonotone accepted candidate index at {index}")
        previous_candidate_index = record["candidate_index"]
        density = record["density_label"]
        if record["size"] not in SIZES or dict(DENSITIES).get(density) != record["p"]:
            raise ValueError(f"invalid stratum at {index}")
        if record["stratum_index"] != [x[0] for x in DENSITIES].index(density):
            raise ValueError(f"invalid stratum index at {index}")
        accepted_index = record["accepted_index_in_stratum"]
        expected_id = dataset_id(record["size"], density, accepted_index)
        if record["dataset_id"] != expected_id:
            raise ValueError(f"noncanonical dataset ID at {index}")
        expected_ids.append(expected_id)
        if record["accepted"] is not True or record["rejection_reason"] is not None:
            raise ValueError(f"invalid accepted status at {index}")
        if not (
            isinstance(record["start"], list)
            and len(record["start"]) == 2
            and all(type(value) is int for value in record["start"])
        ):
            raise ValueError(f"invalid start at {index}")
        component = record["largest_free_component_size"]
        expected_fraction = component / (record["size"] * record["size"])
        if record["largest_free_component_fraction"] != expected_fraction:
            raise ValueError(f"invalid component fraction at {index}")
        if expected_fraction < MIN_LARGEST_COMPONENT_FRACTION:
            raise ValueError(f"accepted component below threshold at {index}")
        if record["cycle_limit"] != random_cycle_limit(component):
            raise ValueError(f"invalid cycle limit at {index}")
        _validate_hash(record["map_hash"], index)
        expected_strata[f"{record['size']}x{record['size']}/{density}"] += 1

    rejected_required = {
        "candidate_index", "stratum_index", "size", "density_label", "p",
        "seed", "accepted", "rejection_reason", "start",
        "largest_free_component_size", "largest_free_component_fraction",
        "cycle_limit", "map_hash",
    }
    for index, record in enumerate(rejected):
        if set(record) != rejected_required:
            raise ValueError(f"rejected record schema mismatch at {index}")
        if record["accepted"] is not False or not record["rejection_reason"]:
            raise ValueError(f"invalid rejected status at {index}")
        expected_fraction = record["largest_free_component_size"] / (
            record["size"] * record["size"]
        )
        if record["largest_free_component_fraction"] != expected_fraction:
            raise ValueError(f"invalid rejected fraction at {index}")
        if record["cycle_limit"] != random_cycle_limit(
            record["largest_free_component_size"]
        ):
            raise ValueError(f"invalid rejected cycle limit at {index}")
        _validate_hash(record["map_hash"], index)

    attempts = sorted(
        [*accepted, *rejected], key=lambda record: record["candidate_index"]
    )
    if [record["candidate_index"] for record in attempts] != list(range(len(attempts))):
        raise ValueError("candidate seed stream has a missing or duplicate position")
    expected_strata_map = {
        f"{size}x{size}/{density}": ACCEPTED_PER_STRATUM
        for size in SIZES for density, _ in DENSITIES
    }
    if dict(sorted(expected_strata.items())) != dict(sorted(expected_strata_map.items())):
        raise ValueError("accepted stratum quotas differ from the freeze")
    expected_timing = [
        dataset_id(size, density, 1)
        for size in SIZES for density, _ in DENSITIES
    ]
    expected_sensitivity = [dataset_id(30, density, 1) for density, _ in DENSITIES]
    if config["timing_subset_map_ids"] != expected_timing:
        raise ValueError("timing subset differs from the freeze")
    if config["sensitivity_subset_map_ids"] != expected_sensitivity:
        raise ValueError("sensitivity subset differs from the freeze")
    reason_counts = Counter(record["rejection_reason"] for record in rejected)
    expected_counts = {
        "accepted_total": 27,
        "rejected_total": len(rejected),
        "accepted_by_stratum": dict(sorted(expected_strata_map.items())),
    }
    if config["counts"] != expected_counts:
        raise ValueError("dataset count summary mismatch")
    if config["rejected_summary"] != dict(sorted(reason_counts.items())):
        raise ValueError("rejection summary mismatch")


def _validate_hash(value: Any, index: int) -> None:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"invalid map hash at {index}")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"non-hex map hash at {index}") from exc


def load_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        result = json.load(handle)
    validate_config_schema(result)
    return result


def regenerate_record(record: Mapping[str, Any]) -> AcceptedEfficiencyMap:
    grid = generate_ground_truth(record["size"], record["p"], record["seed"])
    start, component_size, _ = select_start(grid)
    if start is None:
        raise ValueError("accepted record regenerated without a FREE start")
    return AcceptedEfficiencyMap(
        dataset_index=record["dataset_index"],
        candidate_index=record["candidate_index"],
        dataset_id=record["dataset_id"],
        stratum_index=record["stratum_index"],
        accepted_index_in_stratum=record["accepted_index_in_stratum"],
        size=record["size"],
        density_label=record["density_label"],
        p=record["p"],
        seed=record["seed"],
        start=start,
        largest_free_component_size=component_size,
        largest_free_component_fraction=component_size / (record["size"] ** 2),
        cycle_limit=random_cycle_limit(component_size),
        map_hash=ground_truth_hash(grid),
        ground_truth=grid,
    )


def write_config(path: str | Path, config: Mapping[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(config, handle, indent=2, sort_keys=False, allow_nan=False)
        handle.write("\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    dataset = materialize_dataset()
    config = dataset_config(dataset)
    validate_config_schema(config)
    write_config(args.output, config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
