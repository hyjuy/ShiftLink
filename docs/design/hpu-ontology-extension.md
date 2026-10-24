# HPU 자산–관측–사건–조치–결과 온톨로지 확장 설계

작성일: 2026-10-24 (Asia/Seoul)

상태: **1~5단계와 6단계 기본 off의 별도 검색 비교 실험 구현 완료. shadow는 별도 진단, explain은 관리자 설명 API다. 운영 질의·검색·답변에는 실험을 연결하지 않는다.**
구현은 설비 공통 `incident_ontology.py`와 HPU 진입점 `hpu_ontology.py`로 분리했다.
구체적인 사용법과 RED/GREEN·회귀 결과는 [1~2단계 구현 기록](../testing/hpu-ontology-phase12-20261024.tdd.md)에 있다.
3단계는 [shadow 실행 안내](../guides/hpu-ontology-shadow.md)와
[검증 기록](../testing/hpu-ontology-shadow-20261024.tdd.md)을 따른다.
4단계의 실제 계약과 한계는 [설명 API 안내](../guides/hpu-ontology-api.md)와
[검증 기록](../testing/hpu-ontology-api-20261024.tdd.md)을 따른다.
기준 HEAD: `a37547f81dad64f5d77ce692e5df86269f4362f5`와 현재 로컬 작업 트리.
`server.py`, `storage.py` 등에는 미커밋 변경이 있으므로 구현 시작 시 HEAD와 관련 diff를 다시 고정한다.
설계 작성 시점에는 운영 DB·장비·실제 모델을 조회하지 않았다. 후속 실제 모델 검증은 [p95 분석](../testing/hpu-p95-20261025.md)에 별도로 기록한다. 기존 [검색 그래프 계약](knowledge-graph-runtime.md)과
[기능 지도](feature-map.md)를 확장하되 기존 기능의 의미와 저장 원문을 유지한다.

## 1. 목표와 첫 구현 범위

HPU의 한 사건에 대해 다음을 원문 근거와 함께 조회할 수 있게 한다.

> 어느 자산에서 무엇을 언제 관측했고, 어떤 사건으로 기록했으며, 누가 무엇을 했고,
> 어떤 결과를 어떤 방식으로 확인했는가?

첫 구현은 **기존 업무 데이터의 읽기 전용 그래프 투영**이다. 새 지식 원장을 만들지 않는다.
원본 SQLite/JSON을 사실의 기준으로 유지하고 질의별로 연결 결과를 만든다.
초기에는 기존 검색 순위·프롬프트·답변·PDA를 변경하지 않는다. 온톨로지 조회가 실패해도
일지 저장·질의·검수·게시가 실패하지 않게 분리한다.

대상은 원본 마스터에서 `equipment.equipment_type_id → equipment_types.type_code == HPU`로 확인한
설비다. 현재 합성 마스터는 `EQ-0001` / `HPU-01` / `ET-0001`이며 기본 자산 생성 규칙은
`AS-{equipment_id}-001`이다. 이 ID를 실행 코드에 고정하지 않고 기록 당시 config/asset을 사용한다.
기본 구성의 ID를 과거 기록이나 현재 실장비의 자산 ID로 소급 대입하지 않는다.

제외: 실제 부품 장착 추정, 원인 자동 확정, 작업 승인, 설비 자동 제어, 기존 증상 후보의 자동 검수,
전 설비 확대, 원본 재생성, 정적 KB/임베딩 변경, 그래프 DB·OWL 추론기 도입, 운영 배포.
RDF/OWL 교환은 외부 연계 요구가 확정될 때 후속 어댑터로 검토한다.

## 2. 현재 코드에서 재사용할 계약

경로는 저장소 루트 기준이며, 아래는 이번에 본 기존 구현이다.

