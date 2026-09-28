# T4 인수인계 지식카드 원문 검토 결과

검토 기준일: 2026-09-25. **유효 초안 0 / 목표 25 / 부족 25.** 아래 8건은 카드가 아닌 보완 대기 후보다. 출처 승인·안전 검토·카드 채택을 수행한 사람이 없으며, 이를 완료로 표시하지 않았다.

## A. 검토한 원문과 근거 위치

지정한 다섯 기준 파일과 페르소나 파일(v0.2, V-11–V-13), 출처·분할 계약 및 등록부를 확인했다. `KnowledgeCard` 계약 버전은 1.1이다. PDF 26개(1,047쪽)와 HTML 1개를 텍스트 추출·관련어 탐색하고 아래 절을 중심으로 읽었다. 전체 1,047쪽을 시각 정독했다는 뜻은 아니다. 핵심 근거 8쪽은 렌더링해 문단·표·도식의 문맥을 확인했다. 텍스트가 적은 표지·도면 등은 인계 근거로 채택하지 않았다. 원문 SHA-256과 기준 입력 해시는 [sources.json](sources.json)에 있다.

PDF 위치는 파일의 1부터 시작하는 페이지다. 인쇄 쪽수가 다른 경우 병기했다. 분류는 보관본에 적힌 내용의 성격이며, 공개 사례를 독립 검증된 현장 사건으로 승인한 결과가 아니다. 프로젝트 기준의 **확인된 실제 사건은 0건**을 유지한다.

