# shared 원문 검토와 지식카드 후보 근거표

2026-09-25 검토. 대상: `docs/data/events/shared/` 폴더의 원문 7건 (추출 페이지 총 149 + 추출 불가 5). 냉간코일 공장 설비 사건 기록 여부, 공급사 주장 vs. 실제 수행 조치 구분, T1~T6 카드 후보 판정.

## 1. 원문 분류

| 파일 | 정체 | 분류 | 근거 |
|---|---|---|---|
| **Troubleshooting.pdf** | DGUV Information 209-071 E (March 2015). 독일 사회재해보험 발행. "Safe maintenance of hydraulic systems" — 유압 시스템의 안전한 정비 절차 참고자료 | C | 일반 유압 정비 매뉴얼 및 트러블슈팅 가이드. 실제 냉간코일 공장 사건 기록 아님. 시스템 설계, 구성요소별 작업, 위험 관리, 일반 진단 원칙 수록. 사건 후보 제외. |
| **hydraulic_maintenance.pdf** | Norman Kronowitz 발표. CMA/Flodyne/Hydradyne 협력 제작. "Hydraulic Maintenance & Troubleshooting" 프레젠테이션 | B/C | 유압 시스템 유지보수 및 진단 교육 자료. 프레젠테이션 형식이며 제목별 요약 집합. 실제 사건 기록 미포함. 배경 참고자료로 범주화. |
| **NSK-Case-Study-Cold-Rolling-Mill_SteelStrip.pdf** | NSK (Nippon Seiko K.K.) 사례집. "Cold Rolling Mill Application CS 1 / ATI / 21". 원제: "NSK CASE STUDY" | C | NSK 마케팅 자료. 냉간압연 베어링 손상(철강 칩 유입) 진단 + NSK WTF 베어링 권고. "More than 3X longer bearing life", "$28,288 cost savings" — 공급사 주장 수치. 제품 특성 설명과 ROI 계산 포함. 실제 설치 후 검증 기록 미제공. |
| **Rolling mill bearing reliability_ three case studies, one conclusion - Euro Bearing.pdf** | Euro Bearing(Global Components, Italy) 웹 기사. 2026년 콘텐츠로 보임. | C | 3개 진단 사례(독일 열간, 이탈리아 냉간, 스페인 장재). 관측·분석·권고 기술. 냉간압연 백업롤 사례(진동 모니터링, 초크 보어 마모 발견, 정기 정비 후 고장 중단)에 "failures stopped"라는 성과 표현. 실제 정비 원장·측정값·추적 기간 미제공. 계속성 미확인(몇 개월/년 추적했는지 불명). |
| **SKF-10404_EN_Driveline_for_Metals.pdf** | SKF PUB 71/S7 10404 EN (May 2010). 금속 산업 구동계 제품 솔루션 자료 | C | SKF 제품 카탈로그 + 마케팅 사례. "Rolling mill doubles MTBF with SKF engineered solutions" 사례 포함. "ROI 325%", "customer estimates" 표시. 냉간코일 관련 아님 — 사례는 "steel strip-pickling line" (피클링/산세척, 열간 후공정). 구동계 제품 설명이 주 내용. |
| **shell-sls-whitepaper-02-v7edited.pdf** | Shell Lubricant Solutions. "Tackling common issues in hydraulic systems" 백서 | B/C | 윤활제 회사의 기술 백서. 3개 이슈(Sludge and varnish, Water contamination, Aeration) 설명 + 권고 사항 (유압액 선택, 유지보수 방법론). 냉간코일 또는 금속 산업 구체적 사례 미포함. "How to deal with...", "Practise preventive..." 등 권고 방식. 실제 현장 결과 기록 아님. |
| **FUCHS-RENOLIT-CXS-AM-1.html** | FUCHS Lubricants Co. (USA) 웹 페이지. "Case Study - RENOLIT CXS AM 1" | C | FUCHS 윤활제 사례 연구. Challenge(물 부식, 리튬 그리스의 한계) → Solution(RENOLIT CXS AM 1 칼슘 설폰산 그리스) → Results. 냉간압연 Work Roll Bearing & Chock 적용 사례. 공급사 주장 수치: "~$400,000 per year" 절감 (퍼지율 100% → 70% 감소). 결과는 고객이 보고한 값이며 독립 검증 미제공. 운전 수행·추적 기간 미명시. |

