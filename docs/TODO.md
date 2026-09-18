# TODO

Last updated: 2026-09-19

## P0 — Research Gates Before Implementation

- [x] Complete and document focused prior-art review covering lazy evaluation, caching, NBV, informative planning, and relevant submodular optimization results.
- [x] Formalize Candidate 1's exact candidate set, lifecycle, gain, travel cost, score, upper bound, and deterministic tie-aware selection rule.
- [x] Prove conditional admissibility and record counterexamples outside the assumptions.
- [x] Prove initial bounds for newly generated candidates and specify cache/index invalidation rules.
- [x] State the exact single-cycle correctness certificate against deterministic exhaustive optimistic NBV.
- [x] Validate the APN distinction against the reviewed full method.
- [x] Perform broader/citation-chained novelty validation including AEP, APN, SEE++, FrontierNet, hierarchical NBV, recent upper-bound pruning work, and adjacent bounded-IG methods.
- [x] Record novelty-gate decision: **PROVISIONAL PASS — HIGH RISK, NARROW CLAIM ONLY**.

## P1 — Common Simulator and Preregistered Test Specification

- [x] Decide 8-neighbor movement with orthogonal cost `1`, diagonal cost `sqrt(2)`, and no corner cutting.
- [x] Specify and implement fixed supercover traversal, endpoint/corner behavior, UNKNOWN transparency, physical occlusion, and sensing range `R=8`.
- [x] Specify deterministic candidate generation independently of frontier-only assumptions.
- [x] Specify immutable coordinate identity, eligibility transitions, and the total tie order.
- [x] Define deterministic 20x20 fixtures: open, single room, corridor, dead end, separated rooms, clutter, and maze-like.
- [x] Convert the opaque-UNKNOWN and new-occluder cases into deterministic tests.
- [x] Specify and test atomic planning snapshots with sensing only at arrival and no sensing while moving.
- [x] Freeze Experiment 1 metric definitions, coverage targets, failure conditions, run metadata schema, raw-result storage layout, timing/memory protocols, and analysis rules before execution.
- [x] Preregister Experiment 0 exact-equivalence correctness endpoints, shared conditions, logging fields, failure rules, and gate.
- [x] Complete the initial Experiment 0 v1 random-dataset freeze; later invalidate it before execution because its component-fraction denominator was incorrect.
- [x] Correct acceptance to largest component / all grid cells, add a denominator-distinguishing counterexample, and refreeze the same master-seed stream as `experiment-0-random-v2`.
- [x] Freeze Experiment 0's per-cycle field schema, canonical belief/map hashes, B/C placeholders, and non-overwriting failure-artifact layout.
- [x] Add deterministic regeneration and frozen-artifact tests covering the dataset, rejection rules, starts, cycle limits, and hashes.
- [x] Specify required baselines: exhaustive optimistic NBV, stale-scalar lazy bound, and proposed change-aware cached-set bound.
- [x] Specify resource metrics: exact gain evaluations, ray operations, planning wall time, distance time, bound/index maintenance time, peak memory, cached-set size, inverse-index size.

## P2 — Minimal Implementation After P1 Approval

