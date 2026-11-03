"""One map per job. A fresh attempt owns every file it writes."""
import os
from pathlib import Path
import time
import uuid
from . import basiccode_power as power
from . import basiccode_runner as core
from .basiccode_storage import accept, accepted, read


def run_job(job):
    directory, case_path, stage, config, offset, session, mode, workers = job
    case = read(case_path)
    root = Path(directory) / "jobs" / case["case_id"]
    _, modules = core.load_algorithms()
    reference = None
    if stage in ("timing", "memory"):
        reference = accepted(root / "structural-A")[0]["outcome"]
    sequence = []
    if stage == "timing":
        for phase, count in (("warmup", config["warmups"]), ("timing", config["repetitions"])):
            for rep in range(1, count + 1):
                order = core.ORDERS[(rep - 1 + offset) % len(core.ORDERS)]
                sequence.extend((phase, rep, i, m) for i, m in enumerate(order))
    else:
        sequence = [(stage, int(stage == "memory"), i, m) for i, m in enumerate(core.METHODS)]
    batches = [sequence] if stage == "timing" else [[step] for step in sequence]
    for batch in batches:
        folder = root / ("timing" if stage == "timing" else stage + "-" + batch[0][3].replace("*", "star"))
        if (folder / "mismatch.json").exists():
            raise ValueError(f"Unresolved correctness failure: {folder}")
        saved = accepted(folder)
        if saved is not None:
            if saved[0].get("outcome") is not None:
                reference = saved[0]["outcome"]
            continue
        attempt = folder / uuid.uuid4().hex
        attempt.mkdir(parents=True)
        rows = []
        before = power.sample() if stage == "timing" else None
        for i, (phase, rep, position, method) in enumerate(batch):
            row = {k: case[k] for k in ("case_id", "kind", "size", "obstacle_rate", "seed", "sensor_range", "map_hash")}
            row.update(method=method, phase=phase, repetition=rep, order_index=position,
                       attempt=attempt.name, session=session, mode=mode, workers=workers, pid=os.getpid(),
                       started_utc=core.now(), completed=False, correctness_ok=False, timing_state="pending" if before else "not_applicable")
            core.write_json(attempt / f"{i}.start.json", row)
            print(f"{case['case_id']} {method} {phase} {rep} started", flush=True)
            cpu = time.process_time_ns()
            try:
                metrics, outcome = core.run_episode(modules[method], case, phase)
                row.update(metrics, completed=True, cpu_diagnostic_ns=time.process_time_ns()-cpu)
                row["correctness_ok"] = reference is None or core.canonical(outcome) == core.canonical(reference)
                if reference is None or not row["correctness_ok"]:
                    row["outcome"] = outcome
                if not row["correctness_ok"]:
                    core.write_json(folder / "mismatch.json", {"attempt": attempt.name, "record": i})
                    raise ValueError("Exploration mismatch")
                if reference is None:
                    reference = outcome
                if before:
                    after = power.sample()
                    row.update(power_start=before, power_end=after)
                    if power.interrupted(before, after):
                        row["timing_state"] = "ineligible"
                        raise RuntimeError("Power event or suspend gap within timing block")
                    row["timing_state"] = "eligible"
                row["ok"] = True
            except BaseException as exc:
                row.update(ok=False, error=repr(exc))
                raise
            finally:
                row["finished_utc"] = core.now()
                core.write_json(attempt / f"{i}.json", row)
            rows.append(row)
            print(f"{case['case_id']} {method} {phase} {rep} saved", flush=True)
        accept(folder, attempt, rows)
