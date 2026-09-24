# B 인계: PC LLM 어댑터와 현재 호출 계약

작성일: 2026-09-24. 최초 확인 기준: `aa299da`. 같은 날짜의 A 관측값 검증 작업을 §2에 반영했다(작업 트리 변경).

목표: Jetson 없이 PC에서 질의 1건을 `검색 → 실제 모델 → 검증된 응답`으로 연결한다. 이 문서는 코드 변경이나 모델 설치를 수행한 결과가 아니다. **§1~4는 현재 구조 설명과 B 구현 지침, §5는 신규 반환·오류 계약 제안, §6~8은 실행 예제와 작업 분담**이다. 제안된 출력·오류 계약은 A/B가 확인한 뒤 구현하며 기존 구현 완료로 해석하지 않는다.

## 1. 읽을 파일과 현재 호출 순서

| 파일 | 역할 |
|---|---|
| [router.py](../../shiftlink/agent/router.py) | 입력 검증, query/handover 분기 |
| [pipeline.py](../../shiftlink/agent/pipeline.py) | 도구 → 모델 → 검증 → 최대 1회 재시도 |
| [retrieval.py](../../shiftlink/rag/retrieval.py) | InMemoryToolProvider, 카드 검색·조건 판정 |
| [response.py](../../shiftlink/agent/response.py) | AgentResponse 구성·검증·렌더링 |
| [tools.py](../../shiftlink/agent/tools.py) | 미구현 기본 도구 계약 |
| [test_router_pipeline.py](../../tests/test_router_pipeline.py) | 호출 순서·라우팅 예제 |

```text
FixedPipeline(model=adapter, tools=provider).run(payload)
  → route_request(payload)
      → RoutedRequest(mode, request=Pydantic 모델)
  → _run_tools(request)
      → lookup_equipment(equipment_ids=...)
      → search_cards(query=..., equipment_ids=..., k=..., observations=...)
      → ranked_cards에 일반 검색 결과 보존
      → search_safety_cards(equipment_ids=..., observations=...)
      → cards에 안전 카드 먼저 병합, card_id로 중복 제거
      → list_handover(..., shift=...)  # handover일 때만
      → get_checklist(equipment_ids=...)
  → query이고 병합 cards가 비어 있으면 no_knowledge=True로 즉시 반환
  → model(mode=..., request=..., tool_results=...)
  → validator(mode=..., request=..., tool_results=..., model_output=...)
      → build_response(...) → validate_response(...)
  → output.review_queue이면 같은 입력으로 model(..., retry=True) 1회
      → validator(...) 다시 호출
  → PipelineResult(mode, tool_results, output)
```

- 동기 호출이다. async 함수나 generator를 직접 주입하는 계약이 아니다.
- 최초 호출은 `retry` 키워드를 생략한다. 두 번째 호출에만 `retry=True`를 전달한다.
- 두 번째 호출에 이전 응답이나 검증 오류는 전달하지 않는다.
- `propose_handover`는 인터페이스에 있지만 현재 파이프라인에서 호출하지 않는다.
- `render_response()`는 `run()`에서 자동 호출하지 않는다. 표시 계층/진입점이 호출해야 한다.
- 기본 `tools`는 모두 `NotImplementedError`인 모듈이다. 실행 시 제공자를 명시적으로 주입해야 한다.

## 2. A → B: 실제 함수 인자

현재 `ModelCall = Callable[..., Any]`이므로 반환 형식의 강제 검증은 없다. B는 아래 호출 형태를 수용해야 한다.

```python
def __call__(self, *, mode, request, tool_results, retry=False):
    ...
```

| 인자 | 현재 Python 값 | B의 처리 |
|---|---|---|
| `mode` | `"query"` 또는 `"handover"` | 오늘 구현 범위는 query. handover를 query로 조용히 처리하지 않기 |
| `request` | `QueryRequest` 또는 `HandoverRequest` 객체 | dict가 아님. 필요 시 `request.model_dump(mode="json")` 사용 |
| `tool_results` | `dict[str, Any]` | 아래 §3의 구조. 입력 객체를 변경하지 않기 |
| `retry` | 첫 호출 기본 False, 재호출 True | 호출 조건만 전달됨. B 내부 자동 재시도는 두지 않기 |

