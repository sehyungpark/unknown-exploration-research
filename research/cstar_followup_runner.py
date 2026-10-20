"""User-invoked continuation of the frozen C* pilot; never runs on import.

This is exploratory follow-up infrastructure, not Experiment 3. Historical
structural evidence is read-only. Primary timing and tracemalloc are separate.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
from statistics import median
import subprocess
import sys
from time import perf_counter_ns
import traceback
import tracemalloc
from uuid import uuid4

from research import extension_pilot_20260929 as pilot
from src.environment import GroundTruthGrid
from src.environment.fixtures import MapFixture
from src.evaluation import ExplorationSimulator
from src.evaluation.experiment_2_analysis import linear_quantile
from src.planning import PlanStatus
from src.utils import ground_truth_hash

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = Path("configs/cstar_followup_pilot_v1.json")
BASELINE_PATH = Path("results/extension_pilot_20260929/run-001")
OUTPUT_PATH = Path("results/cstar_followup/runs")
VERSION = "cstar-followup-runner-v1"
METHODS = ("B", "S*", "C*", "CERT")
TIMING_IDS = ("open", "maze_like", "rooms-20-door-1", "rooms-30-door-3",
              "random-20-0.1-1", "random-30-0.3-1")
ORDERS = tuple(METHODS[i:] + METHODS[:i] for i in range(4))
SOURCE_SCOPES = ("src", "research", "tests", "scripts", str(CONFIG_PATH), ".gitattributes")
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


def canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    with temporary.open("xb") as stream:
        stream.write(canonical_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def append_record(path, value):
    with Path(path).open("ab") as stream:
        stream.write(canonical_bytes(value))
        stream.flush()


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True,
                                   encoding="utf-8", errors="strict").strip()


def code_identity(root):
    """Results/docs may be untracked; benchmark code/config must be committed."""
    dirty = git(root, "status", "--porcelain", "--untracked-files=all", "--", *SOURCE_SCOPES)
    require(not dirty, "Commit benchmark source/config/tests/scripts before running:\n" + dirty)
    paths = git(root, "ls-files", "--", *SOURCE_SCOPES).splitlines()
    require(str(CONFIG_PATH).replace("\\", "/") in paths, "Frozen config is not committed")
    hashes = {}
    for name in paths:
        path = Path(root) / name
        if path.is_file():
            # Git CRLF checkout conversion must not change code identity.
            hashes[name] = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    return {"commit": git(root, "rev-parse", "HEAD"),
            "source_sha256": hashlib.sha256(canonical_bytes(hashes)).hexdigest(),
            "source_files": hashes}


def load_baseline(root=ROOT):
    """Read and validate the fixed 21-map evidence without constructing a planner."""
    root = Path(root)
    config = read_json(root / CONFIG_PATH)
    expected = {
        "version": VERSION, "kind": "exploratory", "sensor_range": 8,
        "methods": list(METHODS), "timing_ids": list(TIMING_IDS),
        "orders": [list(x) for x in ORDERS], "warmups": 1, "timed_repetitions": 4,
        "expected_maps": 21, "expected_snapshots": 616,
        "baseline_path": BASELINE_PATH.as_posix(),
    }
    require(set(config) == set(expected) | {"baseline_hashes"}, "Unsupported frozen config fields")
    for key, value in expected.items():
        require(config[key] == value, f"Frozen config changed: {key}")
    baseline = root / BASELINE_PATH
    required_files = {"manifest.json", "maps.json", "structural.jsonl", "snapshots.jsonl",
                      "certificate_properties.json", "structural_source.py", "structural_protocol.md"}
    require(set(config["baseline_hashes"]) == required_files, "Incomplete baseline hash list")
    for name, expected_hash in config["baseline_hashes"].items():
        require(pilot.digest(baseline / name) == expected_hash, f"Baseline evidence changed: {name}")
    original = read_json(baseline / "manifest.json")
    require(original["status"] == "STRUCTURAL_PASS", "Historical structural phase is incomplete")
    require(pilot.digest(baseline / "structural_source.py") == original["script_sha256"],
            "Executed structural source hash mismatch")
    require(pilot.digest(baseline / "structural_protocol.md") == original["protocol_sha256"],
            "Original structural protocol hash mismatch")
    records = read_jsonl(baseline / "structural.jsonl")
    snapshots = read_jsonl(baseline / "snapshots.jsonl")
    maps = read_json(baseline / "maps.json")
    require(len(maps) == len(records) == 21 and len(snapshots) == 616, "Incomplete structural evidence")
    require(all(r["correctness_valid"] for r in records + snapshots), "Invalid structural evidence")
    map_ids = [r["id"] for r in maps]
    require(len(set(map_ids)) == 21, "Duplicate map ID")
    require(set(map_ids) == {r["map"] for r in records} == {r["map"] for r in snapshots}, "Map domains differ")
    fixtures, references = {}, {}
    for item in maps:
        grid = GroundTruthGrid.from_ascii(item["ascii"])
        require(ground_truth_hash(grid) == item["map_hash"], f"Map hash mismatch: {item['id']}")
        require(list(grid.shape) == item["shape"], "Map shape mismatch")
        fixtures[item["id"]] = MapFixture(item["id"], grid, tuple(item["start"]))
        rows = [r for r in snapshots if r["map"] == item["id"]]
        require([r["cycle"] for r in rows] == list(range(len(rows))), "Snapshot cycle gap")
        require(rows[-1]["status"] == "EXPLORATION_COMPLETE" and rows[-1]["target"] is None,
                "Missing terminal snapshot")
        require(all(r["status"] == "SELECTED" and r["target"] is not None for r in rows[:-1]),
                "Premature terminal snapshot")
        for row in rows:
            require(set(row["methods"]) == set(METHODS), "Incomplete method domain")
            require(all(value["target"] == row["target"] for value in row["methods"].values()),
                    "Historical method target mismatch")
        matches = [r for r in records if r["map"] == item["id"]]
        require(len(matches) == 1, "Duplicate structural record")
        ref = matches[0]
        require(ref["snapshots"] == len(rows), "Snapshot count mismatch")
        require(ref["sequence_hash"] == pilot.seqhash([r["target"] for r in rows]), "Historical sequence mismatch")
        references[item["id"]] = ref
    require(set(TIMING_IDS) <= set(fixtures), "Timing map missing")
    return config, fixtures, references


def preflight(root=ROOT):
    require(sys.version_info >= (3, 12), "Python 3.12 or newer is required")
    require(sys.flags.optimize == 0, "Do not run with -O: historical correctness assertions must remain active")
    config, fixtures, references = load_baseline(root)
    identity = code_identity(root)
    return config, fixtures, references, identity


def run_path(root, run_id):
    require(bool(RUN_ID.fullmatch(run_id)), "Run ID must contain only letters, digits, '_' and '-'")
    return Path(root) / OUTPUT_PATH / run_id


@contextmanager
def lock_run(path):
    lock = Path(path) / "execution.lock"
    descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(descriptor, f"pid={os.getpid()}\nstarted={now()}\n".encode())
        os.close(descriptor)
        descriptor = None
        yield
    finally:
        if descriptor is not None:
            os.close(descriptor)
        lock.unlink()


def environment_identity():
    return {"python": platform.python_version(), "executable": sys.executable,
            "platform": platform.platform(), "processor": platform.processor(),
            "logical_cpu_count": os.cpu_count()}


def prepare(root, run_id):
    config, _, _, identity = preflight(root)
    path = run_path(root, run_id)
    path.mkdir(parents=True, exist_ok=False)
    manifest = {"version": VERSION, "run_id": run_id, "status": "PREPARED", "created": now(),
                "identity": identity, "config": config,
                "environment": environment_identity(), "events": []}
    atomic_json(path / "manifest.json", manifest)
    print(f"PREPARED {path}", flush=True)
    return path


def validate_invocation(root, path):
    config, fixtures, references, identity = preflight(root)
    manifest = read_json(path / "manifest.json")
    require(manifest["version"] == VERSION and manifest["config"] == config, "Invocation config differs")
    require(manifest["identity"] == identity, "Code/commit changed: create a new run ID after tests")
    require(manifest["environment"] == environment_identity(), "Machine/Python environment changed between stages")
    return manifest, fixtures, references


def update_status(path, manifest, status):
    manifest["status"] = status
    manifest["events"].append({"status": status, "at": now()})
    atomic_json(path / "manifest.json", manifest)


def decision(result):
    return {"status": result.status.value, "target": result.selected_candidate,
            "gain": result.selected_gain, "distance": result.selected_distance,
            "score": result.selected_score, "path": result.selected_path,
            "eligible_candidates": result.eligible_candidate_count}


class EpisodeFailure(RuntimeError):
    def __init__(self, message, evidence):
        super().__init__(message)
        self.evidence = evidence


def run_episode(fixture, method, *, expected=None, measure="none"):
    """Time planner calls only; comparison, hashing and physical scans are outside.

    Memory is a separate episode-allocation peak after construction/initial scan;
    it includes arrival sensing, movement validation and decision bookkeeping.
    """
    require(method in METHODS + ("A",), "Unknown method")
    require(measure in ("none", "timing", "memory"), "Unknown measurement")
    require(not tracemalloc.is_tracing(), "Unexpected active tracemalloc session")
    simulator = ExplorationSimulator(fixture.ground_truth, fixture.start, 8)
    planner = None if method == "A" else pilot.planner_for(method)
    adapter = pilot.VisibilityAdapter(certify=True, verify=False) if method == "CERT" else None
    delta, elapsed, trace, exact_evaluations = None, 0, [], 0
    if measure == "memory":
        tracemalloc.start()
    try:
        for cycle in range(pilot.limit(fixture)):
            started = perf_counter_ns() if measure == "timing" else None
            try:
                if method == "A":
                    result = simulator.plan()
                elif method == "CERT":
                    adapter.observe(simulator.world.belief, delta)
                    result = pilot.plan(method, planner, adapter, simulator, delta)
                elif method == "B":
                    result = planner.plan(simulator.world.belief, simulator.world.robot)
                else:
                    result = planner.plan(simulator.world.belief, simulator.world.robot, newly_known=delta)
            finally:
                if started is not None:
                    elapsed += perf_counter_ns() - started
            entry = decision(result)
            if expected is not None:
                require(cycle < len(expected), "Episode exceeds exhaustive reference")
                require(canonical_bytes(entry) == canonical_bytes(expected[cycle]),
                        f"Exhaustive decision mismatch at cycle {cycle}")
            trace.append(entry)
            exact_evaluations += result.exact_gain_evaluations
            if result.status is PlanStatus.EXPLORATION_COMPLETE:
                require(expected is None or len(trace) == len(expected), "Early terminal decision")
                memory = tracemalloc.get_traced_memory() if measure == "memory" else (None, None)
                return {"map_id": fixture.name, "method": method, "correctness_valid": True,
                        "snapshot_count": len(trace), "decisions": trace,
                        "decision_hash": hashlib.sha256(canonical_bytes(trace)).hexdigest(),
                        "target_sequence_hash": pilot.seqhash([r["target"] for r in trace]),
                        "planner_wall_time_ns": elapsed if measure == "timing" else None,
                        "tracemalloc_current_bytes": memory[0], "tracemalloc_peak_bytes": memory[1],
                        "exact_evaluations": exact_evaluations,
                        "certificate_counters": dict(adapter.counters) if adapter else {}}
            delta = pilot.advance(simulator, result.selected_path)
        raise RuntimeError("Cycle limit reached")
    except BaseException as exc:
        evidence = {"map_id": fixture.name, "method": method,
                             "cycle": len(trace), "completed_decisions": trace,
                             "robot": simulator.world.robot,
                             "belief": [[cell.value for cell in row] for row in simulator.world.belief.snapshot()],
                             "ground_truth_hash": ground_truth_hash(fixture.ground_truth),
                             "elapsed_planner_ns": elapsed if measure == "timing" else None,
                             "correctness_valid": False}
        if not isinstance(exc, Exception):
            exc.evidence = evidence
            raise
        raise EpisodeFailure(str(exc), evidence) from exc
    finally:
        if measure == "memory":
            tracemalloc.stop()


def timing_schedule():
    for map_id in TIMING_IDS:
        for repetition, order in enumerate((METHODS,) + ORDERS):
            for position, method in enumerate(order):
                yield {"map_id": map_id, "method": method, "repetition": repetition,
                       "timed": repetition > 0, "position": position, "order": list(order)}


def summarize_timing(records):
    schedule = list(timing_schedule())
    require(len(records) == len(schedule) == 120, "Timing schedule incomplete")
    for actual, expected in zip(records, schedule):
        require(all(actual[key] == value for key, value in expected.items()), "Timing order/repetition changed")
        require(actual["correctness_valid"], "Invalid episode cannot enter performance summary")
        require(type(actual["planner_wall_time_ns"]) is int and actual["planner_wall_time_ns"] > 0,
                "Invalid planner timer")
    per_map = {}
    for map_id in TIMING_IDS:
        per_map[map_id] = {}
        for method in METHODS:
            values = [r["planner_wall_time_ns"] for r in records
                      if r["map_id"] == map_id and r["method"] == method and r["timed"]]
            require(len(values) == 4, "Four timed repetitions are required")
            per_map[map_id][method] = {"median_ns": median(values), "minimum_ns": min(values),
                                      "maximum_ns": max(values), "q1_ns": linear_quantile(values, .25),
                                      "q3_ns": linear_quantile(values, .75)}
    comparisons = {}
    for numerator, denominator in (("C*", "S*"), ("C*", "B"), ("CERT", "C*"), ("S*", "B")):
        ratios = {m: per_map[m][numerator]["median_ns"] / per_map[m][denominator]["median_ns"] for m in TIMING_IDS}
        comparisons[f"{numerator}/{denominator}"] = {
            "per_map_ratios": ratios,
            "geometric_mean": math.exp(sum(math.log(x) for x in ratios.values()) / len(ratios))}
    return {"version": VERSION, "exploratory_only": True, "classification": None,
            "measurement": "planner calls only; validation/physical sensing outside timer",
            "timed_episodes": 96, "warmup_episodes": 24,
            "per_map": per_map, "comparisons": comparisons}


def run_tests(root, path, manifest):
    require(manifest["status"] == "PREPARED", "Tests require PREPARED state; use a fresh run ID after failure")
    require(not (path / "tests.log").exists(), "Test output already exists")
    update_status(path, manifest, "TESTS_RUNNING")
    environment = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    with (path / "tests.log").open("x", encoding="utf-8", newline="\n") as log:
        process = subprocess.Popen([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                                   cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding="utf-8", errors="replace", env=environment)
        try:
            for line in process.stdout:
                print(line, end="", flush=True)
                log.write(line)
                log.flush()
            returncode = process.wait()
        except BaseException:
            process.terminate()
            process.wait()
            raise
    text = (path / "tests.log").read_text(encoding="utf-8")
    require(returncode == 0 and re.search(
        r"^Ran [1-9][0-9]* tests? in [^\r\n]+\r?\n\r?\nOK(?: \([^\r\n]*\))?\s*\Z", text, re.M),
        "Full test suite did not produce a verified pass")
    manifest["test_exit_code"] = returncode
    manifest["tests_log_sha256"] = pilot.digest(path / "tests.log")
    update_status(path, manifest, "TESTS_PASSED")


def run_timing(path, manifest, fixtures, historical):
    require(manifest["status"] == "TESTS_PASSED", "Timing requires a recorded full-suite pass")
    require(pilot.digest(path / "tests.log") == manifest["tests_log_sha256"], "Test log changed")
    require(not (path / "timing.jsonl").exists() and not (path / "references.json").exists(),
            "Partial timing/reference output exists; preserve it and use a new run ID")
    update_status(path, manifest, "REFERENCES_RUNNING")
    references = {}
    for map_id in TIMING_IDS:
        print(f"REFERENCE {map_id}", flush=True)
        reference = run_episode(fixtures[map_id], "A")
        require(reference["target_sequence_hash"] == historical[map_id]["sequence_hash"],
                "Current exhaustive sequence differs from historical evidence")
        references[map_id] = reference
    atomic_json(path / "references.json", references)
    manifest["references_sha256"] = pilot.digest(path / "references.json")
    update_status(path, manifest, "TIMING_RUNNING")
    records = []
    for index, spec in enumerate(timing_schedule(), 1):
        print(f"TIMING {index}/120 {spec['map_id']} {spec['method']} repetition={spec['repetition']}", flush=True)
        result = run_episode(fixtures[spec["map_id"]], spec["method"],
                             expected=references[spec["map_id"]]["decisions"], measure="timing")
        result.pop("decisions")
        record = {**result, **spec}
        append_record(path / "timing.jsonl", record)
        records.append(record)
    atomic_json(path / "timing_summary.json", summarize_timing(records))
    manifest["timing_sha256"] = pilot.digest(path / "timing.jsonl")
    update_status(path, manifest, "TIMING_DONE")


def run_memory(path, manifest, fixtures):
    require(manifest["status"] == "TIMING_DONE", "Memory pass requires complete timing")
    require(pilot.digest(path / "references.json") == manifest["references_sha256"], "Reference changed")
    require(pilot.digest(path / "timing.jsonl") == manifest["timing_sha256"], "Timing evidence changed")
    require(not (path / "memory.jsonl").exists(), "Memory output exists; preserve partial runs")
    references = read_json(path / "references.json")
    update_status(path, manifest, "MEMORY_RUNNING")
    for index, (map_id, method) in enumerate(((m, v) for m in TIMING_IDS for v in METHODS), 1):
        print(f"MEMORY {index}/24 {map_id} {method}", flush=True)
        result = run_episode(fixtures[map_id], method, expected=references[map_id]["decisions"], measure="memory")
        result.pop("decisions")
        result["measurement"] = "separate post-initialization episode tracemalloc; includes sensing/validation/bookkeeping"
        append_record(path / "memory.jsonl", result)
    summary = summarize_timing(read_jsonl(path / "timing.jsonl"))
    summary["memory"] = read_jsonl(path / "memory.jsonl")
    summary["memory_limitations"] = "Python allocations only, not process RSS; S* retains C* bitset allocation"
    atomic_json(path / "summary.json", summary)
    update_status(path, manifest, "PASS")


def execute_stage(root, run_id, stage):
    path = run_path(root, run_id)
    with lock_run(path):
        manifest, fixtures, historical = validate_invocation(root, path)
        # Invalid/repeated transitions fail without rewriting a completed manifest.
        expected = {"test": "PREPARED", "timing": "TESTS_PASSED", "memory": "TIMING_DONE"}[stage]
        require(manifest["status"] == expected, f"{stage} requires {expected}, got {manifest['status']}")
        try:
            if stage == "test":
                run_tests(root, path, manifest)
            elif stage == "timing":
                run_timing(path, manifest, fixtures, historical)
            else:
                run_memory(path, manifest, fixtures)
        except BaseException as exc:
            failure = {"stage": stage, "at": now(), "exception_type": type(exc).__name__,
                       "message": str(exc), "traceback": traceback.format_exc(),
                       "evidence": getattr(exc, "evidence", None)}
            atomic_json(path / ("failure-" + uuid4().hex + ".json"), failure)
            update_status(path, manifest, "INTERRUPTED" if isinstance(exc, KeyboardInterrupt) else "FAILED")
            raise
    print(f"{manifest['status']} {path}", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("check", "prepare", "test", "timing", "memory", "status", "all"))
    parser.add_argument("--run-id")
    args = parser.parse_args(argv)
    os.chdir(ROOT)
    if args.stage == "check":
        config, _, _, identity = preflight(ROOT)
        print(json.dumps({"status": "READY", "version": VERSION,
                          "identity": {key: identity[key] for key in ("commit", "source_sha256")},
                          "maps": config["expected_maps"], "planned_timing_episodes": 120,
                          "planned_memory_episodes": 24}, indent=2))
        return 0
    if not args.run_id:
        parser.error("--run-id is required for this stage")
    if args.stage == "status":
        print(json.dumps(read_json(run_path(ROOT, args.run_id) / "manifest.json"), indent=2))
    elif args.stage == "prepare":
        prepare(ROOT, args.run_id)
    elif args.stage == "all":
        prepare(ROOT, args.run_id)
        for stage in ("test", "timing", "memory"):
            execute_stage(ROOT, args.run_id, stage)
    else:
        execute_stage(ROOT, args.run_id, args.stage)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
