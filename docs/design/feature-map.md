# 기능 지도

HPU 자산–관측–사건–조치–결과의 공통 모델과 단계별 계획은
[온톨로지 확장 설계](hpu-ontology-extension.md)에 있다. **1~5단계 설명 연결과 6단계 기본 off의 별도 검색 비교 실험을 구현했다. 운영 질의·검색·답변에는 온톨로지 실험을 연결하지 않는다.**
`shiftlink/mes/incident_ontology.py`의 `read_incident_bundle`/`project_incident`를 재사용하며
`hpu_ontology.py:project_hpu`는 HPU 진입점이다. 다른 설비는 유형 FK 선택값만 바꾼다.
[구현·검증 기록](../testing/hpu-ontology-phase12-20261024.tdd.md)을 함께 확인한다.
3단계는 `ontology_shadow.py:run_shadow`와 `python -m shiftlink.mes.hpu_ontology --mode shadow`로
관계·미확인 사유를 별도 JSON에서 확인한다. 기본 off이며 기존 질의/검색/답변과 업무 DB 저장은 유지한다.
[실행 안내](../guides/hpu-ontology-shadow.md), [3단계 검증](../testing/hpu-ontology-shadow-20261024.tdd.md).
4단계는 `server.py:_Handler.do_GET` → `ontology_api.py:explain` → 기존 shadow/읽기 전용 projector다.
`SHIFTLINK_HPU_ONTOLOGY=explain`과 승인 자료 경로를 명시해야 관리자 Bearer 인증으로
`GET /api/incidents/<incident_id>/ontology`를 조회할 수 있다. 사건 스코프·해시 결합 페이지·상한·미확인 사유를 반환한다.
[API 계약](../guides/hpu-ontology-api.md), [4단계 검증](../testing/hpu-ontology-api-20261024.tdd.md).
5단계는 설명 API의 선택 `query_id` → `publication_ontology.py:connect` → `validated_record`/`still_current`다.
새 질의 로그의 내부 `publication_ticket`으로 실제 인용 판본을 대조하고, 승인 복사본의 출처 사건·자산·원문 해시를 확인해
`CardVersion` → `DERIVED_FROM_INCIDENT`만 추가한다. 반려·판본 미확인·출처 불일치는 unresolved로 남긴다.
답변 응답과 기존 로그 원문은 유지하며 [5단계 검증](../testing/hpu-publication-links-20261024.tdd.md)을 참고한다.
6단계는 `hpu_retrieval_experiment.py:run_experiment`의 독립 S30h 쌍 비교다.
`SHIFTLINK_HPU_RETRIEVAL=off|experiment`이며 기본 off. 환경 변수만으로 서비스 질의를 가로채지 않는다.
같은 검증된 풀의 HPU 사건 관계 후보를 최대 2개 보완하고 기존 청크/토큰·judge·원문 필터를 유지한다.
고정 8사례×5회 fixture에서 필수 인용 0/10→10/10, 오인용·오연결 0, 평균 16.2→62.6ms였으며 운영 채택은 하지 않았다.
[실행 계약](../guides/hpu-retrieval-experiment.md), [비교 JSON](../testing/hpu-retrieval-comparison-20261025.json),
[6단계 검증](../testing/hpu-retrieval-experiment-20261025.tdd.md)을 참고한다.
2026-10-25 실제 운영 모델/인덱스 본평가 32쌍은 이력 인용 10/12→10/12·관계 추가 0건이었다.
별도 탐색 8쌍은 2/8→8/8로 인용을 회복했지만 평균 지연 +1.278초와 공통 이력 분류·미기록 시간 보류 문제가 남아
운영 적용을 보류했다. 기본 off와 운영 소스·인덱스는 유지한다. [실제 모델 검증](../testing/hpu-retrieval-live-20261025.md).

2026-10-25 로컬 후속 수정은 `field_history.py:is_history_question`의 기록 목적어 누락을 고치고,
`S30hPipeline.evidence/run`에서 명시적 일지 조회를 적합한 검수 현장 청크의 벡터 순위로 제한한다.
미기록 기간/날짜는 임베딩 전에, 불필요한 매뉴얼·교대 이벤트는 judge 전에 제외한다.
판정 거절은 보류하고 통과한 일지 원문을 보존한다. 현재 질문 경로·모델·관계 실험 기본 off는 유지하며 운영 미배포다.
[동일 질문 재검증·한계](../testing/hpu-retrieval-recheck-20261025.md), `tests/test_hpu_history_recheck.py`.
같은 실제 모델·대표 질문의 기본 경로는 인용 10/12→12/12, 미기록 조건 보류 2/4→4/4,
평균 5.200→2.986초·p95 10.536→10.233초였다. 기존 탐색 8회도 관계 off에서 8/8 인용으로 회복했다.
수정 후 관계 추가는 0건으로 이 질문에서 추가 이득이 없었으며 기본 off를 유지한다.
대표 현재 질문 8회의 답변 해시와 인용도 같았다. 합성 카드·소표본·PC→Jetson API 측정이라는 한계가 있다.

