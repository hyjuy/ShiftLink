# PDA 사건 연결과 지식카드 승격 수용 계획

2026-10-15 기준. 1차 작업은 현재 PDA의 화면 이동과 저장 경로를 확인하고, 다음 개발에서 만족해야 할 동작을 고정하는 것이다. 제품 구현은 아래 차례별로 진행하며 현재 동작과 목표 동작을 구분한다.

근거: [재사용성 학술논문 조사](../../artifacts/ShiftLink%20재사용성%20향상을%20위한%20학술논문%20조사.md), [기존 현장 해결 기록 검증](field-resolution-card-draft.tdd.md), [PDA 연동 보호 규칙](../../shiftlink/mes/web/AGENTS.md).

## 1 현재 화면과 저장 경계

| 단계 | 현재 동작 | 코드 근거 |
| --- | --- | --- |
| 설비 선택 | 스캔 또는 직접 선택한 설비로 질문 화면을 연다. 질문 요청은 question과 equipment_id 또는 scan_id다. | [pda.js](../../shiftlink/mes/web/pda.js) queryApiPayload |
| 질문 | 새 질문에서 S.tries와 attemptSeq를 초기화한다. incident_id를 서버로 보내지 않는다. | pda.js sendChat, [query.py](../../shiftlink/mes/query.py) query_service, [router.py](../../shiftlink/agent/router.py) QueryRequest |
| 카드 실패 신고 | recordTry는 카드 제목과 관측 표현을 S.tries에 추가한다. 이후 인계 본문의 attempts로 전달할 수 있지만 매 시도마다 서버에 저장하는 경로는 아니다. | pda.js recordTry, hoSave |
| 조치 시작 | openResolve가 새 서버 조치 세션을 만든다. 기준 관측은 서버가 보관한 질의 근거를 우선 사용한다. | pda.js openResolve, [server.py](../../shiftlink/mes/server.py) resolution_start |
| 단계 완료 | 서버가 실제 완료 시점의 센서값과 변화 문장을 resolution_sessions에 저장한다. | server.py resolution_step, [storage.py](../../shiftlink/mes/storage.py) update_resolution_session |
| 조치 마무리 | MES 결과를 확인하고 wrap 화면에 제안 결과를 표시한다. 세션은 아직 open이며 인계와 초안의 최종 저장은 이루어지지 않는다. | pda.js finishResolve, server.py resolution_finish |
| 기록 저장 버튼 | resSave는 입력 검증 후 인계 작성 화면을 열고 resolution.session_id를 붙인다. 이 버튼 자체가 최종 저장 요청은 아니다. | pda.js resSave, sessionPayload |
| 인계 저장 | hoSave가 POST /api/handover를 보낸다. 인계·초안 생성 또는 병합·세션 saved 전환은 하나의 SQLite 트랜잭션으로 저장한다. | pda.js submitHandover, server.py _record_session_handover, storage.py save_handover_with_draft |
| 초안 확인 | GET /api/card-drafts는 읽기 전용이다. 정상 검색 대상으로 초안을 바로 편입하지 않는다. | server.py card_drafts |
| 승격 | 사람이 시연용 스크립트로 pending_review 초안을 accepted/L1/kb로 바꾸고 KB 파일에 추가한다. 기본 경로는 ready와 --yes를 요구하고, --force는 시연 리허설용 우회다. | [field_card_promote.py](../../scripts/field_card_promote.py) main, promoted_card |
| 검색 반영 | 기본 로더는 accepted/kb/L1을 읽는다. 실행 중 검색 반영에는 현재 방식상 MES 재시작이 필요하다. | [loader.py](../../shiftlink/rag/loader.py), [retrieval.py](../../shiftlink/rag/retrieval.py), query.py build_query_pipeline |

S.tries의 카드 피드백과 S.res.steps의 수행 단계는 기록의 단위와 증거 수준이 다르다. 같은 사건에서 함께 조회하도록 연결하되 카드 제목을 실제 수행 단계로 자동 치환하지 않는다.

