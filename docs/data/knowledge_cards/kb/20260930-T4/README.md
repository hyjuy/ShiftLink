# T4 인계 카드 배치 KB-20260930-T4

근무일지·인계 메모를 먼저 합성하고, 그 기록에서 반복된 인계 요령만 뽑아 T4 카드로 만든 배치다. 카드 11장.

- 시드: `20260930` — [`plan.py`](plan.py)가 사건 30건의 설비·시나리오·페르소나·누락 항목을 정한다. 같은 시드면 [`plan.json`](plan.json)이 바이트 단위로 같다.
- 생성: claude-opus-5[1m], 2026-09-29.
- 지시문: [`prompts/stage-a-records.md`](prompts/stage-a-records.md)(기록 합성), [`prompts/stage-b-cards.md`](prompts/stage-b-cards.md)(카드 추출). 해시는 [`prompts/index.json`](prompts/index.json).
- 원 지시서: [`docs/collaboration/t4-handover-cards-prompt-20260930.md`](../../../../collaboration/t4-handover-cards-prompt-20260930.md) `sha256:b37bfb6c9580`
- **재현성 한계**: 시드는 사건 배정만 고정한다. 사건 서술과 카드 문장은 같은 지시문으로 다시 돌려도 똑같이 나오지 않는다. 그래서 지시문 원문과 해시, 카드별 근거 사건을 남긴다.
- 모든 카드는 `status=draft`, `grade=L0`, `confidence=0.0`, `split=kb`이다. accepted 여부는 사람이 검수해 정한다([`review.md`](review.md)).

## 두 층 구분

| 층 | 파일 | 내용 |
|---|---|---|
| 기록(사실) | [`events.json`](events.json), [`artifacts.json`](artifacts.json) | 사건 30건과 사건별 근무일지·인계 메모 60건. 교대마다 1건씩 일어난 일 |
| 카드(요령) | [`cards.json`](cards.json) | 여러 기록에서 2건 이상 반복된 인계 요령 11장. 다음에도 재사용할 수 있는 형태 |

## 데이터 분할

| split | 사건 | 용도 |
|---|---|---|
| `kb` | EV-0301~EV-0320 (20건) | T4 카드의 근거. 유현준 MES 연결 시험 입력 |
| `dev` | EV-0321~EV-0330 (10건) | 평가셋 재료. **카드 근거로 쓰지 않는다** |

인계 메모 5요소(현재 상태·앞 근무자 조치·실패한 시도·미해결·다음 조 확인) 중 하나를 일부러 뺀 누락 사례가 7건 있다(23%). 어느 사건에서 무엇을 뺐는지는 `plan.json`의 `omitted_handover_element`에 있다.

## 카드 → 근거 사건 → 지시문 추적표

각 카드의 `provenance.prompt_version` = `docs/data/knowledge_cards/kb/20260930-T4/prompts/stage-b-cards.md@sha256:c913ebf4ff92…`, `provenance.seed_ids` = `["KB-20260930-T4:seed=20260930", "slot:<Sxx>"]`.

