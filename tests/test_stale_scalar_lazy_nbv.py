import inspect
import unittest
from unittest.mock import patch

from src.planning import (
    CandidateEvaluation,
    PlanStatus,
    StaleScalarLazyNBV,
    tie_aware_rank_certificate,
)
from src.planning.motion import DijkstraResult
import src.planning.stale_scalar_lazy_nbv as stale_module

from tests.helpers import belief_from_ascii


def evaluation(
    candidate: tuple[int, int], gain: int, distance: float, score: float
) -> CandidateEvaluation:
    return CandidateEvaluation(candidate, frozenset(), gain, distance, score)


def fake_visible_set(gain: int) -> frozenset[tuple[int, int]]:
    return frozenset((99, index) for index in range(gain))


class TieAwareCertificateTests(unittest.TestCase):
    def test_score_clearly_dominates(self) -> None:
        best = evaluation((0, 0), gain=5, distance=2.0, score=2.5)
        remaining = evaluation((0, 1), gain=10, distance=5.0, score=2.0)
        self.assertTrue(tie_aware_rank_certificate(best, (remaining,)))

    def test_equal_score_uses_gain_in_both_directions(self) -> None:
        remaining = evaluation((0, 1), gain=4, distance=4.0, score=1.0)
        losing_best = evaluation((0, 0), gain=3, distance=3.0, score=1.0)
        winning_best = evaluation((0, 0), gain=5, distance=5.0, score=1.0)
        self.assertFalse(tie_aware_rank_certificate(losing_best, (remaining,)))
        self.assertTrue(tie_aware_rank_certificate(winning_best, (remaining,)))

    def test_equal_score_and_gain_use_distance(self) -> None:
        remaining = evaluation((0, 1), gain=4, distance=3.0, score=1.0)
        near_best = evaluation((0, 0), gain=4, distance=2.0, score=1.0)
        far_best = evaluation((0, 0), gain=4, distance=4.0, score=1.0)
        self.assertTrue(tie_aware_rank_certificate(near_best, (remaining,)))
        self.assertFalse(tie_aware_rank_certificate(far_best, (remaining,)))

    def test_full_numeric_tie_uses_coordinate_not_score_greater_equal(self) -> None:
        earlier = evaluation((1, 4), gain=4, distance=2.0, score=2.0)
        later = evaluation((1, 5), gain=4, distance=2.0, score=2.0)
        self.assertTrue(tie_aware_rank_certificate(earlier, (later,)))
        self.assertFalse(tie_aware_rank_certificate(later, (earlier,)))


class StaleScalarCacheLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.belief = belief_from_ascii(("...",))
        self.robot = (0, 0)
        self.a = (0, 1)
        self.b = (0, 2)

    def _plan_snapshot(
        self,
        planner: StaleScalarLazyNBV,
        *,
        robot: tuple[int, int],
        candidates: tuple[tuple[int, int], ...],
        distances: dict[tuple[int, int], float],
        gains: dict[tuple[int, int], int],
    ):
        all_distances = {robot: 0.0, **distances}
        search_result = DijkstraResult(
            source=robot,
            distances=all_distances,
            predecessors={candidate: robot for candidate in candidates},
        )

        def visible(_belief, candidate, _sensor_range):
            return fake_visible_set(gains[candidate])

        with (
            patch.object(stale_module, "dijkstra", return_value=search_result) as search,
            patch.object(
                stale_module,
                "reachable_known_free_candidates",
                return_value=candidates,
            ) as generate,
            patch.object(
                stale_module,
                "optimistic_visible_unknown_cells",
                side_effect=visible,
            ) as exact_visibility,
        ):
            result = planner.plan(self.belief, robot)

        search.assert_called_once_with(self.belief, robot)
        generate.assert_called_once_with(self.belief, robot, all_distances)
        return result, exact_visibility

    def test_first_seen_candidates_initialize_independent_scalar_entries(self) -> None:
        planner = StaleScalarLazyNBV()
        with self.assertRaises(AttributeError):
            planner.sensor_range = 9
        result, exact_visibility = self._plan_snapshot(
            planner,
            robot=self.robot,
            candidates=(self.a, self.b),
            distances={self.a: 1.0, self.b: 2.0},
            gains={self.a: 5, self.b: 1},
        )

        self.assertIs(result.status, PlanStatus.SELECTED)
        self.assertEqual(result.selected_candidate, self.a)
        self.assertEqual(result.exact_gain_evaluations, 2)
        self.assertEqual(exact_visibility.call_count, 2)
        self.assertEqual(planner.cached_gains, {self.a: 5, self.b: 1})
        self.assertTrue(all(type(value) is int for value in planner.cached_gains.values()))
        for record in result.candidate_records:
            self.assertIsNone(record.stale_upper_gain)
            self.assertTrue(record.exact_evaluated_this_cycle)
            self.assertTrue(record.cache_refreshed)

    def test_reevaluation_refreshes_one_entry_and_uses_current_distance(self) -> None:
        planner = StaleScalarLazyNBV()
        self._plan_snapshot(
            planner,
            robot=self.robot,
            candidates=(self.a, self.b),
            distances={self.a: 1.0, self.b: 2.0},
            gains={self.a: 5, self.b: 1},
        )
        result, exact_visibility = self._plan_snapshot(
            planner,
            robot=self.robot,
            candidates=(self.a, self.b),
            distances={self.a: 3.0, self.b: 1.0},
            gains={self.a: 4, self.b: 1},
        )

        by_candidate = {record.candidate: record for record in result.candidate_records}
        self.assertEqual(result.selected_candidate, self.a)
        self.assertEqual(result.exact_gain_evaluations, 1)
        self.assertEqual(result.bound_only_candidate_count, 1)
        self.assertEqual(exact_visibility.call_count, 1)
        self.assertEqual(by_candidate[self.a].current_distance, 3.0)
        self.assertEqual(by_candidate[self.a].stale_upper_gain, 5)
        self.assertEqual(by_candidate[self.a].exact_gain, 4)
        self.assertTrue(by_candidate[self.a].cache_refreshed)
        self.assertEqual(by_candidate[self.b].current_distance, 1.0)
        self.assertFalse(by_candidate[self.b].exact_evaluated_this_cycle)
        self.assertIsNone(by_candidate[self.b].exact_gain)
        self.assertFalse(by_candidate[self.b].cache_refreshed)
        self.assertEqual(planner.cached_gains, {self.a: 4, self.b: 1})

    def test_current_robot_exclusion_preserves_then_reuses_coordinate_cache(self) -> None:
        planner = StaleScalarLazyNBV()
        self._plan_snapshot(
            planner,
            robot=self.robot,
            candidates=(self.a, self.b),
            distances={self.a: 1.0, self.b: 2.0},
            gains={self.a: 5, self.b: 2},
        )
        excluded_result, _ = self._plan_snapshot(
            planner,
            robot=self.a,
            candidates=(self.b,),
            distances={self.b: 1.0},
            gains={self.b: 1},
        )
        self.assertNotIn(self.a, {r.candidate for r in excluded_result.candidate_records})
        self.assertEqual(planner.cached_gains[self.a], 5)

        reused_result, _ = self._plan_snapshot(
            planner,
            robot=self.robot,
            candidates=(self.a, self.b),
            distances={self.a: 2.0, self.b: 1.0},
            gains={self.a: 4, self.b: 1},
        )
        reused = {r.candidate: r for r in reused_result.candidate_records}[self.a]
        self.assertEqual(reused.stale_upper_gain, 5)
        self.assertEqual(reused.exact_gain, 4)
        self.assertEqual(planner.cached_gains, {self.a: 4, self.b: 1})

    def test_zero_stale_bound_certifies_completion_without_reevaluation(self) -> None:
        planner = StaleScalarLazyNBV()
        first, _ = self._plan_snapshot(
            planner,
            robot=self.robot,
            candidates=(self.a,),
            distances={self.a: 1.0},
            gains={self.a: 0},
        )
        second, exact_visibility = self._plan_snapshot(
            planner,
            robot=self.robot,
            candidates=(self.a,),
            distances={self.a: 2.0},
            gains={self.a: 0},
        )

        self.assertIs(first.status, PlanStatus.EXPLORATION_COMPLETE)
        self.assertIs(second.status, PlanStatus.EXPLORATION_COMPLETE)
        self.assertEqual(second.certificate_reason, "all_gain_upper_bounds_zero")
        self.assertEqual(second.exact_gain_evaluations, 0)
        self.assertEqual(second.bound_only_candidate_count, 1)
        self.assertEqual(exact_visibility.call_count, 0)
        self.assertIsNone(second.candidate_records[0].exact_gain)

    def test_negative_cache_is_rejected_before_planning(self) -> None:
        planner = StaleScalarLazyNBV()
        planner._cached_gains[self.a] = -1
        with self.assertRaisesRegex(RuntimeError, "nonnegative int"):
            planner.plan(self.belief, self.robot)

    def test_implementation_has_no_exhaustive_or_algorithm_c_state(self) -> None:
        source = inspect.getsource(stale_module)
        self.assertFalse(hasattr(stale_module, "exhaustive_nbv"))
        self.assertNotIn("inverse_incidence", source)
        self.assertNotIn("cached_visible", source)


if __name__ == "__main__":
    unittest.main()
