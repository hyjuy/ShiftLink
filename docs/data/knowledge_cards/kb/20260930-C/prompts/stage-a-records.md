# 배치 C 단계 A - 재가동 합성 근무기록

배치 KB-20260930-C, 고정 시드 20260930. 작업 가이드 docs/collaboration/kb-cau-pdp-t2-t6-guide-20260930.md를 따른다.
event_plan.json에 따라 Event 20건과 사건별 work_note, handover 2건을 만든다. KB는 EV-0401~0415, dev는 EV-0416~0420이다. dev 기록은 분리 파일 records/dev_events.json, records/dev_artifacts.json에 저장한다. 통합 events.json/artifacts.json은 검증용이며 카드 추출 입력으로 읽지 않는다.

실제 현장 기록이 아니라 PDF에서 확인한 안전 범위와 가상 MES 카탈로그에 맞춘 합성 자료이다. 합성 원인 true_cause는 평가 원장 전용이며 관측 기록 텍스트에 복사하지 않는다. 기록 작성 당시 관찰한 사실, 조회한 정비 이력, 승인 상태와 미확인 사항만 문장에 넣는다. 알람 코드를 새로 만들지 않는다.

각 시도는 attempt_id, restart_type, action, observed_result, failure_reason, evidence_gap를 기록한다. 실패 이유를 확정한 확인 기록이 없으면 failure_reason=null, evidence_gap=not_recorded이다. 관측 결과만으로 실패 원인을 확정하지 않는다. 기동 준비 확인에서 승인 누락으로 중단된 것도 전원 투입 없는 보류 시도로 구별한다. 실제 기동은 정지 원인 확인, 인터록 조건 해소, 지정 승인자의 승인 후만 한다. 에너지 차단·잠금 해제는 현장 승인 절차를 따른다. 안전장치와 인터록은 우회하지 않는다.

인계 5요소 [현재 상태], [앞 근무자 조치], [시도했으나 실패], [미해결], [다음 조 확인]을 모두 쓴다. MES 수치는 신호 사전의 가상 관측값이며 제조사 안전 한계로 사용하지 않는다. 동일 사건의 복수 재가동 유형은 시간 단계와 시도를 분리한다. EV-0401은 정비 후 복귀와 다음날 정상정지 후 저온기동, EV-0403/0404는 정비 복귀와 30일 후 정상정지 복귀를 담는다.

확인할 원문: HPU/HY29-0022-UK.pdf PDF 6·24쪽(인쇄 7·25쪽)과 37~38쪽(인쇄 38~39쪽); GR/26867443.pdf PDF 5·39~40·43·45쪽; CV/conveyor-manual-0323-en.pdf PDF 56·62~63·69쪽; RT/1110_Roller_conveyor_EN_TNr_1131919_V1.0.pdf PDF 35~36쪽. 실제 설비와 모델 동일성은 미확정이므로 조립 수치·압력·기동시간·승강 구조는 이식하지 않는다. 원문은 관측/재가동 준비 확인의 범위 제한에 쓰고 실제 작업표준을 대신하지 않는다.

Event·Artifact 스키마, ID 충돌, 신호 설치 위치, KB/dev 15/5, 인계 5요소, 원인 누수 0을 검증한다. eval/ 폴더는 읽지 않는다.
