"""Run the frozen exploratory protocol; never edits historical evidence."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import platform
import random
from statistics import median
import subprocess
from time import perf_counter_ns

from src.environment import GroundTruthGrid
from src.environment.fixtures import MapFixture, deterministic_fixtures
from src.evaluation import ExplorationSimulator
from src.evaluation.random_dataset import generate_ground_truth, select_start
from src.mapping import BeliefGrid
from src.planning import ChangeAwareStarNBV, StaleScalarLazyNBV, PlanStatus
from src.planning import change_aware_star_nbv as star_module
from src.planning.bitmask import coords_to_mask
from src.planning.motion import legal_neighbors
from src.sensing import optimistic_visible_unknown_cells, physical_scan
from src.sensing.supercover import supercover_line
from src.utils import BeliefState, TruthState, ground_truth_hash

VERSION = "extension-pilot-20260929-v1"
METHODS = ("B", "S*", "C*", "CERT")
TIMING_IDS = ("open", "maze_like", "rooms-20-door-1", "rooms-30-door-3",
              "random-20-0.1-1", "random-30-0.3-1")
ORDERS = tuple(METHODS[i:] + METHODS[:i] for i in range(4))
CANONICAL = optimistic_visible_unknown_cells


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def append_json(path, value):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")


def jsonl(path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            yield json.loads(line)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def historical_audit(output):
    from src.evaluation import experiment_1_analysis as e1
    from src.evaluation import experiment_2_analysis as e2
    report = {}
    for number, invocation in [(1, "experiment1-formal-20260917-001"), (2, "experiment2-formal-20260919-001")]:
        root = Path(f"results/experiment_{number}/runs/{invocation}")
        stored = json.loads((root / "summary.json").read_text())
        hashes = {p.name: digest(p) for p in root.iterdir() if p.is_file()}
        manifest = json.loads((root / "manifest.json").read_text())
        if number == 1:
            episodes = list(jsonl(root / "episodes.jsonl"))
            work = e1.aggregate_work(episodes)
            timing = e1.summarize_timing(list(jsonl(root / "timing_repetitions.jsonl")))
            counts = Counter()
            for record in jsonl(root / "snapshots.jsonl"):
                counts["snapshots"] += 1
                counts["invalid"] += record["correctness_valid"] is False
            primary = [r for r in episodes if r["phase"] == "primary_structural"]
            assert len(primary) == 81 and len({r["map_id"] for r in primary}) == 27
            assert counts["invalid"] == 0 and all(r["correctness_valid"] for r in primary)
            classification = e1.classify_decision(
                primary_correctness_valid=True, b_work=work["overall"]["B"], c_work=work["overall"]["C"],
                c_over_b_interval=timing["comparisons"]["C/B"]["bootstrap_interval_95"], invocation_complete=True)
            assert work == stored["work"] and timing == stored["timing"]
            assert classification == stored["decision"]["classification"]
            details = {"snapshot_flags": dict(counts), "classification": classification,
                       "work": work["overall"], "timing_comparisons": timing["comparisons"]}
        else:
            structural = list(jsonl(root / "structural.jsonl"))
            rebuilt = e2.build_summary(structural, list(jsonl(root / "timing_repetitions.jsonl")),
                                       list(jsonl(root / "memory.jsonl")), list(jsonl(root / "audit.jsonl")))
            assert rebuilt == stored
            assert all(r["correctness_valid"] for r in structural)
            details = {"all_summary_fields_identical": True, "classification": rebuilt["decision"]["classification"],
                       "work": rebuilt["work"], "timing_comparisons": rebuilt["timing"]["comparisons"],
                       "structural_records": len(structural)}
        report[str(number)] = {"source": str(root), "hashes": hashes, "manifest": manifest, **details}
    write_json(output / "historical_audit.json", report)
    return report


class ScalarRangeStar(ChangeAwareStarNBV):
    def _fresh_change_bound(self, candidate):
        return min(self._cache[candidate].stale_upper_gain, self._range_upper_gain(candidate))


class VisibilityAdapter:
    def __init__(self, certify=False, verify=False):
        self.certify, self.verify = certify, verify
        self.cache = {}
        self.occupied = 0
        self.counters = Counter()

    def observe(self, belief, delta):
        cells = belief.iter_coords() if delta is None else delta
        self.occupied |= coords_to_mask((x for x in cells if belief.state(x) is BeliefState.OCCUPIED), belief.shape)

    def __call__(self, belief, candidate, sensor_range):
        old = self.cache.get(candidate)
        if self.certify and old is not None:
            visible, support, old_occupied = old
            if not ((self.occupied & ~old_occupied) & support):
                answer = frozenset(x for x in visible if belief.state(x) is BeliefState.UNKNOWN)
                self.counters["certificate_hits"] += 1
                if self.verify:
                    self.counters["audit_visibility_calls"] += 1
                    assert answer == CANONICAL(belief, candidate, sensor_range), (candidate, "certificate mismatch")
                self.cache[candidate] = (answer, support, self.occupied)
                return answer
            self.counters["certificate_invalidated"] += 1
        self.counters["canonical_visibility_calls"] += 1
        answer = CANONICAL(belief, candidate, sensor_range)
        if self.certify:
            interiors = set()
            for target in answer:
                line = supercover_line(candidate, target)
                self.counters["dependency_build_rays"] += 1
                interiors.update(line[1:-1])
            self.cache[candidate] = (answer, coords_to_mask(interiors, belief.shape), self.occupied)
        return answer

    @contextmanager
    def forwarding(self):
        previous = star_module.optimistic_visible_unknown_cells
        star_module.optimistic_visible_unknown_cells = self
        try:
            yield
        finally:
            star_module.optimistic_visible_unknown_cells = previous


def rooms(size, width):
    cells = [["." for _ in range(size)] for _ in range(size)]
    middle = size // 2
    for i in range(size):
        cells[0][i] = cells[-1][i] = cells[i][0] = cells[i][-1] = "#"
        cells[middle][i] = cells[i][middle] = "#"
    for center in (size // 4, 3 * size // 4):
        for offset in range(-(width // 2), width // 2 + 1):
            cells[middle][center + offset] = cells[center + offset][middle] = "."
    return MapFixture(f"rooms-{size}-door-{width}", GroundTruthGrid.from_ascii("".join(row) for row in cells), (2, 2))


def workload(output):
    maps = [(f, "fixture", None, None) for f in deterministic_fixtures()]
    rng = random.Random(20260929)
    for size in (20, 30):
        for p in (0.1, 0.3):
            for rep in (1, 2):
                seed = rng.getrandbits(63)
                grid = generate_ground_truth(size, p, seed)
                start, _, _ = select_start(grid)
                if start is None:
                    raise RuntimeError(f"retained generation failure: {size}, {p}, {seed}")
                maps.append((MapFixture(f"random-{size}-{p}-{rep}", grid, start), "bernoulli", seed, p))
    maps.extend((rooms(size, width), "rooms", None, None) for size in (20, 30, 40) for width in (1, 3))
    manifest = []
    for fixture, family, seed, p in maps:
        grid = fixture.ground_truth
        ascii_rows = ["".join("." if grid.state((r, c)) is TruthState.FREE else "#" for c in range(grid.width)) for r in range(grid.height)]
        manifest.append({"id": fixture.name, "family": family, "seed": seed, "p": p,
                         "start": fixture.start, "shape": grid.shape, "map_hash": ground_truth_hash(grid), "ascii": ascii_rows})
    write_json(output / "maps.json", manifest)
    return maps


def property_checks(output):
    candidate = (0, 0)
    others = [(r, c) for r in range(3) for c in range(3) if (r, c) != candidate]
    counts = Counter()
    example = None
    for states in itertools.product(tuple(BeliefState), repeat=8):
        belief = BeliefGrid.unknown(3, 3)
        belief.apply_observations({candidate: TruthState.FREE})
        observations = {x: TruthState.FREE if state is BeliefState.FREE else TruthState.OCCUPIED
                        for x, state in zip(others, states) if state is not BeliefState.UNKNOWN}
        belief.apply_observations(observations)
        visible = CANONICAL(belief, candidate, 3)
        support = set(x for target in visible for x in supercover_line(candidate, target)[1:-1])
        counts["beliefs"] += 1
        for cell, state in zip(others, states):
            if state is not BeliefState.UNKNOWN:
                continue
            for revelation in (TruthState.FREE, TruthState.OCCUPIED):
                updated = BeliefGrid.unknown(3, 3)
                updated.apply_observations({candidate: TruthState.FREE, **observations, cell: revelation})
                retained = visible - {cell}
                exact = CANONICAL(updated, candidate, 3)
                assert exact <= retained
                certified = revelation is TruthState.FREE or cell not in support
                if certified:
                    assert exact == retained, (states, cell, revelation)
                    counts["certified_transitions"] += 1
                if exact < retained:
                    counts["strict_occlusion_slack"] += 1
                    if example is None:
                        example = {"states": [state.name for state in states], "cell": cell,
                                   "cached_intersection": sorted(retained), "exact": sorted(exact)}
                counts["transitions"] += 1
    result = {**counts, "strict_slack_example": example, "failures": 0}
    write_json(output / "certificate_properties.json", result)
    return result


def planner_for(method):
    if method == "B":
        return StaleScalarLazyNBV(8)
    return ScalarRangeStar(8) if method == "S*" else ChangeAwareStarNBV(8)


def plan(method, planner, adapter, simulator, delta):
    if method == "B":
        return planner.plan(simulator.world.belief, simulator.world.robot)
    with adapter.forwarding():
        return planner.plan(simulator.world.belief, simulator.world.robot, newly_known=delta)


def same(a, b):
    return all(getattr(a, field) == getattr(b, field) for field in
               ("status", "selected_candidate", "selected_gain", "selected_distance", "selected_score", "selected_path"))


def advance(simulator, path):
    assert path[0] == simulator.world.robot
    for source, target in zip(path, path[1:]):
        assert target in dict(legal_neighbors(simulator.world.belief, source))
    simulator.world.robot = path[-1]
    return simulator.world.belief.apply_observations(physical_scan(simulator.world.ground_truth, simulator.world.robot, 8))


def limit(fixture):
    return max(128, 2 * sum(fixture.ground_truth.state(x) is TruthState.FREE for x in fixture.ground_truth.iter_coords()))


def seqhash(sequence):
    return hashlib.sha256(("\n".join(json.dumps(x) for x in sequence) + "\n").encode()).hexdigest()


def structural(fixture, output):
    simulator = ExplorationSimulator(fixture.ground_truth, fixture.start, 8)
    planners = {method: planner_for(method) for method in METHODS}
    adapters = {method: VisibilityAdapter(method == "CERT", True) for method in METHODS}
    totals = {method: Counter() for method in ("A",) + METHODS}
    delta = None
    sequence = []
    for cycle in range(limit(fixture)):
        oracle = simulator.plan()
        totals["A"]["exact_evaluations"] += oracle.exact_gain_evaluations
        records = {}
        for method in METHODS:
            adapter = adapters[method]
            adapter.observe(simulator.world.belief, delta)
            result = plan(method, planners[method], adapter, simulator, delta)
            if not same(oracle, result):
                write_json(output / "failure.json", {"map": fixture.name, "cycle": cycle, "method": method,
                           "oracle": repr(oracle), "result": repr(result), "belief": repr(simulator.world.belief.snapshot())})
                raise AssertionError(f"{fixture.name}, cycle {cycle}, {method}: oracle mismatch")
            totals[method]["exact_evaluations"] += result.exact_gain_evaluations
            if method != "B":
                totals[method].update(asdict(result.counters))
            records[method] = {"target": result.selected_candidate, "exact_evaluations": result.exact_gain_evaluations}
        sequence.append(oracle.selected_candidate)
        append_json(output / "snapshots.jsonl", {"map": fixture.name, "cycle": cycle, "status": oracle.status.name,
                    "target": oracle.selected_candidate, "correctness_valid": True, "methods": records})
        if oracle.status is PlanStatus.EXPLORATION_COMPLETE:
            summary = {"map": fixture.name, "snapshots": len(sequence), "sequence_hash": seqhash(sequence),
                       "correctness_valid": True, "methods": {m: dict(totals[m]) for m in totals},
                       "visibility_adapters": {m: dict(adapters[m].counters) for m in METHODS}}
            append_json(output / "structural.jsonl", summary)
            return summary
        delta = advance(simulator, oracle.selected_path)
    raise RuntimeError(f"cycle limit: {fixture.name}")


def episode(method, fixture, reference_hash):
    simulator = ExplorationSimulator(fixture.ground_truth, fixture.start, 8)
    planner = planner_for(method)
    adapter = VisibilityAdapter(method == "CERT", False)
    delta = None
    sequence, elapsed = [], 0
    for _ in range(limit(fixture)):
        started = perf_counter_ns()
        if method == "CERT":
            adapter.observe(simulator.world.belief, delta)
            result = plan(method, planner, adapter, simulator, delta)
        elif method == "B":
            result = planner.plan(simulator.world.belief, simulator.world.robot)
        else:
            result = planner.plan(simulator.world.belief, simulator.world.robot, newly_known=delta)
        elapsed += perf_counter_ns() - started
        sequence.append(result.selected_candidate)
        if result.status is PlanStatus.EXPLORATION_COMPLETE:
            assert seqhash(sequence) == reference_hash
            return elapsed, dict(adapter.counters)
        delta = advance(simulator, result.selected_path)
    raise RuntimeError(f"timing cycle limit: {fixture.name}, {method}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    phase = parser.add_mutually_exclusive_group()
    phase.add_argument("--structural-only", action="store_true")
    phase.add_argument("--resume-timing", action="store_true")
    args = parser.parse_args()
    output = Path(args.output)
    if not args.resume_timing:
        output.mkdir(parents=True, exist_ok=False)
    manifest = {"version": VERSION, "status": "RUNNING", "started": datetime.now(timezone.utc).isoformat(),
                "python": platform.python_version(), "platform": platform.platform(),
                "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                "script_sha256": digest(Path(__file__)), "protocol_sha256": digest(Path("docs/EXTENSION_PILOT_20260929_PROTOCOL.md")),
                "timing_orders": ORDERS, "sensor_range": 8, "timing_ids": TIMING_IDS}
    if args.resume_timing:
        saved = json.loads((output / "manifest.json").read_text())
        assert saved["status"] == "STRUCTURAL_PASS" and not (output / "timing.jsonl").exists()
        structural_source = output / "structural_source.py"
        assert digest(structural_source) == saved["script_sha256"]
        timing_hash, timing_protocol_hash = manifest["script_sha256"], manifest["protocol_sha256"]
        manifest = saved
        manifest["status"] = "RUNNING_TIMING"
        manifest["timing_script_sha256"] = timing_hash
        manifest["timing_protocol_sha256"] = timing_protocol_hash
    write_json(output / "manifest.json", manifest)
    try:
        if args.resume_timing:
            maps = [(MapFixture(r["id"], GroundTruthGrid.from_ascii(r["ascii"]), tuple(r["start"])), r["family"], r["seed"], r["p"])
                    for r in json.loads((output / "maps.json").read_text())]
            properties = json.loads((output / "certificate_properties.json").read_text())
            results = {r["map"]: r for r in jsonl(output / "structural.jsonl")}
        else:
            maps = workload(output)
            historical_audit(output)
            properties = property_checks(output)
            results = {}
            for fixture, _, _, _ in maps:
                results[fixture.name] = structural(fixture, output)
                print(f"structural PASS {fixture.name}", flush=True)
        if args.structural_only:
            manifest["status"] = "STRUCTURAL_PASS"
            return
        timings = []
        fixtures = {f.name: f for f, _, _, _ in maps}
        for map_id in TIMING_IDS:
            fixture = fixtures[map_id]
            for rep, order in enumerate((METHODS,) + ORDERS):
                for position, method in enumerate(order):
                    elapsed, counters = episode(method, fixture, results[map_id]["sequence_hash"])
                    record = {"map": map_id, "method": method, "repetition": rep, "timed": rep > 0,
                              "position": position, "order": order, "planner_ns": elapsed, "counters": counters, "correctness_valid": True}
                    append_json(output / "timing.jsonl", record)
                    timings.append(record)
            print(f"timing PASS {map_id}", flush=True)
        summary = {"properties": properties, "maps": len(maps), "snapshots": sum(r["snapshots"] for r in results.values()),
                   "correctness_failures": 0, "timing_medians_ns": {}, "exploratory_only": True}
        for map_id in TIMING_IDS:
            medians = {m: median(r["planner_ns"] for r in timings if r["map"] == map_id and r["method"] == m and r["timed"]) for m in METHODS}
            summary["timing_medians_ns"][map_id] = medians
        write_json(output / "summary.json", summary)
        manifest["status"] = "PASS"
    except Exception as exc:
        manifest.update(status="FAILED", failure=repr(exc))
        write_json(output / "failure_exception.json", {"type": type(exc).__name__, "message": str(exc)})
        raise
    finally:
        manifest["completed"] = datetime.now(timezone.utc).isoformat()
        write_json(output / "manifest.json", manifest)


if __name__ == "__main__":
    main()
