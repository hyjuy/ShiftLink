# Unity 연결부 겹침 수정

사용자가 지적한 문제는 Unity 설비 사이 연결부의 시각적 겹침이다. MES 배포 상태와 별도로 `FactoryRig.Build`에서 생성한 연결부 좌표를 확인했다. 별도 계획 파일 없이 현재 10대 설비 구성의 연결부를 테스트로 옮겼다.

## 원인과 수정

- 감속기 하나가 두 설비를 구동할 때 같은 출력 포트에 `Connection_FlexibleCoupling`과 `Connection_ShaftGuard`를 두 번 생성했다. 공용 출력 부품은 감속기마다 한 번만 생성한다.
- 유압 공급·리턴 8개 경로와 전원 케이블 3개 경로가 공용 좌표 구간을 중복 사용했다. 개별 경로에 포트와 높이 간격을 둔다.
- 높이만 분리하면 기존 대각선 경로가 다른 배관과 교차했다. 유압관은 수직 상승·수평 배관·수직 하강으로 연결하고 공급·리턴 포트를 분리한다. 유압관 높이는 2.26~2.88m로 기존 보행 공간 위, CAU 플랫폼 아래에 둔다. 케이블도 분기마다 높이를 구분한다.
- 장비 ID·MES 관계·자재 이송 경로는 바꾸지 않았다. 기존 미커밋 장비 디테일·모션 수정은 유지했고 이 작업 커밋에 포함하지 않았다.

## RED / GREEN

| 단계 | 실제 실행 결과 | 체크포인트 |
|---|---|---|
| 공용 부품 중복·평행 유틸리티 구간 검사 RED | 30건: 부품 중복 4건, 배관·케이블 구간 겹침 26건 | `be76e5f` |
| 공용 부품 재사용과 경로 분리 GREEN | 동일 검사 PASS | `a4fafc7` |
| 선분 간 실제 거리로 교차 검사 확장 RED | 대각선 경로의 교차·관통 12건 | `718b653` |
| 직교 유압 배관·케이블 높이 분리 GREEN | 중복·평행 겹침·교차 검사 PASS | `9fe6399` |

`FactoryConnectionChecks.Run`은 연결 프리팹의 중복 위치와 유압·공압·전원 선분 사이의 최단 거리를 실제 Unity 좌표와 렌더 폭으로 확인한다. 의도된 부품 조립 접합을 전부 충돌로 분류하는 검사는 아니다. 현재 합성 시연 구성의 연결부 검증이며 실장비 배관 도면과 대조하지 않았다. Unity 커버리지 계측은 수행하지 않았다.

검증 명령은 숨김 배치 모드로 아래 메서드를 실행한다.

```powershell
Start-Process -FilePath 'D:/obsd/Unity/Editors/6000.3.12f1/Editor/Unity.exe' -ArgumentList '-batchmode -force-d3d11 -projectPath D:/obsd/Projects/ShiftLink/unity/ShiftLinkFactory -executeMethod FactoryConnectionChecks.Run -logFile D:/obsd/Projects/ShiftLink/tmp/connection-final.log' -WindowStyle Hidden -PassThru -Wait
```

최종 회귀 검사 3개는 모두 종료 코드 0이었다.

| 메서드 | 실제 보장 | 결과 |
|---|---|---|
| `FactoryConnectionChecks.Run` | 연결 프리팹 중복 없음, 유압·공압·전원 경로 사이 겹침·교차 없음 | PASS |
| `FactoryLayoutChecks.Run` | 기존 설비 여유 공간, CAU 플랫폼, 보행 통로, 배관의 타 설비 침범 방지, 자재 이송 속도 | PASS |
| `FactoryMotionChecks.Run` | 기존 롤러·팬 모션과 정지·대기·고장·통신 단절 처리, 코일 유지·이송 | PASS |

로그는 `tmp/connection-final.log`, `tmp/connection-layout-regression.log`, `tmp/connection-motion-regression.log`에 보존했다. 근접 렌더는 `unity/ShiftLinkFactory/Checks/connection-EQ-*.png`, 원본 실패 목록은 `tmp/connection-red-result.txt`와 `tmp/connection-intersection-red-result.txt`에 보존한다.

현재 열린 Unity는 `.worktrees/unity-map-clearance` 프로젝트를 사용하고 있었다. 그 작업트리가 깨끗함을 확인한 뒤 연결부 수정만 적용했고 해당 생성 코드가 검증한 프로젝트와 같음을 확인했다. 관리자 이동·점프·비행과 맵 충돌 수정은 유지했다. 이 작업트리에는 `FactoryRig.cs` 변경만 미커밋으로 남긴다. 이미 생성된 Play Mode 연결부는 Play를 다시 시작해 재생성해야 한다. 열린 편집기를 종료하거나 Play 상태를 변경하지 않았다.
