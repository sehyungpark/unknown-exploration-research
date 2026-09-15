import inspect
import unittest
from unittest.mock import patch

from src.mapping import BeliefGrid
from src.planning import (
    CandidateEvaluation,
    ChangeAwareLazyNBV,
    PlanStatus,
    exact_refresh_candidate,
    exhaustive_nbv,
    tie_aware_rank_certificate,
)
from src.planning.motion import DijkstraResult
from src.sensing import optimistic_visible_unknown_cells
from src.utils import TruthState
import src.planning.change_aware_lazy_nbv as change_module

from tests.helpers import belief_from_ascii


def evaluation(
    candidate: tuple[int, int], gain: int, distance: float, score: float
) -> CandidateEvaluation:
    return CandidateEvaluation(candidate, frozenset(), gain, distance, score)


def fake_visible_set(
    candidate: tuple[int, int], gain: int
) -> frozenset[tuple[int, int]]:
    row = 100 + candidate[0] * 10 + candidate[1]
    return frozenset((row, index) for index in range(gain))


class ChangeAwareLazyPlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.belief = belief_from_ascii(("...",))
        self.robot = (0, 0)
        self.a = (0, 1)
        self.b = (0, 2)

    def _plan_snapshot(
        self,
        planner: ChangeAwareLazyNBV,
        *,
        candidates: tuple[tuple[int, int], ...],
        distances: dict[tuple[int, int], float],
        gains: dict[tuple[int, int], int],
        belief: BeliefGrid | None = None,
        robot: tuple[int, int] | None = None,
        exact_sets: dict[tuple[int, int], frozenset[tuple[int, int]]] | None = None,
    ):
        planning_belief = self.belief if belief is None else belief
        planning_robot = self.robot if robot is None else robot
        all_distances = {planning_robot: 0.0, **distances}
        search_result = DijkstraResult(
            source=planning_robot,
            distances=all_distances,
            predecessors={candidate: planning_robot for candidate in candidates},
        )

        def refresh(cache, actual_belief, candidate, sensor_range):
            self.assertIs(actual_belief, planning_belief)
            self.assertEqual(sensor_range, planner.sensor_range)
            visible = (
                fake_visible_set(candidate, gains[candidate])
                if exact_sets is None
                else exact_sets[candidate]
            )
            cache.install_exact(candidate, visible)
            return visible

        with (
            patch.object(
                change_module,
                "dijkstra",
                return_value=search_result,
            ) as search,
            patch.object(
                change_module,
                "reachable_known_free_candidates",
                return_value=candidates,
            ) as generate,
            patch.object(
                change_module,
                "exact_refresh_candidate",
                side_effect=refresh,
            ) as exact_refresh,
        ):
            result = planner.plan(planning_belief, planning_robot)

        search.assert_called_once_with(planning_belief, planning_robot)
        generate.assert_called_once_with(
            planning_belief,
            planning_robot,
            all_distances,
        )
        return result, exact_refresh

    def test_a_first_seen_candidates_exact_initialize(self) -> None:
        planner = ChangeAwareLazyNBV()

        result, exact_refresh = self._plan_snapshot(
            planner,
            candidates=(self.a, self.b),
            distances={self.a: 1.0, self.b: 2.0},
            gains={self.a: 5, self.b: 2},
        )

        self.assertEqual(result.exact_gain_evaluations, 2)
        self.assertEqual(exact_refresh.call_count, 2)
        for record in result.candidate_records:
            self.assertIsNone(record.change_aware_upper_gain_at_entry)
            self.assertTrue(record.exact_evaluated_this_cycle)
            self.assertTrue(record.cache_refreshed)
            self.assertEqual(
                planner.cache.bound_counts[record.candidate],
                record.current_exact_gain,
            )

    def test_b_temporarily_ineligible_candidate_cache_persists_and_updates(self) -> None:
        belief = belief_from_ascii(("...?",))
        planner = ChangeAwareLazyNBV()
        cell = (0, 3)
        exact_sets = {self.a: frozenset({cell}), self.b: frozenset({cell})}
        self._plan_snapshot(
            planner,
            belief=belief,
            candidates=(self.a, self.b),
            distances={self.a: 1.0, self.b: 2.0},
            gains={self.a: 1, self.b: 1},
            exact_sets=exact_sets,
        )

        belief.apply_observations({cell: TruthState.FREE})
        self._plan_snapshot(
            planner,
            belief=belief,
            candidates=(self.b,),
            distances={self.b: 2.0},
            gains={self.b: 0},
            exact_sets={self.b: frozenset()},
        )
        self.assertIn(self.a, planner.cache.cached_visible_unknown)
        self.assertEqual(planner.cache.bound_counts[self.a], 0)

        returned, exact_refresh = self._plan_snapshot(
            planner,
            belief=belief,
            candidates=(self.a, self.b),
            distances={self.a: 1.0, self.b: 2.0},
            gains={self.a: 0, self.b: 0},
            exact_sets={self.a: frozenset(), self.b: frozenset()},
        )
        returned_a = {r.candidate: r for r in returned.candidate_records}[self.a]
        self.assertEqual(returned_a.change_aware_upper_gain_at_entry, 0)
        self.assertFalse(returned_a.exact_evaluated_this_cycle)
        self.assertEqual(exact_refresh.call_count, 0)

    def test_c_exactly_one_dijkstra_per_planning_snapshot(self) -> None:
        planner = ChangeAwareLazyNBV()

        self._plan_snapshot(
            planner,
            candidates=(self.a,),
            distances={self.a: 1.0},
            gains={self.a: 1},
        )
        self._plan_snapshot(
            planner,
            candidates=(self.a,),
            distances={self.a: 2.0},
            gains={self.a: 1},
        )

    def test_d_upper_score_uses_current_distance(self) -> None:
        planner = ChangeAwareLazyNBV()
        self._plan_snapshot(
            planner,
            candidates=(self.a, self.b),
            distances={self.a: 1.0, self.b: 2.0},
            gains={self.a: 5, self.b: 1},
        )

        result, _ = self._plan_snapshot(
            planner,
            candidates=(self.a, self.b),
            distances={self.a: 5.0, self.b: 1.0},
            gains={self.a: 4, self.b: 1},
        )

        records = {record.candidate: record for record in result.candidate_records}
        self.assertEqual(records[self.a].current_distance, 5.0)
        self.assertEqual(
            records[self.a].change_aware_upper_score_at_entry,
            5 / (5.0 + change_module.SCORE_EPSILON),
        )
        self.assertEqual(records[self.b].current_distance, 1.0)

    def test_e_simple_certificate_skips_dominated_candidate(self) -> None:
        planner = ChangeAwareLazyNBV()
        self._plan_snapshot(
            planner,
            candidates=(self.a, self.b),
            distances={self.a: 1.0, self.b: 10.0},
            gains={self.a: 5, self.b: 1},
        )

        result, exact_refresh = self._plan_snapshot(
            planner,
            candidates=(self.a, self.b),
            distances={self.a: 1.0, self.b: 10.0},
            gains={self.a: 4, self.b: 1},
        )

        records = {record.candidate: record for record in result.candidate_records}
        self.assertEqual(result.selected_candidate, self.a)
        self.assertEqual(result.exact_gain_evaluations, 1)
        self.assertEqual(result.bound_only_candidate_count, 1)
        self.assertEqual(exact_refresh.call_count, 1)
        self.assertFalse(records[self.b].exact_evaluated_this_cycle)

    def test_f_failed_certificate_forces_optimistic_best_reevaluation(self) -> None:
        planner = ChangeAwareLazyNBV()
        self._plan_snapshot(
            planner,
            candidates=(self.a, self.b),
            distances={self.a: 1.0, self.b: 2.0},
            gains={self.a: 5, self.b: 4},
        )

        result, exact_refresh = self._plan_snapshot(
            planner,
            candidates=(self.a, self.b),
            distances={self.a: 1.0, self.b: 2.0},
            gains={self.a: 1, self.b: 3},
        )

        self.assertEqual(result.selected_candidate, self.b)
        self.assertEqual(result.exact_gain_evaluations, 2)
        self.assertEqual(exact_refresh.call_count, 2)

    def test_g_selected_candidate_is_always_current_exact(self) -> None:
        planner = ChangeAwareLazyNBV()
        result, _ = self._plan_snapshot(
            planner,
            candidates=(self.a, self.b),
            distances={self.a: 1.0, self.b: 2.0},
            gains={self.a: 3, self.b: 1},
        )

        selected = next(
            record
            for record in result.candidate_records
            if record.candidate == result.selected_candidate
        )
        self.assertTrue(selected.exact_evaluated_this_cycle)
        self.assertIsNotNone(selected.current_exact_gain)
        self.assertIsNotNone(selected.current_exact_score)
        self.assertEqual(result.selected_gain, selected.current_exact_gain)
        self.assertEqual(result.selected_score, selected.current_exact_score)

    def test_h_full_score_tie_uses_gain(self) -> None:
        lower_gain = evaluation((0, 2), gain=3, distance=3.0, score=1.0)
        higher_gain = evaluation((0, 1), gain=4, distance=4.0, score=1.0)
        self.assertTrue(tie_aware_rank_certificate(higher_gain, (lower_gain,)))
        self.assertFalse(tie_aware_rank_certificate(lower_gain, (higher_gain,)))

    def test_i_score_and_gain_tie_uses_distance(self) -> None:
        near = evaluation((0, 2), gain=4, distance=2.0, score=1.0)
        far = evaluation((0, 1), gain=4, distance=3.0, score=1.0)
        self.assertTrue(tie_aware_rank_certificate(near, (far,)))
        self.assertFalse(tie_aware_rank_certificate(far, (near,)))

    def test_j_full_numeric_tie_uses_lexicographic_coordinate(self) -> None:
        earlier = evaluation((0, 1), gain=4, distance=2.0, score=2.0)
        later = evaluation((0, 2), gain=4, distance=2.0, score=2.0)
        self.assertTrue(tie_aware_rank_certificate(earlier, (later,)))
        self.assertFalse(tie_aware_rank_certificate(later, (earlier,)))

    def test_k_equal_score_does_not_use_a_greater_equal_shortcut(self) -> None:
        planner = ChangeAwareLazyNBV()
        self._plan_snapshot(
            planner,
            candidates=(self.a,),
            distances={self.a: 2.0},
            gains={self.a: 4},
        )
        new_later = self.b

        result, exact_refresh = self._plan_snapshot(
            planner,
            candidates=(self.a, new_later),
            distances={self.a: 2.0, new_later: 2.0},
            gains={self.a: 4, new_later: 4},
        )

        self.assertEqual(result.selected_candidate, self.a)
        self.assertEqual(result.exact_gain_evaluations, 2)
        self.assertEqual(exact_refresh.call_count, 2)

    def test_l_all_zero_upper_bounds_certify_without_reevaluation(self) -> None:
        planner = ChangeAwareLazyNBV()
        self._plan_snapshot(
            planner,
            candidates=(self.a,),
            distances={self.a: 1.0},
            gains={self.a: 0},
        )

        result, exact_refresh = self._plan_snapshot(
            planner,
            candidates=(self.a,),
            distances={self.a: 2.0},
            gains={self.a: 0},
        )

        self.assertIs(result.status, PlanStatus.EXPLORATION_COMPLETE)
        self.assertEqual(result.certificate_reason, "all_gain_upper_bounds_zero")
        self.assertEqual(result.exact_gain_evaluations, 0)
        self.assertEqual(result.bound_only_candidate_count, 1)
        self.assertEqual(exact_refresh.call_count, 0)

    def test_m_positive_upper_bound_prevents_premature_completion(self) -> None:
        planner = ChangeAwareLazyNBV()
        self._plan_snapshot(
            planner,
            candidates=(self.a,),
            distances={self.a: 1.0},
            gains={self.a: 2},
        )

        result, exact_refresh = self._plan_snapshot(
            planner,
            candidates=(self.a,),
            distances={self.a: 1.0},
            gains={self.a: 0},
        )

        self.assertIs(result.status, PlanStatus.EXPLORATION_COMPLETE)
        self.assertEqual(result.certificate_reason, "all_gain_upper_bounds_zero")
        self.assertEqual(result.exact_gain_evaluations, 1)
        self.assertEqual(exact_refresh.call_count, 1)
        self.assertEqual(result.candidate_records[0].current_exact_gain, 0)

    def test_n_occupied_blocker_loose_bound_is_reevaluated_when_required(self) -> None:
        belief = belief_from_ascii(("..???",))
        planner = ChangeAwareLazyNBV()
        candidate = (0, 1)
        first = planner.plan(belief, self.robot)
        self.assertEqual(first.selected_candidate, candidate)
        historical = planner.cache.cached_visible_unknown[candidate]
        self.assertEqual(historical, frozenset({(0, 2), (0, 3), (0, 4)}))

        belief.apply_observations({(0, 2): TruthState.OCCUPIED})

        def observe_refresh(cache, actual_belief, actual_candidate, sensor_range):
            self.assertEqual(actual_candidate, candidate)
            self.assertEqual(cache.cached_visible_unknown[candidate], historical)
            self.assertEqual(cache.bound_counts[candidate], 2)
            return exact_refresh_candidate(
                cache,
                actual_belief,
                actual_candidate,
                sensor_range,
            )

        with patch.object(
            change_module,
            "exact_refresh_candidate",
            side_effect=observe_refresh,
        ) as refresh:
            second = planner.plan(belief, self.robot)

        self.assertEqual(refresh.call_count, 1)
        self.assertIs(second.status, PlanStatus.EXPLORATION_COMPLETE)
        record = second.candidate_records[0]
        self.assertEqual(record.change_aware_upper_gain_at_entry, 2)
        self.assertEqual(record.current_exact_gain, 0)

    def test_o_exact_refresh_tightens_bound_and_preserves_entry_diagnostic(self) -> None:
        planner = ChangeAwareLazyNBV()
        self._plan_snapshot(
            planner,
            candidates=(self.a,),
            distances={self.a: 1.0},
            gains={self.a: 5},
        )

        result, _ = self._plan_snapshot(
            planner,
            candidates=(self.a,),
            distances={self.a: 1.0},
            gains={self.a: 2},
        )

        record = result.candidate_records[0]
        self.assertEqual(record.change_aware_upper_gain_at_entry, 5)
        self.assertEqual(record.current_exact_gain, 2)
        self.assertEqual(planner.cache.bound_counts[self.a], 2)
        self.assertEqual(
            len(planner.cache.cached_visible_unknown[self.a]),
            planner.cache.bound_counts[self.a],
        )

    def test_p_belief_synchronization_precedes_bound_diagnostics(self) -> None:
        belief = belief_from_ascii(("..?",))
        planner = ChangeAwareLazyNBV()
        first = planner.plan(belief, self.robot)
        candidate = (0, 1)
        self.assertEqual(first.selected_candidate, candidate)
        self.assertEqual(planner.cache.bound_counts[candidate], 1)

        belief.apply_observations({(0, 2): TruthState.OCCUPIED})
        second = planner.plan(belief, self.robot)

        record = second.candidate_records[0]
        self.assertEqual(second.synchronized_newly_known_cells, frozenset({(0, 2)}))
        self.assertEqual(record.change_aware_upper_gain_at_entry, 0)
        self.assertEqual(record.change_aware_upper_score_at_entry, 0.0)
        self.assertEqual(second.exact_gain_evaluations, 0)

    def test_q_obsolete_snapshot_installation_remains_rejected(self) -> None:
        belief = belief_from_ascii(("..?",))
        planner = ChangeAwareLazyNBV()
        planner.plan(belief, self.robot)
        candidate = (0, 1)
        obsolete = planner.cache.cached_visible_unknown[candidate]
        belief.apply_observations({(0, 2): TruthState.FREE})
        planner.plan(belief, self.robot)
        synchronized_state = (
            dict(planner.cache.cached_visible_unknown),
            dict(planner.cache.bound_counts),
            dict(planner.cache.inverse_incidence),
            planner.cache.reported_known_cells,
        )

        with self.assertRaisesRegex(ValueError, "already reported known"):
            planner.cache.install_exact(candidate, obsolete)

        self.assertEqual(
            (
                dict(planner.cache.cached_visible_unknown),
                dict(planner.cache.bound_counts),
                dict(planner.cache.inverse_incidence),
                planner.cache.reported_known_cells,
            ),
            synchronized_state,
        )

    def test_r_reset_clears_all_episode_state_and_preserves_configuration(self) -> None:
        planner = ChangeAwareLazyNBV(sensor_range=3.5)
        self._plan_snapshot(
            planner,
            candidates=(self.a,),
            distances={self.a: 1.0},
            gains={self.a: 2},
        )
        self.assertIsNotNone(planner.last_synchronized_snapshot)

        planner.reset()
        planner.reset()

        self.assertEqual(planner.sensor_range, 3.5)
        self.assertIsNone(planner.last_synchronized_snapshot)
        self.assertEqual(planner.cache.cached_visible_unknown, {})
        self.assertEqual(planner.cache.bound_counts, {})
        self.assertEqual(planner.cache.inverse_incidence, {})
        self.assertEqual(planner.cache.reported_known_cells, frozenset())

    def test_s_reset_prevents_cross_map_cache_leakage(self) -> None:
        planner = ChangeAwareLazyNBV()
        self._plan_snapshot(
            planner,
            candidates=(self.a,),
            distances={self.a: 1.0},
            gains={self.a: 1},
        )
        planner.reset()
        second_belief = belief_from_ascii(("..??",))

        result, exact_refresh = self._plan_snapshot(
            planner,
            belief=second_belief,
            candidates=(self.a,),
            distances={self.a: 1.0},
            gains={self.a: 7},
        )

        self.assertEqual(exact_refresh.call_count, 1)
        self.assertIsNone(
            result.candidate_records[0].change_aware_upper_gain_at_entry
        )
        self.assertEqual(result.candidate_records[0].current_exact_gain, 7)
        self.assertEqual(planner.cache.bound_counts[self.a], 7)

    def test_t_sensor_configuration_is_fixed(self) -> None:
        with self.assertRaisesRegex(ValueError, "nonnegative"):
            ChangeAwareLazyNBV(sensor_range=-1)
        planner = ChangeAwareLazyNBV(sensor_range=4.5)
        with self.assertRaises(AttributeError):
            planner.sensor_range = 8
        planner.reset()
        self.assertEqual(planner.sensor_range, 4.5)

    def test_u_first_call_synchronizes_post_initial_scan_before_install(self) -> None:
        belief = belief_from_ascii(("..??",))
        planner = ChangeAwareLazyNBV()
        expected_reported = frozenset({(0, 0), (0, 1)})

        def observe_refresh(cache, actual_belief, candidate, sensor_range):
            self.assertEqual(cache.reported_known_cells, expected_reported)
            return exact_refresh_candidate(
                cache,
                actual_belief,
                candidate,
                sensor_range,
            )

        with patch.object(
            change_module,
            "exact_refresh_candidate",
            side_effect=observe_refresh,
        ):
            result = planner.plan(belief, self.robot)

        candidate = (0, 1)
        exact = optimistic_visible_unknown_cells(belief, candidate, 8)
        self.assertEqual(result.synchronized_newly_known_cells, expected_reported)
        self.assertEqual(planner.cache.reported_known_cells, expected_reported)
        self.assertEqual(planner.cache.cached_visible_unknown[candidate], exact)
        self.assertTrue(exact.isdisjoint(expected_reported))
        self.assertEqual(planner.cache.bound_counts[candidate], len(exact))

    def test_small_frozen_snapshot_choices_match_exhaustive_a(self) -> None:
        snapshots = (
            (belief_from_ascii(("...??",)), (0, 0)),
            (belief_from_ascii(("..#??",)), (0, 0)),
        )
        for belief, robot in snapshots:
            with self.subTest(snapshot=belief.snapshot()):
                exhaustive = exhaustive_nbv(belief, robot, sensor_range=8)
                change_aware = ChangeAwareLazyNBV(8).plan(belief, robot)
                self.assertIs(change_aware.status, exhaustive.status)
                self.assertEqual(
                    change_aware.selected_candidate,
                    exhaustive.selected_candidate,
                )
                self.assertEqual(change_aware.selected_gain, exhaustive.selected_gain)
                self.assertEqual(
                    change_aware.selected_distance,
                    exhaustive.selected_distance,
                )
                self.assertEqual(change_aware.selected_score, exhaustive.selected_score)
                self.assertEqual(change_aware.selected_path, exhaustive.selected_path)

    def test_selector_reuses_common_helpers_without_algorithm_b_state(self) -> None:
        source = inspect.getsource(change_module)
        self.assertNotIn("StaleScalarLazyNBV", source)
        self.assertNotIn("_cached_gains", source)
        self.assertNotIn("optimistic_visible_unknown_cells", source)
        self.assertFalse(hasattr(change_module, "exhaustive_nbv"))


if __name__ == "__main__":
    unittest.main()
