"""Compact preregistered analysis for Experiment 2.

Experiment 2 preserves Experiment 1's map-level timing analysis and ordered
correctness/work/timing decision logic.  The primary optimized method is C*;
Algorithm C is retained as a historical implementation baseline.
"""

from __future__ import annotations

import math
import random
from statistics import median
from typing import Any, Mapping, Sequence

BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20260919
METHODS = ("A", "B", "C", "C*")
WORK_FIELDS = (
    "exact_gain_evaluation_count",
    "visibility_ray_count",
    "visibility_supercover_cell_count",
    "visibility_interior_probe_count",
)
VISIBILITY_WORK_FIELDS = WORK_FIELDS[1:]
DECISIONS = frozenset({"GO", "MODIFY", "DROP", "CORRECTNESS_REOPENED"})


def safe_ratio(numerator: int | float, denominator: int | float) -> float | None:
    return None if denominator == 0 else numerator / denominator


def linear_quantile(values: Sequence[int | float], probability: float) -> float:
    if not values:
        raise ValueError("quantile requires at least one value")
    if not 0 <= probability <= 1:
        raise ValueError("probability must be in [0,1]")
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def summarize_six_timings(values: Sequence[int]) -> dict[str, int | float]:
    if len(values) != 6:
        raise ValueError("primary timing requires exactly six repetitions")
    ordered = sorted(values)
    return {
        "median": median(values),
        "minimum": min(values),
        "maximum": max(values),
        "q1": linear_quantile(ordered, 0.25),
        "q3": linear_quantile(ordered, 0.75),
        "iqr": linear_quantile(ordered, 0.75) - linear_quantile(ordered, 0.25),
    }


