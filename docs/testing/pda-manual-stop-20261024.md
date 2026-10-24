# 수동 가동 정지 전 AI 감지 이력 보존

2026-10-24. 최초 코드·Pi 격리 검증 후, 사용자 배포 요청에 따라 수동 정지 보존을 운영 r5에 적용했다. 아래 미배포 설명은 최초 검증 시점의 기록이며 최종 운영 적용은 후속 항목을 따른다. 실제 MES 정지·고장 주입·기존 경보 확인 조작은 하지 않았다.

## 원인과 최소 수정

기존 worker와 Pi reader가 `fault_stopped_equipment`만 보존 대상으로 사용했다. 따라서 정상 상태에서 수동 정지하면 `inactive`로 전환되고 직전 감지가 사라졌다. `MesEngine.pause()`는 line_mode만 paused로 바꾸므로 설비 operating_state가 running인 같은 sequence의 제어 상태도 고려해야 한다.

공유 helper `stopped_equipment_for_retention`을 worker와 reader에서 함께 사용한다. paused/stopped 전체 라인은 설비 상태가 이전 running으로 남아 있어도 기존 감지를 유지한다. line_mode=running에서 개별 설비가 stopped인 경우도 MES 고장 경보 유무와 관계없이 유지한다. fault 경로와 고장에 의한 waiting 처리는 보존하고, 경보 근거 없는 일반 waiting·recovering·quality_hold는 수동 정지로 확대하지 않는다.

보존하는 것은 **정지 시점 최근 30프레임 안에 이미 확정된 감지**다. 기존 event_id·sequence·observed_at을 유지하고 before_stop·stop_sequence·stopped_at을 붙인다. 정지 중 신규 감지나 통지를 생성하지 않는다. 전역 정지에서는 detector warm과 context ages를 초기화한다. 재조회·체크포인트 복원으로 새 이벤트를 만들지 않으며, 재가동·새 run·프레임 불연속·만료·잘못된 시각·오래된 출력의 기존 거부 조건은 유지한다. 미확정 값이나 오래전에 만료된 감지를 되살리지 않는다.

PDA HTML/JavaScript/CSS와 버튼·용어·알람창 디자인은 수정하지 않았다. 기존 ‘정지 전 감지’ 표현을 사용한다. AI는 operational_notifications=false이며 active_alarms·확인 상태·미확인 배지·진동의 입력으로 추가하지 않는다.

## Pi에서의 RED → GREEN

- RED `3c7da2c6`: 기존 구현에서 수동 정지 3테스트·4실패를 재현했다. 일반 정지·일시정지는 inactive를 반환했고 개별 수동 정지는 보존 항목이 없었다.
- GREEN `12ca0803`: 최소 수정 후 관련 Python 회귀 **44개 통과**, 실패/오류 0. 새 수동 정지 4개는 이 44개에 포함되므로 합산하지 않는다.
- 보수적 실행 줄 확인: worker 277/343=80.76%, reader 86/100=86.00%. 회귀 로그의 unapproved source state 출력은 거부 경계 테스트의 의도적 결과이며 운영 오류 로그가 아니다.
- 실제 Pi Chromium **1개 통과**: fault/paused/stopped에서 같은 설비 한 행, 동일 이벤트와 기존 확인 상태 유지, AI로 인한 추가 진동 없음, 기존 버튼 정렬과 44px 이상 목표 크기를 확인했다. 실제 사용자 경보·계정·화면은 조작하지 않았다.
- 기존 고정 profile을 사용하는 ContextDetector 통합 **3조건 통과**: paused, stopped, 개별 stopped. 동일 event_id `664700d34eaabfac950d994e9e9c0cd1:126:EQ-0006`와 감지 시각을 보존하고, 재시작 후 reader까지 before_stop을 유지했다. 전역 정지의 warm=0·context ages=0도 확인했다. 이는 이전 96건 평가의 마찰 개입 한 건을 재사용한 회귀이며 새 미사용 성능 평가가 아니다.
- 복사한 기존 운영 체크포인트는 새 코드에서 그대로 로드됐고 복사본도 수정되지 않았다. 모델 core·정상 보정 코드·profile·settings는 운영 r4와 바이트가 같으며 재학습·임계값 변경은 하지 않았다.

실행은 `/home/pi/shiftlink/analytics/validation/manual-stop-20261024/source`의 별도 복사본에서 수행했다. 주요 명령:

```sh
python3 -B -m unittest tests.test_pda_manual_stop -v
python3 -B /home/pi/shiftlink/analytics/validation/manual-stop-20261024/green-check.py
SHIFTLINK_BROWSER_EVIDENCE=/home/pi/shiftlink/analytics/validation/manual-stop-20261024/browser python3 -B -m unittest tests.test_mes_causal_pda_browser -v
python3 -B /home/pi/shiftlink/analytics/validation/manual-stop-20261024/profile-check.py
```