후속 [p95 구간 분석](../testing/hpu-p95-20261025.md)은 답변 모델의 입력·decode와
judge·하니스 준비/해제·클라이언트 전송 지연을 구분한다.
`evidence_score.py:judge_dist`는 확인한 judge의 점수까지 6토큰으로 읽고 누락 시 20으로 재확인한다.
`run_experiment`는 한 경로의 독립 인덱스 사본을 해제한 뒤 다른 경로를 실행하며
evidence override 순환 참조를 제거하고 정리 비용을 total에 포함한다.
기본 off·검색/답변 내용·게시 검증은 유지하며 운영 미배포다.
최종 대표 재측정 off p95는 11.124→8.807초(복사 제외 실행 10.618→8.163초)였지만
탐색 off p95는 2.132→2.854초로 악화됐다. 초기 측정의 악화도 보존하여 일관된 운영 개선으로 확대하지 않는다.
전후 출력 비교 80/80에서 후보·통과 목록·경로·답변 hash가 같았다. 일반 서비스 API/PDA 종단 p95와 구분한다.



2026-10-24 로컬 후속 작업의 탐색 인덱스다. 기준 커밋은 `eea5b1101feeda74a68ad59f4a8debb3eb01b099`이며
후속 승인 배포와 격리 실제 모델·Pi 화면 검증 기록을 포함한다. 저장소 전체 지도와 장비 현재 상태는 이 한 행만으로 확정하지 않는다.

| 사용자 목적 | 호출 경로와 코드 근거 | 저장 경계 | 검증과 확인 수준 |
|---|---|---|---|
| 가끔 발생해 수리 전까지 유지되는 점진 합성 고장 | `mes/__main__.py --progressive-faults` → 화면 `random_mode` 제어 → `progressive_factory.py`; 기존 시작은 기본 운전 | 정답은 simulation_labels; 관측/사용자 선택 설비의 공통 수리 절차를 resolution API에 연결, 재가동 후 정상 3회 확인; 기존 랜덤 원본 유지 | 초기 24/24·오통지2 보류 기록 보존. RMS16 별도 후보의 새 평가38/38·오통지/중복0, Pi 1Hz/화면 검증 후 2026-10-25 적용. [평가](../testing/mes-rms-confirmation-20261024.md), [적용](../testing/mes-rms16-deployment-20261025.md). [사용법](../guides/mes-progressive-faults.md). 버튼 분리·복구 연결은 Pi 검증 후 기존 사건을 수리·관측 회복 처리하고 [운영 적용](../testing/mes-random-controls-deployment-20261025.md)했다. 이전 미적용 [후속 기록](../testing/mes-random-mode-controls-20261025.md)은 보존한다. 카드 없는 현재 설비 답변의 조치 시작과 실제 근무일지 저장은 [추가 검증](../testing/mes-random-no-card-record-20261025.md)을 따른다. |
|
| Pi 분석을 현재 센서·지식카드와 함께 질문에 참고 | PDA 기존 UI → `pda/__main__.py:make_handler` → `agent/pi_analysis.py:attach_to_query` → `mes/query.py:query_service` / `validate_context` → `rag2/s30h.py:run` 또는 `edge/ollama.py:build_messages` | 질의 당시 `query_context.pi_analysis`만 추가. 기존 일지·후보·게시·KG·센서는 유지 | `tests/test_pi_analysis_query.py`, 기존 이력·게시·PDA 회귀. 로컬 fixture 이후 2026-10-24 Jetson 5파일→Pi 2파일 순차 배포, 실제 LLM·Pi 실제 UI로 격리 재검증. 당시 분석기는 r5 유지, 기존 업무 14테이블 1054행 보존. 이후 PDA 표시 r6 적용은 질문 연결을 유지하되 Jetson의 기존 30프레임 참고 제한은 남음 |

[입력 계약·실패 처리·배포 순서](../guides/pi-analysis-query-context.md)와
[최종 검증 증거](../testing/pi-analysis-llm-context-20261024.tdd.md)를 참고한다.

[2026-10-24 순차 배포·실제 모델·화면·보존 근거](../testing/pi-analysis-query-deployment-20261024.md).

최신 main `fb88ed9`와의 충돌 해소·로컬 재검증·PR 범위는 [2026-10-24 main 대조 기록](../testing/pi-analysis-main-pr-20261024.md)을 따른다. 이 후속 작업은 추가 배포를 포함하지 않는다.
