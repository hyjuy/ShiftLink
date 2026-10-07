# Unity 직원·PDA 촬영·YOLO 데이터셋 — 2026-10-07

사용자 요청: Unity 가상 공장 안에서 직원이 PDA를 들고 이동·촬영하고 사진을 장비 인식 학습 데이터로 저장한다.
후속 결정: 신규 파이프라인은 YOLO 하나만 사용한다. 기존 CNN 코드는 수정하지 않는다.
이번 구현 범위는 직원·촬영·정답 저장·YOLO 변환이다. 학습·사진 추론·실제 장비 개체 확정은 후속 작업이다.

## 구현 및 검증

| 보장 | 검증 | 결과 |
|---|---|---|
| 직원 초기화·이동·실제 벽 충돌·관찰 복귀 | `FactoryWorkerChecks.Run` | PASS |
| 직원 촬영은 벽·지붕이 있는 환경을 사용하고 cutaway의 물리 벽도 유지 | 같은 Editor 검사 | PASS |
| 카메라 원본·미리보기·PNG/JSON 쌍·고유 ID·반복 저장 | 같은 Editor 검사 | PASS |
| 손상된 저장 파일을 성공 처리하지 않음·저장 오류 후 재시도 | 같은 Editor 검사 | PASS |
| 디스크 갤러리 복원·실시간 PDA 카메라 렌더 | 같은 Editor 검사 | PASS |
| 완전 가림은 라벨 제외·부분 노출은 visible bbox·좌상단/exclusive 좌표 | 같은 Editor 검사 | PASS |
| 객체 마스크 이후 원본 재질 복원·장비 없는 음성 사진 | 같은 Editor 검사 | PASS |
| 실제 Play Mode PDA 입력 격리·미리보기·촬영/저장·disable 복귀 | 같은 메서드의 Play Mode 후속 검사 | PASS |
| 잘못된 PNG/JSON/class/bbox 차단, 음성 라벨, 누수 방지 그룹, CLI | `python -B -m unittest tests.test_unity_dataset -v` | 8 tests PASS |
| 실제 Unity 저장 PNG/JSON을 YOLO로 변환 | `python -B -m shiftlink.vision.unity_dataset --captures unity/ShiftLinkFactory/Checks/worker-captures-b12f19bc789f44e3be48e010a5fb5ce1 --out data/vision/unity-yolo-smoke-20261007` | 3 photos PASS; train=3, val=0, test=0 경고 |
| 기존 MES/PDA 인식·제어 계약 | `uv run --python 3.13 --with pydantic==2.9.2 python -B -m unittest tests.test_unity_mes -v` | 1 test PASS |
| 기존 Unity→PDA 설비 링크 | `node tests/unity_pda_link.cjs` | PASS |

Unity 검증 명령:

```powershell
& 'D:/obsd/Unity/Editors/6000.3.12f1/Editor/Unity.exe' -batchmode -force-d3d11 -projectPath 'D:/obsd/Projects/ShiftLink/unity/ShiftLinkFactory' -executeMethod FactoryWorkerChecks.Run -logFile 'D:/obsd/Projects/ShiftLink/unity/ShiftLinkFactory/Checks/worker-red.log'
```

최종 Editor 검사는 33개 조건을 통과했다. `Checks/worker-check-result.txt` 및 `worker-play-check-result.txt`에 결과를 남긴다.
Play Mode 검사는 로컬 fixture를 사용하고 MES 서버에 접속·제어하지 않는다.
검사 로그·사진·데이터셋은 Git 제외 폴더에 보관한다.
`worker-pda-capture.png`, `worker-character.png`를 직접 열어 원본 사진과 기본 직원 모형을 확인했다.

## TDD 근거

- Exporter RED: `ModuleNotFoundError: No module named 'shiftlink.vision.unity_dataset'`. 체크포인트 `9da5ec0`.
- Unity runtime RED: `Exception: employee and PDA capture components must exist`. 체크포인트 `a3a1796`.
- Exporter GREEN: unittest 8개 PASS. 체크포인트 `167d80d`.
- Unity 초기 GREEN: 실제 C# 컴파일 및 26개 촬영·이동 검사 PASS. 체크포인트 `bb1dca0`.
- 이후 미리보기·갤러리·저장 검증·동작 중단 복귀를 보강하고 33개 Editor 조건과 실제 Play Mode 검사를 재실행하여 PASS.
- Exporter stdlib trace line coverage는 90.3%(154개 실행 대상 줄). 산출물 `artifacts/unity-dataset-coverage/`.
- Unity C# 수치 커버리지는 측정하지 않았다. 80% 이상이라는 주장은 하지 않는다.

체크포인트는 공유 작업트리의 현재 브랜치에서 생성했다.
작업 도중 다른 세션의 브랜치 변경·파일 수정이 있었으며, 본 작업 커밋에는 직원/촬영/exporter 관련 파일만 포함했다.
다른 세션의 MES·PDA·실행 스크립트 변경은 수정하거나 되돌리지 않았다.

## 제한과 후속 작업

- 직원은 Unity 기본 도형으로 만든 기능 검증용 모형이다. 정식 캐릭터 자산·리깅은 아직 적용하지 않았다.
- 단일 공장 preset만으로 모델 학습·일반화 평가를 수행하지 않았다. 독립 배치·환경과 클래스별 충분한 데이터 수집이 필요하다.
- 그룹 단위 70/15/15 해시 분할이므로 실제 개수 비율은 정확히 일치하지 않는다. 현재 고정 `sceneId`의 사진은 한 split로 묶일 수 있다.
- 학습된 YOLO 모델·사진 추론 API·개별 설비 ID 확인은 미구현이다. 정답 ID를 추론 결과로 쓰지 않는다.
- 최종 기기에서 FPS·지속 성능·p50/p95·장시간 안정성을 측정하지 않았다. MX150 Editor에서 마지막 640×360 촬영+저장 1회는 113ms였다. 모델 추론 지연이나 SLA 수치가 아니다.
- 자동 Play Mode 검사에서 `ScreenCapture.CaptureScreenshot`로 HUD 사진이 생성되지 않아 UI 전체의 시각 QA는 남아 있다. 한국어 OS 폰트와 갤러리 스크롤을 적용했지만 실제 1280×720 조작 화면을 수동 확인해야 한다.
- Play Mode 전환 시 기존 문서에도 기록된 `UnityEditor.Search.SearchDatabase` 내부 `ArgumentOutOfRangeException`이 발생했다. 스택에는 신규 직원 코드가 없으며 이후 기능 검사는 통과했다.
- 기본 Python 3.14에서는 기존 pydantic 의존성이 맞지 않았다. 격리된 Python 3.13 + 저장소 지정 `pydantic==2.9.2`로 기존 HTTP 계약 검사는 통과했다.
