# Experiment 2 Laptop Runbook (Windows PowerShell)

This is the exact local workflow for C* validation and the later formal
performance experiment.

## Phase A — code validation first

From the repository root:

```powershell
git status
git fetch origin
git switch main
git pull --ff-only origin main
python --version
```

Use Python 3.12.x if available.

Run focused C* tests:

```powershell
python -m unittest tests.test_change_aware_star_nbv -v
python -m unittest tests.test_change_aware_star_regression -v
python -m unittest tests.test_experiment_2_cstar -v
```

Then run the full suite:

```powershell
python -m unittest discover -s tests -v
```

Do not proceed to performance measurement unless all tests pass.

## Phase B — freeze the new holdout dataset

Generate the Experiment 2 config:

```powershell
python -m src.evaluation.experiment_2_dataset --output configs/experiment_2_cstar_maps.json
```

Inspect the diff:

```powershell
git diff -- configs/experiment_2_cstar_maps.json
git status
```

The config must say:
- dataset_version = experiment-2-cstar-efficiency-v1
- master_seed = 20260919
- accepted_total = 27
- nine timing map IDs
- three sensitivity map IDs

Run the focused dataset/smoke tests again:

```powershell
python -m unittest tests.test_experiment_2_cstar -v
```

Then freeze the config **before looking at any Experiment 2 performance**:

```powershell
git add configs/experiment_2_cstar_maps.json
git commit -m "Freeze Experiment 2 C-star holdout dataset"
git push origin main
```

Wait for GitHub CI to pass.  Do not edit the config after this point.

## Phase C — prepare the laptop for primary timing

Use the same machine for the entire formal invocation.

Recommended:
- reboot before the run;
- connect AC power;
- keep Windows power mode fixed;
- close games, browser tabs doing heavy work, IDE background indexing, downloads;
- pause avoidable updates/sync;
- do not run another benchmark concurrently.

Verify repository identity and cleanliness:

```powershell
git status
git rev-parse HEAD
python --version
```

`git status` must be clean.  The runner refuses a dirty worktree.

## Phase D — formal Experiment 2

Choose one unique invocation ID, for example:

```powershell
python -m src.evaluation.experiment_2_runner --execute-preregistered --invocation-id experiment2-formal-20260919-001
```

The runner performs:
- 27-map shared structural A/B/C/C* correctness/work pass;
- seven anchor fixtures;
- nine-map warm-up + six-repetition primary timing;
- separate decomposition;
- separate tracemalloc memory;
- separate C* audit;
- R=4/8/12 sensitivity.

Do not stop and rerun because a result looks unfavorable.

## Phase E — results

The run is written under:

```text
results/experiment_2/runs/<invocation_id>/
```

Files are deliberately compact and Git-friendly:

- manifest.json
- structural.jsonl
- timing_repetitions.jsonl
- decomposition.jsonl
- memory.jsonl
- audit.jsonl
- summary.json
- failure.json only if a failure occurs

No giant per-snapshot dump is produced by Experiment 2.

Inspect:

```powershell
Get-Content results\experiment_2\runs\experiment2-formal-20260919-001\summary.json
git status
```

If the run completed, preserve it regardless of outcome:

```powershell
git add results/experiment_2/runs/experiment2-formal-20260919-001
git commit -m "Record formal Experiment 2 result"
git push origin main
```

That uploads the core scientific evidence to GitHub.

## Important separation

GitHub Actions is used for correctness/smoke validation, not as the source of
primary wall-clock performance.  Primary timing comes from this laptop formal
invocation only.
