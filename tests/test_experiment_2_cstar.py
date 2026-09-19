import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.environment import GroundTruthGrid
from src.evaluation.experiment_2_analysis import classify_decision
from src.evaluation.experiment_2_dataset import (
    MASTER_SEED,
    dataset_config,
    materialize_dataset,
    write_config,
)
from src.evaluation.experiment_2_logging import METHODS, TIMING_ORDERS, WARMUP_ORDER
from src.evaluation.experiment_2_failure import (
    FAILURE_ARTIFACT_FILES,
    FailureDescription,
    write_failure_artifact,
)
from src.evaluation.experiment_2_runner import (
    Experiment2Case,
    EpisodeReference,
    ReferenceDecision,
    require_exact_frozen_config,
    run_method_episode,
    run_shared_structural,
)
from src.evaluation.simulator import ExplorationSimulator
from src.utils import belief_hash, ground_truth_hash


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


    def test_frozen_config_must_exactly_match_canonical_materialization(self) -> None:
        config = dataset_config(materialize_dataset())
        with TemporaryDirectory() as temp:
            path = Path(temp) / "experiment_2_cstar_maps.json"
            write_config(path, config)
            self.assertEqual(require_exact_frozen_config(path), config)

            changed = json.loads(json.dumps(config))
            changed["accepted_maps"][0]["map_hash"] = "0" * 64
            write_config(path, changed)
            with self.assertRaisesRegex(
                RuntimeError, "differs from canonical master-seed materialization"
            ):
                require_exact_frozen_config(path)

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

    def test_primary_timing_boundary_excludes_reference_validation(self) -> None:
        grid = GroundTruthGrid.from_ascii(("...", "...", "..."))
        case = Experiment2Case(
            dataset_kind="fixture",
            map_id="timing-boundary",
            size=3,
            density_label=None,
            occupancy_probability=None,
            map_seed=None,
            map_hash=ground_truth_hash(grid),
            ground_truth=grid,
            start=(1, 1),
            cycle_limit=10,
        )
        simulator = ExplorationSimulator(grid, (1, 1), 8.0)
        result = simulator.plan()
        reference = EpisodeReference(
            map_id=case.map_id,
            sensor_range=8.0,
            decisions=(
                ReferenceDecision(
                    cycle_index=0,
                    belief_hash=belief_hash(simulator.world.belief),
                    robot=(1, 1),
                    status=result.status.value,
                    candidate=result.selected_candidate,
                    gain=result.selected_gain,
                    distance=result.selected_distance,
                    score=result.selected_score,
                    path=tuple(result.selected_path),
                ),
            ),
        )
        with (
            patch(
                "src.evaluation.experiment_2_runner.time.perf_counter_ns",
                side_effect=(100, 125),
            ),
            patch(
                "src.evaluation.experiment_2_runner.time.process_time_ns",
                side_effect=(200, 215),
            ),
        ):
            record = run_method_episode(
                case=case,
                method="A",
                reference=reference,
                invocation_id="timing-boundary",
                phase="primary_timing",
                repetition_index=1,
                method_order=("A", "B", "C", "C*"),
                method_order_position=0,
                writer=None,
            )
        self.assertEqual(record["planner_wall_time_ns"], 25)
        self.assertEqual(record["process_time_ns"], 15)

    def test_detailed_failure_artifact_has_e1_style_six_file_layout(self) -> None:
        grid = GroundTruthGrid.from_ascii(("...", "...", "..."))
        simulator = ExplorationSimulator(grid, (1, 1), 2.0)
        belief = simulator.world.belief
        with TemporaryDirectory() as temp:
            metadata = {
                "experiment_version": "experiment-2-runner-v1",
                "dataset_version": "experiment-2-cstar-efficiency-v1",
                "invocation_id": "failure-test",
                "failure_run_id": "failure-test-001",
                "phase": "primary_structural",
                "map_id": "fixture",
                "method": "C*",
                "method_order": None,
                "method_order_position": None,
                "repetition_index": None,
                "sensor_range": 2.0,
                "cycle_index": 0,
                "robot_coordinate": [1, 1],
                "map_hash": ground_truth_hash(grid),
                "belief_hash": belief_hash(belief),
                "repository_revision": "0" * 40,
                "failure_classification": "cstar_audit_failure",
            }
            path = write_failure_artifact(
                output_root=temp,
                failure_run_id="failure-test-001",
                metadata=metadata,
                ground_truth=grid,
                belief_before=belief,
                candidates=[],
                algorithm_state={},
                description=FailureDescription(
                    "cstar_audit_failure",
                    "synthetic audit failure",
                ),
            )
            self.assertEqual(
                frozenset(item.name for item in path.iterdir()),
                FAILURE_ARTIFACT_FILES,
            )


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
