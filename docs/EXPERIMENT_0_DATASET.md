# Experiment 0 Random Correctness Dataset

Frozen: 2026-09-15

## Status and Scope

This document freezes the random-map portion of Experiment 0 before Algorithms B or C exist. It defines a correctness dataset only. It does not report an equivalence experiment, performance benchmark, runtime comparison, or research outcome.

The canonical machine-readable artifact is `configs/experiment_0_random_maps.json`. Every accepted map is regenerated from its recorded seed and verified against its recorded SHA-256 hash. Frozen seeds must not be changed in response to later algorithm results.

## Dataset Size and Balance

- Sizes: `12x12`, `16x16`, and `20x20`.
- Accepted maps per size: 20.
- Total accepted maps: 60.
- Density categories: `sparse` (`p=0.10`), `medium` (`p=0.20`), and `dense` (`p=0.30`).
- Accepted density target within each size: 7 sparse, 7 medium, and 6 dense. This is the most even integer allocation of 20 maps under the fixed ordering used here.
- Total accepted density counts: 21 sparse, 21 medium, and 18 dense.

Dataset indices are zero-based. Stable IDs are `random-000` through `random-059`.

## Generator and Seed Derivation

- Dataset version: `experiment-0-random-v1`.
- Generator version: `independent-bernoulli-occupancy-v1`.
- Master seed: `20260915`.
- The master generator is exactly `random.Random(20260915)`.
- One candidate seed is drawn for every candidate attempt using `master_rng.getrandbits(63)`.
- A fresh local `random.Random(candidate_seed)` generates each map. Global random state is never read or changed.
- Cells are visited in row-major order. A cell is OCCUPIED exactly when `local_rng.random() < p`; otherwise it is FREE.
- Sizes are processed in order `12`, `16`, `20`. Within a size, still-unfilled categories are attempted in order sparse, medium, dense until their accepted quotas are met.
- Every attempt receives a monotonically increasing `candidate_index`, including rejected attempts. Rejected attempts never reuse a seed.

## FREE Connectivity and Deterministic Start

FREE connected components use the same traversability convention as the frozen simulator: 8-neighbor adjacency, with a diagonal edge allowed only when both orthogonally adjacent side cells are FREE. This avoids selecting a component that the robot could not traverse under the experiment motion model.

For each generated map:

1. Select the largest FREE component.
2. If component sizes tie, select the component whose lexicographically smallest cell is lexicographically smallest.
3. Let the geometric grid center be `((height-1)/2, (width-1)/2)`.
4. Within the selected component, choose the cell with minimum squared Euclidean distance to that center.
5. Break an equal-distance tie by lexicographically smaller `(row, col)`.

## Acceptance and Rejection

A candidate is accepted only if all of the following hold:

- at least one FREE cell exists and a deterministic start can be selected;
- at least one OCCUPIED cell exists;
- the chosen largest FREE component contains at least 35% of all FREE cells;
- after the existing physical initial scan at range `R=8`, the existing exhaustive optimistic-NBV oracle does not immediately return `EXPLORATION_COMPLETE`;
- initial construction, scan, and planning complete without an exception.

Stable rejection reasons are:

- `no_free_cell`;
- `no_start_cell`;
- `no_occupied_cell`;
- `largest_component_fraction_below_0.35`;
- `initial_scan_exploration_complete`;
- `initial_scan_exception:<ExceptionClass>`.

The frozen materialization produced zero rejected candidates. The canonical config therefore retains an empty `rejected_candidates` list, a rejected count of zero, and an empty rejection summary. This is a property of the preregistered seed stream, not permission to discard future failures.

For every accepted attempt, the config permanently records dataset index, candidate index, dataset ID, size, density label, `p`, seed, accepted status, null rejection reason, start, selected FREE-component size, cycle limit, and map hash. For every rejected attempt it records candidate index, size, density label, `p`, seed, rejected status, reason, start when available, and map hash.

## Cycle Limits

For random maps,

\[
L=\max(64, 2N_{\mathrm{free\_component}}),
\]

where `N_free_component` is the selected largest FREE-component size. Reaching the limit without the required explicit stop is a failure, not an implicit completion. The seven fixed fixtures retain their existing fixture-specific limits.

## Canonical Ground-Truth Hash

- Serialize rows from top to bottom and cells from left to right.
- Encode FREE as `.` and OCCUPIED as `#`.
- Append exactly one LF (`\n`) after every row, including the final row.
- Encode the resulting text as UTF-8 and compute SHA-256.

Changing generator logic, map content, dimensions, row order, symbols, encoding, or newline convention changes the hash and invalidates the frozen artifact unless a new dataset version is declared.

## Frozen Accepted Seed List

The full start, component-size, cycle-limit, and hash record is in the canonical JSON artifact.