- [x] Implement the smallest deterministic common simulator and theorem-derived correctness tests.
- [x] Implement exhaustive optimistic NBV as the reference evaluator.
- [x] Correct physical first-hit handling for blocked target rays and retain a regression test.
- [x] Verify physical/planning corner-occlusion behavior through visibility APIs.
- [x] Check set-level admissibility across 38,673 deterministic and fixed-seed transitions.
- [x] Run every deterministic fixture twice to explicit stop with identical traces and invariant checks.
- [x] Accept the exhaustive reference as the current correctness oracle after the 39-test suite passes.
- [x] Implement the Stage 7 formal shared A/B/C Experiment 0 runner, exact frozen cycle schema/serializer, non-overwriting invocation logs, immutable six-file failure artifacts, stable failure classifications, and guarded single-map reproduction mode.
- [x] Add direct external B/C bound and tie-certificate validation, C cache/index and membership validation, precise pre-plan inverse-incidence decrement counting, terminal snapshot logging, and fail-fast no-movement-before-agreement behavior.
- [x] Validate Stage 7 infrastructure only with canonical serialization/writer tests, synthetic `stage7-smoke` shared runs, and fault-injected mismatch/bound/cache/safety/malformed cases in temporary directories; preserve the unexecuted formal-workload guard.
- [x] Stage 8: execute the first formal 7-fixture + 60-map Experiment 0 invocation, retain all success/failure output, and require zero target, sequence, selected-value/path, candidate-domain/distance, bound, tie, or cache/index violations. **PASS** on 2026-09-16 at revision `b8597a9453fe2a6e011098c8da2c9a0a96e2fb7a`.
- [x] Implement stale-scalar lazy evaluation using the last exact gain as an upper bound.
- [x] Implement Candidate 1 cached visible-unknown sets and inverse-incidence bound maintenance.
- [x] Implement Algorithm C Stage 1 state-only cache/index representation, safe diagnostics, reset lifecycle, and invariant validation.
- [x] Implement Algorithm C Stage 2 atomic exact cached-set installation/replacement, complete old inverse-membership removal, shared-membership preservation, empty-key cleanup, and fresh-bound reset.
- [x] Implement Algorithm C Stage 3 explicit UNKNOWN-to-known processing, once-per-revelation bound decrement, duplicate protection, historical-membership preservation, validation, and atomic rollback.
- [x] Integrate Algorithm C immutable belief-snapshot delta discovery, revelation synchronization, and existing optimistic-visibility exact refresh with the Stage 2-3 cache APIs.
- [x] Verify on actual belief transitions that maintained bounds equal cached-set/current-UNKNOWN intersections, dominate exact current gain, may be strictly loose after a new OCCUPIED blocker, and return to equality after exact refresh.
- [x] Implement the stateful Algorithm C selector with pre-bound belief synchronization, one current Dijkstra, first-seen exact initialization, change-aware upper scores, deterministic optimistic reevaluation, tie-aware certification, current-exact selection, and all-zero-bound completion.
- [x] Add focused Stage 5 lifecycle, diagnostics, strict-slack, reset, tie-certificate, and small frozen-snapshot A/C checks.
- [x] Harden Stage 5 exact reevaluation to capture the maintained bound before pure exact computation, fail fast before installation on `G_exact > q_before`, preserve the full cache atomically on violation, retain diagnostic context, and keep the independent post-refresh tightness check. The impossible negative case is deliberately fault-injected; no supported-run violation has been observed and no exhaustive fallback is used.
- [x] Run the full seven-fixture A/C exact-equivalence development regression: 7/7 runs and 89 shared planning snapshots passed with zero target, status/termination, selected-value, path, or maintained-bound mismatch; safe exact-evaluation skipping was observed.
- [x] Run the full frozen-v2 60-map A/C exact-equivalence development regression: 60/60 runs and 1,096 shared planning snapshots passed after frozen metadata regeneration checks, with zero target, status/termination, selected-value, path, or maintained-bound mismatch; safe exact-evaluation skipping was observed.
- [x] Implement and directly test Algorithm B's tie-aware exact-selection certificate against the exhaustive total rank order.
- [x] Verify A/B 100% argmax agreement through complete runs on all seven fixed fixtures and all 60 frozen v2 random maps.
- [x] Verify A/B 100% target-sequence and termination agreement in development regressions before any speed claim.
- [x] Verify Algorithm B stale-bound admissibility externally against Algorithm A on every shared regression snapshot.
- [x] Demonstrate at least one deterministic case of safe exact-evaluation skipping without interpreting it as a performance result.
- [x] Harden Algorithm B's episode lifecycle with explicit idempotent reset, configuration preservation, first-seen reinitialization, and cross-environment leakage tests.