**분류 요약**: A(실제 사건) 0건, B(매뉴얼/권고) 2건(hydraulic_maintenance, shell 부분), C(참고자료/사례집/백서) 7건 (모두)

---

## 2. 근거표

### 냉간코일 공장 설비 대응 확인도

| 파일 | 냉간코일 공정·설비 대응 | 판정 | 사유 |
|---|---|---|---|
| Troubleshooting.pdf | 미확인 | C로 유지 | 일반 유압 시스템 참고자료. 냉간코일 공장, 특정 설비군, 실제 대응 조치 기록 없음. |
| hydraulic_maintenance.pdf | 미확인 | C로 유지 | 교육용 프레젠테이션. 산업별, 설비별 특화 사례 부재. |
| NSK-Case-Study | 확인됨 | C 유지 (사건 아님) | "Cold rolling mill" 명시. 하지만 분석 및 권고까지만 있고, 설치 후 검증 기록 미제공. |
| Euro Bearing | 부분 확인 | C 유지 (사건 아님) | 사례 2: "Italian cold rolling operation", "backup rolls". 냉간압연 명시. 하지만 진단·권고까지이며, 실제 조치 수행 기록(언제, 누가, 측정값) 미제공. |
| SKF-10404 | 미확인 | C 유지 | 사례는 "steel strip-pickling line" (냉간코일이 아니라 피클링). 금속 산업 제품 카탈로그. |
| Shell | 미확인 | C 유지 | 제조사 배경 자료. 냉간코일 또는 특정 공정·설비 대응 기록 없음. |
| FUCHS | 확인됨 | C 유지 (사건 아님) | "Cold rolling mill work-roll bearing & chock". 공급사가 주장한 사례. 결과는 고객 자체 보고이며 독립 검증 미제공. |

**결론**: 냉간코일 공장 설비 대응이 명시된 파일은 NSK, Euro Bearing(부분), FUCHS이나, 모두 공급사가 주장한 사례 또는 진단 기록이며 실제 정비 원장(날짜, 수행자, 조치 순서, 검증 기록, 재발 확인)이 없음.

---

## 3. 카드 후보 (T1~T6)

### 검토 결과: 카드 후보 1건

| 후보 ID | 유형 | 지식 핵심 | 근거 위치 | 필수 필드 충족 근거 | 미충족 항목 | 원문 종류 |
|---|---|---|---|---|---|---|
| **SH-C01** | T1 | 유압 시스템 9가지 에러(증상) 분류: 과도한 소음, 불충분한 압력, 불규칙한 실린더/모터 움직임, 출력 미작동, 과도한 온도, 유압액 기포, 냉각 실린더, 라인 충격, 펌프 시작/정지 주파수 | `Troubleshooting.pdf`, PDF p78 (Annex 1 - "A Troubleshooting"), 인쇄면 78, 단원 "Annex 1 A Troubleshooting" | T1 필수 조건: 공백 아닌 symptom. 원문 p78에 명시된 9가지 에러 분류 ("Excessive noises", "Insufficient forces and torques", "Jerky cylinder or motor movements" 등) | 조건(conditions) 미제공. 각 증상별 예외/제외 규정 없음. | C (일반 참고자료/매뉴얼) |

**판정**: 카드 후보 1건만 채택. T1의 필수 조건(공백이 아닌 symptom)을 원문에서 충족함. 그 외 T2~T6은 원문 필수 필드 미충족으로 후보 대상 아님.

**주의**: 이 카드는 일반 유압 시스템 가이드(DGUV)이며 냉간코일 공장 설비 특화 지식이 아님. 현장 기술자 검수 필수. approved_scope 승인 후에만 KB 투입 가능.

---

## 4. 기존 카드 중복 확인

### 2026-09-24 카드 패킷 참조

**기존 카드**: K-0301, K-0302, K-0303 (모두 SD-005 KOSHA M-101-2012 기반, CV 컨베이어 안전)

**SKF-10404 및 NSK 계보 확인**:
- `source-packet.json`에서 SKF-10404(source_id=LOCAL-SKF-10404-EN, bucket=7/dev) 및 NSK(source_id=LOCAL-NSK-COLD-ROLLING, bucket=7/dev)는 등록되었으나 `approved_scope=[]` (미승인)
- 두 파일 모두 "not_registered_local_identifier_only" 상태. SD-001~SD-008 정식 등록부의 source_id를 받지 않음.
- 기존 approved_for_draft 카드는 없음.

