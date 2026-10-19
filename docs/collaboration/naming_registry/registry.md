# 레지스트리

사용법은 [`README.md`](README.md) 참고. 새 항목은 알파벳/가나다 순 유지 안 해도 됨 — 표만 정확하면 됨.

## 클래스 (Pydantic 모델 등)

| 이름 | 위치 | 뜻 | 담당자 |
|  ·  ·  | , ,  | 키오스크가 잡은 카메라 JPEG를 이 기기에서만 점수(사번 헤더 ). 이미지는 저장·전달하지 않음. 화면은 통과 3프레임이면 업무 화면으로 넘어가고, 5프레임 미달이면 거절 | 최재영 |
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
| `GET /api/outbox/pending` · `handovers` | `shiftlink/mes/server.py` | 아직 업로드 안 된(pending) 인계 원본 목록, 오래된 순. 각 항목은 저장한 본문 + `created_at` | 허재원 |
| `outboxItemView()` / `openOutbox()` · `#s-outbox` | `shiftlink/mes/web/pda.js` | PDA "업로드 대기 N건" 탭 시 대기 인계 내용 화면 | 허재원 |
| `required_context` · `attempts` · `observations` · `equipment_id` | PDA 인계 본문 | 추가 보존 필드. required_context는 `recipient_role`, `timing`, `channel`, `acknowledgement`, `context`; 시도·관측값은 제출 원본 유지 | 유현준 |
| `submitHandover()` · `queryApiPayload()` · `responseCards()` | `shiftlink/mes/web/pda.js` | PDA API 제출·검증 결과 표시. `shiftlink.handover.pending` localStorage 키로 미확인 인계 ID와 본문을 재전송까지 보존 | 유현준 |
| `renderHomeHandovers()` · `hoCheckEl()` · `#homeHoList` | `shiftlink/mes/web/pda.js`, `pda.html` | 홈 화면 처리·재확인 인계 항목 리스트와 항목별 「확인함」 체크. 체크는 `shiftlink.hoCheck.<handover_id>.<item_id>` localStorage 키(값: 체크 시각 ISO)에만 남고 서버 인계 상태는 바꾸지 않음. `item_id`가 없으면 `id`, 그것도 없으면 `i<인덱스>-<문구 해시>` | Claude |
| `normalFold()` · `S.foldOpen` | `shiftlink/mes/web/pda.js` | 센서 목록에서 범위 이탈·판정 불가는 항상 보이고 정상·정지 중 0은 「정상 N개 보기」로 접음. 펼침 상태는 목록 키(`ctx`, `obs`, `ev<turn.id>`)별로 3초 갱신 뒤에도 유지 | Claude |
| `SYMPTOM_LABELS` · `symptomsFor()` | `shiftlink/mes/web/pda.js` | 증상 질의 선택지 표시 이름(카드 ID → [표시 이름, 묶음 `sym`/`pre`]). 화면에만 쓰고 질의에는 원문 `symptom`을 보냄. T4 카드는 선택지에서 제외. 근거 `docs/design/pda_ui/symptom_labels_20261006.md` | Claude |
| `watchMes()` · `faultsFrom()` · `relevance()` · `#alert` | `shiftlink/mes/web/pda.js`, `pda.html` | PDA가 `/api/state`를 3초마다 읽어 설비별 고장 상황(경보·MES 증상 후보·범위 이탈)을 상단 `#alert` 띠(설비당 한 줄 `.alrow`, `ALERT_ROWS`=3줄까지)로 알리고, 범위 이탈 신호·카드 조건으로 증상 선택지 순서를 매김(`SIGNAL_WORDS`·`DIR_WORDS` 낱말 표). 원인 확정 아님 | Claude |
| `SIGNAL_NAMES` | `shiftlink/mes/scenarios/priority.py` | 기준정보 측정점에 이름이 없는 신호(gr_vib_rms 등)의 화면 이름. `expand()`가 이름이 신호 ID와 같을 때만 채우고, 저장된 구성의 센서 이상 시나리오 제목도 같은 이름으로 바꿈 | Claude |
| `Alarm.label` · `MesEngine.ALARM_LABELS` | `shiftlink/mes/contracts.py`, `shiftlink/mes/engine.py` | 경보 코드의 화면용 한글 이름(예: `AL-SENSOR-ANOMALY` → 센서값 범위 이탈). 스냅샷 `active_alarms[].label`로 MES 대시보드·PDA가 함께 씀. 예전 기록에는 없어 화면은 `code`로 대신함 | Claude |
| `operationMetrics()` · `#operations-window` | `shiftlink/mes/web/app.js`, `index.html` | 운영 표의 가동률(가동·정상 스냅샷 비율)·처리량(설비를 떠난 코일 수)·사이클 타임(머문 시간 평균)을 최근 스냅샷 180개로 계산. 코일 경로(`route`) 밖 설비는 처리량·사이클 타임 없음(지원 설비) | Claude |
| `#control-panel` 제어 바 · `#run-toggle` · `#scenario-lock` | `shiftlink/mes/web/index.html`, `app.js` | 시연 제어를 서랍 대신 탭 아래 한 줄 고정 바로. 시작·일시정지·재개를 `#run-toggle` 하나로, 시나리오는 원인 설비별 묶음, 잠김 사유를 미리 표시. 구성 관리는 이력·분석 탭으로 이동 | Claude |
| `renderLineBoard()` · `#line-board` · `renderUtilBars()` · `#util-bars` · `#board-clock` · `#board-notice` | `shiftlink/mes/web/app.js`, `index.html` | 생산 현황판 디자인: 코일 이송 라인 설비 카드(상태 막대·가동률 게이지·처리량·사이클·대기), 설비별 가동률 막대, 헤더 시계, 하단 안전 공지 띠(고정 문구). 경보는 `#incident-summary`(지금 확인할 위치)에서만 | Claude |

