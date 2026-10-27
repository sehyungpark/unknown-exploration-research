"""비트셋 상한과 힙을 이용하는 C* NBV. 실행: python C_cstarNBV.py

같은 폴더의 nbv_common.py가 필요하다.
기존 C*의 range 상한, 가시 집합 캐시, 지연 교집합 갱신을 유지한다.
이동/가시성/점수/관측/출력은 A 및 B와 같은 공통 함수를 사용한다.
"""
from heapq import heapify, heappop, heappush
import nbv_common as common
from nbv_common import (
    UNKNOWN, FREE, WALL, MOVES, STEP_COST, SCORE_EPSILON,
    free_neighbors, shortest_paths, ray_cells,
    nbv_score, candidate_rank,
    ExplorationResult, print_result,
)

HEIGHT = 20
WIDTH = 20
OBSTACLE_RATE = 0.20
SENSOR_RANGE = 4.0
SEED = 42
MAX_MAP_ATTEMPTS = 1000

truth = None
known = None
NBVpath = []


def create_map():
    global truth, known
    NBVpath.clear()
    truth, known, robot = common.generate_map(
        HEIGHT, WIDTH, OBSTACLE_RATE, SEED, MAX_MAP_ATTEMPTS)
    return truth, known, robot


def sensor_targets(origin):
    return common.sensor_targets(origin, HEIGHT, WIDTH, SENSOR_RANGE)


def cell_bit(coord, width=None):
    """row-major 비트 번호. 내부 계산에는 실제 입력 지도의 너비를 전달한다."""
    if width is None:
        width = WIDTH
    return 1 << (coord[0] * width + coord[1])


def build_unknown_mask(known):
    """현재 UNKNOWN을 구성한다. 증분 모드에서는 탐사 중 최초 계획에만 쓴다."""
    width = len(known[0])
    mask = 0
    for row, values in enumerate(known):
        for col, value in enumerate(values):
            if value == UNKNOWN:
                mask |= cell_bit((row, col), width)
    return mask


class UnknownMaskState:
    """한 탐사에서만 사용하는 UNKNOWN mask와 아직 반영하지 않은 관측 셀.

    첫 계획은 초기 관측 이후의 known으로 mask를 구성한다. 이후에는 관측
    hook이 모은 UNKNOWN->known 셀만 지운다. 다른 탐사에 재사용하지 않는다.
    """

    def __init__(self):
        self.mask = None
        self.shape = None
        self.pending = set()

    def report_newly_known(self, cell):
        self.pending.add(cell)

    def synchronize(self, known):
        shape = (len(known), len(known[0]))
        if self.shape is not None and shape != self.shape:
            raise ValueError("탐사 중 지도 크기가 바뀌었습니다. mask 상태를 새로 만드세요.")
        height, width = shape
        delta_mask = 0
        for row, col in self.pending:
            if not (0 <= row < height and 0 <= col < width):
                raise ValueError("새로 알려진 셀이 지도 범위를 벗어났습니다.")
            if known[row][col] == UNKNOWN:
                raise ValueError("아직 UNKNOWN인 셀은 mask에서 제거할 수 없습니다.")
            delta_mask |= cell_bit((row, col), width)
        # 검증이 끝나기 전에는 유지 중인 mask나 pending을 변경하지 않는다.
        if self.mask is None:
            current = build_unknown_mask(known)
        elif delta_mask:
            current = self.mask & ~delta_mask
        else:
            current = self.mask
        self.mask, self.shape = current, shape
        self.pending.clear()
        return current


def sensor_range_mask(candidate, range_masks, shape=None):
    """고정된 센서의 범위를 처음 필요할 때만 비트셋으로 저장한다.

    같은 cache/range_masks를 다른 지도 크기나 센서 반경에 재사용하지 않는다.
    """
    height, width = shape if shape is not None else (HEIGHT, WIDTH)
    if candidate not in range_masks:
        mask = 0
        for target in common.sensor_targets(candidate, height, width, SENSOR_RANGE):
            mask |= cell_bit(target, width)
        range_masks[candidate] = mask
    return range_masks[candidate]


def visible_unknown_mask(known, candidate):
    """A/B와 같은 가시 셀들을 비트셋으로 표현한다."""
    width = len(known[0])
    mask = 0
    for target in common.visible_unknown_cells(known, candidate, SENSOR_RANGE):
        mask |= cell_bit(target, width)
    return mask


def exact_evaluate(known, candidate, distance, cache, upper_gain):
    """현재 정확 가시 집합과 gain으로 캐시를 교체한다."""
    mask = visible_unknown_mask(known, candidate)
    gain = mask.bit_count()
    if gain > upper_gain:
        raise RuntimeError(
            f"후보 {candidate}의 현재 이득 {gain}이 상한 {upper_gain}보다 큽니다. "
            "환경·센서 변경 또는 다른 탐사의 캐시 재사용 여부를 확인하세요.")
    cache[candidate] = {"visible_mask": mask, "upper_gain": gain}
    return nbv_score(gain, distance), gain, distance


