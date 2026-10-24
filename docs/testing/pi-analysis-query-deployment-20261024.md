# Pi 분석 → Jetson LLM 연결의 순차 배포와 실제 검증

2026-10-24 (Asia/Seoul). 사용자 승인으로 운영 배포했다.
실행 코드 기준은 `0ee6d51230e7ab9ea6448a9cd681496b9f12bd82`, 로컬 브랜치는 `codex/pi-analysis-llm-context`다.
기존 로컬 검증 보고서는 당시의 미배포 기록으로 보존한다.

## 적용 결과

| 대상 | 적용 파일 수 | 정상 응답 시각 KST | 정지→정상 응답 |
|---|---:|---|---:|
| Jetson MES | 5 | 2026-10-24 19:15:48 | 1.35초 |
| Pi PDA 프록시 | 2 | 2026-10-24 19:16:39 | 3.42초 |

Jetson: `agent/pi_analysis.py`, `agent/router.py`, `edge/ollama.py`, `mes/query.py`, `rag2/s30h.py`.
Pi: `agent/pi_analysis.py`, `pda/__main__.py`. 모두 `shiftlink/` 아래 경로다. 공용 모듈을 제외한 고유 실행 파일은 6개다.
Jetson 적용·정상 응답 확인 이후에만 Pi 프록시를 적용했다. 운영 환경 변수·모델 선택·서비스 설정·정적 KB/인덱스·UI는 변경하지 않았다.
Jetson MES 재기동으로 새 실행 ID가 생성됐고, 기존 실행과 센서 기록을 보존한 채 이전 running 상태를 복구했다.
Pi 분석 서비스는 재시작하지 않았으며 PID 7066과 r5의 프로필·설정·명령이 유지됐다.

## 최신 Pi 차이와 보완

배포 전 Pi가 `normal-context-v1-pda-20261024-r5-manual-stop`으로 갱신된 것을 발견했다.
기존 연결 검증기는 고장 정지 전 기록만 허용하여 수동 일시정지·정지·개별 장비 정지를 누락했다.
실패 3유형과 running/ready 상태에서의 개별 장비 정지 사례를 테스트로 고정하고,
새 공용 연결 검증기만 r5의 기존 유지 계약에 맞췄다. 분석기·UI는 덮어쓰지 않았다.
시각·실행·설정·순번·최근성 검사를 유지하며 `before_stop`을 활성 고장으로 바꾸지 않는다.
관련 로컬 4모듈은 **100 passed in 35.01s**이며 기존 908개 서비스 질문 검사도 포함한다.

## 실제 LLM과 실제 Pi 화면

- 실제 답변 모델 `exaone-rag-mes-ck176`, 실제 judge `exaone-sft-judge`를 그대로 사용했다.
- 배포 전 복사본과 배포 후 실제 소스에서 각각 검증했다. 생성 프롬프트의 Pi 참고 블록·현재 MES·실제 검색 근거 XML source 태그를 확인했다.
- Pi에 배포돼 있던 `shiftlink/mes/web/` 파일을 그대로 별도 프록시에서 제공했다. 운영 UI와 다른 디자인을 만들지 않았다.
- Pi 물리 Chromium에서 설비 목록 → HPU-01 선택 → 기존 질문 입력 → 보내기를 실행했다.
  현재 센서, K-1004 기반 답변, 관련 지식 연결·매뉴얼 영역이 표시되는 것을 확인했다.
- 질의 ID `Q-57443be5b69e425ba0413549c6532742`, route confident, knowledge_status answered, graph status ok.
- Pi 결과는 ready, 선택 장비 EQ-0001, 같은 실행·설정, 센서보다 1틱 전 분석이었다. 분석 생성/입력/질의 시각과 현재 운전 상태가 함께 저장됐다.
- 테스트 로그인 상태는 별도 브라우저 프로필의 합성 작업자 fixture다. 운영 계정·인증·안면 인식은 우회하거나 재검증하지 않았다.

운영 DB에 테스트 질문이 남지 않도록 Jetson의 별도 SQLite와 현재 센서의 읽기 전용 미러를 사용했다.
Pi는 실제 `latest.json`을 읽었고 실제 LLM을 호출했다. 합성 테스트 카드는 만들지 않았다.
테스트 종료 후 별도 서버·프로필의 브라우저·CDP 포트를 닫았고 원래 운영 로그인 화면 복귀를 물리 화면 캡처로 확인했다.

## 보존·격리 검사

- 기존 업무 14테이블의 **1054행**을 PK와 전체 행 해시로 대조: 누락 0, 변경 0.
  운영 query_log는 **552→552**, 카드 초안 **5→5**, 게시 카드 **1→1**이다.
- 백업에 있던 센서 기록 키 보존: runs 97개, snapshots 155659개, runtime_events 22945개, ground_truth 0개 모두 누락 0.
  센서 전체 payload의 바이트 비교를 주장하지 않는다.
- 양쪽의 배포 파일 해시는 manifest와 일치하고, 허용한 대상 이외의 기존 소스·UI·정적 데이터/검색 인덱스·분석 배포본 해시는 일치한다.
- 계정 파일과 모델·온톨로지·센서 관련 실행 설정도 일치한다.
- 격리 DB의 질의 ID **3개 모두 운영 query_log에서 0건**이다. 격리 초안도 0건이며 uploader를 실행하지 않았다.
- 최종 Pi 상태 5회: Jetson 센서 필드 5/5 일치, 분석 ready 5/5, 실행·설정 5/5 일치, 지연 1~2틱.

## 백업·중간 오류·제한

백업은 각 장비 `/home/<사용자>/shiftlink/backups/pi-analysis-query-20261024-r5`에 보존했다.
Jetson은 전체 SQLite와 원래/후보 실행 파일, Pi는 원래/후보 실행 파일과 manifest를 보관한다.
전체 DB 백업은 `PRAGMA quick_check=ok`로 확인했으며 운영 DB를 교체하지 않았다.

초기 백업은 읽기 시점을 고정하지 않아 실시간 쓰기 중 재진행될 수 있었고 배포 전에 중단해 고정 스냅샷으로 다시 완료했다.
백업·재시작 구간에 Pi 분석 오류 5건(타임아웃/연결 끊김)이 기록됐지만 자동 복구했고 최종 최근 5분 오류는 0건이다.
위 1.35/3.42초는 서비스 재시작 구간이며 백업 중 지연을 포함한 무중단 시간 수치가 아니다.

격리 도구의 중복 run 등록과 프롬프트 source 표기 감지 오류도 발견해 도구만 수정하고 실제 모델 검사를 다시 실행했다.
CLI 브라우저 도구를 사용할 수 없어 Chromium CDP로 실제 Pi를 제어했다. 초기 별도 프로필의 연결 문제는 운영 코드 결함으로 계산하지 않았다.

현재 실제 분석 결과 items는 0개였다. 실제 결과 전달·현재 상태 구분·모델 입력과 답변 표시를 확인했으며 물리 결함 탐지 정확도를 인증하지 않는다.
운영 설비에 고장·수동 정지를 주입하지 않았다. 수동 정지 유지 경계는 로컬 격리 fixture로 검사했다.

증거는 `artifacts/pi-analysis-llm-deploy-20261024/`의 `report.json`, host별 preservation/cleanup JSON,
`jetson-verification-deployed.json`, `deployed-gate.json`, 실제 화면 `physical-final.png`, 복귀 화면 `physical-restored.png`에 보존한다.
Pi의 `pi-bootstrap-verification-*`는 격리 backend URL 전달용 초기 사본이며 실제 모델 결과 원자료는 `jetson-verification-*`다.
