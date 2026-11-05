# 연구 진행도 점검 — 2026-10-20

## 판단

현재 Candidate 1은 **문제 정식화 → 공통 simulator → 정확성 검증 → 실패한 구현의 원인 분석 → C* 재설계 → 사전등록된 정식 효율성 검증**까지 진행되었다. 다음 단계는 C*의 기여 원인을 분리하고, 환경과 규모를 넓혀 논문 주장을 검증하는 것이다. Candidate 2·3·4는 현재 저장소에서 같은 수준으로 구현·검증된 상태가 아니다.

연구의 중심 주장은 다음으로 유지한다.

> 고정된 exhaustive optimistic NBV와 동일한 선택을 인증하면서 평가 계산을 줄인다.

같은 선택과 경로를 보존하는 방법이므로, 현재 실험으로 주장할 성과는 계획 계산 비용 절감이다. 더 짧은 탐사 경로나 더 우수한 탐사 정책을 개발했다고 해석하지 않는다.

## 확인 범위와 저장소 상태

- GitHub main과 로컬 HEAD는 `88f1b6bfefa56d928bd8dee62fcf1d30dc900714`로 동일했다. GitHub의 마지막 main 커밋은 2026-09-19 정식 Experiment 2 결과 기록이며, 열린 PR은 없었다. 조회된 브랜치는 main, algorithm-c-star, experiment-2-cstar, experiment-2-e1-integrity였다.
- 로컬에는 2026-09-29 상태 문서 수정, 연구용 스크립트, 후속 파일럿 결과가 미커밋 상태로 남아 있다. Experiment 1 원시 결과도 미추적 상태이다. GitHub만으로는 이 후속 상태가 전달되지 않는다.
- 2026-09-29 원시 결과 재집계 감사에서 보존한 SHA-256과 현재 Experiment 1의 6개 파일 및 Experiment 2의 7개 파일을 비교했으며, **13/13이 일치**했다. 이번 점검은 기록 확인과 구조적 집계이며 정식 실험 재실행이 아니다.
- 현재 실행 중인 Python 실험 프로세스는 관찰되지 않았다. 9월 29일 전체 테스트 로그는 0바이트이며 완료 상태를 입증하지 못한다. 통과 또는 실패를 새로 단정하지 않는다.

## 완료한 연구 성과

| 항목 | 확인된 상태 | 해석 범위 |
|---|---|---|
| 공통 simulator | 구현됨: 정확한 pose, static grid, 공통 sensing/motion/mapping/planning | 기본 결정론적 simulation 조건 |
| 이론 | cached visible-UNKNOWN intersection bound와 tie-aware exact-selection 정식화 | static world, monotone belief, 고정 viewpoint/sensor 등의 조건부 결과 |
| Experiment 0 | 67개 complete run, 1,185 snapshot에서 A/B/C 일치, PASS | B/C의 정식 정확성 결과; C*는 별도 회귀와 Experiment 2로 평가 |
| Experiment 1 | 역사적 C의 C/B 시간 비율 8.8379, 95% bootstrap 구간 6.9545–10.8448, DROP | ray 계산 절감이 전체 속도 개선을 보장하지 않음을 보여 준 실패 결과 |
| Experiment 2 | C* 정식 실행 완료, correctness 통과, GO | 27개 holdout map의 구조적 비교와 9개 map의 시간 비교 |
| C* 후속 파일럿 | 21개 map, 616개 snapshot, 기록된 결정·선택값·경로 불일치 0 | 탐색적 구조 검증 완료; 시간 측정 미실행 |

Experiment 2에서 C*/B planner-time 기하평균 비율은 **0.33069**, map-level paired bootstrap 95% 구간은 **0.24543–0.44563**이다. 이 workload에서 약 **3.02배** 빠르고 약 **66.9%** 적은 계획 시간을 사용했다. 정확한 gain 평가 수는 B의 39.28%, ray 수는 57.90%, supercover cell 수는 58.52%, interior probe 수는 53.70%이다. 네 방법을 같은 invocation 안에서 비교한 결과다. 서로 다른 기계와 Python 버전을 사용한 Experiment 1/2의 절대 실행 시간을 직접 비교하지 않는다.

근거: `results/experiment_0/runs/experiment0-formal-20260916-001/`, `results/experiment_1/runs/experiment1-formal-20260917-001/`, `results/experiment_2/runs/experiment2-formal-20260919-001/`.

## 후속 파일럿에서 이미 배운 점

동일한 simulator·map·sensor range·tie rule로 일곱 fixture, 여덟 fresh Bernoulli map, 여섯 four-room map을 평가했다. 사전 고정한 소규모 탐색적 실험이며 정식 Experiment 2의 분류를 변경하지 않는다.