Pi CRC와 전송 후 SHA256 대조를 통과한 원자료 ZIP은 Pi 위 경로와 로컬 `D:\obsd\Projects\ShiftLink\output\pda-manual-stop-20261024\evidence.zip`에 보존했다. SHA256 `b0e94d3321602aa6e1aabc173913316ef018eb1583c6a75f2995ace52977624f`. [검증 요약](evidence/pda-manual-stop-20261024/summary.json), [실행 줄 확인](evidence/pda-manual-stop-20261024/green-result.json), [고정 profile 통합](evidence/pda-manual-stop-20261024/profile-result.json), [보호 파일·원본 모델 대조](evidence/pda-manual-stop-20261024/integrity.json)를 함께 보존한다.

## 최초 격리 검증 당시 운영 상태와 남은 범위

운영 r4·기존 PDA·얼굴/CNN·이전 릴리스 보호 **65파일 불변**, worker PID4053·PDA PID1215와 기존 unit 해시 불변을 확인했다. 이번에는 파일 설치·서비스 재시작·운영 중 정지 명령을 실행하지 않았다.

운영에 적용하려면 worker와 Pi app reader 양쪽을 함께 갱신해야 한다. Python reader는 이미 PDA 프로세스에 로드돼 있어 파일만 바꿔서는 반영되지 않는다. 현재 공식 `/pda/restart`는 키오스크 창도 닫고 다시 열기 때문에 실제 적용 시 창 재시작과 기존 화면 상태 유지까지 별도 확인해야 한다. 격리 브라우저에서의 정지·재조회 무진동 통과를 운영 키오스크 재시작 무진동 보장으로 확대하지 않는다. 실제 운영 수동 정지 재현과 배포는 아직 수행하지 않았다.

## 사용자 요청 후 운영 적용 (2026-10-24 18:38 KST)

사용자가 수동 정지 수정의 운영 배포와 배포 후 확인을 명시적으로 요청했다. Pi에서 관련 Python 회귀 44개(39.770초)와 Chromium 검사를 다시 통과한 뒤 적용했다. 운영 직전 active_alarms와 AI 항목이 모두 0건임을 확인해, 기존 경보를 임의로 확인하거나 해제하지 않았다. 현재 공식 재시작 경로는 Chromium 창과 PDA backend를 함께 다시 열며, 세션 로그인은 초기화될 수 있다. 화면 코드의 확인 상태 저장 규칙을 변경하지 않았다.

- 적용 릴리스: `/home/pi/shiftlink/analytics/releases/normal-context-v1-pda-20261024-r5-manual-stop`
- 원본 r4 및 기존 릴리스는 보존. r4의 16개 고정 파일과 비교해 달라진 것은 `scripts/mes_causal_pda_service.py`와 `shiftlink/pda/ai_insights.py` 두 파일뿐이다.
- 제품 코드 기준: `b14731e8d04b97b403ee1618157c92777b63b745`. worker SHA256 `e15beb387df486a4d8dfbdfc6805f898a442d636a9ed7e9a3e5e3fb79817a7b1`, reader SHA256 `ce48e76280447596f89f73fa657dcaef86aae14e71f573f3602d53245c54d306`.
- 복구 백업: `/home/pi/shiftlink/analytics/backups/20261024-183824`. 이 백업의 기존 unit·PDA 네 경로·원래 실행 인수와 별도의 배포 직전 checkpoint 복사본을 보존했다.
- `apply_release.py` check/apply 종료 0. worker active/enabled, PDA PID1215 → 7075. HTML/JS와 PDA `__main__.py`는 바이트가 같아 유지했으며 app reader만 교체했다. 새 unit은 r5를 가리키며 기존 normal state directory와 글로벌 STOP을 사용한다.
- 모델·정상 profile·settings·채널 설정은 r4와 같고 재학습·문턱 변경·패키지 설치·Jetson MES 재시작·MES 정지·고장 주입은 하지 않았다.

복구가 필요한 경우 이번 배포의 백업을 명시해 기존 도구를 실행한다. PDA도 이전 reader로 복원되므로 창이 다시 열릴 수 있다.

```sh
sudo -v
python3 -B /home/pi/shiftlink/analytics/releases/normal-context-v1-pda-20261024-r5-manual-stop/deploy/analytics/apply_release.py --rollback /home/pi/shiftlink/analytics/backups/20261024-183824
```
### 배포 후 확인

