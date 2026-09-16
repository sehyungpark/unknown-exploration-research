# Experiment Log

This is an append-only record. Failed, unfavorable, incomplete, and non-reproducible experiments must remain in the log.

For new runs, record at least: date/time, run ID, code/algorithm version, map family and instance ID, map seed, start seed, map size, movement model, sensor configuration, algorithm, parameters, completion target, metrics, raw-result location, runtime, success/failure, failure reason, and interpretation.

## Legacy Records Recovered from `RESEARCH_CONTEXT.md`

These entries predate this log. Missing values are explicitly marked rather than inferred.

### LEGACY-C1 — Candidate 1 Toy Sanity Check

- **Date/time:** Not recorded
- **Status:** Preliminary evidence; not reproducible from current repository
- **Map conditions:** 31×31 toy maps; rooms, clutter, and maze families
- **Map instance IDs:** Not recorded
- **Random seeds:** Not recorded
- **Start seeds/positions:** Not recorded
- **Algorithm:** Exhaustive NBV versus Candidate 1 lazy NBV prototype
- **Algorithm/code version:** Not recorded; code unavailable
- **Parameters:** Not recorded
- **Reported results:** Same target sequence and moves; exact gain evaluations reduced by approximately 82%, 87%, and 96% across the reported toy cases
- **Raw results/runtime:** Not recorded
- **Failure:** No mismatch reported; reproducibility metadata is missing
- **Interpretation:** Sanity-check evidence only, not a publication result or a verified repository result

### LEGACY-C2 — Candidate 2 Synthetic Prediction Check

- **Date/time:** Not recorded
- **Status:** Preliminary evidence; not reproducible from current repository
- **Map conditions:** Synthetic corrupted prediction; exact maps and corruption settings not recorded
- **Map instance IDs/random seeds:** Not recorded
- **Algorithm:** Blind predictor, robust baseline, and robust-gate prototype
- **Algorithm/code version:** Not recorded; code unavailable
- **Parameters:** Not recorded
- **Reported results:** Blind prediction could fail; baseline and robust gate succeeded in the toy tests
- **Raw results/runtime:** Not recorded
- **Failure:** Blind predictor failures were observed; individual failure cases and reasons were not recorded
- **Interpretation:** Suggests avoidance of catastrophic prediction failure, but does not establish consistently shorter paths

### LEGACY-C3 — Candidate 3 Sequential Sensing Check

- **Date/time:** Not recorded
- **Status:** Preliminary evidence; not reproducible from current repository
- **Map/sensor conditions:** Not recorded
- **Map instance IDs/random seeds:** Not recorded
- **Algorithm:** Simple sequential evidence accumulation versus fixed repeated sensing
- **Algorithm/code version:** Not recorded; code unavailable
- **Parameters:** Not recorded
- **Reported results:** Sequential evidence accumulation reportedly required substantially fewer sensor evaluations
- **Raw results/runtime:** Not recorded
- **Failure:** No run failure reported; theoretical certification is incomplete
- **Interpretation:** Motivating observation only; the stopping rule has not been justified as a rigorous confidence-sequence theorem

### LEGACY-C4 — Candidate 4 Low-Recourse Repair Check

- **Date/time:** Not recorded
- **Status:** Preliminary and unfavorable evidence; not reproducible from current repository
- **Map conditions:** Some toy maps; exact families and instances not recorded
- **Map instance IDs/random seeds:** Not recorded
- **Algorithm:** Fresh greedy cover versus low-recourse repair prototype
- **Algorithm/code version:** Not recorded; code unavailable
- **Parameters:** Not recorded
- **Reported results:** Low-recourse repair reduced recourse but substantially increased viewpoint count on some maps
- **Raw results/runtime:** Not recorded
- **Failure:** Quality degradation occurred on unspecified maps; exact thresholds and cases were not recorded
- **Interpretation:** Candidate 4 remains high risk; reducing recourse alone is not sufficient evidence of success

## New Experiments

### EXPERIMENT0-FORMAL-20260916-001 — First Formal Preregistered Experiment 0 Execution

- **Execution date:** 2026-09-16
- **Invocation ID:** `experiment0-formal-20260916-001`
- **Status:** **PASS**
- **Execution revision:** `b8597a9453fe2a6e011098c8da2c9a0a96e2fb7a`
- **Runner version:** `experiment-0-runner-v1`
- **Dataset:** Seven deterministic fixtures plus 60 frozen `experiment-0-random-v2` maps; 67 total complete runs. Frozen map IDs, seeds, starts, sizes, density targets, acceptance metadata, hashes, and cycle limits are recorded in `configs/experiment_0_random_maps.json` and the formal manifest.
- **Map conditions:** Static 20×20 deterministic fixtures and frozen 12×12, 16×16, and 20×20 random maps, with 20 accepted maps per random-map size. Agent pose is exact; SLAM and localization error are excluded.
- **Movement model:** Legal 8-neighbor known-FREE motion with orthogonal cost `1`, diagonal cost `sqrt(2)`, and no diagonal corner cutting.
- **Sensor configuration:** Fixed range `R=8`; deterministic corner-inclusive, endpoint-inclusive supercover; UNKNOWN-transparent optimistic planning visibility and first-hit OCCUPIED physical occlusion.
- **Algorithms:** A exhaustive optimistic NBV; B stale-scalar certified exact-lazy NBV; C change-aware cached-set certified exact-lazy NBV. One shared environment and planning snapshot were used per run in A→B→C evaluation order.
- **Completion target:** Identical A/B/C selected target at every planning snapshot and identical complete target/STOP sequence, with explicit `EXPLORATION_COMPLETE` termination for every map.
- **Planning snapshots:** **1,185** total; **1,118** selected snapshots and **67** terminal snapshots.
- **Target agreement:** **100%**. A/B target mismatches: **0**; A/C: **0**; B/C: **0**.
- **Sequence agreement:** **100%**. Complete sequence divergences: **0**.
- **Other correctness results:** Termination mismatches: **0**; selected gain/distance/score/path mismatches: **0**; candidate-domain/distance mismatches: **0**; B bound violations: **0**; C bound violations: **0**; B tie-certificate violations: **0**; C tie-certificate violations: **0**; C cache/index invariant violations: **0**; supported `ChangeAwareGainBoundViolation` events: **0**; unsupported assumption/lifecycle failures: **0**; safety-limit exhaustions: **0**; malformed records: **0**; unexpected exceptions: **0**.
- **Exact-gain evaluation diagnostics:** A **215,939**; B **40,764**; C **20,578**.
- **Raw result:** `results/experiment_0/runs/experiment0-formal-20260916-001/`
- **Runtime:** Approximately 21 minutes 35 seconds from formal manifest creation to summary write; retained as execution metadata only.
- **Failure reason/artifact:** None; `failure_run_id` is null and no failure directory exists for this passing invocation.
- **Interpretation:** Experiment 0 is a correctness experiment. It establishes empirical exact-equivalence on the preregistered correctness dataset, not a mathematical proof of global equivalence. No wall-clock, memory, speedup, or efficiency conclusion is drawn from this result.
