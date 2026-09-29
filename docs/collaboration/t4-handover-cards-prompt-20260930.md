# T4 인계 카드 생성 — 작업 지시 프롬프트 (허재원 담당)

> 작성 2026-09-30, 최재영(Claude Code 초안). 아래 `---` 사이를 AI 작업 도구(Claude Code·Codex 등)에 그대로 붙여 넣는다.
> 참고 선례: `docs/data/knowledge_cards/kb/20260929-A/` (시드 계획 → 프롬프트 해시 → 생성 → 사람 검수 → 승격).

---

너는 ShiftLink 저장소(루트에서 작업, Python은 `.venv/Scripts/python.exe` 또는 `python`)의 데이터 작성 에이전트다. **근무일지·정비기록을 먼저 합성하고, 그 기록에서 반복되는 인계 요령을 뽑아 T4 지식카드를 만든다.**

## 0. T4가 무엇인가 (팀 정의)
- `docs/archive/카드_작성_가이드_초안.md`: **T4 인수인계 맥락 = 현재 상태, 이미 확인한 것, 미해결 사항, 다음 조 확인 사항.** "T4에는 개별 교대 기록 전체보다 **다음에도 재사용할 수 있는 인계 요령**을 담고, **원 사건은 출처로 연결**한다."
- 즉 두 층이다.
  - **기록(사실)**: "B조 14:20 흡입 필터 교체 → 압력 미회복, 관찰 중. 다음 조 30분 뒤 재확인" — 교대마다 1건.
  - **T4 카드(요령)**: "유압 압력 저하 인계 시: 교체한 부품, 교체 후 압력값, 미회복이면 재확인 시각을 적고 받는 사람이 복창한다" — 여러 기록에서 반복된 패턴.

## 1. 단계 A — 근무일지·정비기록 30건 합성
| 구분 | 사건 ID | 용도 |
|---|---|---|
| KB용 | `EV-0301`~`EV-0320` (20건) | T4 카드의 근거로만 쓴다 |
| 평가용 | `EV-0321`~`EV-0330` (10건) | 평가셋 재료. **T4 카드 근거로 절대 쓰지 않는다** |

사건 하나마다:
- `Event` 1건 (`shiftlink/agent/schemas.py`): `scenario`(S1/S2/S3), `equipment`, `timeline`(시각별 한 줄), `true_cause`, `true_actions`, `measurements`, `cards_expected`, `restart_attempts`, `split`(`kb` 또는 `dev`).
- `Artifact` 2건: `kind="work_note"`(근무일지) + `kind="handover"`(교대 인계 메모). ID `AR-0301`부터 순서대로. `persona_id`는 `seeds/personas_v0.1.yaml`의 **V-11·V-12·V-13**(말투·담당 설비·판단 습관을 따른다).
- 인계 메모에는 반드시: **현재 상태 / 앞 근무자가 한 조치(시각·결과) / 시도했으나 실패한 것 / 미해결 사항 / 다음 조 확인 사항.** 일부 사건(20~30%)은 일부러 한 항목을 빠뜨린다(누락 사례 — 평가·카드 대비용). 빠뜨린 것은 `plan.json`에 기록한다.

상황 설계 근거(이것만 쓴다):
- 모의 MES 시나리오·알람·신호: `shiftlink/mes/scenarios/`, `shiftlink/mes/catalog.py`, `docs/data/reference/00_plant_and_relations.json`(설비 ID, 신호 16개와 정상범위, 공급 관계 HPU-01→RT·CV, PDP-01→GR·HPU).
- 조치 내용: 이미 승인된 카드 `docs/data/knowledge_cards/kb/20260929-A/cards.json`(K-1001~K-1030)의 절차에서 가져온다. 해당 카드를 `cards_expected`에 넣는다.
- 측정값: `measurements`의 키는 **MES 신호 이름 그대로**(예: `hpu_pressure`, `gr_brg_temp`), 값은 MES 정상범위 기준으로 정상/이상을 설계한다. 카드↔신호 대응은 `docs/data/knowledge_cards/kb/20260929-A/mes_signal_map.md` 참고. (MES 필드 스키마는 유현준이 확정 중 — 확정되면 이름만 맞춘다.)
- **정답 누수 금지**: `work_note`·`handover` 텍스트에는 작업자가 그 시점에 **관측할 수 있는 것만** 쓴다. `true_cause`(주입 원인)를 문장에 흘리지 않는다.

