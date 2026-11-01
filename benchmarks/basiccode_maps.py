"""Constructive shared maps with exact occupancy, connected FREE, observable WALL.

This deliberately defines a structured map family, not an IID Bernoulli sample.
The scaffold is independent of planner behavior and shared by all algorithms.
"""
from random import Random

GENERATOR = "connected_dominating_v1"


def connected_map(size, density, seed):
    """Return (truth, start, metadata) in O(size**2) work and memory.

    Full free rows separated by at most two other rows dominate the grid.
    One free spine joins all rows. Every remaining cell touches that connected
    scaffold, so making any subset of those cells WALL preserves both required
    invariants. Rotation/reflections and obstacle order depend only on seed.
    """
    if type(size) is not int or size < 5:
        raise ValueError("connected_dominating_v1 requires side length >= 5")
    if not 0 <= density <= 0.5:
        raise ValueError("connected_dominating_v1 supports densities in [0, 0.5]")
    rng = Random(seed)
    rows = set(range(1, size, 3))
    if size - 1 - max(rows) > 1:
        rows.add(size - 2)
    spine = rng.randrange(size)
    transpose, flip_row, flip_col = (bool(rng.getrandbits(1)) for _ in range(3))

    def transformed(row, col):
        if transpose:
            row, col = col, row
        if flip_row:
            row = size - 1 - row
        if flip_col:
            col = size - 1 - col
        return row, col

    eligible = [row * size + col for row in range(size) for col in range(size)
                if row not in rows and col != spine]
    wall_count = round(size * size * density)
    if wall_count > len(eligible):
        raise ValueError("Requested occupancy exceeds this scaffold's capacity")
    # Same seed/scaffold/order across densities makes the wall sets nested.
    rng.shuffle(eligible)
    truth = [[0] * size for _ in range(size)]
    for index in eligible[:wall_count]:
        row, col = transformed(*divmod(index, size))
        truth[row][col] = 1
    # Choose the same seed-defined point on the guaranteed-free scaffold across
    # densities. No start is selected after inspecting planner performance.
    scaffold_row = rng.choice(sorted(rows))
    start = transformed(scaffold_row, rng.randrange(size))
    metadata = {"generator": GENERATOR, "requested_density": density,
                "realized_density": wall_count / (size * size),
                "wall_count": wall_count, "free_count": size * size - wall_count,
                "scaffold_free_count": size * size - len(eligible),
                "base_free_rows": sorted(rows), "base_spine_column": spine,
                "transpose": transpose, "flip_row": flip_row, "flip_col": flip_col,
                "start_rule": "seed-selected scaffold cell; identical across densities"}
    return truth, start, metadata
