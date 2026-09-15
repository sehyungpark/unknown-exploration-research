# Research Log

This is an append-only log of theoretical findings, literature results, hypothesis changes, counterexamples, and other research-significant observations. Entries must label their status as verified, hypothesis, unresolved, preliminary evidence, or refuted.

## 2026-09-14 — Initial Consolidation

### Theoretical Findings

- **Hypothesis:** Under deterministic occupancy updates, fixed candidate poses, uncertainty that only decreases, and an optimistic unknown-transparent visibility model, the exact gain may satisfy \(G_{t+1}(v) \le G_t(v)\).
- **Hypothesis:** A cached gain can serve as a cross-cycle upper bound, allowing exact lazy evaluation to return the same argmax as exhaustive NBV when the current exact best dominates all remaining valid upper bounds.
- **Important condition:** Travel distance is not covered by gain monotonicity and must be recomputed each planning round.
- **Important condition:** Newly introduced candidates require a valid geometric maximum bound, and tie-breaking must match the exhaustive baseline.
- **Counterexample risk:** Treating UNKNOWN cells as opaque can make visibility increase after observations and can therefore break the proposed monotonicity argument.

### Literature and Novelty Status

- **Unresolved:** No documented literature search is available in the repository yet.
- **Unresolved:** Candidate 1's closest prior work and its one-sentence distinction from that work have not been established.
- **Required wording:** Novelty must not be claimed from absence in a limited search; conclusions must remain scoped to the literature actually reviewed.

### Research Hypotheses

- **Current primary hypothesis:** Monotone information upper bounds can substantially reduce exact information-gain evaluations while preserving the exact target choice and target sequence of exhaustive greedy NBV.
- **Unchanged:** Four directions remain under consideration; no final candidate has been selected.
- **Priority decision:** Candidate 1 is investigated first, followed by Candidate 3, Candidate 2, and Candidate 4 for implementation reuse and stability reasons.

### Preliminary Observations Retained from Existing Context

- **Preliminary evidence, not repository-verified:** Candidate 1 toy runs reportedly matched exhaustive target sequences and moves while reducing exact gain evaluations.
- **Preliminary evidence, not repository-verified:** Candidate 2 toy runs reportedly showed that blind prediction can fail while a baseline and robust gate succeed, without guaranteeing shorter paths.
- **Preliminary evidence, not repository-verified:** Candidate 3 toy runs reportedly used fewer sensor evaluations with sequential evidence accumulation than fixed repeated sensing; the stopping rule is not yet a rigorous confidence-sequence result.
- **Preliminary evidence, unfavorable:** Candidate 4 low-recourse repair reportedly reduced recourse but substantially increased viewpoint count on some maps.

The run metadata needed to reproduce or independently verify these observations is unavailable; the corresponding legacy records are preserved in `docs/EXPERIMENT_LOG.md`.

## 2026-09-14 — Candidate 1 Focused Prior-Art Review

### Verified Literature Findings

- **Verified:** Generic lazy-greedy acceleration is established prior art. Minoux's accelerated greedy method stores stale marginal gains as upper bounds, reevaluates the largest bound first, and can recover the same greedy choice under the relevant diminishing-return condition.
- **Verified:** Adaptive lazy evaluation under partial observability is also established prior art via adaptive submodularity (Golovin & Krause). Therefore, "online/adaptive lazy evaluation" by itself is not a defensible novelty claim.
- **Verified:** Robotics NBV already uses cross-cycle information-gain caching. Selin et al. (RA-L 2019) explicitly cache previously estimated gains and reuse cached points for faster queries.
- **Verified:** Persistent candidate caches and selective reevaluation also exist in later NBV planners such as Naazare et al. (2022).
- **Verified:** Efficient gain computation through alternative visibility evaluation, including recursive shadowcasting, is prior art (Batinović et al.).
- **Verified:** Difference-aware incremental map updates, memoization, and local reconditioning of view/frontier information appear in the Active Perception Network (Vutetakis & Xiao, arXiv:2309.11695).
- **Verified:** Bound-based pruning of expensive information-gain evaluations exists in adjacent sensor-selection literature, e.g. PAC Greedy Maximization with Efficient Bounds on Information Gain (Satsangi et al., IJCAI 2016), though that result is probabilistic/approximate rather than the proposed deterministic NBV certificate.

