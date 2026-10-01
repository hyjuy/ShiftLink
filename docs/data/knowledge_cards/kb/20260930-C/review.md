# KB-20260930-C 검수표

A 배치와 같은 항목 순서로 정리했다. 판정 칸에 `accepted` / `rejected` / `수정`을 기록하고 판정 근거를 남긴다. 사람 판정은 미정이며 이 문서를 작성하거나 재생성해도 카드 상태·등급은 자동 변경하지 않는다. 출처·계보·편입 게이트는 별도 검수 대상이다.

## K-1201 · HPU · T2 — 필터 차압 > 1.2 bar에서 설치된 막힘 표시기 종류에 따라 확인 위치를 나눈다

- **부품**: 필터 막힘 표시기
- **증상**: hpu_filter_dp > 1.2 bar(가상 정상 범위 0–1.2 bar)이며 실제 막힘 표시 확인이 필요하다.
- **노하우**: 필터 차압 > 1.2 bar는 표시기 확인을 시작하는 신호로만 쓴다. 대상 필터에 광학식 막힘 표시기가 설치되어 있으면 해당 표시기의 막힘 표시를 확인한다. 전기식 표시기가 설치되어 있으면 제어반에 직접 표시되는 고장 신호를 확인한다. 어느 표시기가 설치되어 있는지 확인되지 않으면 설비 담당자에게 표시기 사양을 확인하고 차압 값만으로 막힘이나 교체를 확정하지 않는다. 전기식 표시기에 차단 시퀀스를 설정할 수 있다는 원문 설명은 해당 HPU에 시퀀스가 구현되어 있다는 뜻이 아니다. 검색 관측 기준: hpu_filter_dp > 1.2 bar(가상 정상 범위 0.0–1.2 bar). 이 수치는 기본 가상 MES의 정상 범위 경계이며 제조사 고장·작업 기준이 아니다. 해당 run의 config_id·신호 단위·quality=good을 확인하고, 실제 계측과 대상 모델 기준을 별도로 대조한다.
- **근거 설명**: MAN-C-012 §1.10은 optical/electrical clogging indicators를 구분하고 전기식 표시기의 고장 신호는 제어반에 직접 표시된다고 설명한다. 표시기 종류별 확인 위치만 요약한다. 저온과 차압을 인과관계로 묶을 근거가 없어 온도 예시를 대체했다.
- **조건**: `hpu_filter_dp_state == high`
- **출처**: M-C-006 — MAN-C-012.pdf | PDF p.6 / 인쇄 p.7 / §1.10 Oil filters control
- **작성 노트**: 근거 사건: -; 재가동 유형: -; 프롬프트: `docs/data/knowledge_cards/kb/20260930-C/prompts/T2.md@sha256:4c4023b9a29976e399639d538fbb263814da95bd845f7148504fec1124d703be`; 정책 연결: `docs/data/knowledge_cards/kb/20260930-C/policy_manifest.json@sha256:29afb0ecb89456db9291e8c32bf240ef43467c6cbc852342f43c7bf98b20d37d` · [카드별 보완 항목](policy_manifest.json); 독립 검토 근거: [1차 판정](review_round1.md) · [수정 후 재검토](review_round2.md) · [변경 전후](review_changes.json)
- **판정**:
- **판정 근거**:

## K-1202 · HPU · T2 — 필터 차압 > 1.2 bar 후 실제 교체 표시가 있으면 정기 교체 시점과 별도로 처리한다

- **부품**: 필터 카트리지
- **증상**: 필터 차압 > 1.2 bar가 관측되었고 카트리지 교체 필요 여부를 확인한다.
- **노하우**: 설치된 막힘 표시기가 카트리지 교체 필요를 실제로 표시하면 원문은 표시가 요구할 때마다 카트리지를 교체하도록 한다. 교체 표시가 확인되지 않으면 필터 차압 > 1.2 bar만으로 그 조치를 확정하지 않고 표시기 확인과 정기 교체 계획 검토로 남긴다. 표시가 없는 경우에도 원문은 최소 연 1회 교체를 강하게 권고하므로 마지막 교체 이력과 해당 모델의 정기 교체 지침을 확인한다. 교체 필요가 표시된 경우 정비 담당자에게 현장 절차·모델 적용성·작업 전 안전 조건을 확인하도록 요청한다. 이 카드는 교체 작업 방법이나 작업 허가를 정하지 않는다. 검색 관측 기준: hpu_filter_dp > 1.2 bar(가상 정상 범위 0.0–1.2 bar). 이 수치는 기본 가상 MES의 정상 범위 경계이며 제조사 고장·작업 기준이 아니다. 해당 run의 config_id·신호 단위·quality=good을 확인하고, 실제 계측과 대상 모델 기준을 별도로 대조한다.
- **근거 설명**: MAN-C-012 §1.10은 clogging indicator가 교체 필요를 표시할 때마다 교체하라는 조건과 최소 연 1회 정기 교체 권고를 구분한다. 이 카드는 표시의 실제 확인 여부에 따라 교체 요구와 정기 이력 확인을 나눈다. 가상 차압은 원문 표시기의 임계값을 대체하지 않는다.
- **조건**: `hpu_filter_dp_state == high`
- **출처**: M-C-006 — MAN-C-012.pdf | PDF p.6 / 인쇄 p.7 / §1.10 Oil filters control
- **작성 노트**: 근거 사건: -; 재가동 유형: -; 프롬프트: `docs/data/knowledge_cards/kb/20260930-C/prompts/T2.md@sha256:4c4023b9a29976e399639d538fbb263814da95bd845f7148504fec1124d703be`; 정책 연결: `docs/data/knowledge_cards/kb/20260930-C/policy_manifest.json@sha256:29afb0ecb89456db9291e8c32bf240ef43467c6cbc852342f43c7bf98b20d37d` · [카드별 보완 항목](policy_manifest.json); 독립 검토 근거: [1차 판정](review_round1.md) · [수정 후 재검토](review_round2.md) · [변경 전후](review_changes.json)
- **판정**:
- **판정 근거**:

## K-1203 · HPU · T2 — 압력 이상 여부에 따라 릴리프 설정과 유량 확인 경로를 나눈다

- **부품**: 기어·베인 펌프 및 릴리프 밸브
- **증상**: 펌프 출구 압력은 읽히지만 작업에 필요한 압력 또는 유량이 부족하다.
- **노하우**: MES hpu_pressure < 145 bar(가상 정상 범위 145–165 bar)는 확인 시작 신호다. 먼저 펌프 출구의 실제 압력을 해당 계통의 정상 작업압과 대조한다. 정상 작업압이 아니면 릴리프 밸브 설정이 올바른지 확인한다. 설정이 맞는데 동작이 진행 중이면 동작이 멈춘 상태에서 압력을 다시 확인하고, 동작이 없으면 밸브 리턴 라인의 유량 유무를 확인한다. 실제 압력이 정상 작업압이고 문제가 유량 부족이면 펌프 출구 유량을 확인한다. 펌프 유량이 정상일 때는 목록의 다음 장치를 확인하고, 정상이지 않으면 릴리프 탱크 라인으로 흐르는 유량이 있는지에 따라 릴리프 밸브 또는 펌프 점검으로 나눈다. MES hpu_flow < 38 L_min 또는 38–46 L_min(가상 정상 범위)만으로 원문 유량 판정을 대신하지 않는다. 이 흐름도는 확인 경로의 요약이며, 유량계 설치·계통 작동·밸브 조정은 담당자가 대상 모델의 작업표준과 안전 조건을 확인한 범위에서만 수행한다. 이 수치는 기본 가상 MES의 정상 범위 경계이며 제조사 고장·작업 기준이 아니다. 해당 run의 config_id·신호 단위·quality=good을 확인하고, 실제 계측과 대상 모델 기준을 별도로 대조한다.
- **근거 설명**: Algo A.1은 출구 압력 있음에서 정상 작업압 여부를 먼저 갈라 릴리프 설정 확인 경로와 유량 부족 확인 경로를 별도로 둔다. low/normal은 가상 MES 검색 상태이며 원문 작업압 판정은 따로 필요하다.
- **조건**: `hpu_pressure_state == low`
- **출처**: M-C-001 — 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf | PDF p.17 / 인쇄 p.17 / Algo A.1 System test for gear and vane pumps, 출구 압력 있음 분기
- **작성 노트**: 근거 사건: -; 재가동 유형: -; 프롬프트: `docs/data/knowledge_cards/kb/20260930-C/prompts/T2.md@sha256:4c4023b9a29976e399639d538fbb263814da95bd845f7148504fec1124d703be`; 정책 연결: `docs/data/knowledge_cards/kb/20260930-C/policy_manifest.json@sha256:29afb0ecb89456db9291e8c32bf240ef43467c6cbc852342f43c7bf98b20d37d` · [카드별 보완 항목](policy_manifest.json); 독립 검토 근거: [1차 판정](review_round1.md) · [수정 후 재검토](review_round2.md) · [변경 전후](review_changes.json)
- **판정**:
- **판정 근거**:

