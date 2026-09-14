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
