"""Frozen deterministic random-map dataset construction for Experiment 0."""

from __future__ import annotations

import argparse
from collections import Counter, deque
from dataclasses import dataclass
import json
from pathlib import Path
import random
from typing import Any, Iterable, Mapping, Sequence

from src.environment import GroundTruthGrid
from src.planning import PlanStatus
from src.utils import Coord, TruthState, ground_truth_hash

from .simulator import ExplorationSimulator

DATASET_VERSION = "experiment-0-random-v2"
SUPERSEDED_DATASET_VERSION = "experiment-0-random-v1"
GENERATOR_VERSION = "independent-bernoulli-occupancy-v1"
MASTER_SEED = 20260915
SIZES = (12, 16, 20)
DENSITIES: tuple[tuple[str, float], ...] = (
    ("sparse", 0.10),
    ("medium", 0.20),
    ("dense", 0.30),
)
DENSITY_TARGETS: Mapping[str, int] = {
    "sparse": 7,
    "medium": 7,
    "dense": 6,
}
MIN_LARGEST_COMPONENT_FRACTION = 0.35
SENSOR_RANGE = 8.0


@dataclass(frozen=True, slots=True)
class AcceptedMap:
    dataset_index: int
    candidate_index: int
    dataset_id: str
    size: int
    density_label: str
    p: float
    seed: int
    start: Coord
    free_component_size: int
    cycle_limit: int
    map_hash: str
    ground_truth: GroundTruthGrid


@dataclass(frozen=True, slots=True)
class RejectedMap:
    candidate_index: int
    size: int
    density_label: str
    p: float
    seed: int
    reason: str
    start: Coord | None
    map_hash: str


@dataclass(frozen=True, slots=True)
class Experiment0Dataset:
    accepted: tuple[AcceptedMap, ...]
    rejected: tuple[RejectedMap, ...]


def generate_ground_truth(size: int, p: float, seed: int) -> GroundTruthGrid:
    """Generate one square Bernoulli occupancy map from an isolated RNG."""

    if size <= 0:
        raise ValueError("map size must be positive")
    if not 0.0 <= p <= 1.0:
        raise ValueError("occupancy probability must be in [0, 1]")
    rng = random.Random(seed)
    cells = tuple(
        tuple(
            TruthState.OCCUPIED if rng.random() < p else TruthState.FREE
            for _ in range(size)
        )
        for _ in range(size)
    )
    return GroundTruthGrid(cells)


def _free_neighbors(grid: GroundTruthGrid, coord: Coord) -> tuple[Coord, ...]:
    """Use the frozen 8-neighbor/no-corner-cutting traversability rule."""

    row, col = coord
    neighbors: list[Coord] = []
    for row_delta in (-1, 0, 1):
        for col_delta in (-1, 0, 1):
            if row_delta == 0 and col_delta == 0:
                continue
            target = row + row_delta, col + col_delta
            if not grid.in_bounds(target) or grid.state(target) is not TruthState.FREE:
                continue
            if row_delta != 0 and col_delta != 0:
                side_row = row + row_delta, col
                side_col = row, col + col_delta
                if (
                    grid.state(side_row) is not TruthState.FREE
                    or grid.state(side_col) is not TruthState.FREE
                ):
                    continue
            neighbors.append(target)
    return tuple(sorted(neighbors))


def free_components(grid: GroundTruthGrid) -> tuple[frozenset[Coord], ...]:
    """Return all FREE traversability components in deterministic order."""

    unseen = {
        coord for coord in grid.iter_coords() if grid.state(coord) is TruthState.FREE
    }
    components: list[frozenset[Coord]] = []
    while unseen:
        root = min(unseen)
        unseen.remove(root)
        queue = deque([root])
        component = {root}
        while queue:
            current = queue.popleft()
            for neighbor in _free_neighbors(grid, current):
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    component.add(neighbor)
                    queue.append(neighbor)
        components.append(frozenset(component))
    return tuple(components)


def select_largest_component(
    components: Iterable[frozenset[Coord]],
) -> frozenset[Coord] | None:
    materialized = tuple(components)
    if not materialized:
        return None
    return min(materialized, key=lambda component: (-len(component), min(component)))


def select_start(grid: GroundTruthGrid) -> tuple[Coord | None, int, int]:
    """Select the center-nearest cell of the deterministically chosen component."""

    components = free_components(grid)
    selected = select_largest_component(components)
    total_free = sum(len(component) for component in components)
    if selected is None:
        return None, 0, 0
    center_row = (grid.height - 1) / 2.0
    center_col = (grid.width - 1) / 2.0
    start = min(
        selected,
        key=lambda coord: (
            (coord[0] - center_row) ** 2 + (coord[1] - center_col) ** 2,
            coord,
        ),
    )
    return start, len(selected), total_free