| 방법 | 정확한 gain 평가 수 |
|---|---:|
| A: exhaustive | 294,512 |
| B: stale scalar | 33,897 |
| S*: C*의 scheduler/range bound를 유지하고 cached-set intersection을 제거한 소거 방법 | 12,717 |
| C* | 9,878 |

C*는 S*보다 정확한 평가를 **22.32%** 줄였다. 따라서 이번 표본에서는 변화 인지 bound가 range bound와 동일한 scheduler 위에서 추가 pruning을 제공한다. 다만 S*는 원인 분리를 위해 C*의 bitset 할당과 진단 구조를 유지한다. 완전히 최적화된 scalar 경쟁 알고리즘의 속도나 메모리와 동등하게 해석하지 않는다. **파일럿 시간 기록과 최종 summary는 없으므로 S* 대비 wall-clock 우위는 아직 미검증이다.**

연구용 occlusion certificate는 6,561개 3×3 belief와 34,992개 단일 monotone transition 검증에서 위반이 없었다. 실제 파일럿에서는 C*가 수행할 9,878개 정확한 visibility 쿼리 중 **79개(0.80%)**를 재사용했고, dependency 작성에 별도로 **113,957개 ray 경로 구성**이 필요했다. query 수와 ray 수는 다른 단위다. 이것만으로 느리다고 판정할 수는 없지만, 현재 구현을 우선 확장할 실용적 근거는 약하다. 이론적 충분조건과 실용적 이득을 구분한다.

비트셋 구조 점검에서는 R=8, 중앙 footprint의 197개 membership을 담는 전역 integer가 40×40에서 180바이트, 320×320에서 7,216바이트였다. 같은 footprint를 지역 좌표로 재인코딩한 integer는 모두 64바이트였고 20개 위치·크기 조합의 복원 검사가 일치했다. 이는 integer 객체만의 비교다. 지역 UNKNOWN 추출, 변환, 컨테이너, 전체 planner 비용을 포함한 개선은 아직 구현·검증하지 않았다.

근거: `results/extension_pilot_20260929/run-001/{maps.json,structural.jsonl,snapshots.jsonl,certificate_properties.json,bitmask_scaling.json,historical_audit.json}`. Manifest 상태는 `STRUCTURAL_PASS`이다.

## 논문 주장으로 묶기 위해 남은 일

1. **기여 원인의 분리.** C* 대 B는 여러 설계 변경을 묶어서 비교한다. 동일한 실행 구조에서 range bound, cached-set bound, lazy refresh, 자료 표현을 각각 제거해 work·time·memory를 함께 비교해야 한다. 기존 소거 파일럿의 시간 측정을 먼저 완료한다.
2. **환경과 규모에 대한 일반화.** 정식 주 workload는 20–40 grid의 Bernoulli map이다. 방·복도·좁은 문·긴 dead end·maze 및 더 큰 map에서 성능 유지 또는 실패 경계를 확인해야 한다. 기존 21-map pilot은 이 방향의 초기 정확성 근거다.
3. **이론·기여 주장의 정리.** 저장소의 novelty 평가는 조건부·고위험이다. 일반적인 caching, lazy selection, changed-region update, gain decrement를 독창적 기여로 제시할 수 없다. 현재의 정확한 결합 정식화, 선택 인증, 비용 분석을 선행연구와 대조해야 한다.
4. **재현 가능한 연구 상태의 보존.** Experiment 1 및 후속 원시 기록의 저장·공유 방식을 정하고, 실행 완료를 반영한 문서와 코드·결과를 같은 연구 상태로 묶어야 한다. 이번 점검은 commit/push를 수행하지 않았다.

기존 C*를 완성할 다음 작업의 우선순위는 **파일럿 시간 측정과 강한 scalar＋range 기준선 → 구조적 환경 및 큰 map 검증 → 필요한 경우 local/tiled representation → 새로운 확장 후보**로 판단한다. 이 순서는 새 성능 가설이며 정식 결과가 아니다. 동적 환경, sensing noise, Candidate 3의 statistical completion은 현재 bound의 가정을 바꾸므로 별도 정식화가 필요하다.

연구 단계 평가는 **알고리즘과 정식 효율성 근거를 확보했으며, 기여 분리·일반화·논문화 검증이 남은 단계**이다. C*를 폐기하거나 네 후보를 모두 다시 시작할 근거는 현재 기록에서 보이지 않는다. 완성률을 하나의 숫자로 표현할 만큼 논문 범위와 완료 기준이 고정되어 있지는 않다.
