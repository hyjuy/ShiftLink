# H5 — PDP-01 측정점 결정 (2026-10-02)

결정: `breaker_trip`을 PDP-01 (`EQ-0002`)의 `bool` 상태 접점 측정점으로 포함·유지한다(`0` 정상, `1` 트립); 단락 원인이나 무전압 확인을 대신하는 신호로 해석하지 않는다.

근거: `shiftlink/mes/scenarios/priority.py`의 `ADDITIONAL_SIGNALS['PDP']`에 이미 등록돼 있고, `shiftlink/mes/signal_semantics.py`에 접점 의미가 정의돼 있다. `shiftlink/mes/symptoms.py`의 `pdp_trip`은 트립 접점과 전류 소실을 함께 다룬다. 새 측정점 구현 변경은 필요 없다.

검증: `$env:PYTHONPATH='tmp/card-review-deps;.test-deps'; python -m pytest tests/test_mes_sensor_coverage.py tests/test_mes_scenario_criteria.py -q` → **17 passed, 10 subtests passed**. 합성 MES의 측정점 포함·bool 판정 검증이며 실제 PDP 하드웨어 접점 연결을 확인한 결과는 아니다.