| 원문 (`docs/data/events/` 아래) | 분류 | 검토 위치 | 판단·사용 한계 |
|---|---|---|---|
| `CV/brochure-conveyor-solutions-handbook-4230-en.pdf` | 제품 핸드북 | PDF p.1, 3, 5 및 제품별 절 | Edition 2; 벨트·부품 선정 자료. 제품별 문의를 교대 인계로 바꾸지 않음. |
| `CV/Convey-All-TroubleshootingGuide.pdf` | 제품 고장 지침 | PDF pp.1–4, Troubleshooting Guide | 증상·가능 원인·권장 대책 표. 실제 조치·결과나 인계 절차가 아님. |
| `CV/conveyor-manual-0323-en.pdf` | 제품 운전 매뉴얼 | PDF p.9(인쇄 p.5) §§3.1, 3.1.2; p.10(6) §3.1.3; p.69(65) §§10, 10.1 | December 2022. 보고·운전측 반환·교육 서명이 서로 다른 문맥. 프로젝트 CV 모델 대응 미확인. |
| `CV/Martin_C4_CR_18_09_4_Manual.pdf` | 제품 설치·정비 매뉴얼 | PDF pp.2–5 안전; pp.7–15 점검·고장 표 | 작업 안전과 아이들러 정비 지침. 고장 문의 권고는 있으나 인계 수신 확인 없음. |
| `GR/26867443.pdf` | 제품 설치·운전 매뉴얼 | PDF p.4 §1.1; p.45 §9.1 Customer service; pp.53–61 Contact Information | ML..2 & ML..V2. 문의 시 명판·고장 범위·발생 시점·주변 상황·추정 원인. 연락처 목록은 인계 채널의 의무 규정이 아님. |
| `GR/26873427.pdf` | 제품 카탈로그 | PDF pp.3–6, Contents/Introduction/Product Description | ML..2 & ML..V2 제품 소개·설계 자료. 운전 지침 26867443.pdf와 같은 문서로 합치지 않음. |
| `GR/Failure analysis and countermeasures of gearbox in cold rolling mill.pdf` | 일반 설명·사건 후보 단편 | PDF pp.1–2; p.2 Specific cases of failure analysis; p.3 | 사건 도입문 뒤 상세 분석이 보관본에 없음. 제목만으로 완성된 고장 대응 사례로 계산하지 않음. |
| `GR/Roll Drive Design Considerations for Steel Mill Rolling Operations.pdf` | 설계 백서·제품 배경 | PDF pp.3–5 Introduction; p.10 Availability | 구동계 설계와 공급 서비스 설명. 현장 사건이나 인계 규정 아님. |
| `GR/roller-table (1).pdf` | 제품 카탈로그 | PDF pp.1–4 Roller Table Motor | WEG 유럽시장 전동기 기술 카탈로그. 롤러 테이블 모터와 감속기를 동일 설비로 간주하지 않음. |
| `GR/xu-zhang-2024-research-on-the-service-life-of-bearings-in-the-gearbox-of-rolling-mill-transmission-system-under-non.pdf` | 연구·현장 고장 언급 후보 | PDF pp.1–2 서론; pp.12–14 수명 검증·Conclusion | 2024, Vol.16(9), DOI 10.1177/16878132241276941. 고장·관측·수명 연구를 인계 수행·복구 기록으로 바꾸지 않음. |
| `HPU/100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf` | 범용 진단 지침·가정 예시 | PDF pp.3–4 Line Service/Checking Faults; p.9 Machine malfunction procedure; p.34 Algo 0.6; p.35 가정 예시 | 재가동 예고와 인지 여부 분기는 있으나 회신 방법 미기재. p.34의 safety interlocks 제거 문구는 작업 지침으로 채택하지 않음. p.35 Assume 예시는 실제 사건 아님. |
| `HPU/AX189986484780en-000501.pdf` | 제품 서비스 매뉴얼 | PDF pp.2–6 판본·Introduction; pp.37–39 Troubleshooting | D1 High Power Open Circuit Pumps, October 2024. 공장 인증 서비스망 설명은 수신 확인 절차가 아님. |
| `HPU/AX549927744283en-000201.pdf` | 제품 서비스 가이드 | PDF pp.2–3 §§1.1–1.2; p.21 §7 | PVMX, 2026.09. 유지보수·진단 권고. 적용 펌프와 인계 방법 미확인. |
| `HPU/HY13-PMDSPS1M_US.pdf` | 제품 설치·정비 매뉴얼 | PDF p.4 목차; p.26(인쇄 p.22) Field and factory service; pp.38–39 Offer of Sale | 스크루 펌프 서비스 지원·계약 문구. 계약 acknowledgement를 현장 인계 수신 확인으로 사용하지 않음. |
| `HPU/HY29-0022-UK.pdf` | 제품 고장 분석 지침 | PDF p.3(인쇄 p.4) §§1.1–1.2; p.53(54) §4.2 | Denison vane pump/motor 고장 사진·진단 표. 특정 공장 사건·실행된 조치·보고 체계 없음. |
| `HPU/MAN-C-012.pdf` | 제품 유지보수 수첩·빈 양식 | PDF p.3(인쇄 p.4) HPU identification; p.8(9) §2; pp.9–11(10–12) §3 | MAN-C-012-EN/0. 날짜·작업 유형·내용·작업자·서명 양식. 서명은 인수자의 수신 확인으로 명시되지 않음. |
| `HPU/ServMan_DHM.pdf` | 제품 서비스 매뉴얼 | PDF pp.1–4; p.2 Trouble Shooting Guide | Series D/H/M, Bulletin 2630-C1, January 2000. 권장 정비와 고장 표이며 실제 사례 아님. |
| `RT/1110_Roller_conveyor_EN_TNr_1131919_V1.0.pdf` | 제품 설치·운전 매뉴얼 | PDF p.6 Introduction; p.8 Intended use; p.36 사고·고장; pp.51–53 진단·부품 | SH 1110, Version 1.0 (06/2022). 후속 운전자에게 매뉴얼 전달, 자격자 통보는 있으나 수신 확인 없음. 상자·포장 식품 등 적용 설명으로 냉간코일 RT 모델 일치 미확인. |
| `RT/830CC-V1.pdf` | 제품 매뉴얼·외부 운송 검사 포함 | PDF pp.1–3 식별·검사; p.12 Lift Blocking Instructions; p.21 윤활 문의 | Trojan Coil Car, Version 1.0, 09/2001. p.3 운송 손상 서면 신고는 공장 내부 고장 인계 범위 밖. RT 적용 모델로 매핑하지 않음. |
| `RT/Coil-Cars.pdf` | 제품 매뉴얼 | PDF pp.1–4 식별·Introduction; pp.8–9 안전 | Southworth, July 2015. 문의 창구와 사용 전 숙지. 프로젝트 RT 적용 모델이나 수신 확인 방식 미확인. |
| `shared/FUCHS-RENOLIT-CXS-AM-1.html` | 제조사 공개 사례·제품 홍보 | HTML main: Case Study - RENOLIT CXS AM 1 / Challenge / Application / Solution / Results | Application은 Cold Rolling Mill Work - Roll Bearing & Chock Lubrication을 명시. 원문에 시험·교육·효과 주장이 있으나 프로젝트 설비 대응·고장 인계 방법·독립 현장 검증은 없음. |
| `shared/hydraulic_maintenance.pdf` | 범용 교육 슬라이드 | PDF pp.4–7 Mentally Prepare / Obtain Documentation / Starting the Process / Predictability | 도면 확보·증상 파악·예측의 교육 자료. 현장 수행 기록이나 통보 수신 확인 아님. |
| `shared/NSK-Case-Study-Cold-Rolling-Mill_SteelStrip.pdf` | 제조사 공개 냉간압연 사례 | PDF pp.1–2 Key facts / Value proposals / Product features | 철분 유입·베어링 분석·제품 변경 및 수명 개선 주장. GR/RT 부품 대응과 인계 행위 미확인. |
| `shared/Rolling mill bearing reliability_ three case studies, one conclusion - Euro Bearing.pdf` | 유통사 공개 사례·일반 권고 | PDF p.2 The cold mill with a vibration problem nobody could locate; p.3 What a rolling mill programme should actually contain | 냉간압연 백업롤 사례와 로그 권고. 열간·형강 사례는 별도 범위. 익명 사례의 1차 기록·인계 방법 미확보. |
| `shared/shell-sls-whitepaper-02-v7edited.pdf` | 윤활 백서·공개 홍보 사례 | PDF pp.3–8 이슈 설명; p.11(인쇄 p.09) Shell Tellus in action | wire rod mill·기타 유압 적용의 효과 주장. 냉간코일 공정 대응·인계 원문 미확보. 표의 사례를 자동 Event화하지 않음. |
| `shared/SKF-10404_EN_Driveline_for_Metals.pdf` | 제품·서비스 배경 자료 | PDF pp.1–2 Drivelines / SKF 360° Solution | 구동계 신뢰성·서비스·유지보수 투자 설명. 오류→실제 조치→결과→인계가 연결된 사건 기록 아님. |
| `shared/Troubleshooting.pdf` | 범용 안전·정비 지침 | PDF pp.13–15 §1.5; pp.24–27 §3; pp.86–87 Annex 1 B; p.92 Annex 1 F | DGUV Information 209-071, March 2015. 독일 자료의 보관 판본 검토이며 국내 현장 표준·현행 법률 확인이 아님. |

