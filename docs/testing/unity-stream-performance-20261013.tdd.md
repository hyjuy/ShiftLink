# Unity 스트림 성능 개선과 Pi 측정 — 2026-10-13

기준은 PR #269가 병합된 `1e6d54b`다. 변경은 별도 작업 폴더의 `perf/unity-stream-20261013` 브랜치에 커밋했다. 원본 작업 폴더와 Pi 배포 파일, 시스템 DNS는 변경하지 않았다.

실행 주소: `--mes-url http://jetson-06:8000 --pda-url http://raspberrypi:8080`.

## 최종 결과

| 측정 | 결과 | 범위 |
|---|---|---|
| 캡처 main p95 | 93.666 → 28.640ms | 고정 모델 Edit Mode, 준비 10회 뒤 100프레임씩 |
| JPEG 게시 완료 p95 | 94.892 → 47.590ms | 같은 캡처 경로 |
| Unity 이동 → Pi 영상 표식 | 중앙값 563.5ms / p95 831.5ms / 최대 882.5ms | 자동 컨트롤러 이동 20회, 시계 보정 추정 ±6.5ms |
| HPU 근거리 이동 → 사진·메타데이터 저장 | 239.1786ms | HPU 앞 표준 위치에서 1회 |
| Pi 촬영 흐름 → 임시 결과 화면 RAF | 812.2ms | 기존 기록 조회·촬영 API·새 기록 확인 포함, 1회 |
| Pi HPU 촬영 API 자체 | 191.6ms | 실제 PDA API 호출 1회 |
| HPU 추론 | 71.3ms, conf 0.9941 | confirmed=true, sent=true, EQ-0001 / HPU-01 |
| 최종 PDA 영상 수신 | 8.525141fps, 프레임 간격 p95 168.2592ms | 실제 지정 주소, 서로 다른 JPEG 100개 |

캡처 처리 개선은 확인했다. Pi 표시 지연은 약 0.6~0.8초가 남아 있다. 전체 버벅임 해결이나 전체 시스템 개선율을 주장하지 않는다.

## 문제별 원인·해결·검증

