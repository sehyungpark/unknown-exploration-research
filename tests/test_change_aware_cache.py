import inspect
import unittest

from src.planning import ChangeAwareGainCache
import src.planning.change_aware_cache as cache_module


class ChangeAwareGainCacheTests(unittest.TestCase):
    candidate = (2, 3)
    other_candidate = (4, 5)
    cell_a = (6, 7)
    cell_b = (8, 9)

    def _populate_valid_state(self, cache: ChangeAwareGainCache) -> None:
        cache._cached_visible_unknown[self.candidate] = frozenset(
            {self.cell_a, self.cell_b}
        )
        cache._bound_counts[self.candidate] = 2
        cache._inverse_incidence[self.cell_a] = {self.candidate}
        cache._inverse_incidence[self.cell_b] = {self.candidate}
        cache.validate(require_fresh_bounds=True)

    def test_fresh_state_is_empty_and_valid(self) -> None:
        cache = ChangeAwareGainCache()

        self.assertEqual(cache.cached_visible_unknown, {})
        self.assertEqual(cache.bound_counts, {})
        self.assertEqual(cache.inverse_incidence, {})
        cache.validate()

    def test_reset_clears_all_three_state_families(self) -> None:
        cache = ChangeAwareGainCache()
        self._populate_valid_state(cache)

        cache.reset()

        self.assertEqual(cache.cached_visible_unknown, {})
        self.assertEqual(cache.bound_counts, {})
        self.assertEqual(cache.inverse_incidence, {})
        cache.validate()

    def test_reset_is_idempotent_for_empty_and_populated_state(self) -> None:
        cache = ChangeAwareGainCache()
        cache.reset()
        cache.reset()
        self._populate_valid_state(cache)

        cache.reset()
        cache.reset()

        self.assertEqual(cache.cached_visible_unknown, {})
        self.assertEqual(cache.bound_counts, {})
        self.assertEqual(cache.inverse_incidence, {})

    def test_diagnostics_cannot_mutate_internal_state(self) -> None:
        cache = ChangeAwareGainCache()
        self._populate_valid_state(cache)
        cached = cache.cached_visible_unknown
        bounds = cache.bound_counts
        inverse = cache.inverse_incidence

        with self.assertRaises(TypeError):
            cached[self.other_candidate] = frozenset()
        with self.assertRaises(AttributeError):
            cached[self.candidate].add((10, 10))
        with self.assertRaises(TypeError):
            bounds[self.candidate] = 0
        with self.assertRaises(TypeError):
            inverse[self.cell_a] = frozenset()
        with self.assertRaises(AttributeError):
            inverse[self.cell_a].add(self.other_candidate)

        self.assertEqual(
            cache.cached_visible_unknown[self.candidate],
            frozenset({self.cell_a, self.cell_b}),
        )
        self.assertEqual(cache.bound_counts[self.candidate], 2)
        self.assertEqual(
            cache.inverse_incidence[self.cell_a], frozenset({self.candidate})
        )

    def test_negative_float_and_bool_bounds_are_rejected(self) -> None:
        for invalid_bound in (-1, 1.5, True):
            with self.subTest(bound=invalid_bound):
                cache = ChangeAwareGainCache()
                cache._cached_visible_unknown[self.candidate] = frozenset()
                cache._bound_counts[self.candidate] = invalid_bound
                with self.assertRaisesRegex(RuntimeError, "nonnegative int"):
                    cache.validate()

    def test_mismatched_candidate_keys_are_rejected_in_both_directions(self) -> None:
        cached_only = ChangeAwareGainCache()
        cached_only._cached_visible_unknown[self.candidate] = frozenset()
        with self.assertRaisesRegex(RuntimeError, "candidate keys must match"):
            cached_only.validate()

        bound_only = ChangeAwareGainCache()
        bound_only._bound_counts[self.candidate] = 0
        with self.assertRaisesRegex(RuntimeError, "candidate keys must match"):
            bound_only.validate()

    def test_extra_inverse_membership_is_rejected(self) -> None:
        cache = ChangeAwareGainCache()
        self._populate_valid_state(cache)
        cache._inverse_incidence[self.cell_a].add(self.other_candidate)
        cache._cached_visible_unknown[self.other_candidate] = frozenset()
        cache._bound_counts[self.other_candidate] = 0

        with self.assertRaisesRegex(RuntimeError, "exactly match"):
            cache.validate()

    def test_missing_inverse_membership_is_rejected(self) -> None:
        cache = ChangeAwareGainCache()
        self._populate_valid_state(cache)
        cache._inverse_incidence.pop(self.cell_b)

        with self.assertRaisesRegex(RuntimeError, "exactly match"):
            cache.validate()

    def test_uninitialized_candidate_in_inverse_index_is_rejected(self) -> None:
        cache = ChangeAwareGainCache()
        self._populate_valid_state(cache)
        cache._inverse_incidence[self.cell_a].add(self.other_candidate)

        with self.assertRaisesRegex(RuntimeError, "uninitialized candidate"):
            cache.validate()

    def test_duplicate_inverse_membership_is_rejected_if_state_is_corrupted(self) -> None:
        cache = ChangeAwareGainCache()
        cache._cached_visible_unknown[self.candidate] = frozenset({self.cell_a})
        cache._bound_counts[self.candidate] = 1
        cache._inverse_incidence[self.cell_a] = [self.candidate, self.candidate]

        with self.assertRaisesRegex(RuntimeError, "duplicate inverse membership"):
            cache.validate()

    def test_coordinate_shapes_and_cached_set_type_are_validated(self) -> None:
        invalid_candidate = ChangeAwareGainCache()
        invalid_candidate._cached_visible_unknown[(1,)] = frozenset()
        invalid_candidate._bound_counts[(1,)] = 0
        with self.assertRaisesRegex(RuntimeError, "candidate coordinate"):
            invalid_candidate.validate()

        invalid_cell = ChangeAwareGainCache()
        invalid_cell._cached_visible_unknown[self.candidate] = frozenset({(-1, 2)})
        invalid_cell._bound_counts[self.candidate] = 1
        with self.assertRaisesRegex(RuntimeError, "visible-UNKNOWN coordinate"):
            invalid_cell.validate()

        mutable_cache = ChangeAwareGainCache()
        mutable_cache._cached_visible_unknown[self.candidate] = {self.cell_a}
        mutable_cache._bound_counts[self.candidate] = 1
        with self.assertRaisesRegex(RuntimeError, "must be frozenset"):
            mutable_cache.validate()

    def test_bound_must_not_exceed_cache_and_fresh_bound_must_equal_size(self) -> None:
        too_large = ChangeAwareGainCache()
        too_large._cached_visible_unknown[self.candidate] = frozenset({self.cell_a})
        too_large._bound_counts[self.candidate] = 2
        too_large._inverse_incidence[self.cell_a] = {self.candidate}
        with self.assertRaisesRegex(RuntimeError, "exceeds cached-set size"):
            too_large.validate()

        maintained = ChangeAwareGainCache()
        self._populate_valid_state(maintained)
        maintained._bound_counts[self.candidate] = 1
        maintained.validate()
        with self.assertRaisesRegex(RuntimeError, "must equal cached-set size"):
            maintained.validate(require_fresh_bounds=True)

    def test_stage_one_has_no_selector_or_dynamic_update_operations(self) -> None:
        cache = ChangeAwareGainCache()
        source = inspect.getsource(cache_module)

        self.assertFalse(hasattr(cache, "plan"))
        self.assertNotIn("dijkstra", source.lower())
        self.assertNotIn("optimistic_visible_unknown_cells", source)
        self.assertNotIn("candidate_rank_key", source)
        self.assertNotIn("physical_scan", source)
        self.assertEqual(
            {
                name
                for name in dir(ChangeAwareGainCache)
                if not name.startswith("_")
            },
            {
                "bound_counts",
                "cached_visible_unknown",
                "inverse_incidence",
                "reset",
                "validate",
            },
        )


if __name__ == "__main__":
    unittest.main()
