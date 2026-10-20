"""상하좌우로 이동하는 전수 NBV. 실행: python minimal_nbv.py

실제 지도(truth)는 관측할 때만 사용하고, 계획은 관측 지도(known)로 계산한다.
"""

from collections import deque
from math import ceil, inf
from random import Random


# 0. 상수: 좌표는 (행, 열), 거리와 이동 비용은 칸 단위이다.
HEIGHT = 20
WIDTH = 20
OBSTACLE_RATE = 0.20
SENSOR_RANGE = 4.0
SEED = 42
MAX_MAP_ATTEMPTS = 1000
UNKNOWN, FREE, WALL = -1, 0, 1
MOVES = ((-1, 0), (0, -1), (0, 1), (1, 0))
STEP_COST = 1

# 한 번의 탐사에서 공유하는 전역 지도 상태이다.
# truth는 실제 지도이고, known은 에이전트가 현재까지 관측한 지도이다.
truth = None
known = None
NBVpath = []


# 1. 맵을 생성하고 빈칸에 에이전트를 배치한다.
def create_map():
    """빈칸들이 연결되고, 모든 벽이 빈칸에 인접한 맵만 생성한다.

    시야 반경이 1 이상이면 모든 칸을 관측할 수 있는 조건이다.
    """
    global truth, known, NBVpath
    NBVpath.clear() 
    if HEIGHT < 1 or WIDTH < 1 or not 0 <= OBSTACLE_RATE < 1:
        raise ValueError("맵 크기는 양수, 장애물 확률은 0 이상 1 미만이어야 합니다.")
    rng = Random(SEED)
    for _ in range(MAX_MAP_ATTEMPTS):
        truth = [[int(rng.random() < OBSTACLE_RATE) for _ in range(WIDTH)]
                 for _ in range(HEIGHT)]
        free_cells = [(r, c) for r in range(HEIGHT) for c in range(WIDTH)
                      if truth[r][c] == FREE]
        if not free_cells:
            continue
        robot = rng.choice(free_cells)
        distances, _ = shortest_paths(truth, robot)
        if len(distances) != len(free_cells):
            continue
        if any(truth[r][c] == WALL and not any(free_neighbors(truth, (r, c)))
               for r in range(HEIGHT) for c in range(WIDTH)):
            continue
        known = [[UNKNOWN] * WIDTH for _ in range(HEIGHT)]
        return truth, known, robot
    raise RuntimeError("전체를 관측할 수 있는 맵 생성 실패: 장애물 확률을 낮춰주세요.")


# 2. 가시성 기반 IG와 이동 비용을 하나의 비용 값으로 계산한다.
def free_neighbors(grid, position):
    """상하좌우 중 FREE인 이웃만 반환한다. UNKNOWN으로 이동하지 않는다."""
    r, c = position
    for dr, dc in MOVES:
        nr, nc = r + dr, c + dc
        if 0 <= nr < HEIGHT and 0 <= nc < WIDTH:
            if grid[nr][nc] == FREE:
                yield nr, nc


def shortest_paths(known, robot):
    """이동 비용이 모두 1이므로 BFS 한 번으로 모든 최단 경로를 구한다."""
    distances, parents = {robot: 0}, {}
    queue = deque([robot])
    while queue:
        current = queue.popleft()
        for neighbor in free_neighbors(known, current):
            if neighbor not in distances:
                distances[neighbor] = distances[current] + STEP_COST
                parents[neighbor] = current
                queue.append(neighbor)
    return distances, parents


def ray_cells(start, end):
    """직선이 닿는 모든 칸. 모서리 통과 시 양옆 칸도 포함한다(supercover)."""
    r, c = start
    dr, dc = abs(end[0] - r), abs(end[1] - c)
    sr = (end[0] > r) - (end[0] < r)
    sc = (end[1] > c) - (end[1] < c)
    row_crossing = col_crossing = 1
    cells = [start]
    while (r, c) != end:
        row_event = row_crossing * dc
        col_event = col_crossing * dr
        if row_event == col_event:
            cells.extend(sorted(((r + sr, c), (r, c + sc))))
        if row_event <= col_event:
            r += sr
            row_crossing += 2
        if col_event <= row_event:
            c += sc
            col_crossing += 2
        cells.append((r, c))
    return cells


