# Candidate 1 Formalization: Change-Aware Admissible Bounds for Exact NBV

Last updated: 2026-09-14

This document formalizes the refined Candidate 1 hypothesis. It establishes a theory gate under explicit assumptions; it does not establish novelty, practical speedup, or empirical value.

## 1. Formal Environment

Let \(\mathcal C\subset\mathbb Z^2\) be a finite 2D occupancy grid. Its dimensions, resolution, and geometry are symbolic parameters. The static ground-truth map is

\[
M:\mathcal C\to\{\mathsf F,\mathsf O\},
\]

where \(\mathsf F\) and \(\mathsf O\) denote FREE and OCCUPIED.

At completed planning snapshot \(t\), the belief map is

\[
B_t:\mathcal C\to\{\mathsf U,\mathsf F,\mathsf O\},
\]

where \(\mathsf U\) denotes UNKNOWN. Define

\[
U_t=\{c\in\mathcal C:B_t(c)=\mathsf U\},\quad
F_t=\{c:B_t(c)=\mathsf F\},\quad
O_t=\{c:B_t(c)=\mathsf O\}.
\]

The robot pose \(x_t\) is exact. There is no SLAM or localization error. Physical observations are deterministic and correct: when an observed cell leaves \(\mathsf U\), it is assigned \(M(c)\). Belief updates are monotone:

\[
U_{t+1}\subseteq U_t,
\]

and a cell labeled \(\mathsf F\) or \(\mathsf O\) never changes label. A planning snapshot may contain any finite batch of such updates.

Navigation uses only currently known FREE cells. Let \(\mathcal N_t\) be a graph induced by \(F_t\), with a fixed but not yet selected neighborhood and nonnegative edge-cost convention. A candidate is eligible only if its position is reachable from \(x_t\) in \(\mathcal N_t\). Map size, sensor range, ray discretization, movement connectivity, and candidate density remain symbolic.

## 2. Two Different Visibility Models

Fix a deterministic ray traversal convention, sensor footprint, range parameter \(R\), and field of view. A viewpoint \(v\) includes every variable that changes that footprint, including position and orientation when orientation matters.

### Physical sensor visibility

Physical visibility, \(\operatorname{PVis}(M,v)\), is evaluated against the ground-truth map. Along each ray, ground-truth FREE cells are traversed and the first ground-truth OCCUPIED cell blocks all cells behind it. Whether that first obstacle cell is returned as an observation is part of the fixed sensor convention; in the intended occupancy sensor it is observed and then stops the ray. This model determines actual deterministic observations.

### Planning-time optimistic visibility

Planning-time optimistic visibility, \(\operatorname{OVis}(B_t,v)\), is evaluated only against the current belief map using the same fixed geometric footprint and ray traversal:

- \(\mathsf F\): the ray passes;
- \(\mathsf U\): the cell contributes potential gain and the ray passes;
- \(\mathsf O\): the ray stops.

Thus only currently known OCCUPIED cells occlude planning rays. Physical visibility and optimistic planning visibility are different functions and must never be substituted for one another in the proof.

## 3. Exact Information Gain

For candidate \(v\), define its current visible-unknown set

\[
A_t(v)=U_t\cap\operatorname{OVis}(B_t,v).
\]

The exact planning-time information gain is the number of distinct cells in this set:

\[
G_t(v)=|A_t(v)|.
\]

This is an unweighted cardinality gain. It is not entropy, expected physical gain under an unknown ground truth, or the number of cells physically visible after visiting \(v\). Extensions to weights require separate assumptions; they are outside the core theorem.

## 4. Exhaustive NBV Baseline

Let \(V_t\) be the finite set of eligible candidates at snapshot \(t\). For \(v\in V_t\), let \(d_t(v)\) be the exact shortest-path travel cost from the exact current pose \(x_t\) to \(v\) through \(\mathcal N_t\). For a fixed symbolic constant \(\epsilon>0\), define

\[
S_t(v)=\frac{G_t(v)}{d_t(v)+\epsilon}.
\]

