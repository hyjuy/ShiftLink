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
| `HandoverMethod` | `shiftlink/agent/schemas.py` | D-27 T4 인수인계 방법 (v1.0) | 유현준 |
| `ResolutionStep` | `shiftlink/agent/schemas.py` | D-28 T3 단계 (v1.0) | 유현준 |
| `FailedAttempt` | `shiftlink/agent/schemas.py` | D-29 시도·실패 기록 (v1.0) | 유현준 |
| `TypePayload` | `shiftlink/agent/schemas.py` | 암묵지 유형별 payload (v1.0) | 유현준 |
| `V09ConversionResult` | `shiftlink/agent/compat.py` | v0.9 → v1.0 변환 결과 | 유현준 |
| `ConversionIssue` | `shiftlink/agent/compat.py` | 변환 findings 1건 (code·severity·field·message) | 유현준 |
| `V09ConversionBatch` | `shiftlink/agent/compat.py` | v0.9 일괄 변환 집계 (counts·issue_counts·중복 ID·auto_accepted) | 유현준 |
| `QueryRequest` | `shiftlink/agent/router.py` | 질의 모드 입력 (공용 접근자: `equipment_ids`·`search_text`·`k`·`shift`·`observation_map()`) | 유현준 |
| `HandoverRequest` | `shiftlink/agent/router.py` | 인계 모드 입력 (공용 접근자 동일) | 유현준 |
| `Observation` | `shiftlink/agent/router.py` | 관측 신호 1건 (signal·value·unit) — §4.2 조건 판정 입력 | 유현준 |
| `RoutedRequest` | `shiftlink/agent/router.py` | 라우터 판정 결과 (+ `route_reason`) | 유현준 |
| `ToolProvider` | `shiftlink/agent/pipeline.py` | 도구 6종 Protocol (v1.0) | 유현준 |
| `ToolSpec` | `shiftlink/agent/tools.py` | 4.8 도구 표 1행(입력·출력·저장소·읽기 전용) | 유현준 |
| `PipelineResult` | `shiftlink/agent/pipeline.py` | 고정 파이프라인 출력 (mode·tool_results·output·model_calls·no_knowledge·cache_hit·audit) | 유현준 |
| `AuditRecord` | `shiftlink/agent/pipeline.py` | 실행 1스텝 감사 기록 (4.12) | 유현준 |
| `ResponseCache` | `shiftlink/agent/pipeline.py` | 질의+검색결과 해시 키 모델 출력 캐시 (4.8) | 유현준 |
| `FixedPipeline` | `shiftlink/agent/pipeline.py` | 고정 파이프라인 본체 | 유현준 |
| `AgentResponse` | `shiftlink/agent/response.py` | D-26~29 응답 구조화 모델 (v1.0). `handover_method`는 `handover_methods[0]` 파생 | 유현준 |
| `SafetyNotice` | `shiftlink/agent/response.py` | 안전 공지 렌더링 (v1.0) | 유현준 |
| `CardCitation` | `shiftlink/agent/response.py` | 인용 카드 + 등급 표기 (4.10) | 유현준 |
| `HandoverCandidate` | `shiftlink/agent/response.py` | 인계 등록 후보 (수락 전·미저장, F-04) | 유현준 |
| `StepRender` | `shiftlink/agent/response.py` | T3 단계 렌더링 (v1.0) | 유현준 |
| `HandoverMethodRender` | `shiftlink/agent/response.py` | T4 인계 방법 렌더링 (v1.0). `card_id`로 카드별 구분 | 유현준 |
| `RestartFailure` | `shiftlink/agent/response.py` | 재가동 실패 렌더링 (v1.0) | 유현준 |
| `InMemoryToolProvider` | `shiftlink/rag/retrieval.py` | 인메모리 KB 검색 구현 (v1.0) | 유현준 |
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
| `OllamaModel` | `shiftlink/edge/ollama.py` | 로컬 Ollama 어댑터 — 파이프라인이 부르는 단일 ModelCall (호출당 1회, 재시도 없음) | 허재원 |
| ~~`ModelCallError`~~ | — | 2026-09-24 삭제. A 계약 §3에 따라 표준 예외(`ValueError`·`TimeoutError`·`ConnectionError`·`NotImplementedError`)로 대체 — `agent`가 `edge`를 import하지 않아도 되게 | 허재원 |
| `EventSpec` | `shiftlink/data/scenario.py` | 합성 사건 명세. 작성자가 정하는 것만 담고 ID·split·카나리는 제외 | 허재원 |
| `Stabilizer` | `shiftlink/vision/classify.py` | 웹캠 분류 결과를 연속 N프레임·신뢰도 기준으로 한 번만 확정 | 허재원 |