### Refuted / Weakened Novelty Claims

- **Refuted as a standalone novelty claim:** "Cache previous gain values."
- **Refuted as a standalone novelty claim:** "Use stale gains as upper bounds and lazily reevaluate candidates."
- **Refuted as a standalone novelty claim:** "Only update locally changed map regions."
- **Refuted as a standalone novelty claim:** "Reduce NBV raycasting cost."

### Refined Candidate 1 Hypothesis

- **Hypothesis:** Candidate 1 may remain viable if it contributes an exploration-specific admissible bound that is tighter than the stale scalar gain and can be maintained cheaply from occupancy-state changes while still certifying the exact same deterministic NBV as an exhaustive evaluator.
- **Proposed bound:** If `tau(v)` is the last exact-evaluation time and `A_tau(v)` is the set of cells that were UNKNOWN and optimistically visible from viewpoint `v` then, under the static deterministic unknown-transparent model,

  \[
  \overline G_t(v)=|A_{\tau(v)}(v)\cap U_t|
  \]

  is a candidate upper bound on current exact gain `G_t(v)`.
- **Proposed maintenance:** Maintain an inverse incidence index from each previously visible unknown cell to the candidate viewpoints whose cached visible-unknown set contains that cell. When a cell changes from UNKNOWN to known, decrement the affected candidates' bound counts without reraycasting them.
- **Important distinction:** Newly discovered occupied cells may occlude currently unknown cells that remain in the cached set; this makes the bound looser but should not violate admissibility.
- **Exact certificate goal:** Recompute current travel distances correctly; lazily exact-evaluate candidates in descending score upper bound; terminate only when the current exact best dominates all remaining score upper bounds using the same deterministic tie-breaking as exhaustive NBV.

### Current Verdict

- **Status: MODIFY / CONTINUE RESEARCH.** The original cached scalar monotone-gain framing is too close to established lazy-greedy theory and existing NBV caching.
- Candidate 1 is **not ready for implementation** until the exploration-specific bound, its proof, candidate lifecycle, and exact-certificate conditions are formalized and compared carefully against APN and related work.
- Detailed comparison is recorded in `docs/CANDIDATE_1_PRIOR_ART.md`.

## 2026-09-14 — Refined Candidate 1 Theory Gate

### Verified Theoretical Results

- **Verified under explicit assumptions:** For a persistent immutable viewpoint, static deterministic truth, correct monotone belief updates, fixed sensor/ray geometry, and UNKNOWN-transparent planning visibility,

  \[
  G_t(v)\le \overline G_t(v)=|A_{\tau(v)}(v)\cap U_t|.
  \]

- **Verified:** \(\overline G_t(v)\le G_{\tau(v)}(v)\); the first inequality is strict when newly known cells are removed from the cached set, while the admissibility inequality can be strict when a newly discovered obstacle occludes still-UNKNOWN cached cells.
- **Verified:** An inverse incidence index \(I(c)=\{v:c\in A_{\tau(v)}(v)\}\) preserves the exact cached-intersection count when each UNKNOWN-to-known transition decrements every current member exactly once.
- **Verified:** Combining the gain bound with the exact current distance yields a score upper bound. A separately proved distance lower bound could be used only as a future extension.
- **Verified:** Exact exhaustive-NBV equivalence requires a tie-aware certificate. Numerical \(\ge\) alone is insufficient if an equal-score competitor is preferred by the deterministic baseline.

### Counterexamples and Required Assumptions

- **Counterexample found:** With opaque UNKNOWN cells, a 1×3 ray containing two UNKNOWN cells violates the bound after the nearer cell becomes FREE and reveals the farther UNKNOWN cell.
- **Counterexamples found:** Reusing an identity after candidate position or orientation changes can make current visible UNKNOWN cells absent from the cached set.
- **Counterexamples found:** Belief reversion, dynamic-obstacle removal, increased range/FOV, changed ray discretization, or a changed visibility/gain definition can reveal previously uncached UNKNOWN cells and violate admissibility.
- **Required:** Candidate identity includes position, orientation when relevant, range, FOV, and ray convention; selection operates on an atomic snapshot.

### Candidate Lifecycle Result

