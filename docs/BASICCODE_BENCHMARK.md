# basiccode A/B/C* benchmark protocol

## Scope fixed before measuring

- Candidate: Candidate 1, the standalone `basiccode` implementation.
- Phase: correctness/infrastructure validation followed by a user-run exploratory timing/scaling benchmark. This is not formal Experiment 2 and introduces no new algorithm or novelty claim.
- Closest existing mechanism: `src/evaluation/experiment_2_runner.py` already separates correctness, work, timing and memory. This runner applies that measurement separation to the different 4-neighbor/per-movement-step-sensing `basiccode` contract.
- Shared components: use the existing `nbv_common.generate_map` and each algorithm's actual `explore()`. Do not duplicate the simulator, change baseline search structures, or use the `src` planners as substitutes.
- Correctness condition: complete `ExplorationResult` (all targets, scores, gains, distances, planned/actual paths, costs, termination) and final known map equal A. Compare the structural, warm-up, timed and memory episodes to A's structural outcome outside timing.
- Hypothesis: B/C* preserve A's decisions while reducing exact gain evaluations and possibly runtime. No speedup threshold is enforced. Fewer evaluations with slower runtime refutes the runtime benefit on this workload; slower and failed cases remain in the raw data.
- Scientific scope: the fixed seed list is small. This produces machine-specific exploratory evidence, not a new universal efficiency guarantee or a reclassification of the completed C* Experiment 2.

## Workload

`configs/basiccode_benchmark_v1.json` fixes 10/15/20 square grids, p=0.20, seeds 42/43/44, R=4, one warm-up and six timed repetitions per method. Nine requested maps give 162 timed episodes, 27 warm-ups, 27 structural episodes, 27 separate memory episodes and 21 seven-family sanity episodes: 264 total.

`--smoke` always uses `configs/basiccode_smoke_v1.json`: two tiny maps, R=2, two timed repetitions, 51 episodes including the same seven sanity families. Its outputs and every figure are labeled **SMOKE VALIDATION - NOT PERFORMANCE EVIDENCE**. It may run on uncommitted development code. Non-smoke runs require committed, clean algorithm/runner/test/config/requirements source. Result files and research notes may remain untracked.

All requested maps and sanity inputs are saved to `maps.json` before the first performance measurement. Every algorithm receives fresh copies of exactly the same truth and all-UNKNOWN initial map, start and sensor range. The existing generator's connectivity/observable-wall rejection rules and internal random stream are unchanged. A generation failure is saved with its seed/config/error, blocks timing and is never replaced with another seed. The generator's existing 1000-attempt cap remains fixed; internal rejected candidates are reproducible from seed and source version, not individually logged.

The seven tiny sanity families (open, single room, corridor, dead end, separated rooms, clutter, maze-like) run only as correctness checks at R=2 and are never pooled into the timing/scaling graphs. Some fixtures can terminate with remaining UNKNOWN; agreement and successful full reconstruction are separate facts. All benchmark terminations and remaining UNKNOWN counts are retained.

## Measurement boundaries

- A wrapper times the original `evaluate_candidates` with `perf_counter_ns`. This includes BFS, range/cache/heap work and C*'s pending UNKNOWN-mask synchronization.
- The episode clock surrounds the original `explore`. It includes initial observation, every movement scan, C*'s newly-known bookkeeping, cache initialization, result construction and the small timer wrapper overhead. Input copies, parameter setup, output, reference comparisons, hashing and file writes are outside both clocks. Planner time and episode time are distinct metrics.
- Cold episode caches are initialized by the existing `explore` every run. Warm-up warms interpreter/allocator execution, not reusable planner state. The six timed orders are all six permutations of A/B/C*, balancing method positions in the default six repetitions. Other configured repetition counts are deterministic but may be unbalanced.
- Exact gain evaluations are counted from the exact-evaluation dictionary returned at each planning call in a separate structural pass. No exact-call counter is installed during primary timing.
- Memory is a separate `tracemalloc` pass with no timing metrics. It reports Python allocations created inside `explore`, including output paths/result and wrapper allocations, excluding pre-created input copies. It is **not** process RSS, total machine memory or only cache memory.
- No runs execute concurrently. Failures/interruptions retain partial files. A unique run ID is required; rerunning never overwrites existing evidence.

## Summaries and figures

`records.jsonl` is the raw source; `records.csv` includes all successful and failed records. Structural records retain full outcomes. Manifest contains commit, source/config byte hashes, OS/architecture/CPU/Python/clock, complete config and run purpose. `summary.csv` provides per-map/per-method repetition median, minimum, maximum and quartiles, exact evaluations and separate peak memory.

For each grid size/density, reduce repetitions to a median per map/method, then take the geometric mean across maps. Speedups are paired map-level median ratios A/B, A/C*, B/C*; values above 1 favor the denominator. Resample maps, not individual repetitions, for 2000 fixed-seed percentile bootstrap replicates (seed 20261102). With three seeds per size, intervals have limited inferential strength. Zero-time ratios are marked undefined; a size group is not silently computed using only its remaining maps.

The headless Matplotlib Agg backend writes `timing`, `speedup`, `exact_evaluations`, `python_memory` as both PNG and PDF. Timing/speedup have separate planning/episode panels. Memory figures are omitted if the committed config disables that pass. The plot command re-analyzes raw files, verifies the complete record matrix/input hashes/outcome agreement, and refuses comparison plots when data are failed, partial, duplicated or malformed. No experiment is rerun to adjust a figure.

Do not merge timings across different computers/Python builds. Compare A/B/C* within the laptop run and later within the iMac run. Source/version/workload matching is necessary to discuss cross-machine differences. This runner does not tune parameters based on observed performance.

References for implementation APIs: [Python high-resolution timers](https://docs.python.org/3/library/time.html#time.perf_counter_ns), [tracemalloc](https://docs.python.org/3/library/tracemalloc.html), [Matplotlib non-interactive backends](https://matplotlib.org/stable/users/explain/figure/backends.html).

## Validation

See `docs/BASICCODE_RUNBOOK.md` for Windows PowerShell and macOS commands. Infrastructure verification uses tiny smoke data and injected failures, never the default performance workload. Local checks and retained smoke runs are recorded in `docs/EXPERIMENT_LOG.md`; they cannot establish an A/B/C* speedup.
