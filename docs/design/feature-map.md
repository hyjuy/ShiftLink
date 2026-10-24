# 기능 지도

2026-10-24 로컬 후속 작업의 탐색 인덱스다. 기준 커밋은 `eea5b1101feeda74a68ad59f4a8debb3eb01b099`이며
운영 미배포 변경을 포함한다. 저장소 전체 지도와 장비 현재 상태는 이 한 행만으로 확정하지 않는다.

| 사용자 목적 | 호출 경로와 코드 근거 | 저장 경계 | 검증과 확인 수준 |
|---|---|---|---|
| Pi 분석을 현재 센서·지식카드와 함께 질문에 참고 | PDA 기존 UI → `pda/__main__.py:make_handler` → `agent/pi_analysis.py:attach_to_query` → `mes/query.py:query_service` / `validate_context` → `rag2/s30h.py:run` 또는 `edge/ollama.py:build_messages` | 질의 당시 `query_context.pi_analysis`만 추가. 기존 일지·후보·게시·KG·센서는 유지 | `tests/test_pi_analysis_query.py`, 기존 이력·게시·PDA 회귀. 로컬 fixture 검증이며 실제 모델·장비 재배포 확인과 구분 |

[입력 계약·실패 처리·배포 순서](../guides/pi-analysis-query-context.md)와
[최종 검증 증거](../testing/pi-analysis-llm-context-20261024.tdd.md)를 참고한다.
