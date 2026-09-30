# T6 생성 근거 및 추적

9장 모두 합성 기록에서 추출한 draft/L0이다. 실제 현장경험·사람 승인은 없다. 원문 특유 수치와 작업 절차를 가상 설비에 이식하지 않았다.

KB EV-0401~0415만 추출에 사용했다. dev EV-0416~0420 및 eval/를 단계 B에서 읽지 않는다. records/kb_events.json은 원인 정답·조치 정답·기대 카드 없는 관측 투영이며 통합 원장은 검증 전용이다.

EV-0401은 D0 정비복귀와 D1 정상정지 저온기동, EV-0403/0404는 D0 정비복귀와 D30 정상정지 복귀를 구분한다. 카드마다 해당 restart_type 시도만 사용한다.

실패 이유 진단이 없으므로 모든 failure_reason=null, evidence_gap=not_recorded. 기동 준비 보류는 전원 투입 없는 보류이며 허가 없는 재기동이 아니다.

| 카드 / 슬롯 | 재가동 유형 | KB 관측 근거 | PDF 확인 범위 |
| --- | --- | --- | --- |
| K-1211 / S11 | maintenance_restart | EV-0401 / AR-0401,AR-0402, EV-0402 / AR-0403,AR-0404 | HPU/HY29-0022-UK.pdf, PDF 6·24쪽 / 인쇄 7·25쪽, 1.4 및 2.4.1 |
| K-1212 / S12 | maintenance_restart | EV-0403 / AR-0405,AR-0406, EV-0404 / AR-0407,AR-0408 | GR/26867443.pdf, PDF/인쇄 39~40·43쪽, 7.1 및 8.3 |
| K-1213 / S13 | maintenance_restart | EV-0405 / AR-0409,AR-0410, EV-0406 / AR-0411,AR-0412 | CV/conveyor-manual-0323-en.pdf, PDF 62~63쪽 / 인쇄 58~59쪽, 8.3 및 8.5 |
| K-1214 / S14 | maintenance_restart | EV-0407 / AR-0413,AR-0414, EV-0408 / AR-0415,AR-0416 | RT/1110_Roller_conveyor_EN_TNr_1131919_V1.0.pdf, PDF/인쇄 35~36쪽, Initial startup / Before every operation start |
| K-1215 / S15 | abnormal_stop_restart | EV-0409 / AR-0417,AR-0418, EV-0410 / AR-0419,AR-0420 | CV/conveyor-manual-0323-en.pdf, PDF 69쪽 / 인쇄 65쪽, 10.1 Procedure in Case of Operational Malfunctions |
| K-1216 / S16 | abnormal_stop_restart | EV-0411 / AR-0421,AR-0422, EV-0412 / AR-0423,AR-0424 | GR/26867443.pdf, PDF/인쇄 5·45쪽, Safety notes 및 9.1 Operating temperature too high / Bearing point temperatures too high |
| K-1217 / S17 | abnormal_stop_restart | EV-0413 / AR-0425,AR-0426, EV-0414 / AR-0427,AR-0428 | RT/1110_Roller_conveyor_EN_TNr_1131919_V1.0.pdf, PDF/인쇄 36쪽, Before every operation start / Procedure in case of accident or fault |
| K-1218 / S18 | normal_stop_restart | EV-0401 / AR-0401,AR-0402, EV-0415 / AR-0429,AR-0430 | HPU/HY29-0022-UK.pdf, PDF 6·37~38·49쪽 / 인쇄 7·38~39·50쪽, 1.4 및 viscosity failures / no flow no pressure |
| K-1219 / S19 | normal_stop_restart | EV-0403 / AR-0405,AR-0406, EV-0404 / AR-0407,AR-0408 | GR/26867443.pdf, PDF/인쇄 39~40쪽, 7.1 Before startup 및 7.2 Taking out of operation |

HPU 원문 HY29는 베인펌프 자료이지만 설치 모델 일치는 확인되지 않았다. GR 원문은 ML..2/ML..V2이며 CV 원문은 특정 컨베이어, RT 원문은 SH1110 롤러 컨베이어다. 따라서 원문은 충유/공기,유면,방호,시험운전 확인 범위의 배경으로만 사용했다. RT 승강·클램프 압력 설정·인터록 회로 및 구체 잠금 해제 절차를 제시하지 않는다.

가상 MES 수치는 매뉴얼 임계값이 아니다. 정지중 속도·전류 0을 고장 또는 정상으로 임의 보정하지 않는다. 혼합 단계 사건 measurements는 마지막 단계 관측이며 다른 단계는 timeline과 근무기록을 참조한다.

프롬프트 해시: c2c7d293c36c6e511012f71064b58532aafe15742886e144302dd8e525800d2c
