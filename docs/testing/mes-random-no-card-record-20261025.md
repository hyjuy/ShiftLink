# 랜덤 모드의 카드 없는 직접 조치 기록 (2026-10-25 후속)

## 상태와 범위

앞선 [버튼·복구 연결](mes-random-mode-controls-20261025.md)을 보완한 후보이며 운영 미배포다. 사용자가 지식카드 없이도 직접 수행한 조치와 복구 결과를 남겨야 한다고 확인했다. 이를 현재 모의 사건 해제나 운영 재시작의 승인으로 해석하지 않았다. 원본/기존 평가 결과는 보존한다.

현재 PDA가 실제 쓰는 **근무일지 작성** 경로와 이전 **인계 저장** 경로를 구분해 검증했다. MES의 짧은 회복 확인을 장시간 정상 운전이나 지식카드 검수 완료로 바꾸지 않는다.

## 원인과 최소 변경

`pda.js:answerBody`가 인용 카드가 있을 때만 **조치 시작**을 표시했다. 카드 없는 현재 설비 답변에도 이 버튼을 표시하도록 조건 한 곳과 주석만 바꿨다. 설비가 없거나 다른 설비의 카드 없는 답변에는 새 진입을 허용하지 않고, 인사 응답과 기존 인용 카드 동작은 유지한다. 기존 btn/primary 디자인을 재사용한다.

흐름은 **조치 시작 → 다른 조치 입력/완료 → MES 연동의 모의 수리 완료 기록 → 재가동 (라인 복구 시작) → 결과 확인 → 근무일지 작성 → 저장**이다. 앞선 서버 수정이 카드 유무에 관계없이 동일한 MES 복구 단계를 제공한다. 직접 한 조치와 모의 수리/재가동 확인은 원래의 별도 필드와 원본 세션에 보존한다.

센서 수신·바인딩·질의 근거·장비 매핑·AI 모델·경보 병합·중복 억제·진동 코드는 바꾸지 않았다. 기존 운영의 PDA 파일도 아직 바꾸지 않았다.

## Raspberry Pi 검증

- 카드 없는 답변에서 조치 시작이 안 보이는 DOM assertion을 먼저 재현했다. `cardless-entry-red.log`와 RED 체크포인트 `99b3166`을 보존했다.
- **제어/기록/실제 Chromium 15/15 통과**, 0skip, 26.558초. 직접 조치·전후 센서·모의 복구 연결·결과 저장, 회복 안 된 시도의 미해결 저장, 실제 PDA `sessionRecord` 출력의 근무일지 저장을 확인했다. 근무일지에는 조치 내용·모의 복구 확인·source_session_id·복구 결과가 남고 `normal_run_status=unconfirmed` 및 candidate=false를 유지한다. 원본 세션의 before/after/steps/verdict도 유지한다.
- 인계 저장 경로에서는 카드 없는 성공 기록이 검수 대기 초안으로 남고, 실패 시도는 기록을 남기되 해결 초안을 만들지 않는 것을 별도로 확인했다. 이를 근무일지가 자동 게시되는 것으로 설명하지 않는다.
- **기존 MES DOM/Python 12/12 통과**. 이전 head232d48b의 전체 CI는 3156pass·20skip·2fail이었다. 두 실패는 새 버튼의 setAttribute를 기존 DOM 모형에 반영하지 않은 데서 났다. Pi에서도 같은 두 실패를 dom-red.log로 재현한 뒤 모형에 표준 메서드만 보완했다. 기존 기대값/초점/재시도 assertion을 유지하고 오프라인 aria-pressed=false 확인도 추가했다. 제품 코드에 테스트 전용 예외를 넣지 않았다.
- **PDA Node 회귀 7/7 통과**: sensor_display, network_boot, unity_pda_link, symptom_rank, mes_query_pda, resolution, 새 cardless_recovery. `node --check shiftlink/mes/web/pda.js`도 통과했다.
- `python scripts/check_knowledge_publication.py`: ok=true, errors=[], metadata_and_syntax. Pi 격리 Git index의 관련 Python 12파일도 검사했다. 이번 작업은 게시/검색/문맥 분류 변경이 아니며 history 의미 진단이나 실제 모델 품질을 인증한 것으로 표현하지 않는다.
- 테스트용 기존 venv에 프로젝트의 고정 의존성 PyYAML6.0.2를 보완하고, 별도 검증 폴더에만 Node ARM64 v22.16.0을 풀었다. 공식 배포 SHASUMS256과 archive SHA256 `eab80cb88f8fda1e65f5e8d0420c9809bdb320b03fd34976ab7161b6e703b910`을 확인했다. 운영 Python·시스템 패키지·서비스 환경은 바꾸지 않았다.

KB 파일 누락/YAML 미설치 환경 로그, 잘못 만든 단일 설비 일지 요청의 fixture 오류, 첫 브라우저 하니스 오류와 이후 결과를 모두 보존했다. 기존 결과를 새 후보의 성능 수치로 재사용하지 않는다. 앞선 실행 행 관측208/217은 그때의 progressive 모듈 관측이며 이번 PDA 한 조건의 분기 커버리지가 아니다.

집계·실제 검증 묶음의 바이트 해시는 [summary JSON](mes-random-no-card-record-20261025-summary.json)에 있다. Git LF 정규화와 구분한다. 비공개 원본 로그/소스/화면은 `/home/pi/shiftlink/analytics/validation/random-mode-control-20261025`에 보존한다.

## 운영 상태와 적용 조건

읽기 전용 최종 확인에서 기존 실행 `2ce4d5209feb46cbbf33f369c379474a`의 EQ-0004 AI 사건(첫 sequence372)이 sequence4829에도 같은 ID로 유지됐다. AI ready, 기존 active_alarms0, Pi PDA PID20812·분석 PID30896/NRestarts0를 보존했다. 운영에 제어 쓰기·고장 해제·파일 설치·서비스 재시작은 하지 않았다.

이번 전체 기능 적용은 Jetson의 MES 수정과 Pi의 PDA 정적 JS 변경이 필요하다. 현재 모의 사건을 임의로 지우지 않는다. 수리·회복 처리에 대한 별도 결정 또는 기존 사건의 종료를 확인하고, 원본 파일/unit/일관된 DB를 보존한 뒤 적용해야 한다. Pi는 JS 원본을 별도 보존하고 기존 PDA 서비스는 유지한다. 센서·AI 경보·분석 프로파일과 운영 DB를 덮어쓰지 않는다. 실패 시 정확히 변경한 파일만 복원하며 기존 DB를 과거 DB로 되돌리지 않는다.
