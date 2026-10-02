# H1~H5 완료 항목과 남은 작업 (2026-10-02)

확인 기준: MES 질의·인계 API, 명칭 등록, PR #156 정책 검토, PDP-01 측정점 결정. API 구현과 현장 수용 검증을 구분한다. H1~H3 구현·등록은 PR [#178](https://github.com/hyjuy/ShiftLink/pull/178)에서 병합됐다.

## 완료 항목

| 항목 | 완료 내용 | 구현·기록 위치 |
| --- | --- | --- |
| H1 | `POST /api/query`: 질문과 최근 웹캠 인식 설비 또는 수동 선택 설비, 현재 MES 관측값을 FixedPipeline 검색·exaone 호출에 연결하고 답·인용·안전 공지·MES 근거를 JSON으로 반환한다. | `shiftlink/mes/server.py`, `shiftlink/mes/query.py`, `shiftlink/mes/web/pda.js` |
| H2 | `POST /api/handover`: 인계 메모를 SQLite outbox에 저장한다. 서버 재시작 후 유지하며 동일 ID·동일 내용 재전송은 1건으로 유지한다. 같은 ID의 다른 내용은 HTTP 409로 거절한다. | `shiftlink/mes/storage.py`, `shiftlink/mes/server.py`, `shiftlink/mes/web/pda.js` |
| H3 | 새 엔드포인트·요청·응답 필드·공개 함수 등록 및 등록 PR 병합. | `docs/collaboration/naming_registry/registry.md`, PR #178 |
| H4 | PR [#156](https://github.com/hyjuy/ShiftLink/pull/156)의 출처 등록부·분할 정책·T6 게이트 변경 확인 및 수정 의견 작성. 해당 PR은 이미 병합됐다. | `docs/testing/policy-156-review-20261002.md` |
| H5 | `breaker_trip`을 PDP-01 (`EQ-0002`)의 bool 상태 접점 측정점으로 포함·유지하기로 결정했고 측정점도 구현돼 있다. `0` 정상, `1` 트립이며 단락 원인이나 무전압 확인을 대신하지 않는다. | `docs/testing/pdp-01-breaker-trip-decision-20261002.md`, `shiftlink/mes/scenarios/priority.py`, `shiftlink/mes/signal_semantics.py` |

## 남은 작업

- [ ] **H1 설명형 답변 품질 확인·개선:** 기존 Jetson 분리 실행 기록에서 실제 exaone 호출은 성공했으나 answer가 `K-1001` 문자열뿐이었다. `shiftlink/edge/ollama.py`, `shiftlink/agent/pipeline.py`에서 프롬프트·응답 처리 원인을 확인하고 실제 모델로 다시 검증한다.
- [ ] **H1 현장 수용 검증:** 물리 PDA·웹캠 → Jetson 질의 1건을 실행하고 루브릭 W2-1·G1·G2를 채점한다. 인식 결과 API 주입과 stub 기반 테스트만으로 현장 완료 처리하지 않는다.
- [ ] **H1 Claude 연결부 리뷰 확인:** PR #178에는 `nalziori`의 APPROVED 기록이 있으나 리뷰 본문이 비어 있다. `shiftlink/mes/query.py`의 관측값 → FixedPipeline 연결부에 대한 Claude 상세 리뷰 완료 여부를 확인하고 결과를 기록한다.
- [ ] **H4 예외 검증 보강:** `docs/data/knowledge_cards/kb/20260930-C/policy_gate.py`의 T6 예외를 명시적 승인 기록과 검토 카드 SHA에 결합한다. 승인 없는 예외·검토 후 카드 변경을 거절하는 테스트를 추가한다.
- [ ] **H4 실제 사례 계보 검증 보강:** 같은 파일에서 실제 사례의 유효한 case 승인 범위와 카드 연결을 확인하고 승인된 사건 `group_id`로 중복 제거한다. scope 누락·카드 불일치·동일 사건 출처 중복 테스트를 추가한다. 확인 당시 최신 main에도 기존 T6 분기가 남아 있었다.
- [ ] **H4 검토 의견 공유:** 수정 의견은 로컬 문서에 작성돼 있으며 GitHub 댓글·리뷰로 게시하지 않았다. 담당자에게 전달한 기록을 남긴다.

H2·H3·H5에는 제시된 범위에서 추가 구현 항목이 없다. outbox의 Aiven 업로드 워커는 H2의 로컬 저장 요구 범위 밖이다.

## 확인한 검증과 한계

2026-10-02 로컬 `feat/mes-query-handover-20261002`의 `a7b80b5`에서 다음을 재실행했다. 이 숫자를 이번 문서 브랜치의 전체 테스트 결과로 해석하지 않는다.

```powershell
$env:PYTHONPATH='tmp/card-review-deps;.test-deps'
python -m pytest tests/test_mes_query.py tests/test_mes_handover.py tests/test_mes_handover_http.py tests/test_pda_handover.py tests/test_communication_integration.py -q
node tests/mes_query_pda.cjs
```

- Python: **18 passed, 7 subtests passed**.
- PDA 질의 계약: **MES query PDA contract PASS**.
- GitHub 확인: PR #178 병합 및 승인 기록, PR #156 병합, 최신 main의 `policy_gate.py` T6 분기.
- 기존 Jetson 실호출·인계 재시작 증거 및 품질 한계: [MES API 검증](mes-query-handover-20261002.tdd.md).
- 이번 PR은 `feat/mes-query-handover-20261002`의 후속 통신 연동·검증 기록도 포함한다. `MesHTTPClient`, `scripts/check_mes_http.py`, Jetson `--api-only`, 명칭 등록, HTTP·PDA 프록시 통합 테스트 및 Jetson 분리 실행 증거를 함께 반영한다. 현장 채점, 모델 품질 개선, 정책 게이트 수정은 수행하지 않는다.

후속 변경을 최신 main 기준 문서 브랜치에 병합한 뒤 재검증했다.

```powershell
python -m pytest tests/test_communication_http_client.py tests/test_communication_integration.py tests/test_mes_http.py tests/test_mes_query.py tests/test_mes_handover.py tests/test_mes_handover_http.py tests/test_pda_app.py -q
node tests/mes_query_pda.cjs
git diff --check
```

결과: **35 passed, 38 subtests passed**, **MES query PDA contract PASS**, diff 검사 통과. Python 의존성 경로는 기존 작업 공간의 `tmp/card-review-deps`와 `.test-deps`를 사용했다. 실제 LLM·물리 장치를 이번 재검증에서 실행하지 않았다.
