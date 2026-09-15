import unittest

from src.environment import GroundTruthGrid
from src.mapping import BeliefGrid
from src.planning import (
    ChangeAwareGainCache,
    exact_refresh_candidate,
    newly_known_cells,
    synchronize_revelations,
)
from src.sensing import optimistic_visible_unknown_cells
from src.utils import BeliefState, TruthState

from tests.helpers import belief_from_ascii


U = BeliefState.UNKNOWN
F = BeliefState.FREE
O = BeliefState.OCCUPIED


def snapshot(*rows: tuple[BeliefState, ...]):
    return tuple(rows)


def cache_snapshot(cache: ChangeAwareGainCache) -> tuple[dict, dict, dict, frozenset]:
    return (
        dict(cache.cached_visible_unknown),
        dict(cache.bound_counts),
        dict(cache.inverse_incidence),
        cache.reported_known_cells,
    )


class BeliefDeltaTests(unittest.TestCase):
    def test_a_unknown_to_free_is_returned(self) -> None:
        self.assertEqual(
            newly_known_cells(snapshot((U,)), snapshot((F,))),
            frozenset({(0, 0)}),
        )

    def test_b_unknown_to_occupied_is_returned(self) -> None:
        self.assertEqual(
            newly_known_cells(snapshot((U,)), snapshot((O,))),
            frozenset({(0, 0)}),
        )

    def test_c_unchanged_unknown_is_not_returned(self) -> None:
        self.assertEqual(
            newly_known_cells(snapshot((U,)), snapshot((U,))),
            frozenset(),
        )

    def test_d_unchanged_known_cells_are_not_returned(self) -> None:
        self.assertEqual(
            newly_known_cells(snapshot((F, O)), snapshot((F, O))),
            frozenset(),
        )

    def test_e_multiple_newly_known_cells_are_returned_once(self) -> None:
        previous = snapshot((U, U), (F, U))
        current = snapshot((F, O), (F, U))
        self.assertEqual(
            newly_known_cells(previous, current),
            frozenset({(0, 0), (0, 1)}),
        )

    def test_f_known_to_unknown_is_rejected(self) -> None:
        for known in (F, O):
            with self.subTest(known=known):
                with self.assertRaisesRegex(ValueError, "non-monotone"):
                    newly_known_cells(snapshot((known,)), snapshot((U,)))

    def test_g_free_to_occupied_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "FREE -> OCCUPIED"):
            newly_known_cells(snapshot((F,)), snapshot((O,)))

    def test_h_occupied_to_free_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "OCCUPIED -> FREE"):
            newly_known_cells(snapshot((O,)), snapshot((F,)))

    def test_i_shape_mismatch_is_rejected(self) -> None:
        mismatch_cases = (
            (snapshot((U,)), snapshot((U, U))),
            (snapshot((U,)), snapshot((U,), (U,))),
        )
        for previous, current in mismatch_cases:
            with self.subTest(current=current):
                with self.assertRaisesRegex(ValueError, "shapes must match"):
                    newly_known_cells(previous, current)

    def test_j_inputs_are_not_mutated_and_mutable_storage_is_rejected(self) -> None:
        previous = snapshot((U, U), (F, O))
        current = snapshot((F, O), (F, O))
        before = (previous, current)

        result = newly_known_cells(previous, current)

        self.assertEqual((previous, current), before)
        self.assertIsInstance(result, frozenset)
        with self.assertRaisesRegex(TypeError, "tuple-of-tuples"):
            newly_known_cells([[U]], snapshot((U,)))


