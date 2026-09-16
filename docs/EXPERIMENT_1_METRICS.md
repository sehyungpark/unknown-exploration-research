# Experiment 1 Metrics and Raw Schema

Frozen: 2026-09-16

Applies to: `experiment-1-efficiency-v1`

Status: **PREREGISTERED — NOT EXECUTED**

## Measurement Definitions

### Exact gain evaluations

At every planning snapshot record `a_exact_gain_evaluation_count`, `b_exact_gain_evaluation_count`, and `c_exact_gain_evaluation_count`. Sum per map, size, density, and overall; retain snapshot values. Report B/A, C/A, and primarily C/B.

### Canonical exact-visibility work

For every exact invocation of `optimistic_visible_unknown_cells(...)`, benchmark-only forwarding instrumentation around the existing canonical functions records:

- `visibility_ray_count`: number of UNKNOWN target cells for which `supercover_line(origin, target)` is invoked.
- `visibility_supercover_cell_count`: sum of the lengths of all complete generated supercover lines. The current function constructs a complete line before testing occlusion.
- `visibility_interior_probe_count`: number of `belief.state(cell) is OCCUPIED` checks actually consumed from `line[1:-1]` by the short-circuit `any(...)`.

Counters include every exact visibility computation made inside the timed planner call, but reconstructing or serializing them must not occur inside the primary timer. Instrumentation must forward to the canonical implementation and may not approximate ray cost or fork planner logic.

### Bound tightness

For every eligible candidate carrying a B or C maintained bound `U`, use Algorithm A's exact current gain `G_A` only as an external measurement oracle. Record absolute slack `U-G_A`, `tight = (U == G_A)`, and normalized slack `(U-G_A)/max(1,U)`. Negative slack is a correctness failure.

For B and C separately aggregate mean, median, and nearest-rank 95th percentile of absolute and normalized slack, plus tight-bound fraction, per map, size, density, and overall. All candidate observations are descriptive; statistical confidence remains map-level. Do not alter B/C refresh histories for measurement.

### C maintenance

Per snapshot record synchronized newly-known cells, bound-decrement operations, exact cache installations/replacements, cached-set membership count, inverse-incidence membership count, bound-count entry count, and reported-known-cell count. Require cached membership count to equal inverse membership count. Sum operation counters and retain per-episode peaks for storage counters.

### Planner time

`planner_wall_time_ns` is measured by `time.perf_counter_ns()` immediately before and after only `exhaustive_nbv(...)` or `planner.plan(...)`. `process_time_ns` uses the identical boundary with `time.process_time_ns()`. Episode values are sums across planner snapshots.

Excluded are map generation, physical scan, belief application, movement, serialization, disk I/O, offline visibility-work reconstruction, statistics, and analysis. The primary time is total wall time, not a decomposition component.

### Internal decomposition

A separate instrumented pass records distance/Dijkstra, exact visibility, C synchronization plus bound/index maintenance, and other selection/certificate/bookkeeping nanoseconds. Benchmark-only forwarding wrappers must call already imported canonical functions and may not duplicate A/B/C logic. The components should approximately sum to total planner time; nesting and timer-call overhead are reported as `decomposition_residual_ns = total - distance - visibility - maintenance - other` and explained. These values are descriptive only.

### Structural and Python memory

Primary deterministic storage counters are:

- B: cached scalar entry count.
- C: cached candidate count, bound-count entry count, cached-set membership count, inverse-incidence key count, inverse-incidence membership count, and reported-known-cell count.

Record each per snapshot and its episode peak. Separately, on the nine timing maps, run a fresh non-timed episode under `tracemalloc` per method/map and record peak traced Python bytes. Do not place `tracemalloc` around a primary timing repetition. This is Python implementation memory, not language-independent algorithmic memory.

### Scaling and sanity fields

Every snapshot records eligible candidate count, known-FREE count, and map cell count. Later plots relate exact evaluations, ray work, C memberships, and planner time directly to eligible-candidate count. No asymptotic fit or claim is permitted from only three map sizes.

Record path length, coverage trajectory, planning snapshot count, and first 90%, 95%, and 99% coverage step/time indices as decision-equivalence sanity checks. They are not evidence of improved path quality.

## JSON Conventions

