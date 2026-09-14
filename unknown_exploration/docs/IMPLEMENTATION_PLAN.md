# Implementation and Experiment Plan

## 1. Overall Strategy

```text
Phase A — Common Simulator
        ↓
Phase B — Candidate 1 prototype
        ↓
Phase C — Candidate 3 prototype
        ↓
Phase D — Candidate 2 prototype
        ↓
Phase E — Candidate 4 prototype
        ↓
Phase F — Comparative Evaluation
        ↓
Phase G — Select Final Research Topic
```

각 candidate는 작은 prototype에서 핵심 가설을 검증하지 못하면 중단할 수 있다.

## 2. Phase A — Common Simulator

### Goal
모든 candidate가 동일한 조건에서 비교될 수 있는 minimal exploration simulator를 만든다.

### Components

#### Environment
```text
GridWorld
├─ width
├─ height
├─ ground_truth
├─ start_position
└─ reachable_free_cells
```

#### Sensor
```text
RangeSensor
├─ max_range
├─ ray_directions
├─ cast_ray()
└─ scan()
```

#### Belief Map
```text
OccupancyMap
├─ UNKNOWN
├─ FREE
├─ OCCUPIED
├─ update()
└─ get_candidates()
```

Frontier는 mandatory abstraction이 아니다.

#### Navigation
```text
PathPlanner
├─ A*
├─ Dijkstra
└─ path_cost()
```

#### Candidate Generation
```text
CandidateGenerator
└─ generate(map, agent_state)
```

#### Evaluation
```text
Metrics
├─ coverage
├─ path_length
├─ planning_time
├─ sensor_evaluations
├─ ray_count
├─ replanning_count
└─ success
```

## 3. Map Families

초기 procedural generator:
- Open
- Rooms
- Clutter
- Maze
- Mixed

각 family에 여러 random seed를 사용한다.

## 4. Candidate 1 Plan

### Hypothesis
Monotone information upper bounds를 사용하면 exhaustive greedy NBV와 정확히 동일한 target을 선택하면서 exact information-gain evaluation 수를 크게 줄일 수 있다.

### Step 1 — Exhaustive Baseline
모든 candidate에 대해 exact gain, distance, score를 계산한다.

### Step 2 — Prove Gain Monotonicity
필요 조건:
- deterministic observation
- unknown treated optimistically for gain
- observation only reduces map uncertainty
- candidate pose fixed

목표:
\[
G_{t+1}(v)\le G_t(v)
\]

### Step 3 — Lazy Upper Bound
\[
UB_t(v)=\frac{G_{\mathrm{cached}}(v)}{d_t(v)+\epsilon}
\]

새 candidate에는 geometric maximum gain bound를 부여한다.
Priority queue에서 가장 높은 UB부터 exact evaluation하고, 현재 exact best가 모든 remaining UB 이상이면 종료한다.

### Step 4 — Correctness Test
- argmax match rate = 100% 목표
- selected target sequence도 exhaustive와 같아야 함

### Step 5 — Efficiency Experiment
변수:
- map size
- candidate density
- sensing radius
- obstacle density
- exploration progress

측정:
- exact gain evaluations
- ray casts
- planning CPU
- peak memory

### Stop Condition
exhaustive와 target mismatch가 생기고 valid proof/correction으로 해결되지 않으면 Candidate 1을 재검토한다.

## 5. Candidate 3 Plan

### Hypothesis
모든 cell에 동일한 sensing budget을 쓰는 것보다 certification deficit이 큰 cell에 관측을 adaptive하게 배분하면 동일한 global reconstruction confidence를 더 적은 sensing으로 달성할 수 있다.

### Step 1 — Noisy Sensor
예:
\[
P(z=M_i\mid d)=q(d)
\]

처음에는 constant q로 시작하고 이후 distance-dependent noise를 추가한다.

### Step 2 — Evidence State
각 cell이 저장:
```text
num_observations
positive_evidence
negative_evidence
log_likelihood_ratio
confidence
certification_state
```

### Step 3 — Sequential Test
Baseline: fixed n-sample majority vote.
Proposed: sequential stopping.
최종 연구에서는 anytime-valid statistical method를 사용한다.

### Step 4 — Global Error Control
\[
P(\exists\text{ wrongly certified cell})\le\delta
\]

초기 error allocation:
\[
\delta_i = \frac{\delta}{N}
\]

### Step 5 — Active Planner
\[
G_{\mathrm{cert}}(v)=\sum_{i\in Vis(v)} D_i
\]

Distance-aware score:
\[
S(v)=\frac{G_{\mathrm{cert}}(v)}{d(v)+\epsilon}
\]

