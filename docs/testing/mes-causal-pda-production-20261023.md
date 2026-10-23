# Pi 통계 이상징후 운영 연결 검증 — 2026-10-23

## 적용 범위와 보존

사용자가 운영 배포와 PR 생성을 승인했다. 기존 작업 트리는 보존하고 별도 `codex/causal-v14-pda-production` 브랜치를 main `e1c88f59`에서 시작했다. 원본 stage5·v11/v12c/v13/v14c와 기존 평가 산출물은 수정하지 않았다. Timestral·Torch를 실행하지 않는 고정 v14c 통계 후보를 사용한다.

장비는 `pi@raspberrypi`다. 아래 기능·회귀·브라우저·해시·서비스 검사는 모두 Raspberry Pi에서 실행했다. PC는 편집·Git·파일 전송·결과 보존에만 사용했다. MES 제어 API, 실제 경보 확인·해제, 개인 얼굴 인증·촬영 API는 호출하지 않았다. 원격 접속 비밀번호는 파일·명령 인수·로그에 저장하지 않았다.

## 실제 연결에서 발견한 차이와 수정

| 실제 조건 / RED 근거 | 최소 수정 / GREEN |
|---|---|
| 현재 MES는 69채널이며 연구 config_id와 다름 | 승인된 전체 source config 해시·키·단위·정상 범위를 고정한다. 채널은 키로 정렬하고 모델 임계값은 고정한다. source ID를 연구 ID로 위장하지 않는다. |
| replay snapshot에 config_id가 없고 실제 최초 sequence는 1 | 배치 provenance 확인 전 체크포인트·화면 게시를 유예한다. 최초 1만 허용하고 중간 누락·역전은 거부한다. |
| 실제 `fault` 모드와 개별 stopped/waiting 설비 | 내부 분석 입력에서만 알려진 fault를 비가동 모드로 정규화하고 비가동 설비 측정 품질을 제외한다. 원본 API 센서값은 보존한다. |
| sequence가 그대로인 상태에서 pause로 변경 | 이력을 초기화해 운전 재개 후 정상 64프레임을 다시 모은다. 불량 측정·공통 품질 보류를 healthy로 표현하지 않는다. |
| 최초 실제 replay가 단순 16MB 응답 한도를 넘음 | UTF-8 청크·개별 값 크기를 제한하는 스트리밍 파서로 처리한다. 잘린 JSON·잘못된 trailer는 영속 상태와 게시를 변경하지 않는다. |
| worker 재시작 시 통지 latch·cursor 손실 위험 | JSON 체크포인트에 고정 fingerprint·유한 통계 이력·통지 latch·cursor를 저장하고 재시작 후 그 뒤만 소비한다. 통지는 저장 후 게시한다. |
| 기존 경보와 AI가 같은 설비에서 함께 발생 | 같은 알람창에서 설비별 한 행으로 합치고 AI 설명만 덧붙인다. 기존 확인·미확인 배지·진동 입력은 유지한다. 불변 poll에서 버튼 DOM을 재생성하지 않는다. |
| 배포 도구가 지연 재시작 전의 옛 PDA를 정상으로 오인 | 이전 PID 종료와 새 PID의 HTTP 응답을 함께 확인한다. endpoint가 꺼진 복구는 원래 argv·화면 환경으로 시작하며 중복 프로세스를 만들지 않는다. |

source config ID는 `14dbf3965aeea121a083b71c67ffcbf830a3a4ab156eba6f9011b24383a30bec`다. 69개 전송 채널을 검증하며 고정 통계 모델의 선택 채널만 분석한다. 원래 68채널 Timestral 입력 경로를 사용하는 배포가 아니다. 실측과 물리적 고장 원인 확정의 근거로 해석하지 않는다.

## 검증과 실패 보존

