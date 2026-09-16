# Experiment 1 — Efficiency and Scaling Evaluation

Frozen: 2026-09-16

Dataset: `experiment-1-efficiency-v1`

Status: **PREREGISTERED — NOT EXECUTED**

## Purpose and Scope

Experiment 1 tests whether Candidate 1's certified change-aware bound (Algorithm C) provides empirical computational value over the stale-scalar exact-lazy baseline (B) while preserving the exhaustive optimistic-NBV decisions of Algorithm A. It measures exact evaluations, canonical visibility work, bound tightness, C maintenance, total planner time, storage, scaling, and sensor-range sensitivity.

The primary comparison is C versus B. A remains the exhaustive external correctness and measurement oracle. This experiment does not test path-quality improvement because exact decision equivalence requires the same path.

## Frozen Workloads

The primary workload is the 27-map `experiment-1-efficiency-v1` dataset defined in `docs/EXPERIMENT_1_DATASET.md` and `configs/experiment_1_efficiency_maps.json`: sizes 20×20, 30×30, and 40×40; densities sparse (`p=0.10`), medium (`p=0.20`), and dense (`p=0.30`); three accepted maps per size-density stratum. Primary conclusions use sensor range `R=8`.

The seven unchanged 20×20 fixtures (`open`, `single_room`, `corridor`, `dead_end`, `separated_rooms`, `clutter`, and `maze_like`) are included once at `R=8` as descriptive structural anchors. They receive no repeated timing or `tracemalloc` pass. Primary scaling conclusions use the 27 new maps.

The frozen nine-map timing and `tracemalloc` subset is the first accepted map in each size-density stratum:

- `efficiency-20x20-sparse-01`
- `efficiency-20x20-medium-01`
- `efficiency-20x20-dense-01`
- `efficiency-30x30-sparse-01`
- `efficiency-30x30-medium-01`
- `efficiency-30x30-dense-01`
- `efficiency-40x40-sparse-01`
- `efficiency-40x40-medium-01`
- `efficiency-40x40-dense-01`

The secondary sensor-range subset is `efficiency-30x30-sparse-01`, `efficiency-30x30-medium-01`, and `efficiency-30x30-dense-01`, each run separately at `R=4`, `R=8`, and `R=12`.

## Frozen Simulator Semantics

All methods use 8-neighbor known-FREE movement, orthogonal cost 1, diagonal cost `sqrt(2)`, no corner cutting, corner-inclusive deterministic supercover lines, UNKNOWN-transparent optimistic planning visibility, first-hit OCCUPIED physical visibility, and sensing only at arrival. Within a run, physical sensing, planning visibility, and planner cache identity use the same sensor range. No trajectory or visibility semantic may be changed for performance.

## Correctness Gate

At every planning snapshot the runner must verify `target_A(t) = target_B(t) = target_C(t)`, identical selected values and paths, all registered bound/tie/cache invariants, and identical terminal decisions and complete target/STOP sequences. There is no fallback to A.

A target or sequence mismatch, bound violation, tie-certificate violation, C cache/index invariant failure, unsupported lifecycle/configuration failure, cycle-limit exhaustion, or malformed measurement record invalidates that benchmark run. Its performance values must not enter analysis, and its evidence must be retained under the append-only failure layout.

## Formal Invocation Passes

One formal invocation on one machine/environment contains these logically separate passes:

1. **Primary structural pass:** one complete shared-snapshot A/B/C episode on each of 27 maps at `R=8`, collecting correctness, work, slack, maintenance, storage, path, and coverage records. The seven fixtures may receive the same descriptive pass.
2. **Primary timing pass:** the frozen nine-map subset under the timing protocol below. Only total planner wall/process timings from this pass are primary timing evidence. Visibility-work/decomposition wrappers and `tracemalloc` are disabled in this pass; correctness validation occurs outside the timer boundary.
3. **Internal-decomposition pass:** a separate complete episode per method and timing-subset map, used descriptively to partition planner time. Its instrumented timings are not substituted for primary timing.
4. **Python-memory pass:** a separate non-timed `tracemalloc` episode per method and timing-subset map. It is not mixed with timing.
5. **Range-sensitivity pass:** the frozen three-map subset at `R=4`, `R=8`, and `R=12`, collecting A/B/C correctness, deterministic structural work, and structural storage. This is secondary evidence.

Each pass uses a fresh environment and fresh planner for each method/episode. The future Stage 10 runner may implement these passes, but must not change their planner decisions or the frozen documents.

## Timing Protocol

For each timing map, run one untimed complete warm-up episode per method in fixed A, B, C order and discard its timing. Then run six timed complete episodes per method, constructing a fresh environment and planner each time and requiring the same target/STOP sequence in every repetition.

The six repetition orders are frozen, once each and in this order:

1. A, B, C
2. B, C, A
3. C, A, B
4. A, C, B
5. C, B, A
6. B, A, C

The primary `(map, method)` time is the median of six episode planning wall times. All repetitions are retained; IQR, minimum, and maximum are descriptive. Timing uses `time.perf_counter_ns()` immediately around only `exhaustive_nbv(...)` for A or `planner.plan(...)` for B/C. `time.process_time_ns()` is secondary. Map generation, physical scan, belief application, movement, serialization, disk I/O, offline work reconstruction, and analysis are excluded.

All primary repetitions run within one formal invocation on the same machine/environment. The manifest records OS and version, CPU model, logical and available physical CPU counts, RAM, Python implementation/version, repository commit, runner version, process architecture, and available CPU-affinity/frequency-control state. Unavailable fields are explicitly `null`; they are never fabricated.

## Statistical Analysis

The independent unit is the map, not the planning snapshot. Snapshot records are descriptive only.

