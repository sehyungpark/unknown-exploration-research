# Experiment 1 Efficiency Dataset

Frozen: 2026-09-16

Version: `experiment-1-efficiency-v1`

Master seed: `20260916`

Status: **FROZEN — NOT EXECUTED**

## Construction

The dataset contains 27 newly generated square Bernoulli occupancy maps: sizes 20, 30, and 40; sparse `p=0.10`, medium `p=0.20`, and dense `p=0.30`; exactly three accepted maps per size-density stratum.

Generation uses isolated `random.Random` instances and the existing `independent-bernoulli-occupancy-v1` utility. A local master RNG yields one candidate seed with `master_rng.getrandbits(63)` for every attempt. Candidate attempts are ordered by ascending size, then sparse/medium/dense strata, completing three accepted maps in each stratum. Rejections consume their seed-stream position. Cells are generated row-major and are OCCUPIED iff `local_rng.random() < p`.

Stable IDs are `efficiency-{size}x{size}-{density}-{accepted_index:02d}`, where the accepted index is one-based within the stratum.

## Structural Acceptance

Acceptance performs no scan, visibility query, simulator step, planner call, timing, memory tracing, or algorithm execution. It computes FREE components using the frozen 8-neighbor/no-diagonal-corner-cut relation, selects the largest component with the existing deterministic rule, and requires

\[
|C_{\max}|/(H W) \ge 0.35.
\]

The denominator is every grid cell, never the number of FREE cells. The start is the component cell nearest the geometric grid center by squared Euclidean distance, with lexicographic tie breaking. The cycle limit is `max(64, 2 * |C_max|)`.

The canonical map hash is SHA-256 of row-major ASCII (`.` FREE, `#` OCCUPIED), with one LF after every row including the final row, encoded as UTF-8.

## Frozen Counts

| Size | Sparse | Medium | Dense | Total |
|---:|---:|---:|---:|---:|
| 20×20 | 3 | 3 | 3 | 9 |
| 30×30 | 3 | 3 | 3 | 9 |
| 40×40 | 3 | 3 | 3 | 9 |
| **Total** | **9** | **9** | **9** | **27** |

The master-seed stream yielded all 27 accepted maps without a structural rejection. Rejected count is 0 and the frozen rejected-candidate list remains explicitly empty.

## Frozen Accepted Maps

The JSON config is the byte-independent authoritative structured record. The table is a readable mirror.

