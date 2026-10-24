# Pi 분석 → Jetson LLM 참고 문맥 연결: 로컬 TDD 근거

2026-10-24. 운영 미배포. 기준 `eea5b1101feeda74a68ad59f4a8debb3eb01b099`,
작업 브랜치 `codex/pi-analysis-llm-context`. 기존 장비 배포본을 검증한 작업 트리에서 이어서 구현했다.
공유 D: 작업 트리의 다른 수정·미추적 파일과 이전 보고서를 보존했다. 별도 계획 파일은 없으며 아래 사용자 동선에서 검증을 도출했다.

## 동선과 변경

작업자가 기존 PDA에서 질문하면 Pi 프록시가 그 순간의 분석 파일을 함께 보내고,
Jetson은 현재 MES 실행·설정·선택 장비·생성 시각·센서 입력 시각·순번을 검증한다.
유효한 결과만 S30h/하이브리드 LLM 프롬프트의 보조 문맥에 넣는다.
과거 원문 조회에는 넣지 않고 기존 검색·judge·인용·검토·승격은 그대로 유지한다.
분석 없는 질문·손상/오래된 파일도 기존 질의 경로로 계속 처리한다.
계약·배포 순서는 [가이드](../guides/pi-analysis-query-context.md)를 따른다.

실행 코드 6파일:

- `shiftlink/agent/pi_analysis.py`: 최대 16 KiB 읽기·전송, MES와 대조, 허용 필드만 구성, 참고 문맥 생성.
- `shiftlink/pda/__main__.py`: 기존 POST 질문에 분석을 붙인다. 기존 UI·다른 API·인증 헤더 전달은 유지한다.
- `shiftlink/mes/query.py`: 잠금 안에서 캡처한 MES와 분석을 검증하고 질의 당시 근거를 `query_context.pi_analysis`에 보존한다.
- `shiftlink/agent/router.py`: 내부 질의에 선택적 분석 문맥을 허용한다.
- `shiftlink/rag2/s30h.py`: 과거/다른 장비 조회를 제외한 생성 프롬프트에 참고 블록을 추가한다.
- `shiftlink/edge/ollama.py`: 하이브리드 답변 메시지에도 같은 블록을 추가한다.

새 테스트 1파일과 게시 하니스의 트리거·실행 목록, 관련 구조/가이드/기능 지도만 함께 갱신했다.
새 패키지·환경 변수·서비스·DB 테이블·UI 컴포넌트·모델 설정은 추가하지 않았다.

## RED / GREEN

- RED 명령: `.venv/Scripts/python.exe -X utf8 -B -m pytest tests/test_pi_analysis_query.py::test_service_passes_analysis_with_original_question_and_sensor_data -q`
- 실제 결과: `1 failed`, `ValueError: query body must contain question and optional equipment_id, scan_id, k, incident_id`.
  분석 필드가 기존 API에서 거절되어 LLM에 도달하지 않는 의도한 실패였다.
- RED 체크포인트: `de303dfb30c9bf1b515a14836f83beec35459a60`.
- GREEN: 같은 작업 브랜치에서 최소 연결을 구현하고 최종 새 테스트 모듈을 실행했다. `72 passed in 32.87s`, exit 0.
- 중간 테스트 2건은 실제 카탈로그 신호명이 `hpu_pressure`인데 fixture에서 `pressure`를 쓴 오류였다.
  실제 스키마에 맞게 fixture를 고쳤고 신호 허용 목록을 완화하지 않았다.
- 손상된 선택 파일·비표준 JSON·과도한 중첩은 질문을 중단하지 않도록 검사했다.

## 보장과 실행 결과

| 보장 | 실제 검증 | 결과 |
|---|---|---|
| 최신 생성 시각과 MES 입력 시각을 구분하고 같은 실행·설정·0~3틱 지연만 수락 | `tests/test_pi_analysis_query.py` 경계값·입력 손상 검사 | 통과 |
| 선택 장비의 허용 신호만 전달하며 최근/정지 전/비활성 상태 구분 | 같은 모듈의 장비·상태·정지 시각 검사 | 통과 |
| 질문과 센서·카드를 유지하면서 S30h confident/model/mes_only 및 하이브리드 메시지에 참고 문맥 전달 | 같은 모듈의 프롬프트 검사 | 통과 |
| 실제 HTTP 프록시→MES 서비스→모델 fixture, 파일 갱신·소실·브라우저 제공 값 제거 | 같은 모듈의 localhost 임시 서버 검사 | 통과 |
| judge 거절·검토→게시→반려 경계를 우회하지 않음 | 같은 모듈 + 기존 게시/지식카드 회귀 | 통과 |
| 과거 카드·일지·이전 저장 답변·현재/미래 모델 전달 유지 | Pi 문맥을 넣은 기존 908개 질문의 실제 서비스 검사 | 908/908, 과거 418·현재/미래 490 |
| 운영 설정·UI·게시·저장·온톨로지·이력 함수 원본 보존 | 기준 커밋과 보호 경로 `git diff --exit-code` | exit 0 |

