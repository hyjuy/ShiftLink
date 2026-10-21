# Timestral-28M 예측 헤드 추가 학습 — 사전 고정

2026-10-21. 사용자 요청은 PC에서 추가 학습 후 약한 고장 탐지율·오경보를 EWMA와 비교하는 것이다. 공개 Timestral 코드는 추론 중심이며 공식 trainer는 제공하지 않는다. 기존28M의 백본은 동결하고 원본 QuantileHead를 실제 gradient update한다. 전체28M 재학습이라고 부르지 않는다. 정상 시계열 예측의 도메인 적응 실험이며 고장 유형 지도 분류를 추가하지 않는다.

## 데이터와 대조군

- 기존 runtime `output/mes-diagnostic-runtime-20261021` 48파일 해시를 검증한다. 원본 코드 commit a534bdbd244d64f3d9d743f46c7bf6fc330ed4ff, 가중치 revision49b26409ac87b5935539a5d8ffe7f397b720db47을 유지한다.
- 기존 seed2371..2378 full train으로 원래 EWMA 통계와68채널 mask/잔차 scale을 재현한다. 기존 validation/test를 학습·선정에 사용하지 않는다.
- 새로운 정상 corpus: seed35371 시작, independent v7, hazard0, 6runs/split×160ticks, warmup60. train 첫4run은 fit, 나머지2run은 checkpoint selection, validation6run은 threshold calibration. test 본문은 읽거나 해시하지 않는다.
- 과거64→다음1 예측창에서 각 run의 매 두 번째 창만 고정 선택한다. fit192창, selection96창, calibration288창이며 중첩 창은 독립 사건이 아니다. 단계 간 run/seed는 겹치지 않는다. 정상 라벨은 온전한 정상 corpus 확인에만 사용한다.
- 최종 약한 고장: seed45371 시작, independent v7, 8runs/split×300ticks, hazard.003, warmup60, response_scale.2. validation45379..45386만 평가하며 새로운 train은 적합에 쓰지 않는다. 기존 모든 source 및 정상 corpus와 run/seed 겹침을 거부한다. 최종 고장 지표는 checkpoint/임계값 고정 뒤 한 번 계산한다. 사용자가 요청한 weak 비교에 집중하며 full 추가 실험은 하지 않는다.
- 대조군: 현재 EWMA(alpha.4/threshold3), 새 정상 fit4run으로 통계만 다시 적합한 EWMA, 원본 Timestral head와 학습 head. 두 Timestral은 같은 새 정상 calibration288창에서 각자 보정한다. 원본/학습 head 차이는 정상 보정 자료 증가와 분리해 읽는다.

## 학습과 추론

- 백본 hidden을 +context/-context 두 pass에서 캐시한다. 인과 입력에 현재 target을 넣지 않는다. loss는 원래 head의21분위수에 대한 pinball loss이며 target은 마지막 context patch의 loc/scale로 정규화하고 asinh를 적용한다. 누락 target은 loss에서 제외한다.
- AdamW lr1e-4, weight_decay.01, batch512, 5epochs, seed20261021, gradient norm clip1.0. 정상 selection loss가 가장 낮은 학습 epoch1..5를 선택한다. 원본 epoch0 loss는 별도 대조하며 원본보다 loss가 악화해도 숨기지 않는다. 고장 recall로 학습 epoch를 선정하지 않는다.
- 64-step context/horizon1, q01/median/q99, symmetric averaging와 nonnegative clipping을 원본과 같게 유지한다. 원본 cap도 재현한다. 캐시 재구성은 공식 forecast()의 원본 출력과 대조하며, 선택 checkpoint를 모델에 실제 로드한 뒤 공식 forecast()와 재구성 결과를 다시 비교한다.
- score와 threshold는 앞 실험 정의 그대로다: 비대칭 분위폭과 .1*기존train_scale 하한, 설비 최대, 정상 calibration .995(method=higher), 최소1, score>threshold. 경보 후처리나 임계값 재검색은 하지 않는다.
- backbone unchanged / head changed / checkpoint 저장·재로딩·해시 / gradient와 loss 유한성 / 단계 간 누출 방지 / 원본 덮어쓰기 거부를 검증한다. PC CPU1thread×4workers feature 추론과 CPU4threads head 학습을 사용한다. Jetson·PDA·운영 소스는 변경하지 않는다.

## 판정

약한 고장 recall이 기존 EWMA보다 **엄격히 높고**, 오경보 설비·초가 **엄격히 낮아야** 요청한 두 지표 동시 개선이다. data-matched EWMA와 원본 head 대비 결과도 별도 표시한다. 중복·미일치 시작·wrong union seconds·성공건 지연p95·사건별 획득/손실/지연·정상 배경 경보를 함께 기록한다. 한 지표의 이득으로 다른 손실을 감추지 않는다. 공통64프레임 준비 구간 EWMA도 보조 비교한다.

현장 자료·실제 정비 라벨·다양한 운전 모드·전체 모델 fine-tuning·다른 학습률/context·Jetson 장치 추론은 범위 밖이다. 정상 예측 loss 개선이 고장 탐지 개선을 보장하지 않으며 지속 고장 적응 한계가 남는다. 새 실험 산출물만 추가하고 기존 결과·공유 변경은 보존한다.