- **Verified:** A new candidate may be evaluated exactly or initialized with the geometric footprint bound \(|U_t\cap\mathcal F(v)|\), where \(\mathcal F(v)\) ignores all occlusion. The global bound \(|U_t|\) is also admissible but looser.
- **Verified:** Unreachable candidates must be excluded from the eligible set; candidate-set changes are valid only if every new member has a proven bound and deleted members are removed from the certificate.

### Theory Verdict and Novelty Status

- **Theory Gate: PASS, conditional.** The refined bound, decremental maintenance invariant, score bound, and tie-aware exact-selection theorem are logically valid under the stated assumptions.
- **Unresolved:** This PASS does not establish novelty, useful tightness, runtime improvement, or implementation readiness.
- **Novelty risk remains high:** Stale-bound priority evaluation and exact-greedy certification are prior art, while APN is close on difference-aware visibility maintenance. Full-method comparison remains required.
- Full definitions, proofs, counterexamples, lifecycle rules, and prior-art comparison are recorded in `docs/CANDIDATE_1_FORMULATION.md`.

## 2026-09-14 — Candidate 1 Full-Method Novelty Gate

### Additional Verified Prior-Art Findings

- **Verified:** AEP (Selin et al., 2019) goes beyond simple caching: it explicitly treats potential information gain as monotonically decreasing over time under its assumptions, selectively recalculates potentially affected cached points, and uses GP interpolation for unevaluated queries. Therefore monotonic gain, cache reuse, and affected-region refresh are established prior art.
- **Verified:** Full-method review of APN confirms difference-aware incremental regulation, memoization, view-to-frontier visibility relations, and inverse frontier-to-view visibility relations. Therefore change-aware updates and inverse visibility indexing cannot be claimed as new by themselves.
- **Verified:** FrontierNet (Sun et al., 2025) explicitly decreases a stored/predicted frontier information gain using currently known voxels, with an update of the form `g'_i = g_i - |V_known^i|`. Therefore the intuitive idea "subtract newly known cells/voxels from old gain" is not a standalone contribution.
- **Verified:** Lin et al. (Measurement Science and Technology, 2026) use submodular information-gain accounting and branch gain upper bounds to prune low-potential branches during sampling-based UAV exploration. Therefore generic information-gain upper-bound pruning in robotic exploration is not a standalone contribution.
- **Verified:** Low & Lastra's hierarchical NBV work is a strong earlier precedent for accelerating otherwise exhaustive NBV evaluation while retaining a high-resolution search over view space.

### What Was Not Identified

- **Not identified in reviewed literature:** The exact combination of an exact cached optimistic visible-UNKNOWN set, the bound
  \[
  \overline G_t(v)=|A_{\tau(v)}(v)\cap U_t|,
  \]
  maintained deliberately as a conservative certificate, followed by lazy exact reevaluation with a deterministic tie-aware theorem guaranteeing the same current target as an explicitly defined exhaustive optimistic-NBV evaluator.
- **Important qualification:** Failure to identify an equivalent method is not proof that none exists. Any future manuscript must scope its novelty statement to the reviewed literature and avoid absolute "first" claims unless independently justified.

### Novelty Gate Verdict

- **Novelty Gate: PROVISIONAL PASS — HIGH RISK, NARROW CLAIM ONLY.**
- **Rejected broad claim:** Candidate 1 is not novel as caching, monotone gain, known-cell decrement, changed-region maintenance, inverse visibility mapping, lazy evaluation, or upper-bound pruning individually.
- **Remaining defensible hypothesis:** the contribution is the exploration-specific admissible cached-set bound plus decremental maintenance plus exact exhaustive-NBV selection certificate as one narrowly specified method.
- **Implementation status:** CONDITIONAL GO for a minimal deterministic implementation whose purpose is to test correctness and empirical computational value, not to assume the candidate is already a successful final research contribution.

### Empirical Gate Requirements

- Compare exhaustive optimistic NBV, stale-scalar lazy bound, and the proposed change-aware cached-set bound.
- Require exact argmax and target-sequence equality to exhaustive NBV before making efficiency claims.
- Measure exact gain-evaluation count, wall-clock planning time, distance-computation time, bound/index maintenance time, and memory usage.
- **Drop or modify** Candidate 1 if total overhead erases the reduction in exact gain evaluations or if the change-aware bound is not materially tighter than the stale scalar bound.

