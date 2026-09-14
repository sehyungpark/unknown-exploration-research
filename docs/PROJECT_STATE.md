# Project State

Last updated: 2026-09-14

## Current Research Stage

- Four candidate research directions have been selected.
- No final candidate has been chosen yet.
- Candidate 1 is being investigated first.
- Candidate 1 has passed a **conditional theory gate** for its refined bound, but novelty and empirical-value gates remain open.
- Common simulator implementation has not started yet.

## Current Candidate

Candidate 1 remains the current investigation priority, but its original framing has been narrowed.

Original framing:

> Exact Lazy Next-Best-View Selection Using Monotone Information Bounds

Current concern:

- Generic gain caching is prior art in NBV exploration.
- Generic stale-value lazy upper-bound evaluation is prior art in submodular/lazy-greedy optimization.
- Difference-aware incremental map/view updates are also prior art.

Therefore Candidate 1 cannot rely on "cache + lazy reevaluation" alone as its research contribution.

## Refined Candidate 1 Direction

The current stronger hypothesis is to derive and maintain an **exploration-specific admissible upper bound** on NBV information gain from occupancy-state changes.

If `tau(v)` is the last exact evaluation time for candidate `v`, let

\[
A_{\tau(v)}(v)
\]

be the cells that were UNKNOWN and optimistically visible from `v` at that time. Let `U_t` be the currently UNKNOWN cells.

The proposed bound is

\[
\overline G_t(v)=|A_{\tau(v)}(v)\cap U_t|.
\]

`docs/CANDIDATE_1_FORMULATION.md` proves that this bound is admissible under a fixed finite grid, static deterministic truth, monotone correct belief updates, immutable full viewpoint identity, fixed sensor geometry, and UNKNOWN-transparent planning visibility. It also proves that inverse-incidence decrements preserve the bound and gives a tie-aware certificate for the same deterministic NBV as exhaustive evaluation.

This is a conditional mathematical result, not a novelty result or empirical performance result.

## Current Phase

Pre-implementation novelty validation and simulator specification:

1. Revisit the full APN method and citation chain for an equivalent admissible-bound certificate.
2. Validate the refined distinction against all closest robotics prior art.
3. Freeze the symbolic choices left open by the theorem: ray traversal, FOV/range, candidate generation, movement graph, and total tie order.
4. Specify theorem-derived counterexample and correctness tests.
5. Only then decide whether Candidate 1 is sufficiently differentiated to implement.

## Implemented Features

- No common simulator or Candidate 1 algorithm code has been implemented in this repository.
- `docs/RESEARCH_CONTEXT.md` contains earlier toy-prototype observations, but the corresponding code, complete configurations, seeds, and raw outputs are not present; those remain preliminary evidence only.

## Literature Status

A focused prior-art sweep has been documented in `docs/CANDIDATE_1_PRIOR_ART.md`.

Key prior-art categories now confirmed:

- classic exact lazy-greedy upper-bound evaluation;
- adaptive lazy evaluation under partial observability;
- NBV information-gain caching across replanning cycles;
- selective reevaluation of persistent NBV candidates;
- faster gain computation via shadowcasting / alternative visibility evaluation;
- difference-aware incremental visibility/information maintenance;
- bound-based pruning of expensive information gain in adjacent sensor-selection work.

No claim of novelty is currently approved.

## Current Problems and Unresolved Questions

- Does APN or another incremental exploration planner already contain an equivalent admissible bound or exhaustive-NBV certificate?
- Is the refined combination sufficiently different from existing caching, selective reevaluation, and incremental visibility maintenance?
- Can current path distance be recomputed cheaply enough that gain evaluation remains the dominant bottleneck?
- Is the refined bound materially tighter than a stale scalar gain in realistic exploration progress?
- What fixed ray traversal, FOV/range, candidate identity, candidate generator, movement graph, and tie order should instantiate the symbolic theorem?
- How should atomic planning snapshots be enforced if sensing occurs during movement?

## Next Steps

1. Perform full-text and citation-chained comparison with APN and the closest NBV caching/incremental-update methods.
2. Decide whether the refined research distinction passes the novelty gate.
3. Freeze the minimal deterministic simulator specification and deterministic tie rule.
4. Translate every excluded-assumption counterexample into a future correctness test specification.
5. Preregister the first experiment before any implementation.
