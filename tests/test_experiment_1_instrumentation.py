import importlib
import unittest

from src.environment import GroundTruthGrid
from src.evaluation.experiment_1_instrumentation import (
    decomposition,
    require_exact_call_match,
    visibility_work,
)
from src.evaluation.simulator import ExplorationSimulator
from src.mapping import BeliefGrid
from src.planning import ChangeAwareLazyNBV, StaleScalarLazyNBV
from src.sensing import optimistic_visible_unknown_cells, physical_scan
from src.utils import BeliefState


EXHAUSTIVE = importlib.import_module("src.planning.exhaustive_nbv")
STALE = importlib.import_module("src.planning.stale_scalar_lazy_nbv")
INTEGRATION = importlib.import_module("src.planning.change_aware_integration")
VISIBILITY = importlib.import_module("src.sensing.visibility")


def line_belief(*states: BeliefState) -> BeliefGrid:
    return BeliefGrid([list(states)])


class VisibilityInstrumentationTests(unittest.TestCase):
    def test_semantics_and_input_snapshot_are_unchanged(self) -> None:
        belief = line_belief(
            BeliefState.FREE,
            BeliefState.UNKNOWN,
            BeliefState.UNKNOWN,
            BeliefState.UNKNOWN,
        )
        before = belief.snapshot()
        expected = optimistic_visible_unknown_cells(belief, (0, 0), 3)
        with visibility_work() as work:
            observed = EXHAUSTIVE.optimistic_visible_unknown_cells(
                belief, (0, 0), 3
            )
        self.assertEqual(observed, expected)
        self.assertEqual(belief.snapshot(), before)
        self.assertEqual(work.exact_visibility_call_count, 1)

    def test_hand_checked_ray_line_and_full_probe_counts(self) -> None:
        belief = line_belief(
            BeliefState.FREE,
            BeliefState.UNKNOWN,
            BeliefState.UNKNOWN,
            BeliefState.UNKNOWN,
        )
        with visibility_work() as work:
            EXHAUSTIVE.optimistic_visible_unknown_cells(belief, (0, 0), 3)
        self.assertEqual(work.visibility_ray_count, 3)
        self.assertEqual(work.visibility_supercover_cell_count, 2 + 3 + 4)
        self.assertEqual(work.visibility_interior_probe_count, 0 + 1 + 2)

    def test_early_blocker_short_circuits_interior_probes(self) -> None:
        belief = line_belief(
            BeliefState.FREE,
            BeliefState.OCCUPIED,
            BeliefState.UNKNOWN,
            BeliefState.UNKNOWN,
        )
        with visibility_work() as work:
            visible = EXHAUSTIVE.optimistic_visible_unknown_cells(
                belief, (0, 0), 3
            )
        self.assertEqual(visible, frozenset())
        self.assertEqual(work.visibility_ray_count, 2)
        self.assertEqual(work.visibility_supercover_cell_count, 3 + 4)
        self.assertEqual(work.visibility_interior_probe_count, 2)
        self.assertLess(work.visibility_interior_probe_count, 1 + 2)

    def test_physical_sensing_outside_exact_call_is_not_counted(self) -> None:
        ground_truth = GroundTruthGrid.from_ascii(("....",))
        with visibility_work() as work:
            physical_scan(ground_truth, (0, 0), 3)
        self.assertEqual(work.exact_visibility_call_count, 0)
        self.assertEqual(work.visibility_ray_count, 0)
        self.assertEqual(work.visibility_supercover_cell_count, 0)
        self.assertEqual(work.visibility_interior_probe_count, 0)

    def test_patched_call_sites_restore_after_success(self) -> None:
        originals = (
            EXHAUSTIVE.optimistic_visible_unknown_cells,
            STALE.optimistic_visible_unknown_cells,
            INTEGRATION.optimistic_visible_unknown_cells,
            VISIBILITY.supercover_line,
        )
        with visibility_work():
            self.assertIsNot(EXHAUSTIVE.optimistic_visible_unknown_cells, originals[0])
        self.assertEqual(
            originals,
            (
                EXHAUSTIVE.optimistic_visible_unknown_cells,
                STALE.optimistic_visible_unknown_cells,
                INTEGRATION.optimistic_visible_unknown_cells,
                VISIBILITY.supercover_line,
            ),
        )

    def test_patched_call_sites_restore_after_exception(self) -> None:
        original = EXHAUSTIVE.optimistic_visible_unknown_cells
        belief = line_belief(BeliefState.UNKNOWN)
        with self.assertRaises(ValueError):
            with visibility_work():
                EXHAUSTIVE.optimistic_visible_unknown_cells(belief, (0, 0), 1)
        self.assertIs(EXHAUSTIVE.optimistic_visible_unknown_cells, original)

    def test_nested_contexts_have_independent_counters_and_restore(self) -> None:
        belief = line_belief(BeliefState.FREE, BeliefState.UNKNOWN)
        original = EXHAUSTIVE.optimistic_visible_unknown_cells
        with visibility_work() as outer:
            EXHAUSTIVE.optimistic_visible_unknown_cells(belief, (0, 0), 1)
            with visibility_work() as inner:
                EXHAUSTIVE.optimistic_visible_unknown_cells(belief, (0, 0), 1)
            EXHAUSTIVE.optimistic_visible_unknown_cells(belief, (0, 0), 1)
        self.assertEqual(outer.exact_visibility_call_count, 2)
        self.assertEqual(inner.exact_visibility_call_count, 1)
        self.assertIs(EXHAUSTIVE.optimistic_visible_unknown_cells, original)

    def _planner_pair(self, method: str):  # type: ignore[no-untyped-def]
        grid = GroundTruthGrid.from_ascii(("." * 20,))
        plain_sim = ExplorationSimulator(grid, (0, 0), 8)
        measured_sim = ExplorationSimulator(grid, (0, 0), 8)
        if method == "A":
            plain_call = plain_sim.plan
            measured_call = measured_sim.plan
        elif method == "B":
            plain = StaleScalarLazyNBV(8)
            measured = StaleScalarLazyNBV(8)
            plain_call = lambda: plain.plan(plain_sim.world.belief, plain_sim.world.robot)
            measured_call = lambda: measured.plan(
                measured_sim.world.belief, measured_sim.world.robot
            )
        else:
            plain = ChangeAwareLazyNBV(8)
            measured = ChangeAwareLazyNBV(8)
            plain_call = lambda: plain.plan(plain_sim.world.belief, plain_sim.world.robot)
            measured_call = lambda: measured.plan(
                measured_sim.world.belief, measured_sim.world.robot
            )
        expected = plain_call()
        with visibility_work() as work:
            observed = measured_call()
        return expected, observed, work

    def test_a_exact_calls_equal_exact_evaluations_and_decision(self) -> None:
        expected, observed, work = self._planner_pair("A")
        require_exact_call_match(work, observed.exact_gain_evaluations)
        self.assertEqual(observed, expected)

    def test_b_exact_calls_equal_exact_evaluations_and_decision(self) -> None:
        expected, observed, work = self._planner_pair("B")
        require_exact_call_match(work, observed.exact_gain_evaluations)
        self.assertEqual(observed, expected)

    def test_c_exact_calls_equal_exact_evaluations_and_decision(self) -> None:
        expected, observed, work = self._planner_pair("C")
        require_exact_call_match(work, observed.exact_gain_evaluations)
        self.assertEqual(observed, expected)

    def test_exact_call_mismatch_is_not_silently_accepted(self) -> None:
        _, observed, work = self._planner_pair("A")
        with self.assertRaisesRegex(RuntimeError, "instrumentation mismatch"):
            require_exact_call_match(work, observed.exact_gain_evaluations + 1)


class DecompositionInstrumentationTests(unittest.TestCase):
    def test_empty_planner_call_is_exact_complement_and_restores(self) -> None:
        original = EXHAUSTIVE.dijkstra
        ticks = iter((10, 20))
        with decomposition(lambda: next(ticks)) as measured:
            result = measured.measure(lambda: "ok")
        self.assertEqual(result.result, "ok")
        self.assertEqual(result.total_time_ns, 10)
        self.assertEqual(result.distance_time_ns, 0)
        self.assertEqual(result.visibility_time_ns, 0)
        self.assertEqual(result.maintenance_time_ns, 0)
        self.assertEqual(result.other_time_ns, 10)
        self.assertEqual(result.decomposition_residual_ns, 0)
        self.assertIs(EXHAUSTIVE.dijkstra, original)


if __name__ == "__main__":
    unittest.main()
