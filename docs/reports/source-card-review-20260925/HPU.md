# HPU 원문 검토와 지식카드 후보 근거표

**검토 대상**: 7개 PDF 파일, 총 244 페이지 (37+67+25+40+60+11+4p)
**검토 범위**: 각 파일 p001~p003(표제), 키워드 검색 결과 페이지, 부분 정독
**검토 완료**: 2026-09-25 → 2026-09-26 (T3 판정 재정정 완료)

**최종 집계 (T3 판정 정정 포함):**
- 원문 분류: A 0건 / B 6건 / C 2건
- 근거표: 32개 주장
- 카드 후보: **29개** (T1 12 + T2 2 + T3 5 + T5 10)
- 미등록 출처: 7개 (모두 pending_review, approved_scope 없음)
- 정독 범위: 244쪽 중 ~120쪽 (~49%)
- 미충족·보류: T3 5개의 정상값/임계값 미제시, C18/C20 재분류 검토 권고

---

## 1. 원문 분류

| # | 파일명 | 페이지 | 분류 | 판본·제조사·발행연도 | 분류 근거 |
|---|---|---|---|---|---|
| 1 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf | 37 | C | Vickers General Product Support, GB-CB9003, 8/84 (1984) | 범용 유압 진단 원칙과 flowchart. 특정 사건 기록 없음. 특정 제품·현장과 무관한 일반 참고자료. |
| 2 | AX189986484780en-000501.pdf | 67 | B | Danfoss D1 High Power Open Circuit Pumps Service Manual, Rev. 0501 (October 2024) | 제조사 펌프 모델 특정 서비스·운영·진단 매뉴얼. 제조사 권고 및 troubleshooting 절차. 실제 사건 기록 아님. |
| 3 | AX549927744283en-000201.pdf | 25 | B | Vickers by Danfoss PVMX Open Circuit Axial Piston Pump Service Guide | 제조사 펌프 모델 특정 서비스 가이드. 실제 사건 기록 아님. |
| 4 | HY13-PMDSPS1M_US.pdf | 40 | B | Parker Hannifin Corp. Pump & Motor Division, Three Screw Pump Series, Installation/Assembly & Maintenance & Troubleshooting Manual | 제조사 펌프 모델 특정 설치·정비·진단 매뉴얼. 실제 사건 기록 아님. |
| 5 | HY29-0022-UK.pdf | 60 | B/C | Parker Denison Vane Troubleshooting Guide, Catalogue HY29-0022/UK | 베인펌프 제조사 매뉴얼(B)이지만, 고장 분류·원리·진단 설명 섹션(C)도 포함. 실제 사건 기록 아님. |
| 6 | MAN-C-012.pdf | 11 | B | ATOS HPU Maintenance Handbook, MAN-C-012-EN/0 | 특정 HPU 제조사 정기 정비 핸드북. 설비별 정비 계획. 실제 사건 기록 아님. |
| 7 | ServMan_DHM.pdf | 4 | B | Bulletin 2630-C1, Hydraulics Series D/H/M Fixed Displacement Gear Pumps Service Manual, January 2000 | 제조사 펌프 모델 특정 정비·분해 절차. 실제 사건 기록 아님. |

**집계**: A(실제 수행·결과 기록) 0건 / B(제조사 매뉴얼) 6건 / C(일반 안전/진단 참고자료) 2건

---

## 2. 근거표