| 기존 코드·저장 | 확인한 내용 | 재사용 방식 |
|---|---|---|
| `shiftlink/mes/contracts.py:EquipmentConfig`, `configuration.py:from_catalog` | `equipment_id`는 논리 설치 위치, `asset_id`는 교체 자산. config에 신호·단위·기준값 존재 | 유형·위치·자산을 분리하고 보존 config로 과거 바인딩 확인 |
| `storage.py:save_work_report`, `get_incident` | 사건에 `assets`, `config_id` 고정. 일지 `(handover_id, record_index)`와 사건 연결 | 기존 incident ID와 사건의 원 자산을 사용. 새 사건 ID 생성 금지 |
| `storage.py:get_query`, `get_query_evidence` | 질문과 질의 당시 근거 보관. query evidence 키는 run/time/equipment | query payload의 `query_context`와 evidence를 교차 검증 |
| `work_reports.py:sensor_evidence`, `storage.py:work_report_sensors` | 일지 저장 당시 센서에 asset/unit/quality/observed_at, 상위 run/config 포함 | `scope=save_snapshot`을 유지. 발생·조치 시점 센서로 바꾸지 않음 |
| `work_reports.py:validate_capture`, `capture_candidate_from` | 단계별 action/observed_result/failed, 선택 worker/performed_at, 작업자 정상 운전 기록 | 원문·단계 순서·누락을 보존. worker 확인과 MES 판정을 분리 |
| `server.py:resolution_start`, `resolution_step`, `_finish_session` | before/steps/after, 센서 전후 비교, 저장된 MES verdict/check | 저장된 관측·판정을 읽는다. 조회 시 현재 MES로 과거 결과 재판정 금지 |
| `storage.py:get_resolution_session`, `update_resolution_session` | 열린 조치 세션은 변경 가능. 테이블은 equipment_id/data 중심 | 세션 내용 해시로 투영 버전 구분. asset/config 누락을 자동 보완하지 않음 |
| `work_reports.py:handover_resolved` | resolved 외에 정상 운전 상태·지속시간·근거 요구 | 업무상 완료 조건을 재사용하되 작업 안전 인증으로 해석하지 않음 |
| `mes/publication.py:PublicationManager.snapshot`, `still_current` | 검수·모델·해시·자산·관측 조건을 통과한 질의 뷰와 ticket | 지식카드 연결은 이 경로에서 허용된 판본에만 부착 |
| `rag/knowledge_graph.py:KnowledgeGraph`, `graph_explain.py:GraphSnapshot` | 카드 분류·문서 인용, 게시 카드 설명 그래프 | 기존 스키마/ID/관계·검색 예산을 유지하고 별도 HPU 스키마로 연결 |

중요한 빈칸: `resolution_sessions`만으로 과거 자산·config가 항상 확정되는 것은 아니다.
legacy 일지에는 센서·구조화 단계·조치시각이 없을 수 있다. 이를 해결된 사실로 가정하지 않는다.

## 3. 데이터 모델: 업무 사실과 주장 구분

1~2단계 공통 스키마: `shiftlink-incident-ontology-v1`. HPU 전용 스키마를 만들지 않는다.
기존 `shiftlink-retrieval-graph-v1`은 유지한다. 공통 타입/관계는 `incident_ontology.py`의 선언과 검사기로 관리한다.

| 노드 | 의미·원본 | 핵심 속성 |
|---|---|---|
| `Asset` | 사건/관측 당시의 개별 자산 | asset_id, is_synthetic. 위치·config·type 연결은 출처가 있는 관계/바인딩에 기록 |
| `Observation` | 센서값 또는 작업자 관찰 한 건. 이상 여부와 구분 | signal/value/unit/quality 또는 원문 text, observed_at_raw, time_basis, scope, source_kind |
| `Incident` | 기존 `incidents.incident_id`의 사건 | incident_id, config_id, 원 자산 집합, created_at. 실제 발생 시각은 별도 |
| `Action` | 실제 기록된 조치 한 단계. 권고 절차와 구분 | action 원문, ordinal, failed_raw, worker_ref, performed_at_raw, scope_status |
| `Outcome` | 단계 결과·일지 정상 운전·MES 판정을 각각 한 건 | outcome_kind, 원문/원 상태, duration 원 값·단위, verification_basis |

