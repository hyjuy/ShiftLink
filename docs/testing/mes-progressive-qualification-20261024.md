# 새 점진 랜덤 모드 — 운영 AI Pi 검증 결과

2026-10-24 KST. 사용자 요청에 따라 현재 운영 r6의 실제 설치 코드를 Raspberry Pi에서 검증했다. **배포 판정: 보류**. 고장 탐지·중복·지연 기준은 통과했으나 오통지 2건 때문에 고정한 무오통지 기준을 충족하지 못했다. Jetson 운영 MES에 새 모드를 적용하지 않았다.

## 고정과 자료

[평가 전 기준](mes-progressive-qualification-prereg-20261024.md)을 먼저 고정했다. 모델·전처리·profile·임계값을 수정하거나 재학습하지 않았다. Pi에 설치된 `ActiveAdvisorySource/ActiveAdvisorySession`과 운영 PDA reader를 직접 사용했다. 생성기는 별도 후보이며 기반 engine/random_factory/signal_dynamics/fault_schedule/contracts/configuration 6파일이 Jetson 운영 파일과 같은 것을 검사 전후 확인했다.

새 seed·nonce로 종류별 6건씩 고장 24실행과 별도 정상 8실행을 만들었다. 자연 랜덤 결과에서 AI 출력과 무관하게 각 종류의 첫 6건을 채택했다. 모든 자료를 확정한 다음 분석했다. 정상 실행은 900프레임씩 총 7,200프레임, 합성 시간 2시간이다. 고장 실행은 시작 후 300프레임 유지→명시적 pause/repair/resume→160프레임 회복 구간을 포함한다. 전체 25,760프레임을 처리했다.

고장 정답·타깃·강도는 별도 장부에만 두고, 운영 바인딩으로 검사한 센서 69채널·시각·가동·실행 정보만 분석기에 전달했다. 같은 event_id의 3프레임 간격 재조회는 새 통지로 세지 않았다. 이 평가는 같은 합성 생성기·센서 범위를 공유하며 현장 일반화를 입증하지 않는다.

## 결과

| 주입 시나리오 | 해당 설비 탐지 | 미탐 | 중복 통지 | 다른 정상 설비 통지 |
|---|---:|---:|---:|---:|
| 유압 누설 | 6/6 | 0 | 0 | 0 |
| 냉각 손실 | 6/6 | 0 | 0 | 1 |
| 공압 누설 | 6/6 | 0 | 0 | 0 |
| 구동 마찰 | 6/6 | 0 | 0 | 0 |
| 합계 | **24/24 · 100%** | **0** | **0** | **1** |

별도 정상 8실행 중 normal-06에서 **오통지 1건**이 있었다. 따라서 정상 설비 전체에 대한 오통지는 **총 2건**이다. 순수 정상 실행 1건과 고장 중 다른 설비 1건을 구분한다. 총 26개 통지 중 고장과 매칭한 첫 통지는 24개이며 표본 내 통지 정밀도는 92.3%다. 이 수치를 실측 장비 정확도로 설명하지 않는다. 시나리오 이름은 주입 정답이며 AI가 원인 유형까지 진단했다는 뜻이 아니다.

- 고장 시작→첫 통지 지연 p95: **25초**(1초 간격 프레임의 sequence 차이).
- 유효한 타깃 센서의 정상 범위 이탈 3프레임 연속 확인 시점 대비 지연 p95: **0초**. 더 일찍 탐지한 건은 0으로 절삭한 집계이며 실제 지연이 없다는 뜻이 아니다.
- 3프레임 간격 PDA reader 조회를 가정한 가상 표시 지연 p95: **26초**.
- feed/report/reader 처리 계산 p95: **31.06ms**. 공통 입력·계산 루프의 실제 Pi 시간이며 fsync·실제 1Hz 대기·Jetson 통신·실제 화면 표시까지 포함한 시간이 아니다.
- 전체 분석 528.18초. 생성 시간은 별도다. 앞의 20개 기능 검사와 이번 탐지 평가를 합산하지 않는다.

오통지 0건 조건을 통과하지 못해 사전 계획의 후속 실제 1Hz/통신/Chromium 표시 검증과 운영 적용 단계는 진행하지 않았다. **실측 끝단 간 p95는 이번 결과에 없다.** 이전 55건의 6초와 이번 25초는 데이터·점진 악화 방식·시작 정의가 달라 직접 비교하지 않는다.

## 두 오통지의 근거

| 사례·프레임 | 설비·신호 | 정상 관측 | 내부 판정 |
|---|---|---|---|
| cooling_loss-03 / 649 | CV-01 / cv_vib_rms | 1.369, 정상 범위 0.8~1.8, good | 최근 8프레임 peak-to-peak 0 → flat |
| normal-06 / 515 | RT-03 / rt_vib_rms | 1.348, 정상 범위 0.8~1.8, good | 최근 8프레임 peak-to-peak 0 → flat |

