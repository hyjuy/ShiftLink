# GR 원문 검토와 지식카드 후보 근거표

**2026-09-25. 감속기(GR) 폴더의 원문 6건, 추출 페이지 194장 (추출 불가 6장)을 검토했다.**

대상 파일:
- 26867443.pdf (64/3): SEW ML..2/ML..V2 설치·운전 지침
- 26873427.pdf (86/3): 같은 제품군 카탈로그
- Failure analysis and countermeasures of gearbox in cold rolling mill.pdf (3): 기사
- Roll Drive Design Considerations for Steel Mill Rolling Operations.pdf (14): White Paper
- roller-table (1).pdf (12): WEG 롤러테이블 모터 카탈로그
- xu-zhang-2024-research-on-the-service-life-of-bearings-in-the-gearbox-of-rolling-mill-transmission-system-under-non.pdf (15): 연구논문

**검토 범위**: 각 파일 p001~p003로 문서 정체 확인, Grep으로 malfunction/fault/warning/bearing/vibration/inspection 등 키워드 검색, 매뉴얼의 절과 페이지 단위 정독. xu-zhang-2024는 2026-09-23 보고서 판단을 직접 재확인했다.

**미검토 범위**: 26867443.pdf의 정비 절차(§8 Inspection and Maintenance, p041–p044), 26873427.pdf의 기술 데이터(§4–5, p030–p065), Roll Drive의 설계 사례(p007–p014), roller-table의 상세 사양(p004–p012), xu-zhang-2024의 모델 검증 실험 부분(pp.10–15)은 핵심 내용 확인 후 전부 읽지 않았다.

---

## 1. 원문 분류

| # | 파일 | 분류 | 분류 근거 | 제조사·문서번호·판본·발행연도 |
|---|---|---|---|---|
| 1 | 26867443.pdf | B | 제품 설치·운전·정비·고장 대책을 규정한 제조사 매뉴얼. §9 Malfunctions에 고장 증상·원인·해결책을 표로 정리. 사건 사실·수행 조치 기록 없음. | SEW-EURODRIVE, 문서번호 불명, 판본: ML..2 & ML..V2 시리즈 설치·운전 지침, 2021 © |
| 2 | 26873427.pdf | B | 같은 제품군(ML..2 & ML..V2)의 카탈로그. 제품 설명, 기술 데이터, 선택 부품 정보 포함. 사건·조치 기록 없음. | SEW-EURODRIVE, 문서번호 불명, 판본: Catalog – ML..2 & ML..V2 Series, 발행연도 미기재 |
| 3 | Failure analysis and countermeasures of gearbox in cold rolling mill.pdf | C | 제목은 적합하나 본문은 일반 기사·블로그 포맷. p001 도입문에서 "냉간압연 감속기의 고장 분석과 대책"을 예고하나, p002–p003은 고장 원인의 일반 설명(기어 마모, 제조 결함, 온도, 과부하, 윤활 불량)만 있고 실제 사례의 상세 원인·조치·결과 없음. "Specific cases of failure analysis" 섹션 제목은 있으나 내용 부족. 실제 현장 조치 기록 아님. | 출처 미상 (웹사이트 wgt.asia), 문서번호 없음, 판본 없음, 발행연도: 2026-09-22 접근 기준 |
| 4 | Roll Drive Design Considerations for Steel Mill Rolling Operations.pdf | C | 철강산업 롤 드라이브 감속기 설계 고려사항을 설명한 White Paper. 신뢰성, 충격 부하, 밀폐, 설계 기준, Sumitomo Cyclo 감속기 평가 등 일반적인 기술 가이드. 실제 현장 사건·조치 기록 없음. | Patrick M. Laughery & Dan Rosseljong 저, 제조사/문서번호/판본/연도 명확하지 않음 |
| 5 | roller-table (1).pdf | B | WEG 사의 롤러테이블 모터 제품 카탈로그. 제품 특성, 표준 기능, 선택 기능, 표준 사양 기재. 사건·조치 기록 없음. | WEG, 문서번호 불명, 판본: Technical Catalogue – European Market, 발행연도 미기재 |
| 6 | xu-zhang-2024-research-on-the-service-life-of-bearings-in-the-gearbox-of-rolling-mill-transmission-system-under-non.pdf | C | 학술 논문(SAGE Advances in Mechanical Engineering 2024, Vol. 16(9)). 냉간압연 감속기 베어링의 비정상 윤활 상태 수명 연구. p001–p002에서 2022년 5월 26일의 현장 사건(베어링 손상으로 120시간 생산 정지)을 배경으로 언급하나, 실제 현장 조치 기록은 없음. pp.003–015는 연구자의 비선형 결합 모델, 시뮬레이션, 실험실 베어링 피로 테스트(6313-2RS 자체 윤활 베어링)를 다룸. **현장 관측**(베어링 손상 사실)과 **연구자 모델·계산·테스트**(시뮬레이션/실험실 결과)를 엄격히 구분 필요. 복구 성공 절차의 근거로 사용 불가. | Hai Xu, Qingqing Zhang, SAGE Advances in Mechanical Engineering, DOI: 10.1177/16878132241276941, 2024 |