## 2 이번에 고정하는 설계 결정

1. 사건은 여러 질문·조치 세션·인계를 묶는 상위 참조다. 기존 Event, run_id, session_id, handover_id를 대체하지 않는다.
2. 사용자가 같은 사건을 이어갈지 새 문제를 시작할지 명시적으로 선택한다. 같은 설비라는 이유로 다른 작업자의 기록을 자동 병합하지 않는다.
3. 카드 피드백과 수행 기록은 같은 사건에서 조회하되 종류를 구분한다. 단순 신고를 센서로 확인된 조치 효과로 승격하지 않는다.
4. 질의 당시 근거는 고정하고 실시간 현재값과 별도로 표시한다. 자산·설비가 바뀌면 이전 사건의 근거를 섞지 않는다.
5. 첫 구현에서는 인계·초안·세션 종료의 기존 원자적 저장을 유지한다. 인계 없이 해결 기록만 저장하는 API 분리는 후속 과제다.
6. 화면의 저장 안내는 실제 서버 저장 시점과 일치해야 한다. 기록 저장·작업자 결과·MES 확인·카드 검토·클라우드 업로드 상태를 구분한다.
7. PDA는 작업 사실을 기록하고, 카드의 적용 범위와 승인 여부는 별도 검수 흐름에서 판단한다.
8. ready는 권장 표시다. 해결 기록 2건을 같은 사건의 중복 기록으로 채우지 않도록 사건 단위 집계를 후속 개발에서 추가한다. ready를 안전성 인증으로 해석하지 않는다.
9. 기존 카드 status=draft/accepted/rejected, 초안 행의 검토 상태, SafetyReview, 배포 상태는 구분한다. 검토·배포 이력 추가 시 명시적 이전을 설계한다.
10. 초기 개발 동안 모델·카드·검색 설정을 고정한다. 공급원 교체·모델 튜닝·전체 온톨로지 구축은 이번 사건 연결 범위에 포함하지 않는다.

P01의 실패 경험 활용과 P02의 experience/lesson 구분을 적용한다. 현행 스키마와 조건 판정을 활용하며 자동 승인 또는 현장 안전성 보장을 새로 주장하지 않는다.

## 3 화면별 목표 동작

| 화면 | 작업자가 해야 할 일 | 화면과 서버의 목표 동작 |
| --- | --- | --- |
| 홈 | 진행 중 사건 열기 | 설비와 마지막 진행 상태를 보고 동일 사건을 이어간다. |
| 설비 작업 선택 | 새 문제 시작 또는 사건 이어가기 | 사건의 설비·자산과 현재 선택이 맞는지 서버가 확인한다. |
| 질문과 답변 | 후속 질문하기 | 이전 질문·시도 참조를 유지하고 서버가 필요한 이력을 조회한다. 현재 센서와 과거 근거를 구분한다. |
| 시도 기록 | 카드가 도움이 없었던 결과 남기기 | 카드 ID·버전·피드백 종류·관측 참조를 사건에 저장하고 복원한다. |
| 조치 기록 | 실제 단계 완료 기록하기 | 기존 session_id를 이어받고 서버가 단계별 관측을 기록한다. |
| 조치 마무리 | 작업자 결과와 MES 확인 비교 | resolved/temporary/failed와 recovered/not_yet/unconfirmed를 별도로 보여준다. 원인 모름을 허용한다. |
| 인계 작성 | 다음 담당자의 확인 사항 작성 | 기존 사건의 질문·시도·관측을 참조하고, 최종 저장 전 상태임을 알린다. |
| 저장 완료 | 저장 결과 확인 | 로컬 기록 저장, 초안 처리 결과, MES 확인, 전송 대기를 분리한다. |

