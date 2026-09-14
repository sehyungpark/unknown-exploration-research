import unittest

from src.environment import GroundTruthGrid
from src.environment.fixtures import deterministic_fixtures, single_room_fixture
from src.evaluation import ExplorationSimulator
from src.planning import PlanStatus
from src.sensing import physical_scan
from src.utils import BeliefState, TruthState


class FixtureTests(unittest.TestCase):
    def test_required_deterministic_fixtures_exist(self) -> None:
        fixtures = deterministic_fixtures()
        self.assertEqual(
            {fixture.name for fixture in fixtures},
            {
                "open",
                "single_room",
                "corridor",
                "dead_end",
                "separated_rooms",
                "clutter",
                "maze_like",
            },
        )
        for fixture in fixtures:
            with self.subTest(fixture=fixture.name):
                self.assertEqual(fixture.ground_truth.shape, (20, 20))
                self.assertIs(
                    fixture.ground_truth.state(fixture.start), TruthState.FREE
                )


class AtomicSimulatorTests(unittest.TestCase):
    def test_one_full_atomic_planning_cycle_senses_only_at_arrival(self) -> None:
        fixture = single_room_fixture()
        simulator = ExplorationSimulator(
            fixture.ground_truth, fixture.start, sensor_range=8
        )
        self.assertEqual(simulator.scan_count, 1)
        before = simulator.world.belief.snapshot()
        preview = simulator.plan()
        self.assertIs(preview.status, PlanStatus.SELECTED)
        assert preview.selected_candidate is not None
        expected_observations = physical_scan(
            fixture.ground_truth, preview.selected_candidate, sensor_range=8
        )
        expected_changes = frozenset(
            coord
            for coord in expected_observations
            if before[coord[0]][coord[1]] is BeliefState.UNKNOWN
        )

        cycle = simulator.execute_atomic_cycle()

        self.assertEqual(cycle.plan.selected_candidate, preview.selected_candidate)
        self.assertEqual(cycle.arrival_observation_changes, expected_changes)
        self.assertEqual(simulator.scan_count, 2)
        self.assertEqual(cycle.planning_snapshot, 0)
        self.assertEqual(cycle.arrival_snapshot, 1)
        self.assertEqual(cycle.traversed_path[0], fixture.start)
        self.assertEqual(cycle.traversed_path[-1], preview.selected_candidate)

    def test_repeated_execution_on_same_fixture_is_deterministic(self) -> None:
        fixture = single_room_fixture()
        first = ExplorationSimulator(fixture.ground_truth, fixture.start, 8)
        second = ExplorationSimulator(fixture.ground_truth, fixture.start, 8)

        first_results = [first.execute_atomic_cycle() for _ in range(3)]
        second_results = [second.execute_atomic_cycle() for _ in range(3)]

        self.assertEqual(
            [result.plan.selected_candidate for result in first_results],
            [result.plan.selected_candidate for result in second_results],
        )
        self.assertEqual(
            [result.traversed_path for result in first_results],
            [result.traversed_path for result in second_results],
        )
        self.assertEqual(first.world.belief.snapshot(), second.world.belief.snapshot())
        self.assertEqual(first.world.robot, second.world.robot)
        self.assertEqual(first.scan_count, second.scan_count)

    def test_initial_scan_can_produce_deterministic_stop(self) -> None:
        grid = GroundTruthGrid.from_ascii(("...", "...", "..."))
        simulator = ExplorationSimulator(grid, (1, 1), sensor_range=8)
        cycle = simulator.execute_atomic_cycle()
        self.assertIs(cycle.plan.status, PlanStatus.EXPLORATION_COMPLETE)
        self.assertEqual(simulator.scan_count, 1)
        self.assertEqual(cycle.traversed_path, ())


if __name__ == "__main__":
    unittest.main()