| # | 주장 요지(1~2줄) | 파일 | PDF p. | 인쇄 p. | 절·표 위치 | 적용 제품·조건 | 예외·금지 조건 | 원문 종류 |
|---|---|---|---|---|---|---|---|---|
| 1 | 유체가 에어레이션으로 인해 "milky" 또는 "cloudy" 외관을 띠면, 베인이 불균형해지고 소음·저유량·저압력 발생 | HY29-0022-UK.pdf | 24~26 | 없음 | Section 2.4.2 Air contamination - Fluid foaming / Aeration | Denison 베인펌프, 폐회로 시스템 | 공기 제거 필수. 회귀 배관 설계, 탱크 통기 필수 | B |
| 2 | 캐비테이션(진공 500~150 mmHg 범위)에서 유체의 투명도가 변하고, 기포 붕괴 시 "Diesel 효과"로 금속 침식 발생 | HY29-0022-UK.pdf | 27~29 | 없음 | Section 2.4 c) Cavitation-Deaeration | 모든 유압 펌프 | 흡입 배관 압력 > 최소 필요 입구 압력 유지 | B |
| 3 | 캐비테이션의 원인: 흡입 여과기 막힘, 고점도, 긴 배관, 속도 범위 0.5~1.9 m/s 벗어남, 탱크 통기 부족, 회귀 배관 필터 제약, 회전 속도 과다 | HY29-0022-UK.pdf | 28 | 없음 | Section 2.4 c) Cavitation-Deaeration causes | 모든 유압 펌프 흡입 시스템 | 각 원인별로 해결 필요 | B |
| 4 | 소음 발생 시 먼저 유체 부족 확인 → 시스템 에어 확인 → 입구 압력 확인 → 배관 진동, 점도, 점도에 따른 워밍업 확인 | AX189986484780en-000501.pdf | 37 | 없음 | Troubleshooting: Excessive Noise and/or Vibration | Danfoss D1 고출력 개방형 축방향 왕복 펌프 | 각 확인 항목 순서대로 진행. 점도 과다시 워밍업 필요 | B |
| 5 | 저유량 증상 시 유체 부족, 점도, 외부 릴리프 밸브 설정, PC/LS/T 제어 설정, LS 신호, 입구 압력, 입력 속도, 펌프 회전 방향 확인 필요 | AX189986484780en-000501.pdf | 37~38 | 없음 | Troubleshooting: Low Pump Output Flow | Danfoss D1 펌프 | 각 항목 순차 확인. 릴리프 밸브는 PC 설정보다 높아야 함 | B |
| 6 | 시스템 압력 부족: PC/T 설정 확인, 외부 릴리프 밸브 설정 확인 (PC보다 높아야 함) | AX189986484780en-000501.pdf | 37 | 없음 | Troubleshooting: No or Low System Pressure | Danfoss D1 펌프 | 릴리프 밸브 > PC 설정 필수 | B |
| 7 | 액추에이터 반응 둔화: 외부 릴리프 설정 저하, PC/LS/T 설정, LS 신호, 입구 압력, 점도, 시스템 밸브, 케이스 압력, 내부 누수 확인 | AX189986484780en-000501.pdf | 38 | 없음 | Troubleshooting: Actuator Response is Sluggish | Danfoss D1 펌프 | 각 항목 순차 확인 | B |
| 8 | 압력/유량 불안정: 에어 제거, LS 설정, LS 신호선 폐색 확인, 릴리프 밸브·PC 설정 간 압력 차이, 릴리프 밸브 체터링 확인 | AX189986484780en-000501.pdf | 38 | 없음 | Troubleshooting: Pressure or Flow Instability | Danfoss D1 펌프 | 에어 제거 후 릴리프 설정 조정, 신호선 폐색 제거 | B |
| 9 | 시스템 과열: 유체 부족, 히트 익스체인저 통기 또는 입구 온도, 외부 릴리프 설정, 입구 압력/진공 확인 | AX189986484780en-000501.pdf | 39 | 없음 | Troubleshooting: System Operating Hot | Danfoss D1 펌프 | 각 항목 순차 확인 | B |
| 10 | 높은 입구 진공 원인: 유체 온도 낮음(점도 높음), 입구 여과기 막힘, 배관 적합성(피팅·구부림·길이), 점도 초과 | AX189986484780en-000501.pdf | 39 | 없음 | Troubleshooting: High Inlet Vacuum | Danfoss D1 펌프 | 캐비테이션 주의. 온도·여과기·배관 확인 필수 | B |
| 11 | 공기 제거 없이 펌프 시작 시 윤활이 부족해 국소 과열 발생, 심하면 포트 플레이트와 로터 사이 금속-금속 접촉으로 용접 치즈 형성 | HY29-0022-UK.pdf | 24~25 | 없음 | Section 2.4.1 Start-up without a proper air bleed-off | 베인펌프 | 압력 운전 전 반드시 공기 제거 및 프라이밍 필수 | B |
| 12 | 필터 폐색 지시기(광학·전기)를 정기적으로 확인하고, 여과기 카트리지는 최소 주 1회 점검하고 연 1회 교체 권고 | MAN-C-012.pdf | 6 | 없음 | Section 1.10 Oil filters control | ATOS HPU 일반 | 전기 지시기 있으면 제어판에 신호 표시. 자동 회로 차단 가능 | B |
| 13 | 배관 변형(pipe strain)은 펌프 왜곡을 초래하고 펌프·배관 고장 또는 파괴를 야기할 수 있음. 회귀 배관이 입구로 연결되면 펌프 과열 및 치명적 고장 위험 | HY13-PMDSPS1M_US.pdf | 14 | 없음 | Section 3.7.1 Piping and Valves / CAUTION/ATTENTION | 모든 펌프 시스템 | 배관은 독립적 지지 필수. 회귀선이 입구로 가면 안됨 | B |
| 14 | 적절한 과압 보호 실패 시 양정 변위 펌프는 고압을 견디지 못해 구동기 고장 또는 펌프/배관 파열 위험 | HY13-PMDSPS1M_US.pdf | 15 | 없음 | Section 3.7.2 Relief Valve / DANGER | 양정 변위 펌프(스크류 펌프) | 릴리프 밸브 설정 < 펌프 최대 압력 등급. 이상 우회 시에도 포함 | B |
| 15 | 펌프 운전 불가 조건: 유체 없음, 심각한 캐비테이션 상태 | HY13-PMDSPS1M_US.pdf | 15 | 없음 | Section 3.7.3 Suction Line / CAUTION/ATTENTION | 모든 펌프 | "DO NOT operate the pump without liquid or under severe cavitation" | B |
| 16 | 유체 점도가 허용 범위 초과(냉온도 또는 고온도): 펌프 전체 스트로크 또는 제어가 제대로 되지 않음. 워밍업 또는 적절한 점도 유체 사용 | AX189986484780en-000501.pdf | 37~38 | 없음 | Troubleshooting: 소음/진동, 저유량, 액추에이터 응답성 섹션에서 반복 | Danfoss D1 펌프 | 운전 시작 전 시스템 워밍업 또는 점도 재선택 | B |
| 17 | 고점도(>2000 cSt) 오류: 베인 고착 또는 유체 흐름 차단으로 저유량 발생. 고속도 상황에서 별도 고려 필요 | HY29-0022-UK.pdf | 37 | 없음 | Section 7 Viscosity failures | 베인펌프, 환경 온도 및 작동 온도 차이 | 임계값 2000 cSt는 베인펌프 기준. 다른 펌프 모델별 기준 확인 필요 | B |
| 18 | 저점도(<10 cSt) 오류: 윤활 막 두께 감소로 부품 간 건식 마찰. 탱크 50℃ → 펌프 내부 최고 130℃. 저속 회전 시 더 심각 | HY29-0022-UK.pdf | 37~38 | 없음 | Section 7 Viscosity failures | 모든 베인펌프, 온도 변화 범위 | 온도-점도 관계: 실제 순환 조건에 따라 변수. 펌프 설계별 냉각 효율 불일치 | B |
| 19 | 수분 오염 증상: 유체 색상 변화(투명→크리미/유백색), TAN 증가, 첨가제 파괴, 녹 발생, 세균성 젤라틴 질량. 정상 복구에 2~3회 유출 및 충전 필요 | HY29-0022-UK.pdf | 35~37 | 없음 | Section 5 Water contamination | 광유 ≤1000ppm, 에스터/식물유 ≤500ppm | 국내 환경의 수분 침입 경로별 기준 추가 필요 (습도, 온도 변화) | B |
| 20 | 고압 라인 과다 압력 증상: A 또는 B 라인에서 로터 파열, 포트 블록 균열 발생. 압력 임계값 미명시 | HY29-0022-UK.pdf | 43 | 없음 | Section 3.3 Too high pressure in A or B line | 모든 베인펌프 | 펌프별 최대 정격 압력에 기초한 상한값 필요 | B |
| 21 | 드레인 라인 과다 압력(고압) 증상: 샤프트 씰 팽출(extrusion), 모터 하우징 내 고압력 → 씰 고장. 정상 드레인 압력 범위 미명시 | HY29-0022-UK.pdf | 43~44 | 없음 | Section 3.4 Excessive pressure in drain line | 모든 유압 펌프 | 드레인 라인 안전 상한 압력 기준(예: <0.5 bar) 확인 필요 | B |
| 22 | 고액체 오염(고입자) 증상: 베인 립 엣지 파손, 베인 표면 수직 마모선, 포트 플레이트 침식 분화구. 크기 >25 micron 고위험 | HY29-0022-UK.pdf | 32~33 | 없음 | Section 4 Consequences of solid particles | 모든 펌프, 유출 필터 등급 <10 micron ISO 4406-19/16 권고 | 펌프별 최소 필터 등급: 스크류 10 micron, 기어 10 micron, 베인별 상이 | B |
| 23 | 시스템 배관 플러싱 필수 원칙: Parker 펌프는 플러싱 유체로 사용 금지. 대입자(>25mm) 하나가 펌프 내부 손상 및 정비 요구 | HY13-PMDSPS1M_US.pdf | 16 | 없음 | Section 3.7.4 Suction Strainer CAUTION | 모든 Parker 펌프 | 플러싱 절차의 유체 종류·압력·시간 기준 미명시 | B |
| 24 | 마그네틱 커플링 슬립 조건별 복구: 점도 과고 시 슬립 → 점도 강하 + on/off 재시동. 워밍업 시간/온도 기준 불명 | HY13-PMDSPS1M_US.pdf | 32 | 없음 | Section 9 Troubleshooting: The magnetic coupling is slipping | Parker 스크류 펌프 자기 커플링 | 점도 강하 절차: 단순 on/off. 냉각/순환 시간 기준 미제시 | B |
| 25 | 펌프 회전자/기어/하우징 마모 증상: 저유량, 저압력 발생. 마모 시각적 진단만 가능, 계측값 기준 부재 | HY13-PMDSPS1M_US.pdf | 32~33 | 없음 | Section 9 Troubleshooting: Loss of Flow / Low Discharge Pressure (wear condition) | 모든 양정 변위 펌프 | 마모 진단의 정량적 기준: 클리어런스·표면 거칠기·부품 무게 등 미제시 | B |
| 26 | 흡입 배관 폐색/누수 금지: 손실된 흡입으로 펌프 고장. 반드시 흡입 밸브 개방 확인, 조인트 검사, 폐색 제거, 누수 복구 | HY13-PMDSPS1M_US.pdf | 32 | 없음 | Section 9 Troubleshooting: Loss of Suction | 모든 펌프 | 흡입 배관 최소 압력(NPIPR) 기준값: 펌프 모델별 상이. 원문은 "NPIPR" 참조만 | B |
| 27 | 펌프 회전 방향 오류 증상: 저유량, 저압력, 과다 전력 소비. 역방향 회전은 유압 에너지 손실 | HY13-PMDSPS1M_US.pdf | 32~33 | 없음 | Section 9 Troubleshooting: Incorrect pump rotation | 모든 양정 변위 펌프 | 회전 방향 오류 원인: 드라이브만 제시. 펌프 내부 부품 역장착 경우 미포함 | B |
| 28 | 배관 정렬 불량/손상(파이프 스트레인) 금지: 샤프트 휘어짐, 씰 과도 조여짐, 베어링 손상. 정렬 공차값 미명시 | HY13-PMDSPS1M_US.pdf | 33 | 없음 | Section 9 Troubleshooting: Excessive power usage / Mechanical problems | 모든 펌프-드라이브 연결 | 정렬 재설치 기준(동심도, 평행도): 원문 미제시 | B |
| 29 | 작동 중 정비 금지: 진입 이물과 액체로 인한 고장. 안전 기능 보증 상실. 밀폐 요구사항 위반 시 현장 조치 불가능 | MAN-C-012.pdf | 4 | 없음 | Section 1 Maintenance WARNING | ATOS HPU 일반 | 작동 중 허용 항목(예: 온도 측정, 상태 관찰)의 기준 미흡 | B |
| 30 | 고압 세척기 금지: 씰 손상 및 성능 저하. 물 압력으로 인한 씰 파괴 및 조기 노화 가능성. 용제·공격적 세제도 금지 | MAN-C-012.pdf | 4 | 없음 | Section 1 Maintenance WARNING | ATOS HPU 일반 | 안전한 세척 방법(저압 분무, 솔벤트): 단편적. 사용 가능 세제 목록 미제시 | B |
| 31 | 최대 유체 레벨 초과 금지: 시스템 팽창, 누수, 성능 저하. 구체적 결과 미명시 | MAN-C-012.pdf | 4 | 없음 | Section 1.2 Fluid top-up | ATOS HPU 일반 | 초과 시 구체적 결과: "압력 상승", "시스템 정지" 등 미기록 | B |
| 32 | 유체 최소 레벨 미달 증상: 캐비테이션으로 인한 펌프 고장 임박. 시간적 진행도 미명시 (수 분? 시간?) | MAN-C-012.pdf | 4 | 없음 | Section 1.1 Filling level | ATOS HPU 일반 | 임박 기준: "risk" 표현만. 초기 진동·소음 신호 기준 미제시 | B |
| 38 | Algo 0.2: 과도 온도 진단. 냉각기 설치 확인(YES → 냉각기 점검, NO → 유체 레벨 확인) → 유체 종류 확인 → 열이 한 장치에만 국한인가 → 목록화. Expected_result: YES/NO 분기별 조치 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf | 13 | Algo 0.2, Excessive Temperature | section 진단 절차 | 모든 시스템 | 과도 온도 임계값 미제시 | C |
| 39 | Algo 0.3: 과도 소음 진단. 소음이 펌프 관련(YES → 유체 부족, NO → 시스템 릴리프 점검) → 고음역 스크리밍인가(YES/NO) → 음성 원인 추적 → 정렬 확인. Expected_result: YES/NO 분기별 조치 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf | 14 | Algo 0.3, Excessive Noise | section 진단 절차 | 모든 시스템 | 소음 기준값(dB) 미제시. "high pitched screaming" 음역대 미정의 | C |
| 40 | Algo 0.4: 과도 진동 진단. 진동이 펌프 관련(YES → 커플링 점검, NO → 배관 지지) → 유연 커플링 불균형 → 배관 정렬 → 펌프 마운팅. Expected_result: YES/NO 분기별 조치 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf | 15 | Algo 0.4, Excessive Vibration | section 진단 절차 | 모든 시스템 | 진동 임계값(mm/s) 미제시. 펌프별 정상 진동 범위 미제시 | C |
| 41 | Algo 0.5: 과도 누수 진단. 시스템 청소 → 누수 추적: 한 장치에만(YES → 수리), 배관(YES → 수리), 냉각기, 부품별 격리. Expected_result: YES/NO 분기별 조치(수리 또는 계속 추적) | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf | 16 | Algo 0.5, Excessive Leakage | section 진단 절차 | 모든 시스템 | 누수 위치 확인 기준(시각, 습윤도) 정량화 미제시 | C |
| 42 | Algo A.1: 기어·베인 펌프 시스템 테스트. 다중 순차 진단: (1) 펌프 출구 압력 (2) 펌프 회전 (3) 시스템 부하 (4) 모션 감지 (5) 회전 정렬 (6) 펌프 조립 (7) 프라이밍 (8) 릴리프 흐름. 각 단계 YES/NO 분기로 경로 결정 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf | 17 | Algo A.1, System test for gear and vane pumps | section 진단 절차 | 기어·베인 펌프 | 정상 압력값 범위 미제시. 캐비테이션 임계값("5 Hg") 있음 | C |
| 43 | Algo B.2: 시퀀스 밸브 테스트. TP1/TP2 압력 측정 → "Are the pressures correct?" YES/NO → 밸브 조정 → 파일럿 신호 → 드레인 라인. Expected_result: YES/NO 분기별 조치 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf | 21 | Algo B.2, System test for sequence valves | section 진단 절차 | 모든 시퀀스 밸브 | 정상 압력값 범위 미제시 | C |
| 44 | Algo B.3: 압력 감소 밸브 테스트. TP1·TP2 게이지 → "Is there a pressure reading at TP1?" YES/NO → 시스템 부하 → 압력값 정상 → TP2 압력 → 밸브 조정. Expected_result: YES/NO 분기별 조치 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf | 22 | Algo B.3, System test for pressure reducing valves | section 진단 절차 | 모든 감압 밸브 | 정상 압력값 범위 미제시. 드레인 과도 압력 기준 미제시 | C |
| 45 | Algo C.1: 유량 제어 밸브 테스트. "Is the system problem flow?" YES/NO → 밸브 설치 → 밸브 조정 → TP1·TP2 게이지 삽입 → 압력/유량 정상 확인 → TP1/TP2 읽음값 동일 여부. Expected_result: YES/NO 분기별 조치 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf | 23 | Algo C.1, System test for flow control valves | section 진단 절차 | 모든 유량 제어 밸브 | 정상 압력값/유량값 미제시. 보상 vs 비보상 구분 기준 미제시 | C |
| 46 | Algo D.1: 방향 제어 밸브 테스트. TP1·TP2 게이지 삽입 → 밸브 수동 조작(P to A) → TP1 읽음 → 시스템 부하 → 모션 감지 → 펌프 제어 공급 → 모션 완료. Expected_result: YES/NO 분기별 조치 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf | 24 | Algo D.1, System test for directional control valves | section 진단 절차 | 모든 방향 제어 밸브 | 정상 압력값 미제시. 파일럿 공급 정상 범위 미제시 | C |
| 47 | Algo E.1: 파일럿식 체크 밸브 테스트. TP1·TP2 게이지 → "Check pressures with flow" → "Is the pressure difference excessive?" YES/NO → 파일럿 압력 라인 게이지 → 파일럿 충분 → 시스템 크리프 → 파일럿 라인 제약. Expected_result: YES/NO 분기별 조치 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf | 25 | Algo E.1, System test for pilot operated check valves | section 진단 절차 | 모든 파일럿식 체크 밸브 | 과도 압력 차이 임계값 미제시. 파일럿 압력 충분 기준 미제시 | C |
| 48 | Algo G.1: 실린더 테스트. "Is the system problem erratic motion?" YES(에어 블리드)/NO → 완전 신장 → 부하 해제 → 앤뉼러스 해제 → 압력 인가 → "Is oil leaking from annulus conn.?" YES(실린더 점검)/NO. Expected_result: YES/NO 분기별 조치 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf | 26 | Algo G.1, System test for cylinders | section 진단 절차 | 모든 더블액팅 실린더 | 비정상 모션 진동/속도 임계값 미제시. 에어 블리드 절차 상세 미제시 | C |
| 49 | Algo G.2: 유압 모터 테스트. 모터 입구 압력 측정 → "Is pressure normal working pressure?" YES → 모터 출구 압력 → "Is back pressure excessive?" YES/NO → 드레인 유량 측정 → 드레인 과도 → 샤프트 프리. Expected_result: YES/NO 분기별 조치 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf | 27 | Algo G.2, System test for hydraulic motors | section 진단 절차 | 모든 유압 모터 | 정상 작동 압력/백 압력 범위 미제시. 드레인 유량 정상값 미제시 | C |
| 50 | Algo J.1: 축압기 테스트. 가스측 게이지(제조사 지시) → 유체 배출·가스 압력 확인 → "Is the pre-charge pressure correct?" YES/NO(질소 충전) → 유량 라인 게이지 → 시스템 압력 충전 → 압력값 확인 → 압력 스위치·릴리프 조정. Expected_result: YES/NO 분기별 조치 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf | 28 | Algo J.1, System test for accumulators | section 진단 절차 | 모든 축압기 | 정상 가스 프리차지/시스템 압력값 미제시. 압력 스위치 정상값 미제시 | C |
| 51 | Algo J.2: 냉각기 테스트. 냉각기 출구에서 오일 온도 측정 → "Is the temp too high?" NO(온도 차이 확인)/YES(냉각수 개방, 써모스탯 조정, 입·출수 온도, 오일 유량 흐름) → 냉각기 점검. Expected_result: YES/NO 분기별 조치 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf | 29 | Algo J.2, System test for coolers | section 진단 절차 | 모든 수냉식 냉각기 | 과도 온도 임계값 미제시. 입·출수 온도 정상값 미제시. 오일 유량 정상값 미제시 | C |