| 카드 | 슬롯 | 설비 | 안전 | 제목 | 근거 사건 | 근거 건수 |
|---|---|---|---|---|---|---|
| K-1101 | S01 | COMMON |  | 앞 조가 확인을 끝낸 항목과 그 결과를 적어 다음 조의 중복 확인을 막는다 | EV-0301, EV-0307, EV-0309, EV-0312 | 4 |
| K-1102 | S02 | COMMON |  | 조치한 부품·조치 후 계측값·재확인 시각을 한 묶음으로 남긴다 | EV-0302, EV-0306, EV-0307, EV-0312 | 4 |
| K-1103 | S03 | COMMON | ⚠ | 정지·재기동 방지 상태와 운전 복귀 조건·승인 주체·대기 사유를 인계에 명시한다 | EV-0304, EV-0305, EV-0308, EV-0311, EV-0319 | 5 |
| K-1104 | S04 | COMMON |  | 계측에 남지 않는 소리·외관 관측은 인계 메모에 문장으로 남긴다 | EV-0302, EV-0305, EV-0311, EV-0317, EV-0319 | 5 |
| K-1105 | S05 | COMMON |  | 알람이 없는 신호 이상은 값·확인 시각·다음 재확인 시각을 지정해 넘긴다 | EV-0310, EV-0313, EV-0315, EV-0316, EV-0318 | 5 |
| K-1106 | S06 | COMMON |  | 정해진 조치 절차가 없는 증상은 절차를 지어내지 말고 담당 확인 상태로 넘긴다 | EV-0313, EV-0315, EV-0317, EV-0318 | 4 |
| K-1107 | S07 | COMMON |  | 공급원 설비 상태를 함께 읽어 원인 범위를 좁힌 결과를 넘긴다 | EV-0315, EV-0318 | 2 |
| K-1108 | S08 | COMMON |  | 추정과 관측을 구분해 적고 단정하지 말아야 할 이유를 함께 넘긴다 | EV-0302, EV-0310, EV-0317 | 3 |
| K-1109 | S09 | COMMON |  | 요청만 접수된 상태는 미해결로 적고 회신 확인을 다음 조 항목에 넣는다 | EV-0301, EV-0308, EV-0313, EV-0315, EV-0316, EV-0317 | 6 |
| K-1110 | S10 | COMMON | ⚠ | 에너지 차단·감압 여부는 계측 표시로 판단하지 않고 수행 시각·수행자를 기록해 인계한다 | EV-0304, EV-0320 | 2 |
| K-1111 | S11 | COMMON |  | 눈으로만 본 관측은 수치가 없다는 사실을 적고 다음 조에 계측 방법을 지정해 요청한다 | EV-0310, EV-0317 | 2 |

## 해시

| 파일 | sha256 |
|---|---|
| [`prompts/stage-a-records.md`](prompts/stage-a-records.md) | `0a2d10a93a962aafc0b586e5e5e09551817d6283874e3d405849df8b8592d0f9` |
| [`prompts/stage-b-cards.md`](prompts/stage-b-cards.md) | `c913ebf4ff92512eca5eb397048a71e11a6d2c0d6174a7e18b728a5d9be56c10` |
| 원 지시서 `docs/collaboration/t4-handover-cards-prompt-20260930.md` | `b37bfb6c9580f29b4325b256be4610921a7cce19b23bbec374622ba10c959941` |
| 분장 문서 `docs/collaboration/t4-handover-cards-assignment-20260930.md` | `cc768a4ad29fd4a475a2545f642371e94089660de7a2305465d6d0620741f34d` |

## 검증

```bash
uv run --with pydantic==2.9.2 python docs/data/knowledge_cards/kb/20260930-T4/verify.py
# 또는 .venv가 있으면: .venv/Scripts/python.exe docs/data/knowledge_cards/kb/20260930-T4/verify.py
```

[`verify.py`](verify.py)가 보는 것: 스키마 통과, `plan.json` 배정 일치, 인계 메모 5요소(계획된 누락 포함), `true_cause` 누수, `measurements` 키가 MES 신호명인지, 기존 ID 충돌, 카드의 평가용 사건 인용 0건, 근거 사건 2건 이상.

## 안전 근거에 대하여

안전 인계 카드(K-1103·K-1110)는 OSHA 29 CFR 1910.147(f)(4)를 절차 구조 참고로 인용한다. 국내 법적 의무의 대체물이 아니다.

KOSHA GUIDE M-101-2012는 이번 배치의 `safety_basis`에 쓰지 않았다. [`S-02`](../../../../sources/safety/S-02_KOSHA_GUIDE_M-101-2012.md)가 조항 단위 검토 미완 상태이고, 확정 근거로 쓰기 전에 적용 조항 검토와 카드별 매핑이 필요하다고 명시하기 때문이다.

## 재생성

```bash
python docs/data/knowledge_cards/kb/20260930-T4/plan.py              # plan.json
python docs/data/knowledge_cards/kb/20260930-T4/prompts/build_index.py  # prompts/index.json
python docs/data/knowledge_cards/kb/20260930-T4/build_docs.py        # review.md, README.md
```

`build_docs.py`는 `review.md`의 기존 판정 칸을 읽어 그대로 옮긴다. 검수 결과는 재생성으로 지워지지 않는다.