보조 참조: 기존 `EquipmentType`, `CardVersion`, `DocumentVersion` 및 논리 설치 위치 식별자를 재사용한다.
자산의 특정 config 위치 연결은 해당 구성 스냅샷에서의 연결이다. 실제 장착 시작/종료 이력으로 확정하지 않는다.
같은 자산이 여러 config에 나와도 노드를 덮어써 최신 위치만 남기지 않고 config별 바인딩을 병렬 보존한다.
실물 `AssetPart`와 상세 고장/원인 개념은 1차 범위에 넣지 않는다.

공통 근거 필드(노드와 관계):

- `source_ref`: 원본 종류·레코드 ID·정확한 필드 경로. DB 절대 경로나 인증정보는 포함하지 않는다.
- `source_hash`, `source_revision`(있을 때), `schema_version`, `source_namespace`.
- `claim_kind`: sensor_observation / worker_report / mes_assessment / advisory.
- `review_state`: 원본의 검토 상태를 그대로 매핑하며 미검토를 accepted로 승격하지 않는다.
- `run_id`, `config_id`, `asset_id`는 확인된 경우만 채운다. 추출 실행 시각과 사건 시각은 별도다.
- `binding_status`: verified / unresolved / conflict, `missing_fields`와 사유.

센서 관측·작업자 보고·MES 판정은 서로 다른 근거다. `failed=false`는 실패 표시가 없다는 원 값이며
조치 성공을 자동 확정하지 않는다. 원문에 “해결”이 있어도 절차 재사용·안전 타당성이 검수됐다는 뜻은 아니다.

### 관계의 방향과 의미

| 관계 | 시작 → 끝 | 생성 조건 |
|---|---|---|
| `INSTANCE_OF` | Asset → 기존 EquipmentType | 기록 당시 구성과 마스터 FK로 HPU 유형 확인 |
| `INVOLVES_ASSET` | Incident → Asset | 사건의 저장된 assets 매핑과 일치 |
| `OBSERVED_ON` | Observation → Asset | 해당 관측의 원 자산 바인딩 verified |
| `HAS_OBSERVATION` | Incident → Observation | query_id/일지 record/명시 session 연결이 사건에 속함 |
| `HAS_ACTION` | Incident → Action | 원 일지·세션의 사건 연결이 명시적임 |
| `PERFORMED_ON` | Action → Asset | 한 설비 대상 또는 명시 단계 대상 확인. 다중 설비 일지를 추정 분배하지 않음 |
| `NEXT_RECORDED_STEP` | Action → Action | 같은 원본 revision의 배열 순서. 실제 시간 선후·인과관계 보장이 아님 |
| `HAS_RECORDED_RESULT` | Action → Outcome | 그 단계의 observed_result. 일지 전체 결과를 모든 단계에 복제하지 않음 |
| `HAS_OUTCOME` | Incident → Outcome | 원 일지/명시 연결 세션의 종합 결과. 작업자와 MES 결과를 병렬 유지 |
| `SUPPORTED_BY` | Outcome → Observation | 명시 before/after·측정 참조가 있을 때만 생성 |
| `DERIVED_FROM_INCIDENT` | 검증된 CardVersion → Incident | 기존 후보 출처/사건 ID와 publication ticket 판본 일치 |

`HAS_ACTION`은 수행 기록의 연결이고 원인 관계가 아니다. `CAUSES`, `CURES`, `SAFE_TO_RUN`은 생성하지 않는다.
기존 `PART_OF`는 카드 분류 계층 의미를 유지하며 물리적 장착 관계로 재해석하지 않는다.
고장 주입 `ground_truth`, `simulation_labels`, 시나리오 정답 필드는 투영 입력의 허용 목록에서 제외한다.

