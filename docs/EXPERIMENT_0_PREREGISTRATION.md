# Experiment 0 — Exact-Equivalence Correctness Validation

Preregistered: 2026-09-15

## Purpose and Scope

Experiment 0 is a correctness experiment, not a performance comparison. Its sole purpose is to determine whether two future exact-lazy methods make exactly the same deterministic decision as the frozen exhaustive optimistic-NBV oracle at every planning snapshot and throughout complete exploration runs.

No runtime, speedup, or computational-efficiency claim is permitted from Experiment 0. At preregistration time, only Algorithm A is implemented.

## Algorithms

### A. Exhaustive optimistic NBV

Evaluate the exact optimistic visible-UNKNOWN set and exact gain for every eligible candidate, then apply the frozen score and total tie order. **Implementation status: implemented and oracle-hardened.**

### B. Stale-scalar exact lazy NBV

Use the last exact gain as a stale admissible upper bound and perform exact reevaluations until the deterministic exhaustive choice is certified. **Implementation status: not implemented.**

### C. Proposed change-aware cached-set exact lazy NBV

Use the maintained bound

\[
\overline G_t(v)=|A_{\tau(v)}(v)\cap U_t|
\]

and perform exact reevaluations until the deterministic exhaustive choice is certified. **Implementation status: not implemented.**

## Primary Correctness Endpoint

At every planning snapshot,

\[
\operatorname{selected}_A
=\operatorname{selected}_B
=\operatorname{selected}_C.
\]

- Allowed target mismatches: **0**
- Required target agreement: **100%**

Termination decisions are selections for this endpoint: if A stops, B and C must stop on the same snapshot, and no method may stop earlier or later.

## Sequence Endpoint

From the same initial environment, the complete selected-target sequence, including the terminal stop event, must be identical for A, B, and C.

- Allowed sequence divergences: **0**
- Required target-sequence agreement: **100%**

## Shared Conditions

The three algorithms must use exactly the same:

- ground-truth map and map ID;
- start position;
- belief snapshot at each comparison;
- sensor range (`R=8` for the initial deterministic dataset);
- corner-inclusive supercover convention;
- candidate set and immutable coordinate IDs;
- exact distances from the same current-snapshot Dijkstra result;
- score definition \(S_t(v)=G_t(v)/(d_t(v)+10^{-9})\);
- total tie order: larger score, larger exact gain, smaller exact distance, then lexicographically smaller coordinate.

No algorithm-specific map, seed, sensing, candidate, distance, score, or tie configuration is allowed.

## Initial Correctness Dataset

### Stage 1 — Fixed deterministic fixtures

Use all seven fixed 20×20 fixtures:

1. `open`
2. `single_room`
3. `corridor`
4. `dead_end`
5. `separated_rooms`
6. `clutter`
7. `maze_like`

Each fixture uses its repository-defined fixed FREE start cell. Every run must reach the explicit exhaustive stop condition before its fixture-specific safety limit.

### Stage 2 — Fixed-seed random small maps

The random-map generator, accepted-map policy, map count, start-selection procedure, seed list, and cycle limits are **pending** and must be frozen before Algorithms B or C are evaluated on random maps. Failed generated maps or runs must not be selectively removed after the seed set is frozen.

The implementation-level admissibility property suite already uses fixed seed `20260915`; this seed validates monotone bound consistency but is not a substitute for the pending random exploration dataset.

## Required Logged Fields per Planning Cycle

- fixture/map ID;
- cycle index;
- robot coordinate;
- eligible candidate count;
- exhaustive selected candidate;
- stale selected candidate;
- proposed selected candidate;
- exhaustive selected gain;
- selected distance;
- selected score;
- exact gain evaluation count for A;
- exact gain evaluation count for B;
- exact gain evaluation count for C;
- pairwise and all-method target-agreement flags;
- termination status for each method.

For any failure, also retain the full belief snapshot, candidate evaluations/bounds needed to reproduce the failure, algorithm versions, and failure reason.

## Failure Rule

Do not proceed to an efficiency experiment if any run contains:

- a target mismatch;
- a target-sequence divergence;
- an invalid gain or score upper bound;
- an invalid deterministic tie certificate;
- a cache or inverse-index invariant failure;
- a different termination snapshot or status.

Every failure must remain in the record and be reduced to a minimal reproducible example when possible. Failed or unfavorable cases must not be deleted.

## Gate

Experiment 0 passes only when all of the following hold:

- all deterministic tests pass;
- all preregistered fixed-seed random correctness runs pass;
- target agreement is 100%;
- target-sequence agreement is 100%;
- there are zero admissibility violations;
- there are zero cache/index invariant violations;
- there are zero tie-certificate violations.

Until this gate passes, runtime improvement must not be reported as a research result. A failure blocks the efficiency experiment and requires correction, explicit reformulation, or rejection of the affected method before further claims.

## Current Status

**PREREGISTERED, NOT EXECUTED.** Algorithm A exists. Algorithms B and C, the random-map dataset, and the cross-method Experiment 0 runner do not yet exist.
