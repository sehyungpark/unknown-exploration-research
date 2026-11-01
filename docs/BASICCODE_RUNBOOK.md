# basiccode 실험 실행: Windows PowerShell / macOS

현재 실행 브랜치: `codex/basiccode-benchmark`. UNKNOWN mask 증분 관리와 A/B/C* 비교 실행기, 분석기, 그래프 생성기를 함께 포함한다. 기존 formal Experiment 2용 `src.evaluation.experiment_2_runner`와는 다른 실험이다.

## Windows 노트북: 처음 준비

### 덮개를 닫고 실행할 때

1. 충전기를 연결한다.
2. PowerShell에서 `control.exe powercfg.cpl`을 실행한다.
3. 왼쪽 **덮개를 닫으면 수행되는 작업 선택**에서 **덮개를 닫을 때 → 전원 사용 → 아무 것도 안 함**을 선택하고 저장한다.
4. 전원 옵션으로 돌아가 현재 전원 관리 옵션의 **설정 변경**에서 **전원 사용 → 컴퓨터를 절전 모드로 설정 → 해당 없음/안 함**으로 설정한다. 고급 전원 설정에 자동 최대 절전 항목이 있으면 전원 사용 시 사용 안 함으로 설정한다. 화면만 꺼지는 것은 괜찮다.
5. 실행 후 PowerShell 창은 열어 둔 채 덮개만 닫는다. 로그아웃/종료/재시작하면 프로세스가 중단된다. 책상처럼 통풍되는 곳에 둔다. 실험 후 절전 설정은 원하는 값으로 돌린다.