## 4. ID·원문·시간·자산 규칙

1. 새 ID는 `[source_namespace, schema_version, kind, ...원본 식별자]` JSON 배열의 결정적 직렬화로 만든다.
   기존 카드/문서 그래프 ID는 재발급하지 않고 `external_ref`로 참조한다.
2. 일지 Action은 `(handover_id, record_index, 원래 step_index)`를 쓴다. 빈 단계를 빼도 인덱스를 재번호화하지 않는다.
   열린 세션은 삭제/재정렬이 가능하므로 `(session_id, canonical_session_hash, 원래 step_index)`를 사용한다.
   세션 Outcome도 동일 내용 버전을 참조한다. 세션이 바뀌면 이전 투영을 현재 것으로 재사용하지 않는다.
3. 센서 Observation은 원본 근거 ID + 측정 인덱스/신호 + 내용 해시로 식별한다.
   query evidence의 기존 키가 유일성의 충분조건이라고 가정하지 않고 query payload의 내용·문맥과 대조한다.
   동일 원본 재실행은 같은 ID, 다른 원본의 비슷한 값은 별도 ID다.
4. 자산 바인딩은 사건 assets, query_context, 원 센서의 asset, 보존 config를 대조한다.
   하나라도 충돌하면 `conflict`; 누락 시 재구성 가능한 명시 연결만 사용한다.
   `equipment_id`·현재 config·이름 유사도만으로 과거 asset을 채우지 않는다.
   보존 `EquipmentConfig`에는 마스터의 equipment_type_id가 없으므로 과거 유형 FK를 항상 복원할 수 있다고
   가정하지 않는다. 유형은 해당 자료의 catalog 버전/해시가 확인될 때 연결한다. 확인되지 않으면 현재 마스터로
   소급하지 않고 HPU 유형 바인딩을 unresolved로 둔다. fixture에는 source catalog 해시를 함께 고정한다.
5. query/일지/세션의 시간 기준을 각각 보존한다. 저장 시각, 보고된 발생 시각, 센서 시각, 조치 시각,
   모델 참고 생성 시각은 다른 속성이다. 분 단위 보고를 초 단위 정밀도로 승격하지 않는다.
   timezone 없는 문자열은 raw로 보존하고 비교 결과는 unknown. 별도 출처 계약 없이 Asia/Seoul로 추정하지 않는다.
6. 정상 범위·단위는 해당 기록/config에서 읽는다. 현재 마스터의 예시 수치를 과거에 덮어쓰지 않는다.
   값·단위·품질 누락은 unknown이며 0/정상/회복으로 바꾸지 않는다. 단위 자동 변환은 1차 범위 밖이다.
7. 일지 저장 시 센서는 `scope=save_snapshot`이다. 조치 순간 또는 전체 정상 운전 기간의 증거로 쓰지 않는다.
   작업자 `normal_run_minutes`는 worker_report이며 연속 MES 검증 시간으로 승격하지 않는다.
8. 사건/세션의 명시 연결이 없으면 설비·시간 근접성으로 합치지 않는다. unresolved 레코드는 진단 목록에 남기고
   자산별 확정 경로·검색·LLM 입력에서는 제외한다. 누락 건수와 제외 이유를 보고한다.
9. 개인정보 원문은 기존 보호 범위에 둔다. 외부 그래프 응답은 최소 작업자 참조만 제공하고 원문 접근 권한을 재사용한다.
10. 노드/관계 정렬과 canonical JSON을 고정한다. `snapshot_hash`는 원본 내용 해시와 schema/투영 버전에
    결합하고 추출 실행 시각·정렬되지 않은 dict·임시 경로는 해시에 넣지 않는다.

## 5. HPU의 최소 예시와 질문 계약

