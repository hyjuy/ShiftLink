# Unity 공장 현황 디스플레이 검증

2026-10-06. 요청: 가상 공장 내 디스플레이로 현황을 확인한다.

구현: FactoryMonitor가 FactoryDemo에서 검증해 수락한 MES 스냅샷을 표시한다.
별도의 HTTP 조회를 추가하지 않는다. 공장 안의 화면과 우측 상단 확대창에
공정 경로·분기, 코일 수, 경고/심각 장비 수, 장비별 상태를 표시한다.
연결 끊김 때는 이전 수치를 지우고 확인 불가로 표시한다.

검증 대상: Assets/Editor/FactoryMonitorChecks.cs.
Unity 실행 메서드: FactoryMonitorChecks.Run.

- RED: Checks/monitor-red.log, exit 1,
  `Exception: factory must contain an in-world status display`.
- GREEN: Checks/monitor-green.log, exit 0,
  `SHIFTLINK MONITOR CHECK PASS`.
- 경로/분기/장비 코드/코일 수, 일시정지 및 경고 갱신, 연결 끊김 시 이전 값 숨김 확인.
- 실제 HTTP 연동: `python -B scripts/check_unity_live.py`, exit 0.
  FactoryChecks.PlayCheck가 모니터의 MES 연결 표시와 현재 sequence 일치를 확인한다.
- 렌더링: Checks/monitor-factory.png, monitor-front.png, live-factory.png.
- Unity SearchDatabase 내부 ArgumentOutOfRangeException이 실시간 검증 로그에 남지만
  공장 및 모니터 검증은 통과했다.
- 코드 커버리지 수치는 측정하지 않았다. 실제 Pi/Jetson, 확대창 마우스 조작은
  자동화 검증 범위에 포함하지 않았다.

동시 작업 중인 FactoryDemo의 이송 동작 변경과 기타 장비 모델 파일은
디스플레이 체크포인트 당시 기준으로 해당 커밋에 포함하지 않았다.
이후 #214에서 장비 모델과 공장 씬을 추가했다. 디스플레이 연결 호출은
공유 작업 파일에 반영돼 있다.
