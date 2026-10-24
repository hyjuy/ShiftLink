# 랜덤 버튼·카드 없는 복구 기록 운영 적용 (2026-10-25)

사용자의 **운영에 적용** 승인에 따라 검증 소스 `77af5ac10e6909acc463d984615ddf84c4d34450`을 Jetson MES와 Raspberry Pi PDA에 적용했다. [배포 전 검증](mes-random-no-card-record-20261025.md)은 당시 미배포 기록으로 그대로 보존한다. 이번 적용과 확인값은 [요약 JSON](mes-random-controls-deployment-20261025-summary.json)에 있다.

## 적용 결과

- MES의 **시작/재개**는 기존 일반 운전이며 **랜덤 모드** 버튼을 눌러야 점진 고장을 생성한다. 최종 상태는 `standard`, `running`으로 두었다. 랜덤 모드 재활성화는 작업자가 버튼으로 선택한다.
- 카드 유무와 관계없이 **조치 시작 → 다른 조치 입력 → 모의 수리 완료 기록 → 재가동 → 결과 확인 → 근무일지 작성**을 사용할 수 있다. 사용자 조치·원본 세션·전후 센서·실패 결과를 보존하며, 짧은 회복 확인을 장시간 정상 운전이나 카드 게시 승인으로 바꾸지 않는다.
- Jetson은 검증 manifest의 MES 6파일만 교체했다. `shiftlink-mes.service`만 재시작하고 기존 unit/drop-in, DB, 업로더와 추론 서비스는 유지했다. MES PID45593→69298, NRestarts0. 업로더1145·Ollama1049·judge1050은 그대로다.
- Pi는 `shiftlink/mes/web/pda.js` 한 파일만 교체했다. PDA/얼굴/CNN 프로세스20812와 분석 프로세스30896/NRestarts0를 유지했다. HTML·PDA 백엔드·ai_insights.py·분석 모델/프로파일·경보 병합·진동 코드는 바꾸지 않았다. 실제 `/static/pda.js` 응답 SHA256이 후보와 일치하고 Cache-Control은 no-store다.
- 열린 물리 키오스크의 화면 재로딩은 직접 확인하지 않았다. 새 코드 사용에는 PDA 화면 새로고침이 필요하다. 물리 진동도 직접 측정하지 않았다. 별도 Pi Chromium의 실제 운영 MES 버튼 검증과 DOM 진동 호출 검증을 구분한다.

## 기존 사건 보존과 회복

기존 실행 `2ce4d5209feb46cbbf33f369c379474a`의 EQ-0004 사건을 재시작으로 없애지 않았다. 비공개 원본에서 실제 지속 모의 고장임을 확인하고, 승인된 배포 유지보수의 일부로 일시정지·해당 설비 모의 수리·재개를 수행했다. 실제 장비 수리로 기록하지 않는다.

sequence6271 직후 모의 수리를 수행하고 sequence6272의 `synthetic_repair_recorded` 1건이 기존 runtime_events에 저장됐음을 확인했다. AI 상태/체크포인트를 삭제하지 않고 45.58초 관측 후 sequence6316에서 ready·사건 없음이 3개 연속 새 프레임으로 확인됐다. 이는 이번 사건의 회복 관측 시간이며 탐지 p95가 아니다.

원본 SQLite는 수리 전에 읽기 트랜잭션을 고정한 일관된 백업으로 보존했다. 크기2,946,883,584바이트, quick_check=ok, 해당 실행6,103프레임이다. 배포 직전까지의 최종6,323프레임 및 모든 기존 테이블의 행 수가 감소하지 않았음을 확인했다. 새 프로세스의 실행은 `6c99af654a5440e1ba2616def2d26f29`이며, 이전 실행을 그대로 이어간 것으로 설명하지 않는다. 구성 ID와69채널은 동일하다.

## Raspberry Pi 검증

수동 실행 검사는 모두 Pi에서 수행했다. 별도 후보에서 실제 기록 저장을 검증하고, 운영에는 가짜 작업자 일지/지식카드를 만들지 않았다.

| 확인 | 결과 |
|---|---|
| 배포 직전 제어·카드 없는 조치/기록·실제 Chromium 회귀 | 15/15, 0skip, 34.236초 |
| 적용 후 실제 운영 MES를 Pi Chromium에서 조작 | 일반 재개는 standard 유지, 랜덤 버튼 on/off 성공, 같은 run 유지, 최종 standard/running |
| 적용 후 PDA 센서/통신/Unity/질의/조치/카드 없는 진입/기존 경보 | Node8스크립트 통과, 실행 소스와 설치 PDA SHA256 일치 |
| 경보 병합·진동 DOM 회귀 | 같은 설비1행, 기존 경보 첫 진동 유지, AI 반복/정지 이력 추가 진동 호출0 |
| 실제 Jetson→Pi 상태 수신/replay | sequence326~341의16프레임, simulated_at 간격1초, 누락0, replay 일치,69채널 |
| 최종 분석/경보 상태 | ready, 기존 active_alarms0, 확정 AI0, PDA/분석 PID 유지 |

초기 운영 브라우저 검사에는 재개 버튼이 `resume` 명령을 쓸 것으로 잘못 기대한 오류가 있었다. 기존 제품은 화면상 재개에도 `start`를 사용한다. 실제 상태가 running으로 로드된 뒤 검사하고 paused에서 start를 확인하도록 하니스만 보완해 통과했다. 첫 모니터는 새 실행의 warming_up 중 ready를 요구해 종료됐다. 이력을 충분히 채우고 버튼 검증 종료 후 순차 재검사해 위16프레임이 통과했다. 실패 로그도 보존했다. 제품 코드나 기대되는 경보/센서 규칙을 완화하지 않았다.

고정 소스77af의 전체 CI40117400639와 Knowledge publication harness40117400890도 통과했다. 이번 추가 커밋은 운영 기록 문서만 변경한다. 새 탐지 성능 평가·장시간 동시 부하·실측 고장 일반화·물리 키오스크 끝단 지연을 검증한 것으로 설명하지 않는다. 앞선 모델 평가/부하 결과는 그대로 보존한다.

## 백업·중지·롤백

- Jetson 원본6파일/unit/drop-in/일관된 DB: `/home/jetson/shiftlink/backups/20261025-030006-random-controls`
- Pi 원본 pda.js: `/home/pi/shiftlink/analytics/backups/20261025-030007-pda-random-controls`
- Jetson 비공개 배포/수리/관측 로그: `/home/jetson/shiftlink/staging/random-controls-20261025-production`
- Pi 비공개 원본 검사/브라우저/진동/수신 로그: `/home/pi/shiftlink/analytics/validation/random-controls-production-20261025`

원치 않는 고장 생성은 랜덤 모드를 켜지 않으면 시작되지 않는다. 활성 고장이나 미완료 회복 중에는 모드 해제로 사건을 지우지 않고 정상 조치 절차를 끝낸다. 기존 분석 STOP 스위치와 프로파일은 유지한다. 장애 시 위 원본6파일과 pda.js만 정확히 복원하고 MES만 재시작해 정상 제어 API로 이전 가동 상태를 복원한다. 이번에는 systemd 설정을 바꾸지 않았으므로 drop-in을 삭제하지 않는다. 운영 DB를 과거 백업으로 덮어쓰지 않으며 새로 쌓인 일지/센서/사건 기록을 보존한다. 롤백 재시작도 새 모의 실행을 만든다.
