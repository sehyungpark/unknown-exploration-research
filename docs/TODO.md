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
- [ ] Freeze Experiment 0's random small-map generator, map count, seed list, acceptance policy, and safety limits.
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
- [ ] Implement stale-scalar lazy evaluation using the last exact gain as an upper bound.
- [ ] Implement Candidate 1 cached visible-unknown sets and inverse-incidence bound maintenance.
- [ ] Implement tie-aware exact-selection certificate.
- [ ] Verify 100% argmax agreement with exhaustive NBV on all deterministic correctness tests.
- [ ] Verify 100% target-sequence agreement on exploratory runs before any speed claim.

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
