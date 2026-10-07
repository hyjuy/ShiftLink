# MES 이상 시나리오 Unity 연동 검증

2026-10-07. 실제 Jetson `http://100.115.59.4:8000` 구성: 장비 10대, 시나리오 104개. 읽기 전용 `/api/config`, `/api/state` 확인. 당시 정상 시나리오 / 정지 / sequence 0. 운영 서버에 시나리오 주입 또는 제어 요청하지 않음.

## RED

`FactoryFaultChecks.Run` 실행 결과 `FAIL MES physical fault visualizer exists`. 누락 컴포넌트를 reflection으로 검사하여 C# 컴파일 오류가 아닌 실행 가능한 실패를 확인했다. 근거: `unity/ShiftLinkFactory/Checks/fault-red.log`, `fault-result.txt` (ignored runtime artifacts).

`scripts/check_unity_faults.py`는 저장한 실제 구성을 새 로컬 MesEngine으로 재생한다. 정상 1 + 이상 104 fixture 생성 성공. 모든 시나리오별 새로운 run을 사용하여 운영 MES에 쓰지 않는다.

## 구현 및 GREEN

진행 중. 정상/복구, 잘못된 센서 품질, 연결 중단, 장비별 가동, 설명 표식 사진 제외를 검증한다. C# 계측 커버리지는 측정하지 않으므로 80% 달성을 주장하지 않는다.
