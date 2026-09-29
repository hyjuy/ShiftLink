# 평가 질문 작성 지시 (writer, 카드 비공개)

너는 냉간코일 공장 교대 근무자가 현장 보조 시스템(ShiftLink)에 실제로 던질 질문을 쓴다.
정답 카드는 다른 사람이 나중에 붙인다. **너는 지식 카드를 보지 않는다.**

## 읽어도 되는 것
- `seeds/personas_v0.1.yaml` — 질문하는 사람(말투·역할·경력)
- `docs/data/reference/00_plant_and_relations.json` — 설비 4종(HPU·CV·RT·GR)과 MES 신호 카탈로그(이름·단위·정상 범위)
- `docs/data/sources/` 아래 매뉴얼 PDF — 현장에서 생길 법한 증상·작업을 떠올리는 용도. 문장을 옮겨 쓰지 않는다
- 설비별 부품 목록(아래)

| 설비 | 부품 |
|---|---|
| HPU | 주 베인펌프, 작동유, 오일 쿨러, 축압기, 릴리프 밸브, 필터 |
| CV | 벨트, 벨트 스플라이스, 아이들러, 방호·점검 덮개, 전원·안전장치 |
| RT | 롤러 세트, 승강부(유압 실린더·솔레노이드 밸브·파워유닛), 클램프, 반송 모터 |
| GR | 감속 기어박스, 베어링부, 오일 씰·커버 |

## 읽으면 안 되는 것
`docs/data/knowledge_cards/` 전체, `docs/guides/mes-card-signals.md`, `docs/design/mes-sensor-coverage.md`, `eval/`(이 폴더 제외), `graphify-out/`, `tests/`.
카드 제목·증상 문구를 알게 되면 평가가 무의미해진다.

## 만들 것: 질문 70건
- 설비별 17~18건.
- 의도 분포(대략): 증상 → 원인·확인(`symptom`) 40%, 작업 절차(`procedure`) 20%, 안전 가능 여부(`safety`, 예: "돌고 있는데 손 넣어도 되나") 15%, MES 값 해석(`status`, observations 포함) 15%, 기타(`other`) 10%.
- 70건 중 15건 이상은 **이 시스템이 모를 법한 주제**(필터 막힘, 벨트 장력, 전기 배선, 공정 일정, 다른 설비 등)도 섞는다. 무엇이 KB에 있는지 모르므로 현장에서 나올 법한 대로 쓴다.
- 말투: 페르소나별로 다르게. 짧고 구어체, 주어 생략, 모호한 표현("좀 이상하다", "평소보다") 허용. 같은 뜻을 다른 표현으로 반복하지 않는다.
- `status` 질문은 `observations`에 카탈로그 신호명과 값을 넣는다(정상 범위 밖 값 위주, 일부는 정상값). 예: `{"hpu_oil_temp": {"value": 68, "unit": "°C"}}`.
- 질문 하나에 증상 하나. 답을 질문에 쓰지 않는다.

## 출력
`eval/qa/20260929/questions_raw.json` — JSON 배열, 각 항목:
```json
{"qid": "Q-001", "eq_id": "HPU", "persona_id": "V-11", "intent": "symptom",
 "question": "...", "observations": {}, "writer_note": "무엇을 떠올리고 썼는지 한 줄"}
```
qid는 Q-001부터 순서대로. UTF-8, LF, 들여쓰기 1.
