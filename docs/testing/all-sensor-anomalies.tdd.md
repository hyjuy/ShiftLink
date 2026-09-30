# 전체 센서 이상 수치 적용 검증

## 범위와 결과

요청: 현재 설비의 전체 센서에 이상 수치가 있는지 확인하고 누락을 추가한 뒤 서브에이전트로 검증한다.

활성 설비 10대의 센서 위치 46개 중 기존 시나리오가 명시적으로 이상 수치를 주입한 위치는 12개였다. 기존 9개 시나리오는 유지하고, 각 위치를 별도로 지정한 센서 시연 46개를 추가했다. HPU 6·PDP 3·CAU 3·GR 12·RT 13·CV 9개다. 같은 신호 이름도 설비 위치가 다르면 별도 검증한다.

- `ScenarioSpec.cause_equipment_id`는 선택 필드이며, 없는 기존 구성에서는 기존 capability 선택을 유지한다. 직렬화에도 지정한 경우에만 필드를 넣는다.
- 엔진과 운영 화면이 지정한 설비를 일관되게 사용한다. 없는·다른 capability의 설비를 첫 설비로 대체하지 않는다.
- 센서 시연은 `AL-SENSOR-ANOMALY`를 지정 설비에 생성하며 공급 관계 전파는 없다.
- 기존 승인 카드 연결은 변경하지 않고 신규 시나리오·알람을 신호 대응표의 `unlinked`에 등록했다.
- 정상 범위 표와 이상 수치 표를 [신호 계약](../guides/mes-card-signals.md)에 46개 위치 모두 기록했다.

## TDD 기록

| 단계 | 결과 | 커밋 |
| --- | --- | --- |
| 전체 센서·정확한 타깃 테스트 RED | 시나리오 미구현으로 48 failed, 1 passed | `0edb267` |
| 기본 구현 GREEN | 49 passed | `76981de` |
| 사용자 범위·화면 추가 검증 RED | 논리 정상값 1과 작은 압력 범위에서 2 failed, 2 passed | `4be666e` |
| 예외 수정 GREEN | 새 테스트 파일 53 passed | `e44498d` |

새 테스트는 `tests/test_mes_all_sensor_anomalies.py`다. 46개 실제 이상 관측값·단위·low/high·숫자 조건·정상 경계값 제외·알람·정상 복귀·다른 설비로의 오적용 방지를 확인한다. Node 운영 화면 모델에서도 46개 타깃과 다른 설비 강조 방지를 확인한다. 사용자 구성의 반대 논리값과 반올림 후 경계값 문제도 검증한다.

전체 검증: Python 3.10과 기존 프로젝트 의존성을 사용해 `coverage run --source=shiftlink.mes.scenarios.priority,shiftlink.mes.engine,shiftlink.mes.configuration,shiftlink.mes.contracts -m pytest -q tests --basetemp=artifacts/all-sensor-pytest-20260930-02 --tb=short` 실행 — **500 passed in 29.66s**. `coverage report --fail-under=80 -m` 통과: configuration 94%, contracts 100%, engine 96%, priority 95%, 합계 96%. 전체 프로젝트 커버리지가 아니라 지정한 변경 모듈 기준이다. 커버리지 데이터는 `artifacts/all-sensor-anomalies.coverage`에 저장했다.

서브에이전트가 초기 12/46 누락, 엔진·화면의 정확한 타깃, 기존 구성의 hash 보존, 수치의 범위·논리값·백분율을 독립 검토했다. 검토에서 발견한 사용자 범위 예외 2건은 RED를 재현한 뒤 수정했다.

## 해석과 한계

가상 정상 범위의 경계를 벗어난 시연용 수치이며 제조사 임계값·실제 고장 원인·작업 안전 판단이 아니다. 원인 정지에 따른 다른 운동 의존 센서의 0값은 명시적 이상 주입으로 세지 않는다. 기존 저장 구성은 보존하며 새 구성을 생성하면 `config_id`가 달라진다. 정상 범위가 없는 센서와 0/1 모두 정상인 논리 센서는 숫자 이상값 생성 대상에서 제외한다.