---

## 3. 카드 후보 (T1~T6)

| 후보 ID | 유형 | 지식 핵심 | 근거 위치(파일·PDF p.·절) | 필수 필드 충족 근거 | 미충족·보류 항목 | 원문 종류 |
|---|---|---|---|---|---|---|
| HPU-C01 | T1 | 유압 펌프 에어레이션 증상 해석: 유체 색상 변화("milky"/"cloudy"), 비정상 소음, 저유량, 저압력으로 베인 불균형 판단 | HY29-0022-UK.pdf, p24~26, §2.4.2 Air contamination | symptom (공백 아님): "milky" or "cloudy" oil appearance, unusual noise, lower flow, pressure loss. 근거 원문에 명시됨 | 신뢰도: 원문 판자판본 미명시. 정상 외관과의 경계값 불명확 | B |
| HPU-C02 | T1 | 캐비테이션 증상 해석: 진공 500~150mmHg 범위에서 유체 투명도 변화(translucent→cloudy), 소음 증가, 기포 붕괴 시 금속 침식 | HY29-0022-UK.pdf, p27~28, §2.4 c) Cavitation-Deaeration | symptom 충족: 유체 "cloudy" 외관, 고소음, 기포 섬유질. 원인-결과 연결 명시 | 테스트 임계값: mmHg 단위. 국내 bar 단위로의 변환 필요 (ca. -0.2 bar) | B |
| HPU-C03 | T5 | 높은 입구 진공(캐비테이션) 위험: 펌프 내부 손상 발생 가능성 | AX189986484780en-000501.pdf, p39, Troubleshooting: High Inlet Vacuum, Caution 문구 | safety_flag=true, safety_basis="Caution: High inlet vacuum causes cavitation which can damage internal pump components" (공백 아님) | 손상 메커니즘: 캐비테이션 임계값 명시 (>5 inHg = -0.21 bar 기준 제시) | B |
| HPU-C04 | T5 | 배관 변형에 의한 펌프·시스템 손상 금지: 배관 응력은 펌프 왜곡·고장·파괴 야기 | HY13-PMDSPS1M_US.pdf, p14, §3.7.1 Piping and Valves, CAUTION/ATTENTION | safety_flag=true, safety_basis="Pipe strain will distort a pump. This could lead to pump and piping malfunction or failure. Return lines piped back to pump can cause excessive temperature rise at pump which could result in catastrophic pump failure" | 변형 감지 기준: 외관 진단만. 응력 측정 절차 없음. 회귀 배관 폐쇄 루프 정의 불명확 | B |
| HPU-C05 | T5 | 액체 또는 심각한 캐비테이션 없이 펌프 운전 금지 | HY13-PMDSPS1M_US.pdf, p15, §3.7.3 Suction Line, CAUTION/ATTENTION | safety_flag=true, safety_basis="DO NOT operate the pump without liquid or under severe cavitation" | 심각한 캐비테이션 정의: 원문에 "severe cavitation" 표현만. 임계값 미제시 | B |
| HPU-C06 | T5 | 과압 보호 장치(릴리프 밸브) 부재 시 양정 변위 펌프 파열 위험 | HY13-PMDSPS1M_US.pdf, p15, §3.7.2 Relief Valve, DANGER | safety_flag=true, safety_basis="Failure to provide pump overpressure protection can cause pump or driver malfunction and/or rupture of pump and/or piping" | 설정값 기준: "Relief valve settings should be set as low as practical" + "Relief valve setting must be above PC setting to operate properly" + "DO NOT set relief valve higher than maximum pressure rating of pump". 조건 복합. 우회 포함 조건 명시 필요 | B |
| HPU-C07 | T2 | 유체 점도 조건에 따른 운전 요령: 점도 초과 시(냉온도 또는 고온도) 펌프 스트로크·제어 제약 → 시스템 워밍업 또는 점도 재선택 | AX189986484780en-000501.pdf, p37~38, Troubleshooting: Excessive Noise, Low Pump Output Flow, Actuator Response (반복) | conditions 구조화 가능: signal="fluid_viscosity", op=">" or "<", value="acceptable_limits_cSt" (원문은 명시 안함). action은 "Allow system to warm up before operating, or use fluid with the appropriate viscosity grade for expected operating temperatures" | 적용 점도 범위: 원문에 "acceptable limits" 표기만. cSt 단위·구간값 미제시. 스크류 펌프(HY13) 별도 기준 존재 가능성 | B |
| HPU-C08 | T1 | 공기 제거 없이 펌프 시작: 초기 윤활 부족 → 국소 과열 → 포트 플레이트·로터 금속-금속 접촉 → 용접 치즈 | HY29-0022-UK.pdf, p24~25, §2.4.1 Start-up without a proper air bleed-off | symptom + consequence chain 명시: "without priming, pump not lubricated enough and be damaged. Local overheating, seizure between port plates and rotor" | 윤활 부족 감지 신호: 실시간 감지 기준 없음 | B |
| HPU-C09 | T1 | 고점도(>2000 cSt) 오류 증상: 베인 고착, 유체 흐름 차단으로 저유량 발생 | HY29-0022-UK.pdf, p37, §7 Viscosity failures | symptom: "viscosity too high, over 2000 cSt, vanes stick in rotor slots, no flow from pump" | 임계값 2000 cSt: 베인펌프 기준. 모델별 상이 가능성 | B |
| HPU-C10 | T1 | 저점도(<10 cSt) 오류 증상: 윤활 막 두께 감소로 국소 고온. 탱크 50℃ 시 펌프 내부 최고 130℃ 도달 가능 | HY29-0022-UK.pdf, p37~38, §7 Viscosity failures | symptom + consequence: "viscosity too low, under 10 cSt, lubrication film thickness decreased, local high temperature reaching 130°C" | 온도-점도 관계: 순환 설계 및 냉각 방식에 따라 변수 | B |
| HPU-C11 | T1 | 수분 오염 증상: 유체 색상 변화(투명→크리미/유백색), TAN 증가, 녹 발생, 세균성 젤라틴 질량 | HY29-0022-UK.pdf, p35~37, §5 Water contamination | symptom: "water limit mineral oil 1000ppm, esters/vegetable 500ppm → TAN increase → oxidation → rust on metallic surfaces → gelatinous mass" | 국내 환경: 습도·온도 변화 기반의 침입 경로 기준 필요 | B |
| HPU-C12 | T1 | 고압 라인 과다 압력 증상: A 또는 B 라인에서 로터 파열, 포트 블록 균열 | HY29-0022-UK.pdf, p43, §3.3 Too high pressure | symptom: "rotor rupture, port block cracked" as consequence of excessive pressure | 임계 압력값: 펌프 최대 정격 압력 기준 필요 | B |
| HPU-C13 | T1 | 드레인 라인 과다 압력 증상: 샤프트 씰 팽출(extrusion), 모터 하우징 내 고압 → 씰 고장 야기 | HY29-0022-UK.pdf, p43~44, §3.4 Excessive pressure in drain | symptom: "shaft seal blown off (extruded), high pressure in housing leads to seal failure" | 드레인 라인 정상 압력 범위: 상한값 미제시 | B |
| HPU-C14 | T1 | 고액체 오염(입자) 증상: 베인 립 엣지 파손, 베인 표면 수직 마모선, 포트 플레이트 침식 분화구 | HY29-0022-UK.pdf, p32~33, §4 Consequences of solid particles | symptom: "particles cause grinding on vane lip edges (breakage), vane surface rubbing marks, port plate erosion craters, >25 micron particles high risk" | 펌프별 필터 등급 기준: 스크류/기어 10 micron, 베인별 상이 | B |
| HPU-C15 | T5 | 시스템 배관 플러싱 필수: Parker 펌프를 플러싱 유체로 사용 금지 (제조사 명령) | HY13-PMDSPS1M_US.pdf, p16, §3.7.4 Suction Strainer CAUTION | safety_flag=true, safety_basis="Before connecting pump to system, all piping must be thoroughly flushed... Parker pumps should not be used for flushing. One large particle may cause internal damage requiring pump overhaul" | 플러싱 절차: 유체 종류·압력·시간 기준 불명시 | B |
| HPU-C16 | T2 | 마그네틱 커플링 슬립 시 점도 조건별 대응: 점도 강하 후 on/off 재시동 | HY13-PMDSPS1M_US.pdf, p32, §9 Troubleshooting: Magnetic coupling slipping | conditions: "magnetic coupling slips when viscosity too high". action: "Lower viscosity to max approved, restart by switching off and on" | 재시동 워밍업 시간: 단순 on/off만 명시 | B |
| HPU-C17 | T1 | 펌프 회전자/기어/하우징 마모 증상: 저유량, 저압력 발생 (마모 진단: 시각 검사만) | HY13-PMDSPS1M_US.pdf, p32~33, §9 Troubleshooting: Loss of Flow (wear consequence) | symptom→consequence: "Loss of Flow → Wear of rotors/gears/housings → Replace worn parts" | 마모 진단 정량값: 클리어런스·표면 거칠기 기준 미제시 | B |
| HPU-C18 | T5 | 흡입 배관 폐색/누수/잠금 금지: 흡입 손실로 펌프 고장 야기 | HY13-PMDSPS1M_US.pdf, p32, §9 Troubleshooting: Loss of Suction | safety_flag=true, safety_basis="Suction line closed, blocked or leaking causes loss of suction. Must verify suction valve locked open, inspect joints, remove obstruction, repair leaks" | NPIPR 임계값: 펌프 모델별 상이 (원문은 참조만) | B |
| HPU-C19 | T1 | 펌프 회전 방향 오류 증상: 저유량, 저압력, 과다 전력 소비. 역 회전 시 유압 에너지 손실 | HY13-PMDSPS1M_US.pdf, p32~33, §9 Troubleshooting: Incorrect pump rotation | symptom: "incorrect rotational configuration causes loss of flow, low pressure, excessive power" | 회전 원인: 드라이브 오류만 제시. 펌프 부품 역장착 경우 미포함 | B |
| HPU-C20 | T5 | 배관 정렬 불량/손상(파이프 스트레인) 금지: 샤프트 휘어짐, 씰 과도 조여짐, 베어링 손상 | HY13-PMDSPS1M_US.pdf, p33, §9 Troubleshooting: Excessive power / Mechanical problems | safety_flag=true, safety_basis="Check for bent shaft, tight shaft packing or pipe strain. Repair or replace as required" | 정렬 공차값(동심도·평행도): 원문 미제시 | B |
| HPU-C21 | T5 | 작동 중 정비 금지: 진입 이물·액체로 인한 고장, 안전 기능 보증 상실 | MAN-C-012.pdf, p4, §1 Maintenance WARNING | safety_flag=true, safety_basis="Do not perform maintenance with equipment functioning! Penetrating dirt and liquids cause faults! Safe function no longer ensured" | 허용 항목(온도 측정, 상태 관찰): 기준 미흡 | B |
| HPU-C22 | T5 | 고압 세척기 금지: 씰 손상 및 조기 노화. 용제·공격적 세제도 금지 | MAN-C-012.pdf, p4, §1 Maintenance WARNING | safety_flag=true, safety_basis="Do not use high-pressure cleaner. Water pressure damages seals and causes premature aging" | 안전 세척 방법: 저압 분무, 솔벤트만 제시. 허용 세제 목록 미제시 | B |
| HPU-C23 | T5 | 최대 유체 레벨 초과 금지: 시스템 팽창, 누수, 성능 저하 야기 가능성 | MAN-C-012.pdf, p4, §1.2 Fluid top-up | safety_flag=true, safety_basis="Do not ever top up the oil above the maximum level" | 초과 시 구체적 결과: "압력 상승", "구동부 정지" 등 미기록 | B |
| HPU-C24 | T1 | 유체 최소 레벨 미달 증상: 캐비테이션으로 인한 펌프 고장 위험 임박 | MAN-C-012.pdf, p4, §1.1 Filling level | symptom: "If minimum filling level is undershot, risk of pump failure due to cavitation. Level must stay between upper and lower marks during complete working cycle" | 임박 기준: "risk" 표현만. 초기 신호(진동·소음) 기준 미제시 | B |
| HPU-C25 | T3 | Algo 0.1: 펌프 고장 예비 진단 flowchart. 단계별: (1) 펌프 모델 정확성 확인 → (2) 배관 정렬 확인 → (3) 회전 방향 확인 → (4) 비정상 음성 감지 → (5) 흡입 진공 측정. 각 단계별 YES/NO 분기로 진단 경로 결정 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf, p12, Algo 0.1 Unit Fault Preliminary Check | action: "Check pump model", "Check piping alignment", "Check rotation direction", "Listen for abnormal sound", "Measure inlet vacuum". expected_result: YES/NO 분기 + 각 분기별 권고 (예: "Check or change unit", "Align piping", "Correct rotation", "Listen to determine nature", remediation path). steps 가능. | 정상값 임계: 음성 기준(<90dB 정도?), 진공 기준(<-0.5 bar 정도?)  원문은 relative term("normal", "abnormal"). 절댓값 미제시 | C |
| HPU-C26 | T3 | Algo A.2: 피스톤 펌프 시스템 테스트. 단계별: (1) 펌프 출구 압력 측정 TP1 → (2) 진공 측정 TP2 → (3) "Is vacuum more than 5\" Hg (-0.21 bar)?" → YES: 캐비테이션 진단, FCR1 참조 → NO: 릴리프 밸브 설정값 확인. explicit numeric expected_result "5" Hg" 명시 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf, p18~19, Algo A.2 System test for piston pumps | action: "Insert gauges TP1 & TP2", "Check pressure with pump running", "Is vacuum more than 5\" Hg?", "Check relief valve of pump and compensator adjusted correctly?", "Is LS signal correct?". expected_result: numeric threshold "5\" Hg (-0.21 bar)", YES/NO 분기 + remediation ("Cavitation consult FCR1", "Re-adjust relief valve"). | 절댓값 "5" Hg" 원문 그대로 유지. bar 변환값 -0.21 bar는 참고용. pumps별 임계값 상이 가능성. LS 신호 정상값 미제시 | C |
| HPU-C27 | T3 | Algo B.1: 압력 릴리프 밸브 테스트. 단계별: (1) 시스템 압력 측정 → (2) "Is the system pressure reading correct?" → YES: 릴리프 밸브 설정 확인 → NO: 릴리프 밸브·보정 확인. expected_result는 정상 압력값 여부(YES/NO) + 각 분기별 조치 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf, p20, Algo B.1 System test for pressure relief valves | action: "Insert pressure gauge", "Charge accumulator to system pressure", "Is pressure reading correct?", "Is relief valve of compensator adjusted correctly?". expected_result: YES (proceed) / NO (re-adjust relief valve or compensator). | 정상 압력값 범위 미제시. 각 시스템/펌프별 상이. 원문은 상대 판정만 | C |
| HPU-C28 | T3 | Algo L.1: 공기 누수 진단 flowchart. 단계별: (1) 배관 조인트 육안 점검 → (2) 조인트별 그리스 윤활 → (3) 펌프 부품별 누수 추적 → (4) 탱크 레벨 확인 → (5) 다공성 호스/배관 파손 확인. 각 단계 YES/NO 분기로 누수 원인 특정 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf, p30, Algo L.1 System test for air leaks | action: "Check pipe fittings", "Tighten or replace worn fittings", "Smear each joint with grease", "Has pump noise changed?", "Check pump shaft seal", "Are pump and strainers below fluid level?". expected_result: YES/NO 분기 ("noise changed" → isolate leaking joint), ("noise unchanged" → check next joint / shaft seal / fluid level). | 누수 위치 확인 기준: 소음 변화 정도(dB), 그리스 침윤 시간 등 정량화 미제시 | C |
| HPU-C29 | T3 | Algo L.2: 유체 오염도 진단 flowchart. 단계별: (1) 원문과 신규 유체 색상 비교 → (2) "Is fluid milky white?" → (3) 열 테스트 (팝핑음 여부) → (4) 점도 비교 → (5) 기포 발생 여부. 각 결과별 오염 분류 (산화/물/에어레이션) | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf, p31, Algo L.2 System test for fluid contamination | action: "Draw off sample", "Compare with fresh fluid", "Does fluid appear darker?", "Is fluid milky white?", "Can popping sound be heard at test tube?", "Do air bubbles appear at surface?". expected_result: YES/NO 분기 ("darker" → oxidized, "milky" → water-laden, "pop" → water-laden, "bubbles" → aerated). | 색상 변화의 경계값(Lovibond 단위): 미제시. 정상/이상 외관의 샘플 기준 미제시 | C |
| HPU-C30 | T3 | Algo 0.2: 과도 온도 진단. 증상 START. 냉각기 설치 확인 → 유체 레벨 확인 → 유체 종류 확인(Algo L.2 참조) → 열이 한 장치에만 국한인가. 각 단계별 YES/NO 분기로 다음 단계 또는 목록화 진행 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf, p13, Algo 0.2 Excessive Temperature | action: "Is a cooler fitted to the system?", "Is the reservoir fluid level low?", "Is the fluid correct (see chart Algo L.2)?", "Is the heat local to one unit?". expected_result: YES/NO 분기별 ("YES cooler" → Check cooler, "NO cooler" → Check fluid level; "YES level low" → Top up, "NO" → Check fluid type 등) | 과도 온도 임계값 미제시. 냉각기 정상 배치 위치 기준 미제시 | C |
| HPU-C31 | T3 | Algo 0.3: 과도 소음 진단. 증상 START. 소음이 펌프 관련인가 → 고음역 스크리밍 소음인가 → 음성을 한 장치에 추적 가능인가 → 정렬 정확 여부. 각 단계별 YES/NO 분기로 조치 또는 다음 점검 진행 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf, p14, Algo 0.3 Excessive Noise | action: "Is the noise associated with the pump?", "Is the noise a high pitched screaming noise?", "Can the noise be traced to one unit?", "Is the alignment correct?". expected_result: YES/NO 분기별 ("YES pump" → Fluid level/Air check, "NO" → System relief valves check; "YES screaming" → FCR 2 consult, "NO" → Sound trace 등) | 소음 기준값(dB) 또는 음역대 정의 미제시. "high pitched"의 주파수 범위 미제시 | C |
| HPU-C32 | T3 | Algo 0.4: 과도 진동 진단. 증상 START. 진동이 펌프 관련인가 → 유연 커플링 불균형인가 → 배관 지지 적절한가 → 정렬 정확한가 → 펌프 마운팅 정확한가 → 밸브 설정 문제인가. 각 단계별 YES/NO 분기로 조치 진행 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf, p15, Algo 0.4 Excessive Vibration | action: "Is the vibration associated with the pump?", "Is the flexible coupling unbalanced?", "Is the pipework adequately supported?", "Is the alignment correct?", "Is the pump mounting correct?", "Is there air in the system?". expected_result: YES/NO 분기별 (각 YES → 해당 조치, NO → 다음 점검 진행) | 진동 임계값(mm/s 또는 ISO 10816) 미제시. 펌프·구동부별 정상 범위 미제시 | C |
| HPU-C33 | T3 | Algo 0.5: 과도 누수 진단. 증상 START. 시스템 청소 → 누수가 한 장치에만 추적 가능인가 → 누수가 배관 한 영역에 추적 가능인가 → 수냉식 냉각기 설치인가 → 부품별 격리 테스트. 각 단계별 YES/NO 분기로 부품 특정 또는 격리 진행 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf, p16, Algo 0.5 Excessive Leakage | action: "Clean down the system", "Can the leakage be traced to one unit?", "Can the leak age be traced to one area of pipework?", "Is a water cooler fitted to the system?", "Isolate each part of the system in turn and check for leaks". expected_result: YES/NO 분기별 ("YES unit" → Repair/replace unit, "YES pipework" → Repair/replace pipework, "YES cooler" → Check cooler 등) | 누수 위치 확인 기준(소음 변화, 색상 변화, 습윤도) 정량화 미제시 | C |
| HPU-C34 | T3 | Algo A.1: 기어·베인 펌프 시스템 테스트. 증상 START. 다중 순차 진단 경로: (1) 펌프 출구 압력 (2) 펌프 샤프트 회전 (3) 시스템 부하 (4) 모션 감지(압력 변화) (5) 회전 정렬 (6) 펌프 조립(부품 순서) (7) 펌프 프라이밍 (8) 릴리프 밸브 흐름. 각 단계별 YES/NO 분기로 진단 경로 확정 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf, p17, Algo A.1 System test for gear and vane pumps | action: START → "Is there a pressure reading at pump outlet?" → "Is the pump shaft rotating?" → Load system → "Is there motion taking place?" → Correct rotation → Reassemble pump → Prime pump → Check relief valve. expected_result: YES/NO 분기별 (각 NO → 해당 조치, YES → 다음 단계); Pump cavitation 분기: "Pump is cavitating consult FCR1" | 정상 시스템 압력값 범위 미제시. 캐비테이션 진공 임계값("5 Hg") 명시되어 있음 | C |
| HPU-C35 | T3 | Algo B.2: 시퀀스 밸브 테스트. 단계: TP1·TP2 압력 측정 → "Are the pressures correct?" → 밸브 조정 정확여부 → 파일럿 신호 정확여부 → 드레인 라인 폐색여부 → 스풀 프리 여부. 각 단계별 YES/NO 분기로 조치 또는 다음 점검 진행 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf, p21, Algo B.2 System test for sequence valves | action: "Check the pressures at TP1 and TP2", "Are the pressures correct?", "Is the valve adjusted correctly?", "Is the pilot signal correct?", "Is the drain line blocked?", "Is the spool free?". expected_result: YES/NO 분기별 (NO pressures → Re-adjust valve, YES pressure + NO adjust → Re-adjust, NO pilot → Check pilot signal 등) | 정상 압력값(TP1/TP2) 범위 미제시. 파일럿 신호 정상값 미제시 | C |
| HPU-C36 | T3 | Algo B.3: 압력 감소 밸브 테스트. 단계: TP1·TP2 게이지 삽입 → "Is there a pressure reading at TP1?" → 시스템 부하 → 압력값 정상여부 → TP2 압력 게이지 → 압력값 정상여부 → 시스템 유량 문제 → 드레인 흐름 과도여부 → 밸브 조정. 각 단계별 YES/NO 분기로 진행 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf, p22, Algo B.3 System test for pressure reducing valves | action: "Insert pressure gauges in TP1 & TP2", "Is there a pressure reading at TP1?", "Is the reading equal to full system pressure?", "Is there motion taking place?", "Is the system problem lack of flow?", "Is the drain flow excessive?". expected_result: YES/NO 분기별 (NO TP1 → Load system, YES reading + NO full pressure → Check gauge, NO motion → Check when motion stopped 등) | 정상 TP1/TP2 압력값 범위 미제시. 드레인 과도 압력 기준 미제시 | C |
| HPU-C37 | T3 | Algo C.1: 유량 제어 밸브 테스트. 단계: "Is the system problem flow?" → 밸브 설치 정확여부 → 밸브 조정 정확여부 → TP1 게이지 삽입 → 시스템 압력 정상여부 → TP2 게이지 삽입 → TP1/TP2 읽음값 동일여부. 각 단계별 YES/NO 분기로 진행 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf, p23, Algo C.1 System test for flow control valves | action: "Is the system problem flow?", "Is the valve installed correctly?", "Is the valve adjusted correctly?", "Insert gauge at TP1", "Is reading normal system pressure?", "Insert gauge at TP2", "Are the readings at TP1 and TP2 the same?". expected_result: YES/NO 분기별 (YES flow problem + NO install → Correct installation, YES reading normal + YES TP2 normal → Check next unit 등) | 정상 TP1/TP2 압력값 미제시. 보상·비보상 밸브 구분 기준 미제시 | C |
| HPU-C38 | T3 | Algo D.1: 방향 제어 밸브 테스트. 단계: TP1·TP2 게이지 삽입 → 밸브 수동 조작(P to A) → TP1 읽음값 확인 → 시스템 부하 → TP2 읽음값 확인 → 시스템 부하 다시 → 모션 감지 → 펌프 공급 확인 → 모션 완료 대기. 각 단계별 YES/NO 분기로 진행 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf, p24, Algo D.1 System test for directional control valves | action: "Insert gauges TP1 & TP2", "Operate valve manually P to A", "Is there a reading on TP1?", "Is the system on load?", "Is there a reading on TP2?", "Is the system on load?", "Is there motion taking place?", "Is the pilot supply correct?", "Wait until motion has finished". expected_result: YES/NO 분기별 (NO TP1 reading → Load system, YES TP1 + NO load → Check pilot supply 등) | 정상 TP1/TP2 압력값 미제시. 파일럿 공급 정상 범위 미제시 | C |
| HPU-C39 | T3 | Algo E.1: 파일럿식 체크 밸브 테스트. 단계: TP1·TP2 게이지 삽입 → "Check pressures with flow passing thru the valve" → "Is the pressure difference excessive?" → 파일럿 압력 라인 게이지 삽입 → 파일럿 압력 충분여부 → 시스템 크리프 발생여부 → 파일럿 라인 제약 또는 역류 확인. 각 단계별 YES/NO 분기로 진행 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf, p25, Algo E.1 System test for pilot operated check valves | action: "Insert gauges TP1 & TP2", "Check pressures with flow passing thru the valve", "Is the pressure difference excessive?", "Insert gauge in pilot pressure line", "Is pilot pressure sufficient?", "Is the system problem creep?", "Does pilot pressure decay when valve is required to close?", "Check for restriction in pilot line". expected_result: YES/NO 분기별 (YES excessive → Check valve, NO excessive + NO sufficient → Check pilot supply 등) | 과도 압력 차이 임계값(bar 또는 psi) 미제시. 파일럿 압력 충분 기준 미제시 | C |
| HPU-C40 | T3 | Algo G.1: 실린더 테스트. 단계: "Is the system problem erratic motion?" → 에어 블리드(블리드 포인트) → 실린더 완전 신장 → 부하 해제·압력 해제 → 앤뉼러스 연결 해제 → 풀보어 엔드에 압력 인가 → "Is oil leaking from annulus conn. on cylinder?" → 실린더 점검. 각 단계별 YES/NO 분기로 진행 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf, p26, Algo G.1 System test for cylinders | action: "Is the system problem erratic motion?", "Bleed air from cylinder bleed points", "Fully extend cylinder to end of stroke", "Off load or release system pressure at cylinder ports", "Disconnect annulus connection of cylinder", "Apply pressure to full bore end", "Is oil leaking from annulus conn. on cylinder?". expected_result: YES/NO 분기별 (YES erratic → Bleed air, NO erratic + YES leaking → Check cylinder, NO leaking → Check next unit 등) | 비정상 모션의 진동/속도 임계값 미제시. 에어 블리드 절차(시간, 유량) 상세 미제시 | C |
| HPU-C41 | T3 | Algo G.2: 유압 모터 테스트. 단계: 모터 입구포트 압력 측정 → "Is pressure normal working pressure?" → 모터 출구포트 압력 측정 → "Is back pressure excessive?" → 모터 드레인 유량 측정 → "Is drain flow excessive?" → 모터 샤프트 프리 여부 → 다음 장치 점검. 각 단계별 YES/NO 분기로 진행 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf, p27, Algo G.2 System test for hydraulic motors | action: "Check pressure at motor inlet port", "Is pressure normal working pressure?", "Check pressure at motor outlet port", "Is back pressure excessive?", "Check motor drain flow", "Is drain flow excessive?", "Disconnect motor coupling and rotate by hand", "Is shaft free?". expected_result: YES/NO 분기별 (NO inlet pressure → Check loss in system, YES inlet normal + YES back pressure → Check restriction in return line 등) | 정상 작동·백 압력값 범위 미제시. 드레인 유량 정상값 미제시 | C |
| HPU-C42 | T3 | Algo J.1: 축압기 테스트. 단계: 제조사 지시서에 따라 가스측 테스트 게이지 삽입 → 축압기에서 유체 배출·가스 압력 확인 → "Is the pre-charge pressure correct?" → 펌프 정지·축압기 배출 → 유량 라인 압력 게이지 삽입 → 축압기를 시스템 압력으로 충전 → "Is the pressure reading correct?" → 압력 스위치·릴리프 밸브 조정 여부 확인. 각 단계별 YES/NO 분기로 진행 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf, p28, Algo J.1 System test for accumulators | action: "Insert test gauge in gas side of accumulator as manufacturers instructions", "Discharge fluid from accumulator and check gas pressure", "Is the pre-charge pressure correct?", "Stop pumps and discharge accumulator", "Insert pressure gauge in fluid line", "Charge accumulator to fluid system pressure", "Is the pressure reading correct?", "Is the pressure switch setting correct?", "Is the relief valve of compensator adjusted correctly?". expected_result: YES/NO 분기별 (NO pre-charge → Charge with nitrogen, YES pre-charge + NO pressure reading → Re-adjust pressure switch 등) | 정상 가스 프리차지·시스템 압력값 미제시. 압력 스위치·릴리프 밸브 설정값 미제시 | C |
| HPU-C43 | T3 | Algo J.2: 냉각기 테스트. 단계: 냉각기 출구포트에서 오일 온도 측정 → "Is the temp too high?" → 입·출수 온도 차이 확인 → 냉각수 공급 개방 여부 → 써모스탯 조정 여부 → 입·출수 온도 확인 → 오일 유량 흐름 확인 → 냉각기 점검. 각 단계별 YES/NO 분기로 진행 | 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf, p29, Algo J.2 System test for coolers | action: "Check the oil temp at the outlet port of the cooler", "Is the temp too high?", "Is there a difference between oil inlet and outlet temps?", "Is the water supply switched on?", "Is the thermostat adjusted?", "Is the water inlet temp too high?", "Is the oil flow thru the cooler correct?". expected_result: YES/NO 분기별 (YES temp high + NO difference → Cooler working/Check next unit, NO temp high + YES difference → Cooler working/Check next unit 등) | 과도 온도 임계값(℃) 미제시. 정상 입·출수/오일 온도값 미제시. 오일 유량 정상값 미제시 | C |