> 01_고도화_초안 §7.2~7.4가 제안하는 신규 엔티티(약 25종: `ProductionLine`, `Relation`, `ActionCandidate` 등)는 **아직 미승인·미구현**이라 여기 안 올림. 실제로 클래스를 만들면 그때 등록.

## 함수 (모듈 간 공개 API)

| 이름 | 위치 | 뜻 | 담당자 |
| --- | --- | --- | --- |
| `convert_card_v09()` | `shiftlink/agent/compat.py` | v0.9 카드를 v1.0으로 변환 (needs_review/converted/rejected) | 유현준 |
| `convert_cards_v09()` | `shiftlink/agent/compat.py` | v0.9 카드 일괄 변환 → `V09ConversionBatch` | 유현준 |
| `Condition.evaluate()` | `shiftlink/agent/schemas.py` | 조건 1건 결정적 평가 (True/False/None=미관측) — §4.2 단일 출처 | 유현준 |
| `route_request()` | `shiftlink/agent/router.py` | 입력을 질의/인계 모드로 판정 | 유현준 |
| `lookup_equipment()` | `shiftlink/agent/tools.py` | 도구: 장비 조회 | 유현준 |
| `search_cards()` | `shiftlink/agent/tools.py` | 도구: 카드 검색 | 유현준 |
| `search_safety_cards()` | `shiftlink/agent/tools.py` | 도구: 안전 카드 전수 검색 (v1.0) | 유현준 |
| `list_handover()` | `shiftlink/agent/tools.py` | 도구: 인계 목록 | 유현준 |
| `propose_handover()` | `shiftlink/agent/tools.py` | 도구: 인계 제안 | 유현준 |
| `get_checklist()` | `shiftlink/agent/tools.py` | 도구: 체크리스트 조회 | 유현준 |
| `verify_tool_provider()` | `shiftlink/agent/tools.py` | 어댑터의 도구 6종·읽기 전용·범위 밖 도구 계약 검사 | 유현준 |
| `check_tool_output()` | `shiftlink/agent/tools.py` | 도구 출력의 문서화된 필드 존재 검사 | 유현준 |
| `build_response()` | `shiftlink/agent/response.py` | 도구 결과 → 응답 구조화 (v1.0) | 유현준 |
| `GUARD_FALLBACK_ANSWER` · `guard_blocked()` | `shiftlink/agent/response.py` | 규제에 막힌 답을 빈 문자열 대신 수치 기준 확인 문장으로 바꿈 | 최재영 |
| `render_response()` | `shiftlink/agent/response.py` | 응답 → 결정적 텍스트 렌더 (v1.0) | 유현준 |
| `validate_response()` | `shiftlink/agent/response.py` | 응답 불변식 검증 (v1.0). `[code] message` 형식 반환 | 유현준 |
| `is_model_retryable()` | `shiftlink/agent/response.py` | 검증 결함이 모델 재시도 대상인지 판정 (§4.3) | 유현준 |
| `check_card_rules()` | `shiftlink/rag/retrieval.py` | 카드 P5 규칙 검사 (v1.0) | 유현준 |
| `main()` | `shiftlink/data/__init__.py` | 데이터 파이프라인 실행 계획 CLI 진입점 | 유현준 |
| `from_catalog()` | `shiftlink/mes/configuration.py` | 기준정보 JSON → 기본 Configuration | 유현준 |
| `load_draft()` | `shiftlink/mes/configuration.py` | 사용자 구성 초안 로딩(스키마 검사, 해시 재계산) | 유현준 |
| `validate()` | `shiftlink/mes/configuration.py` | 구성 의미 검증(오류 목록 반환) | 유현준 |
| `diff()` | `shiftlink/mes/configuration.py` | 구성 변경 분류(교체/추가/제거/신호/경로) | 유현준 |
| `to_payload()` / `from_payload()` | `shiftlink/mes/configuration.py` | Configuration ↔ JSON dict | 유현준 |
| `finalize()` | `shiftlink/mes/configuration.py` | 내용 기반 config_id(sha256) 채움 | 유현준 |
| `kb_cards()` · `GET /api/kb/cards` | `shiftlink/mes/server.py` | PDA 화면용 검색 대상 카드(accepted/kb/L1)와 예시 인계 기록. kb 파일만 읽음 | 허재원 |
| `record_scan()` · `POST /api/equipment/scan` | `shiftlink/mes/server.py` | 웹캠 CNN 확정 결과 `{class, conf, device_id, ts}` → `scan_id`·`equipment_id`·`code` 붙여 메모리 기록(최근 50건). 여러 대인 형식은 equipment_id 최소 설비 | 허재원 |
| `recent_scans()` · `GET /api/equipment/scan/recent?limit=` | `shiftlink/mes/server.py` | 최신 인식 결과부터 limit(1~50, 기본 5)개 | 허재원 |
| `post_scan()` | `shiftlink/vision/classify.py` | 확정 클래스를 Jetson에 POST, 실패는 False만 반환. `--server`·`--device-id` 인자 | 허재원 |
| `observation_facts()` | `shiftlink/rag/retrieval.py` | 관측값마다 카탈로그 정상범위 판정(low/normal/high). 검색 파생 상태와 같은 범위 | 최재영 |
| `build_messages()` | `shiftlink/edge/ollama.py` | 모드·질문·관측값·카드 → Ollama `/api/chat` messages (+카나리 제외 카드 ID) | 허재원 |
| `card_context()` | `shiftlink/edge/ollama.py` | 카드를 `MODEL_CARD_FIELDS`로 축약하고 카나리 카드 제거 (§4.4·§5). `mode="handover"`면 T4 `handover_method`도 포함 | 허재원 |
| `main()` | `shiftlink/edge/__main__.py` | 픽스처 카드 + 실제 Ollama로 파이프라인 1건 실행하는 진입점 | 허재원 |
| `build_scenario()` | `shiftlink/data/scenario.py` | 사건 명세 → 검증된 합성 시나리오 + split 배정 제안 (배정표는 고치지 않음) | 허재원 |
| `resolve_prototype()` | `shiftlink/data/scenario.py` | 원형 식별 4키로 계보 판정. 기존·미등록 배정이 해시보다 우선 | 허재원 |
| `assign_split()` | `shiftlink/data/scenario.py` | 분할 계약 §63 해시 배정 (`shiftlink-split-v1:<group_id>` SHA-256 mod 12) | 허재원 |
| `generate_narrative()` | `shiftlink/data/narrative.py` | 사건 원장 + 페르소나 → 합성 작업일지 원문. 등록부는 갱신하지 않음 | 허재원 |
| `build_prompt()` | `shiftlink/data/narrative.py` | 정답지·타 페르소나 관측·sealed를 제외한 Stage A 프롬프트 조립 | 허재원 |
| `shop_floor_names()` | `shiftlink/data/narrative.py` | 내부 ID → 현장 호칭(`EQ-0008` → `RT-03`) 매핑 | 허재원 |
| `lint_card()` / `lint_cards()` | `shiftlink/data/card_lint.py` | 카드 작성 가이드 §2·§3·§5·§7 중 **스키마가 못 잡는** 유형 경계·안전 표시를 자문 수준으로 지적 | 허재원 |
| `preprocess()` | `shiftlink/vision/classify.py` | 웹캠 프레임 → CNN 입력(224, ImageNet 정규화). `train.py` 검증 전처리와 같아야 함 | 허재원 |
| `verdict()` | `eval/qa/report.py` | 채점 JSON 한 문항의 자동 판정 (hit/partial/abstain_ok/miss) | 최재영 |
| `render_report()` | `eval/qa/report.py` | 채점 JSON + 문항 파일 → 마크다운 검수표. 틀린 문항이 앞 | 최재영 |

