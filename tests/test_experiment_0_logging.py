import json
import math
from pathlib import Path
import unittest

from src.evaluation.experiment_0_logging import (
    CYCLE_RECORD_FIELDS,
    EXPERIMENT_VERSION,
    Experiment0InvocationWriter,
    serialize_cycle_record,
    validate_cycle_record,
)
from tests.stage7_helpers import workspace_temp_directory


MAP_HASH = "1" * 64
BELIEF_HASH = "2" * 64


def valid_cycle_record(*, terminal: bool = False) -> dict[str, object]:
    status = "EXPLORATION_COMPLETE" if terminal else "SELECTED"
    candidate = None if terminal else [1, 2]
    gain = 0 if terminal else 3
    distance = None if terminal else 1.0
    score = 0.0 if terminal else 2.999999997
    eligible = 2
    return {
        "experiment_version": EXPERIMENT_VERSION,
        "dataset_type": "fixture",
        "map_id": "stage7-smoke",
        "map_seed": None,
        "map_hash": MAP_HASH,
        "cycle_index": 0,
        "robot_coordinate": [1, 1],
        "belief_hash": BELIEF_HASH,
        "unknown_count": 4,
        "known_free_count": 3,
        "known_occupied_count": 2,
        "eligible_candidate_count": eligible,
        "a_status": status,
        "a_selected_candidate": candidate,
        "a_selected_gain": gain,
        "a_selected_distance": distance,
        "a_selected_score": score,
        "a_exact_gain_evaluation_count": eligible,
        "b_status": status,
        "b_selected_candidate": candidate,
        "b_selected_gain": gain,
        "b_selected_distance": distance,
        "b_selected_score": score,
        "b_exact_gain_evaluation_count": 1,
        "b_bound_only_candidate_count": 1,
        "b_certificate_reason": "tie_aware_rank_dominance",
        "c_status": status,
        "c_selected_candidate": candidate,
        "c_selected_gain": gain,
        "c_selected_distance": distance,
        "c_selected_score": score,
        "c_exact_gain_evaluation_count": 1,
        "c_bound_only_candidate_count": 1,
        "c_bound_decrement_count": 2,
        "c_cached_membership_count": 5,
        "c_inverse_membership_count": 5,
        "c_certificate_reason": "tie_aware_rank_dominance",
        "agreement_a_b": True,
        "agreement_a_c": True,
        "agreement_b_c": True,
        "agreement_all": True,
        "sequence_prefix_agreement_all": True,
        "bound_valid_b": True,
        "bound_valid_c": True,
        "tie_certificate_valid_b": True,
        "tie_certificate_valid_c": True,
        "cache_index_invariant_valid_c": True,
    }


class CycleRecordTests(unittest.TestCase):
    def test_exact_frozen_field_names_and_canonical_serialization(self) -> None:
        record = valid_cycle_record()
        self.assertEqual(tuple(record), CYCLE_RECORD_FIELDS)
        serialized = serialize_cycle_record(record, map_cell_count=9)
        self.assertTrue(serialized.endswith("\n"))
        self.assertEqual(serialized.count("\n"), 1)
        self.assertNotIn(": ", serialized)
        self.assertEqual(json.loads(serialized), record)

    def test_coordinate_and_status_json_conversion(self) -> None:
        record = valid_cycle_record()
        decoded = json.loads(serialize_cycle_record(record, map_cell_count=9))
        self.assertEqual(decoded["robot_coordinate"], [1, 1])
        self.assertEqual(decoded["a_selected_candidate"], [1, 2])
        self.assertEqual(decoded["a_status"], "SELECTED")

    def test_nonfinite_number_is_rejected(self) -> None:
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                record = valid_cycle_record()
                record["a_selected_score"] = value
                with self.assertRaises(ValueError):
                    validate_cycle_record(record, map_cell_count=9)

    def test_belief_count_consistency_is_required(self) -> None:
        record = valid_cycle_record()
        record["unknown_count"] = 5
        with self.assertRaisesRegex(ValueError, "belief counts"):
            validate_cycle_record(record, map_cell_count=9)

    def test_agreement_flags_are_recomputed_from_status_and_target(self) -> None:
        record = valid_cycle_record()
        record["b_selected_candidate"] = [1, 3]
        with self.assertRaisesRegex(ValueError, "agreement_a_b"):
            validate_cycle_record(record, map_cell_count=9)

    def test_sequence_prefix_flag_must_be_boolean(self) -> None:
        record = valid_cycle_record()
        record["sequence_prefix_agreement_all"] = None
        with self.assertRaisesRegex(ValueError, "sequence_prefix"):
            validate_cycle_record(record, map_cell_count=9)

    def test_c_membership_mismatch_requires_false_invariant_flag(self) -> None:
        record = valid_cycle_record()
        record["c_inverse_membership_count"] = 4
        with self.assertRaisesRegex(ValueError, "cache_index"):
            validate_cycle_record(record, map_cell_count=9)
        record["cache_index_invariant_valid_c"] = False
        validate_cycle_record(record, map_cell_count=9)

    def test_terminal_snapshot_serializes_with_null_target_and_distance(self) -> None:
        record = valid_cycle_record(terminal=True)
        decoded = json.loads(serialize_cycle_record(record, map_cell_count=9))
        self.assertEqual(decoded["a_status"], "EXPLORATION_COMPLETE")
        self.assertIsNone(decoded["a_selected_candidate"])
        self.assertIsNone(decoded["a_selected_distance"])
        self.assertEqual(decoded["a_selected_gain"], 0)

    def test_status_candidate_semantics_reject_selected_null(self) -> None:
        record = valid_cycle_record()
        record["a_selected_candidate"] = None
        record["agreement_a_b"] = False
        record["agreement_a_c"] = False
        record["agreement_all"] = False
        with self.assertRaisesRegex(ValueError, "status/candidate"):
            validate_cycle_record(record, map_cell_count=9)


class InvocationWriterTests(unittest.TestCase):
    def test_nonoverwriting_run_layout_and_derived_summary(self) -> None:
        with workspace_temp_directory() as directory:
            root = Path(directory)
            writer = Experiment0InvocationWriter(
                root,
                "stage7-smoke-invocation",
                {"mode": "synthetic"},
            )
            writer.append_cycle(valid_cycle_record(), map_cell_count=9)
            writer.append_cycle(valid_cycle_record(terminal=True), map_cell_count=9)
            summary = writer.finalize("PASSED")
            self.assertEqual(summary["planning_snapshot_count"], 2)
            self.assertEqual(summary["terminal_snapshot_count"], 1)
            self.assertEqual(summary["a_exact_gain_evaluation_count"], 4)
            self.assertEqual(
                {path.name for path in writer.directory.iterdir()},
                {"cycles.jsonl", "manifest.json", "summary.json"},
            )
            with self.assertRaises(FileExistsError):
                Experiment0InvocationWriter(
                    root,
                    "stage7-smoke-invocation",
                    {"mode": "synthetic"},
                )


if __name__ == "__main__":
    unittest.main()
