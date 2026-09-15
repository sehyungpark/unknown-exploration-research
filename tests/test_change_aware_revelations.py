import unittest

from src.planning import ChangeAwareGainCache


class ChangeAwareRevelationTests(unittest.TestCase):
    v1 = (1, 1)
    v2 = (2, 2)
    v3 = (3, 3)
    a = (10, 0)
    b = (10, 1)
    c = (10, 2)
    d = (10, 3)
    e = (10, 4)
    unrelated = (99, 99)

    @staticmethod
    def _snapshot(
        cache: ChangeAwareGainCache,
    ) -> tuple[dict, dict, dict, frozenset]:
        return (
            dict(cache.cached_visible_unknown),
            dict(cache.bound_counts),
            dict(cache.inverse_incidence),
            cache.reported_known_cells,
        )

    def test_single_cell_decrements_bound_without_changing_historical_state(self) -> None:
        cache = ChangeAwareGainCache()
        cache.install_exact(self.v1, frozenset({self.a, self.b, self.c}))
        cached_before = dict(cache.cached_visible_unknown)
        inverse_before = dict(cache.inverse_incidence)

        cache.apply_newly_known(frozenset({self.a}))

        self.assertEqual(cache.bound_counts[self.v1], 2)
        self.assertEqual(dict(cache.cached_visible_unknown), cached_before)
        self.assertEqual(dict(cache.inverse_incidence), inverse_before)
        self.assertEqual(cache.reported_known_cells, frozenset({self.a}))
        cache.validate()

    def test_shared_cell_decrements_every_affected_candidate_once(self) -> None:
        cache = ChangeAwareGainCache()
        cache.install_exact(self.v1, frozenset({self.a, self.b}))
        cache.install_exact(self.v2, frozenset({self.b, self.c}))

        cache.apply_newly_known(frozenset({self.b}))

        self.assertEqual(cache.bound_counts, {self.v1: 1, self.v2: 1})
        self.assertEqual(
            cache.inverse_incidence[self.b], frozenset({self.v1, self.v2})
        )
        cache.validate()

    def test_unindexed_revelation_only_updates_episode_accounting(self) -> None:
        cache = ChangeAwareGainCache()
        cache.install_exact(self.v1, frozenset({self.a, self.b}))
        cached_before = dict(cache.cached_visible_unknown)
        bounds_before = dict(cache.bound_counts)
        inverse_before = dict(cache.inverse_incidence)

        cache.apply_newly_known(frozenset({self.unrelated}))

        self.assertEqual(dict(cache.cached_visible_unknown), cached_before)
        self.assertEqual(dict(cache.bound_counts), bounds_before)
        self.assertEqual(dict(cache.inverse_incidence), inverse_before)
        self.assertEqual(
            cache.reported_known_cells, frozenset({self.unrelated})
        )
        cache.validate(require_fresh_bounds=True)

    def test_duplicate_revelation_in_later_call_is_idempotent(self) -> None:
        cache = ChangeAwareGainCache()
        cache.install_exact(self.v1, frozenset({self.a, self.b}))
        cache.apply_newly_known(frozenset({self.a}))
        after_first = self._snapshot(cache)

        cache.apply_newly_known(frozenset({self.a}))

        self.assertEqual(self._snapshot(cache), after_first)
        self.assertEqual(cache.bound_counts[self.v1], 1)

    def test_mixed_batch_counts_already_reported_cell_only_once(self) -> None:
        cache = ChangeAwareGainCache()
        cache.install_exact(self.v1, frozenset({self.a, self.b, self.c}))

        cache.apply_newly_known(frozenset({self.a, self.b}))
        cache.apply_newly_known(frozenset({self.b, self.c}))

        self.assertEqual(cache.bound_counts[self.v1], 0)
        self.assertEqual(
            cache.reported_known_cells,
            frozenset({self.a, self.b, self.c}),
        )
        cache.validate()

    def test_three_candidate_overlap_decrements_each_distinct_incidence(self) -> None:
        cache = ChangeAwareGainCache()
        cache.install_exact(self.v1, frozenset({self.a, self.b, self.d}))
        cache.install_exact(self.v2, frozenset({self.b, self.c, self.d}))
        cache.install_exact(self.v3, frozenset({self.c, self.d, self.e}))
        inverse_before = dict(cache.inverse_incidence)

        cache.apply_newly_known(frozenset({self.b, self.c, self.d}))

        self.assertEqual(
            cache.bound_counts,
            {self.v1: 1, self.v2: 0, self.v3: 1},
        )
        self.assertEqual(dict(cache.inverse_incidence), inverse_before)
        cache.validate()

    def test_bound_reaches_zero_and_duplicates_do_not_underflow(self) -> None:
        cache = ChangeAwareGainCache()
        cache.install_exact(self.v1, frozenset({self.a, self.b}))

        cache.apply_newly_known(frozenset({self.a, self.b}))
        self.assertEqual(cache.bound_counts[self.v1], 0)
        cache.apply_newly_known(frozenset({self.a, self.b}))

        self.assertEqual(cache.bound_counts[self.v1], 0)
        cache.validate()

    def test_corrupted_underflow_state_is_rejected_without_mutation(self) -> None:
        cache = ChangeAwareGainCache()
        cache.install_exact(self.v1, frozenset({self.a}))
        cache.install_exact(self.v2, frozenset({self.b}))
        cache._bound_counts[self.v2] = 0
        corrupted_before = self._snapshot(cache)

        with self.assertRaisesRegex(RuntimeError, "accounting invariant"):
            cache.apply_newly_known(frozenset({self.a, self.b}))

        self.assertEqual(self._snapshot(cache), corrupted_before)

    def test_invalid_batch_is_atomic(self) -> None:
        cache = ChangeAwareGainCache()
        cache.install_exact(self.v1, frozenset({self.a, self.b}))
        original = self._snapshot(cache)
        invalid_cases = (
            ({self.a}, TypeError),
            (frozenset({self.a, (-1, 0)}), ValueError),
            (frozenset({self.a, (True, 0)}), ValueError),
            (frozenset({self.a, (1.5, 0)}), ValueError),
            (frozenset({self.a, (1,)}), ValueError),
        )

        for cells, error_type in invalid_cases:
            with self.subTest(cells=cells):
                with self.assertRaises(error_type):
                    cache.apply_newly_known(cells)
                self.assertEqual(self._snapshot(cache), original)
                cache.validate(require_fresh_bounds=True)

    def test_batch_matches_deterministic_sequential_processing(self) -> None:
        batch = ChangeAwareGainCache()
        sequential = ChangeAwareGainCache()
        for cache in (batch, sequential):
            cache.install_exact(self.v1, frozenset({self.a, self.b, self.c}))
            cache.install_exact(self.v2, frozenset({self.b, self.c, self.d}))

        batch.apply_newly_known(frozenset({self.c, self.a, self.b}))
        for cell in sorted((self.c, self.a, self.b)):
            sequential.apply_newly_known(frozenset({cell}))

        self.assertEqual(self._snapshot(batch), self._snapshot(sequential))

    def test_exact_refresh_after_decrements_restores_fresh_state(self) -> None:
        cache = ChangeAwareGainCache()
        cache.install_exact(self.v1, frozenset({self.a, self.b, self.c}))
        cache.apply_newly_known(frozenset({self.a, self.b}))
        self.assertEqual(cache.bound_counts[self.v1], 1)

        cache.install_exact(self.v1, frozenset({self.c, self.d}))

        self.assertEqual(
            cache.cached_visible_unknown[self.v1], frozenset({self.c, self.d})
        )
        self.assertEqual(cache.bound_counts[self.v1], 2)
        self.assertEqual(
            cache.inverse_incidence,
            {
                self.c: frozenset({self.v1}),
                self.d: frozenset({self.v1}),
            },
        )
        self.assertEqual(
            cache.reported_known_cells, frozenset({self.a, self.b})
        )
        cache.validate(require_fresh_bounds=True)

    def test_refresh_then_later_revelation_decrements_new_cache(self) -> None:
        cache = ChangeAwareGainCache()
        cache.install_exact(self.v1, frozenset({self.a, self.b, self.c}))
        cache.apply_newly_known(frozenset({self.a, self.b}))
        cache.install_exact(self.v1, frozenset({self.c, self.d}))

        cache.apply_newly_known(frozenset({self.d}))

        self.assertEqual(cache.bound_counts[self.v1], 1)
        self.assertEqual(
            cache.cached_visible_unknown[self.v1], frozenset({self.c, self.d})
        )
        self.assertEqual(
            cache.inverse_incidence[self.d], frozenset({self.v1})
        )
        cache.validate()

    def test_install_rejects_already_reported_known_cell_atomically(self) -> None:
        cache = ChangeAwareGainCache()
        cache.install_exact(self.v1, frozenset({self.a, self.b}))
        cache.apply_newly_known(frozenset({self.a}))
        original = self._snapshot(cache)

        with self.assertRaisesRegex(ValueError, "already reported known"):
            cache.install_exact(self.v1, frozenset({self.a, self.c}))

        self.assertEqual(self._snapshot(cache), original)
        cache.validate()

    def test_reset_prevents_reported_cell_history_from_leaking(self) -> None:
        cache = ChangeAwareGainCache()
        cache.install_exact(self.v1, frozenset({self.a}))
        cache.apply_newly_known(frozenset({self.a}))

        cache.reset()
        cache.reset()

        self.assertEqual(cache.cached_visible_unknown, {})
        self.assertEqual(cache.bound_counts, {})
        self.assertEqual(cache.inverse_incidence, {})
        self.assertEqual(cache.reported_known_cells, frozenset())
        cache.install_exact(self.v1, frozenset({self.a}))
        cache.apply_newly_known(frozenset({self.a}))
        self.assertEqual(cache.bound_counts[self.v1], 0)
        cache.validate()

    def test_bounds_equal_explicit_cached_unknown_intersections(self) -> None:
        cache = ChangeAwareGainCache()
        cache.install_exact(
            self.v1, frozenset({self.a, self.b, self.c, self.d})
        )
        cache.install_exact(self.v2, frozenset({self.b, self.c, self.e}))
        unknown = {self.a, self.b, self.c, self.d, self.e, self.unrelated}

        for revelations in (
            frozenset({self.a}),
            frozenset({self.b, self.e}),
            frozenset({self.c}),
        ):
            unknown.difference_update(revelations)
            cache.apply_newly_known(revelations)
            for candidate, cached in cache.cached_visible_unknown.items():
                self.assertEqual(
                    cache.bound_counts[candidate], len(cached & unknown)
                )
            cache.validate()

    def test_validation_covers_revelation_accounting_state(self) -> None:
        wrong_type = ChangeAwareGainCache()
        wrong_type._reported_known_cells = [self.a]
        with self.assertRaisesRegex(RuntimeError, "must be a set"):
            wrong_type.validate()

        invalid_coord = ChangeAwareGainCache()
        invalid_coord._reported_known_cells = {(-1, 0)}
        with self.assertRaisesRegex(RuntimeError, "reported known coordinate"):
            invalid_coord.validate()

        inconsistent = ChangeAwareGainCache()
        inconsistent.install_exact(self.v1, frozenset({self.a}))
        inconsistent._reported_known_cells.add(self.a)
        with self.assertRaisesRegex(RuntimeError, "accounting invariant"):
            inconsistent.validate()


if __name__ == "__main__":
    unittest.main()
