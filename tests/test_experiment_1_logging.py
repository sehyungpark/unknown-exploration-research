import json
from pathlib import Path
import unittest

from src.environment import GroundTruthGrid
from src.evaluation.experiment_1_failure import (
    FAILURE_ARTIFACT_FILES,
    FailureDescription,
    deterministic_failure_run_id,
    write_failure_artifact,
)
from src.evaluation.experiment_1_logging import (
    Experiment1InvocationWriter,
    canonical_json_text,
    serialize_record,
    validate_episode_record,
    validate_memory_record,
    validate_snapshot_record,
)
from src.mapping import BeliefGrid
from src.utils import TruthState, belief_hash, ground_truth_hash
from tests.stage10_helpers import (
    REVISION,
    episode_record,
    manifest,
    memory_record,
    snapshot_record,
)
from tests.stage7_helpers import workspace_temp_directory


class SchemaAndSerializationTests(unittest.TestCase):
    def test_exact_episode_fields_accept_valid_record(self) -> None:
        validate_episode_record(episode_record())

    def test_missing_field_is_rejected(self) -> None:
        record = episode_record()
        del record["map_hash"]
        with self.assertRaisesRegex(ValueError, "exact field/order mismatch"):
            validate_episode_record(record)

    def test_unexpected_field_is_rejected(self) -> None:
        record = episode_record()
        record["unexpected"] = 1
        with self.assertRaisesRegex(ValueError, "exact field/order mismatch"):
            validate_episode_record(record)

    def test_wrong_phase_and_method_are_rejected(self) -> None:
        phase = episode_record()
        phase["phase"] = "not-a-phase"
        with self.assertRaisesRegex(ValueError, "invalid phase"):
            validate_episode_record(phase)
        method = episode_record()
        method["method"] = "D"
        with self.assertRaisesRegex(ValueError, "invalid method"):
            validate_episode_record(method)

    def test_invalid_coordinate_and_status_are_rejected(self) -> None:
        coordinate = snapshot_record()
        coordinate["robot_coordinate"] = [-1, 0]
        with self.assertRaisesRegex(ValueError, "robot_coordinate"):
            validate_snapshot_record(coordinate)
        status = snapshot_record()
        status["status"] = "STOP"
        with self.assertRaisesRegex(ValueError, "invalid status"):
            validate_snapshot_record(status)

    def test_nan_infinity_and_negative_values_are_rejected(self) -> None:
        nan = snapshot_record()
        nan["selected_score"] = float("nan")
        with self.assertRaises(ValueError):
            validate_snapshot_record(nan)
        infinity = episode_record()
        infinity["path_length"] = float("inf")
        with self.assertRaises(ValueError):
            validate_episode_record(infinity)
        negative = episode_record()
        negative["coverage_90_elapsed_planning_ns"] = -1
        with self.assertRaisesRegex(ValueError, "coverage_90_elapsed"):
            validate_episode_record(negative)

    def test_memory_current_bytes_is_validated(self) -> None:
        record = memory_record()
        record["tracemalloc_current_bytes_at_stop"] = -1
        with self.assertRaisesRegex(ValueError, "current_bytes"):
            validate_memory_record(record)

    def test_phase_specific_illegal_non_null_field_is_rejected(self) -> None:
        record = episode_record()
        record["planner_wall_time_ns"] = 1
        with self.assertRaisesRegex(ValueError, "outside timing phase"):
            validate_episode_record(record)

    def test_canonical_serialization_is_deterministic_compact_and_one_lf(self) -> None:
        first = canonical_json_text({"z": 1, "a": 2})
        second = canonical_json_text({"a": 2, "z": 1})
        self.assertEqual(first, second)
        self.assertEqual(first, '{"a":2,"z":1}\n')
        self.assertEqual(first.count("\n"), 1)
        self.assertEqual(serialize_record(episode_record(), "episode").count("\n"), 1)


