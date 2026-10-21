# Timestral-28M 추가 학습 결과 — 탐지 증가, 오경보 동시 개선 실패

2026-10-21. PC에서 실제 추가 학습과 새 약한 고장 평가를 완료했다. **현재 EWMA보다 탐지율은 높아졌지만 오경보와 지연이 늘었다. 요청한 두 지표 동시 개선은 확인하지 못했으므로 EWMA 유지가 타당하다.** 추가 학습 전 Timestral에 비해서는 탐지율과 오경보가 모두 개선됐다.

[사전 고정 설계](mes-timestral-finetune-prereg-20261021.md), [테스트·감사 근거](../testing/mes-timestral-finetune-20261021.tdd.md), [원본 결과 JSON](../../output/mes-timestral-finetune-20261021/result.json).

## 새 약한 고장35건 비교

| 방법 | 탐지/전체 | 탐지율 | 오경보 설비·초 | 중복 경보 시작 | 탐지 지연 p95초 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 현재 EWMA | 29/35 | 82.9% | 19 | 20 | 10 |
| 같은 정상 fit 자료로 통계 재적합한 EWMA | 29/35 | 82.9% | 19 | 21 | 11 |
| 추가 학습 전 Timestral + 새 정상 보정 | 26/35 | 74.3% | 63 | 16 | 24 |
| 추가 학습 후 Timestral + 새 정상 보정 | 32/35 | 91.4% | 32 | 19 | 24 |

현재 EWMA 대비 탐지율은8.6%p 상승했고 오경보 설비·초는68.4% 증가했다. 원본 Timestral 대비 탐지율은17.1%p 상승하고 오경보는49.2% 감소했다. 두 Timestral의 보정 데이터와 점수 계산은 같으며 각 모델별 임계값을 별도로 고정했다. 추가 학습 효과에는 그에 따른 임계값 변화도 포함된다.

오경보 설비·초는 활성 고장 원인이 없는 설비의 경보 시간을 설비별로 합산하는 기존 strict 지표다. 다른 설비의 실제 수치 반응과 고장 종료 후 잔류 반응도 포함하므로 현장 오진 확정 시간이 아니다. 탐지는 관측 가능한 활성 원인 사건에 새 경보 시작이 대응할 때 인정한다. p95는 탐지 성공 사건만의 지연이며 미탐을 함께 읽어야 한다.

현재 EWMA가 탐지한3건을 놓치고 다른6건을 새로 탐지했다. 공통 탐지 중9건은 더 늦었다. 같은 정상 자료로 재적합한 EWMA 대비도3건 손실·6건 획득이며8건 지연 증가다. 원본 Timestral의 탐지는 모두 유지하고6건을 더 탐지했지만 중복 시작은16→19건, 공통 탐지1건의 지연은 증가했다. 모든 지표가 개선된 결과는 아니다.

| 방법 | 미일치 경보 시작 | 잘못된 경보 합집합 초 | 오경보 설비·초 |
| --- | ---: | ---: | ---: |
| 현재 EWMA | 20 | 19 | 19 |
| 정상 재적합 EWMA | 21 | 19 | 19 |
| 학습 전 Timestral | 79 | 12 | 63 |
| 학습 후 Timestral | 51 | 10 | 32 |

학습 후에는 잘못된 경보가 하나 이상 켜진 시간의 합집합은 EWMA보다 짧지만 여러 설비에 경보가 분산돼 설비별 합산 시간과 미일치 시작은 더 크다. 미일치 시작은 중복·비활성 설비·조기 시작을 포함하므로 중복과 별도 오류로 합산하지 않는다.

공통64프레임 준비 구간을 EWMA에도 적용한 보조 비교는 현재 EWMA의 위 네 지표와 같았다. 최초 고장 전854프레임 경보는 EWMA0, 원본 Timestral10설비·프레임, 학습 Timestral4설비·프레임이었다. 고장 활성 원인753설비·프레임 중 경보가 켜진 비율은 EWMA426/753, 원본51/753, 학습60/753이다. 사건의 시작을 더 탐지하는 결과와 고장 지속 중 경보 유지 능력은 별개다.

## 실제 학습 범위와 데이터 분리

실제 모델은27,821,184개 parameter이며 그중 원본 QuantileHead의1,880,064개만 학습했다. 백본은 동결했다. 전체28M fine-tuning이나 모델 압축 실험으로 해석하면 안 된다.

