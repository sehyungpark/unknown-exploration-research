import math
import unittest

from src.planning.motion import DIAGONAL_COST, ORTHOGONAL_COST, dijkstra, legal_neighbors

from tests.helpers import belief_from_ascii


class MotionTests(unittest.TestCase):
    def test_orthogonal_movement_cost(self) -> None:
        belief = belief_from_ascii(("..",))
        neighbors = dict(legal_neighbors(belief, (0, 0)))
        self.assertEqual(neighbors[(0, 1)], ORTHOGONAL_COST)

    def test_diagonal_movement_cost(self) -> None:
        belief = belief_from_ascii(("..", ".."))
        neighbors = dict(legal_neighbors(belief, (0, 0)))
        self.assertEqual(neighbors[(1, 1)], DIAGONAL_COST)
        self.assertEqual(neighbors[(1, 1)], math.sqrt(2))

    def test_diagonal_corner_cutting_is_prohibited(self) -> None:
        belief = belief_from_ascii((".?", "?."))
        self.assertNotIn((1, 1), dict(legal_neighbors(belief, (0, 0))))
        self.assertNotIn((1, 1), dijkstra(belief, (0, 0)).distances)

    def test_exact_dijkstra_distances(self) -> None:
        belief = belief_from_ascii(("...", "...", "..."))
        result = dijkstra(belief, (0, 0))
        self.assertEqual(result.distances[(0, 1)], 1.0)
        self.assertAlmostEqual(result.distances[(1, 1)], math.sqrt(2))
        self.assertAlmostEqual(result.distances[(2, 1)], 1 + math.sqrt(2))
        self.assertEqual(result.path_to((0, 2)), ((0, 0), (0, 1), (0, 2)))


if __name__ == "__main__":
    unittest.main()