## K-1204 · CV · T2 · ⚠ 안전 — 벨트 장력 < 380 kPa에서 미끄럼의 실제 느슨함 여부에 따라 조치를 나눈다

- **부품**: 벨트·구동부
- **증상**: 운전 지시가 있는 컨베이어에서 벨트가 미끄러지거나 돌지 않는다.
- **노하우**: 벨트 장력 < 380 kPa만으로 느슨한 벨트를 확정하지 않는다. 정지 상태에서 실제 벨트 느슨함이 확인되면 벨트 장력과 정렬을 바로잡는다. 벨트가 늘어나 느슨해진 경우는 원문이 벨트 길이 단축을 구분해 제시하므로 일반 장력 조정으로 끝내지 않는다. 실제 벨트 느슨함이 없으면 벨트·롤러에 끼인 이물질과 거칠거나 고착된 베어링을 확인하는 경로로 옮긴다. 정비 작업은 설비 정지 후 자격을 갖춘 담당자가 수행한다. 검색 관측 기준: cv_belt_tension < 380.0 kPa(가상 정상 범위 380.0–460.0 kPa). 이 수치는 기본 가상 MES의 정상 범위 경계이며 제조사 고장·작업 기준이 아니다. 해당 run의 config_id·신호 단위·quality=good을 확인하고, 실제 계측과 대상 모델 기준을 별도로 대조한다.
- **근거 설명**: Convey-All 표는 Belt loose와 Conveyor belt loose because it has stretched에 각각 Tighten and align, Shorten belt를 제시하고, 다른 미끄럼 원인에 이물질과 고착 베어링을 든다. 가상 장력 상태가 물리적 늘어남을 증명하지는 않는다.
- **안전 근거**: MISUMI §3.2.2: 운전 중 작동영역에 손을 넣지 않으며, 기계 작업은 정지 후 자격을 갖춘 담당자만 수행한다.
- **조건**: `cv_belt_tension_state == low`
- **출처**: M-C-004 — Convey-All-TroubleshootingGuide.pdf | PDF p.1 / General Conveyor / Conveyor belt doesn't turn or is slipping; M-C-007 — conveyor-manual-0323-en.pdf | PDF p.11 / 인쇄 p.7 / §3.2.2 Hazards - Mechanical Energy
- **작성 노트**: 근거 사건: -; 재가동 유형: -; 프롬프트: `docs/data/knowledge_cards/kb/20260930-C/prompts/T2.md@sha256:4c4023b9a29976e399639d538fbb263814da95bd845f7148504fec1124d703be`; 정책 연결: `docs/data/knowledge_cards/kb/20260930-C/policy_manifest.json@sha256:29afb0ecb89456db9291e8c32bf240ef43467c6cbc852342f43c7bf98b20d37d` · [카드별 보완 항목](policy_manifest.json); 독립 검토 근거: [1차 판정](review_round1.md) · [수정 후 재검토](review_round2.md) · [변경 전후](review_changes.json)
- **판정**:
- **판정 근거**:

## K-1205 · CV · T2 · ⚠ 안전 — 벨트 장력 380–460 kPa(가상 정상 범위)인데 이송량이 줄면 벨트와 롤러 표면 상태를 나눈다

- **부품**: 벨트·구동 롤러
- **증상**: 운전 중 이송 능력이 떨어졌으며 cv_belt_tension은 380–460 kPa(가상 정상 범위)이다.
- **노하우**: 벨트 장력 380–460 kPa(가상 정상 범위)을 구동 정상으로 간주하지 않는다. 실제 컨베이어 벨트가 미끄러지는지 확인한다. 벨트 느슨함이 확인되면 장력과 정렬을 조정하는 경로로 간다. 느슨함이 확인되지 않으면 구동 롤러의 마모·미끄럼 및 롤러 래깅 마모를 확인한다. 구동 롤러 관련 항목에는 V-belt 교체가, 래깅 마모에는 롤러 교체 또는 재래깅이 원문 조치로 제시되어 있으므로 실제 원인과 구동 구조를 확인한 뒤 담당자가 조치를 선택한다. 검색 관측 기준: 380.0 <= cv_belt_tension <= 460.0 kPa(가상 정상 범위 380.0–460.0 kPa). 이 수치는 기본 가상 MES의 정상 범위 경계이며 제조사 고장·작업 기준이 아니다. 해당 run의 config_id·신호 단위·quality=good을 확인하고, 실제 계측과 대상 모델 기준을 별도로 대조한다.
- **근거 설명**: Convey-All Low conveying capacity 표는 conveyor belt slipping, drive roller worn/slipping, roller lagging worn을 서로 다른 원인·조치로 구분한다. 장력 normal은 가상 검색 상태로만 사용하고 실제 느슨함 확인을 생략하지 않는다.
- **안전 근거**: MISUMI §3.2.2: 기계 작업은 정지 후 자격을 갖춘 담당자만 수행한다.
- **조건**: `cv_belt_tension_state == normal`
- **출처**: M-C-004 — Convey-All-TroubleshootingGuide.pdf | PDF p.2 / General Conveyor / Low conveying capacity; M-C-007 — conveyor-manual-0323-en.pdf | PDF p.11 / 인쇄 p.7 / §3.2.2 Hazards - Mechanical Energy
- **작성 노트**: 근거 사건: -; 재가동 유형: -; 프롬프트: `docs/data/knowledge_cards/kb/20260930-C/prompts/T2.md@sha256:4c4023b9a29976e399639d538fbb263814da95bd845f7148504fec1124d703be`; 정책 연결: `docs/data/knowledge_cards/kb/20260930-C/policy_manifest.json@sha256:29afb0ecb89456db9291e8c32bf240ef43467c6cbc852342f43c7bf98b20d37d` · [카드별 보완 항목](policy_manifest.json); 독립 검토 근거: [1차 판정](review_round1.md) · [수정 후 재검토](review_round2.md) · [변경 전후](review_changes.json)
- **판정**:
- **판정 근거**:

## K-1206 · CV · T2 · ⚠ 안전 — 벨트 속도 < 10 m_min·대기열 > 70 pct에서는 실제 막힘과 느린 벨트를 구분한다

