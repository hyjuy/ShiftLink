# PDA 회복 전 표시 유지 — 운영 r6 배포

2026-10-24 KST. 사용자 요청에 따라 Pi 운영에 적용했다. 원본 r5와 이전 평가·실험 결과를 보존했다. 기존 경보의 발생·확인·미확인 수·진동 규칙과 MES 센서 수신은 유지한다.

## 변경과 운영 상태

- 릴리스: `/home/pi/shiftlink/analytics/releases/active-advisory-v1-pda-20261024-r6`.
- 고정 생애주기 후보를 선택하는 `scripts.mes_causal_active_advisory`를 별도 systemd 진입점으로 사용한다. Timestral은 사용하지 않는다.
- 확정된 사건은 최초 ID·감지 시각을 유지한다. 유효한 정상 근거 32회 연속 확인 뒤 해제한다. 잠깐 정상·정지·재가동 워밍업·불량 측정을 회복으로 세지 않는다. 새 run·입력 누락·오래된 결과의 보호 조건을 유지한다.
- 수동·고장 정지는 `정지 전 감지`, 재가동 워밍업은 `회복 확인 중` 이력으로 표시한다. 정지 중 새 판단은 보류한다.
- AI는 기존 알람창에서 같은 설비 행에 합친 무음 참고 정보다. `operational_notifications=False`이며 새로운 진동 경로를 추가하지 않았다.
- 운영에서 교체한 기존 파일은 app reader·PDA JavaScript·분석 systemd unit 3개다. PDA main의 최신 질의 연결, HTML·CSS·센서·얼굴/CNN은 유지했다. 이전 릴리스도 그대로 보존했다.
- 상태는 `/var/lib/shiftlink-analytics-active-v1`로 분리했다. 기존 normal checkpoint와 글로벌 STOP `/var/lib/shiftlink-analytics/STOP`을 보존한다. 출력 `/run/shiftlink-analytics/latest.json`은 같다.
- 21:41 KST 적용 성공. worker PID20799, PDA backend PID20812로 기동했다. 공식 재시작은 키오스크도 다시 열므로 재로그인이 필요할 수 있다. 적용 직전 기존 경보·AI 항목은 모두 0건이었다.

## Raspberry Pi 검증

모든 실행 검증은 Pi에서 수행했다. PC는 파일·해시 대조와 Git 작업만 담당했다.

| 항목 | 결과와 범위 |
|---|---|
| 배포 전 Python 회귀 | 73개 통과, 실패·오류 0 |
| 배포 전 PDA JavaScript | 문법·필수 회귀 5개·AI 표시/진동 검사 통과 |
| 배포 후 실제 릴리스/운영 reader 직접 import | 19개 통과. 표시·생애주기·reader 검사이며 앞의 73개와 합산하지 않음 |
| 실제 Pi Chromium | 1개 통과. 운영 JS/기기 HTML을 별도 프로필에서 실행 |
| 회복 전 유지 | 30프레임을 넘는 활성 이력, 정지, 재시작, 워밍업·품질 보류 이력 유지, 회복 확인 뒤 제거 |
| 기존 경보와 결합 | 같은 설비 1행, 기존 확인·배지 유지. AI 갱신·정지·회복에 추가 진동 API 호출 0건. 기존 경보의 최초 진동 호출은 유지 |
| 운영 관측 | 101.725초, 같은 프레임 21/21에서 `ai_insights`를 제외한 Pi/Jetson 응답 동일. 불일치·오류 0 |
| 운영 서비스 | active/running, PID20799, NRestarts=0. 관측 종료 41.381°C, throttled=0x0 |
| 재접속 후 무결성 | 보호 대상 60파일 중 승인된 3파일만 변경, 나머지 57파일 불변. 릴리스 manifest 19파일 해시 일치 |
| 실제 제공 정적 파일 | `/static/pda.js`, `/pda.html` 응답과 운영 파일 SHA256 일치 |
| 분석 서비스 오류 로그 | 21:41:36 이후 journal err 항목 없음 |

