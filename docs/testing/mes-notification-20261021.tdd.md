# D18 알림 묶음 — TDD 근거

사용자 여정은 원래 진단 경보를 보존하면서 반복 알림을 줄이고, 새 고장의 첫 알림 손실을 숨기지 않는 것이다. [사전 등록](../research/mes-notification-prereg-20261021.md), [결과](../research/mes-notification-result-20261021.md).

1. 테스트를 먼저 작성해 `ModuleNotFoundError: No module named 'scripts.mes_notification_review'` RED를 확인했다. 체크포인트 `6f8f579`.
2. 최소 구현 뒤6검사 GREEN. 독립 검토자가 run 경계 종료 trace 누락을 찾아 반례를 추가했다. `IndexError: list index out of range` RED를 확인한 뒤 run_end closure와 상태 전이 균형 검사를 구현했다.
3. 알림 집계 재계산, 선행 오경보가 첫 탐지를 가리는 반례, gap 뒤 알림 증가, 비running 양성 정책을 보강한 **10검사 통과**. 구현 체크포인트 `25f1bea`.
4. 관련 기존 회귀까지 **48검사 통과**,27.459초. 고정 runtime을 첫 import 경로에 놓고 아래6모듈을 같은 unittest loader로 수집했다.

```powershell
.venv/Scripts/python.exe -m unittest tests.test_mes_diagnostic_contract tests.test_mes_diagnostic_review tests.test_mes_research_runtime tests.test_mes_notification_review tests.test_evaluate_mes_fault_models tests.test_mes_ewma_release_review -q
```

| 반례/보장 | 결과 |
| --- | --- |
| quiet2초는 병합,3초는 새 incident | PASS |
| 결측은 quiet가 아니며 연속 불완전 양성은 재알림 폭주 없음 | PASS |
| gap/비running/run 경계는 interrupted, resolved와 구별 | PASS |
| 다른 설비의 결측으로 로컬 상태를 초기화하지 않음 | PASS |
| 가까운 새 고장 또는 선행 오경보로 첫 알림이 사라지면 보류 | PASS |
| 같은 episode의 재시작만 줄이고 첫 시각은 보존 | PASS |
| trace 누락과 집계 변조를 거부 | PASS |
| gap 때문에 원래 시작 수보다 알림이 늘면 보류 | PASS |
| 마스크에 없는 설비와 inactive raw-positive는 명시 거부 | PASS |
| 함수 호출 뒤 원래 raw 경보 집합 보존 | PASS |

실제 개발 실행도 동일 frozen 소스로10검사를 먼저 통과한 뒤 한 번 평가했다. 개발 통과 후 신규54사건 확인에서도 원래 경보/strict dict 동일, 이전에 탐지한 사건별 첫 알림 시각 동일, 미일치 알림 감소 관문이 모두 통과했다. 신규 확인 전에 독립 검토가 provenance 연결과 출력 거부를 확인했다.

Python3.13 stdlib `sys.monitoring` local LINE으로 unit+실제 개발 실행의 줄을 수집했다. 새 파일 실행 가능204줄 중179줄, **87.745%**다. [원본 coverage](../../output/mes-notification-coverage-20261021.json), [동결 실행 harness](../../output/mes_notification_coverage_20261021.py). 실행 소스 SHA와 커밋 소스의 동일성을 확인했다. branch 커버리지는 미측정이며 실제 관측 단절·실측 고장·운영 배포 검증은 남아 있다.
