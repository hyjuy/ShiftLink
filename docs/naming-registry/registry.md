# 레지스트리

사용법은 [`README.md`](README.md) 참고. 새 항목은 알파벳/가나다 순 유지 안 해도 됨 — 표만 정확하면 됨.

## 클래스 (Pydantic 모델 등)

| 이름 | 위치 | 뜻 | 담당자 |
| --- | --- | --- | --- |
| `Condition` | `shiftlink/agent/schemas.py` | 카드 적용 조건 | 유현준 |
| `Provenance` | `shiftlink/agent/schemas.py` | 출처·근거 | 유현준 |
| `KnowledgeCard` | `shiftlink/agent/schemas.py` | K-01 지식 카드 스키마 | 유현준 |
| `Event` | `shiftlink/agent/schemas.py` | 사건 스키마 (기존 9필드) | 유현준 |
| `Artifact` | `shiftlink/agent/schemas.py` | 산출물 스키마 | 유현준 |
| `QueryRequest` | `shiftlink/agent/router.py` | 질의 모드 입력 | 유현준 |
| `HandoverRequest` | `shiftlink/agent/router.py` | 인계 모드 입력 | 유현준 |
| `RoutedRequest` | `shiftlink/agent/router.py` | 라우터 판정 결과 | 유현준 |
| `ToolProvider` | `shiftlink/agent/pipeline.py` | 도구 5종 Protocol | 유현준 |
| `PipelineResult` | `shiftlink/agent/pipeline.py` | 고정 파이프라인 출력 | 유현준 |
| `FixedPipeline` | `shiftlink/agent/pipeline.py` | 고정 파이프라인 본체 | 유현준 |
| `Configuration` | `shiftlink/mes/contracts.py` | 모의 MES 구성 버전(설비·관계·경로·시나리오·배치 묶음, config_id=sha256) | 유현준 |
| `EquipmentConfig` | `shiftlink/mes/contracts.py` | 설비 구성(논리 위치 equipment_id + 합성 자산 asset_id + 프로필) | 유현준 |
| `SignalSpec` | `shiftlink/mes/contracts.py` | 신호 정의(단위·정상범위·필수 여부) | 유현준 |
| `RelationConfig` | `shiftlink/mes/contracts.py` | 구성 내 관계(공급·구동·인터록·소재) — 미승인 제안 `Relation`과 별개 | 유현준 |
| `ScenarioSpec` | `shiftlink/mes/contracts.py` | capability 기반 모의 시나리오 정의 | 유현준 |
| `SignalEffect` | `shiftlink/mes/contracts.py` | 시나리오의 신호 override(capability+signal) | 유현준 |
| `LayoutGroup` | `shiftlink/mes/contracts.py` | UI 맵 배치 그룹 | 유현준 |
| `MesEngine` | `shiftlink/mes/engine.py` | 결정적 모의 MES 엔진(Configuration 소비) | 유현준 |
| `MesStorage` | `shiftlink/mes/storage.py` | 모의 MES SQLite 저장(구성·변경 이력 포함) | 유현준 |
| `MesService` | `shiftlink/mes/server.py` | 모의 MES HTTP 서비스(구성 적용 포함) | 유현준 |
| `ObserverAdapter` | `shiftlink/mes/adapters.py` | 모델 관측 허용 목록 경계(as_of) | 유현준 |
| `SourceSpan` | `shiftlink/rag/extraction.py` | F-02 추출 원문 위치 | 최재영 |
| `Negation` | `shiftlink/rag/extraction.py` | F-02 부정 표현 | 최재영 |
| `Withdrawal` | `shiftlink/rag/extraction.py` | F-02 철회 표현 | 최재영 |
| `ExtractionResult` | `shiftlink/rag/extraction.py` | F-02 추출 결과 묶음 | 최재영 |

> 01_고도화_초안 §7.2~7.4가 제안하는 신규 엔티티(약 25종: `ProductionLine`, `Relation`, `ActionCandidate` 등)는 **아직 미승인·미구현**이라 여기 안 올림. 실제로 클래스를 만들면 그때 등록.

## 함수 (모듈 간 공개 API)

| 이름 | 위치 | 뜻 | 담당자 |
| --- | --- | --- | --- |
| `route_request()` | `shiftlink/agent/router.py` | 입력을 질의/인계 모드로 판정 | 유현준 |
| `lookup_equipment()` | `shiftlink/agent/tools.py` | 도구: 장비 조회 | 유현준 |
| `search_cards()` | `shiftlink/agent/tools.py` | 도구: 카드 검색 | 유현준 |
| `list_handover()` | `shiftlink/agent/tools.py` | 도구: 인계 목록 | 유현준 |
| `propose_handover()` | `shiftlink/agent/tools.py` | 도구: 인계 제안 | 유현준 |
| `get_checklist()` | `shiftlink/agent/tools.py` | 도구: 체크리스트 조회 | 유현준 |
| `main()` | `shiftlink/data/__init__.py` | 데이터 파이프라인 실행 계획 CLI 진입점 | 유현준 |
| `from_catalog()` | `shiftlink/mes/configuration.py` | 기준정보 JSON → 기본 Configuration | 유현준 |
| `load_draft()` | `shiftlink/mes/configuration.py` | 사용자 구성 초안 로딩(스키마 검사, 해시 재계산) | 유현준 |
| `validate()` | `shiftlink/mes/configuration.py` | 구성 의미 검증(오류 목록 반환) | 유현준 |
| `diff()` | `shiftlink/mes/configuration.py` | 구성 변경 분류(교체/추가/제거/신호/경로) | 유현준 |
| `to_payload()` / `from_payload()` | `shiftlink/mes/configuration.py` | Configuration ↔ JSON dict | 유현준 |
| `finalize()` | `shiftlink/mes/configuration.py` | 내용 기반 config_id(sha256) 채움 | 유현준 |

> `search_cards()`에 `scope_id`·`source_kind` 필드 추가가 고도화 초안 §4.5(Q4)에서 제안됐지만 **미결**이므로 현재 공개 시그니처에는 포함하지 않는다. 결정되면 여기 시그니처 변경 이력을 한 줄 추가할 것.

## 환경변수 (`.env`)

| 이름 | 뜻 | 담당자 |
| --- | --- | --- |
| `MYSQL_DATABASE_URL` | Aiven MySQL 접속 문자열 | 유현준 |
| `GENERATION_API_KEY` | 합성 데이터 생성 외부 API 키 | 최재영 |
| `OLLAMA_HOST` | Ollama 서버 주소 | 최재영 |

## ID 접두어 규칙 `[기존 — 01_고도화_초안 §7.1]`

새 엔티티에 ID를 붙일 때 이 규칙을 따른다: **`접두어-4자리`** (예: `EV-0031`, `K-0001`). 기존 형식을 절대 깨지 않는다.

| 접두어 | 대상 |
| --- | --- |
| `EV-` | Event (사건) |
| `K-` | KnowledgeCard |
| `PT-` | EventPrototype (신규 제안, 미승인) |
| `R-<영역 2자>` | 요구사항 ID (예: `R-PL01`, `R-SC01`) — §13.1 |

새 엔티티 종류가 생기면(예: 관계·매뉴얼 등, 전부 미승인) 접두어를 여기 먼저 등록하고 코드에 쓴다.