실제 값이 아닌 fixture 시나리오다. 마스터의 HPU 신호는 `hpu_pressure`(bar),
`hpu_oil_temp`(degC), `hpu_filter_dp`(bar), `hpu_flow`(L_min)이다.

- 사건 I의 원 자산 A에서 query Q 당시 압력 관측 O1을 확보한다.
- Q에 연결한 일지 R의 단계 0에 “필터 점검”, 관찰 결과 텍스트를 기록한다.
- R의 정상 운전 보고는 Outcome W로, 명시 연결된 세션의 MES 판정은 Outcome M으로 별도 표현한다.
- 검수·게시된 카드 C가 이 사건을 출처로 가질 때만 C → I 관계를 질의 뷰에 추가한다.
- 이후 자산 A가 B로 교체돼도 I/O1/조치는 A에 남는다. B의 현재 질문에는 기존 자산 필터를 유지한다.

초기 수용 질문과 정답 기준:

| 질문 | 수용 기준 |
|---|---|
| 이 HPU 사건의 당시 관측과 조치 순서는? | 원 기록·신호·단위·품질·단계 순서를 출처와 함께 복원 |
| 회복했다는 판단의 근거는? | worker_report와 mes_assessment를 구분하고 상충 시 둘 다 표시 |
| 이 카드는 어느 사건에서 만들어졌나? | 현재 검증된 게시 판본과 원 사건만 연결. 미게시/반려는 검색 연결 없음 |
| 자산 교체 전 기록인가? | 원 assets/config와 비교. 이력이 모자라면 미확인 |
| 기록의 조치가 실제 원인이었나? | 단순 전후 관계로 인과를 확정하지 않고 확인 가능한 범위만 반환 |

## 6. 구현 구조와 호환성

1~2단계는 다음 세 파일로 구현했다.

- `shiftlink/mes/incident_ontology.py`: 설비 공통 타입/관계·출처 검증·읽기 전용 SQLite 어댑터·순수 투영.
- `shiftlink/mes/hpu_ontology.py`: 공통 projector를 `equipment_type='HPU'`로 호출하는 진입점.
- `tests/test_hpu_ontology.py`: 계약별 fixture와 반례. 테스트 데이터는 임시 DB/작은 고정 JSON 사용.

기존 `storage.py`를 수정하지 않고 동일 테이블·식별자를 선택 조회하는 `read_incident_bundle`을 추가했다.
사건 ID는 필수이며 사건별 일지·질의 한도를 받는다. 연결된 세션과 run/config만 조회하고 전체 snapshot을 읽지 않는다.
입력 파일이 없으면 생성하지 않는다. 파일이 아닌 실행 중 서비스에 연결하는 어댑터는 아직 없다.

운영 통합 전에는 DB를 복사/백업한 오프라인 입력 또는 검증된 JSON bundle을 사용한다.
`MesStorage(path)`는 생성 시 DDL/PRAGMA를 수행하므로 읽기 전용 분석기로 무심코 열지 않는다.
필요한 복사본 조회는 SQLite `mode=ro` 연결을 쓴다. 서버 통합 후에는 기존 `_lock` 아래에서 필요한 데이터를
짧게 복사하고 그래프 생성·직렬화는 잠금 밖에서 수행한다. 원본 묶음에 해시를 남기며 일관된 관측 범위를 검사한다.

초기에는 새 그래프 테이블·마이그레이션·상시 worker·공유 캐시를 추가하지 않는다.
지속화가 필요해지면 재생성 가능한 버전별 캐시만 별도 설계하고 업무 원장의 이중 쓰기를 피한다.
초기 `source_namespace`는 fixture/승인된 자료 묶음의 고정 ID로 제공한다. 복사 DB마다 임의 UUID를 새로 만들거나
DB 절대 경로를 ID로 삼지 않는다. 운영 자료 묶음 namespace의 보존 정책은 서비스 연결 전에 확정한다.

