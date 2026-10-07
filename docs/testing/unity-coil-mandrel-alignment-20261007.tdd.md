# 큰 코일과 거치 축 중심 정렬

사용자가 지적한 대상은 작은 이송 롤러가 아니라 큰 철강 코일과 코일 거치대다. Unity 권출기(`Decoiler`)와 권취기(`Recoiler`)의 고정 코일에서 동일한 오차를 재현했다.

## 원인과 수정

`Material_Coil`의 원점은 구멍 중심보다 아래에 있다. 기존 `Station reel`의 루트 높이 1.24m에 메시 중심 오프셋 0.74m가 더해져 코일 중심은 1.98m였지만, 거치 축 중심은 1.65m였다. 두 장치 모두 0.33m 어긋났다.

- 고정 코일은 `WoundSheet`의 실제 렌더러 중심을 거치 축 중심에 맞춘다.
- 축 높이는 1.85m로 조정한다. 코일 아래 이송 롤러와 간격은 0.03m다.
- 두 코일 장치의 상부 프레임 높이는 2.7m로 조정한다. 코일 위 간격은 0.075m다.
- 축에 설치된 고정 코일에는 이동용 받침을 생성하지 않는다. 다른 코일은 기존 `CreateLoad` 기본값으로 이동용 받침을 유지한다.
- MES 좌표·속도·이송 상태는 바꾸지 않는다. 관련 없는 기존 수정은 이 작업의 커밋에 포함하지 않는다.

## 요구사항과 검증

| 요구사항 | 실제 검사 |
|---|---|
| 큰 코일 구멍 중심과 거치 축 중심 일치 | `FactoryCoilAlignmentChecks.Run`: 두 장치의 중심 거리 1mm 이내 |
| 정렬 후 주변 부품과 겹치지 않음 | 코일 위 프레임 및 아래 롤러와 최소 1cm 간격 |
| 이송 중 코일의 받침 유지 | 기본 `CreateLoad`의 두 받침과 코일 수평 중심 검사 |
| 창고·출하 흐름 유지 | `FactoryLogisticsChecks.Run`: 기존 이송, 보관, 출하, 용량, 일시정지, 초기화 회귀 검사 |

## RED / GREEN 증거

| 단계 | 결과 | 커밋 |
|---|---|---|
| 중심 검사 RED | 두 장치 모두 0.330000m 오차, 고정 코일에 이동용 받침 존재 | `9ba1f32` |
| 메시 중심 기준 정렬 GREEN | 두 장치 모두 0.000000m 오차 | `e4c516e` |
| 주변 간격 검사 RED | 기존 축 높이로 정렬하면 하부 롤러와 0.170000m 겹침 | `f3781c9` |
| 최종 높이 조정 GREEN | 중심 오차 0, 상부 0.075000m·하부 0.030000m 간격, 배치 검사 종료 코드 0 | 최종 수정 커밋 |

실행기는 Unity 6000.3.12f1의 숨김 배치 모드(`-batchmode -force-d3d11 -executeMethod`)다. 로그는 `tmp/coil-station-red.log`, `tmp/coil-station-green.log`, `tmp/coil-clearance-red.log`, `tmp/coil-final-FactoryCoilAlignmentChecks.Run.log`, `tmp/coil-final-FactoryLogisticsChecks.Run.log`에 남긴다. 최초 실패 결과는 `tmp/coil-station-red-result.txt`, 간격 실패 결과는 `tmp/coil-clearance-red-result.txt`에 보존한다.

최종 `FactoryCoilAlignmentChecks.Run`과 `FactoryLogisticsChecks.Run`은 모두 실제 프로세스 종료 코드 0으로 통과했다.

최종 수치 결과는 `unity/ShiftLinkFactory/Checks/coil-alignment-result.txt`에 기록한다. 전체 장치 렌더는 `Checks/coil-alignment-Decoiler.png`, `Checks/coil-alignment-Recoiler.png`다. `Checks/coil-alignment-cutaway-*.png`는 구멍과 축 정렬을 보기 위해 앞 지지 기둥만 일시적으로 숨긴 진단 이미지다. 제품 장면에서는 기둥을 숨기지 않는다.

현재 열려 있는 `.worktrees/unity-map-clearance` 프로젝트에도 두 런타임 파일의 해당 수정만 적용했다. 생성된 기존 장면은 Stop → Play로 다시 만들어야 한다. 검증은 루트 프로젝트의 배치 장면으로 수행했으며 열린 에디터의 실제 Play 화면은 별도로 조작하지 않았다. Unity 코드 커버리지 계측은 수행하지 않았다.
