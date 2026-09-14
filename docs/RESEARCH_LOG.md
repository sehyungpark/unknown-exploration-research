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
