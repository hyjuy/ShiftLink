# H1~H3 리뷰 반영 및 최종 검증 (2026-10-06)

대상은 사용자가 전달한 H1~H3 업무와 H1 Claude 리뷰 의견이다. 최초 로컬 재현은 [이전 기록](card-id-answer-20261006.tdd.md)에 보존하며, 아래 결과가 최신 Jetson 검증이다.

## H1: 군더더기 ID 답변·예시 복사·라이브 끊김

- `answer_is_card_ids_only`에 참조·참고·카드·확인을 통합했다. 이전 별도 검사를 제거했고 설명 문장 속 ID는 허용한다.
- 공용 `answer_content_error`를 어댑터·파이프라인·응답 검증에서 사용한다. 출력 예시 문구의 정확한 복사도 거부한다.
- 재시도는 한 번이다. ID뿐인 답·예시 복사가 계속되면 빈 본문과 검토 대기로 유지하며 숫자 가드 fallback으로 정상 처리하지 않는다.
- 실제 Jetson에서 모델 원본이 160자에서 `프라이밍 과정`으로 끝나는 것을 확인했다. 평가 도구의 저장 단계에서 생긴 문제가 아니다.
- 120자 요약 지시만으로는 해결되지 않았다. 미완성 160자 답을 단순 거부한 중간 버전은 두 질의 모두 재시도 후 검토 대기가 됐다.
- 최종 어댑터는 160자에서 끊겼을 때 **이미 생성된 완결 문장까지만 보존**한다. 소수점은 문장 경계로 보지 않는다. 완결 문장이 하나도 없으면 거부·재시도한다. 카드의 단계·안전 블록은 기존 응답 구성 경로를 사용한다.
- 이는 생성 답변의 내용 정확성을 보장하는 변경이 아니다. 미완성 꼬리를 새 문장으로 지어내거나 카드 절차를 재작성하지 않는다.

Jetson `jetson-06`, 실제 `exaone3.5:2.4b-instruct-q4_K_M`, 컨텍스트 4096에서 격리 MES HTTP 서버와 생산 `_run_ticks`를 함께 실행했다. 실행 코드 기준은 `662a786`이다.

| 항목 | 최종 결과 |
| --- | --- |
| 원래 K-1001 제목 질의 | HTTP 6.494321015초, 완결된 137자 답, K-1001 인용, review_queue=false |
| 확인 순서·이유 상세 질의 | HTTP 6.318477287초, 완결된 98자 답, K-1001 인용, review_queue=false |
| 최소 Linux MemAvailable | 2598.21484375 MiB |
| MES 프로세스 최대 RSS | 37.25390625 MiB |
| tegrastats 최대 RAM 사용 | 4864/7620 MB |
| 최종 모델 원본 | 두 답 모두 160자·미완성. 사용자에게 전달한 답은 완결 문장까지만 보존됨 |

증거:
- [라이브 끊김 수정 전 원본·메모리](../../artifacts/card-id-answer-20261006/jetson-live-before-cap-fix.json)
- [최종 원본 요청·응답·메모리](../../artifacts/card-id-answer-20261006/jetson-live-complete.json)
- 실행 스크립트: `python3 -B scripts/measure_jetson_query.py jetson-live-result.json`

운영 저장소·MES 포트·DB는 변경하지 않았다. `/tmp/shiftlink-h1-live-20261006-complete`의 전용 SQLite와 임의 localhost 포트를 사용했다. 카메라 인식은 HTTP API로 주입했으며 물리 PDA·웹캠을 측정하지 않았다. 다른 시연 앱은 추가 실행하지 않았다. 이 수치는 두 질의의 단일 실행 기록이며 p95·최악 지연·전체 시연 구성의 메모리 보장이 아니다.

## H2: T6 승인과 실제 사건 계보

