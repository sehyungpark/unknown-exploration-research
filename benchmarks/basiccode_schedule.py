"""Recoverable map scheduling for basiccode. Uses v1 measurements and analysis."""
import multiprocessing
from multiprocessing.connection import wait
from pathlib import Path
import platform
import sys
import uuid
import zipfile

from . import basiccode_runner as core
from .basiccode_power import awake
from .basiccode_storage import accepted, coordinator_lock, read
from .basiccode_worker import run_job


def status(directory):
    manifest = read(directory / "manifest.json")
    starts = directory.glob("jobs/*/*/*/*.start.json")
    latest = max(starts, key=lambda p: p.stat().st_mtime_ns, default=None)
    current = read(latest) if latest else {}
    return {"run_id": manifest["run_id"], "status": manifest["status"],
            "mode": manifest.get("mode"), "accepted_jobs": sum(1 for _ in directory.glob("jobs/*/*/accepted.json")),
            "latest_start": {k: current.get(k) for k in ("case_id", "phase", "method", "repetition", "started_utc")},
            "last_error": manifest.get("last_error")}


def dispatch(jobs, workers):
    if workers == 1:
        for index, job in enumerate(jobs, 1):
            run_job(job)
            print(f"{job[2]}: {index}/{len(jobs)} maps ready", flush=True)
        return
    context = multiprocessing.get_context("spawn")
    pending = iter(jobs)
    active = {}
    completed = 0
    try:
        while completed < len(jobs):
            while len(active) < workers:
                job = next(pending, None)
                if job is None:
                    break
                process = context.Process(target=run_job, args=(job,))
                process.start()
                active[process.sentinel] = process, job
            for sentinel in wait(list(active)):
                process, job = active.pop(sentinel)
                process.join()
                code = process.exitcode
                process.close()
                if code:
                    raise RuntimeError(f"{job[1].stem} {job[2]} worker exited with code {code}")
                completed += 1
                print(f"{job[2]}: {completed}/{len(jobs)} maps ready", flush=True)
    finally:
        for process, _ in active.values():
            process.terminate()
            process.join()
            process.close()


def backup_wave(directory, backup, name, files):
    target = backup / (name + ".zip")
    temporary = target.with_suffix(".partial")
    with zipfile.ZipFile(temporary, "x", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            if path.is_file():
                archive.write(path, path.relative_to(directory))
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip():
            raise IOError("Backup verification failed")
    temporary.replace(target)


def run(config_path, output_root, run_id, *, mode="isolated", workers=2, resume=False, smoke=False, plots=True, backup_root=None):
    from .basiccode_analysis import analyze
    if not core.RUN_ID.fullmatch(run_id) or workers < 1 or mode not in ("isolated", "concurrent"):
        raise ValueError("Invalid run ID, mode or worker count")
    if plots and core.importlib.util.find_spec("matplotlib") is None:
        raise RuntimeError("Install requirements-basiccode.txt or use --no-plots")
    config_path = Path(config_path).resolve()
    config = core.validate_config(read(config_path))
    source = core.source_identity(config_path)
    if source["dirty"] and not smoke:
        raise ValueError("Commit benchmark sources before measuring")
    directory = Path(output_root).resolve() / run_id
    if not resume:
        directory.mkdir(parents=True, exist_ok=False)
    signature = {"config_hash": core.digest(config), "source": source, "mode": mode, "workers": workers,
                 "system": {"python": sys.version, "platform": platform.platform(), "host": platform.node(),
                            "processor": platform.processor(), "architecture": platform.machine()},
                 "purpose": "smoke_validation" if smoke else "exploratory_benchmark"}
    manifest_path = directory / "manifest.json"
    with coordinator_lock(directory):
        if resume:
            manifest = read(manifest_path)
            if manifest.get("execution_schema") != 2 or any(manifest.get(k) != v for k,v in signature.items()):
                raise ValueError("Incompatible resume: source, host, config, purpose or execution mode changed")
            dataset = read(directory / "maps.json")
            if core.digest(dataset) != manifest["maps_digest"]:
                raise ValueError("Map checkpoint changed")
        else:
            common, _ = core.load_algorithms()
            dataset = {"benchmark": core.materialize(config, common), "sanity": core.sanity_cases()}
            core.write_json(directory / "maps.json", dataset)
            manifest = {**signature, "run_id": run_id, "execution_schema": 2, "version": core.VERSION,
                        "config": config, "created_utc": core.now(), "sessions": [], "orders": core.ORDERS,
                        "maps_digest": core.digest(dataset), "outcome_storage":"a_reference_only_v1",
                        "case_order_offsets": {c["case_id"]: (1,4,5)[i%3] if config["repetitions"]==5 else 0
                                               for i,c in enumerate(dataset["benchmark"])}}
        session = uuid.uuid4().hex
        manifest["sessions"].append({"id": session, "started_utc": core.now()})
        manifest.update(status="running", problems=[], last_error=None)
        core.write_json(manifest_path, manifest)
        try:
            backup = None
            if backup_root:
                backup = Path(backup_root).resolve() / run_id / session
                backup.mkdir(parents=True, exist_ok=False)
                backup_wave(directory, backup, "inputs", [manifest_path, directory / "maps.json"])
            paths = directory / "inputs"
            paths.mkdir(exist_ok=True)
            for case in dataset["sanity"] + dataset["benchmark"]:
                if case.get("generation_error"):
                    raise ValueError(case["generation_error"])
                core.write_json(paths / (case["case_id"] + ".json"), case)
            stages = [("sanity", dataset["sanity"], 1), ("structural", dataset["benchmark"], workers),
                      ("timing", dataset["benchmark"], 1 if mode == "isolated" else workers)]
            if config["memory_pass"]:
                stages.append(("memory", dataset["benchmark"], workers))
            with awake():
                for stage, cases, active in stages:
                    jobs = [(directory, paths / (c["case_id"]+".json"), stage, config,
                             manifest["case_order_offsets"].get(c["case_id"], 0), session, mode, active)
                            for c in cases]
                    if backup is None:
                        dispatch(jobs, active)
                    else:
                        for index in range(0, len(jobs), active):
                            wave = jobs[index:index+active]
                            dispatch(wave, active)
                            files = (p for job in wave for p in
                                     (directory / "jobs" / job[1].stem).rglob("*"))
                            backup_wave(directory, backup, f"{stage}-{index:03}", files)
            temp = directory / "records.assembling"
            with temp.open("wb") as stream:
                for stage, cases, active in stages:
                    for case in cases:
                        folders = ["timing"] if stage=="timing" else [stage+"-"+m.replace("*","star") for m in core.METHODS]
                        for name in folders:
                            for row in accepted(directory/"jobs"/case["case_id"]/name):
                                stream.write(core.canonical(row)+b"\n")
            temp.replace(directory/"records.jsonl")
            manifest.update(status="completed", finished_utc=core.now())
            core.write_json(manifest_path, manifest)
            if not analyze(directory)["valid"]:
                raise RuntimeError("Final record matrix failed validation")
            if plots:
                from .basiccode_plot import plot
                plot(directory)
            if backup:
                backup_wave(directory, backup, "final", [p for p in directory.glob("*.*") if p.suffix in (".json", ".csv", ".jsonl")]
                            + list((directory / "figures").glob("*.*")))
        except BaseException as exc:
            manifest.update(status="interrupted" if isinstance(exc, KeyboardInterrupt) else "failed",
                            last_error=repr(exc), problems=[{"error":repr(exc)}])
            core.write_json(manifest_path, manifest)
            raise
    return directory
