# ShiftLink 지식 그래프 미니 시연 계약

계약 버전: `kg-demo-v1`
확인일: 2026-10-21 (Asia/Seoul)
상태: **2026-10-21 사용자 승인 완료. 세 PC의 분담 구현을 위한 공통 계약이며 그래프·화면은 아직 구현 전이다.**

## 1. 목적과 경계

발표용으로 지식 카드의 분류, 증상 후보, 카드 버전, 근거 문서 판본을 명시적인 노드와 관계로 표현한다. 유형과 개별 장비를 구분한다. 서비스의 검색·생성·게시 경로에는 연결하지 않는다.

구현 대상은 `EquipmentType`, `Symptom`, `CardVersion`, `DocumentVersion`이다. 장비 마스터가 확인되어 `Asset`은 **합성 장비 10대에 한정하여 연결**하는 안으로 승인되었다. 실제 현장 자산은 확인되지 않았다. `AssetPart`는 설계만 한다.

이름과 의미의 단일 정의는 이 문서다. 기존 naming registry 등록은 사용자가 결정한다. 분담 구현에서는 기존 파일 수정, 커밋, push, PR, Pi/Jetson 배포, 원본 재생성, 임베딩·모델 호출을 하지 않는다. 다만 2026-10-21 사용자가 총괄에게 승인한 공통 기준 준비는 schema.md, distributed-work-plan.md, docs/design/project-structure.md 세 문서만을 codex/kg-base에 커밋·push하는 범위로 수행한다. 산출물과 검증 임시 파일은 모두 `docs/demo/kg/` 안에 둔다.

## 2. 원본 확인 결과

### 2.1 카드 원본

읽기 전용 원본: [kb_cards.json](../../data/knowledge_cards/kb/kb_cards.json). `_meta.note`가 자동 생성 파일임을 명시한다. 생성기를 실행하지 않는다.

| 항목 | 직접 확인한 값 |
|---|---|
| 최상위 키 | `_meta`, `cards`, `evidence_text` |
| 카드 / 고유 card_id / 고유 (card_id, version) | 86 / 86 / 86 |
| 암묵지 유형 | T1 19, T2 14, T3 19, T4 12, T5 13, T6 9 |
| 시나리오 | S1 30, S2 37, S3 19 |
| 설비 분류별 카드 | CAU 13, COMMON 12, CV 13, GR 12, HPU 13, PDP 12, RT 11 |
| 고유 (equipment, component) | 76; 두 필드의 빈 값 없음 |
| symptom | 문자열 73, null 13; 서로 다른 문자열 73 |
| safety_flag | true 56, false 30 |
| 안전 카드의 symptom | 문자열 45, null 11 |
| 비안전 카드의 symptom | 문자열 28, null 2 |
| status | accepted 86; **새 증상 매핑의 검수 완료를 뜻하지 않음** |
| provenance.sources 항목 | 222; 모든 카드에 1개 이상 |
| 판본이 있는 출처 항목 | 180; 고유 (source_id, document_version) 92 |
| 판본이 없는 출처 항목 | 42; 19개 source_id, 11개 카드 |
| 판본이 있는 고유 (카드 버전, 문서 판본) | 156; 같은 쌍의 locator는 한 관계에 모음 |
| 추가 MES 바인딩 필드 | 44장에 mes_equipment_id; 해당 카드의 mes_component_code는 모두 null |

카드 버전은 다음 6종이며 문자열을 그대로 보존한다.

| version | 수 |
|---|---:|
| `1.0-KB-20261001-handover-completion` | 1 |
| `1.0-draft-KB-20260929-A` | 26 |
| `1.0-draft-KB-20260930-C` | 19 |
| `1.0-draft-KB-20260930-D` | 25 |
| `1.0-draft-KB-20260930-T4` | 11 |
| `1.1-safety-20261020` | 4 |

원본 바이트 SHA-256: `05cfc4e79a3087e3544fc01e6b830268b542f55ae3be31bd6ad7601fc1d6dd3a`.

### 2.2 장비 마스터와 요청문에서 달라진 사실