- **부품**: 벨트·구동 영역
- **증상**: 운전 지시가 있는데 벨트가 느리고 이송물이 쌓인다.
- **노하우**: 운전 지시가 없는 정상 정지라면 이 카드를 적용하지 않는다. cv_queue_len > 70 pct는 막힘을 직접 증명하지 않으므로 실제 끼임·쐐기 상태를 확인한다. 이송물이 실제로 끼었으면 즉시 정지하고 도구로 제거하며 맨손으로 빼지 않는다. 끼임이 없고 벨트가 실제로 느리면 풀리·장력 롤러·안내 롤러의 먼지나 오염을 확인하고, 벨트 마모가 확인되면 교체 경로로 간다. 대기열 숫자만 보고 속도 설정을 올리지 않는다. 검색 관측 기준: cv_speed < 10.0 m_min(가상 정상 범위 10.0–60.0 m_min); cv_queue_len > 70.0 pct(가상 정상 범위 0.0–70.0 pct). 이 수치는 기본 가상 MES의 정상 범위 경계이며 제조사 고장·작업 기준이 아니다. 해당 run의 config_id·신호 단위·quality=good을 확인하고, 실제 계측과 대상 모델 기준을 별도로 대조한다.
- **근거 설명**: MISUMI §3.2.2는 적체 원인 제거 시 정지와 도구 사용을 요구하고, §10.3 Belt moving slower는 구동 영역 오염과 벨트 마모를 확인하도록 한다. 대기열과 속도의 인과관계는 원문에 없으므로 현장 증상에 따라 두 원문 경로를 선택한다.
- **안전 근거**: MISUMI §3.2.2: 고장 시 즉시 정지한다. 끼인 이송물은 도구로 제거하고 맨손을 사용하지 않는다.
- **조건**: `cv_speed_state == low`
- **조건**: `cv_queue_len_state == high`
- **출처**: M-C-007 — conveyor-manual-0323-en.pdf | PDF p.11 / 인쇄 p.7 / §3.2.2 Hazards - Mechanical Energy; M-C-007 — conveyor-manual-0323-en.pdf | PDF p.70 / 인쇄 p.66 / §10.3 Frequently Asked Questions (FAQ)
- **작성 노트**: 근거 사건: -; 재가동 유형: -; 프롬프트: `docs/data/knowledge_cards/kb/20260930-C/prompts/T2.md@sha256:4c4023b9a29976e399639d538fbb263814da95bd845f7148504fec1124d703be`; 정책 연결: `docs/data/knowledge_cards/kb/20260930-C/policy_manifest.json@sha256:29afb0ecb89456db9291e8c32bf240ef43467c6cbc852342f43c7bf98b20d37d` · [카드별 보완 항목](policy_manifest.json); 독립 검토 근거: [1차 판정](review_round1.md) · [수정 후 재검토](review_round2.md) · [변경 전후](review_changes.json)
- **판정**:
- **판정 근거**:

## K-1207 · RT · T2 · ⚠ 안전 — 반송 속도 < 20 m_min에서는 롤러 미기동과 물품 미이송을 구분한다

- **부품**: 롤러 반송부
- **증상**: 반송 지시가 있지만 물품이 이동하지 않는다.
- **노하우**: 운전 지시가 없는 정상 정지라면 적용하지 않는다. 반송 지시가 있는데 RollerDrive가 돌지 않으면 주 스위치·제어 전원 상태, 전원선 손상, RollerDrive 고장을 확인하는 경로로 간다. 물품이 이송되지 않는 증상에는 별도 표 항목으로 PolyVee 구동 벨트, 허용 이송중량, MultiControl을 확인하는 경로로 나눈다. 부품 교체는 대상이 원문과 같은 구동 구조인지 확인한 담당자가 수행한다. 원문 두 번째 항목은 롤러가 회전 중이라고 명시하지 않으며 두 증상이 겹칠 수 있다. 구동부 관측을 함께 남겨 담당자가 관련 항목을 확인한다. 검색 관측 기준: rt_speed < 20.0 m_min(가상 정상 범위 20.0–120.0 m_min). 이 수치는 기본 가상 MES의 정상 범위 경계이며 제조사 고장·작업 기준이 아니다. 해당 run의 config_id·신호 단위·quality=good을 확인하고, 실제 계측과 대상 모델 기준을 별도로 대조한다.
- **근거 설명**: Interroll p.51 표는 Transport process cannot be started and RollerDrive does not run과 Conveying goods are not being transported를 별도 항목으로 둔다. 클램프 원문 근거가 없어 계획 예시를 반송 분기로 대체했다.
- **안전 근거**: Interroll p.51 In case of a fault: 전원을 끄고 우발적 기동을 막는다. 전기 고장은 훈련받은 전기 담당자만 처리한다.
- **조건**: `rt_speed_state == low`
- **출처**: M-C-002 — 1110_Roller_conveyor_EN_TNr_1131919_V1.0.pdf | PDF p.51 / 인쇄 p.51 / Troubleshooting: Transport process cannot be started; Conveying goods are not being transported
- **작성 노트**: 근거 사건: -; 재가동 유형: -; 프롬프트: `docs/data/knowledge_cards/kb/20260930-C/prompts/T2.md@sha256:4c4023b9a29976e399639d538fbb263814da95bd845f7148504fec1124d703be`; 정책 연결: `docs/data/knowledge_cards/kb/20260930-C/policy_manifest.json@sha256:29afb0ecb89456db9291e8c32bf240ef43467c6cbc852342f43c7bf98b20d37d` · [카드별 보완 항목](policy_manifest.json); 독립 검토 근거: [1차 판정](review_round1.md) · [수정 후 재검토](review_round2.md) · [변경 전후](review_changes.json)
- **판정**:
- **판정 근거**:

## K-1208 · RT · T2 · ⚠ 안전 — 전류 > 16 A(가상 정상 범위 8–16 A)에서는 실제 과전류 차단과 이송중량 초과를 먼저 구분한다

- **부품**: 반송 모터·차단기
- **증상**: 반송 중 rt_motor_current > 16 A(가상 정상 범위 8–16 A)가 관측되고 모터 차단 상태 확인이 필요하다.
- **노하우**: MES rt_motor_current > 16 A(가상 정상 범위 8–16 A)만으로 과전류 차단을 확정하지 않는다. 실제 모터 차단기가 과전류로 동작한 경우에만 원문 항목을 적용한다. 이송중량이 대상 설비 허용중량을 초과하면 허용중량을 지키는 경로로 간다. 중량 초과 여부와 별도로 전기 담당자가 단락과 전기 연결 상태를 확인하고 결함 부품을 처리하는 경로로 간다. 실제 과전류 차단이 확인되지 않으면 이 원문 항목으로 원인이나 조치를 확정하지 않는다. 중량 초과와 단락은 배타적인 원인이 아니며 중량 확인만으로 전기 점검 필요를 없애지 않는다. 이 수치는 기본 가상 MES의 정상 범위 경계이며 제조사 고장·작업 기준이 아니다. 해당 run의 config_id·신호 단위·quality=good을 확인하고, 실제 계측과 대상 모델 기준을 별도로 대조한다.
- **근거 설명**: Interroll p.52 Motor circuit breaker is triggered due to excessive current consumption 항목은 원인으로 Short circuit과 Transport weight too high를 구분한다. rt_motor_current는 RT-03, rt_lift_delay는 RT-02에 있으므로 지연과 전류를 한 설비 조건으로 묶지 않았다.
- **안전 근거**: Interroll p.51: 전원을 끄고 우발적 기동을 막는다. 전기 고장은 훈련받은 전기 담당자만 처리한다.
- **조건**: `rt_motor_current_state == high`
- **출처**: M-C-002 — 1110_Roller_conveyor_EN_TNr_1131919_V1.0.pdf | PDF p.52 / 인쇄 p.52 / Troubleshooting: Motor circuit breaker is triggered due to excessive current consumption; M-C-002 — 1110_Roller_conveyor_EN_TNr_1131919_V1.0.pdf | PDF p.51 / 인쇄 p.51 / Troubleshooting: In case of a fault (전원 차단·우발 기동 방지·전기 담당 자격)
- **작성 노트**: 근거 사건: -; 재가동 유형: -; 프롬프트: `docs/data/knowledge_cards/kb/20260930-C/prompts/T2.md@sha256:4c4023b9a29976e399639d538fbb263814da95bd845f7148504fec1124d703be`; 정책 연결: `docs/data/knowledge_cards/kb/20260930-C/policy_manifest.json@sha256:29afb0ecb89456db9291e8c32bf240ef43467c6cbc852342f43c7bf98b20d37d` · [카드별 보완 항목](policy_manifest.json); 독립 검토 근거: [1차 판정](review_round1.md) · [수정 후 재검토](review_round2.md) · [변경 전후](review_changes.json)
- **판정**:
- **판정 근거**:

## K-1209 · GR · T2 · ⚠ 안전 — 진동 RMS > 2.8 mm_s(가상 정상 범위 0.5–2.8 mm_s)에서 베어링 온도 동반 여부에 따라 추가 확인을 나눈다

