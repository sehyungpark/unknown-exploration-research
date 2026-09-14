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

- **Status:** Superseded after theory/novelty gates
- **Decision:** Mathematical formulation and novelty validation were required before implementation.
- **Rationale:** Those gates have now been completed sufficiently for a minimal correctness implementation.

### D-005 — Scientific Record Integrity

- **Status:** Accepted
- **Decision:** Use the same maps, seeds, sensing range, movement model, and completion targets for comparable algorithms; retain failed and unfavorable results and record tuning and failure reasons.
- **Rationale:** Prevent biased comparisons and preserve falsifiability.

### D-006 — Refined Candidate 1 Assumption Package

- **Status:** Accepted
- **Decision:** The core bound applies only to a finite fixed grid with static deterministic truth, correct monotone belief updates, UNKNOWN-transparent optimistic planning visibility, immutable full viewpoint identity, fixed sensor/ray geometry, unweighted visible-UNKNOWN cardinality gain, and atomic planning snapshots.
- **Rationale:** Minimal counterexamples break admissibility when candidate configuration changes, UNKNOWN is opaque, beliefs revert, obstacles are dynamic, or visibility/range rules change.

### D-007 — Candidate 1 Conditional Theory Verdict

- **Status:** Accepted
- **Decision:** Accept the set-intersection gain bound, inverse-incidence decrement invariant, exact-current-distance score bound, and tie-aware exhaustive-NBV certificate under D-006.
- **Rationale:** The proofs are valid under the fixed assumptions.

## 2026-09-15 — Minimal Deterministic Simulator Freeze

### D-008 — Motion Model

- **Status:** Accepted for first implementation
- **Decision:** Use 8-neighbor movement with orthogonal cost `1` and diagonal cost `sqrt(2)`. Diagonal corner cutting is forbidden; both adjacent orthogonal side cells must be currently known FREE.
- **Rationale:** Keeps movement simple while avoiding unrealistic diagonal passage through blocked corners.

### D-009 — Exact Distance Computation

- **Status:** Accepted for first implementation
- **Decision:** Use one Dijkstra search per planning snapshot over currently known FREE cells to obtain exact current distances to all eligible candidates.
- **Rationale:** The Candidate 1 score certificate requires valid current distances, and one-source Dijkstra avoids per-candidate A* overhead.

### D-010 — Sensor and Visibility Convention

- **Status:** Accepted for first implementation
- **Decision:** Use a 360-degree finite-range discrete sensor with initial range `R=8` cells. Every target-cell center within Euclidean distance `<=R` is checked with one fixed deterministic supercover grid-line convention. Ground-truth OCCUPIED blocks physical sensing; planning-time UNKNOWN is transparent and known OCCUPIED blocks optimistic visibility.
- **Rationale:** Avoids arbitrary angular beam-count effects and exactly instantiates the theorem-critical UNKNOWN-transparent visibility assumption.

### D-011 — Planning Snapshot Semantics

- **Status:** Accepted for first implementation
- **Decision:** Sense only on arrival. Each planning cycle freezes belief and pose after the arrival scan; candidate generation, distance computation, gain evaluation, and target selection use that atomic snapshot. No sensing occurs while traversing the selected path.
- **Rationale:** Prevents map mutation during a correctness certificate.

### D-012 — Candidate Set

- **Status:** Accepted for first implementation
- **Decision:** Every currently reachable known-FREE cell except the robot's current cell is an eligible candidate. No frontier-only restriction and no random subsampling are used in the initial correctness implementation.
- **Rationale:** Candidate 1 accelerates NBV evaluation, not frontier extraction; using the complete reachable known-free set makes the reference behavior deterministic and avoids hiding errors behind sampling.

### D-013 — Candidate Identity

- **Status:** Accepted for first implementation
- **Decision:** Candidate identity is the immutable grid coordinate `(row,col)` under the globally fixed 360-degree sensor convention. Changing range, FOV, orientation dependence, or ray convention requires a new configuration and cache invalidation.
- **Rationale:** Candidate 1 admissibility requires viewpoint identity to preserve every property that affects visibility/gain.

### D-014 — Exhaustive NBV Score and Tie Order

- **Status:** Accepted for first implementation
- **Decision:** Use `S_t(v)=G_t(v)/(d_t(v)+1e-9)`. Deterministic ranking is: larger score, then larger exact gain, then smaller exact distance, then lexicographically smaller `(row,col)`.
- **Rationale:** Provides a total deterministic order that later lazy methods must reproduce exactly.

### D-015 — Initial Correctness Scale

- **Status:** Accepted
- **Decision:** Use deterministic maps around 20x20 first; expand to 60x60 and 120x120 only after correctness is established.
- **Rationale:** Small fixtures make counterexamples and implementation errors easy to inspect before scaling.

### D-016 — First Implementation Gate

- **Status:** GO
- **Decision:** Implement only the minimal simulator, theorem-derived tests, and exhaustive optimistic-NBV reference first. Do not implement stale-lazy or Candidate 1 lazy selection until the exhaustive reference passes review.
- **Rationale:** Later exact-equivalence claims require a trusted oracle.

### D-017 — Concrete Supercover Corner Convention

- **Status:** Accepted for first implementation
- **Decision:** The supercover contains both endpoints and every cell touched by the closed center-to-center segment. At an exact interior-corner crossing, include both side-adjacent cells before the diagonal cell and order the two side cells lexicographically. The covered-cell set must be direction-symmetric. Any OCCUPIED cell strictly before a visibility target blocks that target, while an OCCUPIED target remains visible.
- **Rationale:** D-010 required one deterministic supercover but did not determine corner-touch membership or traversal ordering; those details affect visibility, tests, and all future cached sets.

## Open Decisions

- Benchmark seed sets and randomized-map generators for later empirical scaling experiments.
- Coverage targets and termination reporting for large experiments.
- Raw-result schema and storage location.
- Exact resource-measurement methodology for wall time and memory.