## 2026-09-15 — Deterministic Simulator and Exhaustive Reference

### Verified Implementation Results

- **Verified by tests:** The minimal common simulator now enforces finite rectangular truth/belief grids, correct monotone UNKNOWN-to-known observation batches, exact pose, known-FREE-only 8-neighbor movement, and prohibited diagonal corner cutting.
- **Verified by tests:** Physical sensing exposes the first OCCUPIED target and blocks cells behind it; planning visibility keeps UNKNOWN transparent and returns the exact visible-UNKNOWN cell set rather than only its cardinality.
- **Verified by tests:** One Dijkstra search supplies current distances and reachable candidate membership for each exhaustive planning call.
- **Verified by tests:** The exhaustive optimistic-NBV reference evaluates every eligible candidate, applies the specified score and total tie order, returns structured evaluation data, and deterministically stops when every eligible gain is zero.
- **Verified by tests:** The simulator performs an initial scan and thereafter uses atomic arrival-scan snapshots with no sensing while moving.
- **Verified by tests:** Repeated execution from the same deterministic fixture produces identical targets, paths, belief states, and scan counts.
- **Test result:** 29 tests passed on 2026-09-15.

### Specification Finding

- **Resolved underspecification:** The prior specification required one deterministic supercover but did not define exact corner-touch traversal. The first implementation now includes both endpoints and both side-adjacent cells when a center-to-center segment crosses an interior grid corner. Covered-cell sets are direction-symmetric, and side-cell traversal order is lexicographic.
- **No contradiction found:** The frozen movement, sensing, candidate, score, tie, and atomic-cycle assumptions were mutually implementable.

### Scope

- **Not implemented:** stale-scalar lazy evaluation, Candidate 1 cached sets, inverse-incidence maintenance, and proposed lazy selection.
- **No research experiment executed:** This entry records implementation verification only, so no experiment result was added to `docs/EXPERIMENT_LOG.md`.

## 2026-09-15 — Exhaustive Oracle Hardening and Experiment 0 Preregistration

### Exhaustive Oracle Bug Found and Corrected

- **Verified bug:** `physical_visible_cells` discarded a blocked target ray without adding the intermediate first-hit OCCUPIED cell encountered on that ray. This violated the frozen physical-sensing rule that the first occupied hit is visible itself.
- **Observed consequence:** Corner-inclusive wall geometry could leave physically encountered wall cells UNKNOWN, producing persistent optimistic gain and repeated no-progress selections on `separated_rooms`, `clutter`, and `maze_like` during the first end-to-end test attempt.
- **Correction:** Physical target rays now add traversed cells through and including the first OCCUPIED cell, then stop. No score, candidate, planning-visibility, movement, or tie assumption changed.
- **Regression coverage:** A blocked corner-crossing ray must retain its intermediate first hit, while its rear target remains occluded.

### Verified Test Results

- **Verified:** Physical corner-touch OCCUPIED side cells are visible and block diagonal targets; FREE corner-touch cells do not spuriously block.
- **Verified:** Planning-time corner-touch side cells behave as specified: FREE and UNKNOWN transmit, while OCCUPIED blocks a rear UNKNOWN target.
- **Verified:** The theorem implementation satisfies set inclusion

  \[
  A_t(v)\subseteq A_{\tau(v)}(v)\cap U_t
  \]

  across 38,673 checked transitions: complete monotone state-pair enumeration on short 1D rays, all single-cell FREE/OCCUPIED revelations across 3×3 belief states, five 4×4 multi-cell/corner batches, and 512 randomized transitions from fixed seed `20260915` under static consistent truth.
- **Verified negative regressions:** Increasing sensor range or changing viewpoint coordinate can invalidate an old cached set. The existing opaque-UNKNOWN counterexample remains active.
- **Verified end to end:** All seven fixtures reached explicit `EXPLORATION_COMPLETE` before their safety limits, and two independent runs per fixture produced identical selected targets, paths, final belief, final pose, scan count, and planning-cycle count.
- **Fixture results:** `open` 14 selected/15 planning cycles/15 scans; `single_room` 12/13/13; `corridor` 4/5/5; `dead_end` 6/7/7; `separated_rooms` 11/12/12; `clutter` 11/12/12; `maze_like` 24/25/25.
- **Full suite:** 39 tests passed on 2026-09-15.