Let \(\prec_t\) be a deterministic total order on \(V_t\), where \(v\prec_t w\) means that \(v\) is preferred to \(w\) on an exact score tie. The exhaustive baseline is

\[
v_t^{\mathrm{exh}}
=\underset{v\in V_t}{\operatorname{argmax}}{}^{\prec_t} S_t(v),
\]

meaning maximum score followed by the fixed tie-breaking order. Exact equivalence is undefined unless this order is specified and shared by both selectors.

## 5. Cached Visible-Unknown Set

For a persistent candidate \(v\), let \(\tau(v)\le t\) be the most recent snapshot at which \(G_{\tau(v)}(v)\) was evaluated exactly. Cache the full set

\[
A_{\tau(v)}(v)
=U_{\tau(v)}\cap\operatorname{OVis}(B_{\tau(v)},v).
\]

The current UNKNOWN set is \(U_t\). The proposed gain upper bound is

\[
\overline G_t(v)
=\left|A_{\tau(v)}(v)\cap U_t\right|.
\]

This bound removes cached gain contributions that have since become known without claiming to maintain current visibility exactly.

## 6. Admissibility Lemma

### Assumptions

For every time interval \([\tau(v),t]\) to which the lemma is applied:

1. **Finite fixed domain:** \(\mathcal C\) and its ray-to-cell discretization do not change.
2. **Static correct world:** \(M\) is static and every deterministic observation is correct.
3. **Monotone belief:** cells may change only \(\mathsf U\to\mathsf F\) or \(\mathsf U\to\mathsf O\); known labels never revert or switch.
4. **Persistent viewpoint identity:** \(v\)'s position, orientation, footprint, FOV, range, and ray convention are unchanged.
5. **Optimistic transparency:** both \(\mathsf U\) and \(\mathsf F\) transmit planning rays; only \(\mathsf O\) blocks them.
6. **Fixed gain definition:** gain is \(|U_t\cap\operatorname{OVis}(B_t,v)|\) at every snapshot.
7. **Exact cache:** \(A_{\tau(v)}(v)\) was computed from the snapshot at \(\tau(v)\), not approximated.
8. **Snapshot consistency:** the belief, candidate identity, visibility parameters, and current distances do not mutate during one selection/certification operation.

### Lemma

For every persistent candidate satisfying the assumptions,

\[
G_t(v)\le \overline G_t(v).
\]

### Proof

It suffices to prove set inclusion

\[
A_t(v)\subseteq A_{\tau(v)}(v)\cap U_t.
\]

Take any \(c\in A_t(v)\). By definition, \(c\in U_t\). Monotone belief implies \(U_t\subseteq U_{\tau(v)}\), so \(c\) was also UNKNOWN at \(\tau(v)\).

Because \(c\in\operatorname{OVis}(B_t,v)\), at least one fixed ray from \(v\) to \(c\) contains no blocking cell from \(O_t\) before \(c\). Monotone correct updates imply \(O_{\tau(v)}\subseteq O_t\). Therefore the same fixed ray contained no blocker from \(O_{\tau(v)}\) either. With UNKNOWN and FREE both transparent, the ray was also planning-visible at \(\tau(v)\). Hence \(c\in A_{\tau(v)}(v)\). Together with \(c\in U_t\), this proves the inclusion. Taking cardinalities yields the lemma. \(\square\)

### Ray-level case analysis

- **UNKNOWN \(\to\) FREE:** The updated cell leaves \(U_t\), so its own cached contribution disappears. It was ray-transparent before and remains transparent, so the transition cannot reveal a cell that was not already optimistically visible.
- **UNKNOWN \(\to\) OCCUPIED:** The cell leaves \(U_t\) and becomes a new blocker. It removes its own contribution and may remove visibility of still-UNKNOWN cells behind it; it cannot create a new visible-unknown cell.
- **Several cells updated at once:** Order the finite batch arbitrarily. Each individual allowed transition preserves the inclusion, so their composition preserves it.
- **A previously FREE cell:** It remains FREE by monotonicity and is transparent at both snapshots; it neither creates a new blocker nor becomes a new gain cell.
- **A previously OCCUPIED cell:** It remains OCCUPIED and blocks the same ray segment at both snapshots. Any cell blocked by it at \(\tau(v)\) remains blocked.
- **A newly discovered occluder:** This is the UNKNOWN \(\to\) OCCUPIED case. It can only shrink current optimistic visibility.
- **UNKNOWN behind a newly discovered occluder:** Such a cell can remain in \(A_{\tau(v)}(v)\cap U_t\) but leave \(A_t(v)\). This creates slack in the upper bound and never violates admissibility.

