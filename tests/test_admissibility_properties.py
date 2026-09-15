import itertools
import random
import unittest

from src.environment import GroundTruthGrid
from src.mapping import BeliefGrid
from src.sensing import optimistic_visible_unknown_cells
from src.utils import BeliefState, TruthState

from tests.helpers import belief_from_ascii

PROPERTY_RANDOM_SEED = 20260915
RANDOM_CASE_COUNT = 128
RANDOM_TRANSITIONS_PER_CASE = 4
RANDOM_TRANSITION_COUNT = RANDOM_CASE_COUNT * RANDOM_TRANSITIONS_PER_CASE
ONE_DIMENSIONAL_TRANSITION_COUNT = sum(
    length * (5 ** (length - 1) - 3 ** (length - 1)) for length in range(2, 6)
)
THREE_BY_THREE_TRANSITION_COUNT = 2 * 8 * 3**7
FOUR_BY_FOUR_TRANSITION_COUNT = 5
PROPERTY_TRANSITION_COUNT = (
    ONE_DIMENSIONAL_TRANSITION_COUNT
    + THREE_BY_THREE_TRANSITION_COUNT
    + FOUR_BY_FOUR_TRANSITION_COUNT
    + RANDOM_TRANSITION_COUNT
)


def _assert_admissible(
    test: unittest.TestCase,
    cached: frozenset[tuple[int, int]],
    belief: BeliefGrid,
    viewpoint: tuple[int, int],
    sensor_range: float,
    context: str,
) -> None:
    current_exact = optimistic_visible_unknown_cells(
        belief, viewpoint, sensor_range
    )
    cached_bound = cached & belief.unknown_cells()
    test.assertTrue(
        current_exact <= cached_bound,
        msg=(
            f"admissibility violation ({context})\n"
            f"viewpoint={viewpoint}, range={sensor_range}\n"
            f"belief={belief.snapshot()}\n"
            f"current_exact={sorted(current_exact)}\n"
            f"cached_bound={sorted(cached_bound)}"
        ),
    )


class DeterministicAdmissibilityEnumerationTests(unittest.TestCase):
    def test_all_monotone_state_pairs_on_short_one_dimensional_rays(self) -> None:
        pair_options = (
            (BeliefState.UNKNOWN, BeliefState.UNKNOWN, None),
            (BeliefState.UNKNOWN, BeliefState.FREE, TruthState.FREE),
            (BeliefState.UNKNOWN, BeliefState.OCCUPIED, TruthState.OCCUPIED),
            (BeliefState.FREE, BeliefState.FREE, TruthState.FREE),
            (BeliefState.OCCUPIED, BeliefState.OCCUPIED, TruthState.OCCUPIED),
        )
        transitions = 0
        for length in range(2, 6):
            for viewpoint_col in range(length):
                other_cols = tuple(col for col in range(length) if col != viewpoint_col)
                for options in itertools.product(pair_options, repeat=len(other_cols)):
                    initial = {(0, viewpoint_col): TruthState.FREE}
                    updates = {}
                    for col, (before, after, truth) in zip(other_cols, options):
                        coord = (0, col)
                        if before is BeliefState.FREE:
                            initial[coord] = TruthState.FREE
                        elif before is BeliefState.OCCUPIED:
                            initial[coord] = TruthState.OCCUPIED
                        elif after is not BeliefState.UNKNOWN:
                            assert truth is not None
                            updates[coord] = truth
                    if not updates:
                        continue

                    belief = BeliefGrid.unknown(1, length)
                    belief.apply_observations(initial)
                    cached = optimistic_visible_unknown_cells(
                        belief, (0, viewpoint_col), sensor_range=8
                    )
                    belief.apply_observations(updates)
                    transitions += 1
                    _assert_admissible(
                        self,
                        cached,
                        belief,
                        (0, viewpoint_col),
                        8,
                        f"1x{length}, options={options}",
                    )

        self.assertEqual(transitions, ONE_DIMENSIONAL_TRANSITION_COUNT)

    def test_every_single_cell_monotone_update_from_three_by_three_states(
        self,
    ) -> None:
        viewpoint = (1, 1)
        other_cells = tuple(
            (row, col)
            for row in range(3)
            for col in range(3)
            if (row, col) != viewpoint
        )
        tau_options = (
            BeliefState.UNKNOWN,
            BeliefState.FREE,
            BeliefState.OCCUPIED,
        )
        transitions = 0
        for states in itertools.product(tau_options, repeat=len(other_cells)):
            belief_tau = BeliefGrid.unknown(3, 3)
            initial = {viewpoint: TruthState.FREE}
            for coord, state in zip(other_cells, states):
                if state is BeliefState.FREE:
                    initial[coord] = TruthState.FREE
                elif state is BeliefState.OCCUPIED:
                    initial[coord] = TruthState.OCCUPIED
            belief_tau.apply_observations(initial)
            cached = optimistic_visible_unknown_cells(
                belief_tau, viewpoint, sensor_range=8
            )
            tau_snapshot = belief_tau.snapshot()

            for coord, state in zip(other_cells, states):
                if state is not BeliefState.UNKNOWN:
                    continue
                for revealed_truth in (TruthState.FREE, TruthState.OCCUPIED):
                    belief_t = BeliefGrid([list(row) for row in tau_snapshot])
                    belief_t.apply_observations({coord: revealed_truth})
                    transitions += 1
                    _assert_admissible(
                        self,
                        cached,
                        belief_t,
                        viewpoint,
                        8,
                        f"3x3, tau={states}, update={coord}:{revealed_truth.value}",
                    )

        self.assertEqual(transitions, THREE_BY_THREE_TRANSITION_COUNT)

    def test_four_by_four_multiple_updates_and_corner_occluders(self) -> None:
        ground_truth = GroundTruthGrid.from_ascii(
            ("....", ".#..", "..#.", "...#")
        )
        viewpoint = (0, 0)
        belief = BeliefGrid.unknown(4, 4)
        belief.apply_observations({viewpoint: TruthState.FREE})
        cached = optimistic_visible_unknown_cells(belief, viewpoint, sensor_range=8)
        batches = (
            ((0, 1), (1, 0)),
            ((1, 1),),
            ((0, 2), (1, 2), (2, 0)),
            ((2, 1), (2, 2)),
            ((0, 3), (1, 3), (2, 3), (3, 3)),
        )
        for transition, batch in enumerate(batches, start=1):
            belief.apply_observations(
                {coord: ground_truth.state(coord) for coord in batch}
            )
            _assert_admissible(
                self,
                cached,
                belief,
                viewpoint,
                8,
                f"4x4 batch transition={transition}, batch={batch}",
            )

        self.assertEqual(len(batches), FOUR_BY_FOUR_TRANSITION_COUNT)