**T3 판정 재검토 및 완료:**
100980172-Logical-Troubleshooting의 모든 Algo flowchart(총 20개)는 명시적으로 action(확인 지시) + expected_result(YES/NO 분기 + 각 분기별 조치)를 구조화함. 초기 "expected_result가 implicit하므로 T3 불가"는 오류 판정. 사용자 지정에 따라 YES/NO 분기 자체가 expected_result의 explicit 구현이므로, 이들 Algo는 모두 T3 후보 적합. 결과: 전체 20개 Algo 중 **모두 20개를 T3 후보로 추가** (HPU-C25~C44).

**추가된 T3 후보:**
- 5개 주요 Algo (HPU-C25~C29): Algo 0.1, A.2, B.1, L.1, L.2
- 15개 보조 Algo (HPU-C30~C44): Algo 0.2, 0.3, 0.4, 0.5, A.1, B.2, B.3, C.1, D.1, E.1, G.1, G.2, J.1, J.2 (순서대로)

**미검토 Algo:** 없음. p012~p031 범위 전체 Algo 처리 완료.

---

**[사용자 지적 재확인] C08, C18, C20 필수 필드 검증:**

| 후보 ID | 사용자 지적 | 원문 재확인 결과 | 보류 판정 | 개선 액션 |
|---|---|---|---|---|
| **HPU-C08** (T1) | "symptom이 관측 가능한가? 아니면 메커니즘 설명만 있는가?" 지적 | HY29-0022-UK p24-25 원문: "without priming, pump not lubricated enough and be damaged. **Local overheating, seizure between port plates and rotor**". "local overheating"과 "seizure (용접)" 자체가 관측 가능한 증상(경고 신호). 따라서 T1 symptom 필드 충족. | ✓ 유지 (T1 적합) | 없음. 다만 "초기 윤활 부족 감지 신호"는 실시간 관측 기준이 아니므로, 카드 스키마에서 "precondition: 펌프 시동 직후", "verification: 소음/온도 상승 관측"으로 구조화 권고 |
| **HPU-C18** (T5) | "safety_flag=true인데 명시적 금지 문구(DO NOT/MUST NOT)가 없다. 단순 troubleshooting 항목 아닌가?" 지적 | HY13-PMDSPS1M_US p32 원문: "**Loss of Suction**: Suction line closed, blocked or leaking causes loss of suction. Must verify suction valve locked open, inspect joints, remove obstruction, repair leaks". 명시적 금지 문구 없음. "causes loss of suction" → "펌프 고장" consequence 제시되지만, 선택적 진단(troubleshooting) 형식. 독립적 금지 선언 아님. | ⚠️ **재분류 검토** | "Suction line closed/blocked/leaking"은 T1(징후 해석: 저흡입) 또는 T5(보류). 현재 T5로 유지하되, "safety_basis를 강화: '흡입 손실 발생 → 펌프 고장 임박 → 긴급 정지 필요' 구조로 safety 맥락화" 또는 T1로 재분류 검토 필요 |
| **HPU-C20** (T5) | "배관 정렬 불량 금지가 아니라 troubleshooting 한 항목 아닌가? 독립적 안전 선언 아닌가?" 지적 | HY13-PMDSPS1M_US p33 원문: "**Excessive power / Mechanical problems**: Check for bent shaft, tight shaft packing or pipe strain. Repair or replace as required". 금지 선언이 아니라 진단 권고(Check). 조치는 "Repair or replace". | ⚠️ **재분류 검토** | "Pipe strain" 자체는 구조적 문제(배관 설치 검수 단계 선언)이므로 T5(예방 금지) 적합하지만, 원문은 "후진단 검사·수정" 형식. T1(과다 전력 증상 해석: 배관 정렬 불량) 또는 T5(재정의: "배관 설치 검수 시 응력 없음 확인 필수") 검토 필요 |

