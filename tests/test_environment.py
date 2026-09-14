import unittest

from src.environment import GridWorld, GroundTruthGrid
from src.mapping import BeliefGrid
from src.utils import BeliefState, TruthState


class GroundTruthValidationTests(unittest.TestCase):
    def test_rejects_empty_and_ragged_maps(self) -> None:
        with self.assertRaises(ValueError):
            GroundTruthGrid.from_ascii(())
        with self.assertRaises(ValueError):
            GroundTruthGrid.from_ascii(("..", "."))

    def test_validates_start_cell(self) -> None:
        grid = GroundTruthGrid.from_ascii((".#", ".."))
        with self.assertRaises(ValueError):
            GridWorld.unexplored(grid, (0, 1))
        with self.assertRaises(ValueError):
            GridWorld.unexplored(grid, (2, 0))
        world = GridWorld.unexplored(grid, (0, 0))
        self.assertEqual(world.belief.state((0, 0)), BeliefState.FREE)


class MonotoneBeliefTests(unittest.TestCase):
    def test_only_unknown_to_known_updates_are_allowed(self) -> None:
        belief = BeliefGrid.unknown(1, 2)
        changed = belief.apply_observations({(0, 0): TruthState.FREE})
        self.assertEqual(changed, frozenset({(0, 0)}))
        self.assertEqual(
            belief.apply_observations({(0, 0): TruthState.FREE}), frozenset()
        )
        with self.assertRaises(ValueError):
            belief.apply_observations({(0, 0): TruthState.OCCUPIED})

    def test_invalid_batch_is_atomic(self) -> None:
        belief = BeliefGrid.unknown(1, 2)
        belief.apply_observations({(0, 0): TruthState.FREE})
        with self.assertRaises(ValueError):
            belief.apply_observations(
                {(0, 0): TruthState.OCCUPIED, (0, 1): TruthState.FREE}
            )
        self.assertEqual(belief.state((0, 1)), BeliefState.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