### 질의 입력: run()에 주는 JSON

```json
{
  "question": "진동 보고에 무엇을 기록해야 하나요?",
  "line_id": "L1",
  "eq_id": "HPU",
  "observations": [{"signal": "vibration_reported", "value": true}],
  "k": 3
}
```

- 합성 개발 입력이며 현장 진단·조치 기준이 아니다.
- question/line_id/eq_id는 공백 아닌 문자열. k는 1~5, 기본 5. observations는 기본 빈 목록.
- `HPU` 직접 입력은 기존 테스트 호환용으로 유지한다. A의 검색 제공자는 이제 사전의 `EQ-0001 ↔ HPU-01 → ET-0001 → HPU` 관계를 해석한다. B가 문자열 절단으로 유형을 추정하지 않는다. 요청의 원래 eq_id는 보존된다.
- line_id는 request에 보존되지만 현재 도구 검색의 필터 인자로 전달되지 않는다.
- 위 observations는 도구에 `{"vibration_reported": true}`로 전달된다. 모델의 request.observations는 이제 `list[Observation]`이다. B는 개별 항목에 `.get()`을 쓰지 말고 속성 접근 또는 request.model_dump(mode="json")을 사용한다.
- signal·value 누락, 빈 signal, 알 수 없는 필드, 공백뿐인 unit, 앞뒤 공백 제거 후 중복 signal은 도구·모델 호출 전에 거부한다. signal/unit의 앞뒤 공백은 제거된다.
- value는 필수이며 0·False를 그대로 보존한다. 명시적 null도 기존 호환을 위해 허용하며, 누락과 구분한다. 값 타입·물리 범위·null의 비교 의미를 검증하는 작업은 별도다.
- unit은 요청 객체와 JSON dump에 보존된다(생략하면 null). 검색 도구는 기존 signal→value 계약을 유지하므로 단위 정보가 전달되지 않으며 단위 변환·호환성 검사는 아직 없다.

### 인계 입력: 현황 참고, 오늘 어댑터 구현 범위 밖

```json
{"memo_text":"HPU-01 진동 확인 미완료","shift":"A","eq_ids":["HPU-01"]}
```

shift는 A/B/C, eq_ids는 비어 있지 않은 목록이다. 인계 검색은 memo_text를 질의로 쓰고 k=5, observations=None이다. question과 memo_text가 동시에 있거나 둘 다 없으면 라우팅을 거부한다. 두 요청 모델 모두 최상위 추가 키를 거부한다.

## 3. tool_results 구조와 프롬프트 경계

| 키 | 현재 값 | 주의 |
|---|---|---|
| `equipment` | 설비 사전 dict의 목록 | equipment_id 또는 code로 찾아 정식 equipment_id가 있는 원래 행 반환. 내용 필드의 별도 스키마 없음 |
| `cards` | 안전 카드와 일반 검색 카드를 병합한 목록 | 모델이 참고할 주된 카드 목록. 안전 카드 때문에 k보다 많을 수 있음 |
| `ranked_cards` | 안전 병합 전 일반 top-k 목록 | 평가용. cards와 중복해서 프롬프트에 넣을 필요 없음 |
| `safety_cards` | 별도 조회한 안전 카드 목록 | 감사·검증용. cards에도 포함됨 |
| `checklist` | 해당 설비의 체크리스트 dict 목록 | 별도 내용 스키마 없음, 빈 목록 가능 |
| `handover` | 해당 설비·교대의 인계 dict 목록 | handover 모드에만 키 존재. query에서는 누락 |

InMemoryToolProvider의 카드는 `KnowledgeCard.model_dump(mode="json")`의 전체 필드에 `condition_status`를 추가한 dict다. 생략된 스키마 기본값도 dump에 포함된다.