마스터: [00_plant_and_relations.json](../../data/reference/00_plant_and_relations.json).
카탈로그 로더: [catalog.py](../../../shiftlink/mes/catalog.py).
기본 마스터 경로: [server.py](../../../shiftlink/mes/server.py)의 `serve` 경로.
식별자 의미: [contracts.py](../../../shiftlink/mes/contracts.py)의 `EquipmentConfig`, [configuration.py](../../../shiftlink/mes/configuration.py)의 `from_catalog`.

- 데이터셋 `DS-v1.0`, `_meta.is_synthetic: true`. 장비 10대와 부품 18개가 있다. 따라서 “마스터 미확인”, “부품 데이터 없음”은 현재 원본과 다르다. **실제 현장 장비·장착 이력은 확인되지 않았다.**
- 현재 코드에서 `equipment_id`는 논리 설치 위치이고 `asset_id`가 교체 시 달라지는 합성 자산 ID다. 카드의 `HPU` 같은 분류, 설치 위치 `EQ-0001`, 개별 자산 `AS-EQ-0001-001`을 구분한다.
- 기본 카탈로그 변환은 `AS-{equipment_id}-001`을 결정적으로 생성한다. 이 시연은 그 규칙의 **기본 구성 스냅샷**만 사용한다. 실행 중 MES 구성·교체 이력·DB는 읽지 않으며 현재 설치 상태라고 주장하지 않는다.
- 유형 연결은 `equipment.equipment_type_id → equipment_types.equipment_type_id → type_code`로 결정한다. 장비 코드 문자열이나 한글 명칭을 추측해 매칭하지 않는다.
- 합성 부품 18개는 존재하지만 이번에는 `AssetPart`를 생성하지 않는다. 부품 장착 이력과 카드 부품 표현의 대응은 별도 설계 과제다.
- `COMMON`은 공통 적용 분류다. “교대 인계 기록” 등의 component 값은 물리 부품이 아니다. 이 시연의 유형 계층에는 원본 분류어가 들어가며, 실제 조립 구조나 표준 부품 분류로 해석하지 않는다.

| equipment_id | code | 기본 합성 asset_id | type_code |
|---|---|---|---|
| EQ-0001 | HPU-01 | AS-EQ-0001-001 | HPU |
| EQ-0002 | PDP-01 | AS-EQ-0002-001 | PDP |
| EQ-0003 | CAU-01 | AS-EQ-0003-001 | CAU |
| EQ-0004 | GR-01 | AS-EQ-0004-001 | GR |
| EQ-0005 | GR-02 | AS-EQ-0005-001 | GR |
| EQ-0006 | RT-01 | AS-EQ-0006-001 | RT |
| EQ-0007 | RT-02 | AS-EQ-0007-001 | RT |
| EQ-0008 | RT-03 | AS-EQ-0008-001 | RT |
| EQ-0009 | CV-01 | AS-EQ-0009-001 | CV |
| EQ-0010 | CV-02 | AS-EQ-0010-001 | CV |

마스터 바이트 SHA-256: `aee891c5e5e2270e815080f22b153e9b64e9128951d2262240c1f41cdc5e1708`.

### 2.3 기존 구현에 대한 확인 범위

`shiftlink/rag/retrieval.py`에는 카드 토큰·어간 겹침 기반 검색이 있고, `shiftlink/rag2/s30h.py`에는 임베딩 벡터 유사도 순위가 있다. 두 경로를 모두 “카드 임베딩 검색” 하나로 설명하지 않는다. 확인한 검색 경로에는 이 시연 그래프를 이용한 검색·추론이 없다.

기존 naming registry와 MES 마스터에는 이미 이름, 유형, 공급 관계 등의 정의가 있다. “프로젝트 전체에 명시적 관계가 전혀 없다”는 표현은 피한다. **카드의 6노드 그래프 계약을 이번에 추가한다**는 범위다. GNN·GeoAI 적용이나 전체 시스템의 완성·배포 상태를 이번 읽기 전용 확인으로 재검증하지는 않았다.

## 3. 공통 ID와 데이터 보존 규칙

ID는 URL이 아닌 문자열이다. 원본 값을 자르거나 대소문자·공백·한글·단위·수치를 정규화하지 않는다. 구분자 충돌 방지를 위해 ID를 구성하는 개별 원본 문자열에 순서대로 `% → %25`, `/ → %2F`, `@ → %40`만 적용한다. 이후 아래 표의 구분자를 붙인다. 원본 값은 props에 그대로 둔다. URL 탐색 주소로 쓸 때는 별도로 URL 인코딩한다.