### Preregistration and Scope

- **Preregistered, not executed:** `docs/EXPERIMENT_0_PREREGISTRATION.md` freezes zero-tolerance exact target/sequence endpoints, shared conditions, cycle log fields, failure rules, and the correctness gate for Algorithms A/B/C.
- **Pending before execution:** The random small-map generator, seed list, map count, acceptance policy, and safety limits.
- **No research experiment executed:** These were oracle/test-hardening runs, so no performance result was appended to `docs/EXPERIMENT_LOG.md`.
- **Still not implemented:** stale-scalar lazy selection, proposed change-aware lazy selection, and runtime inverse-incidence structures.

## 2026-09-15 — Experiment 0 Random Dataset and Logging Freeze

### Verified Reproducibility Results

- **Verified by tests:** The frozen local-RNG generator reproduces the same map for the same candidate seed without changing Python's global random state; distinct tested seeds produce different map contents.
- **Verified by tests:** Repeated master-seed materialization produces the same 60 dataset IDs, candidate seeds, and map hashes.
- **Verified by tests:** The frozen artifact contains exactly 20 accepted maps at each of 12×12, 16×16, and 20×20, with the preregistered 7 sparse / 7 medium / 6 dense split within each size.
- **Verified by tests:** Every accepted start is FREE, lies in the deterministically selected largest traversable FREE component, and follows the center-distance and lexicographic tie rules.
- **Verified by tests:** Every frozen map regenerates to its recorded SHA-256 hash; changing ground-truth or belief content changes the corresponding canonical hash.
- **Verified by tests:** Explicit no-FREE, no-OCCUPIED, fragmented-component, and immediate-initial-stop candidates receive stable rejection reasons.
- **Full suite:** 59 tests passed on 2026-09-15 (39 existing simulator/oracle tests plus 20 dataset/hash/config tests).

### Specification Resolution

- **Resolved underspecification:** FREE-component connectivity had not been defined. Experiment 0 now uses the existing 8-neighbor/no-diagonal-corner-cutting traversability rule so component membership matches executable motion.
- **Resolved byte-level ambiguity:** Ground-truth and belief hashes now use row-major UTF-8 ASCII with one LF after every row, including the final row, before SHA-256.
- **Frozen artifact observation:** Master seed `20260915` produced 60 accepted candidates without a rejection. The empty rejected-candidate list and empty reason summary remain explicit parts of the artifact; deterministic rejection paths are still covered by tests.

### Research Status and Scope

- **Unchanged hypothesis:** No empirical claim about Candidate 1 was tested or changed. This work freezes inputs and diagnostics for the future exact-equivalence experiment.
- **Not executed:** No A/B/C comparison, exact-equivalence run, performance benchmark, runtime measurement, or research experiment was executed.
- **Not implemented:** Algorithms B/C, lazy selection, inverse-incidence runtime state, priority queues, and certificate runtime logic remain absent.

## 2026-09-15 — Experiment 0 v1 Denominator Mismatch and v2 Refreeze

### Mismatch and Impact

- **Verified specification mismatch:** The v1 code accepted maps using `largest_free_component_size / total_FREE_cell_count >= 0.35`, while the intended preregistered rule was `largest_free_component_size / (height * width) >= 0.35`.
- **Why it matters:** The old denominator can accept a fragmented or obstacle-heavy map even when its largest traversable component occupies less than 35% of the complete grid. Deterministic counterexample `size=3, p=0.30, seed=8` has component size 2 and four FREE cells: `2/4=0.50` passes the old rule, but `2/9≈0.222` fails the intended rule.
- **Timing:** The mismatch was detected before Algorithm B or C existed and before any cross-method Experiment 0 execution or result. No lazy outcome informed the correction.

### Correction and Frozen Result

