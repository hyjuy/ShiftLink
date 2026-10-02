# MES 질의·인계 API 검증 (2026-10-02)

오늘 H1~H5 요청에서 사용자 여정을 도출했다. PDA 질문 → 최근 인식 설비와 현재 MES 관측값 → FixedPipeline 검색·exaone → 답·인용·안전 공지, PDA 메모 → SQLite 저장 → 서버 재시작 → 동일 ID 재전송 1건 유지가 대상이다.

## 구현과 RED/GREEN 증거

| 대상 | RED | GREEN 및 보장 |
| --- | --- | --- |
| SQLite outbox | `python -m unittest discover -s tests -p test_mes_handover.py`: save_handover/get_handover 부재로 실패 (`c8e9c52`) | ID 기본키, 동일 본문 재전송, 내용 충돌 거절, 재시작 조회 |
| 질의 모듈 | `python -m pytest tests/test_mes_query.py -q`: shiftlink.mes.query 부재로 수집 실패 (`848a3e5`) | 최신 scan·MES 관측값, 명시적 수동 설비, 바뀐 scan 거절, 원인 정답 배제 |
| HTTP 인계 | `python -m unittest discover -s tests -p test_mes_handover_http.py`: 미구현 경로 404 (`c4daabb`) | 실제 HTTP 서버 교체 후 같은 인계 ID 1건, 충돌 409 |
| HTTP 질의 | `python -m pytest tests/test_mes_query.py -q`: 1 failed, 8 passed; /api/query 404 (`52a152d`) | 실제 HTTP JSON 답변 반환, FixedPipeline 검색 연결 |
| PDA 질의 | `node tests/mes_query_pda.cjs`: queryApiPayload 부재 (`b1af749`) | 인식 scan_id·수동 equipment_id 제출, 검토 대기 시 조치 숨김 |
| PDA 인계 | `python -m unittest discover -s tests -p test_pda_handover.py`: submitHandover 부재 (`6a6cf59`) | ACK 유실 시 ID·본문 보존, 동일 본문 재전송, 다른 메모로 덮어쓰기 거절 |
| 한글 메모 | test_mes_handover_http.py: 한글 4000자 요청이 본문 한도 때문에 HTTP400 (`9e474da`) | query/handover 본문 한도 64KiB, 한글 4000자 저장 |

GREEN 구현 커밋 `1003f02`; 등록·정책 문서 `5e64420`. Windows 샌드박스 Python3.14는 `PYTHONPATH=tmp/card-review-deps;.test-deps`, 승격 환경 Python3.12는 `PYTHONPATH=.test-deps`로 실행했다. 최초 Node 하위 프로세스 검사에서 WinError50, 승격 환경에 cp314 의존성을 사용한 수집 오류가 있었으며, 맞는 Python3.12 의존성으로 다시 검증했다.

- `python -m pytest tests/test_mes_query.py tests/test_mes_handover.py tests/test_mes_handover_http.py tests/test_pda_handover.py tests/test_mes_storage.py -q`: **21 passed** (Python3.12).
- `python -m pytest tests/test_mes_server.py tests/test_mes_http.py tests/test_mes_card_adapter.py tests/test_pda_mes_alignment.py tests/test_router_pipeline.py tests/test_pipeline_ollama_integration.py -q`: **73 passed**.
- `node tests/mes_query_pda.cjs` 및 `node --check shiftlink/mes/web/pda.js`: PASS.
- `python -m coverage run --data-file=tmp/mes-query-20261002.coverage --source=shiftlink.mes.query -m pytest tests/test_mes_query.py -q`, 같은 data-file의 coverage report: **11 passed, query.py 96%**. 전체 프로젝트 커버리지 주장은 하지 않는다.
- `python -m eval.harness --suite dev --run-id mes-h1-h2-20261002`: **A~F 6/6 PASS, 46/46 사례**. [보고서](../../artifacts/mes-h1-h2-20261002/local-harness.json). 기존 하니스는 결정적 모델 stub이며 실제 모델 지연·품질을 증명하지 않는다.

## Jetson 실행

다른 에이전트와 충돌하지 않도록 기존 `/home/jetson/shiftlink/app`, 8000번 서버 및 데이터는 변경하지 않았다. `/tmp/shiftlink-h1h2-1003f02-hyj/app`에 작업 브랜치를 별도 clone하고, 먼저 `python3 -m eval.harness --suite dev --run-id jetson-h1h2-20261002` **6/6 PASS**를 확인했다. Jetson pytest는 설치되어 있지 않아 해당 명령은 실행 불가였다. 의존성을 전역 설치하지 않았다.

그다음 [실행 스크립트](../../artifacts/mes-h1-h2-20261002/acceptance_smoke.py)를 `python3 acceptance_smoke.py`로 실행했다. 임의의 빈 localhost 포트·전용 acceptance.sqlite3를 쓰고 서버를 finally에서 종료한다. 기존 Ollama의 exaone 모델만 사용하고 모델 옵션·서비스 상태는 변경하지 않는다.

[실기기 결과 JSON](../../artifacts/mes-h1-h2-20261002/jetson-acceptance.json): HTTP 질의 응답, `K-1001` 인용, 안전 공지 4건, review_queue=false, 실제 `exaone3.5:2.4b-instruct-q4_K_M` 모델 호출 **2.456초**, 서버 재시작 후 duplicate=true·최초 생성 시각 동일·outbox 1건. 인식 결과는 API로 주입했다.

**품질 한계:** 이번 모델 응답의 answer는 `K-1001` 문자열뿐이었다. HTTP·검색·인용·안전 연결 성공과 별개로 설명형 답변 품질은 이 1건으로 통과 판정할 수 없다. 물리 웹캠·PDA 조작 및 W2-1/G1/G2 현장 루브릭 채점도 미실시다. Claude의 파이프라인 연결부 리뷰는 아직 받지 않았다. 기존 운영 서버에 배포하거나 자동 시작하지 않았다.

## H3~H5

- H3: [naming_registry](../collaboration/naming_registry/registry.md)에 새 엔드포인트·필드·공개 함수·모델 환경변수 등록.
- H4: [#156 검토](policy-156-review-20261002.md): 이미 병합된 변경에 승인 예외 SHA 결합·출처 계보 검증 보강 의견. GitHub 댓글이나 리뷰를 대신 게시하지 않았다.
- H5: [결정](pdp-01-breaker-trip-decision-20261002.md): breaker_trip은 PDP-01 bool 접점 측정점으로 포함·유지.

작업 중 발견된 다른 에이전트의 api-only·별도 PDA 서버 변경과 초기 미추적 파일은 이 PR에 포함하지 않는다. outbox 클라우드 업로드 워커도 이번 범위 밖이다.