설비 사전을 사용하는 A 실행 진입점에서는 기준정보 JSON의 `equipment`를 equipment_db, `equipment_types`를 equipment_types 생성자 인자로 전달한다. 두 검색은 해소된 type_code를 사용하고, 인계·체크리스트는 정식 equipment_id로 저장된 행을 조회한다. 이전 표시 코드 기반 인계 레코드를 자동 마이그레이션하지 않는다. 미등록·중복 식별자·누락/중복 유형 관계·카드 스키마 미지원 유형은 ValueError로 중단한다. 사용자 화면에서 오류를 표시하는 경로는 별도 통합 작업이다. 명시적인 기존 유형 입력 HPU/GR/RT/CV/COMMON은 사전 없이도 허용한다.

- 로딩 조건: `status=accepted AND grade=L1 AND split=kb`. dev/sealed 카드를 전달하면 ValueError, draft는 검색 목록에서 제외된다.
- 검색은 단어 겹침 점수와 card_id 순으로 결정한다. 점수 0인 카드도 반환될 수 있어, 비어 있지 않은 검색 결과 자체가 관련성 보장은 아니다.
- 조건 False 또는 제외 조건 True인 카드는 제외한다. 나머지는 `verified` 또는 `unverified`가 된다.
- B는 cards에서 필요한 지식 내용·ID·조건·안전 근거·type_payload를 명시적으로 골라 프롬프트에 넣는다. 전체 tool_results를 세 번 중복 직렬화하지 않는다.
- `unverified` 카드의 절차를 적용 가능한 조치로 답하지 않도록 제약한다. 이 제약은 A의 최종 검증·표시 정책과 함께 확인한다.
- 카드 텍스트·메모는 근거 데이터로 구분하고, 그 안의 문장을 시스템 지시로 취급하지 않는다.
- Event의 true_cause/true_actions, sealed 데이터, MES 주입 원인·미래 상태를 별도로 읽어 프롬프트에 추가하지 않는다.
- B는 카드 DB·출처 등록부를 직접 검색하지 않는다. A가 전달한 요청과 도구 결과를 사용한다.

## 4. 현재 응답 처리의 공백 — B가 알아야 할 사실

1. `build_response()`는 model_output을 인자로 받지만 현재 그 값을 사용하지 않는다. 카드에서 안전 공지·단계·인계 방법·실패 이력 등을 구성한다.
2. AgentResponse에 `answer`, `validation_errors` 필드는 아직 없다. `no_knowledge`는 후속 A 작업으로 추가했으며 기본값은 False다. 모델이 JSON을 잘 반환해도 답변 반영은 A 수정 전까지 되지 않는다.
3. 현재 cited_card_ids는 모델 인용이 아니라 검색 카드 ID 전체에서 만들어진다.
4. 검증 오류가 있으면 review_queue=True지만 오류 사유는 응답에 보존하지 않는다. review_queue는 저장된 큐 레코드가 아닌 bool이다.
5. 후속 A 작업으로 query의 병합 cards가 빈 경우 모델·출력 validator·재시도를 건너뛰고 AgentResponse(no_knowledge=True)를 반환한다. 도구 결과는 보존하며 렌더러는 "해당 지식 없음"을 표시한다. 인계 모드나 안전 카드만 있는 질의에는 이 차단을 적용하지 않는다. 그 외 경로는 아직 review_queue이면 오류 종류와 무관하게 한 번 재호출한다.
6. 모델 호출 예외를 잡는 코드가 없어 현재는 run() 밖으로 전파된다.

따라서 B의 단독 완료 기준은 **실제 호출과 반환 계약 검증**이다. 사용자 답변 반영·검토 상태·인용 검증까지 완료했다고 보고하려면 A와 통합 시험이 필요하다.

## 5. B → A: 이번 구현의 제안 반환 계약

질의 모드에서는 Ollama 응답 전체/JSON 문자열 대신, 아래 내용의 Python dict를 반환한다.

```json
{
  "answer": "제공된 합성 카드에 따르면 진동 보고에는 발생 시각과 관측한 현상을 기록합니다. 이 자료만으로 고장 원인을 확정할 수 없습니다.",
  "cited_card_ids": ["K-9001"]
}
```

