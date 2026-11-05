"""Regression checks for complete paired retries and checkpoint integrity."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from benchmarks import basiccode_runner as core
from benchmarks.basiccode_storage import accepted, read
from benchmarks.basiccode_worker import run_job


class RetryTests(unittest.TestCase):
    def test_interrupted_paired_block_restarts_and_keeps_old_records(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            case = core.sanity_cases()[2]
            path = root / "input.json"
            core.write_json(path, case)
            def job(stage):
                return (root, path, stage, {"warmups": 1, "repetitions": 2}, 0, "session", "isolated", 1)
            run_job(job("structural"))
            normal = {"sleep_offset_ns": 0, "event": 1}
            changed = {**normal, "event": 2}
            folder = root / "jobs" / case["case_id"] / "timing"
            with patch("benchmarks.basiccode_worker.power.sample", side_effect=[normal, normal, changed]):
                with self.assertRaisesRegex(RuntimeError, "Power event"):
                    run_job(job("timing"))
            self.assertIsNone(accepted(folder))
            with patch("benchmarks.basiccode_worker.power.sample", return_value=normal):
                run_job(job("timing"))
            self.assertEqual(len(accepted(folder)), 9)
            with patch.object(core, "run_episode", side_effect=AssertionError("unexpected rerun")):
                run_job(job("timing"))
            self.assertEqual(len(list(folder.glob("*/0.start.json"))), 2)
            record = folder / read(folder / "accepted.json")["attempt"] / "0.json"
            record.write_text("{}")
            with self.assertRaisesRegex(ValueError, "checksum"):
                accepted(folder)
