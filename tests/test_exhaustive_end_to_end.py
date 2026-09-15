from dataclasses import dataclass
import unittest

from src.candidates import reachable_known_free_candidates
from src.environment.fixtures import MapFixture, deterministic_fixtures
from src.evaluation import ExplorationSimulator
from src.mapping import BeliefGrid
from src.planning import PlanStatus, dijkstra
from src.planning.motion import legal_neighbors
from src.utils import BeliefState, Coord

FIXTURE_CYCLE_LIMITS = {
    "open": 64,
    "single_room": 64,
    "corridor": 64,
    "dead_end": 80,
    "separated_rooms": 96,
    "clutter": 96,
    "maze_like": 128,
}


@dataclass(frozen=True, slots=True)
class ExhaustiveRunTrace:
    selected_targets: tuple[Coord, ...]
    traversed_paths: tuple[tuple[Coord, ...], ...]
    final_belief: tuple[tuple[BeliefState, ...], ...]
    final_robot: Coord
    scan_count: int
    planning_cycle_count: int
    selected_cycle_count: int
    termination_status: PlanStatus


def _known_count(snapshot: tuple[tuple[BeliefState, ...], ...]) -> int:
    return sum(
        state is not BeliefState.UNKNOWN for row in snapshot for state in row
    )


def run_exhaustive_fixture(fixture: MapFixture, cycle_limit: int) -> ExhaustiveRunTrace:
    simulator = ExplorationSimulator(fixture.ground_truth, fixture.start, 8)
    selected_targets: list[Coord] = []
    traversed_paths: list[tuple[Coord, ...]] = []

    for planning_cycle in range(cycle_limit):
        planning_robot = simulator.world.robot
        before = simulator.world.belief.snapshot()
        planning_belief = BeliefGrid([list(row) for row in before])
        distance_result = dijkstra(planning_belief, planning_robot)
        eligible = reachable_known_free_candidates(
            planning_belief, planning_robot, distance_result.distances
        )

        cycle = simulator.execute_atomic_cycle()
        plan = cycle.plan
        evaluated_candidates = tuple(item.candidate for item in plan.evaluations)
        assert evaluated_candidates == eligible, (
            f"{fixture.name}: exhaustive candidates differ from independently "
            f"generated eligible candidates at cycle {planning_cycle}"
        )
        assert plan.eligible_candidate_count == len(eligible)
        assert plan.exact_gain_evaluations == len(eligible)

        if plan.status is PlanStatus.EXPLORATION_COMPLETE:
            assert plan.selected_candidate is None
            assert all(item.gain == 0 for item in plan.evaluations)
            assert simulator.world.belief.snapshot() == before
            return ExhaustiveRunTrace(
                selected_targets=tuple(selected_targets),
                traversed_paths=tuple(traversed_paths),
                final_belief=simulator.world.belief.snapshot(),
                final_robot=simulator.world.robot,
                scan_count=simulator.scan_count,
                planning_cycle_count=planning_cycle + 1,
                selected_cycle_count=len(selected_targets),
                termination_status=plan.status,
            )

        selected = plan.selected_candidate
        assert selected is not None
        assert selected in eligible, (
            f"{fixture.name}: selected ineligible candidate {selected} at "
            f"cycle {planning_cycle}"
        )
        path = cycle.traversed_path
        assert path and path[0] == planning_robot
        assert path[-1] == selected
        for coord in path:
            assert planning_belief.state(coord) is BeliefState.FREE, (
                f"{fixture.name}: path traverses non-FREE {coord} at "
                f"cycle {planning_cycle}"
            )
        for source, target in zip(path, path[1:]):
            legal = {coord for coord, _ in legal_neighbors(planning_belief, source)}
            assert target in legal, (
                f"{fixture.name}: illegal path step {source}->{target} at "
                f"cycle {planning_cycle}"
            )

        after = simulator.world.belief.snapshot()
        assert _known_count(after) >= _known_count(before)
        for row in range(planning_belief.height):
            for col in range(planning_belief.width):
                old_state = before[row][col]
                new_state = after[row][col]
                if old_state is not BeliefState.UNKNOWN:
                    assert new_state is old_state, (
                        f"{fixture.name}: known state changed at {(row, col)} "
                        f"during cycle {planning_cycle}: {old_state}->{new_state}"
                    )

        selected_targets.append(selected)
        traversed_paths.append(path)

    raise AssertionError(
        f"{fixture.name}: reached safety limit {cycle_limit} without explicit stop"
    )


class ExhaustiveFixtureEndToEndTests(unittest.TestCase):
    def test_all_fixtures_stop_and_repeat_deterministically(self) -> None:
        for fixture in deterministic_fixtures():
            with self.subTest(fixture=fixture.name):
                limit = FIXTURE_CYCLE_LIMITS[fixture.name]
                first = run_exhaustive_fixture(fixture, limit)
                second = run_exhaustive_fixture(fixture, limit)
                self.assertEqual(first, second)
                self.assertIs(
                    first.termination_status, PlanStatus.EXPLORATION_COMPLETE
                )
                self.assertLess(first.planning_cycle_count, limit)
                self.assertEqual(first.scan_count, first.selected_cycle_count + 1)


if __name__ == "__main__":
    unittest.main()
