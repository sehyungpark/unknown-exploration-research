"""Deterministic preregistered Experiment 1 analysis on retained raw records."""

from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import math
import random
from statistics import median
from typing import Any, Iterable, Mapping, Sequence


BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20260916
WORK_FIELDS = (
    "exact_gain_evaluation_count",
    "visibility_ray_count",
    "visibility_supercover_cell_count",
    "visibility_interior_probe_count",
)
VISIBILITY_WORK_FIELDS = WORK_FIELDS[1:]
DECISIONS = frozenset({"GO", "MODIFY", "DROP", "CORRECTNESS_REOPENED"})


def safe_ratio(numerator: int | float, denominator: int | float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def linear_quantile(values: Sequence[int | float], probability: float) -> float:
    """Return the frozen h=(n-1)p linearly interpolated quantile."""

    if not values:
        raise ValueError("quantile requires at least one value")
    if not 0 <= probability <= 1:
        raise ValueError("probability must be in [0, 1]")
    ordered = sorted(float(value) for value in values)
    if any(not math.isfinite(value) for value in ordered):
        raise ValueError("quantile values must be finite")
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def nearest_rank_percentile(
    values: Sequence[int | float], probability: float = 0.95
) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    if not 0 < probability <= 1:
        raise ValueError("probability must be in (0, 1]")
    ordered = sorted(float(value) for value in values)
    rank = max(1, math.ceil(probability * len(ordered)))
    return ordered[rank - 1]


def canonical_path_hash(path: Sequence[Sequence[int] | tuple[int, int]]) -> str:
    text = "".join(f"[{int(coord[0])},{int(coord[1])}]\n" for coord in path)
    return sha256(text.encode("utf-8")).hexdigest()


def canonical_sequence_hash(
    sequence: Sequence[Sequence[int] | tuple[int, int] | None],
) -> str:
    lines = [
        "STOP" if value is None else f"[{int(value[0])},{int(value[1])}]"
        for value in sequence
    ]
    return sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()


def _work_totals(records: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    totals = {field: 0 for field in WORK_FIELDS}
    for record in records:
        for field in WORK_FIELDS:
            value = record[field]
            if value is None:
                continue
            totals[field] += value
    return totals


def aggregate_work(
    episode_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    primary = [
        record
        for record in episode_records
        if record["phase"] == "primary_structural"
        and record["correctness_valid"] is True
    ]

    def grouped(key: str) -> dict[str, dict[str, dict[str, int]]]:
        buckets: dict[str, dict[str, list[Mapping[str, Any]]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for record in primary:
            buckets[str(record[key])][record["method"]].append(record)
        return {
            bucket: {
                method: _work_totals(method_records)
                for method, method_records in sorted(methods.items())
            }
            for bucket, methods in sorted(buckets.items())
        }

    per_map = grouped("map_id")
    per_size = grouped("size")
    per_density = grouped("density_label")
    overall_by_method = {
        method: _work_totals(
            record for record in primary if record["method"] == method
        )
        for method in ("A", "B", "C")
    }
    ratios: dict[str, dict[str, float | None]] = {}
    zero_denominator_counts: dict[str, dict[str, int]] = {}
    for comparison, numerator, denominator in (
        ("B/A", "B", "A"),
        ("C/A", "C", "A"),
        ("C/B", "C", "B"),
    ):
        ratios[comparison] = {
            field: safe_ratio(
                overall_by_method[numerator][field],
                overall_by_method[denominator][field],
            )
            for field in WORK_FIELDS
        }
        zero_denominator_counts[comparison] = {
            field: int(overall_by_method[denominator][field] == 0)
            for field in WORK_FIELDS
        }
    return {
        "per_map": per_map,
        "per_size": per_size,
        "per_density": per_density,
        "overall": overall_by_method,
        "overall_ratios": ratios,
        "zero_denominator_counts": zero_denominator_counts,
    }


def aggregate_bound_slack(
    snapshot_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    observations: dict[str, list[Mapping[str, Any]]] = {"B": [], "C": []}
    for record in snapshot_records:
        if record["phase"] != "primary_structural" or not record[
            "correctness_valid"
        ]:
            continue
        for measurement in record["bound_measurements"]:
            observations[measurement["method"]].append(measurement)

    def summarize(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        if not items:
            return {
                "observation_count": 0,
                "mean_absolute_slack": None,
                "median_absolute_slack": None,
                "p95_absolute_slack": None,
                "mean_normalized_slack": None,
                "median_normalized_slack": None,
                "p95_normalized_slack": None,
                "tight_bound_fraction": None,
            }
        absolute = [item["absolute_slack"] for item in items]
        normalized = [item["normalized_slack"] for item in items]
        return {
            "observation_count": len(items),
            "mean_absolute_slack": sum(absolute) / len(absolute),
            "median_absolute_slack": median(absolute),
            "p95_absolute_slack": nearest_rank_percentile(absolute),
            "mean_normalized_slack": sum(normalized) / len(normalized),
            "median_normalized_slack": median(normalized),
            "p95_normalized_slack": nearest_rank_percentile(normalized),
            "tight_bound_fraction": sum(item["tight"] for item in items) / len(items),
        }

    return {method: summarize(items) for method, items in observations.items()}


def summarize_six_timings(values: Sequence[int]) -> dict[str, int | float]:
    if len(values) != 6:
        raise ValueError("primary timing requires exactly six valid repetitions")
    if any(type(value) is not int or value < 0 for value in values):
        raise ValueError("timing values must be nonnegative integers")
    q1 = linear_quantile(values, 0.25)
    q3 = linear_quantile(values, 0.75)
    return {
        "median": median(values),
        "minimum": min(values),
        "maximum": max(values),
        "q1": q1,
        "q3": q3,
        "iqr": q3 - q1,
    }


def paired_bootstrap_interval(
    ratios: Sequence[float],
    *,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[float, float]:
    if not ratios or any(value <= 0 or not math.isfinite(value) for value in ratios):
        raise ValueError("bootstrap ratios must be finite and positive")
    if resamples != BOOTSTRAP_RESAMPLES or seed != BOOTSTRAP_SEED:
        raise ValueError("bootstrap configuration differs from preregistration")
    logs = [math.log(value) for value in ratios]
    rng = random.Random(seed)
    bootstrap = []
    for _ in range(resamples):
        sample_mean = sum(rng.choice(logs) for _ in logs) / len(logs)
        bootstrap.append(math.exp(sample_mean))
    return linear_quantile(bootstrap, 0.025), linear_quantile(bootstrap, 0.975)


def summarize_timing(
    timing_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    warmups = [record for record in timing_records if record["timed"] is False]
    timed = [
        record
        for record in timing_records
        if record["timed"] is True and record["correctness_valid"] is True
    ]
    buckets: dict[tuple[str, str], list[int]] = defaultdict(list)
    repetitions: dict[tuple[str, str], list[int]] = defaultdict(list)
    for record in timed:
        key = (record["map_id"], record["method"])
        buckets[key].append(
            record["episode_planner_wall_time_ns"]
        )
        repetitions[key].append(record["repetition_index"])
    timed_map_ids = sorted(
        {record["map_id"] for record in timing_records if record["timed"] is True}
    )
    expected_keys = {
        (map_id, method) for map_id in timed_map_ids for method in ("A", "B", "C")
    }
    incomplete = sorted(
        [
            list(key) for key in expected_keys
            if len(buckets.get(key, ())) != 6
            or set(repetitions.get(key, ())) != set(range(1, 7))
        ]
    )
    complete = bool(expected_keys) and not incomplete
    per_map_method: dict[str, dict[str, Any]] = defaultdict(dict)
    if complete:
        for (map_id, method), values in sorted(buckets.items()):
            per_map_method[map_id][method] = summarize_six_timings(values)

    comparisons: dict[str, Any] = {}
    undefined_ratio_counts: dict[str, int] = {}
    if complete:
        for label, numerator, denominator in (
            ("C/B", "C", "B"),
            ("B/A", "B", "A"),
            ("C/A", "C", "A"),
        ):
            ratios = [
                safe_ratio(
                    per_map_method[map_id][numerator]["median"],
                    per_map_method[map_id][denominator]["median"],
                )
                for map_id in sorted(per_map_method)
            ]
            undefined_ratio_counts[label] = sum(value is None for value in ratios)
            if any(value is None or value <= 0 for value in ratios):
                complete = False
                comparisons[label] = {
                    "per_map_ratios": dict(zip(sorted(per_map_method), ratios)),
                    "geometric_mean": None,
                    "median_paired_ratio": None,
                    "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
                    "bootstrap_seed": BOOTSTRAP_SEED,
                    "bootstrap_interval_95": None,
                }
                continue
            finite_ratios = [float(value) for value in ratios]
            lower, upper = paired_bootstrap_interval(finite_ratios)
            comparisons[label] = {
                "per_map_ratios": dict(zip(sorted(per_map_method), ratios)),
                "geometric_mean": math.exp(
                    sum(math.log(value) for value in finite_ratios)
                    / len(finite_ratios)
                ),
                "median_paired_ratio": median(finite_ratios),
                "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
                "bootstrap_seed": BOOTSTRAP_SEED,
                "bootstrap_interval_95": [lower, upper],
            }
    return {
        "warmup_record_count": len(warmups),
        "warmups_excluded": True,
        "complete": complete,
        "incomplete_map_methods": incomplete,
        "undefined_ratio_counts": undefined_ratio_counts,
        "per_map_method": dict(per_map_method),
        "comparisons": comparisons,
    }


def aggregate_maintenance(
    episode_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    fields = (
        "c_synchronized_newly_known_count",
        "c_bound_decrement_count",
        "c_exact_cache_installation_count",
        "c_exact_cache_replacement_count",
    )
    primary_c = [
        record for record in episode_records
        if record["phase"] == "primary_structural"
        and record["method"] == "C"
        and record["correctness_valid"] is True
    ]
    return {
        "per_map": {
            record["map_id"]: {field: record[field] for field in fields}
            for record in primary_c
        },
        "overall": {
            field: sum(record[field] for record in primary_c) for field in fields
        },
    }


def sensitivity_summary(
    episode_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    records = [
        record for record in episode_records
        if record["phase"] == "range_sensitivity"
    ]
    conditions: dict[str, dict[str, Any]] = defaultdict(dict)
    for record in records:
        key = f"{record['map_id']}:R={record['sensor_range']}"
        conditions[key][record["method"]] = {
            "correctness_valid": record["correctness_valid"],
            **{field: record[field] for field in WORK_FIELDS},
        }
    return {
        "conditions": dict(sorted(conditions.items())),
        "affects_primary_decision": False,
    }


def path_coverage_sanity(
    episode_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Compare deterministic trajectory fields only within shared passes."""

    fields = (
        "target_stop_sequence_hash", "path_length", "coverage_90_step_index",
        "coverage_95_step_index", "coverage_99_step_index",
    )
    groups: dict[tuple[str, str, float], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for record in episode_records:
        if record["phase"] in {
            "primary_structural", "anchor_structural", "range_sensitivity"
        }:
            groups[(record["phase"], record["map_id"], record["sensor_range"])][
                record["method"]
            ] = record
    conditions: dict[str, Any] = {}
    all_equal = True
    for key, methods in sorted(groups.items()):
        complete = set(methods) == {"A", "B", "C"}
        equal = complete and all(
            len({methods[method][field] for method in "ABC"}) == 1
            for field in fields
        )
        all_equal = all_equal and equal
        conditions[f"{key[0]}:{key[1]}:R={key[2]}"] = {
            "complete": complete,
            "equal": equal,
        }
    return {
        "coverage_denominator": "start_reachable_legal_free_component",
        "all_shared_conditions_equal": bool(conditions) and all_equal,
        "conditions": conditions,
    }


def classify_decision(
    *,
    primary_correctness_valid: bool,
    b_work: Mapping[str, int],
    c_work: Mapping[str, int],
    c_over_b_interval: Sequence[float] | None,
    invocation_complete: bool = True,
    correctness_failure_observed: bool = False,
    memory: Mapping[str, Any] | None = None,
    sensitivity: Mapping[str, Any] | None = None,
) -> str | None:
    """Implement Pre-execution Amendment 1 exactly and in order."""

    del memory, sensitivity  # Required reports cannot override classification.
    if correctness_failure_observed:
        return "CORRECTNESS_REOPENED"
    if not invocation_complete:
        return None
    if not primary_correctness_valid:
        return "CORRECTNESS_REOPENED"
    work_gate = all(c_work[field] < b_work[field] for field in VISIBILITY_WORK_FIELDS)
    if not work_gate:
        return "DROP"
    if c_over_b_interval is None or len(c_over_b_interval) != 2:
        raise ValueError("complete invocation requires a C/B timing interval")
    lower, upper = c_over_b_interval
    if (
        not all(type(value) in (int, float) and math.isfinite(value) for value in (lower, upper))
        or lower > upper
    ):
        raise ValueError("invalid timing interval ordering")
    if upper < 1.0:
        return "GO"
    if lower <= 1.0 <= upper:
        return "MODIFY"
    if lower > 1.0:
        return "DROP"
    raise ValueError("invalid timing interval ordering")


def structural_peak_summary(
    episode_records: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, int]]:
    fields = (
        "b_peak_cached_scalar_entry_count",
        "c_peak_cached_candidate_count",
        "c_peak_bound_entry_count",
        "c_peak_cached_membership_count",
        "c_peak_inverse_key_count",
        "c_peak_inverse_membership_count",
        "c_peak_reported_known_count",
    )
    result: dict[str, dict[str, int]] = {}
    for record in episode_records:
        if record["phase"] not in {"primary_structural", "range_sensitivity"}:
            continue
        result[f"{record['phase']}:{record['map_id']}:{record['method']}:{record['sensor_range']}"] = {
            field: record[field] for field in fields if record[field] is not None
        }
    return result


def build_summary(
    *,
    invocation_id: str,
    episode_records: Sequence[Mapping[str, Any]],
    snapshot_records: Sequence[Mapping[str, Any]],
    timing_records: Sequence[Mapping[str, Any]],
    memory_records: Sequence[Mapping[str, Any]],
    invocation_complete: bool,
    invocation_status: str,
    primary_correctness_failed: bool = False,
) -> dict[str, Any]:
    work = aggregate_work(episode_records)
    timing = summarize_timing(timing_records)
    primary_records = [
        record for record in episode_records if record["phase"] == "primary_structural"
    ]
    correctness_valid = not primary_correctness_failed and bool(primary_records) and all(
        record["correctness_valid"] for record in primary_records
    )
    b_work = work["overall"].get("B", {field: 0 for field in WORK_FIELDS})
    c_work = work["overall"].get("C", {field: 0 for field in WORK_FIELDS})
    interval = None
    if timing["complete"] and "C/B" in timing["comparisons"]:
        interval = timing["comparisons"]["C/B"]["bootstrap_interval_95"]
    primary_groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for record in primary_records:
        primary_groups[record["map_id"]].append(record)
    primary_structural_complete = (
        len(primary_groups) == 27
        and len(primary_records) == 81
        and all(
            {record["method"] for record in records} == {"A", "B", "C"}
            and len(records) == 3
            and all(record["correctness_valid"] for record in records)
            for records in primary_groups.values()
        )
    )
    primary_timing_complete = (
        timing["complete"] and len(timing["per_map_method"]) == 9
    )
    primary_evidence_complete = (
        primary_structural_complete and primary_timing_complete
    )
    decision = classify_decision(
        primary_correctness_valid=correctness_valid,
        b_work=b_work,
        c_work=c_work,
        c_over_b_interval=interval,
        invocation_complete=primary_evidence_complete,
        correctness_failure_observed=primary_correctness_failed,
    )
    return {
        "identity": {"invocation_id": invocation_id},
        "completion": {
            "status": invocation_status,
            "scientific_result_complete": primary_correctness_failed
            or primary_evidence_complete,
            "full_invocation_complete": invocation_complete,
            "primary_structural_complete": primary_structural_complete,
            "primary_timing_complete": primary_timing_complete,
        },
        "correctness": {"primary_valid": correctness_valid},
        "work": work,
        "bound_tightness": aggregate_bound_slack(snapshot_records),
        "maintenance": aggregate_maintenance(episode_records),
        "timing": timing,
        "memory": {
            "structural_peaks": structural_peak_summary(episode_records),
            "tracemalloc_records": list(memory_records),
        },
        "scaling": {
            "primary_work_per_size": work["per_size"],
            "descriptive_only": True,
        },
        "sensitivity": sensitivity_summary(episode_records),
        "path_coverage_sanity": path_coverage_sanity(episode_records),
        "decision": {
            "classification": decision,
            "available": decision is not None,
            "all_three_visibility_work_gate": all(
                c_work[field] < b_work[field] for field in VISIBILITY_WORK_FIELDS
            )
            if correctness_valid
            else None,
        },
    }


__all__ = [
    "BOOTSTRAP_RESAMPLES",
    "BOOTSTRAP_SEED",
    "DECISIONS",
    "VISIBILITY_WORK_FIELDS",
    "WORK_FIELDS",
    "aggregate_maintenance",
    "aggregate_bound_slack",
    "aggregate_work",
    "build_summary",
    "canonical_path_hash",
    "canonical_sequence_hash",
    "classify_decision",
    "linear_quantile",
    "nearest_rank_percentile",
    "paired_bootstrap_interval",
    "path_coverage_sanity",
    "safe_ratio",
    "sensitivity_summary",
    "structural_peak_summary",
    "summarize_six_timings",
    "summarize_timing",
]
