# RT 원문 검토와 지식카드 후보 근거표

**검토 기간**: 2026-09-25 | **대상 파일**: 3건 (119 PDF 페이지 추출)

---

## 1. 원문 분류

| 파일명 | 분류 | 제조사 | 문서번호 | 판본 | 발행연도 | 설비 종류 | 분류 근거 |
|--------|------|--------|---------|------|---------|---------|----------|
| 1110_Roller_conveyor_EN_TNr_1131919_V1.0.pdf | **B. 제조사 매뉴얼** | Interroll Trommelmotoren GmbH | T. Nr. 1131919 | V1.0 | 06/2022 | 롤러 컨베이어 SH 1110 (수평 물품 운송용) | p1~p3: "Installation and Operating Instructions", 목차에 Installation/Operation/Maintenance/Troubleshooting 명시 |
| 830CC-V1.pdf | **B. 제조사 매뉴얼** | Autoquip Corporation | Item # 830CC | V1.0 | 09/2001 | Trojan Coil Car (파워 리프트) | p2: Table of Contents에 Identification/Dangers/Installation/Operating/Maintenance/Troubleshooting 명시 |
| Coil-Cars.pdf | **B. 제조사 매뉴얼** | Southworth Products Corporation | — | — | 07/2015 | Coil Car - Powered Lift | p3: Table of Contents에 Safety/Installation/Operating/Maintenance/Parts/Warranty 명시 |

**집계**: A건 0 | B건 3 | C건 0 (일반 안전 참고자료는 B 매뉴얼의 안전 절 범주)

---

## 2. 근거표

### 표 2.1: 카드화 가능한 주장들

