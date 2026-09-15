import ast
from collections import Counter
import inspect
import json
from pathlib import Path
import random
import unittest

from src.environment import GroundTruthGrid
from src.evaluation import random_dataset
from src.evaluation.random_dataset import (
    DENSITY_TARGETS,
    MASTER_SEED,
    RejectedMap,
    dataset_config,
    evaluate_candidate,
    free_components,
    generate_ground_truth,
    materialize_dataset,
    random_cycle_limit,
    regenerate_record,
    select_largest_component,
    select_start,
    validate_config_schema,
)
from src.mapping import BeliefGrid
from src.utils import (
    BeliefState,
    TruthState,
    belief_hash,
    canonical_belief_text,
    canonical_ground_truth_text,
    ground_truth_hash,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "experiment_0_random_maps.json"


class Experiment0DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dataset = materialize_dataset()
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            cls.config = json.load(handle)

    def test_same_seed_produces_same_map(self) -> None:
        first = generate_ground_truth(16, 0.2, 123456)
        second = generate_ground_truth(16, 0.2, 123456)
        self.assertEqual(first, second)
        self.assertEqual(ground_truth_hash(first), ground_truth_hash(second))

    def test_different_candidate_seeds_can_produce_different_maps(self) -> None:
        first = generate_ground_truth(16, 0.2, 1)
        second = generate_ground_truth(16, 0.2, 2)
        self.assertNotEqual(first, second)

    def test_generation_does_not_change_global_random_state(self) -> None:
        random.seed(991)
        state = random.getstate()
        generate_ground_truth(12, 0.1, 44)
        self.assertEqual(random.getstate(), state)

    def test_repeated_dataset_generation_has_identical_ids_seeds_and_hashes(self) -> None:
        first = materialize_dataset(MASTER_SEED)
        second = materialize_dataset(MASTER_SEED)
        identify = lambda dataset: tuple(
            (item.dataset_id, item.seed, item.map_hash) for item in dataset.accepted
        )
        self.assertEqual(identify(first), identify(second))

    def test_exactly_sixty_maps_are_accepted(self) -> None:
        self.assertEqual(len(self.dataset.accepted), 60)

    def test_exactly_twenty_maps_are_accepted_per_size(self) -> None:
        counts = Counter(item.size for item in self.dataset.accepted)
        self.assertEqual(counts, Counter({12: 20, 16: 20, 20: 20}))

    def test_density_counts_are_as_even_as_possible_per_size(self) -> None:
        for size in (12, 16, 20):
            counts = Counter(
                item.density_label
                for item in self.dataset.accepted
                if item.size == size
            )
            self.assertEqual(counts, Counter(DENSITY_TARGETS))
            self.assertLessEqual(max(counts.values()) - min(counts.values()), 1)

    def test_start_selection_is_deterministic(self) -> None:
        grid = generate_ground_truth(20, 0.3, 8989)
        self.assertEqual(select_start(grid), select_start(grid))

    def test_every_accepted_start_is_free(self) -> None:
        for item in self.dataset.accepted:
            self.assertIs(item.ground_truth.state(item.start), TruthState.FREE)

    def test_every_start_is_in_selected_largest_component(self) -> None:
        for item in self.dataset.accepted:
            selected = select_largest_component(free_components(item.ground_truth))
            assert selected is not None
            self.assertIn(item.start, selected)
            self.assertEqual(len(selected), item.free_component_size)

    def test_accepted_largest_component_fraction_is_at_least_threshold(self) -> None:
        for item in self.dataset.accepted:
            total_free = sum(
                item.ground_truth.state(coord) is TruthState.FREE
                for coord in item.ground_truth.iter_coords()
            )
            self.assertGreaterEqual(item.free_component_size / total_free, 0.35)

    def test_initial_exhaustive_stop_is_rejected(self) -> None:
        result = evaluate_candidate(
            candidate_index=0,
            size=3,
            density_label="test",
            p=0.1,
            seed=1,
        )
        self.assertIsInstance(result, RejectedMap)
        assert isinstance(result, RejectedMap)
        self.assertEqual(result.reason, "initial_scan_exploration_complete")

    def test_rejection_reasons_are_specific_and_deterministic(self) -> None:
        cases = (
            (3, 0.1, 0, "no_occupied_cell"),
            (3, 0.2, 399, "largest_component_fraction_below_0.35"),
            (3, 0.5, 45, "no_free_cell"),
        )
        for size, p, seed, expected in cases:
            with self.subTest(expected=expected):
                result = evaluate_candidate(
                    candidate_index=0,
                    size=size,
                    density_label="test",
                    p=p,
                    seed=seed,
                )
                self.assertIsInstance(result, RejectedMap)
                assert isinstance(result, RejectedMap)
                self.assertEqual(result.reason, expected)

    def test_random_cycle_limit_formula(self) -> None:
        self.assertEqual(random_cycle_limit(0), 64)
        self.assertEqual(random_cycle_limit(31), 64)
        self.assertEqual(random_cycle_limit(32), 64)
        self.assertEqual(random_cycle_limit(33), 66)
        for item in self.dataset.accepted:
            self.assertEqual(
                item.cycle_limit, max(64, 2 * item.free_component_size)
            )

    def test_regenerated_hashes_match_frozen_config(self) -> None:
        for record in self.config["accepted_maps"]:
            regenerated = regenerate_record(record)
            self.assertEqual(regenerated.map_hash, record["map_hash"])
            self.assertEqual(list(regenerated.start), record["start"])

    def test_changed_ground_truth_content_changes_hash(self) -> None:
        first = GroundTruthGrid.from_ascii(("..", ".."))
        second = GroundTruthGrid.from_ascii(("#.", ".."))
        self.assertEqual(canonical_ground_truth_text(first), "..\n..\n")
        self.assertNotEqual(ground_truth_hash(first), ground_truth_hash(second))

    def test_belief_hash_is_deterministic_and_content_sensitive(self) -> None:
        first = BeliefGrid.unknown(2, 2)
        second = BeliefGrid.unknown(2, 2)
        self.assertEqual(canonical_belief_text(first), "??\n??\n")
        self.assertEqual(belief_hash(first), belief_hash(second))
        second.apply_observations({(0, 0): TruthState.FREE})
        self.assertNotEqual(belief_hash(first), belief_hash(second))
        self.assertIs(first.state((0, 0)), BeliefState.UNKNOWN)

    def test_frozen_config_schema_validates(self) -> None:
        validate_config_schema(self.config)

    def test_frozen_artifact_exactly_matches_materialized_dataset(self) -> None:
        self.assertEqual(dataset_config(self.dataset), self.config)

    def test_dataset_module_has_no_candidate_1_lazy_dependency(self) -> None:
        tree = ast.parse(inspect.getsource(random_dataset))
        imported_modules: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported_modules.append(node.module)
        forbidden = ("lazy", "candidate_1", "inverse_index", "certificate")
        for module_name in imported_modules:
            self.assertFalse(
                any(token in module_name.lower() for token in forbidden),
                module_name,
            )


if __name__ == "__main__":
    unittest.main()
