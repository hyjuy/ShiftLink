# 모의 MES 산업 도메인 모델

이 구현은 `docs/data/reference/00_plant_and_relations.json`의 가상 냉연 코일 처리 라인 보조설비를 사용한다. 실제 압연 공정, PLC 인터록, 설비 용량을 검증한 모델이 아니다. 기존 기준정보와 Event/KnowledgeCard 계약은 변경하지 않는다.

## 소재 흐름과 UI 계약

코일은 `coil_id`, `equipment_id`, `segment_id`, `position`을 가진다. 설비와 구간은 기준정보의 `EQ-*`, `SG-*` ID이며 `position`은 현재 설비 내 0~1 위치다. 출측 소재를 입측으로 되돌리지 않는다. 출측 배출 시 `coil_exited` 이벤트를 남기고 입측이 비면 새 ID의 코일을 투입한다.

`material_flow` 관계를 따라 RT-01 → RT-02 → RT-03 → CV-01로 진행한다. 분기점은 기준정보 capacity가 큰 경로를 정상품 경로로 선택하므로 CV-02 스크랩 분기로 코일이 진입하지 않는다. 이 선택은 현재 단일 제품 데모의 명시적 가정이며 범용 생산 스케줄러가 아니다.

시연 용량은 설비당 코일 1개로 둔다. 이 숫자는 기준정보의 m/min 용량을 코일 개수로 변환한 값이 아니다. 다음 설비가 점유되었거나 대기/정지 상태이면 현재 설비 끝에서 기다린다. 이동은 material_flow의 lag_seconds를 시연 체류시간으로 사용하고 마지막 컨베이어는 10초로 가정한다. 코일 크기·설비 길이·운전 속도로 계산한 물리 이동은 아니다.

## 이상 영향

- 구동부 이상: GR-01 자체 고장, `drive`로 연결된 RT-01과 RT-02 대기. 출측의 기존 소재는 계속 배출될 수 있다.
- 출측 정체: CV-01 자체 이상, `interlock`으로 연결된 RT-03 대기. 앞선 설비 소재는 점유 제한으로 쌓이며 넘치지 않는다.
- 유압 공급 이상: HPU-01 자체 고장, `hydraulic_supply`로 연결된 RT-01/02/03 및 CV-01 대기. CV-02는 해당 공급 관계에 없으므로 직접 영향 대상이 아니다.
- 영향받은 설비는 `fault_level=normal`을 유지해 설비 자체 고장과 공급/하류 영향에 따른 대기를 구분한다. 대기/정지 설비의 rt_speed, cv_speed는 0이다.

이상 영향은 해당 시나리오 적용 tick에 즉시 반영한다. 구동·공급 관계의 lag_seconds와 유량 분배는 동적으로 계산하지 않는다. 유압 저하는 데모에서 안전 대기로 단순화했으며 기준정보 common_mode의 저속 운전 모델을 재현하지 않는다. 복구는 2 tick 안정화 후 정상으로 돌아가는 합성 전이다.

## 검증 기록

사용자 여정: 운영자가 코일 위치를 확인하고, 구동/유압/출측 이상을 적용했을 때 연결된 설비와 소재만 영향을 받는지 확인한 후 복구한다.

RED: `python -m unittest tests.test_mes_engine` 실행 결과 10개 중 2 실패, 1 오류. 누락된 equipment_id, GR-01의 RT-02 영향 누락, HPU-01의 CV-01 영향 누락을 재현했다.

GREEN: `python -m unittest tests.test_mes_engine tests.test_mes_integration tests.test_mes_storage tests.test_mes_contracts` 실행 결과 22개 통과. 실제 기준정보 ID, 일방향 이동/배출, 중복 점유 방지, 스크랩 분기 제외, 이상 전파, 출측 독립 이동, 출측 정체 중 소재 보존, 복구 배출, 초기화 및 기존 저장·관측 계약을 확인했다.

`python -m coverage --version`은 `No module named coverage`로 실패하여 커버리지 비율은 측정하지 못했다. UI 브라우저 검증은 협업 UI/UX 담당의 검증 기록을 참조한다. 커밋은 생성하지 않았다.
