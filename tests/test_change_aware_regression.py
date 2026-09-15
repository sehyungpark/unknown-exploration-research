from dataclasses import dataclass
from pathlib import Path
import unittest

from src.environment.fixtures import MapFixture, deterministic_fixtures
from src.evaluation import ExplorationSimulator
from src.evaluation.random_dataset import load_config, regenerate_record
from src.planning import (
    ChangeAwareGainBoundViolation,
    ChangeAwareLazyNBV,
    PlanStatus,
)
from src.planning.motion import legal_neighbors
from src.sensing import physical_scan
from src.utils import Coord, ground_truth_hash

from tests.test_exhaustive_end_to_end import FIXTURE_CYCLE_LIMITS


CONFIG_PATH = Path("configs/experiment_0_random_maps.json")


@dataclass(frozen=True, slots=True)
class ACRunResult:
    target_and_stop_sequence: tuple[Coord | None, ...]
    planning_snapshot_count: int
    safely_skipped_exact_evaluation: bool
    bound_violations: int
    target_mismatches: int
    status_or_termination_mismatches: int
    selected_gain_mismatches: int
    selected_distance_mismatches: int
    selected_score_mismatches: int
    path_mismatches: int


def _advance_shared_environment(
    simulator: ExplorationSimulator,
    selected_path: tuple[Coord, ...],
) -> None:
    """Apply one already-agreed path and one arrival scan."""

    if not selected_path or selected_path[0] != simulator.world.robot:
        raise AssertionError("selected path must start at the shared robot")
    planning_belief = simulator.world.belief
    for source, target in zip(selected_path, selected_path[1:]):
        legal = {coord for coord, _ in legal_neighbors(planning_belief, source)}
        if target not in legal:
            raise AssertionError(f"illegal shared path step: {source} -> {target}")

    simulator.world.robot = selected_path[-1]
    observations = physical_scan(
        simulator.world.ground_truth,
        simulator.world.robot,
        simulator.sensor_range,
    )
    simulator.world.belief.apply_observations(observations)
    simulator.scan_count += 1
    simulator.snapshot_index += 1


