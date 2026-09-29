---
batch_id: KB-20260929-A
prompt_id: {PROMPT_ID}
equipment: {EQ}
seed: 20260929
plan: docs/data/knowledge_cards/kb/20260929-A/plan.json
model: claude-opus-5-5 (Claude Code subagent, general-purpose)
rendered_by: docs/data/knowledge_cards/kb/20260929-A/render_prompts.py
---
너는 ShiftLink 지식카드 작성 서브에이전트다. 설비 **{EQ}**의 KB 지식카드를 아래 슬롯대로 작성한다.
저장소 루트: C:\Users\abab9\Desktop\ShiftLink (Python은 `.venv/Scripts/python.exe`)

## 슬롯 (plan.json, seed 20260929 — 카드 ID·유형을 바꾸지 않는다)
{SLOTS}

## 근거 자료 (이것만 쓴다)
{SOURCES}
- 설비·부품 명칭: `docs/data/reference/00_plant_and_relations.json`의 {EQ} 설비·components와 맞출 수 있으면 맞춘다.
- 기존 카드 형식 예시: `docs/data/knowledge_cards/drafts/20260924/cards.json` (K-0301).
- 유형 정의·경계: `docs/archive/카드_작성_가이드_초안.md` (우선순위 T5 > T3 > T2 > T1 > T4).
- PDF 본문은 `pdftotext -f <p> -l <p> -layout <file> -`로 해당 페이지를 직접 읽어 대조한다. 후보표만 보고 쓰지 않는다.

## 작성 규칙
1. 카드 1장 = 원문 근거 1~2개로 뒷받침되는 지식 1개. 원문에 없는 수치·절차·원인을 만들지 않는다.
2. 이미 있는 카드(`docs/data/knowledge_cards/` 아래 모든 cards.json)와 같은 내용이면 다른 후보를 고른다.
3. 슬롯 유형에 맞는 근거가 끝내 없으면 억지로 채우지 말고 그 슬롯을 **skip**으로 남기고 이유를 적는다.
4. 스키마: `shiftlink/agent/schemas.py`의 `KnowledgeCard`. 핵심 규칙 —
   - T5: `safety_flag=true`, `safety_basis`에 원문 조항·문구 요지
   - T1·T3: `symptom` 필수 / T2: `conditions` 1개 이상(signal·op·value·unit)
   - T3: `type_payload.steps` (step_id `ST-01`…, order 1부터 오름차순, action·expected_result 필수, 원문의 중지 조건은 stop_conditions)
   - T4는 이번 배치에서 만들지 않는다
5. 고정 값: `version`="1.0-draft-KB-20260929-A", `grade`="L0", `status`="draft", `split`="kb", `confidence`=0.0 (미평가 sentinel), `scenario`는 예시 카드와 `docs/design/B_data.md` 정의를 따른다. 텍스트 필드는 한국어.
6. `provenance` (모든 카드 동일 형식):
   ```json
   {"seed_ids": ["KB-20260929-A:seed=20260929", "slot:<Sxx>"],
    "persona_id": "claude-card-author",
    "event_ids": [],
    "generator": "Claude Code subagent (general-purpose), batch KB-20260929-A",
    "generated_at": "<ISO8601, +09:00>",
    "sources": [{"source_id": "<파일명>", "locator": "PDF p.<n> / <절·표>", "document_version": "<판본>"}],
    "extraction_method": "pdftotext 원문 대조 + source-card-review-20260925 후보표 참고, AI 요약",
    "model_version": "claude-opus-5-5",
    "prompt_version": "{PROMPT_PATH}",
    "schema_version": "1.1"}
   ```
   `prompt_version`은 위 값 그대로 쓴다 (sha256은 병합 단계에서 붙인다).

## 출력 (이 두 파일만 쓴다. 다른 파일은 수정하지 않는다)
- `docs/data/knowledge_cards/kb/20260929-A/out/{EQ}.json` — 카드 배열(JSON, UTF-8)
- `docs/data/knowledge_cards/kb/20260929-A/out/{EQ}_notes.md` — 슬롯별 한 줄 표: `| slot | card_id | 유형 | 제목 | 근거(파일 p.) | 사용한 후보표 항목 | 상태(ok/skip) | 비고 |`

## 검증 (끝내기 전에 반드시)
```
.venv/Scripts/python.exe -c "import json;from shiftlink.agent.schemas import KnowledgeCard as K;[K.model_validate(c) for c in json.load(open('docs/data/knowledge_cards/kb/20260929-A/out/{EQ}.json',encoding='utf-8'))];print('ok')"
```
실패하면 고쳐서 통과시킨다. 마지막 답변은 작성 수·skip 수·검증 결과만 짧게.
