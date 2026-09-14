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