| 문제 | 확인한 원인 | 해결 방식 | 검증 |
|---|---|---|---|
| 반복 Renderer 탐색 | 프리뷰마다 FindObjectsByType/Excluded, 작업자 카메라 갱신·물류 Advance마다 GetComponentsInChildren 수행 | Configure 때 프리뷰 제외 Renderer 캐싱. 작업자 생성·물류 반입 때 배열 캐싱. 계층 변경 시 RefreshPreviewRenderers 호출 | Unity 컴파일·회귀·실기 실행 확인 |
| 불필요한 고해상도 캡처 | 사진 프리뷰 1280×720 렌더 뒤 960×540으로 Blit | 깊이 버퍼가 있는 전용 960×540 타깃에 직접 렌더. 사진 해상도·LivePreview 분리 | 사진 해상도 유지·사진용 프리뷰 미할당 PASS |
| 메인 스레드 GPU 대기·JPEG 압축 | ReadPixels/Apply/EncodeToJPG가 LateUpdate에서 동기 실행 | AsyncGPUReadback과 Task의 EncodeArrayToJPG 사용. 동시 진행 1개, RGBA 버퍼 재사용 | 비동기 반환·중복 제한·JPEG 색상과 방향 PASS |
| 끊김 뒤 이전 프레임 게시 | 진행 중 작업이 연결 종료보다 늦게 완료될 수 있음 | 연결 세대 번호로 이전 결과 폐기. 종료 시 소유 readback·encoder 완료 대기 | 이전 결과 폐기·재연결·진행 중 종료 PASS |
| 재연결 뒤 프레임이 안 나옴 | 객체는 남았지만 GPU RenderTexture가 소실됨. 진단에서 targetCreated=False, running=True, streaming=True, frames=0 | 캡처 전에 IsCreated 확인, GPU 자원 재생성 | 명시적 Release로 재현한 회귀 검사 PASS |
| Unity PDA 미리보기 호출부 | 스트림 타깃을 사진용 LivePreview에서 분리하면 기존 UI가 타깃을 못 받음 | 스트리밍 때 전용 Preview 공유. 그 외에는 기존 LivePreview 사용 | 전용 타깃 공유·사진용 프리뷰 미할당 검사 PASS |
| Pi 영상 502 | Pi/PC 8090 리스너가 닫혀 Connection refused 발생 | Unity Play와 SSH reverse tunnel을 모두 연결 | 실제 raspberrypi:8080 경로 JPEG·100프레임 확인 |
| Pi 내부 hostname 실패 | getent hosts raspberrypi가 127.0.1.1을 반환. PDA 서비스는 127.0.0.1:8080 | 임시 측정 Chromium에만 host-resolver-rules 지정. URL 유지 | chrome-error 페이지였던 실패 시도 제외, 후속 Pi 영상 관측 성공 |
| PDA를 올리면 이동 안 됨 | FactoryWorker.Step이 PdaRaised 상태에서 이동 차단 | 스트림은 유지하면서 PDA를 내리고 컨트롤러 호출 | ±0.22m 이동 20회 및 표식 20개 대조 |
| 성능 비교 오염 | 최초 측정과 별도 Unity PID 8024 실행이 겹침 | 다른 Unity가 없는 조건에서 기준·개선 버전 재측정 | baseline-clean / async-clean 각각 100프레임 |
| 할당량 0 출력 | 이 Unity Mono의 GC.GetAllocatedBytesForCurrentThread 값이 유효하지 않음 | 할당량 수치 제외, unavailable 명시 | 0 allocation 주장하지 않음 |
| Edit Mode 검사 timeout | Player 루프 갱신만으로 해결되지 않았고 진단에서 타깃 소실 확인 | QueuePlayerLoopUpdate와 진단 추가 뒤 GPU 자원 재생성으로 해결 | 최종 회귀 PASS |
| 1픽셀 직접 관측 실패 | 입력 20개에 대응하는 색상 표식을 검출하지 못함. 내부 원인은 확정 못 함 | 해당 시도 제외, 전체 프레임을 128×72로 축소해 관측 | 입력·색상 전환 각 20개 일치 |
| 첫 촬영 응답 지연 | 첫 측정은 전체 크기 canvas 관측 루프가 남은 상태. 3743.4ms는 사전 조회까지 포함 | 관측 페이지를 종료하고 촬영 흐름을 구간별 재측정 | 최종 구간별 수치 보존. 조건이 달라 개선율 계산하지 않음 |

## TDD 및 검증 증거

- `815356c`: 최초 RED. FactoryStreamPerformanceChecks.Regression에서 `RED: dedicated stream render is missing` 확인.
- `03a640d`: 비동기·재연결·GPU 타깃 소실 RED 검사 보존.
- `4e7f376`: Renderer 캐싱·전용 캡처·비동기 JPEG 및 GPU 타깃 재생성 GREEN.
- `9f411ca`: Unity PDA 공유 미리보기와 추가 검사 GREEN.
- `Checks/stream-green-final.log`: 전용 저해상도·사진 분리 PASS, 비동기 반환·작업 제한·이전 프레임 폐기·재연결·JPEG 색상과 방향 PASS, readback 진행 중 종료 PASS. 평균 RGB 오차 0.0221132890631755.
- `python -B -m unittest tests.test_unity_camera_proxy -q`: 4 tests OK.
- `node tests/pda_unity_camera.cjs`: start, cleanup, failure and MES isolation PASS.
- `node --check scripts/measure_pi_movement.cjs`: exit 0.
- 코드 커버리지 80%는 측정하지 않았다. 미지원 GPU의 동기 readback fallback은 실제 미지원 하드웨어에서 검증하지 않았다.

## 캡처 성능 측정 조건

FactoryStreamPerformanceChecks.Benchmark로 기본 공장 모델의 고정 카메라에서 LateUpdate를 호출했다. 준비 10회, 측정 100프레임, 960×540, JPEG 70, 최대 10fps, quality level 5, Unity 6000.3.12f1, D3D11, NVIDIA GeForce MX150이다. 메인 호출 시간과 JPEG 게시 완료 시간을 구분했다. MES 운전 상태를 변경하지 않았다.

