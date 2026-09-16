from contextlib import redirect_stderr
from dataclasses import replace
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from src.environment import GroundTruthGrid
from src.evaluation.experiment_0_logging import (
    EXPERIMENT_VERSION,
    Experiment0InvocationWriter,
)
from src.evaluation.experiment_0_runner import (
    Experiment0Case,
    Experiment0RunFailure,
    FAILURE_CLASSIFICATIONS,
    _bound_decrement_count,
    _tie_certificate_valid,
    build_preregistered_cases,
    main,
    run_case,
)
from src.planning import (
    ChangeAwareGainBoundViolation,
    ChangeAwareLazyNBV,
    PlanStatus,
    StaleScalarLazyNBV,
)
from src.planning.exhaustive_nbv import SCORE_EPSILON
from src.utils import BeliefState, ground_truth_hash
from tests.stage7_helpers import workspace_temp_directory


REVISION = "a" * 40


def smoke_case(*, cycle_limit: int = 16) -> Experiment0Case:
    grid = GroundTruthGrid.from_ascii(("." * 20,))
    return Experiment0Case(
        dataset_type="fixture",
        map_id="stage7-smoke",
        map_seed=None,
        map_hash=ground_truth_hash(grid),
        ground_truth=grid,
        start=(0, 0),
        cycle_limit=cycle_limit,
    )


def invocation_writer(root: Path, invocation_id: str) -> Experiment0InvocationWriter:
    return Experiment0InvocationWriter(
        root,
        invocation_id,
        {"mode": "stage7-smoke", "repository_revision": REVISION},
    )


class MismatchingB(StaleScalarLazyNBV):
    def plan(self, belief, robot):  # type: ignore[no-untyped-def]
        result = super().plan(belief, robot)
        if result.status is PlanStatus.SELECTED:
            alternative = next(
                record.candidate
                for record in result.candidate_records
                if record.candidate != result.selected_candidate
            )
            return replace(result, selected_candidate=alternative)
        return result


class MismatchingC(ChangeAwareLazyNBV):
    def plan(self, belief, robot):  # type: ignore[no-untyped-def]
        result = super().plan(belief, robot)
        if result.status is PlanStatus.SELECTED:
            alternative = next(
                record.candidate
                for record in result.candidate_records
                if record.candidate != result.selected_candidate
            )
            return replace(result, selected_candidate=alternative)
        return result


class ViolatingC(ChangeAwareLazyNBV):
    def plan(self, belief, robot):  # type: ignore[no-untyped-def]
        current = belief.snapshot()
        unknown = min(belief.unknown_cells())
        raise ChangeAwareGainBoundViolation(
            candidate=robot,
            old_bound=0,
            exact_visible_unknown=frozenset({unknown}),
            cached_visible_unknown=tuple(sorted(self.cache.cached_visible_unknown.items())),
            bound_counts=tuple(sorted(self.cache.bound_counts.items())),
            inverse_incidence=tuple(sorted(self.cache.inverse_incidence.items())),
            reported_known_cells=self.cache.reported_known_cells,
            previous_synchronized_snapshot=current,
            current_belief_snapshot=current,
            newly_known_delta=frozenset(),
            sensor_range=self.sensor_range,
            current_distance=0.0,
        )


class UnderboundingB(StaleScalarLazyNBV):
    @property
    def cached_gains(self):  # type: ignore[no-untyped-def]
        values = dict(super().cached_gains)
        return {candidate: 0 for candidate in values}


class UnderboundingC(ChangeAwareLazyNBV):
    def plan(self, belief, robot):  # type: ignore[no-untyped-def]
        result = super().plan(belief, robot)
        if result.status is PlanStatus.SELECTED:
            self.cache._bound_counts[result.selected_candidate] = 0
        return result


class CorruptIndexC(ChangeAwareLazyNBV):
    def plan(self, belief, robot):  # type: ignore[no-untyped-def]
        result = super().plan(belief, robot)
        if self.cache._inverse_incidence:
            first_cell = min(self.cache._inverse_incidence)
            self.cache._inverse_incidence[first_cell].clear()
        return result