### Baselines
- Fixed repeated sensing
- Entropy NBV
- Ordinary unknown-cell NBV
- Certification-driven planner

### Metrics
- number of sensor observations
- path length
- actual classification error
- certified coverage
- time to 90/95/99% certification
- violation rate of requested delta
- computation time

## 6. Candidate 2 Plan

### Hypothesis
Untrusted map prediction을 직접 믿는 planner보다 prediction과 robust baseline을 결합한 planner가 prediction quality 전체 구간에서 더 안정적인 performance를 가진다.

### Step 1 — No ML
Ground truth에서 artificial prediction을 만든다.

Error models:
- independent corruption
- missing wall
- fake wall
- incorrect room continuation
- wrong corridor extension

Structured corruption을 반드시 포함한다.

### Step 2 — Planners
- Robust Baseline
- Blind Predictor
- Robust Predictor

### Step 3 — Prediction Error Sweep
```text
0%
5%
10%
20%
30%
40%
50%
```

### Metrics
- path length
- completion
- failures
- backtracking
- false-goal selections
- prediction utilization rate
- fallback rate

### Step 4 — Theoretical Protection
가능한 수준을 찾는다.
- Strong: global competitive bound
- Medium: bounded extra exploration budget before baseline recovery
- Weak but useful: formally justified local acceptance certificate

### Step 5 — Actual Predictor
planner 검증 후에만 추가한다.
1. structural heuristic
2. lightweight supervised model
3. small CNN

Heavy RL은 사용하지 않는다.

## 7. Candidate 4 Plan

### Hypothesis
exploration map의 변화가 local/incremental하므로 future viewpoint cover를 매번 처음부터 계산하지 않고 repair하면 낮은 recourse로 competitive solution quality를 유지할 수 있다.

### Step 1 — Static Set-Cover Representation
- Target cells: \(U_t\)
- Candidate set: \(V_t\)
- Visibility: \(S_t(v)\subseteq U_t\)
- Fresh greedy baseline: \(Q_t^{fresh}\)

### Step 2 — Persistent Solution
Previous solution에서 아직 유효한 viewpoint를 보존하고 새 uncovered element만 추가 cover하며 불필요한 set은 prune한다.

### Step 3 — Recourse
\[
R_t=|Q_t\triangle Q_{t-1}|
\]

\[
R_{\mathrm{total}}=\sum_t R_t
\]

### Step 4 — Trade-Off
동시에 측정:
- \(|Q_t|\)
- \(R_t\)
- \(L(Q_t)\)

recourse만 낮은 algorithm을 성공으로 판단하지 않는다.

### Step 5 — Parameter Sweep
\[
J_t=|Q_t|+\lambda R_t
\]

```text
lambda = 0
lambda = 0.1
lambda = 0.5
lambda = 1
lambda = 2
lambda = 5
```

### Failure Criterion
recourse를 줄이기 위해 viewpoint count 또는 travel cost가 지나치게 증가한다면 Candidate 4는 최종 후보에서 제외할 수 있다.

## 8. Shared Evaluation Protocol

공정한 비교를 위해:
- same generated map
- same start position
- same sensor range
- same movement model
- same random seed
- same completion target

을 사용한다.

## 9. Logging Format

각 run은 최소 다음을 저장한다.
```text
algorithm
candidate_version
map_family
map_seed
start_seed
map_size
sensor_range
coverage_target
path_length
steps
planning_time
sensor_calls
raycasts
success
failure_reason
```

## 10. Final Candidate Selection

평가축:
- Novelty
- Formality
- Effect Size
- Robustness
- Complexity
- Explainability
- Reproducibility

## 11. Current Priority Assessment

- Candidate 1: 가장 구현 가능성이 높음
- Candidate 3: 새 후보 중 가장 유망함
- Candidate 2: 연구 가치가 높지만 robustness theory가 어려울 수 있음
- Candidate 4: 가장 high-risk/high-reward

## 12. First Codex Task

```text
AGENTS.md와 docs/의 연구 문서를 모두 읽어라.

아직 코드를 작성하거나 파일을 수정하지 마라.

다음 내용을 보고하라.

1. 연구의 전체 목표
2. 후보 1~4의 핵심 문제와 차이
3. 네 후보가 공유할 수 있는 simulator component
4. 후보별로 별도로 필요한 component
5. 현재 specification에서 모호한 점
6. 구현 전에 반드시 결정해야 하는 parameter
7. Candidate 1을 시작한다고 가정했을 때 최소 구현 순서
8. Candidate 1 correctness를 검증하기 위한 unit test 목록

문서에 없는 가정을 임의로 추가하지 마라.
```

이 응답을 확인한 뒤에만 실제 coding을 시작한다.