- 배포 파일을 직접 import한 `post-check.py`에서 수동 정지 회귀 4개 + 실제 Pi Chromium 1개, 총 **5개 통과**, 실패·오류·skip 0. worker 경로는 새 r5, reader 경로는 운영 app임을 assert했다. 별도 fixture가 읽은 HTML/JS도 운영 app과 SHA256가 같음을 확인했다. 이 4개는 앞의 44개와 겹치므로 서로 다른 49개 테스트로 합산하지 않는다.
- 실제 배포된 worker·reader와 고정 정상 profile을 불러온 ContextDetector 통합 **paused/stopped/개별 stopped 3조건 통과**. 동일 event_id·감지 시각·before_stop을 정지·재조회·체크포인트 복원 후 유지했고 정지 중 새 판단을 만들지 않았다. 기존 합성 마찰 사례를 재사용한 회귀이며 새 성능 평가가 아니다.
- 같은 알람창에서 기존 경보와 AI가 같은 설비 한 행으로 표시되고 기존 확인 상태·미확인 개수·반복 진동 호출이 바뀌지 않았다. 브라우저 결과의 `vibrations=1`은 최초 기존 경보의 1회이며 AI 변경·정지·재조회로 추가되지 않았다. 물리 진동 장치를 관찰한 결과는 아니다.
- 운영 관측 **61.768초, 17/17 같은 프레임**에서 `ai_insights`를 제외한 Pi·Jetson 응답이 완전히 같았다. AI는 ready·항목 0건, 기존 경보 0건이었다. worker PID7066 active/enabled·NRestarts=0, PDA PID7075·실제 Chromium PID7095 실행, 배포 후 worker analysis_error 0. 관측 종료 온도 44.3℃·throttled=0x0. 30분 부하나 얼굴/CNN 동시 부하를 다시 측정한 결과는 아니다.
- app reader를 변경 대상으로 제외한 **보호 파일 64개 전부 불변**. 이전 릴리스·r4의 원본 16개·PDA main/HTML/JS·얼굴/CNN 코드·가중치가 포함된다. 새 릴리스의 manifest 16개 파일과 운영 reader도 해시 검증을 통과했다.
- 최초 배포 후 점검 실패도 보존했다. Chromium이 `/proc/.../cmdline`을 한 문자열로 다시 쓰므로 첫 프로세스 token 필터가 실행 중인 창을 놓쳤고, namespace package의 `_NamespacePath`에 list.insert를 호출한 첫 테스트 runner도 실패했다. 실제 프로세스 PID7095와 경로를 확인하고 점검 도구의 shlex 분해·namespace 경로 list 변환만 고쳐 재검증했다. 제품 코드·임계값·운영 서비스의 추가 변경은 없었다. 원래 실패 로그와 도구는 `.first`로 남아 있다.

주요 명령은 Pi에서 실행했다.

```sh
python3 -B /home/pi/shiftlink/analytics/validation/manual-stop-deploy-20261024/post-check.py
python3 -B /home/pi/shiftlink/analytics/validation/manual-stop-deploy-20261024/installed-profile/profile-check.py
python3 -B /home/pi/shiftlink/analytics/validation/manual-stop-deploy-20261024/monitor.py
```

[배포 요약](evidence/pda-manual-stop-deploy-20261024/summary.json), [적용 결과](evidence/pda-manual-stop-deploy-20261024/deployment-result.json), [배포 코드 회귀](evidence/pda-manual-stop-deploy-20261024/post-result.json), [정지 조건 통합](evidence/pda-manual-stop-deploy-20261024/installed-profile/profile-result.json), [운영 관측](evidence/pda-manual-stop-deploy-20261024/monitor-result.json), [경보창 확인](evidence/pda-manual-stop-deploy-20261024/browser-after/result.json)을 보존했다. 전체 로그·격리 화면·점검 도구 ZIP은 Pi 위 validation 경로와 로컬 `D:\obsd\Projects\ShiftLink\output\pda-manual-stop-deploy-20261024\evidence.zip`에 있다. Pi CRC와 전송 후 SHA256 `0aedc72b3795ce08570a572aba0795cb6b83f46708fa7cba0f3bf655f5a0522d`가 일치한다. 운영 체크포인트 복사본·얼굴 자료·실제 Chromium 프로필은 공개 ZIP에 포함하지 않았다.

**확인 범위:** 운영에는 실제 적용됐지만 실제 MES 고장 주입·수동 정지를 하지 않았으므로, 운영 화면에서 실제 이상을 확정한 뒤 멈추는 현장 시나리오를 관찰했다고 주장하지 않는다. Pi 격리 fixture에서 배포된 코드·동일 UI를 사용해 정지 전 감지 유지·중복 억제·추가 진동 호출 없음을 검증했다. 기존 경보가 살아 있는 상태의 키오스크 재시작 확인 상태 보존은 이번 무경보 배포로 검증되지 않았다. 현재 경보·확인·진동 규칙을 새로 바꾸지 않았다.
