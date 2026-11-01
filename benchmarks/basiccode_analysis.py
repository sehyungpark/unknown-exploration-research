"""Rebuild summaries/CSV from immutable raw records without rerunning exploration."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import itertools
import json
import math
from pathlib import Path
import random
from statistics import median

from .basiccode_runner import METHODS, ORDERS, VERSION, digest, write_json

BOOTSTRAP_SEED = 20261102
BOOTSTRAP_RESAMPLES = 2000
PAIRS = (("A/B", "A", "B"), ("A/C*", "A", "C*"), ("B/C*", "B", "C*"))


def quantile(values, probability):
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower, upper = math.floor(position), math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def geometric_mean(values):
    if not values or any(v is None for v in values):
        return None
    if any(v == 0 for v in values):
        return 0.0
    return math.exp(sum(math.log(v) for v in values) / len(values))


def estimate(values):
    """Maps are the resampling units; repetitions are reduced to map medians."""
    mean = geometric_mean(values)
    if mean is None:
        return {"value": None, "ci95": None, "n_maps": len(values)}
    rng = random.Random(BOOTSTRAP_SEED)
    samples = [geometric_mean([rng.choice(values) for _ in values])
               for _ in range(BOOTSTRAP_RESAMPLES)]
    return {"value": mean, "ci95": [quantile(samples, 0.025), quantile(samples, 0.975)],
            "n_maps": len(values)}


def read_records(path):
    records, errors = [], []
    if not path.exists():
        return [], ["records.jsonl is missing"]
    with path.open(encoding="utf-8") as stream:
        for index, line in enumerate(stream, 1):
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("Record is not an object")
                if "outcome" in record:
                    record["_outcome_hash_from_raw"] = digest(record.pop("outcome"))
                records.append(record)
            except (ValueError, TypeError) as exc:
                errors.append(f"Invalid raw record at line {index}: {exc}")
    return records, errors


def export_csv(path, rows):
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def analyze(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    config = manifest["config"]
    records, issues = read_records(directory / "records.jsonl")
    maps_path = directory / "maps.json"
    dataset = json.loads(maps_path.read_text(encoding="utf-8")) if maps_path.exists() else {"benchmark": [], "sanity": []}
    cases = dataset["benchmark"]
    all_cases = dataset["sanity"] + cases
    if manifest["status"] != "completed" or manifest.get("problems"):
        issues.append(f"Invocation status is {manifest['status']}")
    if manifest["version"] != VERSION or digest(config) != manifest["config_hash"]:
        issues.append("Manifest config/version mismatch")
    expected_ids = {f"n{size}-p{rate}-seed{seed}" for size, rate, seed in
                    itertools.product(config["sizes"], config["obstacle_rates"], config["seeds"])}
    if {case["case_id"] for case in cases} != expected_ids or len(cases) != len(expected_ids):
        issues.append("Saved maps do not match the requested config")
    if len(dataset["sanity"]) != 7:
        issues.append("Seven sanity families are required")
    expected = set()
    case_by_id = {case["case_id"]: case for case in all_cases}
    for case in all_cases:
        if "generation_error" in case:
            issues.append(f"Map generation failed: {case['case_id']}")
            continue
        if digest(case["truth"]) != case["map_hash"]:
            issues.append(f"Map hash mismatch: {case['case_id']}")
        phases = [("sanity", 0)] if case["kind"] == "sanity" else (
            [("structural", 0)] + [("warmup", n) for n in range(1, config["warmups"] + 1)]
            + [("timing", n) for n in range(1, config["repetitions"] + 1)]
            + ([("memory", 1)] if config["memory_pass"] else []))
        expected.update((case["case_id"], method, phase, rep)
                        for method in METHODS for phase, rep in phases)
    counts = Counter((r.get("case_id"), r.get("method"), r.get("phase"), r.get("repetition")) for r in records)
    if set(counts) != expected or any(count != 1 for count in counts.values()):
        issues.append("Missing, extra or duplicate raw records; partial data cannot form a valid comparison")
    lookup = {(r.get("case_id"), r.get("method"), r.get("phase"), r.get("repetition")): r for r in records}
    for record in records:
        case = case_by_id.get(record.get("case_id"))
        if case is None or not record.get("ok"):
            issues.append(f"Failed/unknown record: {record.get('case_id')} {record.get('method')} {record.get('phase')}")
            continue
        for key in ("map_hash", "size", "seed", "obstacle_rate", "sensor_range", "kind"):
            if record.get(key) != case.get(key):
                issues.append(f"Record input mismatch: {case['case_id']} {key}")
        phase = record["phase"]
        reference_phase = "sanity" if case["kind"] == "sanity" else "structural"
        reference = lookup.get((case["case_id"], "A", reference_phase, 0), {})
        if record.get("outcome_hash") != reference.get("outcome_hash"):
            issues.append(f"Outcome mismatch: {case['case_id']} {record['method']} {phase}")
        full_outcome_required = manifest.get("outcome_storage") != "a_reference_only_v1" or record["method"] == "A"
        if phase in ("sanity", "structural") and full_outcome_required:
            if record.get("_outcome_hash_from_raw") != record.get("outcome_hash"):
                issues.append(f"Saved outcome hash mismatch: {case['case_id']}")
        if phase in ("timing", "warmup"):
            offset = manifest.get("case_order_offsets", {}).get(case["case_id"], 0)
            order = ORDERS[(record["repetition"] - 1 + offset) % len(ORDERS)]
            if record.get("order_index") != order.index(record["method"]):
                issues.append("Recorded execution order does not match the protocol")
            for field in ("planner_ns", "episode_ns"):
                value = record.get(field)
                if type(value) is not int or value < 0:
                    issues.append(f"Invalid {field}: {case['case_id']}")
            if (type(record.get("planner_ns")) is int and type(record.get("episode_ns")) is int
                    and record["planner_ns"] > record["episode_ns"]):
                issues.append("Planner time exceeds episode time")
        if phase in ("structural", "sanity") and (type(record.get("exact_evaluations")) is not int or record["exact_evaluations"] < 0):
            issues.append("Invalid exact evaluation count")
        if phase == "memory" and (type(record.get("python_peak_bytes")) is not int or record["python_peak_bytes"] < 0):
            issues.append("Invalid memory measurement")
    # Export failed and successful records alike; detailed traces remain in JSONL.
    export_csv(directory / "records.csv", [{k: v for k, v in r.items() if k not in ("outcome", "traceback") and not k.startswith("_")} for r in records])
    summary = {"version": VERSION, "run_id": manifest["run_id"], "purpose": manifest["purpose"],
               "valid": not issues, "issues": sorted(set(issues)), "record_count": len(records),
               "requested_maps": len(expected_ids), "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
               "bootstrap_seed": BOOTSTRAP_SEED, "per_case": [], "groups": [],
               "note": "Map medians; map-level paired bootstrap. Zero/undefined ratios are retained, never silently dropped."}
    if not issues:
        flat = []
        for case in cases:
            item = {key: case[key] for key in ("case_id", "size", "obstacle_rate", "seed", "sensor_range", "map_hash")}
            item["generator"] = case.get("generation", {}).get("generator", "legacy_rejection_v1")
            item["realized_density"] = case.get("generation", {}).get("realized_density")
            item["methods"] = {}
            for method in METHODS:
                structural = lookup[(case["case_id"], method, "structural", 0)]
                times = [lookup[(case["case_id"], method, "timing", n)] for n in range(1, config["repetitions"] + 1)]
                data = {"exact_evaluations": structural["exact_evaluations"], "termination": structural["termination"],
                        "remaining_unknown": structural["remaining_unknown"], "total_cost": structural["total_cost"],
                        "python_peak_bytes": lookup[(case["case_id"], method, "memory", 1)]["python_peak_bytes"] if config["memory_pass"] else None}
                for field in ("planner_ns", "episode_ns"):
                    values = [r[field] for r in times]
                    data[field] = {"median": median(values), "min": min(values), "max": max(values),
                                   "q1": quantile(values, 0.25), "q3": quantile(values, 0.75)}
                item["methods"][method] = data
                flat.append({**{k: v for k, v in item.items() if k != "methods"}, "method": method,
                             **{k: v for k, v in data.items() if not isinstance(v, dict)},
                             **{f"{field}_{stat}": value for field in ("planner_ns", "episode_ns") for stat, value in data[field].items()}})
            summary["per_case"].append(item)
        for size, rate in itertools.product(config["sizes"], config["obstacle_rates"]):
            members = [r for r in summary["per_case"] if r["size"] == size and r["obstacle_rate"] == rate]
            group = {"size": size, "obstacle_rate": rate, "n_maps": len(members), "methods": {}, "speedups": {}}
            for method in METHODS:
                group["methods"][method] = {
                    field: estimate([m["methods"][method][field]["median"] for m in members])
                    for field in ("planner_ns", "episode_ns")}
                for field in ("exact_evaluations", "python_peak_bytes"):
                    group["methods"][method][field] = estimate([m["methods"][method][field] for m in members])
            for label, numerator, denominator in PAIRS:
                group["speedups"][label] = {}
                for field in ("planner_ns", "episode_ns"):
                    values = []
                    undefined = []
                    for m in members:
                        top, bottom = (m["methods"][method][field]["median"] for method in (numerator, denominator))
                        values.append(top / bottom if top > 0 and bottom > 0 else None)
                        if values[-1] is None:
                            undefined.append(m["case_id"])
                    group["speedups"][label][field] = {**estimate(values), "undefined_cases": undefined}
            summary["groups"].append(group)
        export_csv(directory / "summary.csv", flat)
    else:
        # A stale valid CSV must not survive reanalysis of invalid raw data.
        export_csv(directory / "summary.csv", [])
    write_json(directory / "summary.json", summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    summary = analyze(args.directory)
    print(f"valid={summary['valid']}; records={summary['record_count']}")
    return 0 if summary["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
