"""Semantics-preserving forwarding instrumentation for Experiment 2."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
import importlib
import time
from typing import Any, Generic, TypeVar, overload

from src.mapping import BeliefGrid
from src.planning.change_aware_cache import ChangeAwareGainCache
from src.utils import Coord


_exhaustive = importlib.import_module("src.planning.exhaustive_nbv")
_stale = importlib.import_module("src.planning.stale_scalar_lazy_nbv")
_change = importlib.import_module("src.planning.change_aware_lazy_nbv")
_integration = importlib.import_module("src.planning.change_aware_integration")
_visibility = importlib.import_module("src.sensing.visibility")

_CANONICAL_VISIBILITY = _visibility.optimistic_visible_unknown_cells
_CANONICAL_SUPERCOVER = _visibility.supercover_line
_CANONICAL_DIJKSTRA = {
    _exhaustive: _exhaustive.dijkstra,
    _stale: _stale.dijkstra,
    _change: _change.dijkstra,
}
_CANONICAL_SYNCHRONIZE = _change.synchronize_revelations
_CANONICAL_INSTALL = ChangeAwareGainCache.install_exact

_T = TypeVar("_T")


@dataclass(slots=True)
class VisibilityWork:
    exact_visibility_call_count: int = 0
    visibility_ray_count: int = 0
    visibility_supercover_cell_count: int = 0
    visibility_interior_probe_count: int = 0


class _ProbeSlice(Iterator[Coord]):
    def __init__(self, cells: Sequence[Coord], work: VisibilityWork) -> None:
        self._iterator = iter(cells)
        self._work = work

    def __iter__(self) -> _ProbeSlice:
        return self

    def __next__(self) -> Coord:
        value = next(self._iterator)
        self._work.visibility_interior_probe_count += 1
        return value


class _LineProxy(Sequence[Coord]):
    """Preserve line sequence semantics while lazily counting interior probes."""

    def __init__(self, line: tuple[Coord, ...], work: VisibilityWork) -> None:
        self._line = line
        self._work = work

    def __len__(self) -> int:
        return len(self._line)

    @overload
    def __getitem__(self, index: int) -> Coord: ...

    @overload
    def __getitem__(self, index: slice) -> Sequence[Coord]: ...

    def __getitem__(self, index: int | slice) -> Coord | Sequence[Coord]:
        if isinstance(index, slice) and index == slice(1, -1, None):
            return _ProbeSlice(self._line[1:-1], self._work)
        return self._line[index]


class VisibilityWorkContext(AbstractContextManager[VisibilityWork]):
    """Patch only runtime call sites and forward exactly once to canonical code."""

    def __init__(self) -> None:
        self.work = VisibilityWork()
        self._saved: list[tuple[Any, str, Any]] = []
        self._active_exact_calls = 0

    def _set(self, owner: Any, name: str, value: Any) -> None:
        self._saved.append((owner, name, getattr(owner, name)))
        setattr(owner, name, value)

    def __enter__(self) -> VisibilityWork:
        def measured_visibility(
            belief: BeliefGrid,
            origin: Coord,
            sensor_range: float = 8,
        ) -> frozenset[Coord]:
            self.work.exact_visibility_call_count += 1
            self._active_exact_calls += 1
            try:
                return _CANONICAL_VISIBILITY(belief, origin, sensor_range)
            finally:
                self._active_exact_calls -= 1

        def measured_supercover(start: Coord, end: Coord) -> Sequence[Coord]:
            line = _CANONICAL_SUPERCOVER(start, end)
            if self._active_exact_calls == 0:
                return line
            self.work.visibility_ray_count += 1
            self.work.visibility_supercover_cell_count += len(line)
            return _LineProxy(line, self.work)

        for module in (_exhaustive, _stale, _integration):
            self._set(
                module,
                "optimistic_visible_unknown_cells",
                measured_visibility,
            )
        self._set(_visibility, "supercover_line", measured_supercover)
        return self.work

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        while self._saved:
            owner, name, original = self._saved.pop()
            setattr(owner, name, original)
        return None


def visibility_work() -> VisibilityWorkContext:
    return VisibilityWorkContext()


def require_exact_call_match(work: VisibilityWork, exact_evaluations: int) -> None:
    if work.exact_visibility_call_count != exact_evaluations:
        raise RuntimeError(
            "instrumentation mismatch: exact visibility calls "
            f"{work.exact_visibility_call_count} != planner exact evaluations "
            f"{exact_evaluations}"
        )


@dataclass(frozen=True, slots=True)
class DecompositionMeasurement(Generic[_T]):
    result: _T
    total_time_ns: int
    distance_time_ns: int
    visibility_time_ns: int
    maintenance_time_ns: int
    other_time_ns: int
    decomposition_residual_ns: int


class DecompositionContext(AbstractContextManager["DecompositionContext"]):
    """Forwarding timers for non-overlapping canonical planner components."""

    def __init__(self, clock_ns: Callable[[], int] = time.perf_counter_ns) -> None:
        self._clock_ns = clock_ns
        self._saved: list[tuple[Any, str, Any]] = []
        self.distance_time_ns = 0
        self.visibility_time_ns = 0
        self.maintenance_time_ns = 0

    def _set(self, owner: Any, name: str, value: Any) -> None:
        self._saved.append((owner, name, getattr(owner, name)))
        setattr(owner, name, value)

    def _timed(self, bucket: str, function: Callable[..., _T]) -> Callable[..., _T]:
        def wrapper(*args: Any, **kwargs: Any) -> _T:
            start = self._clock_ns()
            try:
                return function(*args, **kwargs)
            finally:
                elapsed = self._clock_ns() - start
                setattr(self, bucket, getattr(self, bucket) + elapsed)

        return wrapper

    def __enter__(self) -> DecompositionContext:
        for module, canonical in _CANONICAL_DIJKSTRA.items():
            self._set(module, "dijkstra", self._timed("distance_time_ns", canonical))
        for module in (_exhaustive, _stale, _integration):
            self._set(
                module,
                "optimistic_visible_unknown_cells",
                self._timed("visibility_time_ns", _CANONICAL_VISIBILITY),
            )
        self._set(
            _change,
            "synchronize_revelations",
            self._timed("maintenance_time_ns", _CANONICAL_SYNCHRONIZE),
        )
        self._set(
            ChangeAwareGainCache,
            "install_exact",
            self._timed("maintenance_time_ns", _CANONICAL_INSTALL),
        )
        return self

    def measure(self, planner_call: Callable[[], _T]) -> DecompositionMeasurement[_T]:
        start = self._clock_ns()
        result = planner_call()
        total = self._clock_ns() - start
        components = (
            self.distance_time_ns
            + self.visibility_time_ns
            + self.maintenance_time_ns
        )
        other = total - components
        if other < 0:
            raise RuntimeError(
                "decomposition components exceed total planner time; "
                "timing intervals overlap or clock is invalid"
            )
        return DecompositionMeasurement(
            result=result,
            total_time_ns=total,
            distance_time_ns=self.distance_time_ns,
            visibility_time_ns=self.visibility_time_ns,
            maintenance_time_ns=self.maintenance_time_ns,
            other_time_ns=other,
            decomposition_residual_ns=0,
        )

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        while self._saved:
            owner, name, original = self._saved.pop()
            setattr(owner, name, original)
        return None


def decomposition(
    clock_ns: Callable[[], int] = time.perf_counter_ns,
) -> DecompositionContext:
    return DecompositionContext(clock_ns)


__all__ = [
    "DecompositionContext",
    "DecompositionMeasurement",
    "VisibilityWork",
    "decomposition",
    "require_exact_call_match",
    "visibility_work",
]
