import unittest

from src.evaluation.c_star_instrumentation import (
    measure_c_star_audit,
    measure_c_star_core,
)
from src.planning import ChangeAwareStarNBV, PlanStatus
from src.planning.bitmask import (
    coord_index,
    index_coord,
    coords_to_mask,
    mask_to_coords,
    sensor_range_mask,
    unknown_mask_from_belief,
)
from src.sensing import cells_within_range, optimistic_visible_unknown_cells
from src.utils import TruthState

from tests.helpers import belief_from_ascii


class BitmaskTests(unittest.TestCase):
    def test_row_major_round_trip(self) -> None:
        shape = (3, 4)
        for row in range(shape[0]):
            for col in range(shape[1]):
                coord = (row, col)
                self.assertEqual(index_coord(coord_index(coord, shape), shape), coord)

    def test_mask_round_trip_and_intersection_semantics(self) -> None:
        shape = (4, 5)
        left = frozenset({(0, 0), (1, 2), (3, 4)})
        right = frozenset({(1, 2), (2, 2), (3, 4)})
        left_mask = coords_to_mask(left, shape)
        right_mask = coords_to_mask(right, shape)
        self.assertEqual(mask_to_coords(left_mask, shape), left)
        self.assertEqual(mask_to_coords(left_mask & right_mask, shape), left & right)
        self.assertEqual((left_mask & right_mask).bit_count(), len(left & right))

    def test_range_mask_matches_canonical_cells_within_range(self) -> None:
        shape = (7, 8)
        for origin in ((0, 0), (0, 7), (3, 4), (6, 7)):
            for radius in (0.0, 1.0, 2.5, 8.0):
                expected = frozenset(cells_within_range(origin, shape, radius))
                actual = mask_to_coords(sensor_range_mask(origin, shape, radius), shape)
                self.assertEqual(actual, expected)

    def test_unknown_mask_matches_belief(self) -> None:
        belief = belief_from_ascii(
            (
                ".??",
                ".#?",
                "...",
            )
        )
        actual = mask_to_coords(unknown_mask_from_belief(belief), belief.shape)
        self.assertEqual(actual, frozenset({(0, 1), (0, 2), (1, 2)}))


