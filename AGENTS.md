# AGENTS.md

## 1. Project Purpose

이 저장소는 다음 정보과학 연구를 위한 실험 및 알고리즘 구현 프로젝트다.

**연구 주제:** 미지의 공간 탐사 및 지도 복원 알고리즘 개발 및 성능 검증

연구의 중심은 실제 로봇 제어가 아니라, 가상환경에서의 **알고리즘 설계, 분석, 비교, 검증**이다.

핵심 목표:
- 기존 탐사 알고리즘의 계산적 병목 분석
- 새로운 문제 정식화
- 다른 정보과학 분야의 알고리즘적 아이디어와 탐사 문제의 결합
- 이론적 성질 또는 성능 보장을 가진 새로운 알고리즘 설계
- 통제된 simulation benchmark를 통한 성능 검증

## 2. Hard Constraints

### Environment
- 실제 physical robot은 사용하지 않는다.
- 모든 실험은 simulation에서 수행한다.
- SLAM은 연구 범위에서 제외한다.
- localization error를 연구하지 않는다.
- agent의 현재 위치와 자세는 정확히 안다고 가정한다.
- "unknown environment"는 environment geometry/map이 처음에 unknown이라는 뜻이다.
- 기본 환경은 static environment다.
- 기본 연구는 single-agent로 수행한다.

### Learning
- 많은 GPU 학습이 필요한 heavy deep reinforcement learning은 사용하지 않는다.
- PPO, SAC 등의 대규모 RL을 기본 해결책으로 제안하지 않는다.
- neural network는 명확한 연구 목적이 있을 때만 사용한다.
- learning-based 요소가 들어가더라도 algorithmic contribution과 분리한다.

### Exploration Assumptions
- frontier-based exploration은 baseline 또는 도구일 뿐이며 필수 전제가 아니다.
- Boustrophedon/CPP를 무시하지 않는다.
- unknown environment에도 online/sensor-based coverage 알고리즘이 존재함을 전제로 한다.

## 3. Scientific Integrity Rules

다음 행동을 금지한다.
- proposed method에 유리하도록 baseline을 의도적으로 약하게 구현
- 알고리즘별로 다른 map이나 random seed 사용
- 실패한 map을 결과에서 임의로 제외
- 결과가 좋지 않다는 이유로 metric 변경
- 동일한 목적을 평가하면서 서로 다른 sensing range 사용
- 예상과 다른 결과를 숨김
- 통계적으로 유리한 seed만 선택
- 실험 후 parameter를 반복 조정하고 해당 사실을 기록하지 않는 행위

모든 experiment는 가능하면 configuration, random seed, map generator, map instance ID, algorithm version, metric, raw result, runtime, failure reason을 저장한다.

## 4. Novelty Rules

어떤 아이디어도 단순히 "검색에서 못 찾았다"는 이유만으로 novel이라고 선언하지 않는다.

허용 표현:
> 현재 조사한 문헌 범위에서는 동일한 문제 정식화 또는 동일한 알고리즘을 찾지 못했다.

금지 표현:
> 세계 최초다.
> 아무도 연구하지 않았다.

새 후보를 구현하기 전 가장 가까운 선행연구와 차이를 한 문장으로 정의한다.

## 5. Common Architecture Rule

후보 1~4를 별도 simulator로 작성하지 않는다. 하나의 공통 simulator 위에서 planner 또는 map model만 교체한다.

```text
src/
├─ environment/
├─ sensing/
├─ mapping/
├─ planning/
├─ candidates/
├─ evaluation/
└─ utils/
```

공통 부분:
- ground-truth grid map
- agent state
- sensor ray casting
- observation integration
- shortest-path planning
- candidate generation
- map generators
- evaluation metrics
- logging
- visualization

## 6. Implementation Philosophy

다음 순서를 따른다.
1. 작은 deterministic environment
2. correctness test
3. algorithm core
4. sanity-check experiment
5. scaling experiment
6. 추가 현실성
7. 필요할 경우 learning/noise 추가

각 candidate마다 최소한 open map, single room, corridor, dead end, separated rooms, clutter, maze-like environment를 테스트한다.

## 7. Current Research Candidates

### Candidate 1
**Exact Lazy Next-Best-View Selection Using Monotone Information Bounds**

목적: exhaustive NBV와 동일한 viewpoint를 선택하면서 expensive information-gain calculation을 줄인다.

### Candidate 2
**Robust Prediction-Augmented Exploration**

목적: map prediction이 정확하면 활용하지만, prediction이 잘못되어도 robust baseline에 비해 심각하게 악화되지 않는 exploration algorithm을 만든다.

### Candidate 3
**Anytime-Certified Active Map Reconstruction**

목적: 단순 spatial coverage가 아니라 statistical confidence를 기준으로 map reconstruction completion을 정의하고, 필요한 sensing 횟수를 최소화한다.

### Candidate 4
**Low-Recourse Dynamic View-Cover Exploration**

목적: map update마다 future viewpoint plan 전체를 다시 만들지 않고, solution quality를 유지하면서 plan의 변경량(recourse)을 줄인다.

## 8. Development Priority

```text
Common Simulator
        ↓
Candidate 1
        ↓
Candidate 3
        ↓
Candidate 2
        ↓
Candidate 4
```

이 순서는 최종 후보의 가치 순위가 아니라 공통 코드 재사용성과 구현 안정성을 기준으로 한다.

## 9. Current Status

아직 production-quality implementation을 시작하지 않는다.
현재 단계에서는 문제 정식화, literature validation, simulator specification, experiment design을 먼저 고정한다.

## 10. Before Coding

구현 요청을 받으면 먼저 다음을 확인한다.
1. 어떤 candidate를 구현하는가?
2. 어떤 experiment phase인가?
3. 기존 baseline과 무엇을 공유해야 하는가?
4. correctness condition은 무엇인가?
5. 현재 구현으로 검증하려는 hypothesis는 무엇인가?
6. 결과가 좋지 않으면 연구 가설을 기각할 수 있는가?

## Shared Research State

This repository is the shared source of truth between ChatGPT research conversations and Codex.

After every meaningful implementation or experiment:

1. Update docs/PROJECT_STATE.md.
2. If a research assumption changes, update docs/DECISIONS.md.
3. If an experiment is executed, append it to docs/EXPERIMENT_LOG.md.
4. If a research or theoretical conclusion changes, append it to docs/RESEARCH_LOG.md.
5. Update docs/TODO.md.
6. Never delete failed or unfavorable experimental results.
7. Clearly distinguish verified results, hypotheses, unresolved questions, and failed experiments.
8. Important information must not exist only in the Codex conversation. It must be written into this repository.
