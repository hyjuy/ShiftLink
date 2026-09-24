# 빈 검색 결과 처리 — 2026-09-24

사용자 요청: 질의 검색 카드가 0개면 모델 호출 없이 no_knowledge 응답 반환.

## 구현 범위

- FixedPipeline이 도구 조회와 안전 카드 병합을 마친 뒤 query의 cards가 비었는지 확인한다.
- 비었으면 tool_results를 보존하고 AgentResponse(no_knowledge=True)를 반환한다. 모델·출력 validator·재시도는 실행하지 않는다.
- no_knowledge의 기본값은 False이며 JSON 직렬화/역직렬화를 지원한다.
- render_response는 "해당 지식 없음"과 답변 보류 이유를 표시한다.
- 인계 모드와 안전 카드만 남은 질의는 모델 호출을 유지한다.
- 관측값 전달 테스트는 기존에 빈 카드 fixture를 사용했으므로 카드 1개를 반환하게 조정했다. 이제 빈 결과를 정상 모델 호출 예제로 사용하지 않는다.

## RED / GREEN

```powershell
$env:PYTHONPATH = "$PWD/.test-deps"
python -m pytest tests/test_retrieval_response.py tests/test_router_pipeline.py -q -p no:cacheprovider --tb=short
```

RED: **6 failed, 87 passed**. 빈 카드에서 모델/validator가 호출됐으며 no_knowledge 필드가 없었다.

```powershell
$env:COVERAGE_FILE = "$PWD/artifacts/no-knowledge.coverage"
python -m coverage run --source=shiftlink.agent.pipeline,shiftlink.agent.response -m pytest tests/test_router_pipeline.py tests/test_retrieval_response.py tests/test_eval_harness.py -q -p no:cacheprovider --tb=short
python -m coverage report -m --fail-under=80
```

GREEN: **118 passed**. pipeline.py **96%**, response.py **98%**, 합산 **97% (285/293 statements)**. 실제 모델 없이 기존 평가 하니스 회귀 테스트까지 실행했다.

| 보장 | tests/test_retrieval_response.py |
|---|---|
| 빈 KB·적용 조건 False·제외 조건 True로 최종 카드가 0개면 모델 0회, 보류 표시·JSON 왕복 | test_query_without_cards_skips_model_and_renders_no_knowledge (3 cases) |
| 커스텀 출력 validator도 빈 질의 경로에서 호출하지 않음 | test_empty_query_does_not_invoke_custom_output_validator |
| 빈 인계는 기존 모델 호출 1회 유지 | test_empty_handover_still_calls_model |
| 일반 검색 0건이어도 안전 카드가 있으면 모델 호출·안전 표시 유지 | test_safety_only_search_is_not_treated_as_empty |

## 한계·다음 작업

- 카드가 있지만 질문과 무관한 경우, 유효 인용이 없는 모델 답변, 모든 카드의 조건이 미확인인 경우는 이 빈 결과 검사와 별개다.
- 모든 도구 호출은 게이트 전에 수행한다. 도구 오류를 지식 없음으로 숨기지 않는다.
- 실제 LLM, 브라우저, Jetson 실행은 검증하지 않았다. 다음 단계는 B와 출력·오류 계약 확인 후 모델 답변 파싱·인용 검증이다.
- 체크포인트 커밋은 생성하지 않고 RED/GREEN을 이 문서에 기록했다.
