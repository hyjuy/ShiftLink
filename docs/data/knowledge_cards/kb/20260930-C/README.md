# KB-20260930-C — T2 10장 · T6 9장

2026-09-30 생성. split=kb, confidence=0.0이며 실제 상태는 cards.json과 아래 검수표에서 확인한다.
생성자 2명과 별도 독립 검토자가 출처 대조, 판정, 수정, 재검토를 수행했다.
현재 편입 상태와 승인 범위는 [승격 기록](l1-promotion-20261001.json)과 검수표에서 확인한다.

## 재현과 근거

- [plan.py](plan.py) → [plan.json](plan.json): 시드 20260930, ID K-1201~1219. 슬롯만 재현 가능하며 생성 본문은 고정되지 않는다.
- [prompts/index.json](prompts/index.json): 원본 생성 지시와 SHA256. T2 및 T6 단계 A/B를 구분한다.
- T6 원장 20건과 기록 40건은 최초 KB15/dev5 배정의 감사 기록이다. 현재 독립 평가용 dev 입력은 0건이며 중복 dev5/기록10은 `records/quarantined_dev_*.json`에 보관한다.
- 카드 추출 입력은 `records/kb_events.json`, `records/kb_artifacts.json` 관측 투영이다. 현재 split은 역사적 배정이며 계보 검토 전 활성 정책 배정으로 사용하지 않는다.
- [out/](out/): 배치 카드 원본. [merge.py](merge.py)로 [cards.json](cards.json)을 생성하고 [verify.py](verify.py)로 검사한다.
- [1차 판정](review_round1.md) → [변경 이력](review_changes.json) → [수정 후 재검토](review_round2.md). 생성 프롬프트·해시는 보존했다.
- [review.md](review.md): 지정 통합 검수표와 동기화한 사람 판정. [validation.md](validation.md): 이전 검증과 환경.
- [프로젝트 충돌 검증](integration-review.md): 출처 등록·분할 계보·dev 중복 해결 전 KB 통합 보류.
- [상위 계약 반영](policy-alignment.md): 기준 출처 52개 등록, 계보 7개 후보, dev 격리, 승인·편입 게이트. 출처 승인과 계보 확정은 미완료이다.

## 가이드 예시에서 변경한 슬롯

원문에 없는 차압·유온 분기, RT 클램프 판단, 설치위치가 다른 RT 전류·승강지연 조합,
GR 전류 진단은 사용하지 않았다. HPU 표시기 확인·교체 표시/이력 판단, RT 반송·과전류,
GR 유면·온도 점검의 근거 있는 분기로 대체했다. 상세 사유는 `out/*_notes.md`에 있다.

## 한계와 남은 절차

가상 MES 상태는 검색 후보를 고르는 조건이다. 실제 표시기·부하·소음 등은 수동 확인이 필요하다.
원문 설비 모델과 가상 설치 구조의 일치는 미확정이다. T6는 합성 기록이며 동일 템플릿 반복을 실제 현장 경험으로 주장하지 않는다.
독립 검토자의 원장 정답·dev 접근 편차는 1차/2차 보고에 기록했다. 블라인드 성능평가가 아니다.
2026-10-01 사용자 요청과 human-review-checklist-20260930의 accepted 판정으로 19장을 accepted/L1로 승격하고 통합 KB에 편입했다.
출처 승인·계보·배정·독립 근거 게이트는 보완 대기로 유지한다. `verify.py --kb-ready`는 해당 보류를 계속 보고한다.
요청에 따른 편입은 승격 기록에 고정한 카드 본문과 해당 C 카드 검수 구간의 해시에 한정하며, 이후 변경이나 새로운 정책 문제에 자동 적용하지 않는다. 다른 배치 검수 변경은 C 승격에 영향을 주지 않는다.

## 카드 추적표

