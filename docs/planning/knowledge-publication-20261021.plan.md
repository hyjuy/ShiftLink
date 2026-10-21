# 질문에서 RAG 검색 반영까지 개발 계획

기준일: 2026-10-21. 사용자가 요청한 전체 흐름을 구현 대상으로 삼는다.
심사·검수·구조화·임베딩 작업자·실행 중 검색 반영과 MES 화면 연결을 구현했다.
결정적 모델 픽스처를 사용한 전체 흐름은 검증했고, 실제 Ollama 모델 검증은 연결 복구 후 별도로 수행한다.
임베딩 대기는 실제 벡터 생성 또는 검색 반영 완료가 아니다.

## 개발 전 확인한 PDA·MES

| 단계 | 현재 구현과 연결점 | 필요한 변경 |
| --- | --- | --- |
| 질문·지식 없음 | `pda.js`의 답변 화면, `query.py`의 `knowledge_status`, `storage.py`의 `query_log` | 답변 보류·모델 장애와 `no_applicable_card`를 구분해 유지 |
| 조치 시도 | PDA 조치 세션과 `query_id`를 가진 근무일지 기록 | 질문 당시 evidence와 실제 조치·실패 결과를 보존 |
| 근무일지 | `work_reports.py`, `MesService.record_work_report`, 서버 측 저장 시점 센서 근거 | 질문 ID·설비·자산 연결 검증 유지 |
| 후보 | `MesService._work_report_plans`의 T1~T6 후보와 부족 정보 사유 | 수동 기록도 허용하되 질문에서 출발한 경로와 구별 |
| 심사 | `/knowledge-candidates`, `candidate-review.js`, 관리자 `/api/admin/card-drafts/{id}/review` | 기존 승인·보완·반려와 검수 통과를 구분 |
| 구조화 | 후보부터 `KnowledgeCard` 스키마 사용, 원본은 draft/L0/dev | 검수 통과 시 원본을 보존하며 배포용 accepted/L1/kb 사본 검증 |
| 임베딩 | `rag2/embed.py`의 Ollama 임베딩과 모델별 prefix | 검수된 버전의 텍스트·해시·모델·벡터를 연결하는 작업자 추가 |
| 검색 | `query.py`: FixedPipeline 또는 S30h. S30h는 시작 시 chunks/vectors를 로딩 | 새 카드의 벡터와 청크를 함께 반영하고 실행 중 검색 경로 갱신 |

`scripts/field_card_promote.py`는 시연용 파일 추가·복구 도구로 남긴다. 정식 배포에 재사용하지 않는다.
현재 작업 트리에 다른 PDA·MES·연구 변경이 있으므로 관련 부분만 수정한다.

## 단계별 산출물과 검증

1. **심사 → 검수 → 구조화**
   - 기존 관리자 review API에 `quality_pass`를 추가한다. `approve` 후에만 가능하고 검수 의견이 필수다.
   - 별도 `quality_passed` 상태, 실제 관리자·검수 시각·리비전을 기존 감사 이력에 저장한다.
   - 원본 근무일지와 후보 카드를 바꾸지 않는다. 스키마 검증을 통과한 사본·임베딩 입력·내용 해시를 `review_flags.publication`에 원자적으로 저장한다.
   - 산출물은 `embedding_pending`, `searchable=false`다. 이후 보완·반려·재심사는 이 산출물을 무효화한다.
   - 테스트: 선행 승인 없음, 인증 없음, 의견 없음, 스키마 오류, 오래된 리비전, 저장 실패 롤백, 재시작 복원, 원본 보존.
2. **검수 화면과 작업 상태 표시**
   - 기존 MES 심사 화면에 검수 통과 버튼·구조화 미리보기·대기/실패/검색 반영 상태를 추가한다.
   - 심사·검수·임베딩·검색 반영을 각각 표시한다. 검수 시 안전·조건·반대 근거를 확인한다.
   - PDA 저장 안내에는 근무일지·후보 생성 결과만 표시하고 검색 반영을 확정하지 않는다.
3. **임베딩 작업자**
   - 실제 서비스의 검색 모델·문서 prefix·차원과 동일한 설정을 사용한다. 모델을 임의로 교체하지 않는다.
   - 작업 키는 카드 ID·검수 리비전·내용 해시·임베딩 모델이다. 네트워크 호출 중 MES 잠금을 잡지 않는다.
   - 실패·재시작 시 재시도하며, 처리 후 리비전·해시를 재검사해 반려되거나 변경된 카드의 늦은 결과를 버린다.
   - 유효한 유한 벡터·차원·정규화를 검사한다. 모델 장애는 검색 가능 상태로 바꾸지 않는다.
4. **RAG 검색 풀 반영**
   - 구조화 카드·청크·벡터·manifest를 SQLite delta 인덱스에 동일 버전으로 저장하고 질의용 뷰에 합친다. 정적 인덱스 파일을 덮어쓰지 않는다. 서로 다른 임베딩 모델의 벡터를 섞지 않는다.
   - S30h 및 기존 FixedPipeline의 실제 서비스 설정별 연결을 검증한다. 런타임 교체와 재시작 복원을 지원한다.
   - 검수 취소·재심사 시 검색에서 즉시 제외하고 기존 질의 이력은 보존한다.
