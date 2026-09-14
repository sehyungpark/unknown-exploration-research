# Project State

Last updated: 2026-09-15

## Current Research Stage

- Four candidate research directions have been selected.
- No final candidate has been chosen yet.
- Candidate 1 is being investigated first.
- Candidate 1 has passed a **conditional theory gate**.
- Candidate 1 has received a **provisional novelty pass with high risk and a narrow claim only** after full-method comparison with major close prior art.
- The empirical-value gate remains open.
- The minimal deterministic common simulator and exhaustive optimistic-NBV reference are implemented and pass the current correctness suite.
- Stale-scalar lazy and proposed change-aware lazy methods have not been implemented.

## Current Candidate

Candidate 1 remains the current investigation priority, but its defensible framing is now narrow.

Rejected broad framing:

> Cache monotone information gain and lazily reevaluate candidates.

Current framing:

> Certified change-aware acceleration of a fixed exhaustive optimistic-NBV evaluator using a formally admissible cached visible-unknown upper bound.

Generic caching, monotone gain, changed-region updates, inverse visibility mappings, known-voxel gain decrement, generic upper-bound pruning, and lazy greedy selection all have close prior art and must not be presented as standalone contributions.

## Refined Candidate 1 Direction

If `tau(v)` is the last exact evaluation time for persistent candidate `v`, let

\[
A_{\tau(v)}(v)
\]

be the exact set of cells that were UNKNOWN and optimistically visible from `v` at that time. Let `U_t` be the current UNKNOWN set.

The maintained admissible bound is

\[
\overline G_t(v)=|A_{\tau(v)}(v)\cap U_t|.
\]

Under the assumptions in `docs/CANDIDATE_1_FORMULATION.md`, this bound dominates the current exact optimistic gain. Combined with valid current travel cost and deterministic tie handling, it can be used to skip exact evaluations while certifying the same current target as exhaustive optimistic NBV.

## Novelty Validation Result

The full-method/citation-chained review is recorded in `docs/CANDIDATE_1_PRIOR_ART.md`.

Important findings:

- AEP (Selin et al., 2019) already caches potential information gain and explicitly notes that its gain is monotonic decreasing over time under its assumptions.
- APN (Vutetakis & Xiao) already performs difference-aware map regulation and incrementally maintains view/frontier visibility structures, including inverse visibility relationships.
- FrontierNet (Sun et al., 2025) already adjusts a frontier's stored/predicted information gain downward using currently known voxels.
- Lin et al. (2026) already use exploration gain upper bounds for branch pruning in a sampling-based UAV planner.
- Classic lazy-greedy and adaptive-submodular literature already establish stale upper bounds, priority reevaluation, and exact greedy-choice certification in general optimization settings.

Therefore none of those ingredients individually are novel.

What was **not identified in the reviewed literature** is the exact combined formulation of an exact cached visible-unknown set, the bound `|A_tau(v) ∩ U_t|`, decremental maintenance of that bound as a deliberately conservative certificate, and tie-aware proof of identical current target selection to an explicitly defined exhaustive optimistic-NBV evaluator.

This is not proof of global novelty. The novelty claim must remain scoped to the literature reviewed.

## Current Gate Status

- **Theory gate:** PASS, conditional on stated assumptions.
- **Novelty gate:** PROVISIONAL PASS, HIGH RISK, NARROW CLAIM ONLY.
- **Empirical-value gate:** OPEN.
- **Implementation:** The reference-oracle subphase is complete; lazy-method implementation remains deferred pending review of the exhaustive reference.

## Implemented Features

- Validated finite rectangular ground-truth and UNKNOWN/FREE/OCCUPIED belief grids.
- Atomic monotone observation batches and exact robot/start validation.
- Fixed corner-inclusive, endpoint-inclusive deterministic supercover grid lines.
- Ground-truth physical visibility with first-hit OCCUPIED occlusion and deterministic arrival scans.
- Planning-time optimistic visible-UNKNOWN sets \(A_t(v)\), retained as cell sets rather than counts only.
- Legal 8-neighbor known-FREE motion with costs \(1\) and \(\sqrt 2\), no diagonal corner cutting, and one exact Dijkstra search per plan.
- Deterministic generation of all reachable known-FREE candidates except the current robot cell.
- Exhaustive optimistic-NBV reference with the frozen score and four-level total tie order, structured evaluations, selected path, and deterministic all-zero-gain stop.
- Atomic arrival-scan/planning/movement cycle with no sensing en route.
- Seven fixed 20×20 fixtures: open, single room, corridor, dead end, separated rooms, clutter, and maze-like.
- A 29-test correctness suite covering all required reference behaviors; full suite passed on 2026-09-15.
- No Candidate 1 cache, inverse-incidence index, stale-lazy selector, or proposed change-aware lazy selector has been implemented.
- `docs/RESEARCH_CONTEXT.md` contains earlier toy-prototype observations, but their code/configurations/seeds/raw outputs are unavailable and remain preliminary evidence only.

## Required Baselines for Candidate 1

The first implementation must distinguish the proposed change-aware bound from already-known lazy reuse:

1. exhaustive optimistic NBV;
2. stale-scalar lazy bound using the last exact gain `G_tau(v)`;
3. change-aware cached-set bound `|A_tau(v) ∩ U_t|`;
4. optional tighter occlusion-aware bound only if the third method is too loose.

Only baseline 1 is implemented in the current phase.

Correctness is primary: methods 2/3 must match the exhaustive deterministic argmax and target sequence exactly under the shared tie rule whenever they claim exact equivalence.

## Current Problems and Unresolved Questions

- Does the proposed bound save enough exact raycasts to outweigh inverse-index maintenance and memory costs?
- How large does `sum_v |A_tau(v)|` become as candidate density and sensing range grow?
- Is the change-aware bound materially tighter than the stale scalar bound on realistic map progress?
- Can one shortest-path computation per planning snapshot supply current distances cheaply enough that information-gain evaluation remains the dominant bottleneck?
- Does the corner-inclusive supercover convention create materially different behavior from other fixed supercover conventions in later sensitivity checks?
- The large-experiment coverage, failure, raw-result, timing, and memory protocols remain unfrozen.

## Next Steps

1. Review the deterministic simulator and exhaustive optimistic-NBV reference as the future correctness oracle.
2. Freeze the first experiment's coverage, failure, raw-result, timing, and memory protocols.
3. Preregister the first experiment before implementing either lazy method.
4. Implement the stale-scalar lazy baseline only after the reference is accepted.
5. Implement the change-aware Candidate 1 method only after the stale baseline.
6. Require 100% target and target-sequence agreement before runtime/scaling claims.
7. Measure all bookkeeping overhead and drop or modify Candidate 1 if total savings are weak.