- `tests.test_mes_causal_pda_service`: 18건 PASS. 설정 변조·중복 채널·재시작·고착/불량 측정·신규 run·누락·지연·실제 프록시 응답 보존·큰 replay·잘린 trailer·시작 1·fault·같은 sequence pause·STOP/오류 게시를 검사했다.
- `tests.test_mes_causal_v14_stream`: 13건 PASS. 원본 batch와 행별 통지 일치·제한된 이력·품질·시간·독립 신호·run/정지/재개를 다시 검사했다.
- `tests.test_analytics_release`: 2건 PASS. 실제 파일을 사용하는 임시 복구와 모의 systemctl/PDA 호출로 재시작 확인·복구 fallback을 검사했다. 운영에서 전체 롤백을 실제로 실행한 시험은 아니다.
- `tests.test_pda_advisory_reader`: 3건 PASS. 결과 만료·미래 시각·다른 run/config·sequence·입력 시각·품질 상태·과대/손상 파일·중복 설비·허용 신호·가산 응답을 직접 검사했다.
- Pi의 기존 Chromium으로 같은 알람창 DOM 검사 1건 PASS. 설비 중복 행 없음, AI로 재진동/기존 확인 변경 없음, stale/run/offline 숨김, 동일 poll DOM 유지, 버튼 최소 44px와 오른쪽 정렬을 확인했다. 합성 UI fixture이며 운영 경보를 만들거나 확인하지 않았다.
- 기존 CJS 5건 모두 PASS: `pda_sensor_display`, `pda_network_boot`, `unity_pda_link`, `pda_symptom_rank`, `mes_query_pda`. `node --check shiftlink/mes/web/pda.js` PASS. Pi에 Node가 없어 공식 ARM64 v22.16.0 archive를 공식 SHASUMS256과 대조한 뒤 `/tmp`에서만 사용했다. 전역 설치·환경 변경은 하지 않았다.
- `systemd-analyze verify` 및 모든 릴리스 Python의 compile 검사를 Pi에서 통과했다. 실제 적용 전 원본 PDA 해시 조건도 통과했다.

Python 표준 trace의 실행 줄 집합으로 합친 커버리지는 새 서비스 94.92%(280/295), Pi reader 98.67%(74/75), 배포 도구 39.86%(57/143), 세 모듈 합계 80.12%(411/513)다. 배포 도구의 실제 적용은 별도로 성공했지만 그 실행을 trace 커버리지에 더하지 않았다. 기존 incremental core는 이 통합 집합에서 91.30%(189/207)다. 이는 branch coverage나 저장소 전체 커버리지가 아니다. HTTP handler의 별도 스레드는 이 trace의 줄 집계에 포함되지 않아 reader 직접 경계 검사를 추가했다.

유효한 RED·GREEN 커밋은 같은 브랜치에 보존했다. 초기 8건 미구현, 비가동 오통지, 스트리밍 미구현, 실제 시작/pause/품질 3건, 배포 복구 2건 실패를 각각 재현했다. 초기에 상속 때문에 중복 집계된 18건은 최종 고유 18건과 구성원이 다르므로 더하지 않았다. 첫 Chromium HTTP fixture timeout은 `about:blank`와 로컬 파일을 비교해 로딩 경로 문제로 분리했고 같은 제품 함수·HTML을 로컬 파일에서 검사했다. 첫 trace 보고기에서 Python 3.13의 None 줄 번호 때문에 집계만 실패한 로그도 보존하고, None을 제외해 재측정했다. 실패를 PASS로 바꾸거나 기존 기대값을 완화하지 않았다.

기존 Pi 1Hz 단독/얼굴·CNN 동시 부하의 256/256 프레임·통지 일치·마감 초과 0·스로틀링 0x0 결과와 28,672프레임 원본 일치는 [이전 검증](mes-causal-v14-stream-20261023.md)에 보존한다. 이번 어댑터 추가를 새로운 미사용 정확도 평가나 새 30분 부하시험으로 설명하지 않는다.

## 운영 적용

릴리스 `/home/pi/shiftlink/analytics/releases/v14c-pda-20261023-r1`, 원본 영구 백업 `/home/pi/shiftlink/analytics/backups/20261023-153140`을 사용했다. PDA 4경로와 새 worker unit만 적용했다. 기존 PDA 시작 인수·얼굴/CNN 모델·Jetson 주소는 보존했다. 장비에 없던 knowledge JS/CSS 로딩을 임의로 켜지 않도록 장비 HTML 변형을 사용했고 저장소 HTML의 기존 로딩은 유지했다.

`shiftlink-analytics.service`가 active/enabled로 실행됐다. PDA는 14480에서 24459로 공식 재시작했고 HTTP가 복구됐다. 실제 서비스 재시작 후 체크포인트 sequence 1563을 유지했고, 같은 cursor에서 poll은 약 0.000079초였다. 분석 결과의 operational_notifications는 false, Torch/Timestral 로딩은 false다. 얼굴·CNN 코드/가중치/라벨 6개 SHA256은 전부 이전과 같았다.

처음 정지 상태에서는 Jetson과 Pi의 응답이 ai_insights 제외 완전히 일치했다. 배포 후 외부에서 MES 운전이 재개돼 새 프레임이 계속 들어왔고 모델은 64프레임 준비 후 ready로 전환했다. 우리는 MES 운전·고장 상태를 제어하지 않았다. 최초 60초 감독의 순차 HTTP 비교는 요청 사이 tick 변화 때문에 일부 불일치로 실패했다. 이 원자료를 보존하고 동시 요청의 같은 run·sequence·line_mode만 동등 비교하는 후속 감독으로 구분했다. 운전 중 실제 replay 요청은 약 1.1~1.4초도 걸려 전체 전송·표시를 1초 이내로 보장하지 않는다. 중간 프레임은 순서 검증 replay로 모두 소비하며 기존 PDA 화면 폴링은 3초다.