- **부품**: 기어박스·베어링
- **증상**: 정상 운전과 비교해 진동이 증가했으며 베어링 온도 변화 확인이 필요하다.
- **노하우**: 평상시와 다른 진동·소음·온도 변화가 있고 판단이 불확실하면 주 모터를 정지하고 원인을 확인한다. gr_brg_temp > 62 degC(가상 정상 범위 30–62 degC)가 실제 베어링부 과열로 확인되면 오일 부족·과다, 오일 교환 이력, 베어링 손상을 확인하는 온도 점검 경로를 추가한다. gr_brg_temp가 30–62 degC(가상 정상 범위)여도 새로운 진동을 정상으로 취급하지 않으며 소음 종류를 확인한다. 규칙적인 갈림 소음이면 오일과 베어링 확인, 두드리는 소음이면 서비스 문의, 불규칙한 소음이면 오일 확인 후 구동을 정지하고 서비스에 문의하는 원문 소음 분기로 나눈다. 이 수치는 기본 가상 MES의 정상 범위 경계이며 제조사 고장·작업 기준이 아니다. 해당 run의 config_id·신호 단위·quality=good을 확인하고, 실제 계측과 대상 모델 기준을 별도로 대조한다.
- **근거 설명**: SEW p.5는 정상 운전 대비 온도·소음·진동 변화 시 불확실하면 주 모터를 정지하고 원인을 찾도록 한다. p.45는 베어링부 고온과 각 소음 유형의 점검·조치를 별도로 제시한다. 진동 RMS만으로 특정 소음이나 베어링 고장을 확정하지 않는다.
- **안전 근거**: SEW p.5 Startup/operation: 정상 운전 대비 변화가 있고 의심되면 주 모터를 정지하고 원인을 확인한다.
- **조건**: `gr_vib_rms_state == high`
- **출처**: M-C-003 — 26867443.pdf | PDF p.5 / Safety notes / Startup/operation; M-C-003 — 26867443.pdf | PDF p.45 / 인쇄 p.45 / §9.1 Gear unit malfunctions
- **작성 노트**: 근거 사건: -; 재가동 유형: -; 프롬프트: `docs/data/knowledge_cards/kb/20260930-C/prompts/T2.md@sha256:4c4023b9a29976e399639d538fbb263814da95bd845f7148504fec1124d703be`; 정책 연결: `docs/data/knowledge_cards/kb/20260930-C/policy_manifest.json@sha256:29afb0ecb89456db9291e8c32bf240ef43467c6cbc852342f43c7bf98b20d37d` · [카드별 보완 항목](policy_manifest.json); 독립 검토 근거: [1차 판정](review_round1.md) · [수정 후 재검토](review_round2.md) · [변경 전후](review_changes.json)
- **판정**:
- **판정 근거**:

## K-1210 · GR · T2 · ⚠ 안전 — 베어링 온도 > 62 degC(가상 정상 범위 30–62 degC)에서는 확인된 유면과 오일 이력에 따라 조치를 나눈다

- **부품**: 베어링·윤활유
- **증상**: MES gr_brg_temp > 62 degC(가상 정상 범위 30–62 degC)가 관측되어 실제 베어링부 온도와 해당 모델의 과열 기준 대조가 필요하며 윤활 상태 확인이 필요하다.
- **노하우**: MES gr_brg_temp > 62 degC(가상 정상 범위 30–62 degC)는 확인 시작 신호이며 실제 베어링부 과열을 확인한다. 정비 점검은 모터 전원을 차단하고 우발 재기동을 막은 뒤 기어박스가 식을 때까지 기다린다. 유면 부족이나 과다가 확인되면 해당 설치 자세의 유면 기준으로 수정하는 경로로 간다. 유면 문제는 확인되지 않았지만 오일 교환 이력이 오래되어 대상 제조사 교환 기준에 해당하면 오일 교환 경로로 간다. 이 두 사유가 확인되지 않으면 베어링 손상을 확인하고 필요시 서비스에 문의한다. 관측되지 않은 손상이나 오일 노화를 원인으로 확정하지 않는다. 이 수치는 기본 가상 MES의 정상 범위 경계이며 제조사 고장·작업 기준이 아니다. 해당 run의 config_id·신호 단위·quality=good을 확인하고, 실제 계측과 대상 모델 기준을 별도로 대조한다.
- **근거 설명**: SEW §9.1 Bearing point temperatures too high는 오일 부족/과다, 오일 노화, 베어링 손상을 원인과 조치별로 구분한다. §8.3은 유면 점검 전에 전원 차단·재기동 방지·냉각 대기를 명시한다. GR 전류와 부하의 조치 근거가 없어 온도 기반 원문 분기로 대체했다.
- **안전 근거**: SEW §8.3: 모터 전원을 차단하고 우발 재기동을 막으며 기어박스가 식을 때까지 기다린다.
- **조건**: `gr_brg_temp_state == high`
- **출처**: M-C-003 — 26867443.pdf | PDF p.45 / 인쇄 p.45 / §9.1 Gear unit malfunctions; M-C-003 — 26867443.pdf | PDF p.42 / 인쇄 p.42 / §8.3 Inspection and maintenance of the gear unit / Checking the oil level
- **작성 노트**: 근거 사건: -; 재가동 유형: -; 프롬프트: `docs/data/knowledge_cards/kb/20260930-C/prompts/T2.md@sha256:4c4023b9a29976e399639d538fbb263814da95bd845f7148504fec1124d703be`; 정책 연결: `docs/data/knowledge_cards/kb/20260930-C/policy_manifest.json@sha256:29afb0ecb89456db9291e8c32bf240ef43467c6cbc852342f43c7bf98b20d37d` · [카드별 보완 항목](policy_manifest.json); 독립 검토 근거: [1차 판정](review_round1.md) · [수정 후 재검토](review_round2.md) · [변경 전후](review_changes.json)
- **판정**:
- **판정 근거**:

## K-1211 · HPU · T6 · ⚠ 안전 — 필터·오일 정비 후 압력 152 bar가 정상 범위여도 유량 34 L_min·기포·소음을 함께 확인한다

- **부품**: 필터·오일 정비 후 유압 회로
- **노하우**: 필터 또는 오일 정비 뒤 재가동에서는 압력이 회복됐더라도 펌프 쪽 소음·관찰 가능한 기포와 유량을 함께 본다. 기록의 시험기동에서는 압력 회복과 소음·기포가 동시에 나타났다. 같은 상태가 다시 보이면 반복 기동으로 밀어붙이지 말고 정지 상태에서 정비 담당에게 충유·공기 제거 확인을 요청한다. 공기 제거 방법과 무부하 운전 설정은 해당 설비 작업표준으로 확인하며 이 카드에서 정하지 않는다. 근거 시험기동의 관측은 hpu_pressure 152 bar(가상 정상 145–165 bar 이내), hpu_flow 34 L_min(가상 정상 38–46 L_min의 하한 미만)이며 기포와 펌프 소음이 함께 기록됐다. 가상 MES 정상 범위는 제조사 고장·작업 기준이 아니며 현재 run의 config_id·단위·quality와 대상 모델 기준을 별도로 확인한다.
- **근거 설명**: 서로 다른 합성 KB 사건 EV-0401, EV-0402에서 허용된 시험기동을 시작했으나 소음과 기포가 보여 정지 패턴이 반복됐다. 관측 결과와 보류 사유를 넘어 고장 원인을 확정하지 않았으며, 해당 원문은 안전 범위와 확인 항목의 배경만 제공한다. 가상 설비와 원문 모델의 동일성은 확인되지 않았다.
- **안전 근거**: 정지 원인 확인·인터록 작동 조건 해소·지정 승인자의 승인과 작업 제한 해제 확인이 선행된다. 정비는 정지·에너지 차단·잠금 후 권한 있는 담당자가 현장 작업표준으로 수행한다. 안전장치·인터록 우회 금지. 시험운전은 승인 범위에서만 수행하고 이상 시 정지한다. 해당 설치 모델과 원문 모델 동일성 미확인으로 구체 운전 설정·해제 절차는 현장 확인 대상.
- **출처**: SC-C-AR-0401 — AR-0401 | EV-0401 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-AR-0402 — AR-0402 | EV-0401 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-EV-0401 — EV-0401 | restart_attempts: AT-4001; SC-C-AR-0403 — AR-0403 | EV-0402 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-AR-0404 — AR-0404 | EV-0402 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-EV-0402 — EV-0402 | restart_attempts: AT-4004; M-C-005 — HY29-0022-UK.pdf | PDF 6·24쪽 / 인쇄 7·25쪽, 1.4 및 2.4.1
- **작성 노트**: 근거 사건: EV-0401, EV-0402; 재가동 유형: maintenance_restart; 프롬프트: `docs/data/knowledge_cards/kb/20260930-C/prompts/stage-b-cards.md@sha256:c2c7d293c36c6e511012f71064b58532aafe15742886e144302dd8e525800d2c`; 정책 연결: `docs/data/knowledge_cards/kb/20260930-C/policy_manifest.json@sha256:29afb0ecb89456db9291e8c32bf240ef43467c6cbc852342f43c7bf98b20d37d` · [카드별 보완 항목](policy_manifest.json); 독립 검토 근거: [1차 판정](review_round1.md) · [수정 후 재검토](review_round2.md) · [변경 전후](review_changes.json)
- **판정**:
- **판정 근거**:

