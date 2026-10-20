# Research extension pilot — 2026-09-29

Status: frozen before executing the new pilot. Exploratory evidence, not a replacement for Experiments 1 or 2.

## Before coding

- Candidate: Candidate 1, with specifications for later Candidates 2/3/4 only.
- Phase: historical-result audit, deterministic correctness, mechanism ablation, small exploratory benchmark.
- Shared baseline: the existing ground truth, belief, physical scan, optimistic visibility, Dijkstra, reachable candidates, gain/distance score, complete tie order, and arrival-only sensing.
- Correctness: every method must match A's status, target, exact gain/distance/score, path, and terminal sequence at every shared snapshot. A mismatch fails that episode and is retained.
- Hypotheses: H1, C*'s cached-set intersection contributes beyond its range bound and scheduler; H2, an occluder-dependency certificate safely avoids exact visibility calls; H3, savings survive their implementation cost and transfer to structured rooms.
- Falsification: identical ablation work weakens H1; any certificate mismatch rejects H2; higher planner time despite fewer raycasts rejects this prototype's H3. Keep every map/repetition and do not change parameters after seeing outcomes.

## Closest prior art and difference

Batinovic et al. (arXiv:2109.09323) accelerate NBV gain using shadowcasting; APN (arXiv:2309.11695) maintains difference-aware visibility. This pilot instead checks a sufficient condition for exact reuse of an earlier canonical visible-UNKNOWN set, and checks identical exhaustive NBV decisions. Generic incremental visibility and caching are prior art; novelty of this certificate is unresolved.

## Tested methods

- A: unchanged exhaustive oracle, structural pass only.
- B: unchanged stale-scalar lazy baseline.
- S*: C*'s same implementation/scheduler/range bound with the cached-set intersection replaced by `min(stale_upper, current_range_upper)`. It retains bitset allocation and diagnostic overhead to isolate the bound rule. This is an ablation, not a fully optimized scalar competitor.
- C*: unchanged committed implementation.
- C*+certificate: research-only adapter around C*'s canonical visibility callable. For cached exact set A_tau(v), store D_tau(v), the union of canonical supercover interiors toward its cells, and occupied mask O_tau. If `(O_t & ~O_tau) & D_tau(v) == 0`, return `A_tau(v) intersect U_t` as an exact set. Otherwise call canonical visibility and rebuild dependencies. Include certificate checking and dependency construction in planner time. No production planner is changed.

For every retained x in A_tau intersect U_t, its earlier ray was unblocked and no new OCCUPIED interior cell exists under the condition. Thus x remains visible. Monotonicity supplies the opposite inclusion. A cached bound alone is not an exactness certificate. The structural adapter independently recomputes canonical visibility for every claimed reuse, outside timed runs.

## Frozen workload

- All seven existing 20x20 fixtures.
- Eight fresh Bernoulli maps: sizes 20 and 30, p=0.10 and 0.30, two seeds per stratum from `Random(20260929).getrandbits(63)`, in size/p/repetition order. No rejection or replacement; choose the existing deterministic largest-component start. A no-free map is retained as a generation failure.
- Six deterministic four-room maps: sizes 20,30,40 crossed with doorway widths 1,3. Border walls and cross walls; doors off-center on each half-wall; start (2,2). No random seed applies.
- All methods use R=8, exact pose, static geometry, arrival-only sensing, and the same map. Cycle limit is `max(128, 2 * free_cell_count)`.
- Structural counts: actual canonical visibility calls, certificate hits, exact evaluations reported by the planner, and complete sequence hashes. Certificate validation calls are separate audit work.
- Correctness enumeration: all 3^8 beliefs of a 3x3 grid with a FREE candidate at (0,0), R=3, every single legal UNKNOWN->FREE/OCCUPIED update. Check cached-set admissibility and dependency-certificate equality; retain examples of strict occlusion slack.
- Timing subset fixed by map identity: open, maze_like, rooms-20-door-1, rooms-30-door-3, random-20-0.1-1, random-30-0.3-1.
- One untimed warm-up, four timed repetitions, orders B/S*/C*/certificate; S*/C*/certificate/B; C*/certificate/B/S*; certificate/B/S*/C*. Four-order rotation balances position, but does not completely balance carryover; no confirmatory interval/GO decision is made from this pilot.
- Timer encloses planner call and adapter setup/restoration/check/build only; physical sensing, movement, comparison, hashing, serialization, and structural audit are outside. All methods run serially after the full existing suite.
- Pre-timing implementation clarification: B, S*, and C* execute directly without the research visibility adapter or unused occupied-mask work during timing. Only CERT pays for its occupied-delta processing, adapter, dependency construction, and counters. Structural instrumentation remains outside timing. This fixes an unused-work implementation defect before observing any pilot timing; the executed structural source and separate timing source hashes are retained.
- Freeze a generated map manifest with seeds, hashes, ASCII maps and starts before any pilot planner runs. Non-overwriting invocation directory; partial output/failure evidence stays on failure.

## Historical audit

Recompute Experiment 1's work/timing/classification from retained raw records, stream its correctness flags, and recompute all of Experiment 2's summary from its raw records. Record file SHA-256 hashes and missing-artifact limitations. Do not rerun a four-hour formal workload or change original artifacts. Experiment 1 and 2 used different machines/Python versions; compare methods within each invocation, not absolute times across invocations.
