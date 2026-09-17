from contextlib import redirect_stderr
from dataclasses import replace
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from src.evaluation import experiment_1_runner as runner
from src.evaluation.experiment_1_logging import Experiment1InvocationWriter
from src.evaluation.experiment_1_runner import (
    Experiment1RunFailure,
    MethodEpisodeResult,
    execute_timing_schedule,
    main,
    run_reference_method_episode,
    run_shared_structural_case,
    timed_planner_call,
)
from src.planning import (
    ChangeAwareGainBoundViolation,
    ChangeAwareLazyNBV,
    PlanStatus,
    StaleScalarLazyNBV,
)
from src.utils import TruthState
from tests.stage10_helpers import REVISION, manifest, smoke_case
from tests.stage7_helpers import workspace_temp_directory


class UnderboundingB(StaleScalarLazyNBV):
    @property
    def cached_gains(self):  # type: ignore[no-untyped-def]
        return {candidate: 0 for candidate in super().cached_gains}


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
            first = min(self.cache._inverse_incidence)
            self.cache._inverse_incidence[first].clear()
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


class MutatingB(StaleScalarLazyNBV):
    def plan(self, belief, robot):  # type: ignore[no-untyped-def]
        result = super().plan(belief, robot)
        belief.apply_observations({max(belief.unknown_cells()): TruthState.FREE})
        return result


class RejectingWriter:
    def append(self, kind, record):  # type: ignore[no-untyped-def]
        raise ValueError(f"forced malformed {kind}")


