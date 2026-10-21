# Timestral-28M vs EWMA — 사전 고정 비교

2026-10-21. 사용자 요청: 약한 고장 탐지율, 오경보, 중복 경보, 탐지 지연 비교. 운영 배포는 포함하지 않는다. 결과를 보기 전에 이 설계를 고정한다.

- 보존 runtime `output/mes-diagnostic-runtime-20261021`의 원본 해시 검증, 데이터 loader, `valid_values`, `fit_normal`, `predict_ewma`, `score`, `paired_events`, 재생 검사를 재사용한다. 공유 운영 소스는 수정하지 않는다.
- 공식 코드 commit `a534bdbd244d64f3d9d743f46c7bf6fc330ed4ff`, `mistralai/Timestral-28M`의 실제 다운로드 revision과 파일 해시를 기록한다. 격리 CPU 환경, float32, 8 threads, 기본 symmetric averaging 유지. 파인튜닝하지 않는다.
- 학습은 기존 v7 seed2371..2378 full train만 사용. 최초 비교는 같은 seed2379..2386 validation full/weak(.2). 새 확인은 seed15371 시작, 8 runs/split, 300 ticks, hazard .003, warmup60, independent v7 full/weak(.2)의 validation이다. 새 train은 모델 적합에 사용하지 않는다. test 본문은 읽거나 해시하지 않는다. full/weak는 같은 사건의 짝이며 독립 표본으로 합치지 않는다.
- 학습 정상 프레임에서 유효 관측률 >=95%인 채널을 선택한다. 69개 위치 전체를 연속 센서라고 부르지 않는다. 선택한 센서는 같은 라인의 다변량 target V로 함께 예측한다. 서로 다른 run/window만 batch B로 분리한다.
- 정확히 과거64프레임 `[t-64:t]`에서 horizon1을 예측한다. run 사이와 비가동/시간 단절을 넘겨 이력을 잇지 않는다. 처음64프레임은 Timestral 준비 구간이며, EWMA 원래 전체 점수와 동일 준비 구간 억제를 적용한 EWMA 점수를 모두 보존한다. 초기 고장이 있으면 미탐도 전체 점수에 남긴다.
- 각 채널의 점수는 `max((value-median)/max(q99-median,.1*train_scale), (median-value)/max(median-q01,.1*train_scale),0)`이다. 설비별 최대 채널 점수를 사용한다. 이 점수1은 원래 예측구간 경계에 해당하며, 비대칭 구간을 보존한다.
- 과거64프레임과 현재 모두 라인 전체 faults=[]인 학습 창만 정상 보정에 사용한다(oracle 정상 선택의 한계). 설비별 임계값은 `max(1, 정상 점수의 .995 분위수(method=higher))`. 정상 창64 기준171개가 확인됐으며 독립171사건이 아니다. label은 정상 보정과 채점에만 사용하고 예측 입력에는 넣지 않는다. 정상 구간의 겹침과 작은 보정 표본을 한계로 명시한다.
- 임계값·context·집계·연속확인 횟수는 결과를 본 뒤 변경하지 않는다. 경보는 점수 > 임계값일 때 즉시 켜진다. EWMA 결합 및 경보 후처리는 이번 후보에 포함하지 않는다.
- 기존 strict 평가를 유지: 원인 설비의 새 경보 시작만 사건 탐지로 매칭, 미일치 시작은 inactive/duplicate/premature 분해, wrong union seconds와 equipment-seconds 모두 표시. 정상 라벨/최초 고장 전 경보, 고장 활성 중 경보 coverage도 별도 기록한다. 지연 p95는 성공건만이며 탐지율과 함께 읽는다. 사건별 획득·손실·지연도 비교한다.
- 약한 고장에서 탐지건수 감소, wrong equipment-seconds 증가, 중복 증가, p95 증가 중 하나라도 있으면 전반 개선으로 판정하지 않는다. 네 항목 모두 악화 없이 최소 하나 엄격히 개선해야 aggregate gate 통과다. full 조건, 사건별 손실/지연, 설비·유형 악화도 따로 보고해 승격 판단을 제한한다. 새 확인 결과까지 보고 최종 결론을 낸다.
- 예상되는 한계: 합성 running 모드, 임의 .2 변위, 수동 시료의 합성 매프레임 갱신, 예측의 고장 상태 적응, 짧은64-step 이력. 일반 예측 벤치마크의 우수함은 고장 진단 개선 근거가 아니다. 장치 성능·실제 원인 진단은 미검증.

검증: 인과 window, label 독립성, run/mode reset, 누락·품질, 비대칭 분위수, train-only 보정, 경보 시작/지연, 출력 덮어쓰기 방지 테스트 후 실행. 결과·원본 수치·재현 명령·실제 버전을 보존한다.
