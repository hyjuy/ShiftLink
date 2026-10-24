# 수동 가동 정지 전 AI 감지 이력 보존

2026-10-24. 후속 코드·Pi 격리 검증 완료. **이번 변경은 운영 미배포**이며 현재 운영 r4의 정상 기준 보완 배포와 구분한다. 운영 서비스·실제 경보를 조작하지 않았다.

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

## 운영 적용과 남은 범위

운영 r4·기존 PDA·얼굴/CNN·이전 릴리스 보호 **65파일 불변**, worker PID4053·PDA PID1215와 기존 unit 해시 불변을 확인했다. 이번에는 파일 설치·서비스 재시작·운영 중 정지 명령을 실행하지 않았다.

운영에 적용하려면 worker와 Pi app reader 양쪽을 함께 갱신해야 한다. Python reader는 이미 PDA 프로세스에 로드돼 있어 파일만 바꿔서는 반영되지 않는다. 현재 공식 `/pda/restart`는 키오스크 창도 닫고 다시 열기 때문에 실제 적용 시 창 재시작과 기존 화면 상태 유지까지 별도 확인해야 한다. 격리 브라우저에서의 정지·재조회 무진동 통과를 운영 키오스크 재시작 무진동 보장으로 확대하지 않는다. 실제 운영 수동 정지 재현과 배포는 아직 수행하지 않았다.