README를 그대로 사실 판정으로 복사하지 않았다. 특히 FUCHS HTML은 냉간압연 적용과 시험·교육·효과 주장을 실제로 포함한다. 다만 고장 인계의 다섯 항목과 프로젝트 설비 대응을 뒷받침하지는 않는다. README에 개별 기재되지 않은 추가 파일도 이번 검토 목록에 포함했다.

등록부의 외부 원문 항목은 `pending_review`이며, 기존 합성 일지 SD-901–SD-912의 `approved_for_draft`에는 `reviewed_by="ai-assisted-synthetic-narrative; 사람 승인 아님"`이 기록돼 있다. 이를 사람의 승인이나 새 원문의 승인으로 사용하지 않았다. 등록부·분할표·기존 카드·DB는 변경하지 않았다.

## B. T4 후보별 다섯 필드의 근거 표

`확인`은 아래의 제한된 문구가 원문에 있다는 뜻이며 현장 승인 상태가 아니다. `부분`과 `없음`은 필수값에 넣지 않았다. Q 번호는 이 보고서의 행 번호일 뿐 카드 ID가 아니다. 각 근거 표지는 아래 근거 위치 목록 및 `sources.json`의 실제 발췌문에 연결된다.

| 후보 | required_context | recipient_role | timing | channel | acknowledgement |
|---|---|---|---|---|---|
| Q01 제조사 고장 문의에 식별·발생 맥락을 묶어 전달 | 확인: 명판 전체 정보 / 고장의 성격과 범위 / 발생 시점과 동반 상황 / 추정 원인 [SEW-FAULT] | 확인: SEW-EURODRIVE 고객 서비스 [SEW-FAULT] | 확인: 고객 서비스에 고장을 문의할 때 [SEW-FAULT] | 없음: 연락처 목록은 있으나 고장 인계에 사용할 채널의 선택·사용 절차 미확인. [직접 근거 없음] | 없음: 문의 접수·내용 이해를 확인하는 방법 미기재. [직접 근거 없음] |
| Q02 고장·안전결함을 담당 조직에 즉시 알리기 | 확인: 발견한 고장·오류 또는 안전결함 [DGUV-REPORT, MISUMI-SAFETY] | 확인: 상급자 또는 정비 부서; 안전결함은 상급자 [DGUV-REPORT, MISUMI-SAFETY] | 확인: 발견 시 즉시 [DGUV-REPORT, MISUMI-SAFETY] | 없음: 전화·무전·시스템 등 보고 채널 미기재. [직접 근거 없음] | 없음: 보고를 받은 측의 회신·내용 확인 방식 미기재. [직접 근거 없음] |
| Q03 정비 예정 사실을 작업 전 표지로 알리기 | 확인: 정비 작업을 실시한다는 사실 [DGUV-MAINT-NOTICE] | 확인: 모든 직원 [DGUV-MAINT-NOTICE] | 확인: 정비 작업을 시작하기 전 [DGUV-MAINT-NOTICE] | 확인: 제어반·차단기·액추에이터·접근부 등의 정비 표지 [DGUV-MAINT-NOTICE] | 없음: 표지를 게시한 뒤 대상 직원의 수신·이해를 확인하는 방법 없음. [직접 근거 없음] |
| Q04 재가동 예정 사실을 미리 알리고 인지 여부 확인 | 확인: 기계·시스템이 재가동될 예정이라는 사실 [DGUV-RESTART] | 확인: 직원; Vickers 도식은 모든 인원 [DGUV-RESTART, VICKERS-AWARE] | 확인: 재가동 전에 [DGUV-RESTART] | 확인: 경보를 울리거나 모든 인원에게 알림(Vickers 도식의 선택지) [VICKERS-AWARE] | 부분: 인지 여부의 질문은 있으나 누가 어떤 응답으로 확인하는지 미기재. 경보 송출 자체는 수신 확인이 아님. [VICKERS-AWARE] |
| Q05 고장 처리 후 운전 담당자에게 반환할 때 인계 | 부분: 고장 수정·기능시험 선행 맥락은 있으나 무엇을 전달할지 명시된 정보 목록 없음. [MISUMI-RETURN] | 확인: 운전 담당자 [MISUMI-RETURN] | 확인: 문서 절차상 시험 운전 다음, 운전 담당자에게 반환하는 단계 [MISUMI-RETURN] | 없음: 반환·인계에 쓰는 전달 채널 없음. [직접 근거 없음] | 없음: 인수자의 확인 절차 없음. 시험 운전은 수신 확인이 아님. [직접 근거 없음] |
| Q06 정비 내용과 변경 이력을 추적 가능한 기록으로 남겨 전달 | 확인: 날짜·작업 유형·내용·작업자 / 실시 작업 단계·설정값과 변경 내용 [ATOS-LOG, DGUV-LOG] | 없음: 기록 작성자와 maintenance manager 표기만으로 인계 수신자를 지정할 수 없음. [직접 근거 없음] | 없음: 기록 대상은 있으나 인계 마감·교대 시점은 미기재. [직접 근거 없음] | 확인: 수리·정비 수첩, 기계 문서 또는 정비 로그 [ATOS-LOG, DGUV-LOG] | 부분: 작업자 Signature 칸은 있으나 인수자 서명이라는 근거 없음. [ATOS-LOG] |
| Q07 진단 시작 시 운전자 설명과 과거 고장 로그를 대조 | 확인: 오류 거동·고장·기계와 시스템의 반응 / 기존 정비 수첩·로그가 있으면 같거나 유사한 과거 고장 [DGUV-INTERVIEW] | 부분: 운전자는 질문 대상이지만 질문을 받는 정보를 인수할 담당 역할은 해당 문장에서 명시되지 않음. [DGUV-INTERVIEW] | 확인: 고장 진단을 시작할 때 [DGUV-TIMING] | 확인: 운전자에게 질문하고, 기존 정비 수첩·로그가 있으면 조회 [DGUV-INTERVIEW] | 부분: 진단용 질문·이력 조회는 인계 내용의 되읽기·수신 확인 절차로 명시되지 않음. [DGUV-INTERVIEW] |
| Q08 운영 지침을 전달하고 이해 여부를 서명으로 확인 | 확인: 운영 지침과 그 안의 안전 정보가 포함된 완전한 매뉴얼 [MISUMI-BEFORE, MISUMI-SIGN] | 확인: 매뉴얼을 이해해야 하는 직원·운전자 [MISUMI-SIGN, MISUMI-OPERATORS] | 확인: 최초 시운전 전에 운영 지침을 읽음 [MISUMI-BEFORE] | 확인: 설비 구역에서 항상 이용할 수 있는 완전한 운영 매뉴얼 사본 [MISUMI-SIGN] | 확인: 직원이 운영 지침을 이해했음을 서명으로 확인 [MISUMI-SIGN] |

