# D18 결과 — 첫 탐지를 보존한 알림 묶음, 합성 연구용 채택

2026-10-21. **고정 EWMA의 raw 경보를 보존하면서 알림 수를 줄이는 후보가 개발 검증과 신규 시드 확인을 모두 통과했다.** 신규54개 사건의 full/weak에서 알림은97→81건, 72→59건으로 줄었다. 기존 탐지53건/44건의 첫 알림 시각은 각각 모두 같았다. 현장 효과·배포 승격은 아직 검증하지 않았다.

[사전 등록](mes-notification-prereg-20261021.md), [구현](../../scripts/mes_notification_review.py), [개발 원본](../../output/mes-notification-validation-20261021.json), [신규 확인 원본](../../output/mes-notification-confirmation-20261021.json), [TDD](../testing/mes-notification-20261021.tdd.md).

## 적용한 동작

설비별 열린 incident는 원래 경보가 잠깐 꺼져도 유지한다. 해당 설비의 학습 마스크 전체가 최신·good·유한·단위 일치인 경보 없는 관측이 **연속3초** 쌓이면 닫는다. 1~2초 뒤 재경보는 같은 incident로 묶는다. 값3은 사전 고정한 임의 가설이며 탐색하지 않았다.

관측 단절·비running·불완전한 경보 없는 관측은 복구로 표시하지 않고 interrupted/unknown으로 닫는다. 부분 관측에서도 raw 경보가 이어지면 알림 폭주 없이 incident를 유지한다. run 끝의 미해결 incident도 run_end로 명시한다. 입력은 프레임·설비별 마스크·원래 경보뿐이며 생성기에만 있는 원인 정답과 twin은 알림 생성에 전달하지 않는다.

## 개발과 신규 확인

| 자료 | 반응 | 원래 시작→알림 | 감소율 | 미일치 시작→알림 | 탐지 사건의 첫 시각 보존 | 짧은 gap 재시작 | 제거된 동일 episode 중복 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| seed2371 개발, 46사건 | full | 75→56 | 25.3% | 31→12 | 44/44 | 19 | 14 |
| 같은 개발 사건 | weak .2 | 65→48 | 26.2% | 30→13 | 35/35 | 17 | 17 |
| seed3371 신규, 54사건 | full | 97→81 | 16.5% | 44→28 | 53/53 | 16 | 11 |
| 같은 신규 사건 | weak .2 | 72→59 | 18.1% | 28→15 | 44/44 | 13 | 13 |

같은 사건을 두 반응 강도로 짝지어 평가했다. 개발92건·신규108건의 독립 사건으로 세지 않는다. `미일치`는 원인 사건의 최초 매칭에 연결되지 않은 알림이다. 감소한 모든 알림을 동일 고장의 중복으로 부르지 않는다. 동일 episode ID에 앞선 알림이 실제로 매칭된 경우만 마지막 열에 센다.

신규 확인은 개발 관문 통과 뒤 한 번 실행했다. 같은48파일 runtime, 같은 구성 `23e0e6b3aa6f073857d48e81fd7430068ee40ca2f0cfe77147bae37741a0b036`, v7 independent, hazard.003, warmup60, 각 분할8run×300초, 새 seed3371..3394를 사용했다. 기존 manifest와 seed 중복을 검사했다. full/weak 시각·일정 및 최초 고장 전623프레임 측정이 같았다. 각 validation2400프레임에서69위치·최신 유효68개 계약을 재확인했다.

학습 통계는 **원래2371..2378 full train**에서 동일 함수로 재구성했다. 그 통계로 원래 validation 경보가 D16 캐시와 프레임별 정확히 같음을 확인한 뒤 신규 validation에 적용했다. 신규 train은 loader가 읽지만 적합·선택에는 사용하지 않는다. 원본/신규 test는 생성기 때문에 각4800행씩 생성되었으나 읽기·평가0이다.

## 원래 경보의 의미는 유지

