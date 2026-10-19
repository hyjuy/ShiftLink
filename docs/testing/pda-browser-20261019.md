# 로컬 Chrome · 실제 HTTP 검증

PR #293, 2026-10-19. Python 3.10 가상환경과 Playwright 1.64.1·agent-browser 0.39.1을 저장소 `tmp/browser-validation/` 아래에 별도 설치했다. 설치된 Chrome을 사용하며 운영 서비스·DB·계정에는 연결하지 않는다.

## RED

실제 화면을 그대로 로드하고 계정 로그인·빈 일지 저장·확인 취소·B조 익일 종료·고장 기록 저장·후속 인계·같은 사건의 이력 조회·새로고침·1280/768/375px 검증을 진행했다. HTML/스크립트/HTTP 응답을 가로채거나 화면 함수를 대체하지 않았다. 서버의 모델만 외부 호출 금지용 고정 파이프라인을 사용한다.

`tests/pda_worklog_http_browser.cjs`는 위 흐름 이후 실제 `/api/query` 응답에 저장된 `query_id`가 없다는 assertion에서 실패했다. Python 관련 검사도 130 passed / 24 failed였으며, 23개는 같은 질문 연결 경로의 실패, 1개는 Windows에서 POSIX 파일 모드 `0600`을 기대한 계정 검사였다.

원인: 이전 통합 과정에서 `MesService._save_query_result`가 저장 ID를 응답에 넣지 않고, `query_service`가 계산한 서버 컨텍스트·답변 상태를 반환하지 않는 상태가 됐다. 저장 당시 근거·질문·사건·후보를 연결하는 정보이므로 이 반환 정보를 복구한다. 모델 입력이나 센서 수신 방식은 바꾸지 않는다.

재현 체크포인트에는 실제 HTTP 브라우저 검사와 임시 계정이 있는 격리 서버를 포함한다. 기존 화면 브라우저 검사 7개는 모두 통과했다.

## GREEN

- 브라우저 검사 **8개 통과**: `pda_abnormal_notes_browser`, `pda_capture_browser`, `pda_followup_browser`, `pda_worklog_scenarios_browser`, `pda_report_layout_browser`, `pda_report_cause_layout_browser`, `pda_report_remove_fields_browser`, `pda_worklog_http_browser`.
- 앞의 7개는 Chrome에서 실제 DOM·이벤트를 실행하지만 일부 API/상태를 대체하는 화면 검사다. 마지막 검사는 임시 계정·임시 SQLite 서버로 실제 페이지와 이벤트 배선을 그대로 사용하고 API도 대체하지 않는 별도 E2E다. 외부 모델 호출 없이 로컬 검증했다.
- E2E: 로그인, 저장 확인 취소, 정상 근무·B조 자정 종료, 추가 기록, 수행자·시각·원문·서버 센서 근거의 DB 왕복, 후속 인계와 같은 사건 유지, 읽기 전용 상세, 2건 이력 조회, 새로고침 후 기록 유지, 질문 ID/상태 응답을 확인했다. 브라우저 예외와 실패한 API 응답은 **0건**이다.
- 작성·상세 1280/375px, 인계 표 1280/768/375px에서 가로 넘침을 확인했고 데스크톱·모바일 스크린샷을 육안 확인했다.
- 관련 Python/API 검사 **170 passed**: `test_work_report_api`, `test_work_report_reuse_harness`, `test_typed_work_reports`, `test_work_report_capture`, `test_work_report_followup`, `test_work_report_scenarios`, `test_work_report_t4`, `test_candidate_management`, `test_mes_handover`, `test_mes_handover_http`, `test_pda_handover`, `test_mes_query`. 후속 인계 fixture에는 필수 `followup_from`을 보완하고, 연결 없는 요청의 거부 assertion도 추가했다.
- 기존 Node 검사 **14개 통과**, `node --check` 및 `git diff --check` 통과.

실행 예:

```powershell
# 별도 설치한 Playwright 모듈과 requirements.txt를 설치한 Python 경로를 지정한다.
$env:NODE_PATH = 'D:/obsd/Projects/ShiftLink/tmp/browser-validation/node/node_modules'
$env:PYTHON_BIN = 'D:/obsd/Projects/ShiftLink/tmp/browser-validation/venv/Scripts/python.exe'
$env:TEMP = 'D:/obsd/Projects/ShiftLink/tmp/browser-validation/runtime'
$env:TMP = $env:TEMP
node tests/pda_worklog_http_browser.cjs
```

실행 결과와 스크린샷은 `artifacts/pda-worklog-http-20261019/`에 보관한다. 실제 계정·DB는 변경하지 않으며 임시 서버는 검사 종료 시 닫고 DB를 제거한다.

이번 검사 범위와 별개로 `test_pda_accounts.py`의 POSIX `0600` 파일 모드 assertion은 Windows에서 `0666`으로 보고돼 실패했다. 계정 구현·보안 기대값은 변경하지 않았다. 운영 배포·실장비·중앙 DB·외부 모델 검증과 전체 저장소 테스트는 이번 검증 범위에 포함하지 않는다. 이전 유형별 양식의 `pda_typed_report_browser`·`pda_report_form_browser` 대신 현재 화면 흐름은 새 실제 HTTP E2E에서 검증했다.