class SynchronizationTests(unittest.TestCase):
    candidate = (0, 0)

    def test_k_extracted_delta_is_applied_to_cache_bounds(self) -> None:
        belief = belief_from_ascii((".??",))
        cache = ChangeAwareGainCache()
        exact_refresh_candidate(cache, belief, self.candidate, 8)
        previous = belief.snapshot()
        belief.apply_observations({(0, 1): TruthState.FREE})

        delta = synchronize_revelations(cache, previous, belief.snapshot())

        self.assertEqual(delta, frozenset({(0, 1)}))
        self.assertEqual(cache.bound_counts[self.candidate], 1)

    def test_l_duplicate_synchronization_is_idempotent(self) -> None:
        belief = belief_from_ascii((".??",))
        cache = ChangeAwareGainCache()
        exact_refresh_candidate(cache, belief, self.candidate, 8)
        previous = belief.snapshot()
        belief.apply_observations({(0, 1): TruthState.FREE})
        current = belief.snapshot()
        synchronize_revelations(cache, previous, current)
        after_first = cache_snapshot(cache)

        duplicate_delta = synchronize_revelations(cache, previous, current)

        self.assertEqual(duplicate_delta, frozenset({(0, 1)}))
        self.assertEqual(cache_snapshot(cache), after_first)

    def test_m_initial_scan_before_candidate_installation_is_supported(self) -> None:
        belief = BeliefGrid.unknown(1, 4)
        before_scan = belief.snapshot()
        cache = ChangeAwareGainCache()
        belief.apply_observations(
            {(0, 0): TruthState.FREE, (0, 1): TruthState.OCCUPIED}
        )

        delta = synchronize_revelations(cache, before_scan, belief.snapshot())
        exact = exact_refresh_candidate(cache, belief, self.candidate, 8)

        self.assertEqual(delta, frozenset({(0, 0), (0, 1)}))
        self.assertEqual(cache.reported_known_cells, delta)
        self.assertEqual(exact, frozenset())
        self.assertTrue(exact.isdisjoint(cache.reported_known_cells))
        cache.validate(require_fresh_bounds=True)

    def test_n_bound_equals_cached_intersection_after_every_update(self) -> None:
        belief = belief_from_ascii((".?.?",))
        cache = ChangeAwareGainCache()
        candidates = ((0, 0), (0, 2))
        for candidate in candidates:
            exact_refresh_candidate(cache, belief, candidate, 8)

        for coord, truth in (
            ((0, 1), TruthState.FREE),
            ((0, 3), TruthState.OCCUPIED),
        ):
            previous = belief.snapshot()
            belief.apply_observations({coord: truth})
            synchronize_revelations(cache, previous, belief.snapshot())
            current_unknown = belief.unknown_cells()
            for candidate in candidates:
                self.assertEqual(
                    cache.bound_counts[candidate],
                    len(cache.cached_visible_unknown[candidate] & current_unknown),
                )
            cache.validate()


