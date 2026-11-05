"""Small deterministic regressions; no default 20x20 performance experiment."""
from contextlib import ExitStack, contextmanager
import importlib.util
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / "basiccode"


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, SOURCE / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


common = load_module("_basiccode_mask_common", "nbv_common.py")
with patch.dict(sys.modules, {"nbv_common": common}):
    A = load_module("_basiccode_mask_a", "A_wjstnNBV.py")
    B = load_module("_basiccode_mask_b", "B_stalelazygain.py")
    C = load_module("_basiccode_mask_c", "C_cstarNBV.py")


def unknown_grid(height, width):
    return [[common.UNKNOWN] * width for _ in range(height)]


def assert_mask(test, mask, known):
    height, width = len(known), len(known[0])
    actual = {(i // width, i % width) for i in range(height * width) if (mask >> i) & 1}
    expected = {(r, c) for r in range(height) for c in range(width) if known[r][c] == common.UNKNOWN}
    test.assertEqual(actual, expected)
    test.assertEqual(mask >> (height * width), 0)


@contextmanager
def radius(value):
    with ExitStack() as stack:
        for module in (A, B, C):
            stack.enter_context(patch.object(module, "SENSOR_RANGE", value))
        yield


class MaskStateTests(unittest.TestCase):
    def test_initialization_reads_current_partially_known_grid(self):
        known = [[common.FREE, common.UNKNOWN, common.WALL],
                 [common.UNKNOWN, common.FREE, common.UNKNOWN]]
        state = C.UnknownMaskState()
        state.report_newly_known((0, 0))
        assert_mask(self, state.synchronize(known), known)
        self.assertEqual(state.pending, set())
        self.assertEqual(state.shape, (2, 3))

    def test_initial_scan_is_reflected_before_first_planning_snapshot(self):
        known = unknown_grid(1, 12)
        state = C.UnknownMaskState()
        common.observe([[common.FREE] * 12], known, (0, 0), 2,
                       on_newly_known=state.report_newly_known)
        self.assertEqual(state.pending, {(0, 0), (0, 1), (0, 2)})
        assert_mask(self, state.synchronize(known), known)

    def test_later_updates_do_not_rebuild(self):
        known = unknown_grid(2, 3)
        state = C.UnknownMaskState()
        state.synchronize(known)
        known[0][1] = common.FREE
        known[1][2] = common.WALL
        state.report_newly_known((0, 1))
        state.report_newly_known((1, 2))
        with patch.object(C, "build_unknown_mask", side_effect=AssertionError("must not rescan")):
            assert_mask(self, state.synchronize(known), known)

    def test_empty_delta_preserves_mask_without_rebuild(self):
        known = unknown_grid(2, 3)
        state = C.UnknownMaskState()
        before = state.synchronize(known)
        with patch.object(C, "build_unknown_mask", side_effect=AssertionError("must not rescan")):
            self.assertEqual(state.synchronize(known), before)

    def test_duplicate_reports_are_idempotent_across_snapshots(self):
        known = unknown_grid(1, 3)
        state = C.UnknownMaskState()
        state.synchronize(known)
        known[0][1] = common.WALL
        state.report_newly_known((0, 1))
        state.report_newly_known((0, 1))
        first = state.synchronize(known)
        state.report_newly_known((0, 1))
        self.assertEqual(state.synchronize(known), first)
        assert_mask(self, state.mask, known)

    def test_still_unknown_report_is_rejected_without_partial_mutation(self):
        known = unknown_grid(1, 3)
        state = C.UnknownMaskState()
        before = state.synchronize(known)
        known[0][0] = common.FREE
        state.report_newly_known((0, 0))
        state.report_newly_known((0, 2))
        pending = set(state.pending)
        with self.assertRaisesRegex(ValueError, "UNKNOWN"):
            state.synchronize(known)
        self.assertEqual(state.mask, before)
        self.assertEqual(state.pending, pending)

    def test_invalid_initial_report_does_not_initialize_state(self):
        known = unknown_grid(1, 3)
        state = C.UnknownMaskState()
        state.report_newly_known((0, 2))
        with self.assertRaises(ValueError):
            state.synchronize(known)
        self.assertIsNone(state.mask)
        self.assertIsNone(state.shape)

    def test_out_of_bounds_report_is_rejected(self):
        for cell in ((-1, 0), (0, 3), (1, 0)):
            with self.subTest(cell=cell):
                known = unknown_grid(1, 3)
                state = C.UnknownMaskState()
                before = state.synchronize(known)
                state.report_newly_known(cell)
                with self.assertRaises(ValueError):
                    state.synchronize(known)
                self.assertEqual(state.mask, before)

    def test_shape_change_is_rejected_before_mutation(self):
        state = C.UnknownMaskState()
        before = state.synchronize(unknown_grid(1, 3))
        with self.assertRaises(ValueError):
            state.synchronize(unknown_grid(3, 1))
        self.assertEqual(state.mask, before)
        self.assertEqual(state.shape, (1, 3))


class ObservationHookTests(unittest.TestCase):
    def test_each_initially_unknown_cell_is_reported_once_despite_many_rays(self):
        truth = [[common.FREE] * 3 for _ in range(3)]
        known = unknown_grid(3, 3)
        events = []
        returned = common.observe(truth, known, (1, 1), 4, on_newly_known=events.append)
        self.assertIsNone(returned)
        self.assertEqual(len(events), 9)
        self.assertEqual(len(set(events)), 9)
        common.observe(truth, known, (1, 1), 4, on_newly_known=events.append)
        self.assertEqual(len(events), 9)

    def test_hook_does_not_change_visibility_or_existing_return_value(self):
        truth = [[common.FREE, common.WALL, common.FREE],
                 [common.FREE, common.FREE, common.FREE]]
        plain, hooked = unknown_grid(2, 3), unknown_grid(2, 3)
        events = []
        self.assertIsNone(common.observe(truth, plain, (0, 0), 2))
        self.assertIsNone(common.observe(truth, hooked, (0, 0), 2, on_newly_known=events.append))
        self.assertEqual(plain, hooked)
        self.assertIn((0, 1), events)  # The first wall itself is observed.
        self.assertNotIn((0, 2), events)  # It blocks its straight ray.
        self.assertTrue(all(hooked[r][c] != common.UNKNOWN for r, c in events))

    def test_already_known_cells_are_not_reported(self):
        truth = [[common.FREE] * 5]
        known = [[common.FREE, common.FREE, common.UNKNOWN, common.UNKNOWN, common.UNKNOWN]]
        events = []
        common.observe(truth, known, (0, 0), 2, on_newly_known=events.append)
        self.assertEqual(events, [(0, 2)])

    def test_all_movement_observations_and_early_completion_are_forwarded(self):
        truth = [[common.FREE] * 7]
        plain = unknown_grid(1, 7)
        hooked = unknown_grid(1, 7)
        common.observe(truth, plain, (0, 0), 4)
        common.observe(truth, hooked, (0, 0), 4)
        state = C.UnknownMaskState()
        state.synchronize(hooked)
        _, parents = common.shortest_paths(hooked, (0, 0))
        expected = common.move_to_nbv(truth, plain, (0, 0), (0, 4), parents, 0, 4)
        actual = common.move_to_nbv(truth, hooked, (0, 0), (0, 4), parents, 0, 4,
                                    on_newly_known=state.report_newly_known)
        self.assertEqual(actual, expected)
        self.assertEqual(actual[0], (0, 2))
        self.assertEqual(actual[1], 2)
        self.assertEqual(state.pending, {(0, 5), (0, 6)})
        self.assertEqual(state.synchronize(hooked), 0)
        self.assertEqual(plain, hooked)


class ExplorationRegressionTests(unittest.TestCase):
    CASES = (
        ("open", ("......",) * 4, (0, 0)),
        ("single_room", ("#######", "#.....#", "#.....#", "#.....#", "#######"), (1, 1)),
        ("corridor", ("............",), (0, 0)),
        ("dead_end", ("####.###", "####.###", "........", "####.###", "####.###"), (2, 0)),
        ("separated_rooms", (".........", "....#....", ".........", "....#....", "........."), (0, 0)),
        ("clutter", (".......", ".#.#.#.", ".......", "..#.#..", "......."), (0, 0)),
        ("maze", (".........", "####.###.", ".........", ".###.####", "........."), (0, 0)),
    )

    def test_complete_A_B_rebuild_C_incremental_C_results_match_on_seven_small_cases(self):
        with radius(2):
            for name, rows, start in self.CASES:
                with self.subTest(name=name):
                    truth = [[common.WALL if cell == "#" else common.FREE for cell in row] for row in rows]
                    results, final_grids = [], []
                    for method in ("A", "B", "rebuild", "incremental"):
                        known = unknown_grid(len(rows), len(rows[0]))
                        if method == "A":
                            result = A.explore(truth, known, start)
                        elif method == "B":
                            result = B.explore(truth, known, start)
                        elif method == "incremental":
                            result = C.explore(truth, known, start)
                            self.assertEqual(C.NBVpath, list(result.targets))
                        else:
                            cache, ranges = {}, {}

                            def select(grid, position):
                                return C.evaluate_candidates(grid, position, cache, ranges)

                            result = common.run_exploration(truth, known, start, 2, select)
                        results.append(result)
                        final_grids.append(known)
                    self.assertTrue(all(value == results[0] for value in results))
                    self.assertTrue(all(value == final_grids[0] for value in final_grids))

    def test_multi_plan_exploration_builds_mask_only_once(self):
        truth = [[common.FREE] * 12]
        known = unknown_grid(1, 12)
        with radius(2), patch.object(C, "build_unknown_mask", wraps=C.build_unknown_mask) as build:
            result = C.explore(truth, known, (0, 0))
        self.assertGreater(result.rounds, 1)
        self.assertEqual(build.call_count, 1)
        self.assertEqual(result.status, common.COMPLETE)

    def test_mask_matches_actual_unknown_cells_at_every_planning_snapshot(self):
        synchronize = C.UnknownMaskState.synchronize
        snapshots = []

        def audited(state, known):
            mask = synchronize(state, known)
            assert_mask(self, mask, known)
            snapshots.append(mask)
            return mask

        truth = [[common.FREE] * 12]
        with radius(2), patch.object(C.UnknownMaskState, "synchronize", audited):
            result = C.explore(truth, unknown_grid(1, 12), (0, 0))
        self.assertEqual(len(snapshots), result.rounds)
        self.assertGreater(len(snapshots), 1)

    def test_new_exploration_uses_fresh_episode_state(self):
        instances = []
        state_type = C.UnknownMaskState

        def make_state():
            state = state_type()
            instances.append(state)
            return state

        with radius(2), patch.object(C, "UnknownMaskState", side_effect=make_state), \
             patch.object(C, "build_unknown_mask", wraps=C.build_unknown_mask) as build:
            for width in (12, 14):
                result = C.explore([[common.FREE] * width], unknown_grid(1, width), (0, 0))
                self.assertEqual(result.status, common.COMPLETE)
        self.assertEqual(build.call_count, 2)
        self.assertEqual(len(instances), 2)
        self.assertIsNot(instances[0], instances[1])
        self.assertEqual([state.shape for state in instances], [(1, 12), (1, 14)])

    def test_initial_completion_needs_no_planner_or_mask_build(self):
        with patch.object(C, "build_unknown_mask", side_effect=AssertionError("no planning needed")):
            result = C.explore([[common.FREE] * 2], unknown_grid(1, 2), (0, 0))
        self.assertEqual(result.rounds, 0)
        self.assertEqual(result.status, common.COMPLETE)
        self.assertEqual(result.total_cost, 0)

    def test_legacy_four_argument_selector_still_rebuilds(self):
        known = [[common.FREE, common.FREE, common.UNKNOWN, common.UNKNOWN]]
        with patch.object(C, "build_unknown_mask", wraps=C.build_unknown_mask) as build:
            result = C.evaluate_candidates(known, (0, 0), {}, {})
        self.assertEqual(build.call_count, 1)
        self.assertEqual(result[0], (0, 1))

    def test_stateful_monotone_updates_preserve_targets_and_selected_values(self):
        rng = random.Random(20261027)
        with radius(2):
            for _ in range(8):
                known = unknown_grid(3, 4)
                known[0][0] = common.FREE
                order = [(r, c) for r in range(3) for c in range(4) if (r, c) != (0, 0)]
                rng.shuffle(order)
                b_cache, c_cache, ranges = {}, {}, {}
                state = C.UnknownMaskState()
                robot = (0, 0)
                for cell in [None] + order:
                    if cell is not None:
                        r, c = cell
                        known[r][c] = rng.randrange(2)
                        state.report_newly_known(cell)
                    reachable, _ = common.shortest_paths(known, robot)
                    robot = rng.choice(sorted(reachable))
                    expected = A.evaluate_candidates(known, robot)
                    scalar = B.evaluate_candidates(known, robot, b_cache)
                    actual = C.evaluate_candidates(known, robot, c_cache, ranges, unknown_state=state)
                    self.assertEqual(actual[0], expected[0])
                    self.assertEqual(scalar[0], expected[0])
                    self.assertEqual(actual[2], expected[2])
                    if actual[0] is not None:
                        self.assertEqual(actual[1][actual[0]], expected[1][expected[0]])
                    assert_mask(self, state.mask, known)


if __name__ == "__main__":
    unittest.main()
