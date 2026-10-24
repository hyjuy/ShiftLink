# HPU 온톨로지 1~2단계 구현·검증

일자: 2026-10-24 (Asia/Seoul). 원 계획: [HPU 확장 설계](../design/hpu-ontology-extension.md).
시작 HEAD: `a37547f81dad64f5d77ce692e5df86269f4362f5`와 기존 로컬 변경.
범위: 서비스에 연결하지 않는 공통 모델·HPU 진입점·오프라인 SQLite 어댑터.

## 구현과 사용

- `shiftlink/mes/incident_ontology.py`: `read_incident_bundle`, `project_incident`, `content_hash`.
- `shiftlink/mes/hpu_ontology.py`: `project_hpu`.
- `tests/test_hpu_ontology.py`: 서비스 fixture → 임시 DB/승인 복사본 → bundle → graph 검증.

`read_incident_bundle`은 사건 ID가 필수이고 SQLite `mode=ro` + 일관된 읽기 트랜잭션을 사용한다.
기존 테이블과 식별자를 선택 조회하며 원래 `MesStorage`를 초기화하거나 업무 데이터를 쓰지 않는다.
일지·질의는 각 `max_records`(기본 30, 1..100)로 제한하고 누락 범위는 `truncated`로 표시한다.
순수 projector는 최대 노드 1000개·관계 2000개를 반환하며 상한 초과 시 `truncated=true`다.

```python
from shiftlink.mes.incident_ontology import read_incident_bundle, project_incident
from shiftlink.mes.hpu_ontology import project_hpu

# catalog와 manifest는 해당 오프라인 자료에 대응함을 확인한 보존 자료다.
bundle = read_incident_bundle(
    "approved-copy.sqlite3", "INC-existing-id",
    source_namespace=manifest["source_namespace"],
    catalog=catalog,
    config_catalog_hashes=manifest["config_catalog_hashes"],
)
graph = project_hpu(bundle)
# 같은 어댑터/모델로 다른 유형을 선택할 수 있다.
other_graph = project_incident(bundle, equipment_type="PDP")
```

`config_catalog_hashes`는 `config_id → content_hash(보존 catalog)`의 출처 확인 정보다.
자동 추론이나 서명 검증 기능이 아니며 호출자가 승인된 자료 묶음의 대응을 확인해야 한다.
현재 마스터 해시를 모든 과거 config에 일괄 붙이면 안 된다. 확인 정보를 생략하면 추정 연결 대신
`unresolved`를 반환한다. `source_namespace`는 DB 경로가 아닌 고정 자료 ID다.

결과는 schema_version/equipment_type/scope/nodes/edges/unresolved/truncated/snapshot_hash를 가진다.
노드·관계는 출처 참조·내용 해시·주장 종류·검토 미평가 상태를 보존한다.
센서와 작업자 관찰, 작업자 운전 보고와 MES 판정을 분리한다. 작업자 이름은 복제하지 않고 원문 필드 참조만 남긴다.
같은 자산의 여러 구성 관측은 각 config를 보존하며, 열린 세션 단계는 내용 revision에 따라 ID를 바꾼다.
원본이 다른 조치 표현은 시간·문구가 비슷해도 합치지 않는다.

서비스 호출부·API·PDA·검색·게시 worker·기존 SQLite 스키마를 수정하지 않았다.
카드 초안/게시 데이터는 이 어댑터에서 읽지 않으므로 `DERIVED_FROM_INCIDENT`는 5단계의 미구현 관계다.
설계의 off/shadow/explain 설정도 아직 없다. 모듈을 명시 호출해야 동작한다.

## RED → GREEN 기록

| 단계 | 실제 실행 결과 | 체크포인트 |
|---|---|---|
| 최초 RED | 새 테스트 수집 시 `ModuleNotFoundError: No module named 'shiftlink.mes.incident_ontology'`, exit 1. 필요한 새 구현이 없는 의도한 실패 | `b43d6231` |
| 최초 GREEN | 센서와 작업자 관찰의 테스트 범위를 구분한 뒤 22 passed, 새 모듈 커버리지 96% | `e2cb294a` |
| 추가 RED | missing_run/evidence_config/record_incident, 동일 자산의 구성 변경, 단계별 센서 출처의 5건 실패. 23 passed | `e189899` |
| 추가 GREEN | 출처 충돌 차단·구성별 관측·단계별 센서를 보강해 28 passed in 5.40s, 커버리지 97% | `dd575c2` |

