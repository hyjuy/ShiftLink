# 점진 악화·수리 전 유지 랜덤 모드

기존 정상/`--random-faults` 경로를 보존한 선택적 합성 MES 모드다. 운영 서비스에는 아직 적용하지 않았다. 실제 물리 모델이나 실측 고장 재현으로 설명하지 않는다.

## 동작

- 정상 운전 180~420 tick 후 가동 중인 설비의 고장 하나를 무작위로 선택한다. 기본 tick이 1초이면 3~7분이다. 배속은 실제 대기 시간을 바꾼다.
- 고장 영향을 해당 설비의 유효 가동 120 tick 동안 점진적으로 키운다. 이후 같은 고장 ID와 최대 영향을 모의 수리 전까지 유지한다. 센서 자체의 정상 부하·잡음은 계속 변하므로 개별 값이 매번 단조롭게 증가한다는 의미는 아니다.
- 누설은 HPU 압력·유량 저하와 유온 상승, 냉각 손실은 유온 상승·냉각기 온도 차 감소, 공압 누설은 공급 압력 저하, 구동 마찰은 진동·베어링 온도·전류 상승을 함께 만든다. HPU 유온/냉각기 입구 온도와 유량/냉각기 오일 유량 관계를 유지한다.
- 동시에 한 고장만 만든다. 고장 설비가 비가동이면 악화를 진행하거나 0 값을 이상값으로 덮어쓰지 않는다. 불량 측정도 덮어쓰지 않는다. 잠깐 정상값·운전 정지는 수리로 간주하지 않는다.
- 수리 해제는 일시정지 뒤 설비 ID를 명시해야 한다. 재가동 후 센서 회복은 별도 관찰한다. 수리 후 다시 180~420 tick 정상 구간을 둔다.
- 실행 초기화·구성 교체·MES 프로세스 재시작은 새 시뮬레이션이다. 이전 프로세스의 고장 지속 상태를 복원하는 기능은 이번 범위에 없다. 같은 실행에서 정상 시나리오를 선택해 진행 중인 고장을 지우는 것은 거부한다.
- 고장 정답·강도·타깃·예정 시각은 비공개 simulation_labels에만 저장한다. `/api/state`, replay, export에는 관측 센서만 전달한다. 고장 정답으로 기존 active_alarms를 추가하거나 기존 경보를 지우지 않는다.

## 별도 실행 예

후보 소스 루트에서 실행한다. 운영 MES의 포트·DB를 재사용하지 않는다.

```sh
python -m shiftlink.mes --progressive-faults --host 127.0.0.1 --port 18000 --db output/progressive-demo.sqlite3 --seed 31 --run-nonce progressive-demo-01
```

`--random-faults`와 동시 사용은 거부한다. `--fault-hazard`는 기존 랜덤 모드의 옵션이며 새 모드는 위 대기 구간을 사용한다. 같은 seed·nonce·구성·시작 시각·조작 순서는 재현 가능하다.

별도 서버에만 다음 제어를 보낸다. `HPU-01`은 예시이며 실제 고장이 지속 중인 설비 ID를 사용한다. 이 명령은 시뮬레이션 수리 기록이며 실제 장비 제어가 아니다.

```sh
curl -X POST http://127.0.0.1:18000/api/control -H 'Content-Type: application/json' -d '{"command":"start"}'
curl -X POST http://127.0.0.1:18000/api/control -H 'Content-Type: application/json' -d '{"command":"pause"}'
curl -X POST http://127.0.0.1:18000/api/control -H 'Content-Type: application/json' -d '{"command":"repair_fault","equipment_id":"HPU-01"}'
curl -X POST http://127.0.0.1:18000/api/control -H 'Content-Type: application/json' -d '{"command":"resume"}'
```

새 UI 버튼은 추가하지 않았다. 운영 전환이나 기존 운영 경보·PDA 변경도 하지 않았다. [Pi 회귀·HTTP 검증](../testing/mes-progressive-faults-20261024.tdd.md)을 참고한다.

생성 메커니즘은 탐지기의 PATTERNS를 읽어 구성하지 않는다. 다만 정상 생성기와 센서 범위는 공유하므로 이 기능 검증을 독립 평가나 현장 탐지 성능으로 설명하지 않는다. 현재 AI가 네 종류를 얼마나 잘 탐지하는지는 고정 후보를 대상으로 별도 평가해야 한다.