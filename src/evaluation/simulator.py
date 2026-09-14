"""Atomic sense-plan-move cycle for the deterministic common simulator."""

from dataclasses import dataclass

from src.environment import GridWorld, GroundTruthGrid
from src.planning import ExhaustiveNBVResult, PlanStatus, exhaustive_nbv
from src.planning.motion import legal_neighbors
from src.sensing import physical_scan
from src.utils import Coord


@dataclass(frozen=True, slots=True)
class AtomicCycleResult:
    planning_snapshot: int
    plan: ExhaustiveNBVResult
    traversed_path: tuple[Coord, ...]
    arrival_observation_changes: frozenset[Coord]
    arrival_snapshot: int


class ExplorationSimulator:
    """Minimal simulator with sensing only initially and at target arrival."""

    def __init__(
        self,
        ground_truth: GroundTruthGrid,
        start: Coord,
        sensor_range: float = 8,
    ) -> None:
        if sensor_range < 0:
            raise ValueError("sensor range must be nonnegative")
        self.world = GridWorld.unexplored(ground_truth, start)
        self.sensor_range = sensor_range
        self.snapshot_index = 0
        self.scan_count = 0
        self._sense_at_current_pose()

    def _sense_at_current_pose(self) -> frozenset[Coord]:
        observations = physical_scan(
            self.world.ground_truth, self.world.robot, self.sensor_range
        )
        changed = self.world.belief.apply_observations(observations)
        self.scan_count += 1
        return changed

    def plan(self) -> ExhaustiveNBVResult:
        return exhaustive_nbv(
            self.world.belief, self.world.robot, self.sensor_range
        )

    def execute_atomic_cycle(self) -> AtomicCycleResult:
        """Plan on one frozen snapshot, move fully, then scan once at arrival."""

        planning_snapshot = self.snapshot_index
        plan = self.plan()
        if plan.status is PlanStatus.EXPLORATION_COMPLETE:
            return AtomicCycleResult(
                planning_snapshot=planning_snapshot,
                plan=plan,
                traversed_path=(),
                arrival_observation_changes=frozenset(),
                arrival_snapshot=self.snapshot_index,
            )

        path = plan.selected_path
        if not path or path[0] != self.world.robot:
            raise RuntimeError("selected path must start at the current robot cell")
        for source, target in zip(path, path[1:]):
            legal_targets = {neighbor for neighbor, _ in legal_neighbors(self.world.belief, source)}
            if target not in legal_targets:
                raise RuntimeError(f"selected path contains an illegal move: {source} -> {target}")

        self.world.robot = path[-1]
        changed = self._sense_at_current_pose()
        self.snapshot_index += 1
        return AtomicCycleResult(
            planning_snapshot=planning_snapshot,
            plan=plan,
            traversed_path=path,
            arrival_observation_changes=changed,
            arrival_snapshot=self.snapshot_index,
        )
