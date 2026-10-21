# Timestral 예측 헤드 추가 학습 검증 — 2026-10-21

사용자 요청은 PC에서 Timestral-28M을 추가 학습하고 약한 고장 탐지율과 오경보를 EWMA와 비교하는 것이다. [사전 고정 설계](../research/mes-timestral-finetune-prereg-20261021.md)에 따라 원본 백본을 동결하고 QuantileHead만 학습했다.

## RED → GREEN

- `079eeae`: 의도한 미구현 경로를 대상으로 8개 테스트를 실행했고 `FAILED (errors=8)`을 확인했다. 로그는 `output/mes-timestral-ft-red-20261021.txt`다.
- `a270d54`: 구현 후 새 테스트8개와 기존 비교 테스트12개, 총20개가 통과했다.
- 실제 평가 중 캐시의 동시 실행 분리 테스트를 추가했다. 원본 입력과 부호 반전 입력, 서로 다른 시간 창의 hidden이 섞이지 않고 공식 예측과 일치하는지 검사했다. 총21개 테스트가 통과했으며 `output/mes-timestral-ft-green-20261021.txt`에 로그를 보존했다. 이 추가 테스트는 학습·추론 구현을 바꾸지 않았다.

```powershell
$experimentPython = Join-Path $env:TEMP 'shiftlink-timestral-20261021/Scripts/python.exe'
& $experimentPython -m unittest tests.test_mes_timestral_finetune tests.test_mes_timestral_comparison
```

## 검사 범위

새 테스트는 정상 fit/selection/calibration의 run 분리, 데이터 간 seed 중복 거부, 부호 반전·asinh target 정규화와 누락 처리, pinball gradient, 공식 추론과 캐시 재구성 일치, 실제 head weight 변경과 백본 보존, checkpoint 재로딩·덮어쓰기 거부, 두 요청 지표의 엄격한 동시 개선 판정, 동시 실행 캐시 분리를 검증한다. 작은 실제 Timestral 모델을 사용하는 통합 검사가 포함된다. 기존12개 테스트는 인과 창·시간 단절·누락값·비대칭 잔차·정상 보정·임계값·출처 해시·경보 지표를 다룬다.

## 실제 학습과 독립 감사

실제 Timestral-28M checkpoint에서 QuantileHead의1,880,064개 parameter를 AdamW로5epochs 학습했다. 실제 전체 CLI 실행은 별도 E2E 근거이며 mock 예측을 성능 수치로 사용하지 않았다.

독립 검토자가 저장된 safetensors와 정상 cache를 별도 계산으로 확인했다.

- 백본104개 tensor가 원본과 완전히 동일하고 head의3개 weight만 변경됐다. weight decay만 적용한 예상값과도 차이가 있어 실제 gradient 학습임을 확인했다.
- fit192창·4run, selection96창·2run, calibration288창·6run은 서로 분리됐다. 각 run sequence65..159, stride2이며 key 중복이 없다.
- 세 정상 cache 모두 공식 원본 예측 재구성 최대 오차0.0이었다.
- epoch5가 학습 epoch1..5 중 정상 selection loss 최저다. 원본 epoch0 대비 감소율은1.2739795929961883%다. 이 값으로 고장 탐지 개선을 대신 판정하지 않는다.
- 기존 train prefix2400행에서 정규화 통계를 다시 계산해 저장 해시와 일치함을 확인했다.
- 저장 calibration 예측에서 점수와 .995 higher 임계값을 다시 계산한 결과, 원본·학습 head의10개 설비 임계값이 모두 정확히 일치했다.

실제 CLI와 최종21개 테스트를 합친 줄 커버리지는310 statements 중9 miss, **97%**다. branch coverage는 측정하지 않았다. 원본은 `output/mes-timestral-ft-lines-20261021.json`에 보존했다.

최종 독립 감사는 저장 weak NPZ1888창에서 점수·경보를 별도로 재구성하고 EWMA를 재계산했다. 다섯 방법의 전체 metrics·background, 세 대조군의 paired events·개선 판정이 모두 일치했다. source prefix·runtime48파일·실행 코드·checkpoint·모든 feature/예측 NPZ 해시도 일치했다. EWMA29/35·오경보19설비·초 대비 학습 Timestral32/35·32설비·초이므로 요청한 동시 개선 판정은 false다.

최종 수치·평가 감사는 [결과 보고서](../research/mes-timestral-finetune-result-20261021.md)에 기록한다. test 본문은 사용하지 않으며 운영 코드와 장치 배포는 변경하지 않는다.
