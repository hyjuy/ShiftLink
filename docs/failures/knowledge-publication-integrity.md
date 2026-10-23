# 검수 완료와 실제 검색 가능 상태의 불일치

## Summary

2026-10-21 구현 과정에서 스키마 검증, 임베딩 완료 또는 작업 트리 테스트만으로 검색 반영을 확정할 수 없음을 확인했다.
실제 운영 사고 보고가 아니라 개발 중 반증 테스트와 커밋 대조에서 발견한 실패 기록이다.

2026-10-22 격리 장비 검증에서는 게시·검색 성공 후에도 답변의 출처와 과거/현재 구분이 깨지는 두 P0를 재현했다.
새 카드의 120분 관찰을 그 수치가 없는 인계 기록에 인용했고, 137분 과거 관찰 기록을 현재 MES 정지 상태로 부정했다.
수정·검증 결과는 `docs/testing/knowledge-publication-p0-fix-20261022.md`에 기록한다. 운영 배포와 구분한다.

## Root Cause

- 미완성 근무일지 후보에도 스키마를 만족하는 임시 절차가 있었다. 이전 검수 API는 스키마만 확인해 이 후보를 통과시킬 수 있었다.
- 카드 해시만 검사하면 임베딩 입력·청크·모델·prefix가 다른 상태를 감지하지 못했다.
- 임베딩 요청 중 반려되거나 설비 자산이 바뀌면 늦은 결과가 잘못 게시될 수 있었다.
- 변경 중인 파일의 일부 zero-context diff를 추려 스테이징하면 제외한 hunk의 줄 이동 때문에 코드가 다른 위치에 들어갈 수 있었다. 작업 트리는 정상이어서 작업 트리 테스트만으로 이 오류를 발견하지 못했다. `b4182db`의 잘못된 배치는 `98fdfb4`에서 바로잡았다. 이 과거 커밋은 단독 실행 기준으로 사용하지 않는다.

## Prevention

- 구조화 완료 여부와 임시 값 검사, 원본 사건 자산 결합, 명시적 심사·검수 감사 이력.
- 모델·문서/query prefix·차원·검수 리비전·내용·청크를 함께 검증. 손상된 row는 검색에서 제외하고 재처리한다.
- 완료 시 attempt/revision/hash 재검사와 트랜잭션 게시. 질의 종료 전 publication ticket 검증.
- 관련 코드·테스트·문서 drift check와 스테이징된 Python AST 검사. 부분 스테이징은 문맥을 보존하고 실제 index blob을 검사한다.

- 답변 수치는 질문이나 다른 인용 문장의 숫자로 정당화하지 않는다. 인용된 근거에 없으면 답변을 보류한다.
- 명시적인 구조화 근무일지 조치 이력 조회는 검색·judge를 통과한 검수 원문을 단계별로 보존한다.
  현재 MES 상태로 과거 작업자 관찰을 덮어쓰거나, 현재 작업 지시 질문을 이력 조회로 처리하지 않는다.
- 이력의 분 단위 조건은 전체 토큰으로 대조한다. 현재 작업의 가능 여부·판단을 함께 요청하면 MES·모델 판단 경로를 유지한다.
- 과거 인용을 제외한 뒤 남는 실행 지시·자산명이 끼어 있는 안전성 요청을 별도로 확인한다. 원본 카드와 저장 답변이 불변이어도 현재·미래 요청은 누락될 수 있다. 완료된 인용+진행 요청, 오늘 필터 교체 안전성, 내일의 교체 안전성을 대조군과 함께 검사한다.
- 2026-10-23 검증 하니스 보강은 실행 코드 수정이 아니다. `모레/다음 교대/나중에` 미래 표현과 과거 인용의 `적었던`도 미해결 표본에 포함한다. 명시적 오라클은 `tests/fixtures/field_history_scope_cases.json`에 두며, `known_issue` 표시는 통과 면제가 아니다.
- 같은 날 후속 로컬 수정은 이 미해결 16개 질문을 네 유형으로 구분한다: 과거절 뒤 실행 지시 5개, 안전성의 자산명/조사 6개, 미래 시점 3개, 완료된 보고 동사 2개. 완료한 과거 보고를 제외한 뒤 남은 요청을 검사하고, 시간 단서는 명사 인접 여부 대신 판단 시점으로 해석한다. 명시 완료형과 새 판단 지시를 구분하며 과거 원문·저장 경로는 변경하지 않는다. 원래 30개 오라클은 유지하고 엄격 challenge를 게시 CI에도 포함한다. 실제 결과와 한계는 `docs/testing/history-semantic-fix-20261023.md`에 기록한다.


