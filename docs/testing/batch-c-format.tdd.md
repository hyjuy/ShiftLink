# C 카드 양식 통일 검증 — 2026-10-01

사용자 요청: C의 검수표와 JSON을 A 양식에 맞춘다. 카드 본문·수치·출처·상태·등급·조건·MES 연결·재가동 payload는 보존한다.

검수표는 A의 항목 순서와 안전 표시를 적용했다. `안전 전제`를 `안전 근거`, `검색 조건`을 `조건`, `사람 판정`을 `판정`으로 통일하고 C의 사건·정책·프롬프트 추적 정보는 작성 노트에 유지했다. 이전 이름과 새 이름의 판정·근거를 카드별로 읽어 재생성 시 보존한다. JSON은 A의 공통 필드 순서를 따르고 C 추가 필드는 뒤에 보존했다.

| 단계 | 명령 / 검사 | 실제 결과 |
| --- | --- | --- |
| RED | `python -m pytest tests/test_batch_c_format.py -q` | 1 failed. 기존 C 제목·항목 이름이 A 양식 요구와 달랐다. 체크포인트 `5b97c7b`. |
| GREEN | `python -m coverage run --data-file=artifacts/batch-c-format.coverage --source=docs/data/knowledge_cards/kb/20260930-C -m pytest tests/test_batch_c_format.py tests/test_kb_cards.py -q` | 6 passed. 구·신 판정 보존, 재생성 일치, T2/T6·안전 카드 표기, 19장 출력 동기화·상태 보존 확인. |
| Coverage | `python -m coverage report --data-file=artifacts/batch-c-format.coverage --include='*/build_docs.py' --fail-under=80` | build_docs.py 98%. |
| 데이터 보존 | cards.json 및 out/*.json 6개를 Git HEAD의 JSON과 객체로 비교 | 모든 값 일치. 필드 순서만 변경. |

Python 3.12와 기존 .test-deps 환경에서 실행했다. 통합 accepted KB는 C 초안을 포함하지 않으며 이번 변경으로 승인하거나 편입하지 않는다. A 검수표는 과거 검수 기록으로 수정하지 않았다.