누락·빈 ID 필드는 검증 오류로 처리한다. 판본 누락 인용만 6절의 명시적 보류 규칙을 쓴다. 문자열 `"unknown"` 등을 가짜 판본으로 만들지 않는다. 같은 ID에 다른 핵심 속성이 들어오면 오류다. 노드는 ID 순, 관계는 (type, source, target) 순으로 정렬해 재실행 결과를 결정적으로 만든다.

## 4. 노드 타입 6종

| 이름 | 정의 / 이번 범위 | ID 규칙과 예시 | 필수 props |
|---|---|---|---|
| `EquipmentType` | 재사용되는 설비·부품 분류어. COMMON과 그 하위 업무 분류는 공통 적용 범주이며 물리 부품을 뜻하지 않음. 구현 | 설비 `type:<equipment>`, 부품·하위 분류 `type:<equipment>/<component>`. 예: `type:HPU`, `type:HPU/주 베인펌프` | `kind`: `equipment` 또는 `component`; `equipment`; component 노드에는 `component`; `is_common_scope`: bool |
| `Symptom` | 의미를 구분해 정의한 증상 개념 후보. 원인·조치·승인 상태와 구별. 사람 검수 전 구현 | `sym:<slug>`; slug는 `[a-z0-9]+(?:-[a-z0-9]+)*`. 예: `sym:hpu-outlet-pressure-absent` | `definition`: 비어 있지 않은 문자열, `review_status: "needs_review"` |
| `CardVersion` | 원본 카드의 특정 판본. 구현 | `card:<card_id>@<version>`. 예: `card:K-1001@1.0-draft-KB-20260929-A` | 원본 카드 객체의 모든 필드를 그대로 복사. 특히 card_id, version, equipment, component, symptom, safety_flag, provenance 보존 |
| `DocumentVersion` | 카드가 명시적으로 인용한 출처의 특정 판본. 구현 | `doc:<source_id>@<document_version>`. 각 부분에 3절 이스케이프 적용 | `source_id`, `document_version` |
| `Asset` | 특정 자산 인스턴스. 이번에는 기본 구성의 합성 장비만 연결 | `asset:<asset_id>`. 예: `asset:AS-EQ-0001-001` | `asset_id`, `equipment_id`, `code`, `equipment_type_id`, `type_code`, `is_synthetic: true`, `dataset_version: "DS-v1.0"`, `identity_basis: "from_catalog_default"`, `source_path` |
| `AssetPart` | 특정 Asset에 장착된 개별 부품. 설계만, 생성 0개 | `part:<asset_id>/<part_instance_id>`. 교체품은 새 ID 필요; CP 식별자를 임의로 실물 일련번호로 간주하지 않음 | 향후 `part_instance_id`, `asset_id`, `equipment_id`, `source_component_id`, `is_synthetic`, `installation_basis` |

label은 사람이 읽는 문자열이다. EquipmentType은 원본 equipment/component, CardVersion은 title, DocumentVersion은 `source_id @ document_version`, Asset은 `code (합성 장비)`, Symptom은 매핑 파일의 label을 쓴다.

DocumentVersion 예시: source_id `100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf`, document_version `Vickers General Product Support GBB9003 (8/84)`는 ID `doc:100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf@Vickers General Product Support GBB9003 (8%2F84)`가 된다.

## 5. 관계 타입과 제약

관계의 유일키는 `(source, target, type)`이다. 모든 source/target은 실제 nodes의 ID여야 한다. 역방향 관계를 중복 저장하지 않는다.

