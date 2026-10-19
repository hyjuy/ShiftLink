# 근무일지 Node 회귀 검사 정합성

2026-10-19, PR #293 후속 검증.

## RED

`f658323`에서 다음 세 명령을 실행해 실패를 재현했다.

- `node tests/pda_handover_table.cjs`: 저장 코드 `고장·정비`, `PMS 정비`를 화면 표시 이름으로 기대했으나 현재 표는 `고장 대응·수리`, `정기 예방정비`를 표시한다.
- `node tests/pda_report_input.cjs`: 삭제된 사용자 정의 달력의 `reportLocalDateTime`을 호출한다. 현재 화면은 날짜 입력과 `shiftAt`·`syncReportShift`를 사용한다.
- `node tests/pda_typed_report.cjs`: 현재 화면에 없는 근무 유형 선택과 최상위 `form_version=2`를 기대한다. 현재 새 기록은 기록별 `capture_version=1`로 단계별 조치·수행자·시각·결과를 보존한다. 서버의 이전 양식 수신 지원과는 별개다.

## 수정 범위

화면·센서 연동·서버 저장 로직은 변경하지 않는다. 테스트를 현재 입력 흐름과 저장 형식에 맞추며 날짜 경계, 입력 거부, 원본 보존 검사를 포함한다. 삭제된 기능을 테스트 통과 목적으로 복원하지 않는다.

## GREEN

3개 실패를 수정한 뒤 다음 Node 검사 14개를 모두 실행해 통과했다.

`pda_sensor_display`, `pda_network_boot`, `unity_pda_link`, `pda_symptom_rank`, `mes_query_pda`, `pda_handover_table`, `pda_report_input`, `pda_typed_report`, `pda_abnormal_notes`, `pda_home_handover`, `pda_incident_edge_cases`, `pda_incident_rows`, `pda_report_sensor_context`, `mes_admin_header`.

- 인계 표: 현재 표시 이름과 원래 저장 코드 보존, 기존 다중 설비·원본 불변성 검사를 확인했다.
- 근무 입력: 한국 시각의 00:00·08:00·16:00 경계, A/B/C조 시간, 윤일·연말의 B조 익일 종료, 전송 대기 시간 보존, 빈 일지·선택 메모 및 필수값 검증을 확인했다. DOM은 최소 대역을 쓰고 실제 `shiftAt`·`syncReportShift`를 실행한다.
- 기록별 유형: 이상 징후·고장 대응·정기 정비의 단계별 조치·작업자·시각·결과, 기본 작업자, 빈 단계 제외, 결과 우선순위, 재가동·실패 근거와 입력 오류 거부, 이전 기록·편집 중 원본 보존을 확인했다.
- `node --check shiftlink/mes/web/pda.js`, `git diff --check` 통과.

실행 코드 변경은 없어 신규 실행 코드 커버리지 측정 대상은 없다. Python/API·실제 브라우저 검증은 이번 후속 작업에서 재실행하지 않았으며, PR 생성 당시의 pytest·Playwright 의존성 부족에 따른 미검증 상태를 유지한다.