def random_cycle_limit(free_component_size: int) -> int:
    if free_component_size < 0:
        raise ValueError("FREE component size must be nonnegative")
    return max(64, 2 * free_component_size)


def evaluate_candidate(
    *,
    candidate_index: int,
    size: int,
    density_label: str,
    p: float,
    seed: int,
) -> AcceptedMap | RejectedMap:
    """Generate and acceptance-check one candidate without changing global RNG state."""

    grid = generate_ground_truth(size, p, seed)
    map_digest = ground_truth_hash(grid)
    start, component_size, total_free = select_start(grid)
    occupied_count = size * size - total_free
    total_grid_cell_count = grid.height * grid.width
    component_fraction = component_size / total_grid_cell_count

    reason: str | None = None
    if total_free == 0:
        reason = "no_free_cell"
    elif start is None:
        reason = "no_start_cell"
    elif occupied_count == 0:
        reason = "no_occupied_cell"
    elif component_fraction < MIN_LARGEST_COMPONENT_FRACTION:
        reason = "largest_component_fraction_below_0.35"
    else:
        try:
            initial_plan = ExplorationSimulator(
                grid, start, sensor_range=SENSOR_RANGE
            ).plan()
            if initial_plan.status is PlanStatus.EXPLORATION_COMPLETE:
                reason = "initial_scan_exploration_complete"
        except Exception as exc:  # acceptance retains deterministic failures
            reason = f"initial_scan_exception:{type(exc).__name__}"

    if reason is not None:
        return RejectedMap(
            candidate_index=candidate_index,
            size=size,
            density_label=density_label,
            p=p,
            seed=seed,
            reason=reason,
            start=start,
            map_hash=map_digest,
        )

    assert start is not None
    return AcceptedMap(
        dataset_index=-1,
        candidate_index=candidate_index,
        dataset_id="",
        size=size,
        density_label=density_label,
        p=p,
        seed=seed,
        start=start,
        free_component_size=component_size,
        cycle_limit=random_cycle_limit(component_size),
        map_hash=map_digest,
        ground_truth=grid,
    )


def materialize_dataset(master_seed: int = MASTER_SEED) -> Experiment0Dataset:
    """Produce the frozen 60-map dataset and retain every rejected candidate."""

    master_rng = random.Random(master_seed)
    accepted: list[AcceptedMap] = []
    rejected: list[RejectedMap] = []
    candidate_index = 0

    for size in SIZES:
        counts = Counter({label: 0 for label, _ in DENSITIES})
        while any(counts[label] < DENSITY_TARGETS[label] for label, _ in DENSITIES):
            for density_label, p in DENSITIES:
                if counts[density_label] >= DENSITY_TARGETS[density_label]:
                    continue
                seed = master_rng.getrandbits(63)
                candidate = evaluate_candidate(
                    candidate_index=candidate_index,
                    size=size,
                    density_label=density_label,
                    p=p,
                    seed=seed,
                )
                candidate_index += 1
                if isinstance(candidate, RejectedMap):
                    rejected.append(candidate)
                    continue
                dataset_index = len(accepted)
                accepted.append(
                    AcceptedMap(
                        dataset_index=dataset_index,
                        candidate_index=candidate.candidate_index,
                        dataset_id=f"random-{dataset_index:03d}",
                        size=candidate.size,
                        density_label=candidate.density_label,
                        p=candidate.p,
                        seed=candidate.seed,
                        start=candidate.start,
                        free_component_size=candidate.free_component_size,
                        cycle_limit=candidate.cycle_limit,
                        map_hash=candidate.map_hash,
                        ground_truth=candidate.ground_truth,
                    )
                )
                counts[density_label] += 1

    return Experiment0Dataset(tuple(accepted), tuple(rejected))


def _accepted_record(item: AcceptedMap) -> dict[str, Any]:
    return {
        "dataset_index": item.dataset_index,
        "candidate_index": item.candidate_index,
        "dataset_id": item.dataset_id,
        "size": item.size,
        "density_label": item.density_label,
        "p": item.p,
        "seed": item.seed,
        "accepted": True,
        "rejection_reason": None,
        "start": list(item.start),
        "free_component_size": item.free_component_size,
        "cycle_limit": item.cycle_limit,
        "map_hash": item.map_hash,
    }


