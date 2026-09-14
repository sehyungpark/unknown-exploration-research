# Research Context

## 1. Research Topic

### Korean
**미지의 공간 탐사 및 지도 복원 알고리즘 개발 및 성능 검증**

### Broad English Description
**Algorithm Design and Evaluation for Exploration and Map Reconstruction in Unknown Environments**

본 연구는 가상의 미지 환경에서 제한된 sensing을 이용하여 환경을 점진적으로 복원하는 agent를 연구한다.

Agent는 처음에는 environment geometry를 알지 못하며, 이동하면서 주변을 관측하고, partial map을 갱신하고, 다음 관측 위치를 선택하며, 가능한 적은 비용으로 충분한 map reconstruction을 달성해야 한다.

## 2. Research Motivation

관련 분야:
- Frontier-Based Exploration
- Next-Best-View
- Information-Theoretic Exploration
- Informative Path Planning
- Coverage Path Planning
- Boustrophedon decomposition
- Sampling-based exploration
- Receding-horizon planning
- Hierarchical planning
- Topological exploration
- Learning-based exploration
- Predictive map completion

현재 후보 1~4는 각각 다음 질문을 담당한다.

### A. Computational Question
기존 exploration planner의 결과를 유지하면서 expensive computation을 생략할 수 있는가?

### B. Learning-Augmented Question
불완전한 prediction을 이용하면서도 잘못된 prediction 때문에 planner 전체가 무너지는 것을 막을 수 있는가?

### C. Statistical Question
"map을 관측했다"가 아니라 "map이 충분히 정확하다고 통계적으로 인증되었다"를 completion criterion으로 사용할 수 있는가?

### D. Dynamic-Algorithm Question
새 observation이 들어올 때마다 future plan 전체를 다시 만들지 않고 작은 수정만으로 좋은 plan을 유지할 수 있는가?

## 3. Base Environment

### World
- 2D bounded grid world
- static occupancy map
- ground truth cell: FREE / OCCUPIED
- example map size: 120 × 120 cells
- example resolution: 0.1 m/cell

숫자는 초기 benchmark 설계값이며 최종 표준이 아니다.

### Agent
- single holonomic agent
- exact current pose
- no localization uncertainty
- no SLAM
- start position: random reachable FREE cell

초기에는 4-neighbor 또는 8-neighbor movement 중 하나를 통일해서 사용한다.

### Sensor
초기 deterministic experiment:
- 360° 2D range sensor
- finite sensing radius
- obstacle occlusion
- first occupied cell blocks a ray
- no measurement noise

Candidate 3에서는 noisy sensor model을 별도로 사용한다.

### Internal Map
기본 cell state:
- UNKNOWN
- FREE
- OCCUPIED

Candidate 2는 predicted map을 별도 layer로 가진다.
Candidate 3는 probability/evidence/certification state를 추가한다.

### Navigation
agent는 현재 observed FREE space 안에서만 이동한다.
Shortest path는 A* 또는 Dijkstra를 사용한다.
Unknown cell을 collision-free라고 가정하여 직접 통과하지 않는다.

## 4. Map Reconstruction Evaluation

Ground truth를 알고 있는 offline evaluator가 reachable FREE viewpoint 전체에서 실제 simulator와 동일한 sensor model을 적용한다.

한 번이라도 관측 가능한 cell의 union을

\[
O_{\mathrm{gt}}
\]

로 정의한다.

Coverage:

\[
C_t = \frac{|\text{known cells at time }t \cap O_{\mathrm{gt}}|}{|O_{\mathrm{gt}}|}
\]

90%, 95%, 99% coverage를 기록한다.

## 5. Coverage vs Exploration

Boustrophedon/CPP는 중요한 baseline이다.
"Boustrophedon은 unknown environment에서 못 쓴다"라는 주장은 하지 않는다.

본 후보들의 연구 질문은 coverage completeness 자체와 다르다.
- Candidate 1: expensive information computation
- Candidate 2: robust prediction use
- Candidate 3: statistical reconstruction confidence
- Candidate 4: plan stability / recourse

## 6. Candidate 1 — Exact Lazy NBV Using Monotone Information Bounds

### Core Question
특정 information-gain 정의 아래에서 과거 exact gain을 future upper bound로 사용하여, exhaustive NBV와 동일한 결정을 하면서 exact visibility evaluation을 줄일 수 있는가?

Candidate \(v\)의 exact gain:
\[
G_t(v)
\]

Current travel distance:
\[
d_t(v)
\]

Utility example:
\[
S_t(v)=\frac{G_t(v)}{d_t(v)+\epsilon}
\]

적절한 deterministic occupancy update와 optimistic unknown-transparent visibility 아래에서:
\[
G_{t+1}(v)\le G_t(v)
\]

Cached upper bound:
\[
UB_t(v)=\frac{\overline G_t(v)}{d_t(v)+\epsilon}
\]

현재 exact best \(v^*\)가
\[
S_t(v^*) \ge \max_{v\ne v^*} UB_t(v)
\]
를 만족하면 나머지 candidate의 exact gain 평가를 생략한다.

### Intended Contribution
단순 caching이 아니라 planning cycle을 넘어 유지되는 monotone upper bound와 exhaustive NBV와 동일한 argmax를 반환하는 exact certificate를 목표로 한다.

### Important Conditions
- UNKNOWN을 opaque로 처리하면 monotonicity가 깨질 수 있다.
- current distance는 매 round 재계산해야 한다.
- 새 candidate에는 valid geometric maximum bound가 필요하다.
- tie breaking을 exhaustive와 동일하게 유지해야 한다.