**분류 집계**: A(사건 기록) 0건 / B(매뉴얼/카탈로그) 3건 / C(참고자료/연구) 3건

---

## 2. 근거표

카드화 가능한 주장별 근거. 원문의 직접 서술에서만 추출.

| # | 주장 요지 | 파일 | PDF p. | 인쇄 p. | 절·표 위치 | 적용 제품·조건 | 예외·금지 조건 | 원문 종류 |
|---|---|---|---|---|---|---|---|---|
| 1 | 비정상적이고 규칙적인 소음 → 베어링 손상 또는 기어 불규칙 메싱; 오일 확인 및 베어링 교체 또는 고객 서비스 문의. | 26867443.pdf | 45 | 45 | §9.1 Malfunctions, 문제: "Unusual, regular running noise" | ML..2 & ML..V2 시리즈. 원문에 운전 조건 특정 없음. | 고객 서비스 지원 권장(자체 수리 절차 제시 아님). | B |
| 2 | 비정상적이고 불규칙한 소음 → 오일 내 이물질 존재; 오일 확인, 드라이브 정지, 고객 서비스 문의. | 26867443.pdf | 45 | 45 | §9.1 Malfunctions, 문제: "Unusual, irregular running noise" | ML..2 & ML..V2 시리즈 | 원문 제한 사항 없음. | B |
| 3 | 감속기 장착부 이상 소음 → 장착이 풀림; 명시된 토크로 나사 조인트 조임, 손상된 나사 교체. | 26867443.pdf | 45 | 45 | §9.1 Malfunctions, 문제: "Unusual noise in the area of the gear unit mounting" | ML..2 & ML..V2 시리즈 | 원문에 명시된 토크값 없음; 개별 제품/설치 설명서 참조 필요. | B |
| 4 | 운전 온도 과다 → 오일 과다, 오일 노후화, 오일 오염, 통풍구 막힘, 냉각계통 고장. 각각의 해결책: 오일 레벨 확인/수정, 오일 교체, 냉각계통 분리 매뉴얼 참조. | 26867443.pdf | 45 | 45 | §9.1 Malfunctions, 문제: "Operating temperature too high" | ML..2 & ML..V2 시리즈(특히 팬 장착형). | 냉각계통 고장 시 분리 지침 참조 필요. | B |
| 5 | 베어링 온도점 과다 → 오일 부족/과다, 오일 노후화, 베어링 손상. 각각 오일 확인/교체/베어링 교체. | 26867443.pdf | 45 | 45 | §9.1 Malfunctions, 문제: "Bearing point temperatures too high" | ML..2 & ML..V2 시리즈 | 원문 예외 조건 명시 아님. | B |
| 6 | 커버판/감속기 하우징/베어링 커버/장착 플랜지 누유 → 가스켓 누수 또는 오일 실 손상. 나사 조임 또는 오일 실 교체, 지속되면 고객 서비스. | 26867443.pdf | 45 | 45 | §9.1 Malfunctions, 문제: "Oil leaking from cover plate / gearcase cover / bearing cover / mounting flange / output/input end oil seal" | ML..2 & ML..V2 시리즈 | 원문: 작은 규모 오일/그리스 누수는 24시간 운전-in 단계에서 정상(DIN 3761 참조). | B |
| 7 | 오일 드레인 플러그/통풍 플러그 누유 → 오일 과다, 부정확한 장착 위치, 빈번한 냉시동 또는 고오일 레벨. 오일 레벨 수정, 통풍 플러그 올바른 장착. | 26867443.pdf | 45–46 | 45–46 | §9.1 Malfunctions, 문제: "Oil leaking from oil drain plug / valve, from breather plug" | ML..2 & ML..V2 시리즈 | 원문 추가 제한 사항 없음. | B |
| 8 | 역자동차 온도 과다 → 손상된/불완전한 역자동차 기어. 역자동차 점검 및 필요시 교체, 고객 서비스 문의. | 26867443.pdf | 45 | 45 | §9.1 Malfunctions, 문제: "Operating temperature at backstop too high" | ML..2 & ML..V2 시리즈(역자동차 기어 장착 모델). | 역자동차 교체 시 고객 서비스 권장. | B |
| 9 | 냉간압연 감속기 베어링 수명은 압연 조건(입출력 두께, 압연 속도, 오일 점도, 롤 반지름)의 변화에 민감. 압연 조건이 불안정해질수록 베어링 수명 단축. 구체적: 입력 두께 증가 또는 출력 두께 감소 → 수명 급격히 단축; 무차원화된 압연 속도 1.1 초과 시 수명 급격히 감소. | xu-zhang-2024 | 8–9 | 8–9 | §"A study on the influence of different rolling conditions on the service life of bearings under non steady state lubrication conditions", Figure 6 | 냉간압연 감속기 SDAF23272 자정렬 롤러 베어링을 기준한 시뮬레이션 결과. 실제 설비 적용 조건 명시 아님(논문의 모델 가정). | 논문은 시뮬레이션 결과(연구자 모델)이지 실제 현장 베어링 수명 측정값 아님. 계산식 변수와 실제 설비 계측값의 일대일 대응 미확인. | C |
| 10 | 냉간압연 감속기 베어링 피로 손상은 비정상 윤활 상태 하에서 롤링 파라미터의 변동 폭이 클수록 악화. 예: 입출력 두께 변동폭 > 0.06일 때 베어링 수명 급격히 단축. 정상 감속기 vs 루트 크랙 결함 감속기: 결함 있는 경우 베어링 수명 더 짧음. | xu-zhang-2024 | 9–10 | 9–10 | §"The influence of the fluctuation amplitude of various rolling parameters in the rolling mill system on the service life of bearings", Figure 7 | 시뮬레이션 기반 SDAF23272 베어링. 정상/루트크랙 결함 감속기 대비. | 논문은 모델 시뮬레이션 결과. 실제 현장 베어링 손상 진행 기록 아님. 연구자 실험실 테스트(6313-2RS 자체윤활 베어링)와 혼동 금지. | C |
| 11 | 26867443.pdf의 고장 대책: 모든 작업(조립, 설치, 시동, 정비, 수리)은 훈련된 인원만 수행. 매뉴얼, 경고판, 해당 규정, 국가 안전 규정 준수 필수. 위반 시 심각한 부상/재산 피해 위험. | 26867443.pdf | 5 | 5 | §2 Safety Notes, "General information" | ML..2 & ML..V2 시리즈 | 모터 안전 주의사항은 별도 모터 매뉴얼 참조. 시동/운전 중 모니터링·보호장치 제거 금지(테스트 모드 포함). | B |

