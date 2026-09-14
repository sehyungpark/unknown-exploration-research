# Candidate 1 Prior Art and Novelty Assessment

Last updated: 2026-09-14

## Scope

Candidate 1 investigates whether expensive Next-Best-View (NBV) information-gain evaluations can be skipped while still returning exactly the same deterministic viewpoint as an explicitly defined exhaustive optimistic-NBV evaluator.

This document records the closest prior work found in focused and citation-chained literature searches. It does **not** claim novelty from absence of search results. A literature search can establish close precedents and weaken claims, but cannot prove that no equivalent method exists anywhere.

## Current Candidate 1 Baseline Idea

Given candidate viewpoint `v`, current exact planning-time information gain `G_t(v)`, and current travel distance `d_t(v)`, exhaustive NBV evaluates

\[
S_t(v)=\frac{G_t(v)}{d_t(v)+\epsilon}
\]

for every eligible candidate and returns a deterministic argmax.

The refined Candidate 1 caches the exact visible-unknown set at the last exact evaluation time `tau(v)`,

\[
A_{\tau(v)}(v),
\]

and maintains the change-aware admissible bound

\[
\overline G_t(v)=|A_{\tau(v)}(v)\cap U_t|.
\]

The current exact distance is combined with this gain bound to form a score bound. Candidates are exactly reevaluated only while needed for a tie-aware certificate that the selected viewpoint is the same as the exhaustive evaluator.

## Closest Prior Work

| Work | Relevant mechanism | Direct overlap | Important distinction from refined Candidate 1 |
|---|---|---|---|
| Minoux, **Accelerated Greedy Algorithms for Maximizing Submodular Set Functions** (1978) | Stale marginal gains are upper bounds; highest bound is reevaluated first; lazy evaluation can reproduce the same greedy choice. | Very high at the generic algorithmic level. | Does not provide the occupancy-revelation-specific cached visible-unknown bound. Generic lazy upper-bound selection itself is not novel. |
| Golovin & Krause, **Adaptive Submodularity** (2011) | Extends diminishing-return reasoning and lazy evaluation to adaptive partially observed decisions. | High conceptual overlap. | Does not by itself establish the proposed occupancy-grid visibility bound. Adaptive/online lazy evaluation is not novel. |
| Satsangi, Whiteson & Oliehoek, **PAC Greedy Maximization with Efficient Bounds on Information Gain for Sensor Selection** (IJCAI 2016) | Uses cheap upper/lower confidence bounds to prune expensive information-gain calculations. | Strong precedent for bound-based IG pruning. | Provides probabilistic/approximate guarantees, not the proposed deterministic equality to an exhaustive optimistic-NBV evaluator. |
| Low & Lastra, **Adaptive Hierarchical NBV / Efficient Constraint Evaluation** (2006) | Exploits spatial hierarchy and coherence to make exhaustive NBV view evaluation much faster. | Strong precedent for accelerating exhaustive NBV without simply replacing it by a learned policy. | Primarily accelerates within-cycle view/constraint evaluation through hierarchy, rather than maintaining a cross-cycle change-aware cached-cell upper-bound certificate. |
| Selin et al., **Efficient Autonomous Exploration Planning of Large-Scale 3-D Environments** (RA-L 2019, AEP) | Caches previous potential-gain queries, uses GP interpolation, selectively recalculates affected cached points, and explicitly notes that its potential information gain is monotonic decreasing over time under its assumptions. | Very high. Monotone cross-cycle gain and gain caching are explicit prior art. | AEP uses cached measurements/GP estimates and affected-region recomputation. In the reviewed full text, no exact cached-visible-set bound or theorem certifying the same deterministic argmax as exhaustive NBV was identified. |
| Border & Gammell, **SEE++ / Proactive Estimation of Occlusions and Scene Coverage** (2020/2021) | Maintains a frontier visibility graph, removes invalid frontiers, adds new frontier-view pairs, and locally updates graph connectivity after new measurements. | High for dynamic view↔target visibility maintenance. | Does not match the proposed cached UNKNOWN-cell upper bound or exact exhaustive-NBV selection certificate in the reviewed method. |
| Batinović et al., **A Shadowcasting-Based Next-Best-View Planner for Autonomous 3D Exploration** (2021/2022) | Replaces expensive dense raycasting with recursive shadowcasting/cuboid gain evaluation. | Shows NBV gain-computation acceleration is crowded. | Focus is faster gain computation, not cross-cycle admissible-bound pruning with exact target equivalence. |
| Naazare, Rosas & Schulz, **Online Next-Best-View Planner for 3D-Exploration and Inspection** (2022) | Persists cached RRT nodes, reevaluates expected gain of cached nodes, filters and keeps top candidates. | High for persistent candidate caches and selective reevaluation. | Cached nodes are actually reevaluated/thresholded; no matching deterministic admissible-bound certificate was identified in the reviewed material. |
| Vutetakis & Xiao, **Active Perception Network for Non-Myopic Online Exploration and Visual Surface Coverage** (APN, 2023/2024) | Differential Regulation tracks changed map regions; frontier/view visibility relations are cached and reconditioned incrementally; the method maintains both view-to-frontier and frontier-to-view visibility structures. | Very high for change-aware incremental visibility and inverse incidence-like data structures. | APN aims to maintain current frontier visibility/global planning knowledge. In the reviewed full method, no construction matching `|A_tau(v) ∩ U_t|` as a deliberately conservative admissible bound, nor a lazy certificate of equality to a specified exhaustive optimistic-NBV argmax, was identified. |
| Sun et al., **FrontierNet: Learning Visual Cues to Explore** (2025) | Predicts an initial frontier information gain and later reduces it by projecting currently known voxels into the candidate view, using `g'_i = g_i - |V_known^i|`; selects by adjusted gain divided by distance. | Extremely close to the intuitive idea "gain decreases as more cells become known." | Its initial gain is learned/predicted and the decrement is an adjustment heuristic. The reviewed method does not establish this adjusted value as an admissible bound on an exact raycast gain, and does not use it to certify identical selection to exhaustive exact NBV. Therefore **known-cell decrement alone is not a novelty claim for Candidate 1**. |
| Lin et al., **Fast Sampling-Based UAV Exploration of Unknown 3D Environments with Submodular Information Gain Measure** (Measurement Science and Technology, 2026) | Uses submodular gain accounting and branch pruning based on a branch gain upper bound relative to the global best to reduce sampling-tree expansion. | Important recent precedent for upper-bound pruning inside robotic exploration. | The reviewed material concerns branch/cumulative-gain pruning within a sampling-based trajectory tree. An equivalent persistent-candidate cross-cycle cached-cell bound with exact exhaustive pointwise-NBV target equivalence was not identified. It nevertheless weakens any broad claim such as "first upper-bound pruning method for exploration." |
| **PB-NBV** (2025) and other recent efficiency-focused NBV methods | Replace or approximate expensive raycasting using projection, learned prediction, or alternative representations. | Establish that computational NBV acceleration is highly active/crowded. | They do not make the exact refined claim identified above in the reviewed material. |