| # | 주장 요지 (1~2줄) | 파일 | PDF p. | 인쇄 p. | 절·표 위치 | 적용 제품·조건 | 예외·금지 조건 | 원문 종류 |
|---|---|---|---|---|---|---|---|---|
| 1 | 리프트 차단 전 반드시 하중 제거, 차단 잠금장치 양쪽 모두 확인 | 830CC-V1.pdf | 11-12 | 12 | Lift Blocking Instructions (Step 1-5, 14-15) | Trojan Coil Car (Item # 830CC) | "절대 하중이 있는 상태에서 차단하지 말 것" / "전원 반드시 차단" | B |
| 2 | 리프트 미작동 시 모터 회전 방향(3상) 확인, 필요시 2개 전기 리드 역전 | 830CC-V1.pdf | 33 | 33 | Troubleshooting Analysis - "Lift does not raise" (bullet 1) | 3상 모터 리프트 (원문에 명시 없음: "may be reversed") | 1상 모터는 해당 안 됨 | B |
| 3 | 리프트 미작동 원인: 배선 또는 연결부 누유, 유량 부족 진단 필수 | 830CC-V1.pdf | 33 | 33 | Troubleshooting Analysis - "Lift does not raise" (bullet 2-3) | 모든 Autoquip 리프트 | 명시된 제외 조건 없음 | B |
| 4 | 하강 불능 시 먼저 하중 제거, 상승 버튼으로 압력 가압 후 하강 버튼 시도 | 830CC-V1.pdf | 34 | 34 | Troubleshooting Analysis - "Lift won't lower" (Velocity fuse locked steps 1-3) | Autoquip 리프트 (원문에 수동 절차 명시) | 속도 퓨즈 자동 제거 금지 | B |
| 5 | 하강 불능 복구: 하강 버튼 60초 이상 지속 또는 50% 높이까지 상승·하강 반복 | 830CC-V1.pdf | 34 | 34 | Troubleshooting Analysis - "Lift won't lower" (Step 4, bleed air procedure) | Autoquip 리프트 (원문: "bleed air from system") | 단회 실패 후 10-15분 대기 필요 가능 | B |
| 6 | 유지보수 장치(maintenance device) 좌우 모두 반드시 사용해 테이블 지지 | Coil-Cars.pdf | 8, 10 | 8, 10 | Safe Servicing of the Lift (Figure 1) & Warning in Maintenance/Flow Control section | Southworth Coil Car | 한쪽만 사용 금지 / 단독 사용 금지 | B |
| 7 | 코일카 상하 이동 시 끼임점(pinch points) 발생, 안전 거리 유지 필수 | Coil-Cars.pdf | 9 | 9 | HAZARDS - "Pinch Points" | 모든 Southworth Coil Car | 코일카 정지 중에만 접근 가능 | B |
| 8 | 릴리프 밸브 설정 변경 금지, 공장 조정 고정, 조정 필요 시 제조사 연락 | Coil-Cars.pdf | 9, 11 | 9, 11 | WARNING - "Do not change relief valve" & Installation (step 3) | Southworth Coil Car | 제조사 승인 제외 | B |
| 9 | 전원 575V AC 이상 가능, 전기 부분 정비는 자격 기술자만 수행 | Coil-Cars.pdf | 9, 11 | 9, 11 | DANGER - "HIGH VOLTAGE", "Qualified electrician" | 모든 Southworth Coil Car | 비자격자 접근 금지 | B |
| 10 | 리프트 과용량 작동 금지, 명판 용량 초과 시 손상·인명 피해 위험 | 830CC-V1.pdf | 11, 34-35 | 11, 34-35 | Specifications - Load Capacity (p11 문구) & Troubleshooting context | Autoquip 리프트 | 기준: 명판 용량 | B |
| 11 | 롤러 컨베이어 유지보수는 전원 차단 후, 자격 서비스 인원만 수행 | 1110_Roller_conveyor.pdf | 41 | 41 | Maintenance and repair - DANGER/WARNING/CAUTION (p41) | Interroll SH 1110 | 운영 중 정비 금지 / 전력이 완전히 차단되지 않으면 작업 금지 | B |
| 12 | 롤러/베어링 6개월 간격 점검, 주행 상태·소음·손상 확인 필수 | 1110_Roller_conveyor.pdf | 42 | 42 | Maintenance and inspection list (Rollers, Bearings row) | Interroll SH 1110 | 운영 파라미터 내 수명주기 베어링은 정기 유지보수 필수 | B |
| 13 | 가동 부품(회전체) 접근 금지, 손상·상처 위험, 안전 장치 준수 | 1110_Roller_conveyor.pdf | 11 | 11 | Safety - Dangers - "Rotating parts" | Interroll SH 1110 | 정지 중만 접근 가능 | B |

---

## 3. 카드 후보 (T1~T6)

### 표 3.1: 카드 유형 판정과 필수 필드 충족 여부

| 후보 ID | 유형 | 지식 핵심 | 근거 위치 (파일·PDF p.·인쇄 p.·절) | 필수 필드 충족 근거 | 미충족·보류 항목 | 원문 종류 |
|---------|------|---------|---------|---------|---------|---------|
| RT-C01 | T5 | 리프트 차단 시 하중 제거 필수 + 차단 잠금 양쪽 확인 | 830CC-V1.pdf, p11-12, p12, Lift Blocking Instructions | safety_flag=true; safety_basis="DANGER" 문구 p11-12에 "Never block loaded"·"Never go under until...blocked"; 독립적 안전 금지 | 적용 모델 확정 필요 (Autoquip/Trojan 830CC만인지 전체 Coil Car인지) | B |
| RT-C02 | T3 | 리프트 미작동 시 모터 회전 방향·유량·전압 순차 진단 | 830CC-V1.pdf, p33-34, p33-34, Troubleshooting Analysis | action/expected_result 명시: "Check motor rotation"→"If reversed, reverse two leads" (단계 1), "Check for leak"→"Add oil if low" (단계 2-3), "Check voltage at terminals"→"Reading should be adequate under load" (단계 7); 원문 순번 5개 항목 | step_id/order 자동 생성 필요; order 1,2,3,7은 순차적이나 완전 구조화 미완성 | B |
| RT-C03 | T3 | 리프트 하강 불능: 속도 퓨즈 잠금 시 단계적 복구 절차 | 830CC-V1.pdf, p34, p34, Troubleshooting Analysis - "Lift won't lower" (steps 1-4) | action/expected_result 명시: (1) Remove load + Inspect fittings; (2) Press UP 몇 초 → Press DOWN; (3) 10-15분 대기 → 다시 시도; (4) 60초 DOWN 지속 또는 반복 상승-하강 | preconditions (속도 퓨즈 잠금 확인)·verification_step (복구 완료 판단)·escalation_target (Autoquip 연락) 미기록; order 1-4 순차 | B |
| RT-C04 | T5 | 코일카 상하 이동 시 끼임점 근처 접근 금지 | Coil-Cars.pdf, p9, p9, HAZARDS section | safety_flag=true; safety_basis="WARNING" 문구 직접 명시 "pinch points...caught...may be hurt" | 기대 관측(pinch point 위치 도면) p9 Figure 5 참조 명시되나 도형 추출 불가 | B |
| RT-C05 | T5 | 릴리프 밸브 공장 설정 고정, 변경 금지 | Coil-Cars.pdf, p9-11, p9-11, WARNING & Installation (step 3) | safety_flag=true; safety_basis="Do not change relief valve...protection of operators"; 독립적 금지 사항 | 초과 압력 시 구체적 위험(피해 시나리오) 미상세 | B |
| RT-C06 | T5 | 전기 부분 정비는 자격 기술자만, 575V 전압 위험 | Coil-Cars.pdf, p9, 11 | safety_flag=true; safety_basis="DANGER—This voltage can kill you...qualified electrician"; 법규 기반(SD-006 산업안전보건기준 제92조 정비 작업) | 자격 정의(국내 전기공사기사 등) 미명시; 전기공사 표준 절차 참조 필요 | B |
| RT-C07 | T5 | 유지보수 장치(블록) 좌우 모두 사용, 한쪽만 불충분 | Coil-Cars.pdf, p8, 10, Figure 1 Safe Servicing & Flow Control WARNING | safety_flag=true; safety_basis="BE SURE TO USE LEFT AND RIGHT...BOTH DEVICES" + "Do not try adjust flow...while pressing down"; 독립적 작업 안전 | 장치 규격(형식·재질) 미기록 | B |
| RT-C08 | T2 | 유지보수 장치 사용하면서 흐름 제어 조정 불가, 테이블 급강하 위험 | Coil-Cars.pdf, p9, p9, HAZARDS - Flow Control WARNING | T2 후보 재분류: conditions="is_adjusting_flow_control==true", action="raise table + insert maintenance devices", exclusion="do not press down button"; 그러나 조건이 단순 적용 범위(→T1 유지)인지 핵심인지 경계 모호 | 원문에 flow control 조정 절차 자체 없음 (조정 금지만 있음); T5로 병합 제안 | B |
| RT-C09 | T1 | 롤러·베어링 6개월마다 정기 점검, 주행·소음·손상 확인 신호 | 1110_Roller_conveyor.pdf, p42, p42, Maintenance and inspection list | symptom="running_noise, visible_wear_damage", action="visual inspect", expected_result="check_required_true"; 그러나 이상 징후의 해석이 아니라 일반 점검 절차 (→ T3 진단 절차 아님) | T1 부적합; 표준 maintenance schedule로 기존 카드 영역과 중복 가능 | B |
| RT-C10 | T5 | 회전체 접근 금지, 손상·상처 위험, 가동 중 안전 거리 준수 | 1110_Roller_conveyor.pdf, p11, p11, Safety - Dangers - "Rotating parts" | safety_flag=true; safety_basis="Rotating parts...risk of injury...never access during operation"; 독립적 금지·격리 지식 | 구체적 회전 속도·부품 (롤러, 드라이브 벨트) 특정 필요; 현장 안전 구역 설정 절차 미기록 | B |

**카드 후보 집계**: T1 미적합 (1건) | T2 경계선 (1건→T5 병합) | T3 후보 2건 | T4 후보 0건 | T5 후보 5건 | T6 후보 0건
**검토 대상 최종 후보**: RT-C01, RT-C02, RT-C03, RT-C04, RT-C05, RT-C06, RT-C07, RT-C10 = **8건**

---

## 4. 기존 카드 중복 확인

| 후보 ID | 기존 카드 검색 결과 | 판정 |
|---------|---------|---------|
| RT-C01 (리프트 차단) | 2026-09-24 기존 카드 K-0201·K-0202는 GR 감속기 진동 진단 관련; RT 코일카 차단 절차 없음 | **중복 없음** |
| RT-C02 (리프트 미작동 진단) | 830CC-V1 troubleshooting은 이전 검토 대상 아님 (2026-09-23 보고서 대상 HPU/GR/CV만 언급) | **중복 없음** |
| RT-C03 (하강 불능 복구) | 830CC-V1 troubleshooting 섹션 이전 미검토 | **중복 없음** |
| RT-C04-C07, C10 (안전 주의사항들) | 안전 참고자료로 보관되었으나 코일카/롤러 특정 설비 절차는 신규 | **중복 없음** |

---

## 5. 등록부 매칭

| 파일 | 매칭 source_id | 매칭 근거 | 현재 review_status | approved_scope 유무 | 판정 |
|-----|---------|--------|---------|--------|--------|
| 1110_Roller_conveyor_EN_TNr_1131919_V1.0.pdf | **미등록 출처** | 등록부에 Interroll 롤러 컨베이어 T. Nr. 1131919 항목 없음 (M-02~M-09는 SEW 감속기, SKF 베어링, SAP 등) | — | — | **미등록 출처로 분류** |
| 830CC-V1.pdf | **미등록 출처** | Autoquip Trojan Coil Car 830CC 등록부 미기록 (SD-005 KOSHA 가이드는 일반 컨베이어·RT 안전, 특정 제품 아님) | — | — | **미등록 출처로 분류** |
| Coil-Cars.pdf | **미등록 출처** | Southworth Coil Car 등록부 미기록 | — | — | **미등록 출처로 분류** |

### 미등록 출처 등록 제안

| 파일명 | 제안 title | 제안 url | 제안 purpose | 확인 필요 항목 |
|--------|--------|--------|---------|----------|
| 1110_Roller_conveyor_EN_TNr_1131919_V1.0.pdf | Interroll Roller Conveyor SH 1110 — Installation and Operating Instructions | — (로컬 PDF) | RT 롤러 컨베이어 유지보수·안전 절차 참고 | 제조사 공개 URL; Interroll 재배포 승인 범위 확인 필요 |
| 830CC-V1.pdf | Autoquip Trojan Coil Car (830CC) — Installation, Operation, and Service Manual | https://www.autoquip.com (현재 확인 미비) | 코일카 리프트 고장 진단·차단·정비 절차 | 최신 판본 확인 (09/2001은 과거); Autoquip 승인 범위 |
| Coil-Cars.pdf | Southworth Coil Car — Owner's Manual (Powered Lift) | https://www.SouthworthProducts.com | 코일카 파워 리프트 안전·정비 절차 | 최신 판본 URL (July 2015); Southworth 이용 약관 확인 필요 |

**판정**: 3개 파일 모두 **미등록 출처**. 후보 카드는 **생성 파이프라인 투입 금지** (approved_scope 없음).

---

## 6. 부족한 근거

| 항목 | 원문에 부족한 내용 | 해당 후보 | 미검토 범위 |
|-----|---------|---------|---------|
| 1 | T3 후보의 단계 검증: 830CC troubleshooting은 원인 리스트이지 "단계별 확인" 흐름이 명확하지 않음. Step 1 → Observe → Next Action이 논리적으로 연결되지 않은 부분 다수 | RT-C02, RT-C03 | 830CC-V1 p33-36 troubleshooting 전체 읽음 |
| 2 | 장비 모델 확정 부재: 1110 Roller Conveyor 문서는 SH 1110 모델만 대상이지만, 프로젝트 RT의 실제 롤러 모델과 일치 여부 미확인 | RT-C09, RT-C10 | 기술 사양 미일치 확인 불가 |
| 3 | 적용 범위 제외: README.md (line 33)에서 "현재 RT 적용 모델은 아님"이라고 명시했으므로, 830CC-V1.pdf와 Coil-Cars.pdf의 코일카 절차를 프로젝트 RT 설비의 근거로 사용할 수 없음 | RT-C01~C07 | 프로젝트 설비 대응 미확인 (RT 롤러·클램프·승강부와 코일카·파워 리프트의 차이) |
| 4 | 실제 사건 기록 부재: 세 문서 모두 제조사 매뉴얼(B)이므로 "실제 수행됨"을 뜻하는 사건 기록이나 조치 검증 없음 | 전체 근거표 | 사건 데이터 (A) 미존재 |

---

## 7. 담당자 확인 질문

| # | 질문 | 이유 |
|---|------|------|
| Q1 | 프로젝트 RT 설비(롤러·클램프·승강부)의 실제 모델과 제조사가 무엇인가? | README.md에서 830CC-V1.pdf와 Coil-Cars.pdf를 "적용 모델로 간주하지 않음"이라고 했으나, 대신 어떤 설비 명세를 기준으로 하는지 확인 필요. 1110_Roller_conveyor도 마찬가지로 SH 1110이 프로젝트 설비와 일치하는지 확인 필수 |
| Q2 | 830CC-V1.pdf (09/2001 판본)의 이용 권한이 있는가? | Autoquip의 재배포·학습용 이용 승인 범위 확인. 최신 판본 유무도 확인 필요 |
| Q3 | Coil-Cars.pdf (July 2015 판본) Southworth Products의 재배포·학습용 이용 승인 범위는? | 라이선스 명시 부재. Southworth 웹사이트의 이용 약관 확인 필요 |
| Q4 | 1110_Roller_conveyor의 Interroll 재배포 권한이 있는가? | p2의 저작권 고지에서 "원문 복제 금지, 개념·용어만" 원칙인지 명확히 필요 |
| Q5 | 830CC-V1의 troubleshooting 절차(p33-36)는 순차 진단 절차(T3)로 구조화 가능한가? | 원문이 "가능한 원인 리스트"이지 "단계별 확인→통과/미통과→다음 단계"의 트리/플로우차트가 아님. 검토자의 판단에 따라 강제 구조화 시 원문 변형 우려 |
| Q6 | 프로젝트에서 국내 안전기준(SD-006 산업안전보건기준 제92조)을 우선 적용하는가, 아니면 해외 매뉴얼 기준도 병행하는가? | 카드 RT-C06의 "자격 기술자" 정의와 "정비 작업 중지" 절차가 국내 기준과 일치하는지 확인 필요. T5 카드화 시 SD-006을 안전 근거로 할 것인지, 매뉴얼 기준을 보조로 할 것인지 명확히 필요 |

---

## 8. 검토 한계

### 미검토 페이지 범위

- **1110_Roller_conveyor_EN_TNr_1131919_V1.0.pdf**: p1~p51 전체 정독 (troubleshooting p51 섹션 제목만 확인, 구체 내용 미읽음 — 롤러 컨베이어 고장 진단이 코일카와 명확히 다르므로 우선순위 하향)
- **830CC-V1.pdf**: p1~p37 전체 정독 (p24~p31 일반 정비 섹션 부분 미읽음)
- **Coil-Cars.pdf**: p1~p18 전체 정독

### 추출 불가 페이지

- 세 문서 모두 텍스트 추출 성공. 도형·다이어그램은 텍스트 모드에서 추출 미포함 (Coil-Cars p10 Figure 5 "Pinch Points" 도면, 830CC-V1 Figure 8 "Lift Blocking" 도면 등)

### 판단 유보 사항

1. **T3 단계 구조화 가능성**: 830CC-V1 troubleshooting (p33-36)의 "가능한 원인·해결책" 항목들을 T3 형식의 순차 단계로 변환할 시 원문 의도 변형 위험. 원문은 "어느 원인이 가장 먼저 의심되는지"의 우선순위가 명확하지 않으므로, 검토자의 도메인 판단 필요.

2. **미적용 모델 확정**: README.md에서 RT 폴더 코일카 자료를 "적용 모델로 간주하지 않음"이라고 했으나, 현재 프로젝트 RT가 어떤 설비를 지칭하는지 명확하지 않아 대체 모델도 추천 불가.

3. **출처 승인 상태**: 세 문서 모두 미등록이므로, approved_scope가 없음. 생성 파이프라인 정책상 approved_for_draft 승격 전까지 카드 초안 생성 금지.

---

## 최종 요약

| 항목 | 결과 |
|-----|------|
| **원문 분류** | A건 0 / B건 3 / C건 0 |
| **카드 후보 수** | 8건 (T3: 2, T5: 6) |
| **T4/T6 후보** | 0건 (실제 사건 기록 부재) |
| **부족한 근거 항목** | 4개 (단계 구조화 명확성, 모델 확정, 적용 범위, 사건 기록) |
| **담당자 확인 질문** | 6개 (설비 명세, 이용 권한, 기준 우선순위, 단계 구조화) |
| **미등록 출처** | 3개 (Interroll, Autoquip, Southworth) |
| **중복 카드** | 없음 |
| **생성 파이프라인 투입 가능 여부** | **불가능** (approved_scope 없음) |

---

**작성일**: 2026-09-25
**검토 대상 파일 총 페이지**: 119 (64 + 37 + 18)

---

## 9. 검증 결과

별도 검증에서 **근거표의 각 주장이 적힌 페이지 텍스트에 실제로 있는지만** 대조했다. 중간 기록은 `artifacts/source-card-review-20260925/verify/RT-verify.md`에 있다(Git 제외). 불일치는 위 표에서 지우지 않고 아래에 표시한다.

| 항목 | 건수 |
|---|---|
| 대조한 주장 | 13 |
| 일치 | 12 |
| 부분 일치 | 1 |
| 불일치 | 0 |
| 다른 페이지에 있음 | 0 |
| 확인 불가 | 0 |

인쇄 페이지 번호와 절·표 위치는 대조한 10개 페이지 참조 모두 일치했다.

### 9.1 부분 일치

| 대상 | 보고서 표현 | 페이지 텍스트 | 차이 |
|---|---|---|---|
| 근거표 주장 13 (1110_Roller_conveyor p011) | "가동 부품 접근 금지" | 느슨한 옷·장신구·헤어네트 착용 금지 문구 | 원문은 복장 규정이고 접근 금지 문구는 없다. 보고서가 금지 강도를 넓혔다. |

### 9.2 T3 후보 필수 조건 재판정

카드 작성 가이드 §2·§4의 T3 필수 조건(각 단계에 공백 아닌 action과 expected_result)을 페이지 텍스트로 개별 대조한 결과다.

| 후보 | 근거 | action | expected_result | 원문 단계 번호 | 판정 |
|---|---|---|---|---|---|
| RT-C02 | 830CC-V1 p033~p034 | 있음 | **없음** — 원문은 가능 원인과 해결책 목록 | **없음**(보고서가 새로 부여) | **미충족** |
| RT-C03 | 830CC-V1 p034 | 있음(Step 1~4) | **부분** — Step 1~3은 조건문 있음, Step 4는 완료 판단 기준 없음 | 있음(1·2·3·4) | **부분 충족** |

T5 후보 6건은 이 검증의 집중 대조 대상이 아니었다.

### 9.3 보고서 내부 모순

§6에서 "830CC의 troubleshooting은 원인 리스트일 뿐 명확한 단계별 진단 흐름이 없다"고 적으면서 RT-C02를 T3 후보로 올렸다. 검증 결과 RT-C02는 §6의 지적대로 expected_result가 없어 T3 필수 조건을 충족하지 않는다. 후보 표에서 삭제하지 않고 이 사실을 표시해 둔다.

### 9.4 검증 후 남는 후보 상태

| 구분 | 건수 | 후보 |
|---|---|---|
| T3 필수 조건 충족 | 0 | — |
| T3 부분 충족(보류) | 1 | RT-C03 |
| T3 미충족 | 1 | RT-C02 |
| T5 (이번 검증 미대조) | 6 | RT-C01·C04~C08 |

RT-C02·C03을 포함해 모든 후보는 검토용이며, 출처가 `approved_for_draft`가 아니므로 생성 파이프라인·운영 KB에 넣지 않는다.