> `search_cards()`에 `scope_id`·`source_kind` 필드 추가가 고도화 초안 §4.5(Q4)에서 제안됐지만 **미결**이므로 현재 공개 시그니처에는 포함하지 않는다. 결정되면 여기 시그니처 변경 이력을 한 줄 추가할 것.

2026-09-22: `search_cards(*, query, equipment_ids, k=5, observations=None)`로 확장. 일반 검색도 안전 검색과 같은 관측값·조건 평가를 사용한다.

2026-09-30: `search_cards(*, query, equipment_ids, k=5, observations=None, handover=False)`. `handover=True`(파이프라인 인계 모드)일 때만 T4 카드의 근거 사건 문장(`kb_cards.json`의 `evidence_text`)을 낮은 가중치로 점수에 더한다.

2026-10-01: 웹캠 분류 클래스 상수 `CLASSES` = `("HPU", "GR", "RT", "CV", "CAU", "PDP")`는 `shiftlink/vision/__init__.py`에 둔다(담당 허재원). 라즈베리파이에 pydantic을 두지 않으려고 `schemas.Equipment`를 import하지 않고 복제하며, 일치는 `tests/test_vision.py`가 검사한다.

2026-09-24: `MODEL_CALL_ERRORS` = `(NotImplementedError, TimeoutError, ConnectionError, ValueError)` — `shiftlink/edge/ollama.py`의 어댑터가 올리는 오류 4종 묶음(담당 허재원). 호출자가 `except MODEL_CALL_ERRORS`로 한 번에 잡을 때만 쓰고, 개별 판단은 예외 타입으로 한다.