## K-1212 · GR · T6 · ⚠ 안전 — 오일 교환 후에는 주입량 기록과 실제 유면을 대조하고 시험운전 관측을 남긴다

- **부품**: 오일 교환 후 감속기
- **노하우**: 오일 교환 완료나 주입량만으로 재가동 준비가 끝났다고 보지 않는다. 정비 오더의 오일 종류·주입 기록과 해당 모델 기준의 실제 유면 확인이 모두 있는지 대조한다. 유면 확인이 빠지면 전원을 넣기 전에 보완한다. 정지 원인 확인과 작업 제한 해제, 인터록 조건 해소, 지정 승인 후에만 현장 절차의 시험운전을 진행하고 소음·진동·누유 관측을 남긴다. 새 설비의 길들이기 시간이나 부하 단계는 이 합성 기록에서 도출하지 않는다. 근거 준비 확인 기록에는 실제 유면 측정값과 모델별 유면 기준이 없다. gr_oil_level의 가상 정상 범위 70–100 pct로 미측정 유면을 정상 판정하지 않고, 담당자가 실제 유면·단위·해당 모델 기준을 기록하도록 요청한다. 가상 MES 정상 범위는 제조사 고장·작업 기준이 아니며 현재 run의 config_id·단위·quality와 대상 모델 기준을 별도로 확인한다.
- **근거 설명**: 서로 다른 합성 KB 사건 EV-0403, EV-0404에서 주입량 기록만으로 복귀 준비를 진행하다 유면 확인란이 비어 있어 기동을 보류 패턴이 반복됐다. 관측 결과와 보류 사유를 넘어 고장 원인을 확정하지 않았으며, 해당 원문은 안전 범위와 확인 항목의 배경만 제공한다. 가상 설비와 원문 모델의 동일성은 확인되지 않았다.
- **안전 근거**: 정지 원인 확인·인터록 작동 조건 해소·지정 승인자의 승인과 작업 제한 해제 확인이 선행된다. 정비는 정지·에너지 차단·잠금 후 권한 있는 담당자가 현장 작업표준으로 수행한다. 안전장치·인터록 우회 금지. 시험운전은 승인 범위에서만 수행하고 이상 시 정지한다. 해당 설치 모델과 원문 모델 동일성 미확인으로 구체 운전 설정·해제 절차는 현장 확인 대상.
- **출처**: SC-C-AR-0405 — AR-0405 | EV-0403 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-AR-0406 — AR-0406 | EV-0403 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-EV-0403 — EV-0403 | restart_attempts: AT-4007; SC-C-AR-0407 — AR-0407 | EV-0404 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-AR-0408 — AR-0408 | EV-0404 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-EV-0404 — EV-0404 | restart_attempts: AT-4010; M-C-003 — 26867443.pdf | PDF/인쇄 p.39~40 및 p.42~43 / §7.1 Startup 및 §8.3 Checking the oil level / Changing the oil
- **작성 노트**: 근거 사건: EV-0403, EV-0404; 재가동 유형: maintenance_restart; 프롬프트: `docs/data/knowledge_cards/kb/20260930-C/prompts/stage-b-cards.md@sha256:c2c7d293c36c6e511012f71064b58532aafe15742886e144302dd8e525800d2c`; 정책 연결: `docs/data/knowledge_cards/kb/20260930-C/policy_manifest.json@sha256:29afb0ecb89456db9291e8c32bf240ef43467c6cbc852342f43c7bf98b20d37d` · [카드별 보완 항목](policy_manifest.json); 독립 검토 근거: [1차 판정](review_round1.md) · [수정 후 재검토](review_round2.md) · [변경 전후](review_changes.json)
- **판정**:
- **판정 근거**:

## K-1213 · CV · T6 · ⚠ 안전 — 벨트 정비 후 장력 420 kPa가 정상 범위여도 시험운전의 편주를 확인한다

- **부품**: 벨트 정비 후 컨베이어
- **노하우**: 벨트 정비 뒤 cv_belt_tension이 380–460 kPa(가상 MES 정상 범위)에 있어도 정렬과 주행까지 확인된 것은 아니다. 방호 복구·도구 제거와 재가동 선행조건을 확인한 뒤 승인된 시험운전에서 허용된 관찰 위치로 편주를 본다. 편주가 나타나면 생산 복귀를 보류하고 정비 담당에게 관측 시각과 방향을 전달한다. 장력 표시만으로 조정 완료를 판단하지 않는다. 운전 중 손대거나 조정하는 방법은 이 카드에 포함하지 않는다. 근거 시험운전의 cv_belt_tension은 420 kPa(가상 정상 380–460 kPa 이내)였으나 벨트 가장자리 편주가 관찰됐다. 편주량의 수치와 허용 한계는 기록에 없어 정상 장력으로 편주를 배제하지 않는다. 가상 MES 정상 범위는 제조사 고장·작업 기준이 아니며 현재 run의 config_id·단위·quality와 대상 모델 기준을 별도로 확인한다.
- **근거 설명**: 서로 다른 합성 KB 사건 EV-0405, EV-0406에서 cv_belt_tension 420 kPa(가상 정상 범위 380–460 kPa)인 상태에서 시험운전했으나 벨트가 한쪽으로 치우쳐 중단 패턴이 반복됐다. 관측 결과와 보류 사유를 넘어 고장 원인을 확정하지 않았으며, 해당 원문은 안전 범위와 확인 항목의 배경만 제공한다. 가상 설비와 원문 모델의 동일성은 확인되지 않았다.
- **안전 근거**: 정지 원인 확인·인터록 작동 조건 해소·지정 승인자의 승인과 작업 제한 해제 확인이 선행된다. 정비는 정지·에너지 차단·잠금 후 권한 있는 담당자가 현장 작업표준으로 수행한다. 안전장치·인터록 우회 금지. 시험운전은 승인 범위에서만 수행하고 이상 시 정지한다. 해당 설치 모델과 원문 모델 동일성 미확인으로 구체 운전 설정·해제 절차는 현장 확인 대상.
- **출처**: SC-C-AR-0409 — AR-0409 | EV-0405 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-AR-0410 — AR-0410 | EV-0405 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-EV-0405 — EV-0405 | restart_attempts: AT-4013; SC-C-AR-0411 — AR-0411 | EV-0406 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-AR-0412 — AR-0412 | EV-0406 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-EV-0406 — EV-0406 | restart_attempts: AT-4016; M-C-007 — conveyor-manual-0323-en.pdf | PDF 62~63쪽 / 인쇄 58~59쪽, 8.3 및 8.5
- **작성 노트**: 근거 사건: EV-0405, EV-0406; 재가동 유형: maintenance_restart; 프롬프트: `docs/data/knowledge_cards/kb/20260930-C/prompts/stage-b-cards.md@sha256:c2c7d293c36c6e511012f71064b58532aafe15742886e144302dd8e525800d2c`; 정책 연결: `docs/data/knowledge_cards/kb/20260930-C/policy_manifest.json@sha256:29afb0ecb89456db9291e8c32bf240ef43467c6cbc852342f43c7bf98b20d37d` · [카드별 보완 항목](policy_manifest.json); 독립 검토 근거: [1차 판정](review_round1.md) · [수정 후 재검토](review_round2.md) · [변경 전후](review_changes.json)
- **판정**:
- **판정 근거**:

