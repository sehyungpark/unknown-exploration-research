"""Small infrastructure checks only; never execute the default benchmark."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from benchmarks import basiccode_runner as runner
from benchmarks.basiccode_analysis import analyze, estimate


class EpisodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.common, cls.modules = runner.load_algorithms()
        cls.case = runner.sanity_cases()[2]  # 1x12 corridor, multiple plans

    def test_actual_explore_outcomes_match_across_passes_and_methods(self):
        reference = None
        for method, module in self.modules.items():
            for phase in ("structural", "timing", "memory"):
                with self.subTest(method=method, phase=phase):
                    metrics, outcome = runner.run_episode(module, self.case, phase)
                    reference = outcome if reference is None else reference
                    self.assertEqual(reference, outcome)
                    if phase == "timing":
                        self.assertGreater(metrics["planner_ns"], 0)
                        self.assertGreaterEqual(metrics["episode_ns"], metrics["planner_ns"])
                        self.assertIsNone(metrics["exact_evaluations"])
                        self.assertIsNone(metrics["python_peak_bytes"])
                    else:
                        self.assertIsNone(metrics["planner_ns"])
                        self.assertIsNone(metrics["episode_ns"])

    def test_incremental_c_is_used_and_builds_mask_once(self):
        module = self.modules["C*"]
        with patch.object(module, "build_unknown_mask", wraps=module.build_unknown_mask) as build:
            metrics, _ = runner.run_episode(module, self.case, "structural")
        self.assertGreater(metrics["planner_calls"], 1)
        self.assertEqual(build.call_count, 1)

    def test_structural_pass_counts_real_exact_evaluations(self):
        for module in self.modules.values():
            with patch.object(module, "exact_evaluate", wraps=module.exact_evaluate) as exact:
                metrics, _ = runner.run_episode(module, self.case, "structural")
            self.assertEqual(metrics["exact_evaluations"], exact.call_count)
            self.assertGreater(exact.call_count, 0)

    def test_input_and_parameters_are_restored_even_after_error(self):
        module = self.modules["C*"]
        original = module.HEIGHT, module.WIDTH, module.SENSOR_RANGE
        truth = deepcopy(self.case["truth"])
        with patch.object(module, "evaluate_candidates", side_effect=RuntimeError("test failure")):
            with self.assertRaisesRegex(RuntimeError, "test failure"):
                runner.run_episode(module, self.case, "memory")
        self.assertEqual(original, (module.HEIGHT, module.WIDTH, module.SENSOR_RANGE))
        self.assertEqual(self.case["truth"], truth)
        self.assertFalse(runner.tracemalloc.is_tracing())

    def test_no_clock_is_used_for_untimed_work(self):
        def forbidden():
            raise AssertionError("Clock used in a non-timing pass")
        for phase in ("structural", "memory"):
            runner.run_episode(self.modules["A"], self.case, phase, clock=forbidden)


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.config = runner.ROOT / "configs/basiccode_smoke_v1.json"
        self.identity = {"commit": "test-only", "dirty": False, "dirty_details": "", "sha256": {}}

    def run_smoke(self, name="test", **kwargs):
        with patch.object(runner, "source_identity", return_value=self.identity):
            return runner.run(self.config, self.directory, name, smoke=True, plots=False, **kwargs)

    def test_complete_pipeline_and_reanalysis_without_exploration(self):
        path = self.run_smoke()
        manifest = json.loads((path / "manifest.json").read_text())
        summary = json.loads((path / "summary.json").read_text())
        self.assertEqual(manifest["status"], "completed")
        self.assertEqual(manifest["purpose"], "smoke_validation")
        self.assertTrue(summary["valid"], summary["issues"])
        self.assertEqual(summary["record_count"], 51)
        self.assertEqual(len(summary["per_case"]), 2)
        self.assertTrue((path / "records.csv").is_file())
        self.assertTrue((path / "summary.csv").is_file())
        with patch.object(runner, "run_episode", side_effect=AssertionError("Must not rerun")):
            self.assertEqual(analyze(path), summary)

    def test_missing_duplicate_or_corrupt_record_cannot_be_reported_valid(self):
        path = self.run_smoke()
        raw = (path / "records.jsonl").read_text(encoding="utf-8")
        lines = raw.splitlines()
        for corrupted in ("\n".join(lines[:-1]), raw + lines[-1] + "\n", raw + "{unfinished"):
            with self.subTest(variant=corrupted[-30:]):
                (path / "records.jsonl").write_text(corrupted, encoding="utf-8")
                self.assertFalse(analyze(path)["valid"])
        (path / "records.jsonl").write_text(raw, encoding="utf-8")
        self.assertTrue(analyze(path)["valid"])

    def test_invalid_numeric_measurement_cannot_crash_or_pass_analysis(self):
        path = self.run_smoke("invalid-time")
        raw = (path / "records.jsonl").read_text(encoding="utf-8")
        records = [json.loads(line) for line in raw.splitlines()]
        next(r for r in records if r["phase"] == "timing")["planner_ns"] = None
        (path / "records.jsonl").write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
        self.assertFalse(analyze(path)["valid"])

    def test_result_mismatch_blocks_all_timing_and_retains_failure(self):
        original = runner.run_episode
        phases = []

        def mismatch(module, case, phase):
            phases.append(phase)
            metrics, outcome = original(module, case, phase)
            if module.__name__.endswith("_1"):
                outcome["result"]["total_cost"] += 1
            return metrics, outcome

        with patch.object(runner, "run_episode", side_effect=mismatch):
            with self.assertRaisesRegex(RuntimeError, "Correctness/input gate"):
                self.run_smoke("mismatch")
        self.assertNotIn("timing", phases)
        path = self.directory / "mismatch"
        self.assertFalse(analyze(path)["valid"])
        self.assertIn("mismatch", (path / "records.jsonl").read_text().lower())

    def test_generation_failure_is_preserved_and_never_replaced(self):
        original = runner.materialize

        def failed(config, common):
            cases = original(config, common)
            cases[0] = {k: v for k, v in cases[0].items() if k not in ("truth", "start", "map_hash")}
            cases[0]["generation_error"] = "forced test-only generation failure"
            return cases

        with patch.object(runner, "materialize", side_effect=failed):
            with self.assertRaisesRegex(RuntimeError, "Correctness/input gate"):
                self.run_smoke("generation")
        path = self.directory / "generation"
        self.assertIn("forced", (path / "maps.json").read_text())
        self.assertTrue((path / "failures.jsonl").exists())
        self.assertFalse(analyze(path)["valid"])

    def test_existing_run_id_cannot_overwrite_evidence(self):
        self.run_smoke("unique")
        before = (self.directory / "unique/records.jsonl").read_bytes()
        with self.assertRaises(FileExistsError):
            self.run_smoke("unique")
        self.assertEqual(before, (self.directory / "unique/records.jsonl").read_bytes())

    def test_non_smoke_dirty_source_is_refused_before_output_creation(self):
        identity = {**self.identity, "dirty": True, "dirty_details": "test dirty code"}
        with patch.object(runner, "source_identity", return_value=identity):
            with self.assertRaisesRegex(RuntimeError, "Commit source"):
                runner.run(self.config, self.directory, "dirty", plots=False)
        self.assertFalse((self.directory / "dirty").exists())

    def test_undefined_ratios_are_not_silently_averaged_over_other_maps(self):
        self.assertIsNone(estimate([2.0, None])["value"])
        self.assertEqual(estimate([0, 0])["value"], 0)

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "Graph dependency not installed")
    def test_png_pdf_graphs_and_failure_gate(self):
        from benchmarks.basiccode_plot import plot
        path = self.run_smoke("graphs")
        with patch.object(runner, "run_episode", side_effect=AssertionError("Must not rerun")):
            files = plot(path)
        self.assertEqual(len(files), 8)
        for file in files:
            self.assertGreater(file.stat().st_size, 100)
            if file.suffix == ".png":
                self.assertTrue(file.read_bytes().startswith(b"\x89PNG"))
            else:
                self.assertTrue(file.read_bytes().startswith(b"%PDF"))
        (path / "records.jsonl").write_text("", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "incomplete/failed"):
            plot(path)


class ConfigTests(unittest.TestCase):
    def test_default_uses_user_approved_reduced_workload_without_running_it(self):
        path = runner.ROOT / "configs/basiccode_reduced_v1.json"
        config = json.loads(path.read_text())
        runner.validate_config(config)
        self.assertEqual(config["sizes"], [50, 100, 150])
        self.assertEqual(config["obstacle_rates"], [0.1, 0.3, 0.5])
        self.assertEqual(config["seeds"], [42, 43, 44])
        self.assertEqual(config["repetitions"], 5)
        self.assertEqual(config["sensor_range"], 4.0)
        with patch.object(runner, "run") as run:
            self.assertEqual(runner.main(["--run-id", "routing-check", "--no-plots"]), 0)
        self.assertEqual(run.call_args.args[0], path)
        # Mocked dispatch only: no map generation or exploration is executed.

    def test_user_large_workload_is_exactly_preserved(self):
        config = json.loads((runner.ROOT / "configs/basiccode_large_v1.json").read_text())
        runner.validate_config(config)
        self.assertEqual(config["sizes"], [100, 200, 300, 400, 500])
        self.assertEqual(config["obstacle_rates"], [0.1, 0.2, 0.3, 0.4, 0.5])
        self.assertEqual(config["repetitions"], 5)
        self.assertEqual(len(config["sizes"]) * len(config["obstacle_rates"]) * len(config["seeds"]), 75)
        # No large maps or exploration are run in this check.

    def test_five_repetitions_balance_positions_across_three_seeds(self):
        from collections import Counter
        positions = Counter()
        for offset in (1, 4, 5):
            for rep in range(5):
                for position, method in enumerate(runner.ORDERS[(rep + offset) % 6]):
                    positions[(method, position)] += 1
        self.assertEqual(set(positions.values()), {5})

    def test_invalid_or_duplicate_conditions_are_refused(self):
        config = json.loads((runner.ROOT / "configs/basiccode_smoke_v1.json").read_text())
        for key, value in (("sizes", [4, 4]), ("seeds", [True]), ("obstacle_rates", [float("nan")]),
                           ("repetitions", 1), ("sensor_range", 0), ("memory_pass", 1)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                runner.validate_config({**config, key: value})


class ConnectedMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.common, _ = runner.load_algorithms()

    def test_small_maps_have_exact_density_connectivity_and_observable_walls(self):
        from benchmarks.basiccode_maps import connected_map
        for size in (5, 6, 7, 8, 10, 17):
            for density in (0, 0.1, 0.2, 0.3, 0.4, 0.5):
                for seed in (0, 42):
                    with self.subTest(size=size, density=density, seed=seed):
                        truth, start, metadata = connected_map(size, density, seed)
                        walls = sum(map(sum, truth))
                        self.assertEqual(walls, round(size * size * density))
                        reached, _ = self.common.shortest_paths(truth, start)
                        self.assertEqual(len(reached), size * size - walls)
                        self.assertTrue(all(any(self.common.free_neighbors(truth, (r, c)))
                                            for r in range(size) for c in range(size) if truth[r][c] == 1))
                        self.assertEqual(metadata["wall_count"], walls)
                        self.assertEqual((truth, start, metadata), connected_map(size, density, seed))

    def test_density_sets_are_nested_and_start_is_fixed(self):
        from benchmarks.basiccode_maps import connected_map
        previous, start = set(), None
        for density in (0.1, 0.2, 0.3, 0.4, 0.5):
            truth, current_start, _ = connected_map(20, density, 42)
            walls = {(r, c) for r in range(20) for c in range(20) if truth[r][c] == 1}
            self.assertTrue(previous <= walls)
            start = current_start if start is None else start
            self.assertEqual(start, current_start)
            previous = walls

    def test_small_connected_case_matches_all_methods(self):
        from benchmarks.basiccode_maps import connected_map
        _, modules = runner.load_algorithms()
        reference = None
        for density in (0.1, 0.5):
            truth, start, _ = connected_map(6, density, 42)
            case = {"truth": truth, "start": start, "sensor_range": 2}
            reference = None
            for module in modules.values():
                _, outcome = runner.run_episode(module, case, "structural")
                reference = outcome if reference is None else reference
                self.assertEqual(outcome, reference)


if __name__ == "__main__":
    unittest.main()