새 결과 enum이나 새 카드 status를 화면에서만 추가하지 않는다. 필요하면 서버 계약·저장·검증·이전까지 같은 변경에 포함한다.

## 4 수용 시나리오

아래 기대 결과는 개발 완료 후의 수용 기준이다. 기존 테스트는 현재 동작의 회귀 확인용이며, 미래 기능의 구현 완료 근거로 사용하지 않는다.

| ID | 상황과 조작 | 기대 결과 | 적용 차례 |
| --- | --- | --- | --- |
| AC-01 | HPU-01에서 새 문제를 시작하고 첫 질문 뒤 다시 질문한다. | 같은 incident_id를 사용하며 두 질문의 근거 시각은 각각 유지된다. | 2, 3 |
| AC-02 | 카드에 효과 없음 피드백을 남긴 뒤 후속 질문한다. | 피드백이 사건에 저장되고 다음 질문에서 조회된다. 카드 제목을 실제 완료 단계로 취급하지 않는다. | 2, 3 |
| AC-03 | 조치 단계를 완료하고 PDA 새로고침 또는 재접속 뒤 사건을 연다. | 서버의 기존 session_id와 완료 단계를 복원하고 새 세션을 임의로 중복 생성하지 않는다. | 2, 3 |
| AC-04 | HPU-01 사건 진행 중 다른 설비 또는 교체 자산을 선택한다. | 이전 사건의 센서·근거·조치를 새 대상에 연결하지 않는다. 잘못된 연결 요청은 서버에서 거절한다. | 2, 3 |
| AC-05 | 조치 마무리 후 resSave를 눌러 인계 화면으로 이동한다. | 아직 최종 저장 전임을 표시한다. 인계 제출 시에만 기존 원자적 저장이 완료된다. | 4 |
| AC-06 | 인계 저장 요청의 응답을 받지 못해 같은 본문을 재전송한다. | 동일 handover_id로 한 번만 반영된다. 다른 본문 재전송은 충돌로 처리한다. 세션·초안 일부만 저장하지 않는다. | 2, 4 |
| AC-07 | 작업자는 해결이라고 입력했으나 MES가 정상 복귀를 확인하지 못했다. | 작업자 결과와 MES 결과를 함께 보여주고 MES 확인 해결 건수에 포함하지 않는다. | 4 |
| AC-08 | 매칭 초안이 없는 failed 기록과 기존 초안에 매칭되는 failed 기록을 각각 저장한다. | 전자는 attempt_only로 신규 초안을 만들지 않고, 후자는 반대 근거로 병합될 수 있다. | 4 |
| AC-09 | 같은 원인의 추가 해결 기록과 다른 원인의 기록을 저장한다. | 적합한 기록만 기존 초안에 병합하고 근거를 추적한다. 단순히 같은 설비·공통 MES 단계라는 이유로 다른 원인을 합치지 않는다. | 4, 5 |
| AC-10 | 같은 사건 기록을 반복 저장하고 별개 사건의 해결 기록을 추가한다. | 같은 사건은 독립 성공 사례를 늘리지 않는다. 권장 기준·운영자 확인·반대 근거를 각각 보여주고 자동 승인하지 않는다. | 5 |
| AC-11 | 검수 대기 초안을 조회한 뒤 승인·배포 절차를 수행한다. | 미승인 초안은 일반 권고에 포함되지 않는다. 검토자·변경 이유·배포 버전이 남고 실제 배포본 로딩 후 검색에 반영된다. | 5 |
| AC-12 | 조건이 같은 실패 조치를 다시 요청하거나, 조건 변경 후 정당하게 재시도한다. | 무효 반복을 줄이면서 타당한 재시도를 일괄 차단하지 않는다. 안전 안내와 판정기 장애 차단을 유지한다. | 6 |

## 5 기존 검사와 앞으로 추가할 검사