- 예외는 기존 explicit_user_request, 승인자, 요청, 유효 승인 날짜, 예외 사유·근거 및 검토 카드 SHA가 모두 있어야 인정한다.
- 기존 승인 4건에는 L1 검토 기록과 현재 카드 SHA가 동일함을 확인한 뒤 같은 SHA를 결합했다. 신규 승인을 만들지 않았다.
- 실제 출처의 approved_for_draft 상태만으로 세지 않는다. 비합성 출처의 유효 case 승인 범위·문서 버전·해당 카드 use_scope·group_id를 확인한다.
- 같은 사건의 출처 2개는 승인 범위의 group_id로 중복 제거한다. 일반 L1 승격 기록이 T6 승인 누락·변경 문제를 다시 덮지 못하도록 별도 실패 사유를 유지한다.
- scope 누락, 다른 카드, background, 그룹 누락, 미승인 출처, 합성 출처, 버전 불일치 및 승인자 누락을 검증한다.
- 실제 C 배치 정책 게이트: `kb_ready=true, blocked_cards=0`.

## H3: 상시 실행 구성

**결정: 업로더는 별도 shiftlink-uploader.service로 유지하고, MES가 Wants로 함께 시작하며 동일 SQLite DB를 사용한다.**

`deploy/install_service.sh`에 업로더 Wants와 명시적 DB 경로를 반영했다. 두 설치 스크립트의 실행 경로·DB를 인용하고 Linux LF 줄바꿈을 사용한다. [설치 및 결정](../../deploy/mes-uploader-decision.md)에 같은 DB 지정 방법을 기록했다.

WSL Linux에서 두 스크립트의 `bash -n` 및 DRY_RUN 생성 결과를 확인했다. 동일 DB의 MES·업로더 ExecStart, MES Wants 및 업로더 After를 확인했다. 실제 systemd 등록·활성화와 Aiven 전송은 수행하지 않았다. H3에 대한 별도 Claude 승인 여부는 확인하지 않았다.

## RED/GREEN와 커버리지

| 회귀 단계 | RED | GREEN에서 보장 |
| --- | --- | --- |
| ID 군더더기·예시 복사 | 17 failed, 15 passed | 세 검증 경로의 거부·재시도·소진 및 정상 설명 허용 |
| 라이브 160자 꼬리 | 최초 2 failed, 32 passed; 완결 문장 보존 1 failed, 34 passed | 완결 문장만 보존, 소수점 오인 방지, 완결 문장 없는 답 재시도 |
| T6 정책 | 16 failed, 3 passed | 승인 없는·변경된 예외 거부, 유효 case·카드 연결, 사건 중복 제거 |

최종 PR 작업트리에서 아래 대상 **241 passed**:
```text
tests/test_card_id_answer.py tests/test_answer_id_only.py tests/test_edge_ollama.py
tests/test_pipeline_ollama_integration.py tests/test_router_pipeline.py
tests/test_retrieval_response.py tests/test_answer_guards.py
tests/test_t6_policy_gate.py tests/test_batch_c_format.py
tests/test_mes_uploader.py tests/test_check_upload_recon.py
```

실행: `python -B -X utf8 -m pytest <위 대상> -q -p no:cacheprovider --tb=short`.
동일 대상 coverage run/report: pipeline.py 96%, response.py 96%, ollama.py 94%, policy_gate.py 84%, 합계 94%. 프로젝트 전체 커버리지 주장은 하지 않는다. `git diff --check` 통과.

RED/GREEN 커밋은 현재 PR 브랜치에 보존했다. 병합 시 squash하더라도 이 기록과 실제 JSON 증거를 유지한다. 다른 작업에서 추가된 Unity 커밋은 별도 작업트리로 분리해 이 PR에 포함하지 않았다.

남은 한계: 모델 답변의 현장 정확성·절차 완전성, 물리 PDA·웹캠, 전체 시연 앱 동시 실행의 메모리 및 H3 Claude 검토.
