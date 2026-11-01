# basiccode A/B/C* benchmark protocol

## Scope fixed before measuring

- Candidate: Candidate 1, the standalone `basiccode` implementation.
- Phase: correctness/infrastructure validation followed by a user-run exploratory timing/scaling benchmark. This is not formal Experiment 2 and introduces no new algorithm or novelty claim.
- Closest existing mechanism: `src/evaluation/experiment_2_runner.py` already separates correctness, work, timing and memory. This runner applies that measurement separation to the different 4-neighbor/per-movement-step-sensing `basiccode` contract.
- Shared components: use each algorithm's actual `explore()` and the existing common simulator. The user-selected large-map generator below replaces only input generation; smoke/legacy configs retain `nbv_common.generate_map`. Do not change baseline search structures or use the `src` planners as substitutes.
- Correctness condition: complete `ExplorationResult` (all targets, scores, gains, distances, planned/actual paths, costs, termination) and final known map equal A. Compare the structural, warm-up, timed and memory episodes to A's structural outcome outside timing.
- Hypothesis: B/C* preserve A's decisions while reducing exact gain evaluations and possibly runtime. No speedup threshold is enforced. Fewer evaluations with slower runtime refutes the runtime benefit on this workload; slower and failed cases remain in the raw data.
- Scientific scope: the fixed seed list is small. This produces machine-specific exploratory evidence, not a new universal efficiency guarantee or a reclassification of the completed C* Experiment 2.

## Workload

The user-corrected default is **`configs/basiccode_large_v1.json`**: 100/200/300/400/500 square grids, target obstacle densities 0.1/0.2/0.3/0.4/0.5, seeds 42/43/44, R=4, one warm-up and **five** timed repetitions per method. The 25 size-density conditions give 75 maps, 1125 timed episodes, 225 warm-ups, 225 structural episodes, 225 separate memory episodes and 21 sanity episodes: **1821 total**. No default large experiment has been run locally.

`configs/basiccode_benchmark_v1.json` remains the historical 10/15/20, p=0.20, six-repetition configuration. It is no longer the default and was never executed as a full performance workload. Its existence does not override the user's large-map specification.

`--smoke` always uses `configs/basiccode_smoke_v1.json`: two tiny maps, R=2, two timed repetitions, 51 episodes including the same seven sanity families. Its outputs and every figure are labeled **SMOKE VALIDATION - NOT PERFORMANCE EVIDENCE**. It may run on uncommitted development code. Non-smoke runs require committed, clean algorithm/runner/test/config/requirements source. Result files and research notes may remain untracked.

All requested maps and sanity inputs are saved to `maps.json` before the first performance measurement. Every algorithm receives fresh copies of exactly the same truth and all-UNKNOWN initial map, start and sensor range. Generation failure blocks measurement and is never replaced with another seed. Seven sanity families gate the invocation; each benchmark map then passes its own A/B/C* equality gate immediately before its measurements. This saves earlier map measurements before starting expensive larger-map correctness checks.

### User-selected constructive generator

IID Bernoulli rejection with all FREE connected and every WALL adjacent to FREE becomes impractical at large sizes/densities. The user explicitly selected a generator that guarantees those two properties while matching target density. `benchmarks/basiccode_maps.py:connected_map`, version `connected_dominating_v1`, therefore defines a **structured connected/dominating-scaffold family, not an IID random-obstacle distribution**.

Free rows separated by at most two other rows plus one free spine form a connected dominating scaffold. Rotation/reflections/spine depend only on seed. Uniformly shuffle the remaining eligible cells and make exactly `round(size*size*density)` of them walls. Every other free cell and every wall touches the scaffold, proving FREE connectivity and physical wall observability for R>=1. All requested large sizes/densities have integer wall counts, so actual density equals the requested value. Metadata saves scaffold, transformations, realized density/counts and generator version. The same seed uses nested obstacle sets and the same scaffold start across densities. The generator has no access to algorithm scores or runtimes.

The 1000-attempt setting applies only to legacy/smoke rejection generation and is unused by the constructive generator. Neither the constructive geometry nor the 100-500 benchmark has been experimentally validated locally in this update; small deterministic generator/correctness tests were added for the user's Check command and CI. Do not pool this map family with IID rejection results as if they came from the same distribution.