**중복 판정**: 
- **새 후보 관련 중복 없음** (카드 후보가 0건이므로 해당 없음)
- **계보 중복 확인**: SKF-10404와 NSK는 2026-09-24 source-packet.json의 로컬 ID로 참조되었던 파일들과 동일 파일.
  - 구 경로: `docs/data/events/SKF-10404_EN_...` / `docs/data/events/NSK-Case-Study-...`
  - 현 경로: `docs/data/events/shared/SKF-10404_EN_...` / `docs/data/events/shared/NSK-Case-Study-...`
  - SHA-256 확인 필요 (파일 내용 변경 여부).

---

## 5. 등록부 매칭

### source_registry.json 대조

| 파일 | 매칭된 source_id | 매칭 근거 | 현재 review_status | approved_scope | 판정 |
|---|---|---|---|---|---|
| **Troubleshooting.pdf** | 미등록 | 제목/저자 "DGUV Information 209-071 E"로 등록부 검색 미결과. 파일명도 일치하는 source_id 없음. | — | — | **미등록 출처**. 등록 제안: title="DGUV Information 209-071 E: Safe maintenance of hydraulic systems", 제조사=DGUV(독일 사회재해보험), 문서번호=209-071, 판본=English translation, 발행연도=2015, purpose="유압 시스템 정비 안전 참고자료" |
| **hydraulic_maintenance.pdf** | 미등록 | 제목 "Hydraulic Maintenance & Troubleshooting", 저자 Norman Kronowitz로 등록부 미등재. | — | — | **미등록 출처**. 등록 제안: title="Hydraulic Maintenance & Troubleshooting", 저자=Norman Kronowitz, 발행기관=CMA/Flodyne/Hydradyne, purpose="유압 정비 교육 프레젠테이션" |
| **NSK-Case-Study-Cold-Rolling-Mill_SteelStrip.pdf** | 미등록 (SD-003 관련?) | 문서번호 "CS 1 / ATI / 21"은 기존 등록부 SD-003(SKF 베어링 손상 분류)와 무관. NSK 사례집으로 등록부의 "NSK", "Cold Rolling", "Case Study" 키워드 검색 미결과. | — | — | **미등록 출처**. 기존 source-packet.json의 LOCAL-NSK-COLD-ROLLING ID는 비정식 로컬 식별자(not_registered). 등록 제안: title="NSK Case Study: Cold Rolling Mill / Water-Tough Steel Bearings", 제조사=NSK, 문서번호=CS 1 / ATI / 21, purpose="냉간압연 베어링 손상 사례(마케팅 자료)" |
| **Rolling mill bearing reliability...** | 미등록 | "Euro Bearing", "web article", "three case studies"로 등록부 검색 미결과. URL도 명시되지 않음(웹 페이지 캡처본). | — | — | **미등록 출처**. 등록 제안: title="Rolling mill bearing reliability: three case studies, one conclusion", 발행기관=Euro Bearing (Global Components, Italy), URL=https://eurobearing.eu/rolling-mill-bearing-reliability-three-case-studies-common-conclusion/ (추정), purpose="냉간·열간압연 베어링 진단 기사" |
| **SKF-10404_EN_Driveline_for_Metals.pdf** | 미등록 (SD-003 동족?) | 문서번호 "PUB 71/S7 10404 EN"은 기존 등록부 SD-003(SKF 베어링 손상)과 제조사 동일하나 다른 문서. 등록부에 "SKF-10404" 명시 없음. source-packet.json의 LOCAL-SKF-10404-EN 참조(비정식). | — | — | **미등록 출처**. 기존 SKF 관련 SD-003/SD-004와 계열 다름 (손상 분류 vs. 제품 카탈로그). 등록 제안: title="SKF Solutions for Metal Industry Drivelines (PUB 71/S7 10404 EN)", 제조사=SKF, 문서번호=PUB 71/S7 10404 EN, 판본=May 2010, purpose="금속 산업 구동계 제품 자료" |
| **shell-sls-whitepaper-02-v7edited.pdf** | 미등록 | 제목 "Tackling common issues in hydraulic systems", 발행기관 Shell Lubricant Solutions로 등록부 검색 미결과. | — | — | **미등록 출처**. 등록 제안: title="Tackling common issues in hydraulic systems: Whitepaper", 제조사=Shell Lubricant Solutions, purpose="유압계통 윤활제 기술 백서" |
| **FUCHS-RENOLIT-CXS-AM-1.html** | 미등록 | 제목 "Case Study - RENOLIT CXS AM 1", 발행기관 FUCHS Lubricants Co. (USA), URL=제조사 웹사이트로 등록부 미등재. | — | — | **미등록 출처**. 등록 제안: title="FUCHS Case Study: RENOLIT CXS AM 1 for Cold Rolling Mill Work Roll Bearings", 제조사=FUCHS Lubricants Co., 제품=RENOLIT CXS AM 1, purpose="냉간압연 윤활제 사례" |