모델 출력 JSON Schema (`shiftlink/edge/ollama.py` 구현):

```json
{
  "type": "object",
  "properties": {
    "answer": {"type": "string", "minLength": 1},
    "cited_card_ids": {
      "type": "array",
      "items": {"type": "string", "pattern": "^K-\\d{4}$"},
      "uniqueItems": true,
      "minItems": 1
    }
  },
  "required": ["answer", "cited_card_ids"],
  "additionalProperties": false
}
```

- B는 모델 응답에서 JSON을 파싱하고 구조·타입·공백뿐인 answer 등을 검사해 반환한다.
- A는 인용 ID가 이번 호출의 `tool_results["cards"]`에 포함되는지 검사하고 적용 조건·응답 보류를 판단한다. KB에 존재하더라도 이번 검색 결과에 없는 ID는 거부한다. 정규식 일치만으로 이 검사를 대신하지 않는다.
- 빈 인용 목록은 출력 형식 오류로 거부한다. A는 한 번 재시도하고 다시 실패하면 자유 답변을 표시하지 않고 `review_queue`로 보류한다.
- 안전 공지·절차 구조는 A가 구성한다. 모델이 AgentResponse 전체를 덮어쓰게 하지 않는다.
- JSON Schema는 의미 정확성을 보장하지 않는다. 카드와 답변 내용의 일치는 별도로 평가한다.

### 제안 오류 계약과 책임

처음에는 아래 Python 표준 예외로 맞추는 안이다. 구현 전에 A/B가 확인한다.

| 상황 | B → A | A의 예정 처리 |
|---|---|---|
| 타임아웃 | TimeoutError | 모델 이용 불가 상태 반환. 초기 정책상 자동 재시도하지 않음 |
| 접속 실패·HTTP 오류 | ConnectionError | 동일. 접속 정보·원문 응답을 사용자용 오류에 포함하지 않음 |
| JSON 파싱·출력 형식 오류 | ValueError | 최대 1회 재호출, 재실패는 사유와 함께 보류 |
| handover 등 미지원 모드 | NotImplementedError | 미지원 명시. query로 대신 처리하지 않음 |
| 이번 tool_results["cards"]에 없는 ID 인용 | 정상 dict 반환 | A가 검출, 최대 1회 재시도 후 재실패는 보류 |

전체 모델 호출 상한은 2회다. B 내부 HTTP 자동 재시도는 사용하지 않는다. 현재 재호출에는 오류 사유가 전달되지 않으므로 retry=True일 때 출력 형식·제공된 ID 제약을 다시 강조하는 정도로 구현한다. 없는 errors 인자를 요구하지 않는다. 오류별 수정 지시가 필요하면 먼저 A/B 호출 계약을 갱신한다.

host/model/timeout은 설정으로 받고 모델 태그를 코드에 고정하지 않는다. `.env.example`에 OLLAMA_HOST는 있지만 자동 로딩을 전제하지 않는다. 모델 태그·타임아웃의 설정 방법과 값은 B가 PC에서 확인해서 넘긴다.

## 6. 외부 접속 없는 최소 호출 예제

아래는 기존 코드로 실행 가능한 합성 fixture다. accepted/L1은 테스트 입력값이며 실제 카드의 검수·승격 기록이 아니다. 기존 실데이터를 변경하거나 승격하지 않는다.

