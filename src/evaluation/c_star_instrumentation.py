"""Separated timing helpers for Algorithm C* research instrumentation.

Core planner timing and debug/audit timing are measured in distinct calls. The
module deliberately provides no "total minus audit" subtraction path.
"""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Callable, Generic, TypeVar


_T = TypeVar("_T")


@dataclass(frozen=True, slots=True)
class CoreTimingMeasurement(Generic[_T]):
    result: _T
    core_time_ns: int


@dataclass(frozen=True, slots=True)
class AuditTimingMeasurement(Generic[_T]):
    result: _T
    audit_time_ns: int


def measure_c_star_core(
    planner_call: Callable[[], _T],
    *,
    clock_ns: Callable[[], int] = time.perf_counter_ns,
) -> CoreTimingMeasurement[_T]:
    """Measure one production-required C* operation only."""

    start = clock_ns()
    result = planner_call()
    return CoreTimingMeasurement(
        result=result,
        core_time_ns=clock_ns() - start,
    )


def measure_c_star_audit(
    audit_call: Callable[[], _T],
    *,
    clock_ns: Callable[[], int] = time.perf_counter_ns,
) -> AuditTimingMeasurement[_T]:
    """Measure a separate debug/audit operation.

    Call this on a separate validation pass when benchmarking. Do not subtract
    this value from core timing; it was never included there.
    """

    start = clock_ns()
    result = audit_call()
    return AuditTimingMeasurement(
        result=result,
        audit_time_ns=clock_ns() - start,
    )


__all__ = [
    "AuditTimingMeasurement",
    "CoreTimingMeasurement",
    "measure_c_star_audit",
    "measure_c_star_core",
]