최종 감독 수치·릴리스 해시·원자료 묶음은 후속 항목에 기록한다. 중지·복구 명령은 [운영 안내](../../deploy/analytics/README.md)를 따른다.

## 남은 한계

실제 물리 센서의 탐지율·고장 원인 분류·오통지율과 실제 고장→PDA 렌더 완료 p95는 미검증이다. 기존 합성 사건 평가의 41/42(97.6%), 정상 오통지 0·중복 0·비매칭 11·발생 기준 지연 p95 23초는 새 운영 성능 수치가 아니다. 경보를 생성/해제해 현장 반응을 시험하지 않았다. 현재 배포는 같은 알람창의 무음 점검 참고 연결이며, 기존 경보를 대체하지 않는다.

## 최종 배포 후 감독 결과

동시 조회 방식의 후속 감독 60초·13표본이 모두 통과했다. 같은 run·sequence·line_mode에서 Pi 응답의 ai_insights를 제외한 전체 내용이 Jetson과 13/13 일치했다. 이 구간은 실제 합성 MES 운전 중 sequence 1685→1737이며 전 표본 AI ready, source 대비 처리 cursor 지연 최대 2프레임이었다. 분석 서비스 최대 RSS 39,344KiB, 최고 온도 50.634℃, 스로틀링 전부 0x0이었다. 관측 replay 처리 구간 최대 1.619984초는 네트워크를 포함하며, 계산 전용 추론 시간이나 전체 화면 p95가 아니다. 이후 게시된 JS의 HTTP 내용 해시도 릴리스와 대조했다.

원자료 보존 위치는 Pi `/tmp/shiftlink-production-validate-20261023`, 로컬 `output/mes-causal-v14-production-20261023/`다. 영구 롤백 백업과 릴리스는 `/tmp`가 아닌 `/home/pi/shiftlink/analytics/`에 남는다. 서비스 재시작 1회·PDA 재시작 1회를 수행했고 MES 서비스·DB·실제 경보에는 변경 명령을 보내지 않았다.

Pi 생성 근거: [최종 요약](evidence/mes-causal-pda-production-20261023/verified-summary.json), [운전 중 감독 13표본](evidence/mes-causal-pda-production-20261023/post-deploy-monitor-v2.json), [실행 줄 커버리지](evidence/mes-causal-pda-production-20261023/merged-coverage.json), [Chromium 결과](evidence/mes-causal-pda-production-20261023/browser-result.json). Pi에서 ZIP CRC와 SHA256을 확인한 원자료 `production-evidence.zip`은 로컬 output에 보존했다. SHA256은 `394cfda030a69a08c5e292618d808308f81b4df504a2749d2e9a446454f174b99`다. PR: https://github.com/hyjuy/ShiftLink/pull/343.

## 고장 정지 전 감지 이력 유지 — 2026-10-23 후속

기존 배포는 비가동 시 신규 분석과 기존 AI 이력 표시를 함께 중단했다. 후속 요청에 따라 신규 분석 보류는 유지하고, 정지 직전 확정된 AI 통지를 별도 `stopped_notices`로 보존한다. 모델·정상화·임계값·감지 조건·Timestral 제외 결정은 바꾸지 않는다.

- 대상은 stopped/waiting 설비 중 MES fault 모드 또는 해당 설비의 활성 경보·warning/critical/fault 상태가 있는 경우다. 정지 사유의 인과관계를 AI가 확정하는 규칙은 아니다.
- 정지 시점 기준 최근 30프레임 안에 이미 발생한 AI 통지만 동일 event_id·감지 시각으로 보존한다. 정지 중 0값·고정값으로 새 통지를 만들지 않는다. 화면은 `AI 이상징후 · 정지 전 감지 · 시각`으로 구분한다.
- 정지가 이어지는 동안 이력을 유지하고 체크포인트에 즉시 저장한다. 서비스 재시작 뒤에도 같은 이력이며, 구형 체크포인트의 필드 부재는 빈 이력으로 읽는다. 이전 버전에서 이미 지운 과거 AI 감지를 만들어 복원하지 않는다.
- 정상 계획 정지, 운전 재개, 다른 run, 프레임 불연속에는 정지 이력을 재사용하지 않는다. 통신 만료·config/run 불일치·잘린 replay·조작된 정지 시각은 게시하지 않는다.
- 동일 설비는 기존 알람창 한 행에 합친다. 기존 active_alarms·확인·배지·진동·범위 이탈 규칙은 변경하지 않았다. AI 이력의 유지·재조회·복원 자체는 재진동이나 새 미확인을 만들지 않는다.
- 잠깐 튄 값을 점검 요청으로 만들지 않는 대조군도 검사했다. 1프레임 20z·2프레임 6z·6프레임 1.5z는 AI 통지 없음, 12프레임 6z 지속 이상은 통지 있음을 확인했다. 특정 합성 채널 fixture의 회귀 결과이며 모든 순간 변화에 대한 성능 보장은 아니다. 같은 창의 기존 MES 범위 이탈 표시는 원래 규칙대로 남는다.

