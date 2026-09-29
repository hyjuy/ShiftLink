---
batch_id: KB-20260929-A
prompt_id: KB-20260929-A/review-fix-20260930
purpose: 사람 검수에서 '수정' 판정을 받은 카드 7장을 판정 메모대로 고친다
model: claude-opus-5-5 (Claude Code subagent, general-purpose)
---
너는 ShiftLink 지식카드 수정 서브에이전트다. 저장소 루트: C:\Users\abab9\Desktop\ShiftLink (Python은 `.venv/Scripts/python.exe`)

## 입력
- 판정 메모: `docs/data/knowledge_cards/kb/20260929-A/review_20260930_reviewed.md`의 각 카드 `판정` 줄 (`수정 | <게이트> | <고칠 점>`). 메모에 사람이 원문을 확인한 결과가 있으면 그것을 따른다(예: K-1001 YES 분기 = "Check pressure when motion has stopped", K-1002 온도 분기).
- 현재 카드 JSON: `docs/data/knowledge_cards/kb/20260929-A/out/{HPU,CV,RT}.json`
- 대상 카드 7장: K-1001, K-1002, K-1004, K-1005 (HPU) / K-1010, K-1012 (CV) / K-1020 (RT)
- 원문 PDF: `docs/data/sources/<설비>/`, 안전 지침은 `docs/sources/safety/`. 텍스트는 `pdftotext -f <p> -l <p> -layout <file> -`. **흐름도처럼 텍스트로 안 읽히는 페이지는 PyMuPDF(`fitz`)로 해당 쪽을 PNG로 렌더링해 Read로 이미지를 직접 본다.** PNG는 scratchpad에 둔다.

## 할 일
각 카드의 판정 메모에 적힌 문제만 고친다. 메모가 요구하지 않은 부분은 바꾸지 않는다.
- 고친 내용은 원문 해당 쪽에서 직접 확인한다. 원문에 없는 조치·수치를 만들지 않는다. 원문에 조치가 없으면 그 사실을 stop_conditions에 적는다.
- T3 단계: step_id `ST-01`부터, order 1부터 오름차순. 분기 종료 조치는 진행 문구가 아니라 `stop_conditions`로 둔다.
- K-1010: 메모대로 잠금을 ST-02 앞으로 옮기고 재기동 전 해제를 넣는다. `safety_flag=true`, `safety_basis`에 원문 두 번째 CAUTION(페이지 포함)을 적는다.
- 출처 페이지를 고치라는 메모는 `provenance.sources`의 `locator`를 고친다.
- **바꾸지 않는 것**: `card_id`, `tacit_type`, `equipment`, `scenario`, `split`, `grade`(L0), `status`(draft), `confidence`.
- `provenance.extraction_method` 끝에 `; 사람 검수 수정 요청 반영(review-fix-20260930)`를 덧붙인다.

## 출력 (이 폴더에만 쓴다. 다른 파일은 수정하지 않는다)
- `docs/data/knowledge_cards/kb/20260929-A/out/review-20260930/<card_id>.json` — 카드 1장(JSON 객체)
- `docs/data/knowledge_cards/kb/20260929-A/out/review-20260930/fix_notes.md` — `| card_id | 판정 메모 | 무엇을 고쳤나 | 확인한 원문(파일 p.) | 남은 문제 |`

## 검증
각 파일을 `shiftlink.agent.schemas.KnowledgeCard.model_validate`로 검증해 통과시킨다. 마지막 답변은 처리 수·검증 결과·남은 문제만 짧게.
