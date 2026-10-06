# Unity ↔ Jetson MES 연결 검증

2026-10-06. 대상: http://jetson-06:8000 (100.115.59.4).

실제 문제가 두 가지였다:
1. 인자 없는 Unity 실행 스크립트는 로컬 MES를 시작했다.
2. Jetson 주소로 실행해도 Unity가 외부 HTTP를 차단해
   `InvalidOperationException: Insecure connection not allowed`로 조회 코루틴이 종료됐다.

FactoryChecks.OpenDemo에서 InsecureHttpOption.DevelopmentOnly를 적용한다.
실제 MES에는 --mes-url http://jetson-06:8000으로 실행한다.
인자 없는 실행의 로컬 시연 동작은 유지한다.

검증: FactoryJetsonChecks.Run. Unity Editor를 -batchmode -force-d3d11로 실행하고
--mes-url http://jetson-06:8000 --pda-url http://jetson-06:8000을 지정했다.

RED: Checks/jetson-red.log, exit 1:
`Exception: Jetson HTTP must be allowed in development`.

GREEN: Checks/jetson-green.log, exit 0:
`PASS: Jetson MES http://jetson-06:8000; run=f375b316382540bd80a68146c3f0b5c0; sequence=318; equipment=10; coils=3`.

보장: 로컬 서버가 아닌 Jetson 주소 사용, HTTP 조회 성공, 실제 장비 배치,
동일 실행의 sequence 증가, 모니터에 해당 sequence 표시.
Jetson의 /api/config, /api/state, /api/equipment/scan/recent?limit=1 및 /pda.html의
HTTP 200도 확인했다. 서버 제어 명령이나 테스트용 인식 데이터는 보내지 않았다.
Pi 실물의 카메라·PDA UI 연동과 배포 빌드, 수치 커버리지는 검증하지 않았다.
Unity SearchDatabase 내부 예외는 남았으나 연결 검증은 통과했다.