| 이름 | 출발 → 도착 / 의미 | 예시 | 필수 props |
|---|---|---|---|
| `PART_OF` | EquipmentType(kind=component) → EquipmentType(kind=equipment). 같은 equipment의 하위 카드 분류. 실제 장착·구성의 증거로 쓰지 않음 | `type:HPU/주 베인펌프 → type:HPU` | `basis: "card_classification"` |
| `ABOUT` | CardVersion → EquipmentType. 카드가 다루는 원본 설비·하위 분류 | `card:K-1001@1.0-draft-KB-20260929-A → type:HPU/주 베인펌프` | `basis: "card_equipment"` 또는 `"card_component"` |
| `DESCRIBES_SYMPTOM` | CardVersion → Symptom. 원문을 개념에 연결한 검수 전 후보 | 위 카드 → `sym:hpu-outlet-pressure-absent` | `review_status: "needs_review"`, `basis: "symptom_concepts"` |
| `CITES` | CardVersion → DocumentVersion. 판본이 명시된 원본 인용 | 위 카드 → 4절 문서 판본 ID | `locators`: 원문 locator의 중복 제거 배열; `source_ref_count`: 합쳐진 원본 항목 수 |
| `INSTANCE_OF` | Asset → EquipmentType(kind=equipment). 합성 마스터의 유형 FK 연결 | `asset:AS-EQ-0001-001 → type:HPU` | `basis: "catalog_equipment_type_id"`, `is_synthetic: true` |
| `INSTALLED_ON` | AssetPart → Asset. 특정 부품이 특정 자산에 장착됨. 설계만 | `part:AS-EQ-0001-001/part-example-001 → asset:AS-EQ-0001-001` (설계 예시) | 향후 `installation_basis` |

카드마다 설비 분류와 하위 분류에 ABOUT을 각각 1개씩 만든다. mes_equipment_id는 CardVersion props에 보존하지만 카드가 해당 자산의 사건 기록이라는 추가 관계를 추론하지 않는다. PART_OF와 INSTANCE_OF는 증상·원인·조치 추론 규칙이 아니다.

## 6. 교환 파일과 변환 정책

### 6.1 graph.json

정식 산출물: `docs/demo/kg/build/graph.json`. UTF-8 JSON. 최상위 키는 정확히 아래 두 개이며 개수·원본 해시·검증 이력은 별도 validation.json에 둔다.

```json
{
  "nodes": [
    {"id": "type:HPU", "type": "EquipmentType", "label": "HPU", "props": {"kind": "equipment", "equipment": "HPU", "is_common_scope": false}},
    {"id": "type:HPU/주 베인펌프", "type": "EquipmentType", "label": "주 베인펌프", "props": {"kind": "component", "equipment": "HPU", "component": "주 베인펌프", "is_common_scope": false}}
  ],
  "edges": [
    {"source": "type:HPU/주 베인펌프", "target": "type:HPU", "type": "PART_OF", "props": {"basis": "card_classification"}}
  ]
}
```

위는 **형식 예시**이며 전체 카드가 담긴 그래프가 아니다. 노드는 id/type/label/props, 관계는 source/target/type/props를 필수로 갖고 props는 객체다. 화면용 좌표·접힘 상태는 교환 파일에 기록하지 않는다.

### 6.2 판본 없는 출처

42개 출처 항목은 DocumentVersion·CITES로 변환하지 않는다. CardVersion.props.provenance.sources에 손실 없이 남기고 validation.json의 `unversioned_sources`에 card_id, card_version, 원본 source 객체, reason을 기록한다. 대상 카드는 `K-1101`, `K-1102`, `K-1103`, `K-1104`, `K-1105`, `K-1106`, `K-1107`, `K-1108`, `K-1109`, `K-1110`, `K-1111`이다.

그중 EV 접두어는 사건 근거다. 근거 사건을 문서 판본으로 바꾸거나 카드 version을 document_version으로 대입하지 않는다. 마스터의 DS-v1.0도 해당 카드 인용의 판본으로 소급 확정하지 않는다. 이 42건은 스키마 오류가 아니라 **공개해야 하는 보류 항목**이며, 스키마 위반 0건과 별도로 집계한다.

### 6.3 symptom_concepts.json

경로: `docs/demo/kg/symptoms/symptom_concepts.json`. 최상위 키는 아래 세 개다.

```json
{
  "concepts": [
    {
      "id": "sym:hpu-outlet-pressure-absent",
      "label": "펌프 출구 압력 없음",
      "definition": "펌프 운전 중 출구 압력계에 압력이 읽히지 않는 상태. 압력이 낮게 읽히는 상태와 구별한다."
    }
  ],
  "card_map": {
    "K-1001": ["sym:hpu-outlet-pressure-absent"],
    "K-1003": []
  },
  "needs_review": [
    {"card_id": "K-1001", "reason": "개념 정의와 연결의 사람 검수 전"},
    {"card_id": "K-1003", "reason": "safety_flag=true; symptom=null. 증상 생성·연결 보류"}
  ]
}
```