- 정상 합성 corpus seed35371 시작, hazard0, 6runs/split×160ticks. fit35371..35374의640프레임에서192창, selection35375..35376에서96창, calibration35377..35382에서288창을 사용했다. 과거64→다음1, 매 두 번째 창을 사용했고 중첩 창은 독립 사건으로 세지 않는다.
- AdamW lr1e-4, weight_decay.01, batch512, 5epochs, seed20261021, gradient norm clip1.0. 원본 입력과 부호 반전 입력의 백본 hidden을 캐시하고21분위수 pinball loss로 학습했다. target은 마지막 context patch의 loc/scale과 asinh로 변환했다.
- 정상 selection loss가 최소인 학습 epoch5를 고정했다. 원본0.042878294254050535→학습0.042332033535429074, **1.274% 감소**다. 정상 loss로만 checkpoint를 고르고 고장 recall로 선택하지 않았다.
- 약한 고장 corpus seed45371 시작, independent v7, hazard.003, warmup60, response_scale.2, 8runs/split×300ticks. 새 validation45379..45386의2400프레임·35사건, 예측1888창을 평가했다. 학습과 보정을 마친 뒤 고장 데이터 본문을 열었다.
- 원래 EWMA와 잔차 정규화 통계는 기존 seed2371..2378 train의정상1386프레임으로 재현했다.68채널은 연속59·derived4·합성 매프레임 manual sample5다. 재적합 EWMA는 새 정상 fit4run만 사용하며 기존 자료와 합치지 않았다. 두 EWMA 모두 alpha.4/threshold3을 유지했다.
- 모든 source·normal·weak run/seed는 겹치지 않는다. loader가 train/validation prefix를 읽지만 새 weak train은 적합·채점에 사용하지 않았다. test 본문은 읽거나 해시하지 않았다. 앞 실험의46/42사건 결과와 이번35사건을 직접 짝지어 비교하지 않는다.

Timestral은 인과64프레임·horizon1, q01/median/q99 비대칭 잔차와 .1*기존train_scale 하한, 설비별 최대 점수를 사용했다. 정상 calibration .995(method=higher), 최소1의 임계값에 엄격한 >를 적용했다. 결과 확인 후 학습률·임계값·후처리를 다시 맞추지 않았다.

## 검증과 PC 비용

실제 CLI 실행과21개 테스트가 통과했다. 추가 학습 스크립트 줄 커버리지는310 statements 중9 miss, **97%**이며 branch coverage는 측정하지 않았다. coverage 원본은 `output/mes-timestral-ft-lines-20261021.json`이다.

원본 백본104개 tensor는 학습 checkpoint와 완전히 같고 head3개 weight만 변경됐다. 모든 정상·고장 창에서 원본 공식 forecast와 cache 재구성의 최대 오차는0.0이었다. 학습 checkpoint를 실제 재로딩한 공식 forecast도 정상3창·고장3창에서 허용오차 검사를 통과했다(최대 절대 오차6.103515625e-05). 정상 cache·정규화 통계·두 모델의 임계값은 독립 계산으로 일치함을 확인했다. 최종 평가의 factual replay와 frozen runtime48파일 검사도 통과했다.

최종 독립 감사에서도 저장 weak NPZ1888창에서 점수·설비 최대·임계값 경보를 직접 재구성했고 EWMA 두 방법을 재계산했다. 다섯 방법의 전체 metrics·background, 세 대조군의 paired events·개선 판정이 모두 저장 결과와 정확히 일치했다. source/normal/weak prefix, runtime48파일, 실행 스크립트2개, checkpoint, 예측·feature NPZ의 SHA256도 일치했다. 감사 중 test 본문은0행이었다.

PC CPU에서 전체 평가 CLI757.413초(약12.6분), head 학습 자체17.504초였다. feature 추론은 fit38.499초, selection19.844초, calibration66.298초, weak473.959초다. 설치·자료 생성·별도 테스트는 전체 CLI 시간에 포함하지 않는다. GPU·Jetson·Raspberry Pi의 실행 시간이나 메모리를 측정한 결과가 아니다. head만 학습했어도 추론할 때는 전체 모델이 필요하다.

공식 코드 commit `a534bdbd244d64f3d9d743f46c7bf6fc330ed4ff`, 원본 모델 revision `49b26409ac87b5935539a5d8ffe7f397b720db47`. 저장 checkpoint는 `output/mes-timestral-finetune-20261021/checkpoint`이며 model.safetensors SHA256은 `6345f20b018bdb82c4766216b1734679595e08a7cabafa93247a6516eb273ff4`다. config와 가중치를 함께 보존했다.

## 재현과 남은 불확실성

```powershell
$experimentPython = Join-Path $env:TEMP 'shiftlink-timestral-20261021/Scripts/python.exe'
& $experimentPython scripts/mes_timestral_finetune.py --runtime output/mes-diagnostic-runtime-20261021 --source output/mes-fault-current-v7-seed2371-full-20261021 --normal output/mes-timestral-ft-normal-v7-seed35371-20261021 --weak output/mes-timestral-ft-weak-v7-seed45371-20261021 --model output/mes-timestral-20261021/hub/models--mistralai--Timestral-28M/snapshots/49b26409ac87b5935539a5d8ffe7f397b720db47 --reference-calibration output/mes-timestral-20261021/calibration.json --out-dir output/mes-timestral-finetune-replay-20261021
```

출력 폴더는 새 경로여야 한다. 원천 자료·예측 NPZ·학습 이력·checkpoint·해시는 ignored `output/`에 보존한다. 실행 구현은 `scripts/mes_timestral_finetune.py`, 테스트는 `tests/test_mes_timestral_finetune.py`다.

이 결론은 합성 running 시계열의 한 학습 설정과 새35사건에 한정된다. 실측 정상 운전·정비 확인 고장·다양한 운전 모드·전체 모델 학습·다른 context나 학습률은 검증하지 않았다. 현장 개선이나 통계적 우월성을 입증한 결과가 아니다. 이번 모델을 EWMA 대체로 채택하지 않고 연구용 checkpoint로 보존한다. Jetson·PDA·기존 운영 코드는 변경하지 않았다.
