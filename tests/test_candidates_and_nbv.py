import unittest
from unittest.mock import patch

from src.candidates import reachable_known_free_candidates
from src.planning.exhaustive_nbv import (
    CandidateEvaluation,
    PlanStatus,
    choose_best_candidate,
    exhaustive_nbv,
)
from src.planning.motion import dijkstra

from tests.helpers import belief_from_ascii


def evaluation(
    candidate: tuple[int, int], gain: int, distance: float, score: float
) -> CandidateEvaluation:
    return CandidateEvaluation(candidate, frozenset(), gain, distance, score)


class CandidateGenerationTests(unittest.TestCase):
    def test_unreachable_known_free_cell_is_excluded(self) -> None:
        belief = belief_from_ascii((".?.",))
        distances = dijkstra(belief, (0, 0)).distances
        self.assertEqual(
            reachable_known_free_candidates(belief, (0, 0), distances), ()
        )

    def test_all_reachable_known_free_except_robot_are_candidates(self) -> None:
        belief = belief_from_ascii(("...",))
        distances = dijkstra(belief, (0, 0)).distances
        self.assertEqual(
            reachable_known_free_candidates(belief, (0, 0), distances),
            ((0, 1), (0, 2)),
        )


class ExhaustiveNBVTests(unittest.TestCase):
    def test_returns_visible_unknown_set_not_only_count(self) -> None:
        belief = belief_from_ascii(("..??",))
        result = exhaustive_nbv(belief, (0, 0), sensor_range=8)
        by_candidate = {item.candidate: item for item in result.evaluations}
        self.assertEqual(
            by_candidate[(0, 1)].visible_unknown,
            frozenset({(0, 2), (0, 3)}),
        )
        self.assertEqual(by_candidate[(0, 1)].gain, 2)
        self.assertEqual(result.exact_gain_evaluations, 1)
        self.assertEqual(result.eligible_candidate_count, 1)

    def test_all_zero_gain_returns_complete(self) -> None:
        belief = belief_from_ascii(("...",))
        result = exhaustive_nbv(belief, (0, 1), sensor_range=8)
        self.assertIs(result.status, PlanStatus.EXPLORATION_COMPLETE)
        self.assertIsNone(result.selected_candidate)
        self.assertEqual(result.selected_gain, 0)
        self.assertEqual(result.exact_gain_evaluations, 2)

    def test_one_dijkstra_search_is_used_for_a_planning_snapshot(self) -> None:
        belief = belief_from_ascii(("..??",))
        with patch("src.planning.exhaustive_nbv.dijkstra", wraps=dijkstra) as search:
            exhaustive_nbv(belief, (0, 0), sensor_range=8)
        search.assert_called_once_with(belief, (0, 0))

    def test_score_tie_prefers_larger_gain(self) -> None:
        low_gain = evaluation((0, 0), gain=2, distance=2.0, score=1.0)
        high_gain = evaluation((9, 9), gain=3, distance=3.0, score=1.0)
        self.assertIs(choose_best_candidate((low_gain, high_gain)), high_gain)

    def test_gain_tie_prefers_smaller_distance(self) -> None:
        far = evaluation((0, 0), gain=2, distance=3.0, score=1.0)
        near = evaluation((9, 9), gain=2, distance=2.0, score=1.0)
        self.assertIs(choose_best_candidate((far, near)), near)

    def test_distance_tie_prefers_smaller_row(self) -> None:
        later = evaluation((2, 0), gain=2, distance=2.0, score=1.0)
        earlier = evaluation((1, 9), gain=2, distance=2.0, score=1.0)
        self.assertIs(choose_best_candidate((later, earlier)), earlier)

    def test_coordinate_tie_prefers_smaller_column(self) -> None:
        later = evaluation((1, 5), gain=2, distance=2.0, score=1.0)
        earlier = evaluation((1, 4), gain=2, distance=2.0, score=1.0)
        self.assertIs(choose_best_candidate((later, earlier)), earlier)


if __name__ == "__main__":
    unittest.main()