---

## 3. 카드 후보 (T1~T6)

카드 작성 가이드 §2의 유형 판정과 필수 조건을 적용하여 선별했다.

### 3.1 근거 충분 후보

해당 없음. B/C 유형 원문에서 T1(증상 해석), T2(조건부 요령), T3(확인 절차), T4(인계 방법), T5(안전 금기), T6(재가동 실패)의 필수 조건을 모두 충족하는 항목을 찾지 못했다.

**근거 부족 사유**:
- **T1**: 26867443.pdf의 고장 증상 표에 "문제 설명(Problem)" 수준의 증상만 있고, 감각 기반 이상 징후의 *해석 의미*(예: "진동 주파수 변화 → 베어링 손상")는 명시하지 않음. 단순 증상 나열에 그침.
- **T2**: 고장 대책이 문제-원인-해결책 형식인 모든 항목이 조건의 효과를 구분하지 않음. "오일 확인 후 필요시 교체" 같은 일반 권고이지, 조건에 따라 달라지는 *요령*은 아님.
- **T3**: 26867443.pdf p045의 Malfunctions 표에는 **단계별 확인 행동과 기대 결과가 모두 명시되지 않음**. 표는 "원인 후보 제시" 수준이며, "1단계: 오일 확인 → 결과 표시는 [X]" 같은 구조화된 진단 절차 없음.
- **T4**: 인계 방법(required_context, recipient_role, timing, channel, acknowledgement)이 명시된 절이 모든 매뉴얼과 논문에 없음.
- **T5**: 26867443.pdf p005의 안전 주의사항("훈련된 인원만 작업", "보호장치 제거 금지")은 고장 진단이나 조치와 무관한 일반 운영 규정. 독립적인 금지·정지·격리 지식이 아닙니다.
- **T6**: 재가동 실패 경험(tried_and_failed)이 실제 시도와 관측 결과 기록 형태로 어느 원문에도 없음. 매뉴얼의 "이렇게 하지 마라"는 매뉴얼 권고이지 실패 경험 아님.

### 3.2 판정 보류 항목

**항목 1**: 26867443.pdf §9.1 Malfunctions 표의 고장별 진단 절차화 가능성
- 주장: "비정상 소음이 규칙적 ↔ 불규칙 ↔ 장착 부위에만 발생"에 따라 베어링 손상 여부를 구분하는 것이 T3 수준의 절차일 수 있음.
- 근거 부족: 원문에는 "비정상 규칙 소음 = 베어링 손상 또는 기어 불규칙", "비정상 불규칙 소음 = 오일 이물질"이라고만 명시. 어떤 확인 행동(예: 주파수 측정, 오일 샘플 채취 등)으로 이 원인 후보를 좁히는지 *단계별 절차* 없음.
- 결론: 카드화 보류. 원문의 고장-원인 대응표가 진단 *절차*가 아니라 증상 *분류표*이므로, T3로 전환하려면 "비정상 규칙 소음을 확인하는 행동" 섹션을 별도 원문에서 찾아야 함.

