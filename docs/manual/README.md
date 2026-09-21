# 이상상황 시나리오용 산업 매뉴얼

조사·정리일: 2026-09-20 (Asia/Seoul)

ShiftLink의 가상 냉연 코일 이송 보조설비(유압장치·감속기·롤러·컨베이어)와 MES 이상 처리 시나리오를 위한 공식 공개 자료 목록이다. 개별 제철소의 내부 작업표준서나 실제 설비에 대한 승인된 작업 지시서는 아니다.

## 자료 목록

| ID | 발행 기관·자료 | 확인 지점 | ShiftLink 활용 |
| --- | --- | --- | --- |
| M-01 | [Parker — Hydraulic Pumps, Overall Instructions](https://www.parker.com/content/dam/Parker-com/Literature/PMDE/Service_Manuals/Vane_Pumps/HY29-0035-UK.pdf), `HY29-0035-M1/UK`, T7 / T67 / T6 | 7절 Vane Troubleshooting Guide, 인쇄 페이지 33~36 | `HPU-01` 압력·유량 이상에서 원인 후보와 추가 확인 항목 구성 |
| M-02 | [SEW‑EURODRIVE — Possible malfunctions/remedy](https://download.sew-eurodrive.com/download/html/31981496/en-EN/25440305419.html) | 고장·가능 원인·조치 표 | `GR-01` 과열, 베어링부 온도 상승, 누유, 냉각 문제 구분 |
| M-03 | [SKF — Bearing damage analysis: ISO 15243 is here to help you](https://evolution.skf.com/bearing-damage-analysis-iso-15243-is-here-to-help-you/), 2022-08-10 | 베어링 손상 유형과 원인 해설 | 롤러·구동부의 증상과 확정 진단 구분 |
| M-04 | [Siemens — SINAMICS G120 CU240B/E-2 List Manual](https://cache.industry.siemens.com/dl/files/596/59745596/att_77615/v1/LH11_0112_eng.pdf), 01/2012 | 고장·경고별 원인, 반응, 확인 항목 | 향후 인버터 알람을 추가할 때 코드 해석과 원인 추정 구분 |
| M-05 | [SAP Digital Manufacturing — Nonconformance Disposition Routings](https://help.sap.com/docs/sap-digital-manufacturing/execution/nonconformance-disposition-routings) | 부적합 분석·수리·복귀·폐기 경로 및 허용범위 이탈 처리 | 영향 코일의 검사·재작업·폐기 업무 시나리오 |
| M-06 | [SAP — Controlling Production (Buyoff, Hold, Release)](https://learning.sap.com/courses/configuring-sap-digital-manufacturing-for-execution-basic-data-and-configuration/controlling-production-buyoff-hold-release-) | 제품 보류·해제 및 보류 상태의 작업 제한 | 영향 코일 식별, 보류, 조치 기록, 해제 시나리오 |

M-03은 제조사 기술 해설이며 독립된 운전 매뉴얼은 아니다. M-05와 M-06은 MES 제품 도움말·교육 자료이다. 웹 문서는 변경될 수 있고, 검색 시점의 공개 여부가 최신 적용본임을 의미하지 않는다. M-04는 2012년판이므로 실제 적용 모델·펌웨어와 일치하는지 별도 확인해야 한다.

## 자료별 활용 메모

### M-01 — 유압 펌프

압력·유량이 발생하지 않거나 유량이 부족한 상황에서 회전, 흡입 조건, 유면, 밸브 계통 등 여러 후보를 구분하는 진단 구조를 참고한다. 저압 신호만으로 펌프 고장을 확정하는 정답을 만들지 않는다. 프로젝트 `../data/00_plant_and_relations.json`의 `SD-002` 참고문헌과 연결된다.

### M-02 — 감속기

과열과 누유를 각각 관측 증상으로 기록하고 오일 상태, 냉각 상태, 베어링 관련 후보를 분리한다. 원문이 제시하는 조치는 해당 제품의 조건을 전제로 하므로 다른 설비의 작업 절차로 그대로 전용하지 않는다.

### M-03 — 베어링

진동·소음·온도 이상과 손상 분류를 구분하는 데 활용한다. 관측만으로 확정하기 어려운 경우에는 추가 점검이 필요하다는 답변을 평가한다. 프로젝트 `SD-003`의 SKF 핸드북과 관련된 보조 자료이며 핸드북 자체를 확보한 것으로 취급하지 않는다.

### M-04 — 인버터

고장 코드의 의미와 실제 발생 원인을 분리한다. 예를 들어 `F30017`은 단일 기계 고장의 확정 코드가 아니라 여러 전기·부하·설정 원인을 검토하는 항목이다. 현재 ShiftLink에 해당 제조사 인버터가 설치되어 있다고 가정하지 않는다.

### M-05 / M-06 — MES 업무 처리

부적합 기록, 별도 처리 경로, 제품 보류 및 해제의 상태 흐름을 참고한다. 설비가 정상화된 시점과 영향 제품의 검사·보류 해제 시점을 분리한다. SAP의 기능 설명은 ShiftLink에 동일 기능이 구현되어 있다는 의미가 아니다.

## 합성 시나리오 후보

아래 항목은 공개 자료와 현재 `../design/mock-mes-domain.md`의 설비 관계를 조합한 설계 제안이다. 제조사가 제공한 실제 사고 사례나 검증된 공정 모델이 아니다.

| 시나리오 | 관측·사건 | LLM 평가 지점 | 근거 구분 |
| --- | --- | --- | --- |
| 유압 공급 저하 | `HPU-01` 압력 저하와 연결 설비의 동시 대기 | 공통 공급원과 개별 고장을 구분하고 추가 정보 요청 | 진단 구조 M-01, 영향 관계는 프로젝트 모델 |
| 구동부 과열 | `GR-01` 온도 상승과 오일·냉각 관측 | 원인 후보와 확인 근거를 제시하고 단정 방지 | M-02, M-03 |
| 출측 정체 | `CV-01` 이상 → `RT-03` 대기 → 상류 소재 적체 | 최초 이상과 후속 대기 구분, 영향 코일 설명 | 프로젝트 모델; 현장 인터록 검증은 별도 |
| 관측 불일치 | 정지 상태와 속도 신호 모순 또는 갱신 지연 | 데이터 신뢰도 표시와 판단 보류 | 별도 합성 평가 제안; 매뉴얼의 직접 사례 아님 |
| 복구 후 제품 처리 | 설비 정상화, 영향 코일 검사·보류 미완료 | 설비 복구와 제품 해제를 별도로 판단 | M-05, M-06을 참고한 확장 제안 |

시나리오마다 관측값, 원인 후보, 추가 확인, 영향 설비·코일, 대응 근거, 복구 조건을 구분한다. 문서 ID, 절·페이지, 적용 모델·버전과 합성 여부를 함께 기록한다.

## 적용 한계와 후속 확인

- 현재 MES의 2 tick 안정화 후 복구는 합성 규칙이며 매뉴얼로 검증된 재가동 조건이 아니다.
- 압력·온도 임계값, 정비 및 재가동 절차는 실제 적용 설비의 사양과 현장 승인 절차로 확인해야 한다.
- 원문 저작권은 각 발행자에게 있다. 공개 열람 가능 여부와 재배포·학습 이용 허용 여부는 별개이며 원문 표·본문을 합성 데이터에 그대로 복제하지 않는다.
- 본 목록은 앞선 조사에서 확인한 공개 본문·검색 색인을 기반으로 한다. 개별 현장의 최신 적용본 여부와 모든 문서의 전문을 검증한 것은 아니다.

PDF 원본의 로컬 확보 여부는 [다운로드 기록](download-status.md)을 참고한다.
