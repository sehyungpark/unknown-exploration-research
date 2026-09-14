# TODO

Last updated: 2026-09-14

## P0 — Before Any Implementation

- [x] Complete and document a focused prior-art review covering lazy evaluation, caching, NBV, informative planning, and relevant submodular optimization results.
- [x] Formalize a provisional one-sentence distinction from APN without asserting novelty.
- [x] Define the candidate set, lifecycle, gain \(G_t(v)\), travel cost, score, upper bound, and deterministic tie-aware selection rule symbolically.
- [x] Prove conditional admissibility and record counterexamples outside the assumptions.
- [x] Prove initial bounds for newly generated candidates and specify cache/index invalidation rules.
- [x] State the exact single-cycle correctness certificate against deterministic exhaustive NBV.
- [ ] Validate the APN distinction against the full method, not only the focused reviewed material.
- [ ] Perform citation-chained novelty validation for an equivalent change-aware admissible NBV bound and exact-selection certificate.
- [ ] Decide and record whether Candidate 1 passes the novelty gate.

## P1 — Common Simulator Specification

- [ ] Decide 4-neighbor versus 8-neighbor movement and its cost convention.
- [ ] Specify ray casting, angular/ray discretization, endpoint behavior, occlusion, and sensing range.
- [ ] Specify candidate generation independently of frontier-only assumptions.
- [ ] Specify immutable candidate identity, persistent-ID rules, eligibility transitions, and total tie order.
- [ ] Define deterministic map fixtures: open, single room, corridor, dead end, separated rooms, clutter, and maze-like.
- [ ] Convert the formulation's minimal counterexamples into deterministic test specifications.
- [ ] Specify how atomic planning snapshots handle observations received during movement or selection.
- [ ] Freeze metric definitions, coverage targets, failure conditions, run metadata schema, and raw-result storage layout.
- [ ] Preregister the first correctness and sanity-check experiment, including fixed map instances and seeds.

## P2 — Implementation After P0/P1 Approval

- [ ] Obtain an explicit implementation go/no-go decision after the novelty and specification gates.
- [ ] Implement the smallest deterministic common simulator and correctness tests.
- [ ] Implement exhaustive NBV as the shared reference baseline.
- [ ] Implement Candidate 1 lazy evaluation on the shared simulator.
- [ ] Verify 100% argmax and target-sequence agreement before efficiency or scaling experiments.

## Deferred

- [ ] Candidate 3 prototype after Candidate 1's initial evaluation.
- [ ] Candidate 2 prototype after Candidate 3.
- [ ] Candidate 4 prototype after Candidate 2.
- [ ] Comparative evaluation and final research-topic selection.
