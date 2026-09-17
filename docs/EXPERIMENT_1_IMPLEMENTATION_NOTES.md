# Experiment 1 Implementation Notes

Status: Stage 10 infrastructure implemented; formal Experiment 1 **NOT EXECUTED**.

These conventions implement the frozen Stage 9 specifications without changing a primary metric, workload, threshold, timing protocol, or decision rule. The authoritative specifications remain `EXPERIMENT_1_PREREGISTRATION.md`, `EXPERIMENT_1_DATASET.md`, `EXPERIMENT_1_METRICS.md`, and `configs/experiment_1_efficiency_maps.json`.

## Runner and execution boundary

- Runner identity is `experiment-1-runner-v1`.
- Formal execution requires both `--execute-preregistered` and an explicit `--invocation-id`. Importing the module and invalid/incomplete CLI parsing create no result directory.
- Formal pass order is primary structural, anchor structural, primary timing, decomposition, memory, then sensor-range sensitivity. Frozen map, fixture, range, warm-up, and six timing-method orders are encoded directly.
- The runner is single-process and single-threaded. Benchmark-only forwarding contexts temporarily replace module-local call references and always restore them; concurrent planner measurement in one process is unsupported.

## Exact-visibility work instrumentation

The work context forwards exactly once to the accepted canonical optimistic-visibility callable. It patches the A/B module-local references and C's integration-layer reference, then temporarily wraps canonical `supercover_line`. One canonical line call contributes one ray and its full returned length. A lazy proxy for canonical `line[1:-1]` increments the interior-probe count only when the short-circuit occupancy predicate actually consumes a cell. Physical sensing outside an active exact-visibility call is not counted. Measured exact-call count must equal the planner's reported exact-gain-evaluation count.

## Timing and decomposition

- Primary timing places `perf_counter_ns()` and `process_time_ns()` immediately around only `simulator.plan()` for A or `planner.plan()` for B/C. Construction, initial sensing, validation, movement, arrival sensing, hashing, serialization, work instrumentation, decomposition, and memory tracing remain outside the timing boundary.
- The separate decomposition context forwards through the canonical module-local Dijkstra and exact-visibility references. For C it also times revelation synchronization and exact cache installation/replacement as non-overlapping maintenance. `other_time_ns` is the exact outer total minus distance, visibility, and maintenance; a negative complement is a measurement failure. Because other is the exact complement, `decomposition_residual_ns` is zero.
- Timing Q1/Q3 and bootstrap percentile bounds use sorted-value linear interpolation with `h=(n-1)p`. Bound-slack p95 uses nearest rank.

## Memory, coverage, and hashes

- Each memory method/map uses a fresh environment and planner. Environment/planner construction and the initial physical scan precede `tracemalloc.start()`. Tracing spans the first planning call through the terminal planner return and final in-episode measurement, then current/peak bytes are read and tracing is stopped/cleared before the next method. These Python allocation values are secondary to deterministic structural storage counters.
- Coverage denominator is the ground-truth FREE component containing the frozen start under the accepted 8-neighbor/no-corner-cutting relation. Initial post-scan coverage is step zero; OCCUPIED and unreachable FREE cells are excluded.
- A selected path hashes the UTF-8 concatenation of one `[row,col]\n` line per coordinate. A target/STOP sequence hashes one `[row,col]` or `STOP` line per decision with one final LF. SHA-256 is used; Python's process-dependent `hash()` is not used.

## Raw evidence and failure state

- The invocation writer accepts only exact phase-aware schemas, canonical compact sorted-key JSON with one final LF, and finite values. It refuses unsafe/existing invocation IDs, derives the sole summary from retained raw records, and atomically replaces the RUNNING manifest at finalization.
- Failure evidence is an immutable, non-overwriting six-file directory with deterministic phase/method/repetition/cycle-aware identity.
- A verified primary structural correctness failure is represented as `CORRECTNESS_REOPENED` even though the invocation stops. A runner/configuration/instrumentation failure before complete primary evidence leaves the scientific classification `null`. Once all 27 primary structural conditions and all nine six-repetition timing conditions are valid, later descriptive memory/decomposition/sensitivity evidence cannot override the primary Amendment 1 classification.

## Stage 10 boundary

Stage 10 tests use hand-built beliefs, a nonformal one-row smoke map, mocks, fake clocks, fault injection, and workspace-local temporary directories. No planner was run on the 27 frozen Experiment 1 maps, no formal result/failure directory was created, and the empirical-value gate remains **OPEN**.