class ACSharedSnapshotRegressionMixin:
    def run_ac_to_completion(
        self,
        fixture: MapFixture,
        cycle_limit: int,
    ) -> ACRunResult:
        simulator = ExplorationSimulator(fixture.ground_truth, fixture.start, 8)
        change_aware = ChangeAwareLazyNBV(8)
        sequence: list[Coord | None] = []
        safely_skipped = False

        for cycle_index in range(cycle_limit):
            robot_before = simulator.world.robot
            belief_before = simulator.world.belief.snapshot()
            exhaustive = simulator.plan()
            try:
                lazy = change_aware.plan(
                    simulator.world.belief,
                    simulator.world.robot,
                )
            except ChangeAwareGainBoundViolation as exc:
                raise AssertionError(
                    f"{fixture.name} cycle {cycle_index}: supported-run "
                    f"change-aware bound violation; robot={robot_before}; "
                    f"belief={belief_before!r}"
                ) from exc
            except (RuntimeError, TypeError, ValueError) as exc:
                raise AssertionError(
                    f"{fixture.name} cycle {cycle_index}: unsupported-assumption "
                    f"or lifecycle failure; robot={robot_before}; "
                    f"belief={belief_before!r}"
                ) from exc

            context = (
                f"{fixture.name} cycle {cycle_index}; robot={robot_before}; "
                f"belief={belief_before!r}; "
                f"A=(status={exhaustive.status}, "
                f"target={exhaustive.selected_candidate}, "
                f"gain={exhaustive.selected_gain}, "
                f"distance={exhaustive.selected_distance}, "
                f"score={exhaustive.selected_score}, "
                f"path={exhaustive.selected_path}); "
                f"C=(status={lazy.status}, target={lazy.selected_candidate}, "
                f"gain={lazy.selected_gain}, distance={lazy.selected_distance}, "
                f"score={lazy.selected_score}, path={lazy.selected_path}, "
                f"records={lazy.candidate_records!r})"
            )

            self.assertEqual(simulator.world.robot, robot_before, msg=context)
            self.assertEqual(
                simulator.world.belief.snapshot(), belief_before, msg=context
            )
            self.assertIs(lazy.status, exhaustive.status, msg=context)
            self.assertEqual(
                lazy.selected_candidate,
                exhaustive.selected_candidate,
                msg=context,
            )
            self.assertEqual(
                lazy.eligible_candidate_count,
                exhaustive.eligible_candidate_count,
                msg=context,
            )
            self.assertGreaterEqual(lazy.exact_gain_evaluations, 0, msg=context)
            self.assertLessEqual(
                lazy.exact_gain_evaluations,
                lazy.eligible_candidate_count,
                msg=context,
            )
            self.assertEqual(
                lazy.bound_only_candidate_count,
                lazy.eligible_candidate_count - lazy.exact_gain_evaluations,
                msg=context,
            )
            self.assertEqual(
                lazy.exact_gain_evaluations,
                sum(
                    record.exact_evaluated_this_cycle
                    for record in lazy.candidate_records
                ),
                msg=context,
            )
            self.assertEqual(
                lazy.bound_only_candidate_count,
                sum(
                    not record.exact_evaluated_this_cycle
                    for record in lazy.candidate_records
                ),
                msg=context,
            )

            exhaustive_by_candidate = {
                item.candidate: item for item in exhaustive.evaluations
            }
            self.assertEqual(
                tuple(record.candidate for record in lazy.candidate_records),
                tuple(item.candidate for item in exhaustive.evaluations),
                msg=context,
            )
            for record in lazy.candidate_records:
                oracle = exhaustive_by_candidate[record.candidate]
                candidate_context = (
                    f"{context}; candidate={record.candidate}; "
                    f"A_evaluation={oracle!r}; C_record={record!r}"
                )
                self.assertEqual(
                    record.current_distance,
                    oracle.distance,
                    msg=candidate_context,
                )
                entry_bound = record.change_aware_upper_gain_at_entry
                if entry_bound is not None:
                    self.assertLessEqual(
                        oracle.gain,
                        entry_bound,
                        msg=candidate_context,
                    )

                if record.exact_evaluated_this_cycle:
                    self.assertTrue(record.cache_refreshed, msg=candidate_context)
                    self.assertEqual(
                        record.current_exact_gain,
                        oracle.gain,
                        msg=candidate_context,
                    )
                    self.assertEqual(
                        record.current_exact_score,
                        oracle.score,
                        msg=candidate_context,
                    )
                    self.assertEqual(
                        change_aware.cache.bound_counts[record.candidate],
                        oracle.gain,
                        msg=candidate_context,
                    )
                else:
                    self.assertFalse(record.cache_refreshed, msg=candidate_context)
                    self.assertIsNone(
                        record.current_exact_gain,
                        msg=candidate_context,
                    )
                    self.assertIsNone(
                        record.current_exact_score,
                        msg=candidate_context,
                    )
                    self.assertIsNotNone(entry_bound, msg=candidate_context)
                    self.assertEqual(
                        change_aware.cache.bound_counts[record.candidate],
                        entry_bound,
                        msg=candidate_context,
                    )

                if entry_bound is None:
                    self.assertTrue(
                        record.exact_evaluated_this_cycle,
                        msg=candidate_context,
                    )
                    self.assertTrue(record.cache_refreshed, msg=candidate_context)

            change_aware.cache.validate()
            safely_skipped |= (
                lazy.status is PlanStatus.SELECTED
                and lazy.exact_gain_evaluations
                < exhaustive.exact_gain_evaluations
            )
            sequence.append(exhaustive.selected_candidate)

            if exhaustive.status is PlanStatus.EXPLORATION_COMPLETE:
                self.assertIsNone(exhaustive.selected_candidate, msg=context)
                self.assertIsNone(lazy.selected_candidate, msg=context)
                self.assertIs(
                    lazy.status,
                    PlanStatus.EXPLORATION_COMPLETE,
                    msg=context,
                )
                return ACRunResult(
                    target_and_stop_sequence=tuple(sequence),
                    planning_snapshot_count=len(sequence),
                    safely_skipped_exact_evaluation=safely_skipped,
                    bound_violations=0,
                    target_mismatches=0,
                    status_or_termination_mismatches=0,
                    selected_gain_mismatches=0,
                    selected_distance_mismatches=0,
                    selected_score_mismatches=0,
                    path_mismatches=0,
                )

            self.assertEqual(
                lazy.selected_gain,
                exhaustive.selected_gain,
                msg=context,
            )
            self.assertEqual(
                lazy.selected_distance,
                exhaustive.selected_distance,
                msg=context,
            )
            self.assertEqual(
                lazy.selected_score,
                exhaustive.selected_score,
                msg=context,
            )
            self.assertEqual(
                lazy.selected_path,
                exhaustive.selected_path,
                msg=context,
            )
            selected_record = next(
                record
                for record in lazy.candidate_records
                if record.candidate == lazy.selected_candidate
            )
            self.assertTrue(
                selected_record.exact_evaluated_this_cycle,
                msg=context,
            )
            self.assertTrue(selected_record.cache_refreshed, msg=context)
            self.assertIsNotNone(selected_record.current_exact_gain, msg=context)
            self.assertIsNotNone(selected_record.current_exact_score, msg=context)

            # Environment advancement occurs only after every comparison above.
            _advance_shared_environment(simulator, exhaustive.selected_path)

        self.fail(
            f"{fixture.name}: reached frozen cycle limit {cycle_limit} "
            "without shared terminal decision"
        )