class SharedStructuralRunnerTests(unittest.TestCase):
    def _run(self, root: Path, **kwargs):  # type: ignore[no-untyped-def]
        return run_shared_structural_case(
            case=smoke_case(),
            invocation_id="synthetic",
            phase="anchor_structural",
            output_root=root,
            revision=REVISION,
            **kwargs,
        )

    def test_shared_snapshot_agreement_terminal_and_structural_metrics(self) -> None:
        with workspace_temp_directory() as directory:
            result = self._run(Path(directory))
            self.assertEqual(len(result.episode_records), 3)
            self.assertEqual(result.reference.snapshots[-1].status, "EXPLORATION_COMPLETE")
            by_cycle = {}
            for record in result.snapshot_records:
                by_cycle.setdefault(record["cycle_index"], []).append(record)
            for records in by_cycle.values():
                self.assertEqual({record["belief_hash"] for record in records}, {records[0]["belief_hash"]})
                self.assertEqual({tuple(record["robot_coordinate"]) for record in records}, {tuple(records[0]["robot_coordinate"])})
                self.assertTrue(all(record["agreement_all"] for record in records))
                self.assertTrue(all(record["sequence_prefix_agreement_all"] for record in records))
            c = next(record for record in result.episode_records if record["method"] == "C")
            self.assertEqual(
                c["c_exact_cache_installation_count"] + c["c_exact_cache_replacement_count"],
                c["exact_gain_evaluation_count"],
            )
            self.assertEqual(
                c["c_peak_cached_membership_count"],
                c["c_peak_inverse_membership_count"],
            )

    def _target_mismatch(self, target_method: str):
        def transform(method, result):  # type: ignore[no-untyped-def]
            if method == target_method and result.status is PlanStatus.SELECTED:
                alternative = next(
                    record.candidate for record in result.candidate_records
                    if record.candidate != result.selected_candidate
                )
                return replace(result, selected_candidate=alternative)
            return result
        return transform

    def test_forced_b_target_mismatch_stops_before_movement(self) -> None:
        with workspace_temp_directory() as directory:
            movements = []
            with self.assertRaises(Experiment1RunFailure) as caught:
                self._run(
                    Path(directory), result_transform=self._target_mismatch("B"),
                    before_movement=lambda: movements.append(True),
                )
            self.assertEqual(caught.exception.classification, "target_mismatch")
            self.assertEqual(movements, [])

    def test_forced_c_target_mismatch_stops_before_movement(self) -> None:
        with workspace_temp_directory() as directory:
            movements = []
            with self.assertRaises(Experiment1RunFailure) as caught:
                self._run(
                    Path(directory), result_transform=self._target_mismatch("C"),
                    before_movement=lambda: movements.append(True),
                )
            self.assertEqual(caught.exception.classification, "target_mismatch")
            self.assertEqual(movements, [])

    def test_selected_path_mismatch_is_detected(self) -> None:
        def transform(method, result):  # type: ignore[no-untyped-def]
            if method == "B" and result.status is PlanStatus.SELECTED:
                return replace(result, selected_path=())
            return result
        with workspace_temp_directory() as directory:
            with self.assertRaises(Experiment1RunFailure) as caught:
                self._run(Path(directory), result_transform=transform)
            self.assertEqual(caught.exception.classification, "selected_value_or_path_mismatch")

    def test_candidate_domain_mismatch_is_detected(self) -> None:
        def transform(method, result):  # type: ignore[no-untyped-def]
            if method == "B" and result.candidate_records:
                return replace(result, candidate_records=result.candidate_records[:-1])
            return result
        with workspace_temp_directory() as directory:
            with self.assertRaises(Experiment1RunFailure) as caught:
                self._run(Path(directory), result_transform=transform)
            self.assertEqual(caught.exception.classification, "candidate_domain_or_distance_mismatch")

    def test_external_b_underbound_is_detected(self) -> None:
        with workspace_temp_directory() as directory:
            with patch.object(runner, "StaleScalarLazyNBV", UnderboundingB):
                with self.assertRaises(Experiment1RunFailure) as caught:
                    self._run(Path(directory))
            self.assertEqual(caught.exception.classification, "b_bound_violation")

    def test_external_c_underbound_is_detected(self) -> None:
        with workspace_temp_directory() as directory:
            with patch.object(runner, "ChangeAwareLazyNBV", UnderboundingC):
                with self.assertRaises(Experiment1RunFailure) as caught:
                    self._run(Path(directory))
            self.assertEqual(caught.exception.classification, "c_bound_violation")

    def test_c_inverse_corruption_is_detected(self) -> None:
        with workspace_temp_directory() as directory:
            with patch.object(runner, "ChangeAwareLazyNBV", CorruptIndexC):
                with self.assertRaises(Experiment1RunFailure) as caught:
                    self._run(Path(directory))
            self.assertEqual(caught.exception.classification, "c_cache_index_invariant_failure")

    def test_supported_change_aware_violation_preserves_six_file_evidence(self) -> None:
        with workspace_temp_directory() as directory:
            with patch.object(runner, "ChangeAwareLazyNBV", ViolatingC):
                with self.assertRaises(Experiment1RunFailure) as caught:
                    self._run(Path(directory))
            self.assertEqual(
                caught.exception.classification,
                "supported_change_aware_gain_bound_violation",
            )
            self.assertEqual(len(list(caught.exception.artifact_path.iterdir())), 6)

    def test_cycle_limit_exhaustion_creates_failure_evidence(self) -> None:
        with workspace_temp_directory() as directory:
            with self.assertRaises(Experiment1RunFailure) as caught:
                run_shared_structural_case(
                    case=smoke_case(cycle_limit=0), invocation_id="limit",
                    phase="anchor_structural", output_root=directory,
                    revision=REVISION,
                )
            self.assertEqual(caught.exception.classification, "cycle_limit_exhaustion")

    def test_malformed_measurement_fails_before_movement(self) -> None:
        with workspace_temp_directory() as directory:
            movements = []
            with self.assertRaises(Experiment1RunFailure) as caught:
                self._run(
                    Path(directory), writer=RejectingWriter(),
                    before_movement=lambda: movements.append(True),
                )
            self.assertEqual(caught.exception.classification, "malformed_measurement_record")
            self.assertEqual(movements, [])

    def test_instrumentation_mismatch_fails(self) -> None:
        def transform(method, result):  # type: ignore[no-untyped-def]
            if method == "A":
                return replace(
                    result,
                    exact_gain_evaluations=result.exact_gain_evaluations + 1,
                )
            return result
        with workspace_temp_directory() as directory:
            with self.assertRaises(Experiment1RunFailure) as caught:
                self._run(Path(directory), result_transform=transform)
            self.assertEqual(caught.exception.classification, "instrumentation_mismatch")

    def test_planner_belief_mutation_is_detected(self) -> None:
        with workspace_temp_directory() as directory:
            with patch.object(runner, "StaleScalarLazyNBV", MutatingB):
                with self.assertRaises(Experiment1RunFailure) as caught:
                    self._run(Path(directory))
            self.assertEqual(
                caught.exception.classification,
                "unsupported_lifecycle_or_configuration",
            )

    def test_real_writer_accepts_synthetic_shared_records(self) -> None:
        with workspace_temp_directory() as directory:
            root = Path(directory)
            writer = Experiment1InvocationWriter(root, "writer-run", manifest("writer-run"))
            run_shared_structural_case(
                case=smoke_case(), invocation_id="writer-run",
                phase="anchor_structural", output_root=root,
                revision=REVISION, writer=writer,
            )
            summary = writer.finalize("FAILED")
            self.assertIsNone(summary["decision"]["classification"])