## What Is Already Prior Art

The following are **not sufficient standalone contributions**:

- caching previous information gains;
- observing that exploration information gain decreases over time under suitable assumptions;
- lazily reevaluating candidates;
- using stale values as generic upper bounds;
- pruning with upper bounds in a generic search/lazy-greedy sense;
- updating only map regions that changed;
- maintaining view-to-target or target-to-view visibility relations;
- decrementing a stored/predicted gain as voxels become known;
- avoiding or accelerating raycasts;
- making NBV computation faster in general.

Each of these has a close precedent in the reviewed literature.

## What Was Not Matched in the Reviewed Literature

The literature review did **not identify an exact match** for the following combined formulation:

1. At an exact evaluation of a persistent viewpoint `v`, cache the exact optimistic visible-unknown set `A_tau(v)(v)`.
2. Under monotone static occupancy revelation and UNKNOWN-transparent planning rays, maintain

   \[
   \overline G_t(v)=|A_{\tau(v)}(v)\cap U_t|
   \]

   as a formally admissible upper bound without claiming that it is the current exact gain.
3. Maintain that cached-intersection count decrementally from cell-state changes, e.g. through an inverse cell-to-candidate incidence structure.
4. Combine the bound with a valid current travel-cost treatment.
5. Use the bound only to skip exact evaluations, with a deterministic tie-aware stopping certificate proving that the returned current viewpoint is exactly the one an explicitly defined exhaustive optimistic-NBV evaluator would return.

This combination is narrower than the original Candidate 1 idea and is the only currently defensible novelty hypothesis.

## Detailed APN Comparison

APN is the closest match on data-structure philosophy. Its Differential Regulation procedure exploits the fact that sequential map changes occur in a localized region. It caches and incrementally reconditions perception-network state rather than rebuilding global perception information. Its frontier-guided visibility machinery represents which frontiers are visible from views and the inverse relation from frontiers to views.

That means Candidate 1 **cannot** claim that inverse visibility mappings, change awareness, memoization, or local visibility updates are new.

The distinction retained after full-method comparison is narrower:

> APN incrementally maintains current exploration/perception information to support sampling, pruning, refinement, and non-myopic planning; refined Candidate 1 would deliberately maintain a possibly loose but provably admissible stale-view upper bound and use it as a certificate to avoid exact evaluations while reproducing a fixed exhaustive optimistic-NBV decision rule exactly.

No equivalent exact-selection theorem or cached UNKNOWN-cell intersection bound was identified in the APN full method reviewed here.

## FrontierNet Comparison

FrontierNet materially narrows Candidate 1's claim. FrontierNet already recognizes that a frontier's initial gain should fall as the world becomes known and uses current known voxels to reduce that gain.

Therefore Candidate 1 must **not** be presented as the first method to update/decrement gain from newly known cells.

The current technical distinction is that Candidate 1's cached set is produced by an exact evaluation of the same baseline gain, so every removed cached contribution is tied to that exact earlier gain. The resulting value is proved to remain above the current exact optimistic gain under explicit assumptions. It is then used for safe pruning rather than treated as the current gain itself.

