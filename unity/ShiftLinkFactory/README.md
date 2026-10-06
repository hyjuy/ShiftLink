# ShiftLink 3D 공장 · MES · PDA 시연

공장 외벽·지붕·철골과 천장 LED 12개, 외부 LED 4개를 설치했다.
시작 화면에서 **View factory interior**로 내부를 확인하고 **View factory exterior**로 외관 보기로 돌아간다.
배치·보행 공간·외관·조명 검증은 `docs/testing/unity-factory-layout-20261006.tdd.md`에 기록했다.

프로젝트 경로: `D:/obsd/Projects/ShiftLink/unity/ShiftLinkFactory`.
Unity 버전은 6000.3.12f1, Built-in Render Pipeline이다. 장비 프리팹과 FactoryRig로 공장 장비와 이송 구간을 구성한다.

## 실행

Unity Editor 설치 경로는 `D:/obsd/Unity/Editors/6000.3.12f1/Editor/Unity.exe`다.
[공식 설치 파일](https://unity.com/releases/editor/whats-new/6000.3.12f1)을 사용한다.
설치 파일은 `D:/obsd/Installers/Unity/UnitySetup64-6000.3.12f1.exe`에 저장했다.

저장소 루트에서:

```powershell
python -B scripts/run_unity_demo.py
```

전용 시연 DB `mes_data/unity-demo.sqlite3`로 MES와 PDA 프록시를 시작하고 Unity Play Mode를 연다.
MES는 `http://127.0.0.1:8000/`, PDA는 `http://127.0.0.1:8080/pda.html`이다.
기존 서비스가 포트를 사용 중이면 다른 포트를 지정한다.

```powershell
python -B scripts/run_unity_demo.py --mes-port 8010 --pda-port 8081
```

실제 Jetson/PDA 연결에는 같은 MES 주소를 사용한다.
Pi의 기존 PDA 앱도 해당 MES를 대상으로 실행한다. 각 장치의 `127.0.0.1`은 그 장치 자신이다.

```powershell
python -B scripts/run_unity_demo.py --mes-url http://jetson-06:8000
```

기존 MES를 지정하면 실행 스크립트는 해당 MES의 공정 상태를 변경하지 않는다.
별도 PDA 웹 주소가 있으면 `--pda-url http://PDA_WEB_HOST:PORT`를 지정한다.
Editor 위치가 다르면 `--editor 경로/Editor/Unity.exe`를 지정한다.

## 동작

- Unity는 `/api/config`의 실제 장비 ID·공정 경로·분기를 읽어 3D 장면을 만든다.
- `/api/state`를 약 0.5초 간격으로 조회해 장비 상태와 코일 위치를 표시한다.
- 녹색은 가동, 주황은 대기·경고, 빨강은 심각한 고장, 회색은 정지·연결 실패다.
- 구성이 바뀌면 새 구성을 읽어 장면을 다시 만든다. 구성 ID가 다른 상태는 표시하지 않는다.
- 통신 실패 시 이전 상태를 회색으로 바꾸고 코일을 숨긴다.
- PDA/카메라가 MES에 등록한 최신 설비 인식 결과를 `/api/equipment/scan/recent?limit=1`로 읽어 선택 표시한다.
- 장비 클릭 후 **Open this equipment on PDA**를 누르면 해당 ID의 PDA 장비 화면을 연다.
  이 선택은 수동 선택으로 처리하며 카메라 인식 기록을 생성하지 않는다.
- Start/Pause/Resume은 기존 MES 제어 API를 사용한다.
- 고장 시나리오는 **Open MES dashboard / fault scenarios**에서 적용한다.
- 마우스 오른쪽 드래그로 회전하고 휠로 확대한다.

PDA의 직접 장비 선택은 서버에 저장되는 이벤트가 아니므로 Unity로 자동 전송되지 않는다.
카메라 인식 결과는 두 화면이 동일한 MES 기록을 읽는다.
모든 공정 값과 3D 모형은 프로젝트의 합성 MES 시연용이다.

## 검증

```powershell
node tests/unity_pda_link.cjs
python -B -m unittest tests.test_unity_mes tests.test_communication_integration -v
python -B -c "from tests.test_unity_mes import write_fixtures; write_fixtures()"
& 'D:/obsd/Unity/Editors/6000.3.12f1/Editor/Unity.exe' -batchmode -force-d3d11 -projectPath 'D:/obsd/Projects/ShiftLink/unity/ShiftLinkFactory' -executeMethod FactoryChecks.Run -logFile 'D:/obsd/Projects/ShiftLink/unity/ShiftLinkFactory/Checks/editor-check.log'
```

`FactoryChecks.Run` 검증은 JSON 계약, 상태 색상, 전체 장비, 코일, PDA 인식, 연결 단절 표시를 확인하고 장면을 저장한다.
`FactoryChecks.PlayCheck`는 별도로 실행 중인 로컬 MES에 가동 상태와 진단용 스캔이 있을 때 실제 Unity HTTP 연결을 확인한다.
결과와 렌더링 이미지는 Git 제외 폴더 `Checks/`에 저장한다.

2026-10-06: Unity Editor 설치 성공(exit 0)을 확인했다. Python/Node 연동 검증, 실제 Unity C# 컴파일, 장비 10대·6종 모형 렌더링, 잘못된 구성·스캔 입력 검증이 통과했다.
실제 Play Mode에서 임시 MES/PDA HTTP 서버를 연결했고 MES sequence 증가·코일·PDA 인식 장비 선택을 확인했다.
실제 Pi/Jetson 하드웨어 연결은 별도 검증이 필요하다.

실시간 검증 명령:

```powershell
python -B scripts/check_unity_live.py
```

실행 중 MES/PDA 주소는 화면에서 확인할 수 있다. 주소 변경은 실행 스크립트의 `--mes-url`, `--pda-url` 또는 Play Mode 시작 전 Inspector에서 설정한다.
현재 기본 장면은 `Assets/Scenes/Factory.unity`다. 렌더링 결과는 `Checks/live-factory.png`에서 확인한다.

## 공장 현황 디스플레이

공장 왼쪽 대형 화면에서 주경로·분기, 코일 수, 장비별 가동·대기·경고 상태와 MES 연결 상태를 확인한다.
우측 상단 **현황 디스플레이 확대** 버튼으로 같은 정보를 크게 볼 수 있다. 연결이 끊기면 이전 실시간 수치를 숨긴다.

검증 메서드: `FactoryMonitorChecks.Run`. 결과는 `Checks/monitor-check-result.txt`, 화면은 `Checks/monitor-front.png`에 저장한다.

## Jetson 실제 MES 연결

현재 확인한 MES 주소는 `http://jetson-06:8000`(Tailscale IP: `100.115.59.4`)이다.
실제 연결에는 `--mes-url http://jetson-06:8000`을 지정한다. 인자 없는 실행은 로컬 시연 서버를 시작한다.
`FactoryChecks.OpenDemo`는 Unity의 HTTP 허용을 개발 환경으로 설정한다.
Jetson 연결 검증 메서드는 `FactoryJetsonChecks.Run`이며, 서버에 제어·인식 데이터를 전송하지 않고 상태 갱신만 확인한다.
