from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import random
import unittest
from unittest.mock import patch

from src.evaluation.experiment_1_dataset import (
    ACCEPTED_PER_STRATUM,
    DATASET_VERSION,
    DENSITIES,
    MASTER_SEED,
    SIZES,
    dataset_config,
    dataset_id,
    materialize_dataset,
    regenerate_record,
    validate_config_schema,
)
from src.evaluation.random_dataset import (
    generate_ground_truth,
    random_cycle_limit,
    select_start,
)
from src.utils import ground_truth_hash

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "experiment_1_efficiency_maps.json"


class Experiment1DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            cls.config = json.load(handle)

    def test_frozen_config_schema_and_constants(self) -> None:
        validate_config_schema(self.config)
        self.assertEqual(self.config["dataset_version"], DATASET_VERSION)
        self.assertEqual(self.config["master_seed"], MASTER_SEED)
        self.assertEqual(
            self.config["status"], "frozen and preregistered; not executed"
        )

    def test_frozen_config_exactly_matches_structural_materialization(self) -> None:
        self.assertEqual(dataset_config(materialize_dataset()), self.config)

    def test_balance_and_stable_ids(self) -> None:
        dataset = materialize_dataset()
        self.assertEqual(len(dataset.accepted), 27)
        counts = Counter(
            (item.size, item.density_label) for item in dataset.accepted
        )
        self.assertEqual(
            counts,
            Counter(
                {
                    (size, density): ACCEPTED_PER_STRATUM
                    for size in SIZES
                    for density, _ in DENSITIES
                }
            ),
        )
        self.assertEqual(
            [item.dataset_id for item in dataset.accepted],
            [
                dataset_id(size, density, accepted_index)
                for size in SIZES
                for density, _ in DENSITIES
                for accepted_index in range(1, ACCEPTED_PER_STRATUM + 1)
            ],
        )

    def test_every_frozen_record_regenerates_all_structural_fields(self) -> None:
        for record in self.config["accepted_maps"]:
            regenerated = regenerate_record(record)
            grid = generate_ground_truth(record["size"], record["p"], record["seed"])
            start, component_size, _ = select_start(grid)
            self.assertEqual(regenerated.start, start)
            self.assertEqual(start, tuple(record["start"]))
            self.assertEqual(
                regenerated.largest_free_component_size, component_size
            )
            self.assertEqual(component_size, record["largest_free_component_size"])
            self.assertEqual(
                regenerated.largest_free_component_fraction,
                record["largest_free_component_fraction"],
            )
            self.assertEqual(
                regenerated.cycle_limit, random_cycle_limit(component_size)
            )
            self.assertEqual(regenerated.cycle_limit, record["cycle_limit"])
            self.assertEqual(regenerated.map_hash, ground_truth_hash(grid))
            self.assertEqual(regenerated.map_hash, record["map_hash"])

    def test_candidate_seed_stream_is_contiguous_and_reproducible(self) -> None:
        records = sorted(
            [
                *self.config["accepted_maps"],
                *self.config["rejected_candidates"],
            ],
            key=lambda item: item["candidate_index"],
        )
        self.assertEqual(
            [record["candidate_index"] for record in records],
            list(range(len(records))),
        )
        master_rng = random.Random(MASTER_SEED)
        self.assertEqual(
            [record["seed"] for record in records],
            [master_rng.getrandbits(63) for _ in records],
        )

    def test_timing_and_sensitivity_subsets_are_frozen(self) -> None:
        self.assertEqual(
            self.config["timing_subset_map_ids"],
            [
                dataset_id(size, density, 1)
                for size in SIZES
                for density, _ in DENSITIES
            ],
        )
        self.assertEqual(
            self.config["sensitivity_subset_map_ids"],
            [dataset_id(30, density, 1) for density, _ in DENSITIES],
        )

    def test_generation_does_not_change_global_rng_state(self) -> None:
        random.seed(314159)
        before = random.getstate()
        materialize_dataset()
        self.assertEqual(random.getstate(), before)

    def test_generation_cannot_call_the_experiment_0_planner(self) -> None:
        def forbidden_plan(*args: object, **kwargs: object) -> object:
            raise AssertionError("Experiment 1 dataset generation executed a planner")

        with patch(
            "src.evaluation.random_dataset.ExplorationSimulator.plan",
            new=forbidden_plan,
        ):
            dataset = materialize_dataset()
        self.assertEqual(len(dataset.accepted), 27)

    def test_config_rejects_changed_timing_subset(self) -> None:
        config = json.loads(json.dumps(self.config))
        config["timing_subset_map_ids"][0] = "not-frozen"
        with self.assertRaisesRegex(ValueError, "timing subset"):
            validate_config_schema(config)


if __name__ == "__main__":
    unittest.main()
