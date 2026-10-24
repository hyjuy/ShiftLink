# 최신 main과 Jetson 온톨로지 로컬 통합 검증

기준일: 2026-10-24. 기준 main: `99c334d832195c1d800fbf8fad63e33023f235c5`.
브랜치: `codex/ontology-main-integration`. 운영 미배포. 별도 계획 파일 대신 이번 사용자 요청과 실제 장비 소스 비교에서 검증할 흐름을 정했다.

## 변경과 보존 범위

실행 코드는 `mes/publication.py`, `mes/query.py`, `rag/graph_explain.py`, `rag/knowledge_graph.py`, `rag2/s30h.py`의 5파일만 변경한다(`shiftlink/` 기준). Jetson에서 읽어 해시를 확인한 온톨로지 변경분을 main에 통합했다. `rag2/field_history.py`는 main과 바이트 단위로 같다. Pi가 PDA, Jetson이 MES인 역할을 유지하며 Jetson의 구형 PDA/UI 사본은 가져오지 않았다.

검증은 로컬 임시 SQLite, 인덱스, 계정과 결정적 임베딩·judge·생성 fixture를 사용한다. HTTP/브라우저 서버는 loopback만 사용한다. 운영 장비 연결, 데이터 접근, 배포, 서비스 재시작, 모델 다운로드를 하지 않았다. 모델 fixture 결과는 실제 LLM 품질·검색 정확도·운영 지연의 측정값이 아니다.

## 사용자 흐름과 보장

| 흐름 | 검증 계약 | 검사 |
|---|---|---|
| 질문→관계 검색→답변 | 같은 분류/문서 판본의 이웃 최대 2개, 기존 예산·judge 유지 | `test_knowledge_graph_runtime.py` |
| 일지→검수→게시→검색→반려 | 검증된 동일 자산/판본 snapshot만 연결, 반려 후 제외, 기존 답변 보존 | `test_publication_ontology_integration.py` |
| 관계 검색으로 추가된 과거 카드 조회 | 전체 원문·137분·시각·작업자 보존, 생성 호출 없음 | `test_graph_neighbor_preserves_main_history_and_current_contracts` |
| 관계 검색으로 추가된 카드로 현재 요청 | 원 질문 전체와 MES를 모델에 전달 | 같은 매개변수 검사 |
| 37분 요청과 137분 기록 | 부분문자열 오선택 거부 | 같은 매개변수 검사 |
| main의 이력·현재/미래 경계 | 기존 오라클을 변경하지 않고 각 계약 독립 유지 | `test_field_history_integration.py`, 엄격 의미 검사 6프로필 |
| Pi PDA·센서·AI 분석 | 소스 해시 보존 및 관련 회귀 검사 | `integrity.json`, Node·Python 검사 |

## TDD 근거

- RED 체크포인트 `22bf6256e3723ef1692e9d905b0cf08e2c0556e1`: main에서 두 표적 검사가 실패했다. 원인은 없는 `knowledge_graph` 모듈과 `explain`의 없는 `published_card_ids` 인자다. `red-command.json`, `red.log`에 명령·종료코드 1을 보존했다.
- GREEN 체크포인트 `194a177d044187a58f441a3522ff01c27d2130ec`: `python -m pytest -q tests/test_knowledge_graph_runtime.py tests/test_publication_ontology_integration.py`의 전체 43검사가 통과했다. 종료코드 0. `graph-green.xml`, `graph-green-command.json`, `graph-green.log`에 근거가 있다.
- staged Python 구문을 포함한 `python scripts/check_knowledge_publication.py`도 통과했다. 이는 의미 검사와 별개의 메타데이터/구문 검사다.

## 최종 회귀 결과

- `suite-command.json`에 기록한 32파일 pytest+branch coverage: **1703 passed, 실패/오류/skip 0**, 345.46초. `suite.xml`, `suite.log`에 전체 결과가 있다.
- 실제 게시 서비스의 질문 908건: **908/908 계약 통과**(과거 원문 418/418, 현재·미래 판단 490/490). 고정 283개 비교군도 과거 125/125·현재 158/158을 각각 통과했다. 기존 main 요청 보존 표식 267건 및 기존 로컬 원문 보존 표식 95건도 각각 통과했다. 실제 고유 질문은 908개다. 결함 발견용 유한 표본이므로 운영 전체 정확도로 해석하지 않는다. `suite-temp`의 `integration-observations.json`에 개별 경로·모델 호출·원문·보존 상태를 남겼다.
- 엄격 분류 진단 `full`, `integration`, `reaudit`, `postaudit`, `stability`, `closure`: 모두 exit 0. 개별 보고서는 `history-*.json`.
- Node `mes_query_pda`, `pda_graph_explain`, `pda_sensor_display`, `pda_report_sensor_context`, `pda_report_form`, `pda_report_save_success`: 6개 모두 exit 0.
- 합산 분기 포함 coverage **92%**. 모듈별 표시: publication 87%, query 72%, s30h 96%, graph_explain 99%, knowledge_graph 95%. `coverage-report.log`, `coverage.json` 참조. query의 미실행 일반 분기는 합산 수치와 별도로 남겨 둔다.
- 보호 대상 62파일 불변, `field_history.py`는 main과 바이트 동일. 실행 코드 변경은 지정한 5파일뿐이다. `integrity.json` 참조.
- 브라우저 검사는 실제 로컬 Chrome과 loopback MES를 사용했으며, 임베딩·judge·생성은 fixture다. 새 그래프 브라우저 검사는 기존 테스트처럼 `SHIFTLINK_BROWSER_CHANNEL`과 선택적 Playwright 설치를 따른다. 이 로컬 실행에서는 Playwright가 설치돼 실제 실행했고 skip은 없다. 임시 응답 파일도 pytest 임시 디렉터리에만 저장한다.
- 최종 테스트 이식성 조정 후 같은 그래프/게시 묶음을 재실행해 **43 passed, skip 0**, 20.45초를 확인했다(`final-graph.xml`, `final-graph.log`). 실행 코드 5파일은 포괄 회귀 검사 이후 변경하지 않았다.
- 새 그래프/게시 테스트를 publication CI 실행 목록과 경로 트리거에 추가했다. 원격 CI 자체는 실행하지 않았다.

## 재현 자료

로컬 증거 디렉터리: `artifacts/ontology-main-integration-20261024/` (원래 작업 공간의 산출물 경로). `baseline.json`, `integrity.json`, `additional-checks.json`, `history-*.json`, `suite-command.json`, `suite.xml`, `coverage.json`을 함께 확인한다. 테스트 질문·기대값·기존 보고서는 삭제하거나 재분류하지 않았다. 이 브랜치는 push·PR·운영 배포를 하지 않았다.
