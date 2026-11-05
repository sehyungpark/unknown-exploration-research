# basiccode C* — incremental UNKNOWN mask

## Implementation contract (2026-10-27)

- Candidate: Candidate 1, standalone basiccode C* implementation.
- Phase: implementation-only maintenance change with small correctness regression; no performance benchmark.
- Shared baseline: retain the existing basiccode truth/known representation, 4-neighbor BFS, R=4 defaults, per-step observations, score/tie order, heap, range/visible-set caches, movement and completion rules.
- Correctness: at every planning snapshot the maintained mask must equal a fresh reconstruction of current UNKNOWN cells. Selected target, gain, score, distance, planned/actual path, cost, termination and final belief must match the previous rebuild-based behavior and A/B on the same inputs.
- Hypothesis: one initialization plus observation-delta updates can remove repeated full-grid mask reconstruction. This is a structural work change; runtime improvement is unverified and may be absent on small maps.
- Falsification: any mask/decision/path mismatch rejects the implementation. A later runtime study may reject practical value while preserving correctness. Do not tune or run the real benchmark during this implementation task.
- Closest precedent: the repository's original `src/planning/change_aware_star_nbv.py` already initializes UNKNOWN once and clears bits from explicit revelation deltas. This ports only that state-maintenance mechanism into basiccode; it is not a new algorithm or novelty claim.

## Intended data flow

The common observer optionally reports UNKNOWN-to-known transitions without changing the cells or ray order it observes. Initial observation and every movement-step observation forward this hook. C* accumulates the cells in an episode-local state; its first planning call builds the current mask once, and later calls validate/apply only pending cells inside candidate evaluation. Duplicate reports are idempotent.

The old four-argument `evaluate_candidates` call remains a rebuild-based compatibility/reference path. Normal `C.explore()` supplies fresh episode-local state and uses incremental updates. A/B files and public result/tuple shapes remain unchanged.

The optional observation hook adds bookkeeping during sensing; clearing mask bits happens during planning. Any later timing comparison must account for observation bookkeeping and distinguish planner time from total episode time. Other full-map work, including `unknown_count`, remains unchanged. No speedup is claimed here.

## Validation planned

Check initialization after initial scan, partial-known input, all pending movement-step revelations, duplicate/empty deltas, safe rejection of still-UNKNOWN/out-of-bounds reports and shape changes, fresh state between episodes, one reconstruction per multi-plan exploration, and complete A/B/rebuild-C/incremental-C agreement on small open/room/corridor/dead-end/separated-room/clutter/maze maps. Actual full-size experiments remain user-run.

## Usage and compatibility

Update `basiccode/C_cstarNBV.py` and `basiccode/nbv_common.py` together. The command is unchanged:

```powershell
Set-Location basiccode
python C_cstarNBV.py
```

Normal `explore()` now uses incremental state automatically. Direct callers of `evaluate_candidates(known, robot, cache, range_masks)` retain the original reconstruction behavior. To use incremental state directly, create one `UnknownMaskState` per episode, report every newly known cell, and pass it with `unknown_state=state`. The optional observation hook is keyword-only; default return values and the four-element movement tuple are unchanged.

The focused check command, from the repository root, is:

```powershell
python -m unittest tests.test_basiccode_unknown_mask -v
```

Validation status: all 20 focused regressions passed. The default 20x20 run, full repository suite and performance measurements were not executed during this implementation task. This port does not change or reinterpret the original C* formal Experiment 2 result.