```python
from shiftlink.agent.pipeline import FixedPipeline
from shiftlink.agent.schemas import KnowledgeCard
from shiftlink.rag.retrieval import InMemoryToolProvider

card = KnowledgeCard.model_validate({
    "card_id": "K-9001", "version": "handoff-fixture-1",
    "grade": "L1", "status": "accepted", "split": "kb",
    "tacit_type": "T1", "equipment": "HPU", "component": "pump",
    "scenario": "S1", "title": "합성 테스트: 진동 보고",
    "symptom": "진동 보고", "know_how": "발생 시각과 관측한 현상을 기록한다.",
    "rationale": "연결 확인용 합성 fixture. 현장 절차의 근거가 아니다.",
    "confidence": 0.0,
    "provenance": {
        "seed_ids": [], "persona_id": "TEST", "event_ids": [],
        "generator": "handoff-fixture", "generated_at": "2026-09-24T00:00:00Z",
        "schema_version": "1.1"
    }
})
provider = InMemoryToolProvider(
    cards=[card], equipment_db=[{"equipment_id": "HPU"}]
)
payload = {
    "question": "진동 보고에 무엇을 기록해야 하나요?",
    "line_id": "L1", "eq_id": "HPU",
    "observations": [{"signal": "vibration_reported", "value": True}], "k": 3
}
calls = []
def capture_model(*, mode, request, tool_results, retry=False):
    calls.append({
        "mode": mode, "request": request.model_dump(mode="json"),
        "tool_results": tool_results, "retry": retry
    })
    return {"answer": "연결 테스트 응답", "cited_card_ids": ["K-9001"]}

result = FixedPipeline(model=capture_model, tools=provider).run(payload)
assert len(calls) == 1
assert calls[0]["request"]["observations"][0]["value"] is True
assert calls[0]["tool_results"]["cards"][0]["condition_status"] == "verified"
assert "handover" not in calls[0]["tool_results"]
assert result.output.cited_card_ids == ["K-9001"]
# 현재 모델의 answer는 최종 응답에 저장되지 않는다. A 구현 후 기대값을 갱신한다.
assert "answer" not in result.output.model_dump()
```

호출 내용은 `calls[0]`에서 확인한다. 이는 관찰용 JSON 스냅샷으로, request를 dict로 변환한 기록이다. **`adapter(**calls[0])`로 호출하면 실제 계약과 달라진다.** B의 독립 시험에서는 `route_request(payload).request`로 얻은 Pydantic 객체를 request에 전달하고, tool_results에는 `calls[0]["tool_results"]`를 사용할 수 있다. 원문 전체를 감사 로그에 저장할 경우 저장 범위는 별도로 정한다.

## 7. 선후 관계와 파일 소유권

| 순서 | A | B | 다음 단계 조건 |
|---|---|---|---|
| 1 | 이 계약과 fixture 확인 | PC Ollama·모델·호출 가능 여부 확인 | 출력·오류 계약을 양쪽이 확인 |
| 2 병렬 | 입력·ID 해소·응답 검증·예외 처리 구현 | edge에 동기 어댑터·독립 테스트 구현 | 각자 테스트 통과 |
| 3 | 가짜 모델로 정상·실패 검사 | 실제 모델의 dict 반환·오류 변환 검사 | A/B 모두 검증 완료 |
| 4 | 통합 실행 진입점 작성, B 어댑터 주입 | 모델 쪽 문제 수정·실행 지원 | PC에서 실제 답변 반영 확인 |
| 5 | 회귀 시험·미완료 기록 | 실행 방법·측정 조건 기록 | 정상·실패 결과 확보 |

- A 소유: router.py, pipeline.py, response.py, 설비 ID 해소, 관련 테스트, 통합 실행 진입점.
- B 소유: edge의 모델 어댑터, 어댑터 테스트, 모델 실행 안내.
- 공통 계약·fixture는 A가 편집하고 B가 참조한다. 같은 파일을 동시에 수정하지 않는다.
- B는 A 구현을 기다리는 동안에도 단독 모델 호출을 진행할 수 있다. 모델 실행이 막히면 모의 시험을 진행하되 실제 LLM 미검증으로 기록한다.
- 오늘은 query 연결까지다. 인계 저장·임베딩 최적화·대량 카드 생성·Jetson 측정은 후속 작업이다.

## 8. B가 A에게 넘길 값과 완료 체크

다음 항목을 넘긴다. API 키 등 비밀 값은 포함하지 않는다.

1. 어댑터 import 경로, 생성 방법, __call__ 인자.
2. 실제 사용한 모델 태그·확인 가능한 digest, PC 실행 조건.
3. host/model/timeout 설정 방법과 로컬 실행 명령.
4. §5에 맞는 성공 dict 예제, 오류별 예외 타입, 내부 재시도 없음 확인.
5. 정상·JSON 오류·타임아웃·접속 실패 테스트 결과. 모의 시험과 실제 측정을 구분.
6. 미완료 항목. PC 시간을 Jetson 성능으로 표시하지 않는다.