3단계 실행기는 `SHIFTLINK_HPU_ONTOLOGY=off|shadow`와 CLI `--mode`를 지원하며 기본은 `off`다.
명시 CLI 값이 우선한다. shadow는 서비스에서 자동 실행되지 않는다.
4단계 `explain`은 별도 인증 GET만 활성화하며 DB·카탈로그·manifest 경로를 추가로 명시해야 한다.
현재 `SHIFTLINK_KNOWLEDGE_GRAPH`/`SHIFTLINK_KG_MODE`의 의미는 바꾸지 않는다.
`off`에서는 projector를 호출하지 않고 기존 응답 키·저장·검색·모델 호출 수·예산을 유지한다.
`shadow`는 허용된 격리 실행에서 그래프 진단만 수집하며 기존 답변에 넣지 않는다.

`explain` 단계에서는 사건 단위 별도 GET `/api/incidents/<incident_id>/ontology`를 구현했다.
기존 역할 인증과 대상 원문 접근 정책을 적용하고 사건 ID만으로 공개하지 않는다.
응답은 `{schema_version, snapshot_hash, scope, nodes, edges, unresolved, truncated}` 형태다.
페이징/페이지 크기는 조회 시점 해시와 묶고, 결과 상한 초과를 빈 성공으로 숨기지 않는다.
첫 한도 제안은 사건 1건·일지 30건·노드 1000개·관계 2000개이며 fixture 측정 후 확정한다.
PDA·기존 `/api/query` 응답에는 이 단계까지 새 필드를 추가하지 않는다.

지식과 연결할 때 전체 업무 기록을 `KnowledgeGraph`나 프롬프트에 넣지 않는다.
검증된 publication ticket의 실제 인용 카드에 연결된 사건만 추가 설명한다.
응답 직전 같은 ticket을 기존 저장 잠금에서 재검증하며 반려·자산 교체 시 해당 연결도 제외한다.
원 업무 기록은 내부 이력으로 남는다. 카드가 반려됐다고 원 사건/일지를 삭제하지 않는다.

## 7. 단계별 구현·검증·중단 기준

단계마다 기존 회귀를 독립 게이트로 유지한다. 아래 명령은 **후속 구현 시 실행 계획**이며 이번 설계에서
새 projector/API가 검증됐다는 뜻이 아니다. 실제 구현은 작은 실패 사례를 먼저 만들고 통과시킨다.

| 단계 | 구현 범위 | 검증·완료 조건 | 실패 시 복구 |
|---|---|---|---|
| 0. 기준 고정 | HEAD/관련 diff·데이터 계약·기존 결과 기록. 합성 HPU/타 설비 fixture 준비 | 동일 원본/현재 코드가 재현 가능. 기존 실패와 새 실패 구분 | 실행 코드 변경 없음 |
| 1. 순수 모델 | hpu_ontology.py의 선언·ID·순수 bundle 변환 | 타입/방향, 결정성, 원문·시간·품질, 교체/다중 설비/누락 반례 통과 | 새 모듈 미연결 유지 |
| 2. 원본 어댑터 | incident/query/report/session의 선택 조회와 JSON bundle | 임시 SQLite에서 실제 서비스 작성 → 투영 → 원본/이전 답변 불변 확인. unresolved는 추측 연결 0 | 어댑터 호출 해제, DB 마이그레이션 없음 |
| 3. shadow | 기본 off, 격리 실행에서 원본 해시·관계·누락 이유 수집 | off의 기존 응답 완전 동일. shadow의 저장/모델/검색 영향 0. 상한·잠금 검사 | off |
| 4. 설명 조회 | 별도 인증 GET, scope·해시·상한/페이지 처리 | 권한 없는 접근 차단, 다른 자산/사건 누출 0, 누락·상충 표시, 기존 API 회귀 통과 | off/새 라우트 비활성 |
| 5. 게시 지식 연결 | ticket 기반의 인용 카드 ↔ 사건 설명 | 게시 전/후/반려/질의 중 변경 검증. 과거 원문·judge·검색 예산 유지 | 연결 설명만 해제, 기존 게시 자료 유지 |
| 6. 검색 활용(선택 후속) | 수용 질문에서 이득이 확인된 관계만 후보 확장 실험 | 기존 모드 대비 인용/보류/오연결/지연 비교. 현재·과거 경계의 회귀 0 | 기존 벡터+분류/인용 그래프 경로 |

