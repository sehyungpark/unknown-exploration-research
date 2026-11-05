# C* 후속 파일럿 — 사용자 PowerShell 실행 안내

상태: 실행 인프라 준비. 이번 변경에서는 실제 파일럿 시간·메모리 실험을 실행하지 않았다.

## 범위

승인한 계획의 1·2단계인 실행 준비/전체 테스트와 기존 파일럿의 시간 측정을 수행한다. 같은 여섯 지도에서 별도 메모리 측정도 제공한다. 새로운 큰 지도 실험이나 알고리즘 변경은 포함하지 않는다.

공통 simulator·sensor range 8·A/B/C*의 정의는 그대로이다. S*는 C*와 같은 구현에서 cached-set bound를 제거한 소거 방법이다. 완전히 최적화된 scalar 경쟁 구현이라고 해석하지 않는다. CERT도 기존 파일럿의 고정 방법이므로 포함한다.

## 준비

1. `codex/cstar-followup-runner` 브랜치 또는 이 PR을 병합한 main을 사용한다. 해당 코드/config/tests/scripts에는 미커밋 변경이 없어야 한다. 다른 문서와 결과 파일은 미추적 상태여도 된다.
2. Python 3.12 이상과 Git을 사용한다. 외부 Python 패키지는 필요 없다. 같은 invocation의 모든 단계를 같은 PC·Python·커밋에서 실행한다.
3. 전원에 연결하고 절전/자동 재시작을 피한다. 측정 중 다른 벤치마크·테스트·실험을 동시에 실행하지 않는다.

저장소 폴더에서 다음 명령으로 입력과 코드 상태만 확인한다. 이 명령은 planner를 실행하거나 결과 폴더를 만들지 않는다.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_cstar_followup.ps1 -Stage Check
```

기본적으로 `py -3`, 없으면 `python`을 사용한다. 특정 Python을 고정하려면 모든 명령에 다음 옵션을 추가한다.

```powershell
-PythonExe 'C:\path\to\python.exe'
```

## 한 번에 실행

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_cstar_followup.ps1 -Stage All -RunId cstar-pilot-20261020-001
```

실행 순서는 다음과 같다.

1. 보존된 21개 지도·616개 구조 snapshot·원본 source의 해시와 일관성 확인.
2. 새 invocation 생성 및 커밋·source hash·환경 기록.
3. 전체 unittest 실행. 진행 상황을 화면과 `tests.log`에 동시에 기록한다. exit code와 완료 문구를 모두 확인한 후 다음 단계로 간다.
4. 여섯 시간 측정 지도에서 A의 전체 decision/path 참조를 별도 비측정 pass로 생성하고 과거 target/STOP hash와 비교한다.
5. B/S*/C*/CERT에 대해 warm-up 1회와 고정 순서의 측정 4회: 총 120개 episode(24 warm-up, 96 timed).
6. 같은 여섯 지도·네 방법에 대해 fresh episode 24회의 별도 tracemalloc pass.
7. 모든 검증을 통과하면 `PASS`와 `summary.json` 생성.

전체 테스트가 오래 걸릴 수 있다. 각 테스트 이름과 `TIMING 1/120`, `MEMORY 1/24` 형태의 진행 표시가 출력된다. 이번 코드 준비 과정에서 전체 테스트나 실제 파일럿 측정의 통과를 미리 주장하지 않는다.

## 단계별 실행

각 명령은 직전 단계의 정상 완료를 요구한다. 예를 들어 전체 테스트를 마친 뒤 잠시 쉬었다가 시간 측정을 시작할 수 있다.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_cstar_followup.ps1 -Stage Prepare -RunId cstar-pilot-20261020-001
powershell -ExecutionPolicy Bypass -File .\scripts\run_cstar_followup.ps1 -Stage Test -RunId cstar-pilot-20261020-001
powershell -ExecutionPolicy Bypass -File .\scripts\run_cstar_followup.ps1 -Stage Timing -RunId cstar-pilot-20261020-001
powershell -ExecutionPolicy Bypass -File .\scripts\run_cstar_followup.ps1 -Stage Memory -RunId cstar-pilot-20261020-001
```

`All`과 위 단계별 명령 중 하나를 선택한다. 이미 존재하는 run ID에 `All`/`Prepare`를 다시 실행하면 기존 결과를 보호하기 위해 거부한다.

상태 조회:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_cstar_followup.ps1 -Stage Status -RunId cstar-pilot-20261020-001
```

## 결과 위치와 판독

`results/cstar_followup/runs/cstar-pilot-20261020-001/`

| 파일 | 내용 |
|---|---|
| `manifest.json` | 커밋/source/config/환경, 단계별 상태 |
| `tests.log` | 전체 테스트 실시간 기록 |
| `references.json` | A의 전체 선택값·경로·종료 참조 |
| `timing.jsonl` | warm-up 포함 120개 원시 episode |
| `timing_summary.json` | 지도별 중앙값·사분위수·C*/S*, C*/B, CERT/C* 비율 |
| `memory.jsonl` | 시간 측정과 분리한 24개 Python allocation 기록 |
| `summary.json` | 최종 시간 요약과 메모리 기록 |
| `failure-*.json` | 오류/불일치/중단의 traceback 및 가능한 상태 증거 |

주 비교는 C*/S*이다. 시간 비율 1 미만이면 C*가 빠르다. 지도 단위의 비율과 기하평균을 함께 보고, 일부 지도에서 느린 결과도 유지한다. 이 파일럿은 탐색적 연구이므로 새 GO/DROP 분류나 confirmatory 신뢰구간을 만들지 않는다.

시간에는 planner 호출만 포함한다. CERT의 occupied-delta 처리·인증·dependency 작성·forwarding 비용도 포함한다. A 참조 생성, 방법 간 검증, hashing, 이동과 physical sensing은 시간 밖이다. B/S*/C*에는 불필요한 CERT adapter나 work instrumentation을 넣지 않는다.

메모리는 초기 환경/첫 scan/planner 생성 후부터 종료까지의 별도 Python tracemalloc high-water 값이다. 이 구간에는 이동·arrival sensing·decision 검증/기록도 포함되며 process RSS 또는 planner 객체만의 크기와 다르다. 원시 지표 이름과 한계를 유지한다.

## 오류나 중단 시

부분 기록과 실패 폴더를 그대로 보존한다. 실패나 중간 종료한 측정에서 완료된 지도만 골라 성능을 요약하지 않는다. 수정 후 재실행은 새 커밋과 새 run ID로 수행하고, 재실행 이유를 기록한다. 종료된 측정 단계를 같은 run ID로 반복하거나 일부 반복만 바꾸는 기능은 없다.

강제 프로세스 종료로 `execution.lock`과 RUNNING 상태가 남으면 기존 폴더를 보존한 채 새 run ID를 사용한다. `TESTS_PASSED` 또는 `TIMING_DONE`까지 정상 완료했다면 같은 코드/환경에서 다음 단계만 이어갈 수 있다.

Experiment 1의 큰 로컬 원시 파일이나 `research_baseline_tests_20260929.log`는 이 runner의 필수 입력이 아니다. 새 PC는 이 브랜치의 코드와 커밋된 구조적 evidence만으로 실행할 수 있다.
