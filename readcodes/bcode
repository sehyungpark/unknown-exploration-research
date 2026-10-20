"""상하좌우로 이동하는 stale-lazy-gain NBV.

실행: python stale_lazy_gain.py

후보 평가는 현재 관측 지도 known만 사용한다.
실제 지도 truth는 지도 생성 조건 검사와 실제 관측에 사용한다.
캐시는 정적 환경, UNKNOWN에서 알려진 상태로만 바뀌는 지도, 고정 센서를 전제로 한다.
"""

from collections import deque
from math import ceil
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
SCORE_EPSILON = 1e-9

# NBVpath는 선택한 목표들의 기록이다. 매 칸의 실제 이동 경로와는 다르다.
truth = None
known = None
NBVpath = []


# 1. 지도 생성
# 역할: 연결된 빈칸들과, 빈칸에 인접한 벽들로 이루어진 지도를 생성한다.
# 입력: 인자 없이 지도 크기, 장애물 확률, 시드 등의 전역 상수를 사용한다.
# 과정: 무작위 지도 생성 → 빈칸 연결 검사 → 벽의 빈칸 인접 검사.
# 반환: (실제 지도 truth, 모두 UNKNOWN인 관측 지도 known, 시작 좌표 robot).
# 부수 효과: 전역 지도를 설정하고 NBVpath를 비운다.
def create_map():
    """시야 반경이 1 이상일 때 전체 셀 관측이 가능한 조건의 지도를 만든다."""
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


# 2. 이동과 가시성
# 역할: 현재 위치에서 상하좌우로 이동 가능한 빈칸만 찾는다.
# 입력: 검사할 지도 grid, 현재 좌표 position.
# 과정: 전역 지도 경계 안에 있고 FREE인 이웃만 남긴다.
# 산출: 이동 가능한 이웃 좌표를 yield로 하나씩 전달한다.
def free_neighbors(grid, position):
    """UNKNOWN과 WALL로는 이동하지 않는다."""
    r, c = position
    for dr, dc in MOVES:
        nr, nc = r + dr, c + dc
        if 0 <= nr < HEIGHT and 0 <= nc < WIDTH:
            if grid[nr][nc] == FREE:
                yield nr, nc


# 역할: BFS로 로봇에서 도달 가능한 모든 빈칸의 최단 거리를 계산한다.
# 입력: 이동에 사용할 지도 known, FREE 셀인 로봇 좌표 robot.
# 과정: 가까운 셀부터 방문하며 거리와 바로 이전 셀을 기록한다.
# 반환: distances={좌표: 최단 거리}, parents={좌표: 바로 이전 좌표}.
# 참고: 모든 이동 비용이 1이므로 BFS를 사용하며, 매 계획 시점에 새로 계산한다.
def shortest_paths(known, robot):
    """시작점의 거리는 0이며, 도달할 수 없는 셀은 사전에 포함하지 않는다."""
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


# 역할: 두 셀 중심 사이의 직선이 닿는 모든 격자 셀을 구한다.
# 입력: 시작 좌표 start, 끝 좌표 end.
# 과정: 행/열 경계 교차 순서를 비교한다. 모서리를 통과하면 양옆 셀도 포함한다.
# 반환: 시작점과 끝점을 포함한 좌표 목록. 벽에 의한 가림은 호출자가 검사한다.
def ray_cells(start, end):
    """모서리 통과 시 양옆 칸을 좌표순으로 포함하는 supercover 선분."""
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


# 역할: 원형 센서 범위에 속하는 지도 셀을 열거한다.
# 입력: 센서 위치 origin. 반경과 지도 크기는 전역 상수를 사용한다.
# 과정: 지도 안의 셀 중 유클리드 거리 제곱이 반경 제곱 이하인 셀을 남긴다.
# 산출: 대상 좌표를 yield로 전달한다. 이 단계에서는 장애물 가림을 검사하지 않는다.
def sensor_targets(origin):
    """360도 원형 시야 안에 있는 칸들을 반환한다."""
    r, c = origin
    radius = ceil(SENSOR_RANGE)
    for nr in range(max(0, r - radius), min(HEIGHT, r + radius + 1)):
        for nc in range(max(0, c - radius), min(WIDTH, c + radius + 1)):
            if (nr - r) ** 2 + (nc - c) ** 2 <= SENSOR_RANGE ** 2:
                yield nr, nc