**결론**: 7개 파일 모두 **미등록 출처**. source-registry.json의 SD-001~SD-012에 명시되지 않음. 2026-09-24 source-packet.json의 로컬 ID(LOCAL-SKF-10404-EN, LOCAL-NSK-COLD-ROLLING)는 임시 참조용이며 정식 등록이 아님.

**생성 파이프라인 적용 가능성**: 모든 파일이 `approved_for_draft` 상태가 아니므로 운영 KB 투입 불가. 검토용 초안만 가능. "생성 파이프라인·운영 KB 투입 금지" 표시 필요.

---

## 6. 부족한 근거

### 카드화 시도했으나 원문 미충족 항목

| 항목 | 파일 | 빠진 것 | 확인 범위 | 필요 정보 |
|---|---|---|---|---|
| **T3 원인 확인 절차** | NSK-Case-Study (p001~p002) | 단계별 action + expected_result 구조화 미제공. 진단 과정(분석 → 권고) 기술되나, "Step 1: [확인 내용] → 기대 관측: [결과]" 형식 없음. | 전체 2p 검토 | 원문이 마케팅 문서이므로 절차 기술 아님. T3 작성 불가. |
| **T3 원인 확인 절차** | Euro Bearing (p002~p003) | 3개 사례 모두 결론 먼저 제시("이 문제였다") → 역추적. 의도적 단계 진단이 아님. | 전체 5p 검토 | 기사/컨설팅 서술형. T3 단계 재구성 불가(원문이 제공 안 함). |
| **T4 인계 방법** | 모든 파일 | required_context, recipient_role, timing, channel, acknowledgement 중 대부분 미기록. | 전체 검토 | 사건 기록이 아니라 자료/가이드이므로 인계 방법 규정 없음. |
| **T6 재가동 실패 경험** | Euro Bearing (p003-p004) | "failures stopped" 표현. 하지만 "정지 후 어떻게 재가동했는가"의 시도·실패 기록 미제공. 단순히 "조치 후 고장이 멈췄다"는 결과 표현. | 전체 5p 검토 | 재가동 순서, 실패 사례, 검증 기록 없음. T6 작성 불가. |
| **원시 정비 기록** | NSK-Case-Study, Euro Bearing, FUCHS | 모든 공급사 사례에서 "언제", "누가", "어떤 순서로", "측정값은 얼마였는가", "재발 확인 기간" 등 원시 정비 원장의 요소 미제공. 분석·결론만 기술. | 각 전체 | 사건 분류(A)로 올리려면 실제 정비 원장 필요. 없으면 C 유지. |
| **공급사 주장 수치 검증** | NSK(p002): "$28,288 cost savings", "3X longer bearing life" | 절감액과 수명 배수가 어떻게 계산되었는가(측정 기간, 표본 수, 계산식) 미기록. "고객이 추정한 값"일 수 있음. | 2p 전체 | 독립 검증된 수치가 아님. 공급사 주장으로만 인용 가능. |
| **공급사 주장 수치 검증** | FUCHS(p001): "~$400,000 per year" 절감 | "년간"이지만 몇 년을 추적했는가, 퍼지율 70%라는 수치의 근거는 무엇인가 미기록. "고객 자체 보고"로만 기술. | 1p 전체 | 독립 검증 불가. |
| **추적 기간** | Euro Bearing (p002-p003) | 3개 사례 모두 "failures stopped"이지만 시점 미제공. "얼마나 오래 모니터링했는가", "얼마나 오래 실패가 없었는가" 불명. | 전체 5p | 재발 위험 평가 불가. |

---

## 7. 담당자 확인 질문