이 예시의 card_map은 일부만 보였다. **완성 매핑에는 원본 86개 card_id가 각각 1회 등장**해야 한다. 모든 배열 원소는 concepts의 ID이고 중복은 금지한다. 현재 원본은 card_id가 유일하므로 이 키를 쓴다. 향후 동일 card_id에 여러 version이 있으면 조용히 재사용하지 말고 빌드를 실패시켜 계약 개정을 요청한다.

증상 담당자는 원문 symptom과 적용 조건·제외·안전 근거를 함께 읽는다. “없음/낮음”, “정지/저속”, 관측/추정, 운전/재가동, 설비·매체, 단위·임계값 차이를 보존한다. 텍스트 유사도만으로 병합하지 않는다. 원인·조치·정비 시점만 있는 문장은 억지로 증상으로 만들지 않는다. 같은 의미의 병합 후보와 병합하지 않은 이유를 review.md에 쓴다.

- safety_flag=true인 **56장 전부**는 card_map을 빈 배열로 두고 needs_review에 사유를 넣는다. 증상이 있는 45장의 병합·연결 후보는 review.md에만 기록한다. 자동 생성 그래프에 해당 카드의 DESCRIBES_SYMPTOM은 **0개**다. 빌더도 이 조건을 독립적으로 검사한다.
- symptom=null인 **13장 전부**는 빈 배열과 검수 사유를 둔다. title·know_how로 대체해 증상을 만들어 내지 않는다.
- 두 집합의 합집합은 **58장**이다. 나머지 **28장**은 비안전·문자열 카드이며 의미를 확인한 후보만 연결한다. 후보도 needs_review에 등록하고 UI에서 “검수 전”으로 표시한다.
- 이번 매핑은 모든 카드의 연결/보류 이유를 needs_review에 담는다. 최종 needs_review는 고유 card_id 86개이고 reason은 비어 있지 않다. 검수 목록에 있다는 이유만으로 비안전 후보 연결을 삭제하지 않는다. 안전·null 보류는 위의 별도 강제 규칙이다.
- concepts는 실제 card_map에서 참조되는 후보만 포함한다. 안전 카드만을 위한 미연결 개념을 추가하지 않는다.
- 매핑 파일이 없으면 증상 노드·관계 없이 정상 생성하고 `symptoms_loaded: false`를 기록한다. 파일이 존재하지만 잘못되면 **실패**하며 조용히 무시하지 않는다.

## 7. 소유권과 에이전트 간 계약

| 담당 | 쓰기 소유 범위 | 읽기 입력 | 산출물 |
|---|---|---|---|
| 총괄 | `docs/demo/kg/` 바로 아래 문서 | 원본·이 계약·세 에이전트 산출물 | schema.md, 승인 후 README.md |
| 에이전트 1 변환 | `docs/demo/kg/build/` | KB, 합성 장비 마스터, schema.md, 있으면 symptom_concepts.json | build_graph.py, graph.json, validation.json |
| 에이전트 2 증상 | `docs/demo/kg/symptoms/` | KB, schema.md | symptom_concepts.json, review.md; 로직 파일을 만들면 같은 폴더에 보관 |
| 에이전트 3 시각화 | `docs/demo/kg/viz/` | schema.md, 자체 mock_graph.json, 나중에 실제 graph.json | index.html, demo_questions.md, mock_graph.json |

각 에이전트는 다른 소유 폴더를 읽기만 한다. 기존 저장소 파일은 어떤 에이전트도 수정하지 않는다. 최초 생성 후 보완은 이번 작업에서 새로 만든 자기 소유 산출물에만 허용한다.

총괄은 통합 시 에이전트 1의 스크립트를 실행하여 그 스크립트가 build/ 산출물을 재생성하게 한다. 타 에이전트 파일의 코드 수정이 필요하면 담당자에게 전달한다. 세 담당자는 서로의 완료를 기다리지 않는다.

### 에이전트별 실행 계약