추천 첫 구현 묶음은 **1~2단계까지**다. 3단계부터 서비스 통합 범위를 별도로 확정한다.
6단계는 설명 조회의 완성 조건이 아니며 성능/품질 증거 없이 자동 진행하지 않는다.

### 최소 회귀 명령 묶음

```powershell
# 단계 1~2: 새 계약 + 기존 원본 저장/조치 캡처/후속 인계
python -m pytest tests/test_hpu_ontology.py tests/test_mes_storage.py tests/test_work_report_capture.py tests/test_work_report_followup.py -q

# 단계 3~5: 기존 검색·게시·인용·동일 질문 재사용
python -m pytest tests/test_knowledge_graph_runtime.py tests/test_publication_ontology_integration.py tests/test_publication_worker.py tests/test_publication_s30h.py tests/test_knowledge_gap_loop.py -q

# 질의·이력·Pi 참고에 실제 연결되는 단계의 보존 검사
python -m pytest tests/test_field_history_integration.py tests/test_s30h_publication_integrity.py tests/test_pi_analysis_query.py -q
python scripts/check_knowledge_publication.py --history-scope closure
python scripts/check_knowledge_publication.py
```

심사/검수·이력 분류 자체를 수정하면 `.github/instructions/knowledge-publication.instructions.md`의
추가 엄격 검사도 적용한다. 하니스 성공을 의미 검증 성공으로 바꾸지 않는다.
브라우저 노출을 구현하는 단계에서는 임시 DB/모델 fixture의 실제 브라우저·HTTP 검사도 수행한다.
PDA UI를 실제로 변경할 때만 `shiftlink/mes/web/AGENTS.md`의 최소 검사와 육안 확인을 추가한다.
기존 `pda_ai_insights_display.cjs`의 미정의 함수 실패는 별도 알려진 테스트 결함으로 기록하며 통과로 세지 않는다.

### 새 테스트가 반드시 포함할 반례

- 같은 위치의 자산 교체 A→B, 다른 HPU/비HPU, 같은 시간의 다른 사건을 서로 연결하지 않음.
- 다중 설비 일지의 단계 대상을 특정 HPU에 임의 배분하지 않음.
- 조치시각 누락/naive 시각/센서 bad·missing/단위 충돌/다른 run을 정상·현재 근거로 승격하지 않음.
- 일지 save_snapshot으로 작업자가 적은 정상 운전 전체 시간을 증명하지 않음.
- worker 해결 보고와 MES 미복구가 함께 있을 때 한쪽을 덮어쓰지 않음.
- 열린 session 단계 삭제/재정렬/재시작, 중복 저장/재실행에 잘못된 ID 재사용·중복 관계가 없음.
- 후보/quality_passed이나 미게시/임베딩 실패/반려/원 자산 변경은 지식 검색 연결 없음.
- 게시 연결 도중 반려 시 새 답변 연결은 제외되며 이전 저장 답변·원 일지는 불변.
- 시나리오 정답/주입 라벨은 bundle에 없음. Pi advisory는 센서·원인·작업 승인으로 바뀌지 않음.
- 실패·잘린 결과·빈 이력·정보 미상은 각각 구분. 상한 초과로 무제한 스캔하지 않음.

## 8. 평가·배포 결정과 남은 의문

