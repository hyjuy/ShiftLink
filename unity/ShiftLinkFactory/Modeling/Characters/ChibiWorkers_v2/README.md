# ShiftLink chibi workers v2

2026-10-23 사용자 제공 SD 작업자 일러스트를 기준으로 만든 남녀 3D 원본과 Unity 남성 작업자 연결본.
큰 머리, 짧은 팔다리, 점눈과 미소, 노란 안전모, 남색·청록색 작업복을 표현한다.

## 편집용 원본

- `ChibiWorkers_TPose.blend`: 남녀 22본 리그와 별도 PDA, T 포즈.
- `ChibiWorkers_Presentation.blend`: Blender 검토 포즈와 조명.
- `ChibiWorkers_Preview.png`: Blender 렌더. 게임 중 동작의 캡처는 아니다.
- `build_chibi_workers.py`: 원본/FBX/렌더 재생성.
- `verify_fbx.py`, `validation.json`, `fbx_validation.json`: FBX 재수입·크기·UV·본 변형 검사.
- FBX 위치: `../../../Assets/Models/Characters/ChibiWorkers_v2/`.

원본은 남성 34,908 / 여성 36,140 triangles, 각각 22본, 재질 9개, 높이 약 1.719 m다.
Blender는 Z up/-Y 전방이며 FBX는 Y up/-Z 전방으로 내보냈다.

## Unity 연결

`Assets/Editor/FactoryWorkerAssetBuilder.cs`가 FBX의 단위·전방 축을 맞추고
`Assets/Resources/Factory/WorkerMale.prefab`을 자동 생성한다. 필요하면
Unity 메뉴 대신 `FactoryWorkerAssetBuilder.Prepare`를 executeMethod로 실행할 수 있다.
FBX는 Generic, importAnimation=false, optimizeGameObjects=false 설정으로 본을 보존한다.

`FactoryWorker.cs`가 기본 도형 대신 이 남성 프리팹을 사용한다.
`FactoryWorkerVisual.cs`는 외부 패키지나 Animator Controller 없이 본을 직접 움직여
대기/걷기/달리기/점프/촬영 자세와 짧은 셔터 반응을 만든다.
이동 속도·중력·충돌·점프는 기존 CharacterController 경로를 사용한다.
PDA 모드에서는 기존처럼 이동을 막으며 카메라는 소품의 PhotoLens 위치를 따른다.
촬영 이미지에서는 자기 캐릭터를 제외하고 기존 PNG·JSON 저장 기능을 유지한다.

윤곽선과 팔레트는 `Assets/Models/Characters/ChibiWorkers_v2/WorkerToon.shader`와
같은 폴더의 `Materials/`를 사용한다. Blender Freestyle 효과를 그대로 가져온 것은 아니다.
프리팹은 약 1.72 m로 맞추며 모델 교체 후에도 자동 정규화한다.

조작: F 현장 모드, WASD 이동, Shift 달리기, Space 점프, V 1/3인칭 전환,
P PDA 열기/닫기, PDA 상태에서 Space/Enter 또는 촬영 버튼, 사진 저장 버튼.
3인칭에서는 촬영 자세도 표시하며 1인칭은 얼굴·안전모가 시야를 가리지 않게 숨긴다.

## 검사와 남은 범위

Unity 검사: `FactoryWorkerVisualChecks.Run`, `FactoryWorkerVisualChecks.RunPlay`,
기존 `FactoryWorkerChecks.RunMovement` 및 `FactoryWorkerChecks.Run`.
관련 증거는 저장소 루트 `artifacts/unity-chibi-worker-20261023/`에 둔다.

원본 FBX에는 애니메이션 클립이 없다. 게임 동작은 실행 중 본 제어다.
개별 손가락·표정·Humanoid 리타게팅, 여성의 플레이어 선택, 새 멀티플레이 동작 동기화는 포함하지 않는다.
최종 리토폴로지·재질 atlas·LOD는 이후 최적화 범위다.

## PR 분리 검증

최신 main에서 이번 Unity 파일만 적용한 별도 작업 공간에서도 모델/자세/촬영 통합 42개와
실제 Play Mode 상태/프레임/사진 저장 11개 검사를 통과했다.
검사 재현은 Unity 6000.3.12f1에서 `-executeMethod FactoryWorkerVisualChecks.Run --chibi-play`를 사용한다.