5. **전체 경로 검증**
   - 질문 결과가 `no_applicable_card`인 것을 확인 → 조치 수행 → 연결된 근무일지 저장 → 후보 → 심사 → 검수 → 구조화 → 실제 모델 임베딩 → 같은 설비의 후속 질문에서 검색 후보로 조회.
   - 다른 설비·자산, 실패 조치, 불충분 근거, 반려 후보, 중복 제출, 작업자 장애, 임베딩 장애, 실행 중 재심사도 확인한다.
   - 검색 후보 조회와 최종 답변 채택은 구분한다. 기존 judge가 거른 카드를 답변에 강제로 포함하지 않는다.

## 고정할 데이터 계약

- 질문·근무일지·조치 원문은 근거이며 검수 과정에서 덮어쓰지 않는다.
- 후보 심사 상태, `KnowledgeCard.status`, 임베딩 상태, 검색 반영 상태는 별도다.
- 후보 생성은 이미 스키마를 사용한다. 검수 후 구조화는 근거 없는 재작성 없이 정식 사본을 검증하는 작업이다.
- 검수 의견은 확인 근거다. 빈칸을 모델로 채우거나 기존 safety_review를 자동 승인하지 않는다.
- `completeness.ready`는 기존 권장 지표다. 사람의 검수와 구별하며 단순 기록 건수만으로 자동 통과시키지 않는다.
- PDA 센서 폴링·단위·품질·질의 시점 evidence와 MES 운영 서비스 설정은 이번 변경에서 보존한다.

## 진행 상태

- [x] 현재 PDA·MES·후보 심사·스키마·검색 경로 코드 확인
- [x] 1단계 구현·회귀 검증
- [x] 2단계 검수 화면
- [x] 3단계 Ollama 임베딩 작업자 구현·HTTP 계약 검증
- [x] 4단계 실행 중 검색 풀 반영
- [x] 5단계 결정적 모델 픽스처·실제 브라우저 전체 검증
- [ ] 실제 Ollama 모델 검사: 현재 로컬·Jetson 연결 불가. `tests/publication_live.py`로 후속 확인

## 1단계 API와 검증 결과

기존 관리자 `POST /api/admin/card-drafts/{draft_id}/review`에 아래 요청을 보낸다.
관리자 세션·동일 출처·JSON·리비전 검증은 기존 경로를 사용한다.

```json
{"action":"quality_pass","reason":"원문·조건·조치 결과 검수 완료","expected_revision":1}
```

`expected_revision`은 실제 최신 조회값을 사용한다. 직전 상태는 `review_approved`여야 한다.
응답 `draft.status`는 `quality_passed`, `draft.review_flags.publication.state`는 `embedding_pending`이다.
`publication`에는 구조화 카드 사본·임베딩 입력·SHA-256·검수자·시각·리비전이 들어간다.
검수 직후에는 `searchable=false`다. 배경 작업자가 임베딩·인덱스 저장을 완료하면 `published/searchable=true`가 된다.
현재 MES 화면에 검수 버튼·구조화 미리보기·처리 상태를 연결했다. [사용법과 실행 경계](../guides/knowledge-publication.md)를 참고한다.

- 적용 스킬: `ponytail`, `tdd-workflow`, `systematic-debugging`.
- RED: 신규 HTTP 통합 테스트 11개 중 6개 실패·5개 통과. 미구현 `quality_pass`가 400으로 거절되는 것을 확인했다. 체크포인트 `d0028e3`.
- GREEN: 신규 12개를 포함한 관련 테스트 87개 중 86개 통과. 기존 저장소 프로세스 동시성 테스트가 시작 대기 10초 제한으로 1회 실패했고, 단독 재실행에서는 통과했다.
- 실행 대상: `test_knowledge_publication.py`, `test_candidate_management.py`, `test_work_report_capture.py`, `test_work_report_reuse_harness.py`, `test_mes_storage.py`.
- 원본 보존·재시작 복원·권한·선행 승인·리비전 충돌·필수 의견·스키마 실패·중복 검수·재심사 무효화·감사 이력 실패 시 트랜잭션 롤백을 확인했다.
- 위 RED/GREEN 수치는 1단계 당시 결과다. 최종 관련 회귀는 **183 passed**, 핵심 신규 모듈의 branch 포함 커버리지는 **89%**다.
- JavaScript 문법을 포함한 PDA Node 검증 8개 명령 통과. 실제 Chrome에서 1280/390 화면·실제 HTTP 업무 흐름을 확인했다.
- 실제 Ollama와 장비 배포는 검증하지 않았다. [반증 및 하니스 적용 기록](../harness/knowledge-publication-adoption-20261021.md)에 증거와 한계를 분리했다.
