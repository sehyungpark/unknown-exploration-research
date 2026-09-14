import unittest

from src.environment import GroundTruthGrid
from src.sensing import (
    cells_within_range,
    optimistic_visible_unknown_cells,
    physical_scan,
    physical_visible_cells,
    supercover_line,
)
from src.utils import BeliefState, TruthState

from tests.helpers import belief_from_ascii, opaque_visible_unknown_cells


class PhysicalSensingTests(unittest.TestCase):
    def test_euclidean_range_is_center_to_center_and_inclusive(self) -> None:
        targets = set(cells_within_range((10, 10), (20, 20), sensor_range=8))
        self.assertIn((10, 18), targets)
        self.assertIn((18, 10), targets)
        self.assertNotIn((11, 18), targets)

    def test_first_occupied_cell_is_visible_and_blocks_cells_behind(self) -> None:
        ground_truth = GroundTruthGrid.from_ascii(("..#..",))
        visible = physical_visible_cells(ground_truth, (0, 0), sensor_range=8)
        self.assertEqual(visible, frozenset({(0, 0), (0, 1), (0, 2)}))

        observations = physical_scan(ground_truth, (0, 0), sensor_range=8)
        self.assertEqual(observations[(0, 2)], TruthState.OCCUPIED)
        self.assertNotIn((0, 3), observations)


class PlanningVisibilityTests(unittest.TestCase):
    def test_unknown_cells_are_transparent(self) -> None:
        belief = belief_from_ascii((".??",))
        self.assertEqual(
            optimistic_visible_unknown_cells(belief, (0, 0), sensor_range=8),
            frozenset({(0, 1), (0, 2)}),
        )

    def test_newly_discovered_occupied_blocks_unknown_behind(self) -> None:
        belief = belief_from_ascii((".??",))
        cached = optimistic_visible_unknown_cells(belief, (0, 0), sensor_range=8)
        belief.apply_observations({(0, 1): TruthState.OCCUPIED})
        current = optimistic_visible_unknown_cells(belief, (0, 0), sensor_range=8)
        maintained_bound = len(cached & belief.unknown_cells())

        self.assertEqual(current, frozenset())
        self.assertEqual(maintained_bound, 1)
        self.assertLess(len(current), maintained_bound)

    def test_minimal_opaque_unknown_counterexample(self) -> None:
        belief = belief_from_ascii((".??",))
        opaque_cached = opaque_visible_unknown_cells(
            belief, (0, 0), supercover_line
        )
        optimistic_cached = optimistic_visible_unknown_cells(
            belief, (0, 0), sensor_range=8
        )
        self.assertEqual(opaque_cached, frozenset({(0, 1)}))
        self.assertEqual(optimistic_cached, frozenset({(0, 1), (0, 2)}))

        belief.apply_observations({(0, 1): TruthState.FREE})
        opaque_current = opaque_visible_unknown_cells(
            belief, (0, 0), supercover_line
        )
        opaque_bound = len(opaque_cached & belief.unknown_cells())
        optimistic_bound = len(optimistic_cached & belief.unknown_cells())

        self.assertEqual(belief.state((0, 2)), BeliefState.UNKNOWN)
        self.assertEqual(opaque_current, frozenset({(0, 2)}))
        self.assertEqual(opaque_bound, 0)
        self.assertGreater(len(opaque_current), opaque_bound)
        self.assertEqual(
            len(optimistic_visible_unknown_cells(belief, (0, 0), 8)),
            optimistic_bound,
        )


if __name__ == "__main__":
    unittest.main()