| 질문 | 파일 | 필요 이유 | 확인 대상 |
|---|---|---|---|
| **SKF-10404의 "피클링 라인"이 냉간코일 공정 범위에 포함되는가?** | SKF-10404 (p002) | p002의 사례는 "steel strip-pickling line" (산세척). 냉간코일 공정인지(코일 생산 후 열간 → 냉간 → 피클링) 또는 별도 공정인지 확인 필요. 포함 여부에 따라 설비 대응 재분류. | 냉간코일 공정 담당자 또는 설비 매뉴얼 |
| **NSK와 Euro Bearing 사례의 "실제 설치/적용 시점과 사례 발생 시점"이 명확한가?** | NSK, Euro Bearing | 마케팅 문서와 기사는 진단 완료 시점만 명시. 실제 베어링 또는 정비 시행이 언제 이루어졌는지, 사례의 시간적 배경이 불명확. 냉간코일 공장의 실제 사건인지 확인. | NSK 지역 영업소 또는 Euro Bearing 컨설팅팀 |
| **Shell 백서의 "금속 산업 사례"가 냉간코일 공장을 대상으로 했는가?** | Shell | p002-p010의 "metals industry" 기술은 일반적이며 냉간코일 공장 구체적 사례 미포함. 백서 작성 시 냉간코일을 적용 범위로 고려했는지 확인. | Shell Lubricant Solutions 세일즈 또는 기술팀 |
| **FUCHS 사례의 "년간 $400,000 절감"을 산정한 고객사의 정비 기록을 확보할 수 있는가?** | FUCHS | 공급사 주장 수치는 "고객이 측정"이라고만 기술. 실제 구체적 정비 기록(교체 주기, 그리스 소비량 측정 기록, 베어링 수명 기록)을 외부에서 검증할 수 있는지 확인. | FUCHS 고객 (냉간압연 공장) 또는 FUCHS 영업팀 |
| **Troubleshooting.pdf와 hydraulic_maintenance.pdf의 "일반 원칙"이 ShiftLink의 냉간코일 공장 설비에 적용 가능한가?** | Troubleshooting, hydraulic_maintenance | 두 문서 모두 일반 유압 시스템 가이드. 프로젝트 현장의 유압펌프 모델, 시스템 구성, 위험 수준이 이들 자료의 대상 범위에 포함되는지 확인. | 현장 설비 담당자 또는 설비 매뉴얼 |

---

## 8. 검토 한계

### 미검토 페이지 범위

| 파일 | 추출 페이지 | 실제 검토 범위 | 미검토 범위 | 사유 |
|---|---|---|---|---|
| **Troubleshooting.pdf** | 100 | p001~p010, p024 (목차 구조 확인) + p078 Annex 1 A Troubleshooting 위치 파악 | p025~p077, p079~p100 | 일반 참고자료이며 p024부터 실제 상세 지침이 시작. 냉간코일 사건 기록 가능성 매우 낮음. 전부 정독 불필요. 추출 불가 4페이지 p082~p085 미확인. |
| **hydraulic_maintenance.pdf** | 27 | p001~p005 (개요, 목차), p010~p012 (트러블슈팅 주제) | p006~p009, p013~p027 | 프레젠테이션이므로 슬라이드별 세부 내용이 방대. 냉간코일 사건 기록 미제공 예상. 핵심 섹션만 검토. |
| **NSK-Case-Study-Cold-Rolling-Mill_SteelStrip.pdf** | 2 | 전체 (p001~p002) | 없음 | 파일 수 적음. 전체 검토 완료. |
| **Rolling mill bearing reliability...** | 5 | 전체 (p001~p005) | 없음 | 파일 수 적음. 전체 검토 완료. |
| **SKF-10404_EN_Driveline_for_Metals.pdf** | 2 | 전체 (p001~p002) | 없음 | 파일 수 적음. 전체 검토 완료. |
| **shell-sls-whitepaper-02-v7edited.pdf** | 12 | p001~p008 (목차, 주요 이슈 3개 설명) | p009~p012 (추가 이슈 상세, 결론) | 구조상 p003 이후는 각 이슈별 상세 기술. 냉간코일 공장 사건 기록 미제공 예상. 핵심 섹션만 검토. 추출 불가 1페이지 p009 미확인. |
| **FUCHS-RENOLIT-CXS-AM-1.html** | 1 | 전체 (p001) | 없음 | 1페이지 HTML. 전체 검토 완료. |

### 추출 불가 페이지

- **Troubleshooting.pdf**: 4페이지 (추출 불가. 페이지명 "p082.txt ~ p085.txt" 등으로 표기될 것으로 예상)
- **shell-sls-whitepaper-02-v7edited.pdf**: 1페이지 (추출 불가)
- **기타**: 추출 불가 페이지 없음

