# 카드 위치별 가상 MES 관측 신호

2026-10-01 사용자 요청: 카드에 필요한 센서값을 MES에 추가한다.

기존 ADDITIONAL_SIGNALS에 11종, 설비별 13개 측정 위치를 추가했다. 위치별 단위·정상 범위를 유지한 채 엔진 스냅샷, 카드 검색, 설비 지정 이상 시나리오, 복구 및 운영 화면으로 전달된다. 새 구조나 의존성은 추가하지 않았다.

## 검증 기록

- RED: `tests/test_mes_card_sensor_positions.py` 실행 결과 13 failed. 모두 설치 신호 누락에 대한 assertion 실패였다. 테스트 커밋 eaba4a0의 재현 테스트를 Python 3.12 환경에서 확인했다. 최초 환경 실행은 접근 문제로 실패했으며 유효한 RED 증거로 계산하지 않았다.
- GREEN: 동일 테스트 13 passed.
- 회귀: Python 3.12, PYTHONPATH=.test-deps에서 아래 명령 실행 결과 178 passed.

```text
python -m coverage run --data-file=artifacts/card-sensor.coverage --source=shiftlink.mes.scenarios.priority -m pytest tests/test_mes_card_sensor_positions.py tests/test_mes_all_sensor_anomalies.py tests/test_mes_configuration.py tests/test_mes_engine.py tests/test_mes_card_adapter.py tests/test_mes_http.py tests/test_mes_sensor_coverage.py tests/test_mes_symptom_screening.py -q
python -m coverage report --data-file=artifacts/card-sensor.coverage
```

변경 모듈 커버리지: 96% (45 statements, 2 miss).

| 보장 | 테스트 | 결과 |
| --- | --- | --- |
| 위치별 단위·범위, 정상 검색 상태 | test_mes_card_sensor_positions.py | PASS |
| 이상값 검색 전달·복구 | test_mes_card_sensor_positions.py | PASS |
| 개별 설비 지정, 운영 화면의 관련 측정값 표시 | test_mes_all_sensor_anomalies.py | PASS |
| 구성 직렬화·API·기존 계측·증상 판정 회귀 | 위 명령의 나머지 테스트 | PASS |

실제 센서 설치·통신 드라이버 연동을 검증한 것은 아니다. 저장된 과거 run 구성은 유지하고 새 실행부터 추가 신호를 사용한다. 새 범위는 시연 가정이다. 소음·기포·누유 위치·잠금/감압 기록은 별도 관찰·기록으로 유지한다. 회전 비율은 가상 관측 채널이며 실제 롤 회전수 계측으로부터 계산하는 기능은 포함하지 않는다.