- **Invalidated:** `experiment-0-random-v1` is retained in repository history but is invalid for Experiment 0.
- **Corrected freeze:** `experiment-0-random-v2` uses the total grid-cell denominator and was regenerated from the unchanged master seed `20260915` using the unchanged candidate-seed derivation and Bernoulli generator.
- **Verified materialization:** v2 retains 60 accepted maps with 20 per size and 7 sparse / 7 medium / 6 dense per size. It retains one rejected candidate: index 34, size 16, dense, seed `610347355546169441`, reason `largest_component_fraction_below_0.35` because `79/256 < 0.35`.
- **Verified stream handling:** The rejected seed consumed its normal position. Consequently, 26 of 60 dataset-ID positions have different accepted seeds and hashes from v1.
- **Full suite:** 60 tests passed on 2026-09-15 (39 existing simulator/oracle tests plus 21 corrected dataset/hash/config tests).
- **Scope:** This was a dataset correction and test/refreeze operation, not an A/B/C correctness experiment or performance benchmark. The logging/failure-artifact schema did not require a change.
- **Still not implemented:** Algorithms B/C, inverse-index runtime state, lazy certificates, the cross-method runner, and performance benchmarking remain absent.

## 2026-09-15 — Algorithm B Stale-Scalar Exact-Lazy Baseline

### Implementation and Semantics

- **Implemented:** Algorithm B is now a stateful planner independent of Algorithm A. It does not call `exhaustive_nbv`, read exhaustive evaluations, or obtain skipped exact gains from the oracle.
- **Cache semantics:** The persistent cache contains only `candidate coordinate -> last exact nonnegative integer gain`. Ineligible coordinates, including the current robot coordinate, retain their entries for valid later reuse; no visible-UNKNOWN sets or inverse incidence are stored.
- **New-candidate policy:** Every currently eligible candidate without a cache entry is evaluated exactly in that snapshot, and that exact gain initializes its scalar entry.
- **Current-distance rule:** Every planning call performs one Dijkstra search on the frozen current belief. Stale gains are combined only with current exact distances; distances are never cached across snapshots.
- **Exact evaluation:** B directly calls the common optimistic visible-UNKNOWN computation. Exact reevaluation refreshes only that candidate's scalar gain.
- **Tie-aware certificate:** The current best exact candidate is selected only when its exhaustive rank key is strictly earlier than every remaining candidate's optimistic rank key formed from stale upper gain, current distance, score, and immutable coordinate. A numeric score `>=` check alone is not used.
- **Completion certificate:** B stops only when the eligible set is empty or every current exact/stale gain upper bound is zero.

### Development Correctness Regression

- **Verified:** All seven fixed fixtures matched Algorithm A at every shared frozen snapshot through the same terminal stop event. Target mismatches: **0**. Sequence/termination divergences: **0**.
- **Verified:** All 60 accepted maps in frozen `experiment-0-random-v2` were regenerated only from their canonical records and rechecked against the recorded seed, map hash, start, and cycle limit. A/B target mismatches: **0**. Sequence/termination divergences: **0**.
- **Verified:** Every checked persistent stale scalar dominated Algorithm A's independent current exact gain. Stale-bound violations: **0**.
- **Verified:** Synthetic certificate tests cover clear score dominance; equal-score gain ordering in both directions; equal-score/equal-gain distance ordering; and full numeric ties resolved by coordinate. Tie-certificate violations: **0**.
- **Verified:** Cache lifecycle tests cover exact first-seen initialization, independent refresh/retention, current-distance recomputation, temporary current-robot exclusion and reuse, zero-bound completion, nonnegative scalar enforcement, and single-entry update isolation.
- **Verified:** At least one deterministic shared-snapshot run selected the same target as A while safely leaving at least one eligible candidate bound-only for that cycle.
- **Full suite:** **72 tests passed** on 2026-09-15.

### Bug Findings and Scope

- **No new pre-existing simulator or exhaustive-oracle bug was found.** The first targeted Algorithm B unit, fixture, and frozen-v2 regression runs completed without a target, bound, sequence, termination, or tie failure, so no outcome-driven algorithm correction was made.
- This was baseline implementation and development correctness regression, not the preregistered three-method Experiment 0 and not an efficiency experiment. No runtime advantage, speedup, or aggregate performance result is claimed.
- **Not implemented:** Algorithm C cached visible-UNKNOWN sets, cached-intersection bounds, inverse incidence, decremental maintenance, priority queues, and C comparison.