**항목 2**: xu-zhang-2024의 압연 조건별 베어링 수명 예측 모델
- 주장: 압연 조건(입출력 두께, 속도, 점도) 변화에 따른 베어링 수명 변화 트렌드.
- 근거의 성질: 연구자의 비선형 결합 모델과 시뮬레이션 결과. 실제 현장 베어링 수명 측정 데이터가 아님. pp.010~014에서 연구자가 실험실에서 6313-2RS 베어링(프로젝트 설비 모델 불명)을 테스트한 결과만 제시. 논문 p001–002의 2022년 5월 26일 현장 베어링 손상 사건은 연구 배경으로만 제시되고, 그 이후 정비·복구·재발 기록 없음.
- 결론: 카드화 보류. 현장 적용을 위해서는 ① 프로젝트 GR 감속기 베어링 모델과 xu-zhang의 SDAF23272의 기술적 동등성 확인, ② 압연 공정 조건 매핑(연구의 무차원화된 변수 → 현장 계측값), ③ 모델 신뢰도(confidence)를 별도로 검증해야 함.

---

## 4. 기존 카드 중복 확인

**2026-09-23 보고서 연계 검토**: 이전 검토에서 xu-zhang-2024 논문을 기반으로 생성한 카드:
- **K-0201**: "감속기 진동 보고에서 운전 조건과 손상 판단을 구분하기" (T3 초안, 합성 사건 EV-0202 기반)
- **K-0202**: "진단 미회신 사건을 교대 인계에서 미해결로 유지하기" (T4 초안, 합성 사건 EV-0202 기반)
- **EV-0201**: "냉간압연 감속기 입력단 베어링 외륜 압흔" (비합성 사건 후보)

**xu-zhang-2024 논문과의 관계**: EV-0201은 xu-zhang-2024 p001–002의 2022년 5월 26일 현장 사건을 정리한 미완성 사건. K-0201·K-0202는 이 사건을 배경으로 하되, V-01·V-03(페르소나 v0.2)의 합성 서사로 재구성된 카드. 

**중복 판단**:
- 본 검토(2026-09-25)에서 xu-zhang-2024 원문 재확인 결과, 2026-09-23 보고서의 "조치 기록 부족, 복구 성공 절차 미확정" 판단과 **일치**.
- 26867443.pdf (SEW 매뉴얼)의 고장 대책은 일반 제조사 지침이므로, 기존 K-0201·K-0202의 내용과 **직접 계보 중복 아님**. 단, K-0201의 "T3 진단 절차" 원형이 26867443.pdf의 §9.1 Malfunctions 표에 일부 포함될 수 있으나, 이미 지적한 대로 "진단 절차"로 성숙하지 못함.
- 결론: **기존 K-0201·K-0202와 내용 중복 없음. 원문 계보 중복도 없음.**(기존 카드는 합성 사건 기반, 본 검토 대상은 제조사 매뉴얼/연구논문)

**docs/data/knowledge_cards/ 기존 카드와의 교차 확인**:
- 26867443.pdf의 고장 대책 표는 다른 SD-/M- 출처의 기존 카드에서도 인용할 수 있는 일반 제조사 지침. "고장 원인 후보 목록" 형태의 내용이므로, 기존 KB의 T1(증상 해석) 카드와 가능한 참고 관계(supporting_evidence)는 있으나, 직접적인 중복은 아님.

---

## 5. 등록부 매칭

source_registry.json 기준으로 각 파일의 매칭 상태.