def _rejected_record(item: RejectedMap) -> dict[str, Any]:
    return {
        "candidate_index": item.candidate_index,
        "size": item.size,
        "density_label": item.density_label,
        "p": item.p,
        "seed": item.seed,
        "accepted": False,
        "rejection_reason": item.reason,
        "start": list(item.start) if item.start is not None else None,
        "map_hash": item.map_hash,
    }


def dataset_config(
    dataset: Experiment0Dataset, master_seed: int = MASTER_SEED
) -> dict[str, Any]:
    reason_counts = Counter(item.reason for item in dataset.rejected)
    size_counts = Counter(str(item.size) for item in dataset.accepted)
    density_counts = Counter(item.density_label for item in dataset.accepted)
    return {
        "dataset_version": DATASET_VERSION,
        "supersedes": {
            "dataset_version": SUPERSEDED_DATASET_VERSION,
            "status": "invalidated before Experiment 0 execution",
            "reason": "largest-component acceptance used total FREE cells instead of total grid cells",
        },
        "master_seed": master_seed,
        "generator": {
            "version": GENERATOR_VERSION,
            "rng": "random.Random",
            "seed_derivation": "master_rng.getrandbits(63) per candidate attempt",
            "cell_rule": "OCCUPIED iff local_rng.random() < p, row-major",
            "sizes": list(SIZES),
            "densities": {label: p for label, p in DENSITIES},
            "accepted_targets_per_size": dict(DENSITY_TARGETS),
        },
        "acceptance": {
            "connectivity": "8-neighbor with no diagonal corner cutting",
            "minimum_largest_free_component_fraction": MIN_LARGEST_COMPONENT_FRACTION,
            "component_fraction_denominator": "height * width (total grid-cell count)",
            "requires_free_and_occupied": True,
            "reject_initial_exhaustive_stop": True,
            "sensor_range": SENSOR_RANGE,
        },
        "start_selection": {
            "component": "largest FREE component; lexicographically smallest cell breaks component ties",
            "cell": "minimum squared Euclidean distance to geometric grid center; lexicographic tie",
        },
        "cycle_limit": "max(64, 2 * free_component_size)",
        "hashing": {
            "algorithm": "SHA-256",
            "ground_truth_symbols": {"FREE": ".", "OCCUPIED": "#"},
            "encoding": "UTF-8",
            "row_order": "top-to-bottom, left-to-right",
            "line_ending": "LF after every row, including the final row",
        },
        "counts": {
            "accepted_total": len(dataset.accepted),
            "rejected_total": len(dataset.rejected),
            "accepted_by_size": dict(sorted(size_counts.items())),
            "accepted_by_density": dict(sorted(density_counts.items())),
        },
        "accepted_maps": [_accepted_record(item) for item in dataset.accepted],
        "rejected_candidates": [_rejected_record(item) for item in dataset.rejected],
        "rejected_summary": dict(sorted(reason_counts.items())),
    }


