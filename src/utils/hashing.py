"""Canonical text encodings and SHA-256 hashes for Experiment 0 grids."""

from __future__ import annotations

from hashlib import sha256
from typing import TYPE_CHECKING

from .types import BeliefState, TruthState

if TYPE_CHECKING:
    from src.environment import GroundTruthGrid
    from src.mapping import BeliefGrid


def canonical_ground_truth_text(grid: GroundTruthGrid) -> str:
    """Encode ground truth row-major as ./# rows, each terminated by LF."""

    symbols = {TruthState.FREE: ".", TruthState.OCCUPIED: "#"}
    return "".join(
        "".join(symbols[grid.state((row, col))] for col in range(grid.width)) + "\n"
        for row in range(grid.height)
    )


def canonical_belief_text(belief: BeliefGrid) -> str:
    """Encode a belief row-major as ?/.# rows, each terminated by LF."""

    symbols = {
        BeliefState.UNKNOWN: "?",
        BeliefState.FREE: ".",
        BeliefState.OCCUPIED: "#",
    }
    return "".join(
        "".join(symbols[belief.state((row, col))] for col in range(belief.width))
        + "\n"
        for row in range(belief.height)
    )


def ground_truth_hash(grid: GroundTruthGrid) -> str:
    return sha256(canonical_ground_truth_text(grid).encode("utf-8")).hexdigest()


def belief_hash(belief: BeliefGrid) -> str:
    return sha256(canonical_belief_text(belief).encode("utf-8")).hexdigest()
