"""Deterministic grid sensing and visibility."""

from .supercover import supercover_line
from .visibility import (
    cells_within_range,
    optimistic_visible_unknown_cells,
    physical_scan,
    physical_visible_cells,
)

__all__ = [
    "cells_within_range",
    "optimistic_visible_unknown_cells",
    "physical_scan",
    "physical_visible_cells",
    "supercover_line",
]
