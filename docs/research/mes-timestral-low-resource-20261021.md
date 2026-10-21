# 현재 Raspberry Pi용 저자원 추론 설정 — 2026-10-21

사용자 선택은 모델 압축이 아니라 현재 Pi에서 실행할 수 있는 저자원 설정으로 비교하는 것이다. 기존 기록 `bench/experiments.tsv`는 Raspberry Pi 4 Model B Rev 1.5를 명시한다. `docs/testing/cnn-unity-result-20261008.md`에는 CPU ONNX 설비 분류 CNN, `docs/guides/run-demo.md`에는 PDA 키오스크가 기록돼 있다. RAM 용량과 현재 여유 자원은 기록에서 확인하지 못했다. `ssh -o BatchMode=yes -o ConnectTimeout=8 pi@raspberrypi`는 `Permission denied (publickey,password).`로 실패했다.

**저자원 실행 파일을 만들고 PC에서 실제 실행했지만, 현재 Pi에서의 실행 가능 여부는 아직 확정하지 못했다.** PC 스레드 제한은 ARM CPU 성능이나 Pi의 RAM 제한을 재현하지 않는다.

## 고정 설정

| 항목 | 값 |
| --- | --- |
| 모델 | 기존 추가 학습 checkpoint, 전체27,821,184 parameters |
| 실행 | CPU, PyTorch1스레드·interop1스레드·작업자1개·배치1 |
| 입력 | 68채널, 과거64프레임, 다음1프레임 예측 |
| 정밀도 | FP32 |
| 예측 처리 | 원본·부호 반전 입력 평균, nonnegative clipping 유지 |
| 학습 | PC에서 완료한 checkpoint 사용; Pi에서는 추론 |

입력 채널·정밀도·모델·임계값은 바꾸지 않았다. 채널 축소나 INT8 변환으로 기존 탐지 결과가 달라지는 실험은 하지 않았다. 동시에4창을 처리하던 PC 실험의 병렬 작업자를1개로 줄이고 모든 수치 라이브러리 스레드를1개로 제한했다.

## PC 저자원 실행 확인

`scripts/mes_timestral_low_resource.py`를 실제 checkpoint와 저장된68채널 입력으로 실행했다. 공식 `forecast(context[None], prediction_length=1)`을 사용하고, 서로 다른3개 시간 창의 예측을 기존 저장값과 비교한 뒤12회 순차 추론을 측정했다.

| 관측값 | Windows AMD64 PC, 단일 실행 |
| --- | ---: |
| 추론 p50 | 0.367초/창 |
| 추론 p95 | 0.488초/창 |
| 모델 로딩 | 0.940초 |
| 로딩·추론 과정 프로세스 최대 RSS | 444,022,784bytes (약423.5MiB) |
| checkpoint 가중치 파일 | 111,296,432bytes (약106.1MiB) |
| 기존 저장 예측 대비 최대 절대 오차 | 6.103515625e-05 |

예측 비교는 rtol1e-5/atol1e-5를 통과했다. 모델 가중치 SHA256도 기존 학습 checkpoint `6345f20b018bdb82c4766216b1734679595e08a7cabafa93247a6516eb273ff4`와 같다. RSS는 이 프로세스의 로딩·추론 관측값이며 OS·Chromium·PDA·CNN까지 합친 메모리나 Pi 메모리 요구량이 아니다. 측정값은 정밀 벤치마크나1Hz 운영 보장이 아니며, 반복한3개 입력으로 전체35사건을 다시 평가했다고 주장하지 않는다.

## 고장 지표 해석

새 실행은 자원 설정과3창의 예측 일치를 검사했다. 아래는 같은 checkpoint의 앞선 합성 약한 고장35건 평가이며 Pi 실측 지표가 아니다.

| 방법 | 탐지율 | 오경보 설비·초 | 중복 시작 | 지연p95 |
| --- | ---: | ---: | ---: | ---: |
| 현재 EWMA | 29/35 (82.9%) | 19 | 20 | 10초 |
| 추가 학습 Timestral | 32/35 (91.4%) | 32 | 19 | 24초 |

같은 정상 fit자료로 재적합한 EWMA도29/35·19설비·초였다. 오경보 정의와 데이터 분리는 [추가 학습 결과](mes-timestral-finetune-result-20261021.md)를 따른다. 스레드·작업자 제한은 모델 압축이 아니며 오경보를 줄이는 변경도 아니다. 현재까지 EWMA보다 탐지율·오경보가 동시에 개선됐다는 근거는 없다.

## Pi에서 같은 설정으로 재현

Pi의64bit OS·Python·NumPy·PyTorch·고정 Timestral 코드 환경을 먼저 확인해야 한다. 해당 Pi의 설치 호환성은 아직 검사하지 못했다. 전체 저장소나 feature cache는 불필요하며 실행 파일, checkpoint의 config.json/model.safetensors, weak-predictions.npz가 있으면 아래 실행을 할 수 있다. 원본은 로컬 `output/mes-timestral-finetune-20261021`에 보존했다.

```bash
python3 scripts/mes_timestral_low_resource.py \
  --checkpoint output/mes-timestral-finetune-20261021/checkpoint \
  --predictions output/mes-timestral-finetune-20261021/weak-predictions.npz \
  --out output/mes-timestral-low-resource-pi-20261021.json
```

결과 파일 덮어쓰기를 거부하며 새 경로를 써야 한다. Linux에서는 resource.ru_maxrss를 bytes로 변환한다. Windows 분기는 실제 검사했지만 Linux/ARM 분기는 Pi 인증 문제로 실행하지 못했다. PC 측정 원본은 `output/mes-timestral-low-resource-pc-20261021.json`이다.

남은 확인은 Pi RAM·가용 메모리, ARM 추론 지연, PDA/CNN을 켠 상태의 메모리·응답 시간이다. 현재 장치에는 파일 설치·서비스 변경·배포를 하지 않았다. 실제 저자원 운영 적합성은 이 확인 후 판단한다.
