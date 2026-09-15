# Experiment 0 Logging and Failure Artifacts

Frozen: 2026-09-15

## Scope

This document freezes the per-cycle correctness record and failure-artifact layout before Algorithms B and C are implemented. Fields for B and C are placeholders only. They must remain `null` or absent according to the eventual serializer until those algorithms produce real values; no B/C values are inferred or fabricated here.

Experiment 0 is not a performance benchmark. This schema contains correctness and diagnostic state, not timing or speedup claims.

## Canonical Belief Hash

- Serialize rows from top to bottom and cells from left to right.
- Encode UNKNOWN as `?`, FREE as `.`, and OCCUPIED as `#`.
- Append exactly one LF (`\n`) after every row, including the final row.
- Encode as UTF-8 and compute SHA-256.

Ground truth uses the same row order, encoding, final-LF rule, and SHA-256 algorithm, with `.` for FREE and `#` for OCCUPIED. The shared implementations are `canonical_ground_truth_text`, `ground_truth_hash`, `canonical_belief_text`, and `belief_hash` in `src/utils/hashing.py`.

## Per-Cycle Record Schema

One logical record is written for every planning snapshot, including the terminal stop snapshot.

### Identification

| Field | Type | Meaning |
|---|---|---|
| `experiment_version` | string | Frozen Experiment 0 runner/config version. |
| `dataset_type` | enum | `fixture` or `random`. |
| `map_id` | string | Fixture name or frozen random dataset ID. |
| `map_seed` | integer or null | Frozen candidate seed for random maps; `null` for fixtures. |
| `map_hash` | SHA-256 hex string | Canonical ground-truth hash. |
| `cycle_index` | nonnegative integer | Zero-based planning snapshot index, including terminal stop. |

### Shared Snapshot State

| Field | Type | Meaning |
|---|---|---|
| `robot_coordinate` | `[row, col]` | Exact robot coordinate at the frozen snapshot. |
| `belief_hash` | SHA-256 hex string | Canonical belief hash before selection. |
| `unknown_count` | nonnegative integer | UNKNOWN cells in the shared belief. |
| `known_free_count` | nonnegative integer | known FREE cells. |
| `known_occupied_count` | nonnegative integer | known OCCUPIED cells. |
| `eligible_candidate_count` | nonnegative integer | Candidates shared by A, B, and C. |

The three belief-state counts must sum to the map cell count. Every algorithm consumes this same snapshot, candidate set, current distances, score definition, and tie order.

### Algorithm A — Exhaustive Oracle

| Field | Type |
|---|---|
| `a_status` | `SELECTED` or `EXPLORATION_COMPLETE` |
| `a_selected_candidate` | `[row, col]` or null |
| `a_selected_gain` | nonnegative integer |
| `a_selected_distance` | number or null |
| `a_selected_score` | number |
| `a_exact_gain_evaluation_count` | nonnegative integer |

### Algorithm B — Stale-Scalar Placeholder

| Field | Type |
|---|---|
| `b_status` | enum or null |
| `b_selected_candidate` | `[row, col]` or null |
| `b_selected_gain` | nonnegative integer or null |
| `b_selected_distance` | number or null |
| `b_selected_score` | number or null |
| `b_exact_gain_evaluation_count` | nonnegative integer or null |
| `b_bound_only_candidate_count` | nonnegative integer or null |
| `b_certificate_reason` | string or null |

### Algorithm C — Change-Aware Placeholder

| Field | Type |
|---|---|
| `c_status` | enum or null |
| `c_selected_candidate` | `[row, col]` or null |
| `c_selected_gain` | nonnegative integer or null |
| `c_selected_distance` | number or null |
| `c_selected_score` | number or null |
| `c_exact_gain_evaluation_count` | nonnegative integer or null |
| `c_bound_only_candidate_count` | nonnegative integer or null |
| `c_bound_decrement_count` | nonnegative integer or null |
| `c_cached_membership_count` | nonnegative integer or null |
| `c_inverse_membership_count` | nonnegative integer or null |
| `c_certificate_reason` | string or null |

These C fields reserve diagnostics required by the preregistered invariants; they do not authorize implementation of cached sets, an inverse index, a priority queue, or a certificate in this phase.

### Agreement and Invariant Flags

| Field | Type | Meaning |
|---|---|---|
| `agreement_a_b` | boolean or null | Exact A/B status-and-target agreement. |
| `agreement_a_c` | boolean or null | Exact A/C status-and-target agreement. |
| `agreement_b_c` | boolean or null | Exact B/C status-and-target agreement. |
| `agreement_all` | boolean or null | All implemented methods agree. |
| `sequence_prefix_agreement_all` | boolean or null | Complete target/stop prefix agrees through this cycle. |
| `bound_valid_b` | boolean or null | All checked B bounds are admissible. |
| `bound_valid_c` | boolean or null | All checked C bounds are admissible. |
| `tie_certificate_valid_b` | boolean or null | B certificate respects the frozen total tie order. |
| `tie_certificate_valid_c` | boolean or null | C certificate respects the frozen total tie order. |
| `cache_index_invariant_valid_c` | boolean or null | C cache/index invariants hold. |

Until B or C exists, its fields and dependent agreement/invariant flags have no observed value and must not be presented as results.

## Failure Artifact Convention

Every detected mismatch, invalid bound, invalid tie certificate, invariant failure, different termination, exception, safety-limit exhaustion, or malformed record creates a new immutable directory:

```text
results/experiment_0/failures/<run_id>/
├─ metadata.json
├─ ground_truth.txt
├─ belief_before.txt
├─ candidates.json
├─ algorithm_state.json
└─ failure.txt
```

`run_id` must be unique and deterministic or collision-resistant for the run invocation. A writer must fail if the target directory already exists. Failure artifacts are never overwritten, deleted, or silently replaced.

### `metadata.json`

Contains the full identification fields, start, sensor/ray/motion/score/tie configuration, cycle limit, algorithm and repository revisions, invocation identifier, and failure classification. It also records whether the failure occurred on a fixture or frozen random map and references the map seed/hash where applicable.

### `ground_truth.txt`

Contains the exact canonical ground-truth ASCII serialization used for `map_hash`, including the final LF.

### `belief_before.txt`

Contains the exact canonical belief ASCII serialization at the shared planning snapshot before the failed selection, including the final LF.

### `candidates.json`

Contains every eligible candidate in deterministic coordinate order. Each record reserves:

- candidate ID/coordinate;
- exact current distance;
- Algorithm A exact visible-UNKNOWN set or its reproducible representation, exact gain, and score;
- Algorithm B stale scalar bound, exact-evaluated flag, exact gain/score when evaluated, and tie-order information;
- Algorithm C current bound, exact-evaluated flag, exact gain/score when evaluated, and tie-order information;
- the final deterministic rank/tie comparison needed to explain the selected or competing candidates.

Unimplemented B/C fields remain null; they are not reconstructed after a failure.

### `algorithm_state.json`

Reserves method-specific state needed for later reproduction, including cache generations, cached visible-UNKNOWN memberships, inverse memberships, decrement counters, priority/certificate state, and candidate lifecycle state. Before those mechanisms exist, this file records only the implemented algorithms and explicit null/not-implemented markers.

### `failure.txt`

Contains a concise human-readable classification, the first failing invariant or comparison, expected versus observed values, exception information if applicable, and the reproduction command. It must not replace the structured files.

## Preservation Rule

Failure directories are append-only evidence. Retrying a corrected run creates a different run directory and does not remove or mutate the original. Failed and unfavorable cases remain part of the research record even if the implementation later passes.