| `handover_upload` | `db/aiven_schema.sql` (Aiven) | PDA 인계 본문 원본 업로드 표. `handover_id`(64자) 기본키, `payload` JSON, `content_sha256`. 합성 데이터라 원문 포함(§4.11 예외, 실데이터면 해시만) | Claude |
| `upload_pending()` · `python -m shiftlink.mes.uploader` | `shiftlink/mes/uploader.py` | outbox `pending` → Aiven. 같은 ID·같은 해시 `uploaded`, 다른 해시 `conflict`(로컬 보류), 끊기면 `pending` 유지 후 재시도(`--interval`, 기본 30초) | Claude |
| `list_uploads()` · `python -m shiftlink.mes.handover_board` | `shiftlink/mes/handover_board.py` | Aiven `handover_upload` SELECT만. 노트북 다음 조 목록. 접속 실패는 오프라인 배지 | 최재영 |
| `pending_handovers()` / `mark_handover()` | `shiftlink/mes/storage.py` | 업로드 대기 인계 조회, `handover_outbox.status` 변경(`pending`·`uploaded`·`conflict`) | Claude |

| `query_upload` | `db/aiven_schema.sql` (Aiven) | `/api/query` 기록 업로드 표. `query_id`(`Q-`+uuid4), `latency_ms`, `no_knowledge`, `payload`(질문·답·인용 카드·모델). 원문 포함 §4.11 예외(합성) | Claude |
| `query_log` · `save_query()` / `pending_queries()` / `mark_query()` | `shiftlink/mes/storage.py` | `MesService.query()`가 답을 돌려줄 때마다 로컬에 한 줄 기록. 업로더가 `query_upload`로 올림 | Claude |
| `FaceEngine` · `cosine()` | `shiftlink/face/engine.py` | 얼굴 검출(YuNet) → 정렬 → 임베딩(SFace). `embed(frame)`은 가장 큰 얼굴의 L2 정규화 128차원, 없으면 None. cv2 객체를 주입받아 모델 없이 테스트 | 최재영 |
| `FaceStore` | `shiftlink/face/store.py` | 사번당 `<employee_id>.npz`(임베딩+`model_version`)만 저장, 권한 600, 원본 이미지 저장 없음. 모델 버전이 다르면 `load`가 None(재등록). 기본 경로 `~/shiftlink/data/face/templates` | 최재영 |
| `decide()` · `Verdict` · `frame_score()` | `shiftlink/face/verify.py` | 1:1 판정: 프레임별 등록 임베딩 중 최고 코사인, 통과 프레임이 `min_pass` 이상이면 통과 | 최재영 |
| `FACE_NEED` · `FACE_FRAMES` · `GET /api/face/config` · `SHIFTLINK_FACE_BYPASS` | `shiftlink/face/__init__.py`, `shiftlink/pda/__main__.py` | 통과 기준은 여기만(0.363, 5장 중 3장). 화면은 이 응답을 따른다. `SHIFTLINK_FACE_BYPASS=1`일 때만 건너뛰기(기본 끔, 서버는 127.0.0.1) | 최재영 |
| `score_login_jpeg()` · `POST /api/face/frame` · `faceVerdict()` | `shiftlink/face/verify.py`, `shiftlink/pda/__main__.py`, `shiftlink/mes/web/pda.js` | 키오스크가 잡은 카메라 JPEG를 이 기기에서만 점수(사번 헤더 `X-Employee-Id`). 이미지는 저장·전달하지 않음. 응답의 threshold·need·frames로 판정. 이름은 화면 표시만 | 최재영 |
| `showToast()` · `POST /api/pda/exit` · `stop_kiosk()` | `shiftlink/mes/web/pda.js`, `shiftlink/pda/__main__.py` | 로그인 통과 후 2초간 `이름님 로그인 되었습니다`. 홈의 종료는 키오스크 창을 닫고 PDA 프로세스를 끝낸다 | 최재영 |
| `MANIFEST` · `fetch_models()` | `shiftlink/face/models.py` | OpenCV Zoo 고정 커밋의 YuNet 2023mar·SFace 2021dec URL과 sha256. 받은 뒤 해시가 다르면 삭제하고 실패. 가중치는 커밋하지 않음 | 최재영 |
| `SHIFTLINK_FACE_DIR` · `MODEL_VERSION` · `DEFAULT_THRESHOLD` · `python -m shiftlink.face` (`fetch`·`enroll`·`verify`·`delete`·`bench`) | `shiftlink/face/__init__.py`, `__main__.py` | 얼굴 데이터 폴더(기본 `~/shiftlink/data/face`), 등록 모델 식별자(`sface-2021dec`, `employee.face_model_version`과 같은 값), OpenCV 문서 기본 임계값 0.363(튜닝 전), 웹캠 점검·등록·삭제·지연 측정 CLI | 최재영 |