| 근거 표지 | 파일·쪽·절 |
|---|---|
| SEW-FAULT | `GR/26867443.pdf`, PDF p.45, §9.1, Customer service |
| DGUV-REPORT | `shared/Troubleshooting.pdf`, PDF p.24, §3 Troubleshooting |
| MISUMI-SAFETY | `CV/conveyor-manual-0323-en.pdf`, PDF p.9, 인쇄 p.5 §3.1.2 |
| MISUMI-RECUR | `CV/conveyor-manual-0323-en.pdf`, PDF p.69, 인쇄 p.65 §10 |
| DGUV-MAINT-NOTICE | `shared/Troubleshooting.pdf`, PDF p.86, Annex 1 B |
| DGUV-RESTART | `shared/Troubleshooting.pdf`, PDF p.87, Annex 1 B, last bullet |
| VICKERS-AWARE | `HPU/100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf`, PDF p.34, Algo 0.6, awareness diamond and alarm box |
| MISUMI-RETURN | `CV/conveyor-manual-0323-en.pdf`, PDF p.69, 인쇄 p.65 §10.1 |
| ATOS-LOG | `HPU/MAN-C-012.pdf`, PDF p.9, 인쇄 p.10 §3 |
| DGUV-LOG | `shared/Troubleshooting.pdf`, PDF p.27, §3 Troubleshooting |
| DGUV-INTERVIEW | `shared/Troubleshooting.pdf`, PDF p.25, §3 Troubleshooting |
| DGUV-TIMING | `shared/Troubleshooting.pdf`, PDF p.24, §3 Troubleshooting |
| MISUMI-BEFORE | `CV/conveyor-manual-0323-en.pdf`, PDF p.9, 인쇄 p.5 §3.1 |
| MISUMI-SIGN | `CV/conveyor-manual-0323-en.pdf`, PDF p.9, 인쇄 p.5 §3.1.2 |
| MISUMI-OPERATORS | `CV/conveyor-manual-0323-en.pdf`, PDF p.10, 인쇄 p.6 §3.1.3 |