통합 후 확인: 실제 답변 반영, 없는 인용 거부, 빈 KB에서 모델 호출 0회, 잘못된 관측값 사전 거부, 조건 미확인 시 보류, 호출 상한 2회, 재현 가능한 실행 명령.

## 9. 문서 검증 범위

현재 코드와 호출 순서를 대조했다. 저장소의 `.test-deps`를 PYTHONPATH로 지정해 다음을 확인했다.

- JSON 블록 4개 파싱 성공. 질의·인계 입력이 각각 QueryRequest·HandoverRequest로 라우팅됨.
- 제안 출력 예제의 키와 인용 ID가 제안 JSON Schema의 해당 제약과 일치함. 전체 JSON Schema 검증기를 실행한 것은 아님.
- §6 Python 예제를 실제 실행해 호출 1회, 관측값 보존, 카드 condition_status, query의 handover 키 부재, 현재 answer 미반영을 확인함.
- 상대 링크 6개가 모두 존재하고 `git diff --check`가 통과함.

최초 문서 작성 때는 런타임 코드를 변경하지 않았다. 후속 관측값 구조 검증의 코드 변경·94개 테스트 통과·커버리지 96%는 [관측값 증빙](../testing/observation-validation.tdd.md)에 기록했다. 설비 ID 해소·104개 테스트 통과는 [설비 해소 증빙](../testing/equipment-resolution.tdd.md)에 기록했다. 빈 검색 결과 처리·118개 테스트 통과는 [지식 없음 증빙](../testing/no-knowledge.tdd.md)에 기록했다. Ollama 접속·모델 설치·Jetson 측정은 수행하지 않았다.

2026-09-24 서브에이전트 독립 검토에서도 호출 구조·예제 실행·JSON 4개·상대 링크 6개를 확인했다. 지적된 관찰용 request 스냅샷과 실제 객체의 차이, 인용 허용 범위, 현재 사실과 구현 지침의 구분을 문서에 반영했다. 스냅샷 설명 수정 후 예제를 재실행해 통과했다.

## 10. 2026-09-24 후속 계약 확인 및 A 통합

B는 §5의 호출 방식·성공 dict·표준 예외·책임 분리에 동의했다고 회신했다. B의 회신에 따르면 실제 PC 모델 호출과 어댑터 검증도 마쳤고 전체 테스트 306건이 통과했다. 그 수치와 실모델 결과는 B의 보고이며, 이 체크아웃에서 독립 재실행하지 않았다.

A의 재시도 정책은 다음으로 확정했다.

- `ValueError`와 A의 출력/인용 검증 실패는 `retry=True`로 한 번 재호출한다.
- `TimeoutError`, `ConnectionError`(HTTP 오류 포함), `NotImplementedError`는 재호출하지 않고 보류한다. 예외 분기는 `TimeoutError`를 `ConnectionError`보다 먼저 처리한다.
- `answer`는 비어 있지 않은 문자열이어야 하고, 정확히 `answer`와 `cited_card_ids` 키만 허용한다. 인용 목록은 비어 있지 않고 중복되지 않아야 하며, 각 ID가 카드 ID 형식에 맞고 이번 호출의 `tool_results["cards"]` 안에 있어야 한다.
- 위 조건을 만족하지 못하면 자유 답변을 표시하지 않고 검증 사유와 함께 `review_queue`에 둔다. 빈 query 검색은 모델 호출 전에 계속 차단한다.

A 변경은 `1c37fff`(실패 테스트)와 `4d501d6`(구현)이며, 전체 회귀 시험은 324건 통과했다. 단, 이 저장소 체크아웃에는 B의 어댑터 모듈이 없으므로 해당 어댑터를 주입한 PC 실모델 통합 E2E는 아직 실행하지 않았다. 다음 통합 단계에는 B가 넘길 import 경로·생성 방법·실행 설정을 사용한다.
