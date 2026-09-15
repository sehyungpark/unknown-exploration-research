# Project State

Last updated: 2026-09-16

## Current Research Stage

- Four candidate research directions have been selected.
- No final candidate has been chosen yet.
- Candidate 1 is being investigated first.
- Candidate 1 has passed a **conditional theory gate**.
- Candidate 1 has received a **provisional novelty pass with high risk and a narrow claim only** after full-method comparison with major close prior art.
- The empirical-value gate remains open.
- The minimal deterministic common simulator and exhaustive optimistic-NBV reference are implemented, oracle-hardened, and pass the current correctness suite.
- Experiment 0 exact-equivalence validation is preregistered but has not been executed because the formal full A/B/C runner and immutable failure-artifact writer do not yet exist.
- Experiment 0's corrected `experiment-0-random-v2` 60-map correctness dataset, seed list, hashes, start/acceptance rules, cycle limits, per-cycle logging schema, and failure-artifact convention are frozen. The invalid v1 denominator was detected and corrected before Algorithms B/C or Experiment 0 execution.
- Algorithm B, the stale-scalar exact-lazy baseline, is implemented and passes development exact-equivalence regressions against Algorithm A on all seven fixed fixtures and all 60 frozen v2 random maps.
- Algorithm C Stages 1-5 provide cache/index state, atomic exact cached-set installation/refresh, once-per-cell revelation decrement, immutable belief-snapshot synchronization, common exact visibility integration, a stateful certified exact-lazy selector, and fail-fast pre-refresh admissibility checks. Stage 6 passed the full development A/C exact-equivalence regression on all seven fixtures and all 60 frozen-v2 random maps.

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
- **Implementation:** The exhaustive reference is accepted as the current correctness oracle after corner-occlusion, complete-fixture, and admissibility-property hardening. The stale-scalar exact-lazy baseline is implemented. Algorithm C has passed its full development A/C exact-equivalence regression; the formal preregistered A/B/C Experiment 0 gate remains unexecuted.

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
- Algorithm C Stage 2 adds one public `install_exact(candidate, visible_unknown)` mutation for both first exact installation and exact replacement. It validates strict nonnegative integer coordinates and `frozenset` input before mutation, replaces state transactionally, removes the candidate from every cell in its complete old cached set, preserves other candidates on shared cells, deletes newly empty inverse keys, installs the complete new cached set, and resets the candidate's bound to the new exact-set size.
- Algorithm C's inverse incidence represents the full installed historical cached set `A_tau(v)`, not only cells that are currently UNKNOWN. A later revelation may validly produce `bound_counts[v] < len(cached_visible_unknown[v])` while every old cached membership remains in the inverse index until exact refresh.
- Algorithm C Stage 3 adds `apply_newly_known(cells)` for explicit monotone UNKNOWN-to-known batches. An episode-wide `reported_known_cells` set makes duplicate reports idempotent, including revelations that currently have no inverse-index entry. Each first report decrements every incident candidate exactly once while leaving cached sets and inverse incidence unchanged.
- Stage 3 validation enforces `bound_counts[v] == len(cached_visible_unknown[v] - reported_known_cells)`. All mutation is transactional; malformed input, accounting inconsistency, and potential underflow are rejected without partial state changes. Fresh exact installation rejects cells already reported known, relying explicitly on monotone belief, exact fresh sets containing only current UNKNOWN cells, and no known-to-UNKNOWN reversion.
- Algorithm C Stage 4 uses the existing immutable `BeliefGrid.snapshot()` tuple-of-tuples representation to extract exact legal UNKNOWN-to-FREE/OCCUPIED deltas while rejecting shape mismatch, known-state reversion, and FREE/OCCUPIED switching. `synchronize_revelations` applies each extracted delta through the accepted Stage 3 API, including the initial-scan-before-cache lifecycle and idempotent duplicate synchronization.
- Stage 4 exact candidate refresh calls the existing `optimistic_visible_unknown_cells` implementation and passes its exact `frozenset` directly to `install_exact`; no second ray traversal or visibility definition was added. Actual belief-transition regressions verify the maintained cached-intersection invariant and `G_t(v) <= q_t(v)` for several persistent viewpoints. A newly OCCUPIED near blocker creates the intended strict conservative slack, and exact refresh restores equality and exact inverse incidence.
- Algorithm C Stage 5 adds episode-scoped `ChangeAwareLazyNBV` with immutable fixed sensor range, a planner-owned `ChangeAwareGainCache`, last-synchronized belief snapshot state, explicit reset, and all-UNKNOWN first-call synchronization for post-initial-scan beliefs. Every snapshot synchronizes before one current Dijkstra search and candidate generation.
- First-seen eligible candidates are exact-initialized through the Stage 4 refresh helper. Persistent candidates retain caches while ineligible, and global revelation incidence continues to decrement their maintained bounds. Bound-only scores use `q_t(v)/(d_t(v)+1e-9)` with current distance only.
- The selector reuses the frozen total rank and tie-aware certificate utilities. It exact-reevaluates the deterministic optimistic-best remaining candidate until a current-exact incumbent strictly dominates every optimistic rank, and it certifies completion from all-zero upper gains. A selected target is defensively required to be current-exact.
- Stage 5 hardening separates pure exact-set computation from cache installation. For an initialized candidate it captures `q_before`, computes `G_exact` through the shared optimistic-visibility API, raises `ChangeAwareGainBoundViolation` if `G_exact > q_before`, and installs only after the pre-refresh check passes. A successful install retains the independent post-refresh check `q_after = G_exact`; first-seen candidates remain exempt from the historical-bound comparison.
- No admissibility violation has been observed on normal supported inputs. A deliberately fault-injected `q_before=2`, `G_exact=3` regression verifies a clear correctness exception and zero mutation of cached sets, bounds, inverse incidence, or reported-known history. This is not an empirical counterexample to the theorem. Unsupported-assumption inputs remain a separate validation/lifecycle category, and no exhaustive fallback hides a supported-run violation.
- `ChangeAwareGainBoundViolation` retains detached cache diagnostics plus previous/current belief snapshots, newly-known delta, sensor configuration, and current candidate distance while the planner-owned pre-violation cache remains inspectable. Stage 6 and Experiment 0 runners must stop, classify the run as a correctness failure, and retain this evidence if a supported run ever triggers it.
- Structured Stage 5 results retain synchronized deltas, exact/skipped counts, certificate reason, selected path and exact values, plus per-candidate current distance, snapshot-entry change-aware bound/score, exact-evaluation values, and refresh status. Snapshot-entry bounds are not overwritten by later exact refreshes.
- Stage 6 adds a test-only shared-snapshot A/C complete-run regression. On every cycle it evaluates A and C on the same belief and robot, validates status, target, candidate order, current distances, every available maintained bound, exact/bound-only diagnostics, selected exact values, and path, and advances the one shared environment only after agreement.
- **Fixed-fixture development gate:** **7/7 complete A/C runs passed** across **89 shared planning snapshots**. Target mismatches: **0**; status/sequence/termination mismatches: **0**; selected gain/distance/score/path mismatches: **0**; maintained-bound violations: **0**. Safe exact-evaluation skipping was observed.
- **Frozen-v2 development gate:** **60/60 complete A/C runs passed** across **1,096 shared planning snapshots** after every record's seed, start, cycle limit, regenerated map hash, and canonical ground-truth hash were reverified. Target mismatches: **0**; status/sequence/termination mismatches: **0**; selected gain/distance/score/path mismatches: **0**; maintained-bound violations: **0**. Safe exact-evaluation skipping was observed.
- Across all **67 complete runs and 1,185 planning snapshots**, every C selected candidate was current-exact, candidate domain/order and current distances matched A, no supported-run `ChangeAwareGainBoundViolation` occurred, and no unsupported-assumption/lifecycle failure occurred.
- The 165-test suite passed on 2026-09-16, including the unchanged full A/B regressions and the two new Stage 6 complete-run tests. Stage 6 is a development correctness regression, not the formal preregistered Experiment 0 and not an empirical proof of the conditional theorem.
- The formal A/B/C runner does not exist, Experiment 0 has not been executed, and no wall-clock, memory, speedup, or efficiency claim is made.
- `docs/RESEARCH_CONTEXT.md` contains earlier toy-prototype observations, but their code/configurations/seeds/raw outputs are unavailable and remain preliminary evidence only.

## Required Baselines for Candidate 1

The first implementation must distinguish the proposed change-aware bound from already-known lazy reuse:

1. exhaustive optimistic NBV;
2. stale-scalar lazy bound using the last exact gain `G_tau(v)`;
3. change-aware cached-set bound `|A_tau(v) ∩ U_t|`;
4. optional tighter occlusion-aware bound only if the third method is too loose.

Baselines 1 and 2 are implemented. Baseline 3 has its state, belief/visibility integration, certified exact-lazy selector, and full development A/C exact-equivalence regression pass, but still awaits the formal preregistered A/B/C Experiment 0 gate.

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
2. Preserve the accepted Stage 5 ordering, lifecycle, no-fallback admissibility guard, and Stage 6 shared-snapshot A/C development regression.
3. Implement the formal cross-method Experiment 0 runner and immutable failure-artifact writer against the frozen schemas without changing the frozen algorithms, simulator, dataset, or preregistration.
4. Execute Experiment 0 and require zero target, sequence, bound, tie, and invariant violations.
5. Do not begin efficiency evaluation until Experiment 0 passes.