| 확인 대상 | 기존 파일과 검사 | 후속 개발에서 추가할 보장 |
| --- | --- | --- |
| 조치 시작·단계·마무리 | [test_field_draft.py](../../tests/test_field_draft.py) test_start_uses_query_evidence_and_suggests_from_mes, test_step_result_is_sensor_change_measured_by_server, test_finish_needs_real_recovery | 사건과 세션의 연결, 재조회, 다른 설비·자산 연결 거절 |
| 저장의 원자성·중복 방지 | test_field_draft.py test_handover_session_and_draft_are_atomic, test_retry_conflict_and_wrong_equipment | 사건 참조를 추가한 후에도 동일 보장 유지 |
| 초안 생성·반대 근거 | test_field_draft.py test_failed_makes_no_draft, test_failed_same_action_is_contradicting_and_blocks_ready, test_different_cause_same_condition_stays_separate | 사건 단위 중복 집계 방지와 근거 참조 |
| 수동 승격·복원 | [test_field_card_promote.py](../../tests/test_field_card_promote.py) test_only_pending_review_drafts, test_promote_then_restore_round_trip | 검토·배포 이력과 미승인·철회 카드 제외 |
| 인계 재전송 | [test_mes_handover_http.py](../../tests/test_mes_handover_http.py) test_restart_retry_and_conflict | 같은 사건의 인계 재전송과 세션 일관성 |
| PDA 화면 연결 | [pda_resolution.cjs](../../tests/pda_resolution.cjs), [mes_query_pda.cjs](../../tests/mes_query_pda.cjs) | 사건 이어가기, 피드백 복원, 저장 전후 안내 |

PDA 변경 차례에서는 web/AGENTS.md의 센서·통신 관련 검사와 화면 확인을 수행한다. 사건 기능을 추가하더라도 센서 수신·품질/단위/시각 검증·수동 관측 우선·연결 실패 처리·질의 당시 evidence 고정을 유지한다.

## 6 차례별 실행 범위

| 차례 | 산출물 | 완료 판단 |
| --- | --- | --- |
| 1 현재 차례 | 이 수용 계획과 코드·기존 검사 연결 | 경로와 저장 시점, AC-01부터 AC-12까지 추적 가능 |
| 2 다음 차례 | 서버 사건 참조와 기존 질문·조치 세션·인계의 연결 | 기존 호출과 기록을 보존하며 사건별 조회·대상 검증·원자적 저장 검사 통과 |
| 3 | PDA 사건 시작·이어가기와 이력 복원 | AC-01부터 AC-04까지 화면·서버 확인 |
| 4 | 저장 시점 안내와 결과·초안 상태 표시 | AC-05부터 AC-09까지 확인 |
| 5 | 검수·승격·배포 이력과 사건별 근거 집계 | AC-09부터 AC-11까지 확인 |
| 6 | 다음 사건의 적용성·실패 이력 활용 | AC-12와 검색·안전 회귀 확인 |

다음 차례에서 incident_id의 구체적 형식, 저장 필드, API 경로와 입력 검증을 테스트 가능한 계약으로 정하고 구현한다. 과거 기록에 사건을 임의 생성하거나 동일 설비의 최신 사건을 전역으로 자동 선택하지 않는다. 코드 변경이 필요한 센서·질의 연동은 사건 기능 개발 범위로 명시하고, 외관 변경에 섞지 않는다.

## 7 첫 차례 확인 결과

- 현재 PDA 이동, 조치 세션 저장, 인계 최종 저장, 초안 조회·수동 승격 경로를 코드에서 확인했다.
- 수용 시나리오와 기존 검사 파일·함수 이름의 연결을 정적 검사한다.
- 제품 코드와 지식카드 데이터, 실행 중 장비 서비스, 공개 시각화 사이트는 변경하지 않는다.
- 런타임 회귀 결과는 다음 구현 차례에서 기록한다. 현재 기본 Python에는 pytest가 없어 이번 문서 작업에서는 제품 테스트를 실행하지 않았다.
