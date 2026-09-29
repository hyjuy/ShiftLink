# 단계 B 지시문 — T4 인계 카드 추출 (KB-20260930-T4)

원 지시서: `docs/collaboration/t4-handover-cards-prompt-20260930.md`
입력: 같은 폴더의 `events.json`·`artifacts.json` 중 **`split="kb"` 사건 20건(EV-0301~EV-0320)만**

## T4가 무엇인가

`docs/archive/카드_작성_가이드_초안.md`: T4 = 인수인계 맥락(현재 상태, 이미 확인한 것, 미해결 사항, 다음 조 확인 사항). "T4에는 개별 교대 기록 전체보다 **다음에도 재사용할 수 있는 인계 요령**을 담고, 원 사건은 출처로 연결한다."

두 층을 구분한다.

- **기록(사실)**: "B조 14:20 흡입 필터 교체 → 압력 미회복, 관찰 중. 다음 조 30분 뒤 재확인" — 교대마다 1건
- **T4 카드(요령)**: "유압 압력 저하 인계 시: 교체한 부품, 교체 후 압력값, 미회복이면 재확인 시각을 적고 받는 사람이 복창한다" — 여러 기록에서 반복된 패턴

## 수량

카드 ID는 `K-1101`부터. **수량은 정하지 않는다.** KB용 기록 20건에서 **2건 이상 반복된 인계 요령만** 카드로 만든다. 목표는 10~15장이지만 채우려고 만들지 않는다. 한 건에만 나타난 요령은 카드로 올리지 않는다.

## 필드

- `tacit_type="T4"`, `equipment`(특정 설비 또는 `COMMON`), `component`, `scenario`, `title`, `know_how`, `rationale`
- `type_payload.handover_method` — 5필드 전부 채운다
  - `required_context`: 앞 근무자 조치·결과, 실패한 시도, 남은 관찰을 항목으로
  - `recipient_role`, `timing`, `channel`
  - `acknowledgement`: 받는 사람이 확인하는 방법(복창·서명 등)
- `generalization_evidence`
  - `supporting_event_ids`: KB용 EV-03xx **2건 이상**
  - `contradicting_event_ids`: 반례가 있으면 적는다
  - `generalization_scope`, `confidence_basis`
- 안전 관련(잠금·에너지 차단 상태 인계 등)이면 `safety_flag=true`, `safety_basis`에 근거 조항
  - OSHA 29 CFR 1910.147(f)(4) 교대·인원 변경 시 잠금 연속성 — `docs/sources/safety/S-03_OSHA_29_CFR_1910_147.md`
  - KOSHA GUIDE M-101-2012 — `docs/sources/safety/S-02_KOSHA_GUIDE_M-101-2012.md`
- 고정값: `split="kb"`, `status="draft"`, `grade="L0"`, `confidence=0.0`(미평가 표시), `version="1.0-draft-KB-20260930-T4"`
- `provenance`
  - `seed_ids`: `["KB-20260930-T4:seed=20260930", "slot:<Sxx>"]`
  - `persona_id`, `event_ids`(근거 사건)
  - `generator`(도구·에이전트 이름), `generated_at`(+09:00)
  - `sources`: 근거 사건과 문헌 쪽수
  - `extraction_method`, `model_version`(실제 모델 ID)
  - `prompt_version`: `<이 파일 경로>@sha256:<해시>`
  - `schema_version`

## 금지

- 평가용 사건 EV-0321~EV-0330을 근거로 쓰지 않는다. `supporting_event_ids`에 하나라도 섞이면 실패다.
- 매뉴얼만 보고 카드를 만들지 않는다. 요령은 기록에서 나온다.
- 기존 평가용 T4 50장(`drafts/*t4*`, `split=dev`)을 KB로 옮기거나 근거로 쓰지 않는다.
- 검수 전에 `accepted`로 올리지 않는다.

## 검증

- `KnowledgeCard` 스키마 통과 (T4는 `type_payload.handover_method` 필수)
- `supporting_event_ids`가 전부 `split="kb"` 사건인가
- 평가용 사건 인용 0건
- 기존 ID와 충돌이 없나 (K-1101~)
