# 블라인드 질문 2차 (BN-001~025)

> 작성 2026-10-01 · 질문 작성 **허재원** · 정답 연결: Claude 서브에이전트(질문 작성과 다른 에이전트) → 검수 전혜민

## 왜 다시 만드나

1차 블라인드 셋 `20261001-blind/qa_blind.json`(BL-001~025)은 다음 세 가지 이유로 평가셋 구실을 못 한다.

1. **작성자가 카드를 알고 있었다.** C·D 카드 검수 경험이 있는 사람이 썼다.
2. **카드가 질문을 보고 만들어졌다.** BL-015·019·023은 "답 없음"이었는데, 배치 D 4차에서 이 질문의 빈칸을 채우는 카드(K-1322~1324)가 만들어졌다.
3. **다루는 범위가 비었다.** CAU·PDP의 T2(값 해석)·T6(재가동) 질문이 0개이고, 관측 수치가 붙은 문항은 4/25다. `key_facts`·`difficulty` 칸도 비어 있다.

1차 셋은 지우지 않고 그대로 둔다. 2차 셋은 이 폴더에서 새로 만든다.

## 작성자 규칙 (허재원)

1. **아래 파일은 작성이 끝날 때까지 열지 않는다.** 하나라도 열었다면 `writer_note`에 적는다.
   - `docs/data/knowledge_cards/` 전체 (kb·drafts)
   - `eval/qa/` 안의 다른 폴더 (1차 블라인드 셋 포함)
   - `docs/collaboration/kb-cau-pdp-t2-t6-guide-20260930.md`, `docs/collaboration/t4-retrieval-improvement-guide-20260930.md` (카드 방향이 적혀 있다)
2. 이 README, 아래 신호표, 장비 매뉴얼, 현장 상식만 보고 쓴다.
3. 현장 작업자가 PDA에 칠 법한 말투로 쓴다. 반말, 오타, 짧은 문장 모두 괜찮다. 카드 제목처럼 정리된 문장은 피한다.
4. **답이 있는지는 신경 쓰지 않는다.** 정답 카드는 다음 단계에서 연결한다. "이건 아마 카드가 없겠다" 싶은 질문(수치·규격·부품 호환 등)도 5개 안팎 섞는다.
5. 칸 하나에 질문 하나를 쓴다. 칸의 설비·유형이 안 맞으면 바꿔도 되고, 바꾼 이유는 `writer_note`에 적는다.

## 칸 배분 (25)

| 설비 | T2 값 해석 | T6 재가동 | 자유 | 합 |
|---|---|---|---|---|
| CAU 압축공기 | 4 | 3 | | 7 |
| PDP 배전반 | 4 | 3 | | 7 |
| HPU·CV·GR·RT | 각 1 | 각 1 | | 8 |
| 아무 설비 | | | 3 | 3 |

- **T2 값 해석**: 수치나 상태를 보고 "이러면 이렇게, 저러면 저렇게" 판단이 갈리는 질문. 예: "압력이 이 정도인데 계속 돌려도 돼?" 신호표에 있는 신호라면 `observations`에 값을 넣는다.
- **T6 재가동**: 정비·교체·정전·트립 뒤 다시 돌릴 때 무엇을 확인하는지 묻는 질문.
- **자유**: 유형에 상관없이 현장에서 실제로 나올 법한 질문. 답 없는 질문을 여기에 써도 된다.

## MES 신호표 (`docs/data/reference/00_plant_and_relations.json`)

| 설비 | 신호 | 단위 |
|---|---|---|
| HPU | `hpu_pressure` | bar |
| HPU | `hpu_oil_temp` | degC |
| HPU | `hpu_filter_dp` | bar |
| HPU | `hpu_flow` | L_min |
| PDP | `bus_voltage` | pct |
| CAU | `air_pressure` | kPa |
| GR | `gr_vib_rms` | mm_s |
| GR | `gr_brg_temp` | degC |
| GR | `gr_current` | A |
| RT | `rt_speed` | m_min |
| RT | `rt_clamp_press` | bar |
| RT | `rt_lift_delay` | min |
| RT | `rt_motor_current` | A |
| CV | `cv_speed` | m_min |
| CV | `cv_belt_tension` | kPa |
| CV | `cv_queue_len` | pct |

표에 없는 신호(예: 압축기 토출 온도, 차단기 전류)는 `observations`에 넣지 않고 질문 문장에만 쓴다.

## 쓰는 법

`questions_raw.json`의 빈칸만 채운다.

- `question`: 질문 문장
- `observations`: `{"air_pressure": {"value": 520, "unit": "kPa"}}` 형식. 없으면 `{}`
- `writer_note`: 상황 설명, 칸을 바꾼 이유, 규칙 1에서 열어본 파일

`eq_id`·`slot`은 바꿔도 된다. `qid`는 바꾸지 않는다.

## 다음 단계 (작성 뒤)

| 단계 | 담당 | 결과 |
|---|---|---|
| 정답 연결 | Claude 서브에이전트 (질문을 쓰지 않은 에이전트) | `labels.json`에 문항별 `answerable`·`primary_card_ids`·`acceptable_card_ids`·`safety_card_ids`·`key_facts`·`difficulty`·`label_note` |
| 검수 | 전혜민 | 문항별 채택·수정·제외 |
| 확정 | Claude | 질문과 정답을 합친 `qa_blind2.json`, `route_score.py`에 블라인드 지표 추가 |

**오염 금지**: 정답 연결 중 카드 공백이 보여도 이 셋의 문항을 보고 카드를 만들거나 고치지 않는다. 공백은 목록으로만 남긴다. 1차 셋에서 BL-015·019·023이 이 규칙을 어겼다.
