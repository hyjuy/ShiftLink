# 배치 C 단계 B - T6 9장 추출

입력은 records/kb_events.json의 restart_attempts와 records/kb_artifacts.json의 근무일지/인계뿐이다. true_cause·true_actions·cards_expected는 추출 입력에서 제외한다. events.json/artifacts.json 통합본, records/dev_*.json, eval/는 읽지 않는다.

K-1211~K-1219, 슬롯 S11~S19. 정비 후 4장(HPU/GR/CV/RT), 비정상 정지 후 3장(CV/GR/RT), 정상 정지 후 2장(HPU/GR). 카드별 서로 다른 KB 사건 최소 2건의 관측 기록에서 반복되는 재가동 요령·실패만 추출한다. 장기 정상정지는 보관·새 설비의 최초 기동과 동일하게 간주하지 않는다.

반복 실패 조치를 type_payload.tried_and_failed에 관측 시도 그대로 기록한다. 카드 restart_type과 일치하는 시도만 포함한다. 실패 이유가 기록되지 않았으면 null 및 evidence_gap=not_recorded를 유지한다. 다른 카드의 시도나 다른 재가동 유형을 복사하지 않는다. 실패 원인을 새로 추정하여 채우지 않는다.

version=1.0-draft-KB-20260930-C, grade=L0,status=draft,split=kb,confidence=0.0. provenance.seed_ids=[KB-20260930-C:seed=20260930,slot:Sxx]. prompt_version은 본 파일의 상대 경로@sha256:실제 해시. sources에는 EV/AR 기록 위치와 절차 범위를 제한한 PDF 쪽을 적는다. generalization_evidence는 합성 관측 2건 이상에 한정한 잠정 일반화임을 명시한다. 실제 숙련자의 현장경험으로 주장하지 않는다.

매뉴얼 모델과 가상 설비가 같다고 확인되지 않았으므로 원문 특유의 압력·시간·분해·스플라이스·승강·회로 해제 절차를 만들지 않는다. 재가동 선행조건과 승인/준비 여부 및 관측 요령을 쓴다. 안전장치·인터록 우회는 허용하지 않는다. 정지 원인 확인·인터록 작동 조건 해소·지정 승인자의 승인은 공통 선행조건이다. MES 상태가 정상이어도 이를 대신하지 않는다. 매뉴얼 기준과 MES 가상 정상범위를 구분한다.

out/T6.json, out/T6_notes.md를 저장한다. 독립 서브에이전트의 출처·기록 대조 판정 후 근거에 맞춰 수정한다. 독립 에이전트 검토는 사람 승인이나 L1 승격을 대신하지 않는다.