class CStarPlannerTests(unittest.TestCase):
    def test_first_call_initializes_and_second_requires_explicit_delta(self) -> None:
        belief = belief_from_ascii(
            (
                "...",
                ".??",
                "...",
            )
        )
        planner = ChangeAwareStarNBV(sensor_range=2)
        planner.plan(belief, (0, 0))
        with self.assertRaises(ValueError):
            planner.plan(belief, (0, 0))

    def test_reported_cell_must_actually_be_known(self) -> None:
        belief = belief_from_ascii(
            (
                "...",
                ".??",
                "...",
            )
        )
        planner = ChangeAwareStarNBV(sensor_range=2)
        planner.plan(belief, (0, 0))
        with self.assertRaises(ValueError):
            planner.plan(
                belief,
                (0, 0),
                newly_known=frozenset({(1, 1)}),
            )

    def test_range_upper_bound_is_admissible(self) -> None:
        belief = belief_from_ascii(
            (
                ".....",
                ".???.",
                ".?#?.",
                ".???.",
                ".....",
            )
        )
        planner = ChangeAwareStarNBV(sensor_range=2)
        result = planner.plan(belief, (0, 0))
        exact_by_candidate = {
            record.candidate: len(
                optimistic_visible_unknown_cells(
                    belief, record.candidate, planner.sensor_range
                )
            )
            for record in result.candidate_records
        }
        for record in result.candidate_records:
            self.assertLessEqual(
                exact_by_candidate[record.candidate],
                record.range_upper_gain,
            )

    def test_exact_selected_candidate_and_audit(self) -> None:
        belief = belief_from_ascii(
            (
                ".....",
                ".???.",
                ".?#?.",
                ".???.",
                ".....",
            )
        )
        planner = ChangeAwareStarNBV(sensor_range=2)
        result = planner.plan(belief, (0, 0))
        if result.status is PlanStatus.SELECTED:
            selected_record = next(
                record
                for record in result.candidate_records
                if record.candidate == result.selected_candidate
            )
            self.assertTrue(selected_record.exact_evaluated_this_cycle)
        report = planner.audit(belief)
        self.assertTrue(report.unknown_mask_matches_belief)

    def test_delta_clears_unknown_bits_without_inverse_incidence(self) -> None:
        belief = belief_from_ascii(
            (
                "...",
                ".??",
                "...",
            )
        )
        planner = ChangeAwareStarNBV(sensor_range=2)
        planner.plan(belief, (0, 0))
        changed = belief.apply_observations({(1, 1): TruthState.FREE})
        result = planner.plan(belief, (0, 0), newly_known=changed)
        self.assertEqual(result.counters.unknown_mask_delta_cell_update_count, 1)
        self.assertFalse(hasattr(planner, "_inverse_incidence"))
        planner.audit(belief)

    def test_first_seen_range_only_candidates_can_be_pruned_without_exact(self) -> None:
        belief = belief_from_ascii(
            (
                ".......",
                ".....?.",
                ".......",
            )
        )
        planner = ChangeAwareStarNBV(sensor_range=1)
        result = planner.plan(belief, (1, 0))

        self.assertIs(result.status, PlanStatus.SELECTED)
        self.assertGreater(
            result.counters.first_seen_pruned_without_exact_count,
            0,
        )
        pruned = [
            record
            for record in result.candidate_records
            if not record.was_cached_at_entry
            and not record.exact_evaluated_this_cycle
        ]
        self.assertTrue(pruned)
        self.assertTrue(
            any(record.range_upper_gain == 0 for record in pruned),
            msg="at least one first-seen zero-range-bound candidate must be pruned",
        )

    def test_stale_cached_bound_is_refreshed_and_reinserted_on_demand(self) -> None:
        belief = belief_from_ascii(
            (
                ".......",
                "..??...",
                ".......",
            )
        )
        planner = ChangeAwareStarNBV(sensor_range=2)
        first = planner.plan(belief, (1, 0))
        self.assertIs(first.status, PlanStatus.SELECTED)
        self.assertIsNotNone(first.selected_candidate)

        changed = belief.apply_observations({(1, 2): TruthState.OCCUPIED})
        second = planner.plan(
            belief,
            (1, 0),
            newly_known=changed,
        )

        self.assertGreater(second.counters.stale_bound_pop_count, 0)
        self.assertGreater(second.counters.lazy_bound_refresh_count, 0)
        self.assertGreater(
            second.counters.stale_bound_refresh_reinsert_count,
            0,
        )
        refreshed = [
            record
            for record in second.candidate_records
            if record.lazy_bound_refreshed
        ]
        self.assertTrue(refreshed)
        self.assertTrue(
            any(
                record.stale_upper_gain_at_entry is not None
                and record.change_upper_gain_after_refresh is not None
                and record.change_upper_gain_after_refresh
                <= record.stale_upper_gain_at_entry
                for record in refreshed
            )
        )
        planner.audit(belief)

    def test_reset_clears_episode_state(self) -> None:
        belief = belief_from_ascii(("...", ".?.", "..."))
        planner = ChangeAwareStarNBV(sensor_range=2)
        planner.plan(belief, (0, 0))
        self.assertIsNotNone(planner.shape)
        planner.reset()
        self.assertIsNone(planner.shape)
        self.assertEqual(planner.cached_candidate_count, 0)
        self.assertEqual(planner.range_mask_cache_count, 0)


class CStarTimingTests(unittest.TestCase):
    def test_core_and_audit_are_separate_measurements(self) -> None:
        ticks = iter((10, 25, 100, 145))

        core = measure_c_star_core(lambda: "core", clock_ns=lambda: next(ticks))
        audit = measure_c_star_audit(lambda: "audit", clock_ns=lambda: next(ticks))

        self.assertEqual(core.result, "core")
        self.assertEqual(core.core_time_ns, 15)
        self.assertEqual(audit.result, "audit")
        self.assertEqual(audit.audit_time_ns, 45)


if __name__ == "__main__":
    unittest.main()