## P3 — Empirical Value Gate

- [x] Design and preregister Experiment 1 before execution, including the 27-map dataset, seed stream, nine-map timing subset, timing warm-up/order/repetitions, separate memory pass, resource counters, failure handling, raw-result layout, bootstrap, and GO/MODIFY/DROP rules.
- [x] Add Pre-execution Amendment 1 before observing any Experiment 1 result, preserving the original Stage 9 wording while making CORRECTNESS_REOPENED / GO / MODIFY / DROP mutually exclusive and deterministic; keep memory and scaling as reported tradeoffs rather than decision overrides.
- [x] Stage 10: implement the guarded `experiment-1-runner-v1` measurement runner and canonical serializers without changing Algorithms A/B/C or simulator semantics; formal Experiment 1 remains NOT EXECUTED.
- [x] Add benchmark-only forwarding instrumentation for exact visibility work and internal time decomposition; prove it preserves canonical decisions and counters on synthetic/nonformal inputs.
- [x] Add non-overwriting success/failure writers and schema validation for all six frozen Experiment 1 output files; no formal run was created during infrastructure validation.
- [ ] Execute the first formal Experiment 1 invocation only after Stage 10 acceptance and a clean full suite/CI; retain every raw repetition and failure.
- [ ] Compare stale-scalar versus change-aware bound tightness over planning cycles.
- [ ] Compare exact gain evaluation counts and total ray work.
- [ ] Compare total planning wall-clock time including all bookkeeping overhead.
- [ ] Measure memory scaling versus candidate density and sensing range.
- [ ] Measure path length and coverage/time to 90%, 95%, and 99% as sanity checks that exact decision equivalence is preserved.
- [ ] Apply Pre-execution Amendment 1 exactly, with no post-result override: correctness first, then the all-three aggregate visibility-work gate, then the paired C/B timing-interval boundaries.

## P4 — Algorithm C* Redesign

- [x] Implement C* as a separate planner without changing historical A/B/C semantics or Experiment 0/1 artifacts.
- [x] Replace eager per-revelation candidate-bound decrements with stale admissible bounds and top-only lazy change-aware refresh.
- [x] Replace persistent visible-UNKNOWN sets and current UNKNOWN state with exact row-major Python-int bitmasks.
- [x] Add exact sensor-range-mask upper bounds so first-seen candidates can be pruned before any exact visibility evaluation.
- [x] Remove inverse-incidence/reported-known/full-snapshot-diff maintenance from the C* production path; require explicit revelation deltas after initialization.
- [x] Preserve one current Dijkstra per planning snapshot, the frozen score/tie order, canonical exact visibility, and the invariant that every selected C* target is current-exact.
- [x] Separate C* production/core timing from full debug/audit verification timing; never estimate core time by subtracting audit overhead after the fact.
- [x] Add bitmask/range-bound/lifecycle/timing unit coverage plus complete A/C* shared-snapshot regressions on all seven fixtures and all 60 frozen `experiment-0-random-v2` maps.
- [x] Verify the full GitHub Actions CI suite passes on the C* branch (`59cdf4530859ee3f432b7b5175185f5bb828a148`).
- [x] Add focused behavioral regressions that explicitly force first-seen range-only pruning and stale-bound refresh/reinsert paths, in addition to the full A/C* regressions.
- [ ] Preregister a new C* efficiency experiment before observing formal C* timing results; use fresh holdout maps rather than treating already-seen Experiment 1 maps as an unbiased final test set.
- [ ] In the follow-up experiment, compare A/B/C/C* exact work, range-bound work, lazy-refresh counts, core planner time, audit time, memory, and scaling while preserving exact A-equivalence as a hard gate.

## Deferred

- [ ] Candidate 3 prototype after Candidate 1's initial empirical gate.
- [ ] Candidate 2 prototype after Candidate 3.
- [ ] Candidate 4 prototype after Candidate 2.
- [ ] Comparative evaluation and final research-topic selection.
