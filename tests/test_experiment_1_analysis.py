from copy import deepcopy
import unittest
from unittest.mock import patch

from src.evaluation.experiment_1_analysis import (
    aggregate_bound_slack,
    aggregate_work,
    build_summary,
    canonical_path_hash,
    canonical_sequence_hash,
    classify_decision,
    linear_quantile,
    nearest_rank_percentile,
    paired_bootstrap_interval,
    path_coverage_sanity,
    safe_ratio,
    sensitivity_summary,
    summarize_six_timings,
    summarize_timing,
)
from tests.stage10_helpers import episode_record, snapshot_record, timing_record


WORK = (
    "visibility_ray_count",
    "visibility_supercover_cell_count",
    "visibility_interior_probe_count",
)


def decision(
    *, correct=True, b=(10, 20, 30), c=(5, 10, 15), interval=(0.8, 0.9),
    complete=True, memory=None, sensitivity=None,
):  # type: ignore[no-untyped-def]
    return classify_decision(
        primary_correctness_valid=correct,
        b_work=dict(zip(WORK, b)),
        c_work=dict(zip(WORK, c)),
        c_over_b_interval=interval,
        invocation_complete=complete,
        memory=memory,
        sensitivity=sensitivity,
    )


class DeterministicAnalysisTests(unittest.TestCase):
    def test_quantile_conventions_are_frozen(self) -> None:
        self.assertEqual(linear_quantile([0, 10, 20, 30], 0.25), 7.5)
        self.assertEqual(nearest_rank_percentile(list(range(1, 21))), 19.0)
        summary = summarize_six_timings([1, 2, 3, 4, 5, 100])
        self.assertEqual(summary["median"], 3.5)
        self.assertEqual(summary["q1"], 2.25)
        self.assertEqual(summary["q3"], 4.75)
        self.assertEqual(summary["minimum"], 1)
        self.assertEqual(summary["maximum"], 100)

    def test_path_and_sequence_hashes_are_canonical_and_stop_is_explicit(self) -> None:
        self.assertEqual(canonical_path_hash([(0, 0)]), canonical_path_hash([[0, 0]]))
        self.assertNotEqual(
            canonical_sequence_hash([(0, 0), None]),
            canonical_sequence_hash([(0, 0)]),
        )

    def test_exact_work_aggregates_and_ratios(self) -> None:
        records = []
        for method, amount in (("A", 20), ("B", 10), ("C", 5)):
            record = episode_record(method=method)
            record["exact_gain_evaluation_count"] = amount
            for field in WORK:
                record[field] = amount
            records.append(record)
        result = aggregate_work(records)
        self.assertEqual(result["overall"]["A"]["visibility_ray_count"], 20)
        self.assertEqual(result["per_map"]["synthetic-map"]["C"]["visibility_ray_count"], 5)
        self.assertEqual(result["per_size"]["20"]["B"]["visibility_ray_count"], 10)
        self.assertEqual(result["per_density"]["sparse"]["A"]["visibility_ray_count"], 20)
        self.assertEqual(result["overall_ratios"]["C/B"]["visibility_ray_count"], 0.5)

    def test_zero_denominator_is_null(self) -> None:
        self.assertIsNone(safe_ratio(1, 0))
        records = [episode_record(method=method) for method in "ABC"]
        records[2]["visibility_ray_count"] = 1
        result = aggregate_work(records)
        self.assertIsNone(result["overall_ratios"]["C/B"]["visibility_ray_count"])
        self.assertEqual(
            result["zero_denominator_counts"]["C/B"]["visibility_ray_count"],
            1,
        )

    def test_bound_slack_uses_retained_observations_and_nearest_rank(self) -> None:
        records = []
        for method in ("B", "C"):
            record = snapshot_record(method=method)
            record["bound_measurements"] = [
                {
                    "method": method,
                    "candidate": [0, index],
                    "upper_bound": value,
                    "a_exact_gain": 0,
                    "absolute_slack": value,
                    "normalized_slack": 1.0,
                    "tight": value == 0,
                }
                for index, value in enumerate(range(1, 21))
            ]
            records.append(record)
        result = aggregate_bound_slack(records)
        self.assertEqual(result["B"]["observation_count"], 20)
        self.assertEqual(result["B"]["p95_absolute_slack"], 19.0)
        self.assertEqual(result["C"]["tight_bound_fraction"], 0.0)

    def test_warmup_is_retained_but_excluded(self) -> None:
        records = []
        for method in "ABC":
            warmup = timing_record(method=method)
            warmup.update(
                repetition_index=0,
                timed=False,
                method_order=["A", "B", "C"],
                method_order_position="ABC".index(method),
                warmup_discarded=True,
                episode_planner_wall_time_ns=1_000_000,
            )
            records.append(warmup)
            records.extend(
                timing_record(method=method, repetition=i, wall_ns=10 + i)
                for i in range(1, 7)
            )
        with patch(
            "src.evaluation.experiment_1_analysis.paired_bootstrap_interval",
            return_value=(0.9, 1.1),
        ):
            result = summarize_timing(records)
        self.assertEqual(result["warmup_record_count"], 3)
        self.assertTrue(result["warmups_excluded"])
        self.assertEqual(result["per_map_method"]["synthetic-map"]["A"]["median"], 13.5)

    def test_fewer_than_six_valid_repetitions_is_incomplete(self) -> None:
        records = [
            timing_record(method=method, repetition=i, valid=not (method == "C" and i == 6))
            for method in "ABC" for i in range(1, 7)
        ]
        result = summarize_timing(records)
        self.assertFalse(result["complete"])
        self.assertIn(["synthetic-map", "C"], result["incomplete_map_methods"])

    def test_duplicate_repetition_cannot_substitute_for_exact_six(self) -> None:
        records = [
            timing_record(method=method, repetition=i)
            for method in "ABC" for i in range(1, 7)
        ]
        records[-1]["repetition_index"] = 5
        result = summarize_timing(records)
        self.assertFalse(result["complete"])
        self.assertIn(["synthetic-map", "C"], result["incomplete_map_methods"])

    def test_absent_timing_is_incomplete_not_division_by_zero(self) -> None:
        result = summarize_timing([])
        self.assertFalse(result["complete"])
        self.assertEqual(result["comparisons"], {})

    def test_bootstrap_is_reproducible_and_does_not_touch_global_rng(self) -> None:
        first = paired_bootstrap_interval([0.8, 0.9, 1.0])
        second = paired_bootstrap_interval([0.8, 0.9, 1.0])
        self.assertEqual(first, second)

    def test_timing_bootstrap_unit_is_one_ratio_per_map(self) -> None:
        records = [
            timing_record(
                map_id=map_id,
                method=method,
                repetition=repetition,
                wall_ns={"A": 30, "B": 20, "C": 10}[method],
            )
            for map_id in ("map-1", "map-2")
            for method in "ABC"
            for repetition in range(1, 7)
        ]
        lengths = []

        def capture(values):  # type: ignore[no-untyped-def]
            lengths.append(len(values))
            return 0.5, 0.5

        with patch(
            "src.evaluation.experiment_1_analysis.paired_bootstrap_interval",
            side_effect=capture,
        ):
            result = summarize_timing(records)
        self.assertTrue(result["complete"])
        self.assertEqual(lengths, [2, 2, 2])

    def test_path_coverage_equality_and_sensitivity_are_descriptive(self) -> None:
        records = [episode_record(method=method) for method in "ABC"]
        sanity = path_coverage_sanity(records)
        self.assertTrue(sanity["all_shared_conditions_equal"])
        sensitivity_records = []
        for method in "ABC":
            record = episode_record(method=method, phase="range_sensitivity")
            sensitivity_records.append(record)
        sensitivity = sensitivity_summary(sensitivity_records)
        self.assertFalse(sensitivity["affects_primary_decision"])

    def test_incomplete_summary_has_no_scientific_decision(self) -> None:
        summary = build_summary(
            invocation_id="failed",
            episode_records=[],
            snapshot_records=[],
            timing_records=[],
            memory_records=[],
            invocation_complete=False,
            invocation_status="FAILED",
        )
        self.assertIsNone(summary["decision"]["classification"])
        self.assertFalse(summary["decision"]["available"])