알림 pulse를 별도 경보로 채점해 오진 시간을 줄이지 않았다. 아래 raw 지표는 묶기 전후 **dict 전체가 동일**하다. 기존에 탐지된 각 episode의 첫 매칭 시각을 명시 알림 좌표와 대조했다. 개별 손실·지연 증가0, run/설비별 알림 수 증가0, 모든 알림의 raw-positive 조건, incident trace·집계 일치가 통과했다.

| 자료/반응 | raw 탐지 | raw 오진 합집합 초 | raw 오진 설비·초 | raw p95초 |
| --- | ---: | ---: | ---: | ---: |
| 개발 full | 44/46 | 286 | 358 | 3 |
| 개발 weak | 35/46 | 21 | 21 | 14 |
| 신규 full | 53/54 | 363 | 501 | 3 |
| 신규 weak | 44/54 | 30 | 30 | 13 |

신규 full에 남는 raw 미탐1건과 weak 미탐10건은 그대로다. 알림 감소가 진단 정확도 개선이나 고장 해결을 뜻하지 않는다. 개발 full 종료54resolved+2run_end, weak48resolved; 신규 full78resolved+3run_end, weak58resolved+1run_end다. 실제 자료는 연속 running·완전 관측이므로 outage/unknown 처리는 반례 테스트로만 검증했다.

## 비판·고정·재현

독립 검토가 실행 전에 지적한 선행 오경보, 서로 가까운 새 고장, 결측·gap, 다른 설비 결측, run-end 누락을 테스트와 trace 검증에 반영했다. 특히 열린 incident 때문에 새 원인 사건의 첫 알림이 가려지면 전체 알림 수가 줄어도 보류한다. 개발 독립 감사는 소스와48파일·캐시 해시, 모든 알림 좌표, 3초 유효 quiet 종료, 동일 episode ID, 첫 탐지 시각을 재확인했다.

신규 runner도 실행 전에 실제 runtime provenance SHA와 개발 결과의 SHA 연결, 실제 D16 캐시 SHA 연결, 시작 시 출력 존재 거부를 추가했다. 후보 소스 SHA는 `a6713dc608c5baeb75c15db3f9c50f035b8668392a9c7378ee2f96a966042203`다. 재구성한 정상 통계 SHA는 `55f9d4cd7afa9eaef6969a81fd1e78dbcb93f5bf1be55f375a5ebc74a678019a`다. 생성·점수 확인 뒤 후보 수정이나 quiet/threshold 검색은 하지 않았다.

개발 재현은 기존 출력과 다른 이름을 쓴다. 새 평가를 추가로 선택하는 목적이 아니라 고정 결과 재현용이다.

```powershell
.venv/Scripts/python.exe -c "import runpy,sys; sys.path.insert(0,'output/mes-diagnostic-runtime-20261021'); runpy.run_path('scripts/mes_notification_review.py',run_name='__main__')" --runtime output/mes-diagnostic-runtime-20261021 --cache output/mes-diagnostic-contract-validation-20261021.json --full output/mes-fault-current-v7-seed2371-full-20261021 --weak output/mes-fault-current-v7-seed2371-weak-20261021 --out output/mes-notification-reproduction.json
```

[한 번 실행한 신규 확인 runner](../../output/mes_notification_confirmation_20261021.py)는 출력이 있으면 채점 전에 중단한다. 대형 자료·고정 소스와 runner는 ignored output 산출물이다. 신규 확인의 prefix 읽기·정상 통계 재구성·예측·알림 검증은12.074초였으며 자료 생성 시간은 제외한다.

합성 연구용 알림 계층으로 채택하고 EWMA 연구 기준을 유지한다. 다음 검증은 실제 정비 확인과 운전 전환·관측 단절이 있는 자료에서 첫 알림 보존 여부를 확인하는 것이다. 새 고장들이 짧은 간격으로 이어지거나 원래 경보가 계속 켜진 경우를 다룬 테스트는 위험을 드러내는 관문이며, 모든 현장 사례의 안전성을 증명하지 않는다.
