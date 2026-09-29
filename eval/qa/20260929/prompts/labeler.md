# 평가 질문 정답 라벨링 지시 (labeler)

질문은 카드를 보지 않은 작성자가 썼다(`prompts/writer.md`). 너는 각 질문에 KB 카드 기준 정답을 붙인다.
질문 문구는 고치지 않는다. 고치고 싶으면 `label_note`에 적는다.

## 입력
- `eval/qa/20260929/questions_raw.json` (70건)
- KB: `docs/data/knowledge_cards/kb/20260929-A/cards.json` — `status=accepted`인 30장만 대상
- MES 정상 범위: `docs/data/reference/00_plant_and_relations.json` (`status` 질문의 값 판단용)

## 판정 기준
- `answerable`: 카드 30장 중 하나라도 질문에 **실제로 답이 되는** 카드가 있으면 true. 설비·부품만 같고 증상이 다르면 false.
- `primary_card_ids`: 가장 직접 답하는 카드(보통 1장, 동등하면 최대 2장). answerable=false면 빈 배열.
- `acceptable_card_ids`: 인용해도 틀리지 않은 보조 카드(primary 제외). 없으면 빈 배열. 넓게 잡지 않는다.
- `safety_card_ids`: 이 질문 상황에서 **반드시 함께 보여야 할** 안전 카드(safety_flag=true). 해당 설비 안전 카드를 전부 넣지 말고, 질문 상황의 위험과 직접 관련된 것만.
- `key_facts`: answerable=true면 좋은 답변이 담아야 할 사실 1~3개. primary 카드의 know_how에서 짧게(각 40자 이내). 카드에 없는 사실은 쓰지 않는다. false면 빈 배열.
- `difficulty`: `easy`(질문 표현이 카드 제목·증상과 거의 같음) / `medium` / `hard`(다른 표현·간접 증상·여러 카드 중 판단 필요).
- `label_note`: 판정 근거 한 줄. 헷갈린 경우 반드시 적는다.

## 출력
`eval/qa/20260929/labels.json` — JSON 배열, 질문과 같은 순서:
```json
{"qid": "Q-001", "answerable": true, "primary_card_ids": ["K-1001"], "acceptable_card_ids": [],
 "safety_card_ids": [], "key_facts": ["..."], "difficulty": "medium", "label_note": "..."}
```
UTF-8, LF, 들여쓰기 1. 질문 파일은 수정하지 않는다.