명령은 프로젝트 `.venv/Scripts/python.exe`의 `-m pytest tests/test_hpu_ontology.py -q`다.
초기 한 실패는 모든 Observation을 센서로 가정한 테스트의 오류였다. sensor_observation만 범위 검증하고
worker_report 관찰도 별도로 보존되는지 검사하도록 바로잡았다. 테스트를 삭제·비활성화하지 않았다.

## 보장하는 계약

| 보장 | 테스트 | 종류 |
|---|---|---|
| 실제 서비스 일지 → 원 자산/사건/질의/조치/결과 연결, 원 DB 불변 | `test_service_to_readonly_bundle_to_graph_preserves_originals` | 통합 |
| 같은 입력의 결정성·결과 격리·내용/namespace 변경 식별 | `test_projection_is_deterministic_independent_and_versioned` | 단위 |
| 오자산·구성/실행/사건 충돌·누락 시 추정 연결 차단 | `test_wrong_query_context_never_attaches_observations`, `test_incomplete_or_conflicting_source_context_stays_unresolved` | 단위 |
| HPU 코드 접두어가 아닌 유형 FK로 PDP에도 재사용 | `test_equipment_selection_uses_fk_and_common_projector` | 단위 |
| 다중 설비 조치의 임의 배분 차단 | `test_multi_equipment_actions_are_not_assigned_to_one_hpu` | 단위 |
| worker 보고·MES 판정 분리, 열린 세션 내용 버전 식별 | `test_worker_outcome_and_mes_verdict_are_separate_and_session_revision_changes_id` | 단위 |
| naive 시간·bad/missing 값·실패 표시를 성공/현재 근거로 승격하지 않음 | `test_raw_steps_missing_time_and_sensor_quality_are_not_upgraded` | 단위 |
| 단계별 센서의 정확한 원문 경로 | `test_session_step_measurements_have_exact_source_paths` | 단위 |
| 읽기 전용·없는 파일 생성 금지·조회/그래프 상한 표시 | `test_adapter_is_readonly_does_not_create_missing_files_and_reports_limits`, `test_adapter_truncation_is_explicit`, `test_graph_caps_never_leave_dangling_edges` | 통합/단위 |
| 실제 조치 세션이 포함된 SQLite 복사본도 동일 계약 | `test_real_resolution_session_is_read_from_an_offline_copy` | 통합 |

## 최종 실행과 한계

프로젝트 `.venv/Scripts/python.exe`로 실행했다.

- `python -m coverage run --data-file=.coverage-incident-ontology --source=shiftlink.mes.incident_ontology,shiftlink.mes.hpu_ontology -m pytest tests/test_hpu_ontology.py -q`
  → `29 passed in 11.93s`.
- `python -m coverage report --data-file=.coverage-incident-ontology -m`
  → 공통 모듈 279 statements/6 missed, HPU 진입점 3/0, 전체 **98%**.
  남은 비실행 분기는 관계 타입 오류 방어, 그래프 상한 도달 후 일부 분기, 특정 누락 유형이다.
- `python -m pytest tests/test_hpu_ontology.py tests/test_mes_storage.py tests/test_work_report_capture.py tests/test_work_report_followup.py tests/test_mes_query.py tests/test_knowledge_gap_loop.py tests/test_knowledge_graph_runtime.py tests/test_publication_ontology_integration.py -q`
  → `170 passed in 73.61s (0:01:13)`. 당시 신규 28개와 기존 142개다.
  이후 추가한 실제 세션/DB 복사본 통합 테스트까지 위 신규 29개 실행으로 확인했다. 이후 제품 코드는 변경하지 않았다.
- `python scripts/check_knowledge_publication.py`
  → `ok: true`, `errors: []`, `staged_python_checked: true`,
  `check_kind: metadata_and_syntax`, `history_semantics_evaluated: false`.

원본 서비스가 저장한 일지·질의·사건·조치 세션을 사용했으며 모델은 기존 결정적 fixture다.
28개 시점의 회귀와 29개 시점의 신규 실행은 겹치는 테스트를 포함하므로 단순 합산하지 않는다.

3단계 이후 shadow/API/게시/검색 연결, 브라우저·장비·실제 모델 검증은 범위 밖이다.
소스 카탈로그의 과거 대응 자료가 없으면 그래프 커버리지는 낮아질 수 있으며 미확인 사유를 그대로 남긴다.
