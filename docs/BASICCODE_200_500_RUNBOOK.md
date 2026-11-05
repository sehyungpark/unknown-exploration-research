# basiccode 추가 실험: 200·300·400·500

2026-11-05. 사용자가 직접 실행하는 Candidate 1의 scaling 실험 설정이다. 기존 실행기, A/B/C*, 공통 simulator와 생성기를 사용한다. 동일한 입력에서 전체 행동·최종 지도가 일치하면서 계산 횟수와 실행 시간을 줄이는지 평가하며, 느리거나 실패한 결과도 보존한다. 이 설정 준비 과정에서는 실험을 실행하지 않았다.

## 조건

| 항목 | 설정 |
|---|---|
| 지도 크기 | 200×200, 300×300, 400×400, 500×500 |
| 장애물 밀도 | 0.1, 0.3, 0.5 |
| seed | 42, 43, 44 |
| 알고리즘 | A, B, C* |
| 센서 반경 | 4 |
| 워밍업 / 시간 측정 | 알고리즘별 1회 / 5회 |
| 별도 메모리 측정 | 사용 |
| 지도 생성기 | connected_dominating_v1: 연결·관측 가능 scaffold, 목표 장애물 수 보장 |
| 권장 실행 | isolated, workers=1 |

크기별 9개 지도와 135개 시간 측정이다. 구조 검사·워밍업·메모리·일곱 sanity 환경까지 포함하면 크기별 237회, 네 크기 합계 36개 지도·540개 시간 측정·948회 탐사다. 실패/중단으로 다시 실행한 시도는 추가로 남는다.

새 설정은 기존 50/100/150 reduced 구성의 크기만 확장했다. 기존 기본 설정과 과거 100–500·밀도 다섯 단계 설정은 보존한다. 명시적 `--config` 없이 실행하면 여전히 50/100/150이 선택된다.

## 크기별로 나누는 이유

현재 실행기는 한 invocation의 모든 구조 검사를 완료한 뒤 시간 측정으로 넘어간다. 크기별 별도 설정을 사용하면 500 구조 검사를 기다리기 전에 200의 측정·분석·그래프까지 얻을 수 있다. 각 크기의 결과는 별도 폴더에 저장된다.

| 설정 파일 | 용도 |
|---|---|
| `configs/basiccode_200_v1.json` | 200만 실행 |
| `configs/basiccode_300_v1.json` | 300만 실행 |
| `configs/basiccode_400_v1.json` | 400만 실행 |
| `configs/basiccode_500_v1.json` | 500만 실행 |
| `configs/basiccode_200_500_v1.json` | 네 크기를 한 invocation으로 실행하는 선택지 |

마지막 통합 설정은 36개 지도와 540개 시간 측정, 총 885회 탐사다. sanity를 한 번만 수행해서 분리 실행보다 63회 적다. 모든 36개 지도의 구조 검사를 먼저 끝내야 하므로, 초기 실행에는 크기별 구성을 권장한다.

## 먼저 확인할 자원 제약

큰 지도의 실행 시간과 최대 RAM은 아직 검증하지 않았다. A는 많은 후보를 매 계획마다 전수 평가한다. C*의 `range_masks`와 `visible_mask`는 지도 전체의 셀 번호를 비트 위치로 쓰는 정수여서, 많은 후보를 캐시하면 메모리도 크게 증가할 수 있다. 따라서 처음에는 `--workers 1`로 큰 작업의 중첩을 줄인다. 이 값이 한 탐사의 시간/RAM 사용량을 보장하지는 않는다.

200 결과에서 자원 사용을 확인한 후 300/400/500을 진행한다. 결과가 느리다는 이유로 A를 생략하거나, 유리한 seed만 남기거나, 대기 시간이 큰 반복만 지우지 않는다. 크기별 결과를 나중에 한 그래프로 비교하려면 기기·소스·알고리즘·모드·입력 조건·시간 사용 가능 여부를 확인해야 한다. 현재 plot 명령은 한 invocation씩 집계한다.

## Windows: 코드 업데이트 및 기기 점검

기존 실험이 완료된 폴더에서 업데이트한다. 이전 실험을 같은 버전으로 이어 실행해야 한다면 그 폴더는 보존하고 새 clone에서 이번 실험을 시작한다. 재개는 커밋과 환경이 같아야 하므로, 진행 도중 소스를 업데이트하지 않는다.

```powershell
Set-Location "$env:USERPROFILE\unknown-exploration-basiccode"
git branch --show-current
git pull --ff-only origin codex/basiccode-benchmark
```

