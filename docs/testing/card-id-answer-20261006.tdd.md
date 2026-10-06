# K-1001 카드 ID뿐인 답변: 실제 모델 재현 및 검증 (2026-10-06)

사용자 요청에서 도출한 여정: 기존 MES 관측값과 질문으로 한국어 설명 및 유효한 인용을 받고, ID만 생성하면 한 번 재시도한 뒤 계속 실패할 때 검토 대기로 보낸다.

## 원인

- 수정 전 `ollama.py`의 `NUM_CTX=2048`에서 MES 관측값을 포함한 입력이 잘렸다.
- 실제 Ollama 서버 로그: `time=2026-10-06T10:08:11.447+09:00 level=WARN source=llama_server.go:320 msg="truncating input prompt" limit=1026 prompt=2111 keep=4 new=1026`.
- 원래 프롬프트와 스키마를 그대로 두고 `num_ctx`만 4096으로 바꾸자 입력 2111토큰 전체가 처리되고 설명이 생성됐다. 스키마 enum이 본문에 강제로 적용됐다는 증거는 없다.
- `_parse_output`과 공용 응답 검증은 비어 있지 않은 문자열을 허용해 `answer="K-1001"`을 통과시켰다. 파이프라인은 검증 실패가 없으므로 재시도하지 않았다.
- 관측값 없는 동일 제목 질문은 실제 qwen 및 exaone 모두 설명을 생성했다. MES 입력까지 맞춰야 원래 증상이 재현됐다.

## 수정

- 현재 저장소에는 컨텍스트 4096 변경이 병합돼 있다.
- 초기·재시도 프롬프트에 한국어 본문과 인용 배열의 역할 및 JSON 예시를 명시했다.
- 공용 `answer_is_card_ids_only`를 어댑터·파이프라인·응답 검증에서 사용한다. 괄호·쉼표·코드 표시로 감싼 ID만 있는 본문도 거부한다. 설명 문장 속 ID는 허용한다.
- 한 번 재시도 후 정상 설명이 오면 복구하고, 계속 ID만 오면 빈 본문·검토 대기로 유지한다. 수치 가드의 fallback으로 바꾸지 않는다.
- `scripts/reproduce_card_id_answer.py`는 격리된 메모리 MES와 실제 Ollama 요청·응답을 JSON으로 저장한다. 운영 MES와 Jetson 데이터는 사용하지 않았다.

## 실제 모델 증거

로컬 Windows Ollama에서 실제 `exaone3.5:2.4b-instruct-q4_K_M`를 CPU로 실행했다. Jetson의 SSH 접속은 시간 초과로 실패했다.

| 조건 | 모델 입력 토큰 | 결과 | 증거 |
| --- | ---: | --- | --- |
| 수정 전 커밋 a7b80b5143f3f15bf853c3ba570ec1b0cb170b3e, 컨텍스트 2048, MES 관측값 | 1026 (원래 2111) | answer=K-1001, cited_card_ids=[K-1001], review_queue=false | [원본 요청·응답](../../artifacts/card-id-answer-20261006/mes-before.json) |
| 같은 수정 전 요청, 컨텍스트만 4096 | 2111 | 설명 생성, K-1001 인용 | [컨텍스트 비교](../../artifacts/card-id-answer-20261006/mes-before-4096.json) |
| 본문 검증·프롬프트 수정만 적용, 컨텍스트 2048 | 1026 (원래 2190) | 설명 생성, 문장 끝 잘림 | [중간 비교](../../artifacts/card-id-answer-20261006/mes-after.json) |
| 최신 코드, 컨텍스트 4096 | 2190 | 한국어 설명, K-1001 인용, review_queue=false | [최종 원본 요청·응답](../../artifacts/card-id-answer-20261006/mes-after-4096.json) |

수정 전후 `pipeline_inputs`가 완전히 동일함을 assert로 확인했다. 최종 답변은 160자이며 실제 답변 호출의 total_duration은 29.7543861초였다.

재현:
```powershell
$env:PYTHONPATH='.test-deps'
python -B -X utf8 scripts/reproduce_card_id_answer.py --model exaone3.5:2.4b-instruct-q4_K_M --cpu --mes --baseline-revision a7b80b5143f3f15bf853c3ba570ec1b0cb170b3e --output artifacts/card-id-answer-20261006/mes-before.json
python -B -X utf8 scripts/reproduce_card_id_answer.py --model exaone3.5:2.4b-instruct-q4_K_M --cpu --mes --output artifacts/card-id-answer-20261006/mes-after-4096.json
```

## RED/GREEN 및 범위

- RED: `tests/test_card_id_answer.py`에서 **11 failed, 1 passed**. ID뿐인 본문이 정상 처리되고 한 번도 재시도되지 않았다.
- GREEN: `tests/test_card_id_answer.py tests/test_edge_ollama.py tests/test_pipeline_ollama_integration.py tests/test_router_pipeline.py tests/test_retrieval_response.py tests/test_answer_guards.py tests/test_mes_query.py`를 `python -B -X utf8 -m coverage run --data-file=artifacts/card-id-answer-20261006/coverage.data --source=shiftlink.edge.ollama,shiftlink.agent.pipeline,shiftlink.agent.response -m pytest ... -q -p no:cacheprovider --tb=short`로 실행: **192 passed**.
- 별도 `python -B -X utf8 -m pytest tests/test_answer_id_only.py -q -p no:cacheprovider --tb=short`: **5 passed**.
- 커버리지: pipeline.py **96%**, response.py **96%**, ollama.py **93%**, 합계 **95%**. 프로젝트 전체 커버리지 주장은 하지 않는다.
- `git diff --check` 통과.
- 최초 RED 체크포인트 커밋은 기존 `.git/index.lock`으로 실패했다. 잠금 파일을 삭제하지 않았다. 이후 외부 작업에서 관련 변경이 병합돼 현재 HEAD `93af323`에 본문 검증 및 컨텍스트 변경이 포함됨을 확인했다. 별도 RED 커밋이 생성됐다고 주장하지 않는다.
- 남은 한계: Jetson 재검증은 미실시. 최종 설명의 현장 정확성·절차 완전성은 별도 평가가 필요하다. 160자 문법 제한은 긴 답변을 자를 수 있으며 이번 검증은 ID뿐인 본문 및 컨텍스트 누락 문제를 대상으로 한다.