1. **변환**: 표준 라이브러리 Python으로 읽기 전용 입력을 변환한다. 저장소 위치는 스크립트 위치로 계산한다. 인자 없이 실행하면 위 기본 경로를 쓰며, 출력은 build/에만 쓴다. 그래프와 검증 보고서는 전체 검사 후 저장한다. 오류 시 비정상 종료하고 이전 성공 그래프를 덮어쓰지 않는다. 매핑 파일이 없는 경로도 지원한다.
2. **증상**: 외부 모델 호출 없이 원문에 근거한 개념 후보·보류 이유를 작성한다. 안전 카드별 사유와 null 카드 목록을 빠짐없이 남긴다. 사람 승인이나 안전성이 확보되었다고 쓰지 않는다.
3. **시각화**: 작은 가짜 graph.json을 `viz/mock_graph.json`에 만들고 UI에 “가짜 데이터”를 명시한다. 최종 기본 데이터 주소는 `../build/graph.json`; 명시적인 `?mock=1`일 때만 가짜 데이터를 쓴다. 실제 파일 로드 실패 시 오류와 실행 안내를 표시하며 가짜 데이터로 자동 대체하지 않는다. CDN·추가 설치 없이 동작하는 HTML/CSS/JavaScript를 우선한다. 노드 타입/설비 필터, 노드 선택, 이웃 관계와 원문 props·인용 locator 확인을 지원한다. 합성 장비, 검수 전 증상, 실제 자산과 AssetPart가 없다는 한계를 표시한다. 데이터 문자열은 HTML로 실행하지 않는다. 키보드로 선택 가능한 목록을 함께 둔다.

로직이 있는 각 새 스크립트에는 실패가 명확한 assert 기반 자가 점검을 최소 1개 포함한다. Python은 `assert`, 화면 JavaScript는 예외를 던지는 작은 `assert` 함수를 사용할 수 있다. 테스트 프레임워크·새 의존성은 추가하지 않는다.

각 PC의 담당 AI에는 [분산 작업 계획](distributed-work-plan.md) 6절의 공통 프롬프트와 해당 역할 프롬프트, 배포된 공통 기준 커밋 SHA를 전달한다. 이 계약은 사용자 승인 완료이므로 계약 승인을 다시 기다리지 않고 배정된 폴더에서 구현한다.

## 8. 분담 구현의 검증과 통합

### 8.1 validation.json 최소 보고 내용

- `schema_version`, `source_hashes`(KB, 마스터, 매핑이 있으면 매핑), `symptoms_loaded`.
- `node_counts`: 6종 모두 표시; `edge_counts`: 6종 모두 표시; 총 노드/관계 수.
- `errors`: 위반 목록. 오류 0건일 때만 성공 종료.
- `orphan_nodes`: incident edge가 하나도 없는 노드의 ID/type/label 목록. 단방향 그래프의 진입 차수 0과 혼동하지 않는다.
- `unversioned_sources`: 42개 원본 인용 보류 항목.
- `review_card_ids`, `safety_review_card_ids`, `null_symptom_card_ids`; 매핑 미입력 상태에서도 안전·null 검수 대상은 원본에서 집계한다.

### 8.2 필수 검증

- 필드 형태, 허용 타입, ID 규칙, ID/관계 중복, 모든 관계 양끝 존재와 도메인/범위.
- 같은 equipment 내 PART_OF, 카드 원본과 ABOUT의 일치, Asset의 마스터 FK 일치.
- CardVersion 86장과 원본 필드 손실 없음; 문서 판본·locator·인용 수 추적.
- 안전 카드의 증상 연결 0개, null 카드 연결 0개, 미정의/미참조 개념 없음, 매핑/검수 목록의 원본 카드 집합 일치.
- 후보 매핑과 후보 노드·관계의 “needs_review” 표시; 기존 accepted 상태를 재사용하지 않음.
- 입력 파일 해시를 실행 전후 대조하여 원본 불변 확인. 재실행의 graph.json 바이트 동일성 확인.
- 자가 점검에는 잘못된 관계 끝점과 안전 카드 연결 등 실제 위반을 거부하는 경우를 포함한다.
- 화면의 실제 JSON 로드, 선택·필터, 인용·안전·검수 표시, 오류 상태를 확인한다. 실행하지 못한 화면 검증은 명시한다.
- 저장소 지침의 `python scripts/check_knowledge_publication.py`를 실행한다. 기존 무관 변경은 고치지 않고 실패가 있다면 분리 보고한다.