2026-09-24: D-26~29 §4.4의 모델 입력 화이트리스트 상수 `MODEL_CARD_FIELDS`는 `shiftlink/edge/ollama.py`에 둔다(담당 허재원). 모델 프롬프트를 만드는 유일한 지점이라 여기 한 곳에만 있어야 한다. 파이프라인이 나중에 같은 화이트리스트를 쓰게 되면 이 상수를 import하고 복제하지 않는다.

## 환경변수 (`.env`)

| 이름 | 뜻 | 담당자 |
| --- | --- | --- |
| `MYSQL_DATABASE_URL` | Aiven MySQL 접속 문자열 | 유현준 |
| ~~`GENERATION_API_KEY`~~ | 폐기(2026-09-30): 외부 API 생성을 하지 않기로 함 ([N-7](../../reports/N-7_생성API_비교.md)) | 최재영 |
| `OLLAMA_HOST` | Ollama 서버 주소 | 최재영 |
| `SHIFTLINK_QUERY_MODEL` | MES 질의 모델 태그(기본 `exaone3.5:2.4b-instruct-q4_K_M`) | 유현준 |

## 라즈베리파이 HTTP 클라이언트 (2026-10-02)

| 이름 | 위치 | 역할 | 담당 |
|---|---|---|---|
| `MesHTTPClient` | `shiftlink/communication/http_client.py` | 기존 Jetson MES API를 호출하는 표준 라이브러리 클라이언트. 새 서버·프록시 없이 사용 | Codex |
| `HTTPClientError` | `shiftlink/communication/http_client.py` | HTTP 오류 코드와 연결·응답 오류 구분. `status_code=None`은 HTTP 응답 코드가 없는 오류 | Codex |
| `MesHTTPClient.send_scan()` | `shiftlink/communication/http_client.py` | 클래스·신뢰도·장치 ID·시각 전송. POST 자동 재시도 없음 | Codex |
| `MesHTTPClient.get_recent_scans()` | `shiftlink/communication/http_client.py` | 최근 인식 기록 조회 | Codex |
| `MesHTTPClient.get_state()` | `shiftlink/communication/http_client.py` | 현재 MES 상태·센서값 조회 | Codex |
| `MesHTTPClient.get_events()` | `shiftlink/communication/http_client.py` | `after_sequence` 이후 이벤트 조회. 커서 관리는 호출자 담당 | Codex |
| `MesHTTPClient.query()` | `shiftlink/communication/http_client.py` | 질문과 선택 설비 또는 scan_id 전송. 질의 전용 타임아웃 사용 | Codex |
| `MesHTTPClient.save_handover()` | `shiftlink/communication/http_client.py` | 호출자가 지정한 handover_id와 메모 전송. 재전송 시 같은 ID 유지 | Codex |
| `--api-only` · `serve(api_only=True)` | `shiftlink/mes/__main__.py`, `shiftlink/mes/server.py` | Jetson에서 API만 제공하고 PDA 정적 화면은 라즈베리파이의 기존 `shiftlink.pda`가 제공. 기본 실행은 기존 화면 제공 유지 | 유현준 |