| ID | Candidate | p | Seed | Start | Component | Fraction | Limit | SHA-256 |
|---|---:|---:|---:|---|---:|---:|---:|---|
| efficiency-20x20-sparse-01 | 0 | 0.10 | 396206647092525091 | `(9,9)` | 350 | 0.875000 | 700 | `34ad5320eebf26d65321338119cff933c3879e877fd13bec5723db54fb025904` |
| efficiency-20x20-sparse-02 | 1 | 0.10 | 3527776923142455108 | `(9,9)` | 353 | 0.882500 | 706 | `6a81cb8f799124381257e56c0b8f93eb3b1b93821e4916c652fa30aa27af4e67` |
| efficiency-20x20-sparse-03 | 2 | 0.10 | 1468113507645515565 | `(9,9)` | 353 | 0.882500 | 706 | `dfd5a44396b2fd41bf65168c832a5342ed85061c5d9af96f70ffead14157df2b` |
| efficiency-20x20-medium-01 | 3 | 0.20 | 5936414117056364106 | `(9,9)` | 326 | 0.815000 | 652 | `423a21b9069e84a5151341e25a632f07bc537bb9fee99b1005ba90fb2c4c0e57` |
| efficiency-20x20-medium-02 | 4 | 0.20 | 3408303682260391401 | `(9,10)` | 312 | 0.780000 | 624 | `bed97e5d0c80c5889f8bab65af94516e3e7fabb950a8512053a3d8b5a85c87d1` |
| efficiency-20x20-medium-03 | 5 | 0.20 | 2224974927589785815 | `(9,9)` | 331 | 0.827500 | 662 | `ccc75821d9edbe87eac0f0a83d0b4e1bdd178550e07dd422ec711b6ccf508490` |
| efficiency-20x20-dense-01 | 6 | 0.30 | 7027758812962882640 | `(9,10)` | 212 | 0.530000 | 424 | `1854e6164ea7bd88a28e99e6d73c8958dc06ffd822b61f227a57a6d9f9f8b7b2` |
| efficiency-20x20-dense-02 | 7 | 0.30 | 4039263727621906482 | `(9,9)` | 267 | 0.667500 | 534 | `8f066f44c7a624b5cbe37b99510550403e57d95d2a49a6837eefadb42d9d43cc` |
| efficiency-20x20-dense-03 | 8 | 0.30 | 5285506591182865045 | `(9,9)` | 270 | 0.675000 | 540 | `ad44a6f6538030fc75e25011dbe9460cee24f8fcc540d53edb1bb13e39c9b959` |
| efficiency-30x30-sparse-01 | 9 | 0.10 | 4620242291655990225 | `(14,14)` | 814 | 0.904444 | 1628 | `eb10eaf609dfed2273f0016b176590396239b2622381a825467a1fbbb0192bfd` |
| efficiency-30x30-sparse-02 | 10 | 0.10 | 5179885829496081708 | `(14,14)` | 806 | 0.895556 | 1612 | `62a6893c2f2b7bcb9e85171bddf93e550d223648319ad7933622b9a35b5556b8` |
| efficiency-30x30-sparse-03 | 11 | 0.10 | 4933659159231084536 | `(14,14)` | 820 | 0.911111 | 1640 | `8a7634f5baa246f589b2c8f8e68b3c92172c47b7b655b2cb80b31af4f9966274` |
| efficiency-30x30-medium-01 | 12 | 0.20 | 2292651632388389521 | `(14,14)` | 682 | 0.757778 | 1364 | `e1b97defba5274ac19327717de91d389034f8a8e8ecce6afc6a466ed0468e175` |
| efficiency-30x30-medium-02 | 13 | 0.20 | 4019378740215595271 | `(14,15)` | 736 | 0.817778 | 1472 | `d20f5978d1b6f30cdebeb1685579e7f93d71a149404b084390ab2628ab2e872d` |
| efficiency-30x30-medium-03 | 14 | 0.20 | 4985532690424040885 | `(14,14)` | 734 | 0.815556 | 1468 | `081967fa2c56546201300b79e29a7ef274cce0658c240b17b814c0f0f315892c` |
| efficiency-30x30-dense-01 | 15 | 0.30 | 4181227871730347873 | `(14,15)` | 627 | 0.696667 | 1254 | `e266ced2a6bc22d585135a66eaf4c2af7d2166a297032070804c99d9356765f5` |
| efficiency-30x30-dense-02 | 16 | 0.30 | 3798701923071634959 | `(14,14)` | 627 | 0.696667 | 1254 | `c113b6f0cac0ece63707ec259e4aae9eeeaf14aaa83cab920ea5a9c30476da6a` |
| efficiency-30x30-dense-03 | 17 | 0.30 | 3845252968367052491 | `(14,14)` | 567 | 0.630000 | 1134 | `12999eba5c33888588eb33feebd101dcae691d37becb150f3c32306368cc08d2` |
| efficiency-40x40-sparse-01 | 18 | 0.10 | 7525947285253146464 | `(19,19)` | 1457 | 0.910625 | 2914 | `b2783267351f59db229ff5f99406775ba324d758c1d8d0169d771d4abe6c666c` |
| efficiency-40x40-sparse-02 | 19 | 0.10 | 8480785709378275510 | `(19,19)` | 1456 | 0.910000 | 2912 | `d0eda0c88a18f87c8ae3bf60754fa3ee96d153b030ce9adf97ed26bbd7573708` |
| efficiency-40x40-sparse-03 | 20 | 0.10 | 6900275667820993594 | `(19,19)` | 1427 | 0.891875 | 2854 | `7a9d73c2ce7cc4eb714d696d3e1ae5646cb374b82417d3fcb50e0376eb2aeb71` |
| efficiency-40x40-medium-01 | 21 | 0.20 | 426262264825024557 | `(19,19)` | 1257 | 0.785625 | 2514 | `5f2a5d3548d5e21e3375ee89eba002761109618666eaee012e3766202bd46f1b` |
| efficiency-40x40-medium-02 | 22 | 0.20 | 7282332034119835923 | `(19,19)` | 1278 | 0.798750 | 2556 | `56923445693b45a2cf817436276b4c35dfacc74206d06af70e147c9f563a6859` |
| efficiency-40x40-medium-03 | 23 | 0.20 | 7606866061046530457 | `(19,20)` | 1271 | 0.794375 | 2542 | `65ed717b42dc10a2a21e7f38edebd253956db6600442feabb0109c00204e5afc` |
| efficiency-40x40-dense-01 | 24 | 0.30 | 8734162765531759123 | `(19,20)` | 1119 | 0.699375 | 2238 | `519c4edfad998e8f8b62cf8a566675992c02b141d9fce43bab00f3711ebe95d3` |
| efficiency-40x40-dense-02 | 25 | 0.30 | 2768749553237946917 | `(19,20)` | 1111 | 0.694375 | 2222 | `ab47b0d9917f6ae8a979faf70d285b6101144f190c99c340c01627917a0b8e45` |
| efficiency-40x40-dense-03 | 26 | 0.30 | 4882629557860671764 | `(19,19)` | 1063 | 0.664375 | 2126 | `1862e5de9ebf1c4514dbabdb8c02d1d13b62b8d2afb800f0e46d7b8e6b9d90c6` |

## Frozen Subsets

Timing and separate `tracemalloc`: the nine `*-01` maps, one per stratum. Range sensitivity: the three `efficiency-30x30-*-01` maps. These lists are explicit in the JSON config and must not be changed after observing performance.

## Regeneration

```text
python -m src.evaluation.experiment_1_dataset --output configs/experiment_1_efficiency_maps.json
```

Regeneration tests verify version, seed, IDs, strata, probabilities, candidate seed stream, component size/fraction, start, limit, hash, exact balance, and that dataset construction cannot call the planner. Regeneration is verification, not Experiment 1 execution.