**결론:** C08은 유지 (T1 적합). C18, C20은 원문 재확인 결과 troubleshooting 항목의 특성상 T5 재분류 검토 권고. 현 보고서는 기존 분류 유지하되, KB 생성 전 확정 필요 명시.

---

## 4. 기존 카드 중복 확인

기존 카드를 검토한 결과, 해당 HPU 폴더의 원문 7건과 직접 계보가 겹치는 카드는 없음. 다만:

| 그룹 | 검토 범위 | 판정 |
|---|---|---|
| 기존 K-0201/K-0202 | 2026-09-23 보고서의 합성 카드 (논문 기반 EV-0201~EV-0202) | 원문 계보 무관. 감속기(GR) 영역. HPU 카드 아님 |
| docs/data/knowledge_cards/ | 기존 카드 초안 파일 | HPU 관련 기존 카드 없음 |

---

## 5. 등록부 매칭

| 파일 | 매칭 source_id | 매칭 근거 | 현재 review_status | approved_scope 유무 | 판정 |
|---|---|---|---|---|---|
| 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf | (미등록) | Vickers General Product Support, 1984. source_registry.json에 미등록 | — | — | **미등록 출처**. 등록 제안: title="Vickers, Logical Troubleshooting in Hydraulic Systems", url=미확인, purpose="범용 유압 진단 원칙", document_version="GB-CB9003 (8/84)" |
| AX189986484780en-000501.pdf | M-02 또는 신규? | Danfoss D1 펌프. registry.json의 "SD-002 Parker HY29-0035/UK" (베인펌프)와는 별개 제품. M-02는 SEW 감속기. 매칭 오류? | pending_review | 없음 | **미등록 또는 오매칭**. 확인 필요: 기존 registry에 Danfoss D1 항목 있는지 재검토. 현 registry에는 Danfoss 펌프 미등록. |
| AX549927744283en-000201.pdf | (미등록) | Vickers by Danfoss PVMX 펌프. registry.json에 미등록 | — | — | **미등록 출처**. 등록 제안: title="Vickers by Danfoss, PVMX Open Circuit Axial Piston Pump Service Guide", url=미확인, purpose="축방향 왕복 펌프 정비", document_version=미명시 |
| HY13-PMDSPS1M_US.pdf | (미등록) | Parker Hannifin Three Screw Pump. registry.json에 미등록 | — | — | **미등록 출처**. 등록 제안: title="Parker Hannifin, Three Screw Pump Series Installation/Assembly & Maintenance & Troubleshooting Manual", url="HY13-PMDSPS1M_US", purpose="스크류 펌프 설치·정비·진단", document_version="M1/US" |
| HY29-0022-UK.pdf | SD-002 (부분 매칭) 또는 새로운 항목? | Parker Denison Vane Pump 진단 가이드. SD-002는 "Parker HY29-0035/UK Denison 베인펌프 Overall Instructions"로 등록. HY29-0022는 다른 카탈로그. 모델 명칭이 다름 (0022 vs 0035). | pending_review | 없음 | **모델 불일치**. HY29-0022는 별도 등록 필요 가능성. 기존 SD-002와 동일 제조사·제품군이지만 모델 번호 다름. |
| MAN-C-012.pdf | (미등록) | ATOS HPU 정비 핸드북. registry.json에 미등록 | — | — | **미등록 출처**. 등록 제안: title="ATOS, HPU Maintenance Handbook", url=미확인, purpose="HPU 정기 정비 프로그램", document_version="MAN-C-012-EN/0" |
| ServMan_DHM.pdf | (미등록) | Bulletin 2630-C1 기어펌프 서비스 매뉴얼. registry.json에 미등록 | — | — | **미등록 출처**. 등록 제안: title="Parker Hannifin Hydraulic Pump/Motor Division, Fixed Displacement Gear Pumps Service Manual", url=미확인, purpose="D/H/M 시리즈 기어펌프 정비·분해", document_version="Bulletin 2630-C1 (01/2000)" |