# 역할: 현재 관측 지도에서 후보의 정보 이득을 정확히 계산한다.
# 입력: 후보의 행 x, 열 y, 관측 지도 grid. 생략하면 전역 known을 사용한다.
# 과정: 범위 안의 UNKNOWN 셀마다 시선 중간에 알려진 WALL이 있는지 검사한다.
# 반환: 알려진 벽에 가리지 않는 UNKNOWN 셀 수.
# 참고: UNKNOWN은 시야를 막지 않는다고 가정한다. truth는 참조하지 않는다.
def Information_Gain(x, y, grid=None):
    """현재 지도의 낙관적 가시성 정의에 따른 정보 이득."""
    if grid is None:
        grid = known
    if grid is None:
        raise RuntimeError("known 지도가 아직 생성되지 않았습니다.")

    gain = 0
    origin = (x, y)
    for target in sensor_targets(origin):
        row, col = target
        if grid[row][col] != UNKNOWN:
            continue
        ray = ray_cells(origin, target)
        if all(grid[r][c] != WALL for r, c in ray[1:-1]):
            gain += 1
    return gain


# 3. 점수, 순위, 정확 평가
# 역할: 정보 이득을 이동 거리로 나누어 비교용 점수를 만든다.
# 입력: 정보 이득 gain, 현재 최단 거리 distance.
# 반환: gain / (distance + 1e-9). 큰 값이 좋고, gain이 0이면 점수도 0이다.
def nbv_score(gain, distance):
    """정확 이득과 이득 상한 모두 같은 점수식을 사용한다."""
    return gain / (distance + SCORE_EPSILON)


# 역할: 점수, 이득, 거리, 좌표를 하나의 비교 키로 만든다.
# 입력: 후보 좌표 candidate, (score, gain, distance) 튜플 evaluation.
# 반환: (-score, -gain, distance, row, col). 작은 키가 좋은 후보이다.
# 과정: 큰 점수 → 큰 이득 → 짧은 거리 → 작은 행 → 작은 열 순서를 적용한다.
def candidate_rank(candidate, evaluation):
    """동점 판단에 별도의 허용 오차를 사용하지 않는다."""
    score, gain, distance = evaluation
    row, col = candidate
    return (-score, -gain, distance, row, col)


# 역할: 이번 계획 시점에 정확히 평가한 후보 중 최선을 찾는다.
# 입력: evaluations={좌표: (현재 점수, 현재 이득, 현재 거리)}.
# 반환: 최선 후보 좌표. 사전이 비어 있으면 None.
# 참고: 이 함수의 결과만으로 선택을 확정하지 않고, 남은 후보의 상한도 비교한다.
def choose_best_candidate(evaluations):
    """정확 평가된 후보들의 순위를 비교한다."""
    return min(
        evaluations,
        key=lambda candidate: candidate_rank(candidate, evaluations[candidate]),
    ) if evaluations else None