운영 관측 당시 AI 항목·기존 경보는 0건이었다. 실제 MES 고장 주입·정지·기존 경보 확인 조작은 하지 않았다. 따라서 표시 유지와 중복 억제는 **운영에 설치된 코드의 Pi 격리 재생 및 동일 UI Chromium 검증**으로 입증한 범위다. 물리 진동은 측정하지 않았으며 `navigator.vibrate` 호출을 검사했다. 기존 경보가 켜진 상태의 키오스크 재시작은 미검증이다. 새 미사용 평가·실측 센서 탐지 성능·30분/얼굴/CNN 동시 부하를 이번에 다시 측정하지 않았다.

기존 표시 회귀의 448프레임에서 잠깐 정상 구간 중 이력 숨김 65회→0회, 최초 통지 sequence105와 회복 index312는 동일했다. 이는 기존 개발 자료 재생이며 새 탐지 성능이 아니다. 관측상 회복은 실제 수리 완료의 증명이 아니다.

## 보존·재현·복구

검증 경로: `/home/pi/shiftlink/analytics/validation/active-advisory-deploy-20261024`.

```sh
OPENBLAS_NUM_THREADS=1 python3 /home/pi/shiftlink/analytics/validation/active-advisory-deploy-20261024/post-deploy-final.py
python3 /home/pi/shiftlink/analytics/validation/active-advisory-deploy-20261024/browser-check.py
```

회귀가 사용한 기존 합성 자료와 SHA256를 `tests/fixtures/mes_causal_pi/`에 함께 보존해 Pi 전용 절대 경로가 없는 환경에서도 같은 입력을 사용한다. 기존 기대값을 완화하거나 검사를 건너뛰지 않았다.

복구 백업: `/home/pi/shiftlink/analytics/backups/20261024-214132`. 이전 r5 unit·PDA 파일과 원래 실행 인수를 보존했다. 아래는 필요할 때 실행할 복구 경로이며 이번에는 실행하지 않았다.

```sh
sudo -v
python3 -B /home/pi/shiftlink/analytics/releases/active-advisory-v1-pda-20261024-r6/deploy/analytics/apply_release.py --rollback /home/pi/shiftlink/analytics/backups/20261024-214132
```

최초 정적 파일 점검의 `/pda.js` 404는 점검 URL 오류였다. 실제 라우트 `/static/pda.js`로 해시를 확인했으며 서버를 변경하지 않았다. 최초 배포 후 줄 실행 집계는 검증용 복사본을 대상으로 삼아 0을 보고했다. 이후 실제 릴리스/운영 reader를 대상으로 수정해 97.7%/94.4% 줄 실행 관측을 확인했다. 이는 분기 커버리지와 다르다. 원래 로그도 보존했다.

## 남은 호환 범위

Jetson의 기존 `agent/pi_analysis.py:validate_context`는 질의 참고 사건의 나이를 30프레임으로 제한한다. 따라서 오래 유지된 PDA 표시가 LLM 질문 문맥에는 제외될 수 있다. 이번에는 PDA 표시와 기존 경보 보존 범위를 적용했고 Jetson 질의 검증 규칙을 변경하지 않았다. 화면 표시 유지와 장기 이력의 답변 활용을 동일하게 설명하지 않는다.

공개용 검증 집계는 `docs/testing/evidence/pda-active-advisory-deploy-20261024/public-summary.json`에 보존한다. 원본 운영 로그·스크린샷은 이번 PR에 추가하지 않는다. 전체 검증 로그와 재현 helper 보관본은 별도 로컬 output ZIP 및 Pi 검증 폴더에 둔다. 운영 체크포인트·개인 얼굴 자료·실제 Chromium 프로필은 공개 근거에 포함하지 않는다.

전체 근거 ZIP: `D:/obsd/Projects/ShiftLink/output/pda-active-deploy-20261024/deployment-evidence.zip`. SHA256 `c79b22068a2a1d75b578c76f6d126e6f22f18107b88231704cadad4737d614c5`. Pi ZIP CRC와 PC 전달 해시를 확인했다. 재접속 후 재검사도 Python 19개·Chromium 1개 통과, worker PID20799·NRestarts=0·AI ready를 다시 확인했다. 기존 로그의 원문 공백은 보존했다.