### 8.3 원본에서 계산한 예상 기본 집계

아래는 **아직 생성하지 않은 그래프의 계약상 예상치**다. 증상 수는 담당자 검토 후 정해진다.

| 노드 타입 | 증상 미입력 기준 예상 수 |
|---|---:|
| EquipmentType | 83 (설비 분류 7 + 하위 분류 76) |
| CardVersion | 86 |
| DocumentVersion | 92 |
| Symptom | 0 (통합 후 참조된 후보 수만큼 증가) |
| Asset | 10 (전부 합성; 실제 현장 자산 0) |
| AssetPart | 0 |
| 합계 | 271 + 통합 후 증상 후보 수 |

| 관계 타입 | 증상 미입력 기준 예상 수 |
|---|---:|
| PART_OF | 76 |
| ABOUT | 172 |
| CITES | 156 (원본 판본 포함 인용 180건을 묶음) |
| DESCRIBES_SYMPTOM | 0 (통합 후 비안전 후보 연결만 증가) |
| INSTANCE_OF | 10 |
| INSTALLED_ON | 0 |
| 합계 | 414 + 통합 후 증상 후보 연결 수 |

생성 후에는 예상치가 아니라 실제 검사 집계와 고아 노드 목록을 README에 기록한다. 스키마 위반 0건은 의미적 정확성·사람 검수 완료·검색 품질의 증거가 아니다.

### 8.4 구현 완료 후 실행 명령

저장소 루트 PowerShell:

```powershell
$env:PYTHONIOENCODING='utf-8'
python docs/demo/kg/build/build_graph.py
python scripts/check_knowledge_publication.py
python -m http.server 8765 --bind 127.0.0.1 --directory docs/demo/kg
```

화면 주소: `http://127.0.0.1:8765/viz/`. 포트가 이미 사용 중이면 비어 있는 포트로 바꾸고 실행 안내에 반영한다. 공통 기준 브랜치에는 문서만 포함한다. 위 시연 스크립트와 화면은 각 담당자가 구현한 뒤 실행한다.

## 9. 검수와 발표 표현

검수 우선순위는 안전 카드 56장, null 증상 13장(11장 중복), 비안전 증상 후보, 판본 누락 인용 42건이다. review.md에는 카드별 원문 증상, 후보 또는 보류 이유, 혼동하기 쉬운 개념, 사람이 확인할 사항을 적는다. 실제 작업 절차를 추가하거나 임계값을 새로 제안하지 않는다.

통합 완료 후 사용할 발표 문장:

> 온톨로지 스키마를 설계하고 카드를 그 스키마에 맞춰 그래프로 구성했습니다. 증상 연결은 사람 검수 전이며, 증상-원인-조치 모델링과 GraphRAG는 다음 단계입니다.

현재 단계에서 “그래프로 구성했다”를 완료 사실로 발표하지 않는다. GraphRAG 구현·성능 향상·정식 온톨로지를 달성했다는 문구는 사용하지 않는다. 정식 OWL/RDF 추론, 원인·조치 모델링, 실측 성능 평가와 운영 시스템 통합은 이번 범위 밖이다.

## 10. 최초 계약 작성 기록과 승인

- 구조 문서, 루트/관련 하위 지침, 원본 JSON, MES 식별자·마스터 로드 경로, 관련 검색 진입점을 읽었다.
- 읽기 전용 Python 집계와 assert로 카드 ID/버전의 유일성, 메타 총수와 실제 개수, 인용 수 분해를 확인했다.
- `python scripts/check_knowledge_publication.py`: `ok: true`, `errors: []`, `staged_python_checked: true`.
- 최초 계약 작성 단계의 산출물은 schema.md 하나였으며 당시 기존 파일·원본·staging을 수정하지 않았다.
- **2026-10-21 사용자가 이 계약과 세 문서의 공통 기준 브랜치 생성·커밋·push를 승인했다.** 다음 단계는 같은 기준 커밋을 받은 세 PC에서 역할별 구현이다. 문서 검증 통과를 그래프 통합 검증 통과로 표현하지 않는다.