## K-1214 · RT · T6 · ⚠ 안전 — RT 정비 완료와 재가동 승인을 구분하고 방호·작업구역 복구를 확인한다

- **부품**: 반송부 정비 복귀
- **노하우**: RT 정비 완료 오더와 운전 복귀 승인을 구분한다. 재가동 준비 시 방호장치 복구, 작업구역의 도구·불필요한 자재 철수, 걸림 여부와 지정 승인자의 기록을 대조한다. 확인이 빠진 항목은 미확인 상태로 남기고 기동을 보류한다. 완료 오더나 rt_clamp_press 95–115 bar(가상 정상 범위) 표시로 그 확인을 대신하지 않는다. 실제 RT와 원문 롤러 컨베이어의 구조가 같다고 확인되지 않아 잠금 해제 순서·승강 조작·클램프 조정은 제시하지 않는다. 근거 사건의 rt_clamp_press는 104 bar(가상 정상 95–115 bar 이내), rt_speed는 0 m_min, rt_motor_current는 0 A였다. 정지 중 0은 준비 상태의 관측이며 운전 고장 판정으로 바꾸지 않는다. 도구 철수·방호 복구 확인란 누락은 별도의 미확인 상태로 남긴다. 가상 MES 정상 범위는 제조사 고장·작업 기준이 아니며 현재 run의 config_id·단위·quality와 대상 모델 기준을 별도로 확인한다.
- **근거 설명**: 서로 다른 합성 KB 사건 EV-0407, EV-0408에서 정비 완료만 보고 복귀 준비를 진행했으나 작업구역 정리 확인이 없어 기동 보류 패턴이 반복됐다. 관측 결과와 보류 사유를 넘어 고장 원인을 확정하지 않았으며, 해당 원문은 안전 범위와 확인 항목의 배경만 제공한다. 가상 설비와 원문 모델의 동일성은 확인되지 않았다.
- **안전 근거**: 정지 원인 확인·인터록 작동 조건 해소·지정 승인자의 승인과 작업 제한 해제 확인이 선행된다. 정비는 정지·에너지 차단·잠금 후 권한 있는 담당자가 현장 작업표준으로 수행한다. 안전장치·인터록 우회 금지. 시험운전은 승인 범위에서만 수행하고 이상 시 정지한다. 해당 설치 모델과 원문 모델 동일성 미확인으로 구체 운전 설정·해제 절차는 현장 확인 대상.
- **출처**: SC-C-AR-0413 — AR-0413 | EV-0407 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-AR-0414 — AR-0414 | EV-0407 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-EV-0407 — EV-0407 | restart_attempts: AT-4019; SC-C-AR-0415 — AR-0415 | EV-0408 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-AR-0416 — AR-0416 | EV-0408 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-EV-0408 — EV-0408 | restart_attempts: AT-4022; M-C-002 — 1110_Roller_conveyor_EN_TNr_1131919_V1.0.pdf | PDF/인쇄 35~36쪽, Initial startup / Before every operation start
- **작성 노트**: 근거 사건: EV-0407, EV-0408; 재가동 유형: maintenance_restart; 프롬프트: `docs/data/knowledge_cards/kb/20260930-C/prompts/stage-b-cards.md@sha256:c2c7d293c36c6e511012f71064b58532aafe15742886e144302dd8e525800d2c`; 정책 연결: `docs/data/knowledge_cards/kb/20260930-C/policy_manifest.json@sha256:29afb0ecb89456db9291e8c32bf240ef43467c6cbc852342f43c7bf98b20d37d` · [카드별 보완 항목](policy_manifest.json); 독립 검토 근거: [1차 판정](review_round1.md) · [수정 후 재검토](review_round2.md) · [변경 전후](review_changes.json)
- **판정**:
- **판정 근거**:

## K-1215 · CV · T6 · ⚠ 안전 — CV 비상정지 표시가 풀려도 걸림 제거·기능시험 기록이 없으면 복귀를 보류한다

- **부품**: 비상정지 후 컨베이어
- **노하우**: 끼임으로 비상정지한 CV에서는 표시가 해제됐다는 사실과 고장이 제거됐다는 사실을 나눠 확인한다. 걸림 제거와 안전장치 확인, 기능시험 승인 기록이 없으면 재가동 준비를 중단하고 정비 담당에게 확인을 요청한다. 정지 원인 확인·인터록 조건 해소·지정 승인 후 허가된 기능시험을 거쳐 운전 담당에게 넘긴다. 정지 표시 해제나 cv_belt_tension 380–460 kPa·cv_queue_len 0–70 pct(가상 정상 범위) 표시만으로 복귀시키지 않고 안전장치를 우회하지 않는다. 근거 사건의 cv_belt_tension은 415 kPa(가상 정상 380–460 kPa 이내), cv_queue_len은 65 pct(가상 정상 0–70 pct 이내), cv_speed는 0 m_min이었다. 정지 중 속도 0이나 이 두 신호의 정상 범위 충족으로 걸림 제거·기능시험 승인 누락을 해소하지 않는다. 가상 MES 정상 범위는 제조사 고장·작업 기준이 아니며 현재 run의 config_id·단위·quality와 대상 모델 기준을 별도로 확인한다.
- **근거 설명**: 서로 다른 합성 KB 사건 EV-0409, EV-0410에서 비상정지 표시 해제만으로 복귀 준비를 진행하다 걸림 제거 확인이 없어 기동 보류 패턴이 반복됐다. 관측 결과와 보류 사유를 넘어 고장 원인을 확정하지 않았으며, 해당 원문은 안전 범위와 확인 항목의 배경만 제공한다. 가상 설비와 원문 모델의 동일성은 확인되지 않았다.
- **안전 근거**: 정지 원인 확인·인터록 작동 조건 해소·지정 승인자의 승인과 작업 제한 해제 확인이 선행된다. 정비는 정지·에너지 차단·잠금 후 권한 있는 담당자가 현장 작업표준으로 수행한다. 안전장치·인터록 우회 금지. 시험운전은 승인 범위에서만 수행하고 이상 시 정지한다. 해당 설치 모델과 원문 모델 동일성 미확인으로 구체 운전 설정·해제 절차는 현장 확인 대상.
- **출처**: SC-C-AR-0417 — AR-0417 | EV-0409 [abnormal_stop_restart] 관측·보류 시도·다음 확인; SC-C-AR-0418 — AR-0418 | EV-0409 [abnormal_stop_restart] 관측·보류 시도·다음 확인; SC-C-EV-0409 — EV-0409 | restart_attempts: AT-4025; SC-C-AR-0419 — AR-0419 | EV-0410 [abnormal_stop_restart] 관측·보류 시도·다음 확인; SC-C-AR-0420 — AR-0420 | EV-0410 [abnormal_stop_restart] 관측·보류 시도·다음 확인; SC-C-EV-0410 — EV-0410 | restart_attempts: AT-4028; M-C-007 — conveyor-manual-0323-en.pdf | PDF 69쪽 / 인쇄 65쪽, 10.1 Procedure in Case of Operational Malfunctions
- **작성 노트**: 근거 사건: EV-0409, EV-0410; 재가동 유형: abnormal_stop_restart; 프롬프트: `docs/data/knowledge_cards/kb/20260930-C/prompts/stage-b-cards.md@sha256:c2c7d293c36c6e511012f71064b58532aafe15742886e144302dd8e525800d2c`; 정책 연결: `docs/data/knowledge_cards/kb/20260930-C/policy_manifest.json@sha256:29afb0ecb89456db9291e8c32bf240ef43467c6cbc852342f43c7bf98b20d37d` · [카드별 보완 항목](policy_manifest.json); 독립 검토 근거: [1차 판정](review_round1.md) · [수정 후 재검토](review_round2.md) · [변경 전후](review_changes.json)
- **판정**:
- **판정 근거**:

