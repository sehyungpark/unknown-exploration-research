"""Compact append-only result writer for Experiment 2."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Mapping

from .experiment_2_analysis import build_summary

EXPERIMENT_NAME = "Experiment 2 — C* Efficiency and Scaling Evaluation"
EXPERIMENT_VERSION = "experiment-2-runner-v1"
DATASET_VERSION = "experiment-2-cstar-efficiency-v1"
METHODS = ("A", "B", "C", "C*")

# Six timed repetitions are retained exactly as in Experiment 1.  Because C*
# adds a fourth method, the within-repetition order must be extended.  This
# schedule is frozen before any Experiment 2 planner execution.
TIMING_ORDERS = (
    ("A", "B", "C", "C*"),
    ("B", "C", "C*", "A"),
    ("C", "C*", "A", "B"),
    ("C*", "A", "B", "C"),
    ("A", "C*", "C", "B"),
    ("C", "B", "A", "C*"),
)
WARMUP_ORDER = ("A", "B", "C", "C*")

_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")


def utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json_text(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ) + "\n"


def _safe_id(value: str, label: str) -> None:
    if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
        raise ValueError(f"{label} contains unsafe path characters")


class Experiment2InvocationWriter:
    """Write one immutable compact formal Experiment 2 invocation."""

    STREAMS = {
        "structural": "structural.jsonl",
        "timing": "timing_repetitions.jsonl",
        "decomposition": "decomposition.jsonl",
        "memory": "memory.jsonl",
        "audit": "audit.jsonl",
    }

    def __init__(
        self,
        output_root: str | Path,
        invocation_id: str,
        manifest: Mapping[str, Any],
    ) -> None:
        _safe_id(invocation_id, "invocation_id")
        self.invocation_id = invocation_id
        self.directory = Path(output_root) / "runs" / invocation_id
        self.directory.mkdir(parents=True, exist_ok=False)
        self._manifest = dict(manifest)
        self._manifest["status"] = "RUNNING"
        self._manifest["started_at_utc"] = utc_now_text()
        self._manifest["completed_at_utc"] = None
        (self.directory / "manifest.json").write_text(
            canonical_json_text(self._manifest), encoding="utf-8"
        )
        for filename in self.STREAMS.values():
            (self.directory / filename).write_text("", encoding="utf-8")
        self._finalized = False

    def append(self, kind: str, record: Mapping[str, Any]) -> None:
        if self._finalized:
            raise RuntimeError("cannot append after finalization")
        if kind not in self.STREAMS:
            raise ValueError(f"unknown stream: {kind}")
        payload = dict(record)
        if payload.get("invocation_id") != self.invocation_id:
            raise ValueError("record invocation ID mismatch")
        if payload.get("method") is not None and payload["method"] not in METHODS:
            raise ValueError("invalid method")
        path = self.directory / self.STREAMS[kind]
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json_text(payload))

    def _read(self, kind: str) -> list[dict[str, Any]]:
        result = []
        with (self.directory / self.STREAMS[kind]).open(
            "r", encoding="utf-8"
        ) as handle:
            for line in handle:
                if line.strip():
                    result.append(json.loads(line))
        return result

    def finalize(self, status: str) -> dict[str, Any]:
        if self._finalized:
            raise RuntimeError("invocation already finalized")
        if status not in {"PASS", "FAILED"}:
            raise ValueError("status must be PASS or FAILED")
        structural = self._read("structural")
        timing = self._read("timing")
        memory = self._read("memory")
        audit = self._read("audit")
        summary = build_summary(structural, timing, memory, audit)
        (self.directory / "summary.json").write_text(
            canonical_json_text(summary), encoding="utf-8"
        )
        self._manifest["status"] = status
        self._manifest["completed_at_utc"] = utc_now_text()
        temp = self.directory / ".manifest.tmp"
        temp.write_text(canonical_json_text(self._manifest), encoding="utf-8")
        temp.replace(self.directory / "manifest.json")
        self._finalized = True
        return summary

    def write_failure(self, failure: Mapping[str, Any]) -> None:
        path = self.directory / "failure.json"
        if path.exists():
            raise FileExistsError("failure evidence already exists")
        path.write_text(canonical_json_text(dict(failure)), encoding="utf-8")


__all__ = [
    "DATASET_VERSION", "EXPERIMENT_NAME", "EXPERIMENT_VERSION",
    "Experiment2InvocationWriter", "METHODS", "TIMING_ORDERS",
    "WARMUP_ORDER", "canonical_json_text", "utc_now_text",
]
