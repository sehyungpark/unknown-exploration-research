# basiccode experiment redesign proposal — 2026-11-02

**Status: archived, not implemented or adopted.** The user chose to retain complete explorations and reduce the default to 50/100/150, densities 0.1/0.3/0.5, three seeds and five repetitions (`configs/basiccode_reduced_v1.json`). The proposal below is historical, not current execution guidance. It introduces no performance result or new algorithm. The user's running process and saved evidence are not changed.

## Why reconsider the measurement unit

The current runner performs 1821 complete explorations including 1125 timed ones. User-reported CPU counters increased from 28775.90625 to 28785.5625 in about ten seconds, showing active computation by python3.13. The last reported stage was `Measuring n200-p0.1-seed42`. The approximately eight cumulative CPU hours cannot identify how much time was spent in the completed 100-size cases versus the current 200-size case. Earlier conversational weeks/months estimates were rough risk scenarios, not validated runtime forecasts.

First read existing completed records without running another exploration. Determine method/map/phase runtimes, planning-call counts, and when sleep occurred. The Windows performance-counter clock can include system sleep, so the sleep-affected run must be annotated and its primary timing eligibility audited. Preserve all records. Do not discard an outlier merely because it is unfavorable. If the affected interval cannot be identified reliably, retain that invocation as pilot/feasibility evidence and collect a clean timing run under a new ID.

## Evidence to collect

1. **Complete-exploration evidence:** start with all five densities and three seeds at 100x100, A/B/C*, one warm-up and five timed repetitions (225 timed explorations). Verify the complete A/B/C* trajectory and final map, measure planner and episode time separately. Before formal timing, use the existing pilot to forecast cost; decide a fixed total time/memory budget and whether the entire 200x200 block fits. Include all its densities/methods if that block is selected. Do not extend or shrink blocks based on favorable speedups.
2. **Large-state planner evidence:** retain all 25 requested size-density conditions and all three seeds through 500x500. Preselect observation progress levels, e.g. 10/20/30/40/50/60/70/80/90/95 percent known, and sample the first planning state reaching each level. A/B/C* receive identical known map, position, range and candidate rules. Five measurements of ten saved states on 75 maps gives 11250 timed **planner calls**, not 11250 complete explorations. Reference trace construction/prefix replay has a cost and must be budgeted separately; no runtime reduction factor is guaranteed.
3. **Memory/mechanism evidence:** use a separate untimed pass at a predetermined subset, e.g. seed 42 at all 25 conditions. Report retained cache/mask size and candidate/evaluation counts. If measuring a saved planner call, distinguish pre-existing retained cache from new allocations inside the call and process RSS. A call-only tracemalloc peak does not measure the cache built before tracing. Avoid five full memory explorations per condition.

The first experiment supports complete-exploration claims only on fully tested sizes. The second supports planner latency/work claims at the sampled large states. It must not be labeled as a measured whole-exploration speedup through 500x500. A equality checks only at sampled large states establish sampled agreement, not full-trajectory agreement with A at every omitted state.

## Fair stateful replay requirements

- Build a physically valid monotone observation trace using the same simulator/sensor. A reference B rollout is a possible driver after full A/B/C* agreement on the complete-exploration validation block; verify B/C* decisions throughout the large trace and A at the selected probe states. Record the driver explicitly and do not treat its unsampled decisions as independently validated by A.
- Reconstruct each method's own cache through **every preceding planning state**, including unmeasured states. B keeps its legitimate stale gains; C* keeps range/visibility caches, UNKNOWN mask and pending revelation delta. Independently reset cold caches at each probe would change the algorithmic regime and can weaken B.
- Save the pre-call state. Restore that same pre-call state before each of the five repetitions; never reuse a cache already updated by the previous repetition. Restore/copy outside timing, but keep current-step mask synchronization, BFS and selector work inside the original planning-call boundary.
- Reference validation, trace collection, work counters and memory instrumentation stay outside primary timing. Keep original algorithms, map family, R=4, score/ties and candidate domain fixed.
- If full trace construction or checkpoint storage exceeds the fixed budget, record budget exhaustion and unreached probe levels. Do not silently skip those maps or average only the surviving favorable cases. This trace cost and original C* global bitset RAM remain potential feasibility limits.

## Required runner improvements before adopting this plan

- Persist progress at episode/method/repetition boundaries; resume from saved inputs and matching code/config identity. An interrupted complete episode restarts from its beginning. Do not promise mid-trajectory recovery without serializing planner/map state.
- Record UTC start/end, phase, method, repetition, progress, wall time, CPU time and explicit OS suspend/resume evidence. A wall/CPU gap alone is not proof of sleep and must not automatically remove results.
- Predetermine resource/time limits before the new primary run. Timeouts/OOM and unattempted budget-limited cases are explicit statuses. Preserve original raw evidence and show failure/timeout counts rather than reporting an uncensored mean over survivors.
- Freeze manifests and split full-exploration versus sampled-state result/figure labels. Current old-run reanalysis must stay compatible and must not overwrite its raw files.

## Figures and interpretation

- Complete-exploration planner time and episode time, faceted by density.
- Large-state selection latency and paired speed ratios versus map size, faceted by density/progress.
- Exact evaluations and retained cache/mask storage versus candidate count/map size.
- Completion, timeout, memory-failure and probe-availability tables for every requested condition.

Use maps as the unit for paired summaries; repetitions quantify measurement variation, not extra independent maps. Keep laptop and iMac runs separate. Use one machine for a primary timing invocation and the other for matched-source/config replication, without assuming the iMac is faster. The connected scaffold distribution remains a limitation on environmental generalization.

References: [pyperf sequential measurement/warm-ups](https://pyperf.readthedocs.io/en/latest/run_benchmark.html), [Python memory tracing scope](https://docs.python.org/3/library/tracemalloc.html), [Windows performance counter and sleep](https://learn.microsoft.com/en-us/windows/win32/sysinfo/acquiring-high-resolution-time-stamps).