- 2026-10-23 후속 감사의 신규 12개는 명시 제외 지시 5개, 완료·참조 지시 5개, 완료 인과절 1개, 사동 지시 1개다. 명령 문자열만으로 실행 요청을 정하지 않고 바로 뒤의 완료·참조·제외 범위를 확인한다. 이 범위 뒤의 독립 지시는 남긴다. `해줘서`의 완료 인과절과 `해줘요/해줘야/해줘도/해줘서는`를 대조하며, `진행시켜줘`도 판단 경로로 보낸다. `tests/test_field_history_residual_scope.py`가 12개 전체의 분류·서비스 경로와 이전 저장 답변 불변성을 검사한다. 원래 30개 오라클과 이전 실패 기록은 변경하지 않는다. 검증 결과는 `docs/testing/history-regression12-fix-20261023.md`에 별도로 기록한다.

- 2026-10-23 main 비교는 전체 통과 증가(203→221)가 현재 요청 통과 감소(135→126)를 숨길 수 있음을 확인했다. 고정 283개 질문 중 main의 현재·미래 요청 158개와 기존 수정본의 과거 원문 보존 95개를 별도 회귀 금지 기준으로 둔다. 같은 오라클을 `tests/fixtures/field_history_integration_cases.json`에 보존하고, 분류와 실제 게시 서비스에서 각각 검사한다. `main` 전체를 덮어쓰지 않고 기존 일반 판단 경로를 기본으로 유지한다.
- 후속 통합의 여섯 독립안은 고정 283개를 모두 통과했지만 서로의 신규 문장을 적용하면 모두 누락이 있었다. 완료·제외 범위를 문장 전체로 지우지 않고, 남은 각 절의 조회 목적과 독립 지시를 확인한다. 존대 연결형 `-주시고`를 인용형 `-라고`로 오인하지 않는다. 신규 교차 대조군과 심판 문장은 별도 fixture에 보존하며, 기존 전체 회귀와 실제 게시 서비스도 통과해야 한다. 같은 지시를 반복한 뒤 철회하는 모호한 한 문장은 원래 오라클·예측을 감사 자료에 보존하고 엄격 채점에서 제외한다.

## Detection

- `tests/test_field_history_integration.py::test_reaudit_scope_matches_four_family_oracle`: 2026-10-23 독립 감사의 150개 오라클을 고정한다. 신규 회귀30개는 조회동사·어미23, 완료보고2, 제외조사1, 제외문 앞 현재요청4다. 기존512 통과로 새 실패를 가리지 않으며 공유 미충족13개도 엄격 검사한다. 넓은 시간/제외문 제거와 조회 어휘/종결형 제한이 원인이었다. 과거 원문·저장 query는 별도 서비스 검사로 보존한다.

- `tests/test_publication_worker.py::test_placeholder_draft_cannot_pass_quality_even_when_schema_valid`
- `tests/test_publication_worker.py::test_rejection_during_embedding_cannot_resurrect_card`
- `tests/test_publication_worker.py::test_re_review_removes_live_pool_and_invalidates_inflight_answer`
- `tests/test_publication_worker.py::test_asset_change_and_other_installation_cannot_reuse_field_card`
- `tests/test_publication_worker.py::test_draft_changed_without_review_cannot_publish`
- `tests/test_publication_s30h.py::test_index_manifest_or_text_drift_cannot_enter_search`
- `tests/test_publication_s30h.py::test_corrupt_index_row_is_excluded_without_breaking_other_queries`
- `tests/test_embedding_contract.py::test_real_http_embedding_request_and_normalisation`
- `tests/test_s30h_publication_integrity.py::test_number_must_be_supported_by_its_cited_source`
- `tests/test_s30h_publication_integrity.py::test_runtime_abstains_instead_of_saving_a_wrong_numeric_citation`
- `tests/test_s30h_publication_integrity.py::test_history_preserves_each_step_and_worker_observation`
- `tests/test_s30h_publication_integrity.py::test_history_does_not_resurrect_a_judge_rejected_card`
- `tests/test_field_history_boundaries.py::test_published_history_rejects_wrong_duration`
- `tests/test_field_history_boundaries.py::test_published_mixed_request_keeps_mes_and_model`
- `tests/test_field_history_intent.py::test_published_past_decision_preserves_original`
- `tests/test_field_history_intent.py::test_published_current_paraphrase_uses_mes`
- `tests/test_field_history_request_scope.py::test_published_quoted_history_preserves_original`
- `tests/test_field_history_request_scope.py::test_published_conditional_and_future_request_keeps_mes`
- `scripts/check_knowledge_publication.py`: 작업 트리·스테이징 Python 문법, S30h 모델, HTML 상태 옵션, 이 문서의 회귀 테스트 참조.
- `tests/history_scope_challenge.py::test_published_scope_matches_semantic_oracle`: 명시 실행하는 엄격 의미 검사. 알려진 미해결 결함도 실패한다.
- `tests/test_field_history_evaluation.py::test_known_failure_never_becomes_semantic_success`: 하니스 성공과 제품 의미 성공을 분리한다.
- `tests/test_field_history_evaluation.py::test_semantic_oracle_kills_mutants_without_baseline_failure_credit`: 정상 오라클 대조군에 고장을 주입한다.
- `tests/test_publication_harness.py::test_history_verification_wiring_cannot_silently_drift`: 지침·워크플로 트리거·실행 목록의 누락을 검사한다.
- `tests/test_field_history_residual_scope.py::test_residual_history_preserves_verbatim_card_and_saved_answer`: 미래 표현이 있는 완료 이력·인용 속 지시·부정 요청의 원문을 보존한다.
- `tests/test_field_history_residual_scope.py::test_residual_request_keeps_original_question_and_mes`: 완료 보고 뒤 현재/미래 지시와 안전성 요청을 유지한다.