수용 질문의 모든 정답/반례를 명시 fixture로 고정한다. 오자산 연결, 무근거 인과·안전 결론,
원문/판본 훼손, 기존 회귀는 각각 0건을 목표로 하며 전체 통과율 상승으로 상쇄하지 않는다.
링크 커버리지와 unresolved 사유는 별도 집계한다. 원본이 부족하면 커버리지를 높이기 위해 추정하지 않는다.
조회 지연 p50/p95, 잠금 점유, 반환 크기·메모리를 같은 fixture/장비에서 기준과 비교하고
기기 배포 전 예산을 확정한다. 이번 설계에서 지연 수치·실장비 성능은 제시하지 않는다.

실제 모델 검증은 fixture와 별도로, 선택적 검색 연결 단계에서 독립 질문의 인용 정확성·보류·과거/현재
구분을 비교한다. 현장 검증 없이 합성 HPU 결과를 실제 설비의 원인/안전성 인증으로 설명하지 않는다.

배포 단계는 문서·코드 검토와 격리 검증 후 별도 작업으로 수행한다. 기본 off로 설치하고
신규 조회만 점진 활성화한다. 오류·오연결·지연 예산 초과 시 off로 되돌리며 기존 DB/KB/index는 복원할 필요가
없도록 읽기 전용 투영을 유지한다. 기존 서비스·모델·Pi 분석 릴리스 변경은 이 설계에 포함하지 않는다.

구현 전 확인할 질문: legacy session의 원 자산/config를 복원할 수 있는 비율, source_session_id와 incident의
명시 연결 커버리지, timezone 없는 원문 시각의 출처 계약, 새 조회의 역할별 접근 범위,
실제 HPU 교체 이력·장착 부품·전문가 검증 데이터의 제공 여부. 누락은 unresolved로 시작할 수 있으므로
1~2단계 구현을 막는 이유로 추정 데이터를 넣지 않는다.

## 9. 이번 설계 문서의 검증

프로젝트 `.venv/Scripts/python.exe`로 확인했다.

- 기존 재사용 심볼 20개, 계획의 기존 회귀 파일 경로, 이 문서·기능 지도의 상대 링크 검사 통과.
- `python -m pytest tests/test_mes_storage.py tests/test_work_report_capture.py tests/test_work_report_followup.py -q`
  → `56 passed in 19.98s`. 기존 저장·조치 캡처·후속 인계의 기준 회귀이며 새 온톨로지 구현 검증은 아니다.
- `python scripts/check_knowledge_publication.py` → `ok: true`, `errors: []`,
  `staged_python_checked: true`, `check_kind: metadata_and_syntax`, `history_semantics_evaluated: false`.
- 종료 확인 HEAD도 `a37547f81dad64f5d77ce692e5df86269f4362f5`다. 로컬 미커밋 파일은 기준 설명대로 남아 있다.

위 결과는 설계 작성 시점 기록이다. 이후 1~2단계 공통 모듈과 테스트는 실제로 구현했으며
[구현 기록](../testing/hpu-ontology-phase12-20261024.tdd.md)에 현재 검증 범위를 구분했다.
이후 3단계의 별도 shadow 실행기·off/shadow 설정은 구현했다.
이후 4단계 관리자 설명 API와 5단계 선택 query_id의 실제 게시 인용 연결을 구현했다.
새 질의 로그의 내부 ticket과 현재 게시 상태·원 사건 출처를 대조한다.
[API 계약](../guides/hpu-ontology-api.md)과 [5단계 검증](../testing/hpu-publication-links-20261024.tdd.md)을 따른다.
2026-10-25에는 별도 `hpu_retrieval_experiment.run_experiment`에서만 같은 검증 풀의 HPU 관계 후보를 최대 2개 보완하는 실험을 구현했다.
[실험 계약](../guides/hpu-retrieval-experiment.md)과 [비교·검증](../testing/hpu-retrieval-experiment-20261025.tdd.md)을 따른다.
실시간 질의 hook·운영 검색 후보 확장은 구현하지 않았다.
