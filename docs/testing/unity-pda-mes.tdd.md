# Unity · PDA · MES 구현 검증

사용자 요청: 현재 SSD에 Unity를 저장하고 PDA 통신·3D 공장 시연·MES 연동을 구현한다.
추가 요청: Unity 공장 구현 전문가 에이전트를 활용해 기본 코드를 구성한다.
별도 계획 파일 없이 대화에서 확정한 요구사항을 기준으로 했다.

## 구현

- `FactoryDemo.cs`: MES 구성 기반 장비 10대, 6종 구분 모형, 주경로·분기, 코일·장비 상태 표시.
- MES config/state ID 일치 검증, 중복·비활성 route, 자기 branch, 중복 coil 거부.
- null/빈 PDA scan 필드 무시. PDA 인식의 equipment_id 강조.
- Unity 장비 선택으로 동일 ID의 PDA 화면을 연다.
- Start/Pause/Resume, 궤도 카메라, 확대. UI 클릭은 3D 선택으로 전달하지 않는다.
- `Factory.unity` 및 Unity 기본 설정·meta 파일을 생성했다.
- `run_unity_demo.py`는 전용 시연 DB로 MES/PDA/Unity를 실행한다.
- `check_unity_live.py`는 임시 MES/PDA 서버와 Unity Play Mode를 실제 연결한다.

## RED / GREEN 근거

- 최초 RED: `node tests/unity_pda_link.cjs` → `TypeError: equipmentFromLink is not a function`.
- 최초 RED 체크포인트: `32e4bf7`.
- 최초 GREEN: 같은 Node 테스트·JavaScript 문법 검사 통과, 체크포인트 `471dc4c`.
- 공장 입력 RED: 실제 Unity `FactoryChecks.Run` exit 1 → `Exception: duplicate route must be rejected`.
- 공장 RED 체크포인트: `a0acdef`.
- 전문 에이전트가 FactoryDemo.cs의 입력 검증 및 6종 모형을 수정했다.
- 공장 GREEN: 실제 Unity `FactoryChecks.Run` exit 0, `SHIFTLink FACTORY CHECKS PASS`.
- 라이브 GREEN: 실제 Unity Play Mode exit 0, `SHIFTLINK LIVE PLAY CHECK PASS`.
  임시 PDA 프록시를 통해 GR 인식을 등록했고 Unity가 `EQ-0004`를 선택했다.
  첫 관측 이후 MES sequence 증가를 확인했다. 첫 라이브 종료 시 MES sequence는 48이었다.
- Python HTTP 통합 검증 4개 통과.
- PDA/MES 관련 pytest 10개 통과.
- Node 장비 링크 테스트·기존 MES query PDA 계약·문법 검사 통과.

## 결과 파일

Git 제외 `unity/ShiftLinkFactory/Checks/`에 로그, 검증 JSON, 실제 렌더링 이미지를 저장한다.

- `editor-red.log`: 오류 재현.
- `editor-green.log`, `unity-check-result.txt`: 구성·색상·장비·코일·잘못된 스캔·연결 단절 검증.
- `live-check.log`, `live-check.json`, `play-check-result.txt`: 실제 Play Mode 통신.
- `fixture-factory.png`, `live-factory.png`: 실제 Unity 렌더링.

## 환경과 제한

- 저장소·프로젝트: D: Samsung T7 SSD, exFAT.
- Editor: `D:/obsd/Unity/Editors/6000.3.12f1/Editor/Unity.exe`.
- 공식 설치 파일의 서명 Valid 및 최종 설치 exit 0을 확인했다.
- 첫 라이브 실행에서 UnityEditor.Search.SearchDatabase 초기화의 `ArgumentOutOfRangeException`이 1회 발생했다.
  스택에 공장 코드가 없었고 이후 Play Mode 검증과 렌더링은 통과했다. 최종 재실행에서도 같은 Unity 내부 검색 인덱스 예외가 발생했다. 공장 런타임 예외는 기록되지 않았다.
- 실제 Pi/Jetson 하드웨어·웹캠 인식은 검증하지 않았다. HTTP 인식 메시지는 진단용으로 생성했다.
- Unity 코드의 수치 커버리지는 측정하지 않았다.
- 다른 작업의 Git 변경은 수정하거나 함께 커밋하지 않는다.

최종 라이브 재검증: Unity exit 0, MES sequence 84, GR 스캔 EQ-0004 선택, 실제 렌더링 저장 확인. 서버 주소 표시와 UI 클릭 차단 수정 후 실행했다.
