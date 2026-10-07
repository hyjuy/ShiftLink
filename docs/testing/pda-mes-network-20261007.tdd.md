# PDA–가상 MES 연동 검증 (2026-10-07)

사용자 요청과 네트워크 전문가 서브에이전트 검토를 바탕으로 기존 HTTP 프록시를 재사용했다.

```text
PDA Chromium → Pi 127.0.0.1:8080/api/state
             → http://jetson-06.tail0a6af3.ts.net:8000/api/state
```

Pi는 `192.168.11.82` / `100.72.187.104`, Jetson은 `192.168.11.65` / `100.115.59.4`였다.
장치 간 통신은 기존 Tailscale 이름을 사용한다. SSH 비밀번호는 코드나 문서에 저장하지 않는다.

센서값은 Jetson `MesEngine`이 생성한다. PDA는 `/api/state`를 3초 간격으로 조회하고
`/api/config`의 신호·단위·정상 범위를 사용한다. 측정값 계약은
`equipment_id`, `signal`, `value`, `unit`, `observed_at`, `quality`다.
합성 시각 `simulated_at`에 대해 시료 나이를 검사한다.

## 변경 및 로컬 검증

- 상태 등 일반 API의 프록시 제한은 8초, `/api/query`는 180초다.
- 초기 MES 구성 조회 실패 시 3초 후 자동 재시도하며 이전 오류 표시를 비운다.
- Pi 기존 앱 경로에 Python 프록시와 `pda.js`를 배포하고 키오스크 앱을 다시 실행했다.

RED: `node tests/pda_network_boot.cjs`는 재시도 타이머가 없어 실패했다.
프록시 테스트는 기존 180초와 기대값 8초가 달라 실패했다. RED 체크포인트: `9473179`.

GREEN 명령:

```powershell
node tests/pda_network_boot.cjs
node tests/unity_pda_link.cjs
node --check shiftlink/mes/web/pda.js
python -c "import runpy; t=runpy.run_path('tests/test_pda_app.py'); [f() for n,f in t.items() if n.startswith('test_')]; print('PDA proxy 3 tests PASS')"
```

모두 통과했다. Python 테스트는 로컬 `pytest`가 설치되지 않아 표준 라이브러리로 직접 실행했다.
전체 커버리지는 측정하지 않았다. 전체 UI/E2E 커버리지 80% 달성을 주장하지 않는다.

## 장치 검증

- Jetson `shiftlink-mes`는 `active`, `0.0.0.0:8000`에서 수신했다.
- Pi에서 Jetson 직접 요청과 로컬 프록시 모두 HTTP 200이었다.
- 양쪽 `run_id`는 `644a4ec9c8f9405a8fabc270fe5340a2`, 측정값은 69개였다.
- 가상 MES가 정지 상태여서 Pi 프록시를 통해 `POST /api/control`에
  `{"command":"start"}`를 전달했다. 이후 `line_mode=running`을 확인했다.
- PDA 프록시에서 3초 간격 조회 결과 `sequence=64 → 67`, 센서 69개로 갱신됐다.
- `/api/config`, `/api/kb/cards` 모두 200. 배포된 JS의 재시도 구문도 확인했다.
- 키오스크 프로세스는 재실행했지만 화면을 직접 관찰하는 시각 검증은 수행하지 않았다.
- 재부팅·실제 네트워크 단절 시험은 수행하지 않았다. 기존 데스크톱 자동 시작 설정을 유지한다.

Pi에서 다시 점검:

```bash
curl --max-time 10 http://127.0.0.1:8080/api/state
```

PDA에서 설비를 선택하면 해당 `equipment_id`의 센서 관측값이 표시된다.
별도 MQTT 브로커나 클라우드 업로더는 이 센서 전달 경로에 필요하지 않다.
