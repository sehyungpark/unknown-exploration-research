# TODO

Last updated: 2026-09-14

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

- [ ] Decide 4-neighbor versus 8-neighbor movement and its cost convention.
- [ ] Specify ray casting, angular/ray discretization, endpoint behavior, UNKNOWN transparency, physical occlusion, and sensing range.
- [ ] Specify candidate generation independently of frontier-only assumptions.
- [ ] Specify immutable candidate identity, persistent-ID rules, eligibility transitions, and total tie order.
- [ ] Define deterministic map fixtures: open, single room, corridor, dead end, separated rooms, clutter, and maze-like.
- [ ] Convert formulation counterexamples into deterministic unit-test specifications.
- [ ] Specify atomic planning-snapshot semantics, including what happens to observations received during movement or selection.
- [ ] Freeze metric definitions, coverage targets, failure conditions, run metadata schema, and raw-result storage layout.
- [ ] Preregister first correctness/efficiency experiment with fixed maps and seeds.
- [ ] Specify required baselines: exhaustive optimistic NBV, stale-scalar lazy bound, and proposed change-aware cached-set bound.
- [ ] Specify resource metrics: exact gain evaluations, ray operations, planning wall time, distance time, bound/index maintenance time, peak memory, cached-set size, inverse-index size.

## P2 — Minimal Implementation After P1 Approval

- [ ] Implement the smallest deterministic common simulator and theorem-derived correctness tests.
- [ ] Implement exhaustive optimistic NBV as the reference evaluator.
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