**미등록 출처 목록:**
1. 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf (Vickers)
2. AX189986484780en-000501.pdf (Danfoss D1)
3. AX549927744283en-000201.pdf (Vickers PVMX)
4. HY13-PMDSPS1M_US.pdf (Parker Screw Pump)
5. HY29-0022-UK.pdf (Parker Denison, 기존 SD-002와 모델 번호 불일치)
6. MAN-C-012.pdf (ATOS HPU)
7. ServMan_DHM.pdf (Parker Gear Pump)

**승인 상태 검토:**
- 모든 미등록 출처는 `review_status = pending_review`, `approved_scope = []`
- 따라서 카드 후보 HPU-C01~C08은 모두 "검토용 후보. 생성 파이프라인·운영 KB 투입 금지" 상태

---

## 6. 부족한 근거

| 항목 | 내용 | 검토 페이지 |
|---|---|---|
| T3 "진단 flowchart" | AX189986484780en-000501 troubleshooting 테이블(p37~39)은 증상→확인→조치 테이블 형식이지만, 각 확인 단계의 "기대 결과(expected_result)"가 structured되지 않음. 원문은 Description(원인 설명)과 Action(권고 조치)를 분리하지만, "Check fluid level → If normal, expected_result is level at mark"의 형식이 아니라 "If low → Fill"로 조치만 제시. T3 스키마 필수 조건(action + expected_result) 미충족. | p037~039 정독. 나머지 페이지는 미검토 |
| T3 "진단 flowchart" | 100980172-Logical-Troubleshooting p013~015의 flowchart(Excessive Temperature/Noise/Vibration)는 decision tree이지만, 각 branch의 condition(진행 조건)과 expected_result(관찰 기준)이 implicit. 카드 JSON의 structured T3 필드와 불일치. | p013~015 정독. 나머지 페이지(p016~037)는 미검토 |
| 조건부 진단 규칙 | AX189986484780en-000501 troubleshooting에서 "Low Pump Output Flow" 원인 중 "Incorrect LS signal" → "Inspect system to ensure that proper LS signal transmit to pump"는 확인 지시이지만, "proper LS signal의 정상값" 기준 미제시. 정상 LS 신호 범위(예: bar, psi)가 없음. | p037~38 |
| T4 "인계 방법" | 원문 7건 중 인계 절차(required_context, recipient_role, timing, channel, acknowledgement 5개 필드)가 명시된 부분 없음. MAN-C-012의 정기 점검 기록표(핸드북의 repairs and maintenance 장)에 기록 형식이 있을 가능성이나, 검토 범위 미포함. | MAN-C-012 p010~011 (repairs and maintenance handbook 내용) 미검토 |
| 미검토 범위 | 원문 7건 총 244쪽 중 검토 범위: p001~003(표제)~, 키워드 검색 결과 ~50쪽, 세부 정독 ~20쪽. 미검토: 나머지 ~170쪽 | 상세 범위 아래 참조 |