## 2026 Submodular Branch-Pruning Comparison

Lin et al. (2026) is important because it shows that robotic exploration already uses an explicit gain upper-bound concept to prune low-potential branches. The paper's figures/descriptions state that branches are retained according to whether their gain upper bound exceeds a threshold relative to the global best.

Therefore a broad contribution such as "upper-bound pruning for robotic exploration" is not supportable.

The remaining distinction is the **object being bounded and the guarantee being targeted**:

- Lin et al.: future/cumulative utility of trajectory-tree branches, using submodular gain accounting to accelerate tree expansion;
- refined Candidate 1: current exact pointwise NBV gain of persistent candidates across map-revelation cycles, using a cached visible-unknown set and a tie-aware certificate for the same deterministic exhaustive current target.

A future manuscript would need to state this difference precisely and avoid claiming priority for generic bound-based pruning.

## Novelty Gate Assessment

### Result: **PROVISIONAL PASS — HIGH RISK, NARROW CLAIM ONLY**

Reasoning:

- The original Candidate 1 framing does **not** pass: virtually every ingredient at a broad level has close prior art.
- Full-method review of APN did not reveal the same admissible cached-intersection bound or exhaustive-NBV equality certificate.
- FrontierNet is a strong warning that "subtract known voxels from gain" is already published and cannot be the contribution.
- Lin et al. (2026) is a strong warning that explicit exploration gain upper-bound pruning is already published and cannot be the contribution.
- The exact combined formulation above was not identified in the reviewed literature, so it remains reasonable to implement and empirically test as a narrowly defined research contribution.

This is **not** a proof of global novelty. The approved claim is only that no equivalent formulation was identified in the literature reviewed to date.

## Implementation Implication

Candidate 1 may proceed to a small deterministic implementation **only if** the contribution is framed as certified exact-selection acceleration rather than generic caching or gain decrement.

The first implementation must compare at least:

1. exhaustive optimistic NBV;
2. stale-scalar lazy bound `G_tau(v)`;
3. change-aware cached-set bound `|A_tau(v) ∩ U_t|`;
4. optionally an occlusion-tightened extension if the cached-set bound proves too loose.

Correctness must be tested before speed: the selected candidate and target sequence must match the exhaustive baseline exactly under the shared tie rule. Evaluation must also measure memory and bound-maintenance overhead, not only raycast count.

## Current Verdict

**Status: CONDITIONAL GO FOR MINIMAL IMPLEMENTATION.**

Theory gate: passed under explicit assumptions.

Novelty gate: provisionally passed only for the narrow combined formulation above, with high prior-art risk and no priority claim.

Empirical-value gate: open. Candidate 1 should be dropped or modified if the bound does not materially reduce exact gain evaluations after accounting for bound maintenance, distance computation, and memory.

## Primary Sources Reviewed

- Michel Minoux, *Accelerated Greedy Algorithms for Maximizing Submodular Set Functions* (1978).
- Daniel Golovin and Andreas Krause, *Adaptive Submodularity: Theory and Applications in Active Learning and Stochastic Optimization* (JAIR 2011), arXiv:1003.3967.
- Yash Satsangi, Shimon Whiteson, Frans A. Oliehoek, *PAC Greedy Maximization with Efficient Bounds on Information Gain for Sensor Selection* (IJCAI 2016), arXiv:1602.07860.
- Kok-Lim Low and Anselmo Lastra, *An Adaptive Hierarchical Next-Best-View Algorithm for 3D Reconstruction of Indoor Scenes* and *Efficient Constraint Evaluation Algorithms for Hierarchical Next-Best-View Planning* (2006).
- Magnus Selin et al., *Efficient Autonomous Exploration Planning of Large-Scale 3-D Environments* (IEEE RA-L 2019), DOI: 10.1109/LRA.2019.2897343.
- Rowan Border and Jonathan D. Gammell, *Proactive Estimation of Occlusions and Scene Coverage for Planning Next Best Views in an Unstructured Representation* / SEE++ (2020/2021), arXiv:2009.04515.
- Ana Batinović et al., *A Shadowcasting-Based Next-Best-View Planner for Autonomous 3D Exploration*, arXiv:2109.09323.
- Menaka Naazare, Francisco Garcia Rosas, Dirk Schulz, *Online Next-Best-View Planner for 3D-Exploration and Inspection With a Mobile Manipulator Robot*, arXiv:2203.10113.
- David Vutetakis and Jing Xiao, *Active Perception Network for Non-Myopic Online Exploration and Visual Surface Coverage*, arXiv:2309.11695 / later journal version.
- Boyang Sun et al., *FrontierNet: Learning Visual Cues to Explore*, arXiv:2501.04597 (2025).
- Yuwen Lin et al., *Fast Sampling-Based UAV Exploration of Unknown 3D Environments with Submodular Information Gain Measure*, Measurement Science and Technology 37(4), 046202 (2026), DOI: 10.1088/1361-6501/ae324d.
- *PB-NBV: Efficient Projection-Based Next-Best-View Planning Framework for Reconstruction of Unknown Objects*, arXiv:2501.10663.