| Dataset ID | Size | Density | p | Seed |
|---|---:|---|---:|---:|
| random-000 | 12 | sparse | 0.10 | 5330464865640108879 |
| random-001 | 12 | medium | 0.20 | 955472025546279012 |
| random-002 | 12 | dense | 0.30 | 1903186950733795108 |
| random-003 | 12 | sparse | 0.10 | 8085182145960130748 |
| random-004 | 12 | medium | 0.20 | 6637139884518318721 |
| random-005 | 12 | dense | 0.30 | 7846884780050957208 |
| random-006 | 12 | sparse | 0.10 | 7158271266397058817 |
| random-007 | 12 | medium | 0.20 | 1206365467561632495 |
| random-008 | 12 | dense | 0.30 | 4132815764534142760 |
| random-009 | 12 | sparse | 0.10 | 8802829629943226820 |
| random-010 | 12 | medium | 0.20 | 369154256546639294 |
| random-011 | 12 | dense | 0.30 | 1051975539896974326 |
| random-012 | 12 | sparse | 0.10 | 1800328902482533194 |
| random-013 | 12 | medium | 0.20 | 5988504920873199647 |
| random-014 | 12 | dense | 0.30 | 2572890099909938680 |
| random-015 | 12 | sparse | 0.10 | 4571056704688308073 |
| random-016 | 12 | medium | 0.20 | 6014036470810819738 |
| random-017 | 12 | dense | 0.30 | 1520134412578172377 |
| random-018 | 12 | sparse | 0.10 | 1100028404642902184 |
| random-019 | 12 | medium | 0.20 | 2800958006169347911 |
| random-020 | 16 | sparse | 0.10 | 1880414660931474401 |
| random-021 | 16 | medium | 0.20 | 5134457112488694088 |
| random-022 | 16 | dense | 0.30 | 1230802023119051294 |
| random-023 | 16 | sparse | 0.10 | 1011295616428472583 |
| random-024 | 16 | medium | 0.20 | 7454983040647381124 |
| random-025 | 16 | dense | 0.30 | 4301554879512216079 |
| random-026 | 16 | sparse | 0.10 | 2784396512309990412 |
| random-027 | 16 | medium | 0.20 | 1482061114159451424 |
| random-028 | 16 | dense | 0.30 | 7430184768040742675 |
| random-029 | 16 | sparse | 0.10 | 1136508859744666050 |
| random-030 | 16 | medium | 0.20 | 8412438158528573997 |
| random-031 | 16 | dense | 0.30 | 3075508591194015516 |
| random-032 | 16 | sparse | 0.10 | 6785699117671774509 |
| random-033 | 16 | medium | 0.20 | 5642286221174944837 |
| random-034 | 16 | dense | 0.30 | 610347355546169441 |
| random-035 | 16 | sparse | 0.10 | 4959491098902389966 |
| random-036 | 16 | medium | 0.20 | 5297625360906615739 |
| random-037 | 16 | dense | 0.30 | 1539704733943483973 |
| random-038 | 16 | sparse | 0.10 | 4710615621458320133 |
| random-039 | 16 | medium | 0.20 | 2800192199628028969 |
| random-040 | 20 | sparse | 0.10 | 3401625048423572859 |
| random-041 | 20 | medium | 0.20 | 3752429512835464017 |
| random-042 | 20 | dense | 0.30 | 7897086557936856052 |
| random-043 | 20 | sparse | 0.10 | 6789104085363263613 |
| random-044 | 20 | medium | 0.20 | 7037570802641513515 |
| random-045 | 20 | dense | 0.30 | 2779123786463267563 |
| random-046 | 20 | sparse | 0.10 | 3647060634515756289 |
| random-047 | 20 | medium | 0.20 | 524680294426764532 |
| random-048 | 20 | dense | 0.30 | 5107640096050154906 |
| random-049 | 20 | sparse | 0.10 | 7210308160815558773 |
| random-050 | 20 | medium | 0.20 | 928323131437836541 |
| random-051 | 20 | dense | 0.30 | 6271593426382089067 |
| random-052 | 20 | sparse | 0.10 | 7390184556386850754 |
| random-053 | 20 | medium | 0.20 | 7079186175911782948 |
| random-054 | 20 | dense | 0.30 | 492367480353796936 |
| random-055 | 20 | sparse | 0.10 | 8642220197476521168 |
| random-056 | 20 | medium | 0.20 | 8872522031597770444 |
| random-057 | 20 | dense | 0.30 | 2111518878601351473 |
| random-058 | 20 | sparse | 0.10 | 5711399435219062689 |
| random-059 | 20 | medium | 0.20 | 8000994055318961516 |

## Reproduction and Verification

Materialize the canonical artifact with:

```text
python -m src.evaluation.random_dataset --output configs/experiment_0_random_maps.json
```

The test suite checks deterministic regeneration, exact accepted counts and balance, start selection, acceptance rules, cycle limits, config schema, all frozen hashes, hash content sensitivity, and absence of any Candidate 1 lazy-method dependency.
