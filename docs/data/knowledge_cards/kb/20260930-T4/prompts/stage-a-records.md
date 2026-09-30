# 단계 A 지시문 — 근무일지·정비기록 30건 합성 (KB-20260930-T4)

원 지시서: `docs/collaboration/t4-handover-cards-prompt-20260930.md`
설계 규칙: `docs/collaboration/t4-handover-cards-assignment-20260930.md` "대응표로 정한 설계 규칙"
배정: 같은 폴더의 `plan.json` (SEED=20260930으로 고정)

## 만들 것

`plan.json`의 `events` 배열 30건 각각에 대해:

- `Event` 1건 — `shiftlink/agent/schemas.py`의 `Event` 스키마를 따른다. `event_id`, `scenario`, `equipment`, `timeline`(시각별 한 줄), `true_cause`, `true_actions`, `measurements`, `cards_expected`, `restart_attempts`, `split`.
- `Artifact` 2건 — `kind="work_note"`(근무일지)와 `kind="handover"`(교대 인계 메모). `artifact_id`는 `plan.json`의 `artifact_ids` 순서대로. `persona_id`는 `plan.json`이 배정한 값.

배정 값은 `plan.json`을 그대로 따른다. 설비·MES 시나리오·근거 카드·페르소나·사용 장면·누락 항목을 임의로 바꾸지 않는다.

## 인계 메모 5요소

`kind="handover"` 텍스트에는 다음 다섯 가지를 넣는다.

1. 현재 상태 (`current_state`)
2. 앞 근무자가 한 조치 — 시각과 결과 (`prior_action`)
3. 시도했으나 실패한 것 (`failed_attempt`)
4. 미해결 사항 (`unresolved`)
5. 다음 조 확인 사항 (`next_check`)

`plan.json`의 `omitted_handover_element`가 비어 있지 않은 사건은 **그 요소 하나를 일부러 빼고 쓴다**. 누락 사례는 평가와 카드 대비용이며, 빠진 항목은 `plan.json`에 이미 기록되어 있다.

## 상황 설계 근거 — 이것만 쓴다

- **설비·신호·정상범위**: `docs/data/reference/00_plant_and_relations.json`. `measurements`의 키는 이 파일의 `measurement_points[].signal` 이름을 그대로 쓴다(`hpu_pressure`, `gr_brg_temp` 등). 값은 `normal_min`/`normal_max`/`alarm_high`/`alarm_low` 기준으로 정상·이상을 설계한다.
- **공급 관계**: 같은 파일의 `relations`. HPU-01 → RT-01·RT-02·RT-03·CV-01(유압), PDP-01 → GR-01·GR-02·HPU-01(전력), GR-01 → RT-01·RT-02(구동), GR-02 → RT-03·CV-01(구동), CAU-01 → CV-01(공압), CV-01 → RT-03(인터록).
- **MES 시나리오·알람**: `docs/data/knowledge_cards/kb/20260929-A/mes_signal_map.md`의 시나리오 표(`drive_fault`, `hydraulic_fault`, `downstream_block`, `gearbox_overheat`, `hydraulic_overheat`, `gearbox_leak`, `coil_quality_hold`)와 알람 코드.
- **조치 내용**: 승인 카드 `docs/data/knowledge_cards/kb/20260929-A/cards.json`(K-1001~K-1030)의 절차에서 가져온다. 가져온 카드는 `cards_expected`에 넣는다.
- **페르소나 말투·기록 습관**: `seeds/personas_v0.1.yaml`의 V-11·V-12·V-13. `recording_method.work_log`/`handover`/`omission_risk`를 따른다.

## 대응표에서 온 제약

- **소음은 MES 신호가 없다.** 소음·냄새·외관은 측정값이 아니라 작업자 관측 문장으로 쓴다("감속기 쪽에서 갈리는 소리").
- **알람은 시나리오가 걸릴 때만 난다.** `plan.json`의 `mes_scenario`가 `null`인 사건은 알람 없이 신호만 정상범위를 벗어난 상태로 쓴다.
- **HPU가 정지해도 MES 압력은 정상값으로 나온다.** 감압 여부는 사람이 확인해 적어야 하는 정보로 다룬다.
- **RT는 MES 신호(클램프압·반송 속도·모터 전류)만 쓰고 승강부 구조를 가정하지 않는다.**
- **카드가 없는 영역**(HPU 필터 차압, CV 벨트 장력·속도, PDP-01, CAU-01, 출측 정체)은 조치를 "정비 담당 확인"으로 두고 절차를 지어내지 않는다.
- **engine은 capability의 첫 설비에만 시나리오를 건다.** GR-02는 어떤 시나리오의 원인도 되지 않으므로, GR-02 사건의 신호는 사람이 읽은 값으로 기록한다.

## 정답 누수 금지

`work_note`와 `handover` 텍스트에는 **그 시점에 작업자가 관측할 수 있는 것만** 쓴다. `true_cause`(주입 원인) 문장을 그대로 흘리지 않는다. 원인은 추정으로만 적고 추정임을 표시한다.

## 검증

끝내기 전 확인한다.

- `Event`·`Artifact` 스키마 통과
- `work_note`·`handover` 텍스트에 `true_cause` 문장이 그대로 들어가지 않았다
- `split` 배정이 `plan.json`과 일치한다
- 기존 ID와 충돌이 없다 (EV-0301~0330, AR-0301~0360)
