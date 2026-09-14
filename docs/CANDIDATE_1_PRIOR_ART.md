# Candidate 1 Prior Art and Novelty Assessment

Last updated: 2026-09-14

## Scope

Candidate 1 currently investigates whether expensive Next-Best-View (NBV) information-gain evaluations can be skipped while still returning exactly the same deterministic viewpoint as exhaustive NBV.

This document records the closest prior work found in a focused literature sweep. It does **not** claim novelty from absence of search results.

## Current Candidate 1 Baseline Idea

Given a candidate viewpoint `v`, current information gain `G_t(v)`, and current travel distance `d_t(v)`, exhaustive NBV evaluates

\[
S_t(v)=\frac{G_t(v)}{d_t(v)+\epsilon}
\]

for every candidate and returns a deterministic argmax.

The initial Candidate 1 idea was to cache a previously computed exact gain and use monotonicity of optimistic information gain as an upper bound in future replanning cycles. Candidates would be reevaluated lazily until the exact score of the current best candidate dominates all remaining upper bounds.

## Closest Prior Work

| Work | Relevant mechanism | Cross-cycle reuse | Uses upper-bound pruning | Exact greedy-equivalent selection | Main overlap / distinction |
|---|---|---:|---:|---:|---|
| Minoux, **Accelerated Greedy Algorithms for Maximizing Submodular Set Functions** (1978) | Stores stale marginal gains as upper bounds; reevaluates highest bound first | Across greedy iterations | Yes | Yes, under the lazy-greedy assumptions | Very close algorithmic skeleton. Candidate 1 cannot claim generic stale-value lazy pruning as novel. |
| Golovin & Krause, **Adaptive Submodularity: Theory and Applications in Active Learning and Stochastic Optimization** (2011) | Extends diminishing-return arguments and lazy evaluation to adaptive partially observed decision problems | Across adaptive observations | Yes | Same adaptive greedy choice under stated conditions | Shows that online/adaptive lazy evaluation itself is not new. Candidate 1 needs an exploration-specific admissible bound or structure. |
| Satsangi, Whiteson & Oliehoek, **PAC Greedy Maximization with Efficient Bounds on Information Gain for Sensor Selection** (IJCAI 2016) | Uses inexpensive upper/lower confidence bounds to prune expensive information-gain evaluations | During greedy selection | Yes | Not deterministic exact; PAC/approximate guarantee | Strong conceptual precedent for bound-based pruning of expensive information gain. |
| Selin et al., **Efficient Autonomous Exploration Planning of Large-Scale 3-D Environments** (RA-L 2019) | Sparse gain estimation, caches previously estimated gains, reuses cached points, GP interpolation | Yes | Not the same deterministic certificate | No exact exhaustive-equivalence claim identified | Direct robotics precedent: cross-cycle information-gain caching/reuse is already published. |
| Batinović et al., **A Shadowcasting-Based Next-Best-View Planner for Autonomous 3D Exploration** (2021/2022) | Replaces expensive dense raycasting with recursive shadowcasting / cuboid evaluation | Not the main contribution | No | Not the Candidate 1 certificate | Direct precedent for accelerating NBV gain computation; faster gain evaluation alone is crowded. |
| Naazare, Rosas & Schulz, **Online Next-Best-View Planner for 3D-Exploration and Inspection With a Mobile Manipulator Robot** (2022) | Keeps cached candidate nodes, reevaluates high-gain cached nodes, filters cache | Yes | Threshold/filter based | No exact exhaustive-equivalence claim identified | Selective reevaluation and persistent NBV candidates already exist. |
| Vutetakis & Xiao, **Active Perception Network for Non-Myopic Online Exploration and Visual Surface Coverage** (arXiv 2023) | Difference-aware map updates, memoization, frontier-guided information gain, visibility relations, local reconditioning after map changes | Yes | Uses incremental/local update structure | No exact exhaustive-equivalence certificate identified in the reviewed material | Very close to any generic claim of change-aware incremental visibility/gain maintenance. |
| **PB-NBV: Efficient Projection-Based Next-Best-View Planning Framework for Reconstruction of Unknown Objects** (2025) | Replaces extensive raycasting with projection/ellipsoid approximation | Iterative NBV | No exact certificate | No | Confirms computationally efficient NBV remains an active and crowded area. |

## Main Novelty Risk

The following statements are **not sufficient contributions** for Candidate 1:

- "We cache previous information gains."
- "We lazily reevaluate candidate viewpoints."
- "Previous values are used as upper bounds in the generic lazy-greedy sense."
- "We update only the locally changed part of the map."
- "We avoid some raycasts."
- "We make NBV information-gain computation faster."

All of these have close precedents in either robotics, submodular optimization, or both.

## Refined Research Direction

A potentially stronger direction is an **exploration-specific, change-aware admissible bound** rather than a stale scalar gain alone.

Let `tau(v)` denote the last time candidate `v` was evaluated exactly. At that time cache the set

\[
A_{\tau(v)}(v)
=
\{c:\; c \text{ was UNKNOWN and optimistically visible from } v\}.
\]

Let `U_t` be the set of currently UNKNOWN cells. Under a static deterministic occupancy map with monotone updates and optimistic visibility in which UNKNOWN cells are transparent for planning-time gain evaluation, the following candidate upper bound is proposed:

\[
\overline G_t(v)
=
|A_{\tau(v)}(v)\cap U_t|.
\]

This is at least as tight as the stale scalar bound

\[
G_{\tau(v)}(v)=|A_{\tau(v)}(v)|,
\]

because cells that have left the UNKNOWN state can be removed from the bound without reraycasting the viewpoint.

### Proof sketch for admissibility

Assume `t >= tau(v)`.

1. Monotone map updates imply `U_t` is a subset of `U_tau`.
2. Known occupied cells can only be added, never removed, in the deterministic static model.
3. Planning-time optimistic visibility is blocked only by known occupied cells; UNKNOWN cells do not block rays.
4. If a cell `c` is UNKNOWN and visible from `v` at time `t`, then `c` was also UNKNOWN at `tau(v)` and the ray to `c` could not have been blocked by any occupied cell known at `tau(v)`.
5. Therefore every currently gain-contributing cell must belong to `A_tau(v) ∩ U_t`.

Hence

\[
G_t(v)\le |A_{\tau(v)}(v)\cap U_t|.
\]

The inequality may be strict because a newly discovered occupied cell can occlude cells that remain UNKNOWN behind it.

## Change-Aware Maintenance Idea

Instead of intersecting every cached set with `U_t` from scratch, maintain an inverse incidence index:

\[
I(c)=\{v:\;c\in A_{\tau(v)}(v)\}.
\]

When a cell changes from UNKNOWN to known FREE or known OCCUPIED, decrement the cached upper-bound count only for candidates listed in `I(c)`.

This does **not** attempt to maintain each candidate's exact current gain. It only maintains a guaranteed admissible upper bound cheaply. Newly discovered OCCUPIED cells may create additional occlusion, which makes the bound looser but does not invalidate it.

## Score Certificate

Travel cost is not monotone in the same way and must be recomputed or otherwise bounded correctly at the current planning cycle.

If current exact distance is `d_t(v)`, define

\[
\overline S_t(v)
=
\frac{\overline G_t(v)}{d_t(v)+\epsilon}.
\]

A lazy selector evaluates candidates in descending `\overline S_t`. If an exactly reevaluated candidate `v*` satisfies

\[
S_t(v^*)\ge \max_{v\ne v^*}\overline S_t(v),
\]

with deterministic tie-breaking consistent with the exhaustive baseline, it can certify that `v*` is the same current greedy NBV that exhaustive evaluation would select.

## Why This May Be More Defensible

The proposed gap is **not** generic lazy greedy. The candidate contribution would need to be the combination of:

1. a visibility-structured admissible bound derived specifically from monotone occupancy-map revelation;
2. cheap decremental maintenance of that bound from map-state changes;
3. an exact selection certificate against a defined exhaustive NBV baseline despite evolving map knowledge and current travel cost;
4. explicit treatment of candidate creation/removal, reachability, changing distance, and deterministic ties.

This is still only a **hypothesis of a defensible research gap**. The reviewed literature did not reveal the exact same formulation, but a broader and citation-chained search is still required before any novelty claim.

## Key Distinction to Test Against APN

The closest robotics-side risk is the Active Perception Network's difference-aware visibility and information-gain maintenance.

Candidate 1 must demonstrate a substantive distinction such as:

> APN maintains and incrementally updates view/frontier information to make exploration planning efficient, whereas Candidate 1 would maintain an admissible upper-bound certificate whose purpose is to skip exact viewpoint evaluations while provably returning the same deterministic NBV as an explicitly defined exhaustive evaluator.

This distinction must be checked against the full APN method before being accepted.

## Current Verdict

**Status: MODIFY / CONTINUE RESEARCH, NOT READY TO IMPLEMENT.**

The original "cached monotone gain + lazy upper bound" framing is too close to established lazy-greedy theory and existing NBV caching. Candidate 1 remains potentially viable only if the exploration-specific bound and exact-certificate formulation survives full formalization and deeper prior-art comparison.

## Primary Sources to Revisit

- Michel Minoux, *Accelerated Greedy Algorithms for Maximizing Submodular Set Functions* (1978).
- Daniel Golovin and Andreas Krause, *Adaptive Submodularity: Theory and Applications in Active Learning and Stochastic Optimization* (JAIR 2011), arXiv:1003.3967.
- Yash Satsangi, Shimon Whiteson, Frans A. Oliehoek, *PAC Greedy Maximization with Efficient Bounds on Information Gain for Sensor Selection* (IJCAI 2016), arXiv:1602.07860.
- Magnus Selin et al., *Efficient Autonomous Exploration Planning of Large-Scale 3-D Environments* (IEEE RA-L 2019), DOI: 10.1109/LRA.2019.2897343.
- Ana Batinović et al., *A Shadowcasting-Based Next-Best-View Planner for Autonomous 3D Exploration*, arXiv:2109.09323.
- Menaka Naazare, Francisco Garcia Rosas, Dirk Schulz, *Online Next-Best-View Planner for 3D-Exploration and Inspection With a Mobile Manipulator Robot*, arXiv:2203.10113.
- David Vutetakis, Jing Xiao, *Active Perception Network for Non-Myopic Online Exploration and Visual Surface Coverage*, arXiv:2309.11695.
- *PB-NBV: Efficient Projection-Based Next-Best-View Planning Framework for Reconstruction of Unknown Objects*, arXiv:2501.10663.