생성기의 `signal_dynamics.py:118`은 값을 소수점 3자리로 반올림한다. 작은 정상 변동이 반올림 후 같은 값으로 이어졌고, 두 채널의 profile 고착 창은 8프레임·알려진 정상 plateau 범위는 null이었다. `mes_causal_context.py:104`의 짧은 창 고착 검사가 이를 이상으로 인정했다. 두 채널 tolerance는 각각 약 4.87942e-6, 3.876871e-6이었다. 단순히 tolerance를 바꾸면 해결된다고 해석하지 않는다.

동일 seed·nonce·시작 시각에서 고장을 비활성화한 생성 이력과 비교했다. CV-01은 해당 시점까지 649프레임, RT-03은 515프레임의 값·품질 이력이 전부 같았다. 고장 파급 반응이 아니라 정상 양자화/정체와 센서 고착을 구분하지 못한 오통지로 판정했다. 원본 평가 자료를 별도 고정 모델로 재생해서도 같은 고착 경로와 통지 시점을 확인했다. 원본 결과를 보존했으며 오통지를 제외해 수치를 다시 쓰지 않았다.

후속 개선에는 실제 측정 해상도·운전/부하별 정상 정체를 포함한 별도 개발 자료가 필요하다. 정상 범위 안 고착을 일괄 무시하면 실제 센서 고착을 놓칠 수 있으므로 양쪽을 함께 검증해야 한다. 이번 평가 자료는 이미 확인했으므로 수정 후 새 미사용 평가셋으로 다시 검증해야 한다. 이번에는 모델이나 생성기에 잡음을 추가해 수치를 맞추지 않았다.

## 보존과 재현

- Pi 검증 경로: `/home/pi/shiftlink/analytics/validation/mes-progressive-eval-20261024-v2`.
- 모델·입력·운영 reader/JS/unit 등 고정 17파일 해시 불변, 입력 gzip 32개 해시 일치.
- 운영 분석 PID20799·NRestarts=0·active, PDA AI ready. 기존 MES PID19235·NRestarts=0·active. 두 서비스를 재시작하거나 경보를 조작하지 않았다.
- 기존 MES는 처음 조회 시 fault/경보1건이었고 이후 같은 run에서 running/경보0건으로 관측됐다. 본 작업은 Jetson 상태 GET과 파일·서비스 정보 조회만 수행했다.
- Pi 관측 63회, 최고 48.686°C, throttled=0x0. 30분 부하·얼굴/CNN 강제 동시 부하를 다시 수행한 결과는 아니다.
- 처음 생성하던 자료는 분석 시작 전에 pause 경로를 운영 poll과 같게 보완하면서 중단했다. 그 자료와 도구는 첫 validation 경로에 보존했고, v2에서는 새 seed/nonce로 생성했다. 모델·임계값·통과 기준은 바꾸지 않았다.
- 채점 경계·재조회 중복 억제·p95 계산의 별도 검사 3개 통과. 진단 도구와 평가 도구의 Pi/PC 바이트 일치를 확인했다.

```sh
OPENBLAS_NUM_THREADS=1 python3 evaluate.py --source-root /home/pi/shiftlink/analytics/validation/mes-progressive-20261024/source --release /home/pi/shiftlink/analytics/releases/active-advisory-v1-pda-20261024-r6 --out /home/pi/shiftlink/analytics/validation/mes-progressive-eval-20261024-v2
OPENBLAS_NUM_THREADS=1 python3 diagnose.py --out /home/pi/shiftlink/analytics/validation/mes-progressive-eval-20261024-v2
```

위 evaluate는 결과를 다시 쓰므로 원본 보존본을 먼저 복사하고 별도 출력 경로에서 실행한다. `summary.passed`가 판정 기준이며 도구 실행 완료를 배포 통과로 해석하지 않는다. 공개 기록은 [검증 집계와 원인](mes-progressive-qualification-20261024-summary.json)이다. 실제 운영 로그·화면을 새로 GitHub에 게시하지 않는다.

전체 입력·정답·원본 로그·고정 목록·진단 보관본: `D:/obsd/Projects/ShiftLink/output/mes-progressive-eval-20261024-evidence.zip`.
SHA256: `2c104ebad8bd5bc02fabc2ce539099afcfecd7bd1f95782a2f8c518920250442`.
Pi ZIP CRC와 PC 전달 해시를 확인했다. 전체 이력 대조는 별도 counterfactual-series JSON에 보존한다.

[전체 이력 대조 결과](mes-progressive-qualification-20261024-counterfactual.json)의 SHA256는 `edb5c3fc5bb07b6a3b2a8c8a5b1b99fc99178fa84317e862ffe726d80c66ac64`이며 Pi/PC 전달 해시가 일치했다. PR #354에 후속 검증과 운영 전환 보류를 댓글로 기록했으며, 새 후보 코드를 운영 또는 해당 PR의 병합 코드에 반영하지 않았다.