class ExactVisibilityIntegrationTests(unittest.TestCase):
    candidate = (0, 0)

    def test_o_helper_exact_set_equals_direct_visibility_call(self) -> None:
        belief = belief_from_ascii((".???",))
        expected = optimistic_visible_unknown_cells(belief, self.candidate, 8)

        actual = exact_refresh_candidate(
            ChangeAwareGainCache(), belief, self.candidate, 8
        )

        self.assertEqual(actual, expected)

    def test_p_exact_refresh_installs_direct_visibility_set(self) -> None:
        belief = belief_from_ascii((".???",))
        cache = ChangeAwareGainCache()
        direct = optimistic_visible_unknown_cells(belief, self.candidate, 8)

        returned = exact_refresh_candidate(cache, belief, self.candidate, 8)

        self.assertEqual(returned, direct)
        self.assertEqual(cache.cached_visible_unknown[self.candidate], direct)
        self.assertEqual(cache.bound_counts[self.candidate], len(direct))
        for cell in direct:
            self.assertEqual(
                cache.inverse_incidence[cell], frozenset({self.candidate})
            )

    def test_q_unknown_to_free_keeps_exact_gain_admissible(self) -> None:
        belief = belief_from_ascii((".??",))
        cache = ChangeAwareGainCache()
        exact_refresh_candidate(cache, belief, self.candidate, 8)
        previous = belief.snapshot()
        belief.apply_observations({(0, 1): TruthState.FREE})
        synchronize_revelations(cache, previous, belief.snapshot())

        current = optimistic_visible_unknown_cells(belief, self.candidate, 8)

        self.assertEqual(current, frozenset({(0, 2)}))
        self.assertLessEqual(len(current), cache.bound_counts[self.candidate])
        self.assertEqual(len(current), cache.bound_counts[self.candidate])

    def test_r_occupied_blocker_produces_a_strict_conservative_bound(self) -> None:
        belief = belief_from_ascii((".???",))
        cache = ChangeAwareGainCache()
        old_exact = exact_refresh_candidate(cache, belief, self.candidate, 8)
        old_inverse = dict(cache.inverse_incidence)
        previous = belief.snapshot()
        belief.apply_observations({(0, 1): TruthState.OCCUPIED})

        delta = synchronize_revelations(cache, previous, belief.snapshot())
        current = optimistic_visible_unknown_cells(belief, self.candidate, 8)

        self.assertEqual(delta, frozenset({(0, 1)}))
        self.assertEqual(old_exact, frozenset({(0, 1), (0, 2), (0, 3)}))
        self.assertEqual(current, frozenset())
        self.assertEqual(cache.bound_counts[self.candidate], 2)
        self.assertLess(len(current), cache.bound_counts[self.candidate])
        self.assertEqual(cache.cached_visible_unknown[self.candidate], old_exact)
        self.assertEqual(dict(cache.inverse_incidence), old_inverse)

    def test_s_exact_refresh_after_loose_bound_restores_equality(self) -> None:
        belief = belief_from_ascii((".???",))
        cache = ChangeAwareGainCache()
        exact_refresh_candidate(cache, belief, self.candidate, 8)
        previous = belief.snapshot()
        belief.apply_observations({(0, 1): TruthState.OCCUPIED})
        synchronize_revelations(cache, previous, belief.snapshot())
        self.assertGreater(cache.bound_counts[self.candidate], 0)

        current = exact_refresh_candidate(cache, belief, self.candidate, 8)

        self.assertEqual(current, frozenset())
        self.assertEqual(cache.cached_visible_unknown[self.candidate], current)
        self.assertEqual(cache.bound_counts[self.candidate], len(current))
        self.assertEqual(cache.inverse_incidence, {})
        cache.validate(require_fresh_bounds=True)

    def test_t_obsolete_post_sync_installation_is_rejected_atomically(self) -> None:
        belief = belief_from_ascii((".??",))
        cache = ChangeAwareGainCache()
        obsolete = exact_refresh_candidate(cache, belief, self.candidate, 8)
        previous = belief.snapshot()
        belief.apply_observations({(0, 1): TruthState.FREE})
        synchronize_revelations(cache, previous, belief.snapshot())
        synchronized = cache_snapshot(cache)

        with self.assertRaisesRegex(ValueError, "already reported known"):
            cache.install_exact(self.candidate, obsolete)

        self.assertEqual(cache_snapshot(cache), synchronized)
        cache.validate()

    def test_deterministic_multiview_admissibility_across_updates(self) -> None:
        truth = GroundTruthGrid.from_ascii(
            (".....", ".#...", "..#..", "...#.", ".....")
        )
        belief = BeliefGrid.unknown(5, 5)
        cache = ChangeAwareGainCache()
        candidates = ((0, 0), (2, 1), (4, 4))

        episode_start = belief.snapshot()
        belief.apply_observations(
            {candidate: TruthState.FREE for candidate in candidates}
        )
        synchronize_revelations(cache, episode_start, belief.snapshot())
        for candidate in candidates:
            exact_refresh_candidate(cache, belief, candidate, sensor_range=4)

        batches = (
            ((0, 1), (1, 0), (1, 1)),
            ((2, 2), (2, 3), (3, 3)),
            ((3, 4), (4, 3), (1, 4)),
        )
        for step, batch in enumerate(batches):
            previous = belief.snapshot()
            belief.apply_observations(
                {coord: truth.state(coord) for coord in batch}
            )
            synchronize_revelations(cache, previous, belief.snapshot())

            for candidate in candidates:
                exact = optimistic_visible_unknown_cells(
                    belief, candidate, sensor_range=4
                )
                self.assertLessEqual(
                    len(exact),
                    cache.bound_counts[candidate],
                    msg=f"step={step}, candidate={candidate}",
                )
                self.assertEqual(
                    cache.bound_counts[candidate],
                    len(
                        cache.cached_visible_unknown[candidate]
                        & belief.unknown_cells()
                    ),
                )

            refreshed = candidates[step % len(candidates)]
            refreshed_exact = exact_refresh_candidate(
                cache, belief, refreshed, sensor_range=4
            )
            self.assertEqual(
                cache.bound_counts[refreshed], len(refreshed_exact)
            )
            cache.validate()


if __name__ == "__main__":
    unittest.main()