| 조건 | main p50 ms | main p95 ms | publish p50 ms | publish p95 ms | 판단 |
|---|---:|---:|---:|---:|---|
| 최초 기준 | 183.949 | 261.355 | 185.367 | 263.626 | 동시 Unity 실행 때문에 비교 제외 |
| 캐싱 단계 | 147.422 | 253.539 | 151.321 | 257.007 | 동시 Unity 실행 때문에 비교 제외 |
| 직접 저해상도 단계 | 197.492 | 261.339 | 200.483 | 271.328 | 동시 Unity 실행 때문에 비교 제외 |
| 최초 비동기 단계 | 27.164 | 37.300 | 41.763 | 52.202 | 동일 조건 비교 수치로 사용하지 않음 |
| 단독 baseline-clean | 72.684 | 93.666 | 73.191 | 94.892 | 유효한 기준 측정 |
| 단독 async-clean | 24.605 | 28.640 | 41.095 | 47.590 | 유효한 개선 버전 측정 |

이 수치를 Play Mode 전체 프레임 시간이나 Pi 표시 개선율로 환산하지 않는다.

## 실제 Pi 이동 및 연결 측정

영상 경로는 Pi Chromium → raspberrypi:8080 PDA 프록시 → Pi 내부 8090 → SSH reverse tunnel → PC Unity 8090이다. 8080은 PDA 화면·API, 8090은 영상 서버이며 서로 역할이 다르다.

Pi의 기존 키오스크 창은 변경하지 않고 임시 Chromium 창을 사용했다. 임시 프로필은 /tmp 아래에 두고 localhost CDP 19222만 SSH로 전달했다. Pi 내부에서는 `--host-resolver-rules=MAP raspberrypi 127.0.0.1`을 임시 Chromium에만 지정했다. 표시 주소는 계속 http://raspberrypi:8080이다. 배포와 시스템 DNS는 수정하지 않았다.

이동은 실제 키보드가 아니라 FactoryWorker.Step의 자동 호출이다. 카메라가 움직인 시각에 임시 색상 표식을 바꾸고 Pi의 MJPEG 이미지 픽셀을 requestAnimationFrame 중 관측했다. 최종 방식은 전체 프레임을 128×72로 축소하고 표식 중심을 읽는다. 입력 20개와 색상 전환 20개를 대조했다. 최소 시계 보정 왕복 13ms에 따른 불확실성 추정은 ±6.5ms다.

최초 유효한 전체 크기 canvas 측정은 p50 611ms / p95 916ms / max 1046ms, 시계 보정 추정 ±8ms였다. 관측 부하를 줄인 최종 수치는 중앙값 563.5ms / p95 831.5ms / max 882.5ms다. 두 값을 시스템 개선율로 계산하지 않는다.

최종 지정 주소 수신 확인은 HTTP 200, 100개 모두 서로 다른 JPEG, 수신 8.525141fps, 첫 프레임 207.736ms, 간격 p50 119.8378ms / p95 168.2592ms / max 212.2711ms, 평균 44866.15 bytes였다. 앞선 다른 카메라 시점의 8.7497fps와 개선율로 비교하지 않는다. 생산자 시각 표시가 없으므로 수신 FPS는 영상 나이가 아니다.

## HPU 촬영 시간

HPU 전방 5m의 표준 위치에서 짧게 전진한 뒤 PDA를 올려 촬영했다. 공장 입구부터 HPU까지 걷는 시간은 포함하지 않는다. 사진의 HPU 가시 마스크를 확인했고 PNG도 시각적으로 확인했다. 유압 탱크·모터·계기와 프레임이 정상 방향으로 보인다.

최종 Unity 사진은 Capture 144.5557ms, Save 91.8316ms, 이동부터 PNG·메타데이터 저장까지 239.1786ms였다. 새 스트림 프레임 2개 준비까지는 442.0799ms였다.

실제 Pi 촬영 API 1회에서 사전 scan 조회 73.6ms, 촬영 API 자체 191.6ms, 사전 조회부터 API 응답까지 265.2ms, 새 scan 확인 529.1ms, 임시 결과 화면 double-RAF까지 812.2ms였다. 실제 PDA와 같은 촬영 API 5초 timeout, 새 scan 조회 500ms 주기를 사용했다. 529.1ms에는 의도된 폴링 대기가 포함돼 있다. 반환된 추론 시간은 71.3ms다.