class TimingAndLifecycleTests(unittest.TestCase):
    def _reference(self, root: Path):  # type: ignore[no-untyped-def]
        return run_shared_structural_case(
            case=smoke_case(), invocation_id="reference",
            phase="anchor_structural", output_root=root,
            revision=REVISION,
        ).reference

    def test_timer_boundary_is_immediately_around_callable(self) -> None:
        events = []
        wall_values = iter((100, 160))
        process_values = iter((200, 230))
        def wall():  # type: ignore[no-untyped-def]
            events.append("wall")
            return next(wall_values)
        def process():  # type: ignore[no-untyped-def]
            events.append("process")
            return next(process_values)
        def planner():  # type: ignore[no-untyped-def]
            events.append("planner")
            return "result"
        result, wall_ns, process_ns = timed_planner_call(
            planner, wall_clock_ns=wall, process_clock_ns=process
        )
        self.assertEqual(events, ["wall", "process", "planner", "process", "wall"])
        self.assertEqual((result, wall_ns, process_ns), ("result", 60, 30))

    def test_timing_schedule_has_one_warmup_and_exact_six_orders(self) -> None:
        calls = []
        def fake_episode(**kwargs):  # type: ignore[no-untyped-def]
            calls.append(kwargs)
            return MethodEpisodeResult({}, ())
        with workspace_temp_directory() as directory:
            reference = self._reference(Path(directory))
            results = execute_timing_schedule(
                case=smoke_case(), reference=reference,
                invocation_id="schedule", output_root=directory,
                revision=REVISION, episode_runner=fake_episode,
            )
        self.assertEqual(len(results), 21)
        self.assertEqual([call["method"] for call in calls[:3]], ["A", "B", "C"])
        for repetition, expected in enumerate(runner.TIMING_ORDERS, start=1):
            group = calls[3 + (repetition - 1) * 3:3 + repetition * 3]
            self.assertEqual([call["method"] for call in group], list(expected))
            self.assertTrue(all(call["repetition_index"] == repetition for call in group))

    def test_primary_timing_does_not_enable_other_measurement_modes(self) -> None:
        class Clock:
            def __init__(self):
                self.value = 0
            def __call__(self):
                self.value += 10
                return self.value
        with workspace_temp_directory() as directory:
            root = Path(directory)
            reference = self._reference(root)
            with patch.object(runner, "visibility_work", side_effect=AssertionError), patch.object(
                runner, "decomposition", side_effect=AssertionError
            ), patch.object(runner.tracemalloc, "start", side_effect=AssertionError):
                result = run_reference_method_episode(
                    case=smoke_case(), method="A", reference=reference,
                    invocation_id="timing", phase="primary_timing",
                    output_root=root, revision=REVISION,
                    repetition_index=1, method_order=["A", "B", "C"],
                    method_order_position=0, wall_clock_ns=Clock(),
                    process_clock_ns=Clock(),
                )
            self.assertTrue(result.episode_record["timed"])
            self.assertIsNotNone(result.timing_record)
            self.assertIsNone(result.memory_record)

    def test_movement_occurs_after_all_planner_timers_stop(self) -> None:
        events = []
        class Clock:
            def __call__(self):
                events.append("clock")
                return len(events) * 10
        with workspace_temp_directory() as directory:
            root = Path(directory)
            reference = self._reference(root)
            run_reference_method_episode(
                case=smoke_case(), method="A", reference=reference,
                invocation_id="order", phase="primary_timing",
                output_root=root, revision=REVISION,
                repetition_index=1, method_order=["A", "B", "C"],
                method_order_position=0, wall_clock_ns=Clock(),
                process_clock_ns=Clock(),
                before_movement=lambda: events.append("move"),
            )
        for index, event in enumerate(events):
            if event == "move":
                self.assertEqual(events[index - 1], "clock")

    def test_initial_and_arrival_sensing_are_outside_timers(self) -> None:
        events = []
        original_simulator = runner.ExplorationSimulator
        original_advance = runner._advance_shared_environment
        class RecordingSimulator(original_simulator):
            def _sense_at_current_pose(self):  # type: ignore[no-untyped-def]
                events.append("sense")
                return super()._sense_at_current_pose()
        class Clock:
            def __init__(self):
                self.value = 0
            def __call__(self):
                events.append("clock")
                self.value += 10
                return self.value
        def recording_advance(simulator, path):  # type: ignore[no-untyped-def]
            value = original_advance(simulator, path)
            events.append("sense")
            return value
        with workspace_temp_directory() as directory:
            root = Path(directory)
            reference = self._reference(root)
            with patch.object(
                runner, "ExplorationSimulator", RecordingSimulator
            ), patch.object(
                runner, "_advance_shared_environment", recording_advance
            ):
                run_reference_method_episode(
                    case=smoke_case(), method="A", reference=reference,
                    invocation_id="sense-boundary", phase="primary_timing",
                    output_root=root, revision=REVISION,
                    repetition_index=1, method_order=["A", "B", "C"],
                    method_order_position=0, wall_clock_ns=Clock(),
                    process_clock_ns=Clock(),
                )
        self.assertEqual(events[0], "sense")
        chunks = " ".join(events).split("sense")
        self.assertEqual(chunks[0].strip(), "")
        for between_senses in chunks[1:-1]:
            self.assertEqual(between_senses.split(), ["clock"] * 4)
        self.assertEqual(chunks[-1].split(), ["clock"] * 4)

    def test_decomposition_records_forwarded_component_complement(self) -> None:
        with workspace_temp_directory() as directory:
            root = Path(directory)
            reference = self._reference(root)
            result = run_reference_method_episode(
                case=smoke_case(), method="A", reference=reference,
                invocation_id="decomposition", phase="decomposition",
                output_root=root, revision=REVISION,
            )
        episode = result.episode_record
        self.assertGreater(episode["distance_time_ns"], 0)
        self.assertGreater(episode["visibility_time_ns"], 0)
        self.assertEqual(episode["maintenance_time_ns"], 0)
        self.assertGreaterEqual(episode["other_time_ns"], 0)
        self.assertEqual(episode["decomposition_residual_ns"], 0)

    def test_complete_sequence_must_match_structural_reference(self) -> None:
        with workspace_temp_directory() as directory:
            root = Path(directory)
            reference = replace(self._reference(root), target_stop_sequence_hash="0" * 64)
            with self.assertRaises(Experiment1RunFailure) as caught:
                run_reference_method_episode(
                    case=smoke_case(), method="A", reference=reference,
                    invocation_id="sequence", phase="decomposition",
                    output_root=root, revision=REVISION,
                )
            self.assertEqual(caught.exception.classification, "sequence_or_termination_mismatch")

    def test_each_method_episode_constructs_fresh_environment_and_planners(self) -> None:
        created = {"sim": [], "b": [], "c": []}
        original_sim = runner.ExplorationSimulator
        original_b = runner.StaleScalarLazyNBV
        original_c = runner.ChangeAwareLazyNBV
        def sim_factory(*args, **kwargs):  # type: ignore[no-untyped-def]
            value = original_sim(*args, **kwargs)
            created["sim"].append(value)
            return value
        def b_factory(*args, **kwargs):  # type: ignore[no-untyped-def]
            value = original_b(*args, **kwargs)
            created["b"].append(value)
            return value
        def c_factory(*args, **kwargs):  # type: ignore[no-untyped-def]
            value = original_c(*args, **kwargs)
            created["c"].append(value)
            return value
        with workspace_temp_directory() as directory:
            root = Path(directory)
            reference = self._reference(root)
            with patch.object(runner, "ExplorationSimulator", side_effect=sim_factory), patch.object(
                runner, "StaleScalarLazyNBV", side_effect=b_factory
            ), patch.object(runner, "ChangeAwareLazyNBV", side_effect=c_factory):
                for _ in range(2):
                    run_reference_method_episode(
                        case=smoke_case(), method="A", reference=reference,
                        invocation_id="fresh", phase="decomposition",
                        output_root=root, revision=REVISION,
                    )
        self.assertEqual({key: len(values) for key, values in created.items()}, {"sim": 2, "b": 2, "c": 2})
        self.assertTrue(all(values[0] is not values[1] for values in created.values()))

    def test_memory_is_a_separate_non_timed_tracemalloc_pass(self) -> None:
        with workspace_temp_directory() as directory:
            root = Path(directory)
            reference = self._reference(root)
            result = run_reference_method_episode(
                case=smoke_case(), method="C", reference=reference,
                invocation_id="memory", phase="memory",
                output_root=root, revision=REVISION,
            )
            self.assertFalse(result.episode_record["timed"])
            self.assertIsNone(result.timing_record)
            self.assertEqual(
                result.memory_record["measurement_kind"],
                "python_tracemalloc_separate_non_timed_pass",
            )
            self.assertGreaterEqual(result.memory_record["tracemalloc_peak_bytes"], 0)


class FormalGuardTests(unittest.TestCase):
    def test_cli_without_explicit_gate_cannot_execute_or_create_output(self) -> None:
        with workspace_temp_directory() as directory:
            with patch.object(runner, "run_preregistered_experiment") as formal:
                with redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as caught:
                        main(["--invocation-id", "must-not-run", "--output-root", directory])
                self.assertEqual(caught.exception.code, 2)
                formal.assert_not_called()
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_imported_runner_identity_is_frozen(self) -> None:
        self.assertEqual(runner.EXPERIMENT_VERSION, "experiment-1-runner-v1")


if __name__ == "__main__":
    unittest.main()