## K-1216 · GR · T6 · ⚠ 안전 — 정지 전 75 degC에서 냉각 후 49 degC로 변해도 원인 확인과 재가동 관측을 생략하지 않는다

- **부품**: 과열 정지 후 감속기
- **노하우**: 과열로 멈춘 GR은 냉각 후 gr_brg_temp 표시가 30–62 degC(가상 정상 범위)로 복귀해도 정지 원인이 확인됐다고 간주하지 않는다. 정비 담당에게 유면·오일 교환 이력과 해당 설비의 냉각 구성 확인 결과를 요청하고 원인 확인·작업 제한 해제·인터록 조건 해소·지정 승인 후 현장 절차로 복귀한다. 승인된 재가동 관측에서 온도·진동·소음의 재상승이 보이면 정지해 담당자에게 알린다. 원문 감속기 운전온도와 가상 MES 베어링온도를 같은 임계값으로 쓰지 않는다. 근거 기록의 gr_brg_temp는 정지 전 75 degC(가상 정상 30–62 degC의 상한 초과)에서 냉각 후 49 degC(같은 범위 이내)로 바뀌었다. 이 수치 변화와 정지 원인 확인 서명 누락을 함께 남긴다. 가상 MES 정상 범위는 제조사 고장·작업 기준이 아니며 현재 run의 config_id·단위·quality와 대상 모델 기준을 별도로 확인한다.
- **근거 설명**: 서로 다른 합성 KB 사건 EV-0411, EV-0412에서 온도 하강만 보고 복귀 준비를 진행하다 원인 확인 기록이 없어 기동 보류 패턴이 반복됐다. 관측 결과와 보류 사유를 넘어 고장 원인을 확정하지 않았으며, 해당 원문은 안전 범위와 확인 항목의 배경만 제공한다. 가상 설비와 원문 모델의 동일성은 확인되지 않았다.
- **안전 근거**: 정지 원인 확인·인터록 작동 조건 해소·지정 승인자의 승인과 작업 제한 해제 확인이 선행된다. 정비는 정지·에너지 차단·잠금 후 권한 있는 담당자가 현장 작업표준으로 수행한다. 안전장치·인터록 우회 금지. 시험운전은 승인 범위에서만 수행하고 이상 시 정지한다. 해당 설치 모델과 원문 모델 동일성 미확인으로 구체 운전 설정·해제 절차는 현장 확인 대상.
- **출처**: SC-C-AR-0421 — AR-0421 | EV-0411 [abnormal_stop_restart] 관측·보류 시도·다음 확인; SC-C-AR-0422 — AR-0422 | EV-0411 [abnormal_stop_restart] 관측·보류 시도·다음 확인; SC-C-EV-0411 — EV-0411 | restart_attempts: AT-4031; SC-C-AR-0423 — AR-0423 | EV-0412 [abnormal_stop_restart] 관측·보류 시도·다음 확인; SC-C-AR-0424 — AR-0424 | EV-0412 [abnormal_stop_restart] 관측·보류 시도·다음 확인; SC-C-EV-0412 — EV-0412 | restart_attempts: AT-4034; M-C-003 — 26867443.pdf | PDF/인쇄 5·45쪽, Safety notes 및 9.1 Operating temperature too high / Bearing point temperatures too high
- **작성 노트**: 근거 사건: EV-0411, EV-0412; 재가동 유형: abnormal_stop_restart; 프롬프트: `docs/data/knowledge_cards/kb/20260930-C/prompts/stage-b-cards.md@sha256:c2c7d293c36c6e511012f71064b58532aafe15742886e144302dd8e525800d2c`; 정책 연결: `docs/data/knowledge_cards/kb/20260930-C/policy_manifest.json@sha256:29afb0ecb89456db9291e8c32bf240ef43467c6cbc852342f43c7bf98b20d37d` · [카드별 보완 항목](policy_manifest.json); 독립 검토 근거: [1차 판정](review_round1.md) · [수정 후 재검토](review_round2.md) · [변경 전후](review_changes.json)
- **판정**:
- **판정 근거**:

## K-1217 · RT · T6 · ⚠ 안전 — RT 인터록 정지 후에는 해제 표시와 작동 조건 해소·승인을 각각 확인한다

- **부품**: 인터록 정지 후 반송부
- **노하우**: 인터록으로 멈춘 RT는 해제 표시만 보고 기동하지 않는다. 작동 조건인 반송부 걸림이 해소됐는지 담당 확인 기록을 받고 안전장치·작업구역과 지정 승인자의 재가동 승인을 따로 대조한다. 미확인 항목이 있으면 기동을 보류하며 인터록을 강제 해제하거나 우회하지 않는다. 매뉴얼이 특정 RT 회로를 설명한다고 간주하지 않으며 승강부 구조와 해제 회로는 현장 작업표준에서 확인한다. 근거 사건의 rt_clamp_press는 106 bar(가상 정상 95–115 bar 이내), rt_speed는 0 m_min, rt_motor_current는 0 A였다. 정지 중 0과 정상 범위 압력은 인터록 작동 조건 해소나 재가동 승인의 근거가 아니다. 인터록 해제 표시는 숫자 신호로 기록되지 않았으므로 임의로 0/1을 부여하지 않는다. 가상 MES 정상 범위는 제조사 고장·작업 기준이 아니며 현재 run의 config_id·단위·quality와 대상 모델 기준을 별도로 확인한다.
- **근거 설명**: 서로 다른 합성 KB 사건 EV-0413, EV-0414에서 인터록 해제 표시만 보고 복귀 준비를 진행하다 조건 해소 확인이 없어 기동 보류 패턴이 반복됐다. 관측 결과와 보류 사유를 넘어 고장 원인을 확정하지 않았으며, 해당 원문은 안전 범위와 확인 항목의 배경만 제공한다. 가상 설비와 원문 모델의 동일성은 확인되지 않았다.
- **안전 근거**: 정지 원인 확인·인터록 작동 조건 해소·지정 승인자의 승인과 작업 제한 해제 확인이 선행된다. 정비는 정지·에너지 차단·잠금 후 권한 있는 담당자가 현장 작업표준으로 수행한다. 안전장치·인터록 우회 금지. 시험운전은 승인 범위에서만 수행하고 이상 시 정지한다. 해당 설치 모델과 원문 모델 동일성 미확인으로 구체 운전 설정·해제 절차는 현장 확인 대상.
- **출처**: SC-C-AR-0425 — AR-0425 | EV-0413 [abnormal_stop_restart] 관측·보류 시도·다음 확인; SC-C-AR-0426 — AR-0426 | EV-0413 [abnormal_stop_restart] 관측·보류 시도·다음 확인; SC-C-EV-0413 — EV-0413 | restart_attempts: AT-4037; SC-C-AR-0427 — AR-0427 | EV-0414 [abnormal_stop_restart] 관측·보류 시도·다음 확인; SC-C-AR-0428 — AR-0428 | EV-0414 [abnormal_stop_restart] 관측·보류 시도·다음 확인; SC-C-EV-0414 — EV-0414 | restart_attempts: AT-4040; M-C-002 — 1110_Roller_conveyor_EN_TNr_1131919_V1.0.pdf | PDF/인쇄 36쪽, Before every operation start / Procedure in case of accident or fault
- **작성 노트**: 근거 사건: EV-0413, EV-0414; 재가동 유형: abnormal_stop_restart; 프롬프트: `docs/data/knowledge_cards/kb/20260930-C/prompts/stage-b-cards.md@sha256:c2c7d293c36c6e511012f71064b58532aafe15742886e144302dd8e525800d2c`; 정책 연결: `docs/data/knowledge_cards/kb/20260930-C/policy_manifest.json@sha256:29afb0ecb89456db9291e8c32bf240ef43467c6cbc852342f43c7bf98b20d37d` · [카드별 보완 항목](policy_manifest.json); 독립 검토 근거: [1차 판정](review_round1.md) · [수정 후 재검토](review_round2.md) · [변경 전후](review_changes.json)
- **판정**:
- **판정 근거**:

