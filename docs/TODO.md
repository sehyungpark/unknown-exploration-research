# TODO

Last updated: 2026-09-14

## P0 — Before Any Implementation

- [ ] Search and document the closest prior work for Candidate 1, including lazy evaluation, caching, NBV, informative planning, and relevant submodular optimization results.
- [ ] State Candidate 1's difference from the closest prior work in one sentence without making an unsupported novelty claim.
- [ ] Define the exact candidate set, candidate lifecycle, gain function \(G_t(v)\), travel cost, score, upper bound, and deterministic tie-breaking rule.
- [ ] Prove the monotonicity conditions or record a counterexample and revise the hypothesis.
- [ ] Specify bounds for newly generated candidates and how bounds are invalidated or updated.
- [ ] Freeze the correctness condition: exact argmax match and selected target sequence match against exhaustive NBV.

## P1 — Common Simulator Specification

- [ ] Decide 4-neighbor versus 8-neighbor movement and its cost convention.
- [ ] Specify ray casting, angular/ray discretization, endpoint behavior, occlusion, and sensing range.
- [ ] Specify candidate generation independently of frontier-only assumptions.
- [ ] Define deterministic map fixtures: open, single room, corridor, dead end, separated rooms, clutter, and maze-like.
- [ ] Freeze metric definitions, coverage targets, failure conditions, run metadata schema, and raw-result storage layout.
- [ ] Preregister the first correctness and sanity-check experiment, including fixed map instances and seeds.

## P2 — Implementation After P0/P1 Approval

- [ ] Implement the smallest deterministic common simulator and correctness tests.
- [ ] Implement exhaustive NBV as the shared reference baseline.
- [ ] Implement Candidate 1 lazy evaluation on the shared simulator.
- [ ] Verify 100% argmax and target-sequence agreement before efficiency or scaling experiments.

## Deferred

- [ ] Candidate 3 prototype after Candidate 1's initial evaluation.
- [ ] Candidate 2 prototype after Candidate 3.
- [ ] Candidate 4 prototype after Candidate 2.
- [ ] Comparative evaluation and final research-topic selection.