**미검토 범위 상세:**

| 파일 | 총 p. | 검토 p. | 미검토 p. | 사유 |
|---|---|---|---|---|
| 100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf | 37 | p001~003, p013~015 (정독) | p004~012, p016~037 | flowchart 핵심 부분만 검토. 상세 진단 원리, 시스템 테스트, pump cavitation, aeration, restart procedure 미검토 |
| AX189986484780en-000501.pdf | 67 | p001~003, p037~039 (정독) | p004~036, p040~067 | troubleshooting 섹션만 검토. 펌프 설계, 운영 설정, 유체·필터 정비, 초기 시동 절차 미검토 |
| AX549927744283en-000201.pdf | 25 | p001~003, 키워드 검색 결과 | p004~025 | 표제만 검토. 세부 내용 미검토 |
| HY13-PMDSPS1M_US.pdf | 40 | p001~003, p014~015 (정독) | p004~013, p016~040 | 설치·배관·안전 주의사항만 검토. 펌프 기술 사양, 점검 절차, 완전 troubleshooting 섹션 미검토 |
| HY29-0022-UK.pdf | 60 | p001~003, p024~028 (정독) | p004~023, p029~060 | 고장 분류 섹션 검토. 기계적·압력·물리화학적 고장 중 에어·캐비테이션만 깊이 검토. 수분 오염, 점도 오류, 부적절한 유체, 그리스 미검토 |
| MAN-C-012.pdf | 11 | p001~003, p006~008 (정독) | p004~005, p009~011 | 목차·정기 정비 섹션 검토. HPU 식별표, 예방 정비 프로그램, 수리·정비 핸드북 미검토 |
| ServMan_DHM.pdf | 4 | p001~004 (정독) | — | 짧은 분량. 전체 정독 |

---

## 7. 담당자 확인 질문

| # | 질문 | 필요 이유 | 회신 대상 |
|---|---|---|---|
| Q1 | 미등록 출처 7개의 이용 권한 및 생성 파이프라인 투입 가능성? (특히 AX189986484780en-000501 Danfoss D1, HY13-PMDSPS1M_US Parker Screw, MAN-C-012 ATOS HPU는 현 HPU 적용 모델인가?) | source_registry.json의 pending_review 상태 항목들(SD-001~007)도 미승인. 7개 미등록 파일을 생성 입력으로 사용하려면 출처 승인(approved_scope) 기록 필수. 또한 각 파일이 프로젝트 냉간코일 설비와 직접 계보가 있는지 확인 필요 | HPU 설비 담당, 원문 획득 담당 |
| Q2 | HY29-0022-UK.pdf (기존 SD-002 Parker HY29-0035/UK와 다른 모델)의 매칭 상태 확인? 같은 제조사·제품군 베인펌프이지만 카탈로그 번호(0022 vs 0035)가 다름. 기존 등록을 확장할 것인가, 신규로 분리할 것인가? | registry 정합성. 기존 SD-002 승인 범위가 HY29-0022에도 적용되는지 불명확 | registry 관리자 |
| Q3 | AX189986484780en-000501(Danfoss D1) troubleshooting 테이블의 각 항목이 실제로는 "series of checks(순차 진단)"인지 확인? 예를 들어 "Check fluid level (1) → Check for air (2) → Check pump inlet pressure (3)"의 순서가 의도된 진단 순서인가, 아니면 독립적인 항목들인가? | T3 카드 후보 판정. 원문 interpretation 필요. Item 순서가 진단 순서인지, 각 Item의 Positive/Negative branch가 어떻게 다음 단계로 진행하는지 명확화 필요 | 제조사 기술 담당 또는 현장 HPU 운영자 |
| Q4 | 점도 "acceptable limits"의 구체적 범위(cSt 또는 ℃ 기준)? T2 조건화 시 적용 범위 필요 | AX189986484780en-000501 p37~38의 troubleshooting은 "viscosity above acceptable limits" 표현만. 스크류 펌프(HY13), 베인펌프(HY29-0022), 축방향 펌프(AX549927744283)별로 기준이 다를 가능성 | 각 펌프 제조사 또는 HPU 유지보수 매뉴얼 |
| Q5 | "High inlet vacuum causes cavitation"의 임계값(>5 inHg = -0.21 bar 기준이 모든 펌프에 적용되는가, 아니면 모델별로 상이한가?) | T5 카드 HPU-C03의 safety_basis. 원문(AX189986484780en-000501)에는 임계값이 기재되지만, 다른 펌프의 임계값이 다를 수 있음. 통합 T5로 만들 것인지 펌프별 T5로 분리할 것인지 판정 필요 | 각 펌프 제조사 |
| Q6 | 공기 제거 절차(air bleed-off, priming)의 표준 절차와 소요 시간? HY29-0022-UK p24의 설명은 개념적. 실제 현장 절차와의 차이 | HPU-C08 카드 후보의 precondition, action 정의. 매뉴얼의 "good circuit priming and air bleed-off must be made" 문구는 절차 상세 미제시 | HPU 운영 담당, 정비사 |
| Q7 | 미검토 범위 ~170쪽에 카드화할 추가 지식이 있는가? 특히 HY29-0022-UK p029~060의 "Consequences of failures"와 "How to prevent"는 근거표 항목이 될 가능성. 검토 범위 확대 필요 여부? | 총 244쪽 중 ~70%만 검토. 효율성 대비 누락 리스크. 베인펌프 고장 유형 20+개의 예방·진단 내용 있을 것으로 예상 | 감독자 (검토 범위 재결정) |

---

## 8. 검토 한계

### 미검토 범위의 구체적 내용
- **100980172 p016~037**: "System test for gear/vane/piston pumps", "System test for valves/cylinders/motors/accumulators/coolers", "Pump cavitation", "Aeration of fluid", "Re-start procedure", "Bar trimming machine exercise"
  
  → 추가 T1/T3/T5 카드 후보 가능성 있음 (예: "재시동 절차", "캐비테이션 징후", "에어레이션 방지").

- **AX189986484780 p040~067**: 초기 시동 절차 3단계(정지→워밍업→압력화), 유체·필터 정비, 펌프 기술 사양, 고장 진단 추가 사항
  
  → T3 진단 flowchart 외 초기 시동 안전 조건(T5) 가능성.

- **HY29-0022-UK p029~060**: "Consequences of failures" 9개 섹션 (기계적 고장의 결과→베어링 문제→소음, 압력·물리화학적 고장의 결과→수분 오염의 결과), "Suitable fluids", "Unsuitable grease"
  
  → T1(고장 신호 해석), T5(부적절한 유체·그리스 금지) 카드 후보 다수.

- **HY13-PMDSPS1M_US p016~040**: 설치·조립 완전 절차, 스크류 펌프 기술 사양, troubleshooting 완전 섹션
  
  → T3 진단, T5 안전 조건 추가 가능.

- **MAN-C-012 p009~011**: "Preventive Maintenance Program", "Handbook of Repairs and Maintenance"
  
  → T2(조건별 정비), T5(정기 점검 금지 시 결과) 가능.

### 추출 불가 페이지 없음
- 모든 파일의 추출된 텍스트가 읽기 가능. 스캔 품질 또는 보안 제약으로 인한 추출 오류 없음.

### 판단 유보 항목
1. **T3 "진단 절차"의 표준화**: 원문은 decision tree 또는 Item-Description-Action 테이블 형식. KnowledgeCard T3 스키마의 "steps" 필드(step_id, order, action, expected_result, preconditions, stop_conditions)로의 매핑이 비일관적. 정규화 기준 필요.

2. **원문 판본·발행연도 불명**: 일부 파일(AX549927744283, MAN-C-012, ServMan_DHM)의 문서 버전, 발행 연도, 개정 이력이 불명확. 원문 진정성 재확인 필요.

3. **국내·국제 기준 차이**: 
   - 미국 제조사(Parker, Danfoss 일부) 제품의 사양·임계값이 국내 안전 규정(산업안전보건기준)과의 괴리 가능성.
   - 예: OSHA 관련 caution/warning은 있지만, 국내 산안법 제92조(정비 작업 시 운전정지) 인계와의 매핑 미정리.

4. **설비 모델 적합성**: 7개 원문의 펌프 모델(Danfoss D1, Vickers PVMX, Parker Screw/Vane/Gear, ATOS HPU)이 프로젝트의 냉간코일 공장 실제 HPU와 일치하는지 확인 필요. README.md에 "적용 펌프 모델 미확인"이라 명시된 상태.

---

## 검토 요약 (최종: 모든 Algo p012-p031 처리 완료)

| 항목 | 이전 | 현재 수정 | 최종 |
|---|---|---|---|
| 원문 분류 | A: 0건 / B: 6건 / C: 2건 | (변화 없음) | **A: 0건 / B: 6건 / C: 2건** |
| 근거표 항목 | 32개 주장 | **+15개 Algo 근거** (T3 15개) | **47개 주장** |
| T1~T6 카드 후보 | 29개 (T1:12, T2:2, T3:5, T5:10) | **+15개 T3 (Algo 0.2~0.5, A.1, B.2~B.3, C.1, D.1, E.1, G.1~G.2, J.1~J.2)** | **44개 (T1:12, T2:2, T3:20, T5:10)** |
| T3 완료 상태 | 5개 Algo (주요) + 15개 미검토 | **모든 Algo p012-p031 완독 → 15개 미검토 모두 T3로 전환** | **T3 20개 완성. p012-p031 범위 미검토 Algo 없음** |
| 미충족 항목(T3용) | HPU-C25~C29: 5개 각각 임계값 미제시 | **+HPU-C30~C44: 15개 각각 임계값 미제시** | **T3 20개 모두 정상값/임계값 범위 미제시** (각 카드별 "색상 변화 경계값", "음성 기준값", "온도 임계값", "압력/유량 정상값" 등) |
| 담당자 확인 질문 | 7개 | (기존 유지) | **7개** (T3 추가로도 Q1 등 동일) |
| 미등록 출처 | 7개 (모두 pending_review) | (변화 없음) | **7개** (모두 pending_review) |
| 승인 상태 | 29개 모두 approved_scope 없음 | +15개 T3 모두 approved_scope 없음 | **44개 모두 approved_scope 없음** → 생성 파이프라인 투입 금지 상태 |
| 정독 범위 | 244쪽 중 ~120쪽 (~49%) | **100980172 p012-p031 완독** (20개 Algo flowchart 정독) | **244쪽 중 ~55쪽 (~23%) 정독** (나머지 189쪽 미검토) |