class PureValidationTests(unittest.TestCase):
    def test_direct_tie_certificate_uses_frozen_total_order(self) -> None:
        candidates = ((0, 0), (0, 1))
        distances = {(0, 0): 1.0, (0, 1): 1.0}
        bounds = {(0, 0): 2, (0, 1): 2}
        score = 2 / (1.0 + SCORE_EPSILON)
        self.assertTrue(
            _tie_certificate_valid(
                status=PlanStatus.SELECTED,
                selected_candidate=(0, 0),
                selected_gain=2,
                selected_distance=1.0,
                selected_score=score,
                candidates=candidates,
                distances=distances,
                exact_candidates=frozenset({(0, 0)}),
                maintained_bounds=bounds,
            )
        )
        self.assertFalse(
            _tie_certificate_valid(
                status=PlanStatus.SELECTED,
                selected_candidate=(0, 1),
                selected_gain=2,
                selected_distance=1.0,
                selected_score=score,
                candidates=candidates,
                distances=distances,
                exact_candidates=frozenset({(0, 1)}),
                maintained_bounds=bounds,
            )
        )

    def test_terminal_tie_certificate_requires_all_current_bounds_zero(self) -> None:
        kwargs = {
            "status": PlanStatus.EXPLORATION_COMPLETE,
            "selected_candidate": None,
            "selected_gain": 0,
            "selected_distance": None,
            "selected_score": 0.0,
            "candidates": ((0, 0),),
            "distances": {(0, 0): 1.0},
            "exact_candidates": frozenset(),
        }
        self.assertTrue(_tie_certificate_valid(**kwargs, maintained_bounds={(0, 0): 0}))
        self.assertFalse(_tie_certificate_valid(**kwargs, maintained_bounds={(0, 0): 1}))

    def test_c_bound_decrement_count_uses_pre_plan_inverse_memberships(self) -> None:
        inverse = {
            (0, 0): frozenset({(1, 1), (2, 2)}),
            (0, 1): frozenset({(1, 1)}),
        }
        delta = frozenset({(0, 0), (0, 1), (9, 9)})
        self.assertEqual(_bound_decrement_count(inverse, delta), 3)
        self.assertEqual(_bound_decrement_count({}, delta), 0)

    def test_failure_classification_set_is_stable_and_complete(self) -> None:
        self.assertEqual(len(FAILURE_CLASSIFICATIONS), 18)
        for required in (
            "target_mismatch",
            "status_or_termination_mismatch",
            "b_bound_violation",
            "c_bound_violation",
            "supported_change_aware_gain_bound_violation",
            "unsupported_assumption_or_lifecycle_failure",
            "safety_limit_exhaustion",
            "malformed_cycle_record",
            "unexpected_exception",
        ):
            self.assertIn(required, FAILURE_CLASSIFICATIONS)