The transparency equivalence of UNKNOWN and FREE for ray propagation is essential: without it, UNKNOWN \(\to\) FREE could reveal new cells.

## 7. Counterexample Search

The lemma fails if any assumption that permits new planning-visible unknown cells is removed. The following are minimal or near-minimal grid constructions; all unspecified cells are fixed known FREE, and range/FOV are sufficient unless stated otherwise.

### Candidate position is not identical

Use a 1×4 corridor. At \(\tau\), candidate ID \(v\) is at cell 1 and its only visible UNKNOWN cell 2 is cached. Cell 2 later becomes known. If the same ID is silently moved to known-FREE cell 3, from which UNKNOWN cell 4 is visible, then \(\overline G_t(v)=0\) but \(G_t(v)=1\). Position is therefore part of candidate identity.

### Orientation changes or FOV depends on orientation

Use a 1×3 corridor with the candidate at the center and a one-sided FOV. At \(\tau\), it faces east and caches the east UNKNOWN cell. That cell becomes known. If the same ID turns west, the west cell is still UNKNOWN and visible, giving \(\overline G_t(v)=0<G_t(v)=1\). Orientation must be part of identity whenever it changes FOV.

### Probabilistic belief reversion

Use a 1×2 grid. At \(\tau\), the adjacent visible cell is labeled FREE, so the cache is empty. If a later probabilistic update changes it back to UNKNOWN, then \(G_t(v)=1\) while \(\overline G_t(v)=0\). The core lemma does not cover reversible or probabilistic occupancy states.

### Dynamic obstacle

Use a 1×3 ray: candidate, known OCCUPIED cell, UNKNOWN cell. Initially the obstacle blocks the UNKNOWN cell and the cache is empty. If the obstacle disappears and the belief changes OCCUPIED \(\to\) FREE, the rear UNKNOWN cell becomes visible, again giving \(0<1\). Static truth and non-reverting known occupancy are required.

### UNKNOWN treated as opaque

Use the minimal 1×3 ray: candidate, UNKNOWN cell \(a\), UNKNOWN cell \(b\). Under opaque-UNKNOWN planning, \(A_\tau(v)=\{a\}\). After \(a\) becomes FREE, \(b\) becomes visible while \(a\notin U_t\), so

\[
\overline G_t(v)=|\{a\}\cap\{b\}|=0<1=G_t(v).
\]

This is a direct counterexample to the lemma under opaque UNKNOWN handling.

### Visibility definition changes between cycles

If a cell is excluded at \(\tau\) by one ray discretization, frontier filter, weighting support, or footprint rule and included at \(t\) by another while remaining UNKNOWN, it need not belong to the cached set. A one-cell gain increase from zero already violates the bound. The visibility and gain definitions must remain fixed.

### Sensing model or range changes

Use a straight ray with an UNKNOWN cell at distance two. Let the range be one at \(\tau\), so the cache is empty, and two at \(t\), so the cell contributes gain one. Thus \(\overline G_t(v)=0<G_t(v)=1\). Range, FOV, and ray conventions must be fixed for a persistent identity; otherwise the changed configuration is a new candidate.

### Result of the search

No counterexample was found inside the assumptions of Section 6. Several small counterexamples exist outside them. The assumptions have therefore been strengthened to make candidate pose/configuration immutable, require unknown-transparent planning visibility, prohibit belief reversion and dynamic truth, fix the grid and sensing geometry, and require atomic planning snapshots.

## 8. Bound Tightness

Because \(A_{\tau(v)}(v)\cap U_t\subseteq A_{\tau(v)}(v)\),

