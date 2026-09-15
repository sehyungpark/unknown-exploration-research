import unittest

from src.environment import GroundTruthGrid
from src.sensing import optimistic_visible_unknown_cells, physical_visible_cells

from tests.helpers import belief_from_ascii


class CornerOcclusionIntegrationTests(unittest.TestCase):
    def test_physical_corner_side_obstacle_is_visible_and_blocks_diagonal_target(
        self,
    ) -> None:
        cases = (
            ((".#", ".."), (0, 1)),
            (("..", "#."), (1, 0)),
        )
        for rows, obstacle in cases:
            with self.subTest(obstacle=obstacle):
                ground_truth = GroundTruthGrid.from_ascii(rows)
                visible = physical_visible_cells(
                    ground_truth, (0, 0), sensor_range=2
                )
                self.assertIn(obstacle, visible)
                self.assertNotIn((1, 1), visible)

        all_free = GroundTruthGrid.from_ascii(("..", ".."))
        self.assertIn(
            (1, 1), physical_visible_cells(all_free, (0, 0), sensor_range=2)
        )

    def test_blocked_target_ray_still_observes_its_intermediate_first_hit(
        self,
    ) -> None:
        ground_truth = GroundTruthGrid.from_ascii(
            ("#######", ".......", ".......", ".......")
        )
        visible = physical_visible_cells(
            ground_truth, (3, 6), sensor_range=8
        )
        self.assertIn((0, 1), visible)
        self.assertNotIn((0, 0), visible)

    def test_planning_corner_side_state_controls_diagonal_target_visibility(
        self,
    ) -> None:
        cases = (
            (("..", ".?"), True, "FREE"),
            ((".?", ".?"), True, "UNKNOWN"),
            ((".#", ".?"), False, "OCCUPIED"),
        )
        for rows, expected_visible, state_name in cases:
            with self.subTest(side_cell=state_name):
                visible_unknown = optimistic_visible_unknown_cells(
                    belief_from_ascii(rows), (0, 0), sensor_range=2
                )
                self.assertEqual((1, 1) in visible_unknown, expected_visible)


if __name__ == "__main__":
    unittest.main()