## K-1218 · HPU · T6 · ⚠ 안전 — HPU 유온 < 35 degC 기동은 유온만으로 복귀를 정하지 않고 오일 적합성·흡입 조건을 확인한다

- **부품**: 정상정지 후 저온 기동
- **노하우**: 야간 정상정지 뒤 hpu_oil_temp < 35 degC(가상 정상 범위 35–58 degC)에서 hpu_pressure < 145 bar(정상 145–165 bar)·hpu_flow < 38 L_min(정상 38–46 L_min)와 소음이 나타나면 반복 기동으로 각 가상 정상 범위에 진입시키려 하지 않는다. 유온 관측과 소음 발생 시각을 함께 적고 정비 담당에게 사용 오일의 온도별 점도 적합성 및 흡입 조건 확인을 요청한다. 유온만으로 점도를 계산하거나 제조사의 점도 한계를 넘었다고 단정하지 않는다. 예열 방법·속도·압력은 확인된 해당 설비 저온기동 절차와 승인에 따른다. 근거 시험기동의 hpu_oil_temp는 28 degC(가상 정상 35–58 degC의 하한 미만), hpu_pressure는 133 bar(가상 정상 145–165 bar의 하한 미만), hpu_flow는 32 L_min(가상 정상 38–46 L_min의 하한 미만)이었고 펌프 소음이 관찰됐다. 가상 MES 정상 범위는 제조사 고장·작업 기준이 아니며 현재 run의 config_id·단위·quality와 대상 모델 기준을 별도로 확인한다.
- **근거 설명**: 서로 다른 합성 KB 사건 EV-0401, EV-0415에서 야간 정상정지 뒤 승인된 시험기동을 했으나 유량 부족과 소음으로 정지 패턴이 반복됐다. 관측 결과와 보류 사유를 넘어 고장 원인을 확정하지 않았으며, 해당 원문은 안전 범위와 확인 항목의 배경만 제공한다. 가상 설비와 원문 모델의 동일성은 확인되지 않았다.
- **안전 근거**: 정지 원인 확인·인터록 작동 조건 해소·지정 승인자의 승인과 작업 제한 해제 확인이 선행된다. 정비는 정지·에너지 차단·잠금 후 권한 있는 담당자가 현장 작업표준으로 수행한다. 안전장치·인터록 우회 금지. 시험운전은 승인 범위에서만 수행하고 이상 시 정지한다. 해당 설치 모델과 원문 모델 동일성 미확인으로 구체 운전 설정·해제 절차는 현장 확인 대상.
- **출처**: SC-C-AR-0401 — AR-0401 | EV-0401 [normal_stop_restart] 관측·보류 시도·다음 확인; SC-C-AR-0402 — AR-0402 | EV-0401 [normal_stop_restart] 관측·보류 시도·다음 확인; SC-C-EV-0401 — EV-0401 | restart_attempts: AT-4002; SC-C-AR-0429 — AR-0429 | EV-0415 [normal_stop_restart] 관측·보류 시도·다음 확인; SC-C-AR-0430 — AR-0430 | EV-0415 [normal_stop_restart] 관측·보류 시도·다음 확인; SC-C-EV-0415 — EV-0415 | restart_attempts: AT-4043; M-C-005 — HY29-0022-UK.pdf | PDF 6·37~38·49쪽 / 인쇄 7·38~39·50쪽, 1.4 및 viscosity failures / no flow no pressure
- **작성 노트**: 근거 사건: EV-0401, EV-0415; 재가동 유형: normal_stop_restart; 프롬프트: `docs/data/knowledge_cards/kb/20260930-C/prompts/stage-b-cards.md@sha256:c2c7d293c36c6e511012f71064b58532aafe15742886e144302dd8e525800d2c`; 정책 연결: `docs/data/knowledge_cards/kb/20260930-C/policy_manifest.json@sha256:29afb0ecb89456db9291e8c32bf240ef43467c6cbc852342f43c7bf98b20d37d` · [카드별 보완 항목](policy_manifest.json); 독립 검토 근거: [1차 판정](review_round1.md) · [수정 후 재검토](review_round2.md) · [변경 전후](review_changes.json)
- **판정**:
- **판정 근거**:

## K-1219 · GR · T6 · ⚠ 안전 — 30일 정상정지 뒤에는 이전 운전 성공과 별도로 유면·윤활 준비를 다시 확인한다

- **부품**: 장기 정상정지 후 감속기
- **노하우**: 계획된 장기 정상정지 뒤에는 정지 전 정상 운전 기록을 현재 재가동 준비의 확인으로 대신하지 않는다. 현재 유면과 윤활 준비, 방호·감시장치 확인을 담당자에게 요청하고 현장 장기정지 복귀 절차를 확인한다. 미확인 상태에서는 기동을 보류한다. 기록에 없는 보관처리나 부식방지 조치는 있었다고 가정하지 않는다. 매뉴얼의 장기 보관 조건·최초 길들이기 시간·운전 주기는 30일 정상정지 사건에 그대로 이식하지 않는다. 근거 기록은 30일 전 시험운전을 정상으로 기재했지만 당시 측정값·단위·판정 기준과 현재 실제 유면 수치는 제시하지 않는다. gr_oil_level의 가상 정상 범위 70–100 pct를 과거 정상이라는 문구에 대입하지 않고 현재 유면과 해당 모델 기준을 다시 기록한다. 가상 MES 정상 범위는 제조사 고장·작업 기준이 아니며 현재 run의 config_id·단위·quality와 대상 모델 기준을 별도로 확인한다.
- **근거 설명**: 서로 다른 합성 KB 사건 EV-0403, EV-0404에서 이전 운전이 정상이라는 이유로 준비를 진행하다 현재 유면 확인 기록이 없어 기동 보류 패턴이 반복됐다. 관측 결과와 보류 사유를 넘어 고장 원인을 확정하지 않았으며, 해당 원문은 안전 범위와 확인 항목의 배경만 제공한다. 가상 설비와 원문 모델의 동일성은 확인되지 않았다.
- **안전 근거**: 정지 원인 확인·인터록 작동 조건 해소·지정 승인자의 승인과 작업 제한 해제 확인이 선행된다. 정비는 정지·에너지 차단·잠금 후 권한 있는 담당자가 현장 작업표준으로 수행한다. 안전장치·인터록 우회 금지. 시험운전은 승인 범위에서만 수행하고 이상 시 정지한다. 해당 설치 모델과 원문 모델 동일성 미확인으로 구체 운전 설정·해제 절차는 현장 확인 대상.
- **출처**: SC-C-AR-0405 — AR-0405 | EV-0403 [normal_stop_restart] 관측·보류 시도·다음 확인; SC-C-AR-0406 — AR-0406 | EV-0403 [normal_stop_restart] 관측·보류 시도·다음 확인; SC-C-EV-0403 — EV-0403 | restart_attempts: AT-4008; SC-C-AR-0407 — AR-0407 | EV-0404 [normal_stop_restart] 관측·보류 시도·다음 확인; SC-C-AR-0408 — AR-0408 | EV-0404 [normal_stop_restart] 관측·보류 시도·다음 확인; SC-C-EV-0404 — EV-0404 | restart_attempts: AT-4011; M-C-003 — 26867443.pdf | PDF/인쇄 39~40쪽, 7.1 Before startup 및 7.2 Taking out of operation
- **작성 노트**: 근거 사건: EV-0403, EV-0404; 재가동 유형: normal_stop_restart; 프롬프트: `docs/data/knowledge_cards/kb/20260930-C/prompts/stage-b-cards.md@sha256:c2c7d293c36c6e511012f71064b58532aafe15742886e144302dd8e525800d2c`; 정책 연결: `docs/data/knowledge_cards/kb/20260930-C/policy_manifest.json@sha256:29afb0ecb89456db9291e8c32bf240ef43467c6cbc852342f43c7bf98b20d37d` · [카드별 보완 항목](policy_manifest.json); 독립 검토 근거: [1차 판정](review_round1.md) · [수정 후 재검토](review_round2.md) · [변경 전후](review_changes.json)
- **판정**:
- **판정 근거**:
