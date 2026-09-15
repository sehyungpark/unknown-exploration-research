# TODO

Last updated: 2026-09-15

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
- [ ] Freeze metric definitions, coverage targets, failure conditions, run metadata schema, and raw-result storage layout.
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
- [ ] Implement the Experiment 0 cross-method cycle logger and immutable failure-artifact writer when Algorithms B/C are available.
- [x] Implement stale-scalar lazy evaluation using the last exact gain as an upper bound.
- [x] Implement Candidate 1 cached visible-unknown sets and inverse-incidence bound maintenance.
- [x] Implement Algorithm C Stage 1 state-only cache/index representation, safe diagnostics, reset lifecycle, and invariant validation.
- [x] Implement Algorithm C Stage 2 atomic exact cached-set installation/replacement, complete old inverse-membership removal, shared-membership preservation, empty-key cleanup, and fresh-bound reset.
- [x] Implement Algorithm C Stage 3 explicit UNKNOWN-to-known processing, once-per-revelation bound decrement, duplicate protection, historical-membership preservation, validation, and atomic rollback.
- [x] Integrate Algorithm C immutable belief-snapshot delta discovery, revelation synchronization, and existing optimistic-visibility exact refresh with the Stage 2-3 cache APIs.
- [x] Verify on actual belief transitions that maintained bounds equal cached-set/current-UNKNOWN intersections, dominate exact current gain, may be strictly loose after a new OCCUPIED blocker, and return to equality after exact refresh.
- [x] Implement the stateful Algorithm C selector with pre-bound belief synchronization, one current Dijkstra, first-seen exact initialization, change-aware upper scores, deterministic optimistic reevaluation, tie-aware certification, current-exact selection, and all-zero-bound completion.
- [x] Add focused Stage 5 lifecycle, diagnostics, strict-slack, reset, tie-certificate, and small frozen-snapshot A/C checks.
- [ ] Run the full seven-fixture A/C exact-equivalence development regression.
- [ ] Run the full frozen-v2 60-map A/C exact-equivalence development regression.
- [x] Implement and directly test Algorithm B's tie-aware exact-selection certificate against the exhaustive total rank order.
- [x] Verify A/B 100% argmax agreement through complete runs on all seven fixed fixtures and all 60 frozen v2 random maps.
- [x] Verify A/B 100% target-sequence and termination agreement in development regressions before any speed claim.
- [x] Verify Algorithm B stale-bound admissibility externally against Algorithm A on every shared regression snapshot.
- [x] Demonstrate at least one deterministic case of safe exact-evaluation skipping without interpreting it as a performance result.
- [x] Harden Algorithm B's episode lifecycle with explicit idempotent reset, configuration preservation, first-seen reinitialization, and cross-environment leakage tests.

## P3 — Empirical Value Gate

- [ ] Compare stale-scalar versus change-aware bound tightness over planning cycles.
- [ ] Compare exact gain evaluation counts and total ray work.
- [ ] Compare total planning wall-clock time including all bookkeeping overhead.
- [ ] Measure memory scaling versus candidate density and sensing range.
- [ ] Measure path length and coverage/time to 90%, 95%, and 99% as sanity checks that exact decision equivalence is preserved.
- [ ] Decide **GO / MODIFY / DROP** for Candidate 1 based on total computational benefit, not raycast count alone.

## Deferred

- [ ] Candidate 3 prototype after Candidate 1's initial empirical gate.
- [ ] Candidate 2 prototype after Candidate 3.
- [ ] Candidate 4 prototype after Candidate 2.
- [ ] Comparative evaluation and final research-topic selection.