| 카드 | 설비 | 유형 | 제목 | 출처 |
|---|---|---|---|---|
| K-1201 | HPU | T2 | 필터 차압 > 1.2 bar에서 설치된 막힘 표시기 종류에 따라 확인 위치를 나눈다 | M-C-006 — MAN-C-012.pdf | PDF p.6 / 인쇄 p.7 / §1.10 Oil filters control |
| K-1202 | HPU | T2 | 필터 차압 > 1.2 bar 후 실제 교체 표시가 있으면 정기 교체 시점과 별도로 처리한다 | M-C-006 — MAN-C-012.pdf | PDF p.6 / 인쇄 p.7 / §1.10 Oil filters control |
| K-1203 | HPU | T2 | 압력 이상 여부에 따라 릴리프 설정과 유량 확인 경로를 나눈다 | M-C-001 — 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf | PDF p.17 / 인쇄 p.17 / Algo A.1 System test for gear and vane pumps, 출구 압력 있음 분기 |
| K-1204 | CV | T2 | 벨트 장력 < 380 kPa에서 미끄럼의 실제 느슨함 여부에 따라 조치를 나눈다 | M-C-004 — Convey-All-TroubleshootingGuide.pdf | PDF p.1 / General Conveyor / Conveyor belt doesn't turn or is slipping; M-C-007 — conveyor-manual-0323-en.pdf | PDF p.11 / 인쇄 p.7 / §3.2.2 Hazards - Mechanical Energy |
| K-1205 | CV | T2 | 벨트 장력 380–460 kPa(가상 정상 범위)인데 이송량이 줄면 벨트와 롤러 표면 상태를 나눈다 | M-C-004 — Convey-All-TroubleshootingGuide.pdf | PDF p.2 / General Conveyor / Low conveying capacity; M-C-007 — conveyor-manual-0323-en.pdf | PDF p.11 / 인쇄 p.7 / §3.2.2 Hazards - Mechanical Energy |
| K-1206 | CV | T2 | 벨트 속도 < 10 m_min·대기열 > 70 pct에서는 실제 막힘과 느린 벨트를 구분한다 | M-C-007 — conveyor-manual-0323-en.pdf | PDF p.11 / 인쇄 p.7 / §3.2.2 Hazards - Mechanical Energy; M-C-007 — conveyor-manual-0323-en.pdf | PDF p.70 / 인쇄 p.66 / §10.3 Frequently Asked Questions (FAQ) |
| K-1207 | RT | T2 | 반송 속도 < 20 m_min에서는 롤러 미기동과 물품 미이송을 구분한다 | M-C-002 — 1110_Roller_conveyor_EN_TNr_1131919_V1.0.pdf | PDF p.51 / 인쇄 p.51 / Troubleshooting: Transport process cannot be started; Conveying goods are not being transported |
| K-1208 | RT | T2 | 전류 > 16 A(가상 정상 범위 8–16 A)에서는 실제 과전류 차단과 이송중량 초과를 먼저 구분한다 | M-C-002 — 1110_Roller_conveyor_EN_TNr_1131919_V1.0.pdf | PDF p.52 / 인쇄 p.52 / Troubleshooting: Motor circuit breaker is triggered due to excessive current consumption; M-C-002 — 1110_Roller_conveyor_EN_TNr_1131919_V1.0.pdf | PDF p.51 / 인쇄 p.51 / Troubleshooting: In case of a fault (전원 차단·우발 기동 방지·전기 담당 자격) |
| K-1209 | GR | T2 | 진동 RMS > 2.8 mm_s(가상 정상 범위 0.5–2.8 mm_s)에서 베어링 온도 동반 여부에 따라 추가 확인을 나눈다 | M-C-003 — 26867443.pdf | PDF p.5 / Safety notes / Startup/operation; M-C-003 — 26867443.pdf | PDF p.45 / 인쇄 p.45 / §9.1 Gear unit malfunctions |
| K-1210 | GR | T2 | 베어링 온도 > 62 degC(가상 정상 범위 30–62 degC)에서는 확인된 유면과 오일 이력에 따라 조치를 나눈다 | M-C-003 — 26867443.pdf | PDF p.45 / 인쇄 p.45 / §9.1 Gear unit malfunctions; M-C-003 — 26867443.pdf | PDF p.42 / 인쇄 p.42 / §8.3 Inspection and maintenance of the gear unit / Checking the oil level |
| K-1211 | HPU | T6 | 필터·오일 정비 후 압력 152 bar가 정상 범위여도 유량 34 L_min·기포·소음을 함께 확인한다 | SC-C-AR-0401 — AR-0401 | EV-0401 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-AR-0402 — AR-0402 | EV-0401 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-EV-0401 — EV-0401 | restart_attempts: AT-4001; SC-C-AR-0403 — AR-0403 | EV-0402 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-AR-0404 — AR-0404 | EV-0402 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-EV-0402 — EV-0402 | restart_attempts: AT-4004; M-C-005 — HY29-0022-UK.pdf | PDF 6·24쪽 / 인쇄 7·25쪽, 1.4 및 2.4.1 |
| K-1212 | GR | T6 | 오일 교환 후에는 주입량 기록과 실제 유면을 대조하고 시험운전 관측을 남긴다 | SC-C-AR-0405 — AR-0405 | EV-0403 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-AR-0406 — AR-0406 | EV-0403 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-EV-0403 — EV-0403 | restart_attempts: AT-4007; SC-C-AR-0407 — AR-0407 | EV-0404 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-AR-0408 — AR-0408 | EV-0404 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-EV-0404 — EV-0404 | restart_attempts: AT-4010; M-C-003 — 26867443.pdf | PDF/인쇄 p.39~40 및 p.42~43 / §7.1 Startup 및 §8.3 Checking the oil level / Changing the oil |
| K-1213 | CV | T6 | 벨트 정비 후 장력 420 kPa가 정상 범위여도 시험운전의 편주를 확인한다 | SC-C-AR-0409 — AR-0409 | EV-0405 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-AR-0410 — AR-0410 | EV-0405 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-EV-0405 — EV-0405 | restart_attempts: AT-4013; SC-C-AR-0411 — AR-0411 | EV-0406 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-AR-0412 — AR-0412 | EV-0406 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-EV-0406 — EV-0406 | restart_attempts: AT-4016; M-C-007 — conveyor-manual-0323-en.pdf | PDF 62~63쪽 / 인쇄 58~59쪽, 8.3 및 8.5 |
| K-1214 | RT | T6 | RT 정비 완료와 재가동 승인을 구분하고 방호·작업구역 복구를 확인한다 | SC-C-AR-0413 — AR-0413 | EV-0407 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-AR-0414 — AR-0414 | EV-0407 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-EV-0407 — EV-0407 | restart_attempts: AT-4019; SC-C-AR-0415 — AR-0415 | EV-0408 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-AR-0416 — AR-0416 | EV-0408 [maintenance_restart] 관측·보류 시도·다음 확인; SC-C-EV-0408 — EV-0408 | restart_attempts: AT-4022; M-C-002 — 1110_Roller_conveyor_EN_TNr_1131919_V1.0.pdf | PDF/인쇄 35~36쪽, Initial startup / Before every operation start |
| K-1215 | CV | T6 | CV 비상정지 표시가 풀려도 걸림 제거·기능시험 기록이 없으면 복귀를 보류한다 | SC-C-AR-0417 — AR-0417 | EV-0409 [abnormal_stop_restart] 관측·보류 시도·다음 확인; SC-C-AR-0418 — AR-0418 | EV-0409 [abnormal_stop_restart] 관측·보류 시도·다음 확인; SC-C-EV-0409 — EV-0409 | restart_attempts: AT-4025; SC-C-AR-0419 — AR-0419 | EV-0410 [abnormal_stop_restart] 관측·보류 시도·다음 확인; SC-C-AR-0420 — AR-0420 | EV-0410 [abnormal_stop_restart] 관측·보류 시도·다음 확인; SC-C-EV-0410 — EV-0410 | restart_attempts: AT-4028; M-C-007 — conveyor-manual-0323-en.pdf | PDF 69쪽 / 인쇄 65쪽, 10.1 Procedure in Case of Operational Malfunctions |
| K-1216 | GR | T6 | 정지 전 75 degC에서 냉각 후 49 degC로 변해도 원인 확인과 재가동 관측을 생략하지 않는다 | SC-C-AR-0421 — AR-0421 | EV-0411 [abnormal_stop_restart] 관측·보류 시도·다음 확인; SC-C-AR-0422 — AR-0422 | EV-0411 [abnormal_stop_restart] 관측·보류 시도·다음 확인; SC-C-EV-0411 — EV-0411 | restart_attempts: AT-4031; SC-C-AR-0423 — AR-0423 | EV-0412 [abnormal_stop_restart] 관측·보류 시도·다음 확인; SC-C-AR-0424 — AR-0424 | EV-0412 [abnormal_stop_restart] 관측·보류 시도·다음 확인; SC-C-EV-0412 — EV-0412 | restart_attempts: AT-4034; M-C-003 — 26867443.pdf | PDF/인쇄 5·45쪽, Safety notes 및 9.1 Operating temperature too high / Bearing point temperatures too high |
| K-1217 | RT | T6 | RT 인터록 정지 후에는 해제 표시와 작동 조건 해소·승인을 각각 확인한다 | SC-C-AR-0425 — AR-0425 | EV-0413 [abnormal_stop_restart] 관측·보류 시도·다음 확인; SC-C-AR-0426 — AR-0426 | EV-0413 [abnormal_stop_restart] 관측·보류 시도·다음 확인; SC-C-EV-0413 — EV-0413 | restart_attempts: AT-4037; SC-C-AR-0427 — AR-0427 | EV-0414 [abnormal_stop_restart] 관측·보류 시도·다음 확인; SC-C-AR-0428 — AR-0428 | EV-0414 [abnormal_stop_restart] 관측·보류 시도·다음 확인; SC-C-EV-0414 — EV-0414 | restart_attempts: AT-4040; M-C-002 — 1110_Roller_conveyor_EN_TNr_1131919_V1.0.pdf | PDF/인쇄 36쪽, Before every operation start / Procedure in case of accident or fault |
| K-1218 | HPU | T6 | HPU 유온 < 35 degC 기동은 유온만으로 복귀를 정하지 않고 오일 적합성·흡입 조건을 확인한다 | SC-C-AR-0401 — AR-0401 | EV-0401 [normal_stop_restart] 관측·보류 시도·다음 확인; SC-C-AR-0402 — AR-0402 | EV-0401 [normal_stop_restart] 관측·보류 시도·다음 확인; SC-C-EV-0401 — EV-0401 | restart_attempts: AT-4002; SC-C-AR-0429 — AR-0429 | EV-0415 [normal_stop_restart] 관측·보류 시도·다음 확인; SC-C-AR-0430 — AR-0430 | EV-0415 [normal_stop_restart] 관측·보류 시도·다음 확인; SC-C-EV-0415 — EV-0415 | restart_attempts: AT-4043; M-C-005 — HY29-0022-UK.pdf | PDF 6·37~38·49쪽 / 인쇄 7·38~39·50쪽, 1.4 및 viscosity failures / no flow no pressure |
| K-1219 | GR | T6 | 30일 정상정지 뒤에는 이전 운전 성공과 별도로 유면·윤활 준비를 다시 확인한다 | SC-C-AR-0405 — AR-0405 | EV-0403 [normal_stop_restart] 관측·보류 시도·다음 확인; SC-C-AR-0406 — AR-0406 | EV-0403 [normal_stop_restart] 관측·보류 시도·다음 확인; SC-C-EV-0403 — EV-0403 | restart_attempts: AT-4008; SC-C-AR-0407 — AR-0407 | EV-0404 [normal_stop_restart] 관측·보류 시도·다음 확인; SC-C-AR-0408 — AR-0408 | EV-0404 [normal_stop_restart] 관측·보류 시도·다음 확인; SC-C-EV-0404 — EV-0404 | restart_attempts: AT-4011; M-C-003 — 26867443.pdf | PDF/인쇄 39~40쪽, 7.1 Before startup 및 7.2 Taking out of operation |
