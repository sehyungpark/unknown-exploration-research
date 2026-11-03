"""Exclusive coordinator and immutable attempt checkpoints."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
from .basiccode_runner import digest, write_json


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


@contextmanager
def coordinator_lock(directory):
    with (directory / "coordinator.lock").open("a+b") as stream:
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def accepted(folder):
    marker = folder / "accepted.json"
    if not marker.exists():
        return None
    index = read(marker)
    rows = []
    for name, checksum in index["records"]:
        row = read(folder / index["attempt"] / name)
        if digest(row) != checksum:
            raise ValueError(f"Checkpoint checksum mismatch: {folder}/{name}")
        rows.append(row)
    return rows


def accept(folder, attempt, rows):
    write_json(folder / "accepted.json", {"attempt": attempt.name,
               "records": [(f"{i}.json", digest(row)) for i, row in enumerate(rows)]})
