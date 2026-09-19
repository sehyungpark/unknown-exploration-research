import unittest

from src.environment import GroundTruthGrid
from src.evaluation.experiment_2_analysis import classify_decision
from src.evaluation.experiment_2_dataset import (
    MASTER_SEED,
    dataset_config,
    materialize_dataset,
)
from src.evaluation.experiment_2_logging import METHODS, TIMING_ORDERS, WARMUP_ORDER
from src.evaluation.experiment_2_runner import Experiment2Case, run_shared_structural
from src.utils import ground_truth_hash


class Experiment2DatasetTests(unittest.TestCase):
    def test_new_holdout_seed_and_shape(self) -> None:
        self.assertEqual(MASTER_SEED, 20260919)
        dataset = materialize_dataset()
        config = dataset_config(dataset)
        self.assertEqual(config["master_seed"], 20260919)
        self.assertEqual(len(config["accepted_maps"]), 27)
        self.assertEqual(len(config["timing_subset_map_ids"]), 9)
        self.assertEqual(len(config["sensitivity_subset_map_ids"]), 3)
        first = config["accepted_maps"][0]
        self.assertEqual(first["seed"], 907189991483662692)
        self.assertEqual(
            first["map_hash"],
            "439031f9116516db4cd777081e76bde0d473b293e51d702e9cdb37c02ebafc39",
        )

    def test_timing_schedule_keeps_six_repetitions_and_all_four_methods(self) -> None:
        self.assertEqual(tuple(WARMUP_ORDER), METHODS)
        self.assertEqual(len(TIMING_ORDERS), 6)
        for order in TIMING_ORDERS:
            self.assertEqual(set(order), set(METHODS))
            self.assertEqual(len(order), 4)


class Experiment2RunnerTests(unittest.TestCase):
    def test_shared_small_case_matches_A_B_C_Cstar_to_completion(self) -> None:
        grid = GroundTruthGrid.from_ascii(
            (
                ".......",
                ".......",
                ".......",
                ".......",
                ".......",
                ".......",
                ".......",
            )
        )
        case = Experiment2Case(
            dataset_kind="fixture",
            map_id="experiment2-smoke",
            size=7,
            density_label=None,
            occupancy_probability=None,
            map_seed=None,
            map_hash=ground_truth_hash(grid),
            ground_truth=grid,
            start=(3, 3),
            cycle_limit=100,
        )
        reference = run_shared_structural(
            case=case,
            invocation_id="experiment2-smoke",
            phase="anchor_structural",
            sensor_range=2.0,
            writer=None,
        )
        self.assertGreater(len(reference.decisions), 1)
        self.assertEqual(reference.decisions[-1].status, "EXPLORATION_COMPLETE")

    def test_decision_rule_mirrors_experiment1_with_cstar_as_primary_method(self) -> None:
        work_b = {
            "visibility_ray_count": 100,
            "visibility_supercover_cell_count": 200,
            "visibility_interior_probe_count": 300,
        }
        work_star = {
            "visibility_ray_count": 90,
            "visibility_supercover_cell_count": 180,
            "visibility_interior_probe_count": 250,
        }
        self.assertEqual(
            classify_decision(
                correctness_valid=True,
                cstar_work=work_star,
                b_work=work_b,
                cstar_over_b_interval=(0.8, 0.95),
                complete=True,
            ),
            "GO",
        )


if __name__ == "__main__":
    unittest.main()
