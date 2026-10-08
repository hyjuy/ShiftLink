# Unity 가상 PDA 카메라 → 라즈베리파이 PDA

PDA에서 **설비 스캔**을 누르면 Unity 캐릭터가 든 가상 카메라의 영상을 표시한다.
현재 단계는 영상 표시까지다. 영상 기반 설비 분류와 Pi 움직임에 따른 시점 제어는 후속 단계다.

Unity는 PC에서 실행한다. Pi PDA는 로컬 프록시를 통해 가상 카메라 프레임을 받는다.
MES 센서·질의는 계속 Jetson으로 요청하며 실제 웹캠을 이 영상의 입력으로 사용하지 않는다.

## 실행

PC에서 SSH 터널을 유지한다. 비밀번호는 SSH 프롬프트에 입력하고 파일에 저장하지 않는다.

```powershell
ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=3 -R 127.0.0.1:8090:127.0.0.1:8090 pi@raspberrypi
```

다른 PC 터미널에서 Unity를 실행한다.

```powershell
python -B scripts/run_unity_demo.py --editor D:/obsd/Unity/Editors/6000.3.12f1/Editor/Unity.exe --mes-url http://jetson-06:8000
```

Pi의 PDA 실행 인자에 가상 카메라 주소를 지정한다.

```bash
python -m shiftlink.pda --jetson http://jetson-06.tail0a6af3.ts.net:8000 --unity http://127.0.0.1:8090
```

자동 시작 설치 시 두 번째 인자로 같은 주소를 지정한다.

```bash
deploy/install_pda.sh http://jetson-06.tail0a6af3.ts.net:8000 http://127.0.0.1:8090
```

PDA에서 로그인 후 **설비 스캔**을 누른다. Unity는 캐릭터의 가상 PDA 카메라를 활성화한다.
화면을 닫으면 요청을 취소하고, Unity는 마지막 요청 후 약 3초가 지나면 기존 카메라 모드로 돌아간다.
Unity나 터널이 끊기면 PDA는 이전 영상을 숨기고 자동으로 다시 연결한다.

`--unity`를 지정하지 않은 PDA는 기존 실제 카메라 인식 결과 대기 방식을 사용한다.
Unity 서버와 Pi PDA 서버는 모두 루프백에만 바인딩한다. 터널을 닫으면 영상 연결도 끊긴다.

## 혼자 실행하고 캐릭터 조작하기

Unity Hub에서 `unity/ShiftLinkFactory` 프로젝트를 열고 `Assets/Scenes/Factory.unity` 씬을 연다.
상단 ▶ 버튼으로 플레이 모드를 시작한 뒤 **Game 화면을 한 번 클릭**한다.
위 실행 스크립트를 사용하면 공장 씬과 플레이 모드가 자동으로 열린다.

| 키 | 동작 |
|---|---|
| F | 캐릭터 조작 모드 / 공장 전체 보기 |
| W / A / S / D | 앞으로 / 왼쪽 / 뒤로 / 오른쪽 이동 |
| 마우스 | 시점 회전 |
| V | 1인칭 / 3인칭 전환 |
| P | 가상 PDA 올리기 / 내리기 |
| Esc | 올린 PDA 내리기 |

PDA를 올리면 이동과 시점 회전이 멈춘다. 위치를 바꾸려면 P로 내리고 이동한 뒤 다시 P를 누른다.
Pi에서 영상을 보려면 SSH 터널 창을 계속 열어 두고 PDA에서 로그인 후 설비 스캔을 누른다.
종료할 때는 Unity의 ▶ 버튼을 다시 누르고 SSH 터널 창에서 Ctrl+C를 누른다.
기존 Pi 장비 인식 코드가 별도로 수정된 환경에서는 설치 스크립트로 전체 앱을 덮어쓰지 않는다.
장비 인식 코드를 보존한 상태에서 영상 연동 변경만 검토해 반영한다.

## 현재 전송 방식과 검증

MJPEG 연결 하나로 JPEG 프레임을 연속 전송한다. 전송 크기는 960×540, JPEG 품질은 85,
Unity 렌더링 상한은 초당 20장이다. 프레임마다 HTTP 왕복을 기다리지 않는다.
실제 표시 속도는 네트워크 왕복 시간과 Pi의 디코딩 속도에 따라 낮아질 수 있다.
현재는 단일 PDA용이다. 측정 결과 더 높은 프레임률·낮은 지연이 필요하면 WebRTC로 전환한다.

```powershell
python -B -m unittest tests.test_unity_camera_proxy -q
node tests/pda_unity_camera.cjs
```

실제 Unity HTTP·JPEG·연결 종료 검증은 `FactoryCameraStreamChecks.Run`으로 실행한다.
결과는 `unity/ShiftLinkFactory/Checks/camera-stream-check-result.txt`와 `camera-stream.jpg`에 남는다.