## MES 질의·인계 HTTP 계약 (2026-10-02)

| 이름 | 위치 | 뜻 | 담당자 |
| --- | --- | --- | --- |
| `query()` · `POST /api/query` | `shiftlink/mes/server.py` | 질문 + 최근 웹캠 설비 + 현재 MES 관측값 → FixedPipeline. 본문 `question`(1~4000자), 선택 `scan_id` 또는 `equipment_id`(직접 선택), `k`. 두 식별자는 동시 사용 불가. 생략하면 최신 인식 사용, 바뀐 scan_id는 거절 | 유현준 |
| `query_service()` / `build_query_pipeline()` | `shiftlink/mes/query.py` | 허용 관측값 추출 및 accepted/kb 검색 + Ollama 모델 연결. 현재 서비스의 파이프라인 재사용 | 유현준 |
| `answer` · `cited_card_ids` · `safety_notices` | `/api/query` 응답 | AgentResponse의 답변·인용 카드 ID·안전 공지(`card_id`, `safety_basis`, `stop_conditions`). `review_queue`, `no_knowledge`, `unverified_card_ids`도 기존 스키마 그대로 | 유현준 |
| `scan` · `evidence` | `/api/query` 응답 | 사용한 인식 기록(직접 선택이면 null), MES 근거(`run_id`, `equipment_id`, `equipment_code`, `simulated_at`, `measurements`, `alarms`). 원인 정답·시나리오 ID 제외 | 유현준 |
| `record_handover()` · `POST /api/handover` | `shiftlink/mes/server.py` | 본문 `handover_id`(1~64자), `memo_text`(1~4000자). ID 기준 SQLite outbox 저장. 동일 내용 재전송 200, 같은 ID 내용 변경 409 | 유현준 |
| `save_handover()` / `get_handover()` | `shiftlink/mes/storage.py` | 원본 JSON 영속 저장·조회. `handover_outbox.handover_id`가 기본키 | 유현준 |
| `status` · `duplicate` · `created_at` | `/api/handover` 응답 | 로컬 저장 상태 `pending`, 기존 동일 기록 여부, 최초 저장 시각. `handover_id`, `is_synthetic` 포함 | 유현준 |
| `required_context` · `attempts` · `observations` · `equipment_id` | PDA 인계 본문 | 추가 보존 필드. required_context는 `recipient_role`, `timing`, `channel`, `acknowledgement`, `context`; 시도·관측값은 제출 원본 유지 | 유현준 |
| `submitHandover()` · `queryApiPayload()` · `responseCards()` | `shiftlink/mes/web/pda.js` | PDA API 제출·검증 결과 표시. `shiftlink.handover.pending` localStorage 키로 미확인 인계 ID와 본문을 재전송까지 보존 | 유현준 |

