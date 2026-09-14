# Project State

Last updated: 2026-09-14

## Current Research Stage

- Four candidate research directions have been selected.
- No final candidate has been chosen yet.
- Candidate 1 is being investigated first.
- Candidate 1 is currently under **MODIFY / CONTINUE RESEARCH** status after a focused prior-art review.
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

The research question is whether this bound can be proved admissible under a precisely defined static deterministic occupancy model, maintained cheaply with a changed-cell inverse index, and combined with current travel-distance evaluation to certify exactly the same deterministic NBV as exhaustive evaluation.

This is not yet a verified theorem.

## Current Phase

Pre-implementation formalization and novelty validation:

1. Compare the refined bound/certificate directly against the closest prior work.
2. Formalize the occupancy-map update model and optimistic visibility relation.
3. Prove or refute the admissibility of the proposed bound.
4. Prove or refute the exact selection certificate when current travel distance is included.
5. Define candidate lifecycle, new-candidate bounds, reachability handling, invalidation, and deterministic ties.
6. Only then freeze the minimal common simulator specification.

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

- Is the proposed set-intersection upper bound always admissible under the exact visibility definition?
- Does sensing during movement alter the clean cross-cycle proof assumptions?
- How should newly created candidates receive valid finite upper bounds?
- How should persistent candidate identity be defined if candidate generation changes over time?
- Can current path distance be recomputed cheaply enough that gain evaluation remains the dominant bottleneck?
- Is the refined bound materially tighter than a stale scalar gain in realistic exploration progress?
- Does APN or another incremental exploration planner already imply an equivalent certificate that the current search has missed?

## Next Steps

1. Create a formal Candidate 1 mathematical specification based on `docs/CANDIDATE_1_PRIOR_ART.md`.
2. Search specifically for counterexamples to the proposed admissible bound.
3. Establish the exact theorem assumptions before coding.
4. Specify a minimal deterministic experiment only after theorem-level consistency is established.
5. Begin implementation only after Candidate 1 passes this theory gate.
