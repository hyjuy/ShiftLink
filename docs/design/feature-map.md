# 기능 지도

2026-10-24 로컬 후속 작업의 탐색 인덱스다. 기준 커밋은 `eea5b1101feeda74a68ad59f4a8debb3eb01b099`이며
후속 승인 배포와 격리 실제 모델·Pi 화면 검증 기록을 포함한다. 저장소 전체 지도와 장비 현재 상태는 이 한 행만으로 확정하지 않는다.

| 사용자 목적 | 호출 경로와 코드 근거 | 저장 경계 | 검증과 확인 수준 |
|---|---|---|---|
| Pi 분석을 현재 센서·지식카드와 함께 질문에 참고 | PDA 기존 UI → `pda/__main__.py:make_handler` → `agent/pi_analysis.py:attach_to_query` → `mes/query.py:query_service` / `validate_context` → `rag2/s30h.py:run` 또는 `edge/ollama.py:build_messages` | 질의 당시 `query_context.pi_analysis`만 추가. 기존 일지·후보·게시·KG·센서는 유지 | `tests/test_pi_analysis_query.py`, 기존 이력·게시·PDA 회귀. 로컬 fixture 이후 2026-10-24 Jetson 5파일→Pi 2파일 순차 배포, 실제 LLM·Pi 실제 UI로 격리 재검증. 분석기는 r5 유지, 기존 업무 14테이블 1054행 보존 |

[입력 계약·실패 처리·배포 순서](../guides/pi-analysis-query-context.md)와
[최종 검증 증거](../testing/pi-analysis-llm-context-20261024.tdd.md)를 참고한다.

[2026-10-24 순차 배포·실제 모델·화면·보존 근거](../testing/pi-analysis-query-deployment-20261024.md).

최신 main `fb88ed9`와의 충돌 해소·로컬 재검증·PR 범위는 [2026-10-24 main 대조 기록](../testing/pi-analysis-main-pr-20261024.md)을 따른다. 이 후속 작업은 추가 배포를 포함하지 않는다.