class InvocationWriterTests(unittest.TestCase):
    def test_writer_refuses_unsafe_id_before_creating_directory(self) -> None:
        with workspace_temp_directory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                Experiment1InvocationWriter(root, "../unsafe", manifest("safe"))
            self.assertEqual(list(root.iterdir()), [])

    def test_invalid_manifest_does_not_create_invocation_directory(self) -> None:
        with workspace_temp_directory() as directory:
            root = Path(directory)
            invalid = manifest("invalid-manifest")
            invalid["timed_repetitions"] = 7
            with self.assertRaises(ValueError):
                Experiment1InvocationWriter(root, "invalid-manifest", invalid)
            self.assertFalse((root / "runs" / "invalid-manifest").exists())

    def test_writer_refuses_overwrite(self) -> None:
        with workspace_temp_directory() as directory:
            root = Path(directory)
            Experiment1InvocationWriter(root, "no-overwrite", manifest("no-overwrite"))
            with self.assertRaises(FileExistsError):
                Experiment1InvocationWriter(root, "no-overwrite", manifest("no-overwrite"))

    def test_failed_partial_run_is_retained_and_summary_is_derived(self) -> None:
        with workspace_temp_directory() as directory:
            root = Path(directory)
            writer = Experiment1InvocationWriter(root, "partial", manifest("partial"))
            record = episode_record(invocation_id="partial")
            record["visibility_ray_count"] = 7
            writer.append("episode", record)
            summary = writer.finalize("FAILED", failure_run_ids=["failure-one"])
            run = root / "runs" / "partial"
            self.assertEqual(
                {path.name for path in run.iterdir()},
                {
                    "manifest.json", "episodes.jsonl", "snapshots.jsonl",
                    "timing_repetitions.jsonl", "memory.jsonl", "summary.json",
                },
            )
            self.assertEqual(summary["work"]["overall"]["A"]["visibility_ray_count"], 7)
            self.assertIsNone(summary["decision"]["classification"])
            stored = json.loads((run / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(stored, summary)
            final_manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(final_manifest["status"], "FAILED")
            self.assertEqual(final_manifest["failure_run_ids"], ["failure-one"])
            self.assertFalse((run / ".manifest.json.tmp").exists())

    def test_append_rejects_wrong_invocation_and_preserves_empty_stream(self) -> None:
        with workspace_temp_directory() as directory:
            root = Path(directory)
            writer = Experiment1InvocationWriter(root, "right", manifest("right"))
            with self.assertRaisesRegex(ValueError, "invocation ID mismatch"):
                writer.append("episode", episode_record(invocation_id="wrong"))
            self.assertEqual(
                (root / "runs" / "right" / "episodes.jsonl").read_text(encoding="utf-8"),
                "",
            )

    def test_primary_correctness_failure_is_not_treated_as_infrastructure_null(self) -> None:
        with workspace_temp_directory() as directory:
            writer = Experiment1InvocationWriter(
                directory, "correctness", manifest("correctness")
            )
            summary = writer.finalize(
                "FAILED",
                failure_run_ids=["correctness-failure"],
                primary_correctness_failed=True,
            )
            self.assertEqual(
                summary["decision"]["classification"],
                "CORRECTNESS_REOPENED",
            )
            self.assertTrue(summary["completion"]["scientific_result_complete"])


class FailureWriterTests(unittest.TestCase):
    def _inputs(self):  # type: ignore[no-untyped-def]
        ground_truth = GroundTruthGrid.from_ascii((".",))
        belief = BeliefGrid.unknown(1, 1)
        belief.apply_observations({(0, 0): TruthState.FREE})
        failure_id = deterministic_failure_run_id(
            invocation_id="invocation",
            phase="primary_structural",
            map_id="synthetic-map",
            method="B",
            repetition_index=None,
            cycle_index=0,
            classification="target_mismatch",
        )
        metadata = {
            "experiment_version": "experiment-1-runner-v1",
            "dataset_version": "experiment-1-efficiency-v1",
            "invocation_id": "invocation",
            "failure_run_id": failure_id,
            "phase": "primary_structural",
            "map_id": "synthetic-map",
            "method": "B",
            "method_order": None,
            "method_order_position": None,
            "repetition_index": None,
            "sensor_range": 8.0,
            "cycle_index": 0,
            "robot_coordinate": [0, 0],
            "map_hash": ground_truth_hash(ground_truth),
            "belief_hash": belief_hash(belief),
            "repository_revision": REVISION,
            "failure_classification": "target_mismatch",
        }
        return ground_truth, belief, failure_id, metadata

    def test_failure_directory_has_exactly_six_final_files(self) -> None:
        with workspace_temp_directory() as directory:
            ground_truth, belief, failure_id, metadata = self._inputs()
            target = write_failure_artifact(
                output_root=directory,
                failure_run_id=failure_id,
                metadata=metadata,
                ground_truth=ground_truth,
                belief_before=belief,
                candidates=[],
                algorithm_state={},
                description=FailureDescription("target_mismatch", "forced"),
            )
            self.assertEqual({path.name for path in target.iterdir()}, FAILURE_ARTIFACT_FILES)

    def test_second_failure_write_is_refused_without_modifying_first(self) -> None:
        with workspace_temp_directory() as directory:
            ground_truth, belief, failure_id, metadata = self._inputs()
            kwargs = dict(
                output_root=directory,
                failure_run_id=failure_id,
                metadata=metadata,
                ground_truth=ground_truth,
                belief_before=belief,
                candidates=[],
                algorithm_state={},
                description=FailureDescription("target_mismatch", "forced"),
            )
            target = write_failure_artifact(**kwargs)
            before = (target / "failure.txt").read_bytes()
            with self.assertRaises(FileExistsError):
                write_failure_artifact(**kwargs)
            self.assertEqual((target / "failure.txt").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
