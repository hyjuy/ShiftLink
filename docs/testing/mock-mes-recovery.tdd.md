# MES 조치·복귀 / 모의 부품 내구도 검증

사용자 요청에서 여정을 도출했다: 우선 후보 4종 선택 → 조치 단계 확인 → 순서대로 완료 → 복귀 진행 → 정상화 확인. 부품별 모의 건전도·운전시간·정비 이력과 기록 재생을 포함한다.

## RED

- `python -m unittest tests.test_mes_recovery`: 초기 6개 테스트에서 9개 실패(subtest 포함). 시나리오 4종과 components 필드가 없음을 확인했다. 체크포인트 `2a14de4`.
- `python -m unittest tests.test_mes_recovery_web`: `recoveryView is not a function`으로 실패. 체크포인트 `f8e6244`.
- 기존 진동 이상에서 새 과열 시나리오로 전환했을 때 알람 코드가 `AL-DRV-VIB`로 남는 추가 재현을 확인하고, 코드 변경 시 이전 알람을 해제하도록 수정했다.

## GREEN

PowerShell에서 `$env:PYTHONPATH = '.test-deps'` 설정 후:

```text
python -m coverage run --source=shiftlink.mes -m pytest -q tests/test_mes_recovery.py tests/test_mes_recovery_web.py tests/test_mes_engine.py tests/test_mes_configuration.py tests/test_mes_integration.py tests/test_mes_http.py tests/test_mes_server.py tests/test_mes_storage.py tests/test_mes_contracts.py tests/test_mes_web.py tests/test_mes_ui_layout.py
python -m coverage report -m
```

결과: **94 passed**, MES Python 전체 **92%**, 엔진 **96%**, 신규 시나리오 정의 **100%**. Windows 임시 SQLite 파일에 대한 샌드박스 접근 실패는 승인된 동일 테스트 재실행에서 해소했다.

| 보장 | 검증 |
| --- | --- |
| 미완료 조치·역순 조치·시나리오 변경으로 복귀 우회 불가 | test_mes_recovery.py |
| 조치 완료 → 준비 → 안정화 → 정상 복귀 | test_mes_recovery.py, 실제 HTTP test_mes_http.py |
| 영향 코일 보류 중 이동·배출 차단, 해제 후 배출 | test_mes_recovery.py |
| 고장 신호와 부품 손상은 대상 설비에만 적용 | test_mes_recovery.py |
| 운전 시 건전도 감소, 일시정지 시 불변, 정비 부품만 회복 | test_mes_recovery.py |
| 반복 조치 중복 정비 방지, 새 실행은 완료 상태 초기화 | test_mes_recovery.py |
| 기록 재생에 복구 단계·부품 상태 보존 | test_mes_recovery.py, test_mes_http.py |
| 기본 구성 업그레이드 시 과거 구성 보존 | test_mes_recovery.py |
| 다음 단계 버튼만 노출, 재생은 조치 불가, 건전도 meter·문자 상태 | Node를 호출하는 test_mes_recovery_web.py |
| 기존 엔진·구성·저장·관측 경계·화면 계약 회귀 | 나머지 MES 테스트 |

## 남은 한계

- 브라우저 도구의 `iab`는 사용 불가, 연결된 브라우저 목록도 비어 있어 실제 브라우저 클릭 E2E와 화면 스크린샷 검사는 수행하지 못했다. HTML 계약·Node 동작·HTTP 통합 검증으로 확인한 범위와 구분한다.
- Python 커버리지는 JavaScript의 커버리지 수치가 아니다.
- 물리적 정비 성공, 냉각 동특성, 실제 부품 수명은 검증 대상이 아니다. 가정은 [기능 설명](../guides/mock-mes-recovery.md)에 기록했다.
- 기존 사용자의 미커밋 화면 변경이 있어 UI 파일은 작업 트리에 보존하며 백엔드·신규 테스트·문서만 GREEN 체크포인트 대상으로 삼는다.