| 파일 | 매칭 source_id | 매칭 근거 | 현재 review_status | approved_scope | 판정 |
|---|---|---|---|---|---|
| 26867443.pdf | M-02 가능성 검토 필요 | 등록부의 M-02: "SEW-EURODRIVE - Possible malfunctions/remedy" (URL: download.sew-eurodrive.com/html/31981496/en-EN/25440305419.html). 본 파일은 "Installation and Operating Instructions – ML..2 & ML..V2 Series" 문서. 같은 제조사이나 URL·문서번호·절 범위 명시 필요. 원문에서 확인된 제조사 표기: "© 2021 - SEW-EURODRIVE". 정확한 매칭 확인 필요. | pending_review | 빈 배열 | **매칭 확인 필요**: 등록부 M-02와 동일 문서인지, 부분 중복인지, 별개 문서인지 판정 필요. URL 검증 및 approved_scope 별도 검토 필수. |
| 26873427.pdf | 등록부에 직접 매칭 없음 | 파일명과 내용(카탈로그, ML2/V2 시리즈)으로 보아 제조사 SEW-EURODRIVE. 등록부에서 찾은 유사 항목 없음. | — | — | **미등록 출처**: 신규 source_id 필요 (예: M-10). 제안: title="SEW-EURODRIVE Catalog ML..2 & ML..V2 Series", url=미확인, purpose="제품 기술 데이터 및 선택 부품", document_version=미기재. |
| Failure analysis and countermeasures of gearbox in cold rolling mill.pdf | 등록부에 직접 매칭 없음 | 웹 기사 (wgt.asia 도메인). 제조사·문서번호 없음. 등록부의 SD-008 "IspatGuru, Historical Development of Rolling Mills"와 다른 출처. | — | — | **미등록 출처**: 저작권·인용 권한 확인 필수. 제한적 사용 가능성. |
| Roll Drive Design Considerations for Steel Mill Rolling Operations.pdf | 등록부에 직접 매칭 없음 | White Paper, 저자: Patrick M. Laughery & Dan Rosseljong. 제조사/정확한 출처/URL 미기재. Sumitomo Cyclo 제품 설명 포함. | — | — | **미등록 출처**: 신규 등록 제안(선택). title="Roll Drive Design Considerations for Steel Mill Rolling Operations", purpose="감속기 설계 가이드 및 산업 표준", document_version 미기재. |
| roller-table (1).pdf | 등록부에 직접 매칭 없음 | 제조사: WEG, 제품: Roller Table Motors. 등록부에 WEG 관련 항목 없음. | — | — | **미등록 출처**: 신규 등록 제안(선택). title="WEG Roller Table Motors Technical Catalogue", url=미확인, purpose="롤러테이블 모터 제품 사양", document_version="European Market". |
| xu-zhang-2024-research-on-the-service-life-of-bearings... | 등록부 SRC-XU-ZHANG-2024-NONSTEADY-LUBRICATION 매칭 (2026-09-23 보고서 기준) | 등록부 미확인. 2026-09-23 보고서에서 xu-zhang-2024 논문을 "SRC-XU-ZHANG-2024-NONSTEADY-LUBRICATION" 그룹명으로 할당했으나, source_registry.json에 아직 공식 등록되지 않은 것으로 보임. | pending_review (추정) | 빈 배열 (추정) | **기존 계보 매칭**: 2026-09-23 보고서의 제안 그룹 이름 확인. approved_for_draft 전환 전에 ① 논문의 현장 관측 부분과 연구 결과의 분리, ② 카드 주장의 근거로 사용 범위 명시 필요. 현재 상태: approved_scope 없으므로 "검토용 후보. 생성 파이프라인·운영 KB 투입 금지". |

**미등록 출처 목록 및 등록 제안**:
1. **26873427.pdf**: SEW-EURODRIVE ML..2 & ML..V2 Catalog
   - 제안 source_id: M-10 (또는 M-02의 보조 카탈로그로 alias 연결)
   - title: "SEW-EURODRIVE Catalog - ML..2 & ML..V2 Series Helical and Bevel-Helical Gear Units"
   - purpose: "제품 기술 사양, 기어 옵션, 선택 부품"
   - URL: 미확인 (등록 전 확인 필요)
   - document_version: Catalog 판본 미기재
   - 확인 필요: M-02와의 관계, 사용 권한

2. **roller-table (1).pdf**: WEG Roller Table Motor Catalog
   - 제안 source_id: M-11
   - title: "WEG Roller Table Motors - Technical Catalogue European Market"
   - purpose: "롤러테이블 구동 모터 제품 사양 및 기능"
   - URL: weg.net (미확인)
   - document_version: European Market (발행연도 미기재)
   - 확인 필요: 프로젝트 RT 설비와의 모델 대응

3. **Failure analysis and countermeasures of gearbox in cold rolling mill.pdf**: Web Article
   - 제안 source_id: WEB-001 (또는 별도 카테고리)
   - title: "Failure analysis and countermeasures of gearbox in cold rolling mill"
   - URL: https://www.wgt.asia/new/new-62-974.html (2026-09-22 확인)
   - purpose: "감속기 고장의 일반적 원인 설명 (사례 본문 부족)"
   - 확인 필요: 저작권, 복제 권한, 가용성 (웹 기사는 지속성 불명)

4. **Roll Drive Design Considerations...**: White Paper
   - 제안 source_id: M-12 (또는 WP-001)
   - title: "Roll Drive Design Considerations for Steel Mill Rolling Operations"
   - purpose: "롤 드라이브 감속기 설계 기준 및 Sumitomo Cyclo 평가"
   - author: Patrick M. Laughery, Dan Rosseljong
   - document_version: 미기재
   - 확인 필요: 발행처, URL, 사용 권한

---

## 6. 부족한 근거