## 7. Candidate 2 — Robust Prediction-Augmented Exploration

### Core Question
prediction이 정확할 때는 성능을 얻고, prediction이 틀릴 때는 robust baseline보다 크게 악화되지 않는 exploration algorithm을 만들 수 있는가?

Observed map:
\[
M_t
\]

Predicted map:
\[
\hat M_t
\]

Prediction은 advice이며 observed map과 분리한다.

### Initial Experiment
neural network 없이 synthetic corruption으로 prediction quality를 조절한다.

비교:
- baseline planner
- blind prediction planner
- robust prediction planner

주요 그래프:
- x: prediction error
- y: exploration cost

### Long-Term Theory Goal
\[
C_{\mathrm{robust}} \le \alpha C_{\mathrm{baseline}} + f(\eta)
\]

전역 보장이 어렵다면 local acceptance certificate 또는 bounded deviation rule을 연구한다.

### Intended Contribution
map completion model 자체가 아니라 **untrusted advice를 사용하는 robust exploration algorithm**이 핵심이다.

## 8. Candidate 3 — Anytime-Certified Active Map Reconstruction

### Core Question
noisy sensor 환경에서 "관측했다"가 아니라 "정확하다고 통계적으로 인증되었다"를 completion criterion으로 사용할 수 있는가?

Target guarantee:
\[
P(\exists i: \hat M_i \ne M_i) \le \delta
\]

### Sensor Model
예:
\[
P(z=M_i\mid d)=q(d)
\]

### Cell State
- UNCERTIFIED
- CERTIFIED FREE
- CERTIFIED OCCUPIED

cell별 evidence/confidence statistic을 유지한다.

### Planning
기존 unknown-cell gain 대신 certification deficit을 사용한다.

\[
G_{\mathrm{cert}}(v)=\sum_{i\in Vis(v)} D_i
\]

### Intended Theory
- sequential hypothesis testing
- confidence sequence
- anytime-valid inference
- multiple-testing control

### Intended Contribution
binary occupancy-map reconstruction에서 global classification-error guarantee를 explicit stopping criterion으로 사용하고 sensing을 active하게 배분하는 것이다.

## 9. Candidate 4 — Low-Recourse Dynamic View-Cover Exploration

### Core Question
map update마다 future viewpoint plan을 새로 만들지 않고, approximation quality를 유지하면서 plan 변경량을 줄일 수 있는가?

현재 viewpoint plan:
\[
Q_t
\]

Recourse:
\[
R_t = |Q_t\triangle Q_{t-1}|
\]

Dynamic set-cover view:
- unresolved targets: \(U_t\)
- viewpoint coverage: \(S_t(v)\)
- selected viewpoints: \(Q_t\)

Objective example:
\[
J_t = |Q_t| + \lambda |Q_t\triangle Q_{t-1}|
\]

추후 route length를 포함할 수 있다.

### Main Difficulty
recourse만 줄이면 old viewpoints가 누적되어 solution quality가 악화될 수 있다.

목표 예시:
\[
|Q_t| \le \alpha |Q_t^*|
\]
이면서
\[
R_t \le k
\]

### Intended Contribution
set cover 자체가 아니라 evolving map에서 **approximation quality와 recourse를 동시에 다루는 것**이다.

## 10. Prototype Evidence

### Candidate 1
31×31 toy maps의 rooms/clutter/maze에서 exhaustive와 lazy가 동일 target sequence와 moves를 보였고 exact gain evaluations는 대략 82%, 87%, 96% 감소했다. 이는 sanity-check이며 publication result가 아니다.

### Candidate 2
synthetic corrupted prediction에서 blind predictor는 실패할 수 있었지만 baseline과 robust gate는 toy tests에서 성공했다. 핵심 관찰은 catastrophic failure 회피이며, 항상 더 짧은 path를 보장한 것은 아니다.

### Candidate 3
simple sequential evidence accumulation이 fixed repeated sensing보다 필요한 sensor evaluations를 크게 줄이는 현상이 toy experiment에서 관찰되었다. 그러나 stopping rule은 아직 rigorous confidence-sequence theorem으로 정리되지 않았다.

### Candidate 4
fresh greedy cover보다 low-recourse repair가 recourse를 줄였지만 일부 map에서 viewpoint count가 크게 증가했다. 현재 가장 high-risk한 후보다.

## 11. Current Candidate Assessment

### Candidate 1
장점: 구현 가능성 높음, correctness theorem 가능성, 계산량 개선 명확.
위험: lazy/caching 선행연구와 novelty 충돌 가능.

### Candidate 2
장점: learning-augmented algorithm 관점, OOD robustness, predictor와 planner 분리 가능.
위험: 강한 global guarantee가 어려울 수 있음.

### Candidate 3
장점: 연구 질문이 명확, statistical theory와 exploration의 결합, heavy learning 불필요.
위험: rigorous global guarantee 설계가 핵심.

### Candidate 4
장점: dynamic algorithms와 exploration의 독특한 결합.
위험: routing까지 포함하면 난도가 높고 recourse가 실제 mission efficiency와 연결되지 않을 수 있음.

## 12. Research Philosophy

최종 연구 주제는 단순 성능이 가장 좋은 후보가 아니라 novelty, theoretical clarity, experimental evidence, computational feasibility, reproducibility를 종합하여 결정한다.