\[
\overline G_t(v)
=|A_{\tau(v)}(v)\cap U_t|
\le |A_{\tau(v)}(v)|
=G_{\tau(v)}(v).
\]

Equality holds exactly when every cell in the cached set remains UNKNOWN:

\[
A_{\tau(v)}(v)\subseteq U_t.
\]

The inequality is strict exactly when at least one cached visible-unknown cell has become known by time \(t\).

Admissibility itself can also be strict. Specifically,

\[
G_t(v)<\overline G_t(v)
\]

whenever at least one cell remains in \(A_{\tau(v)}(v)\cap U_t\) but is no longer optimistically visible. A newly discovered OCCUPIED cell on its ray is the canonical cause: cells behind that occluder remain UNKNOWN and counted by the cached intersection, although current exact ray casting excludes them. Conversely, \(G_t(v)=\overline G_t(v)\) exactly when every still-UNKNOWN cached cell remains planning-visible at \(t\).

## 9. Inverse Incidence Index

For current cache generations, define

\[
I(c)=\{v:c\in A_{\tau(v)}(v)\}.
\]

Maintain:

- candidate \(\to\) cached visible-unknown set and cache generation;
- cell \(\to\) candidate IDs/cache generations;
- candidate \(\to\) current upper-bound count \(q_t(v)\).

When candidate \(v\) is exactly evaluated, remove or invalidate its old inverse memberships, store \(A_t(v)\), add the new memberships, set \(\tau(v)=t\), and set \(q_t(v)=|A_t(v)|\). When a cell \(c\) changes once from UNKNOWN to either known state, decrement \(q(v)\) once for every current membership \(v\in I(c)\).

### Invariant and proof

The maintained invariant is

\[
q_t(v)=|A_{\tau(v)}(v)\cap U_t|=\overline G_t(v).
\]

It holds immediately after exact evaluation. For one UNKNOWN \(\to\) known transition of \(c\), the right-hand side decreases by one exactly for cached sets containing \(c\), which are exactly the current members of \(I(c)\); all other cached intersections are unchanged. Updating every member once preserves the invariant. Induction covers any batch or sequence of monotone updates. Therefore the index maintains the same admissible bound proved in Section 6.

The index deliberately does not decrement unknown cells newly occluded behind an OCCUPIED update. Omitting those decrements can only leave extra slack. Stale cache generations and duplicate decrements would break the equality invariant, so generation validation or eager removal is required in any future implementation.

## 10. Current Distance

Gain and travel distance obey different update rules. At each snapshot, use the current exact reachable-path cost \(d_t(v)\) and define

\[
\overline S_t(v)
=\frac{\overline G_t(v)}{d_t(v)+\epsilon}.
\]

Since \(d_t(v)+\epsilon>0\) and \(G_t(v)\le\overline G_t(v)\), division by the same positive exact denominator gives

\[
S_t(v)\le\overline S_t(v).
\]

Thus \(\overline S_t(v)\) is a valid score upper bound provided \(d_t(v)\) is the baseline's exact current distance for the same candidate and snapshot. A stale distance is not justified by the gain lemma. Unreachable candidates are excluded from \(V_t\), rather than assigned an ambiguous finite score.

### Future extension: distance lower bounds

If exact distance computation for every candidate is itself too costly, a proven lower bound \(\underline d_t(v)\le d_t(v)\) would yield

\[
S_t(v)
\le\frac{\overline G_t(v)}{d_t(v)+\epsilon}
\le\frac{\overline G_t(v)}{\underline d_t(v)+\epsilon}.
\]

This may support joint gain-and-distance pruning, but it is not part of the core theorem and must not be implemented without a separate proof for the selected navigation metric.

## 11. Exact Selection Certificate

The simple condition \(S_t(v^*)\ge\max_{v\ne v^*}\overline S_t(v)\) is insufficient by itself when equality is possible: another candidate may attain the same exact score and be preferred by the exhaustive tie rule.

### Theorem

