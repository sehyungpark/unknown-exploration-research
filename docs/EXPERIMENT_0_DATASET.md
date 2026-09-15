# Experiment 0 Random Correctness Dataset

Corrected freeze: 2026-09-15

## Status and Scope

This document freezes the random-map portion of Experiment 0 before Algorithms B or C exist. It defines a correctness dataset only. It does not report an equivalence experiment, performance benchmark, runtime comparison, or research outcome.

The canonical machine-readable artifact is `configs/experiment_0_random_maps.json`. Every accepted map is regenerated from its recorded seed and verified against its recorded SHA-256 hash. Frozen seeds must not be changed in response to later algorithm results.

## Dataset Version History

- `experiment-0-random-v1`: **INVALIDATED BEFORE EXPERIMENT 0 EXECUTION.** Its acceptance implementation divided the largest FREE-component size by the number of FREE cells, although the intended rule divided by all grid cells. No Algorithm B/C implementation or result existed when the mismatch was found.
- `experiment-0-random-v2`: **CURRENT CORRECTED FREEZE.** It uses `largest_free_component_size / (height * width) >= 0.35` and was rematerialized from the unchanged master seed and normal candidate-seed stream before Experiment 0 execution.

The v1 record remains in repository history. It must not be used for Experiment 0. The corrected rejection at candidate index 34 consumes that seed normally, so 26 of the 60 ID-indexed accepted seeds and hashes differ between v1 and v2.

## Dataset Size and Balance

- Sizes: `12x12`, `16x16`, and `20x20`.
- Accepted maps per size: 20.
- Total accepted maps: 60.
- Density categories: `sparse` (`p=0.10`), `medium` (`p=0.20`), and `dense` (`p=0.30`).
- Accepted density target within each size: 7 sparse, 7 medium, and 6 dense. This is the most even integer allocation of 20 maps under the fixed ordering used here.
- Total accepted density counts: 21 sparse, 21 medium, and 18 dense.

Dataset indices are zero-based. Stable IDs are `random-000` through `random-059`.

## Generator and Seed Derivation

- Dataset version: `experiment-0-random-v2`.
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
- the chosen largest FREE component contains at least 35% of all grid cells, precisely `largest_free_component_size / (height * width) >= 0.35`;
- after the existing physical initial scan at range `R=8`, the existing exhaustive optimistic-NBV oracle does not immediately return `EXPLORATION_COMPLETE`;
- initial construction, scan, and planning complete without an exception.

Stable rejection reasons are:

- `no_free_cell`;
- `no_start_cell`;
- `no_occupied_cell`;
- `largest_component_fraction_below_0.35`;
- `initial_scan_exploration_complete`;
- `initial_scan_exception:<ExceptionClass>`.

The corrected v2 materialization produced one rejected candidate. Candidate index 34, the 16×16 dense map with seed `610347355546169441`, has largest-component size 79, so `79/256 < 0.35`; it is retained with reason `largest_component_fraction_below_0.35`. The rejected seed consumes its normal master-RNG position.

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

## Frozen v2 Accepted Maps

