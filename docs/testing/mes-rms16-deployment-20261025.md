# RMS16·점진 랜덤 MES 운영 적용 — 2026-10-25

모든 수동 검증을 Raspberry Pi에서 완료한 뒤 Pi 분석 r7과 Jetson MES의 `--progressive-faults`를 적용했다. [고정 후보·미사용 평가·실시간 결과](mes-rms-confirmation-20261024.md)와 [공개 집계](mes-rms-confirmation-20261024-summary.json)를 함께 본다. 배포 코드는 b5b5d65 기준이며, 후속 커밋은 배포 기록과 현재 경로를 보완한다.

## 실제 적용과 보존

| 항목 | 확인 결과 |
|---|---|
| Pi 분석 | `/home/pi/shiftlink/analytics/releases/rms16-active-advisory-20261024-r7`, 별도 RMS16 프로파일·별도 state 디렉터리 |
| 분석 프로세스 | 20799→30896, NRestarts0, active |
| 실제 PDA | PID20812 유지, backend/reader/JavaScript/HTML 네 파일 해시 동일 |
| Jetson MES | `--progressive-faults` 선택, PID45593, NRestarts0, running |
| 나머지 Jetson 서비스 | uploader1145·Ollama1049·judge1050 PID/active 상태 보존 |
| 기존 데이터 | 이전 실행 8,947프레임 보존, 모든 테이블 행 수 감소 없음 |
| 기존 설정 | 기존 unit·환경 drop-in 해시 동일, 새 ExecStart 선택 drop-in만 추가 |
| 기존 모델/이력 | r6·원본 profile·기존 평가·원래 journal 보존, 전환 시 cursor/event_id/정지 이력 명시 복사 |

전환 직전 기존 active_alarms와 확정 AI 이력이 모두0임을 확인했다. 이를 임의 해제해서 적용한 것이 아니다. 분석 worker와 MES만 갱신했고 PDA·얼굴/CNN 앱은 재시작하지 않았다. MES 재시작은 새 시뮬레이션 실행 `414b92e58b834856a6b3085be96c9089`을 만들었으며 이전 in-memory 실행을 그대로 유지했다고 설명하지 않는다. 새 실행의 초기 센서 이력 수집 뒤 ready로 전환했다. 기존 경보 규칙·확인·무음 AI 참고 표시·정지 전 감지 유지 정책은 변경하지 않았다.

## 배포 후 실제 연결

Pi의 실제 PDA API를 120회 조회했다. 120/120 ready, 모델 오류0, 전달 센서69채널·기존68채널 분석 매핑을 유지했다. 실제 replay 1~221의 221프레임은 누락·중복 없이 연속이며 simulated_at은 1초 간격이다. 모든 프레임의 채널 집합·구성 보존·정답 비공개를 확인했다. 실제 API 응답 p95 0.110초, 분석 HTTP/replay/처리/저장 poll p95 0.140초였다. 이 두 값은 고장 발생부터 물리 화면 표시까지의 p95가 아니다.

별도 실제 1Hz·Jetson 왕복 격리 경로의 화면 p95는 26.64초(미리 정한5사례)였고 269/269프레임을 처리했다. 기존 경보와 같은 설비1행, 확인 상태 유지, AI 추가 진동 호출0, 30프레임 이후 유지 검사를 통과했다. 물리 진동 모터와 운영 키오스크 자체의 표시 지연은 계측하지 않았다.

배포 후 자동 발생한 공압 누설 `CAU-01 / EQ-0003`도 감지했다. 별도 비공개 생성 기록의 시작 seq248과 AI 첫 통지 seq274가 일치하는 설비이며 26프레임 지연이다. seq366/369 조회에서 같은 사건 ID가 active로 유지되어 30프레임 뒤에도 사라지지 않았다. 이 단일 관찰은 운영 합성 경로 확인이며 별도의 정확도 추정이나 끝단 간 wall-time 측정은 아니다. 정답 기록은 분석기에 공급하지 않았다. 선택한 모드대로 모의 수리 전까지 유지하며 확인을 위해 임의 수리하거나 경보를 지우지 않았다.

현재 통계 분석 worker VmRSS/VmHWM 40352 kB, Threads1, `throttled=0x0`다. Timestral/torch를 분석 process에 로딩하지 않았다. 기존 MemoryMax 설정은 유지했으며 이 숫자를 메모리 cgroup 강제 적용 증거로 쓰지 않는다. 이번에는 얼굴/CNN의 새로운 강제 동시 추론 부하를 추가하지 않았고, 기존 PDA 서비스를 실행한 상태에서 확인했다.

## 백업·중지·복구

- Pi unit과 최종 원본 checkpoint: `/home/pi/shiftlink/analytics/backups/20261025-004001-rms16`.
- Jetson 원본 세 파일·unit/drop-in·일관된 SQLite 백업: `/home/jetson/shiftlink/backups/20261025-003710-rms16-progressive-pinned`. DB 크기 2,806,358,016bytes.
- 최초 온라인 복사에서 갱신으로 진행이 재시작돼 완료되지 않은 사본은 별도 INCOMPLETE 표기로 보존했다. 운영 DB를 변경하지 않고 WAL 읽기 transaction을 고정한 별도 백업을 완료했다. 원본 서비스의 실행을 중단해 백업한 것이 아니다.
- 공통 중지 스위치 `/var/lib/shiftlink-analytics/STOP`을 유지했다. 이를 지워서 시작을 강제하지 않았다.

Pi 복구는 원본 unit을 되돌려 원래 r6/state를 선택한다. 아래는 준비한 복구 경로이며 이번에는 실행하지 않았다.

```sh
sudo install -m 0644 /home/pi/shiftlink/analytics/backups/20261025-004001-rms16/previous.service /etc/systemd/system/shiftlink-analytics.service
sudo systemctl daemon-reload
sudo systemctl restart shiftlink-analytics.service
```

MES 복구는 위 Jetson 백업의 `files/shiftlink/mes/server.py`, `__main__.py`, `storage.py`를 원래 위치로 복원하고 새 `zz-progressive-faults.conf`만 제거한 뒤 reload/restart한다. 새 모듈은 선택되지 않는 보관본으로 둘 수 있다. 기존 환경 drop-in과 현재 운영 DB는 덮어쓰지 않는다. 재시작은 새 시뮬레이션이므로 현재 확정 이상징후가 있을 때 이를 지우는 수단으로 실행하지 말고 수리/운전 상태와 함께 판단한다. 전체 DB 백업을 현재 DB 위에 복원해 새 기록을 잃게 하는 절차는 사용하지 않는다.

사용·검증·일반 절차는 [점진 모드](../guides/mes-progressive-faults.md), [RMS16 적용 경로](../guides/mes-rms16-deployment.md)를 따른다. 원본 실패·성공 로그와 모든 합성 입력은 Pi의 `analytics/validation/rms-confirmation-20261024` 및 별도 로컬 evidence ZIP에 보존하며 Git에는 소스·소비된 공개 합성 회귀 fixture·집계만 올린다.

실측 센서·현장 고장 일반화 검증은 남아 있다. 기존 Jetson 질의 문맥의 30프레임 참고 제한도 이번에 바꾸지 않았다. PDA의 회복 전 표시 유지와 LLM의 장기 이력 참조를 같은 기능으로 설명하지 않는다.