| 항목 | 원문의 부족 사항 | 미검토 범위 | 확인 페이지까지 |
|---|---|---|---|
| GR-1 | 26867443.pdf의 §9.1 Malfunctions에는 "고장-원인 후보-해결책" 표가 있으나, 각 원인 후보를 확인하기 위한 **단계별 진단 행동과 기대 결과**가 없음. T3 카드 작성 불가. | §8 Inspection and Maintenance (p041–p044) 미검토. 정비 절차에서 진단 관련 내용이 있을 수 있음. | p045까지 확인 후 p041–p044 건너뜀 |
| GR-2 | 26873427.pdf의 카탈로그는 제품 사양만 있고, 실제 고장 사례나 진단 절차 없음. | 전체 86 페이지 중 p003만 목차 확인; 기술 데이터(§4–5, p030–p065) 미검토. | p003까지만 |
| GR-3 | Failure analysis and countermeasures of gearbox in cold rolling mill.pdf는 p002에서 "Specific cases of failure analysis"를 예고하나, p003에는 본문 없고 관련 링크만 있음. **실제 냉간압연 감속기 사례의 원인·조치 기록 부족.** | 3 페이지만 있음. 전부 검토. 추출 가능한 추가 내용 없음. | p003까지 (전부) |
| GR-4 | xu-zhang-2024 논문의 현장 관측 부분(p001–p002의 2022년 5월 26일 베어링 손상): 손상 사실만 기술되고, 이후 **정비 절차, 복구 성공 여부, 재발 확인 기록 없음.** 논문의 메인 내용(pp.003–015)은 연구자의 모델·시뮬레이션·실험실 테스트이므로 현장 사건 기록이 아님. T3/T4/T6 카드화 불가. | pp.010–015의 실험실 베어링 피로 테스트 상세 결과(Figure 8–13, 모델 검증) 미검토. | p010까지 검토; p011–015 건너뜀 |
| GR-5 | 모든 매뉴얼 파일에서: 카드 작성 필수 조건인 **적용 조건(product model, operating condition, environment)과 예외 조건(warning, must not)이 일반적 형태**로만 기술. 냉간코일 공장 GR 설비의 실제 모델, 운전 범위, 환경 조건과의 구체적 매핑 없음. T2 조건부 요령 작성 불가. | 모든 파일 | 각 파일별 p001–p006까지만 집중 검토 |

---

## 7. 담당자 확인 질문

카드 후보 선별 단계에서 해소하지 못한 미결 항목:

| 질문 | 필요 이유 | 대상 담당자 |
|---|---|---|
| 1. 26867443.pdf (SEW ML2/V2 설치·운전 지침)가 source_registry.json의 M-02 "SEW-EURODRIVE - Possible malfunctions/remedy"와 동일 문서인가? 아니면 별개 문서인가? | 등록부 매칭을 위해 URL, 문서번호, 각 절(고장 대책 섹션)의 정확한 범위를 확인해야 함. M-02가 이미 approved_for_draft 상태라면, 26867443.pdf를 별도 source_id로 등록하거나 alias 처리해야 함. | 프로젝트 Source 관리자 |
| 2. xu-zhang-2024 논문의 2022년 5월 26일 현장 사건(냉간압연 제2 스탠드 감속기 베어링 손상, 120시간 정지)에 대해, 프로젝트 GR 설비와의 기술적 동등성이 있는가? (제조사, 모델, 베어링 타입 비교) | 논문은 SDAF23272 자정렬 롤러 베어링을 기준하나, 프로젝트 GR의 실제 베어링 모델이 무엇인지 확인 필요. 다른 모델이면 압연 조건별 수명 예측 카드의 적용 범위 제한. | 설비 엔지니어 / 프로젝트 PM |
| 3. 26867443.pdf의 고장 증상 표(§9.1 Malfunctions)에서 "비정상 규칙 소음 = 베어링 손상 OR 기어 불규칙"으로 원인 후보를 제시하는데, 이 두 원인을 **현장에서 추가로 구분하기 위한 진단 절차**가 별도 원문에 있는가? (예: 진동 주파수, 오일 샘플 분석, 수동 촉각 등) | T3 카드 작성을 위해 확인 행동(action)과 기대 관측(expected_result)의 원문 출처 필요. 없으면 현장 전문가 인터뷰나 별도 절차 문서 필요. | 현장 정비사 / 설비 엔지니어 |
| 4. 26867443.pdf의 안전 주의사항(§2 Safety Notes, p005의 "훈련된 인원만 작업", "보호장치 제거 금지")이 카드화 가능한 **독립적인 T5 (안전 금기/격리 지식)**인가, 아니면 모든 조치에 딸린 일반 안전 선언인가? | T5는 "금지·정지·격리 자체가 핵심"인 경우만 분리. 본 문구는 모든 정비 작업의 전제 조건이므로 safety_flag로 표시할 가능성이 높음. 확인 필요. | 안전 담당자 / 프로젝트 설계자 |
| 5. 현재 카드 작성 가이드(v1.1)에서 T3의 "단계별 확인 절차"는 원문의 명시된 단계 번호를 따르도록 명시되어 있는데, 26867443.pdf처럼 "고장-원인-해결책" 표 형식의 원문을 T3로 변환할 때 원문 단계 구조가 명확하지 않은 경우 어떻게 처리하는가? | 카드 생성 정책(source-and-split-contract.md)에서 "단계 수만으로 분류하지 않음"이라고 명시했으므로, 표 형식 원문의 T3 전환 기준을 명확히 해야 함. | 프로젝트 설계자 / KB 운영팀 |