## 2. 단계 B — T4 카드 추출 (KB용 기록에서만)
- 카드 ID `K-1101`부터. **수량은 정하지 않는다** — KB용 기록 20건에서 **2건 이상 반복된 인계 요령만** 카드로 만든다(목표 10~15장, 채우려고 만들지 않는다).
- 필드:
  - `tacit_type="T4"`, `equipment`(특정 설비 또는 `COMMON`), `component`, `scenario`, `title`, `know_how`, `rationale`
  - `type_payload.handover_method`: `required_context`(**앞 근무자 조치·결과·실패한 시도·남은 관찰**을 항목으로), `recipient_role`, `timing`, `channel`, `acknowledgement`(받는 사람 확인 방법 — 예: 복창·서명)
  - `generalization_evidence`: `supporting_event_ids`(KB용 `EV-03xx` **2건 이상**), `contradicting_event_ids`(반례가 있으면), `generalization_scope`, `confidence_basis`
  - 안전 관련(잠금·에너지 차단 상태 인계 등)이면 `safety_flag=true`, `safety_basis`에 근거 조항: **OSHA 29 CFR 1910.147(f)(4) 교대·인원 변경 시 잠금 연속성**(`docs/sources/safety/S-03_OSHA_29_CFR_1910_147.md`), KOSHA 지침(`S-02`)
  - 고정: `split="kb"`, `status="draft"`, `grade="L0"`, `confidence=0.0`(미평가 표시), `version="1.0-draft-<배치ID>"`
  - `provenance`: `seed_ids=["<배치ID>:seed=<시드>", "slot:<Sxx>"]`, `persona_id`, `event_ids`(근거 사건), `generator`(도구·에이전트 이름), `generated_at`(+09:00), `sources`(근거 사건과 문헌 쪽수), `extraction_method`, `model_version`(실제 모델 ID), `prompt_version`(`<프롬프트 파일 경로>@sha256:<해시>`), `schema_version`

## 3. 재현·추적 기록 (KB-20260929-A와 같은 방식)
폴더 `docs/data/knowledge_cards/kb/<YYYYMMDD>-T4/`에:
- `plan.py` → `plan.json`: 시드로 사건별 설비·시나리오·페르소나·누락 항목 배정을 고정(재실행 시 바이트 동일)
- `prompts/`: 실제로 AI에 넣은 지시문 원문 + `index.json`(sha256, 모델, 실행 시각). 파일은 LF 줄바꿈으로 저장하고 해시한다.
- `events.json`, `artifacts.json`, `cards.json`
- `review.md`: 카드마다 사람이 읽을 요약 + `판정` 칸(accepted / rejected / 수정)
- `README.md`: 카드 → 근거 사건 → 프롬프트 → 해시 추적표

## 4. 검증 (끝내기 전 필수)
```
python -c "import json;from shiftlink.agent.schemas import Event,Artifact,KnowledgeCard as K;d='docs/data/knowledge_cards/kb/<폴더>/';[Event.model_validate(x) for x in json.load(open(d+'events.json',encoding='utf-8'))];[Artifact.model_validate(x) for x in json.load(open(d+'artifacts.json',encoding='utf-8'))];[K.model_validate(x) for x in json.load(open(d+'cards.json',encoding='utf-8'))];print('ok')"
```
추가로 확인:
- T4 카드의 `supporting_event_ids`가 전부 `split="kb"` 사건인가 (평가용 `EV-0321`~`0330`이 섞이면 실패)
- `work_note`·`handover` 텍스트에 `true_cause` 문장이 그대로 들어가지 않았나
- 기존 ID와 충돌이 없나 (`EV-0301`~, `AR-0301`~, `K-1101`~)

## 5. 하지 않는 것
- 매뉴얼만 보고 T4를 만들지 않는다(인계 요령은 기록에서 나온다).
- 기존 평가용 T4 50장(`drafts/20260925-t4-synthetic`, `20260926-t4-*`, `split=dev`)을 KB로 옮기거나 근거로 쓰지 않는다.
- `.env`·접속 정보·재배포 권한 없는 PDF 원문을 커밋하지 않는다.
- 사람 검수 전 카드를 `accepted`로 올리지 않는다.

## 6. 끝나면
- 브랜치 `feat/edge-t4-handover-cards`(origin/main 기준), 커밋·PR.
- 보고: 사건 수(KB/평가), 인계 메모 누락 사례 수, T4 카드 수, 카드별 근거 사건 수, 검증 결과.

---
