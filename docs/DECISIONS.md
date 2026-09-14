# Decisions

This file records research assumptions and decisions that affect formulation, implementation, or evaluation. Update existing decisions when their status changes while preserving the history and rationale.

## 2026-09-14 — Initial Decisions Consolidated from Existing Documents

### D-001 — Research Scope

- **Status:** Accepted
- **Decision:** Study algorithm design, analysis, comparison, and validation in simulation for static unknown environments with a single agent, exact pose, and no SLAM or localization-error research.
- **Rationale:** This isolates exploration and map-reconstruction algorithms from physical-robot and localization concerns.

### D-002 — Shared Simulator Architecture

- **Status:** Accepted
- **Decision:** Candidates 1–4 will share one simulator; candidate-specific planners or map models will be replaceable components rather than separate simulators.
- **Rationale:** Shared infrastructure is required for fair comparisons and reproducibility.

### D-003 — Candidate Investigation Order

- **Status:** Accepted, not a final candidate ranking
- **Decision:** Investigate Candidate 1 first, then Candidate 3, Candidate 2, and Candidate 4.
- **Rationale:** The order prioritizes common-code reuse and implementation stability.

### D-004 — Candidate 1 Before Coding

- **Status:** Accepted
- **Decision:** Complete mathematical formulation and novelty validation before implementing Candidate 1 or the common simulator.
- **Rationale:** The monotonicity and exactness claims, plus differentiation from prior lazy/caching work, are central to Candidate 1's research value.

### D-005 — Scientific Record Integrity

- **Status:** Accepted
- **Decision:** Use the same maps, seeds, sensing range, movement model, and completion targets for comparable algorithms; retain failed and unfavorable results and record tuning and failure reasons.
- **Rationale:** Prevent biased comparisons and preserve falsifiability.

## Open Decisions

- 4-neighbor versus 8-neighbor movement
- Exact sensor ray discretization and initial sensing range
- Exact Candidate 1 gain and utility definitions
- Candidate generation and lifecycle rules
- Benchmark map sizes, seed sets, and completion thresholds
- Raw-result schema and storage location