[Microsoft 덮개 동작 설정 안내](https://www.microsoft.com/en-us/windows/learning-center/how-to-use-external-monitor-with-laptop-closed). 실제 Windows 전원 설정은 사용자가 직접 변경하며, 이 저장소의 실행기는 전원 설정을 바꾸지 않는다.

### 코드 내려받기

기존 작업 폴더에 수정 중인 파일이 있다면 새 폴더로 clone한다. Python 3.13을 권장하며, 아래 명령은 저장소 최상위에서 실행한다.

```powershell
git clone --branch codex/basiccode-benchmark https://github.com/sehyungpark/unknown-exploration-research.git unknown-exploration-basiccode
Set-Location unknown-exploration-basiccode
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-basiccode.txt
```

가상환경 활성화 없이 실행 파일을 직접 호출하므로 PowerShell의 activation 정책을 변경할 필요가 없다. 그래프에만 Matplotlib가 필요하다. 실행기 자체는 Python 표준 라이브러리를 사용한다.

## 1. 작은 검증

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_basiccode_unknown_mask tests.test_basiccode_benchmark -v
.\.venv\Scripts\python.exe -m benchmarks.basiccode_runner --smoke --run-id laptop-check-20261102-001
```

테스트가 `OK`인지 확인하고 smoke 폴더에 그림이 생성되는지 확인한다. smoke 수치는 성능 결론에 사용하지 않는다. 이미 존재하는 run ID는 거부한다. 재실행은 `002`처럼 새 ID로 한다.

## 2. 노트북에서 실제 비교

```powershell
.\.venv\Scripts\python.exe -m benchmarks.basiccode_runner --config configs/basiccode_large_v1.json --run-id laptop-large-20261102-001
```

현재 기본 구성은 **100×100, 200×200, 300×300, 400×400, 500×500 × 장애물 밀도 0.1/0.2/0.3/0.4/0.5 × seed 42/43/44**의 75개 지도다. 센서 반경 4, 알고리즘별 워밍업 1회와 **시간 측정 5회**로 총 1125회 시간 측정(별도 정확성·워밍업·메모리·sanity 포함 1821회 탐사)을 한다. 같은 지도에서 A/B/C*를 순차 실행한다.

사용자가 선택한 연결·관측 가능 보장 생성기로 실제 장애물 칸 수를 목표 밀도에 맞춘다. 독립 무작위 장애물 분포와는 다른, 연결된 free scaffold를 사용하는 지도 계열이다. 모든 알고리즘이 동일한 생성기·지도·시작점을 공유한다. 지도/밀도별 결과와 그림을 저장하며 밀도별 패널로 비교한다.

노트북을 전원에 연결하고 다른 계산 작업과 동시에 실행하지 않는다. **이 대규모 설정의 실행 시간과 RAM 적합성은 아직 확인하지 않았다.** A의 전수 평가와 C*의 전역 인덱스 비트셋 때문에 500×500은 상당한 시간/메모리가 필요할 수 있다. 중단된 원시 기록은 유지되지만 자동 재개는 제공하지 않는다. 큰 실험은 사용자가 직접 실행하며 이번 수정에서 대신 실행하지 않았다.

알고리즘/실행기/설정에 변경 사항이 있으면 본 측정을 거부한다. 사용자 설정을 바꾸려면 기존 설정을 복사해 새 파일로 만들고, 조건을 정한 뒤 성능을 보기 전에 커밋한다. 이후 `--config configs/새파일.json --run-id 새ID`로 실행한다. 결과가 불리하다는 이유로 seed/metric을 바꾸거나 실패 지도를 제외하지 않는다.

## 3. 저장 결과 확인

```text
results/basiccode/runs/laptop-large-20261102-001/
  manifest.json          # 커밋, 실행 환경, 설정, 오류/완료 상태
  maps.json              # 모든 입력 지도, 시작점, seed, 지도 hash
  records.jsonl          # 원시 결과와 정확성 검사, 실패 포함
  records.csv            # 원시 결과 표
  summary.json           # 완전성 검사와 집계
  summary.csv            # 지도별/알고리즘별 통계
  figures/
    timing.png / .pdf
    speedup.png / .pdf
    exact_evaluations.png / .pdf
    python_memory.png / .pdf
```

```powershell
Get-Content .\results\basiccode\runs\laptop-large-20261102-001\summary.json
Invoke-Item .\results\basiccode\runs\laptop-large-20261102-001\figures
```

`summary.json`의 `valid`가 true여야 비교 결과가 완전하다. 속도 비율 A/B, A/C*, B/C*는 1보다 크면 분모 알고리즘이 빠르다. 경로/이동 비용은 개선 목표가 아니라 동일성 검증 항목이다. 그래프의 오차 막대는 지도 단위 bootstrap 95% 구간이며, seed 3개만으로 일반적인 우수성을 단정하지 않는다.

## 4. 탐사를 다시 돌리지 않고 그래프만 생성

```powershell
.\.venv\Scripts\python.exe -m benchmarks.basiccode_plot .\results\basiccode\runs\laptop-large-20261102-001
```

원시 기록을 읽어 집계/그림을 다시 만든다. 처음에 `--no-plots`로 측정만 한 경우에도 사용할 수 있다. 기록 누락/중복/실패가 있으면 정상 비교 그림을 만들지 않는다. Ctrl+C로 중단된 결과는 유지하며 자동 재개/덮어쓰기는 하지 않는다.

선택적으로 PowerShell 래퍼도 같은 명령을 제공한다. 가상환경이 있으면 자동으로 사용한다.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_basiccode.ps1 -Stage Check
powershell -ExecutionPolicy Bypass -File .\scripts\run_basiccode.ps1 -Stage Smoke -RunId laptop-check-20261102-002
powershell -ExecutionPolicy Bypass -File .\scripts\run_basiccode.ps1 -Stage Run -RunId laptop-large-20261102-002
```

## 나중에 iMac에서 실행

Python 3.13과 Git이 있는 상태에서 같은 브랜치를 clone하고 아래 명령을 사용한다.

```bash
cd unknown-exploration-basiccode
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements-basiccode.txt
.venv/bin/python -m unittest tests.test_basiccode_unknown_mask tests.test_basiccode_benchmark -v
.venv/bin/python -m benchmarks.basiccode_runner --smoke --run-id imac-check-001
.venv/bin/python -m benchmarks.basiccode_runner --config configs/basiccode_large_v1.json --run-id imac-large-001
```

Windows와 macOS 모두 같은 Python 실행기·설정·그래프 코드를 쓴다. 컴퓨터별 원시 실행 시간은 섞어서 집계하지 않는다. 아직 로컬 iMac 하드웨어에서 실행한 것은 아니며 CI에도 macOS 검증을 포함한다.
