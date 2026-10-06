# MES·라즈베리파이 통신 작업 통합 검증 (2026-10-02)

사용자 요청: 같은 담당자의 MES 질의·인계 작업과 라즈베리파이 HTTP 통신 작업을 비교하고 정확한 구현을 통합한다. 기존 구현을 확인한 뒤 호환되는 부분을 채택했다. 새 질의 엔드포인트나 프록시를 중복 구현하지 않았다.

## 비교와 채택

| 부분 | 확인한 구현 | 통합 판단 |
| --- | --- | --- |
| 질의·인계 서버 | 기존 `MesService.query`, `record_handover` 및 FixedPipeline/SQLite outbox | 단일 서버 구현 유지. 클라이언트가 서버와 같은 question/equipment_id/scan_id/k 및 handover_id/memo_text 계약 사용 |
| 파이 Python 통신 | `shiftlink.communication.MesHTTPClient` | 채택. 표준 라이브러리 HTTP, UTF-8 JSON, 일반 5초·질의 125초, POST 자동 재전송 없음, HTTP400/409 보존 |
| 파이 브라우저 | main에서 이미 구현된 `shiftlink.pda.make_handler` | 기존 프록시 채택. PDA JS는 같은 출처 `/api/*` 호출, 새 서버 스크립트·CORS 경로 불필요 |
| Jetson 화면 제공 | 작업 트리의 `--api-only`, `serve(api_only=...)` | 채택. 옵션 사용 시 정적 화면 404, API 그대로 제공; 기본 모드의 기존 화면 제공 유지 |
| 인계 재전송 | 브라우저 localStorage 대기 ID와 서버 SQLite ID 기본키 | 유지. Python 호출자도 동일 ID·메모로 명시 재전송; 같은 ID의 다른 내용은409 |
| 명칭 | 양쪽 naming_registry 추가 항목 | 함께 유지하고 api-only 공개 옵션도 등록 |

카메라의 기존 경량 `post_scan` 경로를 새 Python 클라이언트로 강제 교체하지 않았다. `scripts/check_mes_http.py`는 별도 통신 점검 CLI로 채택한다. 초기 미추적 `scripts/device_http.py`, `manual.zip`, tmp 작업물은 이번 통합 커밋에서 제외한다.

## 실행한 검증

Windows 샌드박스 Python3.14에서 `$env:PYTHONPATH='tmp/card-review-deps;.test-deps'`로 실행했다.

- `python -m pytest tests/test_communication_http_client.py tests/test_communication_integration.py tests/test_mes_http.py tests/test_mes_query.py tests/test_mes_handover.py tests/test_mes_handover_http.py -q`: **33 passed, 38 subtests passed**. 직접 HTTP 및 실제 PDA 프록시를 통해 인식·질의·MES 읽기, 서버 재시작 후 인계 재전송·충돌409, scan 변경 오류400을 확인했다. LLM은 이 통합 테스트에서 stub이다.
- `python -m coverage run --data-file=tmp/mes-communication-merge.coverage --source=shiftlink.communication -m pytest tests/test_communication_http_client.py tests/test_communication_integration.py -q`와 `python -m coverage report --data-file=tmp/mes-communication-merge.coverage`: **13 passed, 33 subtests passed**, 통신 모듈 **100% (68/68 statements)**.
- `python -m pytest tests/test_pda_app.py -q`: **2 passed**. 파이 정적 화면, 프록시 상태코드·본문 전달, Jetson 연결 실패502 확인.
- `node tests/mes_query_pda.cjs`: PASS. `node --check shiftlink/mes/web/pda.js`: PASS.
- `python -m eval.harness --suite dev --run-id mes-communication-merge-20261002`: **A~F 6/6 PASS, 46/46 사례**.
- `git diff --check`: PASS.

없는 `tests/test_pda_server.py`를 포함한 최초 명령은 테스트를 실행하지 못했다. 실제 파일 `tests/test_pda_app.py`와 통합 테스트로 다시 검증했으며 위 숫자만 유효하다.

이번 통합은 기존 작업 브랜치 `feat/mes-query-handover-20261002`에 두 작업을 함께 보존하는 것이다. Jetson의 다른 에이전트 작업·기존8000 서버·SQLite 데이터는 변경하지 않았다. 이전 분리 실행에서 실제 exaone 응답은 확인했으나 답 본문이 카드 ID에 그쳐 설명형 답변 품질은 여전히 미검증이다. 물리 PDA·웹캠과 Claude 리뷰도 이 통합 테스트로 완료했다고 주장하지 않는다. 이전 RED/GREEN·Jetson 기록은 [MES API 검증](mes-query-handover-20261002.tdd.md)에 있다.