| ID | Dataset index | Candidate index | Size | Density | p | Seed | Start | Component | Limit | SHA-256 |
|---|---:|---:|---:|---|---:|---:|---|---:|---:|---|
| random-000 | 0 | 0 | 12 | sparse | 0.10 | 5330464865640108879 | `(5,5)` | 125 | 250 | `0f89feeb800881672dd827264f99f0d65435b23ea7d9d102e14dbaf8370169e8` |
| random-001 | 1 | 1 | 12 | medium | 0.20 | 955472025546279012 | `(5,5)` | 114 | 228 | `cb8b7b989e0a245ae8451021fec801e6796d085285cc752c6ce3c82e489e9f18` |
| random-002 | 2 | 2 | 12 | dense | 0.30 | 1903186950733795108 | `(5,5)` | 98 | 196 | `f458bd914ec5a61f45385ba53204b5e78d27b22f2d5ca7cfbd03846136b57478` |
| random-003 | 3 | 3 | 12 | sparse | 0.10 | 8085182145960130748 | `(5,5)` | 126 | 252 | `42b95a87f391403ae4f495ebf16ff9d66ca1ebef6e7285c4d76918210bc02524` |
| random-004 | 4 | 4 | 12 | medium | 0.20 | 6637139884518318721 | `(5,6)` | 111 | 222 | `41177d42d283b990df6393bce5cf74bec5000aaf015ec6a3a1946cb4fbde45de` |
| random-005 | 5 | 5 | 12 | dense | 0.30 | 7846884780050957208 | `(5,6)` | 82 | 164 | `a920f363e444793f53bdd13f5adf16077a2196bd3068d94021675d7205815287` |
| random-006 | 6 | 6 | 12 | sparse | 0.10 | 7158271266397058817 | `(5,5)` | 132 | 264 | `f0578585b619fe4efd668d670aba0171658d28bfb95cafaa74ee44c18dbd5ef6` |
| random-007 | 7 | 7 | 12 | medium | 0.20 | 1206365467561632495 | `(5,5)` | 124 | 248 | `c1728c6962084246642789c17dd99ecc416cbcb00527c0b1e84ee2f64e65680f` |
| random-008 | 8 | 8 | 12 | dense | 0.30 | 4132815764534142760 | `(5,5)` | 75 | 150 | `5539300028f0088678b88b1f87bfbeb54460d42e98c7b06606bcf3febf1a9ebc` |
| random-009 | 9 | 9 | 12 | sparse | 0.10 | 8802829629943226820 | `(5,5)` | 130 | 260 | `07bd677897544a454e46cd0d763cc61ba6c2ba9c02c46b3d237a3eb62642665c` |
| random-010 | 10 | 10 | 12 | medium | 0.20 | 369154256546639294 | `(5,5)` | 115 | 230 | `518781382799664fe5481360fa83473848253e9b1a1b1670052899844ef170df` |
| random-011 | 11 | 11 | 12 | dense | 0.30 | 1051975539896974326 | `(5,5)` | 100 | 200 | `5ee6150f5defba9febfa54f06b3f24ef17089b2b935fde3fb7fa8cc591ba55ce` |
| random-012 | 12 | 12 | 12 | sparse | 0.10 | 1800328902482533194 | `(5,5)` | 124 | 248 | `16d60fd613753d119ab6ee693b2b11ceb6ee9a9207dca9834074fed57a3cd7af` |
| random-013 | 13 | 13 | 12 | medium | 0.20 | 5988504920873199647 | `(5,5)` | 111 | 222 | `138d63ec53f1b961a5587f3ee0e89e7e6900e9938079f5e6bc7da48264fe129b` |
| random-014 | 14 | 14 | 12 | dense | 0.30 | 2572890099909938680 | `(5,6)` | 90 | 180 | `247f400243efad39d6384092b2b675fd271f468489b7f27ef1c57575b3902051` |
| random-015 | 15 | 15 | 12 | sparse | 0.10 | 4571056704688308073 | `(5,5)` | 133 | 266 | `316c35f818dc76cf960295b84f6935f3ad9079070ce746ae9a3411f42b8f76e0` |
| random-016 | 16 | 16 | 12 | medium | 0.20 | 6014036470810819738 | `(5,6)` | 105 | 210 | `b284687ea2409d60d94c7a4908c86fd882d7d9541af045c2ff7dffee3a12d9be` |
| random-017 | 17 | 17 | 12 | dense | 0.30 | 1520134412578172377 | `(5,5)` | 91 | 182 | `67db4060ff86e2f52086076260d6d36f79d59441b647202822a24f42a89da1d5` |
| random-018 | 18 | 18 | 12 | sparse | 0.10 | 1100028404642902184 | `(5,5)` | 130 | 260 | `90b0e2e607a6f54c4e55f987fba5eabf5f9d48b4376e395b07d039f7aa4a8a26` |
| random-019 | 19 | 19 | 12 | medium | 0.20 | 2800958006169347911 | `(5,6)` | 111 | 222 | `f2ab067c9faae908f66a559f1d9136cc7c1a6e86d7254b9f01cd00b361e3807d` |
| random-020 | 20 | 20 | 16 | sparse | 0.10 | 1880414660931474401 | `(7,7)` | 222 | 444 | `2c85fb89bb6cb0a186ae69f36fa109ce900974088987c57b0f89daf00e499b1e` |
| random-021 | 21 | 21 | 16 | medium | 0.20 | 5134457112488694088 | `(7,7)` | 208 | 416 | `e4b8dfd39dc0f3561ff9091a67f101df115ea243d87ef15725297da41e085bd3` |
| random-022 | 22 | 22 | 16 | dense | 0.30 | 1230802023119051294 | `(7,7)` | 161 | 322 | `2b33271e0b86b85823a4b1f4680af185dbec74a3793d256530a0db406b6f3d3c` |
| random-023 | 23 | 23 | 16 | sparse | 0.10 | 1011295616428472583 | `(7,7)` | 233 | 466 | `9802a7342e25211ee44243cea8f5592fbca0240d05e4a152753f00f9dc3a524f` |
| random-024 | 24 | 24 | 16 | medium | 0.20 | 7454983040647381124 | `(7,7)` | 204 | 408 | `8392305fe173c8d54a11e1ad9c11a7b4c0f6bdbf5fc400f5476e093506cebad7` |
| random-025 | 25 | 25 | 16 | dense | 0.30 | 4301554879512216079 | `(7,8)` | 163 | 326 | `0997bad370d61e34bddd34a6e38ccb3c32f5d5f8f66fadc6a3d787268b2d8bff` |
| random-026 | 26 | 26 | 16 | sparse | 0.10 | 2784396512309990412 | `(7,7)` | 233 | 466 | `0f5969178b7c8c7e459aa12765caf316f0a897cd2f0b1ddbd16d811fcfafad33` |
| random-027 | 27 | 27 | 16 | medium | 0.20 | 1482061114159451424 | `(7,8)` | 213 | 426 | `27b49a56b415000201df4d7f0df7854549cd2b24ac616d8b97bfe526fa9a4cf3` |
| random-028 | 28 | 28 | 16 | dense | 0.30 | 7430184768040742675 | `(7,7)` | 164 | 328 | `ff53f6b2973189362af02411d79c447b64acb8627cd03d9e0b13243e12780056` |
| random-029 | 29 | 29 | 16 | sparse | 0.10 | 1136508859744666050 | `(7,7)` | 227 | 454 | `44cdd9bfb187808e5f23c90dd346b73e4abd5f93254f2b575574307780aa127d` |
| random-030 | 30 | 30 | 16 | medium | 0.20 | 8412438158528573997 | `(7,7)` | 203 | 406 | `5d652bb65d1f58eaa35b4a2a553d2e72c0c373f2938a4acca431cd079fdad3da` |
| random-031 | 31 | 31 | 16 | dense | 0.30 | 3075508591194015516 | `(7,7)` | 165 | 330 | `fb280f4c047d7298a393b2941998f1aa44c0282f75d56158734160d59f41dd50` |
| random-032 | 32 | 32 | 16 | sparse | 0.10 | 6785699117671774509 | `(7,7)` | 234 | 468 | `fa24261a83dbda08ebb48494813c91f684224c6171de4935e9d1f3549df2b6f8` |
| random-033 | 33 | 33 | 16 | medium | 0.20 | 5642286221174944837 | `(7,8)` | 204 | 408 | `3a11696a4e94be9640d07d5cd78708e25a40cb6395abe46817fd7553f989da57` |
| random-034 | 34 | 35 | 16 | sparse | 0.10 | 4959491098902389966 | `(7,7)` | 233 | 466 | `591a182712da6b6e7d9b78a55c4b292474cae6cde5fda0f0f12b1cbb9a837d19` |
| random-035 | 35 | 36 | 16 | medium | 0.20 | 5297625360906615739 | `(7,7)` | 186 | 372 | `6f4810738e5dd2de40f7a1b31b4ffbb13eb5f9ac9a88a7c7c2aa5d619e09ba6a` |
| random-036 | 36 | 37 | 16 | dense | 0.30 | 1539704733943483973 | `(8,7)` | 171 | 342 | `7d1829093dd607b326b80c69082729bd0f30b7981e2c3fb601e1800707c8fcbe` |
| random-037 | 37 | 38 | 16 | sparse | 0.10 | 4710615621458320133 | `(7,7)` | 233 | 466 | `0e91b4e7d8dd32027bcca37323b23fb77e7b4c1cc443066d0160cb811ec5792f` |
| random-038 | 38 | 39 | 16 | medium | 0.20 | 2800192199628028969 | `(7,8)` | 202 | 404 | `d0dc72f511ddfa5ccf8d99cc73b6d0b3b36e503138390ac1bad7708617a6f6b5` |
| random-039 | 39 | 40 | 16 | dense | 0.30 | 3401625048423572859 | `(7,7)` | 172 | 344 | `3b8f02da3b12ab451c8298dbd65e0bc3d95503ace5e5596f41d22526c07faeca` |
| random-040 | 40 | 41 | 20 | sparse | 0.10 | 3752429512835464017 | `(9,9)` | 364 | 728 | `39119e13c40cf8aa32db618f156216b0798f7e514774f39afa1c5a53c73b87c6` |
| random-041 | 41 | 42 | 20 | medium | 0.20 | 7897086557936856052 | `(9,10)` | 313 | 626 | `eb800d247e09aa946a55d222c07fccc1cfec54cb311c316e40109759e50475bf` |
| random-042 | 42 | 43 | 20 | dense | 0.30 | 6789104085363263613 | `(9,9)` | 272 | 544 | `3e1cf063358e0cda0cd86749bcd47e0181add0987a461c9c8042a7b33c629b31` |
| random-043 | 43 | 44 | 20 | sparse | 0.10 | 7037570802641513515 | `(9,9)` | 361 | 722 | `45b49d77b28ab67da2fca41a46180a2ae676367adc1da251aff5bec1d22605ea` |
| random-044 | 44 | 45 | 20 | medium | 0.20 | 2779123786463267563 | `(9,9)` | 316 | 632 | `c997316e686e453f97b40e3a1cfcadeb2920dbf1652ef083e1406d3e26073829` |
| random-045 | 45 | 46 | 20 | dense | 0.30 | 3647060634515756289 | `(9,10)` | 280 | 560 | `7d4274afc8a3558c4a602a6a881ee07a2bfd7049be465faa2bf4f02d0c599ee0` |
| random-046 | 46 | 47 | 20 | sparse | 0.10 | 524680294426764532 | `(9,9)` | 352 | 704 | `dede03e5375e3c18a5176c7329e32e04742b1140b2eec4c92d667deb19435c25` |
| random-047 | 47 | 48 | 20 | medium | 0.20 | 5107640096050154906 | `(9,10)` | 307 | 614 | `6b342d5f1c4be36889f261d9cb23027eabea9dab61bb870a3328efb26e165d4b` |
| random-048 | 48 | 49 | 20 | dense | 0.30 | 7210308160815558773 | `(9,9)` | 263 | 526 | `29fbb15a71e9beaefbc4095fd0d5677adcd3afb86376559eb4c78998c3cbefe3` |
| random-049 | 49 | 50 | 20 | sparse | 0.10 | 928323131437836541 | `(9,9)` | 364 | 728 | `c1d7c41e77e2a812787997550d411fa3c5525e2e8a81cd810ab8056c446e6c1d` |
| random-050 | 50 | 51 | 20 | medium | 0.20 | 6271593426382089067 | `(9,9)` | 315 | 630 | `00ff58a44612ffa9096fe4520cc771b25514b56aafd314987c809e930da26a4d` |
| random-051 | 51 | 52 | 20 | dense | 0.30 | 7390184556386850754 | `(9,9)` | 300 | 600 | `91789f46aebdb106f778faa56b1274c3b5058e7e76ec3a81a1aeb7661db71b1c` |
| random-052 | 52 | 53 | 20 | sparse | 0.10 | 7079186175911782948 | `(9,9)` | 356 | 712 | `bf02e58c452d0cd0167aa293d895776034ad93a9edf1824cebfed4cfc69c8c98` |
| random-053 | 53 | 54 | 20 | medium | 0.20 | 492367480353796936 | `(9,9)` | 324 | 648 | `49c68ced0fbe5c459405b4bbd6e7ccedd8d8bed087994505919e383bc8f520d9` |
| random-054 | 54 | 55 | 20 | dense | 0.30 | 8642220197476521168 | `(9,9)` | 268 | 536 | `f801740cb75220ebc6675c4163590762fb23ecefb2dfb640d4d2db02f3a5e127` |
| random-055 | 55 | 56 | 20 | sparse | 0.10 | 8872522031597770444 | `(9,9)` | 370 | 740 | `a43df844baeb52502d73cf0f3e83118d6e7f5c7634fe1dfa98c73acfe5adb258` |
| random-056 | 56 | 57 | 20 | medium | 0.20 | 2111518878601351473 | `(9,9)` | 322 | 644 | `79c3b40c0202b8c49d80a8a444f1472deebc81975ee3a9815dbda695d66c1e95` |
| random-057 | 57 | 58 | 20 | dense | 0.30 | 5711399435219062689 | `(10,10)` | 276 | 552 | `423b829f3977962f5f0f9115f7b0dff31fdff72c1ef84e43e7f922b819db650d` |
| random-058 | 58 | 59 | 20 | sparse | 0.10 | 8000994055318961516 | `(9,9)` | 356 | 712 | `e2776e428d3d408ad57cd13bbf01ea016ec376decaf8edd09db1e8dc66ef1927` |
| random-059 | 59 | 60 | 20 | medium | 0.20 | 5277239599950553096 | `(9,9)` | 286 | 572 | `0a2ec0a79c0778a6de452b473b65526aa6f5ce063fd67e74a13c785add6e230a` |

## Frozen v2 Rejected Candidates

| Candidate index | Size | Density | p | Seed | Start | Reason | SHA-256 |
|---:|---:|---|---:|---:|---|---|---|
| 34 | 16 | dense | 0.30 | 610347355546169441 | `(7,7)` | `largest_component_fraction_below_0.35` | `104937d295cb13bacea4e678c5d3b1b240e33383c4a2b02d1ac6a74be07d6fa1` |

Rejection count: 1. Rejection-reason summary: `largest_component_fraction_below_0.35: 1`.

## Reproduction and Verification

Materialize the canonical artifact with:

```text
python -m src.evaluation.random_dataset --output configs/experiment_0_random_maps.json
```

The test suite checks deterministic regeneration, exact accepted counts and balance, start selection, acceptance rules, cycle limits, config schema, all frozen hashes, hash content sensitivity, and absence of any Candidate 1 lazy-method dependency.
