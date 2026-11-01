"""Shared-map A/B/C* benchmark for unchanged basiccode; Windows/macOS compatible.

Run from the repository root: python -m benchmarks.basiccode_runner --help
This is exploratory infrastructure, not formal Experiment 2.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path
import platform
import re
import subprocess
import sys
from time import get_clock_info, perf_counter_ns
import traceback
import tracemalloc

ROOT = Path(__file__).resolve().parents[1]
VERSION = "basiccode-benchmark-v1"
METHODS = ("A", "B", "C*")
ORDERS = tuple(itertools.permutations(METHODS))
FILES = {"A": "A_wjstnNBV.py", "B": "B_stalelazygain.py", "C*": "C_cstarNBV.py"}
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(canonical(value) + b"\n")
    temporary.replace(path)


def append_jsonl(path, value):
    with Path(path).open("ab") as stream:
        stream.write(canonical(value) + b"\n")
        stream.flush()


def validate_config(config):
    keys = {"version", "sizes", "obstacle_rates", "seeds", "sensor_range",
            "warmups", "repetitions", "max_map_attempts", "memory_pass"}
    if not isinstance(config, dict) or set(config) not in (keys, keys | {"map_generator"}):
        raise ValueError(f"Config requires {sorted(keys)}; map_generator is optional for legacy configs")
    if config["version"] != VERSION:
        raise ValueError("Unsupported config version")
    for key in ("sizes", "obstacle_rates", "seeds"):
        values = config[key]
        if not isinstance(values, list) or not values:
            raise ValueError(f"{key} must be a nonempty list")
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
            raise ValueError(f"{key} must contain finite numbers")
        if len(set(values)) != len(values):
            raise ValueError(f"Duplicate {key} are not allowed")
    if any(type(n) is not int or n < 2 for n in config["sizes"]):
        raise ValueError("sizes must contain integers >= 2")
    if any(type(seed) is not int or seed < 0 for seed in config["seeds"]):
        raise ValueError("seeds must contain nonnegative integers")
    if any(not 0 <= p < 1 for p in config["obstacle_rates"]):
        raise ValueError("obstacle_rates must be in [0, 1)")
    radius = config["sensor_range"]
    if type(radius) not in (int, float) or not math.isfinite(radius) or radius < 1:
        raise ValueError("sensor_range must be finite and >= 1")
    for key in ("warmups", "repetitions", "max_map_attempts"):
        if type(config[key]) is not int or config[key] < 1:
            raise ValueError(f"{key} must be an integer >= 1")
    if config["repetitions"] < 2:
        raise ValueError("At least two timed repetitions are required")
    if type(config["memory_pass"]) is not bool:
        raise ValueError("memory_pass must be boolean")
    generator = config.get("map_generator", "legacy_rejection_v1")
    if generator not in ("legacy_rejection_v1", "connected_dominating_v1"):
        raise ValueError("Unknown map_generator")
    if generator == "connected_dominating_v1":
        if min(config["sizes"]) < 5 or max(config["obstacle_rates"]) > 0.5:
            raise ValueError("Connected generator requires sizes >= 5 and densities <= 0.5")
    return config


@contextmanager
def replace_attribute(obj, name, value):
    previous = getattr(obj, name)
    setattr(obj, name, value)
    try:
        yield
    finally:
        setattr(obj, name, previous)


def load_algorithms():
    """Private imports preserve standalone files and unrelated module bindings."""
    def load(name, filename):
        spec = importlib.util.spec_from_file_location(name, ROOT / "basiccode" / filename)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    common = load("_benchmark_nbvc", "nbv_common.py")
    sentinel = object()
    previous = sys.modules.get("nbv_common", sentinel)
    sys.modules["nbv_common"] = common
    try:
        modules = {method: load(f"_benchmark_nbv_{index}", filename)
                   for index, (method, filename) in enumerate(FILES.items())}
    finally:
        if previous is sentinel:
            sys.modules.pop("nbv_common", None)
        else:
            sys.modules["nbv_common"] = previous
    return common, modules


def sanity_cases():
    """Seven tiny correctness fixtures; never pooled with benchmark timing."""
    definitions = (
        ("open", ("......", "......", "......", "......"), (0, 0)),
        ("single_room", ("#######", "#.....#", "#.....#", "#.....#", "#######"), (1, 1)),
        ("corridor", ("............",), (0, 0)),
        ("dead_end", ("####.###", "####.###", "........", "####.###", "####.###"), (2, 0)),
        ("separated_rooms", (".........", "....#....", ".........", "....#....", "........."), (0, 0)),
        ("clutter", (".......", ".#.#.#.", ".......", "..#.#..", "......."), (0, 0)),
        ("maze_like", (".........", "####.###.", ".........", ".###.####", "........."), (0, 0)),
    )
    cases = []
    for name, rows, start in definitions:
        truth = [[int(cell == "#") for cell in row] for row in rows]
        cases.append({"case_id": "sanity-" + name, "kind": "sanity", "size": len(rows),
                      "obstacle_rate": None, "seed": None, "sensor_range": 2.0,
                      "truth": truth, "start": list(start), "map_hash": digest(truth)})
    return cases


def materialize(config, common):
    """Keep every requested instance, including failures; never substitute seeds."""
    cases = []
    for size, rate, seed in itertools.product(config["sizes"], config["obstacle_rates"], config["seeds"]):
        case = {"case_id": f"n{size}-p{rate}-seed{seed}", "kind": "benchmark",
                "size": size, "obstacle_rate": rate, "seed": seed,
                "sensor_range": config["sensor_range"]}
        try:
            if config.get("map_generator", "legacy_rejection_v1") == "connected_dominating_v1":
                from .basiccode_maps import connected_map
                truth, start, metadata = connected_map(size, rate, seed)
            else:
                truth, _, start = common.generate_map(size, size, rate, seed, config["max_map_attempts"])
                walls = sum(sum(row) for row in truth)
                metadata = {"generator": "legacy_rejection_v1", "requested_density": rate,
                            "realized_density": walls / (size * size), "wall_count": walls}
            case.update(truth=truth, start=list(start), map_hash=digest(truth), generation=metadata)
        except Exception as exc:
            case.update(generation_error=f"{type(exc).__name__}: {exc}",
                        generation_traceback=traceback.format_exc())
        cases.append(case)
    return cases


def source_identity(config_path):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True,
                                       encoding="utf-8", stderr=subprocess.PIPE).strip()

    relative = config_path.resolve().relative_to(ROOT).as_posix()
    scopes = ["basiccode", "benchmarks", "tests/test_basiccode_benchmark.py",
              "requirements-basiccode.txt", relative]
    dirty = git("status", "--porcelain", "--untracked-files=all", "--", *scopes)
    tracked = git("ls-files", "--", *scopes).splitlines()
    if relative not in tracked:
        dirty += "\nSelected config is not committed"
    hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
              for name in tracked if (ROOT / name).is_file()}
    for directory in ("basiccode", "benchmarks"):
        for path in (ROOT / directory).rglob("*.py"):
            hashes[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"commit": git("rev-parse", "HEAD"), "dirty": bool(dirty.strip()),
            "dirty_details": dirty, "sha256": hashes, "config_path": relative,
            "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest()}


def run_episode(module, case, phase, clock=perf_counter_ns):
    """Use the actual explore(); copies, IO and validation are outside timing."""
    if tracemalloc.is_tracing():
        raise RuntimeError("Stop external tracemalloc tracing before benchmarking")
    truth = [row[:] for row in case["truth"]]
    known = [[-1] * len(truth[0]) for _ in truth]
    original = module.evaluate_candidates
    planner_ns = planner_calls = exact_count = 0

    def select(*args, **kwargs):
        nonlocal planner_ns, planner_calls, exact_count
        before = clock() if phase in ("timing", "warmup") else None
        answer = original(*args, **kwargs)
        if before is not None:
            planner_ns += clock() - before
        planner_calls += 1
        if phase in ("structural", "sanity"):
            exact_count += len(answer[1])
        return answer

    old = module.HEIGHT, module.WIDTH, module.SENSOR_RANGE
    module.HEIGHT, module.WIDTH, module.SENSOR_RANGE = len(truth), len(truth[0]), case["sensor_range"]
    module.NBVpath.clear()
    try:
        with replace_attribute(module, "evaluate_candidates", select):
            if phase == "memory":
                tracemalloc.start()
            try:
                before = clock() if phase in ("timing", "warmup") else None
                result = module.explore(truth, known, tuple(case["start"]))
                total_ns = clock() - before if before is not None else None
                peak = tracemalloc.get_traced_memory()[1] if phase == "memory" else None
            finally:
                if phase == "memory":
                    tracemalloc.stop()
    finally:
        module.HEIGHT, module.WIDTH, module.SENSOR_RANGE = old
    if truth != case["truth"]:
        raise RuntimeError("Algorithm mutated its ground-truth input")
    outcome = {"result": asdict(result), "final_known": known}
    metrics = {"planner_ns": planner_ns if total_ns is not None else None,
               "episode_ns": total_ns, "planner_calls": planner_calls,
               "exact_evaluations": exact_count if phase in ("structural", "sanity") else None,
               "python_peak_bytes": peak, "termination": result.status,
               "remaining_unknown": result.remaining_unknown, "total_cost": result.total_cost,
               "rounds": result.rounds, "outcome_hash": digest(outcome)}
    return metrics, outcome


def run(config_path, output_root, run_id, *, smoke=False, plots=True):
    from .basiccode_analysis import analyze

    if not RUN_ID.fullmatch(run_id):
        raise ValueError("run-id must be 1-80 letters, numbers, underscores or hyphens")
    config_path = Path(config_path).resolve()
    config = validate_config(json.loads(config_path.read_text(encoding="utf-8")))
    if plots and importlib.util.find_spec("matplotlib") is None:
        raise RuntimeError("Install requirements-basiccode.txt, or use --no-plots")
    identity = source_identity(config_path)
    if identity["dirty"] and not smoke:
        raise RuntimeError("Commit source and selected config before measuring. --smoke is development-only.\n"
                           + identity["dirty_details"])
    directory = Path(output_root).resolve() / run_id
    directory.mkdir(parents=True, exist_ok=False)
    manifest = {"version": VERSION, "run_id": run_id, "created_utc": now(),
                "purpose": "smoke_validation" if smoke else "exploratory_benchmark",
                "status": "running", "config": config, "config_hash": digest(config), "source": identity,
                "system": {"python": sys.version, "implementation": platform.python_implementation(),
                           "platform": platform.platform(), "machine": platform.machine(),
                           "processor": platform.processor(), "executable": sys.executable,
                           "clock": vars(get_clock_info("perf_counter"))},
                "orders": ORDERS,
                "outcome_storage": "a_reference_only_v1",
                "timing_boundary": "selector includes BFS/mask sync; episode includes sensing/mask reports; copies/IO/validation excluded",
                "memory_boundary": "separate tracemalloc: allocations inside explore including result and wrapper; not process RSS"}
    write_json(directory / "manifest.json", manifest)
    records_path = directory / "records.jsonl"
    records_path.touch(exist_ok=False)
    problems = []

    def execute(case, method, phase, repetition, order_index, reference):
        record = {key: case[key] for key in ("case_id", "kind", "size", "obstacle_rate", "seed", "sensor_range", "map_hash")}
        record.update(method=method, phase=phase, repetition=repetition, order_index=order_index)
        outcome = None
        try:
            metrics, outcome = run_episode(modules[method], case, phase)
            record.update(metrics)
            if reference is not None and outcome != reference:
                raise RuntimeError("Exact result/final-known mismatch against A structural reference")
            record["ok"] = True
        except Exception as exc:
            record.update(ok=False, error=f"{type(exc).__name__}: {exc}", traceback=traceback.format_exc())
            problems.append({"case_id": case["case_id"], "method": method, "phase": phase,
                             "repetition": repetition, "error": record["error"]})
        if (phase in ("structural", "sanity") and method == "A") or not record["ok"]:
            record["outcome"] = outcome
        append_jsonl(records_path, record)
        return outcome if record["ok"] else None

    try:
        common, modules = load_algorithms()
        cases, anchors = materialize(config, common), sanity_cases()
        write_json(directory / "maps.json", {"benchmark": cases, "sanity": anchors})
        # With five repetitions, each map necessarily omits one permutation.
        # Across three seeds per condition omit ABC/BCA/CAB respectively: every
        # method then occurs five times in each execution position per condition.
        offsets = {case["case_id"]: (1, 4, 5)[index % 3] if config["repetitions"] == 5 else 0
                   for index, case in enumerate(cases)}
        manifest["case_order_offsets"] = offsets
        write_json(directory / "manifest.json", manifest)
        for case in cases:
            if "generation_error" not in case:
                continue
            problem = {"case_id": case["case_id"], "phase": "generation", "error": case["generation_error"]}
            problems.append(problem)
            append_jsonl(directory / "failures.jsonl", problem)
        for case in anchors:
            reference = execute(case, "A", "sanity", 0, 0, None)
            for index, method in enumerate(METHODS[1:], 1):
                execute(case, method, "sanity", 0, index, reference)
        if problems:
            raise RuntimeError("Correctness/input gate failed; no performance measurement was started")
        for case in cases:
            print(f"Checking {case['case_id']}", flush=True)
            reference = execute(case, "A", "structural", 0, 0, None)
            before_errors = len(problems)
            for index, method in enumerate(METHODS[1:], 1):
                execute(case, method, "structural", 0, index, reference)
            if reference is None or len(problems) != before_errors:
                raise RuntimeError("Correctness/input gate failed for this case; prior records retained")
            print(f"Measuring {case['case_id']}", flush=True)
            for phase, count in (("warmup", config["warmups"]), ("timing", config["repetitions"])):
                for repetition in range(1, count + 1):
                    for index, method in enumerate(ORDERS[(repetition - 1 + offsets[case["case_id"]]) % len(ORDERS)]):
                        execute(case, method, phase, repetition, index, reference)
            if config["memory_pass"]:
                for index, method in enumerate(METHODS):
                    execute(case, method, "memory", 1, index, reference)
            reference = None  # Do not retain all large A reference trajectories.
        manifest["status"] = "failed" if problems else "completed"
    except BaseException as exc:
        manifest["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        problems.append({"phase": "invocation", "error": f"{type(exc).__name__}: {exc}",
                         "traceback": traceback.format_exc()})
        raise
    finally:
        manifest.update(finished_utc=now(), problems=problems)
        write_json(directory / "manifest.json", manifest)
        analyze(directory)
    if problems:
        raise RuntimeError(f"Benchmark has failures; evidence retained in {directory}")
    if plots:
        from .basiccode_plot import plot
        plot(directory)
    print(f"Saved {manifest['purpose']}: {directory}", flush=True)
    return directory


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, help="Unique ID; existing directories are refused")
    parser.add_argument("--config", type=Path, help="Committed config under this repository")
    parser.add_argument("--output-root", type=Path, default=ROOT / "results/basiccode/runs")
    parser.add_argument("--smoke", action="store_true", help="Tiny validation; not performance evidence")
    parser.add_argument("--no-plots", action="store_true", help="Generate figures separately later")
    args = parser.parse_args(argv)
    if args.smoke and args.config:
        parser.error("--smoke uses the fixed tiny config; omit --config")
    config = args.config or ROOT / ("configs/basiccode_smoke_v1.json" if args.smoke
                                  else "configs/basiccode_large_v1.json")
    try:
        run(config, args.output_root, args.run_id, smoke=args.smoke, plots=not args.no_plots)
    except KeyboardInterrupt:
        print("Interrupted; partial evidence retained. Use a new run ID next time.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