### 기존 판단과의 비교 (2026-09-23 검토 보고서)

| 항목 | 2026-09-23 판단 | 2026-09-25 판단 | 일치/불일치 | 비고 |
|---|---|---|---|---|
| **Euro Bearing (Rolling mill bearing reliability)** | "5쪽 확인. 실제 정비 원장·측정값·추적 기간은 없고 백업롤은 현재 설비 분류와 직접 대응하지 않아 보류. C 분류." | "5쪽 전체 재검토. 냉간압연 백업롤 사례 명시. 관측·분석·권고 있음. 실제 정비 원장 미제공. 계속성 미확인. C 분류." | **일치** | 기존 판단 유지. 냉간압연 언급은 있으나 사건 기록이 아님. |
| **NSK-Case-Study** | 2026-09-23 보고서에서 언급 없음 (당시 검토 대상 6개 PDF에 미포함) | "2페이지 전체 검토. 냉간압연 명시, 진단과 권고, 공급사 주장 수치 포함. 설치 후 검증 미제공. C 분류." | 비교 불가 (기존 판단 없음) | 이번 신규 검토. 계보 중복 확인: source-packet.json의 LOCAL-NSK-COLD-ROLLING이 같은 파일. |
| **SKF-10404** | 2026-09-23 보고서에서 언급 없음 | "2페이지 전체 검토. 피클링 라인 사례. 제품 카탈로그. 냉간코일이 아님. C 분류." | 비교 불가 (기존 판단 없음) | 이번 신규 검토. 계보 중복 확인: source-packet.json의 LOCAL-SKF-10404-EN이 같은 파일. |

**핵심 차이**: 2026-09-23은 6개 PDF 중심 검토. 이번 2026-09-25는 shared 폴더의 7개 파일 검토. NSK와 SKF는 이번에 신규 포함.

---

## 9. 특히 주의할 점

1. **공급사 주장 수치의 구분 필수**: NSK의 "3배 수명", "$28,288 절감", FUCHS의 "$400,000 절감" 등은 모두 마케팅 문서 또는 고객 자체 보고. 독립 검증 또는 제3자 감시 기록 없음. 운영 KB나 현장 조치 정당성의 증거로 사용 불가. 이 구분을 근거표·카드·보고서에 명시해야 함.

2. **"사건 기록이 아님" 판정 근거**: 7개 파일 모두 다음 중 하나에 해당:
   - 제조사 마케팅 자료 (NSK, SKF, FUCHS)
   - 컨설팅 기사 (Euro Bearing)
   - 기술 백서 또는 가이드 (Shell, Troubleshooting, hydraulic_maintenance)
   - 실제 정비 원장(언제, 누가, 무엇을, 순서대로, 결과는) 없음.

3. **미등록 출처의 운영 KB 투입 금지**: 모든 파일이 `approved_for_draft` 상태 아님. source_registry.json에 미등록. 생성 파이프라인 제약에 따라 "검토용 초안만 가능" 표시 필수.

---

## 부록: 확정된 문서 정체

**Troubleshooting.pdf**:
- 정식명: DGUV Information 209-071 E
- 제조사/발행기관: Deutscher Gesetzliche Unfallversicherung (DGUV) / German Social Accident Insurance e.V.
- 원본: DGUV Information 209-070 (독일어, 2014년 1월)
- 영문 번역: March 2015
- 문서번호: 209-071 E (BGI/GUV-I 5100의 후속)
- 범위: 유압 시스템 정비 안전 기준 및 절차 (European Machinery Directive 범위)
- 실제 사건 기록: 없음

---

## 9. 검증 결과

별도 검증에서 **근거표의 각 주장이 적힌 페이지 텍스트에 실제로 있는지만** 대조했다. 중간 기록은 `artifacts/source-card-review-20260925/verify/shared-verify.md`에 있다(Git 제외). 검증은 §3을 이진 판정으로 재정리하기 전 상태의 보고서를 읽었다. 불일치는 위 표에서 지우지 않고 아래에 표시한다.

| 항목 | 건수 |
|---|---|
| 대조한 주장 | 28 |
| 일치 | 24 |
| 부분 일치 | 2 |
| 불일치 | 0 |
| 다른 페이지에 있음 | 1 |
| 확인 불가 | 1 |

**원문에 전혀 없는 주장은 없었다.**