For each timing map, compute `r_m = median(T_C)/median(T_B)`. The primary timing summary is the geometric mean of the nine paired C/B ratios; also report their median. A paired map-level bootstrap resamples the nine log ratios 10,000 times with local bootstrap seed `20260916`; exponentiating the 2.5th and 97.5th percentiles yields the descriptive 95% interval. Apply the same descriptive procedure to B/A and C/A. Never bootstrap snapshots.

For deterministic exact-evaluation, ray, generated-supercover-cell, and interior-probe work, report `sum(C)/sum(B)` over primary maps and paired per-map ratios. No significance test is used. Candidate-density plots use observed eligible-candidate count, not obstacle probability alone. No asymptotic complexity is inferred from three sizes.

## Frozen Decision Rule

For this decision, "strictly less aggregate exact visibility work" means that C's primary-map total is strictly below B's total for each of `visibility_ray_count`, `visibility_supercover_cell_count`, and `visibility_interior_probe_count`. "Materially reduces" uses this same predeclared all-three strict condition; magnitudes are reported without adding a post-result percentage threshold.

**GO** requires all primary `R=8` decisions to remain exactly equivalent, strictly less aggregate exact visibility work for C than B under that definition, and a paired-map 95% bootstrap interval for C/B total planning time entirely below 1.0. Memory/storage overhead remains an explicit tradeoff.

**MODIFY** applies when correctness remains intact and C materially reduces deterministic exact visibility work relative to B, but total time is inconclusive (including an interval crossing 1.0) or bookkeeping/memory clearly absorbs the compute saving.

**DROP** applies to the current Candidate 1 implementation/direction when correctness remains intact but C does not reduce deterministic exact visibility work relative to B; or when C is consistently slower with its paired timing interval entirely above 1.0 and structural scaling provides no evidence that the bookkeeping buys useful pruning.

A correctness failure is not DROP. It reopens the correctness investigation.

## Pre-execution Amendment 1 — Deterministic Decision Categories

Amended: 2026-09-17, before any Experiment 1 execution. At the time of this amendment, no Experiment 1 timing, memory, deterministic work, bound slack, or planner-performance result had been observed. The original Stage 9 decision wording above remains preserved as preregistered history; this amendment supersedes that wording only where it defines the final Experiment 1 decision classification.

The dataset, maps, timing subset, sensor-range sensitivity subset, metrics, repetitions, timing method orders, paired map-level bootstrap protocol, simulator semantics, and Algorithms A/B/C are unchanged. This amendment only makes the final decision categories mutually exclusive and deterministic. Evaluate the following conditions in exactly this order, with no subjective override after observing the result:

1. **CORRECTNESS_REOPENED.** If any primary `R=8` Experiment 1 correctness requirement fails, including any A/B/C target or sequence disagreement or any required bound, tie-certificate, or cache/index invariant failure, set `decision = CORRECTNESS_REOPENED`. Do not interpret performance results from the invalid run. This classification is not GO, MODIFY, or DROP.
2. **Visibility-work reduction gate.** Over the complete primary 27-map `R=8` workload, C has reduced deterministic exact-visibility work relative to B if and only if all three aggregate strict inequalities hold: `C_ray < B_ray` AND `C_supercover < B_supercover` AND `C_probe < B_probe`, for `visibility_ray_count`, `visibility_supercover_cell_count`, and `visibility_interior_probe_count`, respectively. If this all-three condition is false, set `decision = DROP`.
3. **GO.** If correctness is valid, the all-three visibility-work reduction condition is true, and the preregistered paired map-level 95% bootstrap interval `[lower, upper]` for the C/B total planning-time ratio lies entirely below `1.0` (`upper < 1.0`), set `decision = GO`.
4. **MODIFY.** If correctness is valid, the all-three visibility-work reduction condition is true, and the interval contains `1.0`, including endpoint equality (`lower <= 1.0 <= upper`), set `decision = MODIFY`.
5. **DROP.** If correctness is valid, the all-three visibility-work reduction condition is true, and the interval lies entirely above `1.0` (`lower > 1.0`), set `decision = DROP`.

After correctness is established and the all-three visibility-work reduction gate passes, the timing boundaries are exhaustive and mutually exclusive:

- `upper < 1.0` → GO
- `lower <= 1.0 <= upper` → MODIFY
- `lower > 1.0` → DROP

B structural cache size, C structural cache/index size, separate `tracemalloc` results, and scaling behavior remain required reported tradeoffs and must be discussed when interpreting the result. They do not independently override the deterministic classification. A GO result may therefore carry a substantial memory cost, which must be stated. Candidate-density and sensor-range scaling remain descriptive/secondary analyses; they likewise do not override the primary classification and are not separate DROP triggers.

## Path and Coverage Sanity

Record path length, coverage trajectory, planning-snapshot count, and 90%, 95%, and 99% coverage step/time indices. These must agree across A/B/C as applicable and are sanity checks only. No path-quality improvement claim is permitted.

## Integrity and Failure Preservation

The first formal result is preserved whether favorable or not. After execution, do not change thresholds, maps, repetition counts, warm-up handling, method order, or discard slow repetitions. Do not rerun until favorable. Any later optimization study requires a new experiment/version ID.

Outputs are non-overwriting under `results/experiment_1/`. Successful and failed invocations are append-only. Exact schemas are frozen in `docs/EXPERIMENT_1_METRICS.md`.

## Stage 9 Boundary

Stage 9 generated and inspected maps using structural quantities only. It did not run Algorithms A/B/C, the simulator, sensing, any planner, timing, memory tracing, visibility reconstruction, or performance counters on Experiment 1 maps. No `results/experiment_1/runs/` directory exists from this stage. The empirical-value gate remains **OPEN**.