class FixedFixtureACRegressionTests(
    ACSharedSnapshotRegressionMixin,
    unittest.TestCase,
):
    def test_all_seven_fixtures_match_through_terminal_snapshot(self) -> None:
        fixtures = deterministic_fixtures()
        self.assertEqual(len(fixtures), 7)
        results: list[ACRunResult] = []
        for fixture in fixtures:
            with self.subTest(fixture=fixture.name):
                result = self.run_ac_to_completion(
                    fixture,
                    FIXTURE_CYCLE_LIMITS[fixture.name],
                )
                self.assertIsNone(result.target_and_stop_sequence[-1])
                self.assertEqual(result.bound_violations, 0)
                self.assertEqual(result.target_mismatches, 0)
                self.assertEqual(result.status_or_termination_mismatches, 0)
                self.assertEqual(result.selected_gain_mismatches, 0)
                self.assertEqual(result.selected_distance_mismatches, 0)
                self.assertEqual(result.selected_score_mismatches, 0)
                self.assertEqual(result.path_mismatches, 0)
                results.append(result)
                print(
                    "STAGE6_FIXED_RUN "
                    f"fixture={fixture.name} "
                    f"planning_snapshots={result.planning_snapshot_count} "
                    f"safe_skip={result.safely_skipped_exact_evaluation} "
                    f"target_and_stop_sequence={result.target_and_stop_sequence!r} "
                    "target_mismatches=0 "
                    "status_or_termination_mismatches=0 "
                    "selected_gain_mismatches=0 "
                    "selected_distance_mismatches=0 "
                    "selected_score_mismatches=0 path_mismatches=0 "
                    "bound_violations=0"
                )

        print(
            "STAGE6_FIXED_SUMMARY "
            f"runs={len(results)} "
            f"planning_snapshots={sum(r.planning_snapshot_count for r in results)} "
            f"safe_skip={any(r.safely_skipped_exact_evaluation for r in results)} "
            "target_mismatches=0 status_or_termination_mismatches=0 "
            "selected_gain_mismatches=0 selected_distance_mismatches=0 "
            "selected_score_mismatches=0 path_mismatches=0 "
            "bound_violations=0"
        )


class FrozenRandomV2ACRegressionTests(
    ACSharedSnapshotRegressionMixin,
    unittest.TestCase,
):
    def test_all_sixty_canonical_v2_maps_match_through_terminal_snapshot(self) -> None:
        config = load_config(CONFIG_PATH)
        records = config["accepted_maps"]
        self.assertEqual(config["dataset_version"], "experiment-0-random-v2")
        self.assertEqual(len(records), 60)

        results: list[ACRunResult] = []
        for record in records:
            with self.subTest(map_id=record["dataset_id"]):
                regenerated = regenerate_record(record)
                self.assertEqual(regenerated.seed, record["seed"])
                self.assertEqual(regenerated.start, tuple(record["start"]))
                self.assertEqual(regenerated.cycle_limit, record["cycle_limit"])
                self.assertEqual(regenerated.map_hash, record["map_hash"])
                self.assertEqual(
                    ground_truth_hash(regenerated.ground_truth),
                    record["map_hash"],
                )
                fixture = MapFixture(
                    record["dataset_id"],
                    regenerated.ground_truth,
                    regenerated.start,
                )
                result = self.run_ac_to_completion(
                    fixture,
                    record["cycle_limit"],
                )
                self.assertIsNone(result.target_and_stop_sequence[-1])
                self.assertEqual(result.bound_violations, 0)
                self.assertEqual(result.target_mismatches, 0)
                self.assertEqual(result.status_or_termination_mismatches, 0)
                self.assertEqual(result.selected_gain_mismatches, 0)
                self.assertEqual(result.selected_distance_mismatches, 0)
                self.assertEqual(result.selected_score_mismatches, 0)
                self.assertEqual(result.path_mismatches, 0)
                results.append(result)

        print(
            "STAGE6_RANDOM_SUMMARY "
            f"runs={len(results)} "
            f"planning_snapshots={sum(r.planning_snapshot_count for r in results)} "
            f"safe_skip={any(r.safely_skipped_exact_evaluation for r in results)} "
            "target_mismatches=0 status_or_termination_mismatches=0 "
            "selected_gain_mismatches=0 selected_distance_mismatches=0 "
            "selected_score_mismatches=0 path_mismatches=0 "
            "bound_violations=0"
        )


if __name__ == "__main__":
    unittest.main()