class SharedRunnerTests(unittest.TestCase):
    def test_synthetic_shared_run_logs_terminal_snapshot_and_invariants(self) -> None:
        with workspace_temp_directory() as directory:
            root = Path(directory)
            writer = invocation_writer(root, "stage7-smoke-success")
            cycle_count = run_case(
                case=smoke_case(),
                invocation_id="stage7-smoke-success",
                writer=writer,
                output_root=root,
                revision=REVISION,
            )
            summary = writer.finalize("PASSED")
            records = [
                json.loads(line)
                for line in writer.cycles_path.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(cycle_count, len(records))
            self.assertGreater(len(records), 1)
            self.assertEqual(records[-1]["a_status"], "EXPLORATION_COMPLETE")
            self.assertIsNone(records[-1]["a_selected_candidate"])
            self.assertTrue(all(record["agreement_all"] for record in records))
            self.assertTrue(
                all(record["sequence_prefix_agreement_all"] for record in records)
            )
            self.assertTrue(all(record["bound_valid_b"] for record in records))
            self.assertTrue(all(record["bound_valid_c"] for record in records))
            self.assertTrue(
                all(record["tie_certificate_valid_b"] for record in records)
            )
            self.assertTrue(
                all(record["tie_certificate_valid_c"] for record in records)
            )
            self.assertTrue(
                all(record["cache_index_invariant_valid_c"] for record in records)
            )
            self.assertTrue(
                all(
                    record["c_cached_membership_count"]
                    == record["c_inverse_membership_count"]
                    for record in records
                )
            )
            self.assertEqual(records[0]["c_bound_decrement_count"], 0)
            self.assertEqual(summary["status"], "PASSED")
            self.assertFalse((root / "failures").exists())

    def test_forced_b_target_mismatch_writes_evidence_before_movement(self) -> None:
        with workspace_temp_directory() as directory:
            root = Path(directory)
            writer = invocation_writer(root, "stage7-smoke-b-mismatch")
            movements: list[str] = []
            with self.assertRaises(Experiment0RunFailure) as caught:
                run_case(
                    case=smoke_case(),
                    invocation_id="stage7-smoke-b-mismatch",
                    writer=writer,
                    output_root=root,
                    revision=REVISION,
                    planner_b=MismatchingB(8),
                    before_movement=lambda: movements.append("moved"),
                )
            self.assertEqual(caught.exception.classification, "target_mismatch")
            self.assertEqual(movements, [])
            self.assertTrue(caught.exception.artifact_path.is_dir())
            candidates = json.loads(
                (caught.exception.artifact_path / "candidates.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(candidates)
            self.assertTrue(all(set(record) == {"candidate", "distance", "a", "b", "c"} for record in candidates))
            state = json.loads(
                (caught.exception.artifact_path / "algorithm_state.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertIn("cached_gains", state["b"])
            self.assertIn("inverse_incidence", state["c"])

    def test_forced_c_target_mismatch_stops_before_movement(self) -> None:
        with workspace_temp_directory() as directory:
            root = Path(directory)
            writer = invocation_writer(root, "stage7-smoke-c-mismatch")
            movements: list[str] = []
            with self.assertRaises(Experiment0RunFailure) as caught:
                run_case(
                    case=smoke_case(),
                    invocation_id="stage7-smoke-c-mismatch",
                    writer=writer,
                    output_root=root,
                    revision=REVISION,
                    planner_c=MismatchingC(8),
                    before_movement=lambda: movements.append("moved"),
                )
            self.assertEqual(caught.exception.classification, "target_mismatch")
            self.assertEqual(movements, [])

    def test_supported_c_bound_violation_preserves_diagnostic_state(self) -> None:
        with workspace_temp_directory() as directory:
            root = Path(directory)
            writer = invocation_writer(root, "stage7-smoke-c-bound")
            movements: list[str] = []
            with self.assertRaises(Experiment0RunFailure) as caught:
                run_case(
                    case=smoke_case(),
                    invocation_id="stage7-smoke-c-bound",
                    writer=writer,
                    output_root=root,
                    revision=REVISION,
                    planner_c=ViolatingC(8),
                    before_movement=lambda: movements.append("moved"),
                )
            self.assertEqual(
                caught.exception.classification,
                "supported_change_aware_gain_bound_violation",
            )
            self.assertEqual(movements, [])
            state = json.loads(
                (caught.exception.artifact_path / "algorithm_state.json").read_text(
                    encoding="utf-8"
                )
            )
            diagnostic = state["change_aware_gain_bound_violation"]
            self.assertEqual(diagnostic["old_bound"], 0)
            self.assertEqual(diagnostic["exact_gain"], 1)
            self.assertEqual(diagnostic["exact_visible_unknown"], [[0, 9]])

    def test_external_b_bound_validation_detects_underbound(self) -> None:
        with workspace_temp_directory() as directory:
            root = Path(directory)
            writer = invocation_writer(root, "stage7-smoke-b-underbound")
            movements: list[str] = []
            with self.assertRaises(Experiment0RunFailure) as caught:
                run_case(
                    case=smoke_case(),
                    invocation_id="stage7-smoke-b-underbound",
                    writer=writer,
                    output_root=root,
                    revision=REVISION,
                    planner_b=UnderboundingB(8),
                    before_movement=lambda: movements.append("moved"),
                )
            self.assertEqual(caught.exception.classification, "b_bound_violation")
            self.assertEqual(movements, [])

    def test_external_c_bound_validation_detects_underbound(self) -> None:
        with workspace_temp_directory() as directory:
            root = Path(directory)
            writer = invocation_writer(root, "stage7-smoke-c-underbound")
            movements: list[str] = []
            with self.assertRaises(Experiment0RunFailure) as caught:
                run_case(
                    case=smoke_case(),
                    invocation_id="stage7-smoke-c-underbound",
                    writer=writer,
                    output_root=root,
                    revision=REVISION,
                    planner_c=UnderboundingC(8),
                    before_movement=lambda: movements.append("moved"),
                )
            self.assertEqual(caught.exception.classification, "c_bound_violation")
            self.assertEqual(movements, [])

    def test_external_c_cache_validation_detects_inverse_corruption(self) -> None:
        with workspace_temp_directory() as directory:
            root = Path(directory)
            writer = invocation_writer(root, "stage7-smoke-c-index")
            movements: list[str] = []
            with self.assertRaises(Experiment0RunFailure) as caught:
                run_case(
                    case=smoke_case(),
                    invocation_id="stage7-smoke-c-index",
                    writer=writer,
                    output_root=root,
                    revision=REVISION,
                    planner_c=CorruptIndexC(8),
                    before_movement=lambda: movements.append("moved"),
                )
            self.assertEqual(
                caught.exception.classification,
                "c_cache_index_invariant_failure",
            )
            self.assertEqual(movements, [])

    def test_safety_limit_exhaustion_writes_failure_artifact(self) -> None:
        with workspace_temp_directory() as directory:
            root = Path(directory)
            writer = invocation_writer(root, "stage7-smoke-limit")
            with self.assertRaises(Experiment0RunFailure) as caught:
                run_case(
                    case=smoke_case(cycle_limit=0),
                    invocation_id="stage7-smoke-limit",
                    writer=writer,
                    output_root=root,
                    revision=REVISION,
                )
            self.assertEqual(caught.exception.classification, "safety_limit_exhaustion")
            metadata = json.loads(
                (caught.exception.artifact_path / "metadata.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(metadata["cycle_index"], 0)

    def test_malformed_record_writes_failure_before_movement(self) -> None:
        def remove_field(record):  # type: ignore[no-untyped-def]
            malformed = dict(record)
            del malformed["belief_hash"]
            return malformed

        with workspace_temp_directory() as directory:
            root = Path(directory)
            writer = invocation_writer(root, "stage7-smoke-malformed")
            movements: list[str] = []
            with self.assertRaises(Experiment0RunFailure) as caught:
                run_case(
                    case=smoke_case(),
                    invocation_id="stage7-smoke-malformed",
                    writer=writer,
                    output_root=root,
                    revision=REVISION,
                    record_transform=remove_field,
                    before_movement=lambda: movements.append("moved"),
                )
            self.assertEqual(caught.exception.classification, "malformed_cycle_record")
            self.assertEqual(movements, [])
            self.assertEqual(writer.cycles_path.read_text(encoding="utf-8"), "")


class FormalModeGuardTests(unittest.TestCase):
    def test_frozen_builder_reverifies_exact_fixture_then_random_order_only(self) -> None:
        cases = build_preregistered_cases()
        self.assertEqual(len(cases), 67)
        self.assertEqual(
            [case.map_id for case in cases[:7]],
            [
                "open",
                "single_room",
                "corridor",
                "dead_end",
                "separated_rooms",
                "clutter",
                "maze_like",
            ],
        )
        self.assertEqual(cases[7].map_id, "random-000")
        self.assertEqual(cases[-1].map_id, "random-059")
        self.assertTrue(all(case.map_seed is None for case in cases[:7]))
        self.assertTrue(all(case.map_seed is not None for case in cases[7:]))

    def test_cli_without_explicit_execution_gate_never_invokes_formal_runner(self) -> None:
        with workspace_temp_directory() as directory:
            with patch(
                "src.evaluation.experiment_0_runner.run_preregistered_experiment"
            ) as formal_run:
                with redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as caught:
                        main(
                            [
                                "--invocation-id",
                                "stage7-must-not-run",
                                "--output-root",
                                directory,
                            ]
                        )
                self.assertEqual(caught.exception.code, 2)
                formal_run.assert_not_called()
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_experiment_version_is_frozen_runner_v1(self) -> None:
        self.assertEqual(EXPERIMENT_VERSION, "experiment-0-runner-v1")


if __name__ == "__main__":
    unittest.main()
