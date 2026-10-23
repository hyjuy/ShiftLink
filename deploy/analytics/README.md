# Pi 통계 이상징후 서비스 운영

Timestral을 사용하지 않는 고정 v14c 통계 후보를 별도 프로세스로 실행한다. 원본 연구 코드·평가 산출물은 변경하지 않는다. 입력은 현재 합성 Jetson MES이며 실측 센서에 대한 정확도는 검증하지 않았다.

## 경계

- MES를 제어하거나 기존 `active_alarms`·확인·진동 규칙을 수정하지 않는다.
- Pi PDA 프록시는 `/api/state`에 검증된 `ai_insights`만 추가한다. 기존 센서·질의 근거·인증 전달은 유지한다.
- 같은 알람창에 설비별 한 행으로 합치며, AI만 있는 행은 무음 점검 참고 정보다. AI는 미확인 경보 개수·전체 확인·재진동의 입력이 아니다.
- 화면의 기존 3초 폴링은 유지한다. 분석 서비스는 1초 대기 주기로 조회하고 replay로 중간 프레임을 모두 소비한다. 실제 조회 주기는 네트워크·처리 시간을 포함한다.
- 전송은 69채널 전체의 키·단위·정상 범위를 고정 설정과 검사한다. 고정 모델은 그중 선택한 채널을 사용한다. 배열 위치로 임의 축소하거나 config_id를 연구 ID로 위장하지 않는다.
- 실제 MES의 최초 sequence=1, snapshot에 없는 config_id의 배치 검증, `fault` 비가동 처리, 개별 비가동 설비 품질 제외를 어댑터에서 처리한다.
- 정상 64프레임 준비 전·비가동·불량 측정·통신/모델 오류·오래된 결과는 정상 판정으로 표시하지 않는다. `recent`는 최근 통지이며 현재 고장 확정 상태가 아니다.

## 배포

운영 설정 `source-config.json`은 승인 당시 `/api/config.config` 원본이다. 구성 해시가 바뀌면 재승인·재검증이 필요하다. 새 모델을 자동 선택하지 않는다.

릴리스는 `/home/pi/shiftlink/analytics/releases/<고정 식별자>`에 필요한 Python/설정/PDA 파일과 `release-manifest.json`을 넣는다. manifest에는 모든 릴리스 파일 SHA256와 교체 전 PDA 3파일 SHA256, 새 reader 파일 부재를 기록한다. 기존 장비에 없는 knowledge CSS/JS 로딩은 `device-pda.html` 변형에서만 제외해 현재 장비 구성을 보존한다. 저장소 HTML의 기존 로딩은 유지한다.

Pi에서 먼저 확인한다.

```sh
python3 -B deploy/analytics/apply_release.py --release /home/pi/shiftlink/analytics/releases/<식별자>
```

실제 적용은 같은 SSH TTY에서 `sudo -v` 인증 후 위 명령에 `--apply`를 붙인다. 원본 4경로의 존재·내용과 기존 unit 상태를 영구 백업한 뒤 이 서비스 unit만 설치한다. worker가 유효한 결과를 내면 PDA 공식 `/pda/restart`로 화면 서버를 재시작하고 새 PID와 HTTP 응답을 확인한다. MES는 재시작하지 않는다. 실패 시 백업으로 복구하며, PDA endpoint가 꺼져 있으면 저장한 기존 실행 인수와 화면 환경으로 복구한다.

## 상태·중지·복구

```sh
systemctl status shiftlink-analytics.service
journalctl -u shiftlink-analytics.service --since '10 minutes ago'
cat /run/shiftlink-analytics/latest.json
```

NumPy와 Python 표준 라이브러리만 필요하다. 기존 Pi NumPy를 사용하며 전역 패키지는 설치하지 않는다. systemd는 실패 시 재시작하고 한 코어 CPU 할당·384M 메모리 한도를 적용한다. 결과 파일은 tmpfs `/run`, 원자적 JSON 체크포인트는 `/var/lib/shiftlink-analytics/checkpoint.json`에 쓴다. 통지는 게시 전에, 나머지는 최대 30프레임 간격으로 저장한다. 재시작 시 모델·source fingerprint를 검사하고 영속 cursor 뒤만 재생한다.

중지 스위치는 `sudo touch /var/lib/shiftlink-analytics/STOP`이다. 서비스가 다음 조회에 disabled 결과를 내고 정상 종료한다. 즉시 중지는 `sudo systemctl stop shiftlink-analytics.service`를 사용한다. 재개하려면 STOP을 제거하고 서비스를 시작한다. worker만 꺼도 기존 경보·센서 화면은 계속 동작하며 10초가 지난 AI 결과는 숨긴다.

전체 복구는 다음과 같다. `<백업>`은 적용 명령이 출력한 실제 경로여야 한다.

```sh
sudo -v
python3 -B deploy/analytics/apply_release.py --rollback /home/pi/shiftlink/analytics/backups/<백업>
```

해당 worker unit과 PDA 4경로만 이전 상태로 복구한다. 연구 원본·MES DB·얼굴 템플릿·CNN/얼굴 가중치·기존 알람은 복구 도구의 변경 대상이 아니다.

## Pi 검증

```sh
python3 -B -m unittest tests.test_mes_causal_v14_stream tests.test_mes_causal_pda_service tests.test_analytics_release tests.test_pda_advisory_reader -v
SHIFTLINK_BROWSER_EVIDENCE=/tmp/shiftlink-browser-result python3 -B -m unittest tests.test_mes_causal_pda_browser -v
```

브라우저 검사는 Pi에 이미 있는 Chromium과 별도 프로필·합성 화면 데이터를 사용한다. 개인 얼굴·실제 경보 조작은 하지 않는다. 기존 CJS 검사에는 `/tmp`에서만 검증한 ARM64 Node 실행 파일을 사용하고 시스템 환경은 바꾸지 않는다. 상세 실행·실패·수정·결과는 `docs/testing/mes-causal-pda-production-20261023.md`에 기록한다.
