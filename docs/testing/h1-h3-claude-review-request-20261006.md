# H1·H2 완료 내역 및 H3 Claude 리뷰 요청

구현 PR [#198](https://github.com/hyjuy/ShiftLink/pull/198)은 main에 병합됐다. 이 문서는 완료 내역과 남은 리뷰 범위를 정리한다.

| 업무 | 상태 | 이번 요청 |
| --- | --- | --- |
| H1: 카드 ID뿐인 답변 수정 | 전달받은 Claude 리뷰 반영, 수정, 실제 Jetson 재검증 완료 | 완료 내역과 증거 공유 |
| H2: T6 승인 게이트·사건 중복 제거 | 구현·테스트·PR 완료 | 완료 내역 공유 |
| H3: MES와 업로더 상시 실행 구성 | 결정 한 줄·deploy/ 반영 및 스크립트 검증 완료 | Claude 구성 리뷰 요청 |

H1 수정본에 대한 추가 재리뷰를 필수 완료 조건으로 두지 않는다. H3의 Claude 리뷰 완료 여부는 확인되지 않았다.

## H1: Claude 리뷰를 반영한 수정과 검증

원인은 작은 모델 컨텍스트에서 프롬프트가 잘리는 현상이었다. 컨텍스트 4096 수정(#196) 이후, 전달받은 Claude 리뷰에서 공용 ID 검증 누락·MES 동시 실행 메모리·160자 끊김이 지적됐다. #198에서 아래 후속 조치를 반영했다.

- `K-1001 참조`, `카드 K-1001`, `참고: K-1001`, `K-1001 확인`을 공용 검사로 거절한다. 정상 설명 문장 속 카드 ID는 허용한다.
- 어댑터·파이프라인·응답 검증기가 공용 `answer_content_error`를 사용하며 출력 예시의 정확한 복사도 거절한다.
- 계속 실패하면 한 번 재시도한 뒤 검토 대기로 보낸다.
- 실제 모델 원본이 160자에서 문장 중간으로 끝나는 것을 확인했다. 최종 어댑터는 이미 생성된 완결 문장까지만 보존한다. 완결 문장이 없으면 거절·재시도하며 소수점을 문장 경계로 취급하지 않는다.

Jetson의 실제 `exaone3.5:2.4b-instruct-q4_K_M`, 컨텍스트 4096에서 격리 MES HTTP 서버와 생산 tick을 함께 실행했다.

| 측정 | 결과 |
| --- | --- |
| 두 질의의 HTTP 응답 시간 | 6.494초·6.318초 |
| 전달된 답변 | 137자·98자 완결 문장, K-1001 인용, review_queue=false |
| 최소 Linux MemAvailable | 2598.215 MiB |
| MES 최대 RSS | 37.254 MiB |
| tegrastats 최대 RAM | 4864/7620 MB |

모델 원본의 160자 끊김 자체는 남아 있다. 답변 내용의 정확성·절차 완전성을 보장하는 변경은 아니다. 두 질의의 단일 실행이며 p95·콜드 스타트 측정이 아니다. 물리 PDA·웹캠 및 전체 시연 앱 동시 실행은 검증하지 않았다.

- 코드: [response.py](../../shiftlink/agent/response.py), [pipeline.py](../../shiftlink/agent/pipeline.py), [ollama.py](../../shiftlink/edge/ollama.py)
- 실제 요청·응답·메모리: [jetson-live-complete.json](../../artifacts/card-id-answer-20261006/jetson-live-complete.json)
- 상세 검증 기록: [mes-h1-h3-review-20261006.tdd.md](mes-h1-h3-review-20261006.tdd.md)

## H2: 승인 없는 T6 예외 거절과 사건 group_id 중복 제거

#187 후속 구현으로 T6 예외에 명시적 요청·승인자·유효 승인 날짜·사유·근거·검토 카드 SHA를 요구한다. 기존 승인 4건에는 기존 L1 검토 SHA와 현재 카드 SHA가 같음을 확인해 연결했다.

실제 출처는 승인된 case 범위, 문서 버전, 카드 use_scope, group_id를 검증하고 같은 사건의 group_id를 중복 제거한다. 일반 L1 승격으로 T6 승인 누락·변경 실패를 덮지 못하도록 별도 실패 사유를 유지한다.

- 코드: [policy_gate.py](../data/knowledge_cards/kb/20260930-C/policy_gate.py)
- 회귀 테스트: [test_t6_policy_gate.py](../../tests/test_t6_policy_gate.py)
- C 배치 정책 게이트 결과: `kb_ready=true, blocked_cards=0`

## H3: 결정과 Claude 리뷰 요청

**결정: 업로더는 별도 shiftlink-uploader.service로 유지하고, MES가 Wants로 함께 시작하며 동일 SQLite DB를 사용한다.**

MES의 업로더 Wants와 명시적 DB 경로를 반영했고 두 설치 스크립트의 실행 경로·DB를 인용했다. 업로더는 MES 뒤에 시작하며 MES가 종료돼도 저장된 pending 항목을 전송할 수 있도록 별도 서비스로 둔다.

- [install_service.sh](../../deploy/install_service.sh)
- [install_uploader.sh](../../deploy/install_uploader.sh)
- [mes-uploader-decision.md](../../deploy/mes-uploader-decision.md)

WSL Linux의 `bash -n` 및 DRY_RUN으로 동일 DB, MES Wants, 업로더 After를 확인했다. 실제 systemd 등록·부팅·재시작 및 클라우드 전송은 미검증이다.

Claude에게 요청할 검토:
1. 별도 서비스 결정과 MES Wants / 업로더 After 관계가 시작 순서·장애 분리에 적절한가?
2. 두 서비스가 같은 DB를 사용하고, DB 경로·실행 경로에 공백이 있어도 실행 가능한가?
3. MES 정지 시 업로더 유지, 오프라인 재시도, 부팅 자동 시작 구성에 누락이 있는가?
4. 실제 서비스 등록 후 필요한 최소 검증 항목은 무엇인가?

코드를 직접 확인한 판단과 문서·측정 보고서로 확인한 판단을 구분해 달라. 문제가 있다면 파일·위치·재현 조건·필요한 수정을 제시해 달라.

## 기존 검증 결과와 이번 PR 범위

#198의 관련 테스트 241개가 통과했다. 해당 테스트에서 pipeline 96%, response 96%, ollama 94%, policy_gate 84%, 합계 94%를 확인했다. 이는 프로젝트 전체 커버리지가 아니다.

이번 PR은 리뷰 요청 문서만 추가한다. 기존 코드·테스트·Jetson JSON 증거 링크와 변경 범위를 확인한다. 구현을 재실행하거나 H3의 Claude 리뷰가 완료됐다고 주장하지 않는다.
