# Project State

Last updated: 2026-09-15

## Current Research Stage

- Four candidate research directions have been selected.
- No final candidate has been chosen yet.
- Candidate 1 is being investigated first.
- Candidate 1 has passed a **conditional theory gate**.
- Candidate 1 has received a **provisional novelty pass with high risk and a narrow claim only** after full-method comparison with major close prior art.
- The empirical-value gate remains open.
- The minimal deterministic common simulator and exhaustive optimistic-NBV reference are implemented, oracle-hardened, and pass the current correctness suite.
- Experiment 0 exact-equivalence validation is preregistered but has not been executed because the Algorithm C selector/dynamic maintenance and the full A/B/C runner do not yet exist.
- Experiment 0's corrected `experiment-0-random-v2` 60-map correctness dataset, seed list, hashes, start/acceptance rules, cycle limits, per-cycle logging schema, and failure-artifact convention are frozen. The invalid v1 denominator was detected and corrected before Algorithms B/C or Experiment 0 execution.
- Algorithm B, the stale-scalar exact-lazy baseline, is implemented and passes development exact-equivalence regressions against Algorithm A on all seven fixed fixtures and all 60 frozen v2 random maps.
- Algorithm C Stage 1 state infrastructure is implemented, but the proposed change-aware method itself remains incomplete: no exact cache installation/refresh, revelation-driven decrement, selector, or A/C regression exists.

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
- **Implementation:** The exhaustive reference is accepted as the current correctness oracle after corner-occlusion, complete-fixture, and admissibility-property hardening. The stale-scalar exact-lazy baseline is implemented. Algorithm C has state-only cache/index infrastructure; its update and selection behavior remains deferred.

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
- Reference and dataset/hash coverage includes a regression that distinguishes the total-grid-cell denominator from the invalid total-FREE-cell denominator.
- Set-level admissibility checks over 38,673 deterministic and fixed-seed monotone update transitions.
- Complete repeated exhaustive runs on all seven fixtures, each reaching explicit `EXPLORATION_COMPLETE` before its safety limit with identical independent-run traces.
- Corner-occlusion integration coverage at the physical and optimistic planning visibility APIs.
- Deterministic independent-Bernoulli random-map generation with local RNG state, connected-component/start selection, total-grid-cell component acceptance, acceptance/rejection records, v2 map materialization, and frozen config validation. Corrected v2 retains candidate index 34 as its one rejection; normal seed consumption changes 26 ID-indexed accepted seeds/hashes from invalid v1.
- Shared canonical SHA-256 utilities for ground truth (`./#`) and belief (`?/.#`) with fixed row order and final LF.
- Stateful Algorithm B with a scalar-only `candidate coordinate -> last exact gain` cache, exact initialization for first-seen eligible candidates, current-snapshot distances, direct exact visibility evaluation, tie-aware lazy certification, and all-zero-upper-bound completion.
- Algorithm B's stale cache is explicitly episode-scoped. Public `reset()` clears only cached gains before planner reuse on a new environment while preserving the fixed sensor-range configuration; no heuristic automatic reset is performed.
- Structured Algorithm B results expose per-cycle exact-evaluation counts, bound-only counts, certificate reasons, selected current-exact values, and candidate-level stale/exact/cache-refresh diagnostics.
- A/B shared-snapshot development regressions cover complete exploration on all seven fixed fixtures and every accepted map in frozen `experiment-0-random-v2`; stale-bound violations, target mismatches, and sequence/termination divergences were all zero.
- Algorithm C Stage 1 provides an episode-scoped `ChangeAwareGainCache` state abstraction with candidate-to-exact-cached-visible-UNKNOWN sets, candidate-to-maintained-bound counts, cell-to-candidate inverse incidence, safe diagnostics, explicit reset, and defensive structural validation.
- The 91-test suite passed on 2026-09-15. It includes direct synthetic tie-certificate cases, scalar-cache lifecycle/invariant/reset checks, cross-environment leakage prevention, Algorithm C Stage 1 state-invariant checks, and a deterministic case where B safely selects the same target with fewer exact evaluations than A. These are correctness checks, not performance results.
- No Algorithm C cache installation/removal API, exact refresh, raycasting, UNKNOWN-to-known decrement processing, belief-delta handling, lazy priority loop, selector, A/C comparison, or A/B/C runner has been implemented.
- `docs/RESEARCH_CONTEXT.md` contains earlier toy-prototype observations, but their code/configurations/seeds/raw outputs are unavailable and remain preliminary evidence only.

## Required Baselines for Candidate 1

The first implementation must distinguish the proposed change-aware bound from already-known lazy reuse:

1. exhaustive optimistic NBV;
2. stale-scalar lazy bound using the last exact gain `G_tau(v)`;
3. change-aware cached-set bound `|A_tau(v) ∩ U_t|`;
4. optional tighter occlusion-aware bound only if the third method is too loose.

Baselines 1 and 2 are implemented in the current phase. Baseline 3 has only its Stage 1 state representation; its update and selection algorithm remains unimplemented.

Correctness is primary: methods 2/3 must match the exhaustive deterministic argmax and target sequence exactly under the shared tie rule whenever they claim exact equivalence.

## Current Problems and Unresolved Questions

- Does the proposed bound save enough exact raycasts to outweigh inverse-index maintenance and memory costs?
- How large does `sum_v |A_tau(v)|` become as candidate density and sensing range grow?
- Is the change-aware bound materially tighter than the stale scalar bound on realistic map progress?
- Can one shortest-path computation per planning snapshot supply current distances cheaply enough that information-gain evaluation remains the dominant bottleneck?
- Does the corner-inclusive supercover convention create materially different behavior from other fixed supercover conventions in later sensitivity checks?
- Large efficiency-experiment coverage, timing, memory, and raw-result protocols remain unfrozen; Experiment 0's correctness logging/failure protocol is now frozen separately.

## Next Steps

1. Retain the stale-scalar exact-lazy baseline, its explicit per-episode reset contract, and its A/B development regressions as the correctness baseline.
2. Add Algorithm C exact cache installation/refresh and dynamic bound maintenance in later staged work without changing the frozen Algorithm A/B semantics.
3. Implement the cross-method Experiment 0 runner and immutable failure-artifact writer against the frozen schemas.
4. Execute Experiment 0 and require zero target, sequence, bound, tie, and invariant violations.
5. Do not begin efficiency evaluation until Experiment 0 passes.
