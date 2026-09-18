from pathlib import Path
import unittest

from src.environment.fixtures import MapFixture, deterministic_fixtures
from src.evaluation import ExplorationSimulator
from src.evaluation.random_dataset import load_config, regenerate_record
from src.planning import ChangeAwareStarNBV, PlanStatus
from src.planning.motion import legal_neighbors
from src.sensing import physical_scan
from src.utils import Coord, ground_truth_hash

from tests.test_exhaustive_end_to_end import FIXTURE_CYCLE_LIMITS


CONFIG_PATH = Path("configs/experiment_0_random_maps.json")


def _advance_shared_environment(
    simulator: ExplorationSimulator,
    selected_path: tuple[Coord, ...],
) -> frozenset[Coord]:
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
    changed = simulator.world.belief.apply_observations(observations)
    simulator.scan_count += 1
    simulator.snapshot_index += 1
    return changed


class ACStarSharedSnapshotRegressionMixin:
    def run_to_completion(self, fixture: MapFixture, cycle_limit: int) -> None:
        simulator = ExplorationSimulator(fixture.ground_truth, fixture.start, 8)
        cstar = ChangeAwareStarNBV(8)
        pending_delta: frozenset[Coord] | None = None

        for cycle_index in range(cycle_limit):
            exhaustive = simulator.plan()
            result = cstar.plan(
                simulator.world.belief,
                simulator.world.robot,
                newly_known=pending_delta,
            )

            context = f"{fixture.name} cycle {cycle_index}"
            self.assertIs(result.status, exhaustive.status, msg=context)
            self.assertEqual(
                result.selected_candidate,
                exhaustive.selected_candidate,
                msg=context,
            )
            self.assertEqual(
                result.eligible_candidate_count,
                exhaustive.eligible_candidate_count,
                msg=context,
            )
            self.assertEqual(
                tuple(record.candidate for record in result.candidate_records),
                tuple(item.candidate for item in exhaustive.evaluations),
                msg=context,
            )

            exhaustive_by_candidate = {
                item.candidate: item for item in exhaustive.evaluations
            }
            for record in result.candidate_records:
                oracle = exhaustive_by_candidate[record.candidate]
                candidate_context = f"{context} candidate={record.candidate}"
                self.assertEqual(
                    record.current_distance,
                    oracle.distance,
                    msg=candidate_context,
                )
                self.assertLessEqual(
                    oracle.gain,
                    record.range_upper_gain,
                    msg=candidate_context,
                )
                if record.stale_upper_gain_at_entry is not None:
                    self.assertLessEqual(
                        oracle.gain,
                        record.stale_upper_gain_at_entry,
                        msg=candidate_context,
                    )
                if record.change_upper_gain_after_refresh is not None:
                    self.assertLessEqual(
                        oracle.gain,
                        record.change_upper_gain_after_refresh,
                        msg=candidate_context,
                    )
                    if record.stale_upper_gain_at_entry is not None:
                        self.assertLessEqual(
                            record.change_upper_gain_after_refresh,
                            record.stale_upper_gain_at_entry,
                            msg=candidate_context,
                        )
                    self.assertLessEqual(
                        record.change_upper_gain_after_refresh,
                        record.range_upper_gain,
                        msg=candidate_context,
                    )

                if record.exact_evaluated_this_cycle:
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
                else:
                    self.assertIsNone(
                        record.current_exact_gain,
                        msg=candidate_context,
                    )
                    self.assertIsNone(
                        record.current_exact_score,
                        msg=candidate_context,
                    )

            self.assertEqual(
                result.exact_gain_evaluations,
                sum(r.exact_evaluated_this_cycle for r in result.candidate_records),
                msg=context,
            )
            self.assertEqual(
                result.bound_only_candidate_count,
                result.eligible_candidate_count - result.exact_gain_evaluations,
                msg=context,
            )

            if exhaustive.status is PlanStatus.EXPLORATION_COMPLETE:
                self.assertIsNone(result.selected_candidate, msg=context)
                cstar.audit(simulator.world.belief)
                return

            self.assertEqual(result.selected_gain, exhaustive.selected_gain, msg=context)
            self.assertEqual(
                result.selected_distance,
                exhaustive.selected_distance,
                msg=context,
            )
            self.assertEqual(
                result.selected_score,
                exhaustive.selected_score,
                msg=context,
            )
            self.assertEqual(result.selected_path, exhaustive.selected_path, msg=context)
            selected_record = next(
                record
                for record in result.candidate_records
                if record.candidate == result.selected_candidate
            )
            self.assertTrue(
                selected_record.exact_evaluated_this_cycle,
                msg=context,
            )

            pending_delta = _advance_shared_environment(
                simulator,
                exhaustive.selected_path,
            )

        self.fail(
            f"{fixture.name}: reached cycle limit {cycle_limit} without terminal state"
        )


class FixedFixtureACStarRegressionTests(
    ACStarSharedSnapshotRegressionMixin,
    unittest.TestCase,
):
    def test_all_seven_fixtures_match_A(self) -> None:
        fixtures = deterministic_fixtures()
        self.assertEqual(len(fixtures), 7)
        for fixture in fixtures:
            with self.subTest(fixture=fixture.name):
                self.run_to_completion(
                    fixture,
                    FIXTURE_CYCLE_LIMITS[fixture.name],
                )


class FrozenRandomV2ACStarRegressionTests(
    ACStarSharedSnapshotRegressionMixin,
    unittest.TestCase,
):
    def test_all_sixty_canonical_v2_maps_match_A(self) -> None:
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
                    ground_truth_hash(regenerated.ground_truth),
                    record["map_hash"],
                )
                fixture = MapFixture(
                    record["dataset_id"],
                    regenerated.ground_truth,
                    regenerated.start,
                )
                self.run_to_completion(fixture, record["cycle_limit"])


if __name__ == "__main__":
    unittest.main()