# 역할: 후보 하나의 현재 정보 이득을 계산하고 캐시를 갱신한다.
# 입력: 현재 관측 지도, 후보 좌표, 현재 거리, 탐사 동안 유지할 캐시 사전.
# 반환: (현재 점수, 현재 이득, 현재 거리).
# 부수 효과: cached_gains[candidate]를 마지막 정확 이득 숫자로 덮어쓴다.
# 참고: 정적 환경과 단조로운 지도 갱신에서는 현재 이득이 과거 이득보다 클 수 없다.
def exact_evaluate(known, candidate, distance, cached_gains):
    """가시 셀 집합, 과거 점수, 과거 거리는 캐시에 저장하지 않는다."""
    gain = Information_Gain(*candidate, grid=known)
    old_gain = cached_gains.get(candidate)
    if old_gain is not None and gain > old_gain:
        raise RuntimeError(
            f"후보 {candidate}의 현재 이득 {gain}이 캐시 상한 {old_gain}보다 큽니다. "
            "환경·센서 변경 또는 다른 탐사의 캐시 재사용 여부를 확인하세요."
        )
    cached_gains[candidate] = gain
    return nbv_score(gain, distance), gain, distance


# 4. stale-lazy-gain 후보 선택
# 역할: 과거 이득을 상한으로 활용하여 필요한 후보만 정확히 재평가한다.
# 입력: 관측 지도 known, 로봇 좌표 robot, 탐사 동안 공유하는 cached_gains 사전.
# 과정: 현재 BFS → 신규 후보 전부 정확 평가 → 기존 후보의 상한 순위 비교 →
#       필요할 때 가장 유망한 기존 후보 재평가 → 최적임이 확인되면 선택 확정.
# 반환: (선택 좌표 또는 None, 이번에 정확 평가한 후보 사전 exact, BFS 부모 사전).
# None의 의미: 후보가 없거나 모든 후보의 현재 이득이 0임이 상한으로 확인됨.
# 주의: None은 전체 셀 관측 완료를 의미하지 않는다. 종료 판단은 explore()가 한다.
def evaluate_candidates(known, robot, cached_gains):
    """캐시와 별개로 exact는 호출마다 비워 현재 평가 결과만 보관한다."""
    distances, parents = shortest_paths(known, robot)
    candidates = tuple(sorted(candidate for candidate in distances if candidate != robot))
    exact = {}
    if not candidates:
        return None, exact, parents

    # 캐시가 없는 후보는 상한 숫자가 없으므로 모두 정확히 평가한다.
    # 따라서 캐시가 빈 첫 계획 시점에는 모든 후보를 정확히 평가한다.
    for candidate in candidates:
        if candidate not in cached_gains:
            exact[candidate] = exact_evaluate(
                known, candidate, distances[candidate], cached_gains
            )

    remaining = set(candidates) - set(exact)

    # 역할: 미평가 후보가 가질 수 있는 최상의 순위를 구한다.
    # 입력: candidate. 바깥 함수의 cached_gains와 현재 distances를 읽는다.
    # 반환: 캐시 이득과 현재 거리로 계산한 상한의 비교 키.
    # 참고: 가시성 계산이나 캐시 갱신을 수행하지 않는다.
    def upper_rank(candidate):
        upper_gain = cached_gains[candidate]
        distance = distances[candidate]
        upper_score = nbv_score(upper_gain, distance)
        return candidate_rank(candidate, (upper_score, upper_gain, distance))

    while True:
        # 모든 후보를 확인한다. 정확 평가한 후보의 캐시는 현재 이득이며,
        # 나머지 캐시는 현재 이득의 상한이다. 전부 0이면 양의 이득은 불가능하다.
        if all(cached_gains[candidate] == 0 for candidate in candidates):
            return None, exact, parents

        best_exact = choose_best_candidate(exact)
        if not remaining:
            return best_exact, exact, parents

        # 전체 동점 규칙까지 적용한 상한 순위가 가장 좋은 후보를 찾는다.
        next_candidate = min(remaining, key=upper_rank)

        # 나머지 중 가장 좋은 상한을 이기면 나머지 모든 상한도 이긴다.
        # 반드시 현재 시점에 정확히 평가한 후보만 최종 선택한다.
        if best_exact is not None:
            best_key = candidate_rank(best_exact, exact[best_exact])
            if best_key < upper_rank(next_candidate):
                return best_exact, exact, parents

        # 아직 선택을 확정할 수 없으므로 가장 유망한 미평가 후보를 재평가한다.
        # 기존 후보를 이번 호출에서 중복 평가하지 않도록 remaining에서 제거한다.
        remaining.remove(next_candidate)
        exact[next_candidate] = exact_evaluate(
            known, next_candidate, distances[next_candidate], cached_gains
        )