Pi `/tmp/shiftlink-fault-stop-20261023`에서 RED 7건 중 4실패·1오류를 재현했다. 정상 정지/경계와 순간 튐 대조는 수정 전부터 통과했다. 최소 수정 후 초기 Python 29건+Chromium 1건, 추가 경계까지 Python 31건을 통과했다. 이미 active인 서비스를 새 unit으로 교체할 때 `enable --now`만으로는 새 코드가 시작되지 않는 배포 경로도 보완했다. 별도 RED 1오류 후 배포 테스트 3건 PASS를 확인해 전체 고유 Python 회귀는 32건이다. 실제 Chromium 알람창 회귀 1건, 기존 CJS 5건과 JS 문법 검사도 Pi에서 통과했다.

수정 런타임의 보수적 실행 줄 커버리지는 서비스 80.12%(258/322), reader 86.46%(83/96), 두 모듈 합계 81.58%(341/418)다. 이 측정은 테스트 모듈 import 이후 trace를 켰으므로 import/정의 줄은 미집계다. 배포 도구의 기존 전체 코드는 이 80% 범위에 포함하지 않으며 새 업데이트 경로는 별도 기능 테스트와 실제 적용으로 확인한다.

r2 릴리스는 `/home/pi/shiftlink/analytics/releases/v14c-pda-20261023-r2`다. 적용 전에 현재 r1의 PDA 4파일 해시·unit 구문·Python compile·실제 체크포인트를 복사한 독립 `--once` 실행을 확인했다. r1 릴리스와 첫 영구 백업은 보존한다. 새 적용 백업과 배포 후 결과는 아래 Pi 생성 근거에 기록한다. 실제 MES 고장을 강제로 만들거나 사용자 경보를 확인/해제하는 검증은 수행하지 않는다.

r2 운영 적용 백업은 `/home/pi/shiftlink/analytics/backups/20261023-155748`이며 새 worker PID 26455의 cwd/ExecStart가 r2인 것을 확인했다. PDA는 공식 경로로 24459→26465 재시작했다. 운영 main.py·HTML, 얼굴/CNN 코드·모델·라벨 6파일, 고정 incremental core·settings 해시는 그대로다. worker/reader/JS만 새 동작으로 바뀌었다.

배포 후 60초 감독 13표본에서 같은 run·sequence·line_mode의 기존 응답 13/13 일치, 허용 범위의 최대 lag 3프레임, 최대 RSS 39,480KiB, 최고 온도 45.277℃, 스로틀링 0x0을 확인했다. 표본 중 실제 MES는 ready/inactive 상태를 거쳤다. 최종 독립 상태 조회는 MES 운전 재개에 따른 warming_up이었으며 서비스 active/enabled·Torch/Timestral 미로딩·분석 오류 로그 0건을 확인했다. 실제 MES 운전과 고장은 제어하지 않았다. 운영 파일을 읽어 만든 격리 Chromium 화면에서 정지 전 감지 시각·한 행 병합·확인 보존·재진동 없음·44px 버튼·정렬을 추가 확인했다.

Pi 생성 원자료: [최종 요약](evidence/mes-causal-fault-stop-20261023/verified-summary.json), [배포 후 감독](evidence/mes-causal-fault-stop-20261023/r2-monitor.json), [회귀·실행 줄 집계](evidence/mes-causal-fault-stop-20261023/final-tests.json), [기존 PDA 검사](evidence/mes-causal-fault-stop-20261023/js-checks.json), [배포 파일 Chromium 결과](evidence/mes-causal-fault-stop-20261023/browser-result.json). 후속 worker 업데이트 시험 3건은 별도 update-green.log에 보존하며 final-tests.json의 31건과 중복 2건을 빼 전체 고유 32건이다. 해당 JSON의 배포 도구 집계는 후속 수정 전 검증 복사본을 측정한 값이며, 수정 런타임 두 모듈의 커버리지와 구분한다.

로컬 원자료 `output/mes-causal-fault-stop-20261023/evidence.zip`의 CRC·SHA256은 Pi에서 확인했다. SHA256: `96cd4f6cc2eee97e56f4fc3fbcff81cb63e2962dc0302137bf7239ac2dea28fc`.