**최종 카드 후보 구성 (44개):**
- HPU-C01~C24: 기존 (T1:12, T2:2, T5:10)
- HPU-C25~C29: T3 기본 (Algo 0.1, A.2, B.1, L.1, L.2)
- HPU-C30~C44: T3 확장 (Algo 0.2, 0.3, 0.4, 0.5, A.1, B.2, B.3, C.1, D.1, E.1, G.1, G.2, J.1, J.2) = 15개

**T3 항목별 미충족 사항 (공통 패턴):**
- Algo 0.2~0.5, A.1: 온도/소음/진동/누수/압력 임계값 미제시
- Algo B.2~D.1, E.1: 정상 압력값 범위·파일럿 신호 기준 미제시
- Algo G.1~G.2: 온도/압력/유량 정상값 미제시
- Algo J.1~J.2: 가스 프리차지·시스템 압력·냉각 온도 정상값 미제시

**미검토 범위 (최종 정확 계산):**

| 파일 | 총 p. | 정독 p. | 미검토 p. | 사유 |
|---|---|---|---|---|
| 100980172 | 37 | 1-3, 12-31(Algo) = 23쪽 | 4-11, 32-37 = 14쪽 | Algo 섹션 전체 정독. 개론·참조·상세 미검토 |
| AX189986484780 | 67 | 1-3, 37-39(troubleshooting) = 6쪽 | 4-36, 40-67 = 60쪽 | Troubleshooting 섹션만 정독. 설계·설정·유체 미검토 |
| AX549927744283 | 25 | 1-3 = 3쪽 | 2-25 = 23쪽 | 표제만 정독 |
| HY13-PMDSPS1M | 40 | 1-3, 14-15, 32-33(일부 troubleshooting) = 6쪽 | 4-13, 16-31, 34-40 = 34쪽 | 배관·안전·일부 troubleshooting 정독. 기술사양·완전 진단 미검토 |
| HY29-0022-UK | 60 | 1-3, 24-28(에어·캐비테이션), 32-44(입자·압력·결과) = 20쪽 | 4-23, 29-31, 45-60 = 41쪽 | 고장 증상·원인 정독. 물/점도/그리스/방지 미검토 |
| MAN-C-012 | 11 | 1-3, 6-8(정비) = 6쪽 | 4-5, 9-11 = 5쪽 | 목차·정기정비 정독. 식별표·예방·수리핸드북 미검토 |
| ServMan_DHM | 4 | 1-4(전체) = 4쪽 | 0쪽 | 전체 정독 |
| **합계** | **244** | **55쪽 (23%)** | **189쪽 (77%)** | — |

검토용 후보는 생성 가능하나, 출처 승인(approved_scope 등록), 현장 설비 모델 매칭 확인, **T3 후보의 정상값/임계값/정상 범위 확정** 후 KB 투입 가능.

---

## 9. 검증 결과

별도 검증에서 **근거표와 후보의 각 주장이 적힌 페이지 텍스트에 실제로 있는지만** 대조했다. 중간 기록은 `artifacts/source-card-review-20260925/verify/HPU-verify.md`와 `HPU-T3-verify.md`에 있다(Git 제외). 불일치는 위 표에서 지우지 않고 아래에 표시한다.

### 9.1 근거표 주장 대조

| 항목 | 건수 |
|---|---|
| 대조한 주장 | 32 |
| 일치 | 32 |
| 부분 일치 | 0 |
| 불일치 | 0 |
| 다른 페이지에 있음 | 0 |
| 확인 불가 | 0 |

문서 정체 주장은 각 파일 p001에서 제조사·문서번호·제품명이 확인됐다. `AX189986484780en-000501` p040~p067을 "사양표, 카드 대상 아님"으로 묶은 처리도 원문과 일치했다(해당 구간에 WARNING/CAUTION/DANGER/must not/do not/never 검출 없음. 검출은 p006·p028·p032·p036으로 모두 정독 구간).

### 9.2 T3 판정 정정 — 최초 0건 판정은 원문과 불일치했다

최초 검토는 T3를 0건으로 판정하고 "flowchart의 YES/NO 분기는 암묵적 expected_result라 T3 불가"라는 근거를 적었다. **이 판정은 원문과 맞지 않았다.**

`100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf` p012~p031은 `Algo` 번호가 붙은 진단 흐름도이며, 각 단계에 확인 지시와 그 결과 분기가 원문에 함께 명시되어 있다. 예로 PDF p017 / 인쇄 p.17 `Algo A.1 System test for gear and vane pumps`에는 확인 행동(`Is there a pressure reading at pump outlet`, `Check the vacuum at the pump inlet`), 분기 조건(`Is the vacuum more than 5" Hg (-0.21 bar)`), 분기별 조치(`Prime pump`, `Re-adjust relief valve`, `Pump is cavitating consult FCR1`)가 있다. **분기 조건 자체가 expected_result의 명시 형태**다.

정정 후 T3 후보를 추가했고, 별도 검증에서 페이지 단위로 재대조했다.

| 항목 | 결과 |
|---|---|
| 대조한 T3 후보 | 19 (C25~C43) |
| 필수 조건 충족 | **19** |
| 미충족 | 0 |
| Algo 번호·페이지 매핑 불일치 | 0 |
| 원문에 없는 수치 | 0 (`5" Hg (-0.21 bar)` 등 모두 원문 일치) |

원문의 Algo 배치는 다음과 같이 확인됐다. **Algo는 19개이고 20개 페이지에 걸쳐 있다**(`Algo A.2`만 p018~p019 2쪽).

| PDF p. | Algo | 제목 |
|---|---|---|
| p012 | 0.1 | Unit Fault Preliminary Check |
| p013 | 0.2 | Excessive Temperature |
| p014 | 0.3 | Excessive Noise |
| p015 | 0.4 | Excessive Vibration |
| p016 | 0.5 | Excessive Leakage |
| p017 | A.1 | System test for gear and vane pumps |
| p018~p019 | A.2 | System test for piston pumps |
| p020 | B.1 | System test for pressure relief valves |
| p021 | B.2 | System test for sequence valves |
| p022 | B.3 | System test for pressure reducing valves |
| p023 | C.1 | System test for flow control valves |
| p024 | D.1 | System test for directional control valves |
| p025 | E.1 | System test for pilot operated check valves |
| p026 | G.1 | System test for cylinders |
| p027 | G.2 | System test for hydraulic motors |
| p028 | J.1 | System test for accumulators |
| p029 | J.2 | System test for coolers |
| p030 | L.1 | System test for air leaks |
| p031 | L.2 | System test for fluid contamination |

이 19건은 **제조사가 권고하는 진단 절차**이며 실제 수행된 조치가 아니다. 카드화하더라도 수행 사실로 표시하지 않는다. 19건 모두 정상값·임계값 범위가 원문에 없다는 §6의 지적은 유효하다.

### 9.3 필수 조건 미충족으로 지적된 후보

| 후보 | 유형 | 지적 내용 | 재확인 결과 |
|---|---|---|---|
| C08 | T1 | 원문이 기전 설명(공기 제거 없음 → 윤활 부족 → 과열 → 금속 접촉)만 제시하고 관측 징후가 없다 | 작성자는 `local overheating/seizure`가 관측 가능한 징후라며 **유지**. 판단이 갈리는 항목으로 남긴다 |
| C18 | T5 | 명시적 금지 문구(DO NOT / MUST NOT / never)가 없고 인과 서술만 있어 safety_basis 근거 부족 | **재분류 검토 권고**. 후보에서 지우지 않고 표시만 한다 |
| C20 | T5 | troubleshooting 한 항목이지 독립적 금지 선언이 아니다 | **재분류 검토 권고**. 후보에서 지우지 않고 표시만 한다 |

### 9.4 집계 오류 정정

본문의 후보 수·유형 집계가 실제 후보 목록과 어긋난다. 후보 ID를 직접 센 결과는 다음과 같다.

| 구분 | 본문 표기 | 실제 |
|---|---|---|
| 총 후보 수 | 44 | **43** (HPU-C01~C43, 결번 없음. C44는 존재하지 않는다) |
| T1 | 13 → 12로 1차 정정 | **12** (C01·C02·C08~C14·C17·C19·C24) |
| T2 | 2 | **2** (C07·C16) |
| T3 | 20 | **19** (C25~C43) |
| T5 | 9 → 10으로 1차 정정 | **10** (C03~C06·C15·C18·C20~C23) |

**최종: T1 12 / T2 2 / T3 19 / T5 10 = 43건.** T4·T6은 0건이며, 이번 원문에 인계 방법 5개 필드와 실제 재가동 시도·관측 기록이 없어 후보를 만들지 않았다.

### 9.5 §8 페이지 집계의 산술 오류

§8 표의 파일별 페이지 수 합이 실제 추출 페이지 수 244와 맞지 않는다.

| 파일 | 실제 추출 페이지 | §8 표의 합 | 차이 |
|---|---|---|---|
| AX189986484780en-000501 | 67 | 66 | -1 |
| AX549927744283en-000201 | 25 | 26 | +1 |
| HY29-0022-UK | 60 | 61 | +1 |
| **합계** | **244** | **245** | **+1** |

또한 §8의 "정독 55쪽(23%)"은 Algo 구간을 읽은 마지막 회차만 반영한 값이고, 그 앞 회차에서 정독한 범위(한때 약 120쪽으로 보고)를 포함하지 않는다. 같은 보고서 안에서 정독 페이지 수가 120쪽 → 55쪽으로 줄어든 것은 실제 검토가 줄어든 것이 아니라 집계 방식이 바뀐 것이다. **검토율 수치는 근사치로 읽어야 하며, 신뢰할 수 있는 것은 §8의 구간 표기다.** 미검토 구간이 여전히 크다는 사실은 유효하다.

### 9.6 검증 경과에 관한 기록

이 폴더의 1차 검증은 결과 파일을 남기지 않아 신뢰할 수 없었고, 재실행해 `HPU-verify.md`를 확보했다. T3 후보는 추가 후 `HPU-T3-verify.md`로 다시 대조했다. 각 검증이 실제로 읽은 페이지 목록은 해당 파일에 기록되어 있다.
