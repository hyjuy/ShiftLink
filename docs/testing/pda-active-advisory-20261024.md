# PDA 확정 이상징후 표시 유지 후보 — 2026-10-24

## 판정과 보존

**별도 후보 수정·Pi 검증 완료. 운영 미배포.**
Pi의 `/home/pi/shiftlink/analytics/validation/active-advisory-20261024/source`에서 검증했다.
PC에서는 편집·Git·파일 전달·전달 무결성 확인만 수행했다. 운영 PDA·분석 서비스·MES·기존 경보를 변경하지 않았다.

원본 기준은 `0ad3885b`다. `mes_causal_pda_service.py`, `mes_causal_lifecycle.py` 및 이전 평가 산출물을 보존했다.
원본 운영 reader·PDA JavaScript도 근거 보관본의 `original-sources/`에 복사했다.
이전 `fault-lifecycle-20261024/evidence.zip` SHA-256은
`37ae1722e02814fb53d1d32b123a771c4b8646246c27a8fc2890fc85800b505b`로 전후 동일하다.
이번 수정은 `codex/pi-active-advisory-display`에 분리했다. PR·push·운영 연결은 수행하지 않았다.

## 원인과 최소 변경

1. 기존 `AdvisorySession.report`는 내부 고장 사건이 활성이어도 최초 통지 후 30프레임이 지나면 운전 중 표시를 제외했다.
2. `sync_stop`과 reader의 `valid_stop_notice`도 최초 통지→정지 간격을 30으로 제한해 오래 지속된 고장을 정지 이력으로 옮기지 못했다.
3. 원본 poller의 정지·워밍업 초기화와 비가동 통지 삭제는 후보의 확정 사건 이력까지 지우거나 재가동 시 새 ID를 만들 수 있었다.

별도 `scripts/mes_causal_active_advisory.py`가 고정 생애주기 후보를 선택한다. 기본 운영 진입점과 원본 모델을 수정하지 않는다.

- 사건이 활성인 동안 최초 `event_id`, `sequence`, `observed_at`을 유지한다. 기존 후보의 유효한 정상 근거 32회 연속 확인 뒤 제거한다. 점수·임계값·전처리·Timestral 사용 여부는 바꾸지 않는다.
- `confirmed_sequence/confirmed_at`은 확정 사건을 계속 추적한 마지막 입력 위치다. 정지 이력은 이 위치→정지 간격과 최초 시각의 일관성을 검증한다. 이전 형식은 원래 검증 규칙을 따른다.
- 수동·고장 정지에서는 같은 ID를 `정지 전 감지` 이력으로 유지한다. 정지 중 새 판단을 만들지 않는다.
- 재가동 워밍업은 회복으로 세지 않는다. 새 판단을 보류하면서 이전 확정 이력만 `회복 확인 중`으로 표시한다.
- 품질 보류·회복 대기에서는 현재 판단 표시를 보류하되 이력을 체크포인트에 보존한다. 유효한 입력이 돌아오면 같은 ID로 다시 표시한다.
- 새 run 또는 입력 누락에 따른 초기화에서는 이전 사건을 분리한다. 오래된 결과·잘못된 run/config·입력 지연·불량 측정의 보호 조건을 유지한다.
- 기존 `active_alarms`, 미확인 수, 확인 동작과 진동 경로를 보존한다. AI는 같은 설비 알림 행의 참고 정보이며 `operational_notifications=False`다.

UI 변경은 `aiInsightsFrom`의 워밍업 이력 허용과 활성 이력 문구에 한정한다. CSS·배치·버튼·센서 수신·질의 경로는 변경하지 않는다.
후보 체크포인트는 후보 파일 해시로 별도 결합하며 기존 운영 체크포인트에 쓰지 않는다.

## Pi 최종 결과

| 검증 | 결과 |
|---|---|
| Python 회귀 | **73개 통과**, 실패 0·오류 0; 신규 표시 회귀 8개 포함 |
| PDA 검사 | **7개 통과**: 문법 검사, 필수 회귀 5개, AI 표시/진동 검사 |
| 긴 고장·짧은 정상 구간 | 확정 이력 유지; 한 사건 ID |
| 정지·프로세스 재시작·재가동·워밍업 | 같은 ID 유지, 새 통지 없음 |
| 품질 보류·회복 대기 후 재시작 | 회복으로 오인하지 않음; 유효 입력 복귀 후 같은 ID |
| 기존 경보 + AI | 설비당 알림 **1행** |
| AI 갱신·정지 이력·확인 후 재진동 | 추가 `navigator.vibrate` 호출 **0건**; 기존 경보 첫 진동 호출 유지 |
| 후보 줄 실행 관측 커버리지 | 84/86 = **97.7%** |
| reader 줄 실행 관측 커버리지 | 104/107 = **97.2%** |
| 선택한 CLI·중지 스위치 | 격리 출력 `disabled`; MES GET만 사용 |

기존 개발 사례 `002-hydraulic_leak-intermittent-2`의 448프레임을 다시 재생했다.