Every JSONL line is one complete JSON object serialized as UTF-8 with sorted keys, compact separators, finite JSON numbers only, and exactly one LF. Coordinates are `[row,col]`; statuses are `SELECTED` or `EXPLORATION_COMPLETE`; methods are `A`, `B`, or `C`; phases are `primary_structural`, `anchor_structural`, `timing_warmup`, `primary_timing`, `decomposition`, `memory`, or `range_sensitivity`. Fields unavailable by design are JSON `null`, not omitted. Counts and times are nonnegative integers. Ratios and scores are finite numbers or `null` only where the denominator/value is undefined.

The writer validates every record before writing. An existing invocation or failure directory is refused. `summary.json` is derived from retained raw records, never entered independently.

## Output Layout

```text
results/experiment_1/
├─ runs/
│  └─ <invocation_id>/
│     ├─ manifest.json
│     ├─ episodes.jsonl
│     ├─ snapshots.jsonl
│     ├─ timing_repetitions.jsonl
│     ├─ memory.jsonl
│     └─ summary.json
└─ failures/
   └─ <failure_run_id>/
      ├─ metadata.json
      ├─ ground_truth.txt
      ├─ belief_before.txt
      ├─ candidates.json
      ├─ algorithm_state.json
      └─ failure.txt
```

No Stage 9 file may be written under `runs/`. Failure directories follow Experiment 0's immutable six-file evidence principle and retain the measurement phase/repetition context in `metadata.json`.

## `manifest.json`

Exactly one object with these required fields:

- identity: `experiment_name`, `experiment_version`, `dataset_version`, `invocation_id`, `created_at_utc`, `repository_commit`, `runner_version`;
- frozen configuration: `master_seed`, `primary_sensor_range`, `sensitivity_sensor_ranges`, `primary_map_ids`, `anchor_fixture_ids`, `timing_subset_map_ids`, `sensitivity_subset_map_ids`, `timing_orders`, `warmup_repetitions`, `timed_repetitions`, `bootstrap_resamples`, `bootstrap_seed`;
- semantics: `movement_semantics`, `visibility_semantics`, `sensing_semantics`, `score_and_tie_rule_version`;
- environment: `os`, `os_version`, `cpu_model`, `logical_cpu_count`, `physical_cpu_count`, `ram_bytes`, `python_implementation`, `python_version`, `process_architecture`, `cpu_affinity`, `frequency_control_state`;
- completion: `status` (`RUNNING`, `PASS`, or `FAILED`), `started_at_utc`, `completed_at_utc`, and `failure_run_ids`.

Unavailable environment fields are `null`. The manifest is finalized atomically but its invocation directory is never reused.

## `episodes.jsonl`

One record per complete method episode, including warm-up, structural, decomposition, memory, sensitivity, and anchor episodes. Required fields:

```text
experiment_version, invocation_id, phase, dataset_version,
dataset_kind, map_id, size, density_label, occupancy_probability,
map_seed, map_hash, start, sensor_range, method,
repetition_index, timed, method_order, method_order_position,
cycle_limit, terminal_status, correctness_valid,
failure_run_id, planning_snapshot_count, selected_snapshot_count,
target_stop_sequence_hash, path_length,
coverage_90_step_index, coverage_95_step_index, coverage_99_step_index,
coverage_90_elapsed_planning_ns, coverage_95_elapsed_planning_ns,
coverage_99_elapsed_planning_ns,
exact_gain_evaluation_count, visibility_ray_count,
visibility_supercover_cell_count, visibility_interior_probe_count,
c_synchronized_newly_known_count, c_bound_decrement_count,
c_exact_cache_installation_count, c_exact_cache_replacement_count,
b_peak_cached_scalar_entry_count, c_peak_cached_candidate_count,
c_peak_bound_entry_count, c_peak_cached_membership_count,
c_peak_inverse_key_count, c_peak_inverse_membership_count,
c_peak_reported_known_count, planner_wall_time_ns,
process_time_ns, distance_time_ns, visibility_time_ns,
maintenance_time_ns, other_time_ns, decomposition_residual_ns
```

Dataset metadata is `null` only for fixtures where density, probability, or seed does not apply. Repetition/order fields are `null` outside timing phases. Primary timer fields are populated only for `timing_warmup` and `primary_timing`; decomposition component fields are populated only for `decomposition`. A correctness-invalid episode retains measured raw values but is excluded from all performance summaries.

## `snapshots.jsonl`

One record per planning snapshot, including the terminal snapshot:

