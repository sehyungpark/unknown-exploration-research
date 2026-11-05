# Windows와 Colab에서 basiccode 재측정

200·300·400·500 추가 크기는 [전용 실행 안내](BASICCODE_200_500_RUNBOOK.md)의 명시적 설정을 사용한다. 아래의 무설정 기본 명령은 계속 50·100·150을 실행한다.

기존 실행을 종료한 상태에서 사용하는 실험 저장소 최상위로 이동하고 브랜치를 업데이트한다.

```powershell
Set-Location "$env:USERPROFILE\unknown-exploration-basiccode"
git pull --ff-only origin codex/basiccode-benchmark
.\.venv\Scripts\python.exe -m benchmarks.basiccode_power --seconds 600
```

마지막 명령은 전원 보호를 요청하고 10분 동안 대기 사건을 관측한다. 충전기와 덮개를 실제 측정 조건으로 두고 확인한다. 수동 절전·복귀를 별도로 시험하면 중단 감지 메시지가 나와야 한다. Windows에서는 Kernel-Power 사건 ID 42/105/107/506/507의 최신 기록과 절전 포함·제외 시계 차이의 변화(100 ms 초과)를 확인한다. 사건 하나만으로 실제 절전 시간을 추정하지 않는다. Linux에서는 BOOTTIME과 MONOTONIC 차이를 사용한다.

처음에는 소형 검증을 실행한다. 각 새 실행에는 고유한 이름이 필요하다.

```powershell
.\.venv\Scripts\python.exe -m benchmarks.basiccode_runner --smoke --run-id laptop-v2-check-001
```

검증 후 아래 명령은 기존 27개 지도와 알고리즘별 5회 시간 측정을 실행한다.

```powershell
.\.venv\Scripts\python.exe -m benchmarks.basiccode_runner --mode isolated --workers 2 --run-id laptop-v2-001
```

다른 창에서는 같은 폴더에서 `--run-id laptop-v2-001 --status` 옵션으로 마지막 시작 기록과 완료 묶음 수를 본다. 재개는 원래 명령에 `--resume`을 추가한다. 코드 버전, 설정, 기기, 모드 및 작업자 수가 일치해야 한다. 이전 v1 실행은 별도로 보관한다. Windows 래퍼에서도 Run, Resume, Status와 -Mode, -Workers를 사용할 수 있다.

단독 모드는 검증과 메모리 단계만 병렬로 수행한다. 동시 실행을 측정하려면 새 ID에 `--mode concurrent --workers 2`를 지정한다. 각 작업의 PID와 시작·종료 시각, 실제 결과, 단계 및 설정한 최대 동시 작업 수를 기록한다. 두 모드는 서로 다른 측정 조건이다.

각 탐사의 시작과 결과가 jobs 아래에 저장된다. 구조·메모리 검사는 방법별로 완료 처리한다. 시간 단계는 지도 하나의 워밍업과 A/B/C* 반복 전체가 통과해야 채택한다. 중단 시 기존 시도는 보존하고 해당 시간 묶음을 다시 시작한다. 결과 불일치는 별도 실패 표식으로 보존한다. 분석과 그래프는 채택된 전체 기록을 검증한 후 생성한다.

Colab에서는 `notebooks/basiccode_colab.ipynb`를 열고 CPU 런타임에서 위에서부터 실행한다. 소형 검증 후 새 RUN_ID와 SMOKE=False로 변경한다. 계산은 VM 로컬에서 수행하고 완료 묶음을 Drive에 ZIP으로 보관한다. 백업은 해당 작업들이 끝난 뒤 검증한다. VM이 회수되면 마지막 백업 이후 작업은 유실될 수 있다. 다른 호스트에서는 새 시간 실험 ID를 사용한다.