| 관측 | 기존 표시 | 최종 후보 |
|---|---:|---:|
| 최초 통지 sequence | 105 | 105 |
| 고장 중 짧은 정상 구간 관측 수 | 69 | 69 |
| 그 구간에서 확정 이력이 숨겨진 관측 수 | 65 | **0** |
| 관측 회복 후 사건 해제 index | 312 | 312 |

통지 시점과 회복 시점은 바꾸지 않고 표시 누락을 없앴다. 해당 재생에서 feed+report 계산 p95는 약 23.25ms다.
이 시간은 재생 대기·통신·화면·fsync를 포함하지 않는다. 1초 끝단 간 처리 보장이나 새로운 탐지 성능으로 해석하지 않는다.

## 운영 보존 확인

- 기존 파일 및 이전 결과 보관본 등 **14개 해시 불변**.
- `shiftlink-analytics.service`: `active/running`, PID **7066** 동일, `NRestarts=0`.
- 운영 PDA GET 응답 정상, AI `ready`, 당시 기존 경보 0개, line `running`.
- 검증 종료 시 Pi 47.712°C, `throttled=0x0`. 종료 시점 관측이며 연속 최대 온도 측정은 아니다.
- 후보 Python 프로세스에 `torch`·`timestral` 로드 없음. 남은 검증 프로세스 없음.

실제 키오스크를 조작하거나 물리 진동을 측정하지 않았다. 진동 결과는 실제 PDA JavaScript를 DOM과 진동 호출 관찰자로 실행한 자동 검사다.
기존 자료 재생은 회귀 검사이며 새 미사용 평가·실측 현장 고장 성능은 아니다.
회복은 센서 관측 규칙의 판단이다. 실제 수리 완료를 확인하거나 긴 무증상 간헐 고장을 완전히 구별하는 기능으로 설명하지 않는다.

## 재현과 TDD 근거

Pi 격리 `source`에서 실행한다. 전체 실행 helper와 결과는 아래 근거 폴더·보관본에 포함한다.

```sh
OPENBLAS_NUM_THREADS=1 python3 -m unittest tests.test_pda_active_display -v
OPENBLAS_NUM_THREADS=1 python3 ../run-final.py
/tmp/shiftlink-node-check-20261023/node-v22.16.0-linux-arm64/bin/node tests/pda_active_advisory.cjs
python3 run-js.py
OPENBLAS_NUM_THREADS=1 python3 ../final-evidence.py
```

Node v22.16.0은 SHA-256 확인 후 검증 전용 임시 경로에 풀었다. 시스템 패키지·서비스 설치가 아니다.
전체 검사에 필요한 원본 fixture는 Pi의 이전 보관 디렉터리에 그대로 있으며 테스트는 이 경로를 참조한다.

| 단계 | 커밋 | 실행 근거 |
|---|---|---|
| RED: 30프레임·늦은 정지 | `7e153177` | 신규 6개 검사에서 8개 실패 항목(하위 사례 포함) |
| RED: 재가동 중복 | `4bce2609` | 재가동 시 동일 사건 재통지 |
| GREEN: 표시·정지 이력 | `777a4941` | 신규 7개·전체 72개 통과 |
| RED→GREEN: 워밍업 표시 | `abe66e01` → `14d71ed3` | reader·UI 이력 숨김 재현 후 통과 |
| RED→GREEN: 품질 보류 이력 | `9b94dbb0` → `c372cb8` | 품질 보류·회복 대기 2개 실패 재현; 최종 73개 통과 |

최초 커버리지 집계 helper는 Python 3.13의 줄 번호 `None` 처리에서 실패했다. 당시 회귀 72개 자체는 통과했다.
로그를 보존하고 helper를 수정해 재검증했다. Pi 임시 소스의 UI와 작업 브랜치 파일의 차이는 정확한 후보 파일을 다시 전달해 해소했다.
최종 후보 5개 파일은 Pi 검증 파일과 PC 작업 파일의 SHA-256이 모두 동일하다. 줄 실행 관측 커버리지는 분기 커버리지와 구분한다.

근거: `docs/testing/evidence/pda-active-advisory-20261024/`의 결과 JSON·RED/GREEN 로그·재현 helper.
전체 근거: `D:/obsd/Projects/ShiftLink/output/pda-active-advisory-20261024/evidence-final.zip`.
SHA-256: `200d78f59da4cef1023c9c41a155303a56c59bcb441d15fd47e5b4c4c7b5721c`.
Pi ZIP CRC와 PC 전달 해시를 확인했다. 최초 보관본 `evidence.zip`도 Pi에 별도로 보존했다.

운영 배포·실제 사용자 경보 연결은 이 결과 보고 이후의 별도 단계다.

원본 실행 로그의 행 끝 공백·마지막 빈 줄을 보존했으므로 전체 Git 공백 검사에는 로그 경고가 있다.
실행 소스·테스트·구조 문서·보고서 경로만 검사한 `git diff 0ad3885b HEAD --check -- <해당 경로>`는 통과했다.