| `handover_upload` | `db/aiven_schema.sql` (Aiven) | PDA 인계 본문 원본 업로드 표. `handover_id`(64자) 기본키, `payload` JSON, `content_sha256`. 합성 데이터라 원문 포함(§4.11 예외, 실데이터면 해시만) | Claude |
| `upload_pending()` · `python -m shiftlink.mes.uploader` | `shiftlink/mes/uploader.py` | outbox `pending` → Aiven. 같은 ID·같은 해시 `uploaded`, 다른 해시 `conflict`(로컬 보류), 끊기면 `pending` 유지 후 재시도(`--interval`, 기본 30초) | Claude |
| `list_uploads()` · `python -m shiftlink.mes.handover_board` | `shiftlink/mes/handover_board.py` | Aiven `handover_upload` SELECT만. 노트북 다음 조 목록. 접속 실패는 오프라인 배지 | 최재영 |
| `pending_handovers()` / `mark_handover()` | `shiftlink/mes/storage.py` | 업로드 대기 인계 조회, `handover_outbox.status` 변경(`pending`·`uploaded`·`conflict`) | Claude |

두 POST의 HTTP 본문 한도는 64 KiB. `HO-`는 기존 인계 ID 접두어이며 PDA UUID(HTTP LAN에서는 시간+난수)를 붙인다. 기존 정본 인계 ID는 변경하지 않는다. outbox는 로컬 저장이며 클라우드 업로드는 별도 작업이다.

## systemd 서비스 (`deploy/install_service.sh`)

| 이름 | 장비 | 뜻 | 담당자 |
| --- | --- | --- | --- |
| `shiftlink-mes` | Jetson | `python -m shiftlink.mes --host 0.0.0.0 --port 8000` 자동 시작 (작업계획 E1) | 허재원 |
| `shiftlink-vision` | 라즈베리파이 | `python -m shiftlink.vision.classify --headless --server ...` 자동 시작 (작업계획 D2) | 허재원 |

## 파이 화면 (`deploy/install_pda.sh`, `shiftlink/pda`)

화면은 파이가 서빙하고 Jetson은 API만 맡는다 (2026-10-02).

| 이름 | 장비 | 뜻 | 담당자 |
| --- | --- | --- | --- |
| `shiftlink.pda` | 라즈베리파이 | `python3 -m shiftlink.pda` (`~/shiftlink/app`) — 화면 서버 127.0.0.1:8080(`/pda.html` PDA, `/` MES 대시보드), `/api/*` 는 Jetson으로 프록시, Chromium 키오스크 | 허재원 |
| `shiftlink-pda.desktop` | 라즈베리파이 | `~/.config/autostart/` — 데스크톱 로그인 시 위 앱 자동 실행 (작업계획 D3) | 허재원 |
| ~~`pda-kiosk`~~ | 라즈베리파이 | 폐기(2026-10-02): Jetson `/pda.html`을 여는 키오스크 스크립트. Jetson이 API만 서빙하게 되어 `shiftlink-pda`로 대체 | 허재원 |

## ID 접두어 규칙 `[기존 — 01_고도화_초안 §7.1]`

새 엔티티에 ID를 붙일 때 이 규칙을 따른다: **`접두어-4자리`** (예: `EV-0031`, `K-0001`). 기존 형식을 절대 깨지 않는다.

| 접두어 | 대상 |
| --- | --- |
| `EV-` | Event (사건) |
| `K-` | KnowledgeCard |
| `PT-` | EventPrototype (신규 제안, 미승인) |
| `MD-` | ManualDocument (매뉴얼 문서 — 설계 예제 `docs/data/`에서 사용, 미승인 제안) |
| `MS-` | ManualSection (매뉴얼 절 — 위와 동일) |
| `R-<영역 2자>` | 요구사항 ID (예: `R-PL01`, `R-SC01`) — §13.1 |

새 엔티티 종류가 생기면(예: 관계·매뉴얼 등, 전부 미승인) 접두어를 여기 먼저 등록하고 코드에 쓴다.
