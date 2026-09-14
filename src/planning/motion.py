"""Exact 8-neighbor Dijkstra motion on currently known FREE cells."""

from dataclasses import dataclass
from heapq import heappop, heappush
from math import sqrt

from src.mapping import BeliefGrid
from src.utils import Coord

ORTHOGONAL_COST = 1.0
DIAGONAL_COST = sqrt(2.0)

_OFFSETS: tuple[tuple[int, int], ...] = tuple(
    sorted(
        (row_delta, col_delta)
        for row_delta in (-1, 0, 1)
        for col_delta in (-1, 0, 1)
        if (row_delta, col_delta) != (0, 0)
    )
)


def legal_neighbors(belief: BeliefGrid, coord: Coord) -> tuple[tuple[Coord, float], ...]:
    """Return deterministic legal moves, prohibiting diagonal corner cutting."""

    if not belief.known_free(coord):
        return ()
    row, col = coord
    neighbors: list[tuple[Coord, float]] = []
    for row_delta, col_delta in _OFFSETS:
        target = row + row_delta, col + col_delta
        if not belief.known_free(target):
            continue
        diagonal = row_delta != 0 and col_delta != 0
        if diagonal:
            side_row = row + row_delta, col
            side_col = row, col + col_delta
            if not (belief.known_free(side_row) and belief.known_free(side_col)):
                continue
        neighbors.append((target, DIAGONAL_COST if diagonal else ORTHOGONAL_COST))
    return tuple(neighbors)


@dataclass(frozen=True, slots=True)
class DijkstraResult:
    source: Coord
    distances: dict[Coord, float]
    predecessors: dict[Coord, Coord]

    def path_to(self, target: Coord) -> tuple[Coord, ...]:
        if target not in self.distances:
            raise ValueError(f"target is unreachable: {target}")
        reverse_path = [target]
        while reverse_path[-1] != self.source:
            reverse_path.append(self.predecessors[reverse_path[-1]])
        reverse_path.reverse()
        return tuple(reverse_path)


def dijkstra(belief: BeliefGrid, source: Coord) -> DijkstraResult:
    """Run one exact single-source Dijkstra search on known FREE cells."""

    if not belief.known_free(source):
        raise ValueError("Dijkstra source must be known FREE")

    distances: dict[Coord, float] = {source: 0.0}
    predecessors: dict[Coord, Coord] = {}
    queue: list[tuple[float, int, int]] = [(0.0, source[0], source[1])]

    while queue:
        distance, row, col = heappop(queue)
        current = row, col
        if distance != distances[current]:
            continue
        for neighbor, edge_cost in legal_neighbors(belief, current):
            new_distance = distance + edge_cost
            old_distance = distances.get(neighbor)
            if old_distance is None or new_distance < old_distance:
                distances[neighbor] = new_distance
                predecessors[neighbor] = current
                heappush(queue, (new_distance, neighbor[0], neighbor[1]))
            elif new_distance == old_distance and current < predecessors[neighbor]:
                predecessors[neighbor] = current

    return DijkstraResult(source, distances, predecessors)
