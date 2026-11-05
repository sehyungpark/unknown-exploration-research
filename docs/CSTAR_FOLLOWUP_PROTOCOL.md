# C* user-run follow-up — infrastructure addendum, 2026-10-20

Status: infrastructure implemented; full user test gate and performance passes **NOT EXECUTED** by the implementation task.

This addendum operationalizes the approved first two steps: execution preparation/full tests and completion of the existing pilot timing. It is not a new confirmatory Experiment 3 and does not change Experiment 0/1/2 or the historical pilot outputs.

## Research contract

- Candidate 1; phase is mechanism ablation and exploratory efficiency.
- Shared definitions: existing simulator, exact pose/static map, R=8, canonical visibility, Dijkstra, candidate generation, gain/distance objective, full tie order, arrival-only sensing.
- Correctness condition: each method's status, selected target, gain, distance, score, complete path and eligible-candidate count match A at every decision, including STOP.
- H1: C*'s cached-set bound saves planner time over the S* scalar-plus-range ablation.
- H2: certificate reuse saves enough work to compensate for checking/building its dependencies.
- Both hypotheses can be rejected by the retained timing/memory evidence. Work savings alone do not establish H1/H2.
- Closest prior art/difference: the shadowcasting NBV planner (arXiv:2109.09323) accelerates visibility, and APN (arXiv:2309.11695) maintains difference-aware visibility; this pilot measures a fixed evaluator's exact-selection certificate and a sufficient exact-reuse condition. Generic caching/lazy evaluation/incremental visibility are prior art; novelty is unresolved.

## Frozen primary pilot

`configs/cstar_followup_pilot_v1.json` freezes six timing map IDs, B/S*/C*/CERT, R=8, one warm-up and four measured repetitions in the original four rotation orders. Its byte hashes freeze the original 21-map structural evidence and executed structural source.

All 120 timing episodes are retained: 24 warm-ups and 96 measured episodes. Warm-ups are excluded from summaries. All methods start fresh. Timer boundaries remain around planner calls only. CERT pays its occupied-delta, dependency build, certificate and forwarding costs. B/S*/C* execute directly, without unnecessary adapter work or work instrumentation.

Before timing, a separate non-timed A pass on the six maps verifies the original target/STOP sequence and supplies full decision/path references. Every timed or memory episode is checked against that reference outside the planner timing boundary. No first favorable map, subset, repetition or result is selected.

Four measured values per map/method yield median/min/max and linear h=(n-1)p quartiles. C*/S* is the main mechanism comparison; C*/B, S*/B and CERT/C* are reported. Map-level ratios and their geometric means are descriptive only. No GO/DROP rule or confirmatory confidence interval is introduced.

S* retains C*'s bitset allocation and diagnostics to isolate the bound rule. It is not presented as an optimized scalar-only implementation. A stronger such baseline and a larger topology/size study remain future work.

## Separate secondary memory pass

After all timing completes, run one fresh tracemalloc episode per six-map/four-method pair (24 episodes). Tracing begins after environment, initial scan and planner construction and stops at terminal return. It includes planner allocations, arrival sensing, movement validation and accumulated decision/reference bookkeeping. This is a Python episode-allocation metric, not process RSS or isolated planner-state size. Memory never changes the frozen timing interpretation.

## Provenance and failures

Code/config/tests/scripts must be committed. Source fingerprints normalize CRLF/LF; original evidence uses Git `-text` attributes to retain exact bytes. Full unittest completion, exit code and log hash are required before timing. One invocation stays on one code commit, source/config fingerprint, PC and Python version. Historical Experiment 1's large untracked files are not a runtime dependency.

Unique run IDs and an exclusive lock prevent overwrite and concurrent use of the same invocation. Do not run different invocations simultaneously on one machine. Records are flushed episode by episode. Exception/mismatch/interrupt evidence is retained and performance is not summarized from an incomplete schedule. A clean stage boundary can be continued; a partial failed timing pass requires a separately recorded new invocation and reason, never deletion or selective repetition replacement.

Infrastructure validation uses fake schedules, failure injection and a nonformal 1x20 smoke map. It does not execute this frozen performance workload.
