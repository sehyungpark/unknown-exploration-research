# Algorithm C* — Lazy Bitset Change-Aware Exact-Lazy NBV

Status: development implementation only. This does **not** replace Algorithm C's
historical Experiment 1 result and is not a new formal efficiency experiment.

## Scope

C* preserves Algorithm A's candidate domain, exact visibility semantics, score,
tie-breaking, current-distance computation, and selected-path semantics.

It applies only ideas 1, 2, 4, and 5 from the current redesign:

1. lazy rather than eager change-aware bound refresh;
2. Python-int bitset representation;
4. exact sensor-range-mask zero-state upper bound for first-seen candidates;
5. hot-path implementation hygiene and separate core/audit timing.

It intentionally does **not** implement the proposed no-new-occluder exactness
certificate, shadow repair, or any shortcut that treats a cached bound as exact.

## Mathematical invariants

Let U_t be current UNKNOWN cells, A_t(v) the canonical exact optimistic
visible-UNKNOWN set, G_t(v)=|A_t(v)|, and A_tau(v) the exact visible-UNKNOWN
set cached at a prior exact evaluation.

Under static-world, monotone-belief, fixed-sensor assumptions:

    A_t(v) subset A_tau(v) intersection U_t

and therefore:

    G_t(v) <= |A_tau(v) intersection U_t|.

If a change-aware bound was last refreshed at an earlier snapshot e, then

    G_t(v) <= |A_tau(v) intersection U_t| <= b_e(v).

Therefore a stale C* bound remains admissible even when it is not eagerly
updated after every revelation.

For a first-seen candidate, let R(v) be the exact canonical Euclidean
sensor-range footprint. Then:

    G_t(v) <= |R(v) intersection U_t|.

C* may safely use the minimum of the stale change-aware bound and the current
range bound because both are individually admissible.

## Exactness rule

C* does not regard a refreshed change-aware bound as exact. The final selected
candidate must have been exact-evaluated on the current planning snapshot using
the canonical optimistic visibility function.

The existing Algorithm A total order is preserved: higher score, higher gain,
shorter current distance, smaller row, then smaller column.

Current Dijkstra distances are recomputed on every planning snapshot. Historical
scores or distances are never reused across snapshots.

## Data representation

C* stores each cached exact visible-UNKNOWN set as a row-major Python integer
bitmask. Current UNKNOWN state is also a bitmask.

The current change-aware bound is popcount(M_v & M_U).
The first-seen range bound is popcount(M_R(v) & M_U).

No inverse incidence index or per-cell candidate decrement structure is used.

## Revelation synchronization

The first planner call initializes the global UNKNOWN mask from the current
belief. Later calls require an explicit newly_known delta from sensing/mapping.
Only those bits are cleared. This avoids a production-path full belief snapshot diff.

## Timing separation

src/evaluation/c_star_instrumentation.py exposes two independent measurements:

- production/core operation timing;
- debug/audit verification timing.

Audit cost is never subtracted from a previously measured core time. The two
passes are conceptually separate so research validation cannot masquerade as
algorithm runtime.

## Historical boundary

Algorithm C remains the method evaluated by formal Experiment 1. C* is a new
development implementation and must receive its own future preregistered
efficiency experiment if it is formally evaluated.