Q04의 인지 여부 질문은 확인할 상태를 제시하지만 수신자가 응답하는 방법을 정하지 않는다. 경보를 들었다는 이유만으로 복창·서명·무전 응답을 만들어 넣지 않았다. Q08의 서명은 해당 매뉴얼 이해 확인에 한정하며 Q02·Q05·Q06에 옮겨 쓰지 않았다. 원문 서로 간에 없는 절차를 조합해 다섯 필드를 완성하지 않았다.

페르소나는 [synthetic-narratives.json](synthetic-narratives.json)의 3개 합성 검토 메모에만 적용했다. V-11의 짧은 전달, V-12의 체크리스트, V-13의 맥락 서술을 사용했으며 각 문서에 `persona_id`와 `is_synthetic=true`를 남겼다. 실제 사건 원장이 없으므로 작업을 했다는 일지·사건을 만들지 않았다. 세 메모는 Q01의 같은 원문에 대한 문체 변형이며 독립 근거·독립 사건·유효 카드에 포함하지 않는다. 페르소나의 승인권·역할·채널 설정은 카드 필드의 근거로 쓰지 않았다.

## C. 스키마 검사와 중복 검사를 통과한 카드 초안

**없음.** [cards.json](cards.json)은 빈 배열이다. 부족한 값을 임의로 채운 `status=draft`, `grade=L0` 카드는 저장하지 않았다. 스키마를 통과한 빈 결과를 “카드 8건 통과”로 보고하지 않는다.

검증 실행: pydantic과 pypdf가 설치된 Python으로 `docs/data/knowledge_cards/drafts/20260925-t4-evidence-review/verify.py`를 실행한다. 이번에는 Codex 번들 Python을 사용했다(프로젝트 기본 Python에는 pypdf가 없음). 실행 결과는 [validation.json](validation.json)에 저장했다. 기존 `HandoverMethod`와 `KnowledgeCard`를 직접 호출하며 스키마를 변경하지 않는다.