def evaluate_candidates(known, robot, cache, range_masks, *, unknown_state=None):
    """(목표 또는 None, 이번 정확 평가 사전, BFS 부모 사전)을 반환한다.

    정적 환경·단조 공개·고정 센서가 전제이다. 기존 가시 집합을 현재 UNKNOWN과
    교차하는 작업은 후보가 힙에서 꺼내질 때만 수행한다.
    unknown_state가 있으면 명시적으로 보고된 관측만 반영한다. 기존 네 인자
    호출은 호환성과 비교 검증을 위해 매번 mask를 구성하는 동작을 유지한다.
    """
    unknown_mask = (build_unknown_mask(known) if unknown_state is None
                    else unknown_state.synchronize(known))
    distances, parents = shortest_paths(known, robot)
    candidates = tuple(sorted(v for v in distances if v != robot))
    exact = {}
    if not candidates:
        return None, exact, parents

    refreshed = set()
    range_bounds = {}
    queue = []
    shape = (len(known), len(known[0]))
    for candidate in candidates:
        range_mask = sensor_range_mask(candidate, range_masks, shape)
        range_upper = (range_mask & unknown_mask).bit_count()
        range_bounds[candidate] = range_upper
        entry = cache.get(candidate)
        upper_gain = range_upper if entry is None else min(entry["upper_gain"], range_upper)
        distance = distances[candidate]
        queue.append(candidate_rank(candidate,
                                    (nbv_score(upper_gain, distance), upper_gain, distance)))
    heapify(queue)
    best_candidate = best_key = None

    while queue:
        top_key = queue[0]
        top_upper_gain = -top_key[1]
        if top_upper_gain == 0 and (
            best_candidate is None or exact[best_candidate][1] == 0
        ):
            return None, exact, parents
        # 현재 exact 최선이 모든 미평가 후보의 상한을 이기는 경우만 확정한다.
        if best_key is not None and best_key < top_key:
            return best_candidate, exact, parents

        popped_key = heappop(queue)
        candidate = (popped_key[3], popped_key[4])
        distance = distances[candidate]
        entry = cache.get(candidate)
        if entry is not None and candidate not in refreshed:
            # visible_mask는 변경하지 않고 상한 숫자만 줄인다.
            change_upper = (entry["visible_mask"] & unknown_mask).bit_count()
            if change_upper > entry["upper_gain"] or change_upper > range_bounds[candidate]:
                raise RuntimeError(
                    f"후보 {candidate}의 상한이 증가했습니다. "
                    "지도·센서 조건과 캐시 재사용 범위를 확인하세요.")
            entry["upper_gain"] = change_upper
            refreshed.add(candidate)
            upper_gain = min(change_upper, range_bounds[candidate])
            heappush(queue, candidate_rank(candidate,
                                          (nbv_score(upper_gain, distance), upper_gain, distance)))
            continue

        evaluation = exact_evaluate(known, candidate, distance, cache, -popped_key[1])
        exact[candidate] = evaluation
        rank = candidate_rank(candidate, evaluation)
        if best_key is None or rank < best_key:
            best_candidate, best_key = candidate, rank
        # 정확 평가한 후보는 큐에 다시 넣지 않는다.

    if best_candidate is not None and exact[best_candidate][1] > 0:
        return best_candidate, exact, parents
    return None, exact, parents


def observe(truth, known, robot):
    common.observe(truth, known, robot, SENSOR_RANGE)


def move_to_nbv(truth, known, robot, target, parents, total_cost):
    """(실제 끝점, 누적 비용, 계획 경로, 실제 경로)를 반환한다."""
    return common.move_to_nbv(
        truth, known, robot, target, parents, total_cost, SENSOR_RANGE)


def explore(truth, known, robot):
    """탐사마다 두 캐시를 초기화하고 A/B와 같은 경로·종료 결과를 반환한다."""
    NBVpath.clear()
    cache, range_masks = {}, {}
    unknown_state = UnknownMaskState()

    def select_candidate(grid, position):
        return evaluate_candidates(
            grid, position, cache, range_masks, unknown_state=unknown_state)

    result = common.run_exploration(
        truth, known, robot, SENSOR_RANGE, select_candidate,
        on_newly_known=unknown_state.report_newly_known)
    NBVpath.extend(result.targets)
    return result


if __name__ == "__main__":
    truth, known, start = create_map()
    result = explore(truth, known, start)
    print_result(result, known)