class RandomizedAdmissibilityPropertyTests(unittest.TestCase):
    def test_fixed_seed_static_truth_monotone_updates(self) -> None:
        rng = random.Random(PROPERTY_RANDOM_SEED)
        transitions = 0
        for case_index in range(RANDOM_CASE_COUNT):
            height = rng.randint(3, 5)
            width = rng.randint(3, 5)
            viewpoint = (rng.randrange(height), rng.randrange(width))
            truth_cells = []
            for row in range(height):
                truth_row = []
                for col in range(width):
                    state = (
                        TruthState.FREE
                        if rng.random() < 0.65
                        else TruthState.OCCUPIED
                    )
                    truth_row.append(state)
                truth_cells.append(tuple(truth_row))
            truth_cells[viewpoint[0]] = tuple(
                TruthState.FREE if col == viewpoint[1] else state
                for col, state in enumerate(truth_cells[viewpoint[0]])
            )
            ground_truth = GroundTruthGrid(tuple(truth_cells))

            belief = BeliefGrid.unknown(height, width)
            all_other_cells = [
                coord for coord in ground_truth.iter_coords() if coord != viewpoint
            ]
            rng.shuffle(all_other_cells)
            initially_known_count = rng.randint(0, min(2, len(all_other_cells) - 4))
            initially_known = all_other_cells[:initially_known_count]
            belief.apply_observations(
                {
                    viewpoint: TruthState.FREE,
                    **{coord: ground_truth.state(coord) for coord in initially_known},
                }
            )
            cached = optimistic_visible_unknown_cells(
                belief, viewpoint, sensor_range=8
            )

            for step in range(RANDOM_TRANSITIONS_PER_CASE):
                unknown = sorted(belief.unknown_cells())
                remaining_steps = RANDOM_TRANSITIONS_PER_CASE - step - 1
                max_batch = min(2, len(unknown) - remaining_steps)
                batch_size = rng.randint(1, max_batch)
                batch = rng.sample(unknown, batch_size)
                before = belief.snapshot()
                belief.apply_observations(
                    {coord: ground_truth.state(coord) for coord in batch}
                )
                transitions += 1
                _assert_admissible(
                    self,
                    cached,
                    belief,
                    viewpoint,
                    8,
                    (
                        f"random seed={PROPERTY_RANDOM_SEED}, case={case_index}, "
                        f"step={step}, truth={ground_truth.cells}, before={before}, "
                        f"batch={batch}"
                    ),
                )

        self.assertEqual(transitions, RANDOM_TRANSITION_COUNT)


class NegativeAssumptionRegressionTests(unittest.TestCase):
    def test_increasing_range_can_invalidate_old_cache(self) -> None:
        belief = belief_from_ascii((".??",))
        old_cache = optimistic_visible_unknown_cells(
            belief, (0, 0), sensor_range=1
        )
        belief.apply_observations({(0, 1): TruthState.FREE})
        current = optimistic_visible_unknown_cells(
            belief, (0, 0), sensor_range=2
        )
        old_bound = old_cache & belief.unknown_cells()
        self.assertEqual(old_bound, frozenset())
        self.assertEqual(current, frozenset({(0, 2)}))
        self.assertFalse(current <= old_bound)

    def test_changing_viewpoint_can_invalidate_old_cache(self) -> None:
        belief = belief_from_ascii((".?.?",))
        old_cache = optimistic_visible_unknown_cells(
            belief, (0, 0), sensor_range=1
        )
        belief.apply_observations({(0, 1): TruthState.FREE})
        current = optimistic_visible_unknown_cells(
            belief, (0, 2), sensor_range=1
        )
        old_bound = old_cache & belief.unknown_cells()
        self.assertEqual(old_bound, frozenset())
        self.assertEqual(current, frozenset({(0, 3)}))
        self.assertFalse(current <= old_bound)


if __name__ == "__main__":
    unittest.main()
