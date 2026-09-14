# Minimal Deterministic Simulator Specification

Last updated: 2026-09-15

## Purpose

This specification defines the smallest common simulator needed to test Candidate 1 against a deterministic exhaustive optimistic-NBV reference. It is intentionally simple. Its purpose is correctness and controlled computational comparison, not physical realism.

## 1. World and Belief

- Finite 2D rectangular occupancy grid.
- Ground-truth cell state: `FREE` or `OCCUPIED`.
- Belief cell state: `UNKNOWN`, `FREE`, or `OCCUPIED`.
- Static deterministic ground truth.
- Exact robot pose; no SLAM or localization uncertainty.
- Belief updates are correct and monotone only:
  - `UNKNOWN -> FREE`
  - `UNKNOWN -> OCCUPIED`
- No belief reversion is allowed in Candidate 1 correctness experiments.

Initial correctness fixtures should normally use 20x20 maps. Larger 60x60 and 120x120 maps are reserved for later scaling experiments.

## 2. Robot Motion

- Motion graph: 8-connected grid.
- Orthogonal step cost: `1`.
- Diagonal step cost: `sqrt(2)`.
- Diagonal corner cutting is **not allowed**: a diagonal move is legal only when both orthogonally adjacent side cells are currently known `FREE`.
- Robot may traverse only currently known `FREE` cells.
- Current shortest-path distances are exact for the planning snapshot.
- One Dijkstra search from the robot cell should be used to obtain exact distances to all currently reachable known-free cells.

## 3. Sensor Geometry

For the minimal deterministic simulator, avoid arbitrary angular beam-count discretization.

- Sensor field of view: 360 degrees.
- Sensor range for initial correctness experiments: `R = 8` cells measured by Euclidean center-to-center distance.
- Every grid cell whose center lies within Euclidean distance `<= R` of the sensor cell is a potential target cell.
- Visibility between the sensor cell and a target cell is evaluated using one fixed deterministic **supercover grid line** convention.
- The same supercover convention must be used everywhere in sensing, planning-time visibility, tests, and Candidate 1 caching.
- Cells outside the finite grid do not exist and do not contribute information.

The first implementation fixes that convention as follows:

- The closed line segment connects the source and target cell centers.
- Both source and target cells are included.
- Every cell touched by the segment is included.
- If the segment passes exactly through an interior grid corner, both side-adjacent cells at that corner are included before the diagonal cell; the two side cells use lexicographic order for deterministic traversal.
- The covered-cell set is direction-symmetric. For target-cell visibility, any OCCUPIED cell in the covered sequence strictly before the target blocks that target; an OCCUPIED target itself remains visible.

This target-cell line-of-sight definition is the discrete sensor convention for the first study. Later work may study angular beam sensors separately, but changing the ray convention invalidates cached Candidate 1 bounds and must start a new experiment configuration.

## 4. Physical Sensor Visibility

Physical sensing uses the static ground-truth map.

For each target cell within range:

- The line from the robot to the target is traversed by the fixed supercover convention.
- Ground-truth `FREE` cells do not block visibility.
- The first ground-truth `OCCUPIED` cell on a line is visible itself and blocks cells strictly behind it on that line.
- Every physically visible target cell is written correctly into the belief map as `FREE` or `OCCUPIED`.

The initial robot cell is known `FREE`, and one physical scan is performed at the start before the first planning decision.

## 5. Planning-Time Optimistic Visibility

Planning-time information gain is evaluated only on the current belief snapshot.

For line traversal:

- `FREE`: transparent.
- `UNKNOWN`: transparent and, if the target cell is currently `UNKNOWN`, may contribute one unit of gain.
- `OCCUPIED`: blocks visibility; an occupied cell itself does not contribute gain.

Thus planning-time UNKNOWN is intentionally transparent. This is a theorem-critical assumption.

For candidate viewpoint `v`, let `A_t(v)` be the set of cells that are both:

1. currently `UNKNOWN`, and
2. optimistically visible from `v` under the fixed planning-time visibility rule.

Then exact gain is

\[
G_t(v)=|A_t(v)|.
\]

## 6. Planning Snapshot Semantics

Each planning cycle is atomic:

1. Finish the previous movement.
2. Perform one physical scan at the reached target.
3. Apply all resulting belief updates.
4. Freeze the belief map and robot pose as planning snapshot `t`.
5. Generate candidates and exact current distances from this frozen snapshot.
6. Select one target.
7. Execute the complete shortest path to that target **without sensing en route**.
8. Begin the next cycle with a physical scan at arrival.

This avoids asynchronous map changes during a selection certificate. Continuous sensing while moving is deferred.

## 7. Candidate Set

The first correctness implementation must avoid frontier-specific assumptions.

Eligible candidate viewpoints are:

- every currently reachable known-`FREE` grid cell,
- excluding the robot's current cell.

No random candidate sampling is used in the initial correctness tests.

Candidate identity is the immutable grid coordinate `(row, col)` under this global fixed sensor convention. Because the minimal sensor is 360-degree and has no orientation parameter, orientation is not part of identity. If FOV, range, ray convention, or orientation later becomes candidate-specific, identity must be extended and old caches invalidated.

Visited candidate cells are not removed merely because they were visited. If their exact gain is zero, the scoring rule will naturally make them noncompetitive.

Unreachable known-free cells are not eligible.

## 8. Exhaustive NBV Reference

For every eligible candidate `v`, compute exact current gain `G_t(v)` and exact current distance `d_t(v)`.

Use

\[
S_t(v)=\frac{G_t(v)}{d_t(v)+\epsilon}
\]

with fixed

\[
\epsilon = 10^{-9}.
\]

The exhaustive reference evaluates every eligible candidate before selecting a target.

If all eligible candidates have zero exact gain, exploration terminates for the current simulator configuration.

## 9. Deterministic Total Tie Order

Candidate ranking is a total deterministic order:

1. larger score `S_t(v)` is better;
2. if scores are exactly equal in the implementation's numeric representation, larger exact gain is better;
3. if still tied, smaller exact distance is better;
4. if still tied, lexicographically smaller candidate ID `(row, col)` is better.

All lazy certificates must reproduce this same order exactly. Do not introduce an independent tolerance-based tie rule without changing this specification and the proof obligations.

## 10. Initial Deterministic Map Fixtures

At minimum provide small fixed maps representing:

- open area;
- single room;
- straight corridor;
- corridor with dead end;
- separated rooms connected by doorways;
- cluttered obstacles;
- maze-like layout.

Each fixture must include a fixed FREE start cell.

## 11. Required Correctness Tests Before Lazy Methods

Unit/integration tests must cover at least:

- supercover line symmetry and endpoint convention;
- physical first-hit occlusion;
- planning UNKNOWN transparency;
- newly discovered occupied cell blocking still-UNKNOWN cells behind it;
- the minimal opaque-UNKNOWN counterexample showing why the theorem would fail under a different visibility rule;
- 8-neighbor movement and no diagonal corner cutting;
- exact reachability and Dijkstra distances;
- candidate eligibility;
- deterministic total tie order;
- atomic planning-cycle semantics;
- exhaustive gain-set contents `A_t(v)`, not only counts.

## 12. Deferred Choices

The following are deliberately **not** part of the first implementation:

- SLAM or pose noise;
- dynamic obstacles;
- probabilistic occupancy reversion;
- sensing while moving;
- frontier-only candidate generation;
- RRT;
- reinforcement learning;
- learned gain prediction;
- 3D maps;
- orientation-dependent sensor FOV;
- arbitrary angular beam-count sensors.

Any later experiment introducing these must define a new configuration and re-check Candidate 1 admissibility assumptions.
