---
batch_id: KB-20260929-A
prompt_id: KB-20260929-A/review-sync-20260930
purpose: 사람 검수에서 본문을 직접 고치고 accepted로 판정한 카드 6장을 카드 JSON에 옮긴다
model: claude-opus-5-5 (Claude Code subagent, general-purpose)
---
너는 ShiftLink 지식카드 반영 서브에이전트다. 저장소 루트: C:\Users\abab9\Desktop\ShiftLink (Python은 `.venv/Scripts/python.exe`)

## 입력
- 사람 검수 최종본: `docs/data/knowledge_cards/kb/20260929-A/review_20260930_reviewed.md` — 이 텍스트가 정답이다.
- 현재 카드 JSON: `docs/data/knowledge_cards/kb/20260929-A/out/{HPU,CV,RT,GR}.json`
- 대상 카드 6장: K-1015, K-1018, K-1021, K-1023, K-1025, K-1027 (모두 판정 accepted, 본문이 검수 중 수정됨)

## 할 일
각 카드에 대해 현재 JSON을 복사한 뒤, 검수본 텍스트와 **같은 내용**이 되도록 필드를 고친다.
- 대상 필드: `title`(헤더의 " — " 뒤), `component`(부품), `symptom`(증상), `know_how`(노하우), `rationale`(근거 설명), `safety_basis`(안전 근거), `conditions`(조건 줄이 있으면), `type_payload.steps`(번호 줄: `action → expected_result / 중지: stop_conditions`), `provenance.sources`(출처).
- 검수본의 마크다운 강조(`**`, `*`)와 링크 문법은 벗기고 텍스트만 쓴다. 출처에 URL이 붙어 있으면 해당 source의 `locator` 끝에 ` | <URL>` 형태로 남긴다.
- 단계: step_id는 `ST-01`부터, order는 1부터 오름차순. 검수본에 단계가 늘거나 줄었으면 그대로 따른다. `→` 뒤가 expected_result, `중지:` 뒤가 stop_conditions다. 형식이 애매하면 의미가 보존되게 나누고 `sync_notes.md`에 적는다.
- **바꾸지 않는 것**: `card_id`, `tacit_type`, `equipment`, `scenario`, `split`, `grade`, `status`, `confidence`, `safety_flag`(헤더의 ⚠ 기호는 데이터가 아니다), provenance의 나머지 필드.
- 검수본에 없는 내용을 새로 만들지 않는다. 검수본 문장을 요약·재작성하지 않는다.
- `provenance.extraction_method` 끝에 `; 사람 검수 본문 수정 반영(review_20260930_reviewed.md)`를 덧붙인다.

## 출력 (이 폴더에만 쓴다. out/*.json·review.md 등 다른 파일은 수정하지 않는다)
- `docs/data/knowledge_cards/kb/20260929-A/out/review-20260930/<card_id>.json` — 카드 1장(JSON 객체)
- `docs/data/knowledge_cards/kb/20260929-A/out/review-20260930/sync_notes.md` — 카드별로 바뀐 필드 목록 한 줄씩

## 검증
각 파일을 `shiftlink.agent.schemas.KnowledgeCard.model_validate`로 검증해 통과시킨다. 마지막 답변은 처리 수·검증 결과·애매했던 점만 짧게.
