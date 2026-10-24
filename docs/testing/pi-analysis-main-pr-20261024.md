# Pi 분석·Jetson LLM 연결의 최신 main 대조와 PR 검증

2026-10-24 (Asia/Seoul). 로컬 격리 재검증이며 이번 작업에서는 추가 배포·장비 접속·운영 데이터 변경을 하지 않았다.

## 비교 기준과 충돌

- 최신 원격 main: `fb88ed9aea184169384dcfb38643c6d2a839662e`, PR #351 머지, 2026-10-24T18:57:58+09:00. 검증 전후 `git fetch --no-tags origin main`으로 같은 SHA를 확인했다.
- 기존 연결·배포 증거 기준: `035798082fba52a3de044b99ab646f82cf2ebcc8`. 실행 코드 배포 기준은 `0ee6d51230e7ab9ea6448a9cd681496b9f12bd82`다.
- 원래 브랜치 `codex/pi-analysis-llm-context`는 보존하고, `codex/pi-analysis-main-pr`에서 main을 병합했다. 기존 D 드라이브 작업 트리의 소스 변경과 미추적 자료를 PR에 섞지 않았다.
- `git merge-tree --write-tree`와 실제 병합에서 실행 코드 충돌은 없었다. 유일한 충돌은 `docs/design/project-structure.md`의 같은 위치에 추가한 설명이었다. main의 Pi 정상 기준·보정 설명과 이번 질문 연결 설명을 모두 유지했다.

## PR 범위와 선행 온톨로지 보존

main에는 이미 배포·검증한 온톨로지 통합 `eea5b1101feeda74a68ad59f4a8debb3eb01b099`가 아직 없었다. 이 기능을 제거하거나 연결 코드와 분리해 누락시키지 않도록 기존 통합본을 선행 변경으로 함께 포함한다. 이번 main 통합에서 온톨로지 로직을 추가 수정하지 않았다.

| 구분 | 실행 코드 |
|---|---|
| 이번 연결 6파일 | `agent/pi_analysis.py`, `agent/router.py`, `edge/ollama.py`, `mes/query.py`, `pda/__main__.py`, `rag2/s30h.py` |
| 기존 온톨로지 보존 5파일 | `mes/publication.py`, `mes/query.py`, `rag/graph_explain.py`, `rag/knowledge_graph.py`, `rag2/s30h.py` |

경로는 모두 `shiftlink/` 아래다. `query.py`와 `s30h.py`가 겹치므로 고유 실행 파일은 9개다. 세 테스트 모듈과 게시 CI 실행·트리거, 계약·구조·과거 검증·배포 기록도 포함한다.

`git diff --exit-code 03579808 -- <9 실행 파일>`은 exit 0이다. main 통합을 위해 기존 검증·배포 코드를 덮어쓰거나 새 기능을 추가하지 않았다.

## 이번 격리 재검증

- 관련 37개 파일: **1767 passed**, 실패 0, 오류 0, skip 0. pytest 263.04초, 명령 전체 실행 265.39초, exit 0.
- Pi 문맥을 함께 넣은 고정 서비스 질문: **908/908**. 과거 원문 보존 418개와 현재·미래 원질문·MES 모델 전달 490개를 각각 통과했다. 카드·근무일지·이전 답변·새 저장 답변 보존도 같은 서비스 하니스에서 검사했다. 이 질문 수를 pytest 테스트 수에 다시 합산하지 않는다.
- 새 연결 모듈 80개 테스트를 포함한다. 시간·실행·설정·선택 장비·분석 지연, 파일 갱신/소실, HTTP 프록시, 임의 설명 배제, judge 거절, 게시·검색·반려, r5 수동 정지 경계를 검사했다.
- main의 정상 문맥·분석 서비스·배포 도구·수동 정지 회귀와 기존 PDA·센서·온톨로지·S30h·Ollama 경로를 함께 검사했다.
- 로컬 실제 Chrome에서 게시 흐름과 기존 그래프 PDA 화면 2개 depth 검사를 통과했다. 운영 Pi 화면이나 실제 LLM을 이번 작업에서 다시 실행한 결과는 아니다.
- 게시 무결성 기본 검사 및 `--history-scope full/integration/reaudit/postaudit/stability/closure`: 모두 exit 0.
- `node tests/mes_query_pda.cjs`, `node tests/pda_sensor_display.cjs`, `node tests/pda_graph_explain.cjs`: 모두 exit 0.

## 보존 확인과 제한

main의 UI, `pda/ai_insights.py`, 분석기·정상 프로필·배포 설정, 이력 판정 `field_history.py`, 저장·서버·엔진, 얼굴·설비 인식, 데이터·DB 관련 추적 경로는 `git diff --exit-code origin/main -- ...`에서 모두 동일하다. 원래 기준 `99c334d` 이후 main에 추가·변경된 파일도 구조 설명 문서를 제외하고 전부 main과 동일하다. 충돌 표시와 `git diff --check` 오류는 없다.

이번 검증은 임시 SQLite·분석 파일·로컬 HTTP·모델/임베딩 fixture만 사용했다. 운영 데이터·온톨로지 파일·모델 설정·Pi/Jetson 서비스를 변경하지 않았다. 실제 모델·Pi 화면·데이터 보존의 직전 배포 결과는 [별도 시점의 배포 기록](pi-analysis-query-deployment-20261024.md)으로 구분한다. 이번 검증에서 전체 저장소 테스트나 물리 장비의 결함 탐지 정확도를 측정한 것은 아니다.

재현 자료는 로컬 `artifacts/pi-analysis-main-pr-20261024/`의 `regression.json`, `regression.log`, `pytest.xml`, `gates.json`, `integrity.json`, 임시 서비스의 질문별 보존 결과다. 원본 하니스 오라클·과거 보고서·장비별 배포 증거는 변경하지 않았다.

후속 fetch의 객체·참조 수신 뒤 선택적 commit-graph 유지보수에서 임시 파일 rename 오류가 발생했다. 자동 유지보수와 commit-graph 쓰기를 해당 명령에서만 끈 fetch를 재실행해 성공했고 원격 main SHA가 같음을 재확인했다. 저장소 설정이나 commit-graph 파일을 수정·삭제하지 않았다.