The seven tiny sanity families (open, single room, corridor, dead end, separated rooms, clutter, maze-like) run only as correctness checks at R=2 and are never pooled into the timing/scaling graphs. Some fixtures can terminate with remaining UNKNOWN; agreement and successful full reconstruction are separate facts. All benchmark terminations and remaining UNKNOWN counts are retained.

## Measurement boundaries

- A wrapper times the original `evaluate_candidates` with `perf_counter_ns`. This includes BFS, range/cache/heap work and C*'s pending UNKNOWN-mask synchronization.
- The episode clock surrounds the original `explore`. It includes initial observation, every movement scan, C*'s newly-known bookkeeping, cache initialization, result construction and the small timer wrapper overhead. Input copies, parameter setup, output, reference comparisons, hashing and file writes are outside both clocks. Planner time and episode time are distinct metrics.
- Cold episode caches are initialized by the existing `explore` every run. Warm-up warms interpreter/allocator execution, not reusable planner state. Five repetitions use five of the six permutations per map. Across the three seeds in each size-density condition, omit ABC/BCA/CAB respectively, so each method occupies each execution position exactly five times across that condition. Saved per-case offsets let analysis validate the actual order. Legacy six-repetition runs use all permutations; smoke remains tiny and non-inferential.
- Exact gain evaluations are counted from the exact-evaluation dictionary returned at each planning call in a separate structural pass. No exact-call counter is installed during primary timing.
- Memory is a separate `tracemalloc` pass with no timing metrics. It reports Python allocations created inside `explore`, including output paths/result and wrapper allocations, excluding pre-created input copies. It is **not** process RSS, total machine memory or only cache memory.
- No runs execute concurrently. Failures/interruptions retain partial files. A unique run ID is required; rerunning never overwrites existing evidence.

## Summaries and figures

`records.jsonl` is the raw source; `records.csv` includes all successful and failed records. A's structural records retain full outcomes; successful B/C* outcomes are compared in memory and retain hashes, while failed outcomes are preserved in full. Only the current map's reference is kept during execution. Analysis streams JSONL and validates full-outcome hashes without retaining all trajectories in memory. Historical full-outcome records remain supported. Manifest contains commit, source/config byte hashes, OS/architecture/CPU/Python/clock, config, order offsets and purpose. `summary.csv` includes generator/actual density and per-map/per-method repetition median, minimum, maximum, quartiles, exact evaluations and separate peak memory.

For each grid size/density, reduce repetitions to a median per map/method, then take the geometric mean across maps. Speedups are paired map-level median ratios A/B, A/C*, B/C*; values above 1 favor the denominator. Resample maps, not individual repetitions, for 2000 fixed-seed percentile bootstrap replicates (seed 20261102). With three seeds per size, intervals have limited inferential strength. Zero-time ratios are marked undefined; a size group is not silently computed using only its remaining maps.

The headless Matplotlib Agg backend writes `timing`, `speedup`, `exact_evaluations`, `python_memory` as both PNG and PDF. **Each density has its own panel**; timing/speedup also separate planning/episode rows. Memory figures are omitted if the committed config disables that pass. The plot command re-analyzes raw files, verifies the complete record matrix/input hashes/outcome agreement, and refuses comparison plots when data are failed, partial, duplicated or malformed. No experiment is rerun to adjust a figure.

The requested 500x500 workload is computationally substantial. In particular, exhaustive A evaluates many candidates and C* retains global-index Python integer bitsets; candidate count and map area can both increase memory/work. No completion-time or laptop-RAM feasibility estimate is available. Algorithms are not silently optimized, replaced, capped or omitted to make the large workload look successful. There is no automatic resume or per-episode timeout; completed raw episodes remain saved if interrupted.

Do not merge timings across different computers/Python builds. Compare A/B/C* within the laptop run and later within the iMac run. Source/version/workload matching is necessary to discuss cross-machine differences. This runner does not tune parameters based on observed performance.

References for implementation APIs: [Python high-resolution timers](https://docs.python.org/3/library/time.html#time.perf_counter_ns), [tracemalloc](https://docs.python.org/3/library/tracemalloc.html), [Matplotlib non-interactive backends](https://matplotlib.org/stable/users/explain/figure/backends.html).

## Validation

See `docs/BASICCODE_RUNBOOK.md` for Windows PowerShell and macOS commands. Infrastructure verification uses tiny smoke data and injected failures, never the default performance workload. Local checks and retained smoke runs are recorded in `docs/EXPERIMENT_LOG.md`; they cannot establish an A/B/C* speedup.
