# 근무일지 Node 회귀 검사 정합성

2026-10-19, PR #293 후속 검증.

## RED

`f658323`에서 다음 세 명령을 실행해 실패를 재현했다.

- `node tests/pda_handover_table.cjs`: 저장 코드 `고장·정비`, `PMS 정비`를 화면 표시 이름으로 기대했으나 현재 표는 `고장 대응·수리`, `정기 예방정비`를 표시한다.
- `node tests/pda_report_input.cjs`: 삭제된 사용자 정의 달력의 `reportLocalDateTime`을 호출한다. 현재 화면은 날짜 입력과 `shiftAt`·`syncReportShift`를 사용한다.
- `node tests/pda_typed_report.cjs`: 현재 화면에 없는 근무 유형 선택과 최상위 `form_version=2`를 기대한다. 현재 새 기록은 기록별 `capture_version=1`로 단계별 조치·수행자·시각·결과를 보존한다. 서버의 이전 양식 수신 지원과는 별개다.

## 수정 범위

화면·센서 연동·서버 저장 로직은 변경하지 않는다. 테스트를 현재 입력 흐름과 저장 형식에 맞추며 날짜 경계, 입력 거부, 원본 보존 검사를 포함한다. 삭제된 기능을 테스트 통과 목적으로 복원하지 않는다.
