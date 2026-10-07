# PDA 센서 표시와 질의 당시 근거 (2026-10-07)

사용자 요청: 현재 가상 MES 센서가 PDA에서 필요한 곳에 수치로 보이도록 하고,
정비 관점에서 실시간 표시와 질의 당시 기록의 용도를 구분한다.

## 적용 위치

| 위치 | 데이터와 동작 |
|---|---|
| 설비 선택 후 작업 선택 | `/api/state`의 해당 설비 센서값·단위·측정 시각, `/api/config`의 정상 범위. 기존 3초 폴링으로 갱신 |
| 증상 질의 | 현재 관측값·범위 이탈·측정 시각 표시. 수동 입력과 작업자의 제외 선택은 유지 |
| 질의 결과 | Jetson 응답 `evidence.measurements` 중 `used_for_conditions=true`인 당시 측정값 표시. 실시간 폴링으로 덮어쓰지 않음 |
| 결과의 로컬 조건 판정 | 답변을 기다리는 동안 변한 현재값 대신 서버가 답변에 실제 사용한 당시 근거로 판정 |
| 연결 실패 | 현재 센서 표시를 지우고 연결 실패를 표시. 이전 MES 값을 질의용 현재 관측 목록에서 제외, 수동 입력 유지 |

현재 센서 표시에는 수동 입력으로 덮어쓴 수치가 아닌 MES 원값을 사용한다.
‘MES 관측 다시 읽기’ 버튼의 클릭 이벤트를 스냅샷으로 잘못 해석하던 연결도 수정했다.
정지 중 0인 신호는 현재 센서 패널에서 범위 이탈로 강조하지 않는다.

질의 기준 시점은 **서버가 질의를 접수해 엔진 스냅샷을 확보한 시점**이다.
프론트엔드에서 클릭한 정확한 순간과 같다고 주장하지 않는다.
서버는 이미 스냅샷을 확보한 다음 모델을 실행하며 이 근거를 응답에 제공한다.
이 변경은 그 응답 근거를 화면에 표시한다. 별도 영구 진단 이력 저장·조회 기능은 추가하지 않았다.
조치 이후 관측과 인계의 현재 관측은 기존 동작을 유지한다.

## 검증

RED: `node tests/pda_sensor_display.cjs`가 작업 선택 화면의 센서 패널을 렌더링하지 않아 실패했다.
체크포인트: `758e3ac`.

GREEN:

```powershell
node tests/pda_sensor_display.cjs
node tests/pda_network_boot.cjs
node tests/unity_pda_link.cjs
node tests/pda_symptom_rank.cjs
node tests/mes_query_pda.cjs
python -m unittest tests.test_pda_handover -q
node --check shiftlink/mes/web/pda.js
```

모두 통과. 센서 표시 테스트는 실제 Pi에서 확인한 압력 `154.845 bar`·유온 `47.05 ℃`를
재현해 값·정상 범위 표시, 타 설비 제외, 불량 품질 제외, 수동 우선, 연결 실패를 확인한다.
현재 압력 `155 bar`와 답변 근거 `120 bar`가 달라도 결과는 `120 bar`를 표시·판정한다.
전체 커버리지는 측정하지 않았고 실제 화면의 시각 검증은 별도로 수행하지 않았다.

Pi 기존 화면 경로에 HTML과 JS를 반영했다. 배포 JS와 로컬 JS의 SHA256은
`562b3689d3cabf40761b8e21a654cb91baa98dad8b455f5aa3c0dd31fe44dc7b`로 일치했다.
Pi의 로컬 프록시를 통한 `/api/state` HTTP 200 및 센서 69개를 확인했다.

## 시점 구분의 이유

정비 중 현재 상태 확인은 계속 필요하고, 답변의 판단 근거는 당시 값으로 유지해야 추적할 수 있다.
이 설계 판단은 측정 원본 시각을 보존하는
[OPC UA SourceTimestamp 원칙](https://reference.opcfoundation.org/specs/OPC-10000-4/7.11.3)을 참고했다.
이는 이 프로젝트에 OPC UA를 도입했다는 의미가 아니다.
