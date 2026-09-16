import json
from pathlib import Path
import unittest

from src.environment import GroundTruthGrid
from src.mapping import BeliefGrid
from src.utils import (
    TruthState,
    belief_hash,
    canonical_belief_text,
    canonical_ground_truth_text,
    ground_truth_hash,
)
from src.evaluation.experiment_0_failure import (
    FAILURE_ARTIFACT_FILES,
    FailureDescription,
    deterministic_failure_run_id,
    write_failure_artifact,
)
from src.evaluation.experiment_0_logging import EXPERIMENT_VERSION
from tests.stage7_helpers import workspace_temp_directory


class FailureArtifactTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ground_truth = GroundTruthGrid.from_ascii(("...", ".#.", "..."))
        self.belief = BeliefGrid.unknown(3, 3)
        self.belief.apply_observations(
            {(0, 0): TruthState.FREE, (1, 1): TruthState.OCCUPIED}
        )
        self.invocation_id = "stage7-smoke-failure-test"
        self.run_id = deterministic_failure_run_id(
            invocation_id=self.invocation_id,
            dataset_type="fixture",
            map_id="stage7-smoke",
            cycle_index=2,
            classification="target_mismatch",
        )
        self.metadata = {
            "experiment_version": EXPERIMENT_VERSION,
            "invocation_id": self.invocation_id,
            "failure_run_id": self.run_id,
            "dataset_type": "fixture",
            "map_id": "stage7-smoke",
            "map_seed": None,
            "map_hash": ground_truth_hash(self.ground_truth),
            "belief_hash": belief_hash(self.belief),
            "start": [0, 0],
            "cycle_index": 2,
            "cycle_limit": 8,
            "robot_coordinate": [0, 0],
            "sensor_config": {"range_cells": 8.0},
            "ray_config": {"model": "supercover"},
            "motion_config": {"connectivity": 8},
            "score_epsilon": 1e-9,
            "tie_definition": "frozen total order",
            "repository_revision": "a" * 40,
            "algorithm_implementations": {
                key: {"implementation_id": key, "revision": "a" * 40}
                for key in ("A", "B", "C")
            },
            "failure_classification": "target_mismatch",
        }
        self.candidates = [
            {"candidate": [2, 1], "a": {"gain": 1}},
            {"candidate": [0, 2], "a": {"gain": 2}},
        ]
        self.algorithm_state = {
            "c": {
                "inverse_incidence": [
                    {"cell": [1, 2], "candidates": [[2, 1], [0, 2]]}
                ]
            },
            "b": {"cached_gains": []},
        }
        self.description = FailureDescription(
            "target_mismatch",
            "A/B/C selected targets differ",
            [0, 2],
            {"b": [2, 1], "c": [0, 2]},
        )

    def _write(self, root: Path) -> Path:
        return write_failure_artifact(
            output_root=root,
            failure_run_id=self.run_id,
            metadata=self.metadata,
            ground_truth=self.ground_truth,
            belief_before=self.belief,
            candidates=self.candidates,
            algorithm_state=self.algorithm_state,
            description=self.description,
        )

    def test_directory_contains_exactly_six_required_files(self) -> None:
        with workspace_temp_directory() as directory:
            artifact = self._write(Path(directory))
            self.assertEqual(
                {path.name for path in artifact.iterdir()},
                set(FAILURE_ARTIFACT_FILES),
            )

    def test_second_write_fails_and_preserves_existing_artifact(self) -> None:
        with workspace_temp_directory() as directory:
            root = Path(directory)
            artifact = self._write(root)
            before = {path.name: path.read_bytes() for path in artifact.iterdir()}
            with self.assertRaises(FileExistsError):
                self._write(root)
            after = {path.name: path.read_bytes() for path in artifact.iterdir()}
            self.assertEqual(after, before)

    def test_canonical_ground_truth_and_belief_text_match_hashes(self) -> None:
        with workspace_temp_directory() as directory:
            artifact = self._write(Path(directory))
            truth_text = (artifact / "ground_truth.txt").read_text(encoding="utf-8")
            belief_text = (artifact / "belief_before.txt").read_text(encoding="utf-8")
            self.assertEqual(truth_text, canonical_ground_truth_text(self.ground_truth))
            self.assertEqual(belief_text, canonical_belief_text(self.belief))
            metadata = json.loads((artifact / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["map_hash"], ground_truth_hash(self.ground_truth))
            self.assertEqual(metadata["belief_hash"], belief_hash(self.belief))
            self.assertTrue(truth_text.endswith("\n"))
            self.assertTrue(belief_text.endswith("\n"))

    def test_candidates_are_sorted_deterministically(self) -> None:
        with workspace_temp_directory() as directory:
            artifact = self._write(Path(directory))
            candidates = json.loads(
                (artifact / "candidates.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                [record["candidate"] for record in candidates],
                [[0, 2], [2, 1]],
            )
            first = (artifact / "candidates.json").read_bytes()

        with workspace_temp_directory() as second_directory:
            second = self._write(Path(second_directory))
            self.assertEqual((second / "candidates.json").read_bytes(), first)

    def test_algorithm_state_has_canonical_deterministic_serialization(self) -> None:
        with workspace_temp_directory() as first_directory:
            first = self._write(Path(first_directory))
            first_bytes = (first / "algorithm_state.json").read_bytes()
        with workspace_temp_directory() as second_directory:
            reversed_state = dict(reversed(tuple(self.algorithm_state.items())))
            second = write_failure_artifact(
                output_root=Path(second_directory),
                failure_run_id=self.run_id,
                metadata=self.metadata,
                ground_truth=self.ground_truth,
                belief_before=self.belief,
                candidates=self.candidates,
                algorithm_state=reversed_state,
                description=self.description,
            )
            self.assertEqual(
                (second / "algorithm_state.json").read_bytes(),
                first_bytes,
            )

    def test_failure_text_contains_distinct_reproduction_invocation(self) -> None:
        with workspace_temp_directory() as directory:
            artifact = self._write(Path(directory))
            text = (artifact / "failure.txt").read_text(encoding="utf-8")
            self.assertIn("--execute-preregistered", text)
            self.assertIn("--only-map stage7-smoke", text)
            self.assertIn(f"--invocation-id reproduce-{self.run_id}", text)
            self.assertNotEqual(self.invocation_id, self.run_id)


if __name__ == "__main__":
    unittest.main()