브랜치는 `codex/basiccode-benchmark`여야 한다. 가상환경이 이미 준비된 상태를 가정한다. 새 clone이면 [기본 실행 안내](BASICCODE_RUNBOOK.md)의 가상환경/패키지 설치부터 한다.

아직 schema 2를 실제 장치에서 검증하지 않았다면 [재측정 안내](BASICCODE_RERUN.md)의 작은 검증과 전원·중단 사전 점검을 먼저 직접 수행한다. 다음 명령은 성능 측정 없이 10분 동안 전원 보호와 대기 관측을 점검한다.

```powershell
.\.venv\Scripts\python.exe -m benchmarks.basiccode_power --seconds 600
```

수동 절전·복귀 등 정의된 중단을 감지하면 정상 시간 결과로 취급하지 않아야 한다. 짧은 점검은 장시간 완료를 보장하지 않는다. 본 측정에서는 같은 전원 조건과 코드 버전을 유지한다.

## 200부터 실행

```powershell
.\.venv\Scripts\python.exe -m benchmarks.basiccode_runner --config configs/basiccode_200_v1.json --mode isolated --workers 1 --run-id laptop-scaling-20261105-001-n200
```

새 PowerShell 창에서 같은 저장소로 이동한 뒤 상태를 확인한다.

```powershell
.\.venv\Scripts\python.exe -m benchmarks.basiccode_runner --run-id laptop-scaling-20261105-001-n200 --status
```

중단됐다면 소스/기기/설정/모드/작업자 수를 유지한 상태에서 같은 명령에 `--resume`을 붙인다. 기존 실행 창이 종료된 뒤 사용한다.

```powershell
.\.venv\Scripts\python.exe -m benchmarks.basiccode_runner --config configs/basiccode_200_v1.json --mode isolated --workers 1 --run-id laptop-scaling-20261105-001-n200 --resume
```

완료되어 채택된 체크포인트는 검증 후 재사용한다. 미완료 또는 대기 영향 등으로 채택되지 않은 지도별 시간 묶음은 새 시도로 재측정한다. 한 탐사 도중의 로봇 위치/cache에서 이어지는 방식은 아니다. 실패한 기록은 보존한다.

## 네 크기를 차례대로 실행할 때

200에서 자원 사용과 정상 완료를 확인한 후 사용할 선택지다. 한 크기가 실패/중단되면 다음 크기를 시작하지 않는다. 동일 태그로 다시 실행하면 존재하는 실행에는 `--resume`을 전달하므로, 코드·기기·모드 호환성 검사를 통과해야 한다. 새 독립 실험은 태그를 바꾼다.

```powershell
$batchTag = 'laptop-scaling-20261105-001'
foreach ($mapSide in @(200, 300, 400, 500)) {
    $experimentId = "${batchTag}-n${mapSide}"
    $configFile = ".\configs\basiccode_${mapSide}_v1.json"
    $runDirectory = Join-Path '.\results\basiccode\runs' $experimentId
    $resumeArgs = @()
    if (Test-Path -LiteralPath $runDirectory -PathType Container) {
        $resumeArgs = @('--resume')
    }
    & .\.venv\Scripts\python.exe -m benchmarks.basiccode_runner --config $configFile --mode isolated --workers 1 --run-id $experimentId @resumeArgs
    if ($LASTEXITCODE -ne 0) {
        throw "n${mapSide} 실행이 완료되지 않았습니다. 결과를 보존하고 해당 실행 상태를 확인하세요."
    }
}
```

한 번에 동시에 네 실험을 시작하는 명령은 아니다. 각 invocation에서 A/B/C*는 같은 지도/시작점/센서를 사용하고, 단독 시간 측정 조건을 유지한다.

## 결과와 그래프

예를 들어 200 결과는 다음 폴더에 저장된다.

```text
results/basiccode/runs/laptop-scaling-20261105-001-n200/
```

정상 완료 후 완전성·시간 사용 가능 여부를 확인한 집계와 그래프를 생성한다. 그림만 다시 만들 때는 다음 명령을 사용한다.

```powershell
.\.venv\Scripts\python.exe -m benchmarks.basiccode_plot .\results\basiccode\runs\laptop-scaling-20261105-001-n200
```

다른 크기는 config와 ID의 200을 300/400/500으로 바꾼다. 이전 v1 실행의 대기 영향 미확정 시간 기록은 새 schema-2의 정상 시간 측정으로 자동 편입하지 않는다.