HPU conf=0.9941, confirmed=true, sent=true, scan_id=`SC-82166ff14d80`, equipment_id=`EQ-0001`, code=`HPU-01`을 확인했다. 첫 촬영은 conf=0.9939, scan_id=`SC-2306d55239bd`였다. 촬영 검증 2회에 따른 인식 기록 2개와 사진이 저장됐으며 운전 상태 변경 API는 호출하지 않았다.

첫 촬영 측정의 3743.4ms 응답과 4827ms 결과 RAF는 이전 관측 루프가 남은 다른 조건의 값이다. 최종 수치와 개선율로 비교하지 않는다. Pi 내부 읽기 요청 10회에서 Unity JPEG 수신 p50 89.053ms / p95 185.805ms, PDA 경유 최근 scan p50 40.756ms / p95 59.590ms, Jetson 직접 최근 scan p50 43.640ms / p95 164.753ms도 확인했다. 한 번의 느린 응답을 추론 시간으로 단정하지 않는다.

812.2ms는 실제 Pi와 실제 API를 사용한 임시 결과 화면의 RAF까지다. 원래 PDA의 lockScan 뒤 420ms 화면 전환 대기, 얼굴 로그인, 실제 사용자 조작 전체 흐름은 포함하지 않는다. Unity 사진 저장 시간과 별도 Pi 촬영 시간을 단순 합산하지 않는다.

## 재현 자료와 남은 한계

원시 결과와 HPU 사진은 `evidence/unity-stream-performance-20261013/`에 보존했다. 전체 로그와 추가 원시는 별도 작업 폴더의 unity/ShiftLinkFactory/Checks 아래에 있다. Unity가 자동 수정한 QualitySettings.asset은 구현 변경에서 제외하고 원래 상태로 복원했다.

측정용 Unity에서 위 MES/PDA 인자로 Play Mode를 실행하고 임시 Pi Chromium CDP 19222를 localhost로 전달한다. `node scripts/measure_pi_movement.cjs`는 자동 이동 20회, `node scripts/measure_pi_movement.cjs --hpu`는 HPU 근거리 촬영과 인식 1회를 실행한다. 측정용 Play Mode를 재시작하므로 사용자 편집 작업 중인 프로젝트에는 사용하지 않는다.

물리 키보드 입력, LCD scanout, 원래 키오스크의 전체 UI 흐름, 동일 Pi 조건의 개선 전후 비교, 장시간 안정성은 미검증이다. 측정용 Unity와 영상 터널은 최종 연결 상태를 유지했다.

공식 API 근거: [EncodeArrayToJPG](https://docs.unity3d.com/6000.3/Documentation/ScriptReference/ImageConversion.EncodeArrayToJPG.html), [AsyncGPUReadback.Request](https://docs.unity3d.com/6000.3/Documentation/ScriptReference/Rendering.AsyncGPUReadback.Request.html), [Editor forcePlayerLoopUpdate](https://docs.unity3d.com/6000.3/Documentation/ScriptReference/Rendering.AsyncGPUReadbackRequest-forcePlayerLoopUpdate.html).

최종 검산에서 이동 스크립트의 첫 p50 출력은 짝수 표본의 위쪽 관측값 567.5ms를 선택한 값임을 확인했다. 20개 원시 표본의 가운데 두 값을 평균한 중앙값은 563.5ms다. 최종 중앙값 표기와 스크립트를 바로잡았으며 기존 출력과 원시 표본은 보존했다. p95 831.5ms와 최대 882.5ms는 변하지 않는다.

문서 검증 중 PowerShell에서 Python으로 전달한 한글 리터럴 일부가 물음표로 변환된 것을 발견했다. UTF-8을 지정한 PowerShell 직접 저장으로 보고서를 다시 작성하고 UTF-8 재읽기로 본문과 표를 확인했다. 소스 코드와 원시 JSON에는 해당 손상이 없었다.
