# Project State

Last updated: 2026-09-14

## Current Research Stage

- Four candidate research directions have been selected.
- No final candidate has been chosen yet.
- Candidate 1 will be investigated first.
- Candidate 1 is: "Exact Lazy Next-Best-View Selection Using Monotone Information Bounds"
- Mathematical formulation and novelty validation should precede implementation.
- Common simulator implementation has not started yet.

## Current Candidate

Candidate 1 is the current investigation priority. This priority reflects implementation feasibility and shared-code reuse, not a final selection of the research topic.

## Current Phase

Pre-implementation research specification:

- Formalize Candidate 1's problem, assumptions, monotonicity claim, certificate, and tie-breaking behavior.
- Validate novelty against the closest prior work.
- Freeze the common simulator and experiment specifications before production-quality implementation.

## Implemented Features

- No common simulator or Candidate 1 algorithm code has been implemented in this repository.
- `docs/RESEARCH_CONTEXT.md` reports earlier toy-prototype observations for Candidates 1–4. The corresponding code, complete configurations, seeds, and raw outputs are not present in this repository, so those observations are retained as preliminary evidence rather than repository-verified results.

## Current Problems and Unresolved Questions

- Candidate 1 may overlap with prior lazy evaluation, caching, or submodular/NBV work; the closest prior work and the precise difference have not been fixed.
- The exact information-gain definition and the assumptions required for cross-cycle monotonicity need a formal statement and proof.
- Candidate lifecycle, valid bounds for newly generated candidates, distance recomputation, and deterministic tie-breaking need precise definitions.
- Core simulator parameters remain undecided, including movement connectivity, ray discretization, candidate generation, sensing range, benchmark sizes, and stopping criteria.
- Existing toy-prototype claims lack reproducible run metadata and raw results.

## Next Steps

1. Conduct and document Candidate 1 literature and novelty validation.
2. Freeze Candidate 1's mathematical formulation and correctness conditions.
3. Specify the minimal deterministic common simulator and evaluation protocol without implementing it yet.
4. Define deterministic correctness tests and preregister the first sanity-check experiment.
5. Begin implementation only after the preceding decisions are recorded.