---

## 8. 검토 한계

### 미검토 범위 명시

- **26867443.pdf**: §8 Inspection and Maintenance (p041–p044) 미검토. 정기 정비 절차와 진단 방법이 있을 가능성 있음.
- **26873427.pdf**: §4–5 Technical Data (p030–p065, 약 36쪽) 미검토. 기술 사양만 포함하고 고장 대책은 없을 것으로 예상되어 건너뜀.
- **Roll Drive Design..., roller-table (1).pdf**: 전체 페이지 검토 건너뜀. 카탈로그/설계 가이드이므로 실제 현장 사건 기록 없음으로 판단.
- **xu-zhang-2024**: pp.010–015의 실험실 베어링 피로 테스트 상세 결과, 모델 검증 계산식 미검토. 현장 원문 검색 완료 후 연구 모델 세부사항은 생략.

### 추출 불가 페이지

각 파일별 추출 불가 페이지 표시:
- 26867443.pdf: p001 (인코딩/렌더링 오류), 추가 2장
- 26873427.pdf: p001 (인코딩/렌더링 오류), 추가 2장
- 나머지 4개 파일: 추출 가능

### 판단 차이 (2026-09-23 보고서 대비)

- **Failure analysis and countermeasures...**: 동일. 본문 부족으로 보류.
- **xu-zhang-2024**: 동일. 현장 사건 배경 언급이나 조치 기록 부족, 논문 모델/테스트 중심. 다만, 본 검토에서는 "현장 관측 부분(손상 사실)과 연구 결과(모델/시뮬레이션)의 구분" 판단을 더 명시적으로 기록했음.

### 이전 판단과 일치 여부

- xu-zhang-2024: **완전 일치**. 2026-09-23 보고서의 "원문 보고 사건 1건(EV-0201), 미완성, 복구 성공 절차 근거로 사용 불가" 판단 재확인. 추가로 현장 관측 vs 연구 결과의 구분 강조.
- Failure analysis...: **일치**. "사례 본문 부족으로 보류" 재확인.

### 특히 주의할 점

1. **SEW 매뉴얼(26867443.pdf)의 고장 대책은 제조사 일반 지침**: 냉간코일 공장의 특정 감속기 모델(예: ML2.5/0.75, ML3/1 등)에 일반적으로 적용되는 표준 고장 증상-원인-해결책이므로, 이를 현장 정비 절차로 직접 옮기지 않음. 프로젝트 GR 설비의 실제 제조사·모델·운전 조건이 SEW 매뉴얼의 가정과 일치하는지 별도 확인 필수.

2. **xu-zhang-2024 논문의 모델과 현장의 차이**: 논문의 비선형 결합 모델은 이상화된 압연 공정(입출력 두께, 압연 속도, 오일 점도의 순수 변수)을 가정. 실제 냉간코일 공장의 감속기는 기계적 마모, 서멀 사이클, 로드 변동의 돌발성, 윤활 공급 중단 등 모델에 없는 인자가 작용. 시뮬레이션 수명 예측을 절대값으로 신뢰할 수 없음.

3. **카드 작성 기준과 원문 형태의 불일치**: 본 검토의 모든 B(매뉴얼/카탈로그) 원문은 "고장 증상 → 원인 후보 → 해결책" 형식이므로, T3(확인 절차)의 필수 조건인 "단계별 확인 행동과 기대 관측 결과"를 구조적으로 제공하지 않음. 원문을 카드화하려면 현장 정비 규범이나 별도 절차 문서로 보충해야 함.

---

## 요약 통계

- **원문 분류**: A 0건, B 3건, C 3건
- **카드 후보 수**: 0건 (근거 충분 후보 없음)
- **판정 보류 항목**: 2개
- **부족한 근거 항목**: 5개
- **담당자 확인 질문**: 5개
- **미등록 출처**: 4개 (26873427.pdf, Failure analysis, Roll Drive, roller-table)
- **approved_for_draft 미승인 출처 기반 후보**: 0건 (후보 자체가 없음)
- **2026-09-23 보고서와 판단 차이**: 0건 (Failure analysis, xu-zhang-2024 판정 동일)

