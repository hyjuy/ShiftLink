# HPU 5단계 게시 인용 연결 검증

일자: 2026-10-24 (Asia/Seoul). 시작 HEAD: `6a42e8dddb9efcf57b99a605cfa62dbe1f931aad`.
계획: [HPU 확장 설계](../design/hpu-ontology-extension.md) 5단계.
사용법: [설명 API](../guides/hpu-ontology-api.md#5단계-실제-인용-게시-카드-연결).

## 보존 계약과 구현

관리자는 실제 인용된 검수 카드와 그 원본 HPU 사건의 관계를 선택 조회한다.
게시 전·미인용·반려·재검수·자산 교체·출처 불일치 자료를 추정 연결하지 않는다.
기존 질의 payload·답변·검색 예산·원문을 유지하며 API 조회가 DB를 쓰지 않는다.

설명 API의 `query_id`를 생략하면 기존 4단계 결과다. 지정하면
`publication_ontology.connect`가 승인 복사본의 질의와 live 서비스 기록을 대조하고,
기존 `PublicationManager.still_current`와 검색 경로에서 추출한 순수 `validated_record`를 재사용한다.
연결은 CardVersion → DERIVED_FROM_INCIDENT이며 카드 원문이나 업무 기록을 복제·변경하지 않는다.
출처 일지의 정확한 record_index와 투영 해시, 사건·자산을 확인하고 같은 MES 잠금에서 최종 ticket/게시 행을 재검사한다.

새 질의는 기존 최종 ticket 검증 후 실제 인용 항목의 ticket을 query_log payload의 내부 메타데이터로 저장한다.
HTTP 응답 필드는 바뀌지 않는다. 기존 query_log·일지·후보 원문을 갱신하거나 ticket을 소급 생성하지 않는다.
과거 인용에 리비전 증거가 없으면 `citation_revision_unverified`로 보류한다.
질의 시각만으로 검수 리비전을 추정하는 방법은 최종 구현에서 사용하지 않는다.

## RED/GREEN 근거

1. `python -m pytest tests/test_hpu_publication_links.py -q --tb=short`:
   미구현 `publication_ontology` import 실패(exit 1). RED `dd412ad`.
2. 첫 구현은 7 passed/1 failed였다. 설명 도중 반려 hook이 fallback 생성에서도 두 번 반려하여
   예상 리비전 충돌을 냈다. 테스트를 실제 단일 변경으로 한정했다.
3. `test_legacy_citation_without_exact_ticket_is_not_inferred`는 ticket 없이 연결되는 실패를 재현했다.
   RED `43918e6`. 정확한 내부 ticket을 저장·대조한 뒤 신규 9개가 통과했다
   (`9 passed in 33.57s`), GREEN `0e8a418a`.
4. `test_origin_record_hash_must_match_the_projected_snapshot`는 투영 원본 리비전이 다른데
   연결되는 실패를 재현했다(1 failed in 8.19s). RED `a95c60e`.
   정확한 기록 해시 대조 후 전체 신규 테스트 통과, GREEN `6a1d856`.

```text
python -m coverage run --data-file=.coverage-hpu-publication --source=shiftlink.mes.publication_ontology -m pytest tests/test_hpu_publication_links.py -q --tb=short
python -m coverage report --data-file=.coverage-hpu-publication -m
```

결과: **14 passed in 62.83s**, 신규 연결 모듈 **92%**(113 statements/9 missed).
상한·누락 분기 일부는 이 모듈의 커버리지에 포함되지 않았다. 기존 전체 서버 커버리지 수치는 아니다.

## 테스트 보장

| 보장 | `tests/test_hpu_publication_links.py` | 종류 |
|---|---|---|
| 선택 조회·실제 인용 판본·기존 DB 불변 | `test_publication_link_is_opt_in_actual_citation_and_preserves_sources` | 서비스/HTTP/SQLite |
| 게시 전·미인용·없는 질의 차단 | `test_before_publication_or_without_citation_never_links` | HTTP |
| 반려 후 연결 제거·과거 답변 보존·페이지 해시 무효화 | `test_rejection_removes_links_but_preserves_old_answer_and_source` | 서비스/HTTP |
| 질의 중 변경의 기존 final ticket guard 유지 | `test_rejection_during_query_keeps_existing_final_ticket_guard` | 서비스 |
| 설명 생성 중 반려 후 final 재검사 | `test_rejection_during_projection_rechecks_ticket` | HTTP/변경 hook |
| 인덱스 변조 제외·수리/쓰기 없음 | `test_changed_index_is_excluded_without_repairing_or_writing` | SQLite/HTTP |
| 승인 복사본 질의 원문 일치·과거/신규 검수 리비전 구별 | `test_approved_copy_must_match_live_query`, `test_later_review_cannot_relabel_old_citation_as_new_revision`, `test_legacy_citation_without_exact_ticket_is_not_inferred` | 서비스/HTTP |
| 자산 교체·다른 원 사건·일지 불일치 제외 | `test_asset_and_origin_boundaries`(3개) | 서비스/HTTP |
| off/shadow/explain에서 질의 입력·응답 동일 | `test_query_inputs_and_answers_are_identical_across_modes` | 실제 파이프라인 fixture |
| 투영된 원문 리비전 일치 | `test_origin_record_hash_must_match_the_projected_snapshot` | HTTP/투영 hook |

## 기존 회귀와 필수 검사

```text
python -m pytest tests/test_ontology_api.py tests/test_ontology_shadow.py tests/test_hpu_ontology.py tests/test_hpu_publication_links.py tests/test_publication_worker.py tests/test_knowledge_publication.py tests/test_publication_s30h.py tests/test_s30h_publication_integrity.py tests/test_publication_ontology_integration.py tests/test_knowledge_gap_loop.py tests/test_mes_query.py tests/test_work_report_capture.py tests/test_work_report_followup.py tests/test_publication_browser.py -q --tb=short
```

결과: **237 passed in 192.09s**. 기존 게시 단위·HTTP·S30h·인용·반려·실제 브라우저 검사를 포함하며
이 실행에서 skip/fail은 없었다. 브라우저는 로컬 HTTP와 명시적인 임베딩 fixture를 사용했다.

`python scripts/check_knowledge_publication.py --history-scope stability`는
분류 의미 검사 **72/72, semantic_failed: 0, decision: pass**였다.
`python -m pytest tests/test_field_history_integration.py -q --tb=short`는
**909 passed in 34.85s**였다. 이력 라우팅 코드는 변경하지 않았다.
기본 게시 metadata/스테이징 구문 검사는 구현 체크포인트에서 `ok: true`로 통과했다.
마무리의 `python scripts/check_knowledge_publication.py`도 `ok: true`, `errors: []`,
`staged_python_checked: true`로 확인한다. 이 기본 검사는 metadata_and_syntax이며
history_semantics_evaluated는 false다. 위 의미 검사·통합 테스트와 구분한다.
문서 상대 링크·변경 Python 구문·공백 검사도 통과했다.

## 한계

임시 SQLite·실제 로컬 HTTP·결정적 임베딩/판정 fixture를 사용한다.
운영 DB·Jetson/Pi·실제 모델·배포·운영 p95 성능을 검증하지 않았다.
설명 조회는 정합성을 위해 MES 잠금을 사용하며 부하 비용은 별도 측정 대상이다.
실시간 질의 응답의 온톨로지 확장과 검색 후보 추가는 포함하지 않는다.
기존 서버·저장·UI의 무관한 dirty 변경을 정리하거나 체크포인트에 포함하지 않았다.
