# ShiftLink 3D 공장 · MES · PDA 시연

## 공정별 상세 모델·센서 모션 (2026-10-07)

기존 6종·10대 장비의 외형을 공정용 참고제품군에 맞춰 제작했다. HPU는 Bosch ABPAC,
GR은 SEW X 계열, RT는 Butech Bliss 코일·판재 런아웃, CV는 Mayfran 강재 벨트,
PDP는 ABB MNS, CAU는 밀폐형 Atlas Copco GA 외형을 참고했다.
CV-02는 별도 힌지 강재 벨트 모델이며 RT-02는 롤러 16개와 양쪽 베어링 덮개를 갖는다.
제조사 사진을 바탕으로 한 공정 맞춤 모델이다. 설치 모델의 정확한 CAD나 정격 검증 결과는 아니다.
4.8 m 이송 구간·기존 접속점에 맞춘 치수, 클램프·승강·텐셔너·디버터 형상은 제작 가정이다.
MES의 장비 ID·공급/공유 구동 관계·코일/스크랩 데이터 의미를 유지한다.

실물감을 높이기 위해 유압장치의 탱크 상판·플랜지·굽은 배관과 피팅,
감속기의 모터 받침·팬 그릴·주물 리브, 이송장치의 절곡 프레임·베어링 체결부·장력 조절나사·슈트 측판을 보완했다.
배전반에는 얇은 문 패널·이음·체결부, 공압장치에는 서비스 패널·흡기 루버·배기 플랜지를 추가했다.
도장면·가공 금속·고무는 금속성과 거칠기를 달리하며, 압력계에는 눈금을 넣었다.
베어링 체결부는 커버를 따라 움직이고 배전반 문 부품은 해당 힌지에 묶인다.
RT-01·RT-02·RT-03의 상부 가로빔·클램프는 코일과 받침을 포함한 상단 2.58 m를 기준으로 높였다.
클램프 턱 중심은 2.795 m이며, 시연 최대 하강 0.06 m에서도 코일 위에 0.10 m 간격이 남는다.
기둥 하단·롤러 이송면·입출력 앵커는 유지하고 상부 실린더와 배관은 가로빔 높이에 맞췄다.
Unity 검사는 실제 코일 자산을 RT 세 대의 경로 다섯 지점에 배치해 정지 위치와 최대 하강 위치의 간격을 확인한다.