# 5. 관측과 실제 이동
# 역할: 현재 위치의 실제 센서 관측으로 known을 갱신한다.
# 입력: 실제 지도 truth, 관측 지도 known, 로봇 좌표 robot.
# 과정: 센서 범위의 광선을 따라 truth를 읽고 첫 벽까지 알려진 상태로 바꾼다.
# 반환: None. known을 직접 수정하며 첫 벽 자체도 관측한다.
# 참고: 이 함수에서는 이득 캐시를 차감하거나 갱신하지 않는다.
def observe(truth, known, robot):
    """UNKNOWN은 실제 관측된 FREE 또는 WALL로만 바뀐다."""
    for target in sensor_targets(robot):
        for r, c in ray_cells(robot, target):
            known[r][c] = truth[r][c]
            if truth[r][c] == WALL:
                break


# 역할: 선택한 목표까지 매 칸 이동하며 그 위치에서 주변을 관측한다.
# 입력: 두 지도, 현재 위치, 목표, BFS 부모 사전, 지금까지의 이동 비용.
# 과정: 부모 사전으로 경로 복원 → 한 칸 이동 → 비용 추가 → 관측을 반복한다.
# 반환: (실제 최종 위치, 누적 이동 비용). known도 직접 갱신된다.
# 참고: 이동 중 목표를 다시 선택하지 않지만 전체 셀이 관측되면 즉시 멈춘다.
def move_to_nbv(truth, known, robot, target, parents, total_cost):
    """이동 비용과 관측 방식은 기존 전수 코드와 동일하다."""
    path = [target]
    while path[-1] != robot:
        path.append(parents[path[-1]])
    for robot in reversed(path[:-1]):
        total_cost += STEP_COST
        observe(truth, known, robot)
        if not any(UNKNOWN in row for row in known):
            break
    return robot, total_cost


# 6. 전체 탐사
# 역할: 초기 관측부터 전체 셀 관측 완료까지 탐사를 수행한다.
# 입력: 실제 지도 truth, 관측 지도 known, 시작 좌표 robot.
# 과정: 새 캐시 생성 → 초기 관측 → lazy 후보 선택 → 매 칸 이동·관측 → 반복.
# 반환: (최종 위치, 누적 이동 비용, 목표 선택 횟수).
# 부수 효과: known과 전역 NBVpath를 갱신한다.
# 오류: UNKNOWN이 남았는데 관측 가능한 후보가 없다고 확인되면 예외를 발생시킨다.
def explore(truth, known, robot):
    """새 탐사 호출마다 캐시를 초기화하고, 탐사 중에는 같은 사전을 전달한다."""
    global NBVpath
    NBVpath.clear()
    if SENSOR_RANGE < 1:
        raise ValueError("전체 지도 관측을 위해 시야 반경은 1 이상이어야 합니다.")

    cached_gains = {}
    total_cost = rounds = 0
    observe(truth, known, robot)
    while any(UNKNOWN in row for row in known):
        target, exact, parents = evaluate_candidates(known, robot, cached_gains)
        if target is None:
            raise RuntimeError("미확인 칸이 남았지만 관측 가능한 NBV 후보가 없습니다.")
        # evaluate_candidates()는 양의 이득을 가진 현재 정확 평가 후보만 선택한다.
        NBVpath.append(target)
        robot, total_cost = move_to_nbv(
            truth, known, robot, target, parents, total_cost
        )
        rounds += 1
    return robot, total_cost, rounds


# 직접 실행할 때만 지도 생성과 탐사를 수행한다.
# 출력: 시작/종료 위치, 목표 선택 횟수, 누적 이동 비용, 최종 지도, 목표 기록.
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
