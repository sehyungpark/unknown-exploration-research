# Experiment 2 Metrics

Experiment 2 retains Experiment 1's principal metrics and adds C* mechanism
counters.

## Primary correctness
A/B/C/C* exact decision equality for every structural snapshot and complete
target/STOP sequence.

## Exact visibility work
Per method:
- exact gain evaluation count;
- visibility ray count;
- generated supercover cell count;
- consumed interior occupancy probe count.

## Timing
Primary: complete-episode planner wall time on the nine-map subset, six timed
repetitions after one warm-up.  Analysis is paired by map.

Secondary: process time.

## Decomposition
Separate descriptive pass:
- Dijkstra/distance time;
- exact visibility time;
- maintenance/synchronization time;
- remaining selection/bookkeeping time.

## C maintenance
Historical C:
- synchronized newly known cells;
- eager bound decrement operations;
- exact cache installations/replacements;
- cache/inverse-index structural peaks.

## C* mechanism counters
- newly known UNKNOWN-mask bit updates;
- first-seen candidate count;
- first-seen pruned without exact;
- range-bound evaluations and zero-bound prunes;
- lazy bound refreshes;
- stale-bound pops;
- refresh-and-reinsert count;
- exact escalation after current bound;
- exact cache installations/replacements;
- priority pops;
- certificate successes.

## C* structural storage
- cached candidate count;
- cached visible membership count (set-bit count);
- cached range-mask count;
- range-mask membership count.

## Memory
Separate non-timed tracemalloc pass for A/B/C/C* on the nine timing maps.

## Audit
Separate C*-only pass.  Full audit time is reported descriptively and is never
added to primary planner time.

## Bound tightness
For B, C and C*, Algorithm A's exact current gain is the external oracle.
Per-map aggregate slack statistics are retained without modifying planner state.
