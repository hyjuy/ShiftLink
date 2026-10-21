# 검수 완료와 실제 검색 가능 상태의 불일치

## Summary

2026-10-21 구현 과정에서 스키마 검증, 임베딩 완료 또는 작업 트리 테스트만으로 검색 반영을 확정할 수 없음을 확인했다.
실제 운영 사고 보고가 아니라 개발 중 반증 테스트와 커밋 대조에서 발견한 실패 기록이다.

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

## Detection

- `tests/test_publication_worker.py::test_placeholder_draft_cannot_pass_quality_even_when_schema_valid`
- `tests/test_publication_worker.py::test_rejection_during_embedding_cannot_resurrect_card`
- `tests/test_publication_worker.py::test_re_review_removes_live_pool_and_invalidates_inflight_answer`
- `tests/test_publication_worker.py::test_asset_change_and_other_installation_cannot_reuse_field_card`
- `tests/test_publication_worker.py::test_draft_changed_without_review_cannot_publish`
- `tests/test_publication_s30h.py::test_index_manifest_or_text_drift_cannot_enter_search`
- `tests/test_publication_s30h.py::test_corrupt_index_row_is_excluded_without_breaking_other_queries`
- `tests/test_embedding_contract.py::test_real_http_embedding_request_and_normalisation`
- `scripts/check_knowledge_publication.py`: 작업 트리·스테이징 Python 문법, S30h 모델, HTML 상태 옵션, 이 문서의 회귀 테스트 참조.

## Evidence

RED/GREEN 체크포인트와 검증 결과는 `docs/harness/knowledge-publication-adoption-20261021.md`에 기록한다.
결정적인 모델 픽스처의 성공을 실제 모델 측정과 혼동하지 않는다. 실제 모델·장비 확인에는 별도의 증거가 필요하다.