```powershell
& 'C:/Users/hyjuy/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' docs/data/knowledge_cards/drafts/20260925-t4-evidence-review/verify.py
```

- 후보의 근거 확인 필드만 `HandoverMethod`에 투영: 8건 중 Q08 1건만 다섯 필드 형식 충족. 나머지 7건은 실제 누락 필드 오류를 기록한다.
- 전체 카드 완성 여부 검사: 8건 모두 실패. 이는 불완전 후보의 완성도 검사이며 생성된 카드의 통과 검사가 아니다. 관리 값·적용 필드를 보충하지 않았다.
- Q08도 교대·고장 인계로의 일반화와 T4 경계, `component`·`scenario`, 요청자가 제공한 ID·카드 version·confidence, 계보·split 및 실제 provenance 입력이 미확정이다. 매뉴얼 교육 이해 확인 자체의 근거가 있다는 것과 유효한 전체 카드가 있다는 것을 구분한다.
- 원문 파일·근거 발췌·기준 파일의 해시, 근거 참조, 합성 표시, 필드 연결, 후보 정규화 중복을 검사한다. 의미 중복 검토는 아래처럼 같은 방법을 먼저 병합하고 남은 8개 목적의 28쌍을 비교했다. 기존 전체 KB와의 의미 중복 통과를 주장하지 않는다.

| 병합한 변형 | 처리 |
|---|---|
| SEW 소음·누유·과열별 서비스 문의 | Q01 하나. 모두 동일한 고객 서비스 정보 패키지 |
| DGUV 고장·위험 보고, MISUMI 안전결함·반복고장 통보, Interroll 자격자 통보 | Q02 계열로 묶음. 모델·직책·발생 횟수만으로 카드 수를 늘리지 않음 |
| ATOS 동일 정비 양식 3쪽, DGUV 작업·변경 기록 | Q06 하나의 기록·추적 후보. 3쪽을 3건으로 계산하지 않음 |
| V-11/V-12/V-13 메모 | 동일 Q01 계보. 독립 후보·사건으로 계산하지 않음 |

## D. 보완 대기 후보와 부족한 원문

| 후보 | 실질적인 차이·경계 | 추가로 필요한 원문 |
|---|---|---|
| Q01 | 외부 서비스가 대상 설비와 고장 맥락을 식별하도록 묶는 정보 패키지. 소음·누유·과열별로 나누지 않음. | 동일 제품·현장의 서비스 의뢰 절차: 전송 채널, 접수 또는 내용 확인 절차. 프로젝트 적용 제품과 사용 범위 확인. |
| Q02 | 외부 문의(Q01)와 달리 내부 책임 조직에 이상 존재를 즉시 전달하는 최초 보고. 반복 고장 통보는 별도 카드로 늘리지 않음. | 현장 이상 보고 절차의 보고 채널·수신 확인 규칙 및 역할 정의. MISUMI 반복 고장 통보도 동일 방법 계열로 병합. |
| Q03 | 정비 전 주변 인원에 대한 사전 고지이며, 표지 위치가 원문에 있음. 보고 대상·방향이 내부 고장 보고와 다름. | 정비 사전 고지의 대상 범위·수신 확인 절차. 게시가 개인별 통지를 대신할 수 있는지도 현장 절차로 확인. |
| Q04 | 정비 개시 고지(Q03)와 달리 재가동 예정 정보의 사전 전달. 인계 내용은 재가동 승인이나 조작 지시가 아님. | 현재 현장 재가동 사전 통보·응답 확인 절차. Vickers p.34의 safety interlocks 제거 문구와 별개로 적용 가능한 안전 검토가 필요. |
| Q05 | 정비 측에서 운전 측으로 설비를 반환하는 경계의 인계. 재가동 예고와 수신 대상·업무 단계가 다름. | 정비→운전 인계 표준·양식: 전달 정보, 채널, 인수자 확인. 원문의 시험 운전 순서를 프로젝트 재가동 권한으로 전용하지 않음. |
| Q06 | 작업·변경 이력의 추적성이 목적. 장비·작업 유형·서식 페이지를 바꾸어 여러 카드로 분리하지 않음. | 정비기록 작성과 인계의 연결 절차: 지정 수신자, 전달 시점, 수신 확인. ATOS 양식과 DGUV 권고를 결합해 새로운 현장 양식을 확정하지 않음. |
| Q07 | 기술 진단을 시작하기 위한 관측 설명·과거 이력의 수집과 대조. 긴급 통보나 작업 완료 기록과 전달 정보가 다름. | 운전→진단 담당 면담·인계 절차: 정보 인수 역할, 설명 확인·되읽기 등의 실제 규칙. 진단(T3)과 인계(T4) 목적 경계 검토. |
| Q08 | 서명이 실제 이해 확인에 연결된 문서 교육·지식 전달. 이 서명을 고장 보고·교대 인수 서명으로 전용하지 않음. | 일반 교육·매뉴얼 전달을 T4 범위에 포함할지 검토. 교대 인계로 쓰려면 담당 변경 시점·전달 정보·확인 절차를 명시한 별도 원문. 출처 범위와 실제 관리 입력도 필요. |