def validate_config_schema(config: Mapping[str, Any]) -> None:
    """Validate the frozen artifact's required structure and internal counts."""

    required = {
        "dataset_version",
        "supersedes",
        "master_seed",
        "generator",
        "acceptance",
        "start_selection",
        "cycle_limit",
        "hashing",
        "counts",
        "accepted_maps",
        "rejected_candidates",
        "rejected_summary",
    }
    if set(config) != required:
        raise ValueError("dataset config top-level schema mismatch")
    if config["dataset_version"] != DATASET_VERSION:
        raise ValueError("unexpected dataset version")
    if config["supersedes"] != {
        "dataset_version": SUPERSEDED_DATASET_VERSION,
        "status": "invalidated before Experiment 0 execution",
        "reason": "largest-component acceptance used total FREE cells instead of total grid cells",
    }:
        raise ValueError("dataset supersession history mismatch")
    if config["master_seed"] != MASTER_SEED:
        raise ValueError("unexpected master seed")
    generator = config["generator"]
    if (
        generator.get("version") != GENERATOR_VERSION
        or generator.get("rng") != "random.Random"
        or generator.get("sizes") != list(SIZES)
        or generator.get("densities") != {label: p for label, p in DENSITIES}
        or generator.get("accepted_targets_per_size") != dict(DENSITY_TARGETS)
    ):
        raise ValueError("generator schema or parameters differ from the freeze")
    acceptance = config["acceptance"]
    if (
        acceptance.get("minimum_largest_free_component_fraction")
        != MIN_LARGEST_COMPONENT_FRACTION
        or acceptance.get("component_fraction_denominator")
        != "height * width (total grid-cell count)"
    ):
        raise ValueError("component acceptance formula differs from the freeze")
    accepted = config["accepted_maps"]
    rejected = config["rejected_candidates"]
    if not isinstance(accepted, list) or not isinstance(rejected, list):
        raise TypeError("accepted_maps and rejected_candidates must be lists")
    if len(accepted) != 60:
        raise ValueError("frozen dataset must contain exactly 60 accepted maps")

    accepted_required = {
        "dataset_index",
        "candidate_index",
        "dataset_id",
        "size",
        "density_label",
        "p",
        "seed",
        "accepted",
        "rejection_reason",
        "start",
        "free_component_size",
        "cycle_limit",
        "map_hash",
    }
    for index, record in enumerate(accepted):
        if set(record) != accepted_required:
            raise ValueError(f"accepted record schema mismatch at {index}")
        if record["dataset_index"] != index or record["dataset_id"] != f"random-{index:03d}":
            raise ValueError(f"noncanonical dataset identity at {index}")
        if record["accepted"] is not True or record["rejection_reason"] is not None:
            raise ValueError(f"invalid accepted status at {index}")
        if record["size"] not in SIZES:
            raise ValueError(f"invalid size at {index}")
        expected_p = dict(DENSITIES).get(record["density_label"])
        if record["p"] != expected_p:
            raise ValueError(f"invalid density at {index}")
        if not (
            isinstance(record["start"], list)
            and len(record["start"]) == 2
            and all(isinstance(value, int) for value in record["start"])
        ):
            raise ValueError(f"invalid start at {index}")
        if not all(0 <= value < record["size"] for value in record["start"]):
            raise ValueError(f"out-of-bounds start at {index}")
        if record["cycle_limit"] != random_cycle_limit(record["free_component_size"]):
            raise ValueError(f"invalid cycle limit at {index}")
        total_grid_cell_count = record["size"] * record["size"]
        if (
            record["free_component_size"] / total_grid_cell_count
            < MIN_LARGEST_COMPONENT_FRACTION
        ):
            raise ValueError(f"accepted component fraction below threshold at {index}")
        digest = record["map_hash"]
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError(f"invalid map hash at {index}")
        try:
            int(digest, 16)
        except ValueError as exc:
            raise ValueError(f"non-hex map hash at {index}") from exc

    rejected_required = {
        "candidate_index",
        "size",
        "density_label",
        "p",
        "seed",
        "accepted",
        "rejection_reason",
        "start",
        "map_hash",
    }
    for index, record in enumerate(rejected):
        if set(record) != rejected_required:
            raise ValueError(f"rejected record schema mismatch at {index}")
        if record["accepted"] is not False or not record["rejection_reason"]:
            raise ValueError(f"invalid rejected status at {index}")

    size_counts = Counter(str(record["size"]) for record in accepted)
    density_counts = Counter(record["density_label"] for record in accepted)
    for size in SIZES:
        per_size = Counter(
            record["density_label"]
            for record in accepted
            if record["size"] == size
        )
        if per_size != Counter(DENSITY_TARGETS):
            raise ValueError(f"density quota mismatch for size {size}")
    reason_counts = Counter(record["rejection_reason"] for record in rejected)
    expected_counts = {
        "accepted_total": len(accepted),
        "rejected_total": len(rejected),
        "accepted_by_size": dict(sorted(size_counts.items())),
        "accepted_by_density": dict(sorted(density_counts.items())),
    }
    if config["counts"] != expected_counts:
        raise ValueError("dataset count summary mismatch")
    if config["rejected_summary"] != dict(sorted(reason_counts.items())):
        raise ValueError("rejection summary mismatch")


def load_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        result = json.load(handle)
    validate_config_schema(result)
    return result


def regenerate_record(record: Mapping[str, Any]) -> AcceptedMap:
    grid = generate_ground_truth(record["size"], record["p"], record["seed"])
    start, component_size, _ = select_start(grid)
    if start is None:
        raise ValueError("accepted record regenerated without a FREE start")
    return AcceptedMap(
        dataset_index=record["dataset_index"],
        candidate_index=record["candidate_index"],
        dataset_id=record["dataset_id"],
        size=record["size"],
        density_label=record["density_label"],
        p=record["p"],
        seed=record["seed"],
        start=start,
        free_component_size=component_size,
        cycle_limit=random_cycle_limit(component_size),
        map_hash=ground_truth_hash(grid),
        ground_truth=grid,
    )


def write_config(path: str | Path, config: Mapping[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(config, handle, indent=2, sort_keys=False)
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
