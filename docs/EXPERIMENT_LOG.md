# Experiment Log

This is an append-only record. Failed, unfavorable, incomplete, and non-reproducible experiments must remain in the log.

For new runs, record at least: date/time, run ID, code/algorithm version, map family and instance ID, map seed, start seed, map size, movement model, sensor configuration, algorithm, parameters, completion target, metrics, raw-result location, runtime, success/failure, failure reason, and interpretation.

## Legacy Records Recovered from `RESEARCH_CONTEXT.md`

These entries predate this log. Missing values are explicitly marked rather than inferred.

### LEGACY-C1 — Candidate 1 Toy Sanity Check

- **Date/time:** Not recorded
- **Status:** Preliminary evidence; not reproducible from current repository
- **Map conditions:** 31×31 toy maps; rooms, clutter, and maze families
- **Map instance IDs:** Not recorded
- **Random seeds:** Not recorded
- **Start seeds/positions:** Not recorded
- **Algorithm:** Exhaustive NBV versus Candidate 1 lazy NBV prototype
- **Algorithm/code version:** Not recorded; code unavailable
- **Parameters:** Not recorded
- **Reported results:** Same target sequence and moves; exact gain evaluations reduced by approximately 82%, 87%, and 96% across the reported toy cases
- **Raw results/runtime:** Not recorded
- **Failure:** No mismatch reported; reproducibility metadata is missing
- **Interpretation:** Sanity-check evidence only, not a publication result or a verified repository result

### LEGACY-C2 — Candidate 2 Synthetic Prediction Check

- **Date/time:** Not recorded
- **Status:** Preliminary evidence; not reproducible from current repository
- **Map conditions:** Synthetic corrupted prediction; exact maps and corruption settings not recorded
- **Map instance IDs/random seeds:** Not recorded
- **Algorithm:** Blind predictor, robust baseline, and robust-gate prototype
- **Algorithm/code version:** Not recorded; code unavailable
- **Parameters:** Not recorded
- **Reported results:** Blind prediction could fail; baseline and robust gate succeeded in the toy tests
- **Raw results/runtime:** Not recorded
- **Failure:** Blind predictor failures were observed; individual failure cases and reasons were not recorded
- **Interpretation:** Suggests avoidance of catastrophic prediction failure, but does not establish consistently shorter paths

### LEGACY-C3 — Candidate 3 Sequential Sensing Check

- **Date/time:** Not recorded
- **Status:** Preliminary evidence; not reproducible from current repository
- **Map/sensor conditions:** Not recorded
- **Map instance IDs/random seeds:** Not recorded
- **Algorithm:** Simple sequential evidence accumulation versus fixed repeated sensing
- **Algorithm/code version:** Not recorded; code unavailable
- **Parameters:** Not recorded
- **Reported results:** Sequential evidence accumulation reportedly required substantially fewer sensor evaluations
- **Raw results/runtime:** Not recorded
- **Failure:** No run failure reported; theoretical certification is incomplete
- **Interpretation:** Motivating observation only; the stopping rule has not been justified as a rigorous confidence-sequence theorem

### LEGACY-C4 — Candidate 4 Low-Recourse Repair Check

- **Date/time:** Not recorded
- **Status:** Preliminary and unfavorable evidence; not reproducible from current repository
- **Map conditions:** Some toy maps; exact families and instances not recorded
- **Map instance IDs/random seeds:** Not recorded
- **Algorithm:** Fresh greedy cover versus low-recourse repair prototype
- **Algorithm/code version:** Not recorded; code unavailable
- **Parameters:** Not recorded
- **Reported results:** Low-recourse repair reduced recourse but substantially increased viewpoint count on some maps
- **Raw results/runtime:** Not recorded
- **Failure:** Quality degradation occurred on unspecified maps; exact thresholds and cases were not recorded
- **Interpretation:** Candidate 4 remains high risk; reducing recourse alone is not sufficient evidence of success

## New Experiments

No new experiments have been executed in the current repository.
