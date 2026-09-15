from dataclasses import dataclass
from pathlib import Path
import unittest

from src.environment.fixtures import MapFixture, deterministic_fixtures
from src.evaluation import ExplorationSimulator
from src.evaluation.random_dataset import load_config, regenerate_record
from src.planning import PlanStatus, StaleScalarLazyNBV
from src.planning.motion import legal_neighbors
from src.sensing import physical_scan
from src.utils import Coord, ground_truth_hash

from tests.test_exhaustive_end_to_end import FIXTURE_CYCLE_LIMITS


CONFIG_PATH = Path("configs/experiment_0_random_maps.json")


@dataclass(frozen=True, slots=True)
class ABRunResult:
    target_and_stop_sequence: tuple[Coord | None, ...]
    safely_skipped_exact_evaluation: bool
    bound_violations: int
    target_mismatches: int
    sequence_or_termination_mismatches: int


def _advance_shared_environment(
    simulator: ExplorationSimulator,
    selected_path: tuple[Coord, ...],
) -> None:
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


class ABSharedSnapshotRegressionMixin:
    def run_ab_to_completion(
        self,
        fixture: MapFixture,
        cycle_limit: int,
    ) -> ABRunResult:
        simulator = ExplorationSimulator(fixture.ground_truth, fixture.start, 8)
        stale = StaleScalarLazyNBV(8)
        sequence: list[Coord | None] = []
        safely_skipped = False

        for cycle_index in range(cycle_limit):
            exhaustive = simulator.plan()
            lazy = stale.plan(simulator.world.belief, simulator.world.robot)

            self.assertIs(
                lazy.status,
                exhaustive.status,
                msg=f"{fixture.name} cycle {cycle_index}: status mismatch",
            )
            self.assertEqual(
                lazy.selected_candidate,
                exhaustive.selected_candidate,
                msg=f"{fixture.name} cycle {cycle_index}: target mismatch",
            )
            self.assertEqual(
                lazy.eligible_candidate_count,
                exhaustive.eligible_candidate_count,
            )
            self.assertGreaterEqual(lazy.exact_gain_evaluations, 0)
            self.assertLessEqual(
                lazy.exact_gain_evaluations, lazy.eligible_candidate_count
            )
            self.assertEqual(
                lazy.bound_only_candidate_count,
                lazy.eligible_candidate_count - lazy.exact_gain_evaluations,
            )
            safely_skipped |= (
                lazy.status is PlanStatus.SELECTED
                and lazy.exact_gain_evaluations
                < exhaustive.exact_gain_evaluations
            )

            exhaustive_by_candidate = {
                item.candidate: item for item in exhaustive.evaluations
            }
            self.assertEqual(
                tuple(record.candidate for record in lazy.candidate_records),
                tuple(item.candidate for item in exhaustive.evaluations),
            )
            for record in lazy.candidate_records:
                oracle = exhaustive_by_candidate[record.candidate]
                self.assertEqual(record.current_distance, oracle.distance)
                if record.stale_upper_gain is not None:
                    self.assertLessEqual(
                        oracle.gain,
                        record.stale_upper_gain,
                        msg=(
                            f"{fixture.name} cycle {cycle_index}: stale bound "
                            f"violation at {record.candidate}"
                        ),
                    )
                if record.exact_evaluated_this_cycle:
                    self.assertTrue(record.cache_refreshed)
                    self.assertEqual(record.exact_gain, oracle.gain)
                    self.assertEqual(record.exact_score, oracle.score)
                    self.assertEqual(stale.cached_gains[record.candidate], oracle.gain)
                else:
                    self.assertFalse(record.cache_refreshed)
                    self.assertIsNone(record.exact_gain)
                    self.assertIsNone(record.exact_score)
                    self.assertIsNotNone(record.stale_upper_gain)

            sequence.append(exhaustive.selected_candidate)
            if exhaustive.status is PlanStatus.EXPLORATION_COMPLETE:
                self.assertIsNone(exhaustive.selected_candidate)
                self.assertIsNone(lazy.selected_candidate)
                return ABRunResult(
                    target_and_stop_sequence=tuple(sequence),
                    safely_skipped_exact_evaluation=safely_skipped,
                    bound_violations=0,
                    target_mismatches=0,
                    sequence_or_termination_mismatches=0,
                )

            self.assertEqual(lazy.selected_gain, exhaustive.selected_gain)
            self.assertEqual(lazy.selected_distance, exhaustive.selected_distance)
            self.assertEqual(lazy.selected_score, exhaustive.selected_score)
            self.assertEqual(lazy.selected_path, exhaustive.selected_path)
            selected_record = next(
                record
                for record in lazy.candidate_records
                if record.candidate == lazy.selected_candidate
            )
            self.assertTrue(selected_record.exact_evaluated_this_cycle)
            self.assertIsNotNone(selected_record.exact_gain)
            _advance_shared_environment(simulator, exhaustive.selected_path)

        self.fail(
            f"{fixture.name}: reached safety limit {cycle_limit} without shared stop"
        )


class FixedFixtureABRegressionTests(
    ABSharedSnapshotRegressionMixin, unittest.TestCase
):
    def test_all_seven_fixtures_match_through_terminal_snapshot(self) -> None:
        fixtures = deterministic_fixtures()
        self.assertEqual(len(fixtures), 7)
        skipped = False
        for fixture in fixtures:
            with self.subTest(fixture=fixture.name):
                result = self.run_ab_to_completion(
                    fixture, FIXTURE_CYCLE_LIMITS[fixture.name]
                )
                self.assertIsNone(result.target_and_stop_sequence[-1])
                self.assertEqual(result.bound_violations, 0)
                self.assertEqual(result.target_mismatches, 0)
                self.assertEqual(result.sequence_or_termination_mismatches, 0)
                skipped |= result.safely_skipped_exact_evaluation
        self.assertTrue(
            skipped,
            msg="at least one deterministic A/B run must safely skip an exact evaluation",
        )


class FrozenRandomV2ABRegressionTests(
    ABSharedSnapshotRegressionMixin, unittest.TestCase
):
    def test_all_sixty_canonical_v2_maps_match_through_terminal_snapshot(self) -> None:
        config = load_config(CONFIG_PATH)
        records = config["accepted_maps"]
        self.assertEqual(config["dataset_version"], "experiment-0-random-v2")
        self.assertEqual(len(records), 60)

        for record in records:
            with self.subTest(map_id=record["dataset_id"]):
                regenerated = regenerate_record(record)
                self.assertEqual(regenerated.seed, record["seed"])
                self.assertEqual(regenerated.start, tuple(record["start"]))
                self.assertEqual(regenerated.cycle_limit, record["cycle_limit"])
                self.assertEqual(regenerated.map_hash, record["map_hash"])
                self.assertEqual(
                    ground_truth_hash(regenerated.ground_truth), record["map_hash"]
                )
                fixture = MapFixture(
                    record["dataset_id"],
                    regenerated.ground_truth,
                    regenerated.start,
                )
                result = self.run_ab_to_completion(
                    fixture, record["cycle_limit"]
                )
                self.assertIsNone(result.target_and_stop_sequence[-1])
                self.assertEqual(result.bound_violations, 0)
                self.assertEqual(result.target_mismatches, 0)
                self.assertEqual(result.sequence_or_termination_mismatches, 0)


if __name__ == "__main__":
    unittest.main()
