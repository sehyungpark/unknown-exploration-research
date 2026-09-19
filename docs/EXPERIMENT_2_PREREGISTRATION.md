# Experiment 2 — C* Efficiency and Scaling Evaluation

Status: **PREREGISTRATION DRAFT — DO NOT EXECUTE FORMAL RUN UNTIL DATASET CONFIG IS COMMITTED**

## Purpose

Experiment 2 evaluates Algorithm C* against A, B, and historical C on a new
holdout dataset.  It is a follow-up to Experiment 1; Experiment 1 results and
artifacts are not changed or reinterpreted.

Primary optimized comparison: **C* versus B**.
C* versus C is required descriptive evidence showing whether the redesign
removed C's maintenance/runtime cost while preserving useful pruning.

## Dataset protocol

Experiment 1's construction is retained:
- sizes: 20x20, 30x30, 40x40;
- occupancies: p=0.10, 0.20, 0.30;
- three accepted maps per size-density stratum;
- 27 primary maps;
- first accepted map of each stratum for the nine-map timing/memory subset;
- first accepted 30x30 map of each density for range sensitivity;
- R=8 primary; R=4,8,12 sensitivity;
- same structural acceptance, component/start selection, cycle limit and hashes.

Only the dataset master seed changes to **20260919**.  Dataset generation is
structural only and runs no planner.

## Methods

A = exhaustive optimistic NBV.
B = stale-scalar exact-lazy baseline.
C = historical eager change-aware Algorithm C.
C* = lazy bitset redesign with range-mask zero-state bound.

Every primary structural snapshot must produce identical status, target, gain,
distance, score, path and terminal sequence for A/B/C/C*.

## Passes

The Experiment 1 pass structure is retained:
1. primary structural: all 27 maps at R=8;
2. seven deterministic anchor fixtures at R=8;
3. primary timing: nine maps;
4. decomposition: nine maps;
5. Python tracemalloc memory: nine maps;
6. range sensitivity: three maps at R=4,8,12.

C* additionally receives a **separate descriptive audit pass** on the nine
timing maps. Audit time is not included in primary planner time.

## Timing

As in Experiment 1:
- one untimed complete warm-up per method;
- six timed complete episodes per method;
- fresh simulator and planner for every method episode;
- only planner-call time is timed;
- work instrumentation, tracemalloc and audit are absent from primary timing.

Because Experiment 2 adds a fourth method, the six frozen orders are:

1. A, B, C, C*
2. B, C, C*, A
3. C, C*, A, B
4. C*, A, B, C
5. A, C*, C, B
6. C, B, A, C*

Warm-up order: A, B, C, C*.

## Primary decision rule

Use the same ordered logic as Experiment 1 with C* substituted as the proposed
method:

1. any primary correctness failure -> CORRECTNESS_REOPENED;
2. C* must be strictly below B on aggregate ray count, supercover-cell count,
   and interior-probe count; otherwise DROP;
3. if all-three work gate passes, use the paired-map 95% bootstrap interval of
   C*/B total planner time:
   - upper < 1 -> GO
   - interval contains 1 -> MODIFY
   - lower > 1 -> DROP

Memory, C*/C comparison, decomposition, audit cost, scaling, and range
sensitivity are required reported tradeoffs but do not override this rule.

## Integrity

The frozen dataset config must be committed before formal execution.
The formal runner rejects a dirty git worktree before creating output.
The first formal invocation is retained whether favorable or unfavorable.