| `outbox_counts()` · `GET /api/outbox` | `shiftlink/mes/storage.py` · `server.py` | 업로드 상태별 건수 `{handover, query}` × `{pending, uploaded, conflict}` + `is_synthetic`. PDA '업로드 대기 N건' 표시용(읽기 전용) | Claude |
| `answer_mode` · `SHIFTLINK_ANSWER_MODE` | `shiftlink/agent/pipeline.py`, `shiftlink/mes/query.py` | `model`(기본, 모델이 답을 씀) · `extract`(질의 모드, 모델 호출 없이 1위 카드에서 E1 답을 만듦, 판정기·검증기·안전 공지는 그대로). 시연 경로 `build_query_pipeline()`은 10/7부터 `hybrid`가 기본(`extract`는 선택). 인계 모드는 항상 모델. 채택 근거 `docs/experiments/answer-extractive-prereg-20261006.md` | Claude |
| `SHIFTLINK_JUDGE_MODEL` · `OllamaModel(judge_model=…)` | `shiftlink/edge/ollama.py` | 답 없음 판정기가 쓰는 Ollama 모델 이름. 인자 > 환경변수 > 답변 모델 순. E1 추출 모드에서는 답변 모델을 부르지 않아 판정 모델 하나만 Jetson에 올리면 된다 | Claude |
| `answer_mode="hybrid"` · compose 층 `H` · `hybrid_needs_e1()` | `shiftlink/agent/pipeline.py`, `compose.py` | 질의 모드에서 (SFT) 모델이 답을 쓰고, 인용 카드가 보류·금지를 담는데 답이 재기동·충전·개방을 권하면(문장 안에 부정 표현이 없을 때) E1 답으로 대체. 모델 결과가 비었거나 막히면 E1. 규칙은 10/6 사전 등록으로 고정(sft1006 `PREREG_sft_hybrid.md`). 시연 경로의 기본(10/7 확정, `build_query_pipeline()`·`deploy/install_service.sh`). 라이브러리 기본(`FixedPipeline`)은 `model` | Claude |
| `JudgeUnavailableError` · `FixedPipeline(judge_strict=…)` · `judge_model_status()` | `shiftlink/agent/pipeline.py`, `shiftlink/mes/query.py` | 판정기가 실행되지 않으면(모델 없음·Ollama 중단·시간 초과) strict 파이프라인이 예외를 던지고 서버는 `/api/query`에 503 `{error, retry:true}`로 답한다(시연 서버는 strict, 평가 스크립트 기본은 이전처럼 건너뜀). 서버 시작 시 판정 모델이 Ollama에 있는지 확인해 `ok·missing·unreachable`을 경고 로그로 남긴다 | Claude |

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
| `scanTarget()` · `releaseContext()` · `failScan()` · `staleResponse()` · `alertTarget()` · `#s-alertGo` | `shiftlink/mes/web/pda.js`, `pda.html` | PDA 설비 확정 안전 경로. 구성에 있는 code만 확정(같은 유형 대체 없음), 스캔 실패·구성 외 code 시 확정 해제, 질의 시점 설비와 다른 응답 버림, 고장 알림 행은 equipment_id 고정 후 확인 화면 `#s-alertGo`를 거쳐 변경 | Claude |
| `safetyStack()` · `renderWaitSafety()` · `renderAskSafety()` · `#waitCards` · `#askSafety` · `responseCards(response, cards, local, eq)` | `shiftlink/mes/web/pda.js`, `pda.html` | PDA 안전 관문. 대기·질의·결과·시도 화면에 로컬 안전 카드(safety_basis 펼침)를 표시, 서버 안전 공지는 `cardFits`로 현재 설비와 대조해 불일치면 본문 대신 "설비 불일치" 경고. `local`은 `rankCards()` 결과로 조치 이유·조건 3상태를 붙임 | Claude |
| `appendMesContext()` | `shiftlink/mes/web/pda.js` | 인계 작성의 'MES 기록 불러오기'를 다시 눌러도 입력에 이미 있는 측정값·이벤트 줄은 붙이지 않음. 새 줄이 없으면 `null` | Claude |
| `pendingText()` · `.conn-status` | `shiftlink/mes/web/app.js`, `index.html`, `style.css` | 지표를 아직 못 낼 때 운전 상태별 말(운전 정지·일시정지·집계 중). 화면을 열면 `/api/runs/{id}/replay`로 최근 스냅샷을 먼저 채워 가동률을 바로 표시. 헤더 상태는 버튼 모양 대신 시계 아래 점+문구(실시간 수신 중) | Claude |
| `dashSummary()` · `renderDash()` · `#s-dash` · `.mes-link` | `shiftlink/mes/web/pda.js`, `pda.html` | PDA 홈의 '대시보드'는 작업자용 요약 화면(라인 상태·확인 필요 설비·후속 대기·제품 보류·인계 미완료/업로드 대기). `/api/state`를 새로 읽지 않고 감시 폴링 값을 씀. 전체 MES 대시보드는 홈 머리줄 `MES` 버튼(개발용, 완료 시 삭제) | Claude |