후보 이전 단계에서 제외한 자료도 있다. 제조사 사례의 성공 결과·수명 증가, 일반 진단 표의 권장 대책, 계약 수락 문구, 운송 손상 신고, 제품 카탈로그와 도면은 그 자체로 고장 인계 방법이 아니다. 원문의 수치·조치·결과를 새로운 사건에 배정하지 않았다. 실제 현장의 교대 시각, 수행 조치, 복구 결과, 수신 확인이나 승인자를 새로 만들지 않았다.

Vickers p.34에는 safety interlocks 제거를 포함한 도식이 있다. 본 검토는 통보 관련 부분의 존재만 확인했으며 전체 도식을 안전 절차로 채택하지 않았다. MISUMI p.69의 고장 처리·시험 운전 순서도 프로젝트의 재가동 권한을 정하지 않는다. 인계·통보는 운전 조건 변경, 정비 착수, 재가동 승인 행위로 표현하지 않았다.

## E. 목표 대비 유효 수와 추가 자료

| 항목 | 수 |
|---|---:|
| 목표 | 25 |
| 근거 검토 대상으로 정리한 서로 다른 후보 | 8 |
| 다섯 필드 형식을 충족한 경계 후보 | 1 (Q08, 보완 대기) |
| 전체 스키마·근거·중복 기준을 충족한 유효 draft/L0 카드 | **0** |
| 목표 대비 부족 | **25** |
| 보완 대기 | 8 |
| 이번에 검증된 실제 현장 사건 | 0 |
| 합성 문체 예시 | 3 (동일 원문; 수량 미포함) |

추가로 확보할 자료는 (1) 실제 교대 인계 표준과 사용 양식, (2) 고장 보고·서비스 의뢰의 채널·회신 절차, (3) 정비 시작 전 고지와 정비→운전 반환 절차, (4) 재가동 예고의 대상·시점·수신 확인 절차, (5) 미해결 고장·임시 제한·진단 대기·변경 이력의 인계 규칙이다. 각 절차에서 전달 정보·수신 역할·시점·채널·확인 방법을 함께 확인해야 한다. 해당 규칙이 실제로 쓰인 비식별 인계 기록과 후속 확인 기록이 있으면 적용성 검토를 보완할 수 있다. 존재하지 않는 확인 방법을 제안값으로 채우지 않는다.

25건을 만들려면 문서 25개 또는 사건 25개가 반드시 필요한 것은 아니다. 하나의 문서에 실질적으로 다른 방법이 여럿 있을 수 있으나, 각 방법의 다섯 필드와 차별성이 각각 근거를 가져야 한다. 현재 8개 후보가 모두 보완돼도 최대 8건이라는 가정 아래 최소 17개 추가 방법이 필요하며, Q08의 범위 제외나 추가 병합이 있으면 더 필요하다. **현재 실제 부족은 25건**이다.

원문 확보 뒤에는 사람이 확인한 사용 범위·이용 조건, 적용 설비·역할, 원문 계보를 확정하고 요청 ID·version·confidence 및 근거를 제공해야 한다. split은 확정 계보의 실제 배정에서, provenance는 실제 입력·실행에서 가져온다. 이번 검토는 출처 승인·현장 안전 검토·카드 채택을 대신하지 않는다.

검토 한계: 관련 절 중심 검토이며 모든 도면·이미지의 OCR 완전성을 보증하지 않는다. 이번 보관본에서 확인한 내용으로는 유효 카드를 만들 수 없다는 결론이다. 외부 추가 원문을 자동 수집하거나 보관본을 현행 규정으로 인증하지 않았다.