Fix a snapshot \(t\), eligible set \(V_t\), and total tie order \(\prec_t\). Suppose every unevaluated candidate \(w\) has a valid upper bound \(\overline S_t(w)\), and candidate \(v^*\) has been exactly evaluated on that snapshot. If, for every \(w\ne v^*\), either

\[
S_t(v^*)>\overline S_t(w),
\]

or

\[
S_t(v^*)=\overline S_t(w)\quad\text{and}\quad v^*\prec_t w,
\]

then \(v^*=v_t^{\mathrm{exh}}\).

### Proof

For any \(w\ne v^*\), admissibility gives \(S_t(w)\le\overline S_t(w)\). In the first case, \(S_t(v^*)>S_t(w)\). In the second case, either \(S_t(w)<S_t(v^*)\), or \(S_t(w)=S_t(v^*)\) and \(v^*\) is preferred by \(\prec_t\). Therefore no candidate can beat \(v^*\) under the exhaustive score-plus-tie comparison, so the deterministic exhaustive baseline returns \(v^*\). \(\square\)

Operationally, priority evaluation may examine candidates in descending score-upper-bound order, with potential ties ordered consistently with \(\prec_t\), and stop only when the theorem's pairwise condition is satisfied. Priority evaluation and this style of exact-greedy certificate are prior art; the Candidate 1-specific object is the maintained occupancy-change bound.

## 12. Candidate Lifecycle

The theorem applies to the current eligible set \(V_t\), not to an eternal fixed candidate population.

- **Persistent identity:** A candidate ID represents an immutable full viewpoint: grid position, orientation when relevant, and the fixed sensing footprint/range/ray convention. Changing any of these creates a new identity.
- **Newly created candidate:** Either evaluate it exactly immediately, or initialize it with the proven geometric bound

  \[
  H_t(v)=|U_t\cap\mathcal F(v)|,
  \]

  where \(\mathcal F(v)\) is the fixed in-range/FOV cell footprint with all occlusion ignored. Since \(A_t(v)\subseteq U_t\cap\mathcal F(v)\), \(G_t(v)\le H_t(v)\). The still looser \(|U_t|\) is also admissible on the finite domain. No smaller unproved initialization may be used. If \(H_t\) is maintained across updates, its footprint incidence must be indexed just like a cache until the first exact evaluation.
- **Deleted candidate:** Remove it from \(V_t\) and delete or invalidate its inverse-index memberships. It is irrelevant to the current certificate.
- **Unreachable candidate:** Exclude it from \(V_t\). Do not let a finite placeholder distance participate in the theorem.
- **Candidate becomes reachable:** If the same immutable identity was cached and all UNKNOWN-to-known decrements were maintained while inactive, its valid cache may be reused; otherwise treat it as newly created.
- **Previously visited candidate:** Visiting does not by itself prove zero gain. Retain or delete it only by a deterministic candidate-generation policy; if retained, the ordinary bound rules apply.
- **Candidate set changes:** Build the certificate against exactly the current \(V_t\). New candidates must receive an admissible bound before certification; removed candidates must not remain in the maximum.
- **Map update while planning:** Selection requires an atomic snapshot. If observation changes \(B_t\) during evaluation, either restart on a new snapshot or process every change, invalidate affected exact scores/distances as necessary, and recertify. Mixing snapshot values is not covered.
- **Agent movement between cycles:** A fixed viewpoint's gain cache remains admissible if belief updates are processed, but movement changes the current source pose and potentially the known-FREE navigation graph. Recompute \(d_t(v)\) for the new snapshot. Sensing during movement is simply a batch of monotone belief changes that must be incorporated before certification.

## 13. Relation to Lazy Greedy

The following components are not new:

- stale values used as upper bounds;
- priority-first reevaluation of the largest bound;
- stopping with an exact-greedy certificate once one exact value dominates remaining upper bounds.

These are the Minoux-style lazy-greedy skeleton, with adaptive variants also established in prior work. Candidate 1 must not claim them as its contribution.

The limited research possibility is the combination of:

- an admissible bound derived specifically from evolving occupancy belief and optimistic visibility;
- changed-cell-driven decremental maintenance through cached cell/viewpoint incidence;
- explicit treatment of NBV ray occlusion, where new known obstacles create safe bound slack;
- recombination of the gain bound with current, separately updated travel cost;
- a stated equivalence theorem against a deterministic exhaustive-NBV baseline while map knowledge and candidate eligibility evolve between atomic snapshots.

Whether this combination is novel remains unresolved and requires deeper comparison, especially against full incremental-view maintenance methods.

## 14. Relation to Robotics Prior Art

The table is limited to claims supported by `docs/CANDIDATE_1_PRIOR_ART.md`. “Not identified in reviewed material” means the focused review did not establish the property; it is not a claim that the full paper lacks it.

| Paper | What it caches/updates | Whether exact gain is retained | Whether it has an admissible upper bound | Whether it guarantees same argmax as exhaustive NBV | Difference from refined Candidate 1 | Novelty risk |
|---|---|---|---|---|---|---|
| Selin et al., AEP | Previously estimated gains, cached points, sparse gain estimates, and GP interpolation | Exact retention for every current candidate was not identified in reviewed material | Candidate-1-style admissible bound not identified in reviewed material | Exact exhaustive-NBV equivalence not identified in reviewed material | Refined Candidate 1 would cache a visible-unknown cell set, maintain a proved upper bound from state changes, and certify deterministic exhaustive equivalence | **High** for cross-cycle gain caching and reuse; unresolved for the refined certificate |
| Batinović et al., Shadowcasting NBV | Replaces dense raycasting with recursive shadowcasting/cuboid gain evaluation; caching is not the stated core mechanism | Equivalence of its method-specific gain to the defined exhaustive ray evaluator was not identified in reviewed material | Candidate-1-style admissible pruning bound not identified in reviewed material | Exact exhaustive-NBV equivalence not identified in reviewed material | Refined Candidate 1 skips some exact evaluations using bounds; Shadowcasting accelerates the gain computation itself | **Medium** for the broad efficiency claim; lower but unresolved for bound maintenance |
| Naazare et al., cached NBV | Persistent cached candidate nodes, high-gain reevaluation, and cache filtering | Retention of exact current gain for all cached candidates was not identified in reviewed material | A proved admissible upper bound was not identified in reviewed material | Exact exhaustive-NBV equivalence not identified in reviewed material | Refined Candidate 1 would attach a set-based admissibility invariant and deterministic selection theorem to selective reevaluation | **High** for caching/selective reevaluation; unresolved for the proof-backed mechanism |
| Vutetakis & Xiao, APN | Difference-aware map updates, memoized visibility/view-frontier information, and local reconditioning | Exact equivalence to a defined exhaustive NBV gain was not identified in reviewed material | A Candidate-1-style admissible upper-bound certificate was not identified in reviewed material | Exact exhaustive-NBV equivalence not identified in reviewed material | APN incrementally maintains planning information; refined Candidate 1 would maintain a possibly loose bound specifically to avoid exact evaluations while certifying the same deterministic NBV | **Very high**; full-method comparison is required before any novelty claim |

The focused review therefore supports only a scoped statement: the exact same formulation was not identified in the reviewed material. It does not justify “first,” “novel,” or “no prior method” claims.

## 15. Final Theory Gate

### PASS

Under the assumptions stated in Section 6, the proposed bound

\[
\overline G_t(v)=|A_{\tau(v)}(v)\cap U_t|
\]

is admissible, the inverse-incidence decrement preserves it, and combination with exact current distance yields a valid score upper bound. With the strengthened tie-aware condition in Section 11, the selector is certified to return the same candidate as deterministic exhaustive NBV on an atomic snapshot.

The PASS is conditional and narrowly theoretical. The formulation fails under small counterexamples if candidate pose/configuration changes under one identity, UNKNOWN is opaque, belief labels revert, obstacles are dynamic, visibility/range changes, or planning mixes snapshots. The gate does not establish novelty, useful bound tightness, lower runtime, or readiness to implement. APN and other incremental visibility methods remain a serious novelty risk, and simulator specification plus broader prior-art validation must precede code.