def paired_bootstrap_interval(
    ratios: Sequence[float],
    *,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[float, float]:
    if not ratios or any(value <= 0 or not math.isfinite(value) for value in ratios):
        raise ValueError("bootstrap ratios must be finite and positive")
    logs = [math.log(value) for value in ratios]
    rng = random.Random(seed)
    samples = []
    for _ in range(resamples):
        samples.append(
            math.exp(sum(rng.choice(logs) for _ in logs) / len(logs))
        )
    return linear_quantile(samples, 0.025), linear_quantile(samples, 0.975)


def summarize_timing(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    timed = [record for record in records if record["timed"]]
    map_ids = sorted({record["map_id"] for record in timed})
    per_map_method: dict[str, dict[str, Any]] = {}
    complete = True
    for map_id in map_ids:
        per_map_method[map_id] = {}
        for method in METHODS:
            values = [
                int(record["planner_wall_time_ns"])
                for record in timed
                if record["map_id"] == map_id
                and record["method"] == method
                and record["correctness_valid"]
            ]
            reps = {
                int(record["repetition_index"])
                for record in timed
                if record["map_id"] == map_id
                and record["method"] == method
                and record["correctness_valid"]
            }
            if len(values) != 6 or reps != set(range(1, 7)):
                complete = False
                continue
            per_map_method[map_id][method] = summarize_six_timings(values)

    comparisons: dict[str, Any] = {}
    pairs = (
        ("B/A", "B", "A"),
        ("C/B", "C", "B"),
        ("C*/B", "C*", "B"),
        ("C*/C", "C*", "C"),
        ("C*/A", "C*", "A"),
    )
    if complete and map_ids:
        for label, numerator, denominator in pairs:
            ratios = {
                map_id: safe_ratio(
                    per_map_method[map_id][numerator]["median"],
                    per_map_method[map_id][denominator]["median"],
                )
                for map_id in map_ids
            }
            finite = [float(value) for value in ratios.values() if value is not None]
            if len(finite) != len(map_ids) or any(value <= 0 for value in finite):
                complete = False
                comparisons[label] = {"per_map_ratios": ratios}
                continue
            lower, upper = paired_bootstrap_interval(finite)
            comparisons[label] = {
                "per_map_ratios": ratios,
                "geometric_mean": math.exp(
                    sum(math.log(value) for value in finite) / len(finite)
                ),
                "median_paired_ratio": median(finite),
                "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
                "bootstrap_seed": BOOTSTRAP_SEED,
                "bootstrap_interval_95": [lower, upper],
            }
    return {
        "complete": complete and bool(map_ids),
        "per_map_method": per_map_method,
        "comparisons": comparisons,
    }


def aggregate_primary_work(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    primary = [
        record for record in records
        if record["phase"] == "primary_structural"
        and record["correctness_valid"]
    ]
    overall = {
        method: {
            field: sum(
                int(record[field])
                for record in primary
                if record["method"] == method
            )
            for field in WORK_FIELDS
        }
        for method in METHODS
    }
    ratios = {}
    for label, numerator, denominator in (
        ("B/A", "B", "A"),
        ("C/B", "C", "B"),
        ("C*/B", "C*", "B"),
        ("C*/C", "C*", "C"),
        ("C*/A", "C*", "A"),
    ):
        ratios[label] = {
            field: safe_ratio(overall[numerator][field], overall[denominator][field])
            for field in WORK_FIELDS
        }
    return {"overall": overall, "overall_ratios": ratios}


def classify_decision(
    *,
    correctness_valid: bool,
    cstar_work: Mapping[str, int],
    b_work: Mapping[str, int],
    cstar_over_b_interval: Sequence[float] | None,
    complete: bool,
) -> str | None:
    if not correctness_valid:
        return "CORRECTNESS_REOPENED"
    if not complete:
        return None
    if not all(cstar_work[field] < b_work[field] for field in VISIBILITY_WORK_FIELDS):
        return "DROP"
    if cstar_over_b_interval is None or len(cstar_over_b_interval) != 2:
        raise ValueError("complete Experiment 2 requires C*/B timing interval")
    lower, upper = map(float, cstar_over_b_interval)
    if upper < 1.0:
        return "GO"
    if lower <= 1.0 <= upper:
        return "MODIFY"
    if lower > 1.0:
        return "DROP"
    raise RuntimeError("unreachable timing classification")


def build_summary(
    structural_records: Sequence[Mapping[str, Any]],
    timing_records: Sequence[Mapping[str, Any]],
    memory_records: Sequence[Mapping[str, Any]],
    audit_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    work = aggregate_primary_work(structural_records)
    timing = summarize_timing(timing_records)
    primary = [record for record in structural_records if record["phase"] == "primary_structural"]
    groups: dict[str, set[str]] = {}
    correctness_valid = True
    for record in primary:
        groups.setdefault(str(record["map_id"]), set()).add(str(record["method"]))
        correctness_valid = correctness_valid and bool(record["correctness_valid"])
    structural_complete = (
        len(groups) == 27
        and all(methods == set(METHODS) for methods in groups.values())
        and len(primary) == 27 * len(METHODS)
    )
    timing_complete = timing["complete"] and len(timing["per_map_method"]) == 9
    complete = structural_complete and timing_complete
    interval = None
    if timing_complete:
        interval = timing["comparisons"]["C*/B"]["bootstrap_interval_95"]
    decision = classify_decision(
        correctness_valid=correctness_valid,
        cstar_work=work["overall"]["C*"],
        b_work=work["overall"]["B"],
        cstar_over_b_interval=interval,
        complete=complete,
    )
    return {
        "correctness": {
            "primary_valid": correctness_valid,
            "primary_structural_complete": structural_complete,
            "primary_timing_complete": timing_complete,
        },
        "work": work,
        "timing": timing,
        "memory": list(memory_records),
        "audit": list(audit_records),
        "decision": {
            "classification": decision,
            "available": decision is not None,
            "primary_comparison": "C*/B",
            "cstar_vs_c_is_descriptive": True,
        },
    }


__all__ = [
    "BOOTSTRAP_RESAMPLES", "BOOTSTRAP_SEED", "DECISIONS", "METHODS",
    "VISIBILITY_WORK_FIELDS", "WORK_FIELDS", "aggregate_primary_work",
    "build_summary", "classify_decision", "paired_bootstrap_interval",
    "safe_ratio", "summarize_six_timings", "summarize_timing",
]