## 현장 해결 기록 → 카드 초안 (2026-10-13)

| 이름 | 위치 | 뜻 | 담당자 |
| --- | --- | --- | --- |
| `resolution` | `POST /api/handover` 본문(PDA) | 질의가 '해당 지식 없음'일 때 작업자가 해결하고 남긴 기록. `question`·`symptom`·`actions`(순서 있는 목록, 항목은 문자열 또는 `{action, result}` — result는 그 조치 직후 본 결과, 선택)·`result`(`resolved`·`temporary`·`failed`)·`verification`·`evidence`(질의의 MES 근거). 없으면 기존 인계와 같다 | Claude |
| `check_resolution()` · `build_draft()` · `GENERATOR`(`field-resolution-v1`) · `ID_RANGE`(K-7000~K-7999) | `shiftlink/mes/field_draft.py` | 해결 기록을 검사하고 규칙 기반으로 `KnowledgeCard` 초안(status=draft, grade=L0, split=dev, confidence=0.0)을 만든다. 증상은 작업자 문장 뒤에 MES 주 증상(첫 이상 신호)을 붙인다: `… (MES: 유압유 온도가 높아짐)`. LLM 없음. 상태 조건은 활성 구성의 정상 범위로 서버가 다시 계산한다. `failed`는 초안을 만들지 않는다 | Claude |
| `card_drafts` · `save_card_draft()` · `list_card_drafts()` · `next_card_id()` | `shiftlink/mes/storage.py` | 검수 대기 초안 저장소. `draft_id`(=card_id, K-7000~) 기본키, `handover_id` 유일. `status`는 `pending_review`·`invalid`, `review_flags`에 안전 표현·자리표시자·lint·검증 오류를 담는다. 검색(kb_cards.json·질의 파이프라인)에는 나가지 않는다 | Claude |
| `GET /api/card-drafts` · `card_drafts()` | `shiftlink/mes/server.py` | 검수 대기 초안 목록(읽기 전용). 승인·반려 API는 아직 없다. PDA는 호출하지 않는다 | Claude |
| `draft` · `created` · `reason` | `/api/handover` 응답 | 해결 기록이 있을 때만 붙는다. `reason`: `pending_review`·`invalid`·`attempt_only`·`already_exists`·`supporting`(기존 초안에 지지 근거로 붙음)·`contradicting`(같은 조치가 효과 없었던 반대 근거). `mes_recovered`: 저장 시점 MES로 본 정상 복귀 여부. 카드 내용은 싣지 않는다 | Claude |
| `resolutionError()` · `resolutionPayload()` · `draftNotice()` · `evidenceSummary()` · `openResolve()` · `#s-resolve` | `shiftlink/mes/web/pda.js`, `pda.html` | PDA '해결하면 기록 남기기' 화면. 저장은 인계 흐름(`submitHandover`, localStorage 대기 인계)을 그대로 쓰고, 저장 후 확인 문구만 보인다 | Claude |
| `prepare()` · `draft_from()` · `matches()` · `merge()` · `completeness()` · `THIN_MIN` · `OVERLAP_MIN` · `GENERIC_STEMS` | `shiftlink/mes/field_draft.py` | 같은 설비 + 이상 조건 하나 이상 공통 + 조치 전체 어간 겹침 50% 이상(확인·점검 같은 공통어 `GENERIC_STEMS` 제외)이면 해결 기록마다 공통 조건만 남기면서 새 초안 대신 기존 검수 대기 초안의 근거로 붙고 빈 단계 결과를 채운다. 조치가 다르면 다른 원인 후보로 따로 둔다. `review_flags.completeness`: `missing`(기록이 쌓이면 줄어드는 빈칸)·`operator`(부품·시나리오·안전 근거 — 운영자만)·`resolved_records`·`contradicting_records`·`ready`(빈칸 없음 + 해결 2건 이상 + 반대 근거 없음 = 승격 권장 표시, 자동 승격 없음). `thin_record`(짧은 기록)·`temporary`(제목 `[임시조치]`, 해결 기록이 붙으면 해제) | Claude |
| `card_draft_records` · `has_draft_record()` · `update_card_draft()` | `shiftlink/mes/storage.py` | 인계 → 초안 연결(`relation`: `origin`·`supporting`·`contradicting`). 인계 하나는 초안 하나에만 반영된다(재전송 중복 방지) | Claude |
| `HOLD_RESOLUTION_UPLOAD` | `shiftlink/mes/uploader.py` | True면 `resolution`이 실린 인계는 Aiven에 올리지 않고 로컬 pending으로 둔다. 기능 확정 시 False(10/13 결정) | Claude |
| `check_with_mes()` · `match_score()` · `mes_check` · `records[].mes_recovered` | `shiftlink/mes/field_draft.py`, `server.py` | 인계 저장 시점의 서버 MES 스냅샷으로 '해결'을 확인한다: 질의 때 벗어난 신호가 모두 정상 범위 + 그 설비 경보 없음 + 질의 뒤 같은 실행(run_id)에서 `recovered` 또는 그 설비 `alarm_cleared` 이벤트 = `recovered`. 실행이 바뀌었거나 복구 기록이 없으면 `recovery_unconfirmed`에 이유를 남기고 '확인 불가'. 승격 권장의 해결 건수는 MES로 확인된 것만 세고, 작업자 '해결'과 MES가 다르면 운영자 몫에 '해결 표기와 MES 불일치'. 확인 안 된 기록은 초안에 붙기만 하고 빈칸을 채우지 않는다. 새 기록은 `match_score`가 가장 높은 초안 하나에 붙는다(`OVERLAP_MIN` 0.4). 정지 중이라 0인 신호(`zero_when_stopped`)는 조건에서 뺀다 | Claude |
| `query_evidence` · `save_query_evidence()` · `get_query_evidence()` · `save_handover_with_draft()` | `shiftlink/mes/storage.py`, `server.py` | (10/13 P1) `/api/query`가 쓴 MES 근거를 (run_id, simulated_at, equipment_id)로 로컬 보관(업로드 대상 아님). 해결 기록 판정은 PDA가 돌려보낸 근거 대신 이 값으로 한다 — 없으면 근거 없음, MES 확인 '확인 불가 — 서버 질의 기록에 없는 근거'. 인계 저장과 초안 생성·병합은 `save_handover_with_draft` 한 트랜잭션(초안 계산이 실패하면 인계도 남지 않음) | Claude |
| `FIELD_GENERATOR_PREFIX` · `_field_steps()` | `shiftlink/agent/compose.py` | (10/13 P1) E1 답에서 `provenance.generator`가 `field-resolution`인 현장 카드는 `know_how` 앞 두 문장 대신 단계(조치 → 결과, 빈 결과 생략)를 모두 쓴다. 문서 기반 카드의 E1은 그대로 | Claude |
| `resolution_sessions` · `create/get/update_resolution_session()` · `/api/resolution/start` · `/api/resolution/{session_id}/step` · `/api/resolution/{session_id}/finish` · `GET /api/resolution/{session_id}` | `shiftlink/mes/storage.py`, `server.py` | (10/13) 현장 조치 기록 세션. 조치 시작 때 조치 전 MES(서버 보관 질의 근거, 없으면 그 순간 스냅샷)를 `before`로, 조치마다 완료 때 그 순간 센서값과 변화 문장(`result_text`, 예: 유압유 온도 78→70)을, 마무리 때 MES 판정(`verdict`: recovered·not_yet·unconfirmed, `suggested_result`)을 서버가 기록. 위험 조치(`SAFETY_WORDS`)는 `lockout`(예·아니오·해당 없음) 필수. 저장 시 `status` open→saved가 인계·초안과 한 트랜잭션 | Claude |
| `resolution.session_id` · `cause` · `component_id` · `mes_verdict` · `lockout_answers` · `cause_unknown` · `CAUSE_UNKNOWN` · `out_of_range()` · `delta_text()` · `verdict_of()` | `POST /api/handover`, `shiftlink/mes/field_draft.py` | (10/13) 세션으로 저장하는 해결 기록: 작업자는 본 것·원인(`원인 모름` 허용)·부품·결과만 보내고 조치·단계 결과·MES 근거는 세션에서 서버가 채운다. 초안: 부품=선택한 부품(`mes_component_code`), 시나리오=MES `support_scenario`, 노하우 첫 줄 `원인: …`, 제목 `… — 원인: …`, `review_flags.lockout_answers`(안전 근거는 만들지 않음). 묶음 비교에 원인 포함. 응답 `draft.mes_verdict` | Claude |
| `openResolve()` · `renderResolve()` · `completeStep()` · `finishResolve()` · `riskyAction()` · `mesSummary()` · `resolveError()` · `sessionPayload()` · `RISK_WORDS` · `#s-resolve`(조치 기록) | `shiftlink/mes/web/pda.js`, `pda.html` | (10/13) PDA 조치 기록 화면. '해당 지식 없음' 답의 **조치 시작 — 기록하면서 작업** → 본 것 1줄·부품 칩(MES 추천) → 조치 칩/직접 입력 → 위험 조치는 잠금 응답(예·아니오·해당 없음) 뒤 **완료**(서버가 센서값 자동 기록) → **조치 마무리**(MES 판정, 결과 미리 선택) → 원인 칩/직접 → 인계와 함께 저장(`resolution.session_id`). 예전 해결 기록 화면(`resolutionPayload` 등)은 대체 | Claude |
| `DELTA_MIN` | `shiftlink/mes/field_draft.py` | (10/13) 단계 결과 센서 변화의 최소 폭(0.5). 그보다 작은 흔들림은 '센서값 변화 없음' | Claude |
| `similar_kb_cards()` · `drafts[].similar_kb_cards` | `shiftlink/mes/field_draft.py`, `GET /api/card-drafts` | (10/13) 승격 전 확인: 초안 증상·조건으로 기존(문서 기반) 카드 묶음을 검색해 겹칠 수 있는 카드(card_id·title·condition_status)를 붙인다. 기준값 미만이면 빈 목록, 현장 카드는 제외 | Claude |
| `scripts/field_card_promote.py` (`list`·`promote`·`restore`, `.before-field-promote` 백업) | `scripts/` | (10/13) 시연용 승격·원복: 정식 검수 탭 전까지 사람이 초안·겹치는 카드·빈칸을 보고 `--yes`로 1장을 L1(accepted·kb)로 카드 묶음에 넣는다. 승격 권장이 아니면 `--force` 필요. 첫 승격 때 원본 백업, `restore`로 그대로 되돌림. `--remote`는 Jetson 카드 묶음 + MES 서비스만 재시작 | Claude |
| `SHIFTLINK_SIM_LINK`(기본 1) · `_sim_link()` · `RESTART_ACTION`('재가동 (라인 복구 시작)') · `action_suggestions[].source`(`mes_recovery`·`mes_restart`·`field_record`) · `steps[].mes_linked` · `_events_for_check()`(`pending`) · `actionChips()` | `shiftlink/mes/server.py`, `field_draft.py`, `web/pda.js` | (10/13) 시연·모의 MES 연동: PDA 조치 기록의 'MES 단계' 칩을 완료하면 모의 MES에도 그 복구 조치를 수행(순서대로만), 세 단계 뒤 켜지는 재가동 칩은 라인 복구 시작. 직접 입력한 조치는 설비를 바꾸지 않는다. 재가동 직후 다음 틱 전의 대기 이벤트(경보 해제)도 해결 확인에 포함. 실제 설비 연동 시 `SHIFTLINK_SIM_LINK=0` | Claude |
| `GET /api/analytics` · `analytics.summary()` · `analytics.live_incidents()` · `analytics.load_history()` · `resolution_sessions()` · `handover_payloads()` | `shiftlink/mes/analytics.py`, `server.py`, `storage.py` | (10/14) PDA 대시보드 분석. 사건(`incident_id`·`equipment_id`·`alarm_code`·`alarm_at`·`action_at`·`recovered_at`·`action`·`cause`·`result`·`handover_id`·`card_id`)을 저장 4주 이력과 이 실행(경보 이벤트+조치 기록 세션+인계)에서 같은 형식으로 모아 `loss`(이번 주 직접·후속 대기)·`repeats`(4주 같은 설비·경보 2회+, 조치별 재발)를 계산. 계산 결과 필드 `outcome`(recurred·watching·held·open)·`recurred_after_days`·`recurrence_of`·`down_min` | Claude |
| `docs/data/analytics/line_history.json` · `scripts/gen_line_history.py` | `docs/data/analytics/` | (10/14) 대시보드용 합성 4주 사건 이력(`_meta.start/end/adopted_at`). 서버는 `_meta.end`를 실행 시작 시각에 맞춰 옮겨 쓴다 | Claude |
| `card_ids`(조치 기록 시작 본문·세션) · `draft.reason = card_used` · `action_suggestions[].source = card_step`(`card_id`·`step_id`·`n`·`full`·`risky`) · `steps[].card_step` · `_card_step_chips()` · `_kb_card_map()` · `liveRisky()` | `shiftlink/mes/server.py`, `web/pda.js` | (10/15) 카드 답에서도 조치 기록 시작. 답에서 본 카드를 세션에 남기고(카드 묶음에 있는 ID만), 그 카드의 단계를 조치 칩으로 띄운다. 칩으로 완료한 조치는 `card_step`으로 남고(그 세션에서 본 카드의 단계만), 위험 여부는 단계 원문으로 판정. 카드를 본 세션은 새 카드 초안을 만들지 않는다 | Claude |
| `repeats[].resolved_recurred` · `repeats[].methods`(`card`·`other` → `count`·`recurred`·`no_change`) · `repeats[].actions[].method`·`no_change` · 사건 `card_method`·`no_change` | `shiftlink/mes/analytics.py` | (10/15) 대시보드: '해결'로 닫았는데 재발한 건수(근본 원인 미확인 배지), 같은 증상 안에서 카드 방법 대 카드 밖 방법, 모든 조치가 센서를 못 움직였는데 닫은 기록. 저장 이력은 카드 ID가 있으면 카드 방법 | Claude |
| `homeWatch()` · `renderHomeWatch()` · `#homeWatch`(`.watch-row`) · `.eq-prog` · `S.dlFrom` | `shiftlink/mes/web/pda.js`, `pda.html` | (10/15) 홈 「현재 설비 상황」: 머리글에 정상·이상 감지, 이상 설비 줄(없으면 숨김), "지켜볼 설비" 최대 3줄 — 해결 후에도 반복된 증상(원인 미확인) 먼저, 그다음 최근 조치해 재발 기간(7일) 안인 증상. 누르면 그 증상의 지난 조치 목록, 이전은 홈으로(`S.dlFrom`) | Claude |
| `analytics.knowledge_gap()` · `/api/analytics`의 `knowledge`(`no_knowledge`·`drafts`·`pending`·`approved`·`approved_ids`·`answered`) · `storage.query_payloads()` · `#anGap`(`.an-flow`) | `shiftlink/mes/analytics.py`, `server.py`, `storage.py`, `web/pda.*` | (10/15) 대시보드 지식 공백 — 합성 없이 이 MES DB의 실제 기록만: 지식 없음 질의(`query_log`) → 카드 초안(`card_drafts`) → 검수 대기 → 승인(초안 카드 ID가 `kb_cards.json`에 있음) → 카드로 답(승인 카드를 인용한 질의). 기간 필터 없음(누적). 시연 대본 `docs/testing/knowledge-gap-demo.md`, 리허설 `tests/test_knowledge_gap_rehearsal.py` | Claude |
| `production_lines[].production_standard`(`annual_capacity_t`·`effective_hours_per_year`·`avg_coil_weight_t`·`planned_hours_per_week`) · `analytics.coils_per_hour()` · `_halts_line()` · `/api/analytics`의 `production`(`planned`·`lost`·`produced`·`coils_per_hour`)과 `loss[]`(`stop_min`·`coils`·`halts_line`) | `docs/data/reference/00_plant_and_relations.json`, `shiftlink/mes/analytics.py` | (10/15) 정지 손실을 못 만든 코일 개수로: 라인을 세운 정지 시간 × 표준 생산 속도(1.5 Mt ÷ 7,000 h ÷ 20 t ≈ 시간당 10.7개, 가상 값·공개 자료 근거 `docs/design/pda_ui/coil_loss_basis_20261015.md`). 이전 `direct`·`induced`·`total`은 삭제 | Claude |
| `restLine()` · `.an-rest` | `shiftlink/mes/web/pda.js`, `pda.html` | (10/15) 대시보드 정지 손실·반복 증상 칸 아래 "정지 없음 · …" / "반복 없음 · …" 한 줄로 나머지 설비를 보인다 — 칸 하나에 설비 10대 전체. 합성 이력은 4주 32건·설비 10대(`scripts/gen_line_history.py` D·E 이야기 추가) | Claude |
| `lossView()`(`lostPct`·`producedPct`·`rows[].planPct`·`kind`) · `.loss-head`(`.ring.r-made`·`.ring.r-lost` conic-gradient·`.loss-sum`·`.legend`) · `.loss-row`(`--sw`) | `shiftlink/mes/web/pda.js`, `pda.html` | (10/15) 정지 손실 보기 — %는 계획 생산량 대비: 생산 링(회색 생산 + 끝부분 손실)과 손실 링(이번 주 손실 = 100%, 설비별 몫), 범례 "HPU-01 17개 · 0.9%", 설비 줄 "MTBF · MTTR · 정지 N분"(계획 대비 %는 요약에만, `planPct`는 계산만 유지). 설비 종류 색 `--hpu`·`--gr`·`--rt`·`--cv`·`--pdp`·`--cau` | Claude |
| `loss[].reliability`(`failures`·`mttr_min`·`mtbf_h`) | `shiftlink/mes/analytics.py`, `web/pda.*` | (10/15) 정지 손실 줄에 설비 MTBF(평균 고장 간격)·MTTR(평균 수리 시간) — 설비 단위·4주, 그 설비 고장 전부. MTTR = 정지 시간 합 ÷ 고장 수, MTBF = (672 h − 정지 시간 합) ÷ 고장 수 | Claude |
| `.dash-status` | `shiftlink/mes/web/pda.html` | (10/15) 대시보드 상태 한 줄 — 라인 상태 + 확인 필요·후속 대기·제품 보류 칩(0이면 조용히, 0이 아니면 그 칩만 의미 색). 이전 3칸 타일(높이 약 90px)을 대신해 분석 칸에 자리를 준다 | Claude |
| `RING_MAX`(5) · `lossView().slices`·`rows[].color` | `shiftlink/mes/web/pda.js` | (10/15) 손실 링 조각 6개까지 — 상위 5대 설비 종류 색 + 회색 '기타'. 설비 줄 표지 색도 같은 규칙. 링 `role=img`·`aria-label` 요약. 같은 날 접근성 점검: 보조 터치 48(상태 칩·조치 효과 행·홈 지켜볼 설비 행), 보조 글자 tx-3(4.7:1) → tx-2(7:1), 카드 방법 표시는 본문색 글자 + 파란 표지 | Claude |
| `--tx-2`(밝은 팔레트 #465b73 → #3c5066) · `.home-watch.busy` | `shiftlink/mes/web/pda.html`, `pda.js` | (10/15) 홈 접근성 점검(ui-ux-pro-max + 루브릭 A1·A2): 보조 글자색을 한 단계 진하게 해 모든 바탕에서 7:1 이상(밝은 바탕 6.4 → 7.6), 챗봇 글자 #1a4aa6(5.4 → 7.2), 종료·MES 48px. 이상이 있으면 지켜볼 설비 2줄(`busy`)로 칸 안에 맞춤 | Claude |
| `#anErr`(`.an-err`) · `#dashAlert` · `.sr-only` | `shiftlink/mes/web/pda.html`, `pda.js` | (10/15) 웹 인터페이스 가이드라인 반영: 분석 불러오기 실패 표시("10초 뒤 다시 시도 · 아래는 이전 값", 성공하면 숨김), 화면 낭독기용 고장 알림(이상·후속 대기 수가 바뀔 때만 `aria-live`), 홈 `#homeWarnings` `aria-live`, 모든 버튼 `touch-action: manipulation`, 반복 증상 배지를 아랫줄로(누르는 줄 제목 한 줄) | Claude |
| `lossDonut()` · `madeRingArcs()` · `arcPath()` · `LOSS_CHART` · `svg.loss-chart`(`.g-made`·`.g-lost`·`.lbl`·`.ctr`) · `.loss-sum` | `shiftlink/mes/web/pda.js`, `pda.html` | (10/15) 손실 링을 큰 SVG 도넛으로 — 조각마다 바깥에 설비 코드·못 만든 코일 수 라벨, 12시부터 시계 방향, 같은 쪽 라벨 겹침 밀기. 두 그래프는 SVG 하나에 같은 크기·같은 중심 높이로 나란히(왼쪽 생산 링, 오른쪽 손실 도넛), 요약은 위 표 `table.loss-sum`(계획·생산 \| 손실·손실률) | Claude |
| `#homeMade`(`.made-only`) · `renderHomeMade()` · `#homeTodo` · `#homeWatch`(`.busy`·`.todo`, `S.homeWatchRows`) · `homeWatch()[].fix` | `shiftlink/mes/web/pda.js`, `pda.html` | (10/15, v2 홈) 홈 '대시보드' 칸: 지표 3개 아래 이번 주 생산 링(대시보드 생산 링과 같은 그림) · 처리할 일 칩(후속 대기·제품 보류 코일, 0이면 숨김) · 이상 상자(이상 없으면 숨김) · 지켜볼 설비 1줄(아랫줄에 '효과 있던 조치'). 이상이나 처리할 일이 있으면 지켜볼 설비는 숨김 | Claude |
| `openDashboard()` · `#s-dashboard`(`#dashboardBack`) | `shiftlink/mes/web/pda.js`, `pda.html` | (10/15) v2 홈 '상세 보기' → 대시보드(Depth 1). 예전 `#s-dash`(·`toDash`)를 대신해 라인 상태 줄 + 분석 4칸(정지 손실·반복 증상·조치 효과·지식 공백)을 그린다. ↶ 뒤로 = 홈 | Claude |
| `analytics.calendar_weeks()` · `KST` · `/api/analytics`의 `week_end`·`window_start`·`window_end` | `shiftlink/mes/analytics.py`, `web/pda.js` | (10/19) 대시보드 기간을 달력 주(월~일, 한국 시각)로: 정지 손실·생산은 이번 주 월요일 0시부터, 반복 증상·MTBF는 이번 주 포함 4주. `*_end`는 다음 주 월요일 0시(미포함) — PDA는 하루 전(일요일)으로 표시. 예전 `now − 7일/28일` 대신. 이전 서버(필드 없음)면 PDA는 `now`로 대체 | Claude |
| `#eqListModal`(`.eqm`·`#eqListTitle`·`#eqListCount`·`#eqListRows`·`#eqListX`·`#eqListClose`) · `openEqList()` · `S.dashRows` · `dashSummary().waitingRows` · `WAIT_REASON_TXT` · `.eq-tile-go` | `shiftlink/mes/web/pda.js`, `pda.html` | (10/19) 대시보드 이상·연쇄 정지 설비 카드 오른쪽 위 ›(1대 이상일 때) → 설비 목록 팝업(설비·상태·상세 보기). 닫기·✕·Esc·바깥 클릭으로 닫힘 | Claude |
| `.panel-head`·`.panel-toggle`(`#expandEquipment`·`#expandChat`) · `.sensor-list`·`.sensor-row`·`.sensor-state` · `.chat-plus`(`#chatPlus`) · `#chatEq` · `#doSearch.stop`(`cancelChat()`) · `answerParts()`·`.ans-list` · `botHead()` · `clock()` · `.hdr-ic`·`.hdr-sep` | `shiftlink/mes/web/pda.js`, `pda.html` | (10/19) 장비·채팅 화면 시안 반영: 패널 머리 전환(누르면 그 칸 전체, 다시 누르면 함께 보기), 센서 목록(이상→정지→정상), +로 추천 질문·관측값 입력, 답 대기 중 보내기→정지(취소), 답변 첫 문장+• 목록, 상단 메뉴 아이콘. `#splitWorkspace`·`#toggleChat`·`#chatCancelDock`·`setSensorsOpen()` 삭제 | Claude |
| `sessionStorage['shiftlink.fromPda']` | `shiftlink/mes/web/app.js` | (10/19) MES를 PDA 키오스크(`?from=pda`)에서 열었다는 표시를 탭에 기억 — MES 안에서 옮겨 다녀도 「PDA」 버튼이 파이 PDA로 간다 | Claude |
| `openAlertGo()` (`#s-alertGo` 삭제) | `shiftlink/mes/web/pda.js`, `pda.html` | (10/19) 알림 「설비 확인」 → 확인 화면 없이 누른 순간의 `equipment_id` 설비 채팅으로 바로 이동. `#s-alertGo`·`#alertGoOk`·`S.alertPick`·`S.alertBack` 삭제. `alertTarget()`은 유지 | Claude |
| `.workspace-gutter` · `.gut-btn`(`#expandChat` ‹ · `#expandEquipment` ›) · `setWorkspaceMode()` | `shiftlink/mes/web/pda.js`, `pda.html` | (10/19) 장비·채팅 보기 전환을 가운데 줄(전체 높이 세로선 + 테두리 없는 `.gut-box`: ‹ 채팅 확대 · 굵은 막대 너비 조절 · › 장비 확대)로: ‹ 채팅 전체, › 장비 전체, 손잡이(`.workspace-divider`) 드래그로 폭 조절. 전체 화면에서는 남은 버튼 하나(라벨 '함께 보기')가 되돌린다. 패널 머리의 `.panel-toggle` 삭제. 600px 이하(위아래 배치)에는 없음 | Claude |
