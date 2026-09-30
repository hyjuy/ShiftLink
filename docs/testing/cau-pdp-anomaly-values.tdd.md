# CAU·PDP 가상 이상 수치 적용 검증

## 요청과 범위

보강 신호 표의 구체적인 가상 이상 수치를 MES 시나리오에도 적용한다. 기존 정상 범위는 유지하고 제조사 임계값이나 실제 정비 절차로 주장하지 않는다. 서브에이전트가 수치·검색 조건·전파·복귀·과거 구성 보존을 독립 검토했다.

- `cau_supply_fault`: `air_pressure=450 kPa`, `air_flow=70 L_min`, `compressor_current=22 A`.
- `pdp_trip`: `bus_voltage=90 pct`, `bus_current=55 A`, `breaker_trip=1 bool`.
- 기존 승인 카드의 연결은 변경하지 않고 신규 시나리오·알람·대기 사유를 신호 대응표의 `unlinked`에 기록한다.

## RED → GREEN

- RED 커밋 `69e3c33`: `python3.10 -m pytest -q tests/test_mes_utility_scenarios.py --tb=short` — 2 failed. 두 시나리오가 없어 `unknown scenario: cau_supply_fault` / `unknown scenario: pdp_trip`으로 실패했다.
- GREEN 커밋 `1ab150b`: 아래 관련 검증 — 62 passed. 기존 시나리오/센서 확장·검색 어댑터·신호 대응표·복구·구성 보존 검증을 포함한다.

```powershell
python3.10 -m pytest -q tests/test_mes_utility_scenarios.py tests/test_mes_sensor_coverage.py tests/test_mes_card_adapter.py tests/test_mes_signal_map_runtime.py tests/test_mes_recovery.py tests/test_mes_configuration.py --tb=short
```

| 보장 | 검증 | 결과 |
| --- | --- | --- |
| 이상 관측값 6개와 low/high가 숫자 조건으로 전달되고 정상 경계값은 이상 조건에서 제외됨 | `test_mes_utility_scenarios.py` | 통과 |
| 고장 중 수치 유지, 복귀 2 ticks 완료 후 정상 범위·알람 해제 | `test_mes_utility_scenarios.py` | 통과 |
| 직접 공급 관계의 알람·대기와 신호 대응표 정합성 | `test_mes_signal_map_runtime.py` | 통과 |
| 기존 복구 조치와 저장된 과거 구성 보존 | `test_mes_recovery.py`, `test_mes_configuration.py` | 통과 |

독립 검토자는 새 시나리오·신호 대응표·복구 테스트를 별도 실행해 14 passed를 확인했다. 수정된 파일의 `git diff --check`도 통과했다.

push 전 전체 프로젝트 검증: `python3.10 -m pytest -q tests --basetemp=artifacts/utility-push-pytest-20260930-01 --tb=short` — **447 passed in 11.10s**. push 대상 커밋 차이에 대한 `git diff origin/mes/develop...HEAD --check`도 통과했다. 로컬 테스트 결과이며 원격 CI 결과를 뜻하지 않는다.

## 커버리지와 한계

동일한 62개 검증을 `coverage run --source=shiftlink.mes.scenarios.priority -m pytest`로 실행하고 `coverage report --fail-under=80 -m`으로 확인했다. 대상 `priority.py`는 21 statements, 0 missed, **100%**다. 커버리지 파일은 `artifacts/utility-scenarios.coverage`에 저장한다. 전체 프로젝트 커버리지를 뜻하지 않는다.

시뮬레이션 직접 관계만 전파하며 시간 지연·연쇄 전파를 새로 구현하지 않았다. 신규 구성의 `config_id`는 변경된다. 기존 승인 카드 생성·채택, 제조사 적용성 승인, 실제 전기작업 안전 판정은 이 변경에 포함하지 않는다.
