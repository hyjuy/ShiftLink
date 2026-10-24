# HPU 온톨로지 4단계 설명 API 검증

일자: 2026-10-24 (Asia/Seoul). 시작 HEAD: `b19845dde38eda9cdc47124fa57b1deb394eee38`.
원 계획: [온톨로지 확장 설계](../design/hpu-ontology-extension.md) 4단계.
사용법: [API 계약](../guides/hpu-ontology-api.md).

## 사용자 흐름과 구현

관리자는 승인 자료의 사건별 HPU 관계와 미확인 사유를 인증된 GET으로 조회한다.
기존 질의·검색·답변은 같은 입력·응답·모델 호출 수를 유지한다.
기본 off/shadow에서는 이 HTTP 라우트로 자료를 읽을 수 없다.

`_Handler.do_GET`의 별도 라우트가 `ontology_api.explain`을 호출한다.
관리자 인증 후 명시된 승인 복사본·카탈로그·manifest로 기존 `run_shadow`를 호출하고
그래프를 해시 결합 페이지로 반환한다. 서비스 DB 자동 선택·업무 쓰기·검색 호출은 없다.
원래 dirty worktree의 서버·저장·계정·UI 변경은 이 기능 체크포인트에 포함하지 않았다.
서버는 HEAD 원문에 새 라우트만 삽입한 문맥 포함 패치를 스테이징하고 필수 구문 검사를 통과했다.

## RED / GREEN

- RED: `python -m pytest tests/test_ontology_api.py -q --tb=short`.
  `ImportError: cannot import name 'ontology_api' from 'shiftlink.mes'`, exit 1.
  체크포인트 `43b9bda`.
- 최초 GREEN: 같은 명령으로 **11 passed in 24.25s**. 체크포인트 `f346e61`.
- 격리·페이지 재조립·출처 변경·잘림·오류 대조군을 추가했다. 첫 확장 실행은
  13 passed/1 failed였다. 테스트가 Asset의 위치 식별자를 `equipment_id`로 읽었지만
  실제 자산 계약은 `asset_id`다. 테스트를 실제 계약에 맞게 고쳤고 실행 코드는 변경하지 않았다.
- 최종 신규 검증:

```text
python -m coverage run --data-file=.coverage-ontology-api --source=shiftlink.mes.ontology_api -m pytest tests/test_ontology_api.py -q --tb=short
python -m coverage report --data-file=.coverage-ontology-api -m
```

**14 passed in 43.05s**, 신규 설명 모듈 **100%**(49 statements, 0 missed).
이 수치는 대형 기존 서버 전체의 커버리지가 아니다. 새 라우트는 실제 HTTP 요청으로 실행했다.

## 테스트 보장

| 보장 | `tests/test_ontology_api.py` | 종류 |
|---|---|---|
| off/shadow의 자료 읽기 차단 | `test_off_and_shadow_do_not_read` | HTTP |
| 무토큰·잘못된 토큰·작업자 역할 차단 | `test_authentication_before_data_access` | 실제 계정/HTTP |
| 연결·미확인 사유·scope·업무 DB 불변·없는 사건 | `test_graph_scope_reasons_and_readonly` | SQLite/HTTP |
| 후속 해시 필수·해시 불일치 409·다음 페이지 | `test_paging_requires_same_snapshot` | HTTP |
| 상한 밖/중복/알 수 없는 인자 거절 | `test_bad_parameters` | HTTP, 6개 대조군 |
| 파일 오류의 내부 경로 비노출·질의 payload/응답/호출 수 불변 | `test_safe_unavailable_and_query_unchanged` | 서비스/HTTP |
| 다른 설비 사건의 관찰 원문·자산 누출 방지 | `test_other_equipment_incident_does_not_leak` | 서비스 작성/HTTP |
| 모든 페이지 재조립·출처 namespace 변경 후 해시 거절 | `test_all_pages_reassemble_and_changed_source_is_rejected` | HTTP |
| 잘림 표시·투영 실패·잘못된 manifest | `test_projection_errors_truncation_and_bad_manifest` | fixture/HTTP |

## 관련 회귀와 한계

관련 회귀 명령:

```text
python -m pytest tests/test_ontology_api.py tests/test_ontology_shadow.py tests/test_hpu_ontology.py tests/test_mes_storage.py tests/test_work_report_capture.py tests/test_work_report_followup.py tests/test_mes_query.py tests/test_knowledge_gap_loop.py tests/test_knowledge_graph_runtime.py tests/test_publication_ontology_integration.py tests/test_pda_accounts.py tests/test_mes_handover_http.py -q --tb=short
```

결과: **203 passed / 1 failed in 161.02s**.
실패는 기존 `MesStorageTests.test_separate_processes_read_pending_and_preserve_concurrent_writes`의
`store initialization timed out`이며 자식 프로세스의 최초 ready 신호가 10초 내 오지 않았다.
새 API·기존 질의·온톨로지·게시 검색·계정·HTTP 검사는 이 묶음에서 통과했다.
해당 테스트를 코드·제한 시간 수정 없이 단독 재실행한 결과 **1 passed in 4.78s**였다.
일시적 초기화 지연 가능성이 있으나 원인을 확정하지 않았고 최초 실패를 성공으로 바꾸어 기록하지 않는다.
`python -m pytest tests/test_mes_storage.py -q --tb=short`로 저장 모듈 전체를 재실행한 결과도
**7 passed in 6.53s**였다. 통합 묶음 전체를 재실행한 결과로 대체하지 않는다.

`python scripts/check_knowledge_publication.py`는 `ok: true`, `errors: []`,
`staged_python_checked: true`로 통과했다. metadata_and_syntax 검사이며
history_semantics_evaluated는 false다. 문서 상대 링크·변경 Python 구문·공백 검사도 통과했다.

임시 SQLite·실제 로컬 HTTP·결정적 모델 fixture를 사용했다.
운영 장비·실제 모델·배포·부하 성능·PDA UI는 검증하지 않았다.
인증 범위는 관리자 전용이며 작업자별 원문 권한 확장은 포함하지 않는다.
자료는 승인 복사본 기준이므로 실시간 운영 사건의 자동 설명과 다르다.
게시 카드 연결과 검색 후보 활용은 후속 단계다.