- `tests/test_field_history_integration.py::test_integration_scope_matches_fixed_oracle`: 같은 283개 질문과 명시 오라클로 main·로컬 장점의 동시 유지를 검사한다.
- `tests/test_field_history_integration.py::test_integration_scope_matches_cross_lens_oracle`: 독립안 교차 검사·심판의 명확한 신규 문장과 오라클을 별도로 고정한다.
- `tests/test_field_history_integration.py::test_main_requests_and_verbatim_history_survive_publication`: 게시 후 실제 서비스의 판단 전달·원문 응답·이전 저장 답변을 대조한다.
- `tests/test_field_history_integration.py::test_reaudit_scope_matches_four_family_oracle`: 기존 감사의 네 유형 회귀 30개와 공통 누락 13개를 포함한 150개 오라클을 그대로 유지한다.
- `tests/test_field_history_integration.py::test_postfix_independent_audit_oracle`: 독립 재감사의 76개 문장으로 새 분석 요청과 원문 복사·조회 존대형을 구분한다. 합계 통과가 현재 판단 누락을 가릴 수 없다.
- `tests/test_field_history_evaluation.py::test_each_reaudit_family_blocks_independently`: 네 유형의 대표 고장마다 독립적으로 의미 검사 실패가 발생해야 한다.
- `tests/test_field_history_evaluation.py::test_postfix_independent_oracles_cannot_drift`: 독립 재감사 오라클의 중복·설명 누락·라벨 형식·출처 손상을 거부한다.

## Evidence

RED/GREEN 체크포인트와 검증 결과는 `docs/harness/knowledge-publication-adoption-20261021.md`에 기록한다.
결정적인 모델 픽스처의 성공을 실제 모델 측정과 혼동하지 않는다. 실제 모델·장비 확인에는 별도의 증거가 필요하다.


## 기록 조회 문맥이 새 판단을 삼키거나 원문 조회를 거부하는 문제

원인: 과거 지시 인용·문서 재사용·완료 문맥을 넓게 제거하면 독립된 새 배정·계산을 잃는다. 반대로 정중형 읽기나 부정된 재해석을 새 판단으로 읽으면 원문 보존 경로를 잃는다. 기록에 이미 적힌 계산값과 새로 계산해 달라는 값도 구별해야 한다.

예방: 문맥 인증은 해당 절에만 적용하고 앞선 독립 요청 검사를 공유한다. 고정72 감사 오라클과 범위 대조12를 보존하며 양쪽 경로를 각각 검사한다. 실패를 제외·재분류하거나 모델 호출 성공만으로 원문 보존을 통과 처리하지 않는다.

검출: `tests/test_field_history_integration.py::test_bounded_closure_keeps_all_independent_oracles`, `tests/test_field_history_integration.py::test_main_requests_and_verbatim_history_survive_publication`, `tests/test_field_history_evaluation.py::test_closure_cannot_trade_new_requests_for_history`, `tests/test_field_history_evaluation.py::test_closure_oracles_and_independent_cohorts_cannot_drift`.

증거: [2026-10-23 안정화 보고서](../harness/history-stability-20261023.md). `python scripts/check_knowledge_publication.py --history-scope closure` 실패는 차단 상태를 유지한다.
