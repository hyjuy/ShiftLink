# HPU 온톨로지 3단계 shadow 검증

일자: 2026-10-24 (Asia/Seoul). 시작 HEAD: `977f11843a3e126212ba6f85a436eb17f0e37d6f`.
계획: [HPU 확장 설계](../design/hpu-ontology-extension.md)의 3단계.
사용법: [shadow 실행 안내](../guides/hpu-ontology-shadow.md).

## 범위와 보존 계약

`ontology_shadow.py`와 HPU CLI를 추가했다. 공통 read-only bundle/projector를 재사용한다.
사용자 요구를 기존 계획의 승인된 격리 실행 방식으로 구현했으며 실시간 질의 hook이나 API를 추가하지 않았다.
원래 dirty worktree의 서버·저장·연구/UI 변경을 이 기능의 코드에 포함하지 않았다.

보장할 사용자 흐름:

1. 기본 off 또는 명시 off면 입력/출력 없이 disabled다.
2. 승인된 자료의 shadow 실행은 관계·미확인 사유·잘림·소요 시간을 독립 artifact로 확인할 수 있다.
3. shadow 실행 전후 기존 질의 payload/응답/파이프라인 호출 수와 업무 DB는 동일하다.
4. 잘못된 manifest·입력·투영·출력 실패도 업무 흐름에 전달하지 않는다.
5. 원문은 선택한 새 파일에만 기록하고 stdout은 요약으로 제한한다. 기존 파일은 덮어쓰지 않는다.

## RED/GREEN

- RED: `python -m pytest tests/test_ontology_shadow.py -q`
  → 미구현 모듈 `ImportError: cannot import name 'ontology_shadow' from 'shiftlink.mes'`, exit 1.
  체크포인트 `d856c5b`.
- 첫 실행은 11 passed/1 failed였다. 기존 projector가 다른 설비 선택에서 query의 미확인 사유를
  남기는데 테스트가 무조건 empty라고 가정했다. 미확인을 지우지 않고 unresolved와 empty 입력을
  각각 검사하도록 테스트를 바로잡고 partial 상태도 추가했다.
- GREEN: 신규 테스트 17개, `17 passed in 5.94s`. 체크포인트 `64f191a`.
- 커버리지 명령:
  `python -m coverage run --data-file=.coverage-ontology-shadow --source=shiftlink.mes.ontology_shadow,shiftlink.mes.hpu_ontology -m pytest tests/test_ontology_shadow.py -q`
  및 `python -m coverage report --data-file=.coverage-ontology-shadow -m`.
  shadow 실행기 100%, HPU 모듈 95%, 합계 **98%**(81 statements/2 missed).
  미실행 줄은 별도 기존 projector wrapper와 `__main__` 진입 줄이다. 실제 CLI는 subprocess로도 실행했다.

## 테스트 계약

| 보장 | `tests/test_ontology_shadow.py`의 테스트 | 종류 |
|---|---|---|
| 기본/명시 off의 읽기·투영·출력 차단 | `test_default_and_explicit_off_do_no_io` | 단위 |
| 연결/미확인/안정된 graph와 artifact 확인 | `test_shadow_records_connections_reasons_and_stable_graph`, `test_no_attestation_is_visible_as_unresolved_not_a_successful_connection` | 통합 |
| 빈 결과·미확인·부분 연결·잘림 구분 | `test_truncated_empty_and_unresolved_are_distinguishable`, `test_partial_diagnostics_keep_both_connections_and_unknowns` | 단위/통합 |
| 환경 변수와 명시 off 우선순위 | `test_environment_can_only_enable_separate_shadow_runner` | 단위 |
| 오류 메시지의 비밀 정보 비노출·업무 DB 불변 | `test_diagnostic_failures_are_safe_and_do_not_modify_business_data` | 통합 |
| 기존 출력/DB 덮어쓰기 금지 | `test_output_never_overwrites_existing_files_including_source_database` | 통합 |
| 실제 질의 입력/출력/파이프라인 호출 수·저장 불변 | `test_shadow_does_not_change_query_payload_results_calls_or_database` | 서비스 통합 |
| 실행 가능한 CLI와 요약/상세 분리 | `test_real_cli_writes_full_artifact_but_prints_only_summary` | CLI 종단 |
| off CLI·잘못된 인자/manifest 종료 코드 | `test_off_cli_ignores_unreadable_input_and_creates_nothing`, `test_cli_missing_or_bad_inputs_return_nonzero`, `test_cli_rejects_invalid_manifest_and_catalog_objects` | CLI |

## 기존 회귀와 확인 한계

관련 회귀 명령:

```text
python -m pytest tests/test_ontology_shadow.py tests/test_hpu_ontology.py tests/test_mes_storage.py tests/test_work_report_capture.py tests/test_work_report_followup.py tests/test_mes_query.py tests/test_knowledge_gap_loop.py tests/test_knowledge_graph_runtime.py tests/test_publication_ontology_integration.py -q
```

결과: **188 passed in 38.36s**.
`python scripts/check_knowledge_publication.py`도 `ok: true`, `errors: []`,
`staged_python_checked: true`로 통과했다. 이 검사는 metadata_and_syntax 범위이며
history_semantics_evaluated는 false다.
문서 상대 링크와 변경 Python 구문, 변경 파일의 공백 검사도 통과했다.

임시 DB·결정적 모델 fixture와 CLI를 사용했다. 운영 DB·Pi/Jetson·실제 모델·물리 진동은 검증하지 않았다.
서비스에 연결하지 않아 질의의 추가 작업/공유 잠금은 없지만, 같은 기기에서 별도 프로세스를 실행할 때의
CPU/IO 경합이나 p95 성능은 이번 테스트 결과로 보장하지 않는다.
4단계 설명 API 및 5단계 게시 연결은 미구현이다.
