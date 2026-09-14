"""Validated pairing of ground truth, belief, and exact robot pose."""

from dataclasses import dataclass

from src.mapping import BeliefGrid
from src.utils import Coord, TruthState

from .grid import GroundTruthGrid


@dataclass(slots=True)
class GridWorld:
    ground_truth: GroundTruthGrid
    belief: BeliefGrid
    robot: Coord

    @classmethod
    def unexplored(cls, ground_truth: GroundTruthGrid, start: Coord) -> "GridWorld":
        if not ground_truth.in_bounds(start):
            raise ValueError(f"start cell outside ground-truth grid: {start}")
        if ground_truth.state(start) is not TruthState.FREE:
            raise ValueError(f"start cell must be ground-truth FREE: {start}")
        belief = BeliefGrid.unknown(ground_truth.height, ground_truth.width)
        belief.apply_observations({start: TruthState.FREE})
        return cls(ground_truth=ground_truth, belief=belief, robot=start)