**특히 주의할 점**:
- SEW 매뉴얼의 고장 대책은 제조사 표준이므로 프로젝트 GR 모델·조건과의 일치 확인 필수.
- xu-zhang-2024의 시뮬레이션 결과는 연구자 모델이지 현장 측정값이 아님. 현장 적용 전 별도 검증 필요.
- 카드 작성 기준 v1.1의 T3 필수 조건("단계별 확인 행동과 기대 관측 결과")을 원문이 제공하지 않아 카드화 불가. 현장 절차 규범과 매뉴얼의 매핑 작업 필요.

---

## 9. 검증 결과

별도 검증에서 **근거표의 각 주장이 적힌 페이지 텍스트에 실제로 있는지만** 대조했다. 중간 기록은 `artifacts/source-card-review-20260925/verify/GR-verify.md`에 있다(Git 제외). 불일치는 위 표에서 지우지 않고 아래에 표시한다.

| 항목 | 건수 |
|---|---|
| 대조한 주장 | 11 |
| 일치 | 10 |
| 부분 일치 | 1 (표 경계 페이지 표기) |
| 불일치 | 0 |
| 다른 페이지에 있음 | 0 |
| 확인 불가 | 0 |

절·표 위치(§9.1 Malfunctions p045, §2 Safety Notes p005, Figure 6~7 p008~p010)와 인쇄 페이지는 모두 일치했다. 문서 정체 주장 6건(SEW-EURODRIVE ©2021 / SEW 카탈로그 발행연도 미기재 / wgt.asia 기사 / Laughery·Rosseljong 백서 / WEG European Market 카탈로그 / Xu·Zhang DOI 10.1177/16878132241276941, 2024)은 모두 해당 페이지에서 확인됐다.

### 9.1 후보 0건 판정의 일관성 확인

같은 검토의 HPU·RT 폴더는 성격이 비슷한 제조사 매뉴얼에서 T5 후보를 여러 건 올렸으므로, 기준 적용이 엇갈렸는지 별도로 대조했다.

| 파일 | 확인한 금지·정지 문구 | safety_basis 근거 | T5 필수 조건 |
|---|---|---|---|
| 26867443.pdf | p005 §2 Safety Notes(훈련된 인원만, 보호장치 제거 금지), p006·p037 운송·시스템 구성 요건 | 특정 고장·조치와 연결된 근거 없음 | **충족 근거 없음** |
| roller-table (1).pdf | 경고·금지 문구 극소(모터 제품 카탈로그) | 없음 | **충족 근거 없음** |

**판정: 후보 0건이 원문과 일치한다.** 기준을 엄격히 적용한 결과이며, 다른 폴더보다 기준이 달랐던 것이 아니다.

### 9.2 xu-zhang 논문의 사건 서술 판정

| 구분 | 내용 | 페이지 |
|---|---|---|
| 현장 관측 사실 | 2022-05-26 냉간압연 제2 스탠드 베어링 손상, 120시간 정지 | p001~p002 |
| 연구자 계산·실험 | 시뮬레이션과 실험실 피로 시험(6313-2RS 베어링) | p008~p010 |
| 선행 문헌 인용 | 없음 | — |
| 정비·조치·복구 기록 | **없음** | — |

원문에 손상 발생과 정지 시간까지는 있으나 확인 과정·수행 조치·복구 결과가 없다. `docs/data/events/README.md`의 사건 요건(오류 → 확인 → 조치 → 결과)을 충족하지 않으므로 분류 A로 올리지 않은 판정이 유지된다. 120시간 정지는 논문이 배경으로 적은 값이며 독립 검증된 정비 원장이 아니다.

### 9.3 검증에서 별도로 확인한 등록부 기재 오류

이 두 건은 위 §5 표에 남겨 두고 여기에 정정 사실만 표시한다.

| 위치 | 기재 내용 | 현재 등록부 확인 결과 |
|---|---|---|
| §5 xu-zhang 행 | 매칭 `SRC-XU-ZHANG-2024-NONSTEADY-LUBRICATION`, review_status `pending_review (추정)` | `SRC-XU-…`는 출처 ID가 아니라 2026-09-23 보고서가 제안한 **split 그룹 ID**다. `seeds/source_registry.json`에 이 논문 항목은 **없다**. 따라서 상태를 추정하지 말고 **미등록 출처**로 두어야 한다. |
| §7 질문 1 | "M-02가 이미 approved_for_draft 상태라면" | M-02의 현재 `review_status`는 **pending_review**이고 `approved_scope`는 빈 배열이다. |

이 정정을 반영하면 GR 폴더의 실질 미등록 출처는 **5건**이다(§5 표의 4건 + xu-zhang). `26867443.pdf`는 M-02와 동일 문서인지 미확정이라 별도로 "매칭 확인 필요"로 남는다.
