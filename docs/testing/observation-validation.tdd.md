# 관측값 구조 검증 — 2026-09-24

사용자 요청: 관측값 구조 검증부터 구현. 별도 계획 파일 없이 기존 요청 계약과 재현 사례를 기준으로 진행했다.

사용자 흐름: 질의에 잘못된 관측값이 들어오면 검색·모델 호출 전에 거부하고, 정상 관측은 값과 요청 단위를 보존한다.

## 변경

- router.py에 Observation(signal, value, unit)을 추가하고 추가 필드를 거부한다.
- QueryRequest가 list[Observation]을 받으며 공백 정리 후 중복 signal을 거부한다.
- pipeline.py는 검증된 관측 객체의 속성으로 검색용 dict를 만든다.
- 모델 호출 시그니처는 유지한다. B 인계 문서의 관측값 설명도 갱신했다.

## RED / GREEN

기존 `.test-deps`를 PYTHONPATH에 지정했다.

```powershell
$env:PYTHONPATH = "$PWD/.test-deps"
python -m pytest tests/test_router_pipeline.py -q -p no:cacheprovider --tb=short
```

RED: **10 failed, 10 passed**. 누락·공백·추가 필드·중복 신호가 거부되지 않았고, 공백 정리 및 unit 기본값 계약도 미구현이었다.

```powershell
$env:COVERAGE_FILE = "$PWD/artifacts/observation-validation.coverage"
python -m coverage run --source=shiftlink.agent.router,shiftlink.agent.pipeline -m pytest tests/test_router_pipeline.py tests/test_retrieval_response.py tests/test_eval_harness.py -q -p no:cacheprovider --tb=short
python -m coverage report -m --fail-under=80
```

GREEN: **94 passed**. router **100%**, pipeline **94%**, 합산 **96% (105/109 statements)**. 기존 재시도·커스텀 validator 경로 4개 statement는 이 테스트 조합에서 미실행이다.

| 보장 | tests/test_router_pipeline.py의 테스트 | 범위 |
|---|---|---|
| signal/value 누락, 빈 signal, 오타 필드, 빈 unit, 중복 signal을 거부하고 도구·모델 호출 0회 | test_invalid_observations_stop_before_tools_and_model | 요청→파이프라인 경계, 8개 입력 |
| 0·False·문자열·실수를 일반/안전 검색에 보존, 요청 단위는 모델에도 보존 | test_observations_reach_search_and_model_without_value_loss | 가짜 도구·모델 통합 |
| 명시적 null은 누락과 구분해서 보존 | test_observation_value_is_required_but_explicit_null_is_preserved | 요청 직렬화 |

## 제한과 다음 작업

- value의 타입 범위는 기존 object 계약을 유지한다. null·복합 값의 조건 비교 의미, 신호별 타입·물리 범위는 이번에 변경하지 않았다.
- unit은 요청에 보존하지만 검색 도구의 signal→value dict에는 전달되지 않는다. 단위 변환이나 서로 다른 단위 비교를 보장하지 않는다.
- 설비 ID 해소, 모델 출력 파싱, 빈 KB 처리, 실제 LLM·Jetson 실행은 별도 작업이다.
- 전체 테스트를 반복하거나 새 평가 하니스를 만들지 않고 영향받는 라우터·검색/응답·평가 하니스 테스트를 실행했다.
- RED/GREEN은 이 문서에 보존했다. 체크포인트 커밋은 생성하지 않았다.