### 9.1 T1·T3 후보 필수 조건 판정

| 후보 | 근거 | 판정 |
|---|---|---|
| T1 (Troubleshooting 오류 분류) | p078~p081 | **충족** — 공백 아닌 증상 9종(Excessive noise, Insufficient forces, Jerky movements, Output not running, Temperature, Foaming, Casting, Line impacts, Starting frequency)과 구성요소별 점검 항목이 원문에 있다 |
| T3 (Troubleshooting Annex 1A) | p078~p085 | **미충족** — 원문은 "오류 선택 → 가능 원인 범주 목록"이고 expected_result 기준값이 없다. p082~p085는 추출 불가라 완전 대조 불가 |
| T3 (Euro Bearing Case 2) | p002~p003 | **미충족** — 사건 분석 기사 형식. expected_result와 단계 번호 없음. "vibration signature"를 언급하나 정량값 없음 |

T3 2건은 §3에서 §6 부족한 근거로 이미 이동했고, 검증 결과가 그 판정과 일치한다.

### 9.2 공급사 주장 수치의 원문 위치와 귀속

| 수치 | 원문 위치 | 자릿수 | 원문이 밝힌 주장 주체 |
|---|---|---|---|
| NSK `$28,288` | p001·p002 비용표 | 일치 | NSK 자체 산정(계산식 제시) |
| NSK `3X longer life` | p001("More than 3X")·p002("3 times") | 일치 | NSK 제품 특성 주장, 독립 검증 없음 |
| FUCHS `약 $400,000/년` | HTML 본문 | 일치 | 고객 자체 보고 + FUCHS 추정 |

세 수치 모두 원문에 실제로 있고 자릿수도 맞다. 다만 어느 것도 제3자 검증 기록이 아니므로 검증된 복구 결과로 사용하지 않는다.

### 9.3 Euro Bearing 사례의 사건 요소

| 원문에 있는 것 | 원문에 없는 것 |
|---|---|
| 반복 손상("intermittent bearing failures"), 진동 감시, 초크 보어 마모, 정기 측정·재정비, 고장 중단("failures stopped") — 모두 p002 | 구체적 날짜, 수행자·부서·고객사명("Italian cold rolling operation"만), 측정값(진동 수치·마모량·수명 시간), 추적 기간 |

"정비 원장 수준 기록 없음"이라는 판정이 원문과 일치한다. 2026-09-23 보고서의 판단과도 같다.

### 9.4 검증의 오표시를 직접 재대조해 정정

검증은 `Troubleshooting.pdf`의 발행기관(DGUV), 독일어 원본(209-070, 2014년 1월), BGI/GUV-I 5100 후속 관계를 "추출 범위에서 확인되지 않음"으로 표시했다. 추출 텍스트를 다시 대조한 결과 **세 요소 모두 원문에 있다.**

| 요소 | 확인된 위치 |
|---|---|
| 발행기관 | p002 `German Social Accident Insurance e.V. (DGUV)`, p005 `Deutsche Gesetzliche Unfallversicherung" (DGUV)` |
| 독일어 원본·판 | p002 `English translation of the German DGUV Information 209-070 (BGI/GUV-I 5100) of 01/2014` |
| BGI/GUV-I 5100 후속 | p005 `… is the English translation of the German information BGI/GUV-I 5100 …, now listed as DGUV Information 209-070` |
| 영문판 발행 | p003 `DGUV Information 209-071 E March 2015` |

즉 **부록의 문서 정체 주장이 맞고, 검증의 "확인되지 않음" 표시가 틀렸다.** 양쪽을 모두 남긴다.

### 9.5 이용 조건

원문 p005에 번역·책임 관련 면책 고지가 있고 p002에 `www.dguv.de/publikationen` 안내가 있으나, **복제·재배포를 허용하는 명시적 이용 조건은 확인되지 않았다.** DGUV 발행 문헌이라는 이유로 이용 권한을 추정하지 않는다. §7 담당자 확인 대상이다.

### 9.6 추출 불가로 남은 검증 한계

| 파일 | 페이지 | 영향 |
|---|---|---|
| Troubleshooting.pdf | p082~p085 (4쪽) | Annex 1A의 T3 근거를 끝까지 대조하지 못함 |
| shell-sls-whitepaper-02-v7edited.pdf | p009 (1쪽) | Shell의 이슈 설명 대조 불가 |

내용을 추정하지 않았다.