class DecisionRuleTests(unittest.TestCase):
    def test_strict_work_gate_equality_causes_drop(self) -> None:
        self.assertEqual(decision(c=(5, 20, 15)), "DROP")

    def test_all_lower_and_interval_below_one_causes_go(self) -> None:
        self.assertEqual(decision(interval=(0.7, 0.99)), "GO")

    def test_crossing_interval_causes_modify(self) -> None:
        self.assertEqual(decision(interval=(0.9, 1.1)), "MODIFY")

    def test_lower_equal_one_causes_modify(self) -> None:
        self.assertEqual(decision(interval=(1.0, 1.2)), "MODIFY")

    def test_upper_equal_one_causes_modify(self) -> None:
        self.assertEqual(decision(interval=(0.8, 1.0)), "MODIFY")

    def test_interval_above_one_causes_drop(self) -> None:
        self.assertEqual(decision(interval=(1.01, 1.2)), "DROP")

    def test_reversed_interval_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "interval ordering"):
            decision(interval=(1.2, 0.8))

    def test_correctness_failure_dominates_favorable_performance(self) -> None:
        self.assertEqual(decision(correct=False, interval=(0.1, 0.2)), "CORRECTNESS_REOPENED")

    def test_memory_and_sensitivity_cannot_override(self) -> None:
        baseline = decision(interval=(0.7, 0.9))
        altered = decision(
            interval=(0.7, 0.9),
            memory={"bad": True},
            sensitivity={"bad": True},
        )
        self.assertEqual(baseline, altered)

    def test_incomplete_infrastructure_has_null_classification(self) -> None:
        self.assertIsNone(decision(complete=False))

    def test_observed_primary_correctness_failure_survives_incomplete_run(self) -> None:
        self.assertEqual(
            classify_decision(
                primary_correctness_valid=False,
                b_work=dict(zip(WORK, (10, 20, 30))),
                c_work=dict(zip(WORK, (5, 10, 15))),
                c_over_b_interval=None,
                invocation_complete=False,
                correctness_failure_observed=True,
            ),
            "CORRECTNESS_REOPENED",
        )


if __name__ == "__main__":
    unittest.main()
