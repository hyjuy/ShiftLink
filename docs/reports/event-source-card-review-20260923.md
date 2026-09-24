# 원문 검토 및 사건·지식카드 초안

2026-09-23. `docs/data/events`의 PDF 6개를 선별 검토하고, 원문이 부족하면 페르소나로 사건을 생성하라는 요청에 따라 초안을 작성했다. 기존 스키마·운영 카드·출처 승인 상태·평가 자료는 변경하지 않았다.

산출물은 [batch.json](../../artifacts/event-card-drafts-20260923/batch.json), [manifest.json](../../artifacts/event-card-drafts-20260923/manifest.json), [검증 결과](../../artifacts/event-card-drafts-20260923/validation.json)에 있다. `artifacts/`는 기존 저장 원칙에 따라 Git에서 제외된다. 원문 전문의 재배포 권한을 확인한 것은 아니다.

## 원문 판단

| 로컬 PDF | 확인 범위와 판단 | 사용 |
|---|---|---|
| `100980172-Logical-Troubleshooting-in-Hydraulic-Systems.pdf` | 37쪽. pp.3–5의 진단 원칙은 일반 유압 매뉴얼이며 실제 냉간코일 사건 기록이 아니다. | 배경 후보. 아래 유압 사건 후보 계보는 해시상 sealed여서 사건·카드를 생성하지 않음. |
| `Failure analysis and countermeasures of gearbox in cold rolling mill.pdf` | 3쪽. p.2의 사례 도입문 이후 상세 원인·조치가 없다. p.3도 렌더링으로 확인했으며 관련 기사·제품 영역만 있다. | 사례 본문 부족으로 보류. 없는 후속 내용을 생성해 원문으로 표시하지 않음. |
| `Hydraulic System Failure Analysis of Plate Rolling Machine.pdf` | 5쪽. pp.1–3에 판재를 원통 등으로 굽히는 3롤 성형기의 실린더 A/B 고장·조치가 있다. 냉간코일 생산 공정 사례로 확인되지 않는다. | 공정 범위가 달라 사건에서 제외. 해당 시험·조작을 현장 정답 절차로 옮기지 않음. |
| `Rolling mill bearing reliability_ three case studies, one conclusion - Euro Bearing.pdf` | 5쪽. p.2의 이탈리아 냉간압연 백업롤 사례에는 반복 손상, 진동 추적, 초크 보어 마모, 정기 측정·재정비 후 고장 중단이라는 기사 서술이 있다. | 실제 정비 원장·측정값·추적 기간은 없고 백업롤은 현재 설비 분류와 직접 대응하지 않아 보류. GR/RT로 임의 변환하지 않음. |
| `Root Cause Analysis for Steel Plant Failures_ RCA, FMEA & AI Insights.pdf` | 18쪽. pp.1–2의 대표 사례는 Indiana hot strip mill이다. | 해당 열간압연 사례 제외. 문서 전체에 냉간 사례가 없다는 결론은 내리지 않음. |
| `xu-zhang-2024-research-on-the-service-life-of-bearings-in-the-gearbox-of-rolling-mill-transmission-system-under-non.pdf` | 15쪽. pp.1,12–14에서 냉간압연 감속기, 베어링 손상 현장 기록, 조건별 수명 연구를 확인했다. pp.13–14는 렌더링도 확인했다. | 원문 보고 사건 1건을 미완성으로 정리. 논문은 복구 성공 절차의 근거로 사용하지 않음. |

## 생성 결과

| ID | 내용 | 근거 및 상태 |
|---|---|---|
| EV-0201 | 냉간압연 감속기 입력단 베어링 외륜 압흔 | 논문 보고를 정리한 비합성 사건 후보. 원인·손상 후 조치·복구 결과 미확정. 독립 검증된 현장 원장은 아님. |
| EV-0202 | 압연 조건 변경 기록이 불완전한 감속기 진동 보고와 교대 인계 | 합성 사건. V-01·V-03 사용. 원인·복구 성공·측정값을 만들어 확정하지 않음. |
| AR-0201 / AR-0202 | 박 반장 작업 메모 / 이 주임 인계문 | EV-0202의 같은 관측을 역할별로 서술한 합성 초안. 독립 사건 두 건으로 계산하지 않음. |
| K-0201 | 감속기 진동 보고에서 운전 조건과 손상 판단을 구분하기 | T3. 논문 배경과 V-01 역할에서 구성한 기록 대조 절차 초안. 논문의 직접 작업 절차가 아님. |
| K-0202 | 진단 미회신 사건을 교대 인계에서 미해결로 유지하기 | T4. V-03 기반의 재사용 가능한 합성 인계 방법. 실제 현장 표준으로 표시하지 않음. |

카드는 모두 `draft/L0`이며 운영 KB에 적재하지 않았다. `confidence=0.0`은 미평가 기본값으로, 확률이나 검증 결과가 아니다. `true_actions=[]`는 아무 조치도 없었다는 뜻이 아니라 검증된 정답 조치를 확보하지 못했다는 뜻이다. `cards_expected=[]`로 두어 이번 초안을 평가 정답으로 지정하지 않았다. 카드의 `provenance.event_ids`는 예시 연결이며 합성 사건을 카드 주장의 실증 근거로 재투입하지 않았다.

## 계보와 분할

해시 계산 전에 원문·주제로 정한 `SRC-XU-ZHANG-2024-NONSTEADY-LUBRICATION` 그룹은 기존 `shiftlink-split-v1:<group_id>` 규칙에서 버킷 5, `kb`다. EV-0201·EV-0202·인계문·카드는 보수적으로 같은 계보 1개에 묶었다. 원천 사건과 합성 변형을 서로 독립적인 평가 표본으로 계산하지 않는다. 기존 전체 계보와의 의미 중복은 아직 검토하지 않았으므로 배정표 등록은 보류하며 이번 `kb` 값은 승인 전 제안값이다.

유압 후보 그룹 `SRC-VICKERS-LOGICAL-TROUBLESHOOTING-OBSERVATION-GAP`은 버킷 10, `sealed`가 나와 생성 대상에서 제외했다. 원하는 split을 얻으려고 ID를 바꾸지 않았고 기존 sealed 사건은 읽지 않았다. 이 메타데이터가 정식 평가 봉인 완료를 의미하지 않는다.

## 검토와 남은 사항

기존 `Event`, `Artifact`, `KnowledgeCard`로 형식 검증하고, 추가 키·ID 중복·참조·split·출처 해시·합성 표시·초안 등급을 검사한다. 실제 결과는 연결된 `validation.json`에 기록한다. 승인된 원문 범위를 요구하는 운영 생성 파이프라인을 실행한 결과가 아니라 별도 검토용 후보 묶음이다. 출처 등록·이용 범위, 현장 적용성, 의미 중복과 계보, 역할·인계 채널은 검토 대기다. 사람의 검수 기록이나 출처 승인을 생성하지 않았다.

추가 원문이 필요한 항목은 ① 감속기 기사에서 누락된 사례 본문, ② 논문 사례의 손상 후 정비·복구·재발 기록, ③ 백업롤 사례의 실제 정비 이력과 설비 분류다. 현재 근거로 T1~T6을 모두 채우거나 복구 성공 사건을 늘리지 않았다.
