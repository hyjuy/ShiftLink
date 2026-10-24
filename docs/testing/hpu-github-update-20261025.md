# HPU 작업 GitHub 통합 검증

작성일: 2026-10-25 (Asia/Seoul)

GitHub `hyjuy/ShiftLink`의 최신 main `a7acafd2`(PR #355 병합)를 기준으로
`codex/hpu-ontology-validation-20261025`를 준비했다.
기존 로컬 `codex/kg-viz`는 main과 20/139 커밋이 갈라져 있었으므로 그대로 main에 덮어쓰지 않았다.
이 대화의 HPU 작업 40개 커밋만 별도 관리 worktree에 cherry-pick했다.
Unity·영상·다른 센서 연구·로컬 계정 기능 등 기존 미커밋 변경은 원래 작업 트리에 보존했다.

## 공유 범위

- 설비 공통 사건 투영과 HPU 진입점, 별도 shadow 진단, 관리자 설명 API.
- 실제 인용 ticket·검수 판본·게시 상태·원 사건 원문을 검증하는 게시 지식 연결.
- 기본 off이며 서버 훅이 없는 관계 후보 비교 실험.
- 명시적 일지 분류·기간/날짜 조건 보류·일지 검색 범위 개선.
- judge의 불필요한 닫기 토큰 생성 생략과 누락 시 기존 예산 fallback.
- 비교 실험의 evidence 순환 제거·독립 사본 순차 해제·정리 비용 포함.
- 프로젝트 전용 `shiftlink-codebase` 스킬과 설계·기능 지도·측정 근거.

과거 실제 모델 결과는 [p95 분석](hpu-p95-20261025.md)의 당시 소스·합성 데이터·PC→Jetson 경계에 대한 값이다.
이번 GitHub 통합에서 실제 모델 측정을 다시 실행하거나 운영에 배포하지 않았다.
대표 p95 개선과 탐색 p95 악화가 함께 있으므로 일관된 운영 개선으로 해석하지 않는다.
실험 기본 off와 원문·게시 검증을 유지한다.

## 원본 커밋과 공개 커밋

[40개 커밋 대응표](hpu-github-source-map-20261025.json)에 원래/공개 번호를 모두 보존했다.
두 실제 모델 기준의 분류·S30h·judge·실험 소스 8개는 바이트 단위로 동일함을 확인했다.
과거 측정 보고서의 커밋 번호·질문·라벨·결과는 소급 변경하지 않았다.
opt-in 하니스는 등록된 원래 번호와 공개 번호를 같은 공개 소스로 해석하고 임의 참조는 거부한다.
재현 시 전체 Git 이력이 필요하다.

추가 RED/GREEN: `test_hpu_reference_aliases.py`의 미구현 함수 ImportError를 확인한 뒤
alias 해석을 구현했다. alias/요청 바이트 보존 검사는 3 passed (0.76s)였다.

## main 계정 계약 보존

첫 통합 회귀는 1486 passed / 28 setup errors (117.63s)였다.
원인은 로컬의 별도 계정 수정에 의존한 fixture가 `operator['token']`을 읽은 것이었다.
main은 작업자 로그인에 토큰 대신 작업자 정보만 반환한다.

main의 계정 구현은 수정하지 않았다. fixture는 실제 로그인 계약을 확인하고,
관리자 전용 API가 역할이 operator인 세션도 거절하는지 검사할 테스트 세션만 별도로 준비한다.
이 수정 후 설명 API·게시 연결·기존 계정 회귀는 29 passed (41.78s)였다.

## 통합 확인

- 게시 메타데이터·작업 트리와 staged Python 문법 검사: PASS.
- 엄격 분류 검사: `--history-scope full` 30/30, `--history-scope stability` 72/72.
- 변경 Python 파일의 Python 3.10 문법 검사: PASS.
- 관련 설계·가이드·구조 문서의 상대 링크 검사: PASS.
- 공유 대상의 개인 키/GitHub 토큰 패턴 검사: PASS. 로컬 DB·모델·인덱스·인증 정보는 공유하지 않는다.
- 최종 통합 회귀: **1515 passed (131.74s)**. HPU 투영/shadow/설명/게시/검색 실험,
  S30h·일지 의미·기존 게시·실제 브라우저·Pi 문맥·동일 질문 재사용·진행형 설비·계정을 함께 검증했다.

원래 작업 트리의 미커밋 코드를 검증한 결과를 이 공유본의 성공으로 취급하지 않는다.
이 worktree를 PYTHONPATH와 작업 디렉터리로 지정하고 기존 가상환경의 실행기만 재사용했다.
GitHub CI는 push/PR 후의 별도 결과이며 로컬 통과와 구분한다.