def sensor_targets(origin):
    """360도 원형 시야 안에 있는 칸들을 반환한다."""
    r, c = origin
    radius = ceil(SENSOR_RANGE)
    for nr in range(max(0, r - radius), min(HEIGHT, r + radius + 1)):
        for nc in range(max(0, c - radius), min(WIDTH, c + radius + 1)):
            if (nr - r) ** 2 + (nc - c) ** 2 <= SENSOR_RANGE ** 2:
                yield nr, nc


def Information_Gain(x, y):
    """전역 known 지도에서 (x, y)의 가시적인 미탐색 셀 수를 계산한다."""
    if known is None:
        raise RuntimeError("known 지도가 아직 생성되지 않았습니다.")

    gain = 0
    origin = (x, y)

    for target in sensor_targets(origin):
        row, col = target
        if known[row][col] != UNKNOWN:
            continue

        ray = ray_cells(origin, target)
        if all(known[r][c] != WALL for r, c in ray[1:-1]):
            gain += 1

    return gain


def nbv_cost(known, candidate, distance):
    """비용 = 최단 이동거리 / 예상 IG. 작은 값이 좋고, IG=0이면 무한대.

    IG는 후보 시야의 미확인 칸 수이다. 알려진 벽은 시야를 막으며,
    미확인 칸은 투명하다고 가정한다. 실제 지도는 참조하지 않는다.
    """
    gain = 0
    for target in sensor_targets(candidate):
        if known[target[0]][target[1]] == UNKNOWN:
            if all(known[r][c] != WALL for r, c in ray_cells(candidate, target)[1:-1]):
                gain += 1
    return distance / gain if gain else inf


# 3. 이동 가능한 모든 후보를 빠짐없이 평가한다.
def evaluate_candidates(known, robot):
    """현재 위치를 제외한, 도달 가능한 모든 알려진 빈칸이 후보이다."""
    distances, parents = shortest_paths(known, robot)
    costs = {candidate: nbv_cost(known, candidate, distance)
             for candidate, distance in distances.items() if candidate != robot}
    return costs, parents


# 4. 최적 NBV까지 한 칸씩 이동하면서 비용과 관측 지도를 갱신한다.
def observe(truth, known, robot):
    """각 광선에서 첫 벽까지 밝힌다. 첫 벽 자체도 관측된다."""
    for target in sensor_targets(robot):
        for r, c in ray_cells(robot, target):
            known[r][c] = truth[r][c]
            if truth[r][c] == WALL:
                break


def move_to_nbv(truth, known, robot, target, parents, total_cost):
    """BFS 경로를 따라 이동한다. 이동 도중 매 칸에서 관측한다."""
    path = [target]
    while path[-1] != robot:
        path.append(parents[path[-1]])
    for robot in reversed(path[:-1]):
        total_cost += STEP_COST
        observe(truth, known, robot)
        if not any(UNKNOWN in row for row in known):
            break
    return robot, total_cost


# 5. 모든 칸이 확인될 때까지 반복한다.
def explore(truth, known, robot):
    """반환값: 최종 위치, 누적 이동 비용, NBV 선택 횟수. known은 직접 갱신된다."""
    global NBVpath
    NBVpath.clear()
    if SENSOR_RANGE < 1:
        raise ValueError("전체 지도 관측을 위해 시야 반경은 1 이상이어야 합니다.")
    total_cost = rounds = 0
    observe(truth, known, robot)
    while any(UNKNOWN in row for row in known):
        costs, parents = evaluate_candidates(known, robot)
        # 동률이면 (행, 열)이 작은 후보를 고른다.
        target = min(costs, key=lambda p: (costs[p], p)) if costs else None
        if target is None or costs[target] == inf:
            raise RuntimeError("미확인 칸이 남았지만 관측 가능한 NBV 후보가 없습니다.")
        NBVpath.append(target)
        robot, total_cost = move_to_nbv(
            truth, known, robot, target, parents, total_cost)
        rounds += 1
    return robot, total_cost, rounds


if __name__ == "__main__":
    truth, known, start = create_map()
    robot, total_cost, rounds = explore(truth, known, start)
    print(f"start={start}, end={robot}, NBV selections={rounds}, total cost={total_cost}")
    symbols = {UNKNOWN: "?", FREE: ".", WALL: "#"}
    for r, row in enumerate(known):
        print("".join("A" if (r, c) == robot else symbols[cell]
                      for c, cell in enumerate(row)))
    print("All cells observed.")
    print(NBVpath)