```text
experiment_version, invocation_id, phase, map_id, sensor_range,
method, repetition_index, cycle_index, robot_coordinate, belief_hash,
unknown_count, known_free_count, known_occupied_count, map_cell_count,
eligible_candidate_count, status, selected_candidate, selected_gain,
selected_distance, selected_score, selected_path_hash,
exact_gain_evaluation_count, visibility_ray_count,
visibility_supercover_cell_count, visibility_interior_probe_count,
planner_wall_time_ns, process_time_ns,
distance_time_ns, visibility_time_ns, maintenance_time_ns, other_time_ns,
c_synchronized_newly_known_count, c_bound_decrement_count,
c_exact_cache_installation_count, c_exact_cache_replacement_count,
b_cached_scalar_entry_count, c_cached_candidate_count,
c_bound_entry_count, c_cached_membership_count, c_inverse_key_count,
c_inverse_membership_count, c_reported_known_count,
bound_measurements, agreement_all, sequence_prefix_agreement_all,
bound_valid_b, bound_valid_c, tie_certificate_valid_b,
tie_certificate_valid_c, cache_index_invariant_valid_c,
correctness_valid, failure_run_id
```

`bound_measurements` is a coordinate-sorted array. Each item has exactly `method` (`B` or `C`), `candidate`, `upper_bound`, `a_exact_gain`, `absolute_slack`, `normalized_slack`, and `tight`. It covers every eligible candidate with a maintained bound. The C membership equality is independently checked at each C snapshot.

## `timing_repetitions.jsonl`

One record per `(map, method)` warm-up or timed repetition:

```text
experiment_version, invocation_id, dataset_version, map_id,
method, repetition_index, timed, method_order,
method_order_position, warmup_discarded, sensor_range,
episode_planner_wall_time_ns, episode_process_time_ns,
planning_snapshot_count, target_stop_sequence_hash,
correctness_valid, failure_run_id
```

Warm-up has `repetition_index=0`, `timed=false`, and `warmup_discarded=true`. Timed repetitions are 1 through 6 and use the corresponding frozen order. All six raw values remain present. Summary medians, IQR, minimum, and maximum are derived only from correctness-valid timed repetitions; fewer than six makes the formal timing result incomplete.

## `memory.jsonl`

One record per method/map in the separate Python-memory pass:

```text
experiment_version, invocation_id, dataset_version, map_id,
method, sensor_range, measurement_kind,
tracemalloc_peak_bytes, tracemalloc_current_bytes_at_stop,
b_peak_cached_scalar_entry_count, c_peak_cached_candidate_count,
c_peak_bound_entry_count, c_peak_cached_membership_count,
c_peak_inverse_key_count, c_peak_inverse_membership_count,
c_peak_reported_known_count, planning_snapshot_count,
target_stop_sequence_hash, correctness_valid, failure_run_id
```

`measurement_kind` is exactly `python_tracemalloc_separate_non_timed_pass`.

## `summary.json`

Required top-level keys are `identity`, `completion`, `correctness`, `work`, `bound_tightness`, `maintenance`, `timing`, `memory`, `scaling`, `sensitivity`, `path_coverage_sanity`, and `decision`.

`work` contains per-map, per-size, per-density, and overall sums/ratios for exact evaluations and the three visibility counters. `bound_tightness` contains the frozen aggregates. `timing` retains the per-map method medians/IQR/min/max, paired ratios, geometric means, medians, bootstrap configuration and intervals. `decision` contains `GO`, `MODIFY`, `DROP`, or `CORRECTNESS_REOPENED`, plus the truth values for every preregistered criterion. No result is summarized from an invalid run.

## Failure Handling

On the first correctness/invariant/config/record failure, stop interpretation for that run, write the non-overwriting six-file evidence directory, link its ID from raw records and the invocation manifest, and do not move or continue as if valid. `metadata.json` includes invocation, phase, map, method/order/repetition, sensor range, cycle, repository/runner versions, failure classification, and hashes. Remaining five files retain the same canonical meanings as Experiment 0 plus available work/timing/storage state.

Failure classes include target mismatch, sequence/termination mismatch, bound violation, tie-certificate violation, C cache/index violation, unsupported lifecycle/configuration, cycle-limit exhaustion, malformed measurement, and unexpected exception. Failed or unfavorable evidence is never deleted.

## Analysis Rules

The exact aggregation, bootstrap, GO/MODIFY/DROP, timing order, warm-up, range sensitivity, and no-tuning rules are frozen in `docs/EXPERIMENT_1_PREREGISTRATION.md`. Ratios with zero denominators are `null` with an explicit count; they are never coerced. No Experiment 1 measurement exists as of this freeze.