라인 내부 코일은 두 개의 러너·가로보·V 받침을 갖춘 팔레트째 이동한다.
[SMS/AMOVA 팔레트 이송 설명](https://www.sms-group.com/en-cz/plants/logistics-systems)의
롤러 테이블 위 고정 코일 운반 방식을 참고했으며, 치수는 기존 시연 코일에 맞췄다.
[Meccaniche NT 실제 컨베이어 사진](https://www.meccanichent.com/impianti-per-il-trasporto-bobine.php)도
롤러와 이송 통로 구조 비교에 사용했다. 사진 속 제품 자세는 현재 시연 코일과 다르다.
출발·도착 장비의 운전 상태와 유효한 속도 계측을 확인해 이송하며, 정지·품질 보류 시 멈춘다.
CV-02와 분기 슈트의 시야를 가리는 측판은 시연 화면에서 제거했다.
불량 배출은 CV-02 끝단 이송→슈트→수거함 낙하·적치로 표시한다.
MES 시나리오 목록에서 `시연 불량 판정 · RT-03→CV-02 스크랩 배출`(`scrap_discharge`)을 선택하면
RT-03 끝단에서 합성 불량 판정을 기록하고 구성된 CV-02 분기로 보낸다.
CV-02가 정지하거나 가득 차면 기다리며, 품질 보류 제품은 그대로 보류한다.
판재는 스크랩 흐름을 보여 주는 시연 형상이며, 실제 코일 절단 공정은 모델링하지 않았다.
창고·트럭 이송은 이번 변경 범위에 포함하지 않는다.
검증: MES 관련 135개 검사와 하위 검사 6개, Unity의 105개 시나리오·7,245개 센서 상태 검사 및
팔레트 접촉·클램프 간격·배출 수거·정지/재개·초기화 검사가 통과했다.
시각적 적치는 최대 20층이며 누적 배출 개수는 별도로 유지한다.

`Assets/Models/EquipmentTypes/process-motion-map.json`에 장비별 참고제품 URL,
센서 69개, 정상 범위, 관측 페르소나, 실제 계측 기반 모션과 시연 모션을 기록했다.
Unity에서는 장비 선택 시 센서 값·상태와 합성 관찰 문구를 보여 준다.
센서 표시등은 정상 녹색, 범위 이탈 시 주황색 맥동, 확인 불가 회색이다.
촬영 데이터에서 이 설명용 표시등은 제외한다.

- 계측 기반: 롤러/벨트 속도, GR 지정 구동축 RPM, 압력계 바늘, 유면계, 차단기 트립 표시.
- 시연 표현: 과진동 변위·누유 표시, 소재가 있는 클램프/승강 주기, 장력 조절기 변위, 공압 디버터 주기.
- 페르소나: `seeds/personas_v0.1.yaml`의 V-11 한 조장(공급·구동 우선), V-12 오 기사(이송·계측 대조), V-13 윤 주임(정비 기록 대조).
  계측 사실과 물리 모션은 페르소나에 따라 바꾸지 않는다. 없는 감각 관측·정비 이력·승인 기록을 생성하지 않는다.
- 정상 범위는 실제 MES 구성에서 읽는다. 축압기 프리차지는 별도 측정 모드(가스 130–140 bar, 유체·매니폴드 0 bar)로 구분한다.
  단위 불일치·불량 품질·NaN·무한대·음수·미수신 계측은 모션 근거로 사용하지 않는다.
  일시정지·정지·대기·중대 고장에서는 해당 기계 모션을 멈추고, 통신 단절 시 계측 표현을 초기화한다.

후속 보완은 모션 상태 전환 → 계측·페르소나 표시 → 벨트 부품 동반 이동 → Unity 통합 검증 순서로 적용했다.
강재 벨트의 슬랫·힌지 핀·클리트는 현재 속도와 프레임 간격으로 이동량을 누적하며,
각 시연 주기는 해당 장비가 가동한 시간만 사용한다.
디버터는 공압 공급원과 대상 컨베이어가 모두 가동 중이어야 움직인다.
클램프·승강부는 가동 중 소재가 없으면 시연 원점으로 돌아간다. 이는 실물 위치 측정이나 복귀 명령이 아니다.
진동 저값은 표시등으로 구분하고 과진동 흔들림은 상한 초과에서만 표현한다.
관찰 요약은 정지 영값과 가동 정상 범위를 구분하고, 이상값과 함께 미확인 계측도 남긴다.
계측 목록에는 MES의 연속 계측·시료·완료 이벤트·산출값 구분과 관측 시각을 표시한다.
관측 시각이 없으면 미확인으로 남기며, 시료·완료 이벤트를 현재의 연속 계측으로 단정하지 않는다.

편집 파일과 정면·측면·사선 미리보기는 `Modeling/EquipmentTypes/`에 있다.
이번 제작 도구는 로컬 Blender 5.2.2 LTS다. 이전 공동 작업 기준 4.5.15에서의 `.blend` 호환성은 확인하지 않았다.
FBX는 Unity 6000.3.12f1에 가져와 검사했다.

재생성 순서(프로젝트 루트):

```powershell
& 'D:/obsd/Tools/Blender/blender.exe' --background --python-exit-code 1 --python scripts/build_process_equipment.py
& 'D:/obsd/Tools/Blender/blender.exe' --background --python-exit-code 1 --python scripts/export_process_native.py
& 'D:/obsd/Tools/Blender/blender.exe' --background --python-exit-code 1 --python scripts/check_process_equipment.py
python -B -c "from tests.test_unity_mes import write_fixtures; write_fixtures()"
python -B scripts/write_sensor_motion_fixtures.py
& 'D:/obsd/Unity/Editors/6000.3.12f1/Editor/Unity.exe' -batchmode -force-d3d11 -projectPath unity/ShiftLinkFactory -executeMethod FactorySensorMotionChecks.Run -logFile tmp/process-sensor-unity-full.log
```

Python 검사 입력 생성에는 기존 프로젝트 의존성이 필요하다.
모델 검사에서 7개 장비의 UV·재질·법선·FBX 왕복을 확인했고,
Unity 검사에서 실제 MES 104개 시나리오·69개 센서의 7,176개 상태 비교,
RPM·강재 벨트·진동·클램프/승강 방향·유면계·경계값·품질/단위 오류·정지/단절을 확인했다.
후속 검사에는 벨트 속도 변경·개별 장비 대기/고장 후 재개·부품 동반 이동,
디버터 대상 장비 정지·승강 주기·소재 없는 시연 원점 복귀·저진동,
정지 영값/미확인 관찰 요약·계측 방식·관측 시각 보존 및 누락도 포함한다.
검사 결과는 `Checks/sensor-motion-result.txt`, 모델 결과는 `Modeling/EquipmentTypes/process-validation.json`이다.
장비별 정상/이상 비교 화면은 `Checks/process-{normal,abnormal}-EQ-*.png`에 저장한다.

공장 외벽·지붕·철골과 천장 LED 12개, 외부 LED 4개를 설치했다.
시작 화면에서 **View factory interior**로 내부를 확인하고 **View factory exterior**로 외관 보기로 돌아간다.
배치·보행 공간·외관·조명 검증은 `docs/testing/unity-factory-layout-20261006.tdd.md`에 기록했다.

프로젝트 경로: `D:/obsd/Projects/ShiftLink/unity/ShiftLinkFactory`.
Unity 버전은 6000.3.12f1, Built-in Render Pipeline이다. 장비 프리팹과 FactoryRig로 공장 장비와 이송 구간을 구성한다.

## 직원 이동 · PDA 촬영 (2026-10-07)

공장 화면의 `Walk as employee / PDA camera [F]` 또는 F로 직원 모드에 들어간다.
기본 직원 모형은 작업복·안전모·손에 든 PDA로 구성했다.

| 조작 | 동작 |
|---|---|
| WASD / 마우스 | 이동 / 시점 조정 |
| V | 직원 1인칭·3인칭 전환 |
| P | PDA 열기·닫기 |
| Space / Enter | PDA 카메라 화면에서 촬영 |
| 사진 저장 / 다시 촬영 | PNG·촬영정보 저장 / 미리보기 교체 |
| 사진 보관함 | 디스크에 저장된 사진 다시 열기 |
| F | PDA가 닫힌 상태에서 공장 관찰 화면으로 복귀 |

PDA를 열면 이동·시점 조작을 멈춘다. 카메라 미리보기는 실제 PDA 렌즈의 시점이다.
직원 모드에서는 공장 외벽·지붕을 유지하고 관찰 화면의 내부 보기에서는 외관을 숨긴다.
물리 벽은 두 보기 모두 유지한다.

사진은 기본적으로 `Application.persistentDataPath/ShiftLinkCaptures`에 PNG·JSON 쌍으로 저장한다.
Unity Inspector의 `FactoryCapture.outputDirectory`로 저장 위치를 지정할 수 있다.
저장 성공 메시지에는 실제 경로를 표시한다. 기본 해상도는 1280×720이다.
촬영 ID는 UUID이며 이미지·정보 모두 저장된 뒤에만 성공을 표시한다.
저장 실패 시 사진을 유지하고 다시 저장할 수 있다. 사진 원본에는 HUD·설명용 설비 코드·직원/PDA 모형을 넣지 않는다.

JSON에는 카메라 위치·회전·FOV, 촬영 세션·공장 preset·seed, MES 구성/운전/sequence,
객체별 종류·설비 ID·보이는 영역의 정답 상자를 기록한다.
상자는 동일 프레임의 객체 ID 마스크에서 생성하며 좌표는 좌상단 기준 `xmin,ymin,xmax,ymax`이고 최대 경계는 exclusive다.
클래스 순서는 `HPU`, `GR`, `RT`, `CV`, `CAU`, `PDP`로 고정한다.

이번 신규 인식 경로는 **YOLO 하나**를 대상으로 한다. 아직 학습된 모델과 사진 추론은 연결하지 않았다.
정답 설비 ID는 학습·평가용 정보이며 모델 예측으로 표시하지 않는다.

촬영 데이터의 YOLO 변환:

```powershell
python -B -m shiftlink.vision.unity_dataset --captures CAPTURES_PATH --out NEW_DATASET_PATH
```

출력은 `images/{train,val,test}`, `labels/{train,val,test}`, `data.yaml`, `manifest.jsonl`이다.
새 출력 폴더를 지정해야 한다. 원본 폴더 안에 출력하거나 기존 데이터셋을 덮어쓰지 않는다.
동일 scene·session·이미지 해시를 공유하는 사진은 같은 그룹에 넣는다.
현재 기본 `sceneId=factory-default`만 촬영하면 한 split만 생길 수 있으므로 독립적인 실제 배치·환경 preset을 먼저 준비해야 한다.
검증·테스트 세트를 만들기 위해 같은 배치의 ID만 바꾸면 안 된다.

로컬 기본 Python의 의존성이 맞지 않으면 기존 설치된 Python 3.13의 격리 환경으로 시연할 수 있다:

```powershell
uv run --python 3.13 --with pydantic==2.9.2 python -B scripts/run_unity_demo.py --editor D:/obsd/Unity/Editors/6000.3.12f1/Editor/Unity.exe
```

검증과 남은 범위는 [직원/PDA 촬영 검증 기록](../../docs/testing/unity-worker-capture-20261007.tdd.md)에 기록했다.

## 확장 공정과 반출·적재

MES 공정 뒤에 가상 풀림·교정·슬리팅·재권취·검사·포장 라인을 연결하고 32×34m 생산동, 원자재 야드·크레인, 코일 보관대 24칸과 출하 트럭 8칸을 추가했다. 내부 보기에서 전체 공정을 확인한다.

화면 오른쪽 아래에서 `Send next finished coils to truck`을 선택하면 새 반출 코일을 트럭으로 보내며, 기본 목적지는 보관장이다. `Load stored coils`로 보관 코일을 트럭에 싣고, `Dispatch loaded truck`으로 출하한다. 만재 시 보관 또는 대기로 전환한다.

후단 설비와 재고는 Unity 세션의 가상 시연이다. MES 설비·재고를 등록하거나 실제 출하 지시를 보내지 않는다. 연결 해제·새 운전·구성 변경 때 가상 재고를 초기화한다. 검증과 제한 사항은 `docs/testing/unity-factory-logistics-20261006.tdd.md`에 기록했다.

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

Unity에서 설비를 클릭하면 `POST /api/equipment/select`로 선택을 전달한다.
라즈베리파이 PDA는 기존 `/api/state` 조회(3초 주기)의 `unity_selection`을 받아 해당 설비 화면을 연다.
로그인·얼굴 확인 중에는 선택을 보관하고 로그인 후 적용한다. 수동 선택은 카메라 인식 기록을 만들지 않는다.
설비가 바뀌면 이전 설비의 관측·답변 컨텍스트를 초기화한다. MES 실행이나 구성이 바뀐 선택은 적용하지 않는다.
선택은 메모리에만 보관하며 MES 재시작 시 사라진다. 현재 단일 PDA를 대상으로 한다.

```powershell
python -B scripts/run_unity_demo.py --editor D:/obsd/Unity/Editors/6000.3.12f1/Editor/Unity.exe --mes-url http://jetson-06:8000
```

실제 선택 전송 검증은 `FactorySelectionChecks.Run`으로 수행한다. 이 검증은 MES에
`EQ-0004`, `EQ-0005`를 선택하고 마지막 선택이 전달되는지 확인하며 공정 제어는 하지 않는다.

현재 확인한 MES 주소는 `http://jetson-06:8000`(Tailscale IP: `100.115.59.4`)이다.
실제 연결에는 `--mes-url http://jetson-06:8000`을 지정한다. 인자 없는 실행은 로컬 시연 서버를 시작한다.
`FactoryChecks.OpenDemo`는 Unity의 HTTP 허용을 개발 환경으로 설정한다.
Jetson 연결 검증 메서드는 `FactoryJetsonChecks.Run`이며, 서버에 제어·인식 데이터를 전송하지 않고 상태 갱신만 확인한다.
