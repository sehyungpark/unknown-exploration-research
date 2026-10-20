"""Infrastructure tests only: fake schedules and a nonformal 1x20 smoke map."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research import cstar_followup_runner as runner
from src.environment import GroundTruthGrid
from src.environment.fixtures import MapFixture


class FrozenInputTests(unittest.TestCase):
    def test_retained_evidence_loads_without_running_any_planner(self):
        with patch.object(runner, "ExplorationSimulator", side_effect=AssertionError("no workload")):
            config, fixtures, records = runner.load_baseline()
        self.assertEqual(config["expected_maps"], 21)
        self.assertEqual(sum(record["snapshots"] for record in records.values()), 616)
        self.assertEqual(set(fixtures), set(records))

    def test_changed_baseline_byte_is_rejected_before_map_construction(self):
        config = runner.read_json(runner.ROOT / runner.CONFIG_PATH)
        with patch.object(runner, "read_json", return_value=config), \
             patch.object(runner.pilot, "digest", return_value="tampered"), \
             patch.object(runner, "GroundTruthGrid") as grid:
            with self.assertRaisesRegex(RuntimeError, "Baseline evidence changed"):
                runner.load_baseline()
            grid.from_ascii.assert_not_called()

    def test_changed_workload_is_rejected(self):
        config = runner.read_json(runner.ROOT / runner.CONFIG_PATH)
        config["timed_repetitions"] = 3
        with patch.object(runner, "read_json", return_value=config):
            with self.assertRaisesRegex(RuntimeError, "timed_repetitions"):
                runner.load_baseline()

    def test_map_text_must_match_retained_hash(self):
        real_read = runner.read_json

        def changed(path):
            value = real_read(path)
            if Path(path).name == "maps.json":
                value[0]["ascii"][0] = "#" + value[0]["ascii"][0][1:]
            return value

        with patch.object(runner, "read_json", side_effect=changed):
            with self.assertRaisesRegex(RuntimeError, "Map hash mismatch"):
                runner.load_baseline()

    def test_import_has_not_created_any_invocation(self):
        # Calling check/load is read-only, including when no user output exists.
        with TemporaryDirectory() as temporary:
            before = set(Path(temporary).iterdir())
            runner.run_path(temporary, "smoke")
            self.assertEqual(set(Path(temporary).iterdir()), before)


class EpisodeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = MapFixture("followup-smoke-line", GroundTruthGrid.from_ascii(("." * 20,)), (0, 0))

    def test_all_methods_match_full_exhaustive_trace_on_nonformal_map(self):
        reference = runner.run_episode(self.fixture, "A")
        self.assertGreater(len(reference["decisions"]), 1)
        for method in runner.METHODS:
            with self.subTest(method=method):
                result = runner.run_episode(self.fixture, method, expected=reference["decisions"])
                self.assertEqual(result["decision_hash"], reference["decision_hash"])
                self.assertIsNone(result["planner_wall_time_ns"])

    def test_same_target_with_wrong_gain_is_not_accepted(self):
        reference = runner.run_episode(self.fixture, "A")["decisions"]
        bad = deepcopy(reference)
        bad[0]["gain"] += 1
        with self.assertRaises(runner.EpisodeFailure) as caught:
            runner.run_episode(self.fixture, "C*", expected=bad)
        self.assertIn("decision mismatch", str(caught.exception))
        self.assertFalse(caught.exception.evidence["correctness_valid"])
        self.assertIn("belief", caught.exception.evidence)

    def test_timing_excludes_comparison_and_arrival_scan(self):
        real_canonical = runner.canonical_bytes

        def check_not_timed(value):
            self.assertEqual(clock_state["running"], False)
            return real_canonical(value)

        clock_state = {"running": False, "ticks": 0}

        def clock():
            clock_state["running"] = not clock_state["running"]
            clock_state["ticks"] += 100
            return clock_state["ticks"]

        reference = runner.run_episode(self.fixture, "A")["decisions"]
        real_advance = runner.pilot.advance

        def advance(*args):
            self.assertFalse(clock_state["running"])
            return real_advance(*args)

        with patch.object(runner, "perf_counter_ns", side_effect=clock), \
             patch.object(runner, "canonical_bytes", side_effect=check_not_timed), \
             patch.object(runner.pilot, "advance", side_effect=advance):
            result = runner.run_episode(self.fixture, "C*", expected=reference, measure="timing")
        self.assertEqual(result["planner_wall_time_ns"], 100 * len(reference))

    def test_memory_is_untimed_and_tracer_is_stopped_after_exception(self):
        reference = runner.run_episode(self.fixture, "A")["decisions"]
        with patch.object(runner, "perf_counter_ns", side_effect=AssertionError("memory must not time")):
            result = runner.run_episode(self.fixture, "CERT", expected=reference, measure="memory")
        self.assertGreater(result["tracemalloc_peak_bytes"], 0)
        self.assertIsNone(result["planner_wall_time_ns"])
        self.assertFalse(runner.tracemalloc.is_tracing())
        bad = deepcopy(reference)
        bad[0]["gain"] += 1
        with self.assertRaises(runner.EpisodeFailure):
            runner.run_episode(self.fixture, "CERT", expected=bad, measure="memory")
        self.assertFalse(runner.tracemalloc.is_tracing())

    def test_certificate_forwarding_is_restored_after_exception(self):
        module = runner.pilot.star_module
        original = module.optimistic_visible_unknown_cells
        with patch.object(runner.pilot.VisibilityAdapter, "__call__", side_effect=RuntimeError("injected")):
            with self.assertRaises(runner.EpisodeFailure):
                runner.run_episode(self.fixture, "CERT")
        self.assertIs(module.optimistic_visible_unknown_cells, original)

    def test_interrupt_preserves_context_and_stops_memory_tracer(self):
        with patch.object(runner.pilot.VisibilityAdapter, "__call__", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt) as caught:
                runner.run_episode(self.fixture, "CERT", measure="memory")
        self.assertEqual(caught.exception.evidence["map_id"], self.fixture.name)
        self.assertFalse(runner.tracemalloc.is_tracing())


class ScheduleTests(unittest.TestCase):
    def records(self):
        return [{**spec, "correctness_valid": True, "planner_wall_time_ns": 1000 + index}
                for index, spec in enumerate(runner.timing_schedule())]

    def test_frozen_schedule_has_96_timed_and_24_warmup_episodes(self):
        rows = list(runner.timing_schedule())
        self.assertEqual(len(rows), 120)
        self.assertEqual(sum(row["timed"] for row in rows), 96)
        for map_id in runner.TIMING_IDS:
            for method in runner.METHODS:
                positions = [r["position"] for r in rows if r["map_id"] == map_id
                             and r["method"] == method and r["timed"]]
                self.assertEqual(sorted(positions), [0, 1, 2, 3])

    def test_summary_requires_complete_unmodified_order(self):
        rows = self.records()
        summary = runner.summarize_timing(rows)
        self.assertTrue(summary["exploratory_only"])
        self.assertIsNone(summary["classification"])
        self.assertIn("C*/S*", summary["comparisons"])
        for bad in (rows[:-1], rows[1:] + rows[:1]):
            with self.assertRaises(RuntimeError):
                runner.summarize_timing(bad)

    def test_invalid_episode_is_never_summarized(self):
        rows = self.records()
        rows[8]["correctness_valid"] = False
        with self.assertRaisesRegex(RuntimeError, "Invalid episode"):
            runner.summarize_timing(rows)


class InvocationTests(unittest.TestCase):
    def test_source_fingerprint_survives_git_crlf_conversion(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "configs").mkdir()
            (root / "configs/cstar_followup_pilot_v1.json").write_bytes(b"{}\n")
            (root / "research").mkdir()
            source = root / "research/smoke.py"
            source.write_bytes(b"value = 1\n")

            def fake_git(_root, *args):
                if args[0] == "status":
                    return ""
                if args[0] == "ls-files":
                    return "configs/cstar_followup_pilot_v1.json\nresearch/smoke.py"
                return "fixed-commit"

            with patch.object(runner, "git", side_effect=fake_git):
                before = runner.code_identity(root)
                source.write_bytes(b"value = 1\r\n")
                self.assertEqual(runner.code_identity(root), before)

    @patch("builtins.print")
    def test_complete_driver_writes_all_raw_records_with_fake_episodes(self, _print):
        # No planner, map generator, clock or full suite is run by this test.
        with TemporaryDirectory() as temporary:
            path = Path(temporary)
            (path / "tests.log").write_text("unit-test fixture\n", encoding="utf-8")
            manifest = {"status": "TESTS_PASSED", "events": [],
                        "tests_log_sha256": runner.pilot.digest(path / "tests.log")}
            fixtures = {map_id: map_id for map_id in runner.TIMING_IDS}
            historical = {map_id: {"sequence_hash": runner.pilot.seqhash([None])} for map_id in runner.TIMING_IDS}

            def fake_episode(fixture, method, *, expected=None, measure="none"):
                return {"map_id": fixture, "method": method, "correctness_valid": True,
                        "decisions": [{"target": None}], "target_sequence_hash": runner.pilot.seqhash([None]),
                        "planner_wall_time_ns": 1000 if measure == "timing" else None,
                        "tracemalloc_peak_bytes": 2000 if measure == "memory" else None}

            with patch.object(runner, "run_episode", side_effect=fake_episode) as episode:
                runner.run_timing(path, manifest, fixtures, historical)
                self.assertEqual(manifest["status"], "TIMING_DONE")
                self.assertEqual(len(runner.read_jsonl(path / "timing.jsonl")), 120)
                runner.run_memory(path, manifest, fixtures)
                self.assertEqual(episode.call_count, 6 + 120 + 24)
            self.assertEqual(manifest["status"], "PASS")
            summary = runner.read_json(path / "summary.json")
            self.assertEqual(len(summary["memory"]), 24)
            self.assertIsNone(summary["classification"])
            self.assertEqual(summary["comparisons"]["C*/S*"]["geometric_mean"], 1.0)

    def test_code_or_environment_change_cannot_reuse_test_pass(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary)
            identity = {"commit": "fixed"}
            manifest = {"version": runner.VERSION, "config": {}, "identity": identity,
                        "environment": runner.environment_identity()}
            runner.atomic_json(path / "manifest.json", manifest)
            with patch.object(runner, "preflight", return_value=({}, {}, {}, {"commit": "changed"})):
                with self.assertRaisesRegex(RuntimeError, "Code/commit changed"):
                    runner.validate_invocation(temporary, path)
            with patch.object(runner, "preflight", return_value=({}, {}, {}, identity)), \
                 patch.object(runner, "environment_identity", return_value={"python": "changed"}):
                with self.assertRaisesRegex(RuntimeError, "environment changed"):
                    runner.validate_invocation(temporary, path)

    def test_invalid_run_ids_cannot_escape_output_root(self):
        for value in ("../escape", "a/b", "a\\b", "", ".", "x" * 81):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                runner.run_path(Path("workspace"), value)

    @patch("builtins.print")
    def test_prepare_refuses_to_overwrite_old_evidence(self, _print):
        with TemporaryDirectory() as temporary, \
             patch.object(runner, "preflight", return_value=({}, {}, {}, {})):
            path = runner.prepare(temporary, "smoke")
            before = (path / "manifest.json").read_bytes()
            with self.assertRaises(FileExistsError):
                runner.prepare(temporary, "smoke")
            self.assertEqual((path / "manifest.json").read_bytes(), before)

    def test_exclusive_lock_prevents_concurrent_execution(self):
        with TemporaryDirectory() as temporary:
            with runner.lock_run(temporary):
                with self.assertRaises(FileExistsError):
                    with runner.lock_run(temporary):
                        self.fail("second process entered")
            self.assertFalse((Path(temporary) / "execution.lock").exists())

    def test_timing_cannot_bypass_tests(self):
        with TemporaryDirectory() as temporary:
            path = runner.run_path(temporary, "smoke")
            path.mkdir(parents=True)
            initial = {"status": "PREPARED", "events": []}
            runner.atomic_json(path / "manifest.json", initial)
            with patch.object(runner, "validate_invocation", return_value=(initial, {}, {})), \
                 patch.object(runner, "run_timing") as timing:
                with self.assertRaisesRegex(RuntimeError, "requires TESTS_PASSED"):
                    runner.execute_stage(temporary, "smoke", "timing")
            timing.assert_not_called()
            self.assertEqual(runner.read_json(path / "manifest.json"), initial)

    def test_failure_keeps_partial_data_and_marks_invocation_failed(self):
        with TemporaryDirectory() as temporary:
            path = runner.run_path(temporary, "smoke")
            path.mkdir(parents=True)
            initial = {"status": "TESTS_PASSED", "events": []}
            runner.atomic_json(path / "manifest.json", initial)
            runner.append_record(path / "timing.jsonl", {"retained": True})
            failure = runner.EpisodeFailure("injected mismatch", {"map_id": "smoke", "correctness_valid": False})
            with patch.object(runner, "validate_invocation", return_value=(initial, {}, {})), \
                 patch.object(runner, "run_timing", side_effect=failure):
                with self.assertRaises(runner.EpisodeFailure):
                    runner.execute_stage(temporary, "smoke", "timing")
            self.assertEqual(runner.read_json(path / "manifest.json")["status"], "FAILED")
            self.assertEqual(runner.read_jsonl(path / "timing.jsonl"), [{"retained": True}])
            failures = list(path.glob("failure-*.json"))
            self.assertEqual(len(failures), 1)
            self.assertEqual(runner.read_json(failures[0])["evidence"]["map_id"], "smoke")
            self.assertFalse((path / "summary.json").exists())

    @patch("builtins.print")
    def test_tests_fail_closed_on_nonzero_exit_or_missing_completion(self, _print):
        for code, text in ((1, "Ran 3 tests in 0.1s\nFAILED\n"), (0, ""), (0, "OK\n")):
            with self.subTest(code=code, text=text), TemporaryDirectory() as temporary:
                manifest = {"status": "PREPARED", "events": []}
                with patch.object(runner.subprocess, "Popen") as popen:
                    popen.return_value.stdout = iter(text.splitlines(keepends=True))
                    popen.return_value.wait.return_value = code
                    with self.assertRaisesRegex(RuntimeError, "verified pass"):
                        runner.run_tests(Path(temporary), Path(temporary), manifest)

    @patch("builtins.print")
    def test_successful_test_process_records_log_hash(self, _print):
        with TemporaryDirectory() as temporary:
            manifest = {"status": "PREPARED", "events": []}
            with patch.object(runner.subprocess, "Popen") as popen:
                popen.return_value.stdout = iter(["Ran 3 tests in 0.1s\n", "\n", "OK\n"])
                popen.return_value.wait.return_value = 0
                runner.run_tests(Path(temporary), Path(temporary), manifest)
            self.assertEqual(manifest["status"], "TESTS_PASSED")
            self.assertEqual(manifest["tests_log_sha256"], runner.pilot.digest(Path(temporary) / "tests.log"))


if __name__ == "__main__":
    unittest.main()
