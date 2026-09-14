"""Deterministic exhaustive optimistic next-best-view reference."""

from dataclasses import dataclass
from enum import Enum

from src.candidates import reachable_known_free_candidates
from src.mapping import BeliefGrid
from src.sensing import optimistic_visible_unknown_cells
from src.utils import Coord

from .motion import dijkstra

SCORE_EPSILON = 1e-9


class PlanStatus(Enum):
    SELECTED = "SELECTED"
    EXPLORATION_COMPLETE = "EXPLORATION_COMPLETE"


@dataclass(frozen=True, slots=True)
class CandidateEvaluation:
    candidate: Coord
    visible_unknown: frozenset[Coord]
    gain: int
    distance: float
    score: float


@dataclass(frozen=True, slots=True)
class ExhaustiveNBVResult:
    status: PlanStatus
    selected_candidate: Coord | None
    selected_gain: int
    selected_distance: float | None
    selected_score: float
    eligible_candidate_count: int
    exact_gain_evaluations: int
    evaluations: tuple[CandidateEvaluation, ...]
    selected_path: tuple[Coord, ...]


def candidate_rank_key(evaluation: CandidateEvaluation) -> tuple[float, int, float, int, int]:
    """Ascending key implementing the exact specified total order."""

    row, col = evaluation.candidate
    return (
        -evaluation.score,
        -evaluation.gain,
        evaluation.distance,
        row,
        col,
    )


def choose_best_candidate(
    evaluations: tuple[CandidateEvaluation, ...],
) -> CandidateEvaluation:
    if not evaluations:
        raise ValueError("cannot select from an empty evaluation set")
    return min(evaluations, key=candidate_rank_key)


def exhaustive_nbv(
    belief: BeliefGrid,
    robot: Coord,
    sensor_range: float = 8,
) -> ExhaustiveNBVResult:
    """Evaluate exact optimistic gain for every eligible candidate once."""

    distance_result = dijkstra(belief, robot)
    candidates = reachable_known_free_candidates(
        belief, robot, distance_result.distances
    )
    evaluations: list[CandidateEvaluation] = []
    for candidate in candidates:
        visible_unknown = optimistic_visible_unknown_cells(
            belief, candidate, sensor_range
        )
        gain = len(visible_unknown)
        distance = distance_result.distances[candidate]
        score = gain / (distance + SCORE_EPSILON)
        evaluations.append(
            CandidateEvaluation(
                candidate=candidate,
                visible_unknown=visible_unknown,
                gain=gain,
                distance=distance,
                score=score,
            )
        )

    frozen_evaluations = tuple(evaluations)
    if not frozen_evaluations or all(item.gain == 0 for item in frozen_evaluations):
        return ExhaustiveNBVResult(
            status=PlanStatus.EXPLORATION_COMPLETE,
            selected_candidate=None,
            selected_gain=0,
            selected_distance=None,
            selected_score=0.0,
            eligible_candidate_count=len(candidates),
            exact_gain_evaluations=len(candidates),
            evaluations=frozen_evaluations,
            selected_path=(),
        )

    selected = choose_best_candidate(frozen_evaluations)
    return ExhaustiveNBVResult(
        status=PlanStatus.SELECTED,
        selected_candidate=selected.candidate,
        selected_gain=selected.gain,
        selected_distance=selected.distance,
        selected_score=selected.score,
        eligible_candidate_count=len(candidates),
        exact_gain_evaluations=len(candidates),
        evaluations=frozen_evaluations,
        selected_path=distance_result.path_to(selected.candidate),
    )
