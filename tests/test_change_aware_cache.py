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
        cache.install_exact(
            self.candidate,
            frozenset({self.cell_a, self.cell_b}),
        )
        cache.validate(require_fresh_bounds=True)

    @staticmethod
    def _snapshot(cache: ChangeAwareGainCache) -> tuple[dict, dict, dict]:
        return (
            dict(cache.cached_visible_unknown),
            dict(cache.bound_counts),
            dict(cache.inverse_incidence),
        )

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
        cache.install_exact(
            self.candidate,
            frozenset({self.cell_a, self.cell_b}),
        )
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

    def test_first_exact_installation_populates_all_state_families(self) -> None:
        cache = ChangeAwareGainCache()

        cache.install_exact(
            self.candidate,
            frozenset({self.cell_a, self.cell_b}),
        )

        self.assertEqual(
            cache.cached_visible_unknown[self.candidate],
            frozenset({self.cell_a, self.cell_b}),
        )
        self.assertEqual(cache.bound_counts[self.candidate], 2)
        self.assertEqual(
            cache.inverse_incidence[self.cell_a], frozenset({self.candidate})
        )
        self.assertEqual(
            cache.inverse_incidence[self.cell_b], frozenset({self.candidate})
        )
        cache.validate(require_fresh_bounds=True)

    def test_empty_exact_set_initializes_candidate_without_inverse_keys(self) -> None:
        cache = ChangeAwareGainCache()

        cache.install_exact(self.candidate, frozenset())

        self.assertEqual(cache.cached_visible_unknown[self.candidate], frozenset())
        self.assertEqual(cache.bound_counts[self.candidate], 0)
        self.assertEqual(cache.inverse_incidence, {})
        cache.validate(require_fresh_bounds=True)

    def test_replacement_removes_old_and_installs_new_memberships(self) -> None:
        cache = ChangeAwareGainCache()
        cell_c = (10, 11)
        cell_d = (12, 13)
        cache.install_exact(
            self.candidate,
            frozenset({self.cell_a, self.cell_b, cell_c}),
        )

        cache.install_exact(
            self.candidate,
            frozenset({self.cell_b, cell_d}),
        )

        self.assertEqual(
            cache.cached_visible_unknown[self.candidate],
            frozenset({self.cell_b, cell_d}),
        )
        self.assertEqual(cache.bound_counts[self.candidate], 2)
        self.assertNotIn(self.cell_a, cache.inverse_incidence)
        self.assertNotIn(cell_c, cache.inverse_incidence)
        self.assertEqual(
            cache.inverse_incidence[self.cell_b], frozenset({self.candidate})
        )
        self.assertEqual(
            cache.inverse_incidence[cell_d], frozenset({self.candidate})
        )
        cache.validate(require_fresh_bounds=True)

    def test_refresh_preserves_other_candidate_shared_membership(self) -> None:
        cache = ChangeAwareGainCache()
        cell_c = (10, 11)
        cache.install_exact(
            self.candidate,
            frozenset({self.cell_a, self.cell_b}),
        )
        cache.install_exact(
            self.other_candidate,
            frozenset({self.cell_b, cell_c}),
        )

        cache.install_exact(self.candidate, frozenset({self.cell_a}))

        self.assertEqual(
            cache.inverse_incidence[self.cell_b],
            frozenset({self.other_candidate}),
        )
        self.assertEqual(
            cache.inverse_incidence[cell_c], frozenset({self.other_candidate})
        )
        cache.validate(require_fresh_bounds=True)

    def test_refresh_removes_inverse_key_when_last_membership_leaves(self) -> None:
        cache = ChangeAwareGainCache()
        cache.install_exact(self.candidate, frozenset({self.cell_a}))

        cache.install_exact(self.candidate, frozenset())

        self.assertNotIn(self.cell_a, cache.inverse_incidence)
        self.assertEqual(cache.inverse_incidence, {})
        cache.validate(require_fresh_bounds=True)

    def test_reinstall_same_set_is_deterministic_and_restores_fresh_bound(self) -> None:
        cache = ChangeAwareGainCache()
        exact_set = frozenset({self.cell_a, self.cell_b})
        cache.install_exact(self.candidate, exact_set)
        fresh_snapshot = self._snapshot(cache)
        cache._bound_counts[self.candidate] = 1
        cache.validate()

        cache.install_exact(self.candidate, exact_set)

        self.assertEqual(self._snapshot(cache), fresh_snapshot)
        cache.validate(require_fresh_bounds=True)

    def test_refresh_discards_decremented_bound_and_uses_new_exact_size(self) -> None:
        cache = ChangeAwareGainCache()
        cell_c = (10, 11)
        cell_d = (12, 13)
        cache.install_exact(
            self.candidate,
            frozenset({self.cell_a, self.cell_b, cell_c}),
        )
        cache._bound_counts[self.candidate] = 1
        cache.validate()

        cache.install_exact(
            self.candidate,
            frozenset({self.cell_b, cell_d}),
        )

        self.assertEqual(cache.bound_counts[self.candidate], 2)
        self.assertEqual(
            cache.cached_visible_unknown[self.candidate],
            frozenset({self.cell_b, cell_d}),
        )
        cache.validate(require_fresh_bounds=True)

    def test_known_cell_regression_removes_from_complete_old_cached_set(self) -> None:
        cache = ChangeAwareGainCache()
        cell_c = (10, 11)
        cell_d = (12, 13)
        cache.install_exact(
            self.candidate,
            frozenset({self.cell_a, self.cell_b, cell_c}),
        )
        # Future Stage 3 may decrement the bound while retaining every old
        # cached-set membership, including cells that have become known.
        cache._bound_counts[self.candidate] = 1
        cache.validate()

        cache.install_exact(
            self.candidate,
            frozenset({cell_c, cell_d}),
        )

        self.assertNotIn(self.cell_a, cache.inverse_incidence)
        self.assertNotIn(self.cell_b, cache.inverse_incidence)
        self.assertEqual(
            cache.cached_visible_unknown[self.candidate],
            frozenset({cell_c, cell_d}),
        )
        self.assertEqual(cache.bound_counts[self.candidate], 2)
        self.assertEqual(
            cache.inverse_incidence,
            {
                cell_c: frozenset({self.candidate}),
                cell_d: frozenset({self.candidate}),
            },
        )
        cache.validate(require_fresh_bounds=True)

    def test_invalid_installation_inputs_raise_atomically(self) -> None:
        cache = ChangeAwareGainCache()
        self._populate_valid_state(cache)
        original = self._snapshot(cache)
        invalid_cases = (
            ((-1, 3), frozenset({self.cell_a}), ValueError),
            ((True, 3), frozenset({self.cell_a}), ValueError),
            ((2.0, 3), frozenset({self.cell_a}), ValueError),
            ((2,), frozenset({self.cell_a}), ValueError),
            (self.candidate, {self.cell_a}, TypeError),
            (self.candidate, frozenset({(-1, 7)}), ValueError),
            (self.candidate, frozenset({(True, 7)}), ValueError),
        )

        for candidate, visible_unknown, error_type in invalid_cases:
            with self.subTest(candidate=candidate, visible_unknown=visible_unknown):
                with self.assertRaises(error_type):
                    cache.install_exact(candidate, visible_unknown)
                self.assertEqual(self._snapshot(cache), original)
                cache.validate(require_fresh_bounds=True)

    def test_stage_two_has_only_exact_installation_not_future_operations(self) -> None:
        cache = ChangeAwareGainCache()
        source = inspect.getsource(cache_module)

        self.assertFalse(hasattr(cache, "plan"))
        self.assertFalse(hasattr(cache, "decrement"))
        self.assertFalse(hasattr(cache, "apply_observations"))
        self.assertFalse(hasattr(cache, "apply_known_cells"))
        self.assertFalse(hasattr(cache, "update_from_belief"))
        self.assertFalse(hasattr(cache, "process_delta"))
        self.assertFalse(hasattr(cache_module, "ChangeAwareNBVResult"))
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
                "install_exact",
                "inverse_incidence",
                "reset",
                "validate",
            },
        )


if __name__ == "__main__":
    unittest.main()