회귀 명령의 전체 argv/cwd/종료코드는 로컬 증거의 `regression-suite.json`, `new-suite-final.json`,
`additional-gates.json`, `strict-gates.json`에 보존했다.

- 관련 31개 테스트 파일: **1717 passed, 1 skipped**, exit 0, pytest 191.57초.
  이 실행에는 당시 새 연결 71건과 기존 게시·PDA·온톨로지·원래 908개 서비스 질문 검사가 포함된다.
- 이후 추가한 Pi 문맥 동반 908개 서비스 검사 및 임시 경로 보정 후 새 모듈 최종 실행: **72 passed**, exit 0.
  두 실행의 겹치는 테스트를 합산하지 않는다.
- 추가 인증·MES 예열·PDA 센서 정합 검사 3파일: **8 passed**, exit 0.
- 실제 로컬 Chrome을 사용하는 게시 흐름과 그래프 UI 회귀도 위 회귀에 포함되어 통과했다.
  건너뛴 1건은 `test_mes_causal_pda_browser.py`의 Pi 전용 `chromium` 명령 검사다.
  Windows 로컬에 그 실행 파일이 없어 `Pi Chromium is required`로 건너뛰었다. 실제 Pi 화면 재검증은 하지 않았다.
- `node tests/mes_query_pda.cjs`, `node tests/pda_sensor_display.cjs`: 모두 exit 0.
- `check_knowledge_publication.py`의 metadata 및 full/integration/reaudit/postaudit/stability/closure: 모두 exit 0.
  분류만 검사하는 프로필 성공과 위 실제 서비스·저장 검사 성공을 구분한다.

## 커버리지와 제한

분기 포함 coverage로 새 모듈은 **98%**(실행문 85/85, 분기 37/40)다.
변경된 실행 코드 6파일 전체의 합산 커버리지도 80% 하한을 통과했다. 상세 분모와 미검증 경로는
`coverage-six.json`과 `coverage-new.json`에 남겼다. 기존 키오스크 실행·얼굴/촬영·일부 예외 경로 등은 이 수치에 남는다.
커버리지는 결함 탐지 정확도나 LLM 답변 정확도가 아니다.

모든 새 연결 검증은 별도 SQLite·임시 분석 파일·로컬 HTTP 서버·모델/임베딩 fixture를 사용했다.
운영 DB·카드·인덱스·계정·분석기 프로필을 변경하거나 Pi/Jetson 서비스를 실행·재시작·배포하지 않았다.
직접 MES API 입력의 발신자 암호학적 인증, 실제 모델의 답변 품질, 실제 장비의 물리 결함 탐지는 이번 범위에서 검증하지 않았다.

로컬 증거: `artifacts/pi-analysis-llm-context-20261024/`.

## 배포 직전 최신 Pi r5 호환 대조

장비 읽기 전용 대조에서 Pi 분석기가 `normal-context-v1-pda-20261024-r5-manual-stop`으로 바뀐 것을 확인했다.
기존 연결 검증기가 수동 정지/일시정지의 정지 전 기록을 누락하는 3유형을 재현했다(RED `a40ae5a`).
라인이 running/ready인 동안 개별 장비가 stopped인 r5 결과도 추가 재현했다(RED `2f71a6a`).
Pi 분석기와 UI를 변경하지 않고 `agent/pi_analysis.py`의 before_stop 허용 경계만 r5의 기존 유지 조건에 맞췄다.
시각·실행·설정·순번·최근성 검사는 유지하며 수동 정지를 고장으로 바꾸지 않는다.
`python -m pytest tests/test_pi_analysis_query.py tests/test_pda_app.py tests/test_pda_advisory_reader.py tests/test_pda_fault_stop.py -q`: **100 passed in 35.01s**.
이 실행은 기존 908질문 서비스 검사도 포함한다. 장비 배포 결과는 별도 배포 기록에 남긴다.
