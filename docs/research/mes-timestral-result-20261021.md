# Timestral-28M 비교 결과 — EWMA 유지

2026-10-21. **이번 고정 설정에서는 고장 탐지 개선을 확인하지 못했다. Timestral-28M 후보를 보류하고 EWMA 연구 기준을 유지한다.** 정상 보정만 적용한 Timestral을 실제 로컬 CPU에서 실행했으며 파인튜닝하지 않았다. 기존46사건과 새 시드42사건 모두 weak 탐지건수가 줄고 오경보 설비·초가 늘었다. 중복 감소와 일부 빠른 탐지만으로 이 손실을 상쇄하지 않는다.

[사전 고정 설계](mes-timestral-prereg-20261021.md), [테스트·독립 감사 근거](../testing/mes-timestral-20261021.tdd.md).

## 약한 고장: 요청한 네 지표

| 데이터 | 방법 | 탐지/전체 (탐지율) | 오경보 설비·초 | 중복 시작 | 탐지 지연 p95초 |
| --- | --- | ---: | ---: | ---: | ---: |
| 기존 validation | EWMA | 35/46 (76.1%) | 21 | 30 | 14 |
| 기존 validation | Timestral-28M | 33/46 (71.7%) | 94 | 24 | 18 |
| 새 시드 확인 | EWMA | 36/42 (85.7%) | 23 | 36 | 20 |
| 새 시드 확인 | Timestral-28M | 30/42 (71.4%) | 73 | 18 | 20 |

오경보 설비·초는 고장 원인이 활성화되지 않은 설비에 경보가 켜진 시간을 설비별로 합한 기존 strict 지표다. 다른 설비의 실제 수치 반응과 고장 종료 후 기억도 포함한다. 실측 오진 확정 시간이 아니다. 지연 p95는 탐지 성공 사건만의 통계이며 미탐과 함께 읽는다.

## 경보 부담을 한 숫자로 숨기지 않기

| 조건 | 방법 | 미일치 경보 시작 | 잘못된 경보 합집합 초 | 오경보 설비·초 | 중복 시작 |
| --- | --- | ---: | ---: | ---: | ---: |
| 기존 full | EWMA | 31 | 286 | 358 | 14 |
| 기존 full | Timestral | 128 | 22 | 98 | 33 |
| 기존 weak | EWMA | 30 | 21 | 21 | 30 |
| 기존 weak | Timestral | 117 | 18 | 94 | 24 |
| 새 시드 full | EWMA | 20 | 236 | 276 | 3 |
| 새 시드 full | Timestral | 112 | 18 | 81 | 31 |
| 새 시드 weak | EWMA | 36 | 23 | 23 | 36 |
| 새 시드 weak | Timestral | 91 | 14 | 73 | 18 |

새 weak에서는 잘못된 경보가 하나 이상 켜진 시간은 23→14초로 줄었다. 동시에 설비별 합산 시간은23→73설비·초, 미일치 시작은36→91건으로 늘었다. 여러 설비의 짧은 경보가 늘어난 결과이므로 합집합 시간 감소만으로 오경보가 개선됐다고 판정하지 않는다. 미일치 시작은 중복·비활성 설비·조기 시작을 포함하며 중복과 별도 독립 오류로 더하지 않는다.

## full 조건과 사건별 손익

| 데이터 | 방법 | 탐지/전체 | 오경보 설비·초 | 중복 시작 | 지연 p95초 |
| --- | --- | ---: | ---: | ---: | ---: |
| 기존 | EWMA | 44/46 | 358 | 14 | 3 |
| 기존 | Timestral | 39/46 | 98 | 33 | 2 |
| 새 시드 | EWMA | 42/42 | 276 | 3 | 3 |
| 새 시드 | Timestral | 40/42 | 81 | 31 | 1 |

사건별 비교는 EWMA가 탐지했지만 Timestral이 놓친 사건과 반대 경우를 구분했다.

| 데이터·조건 | 기존 탐지 손실 | 새 탐지 획득 | 공통 탐지 중 지연 증가 사건 | 실패 관문 |
| --- | ---: | ---: | ---: | --- |
| 기존 full | 5 | 0 | 1 | detected_events, duplicate_alert_episodes |
| 기존 weak | 7 | 5 | 2 | detected_events, wrong_alert_equipment_seconds, p95_onset_delay_seconds |
| 새 시드 full | 2 | 0 | 2 | detected_events, duplicate_alert_episodes |
| 새 시드 weak | 11 | 5 | 3 | detected_events, wrong_alert_equipment_seconds |

준비 구간64프레임의 경보를 EWMA에도 억제한 보조 비교에서 네 조건의 탐지건수·오경보 설비·초·지연 p95는 원래 EWMA와 같았다. 기존 full 중복만14→13건이었다. 공통 준비 구간에서도 모든 후보가 관문을 통과하지 못했다.

## 고장 지속 중 반응과 정상 배경

| 데이터·조건 | EWMA 활성 원인 경보/활성 설비·초 | Timestral 활성 원인 경보/활성 설비·초 |
| --- | ---: | ---: |
| 기존 full | 800/917 (87.2%) | 114/917 (12.4%) |
| 기존 weak | 451/917 (49.2%) | 80/917 (8.7%) |
| 새 시드 full | 812/876 (92.7%) | 103/876 (11.8%) |
| 새 시드 weak | 484/876 (55.3%) | 60/876 (6.8%) |

기존 validation 최초 고장 전606프레임에는 두 방법 모두 경보0이었다. 새 시드의 최초 고장 전873프레임에서는 EWMA0, Timestral17설비·초였다. 이 배경 구간의 full/weak는 같은 관측이므로 독립 증거 두 개로 세지 않는다. 정상 라벨 시각의 경보에는 과거 고장 영향이 남을 수 있어 순수 정상 배경과 구분한다.

독립 보조 분석에서 기존45사건의 초기4개와 후반4개 활성 예측 점수/임계값 중앙값을 비교했을 때 full39건·weak37건에서 점수가 줄었다. 지속 고장 이력을 예측에 재입력하면서 경보가 줄어드는 가설과 맞지만, 강도 변화도 섞여 인과 원인을 확정하지 않는다.

## 고정한 비교 조건과 검증

- 학습: seed2371..2378 full train만 사용. 정상1386프레임에서 관측률95% 이상인68채널 선택. 연속59·derived4·합성 manual sample5이며 unavailable event1은 제외했다. 69개 위치를 모두 연속 센서라고 부르지 않는다.
- Timestral: 과거64프레임, horizon1, 라인68변수를 joint 예측, q01/median/q99 비대칭 잔차. 과거64개와 현재 모두 정상인171창으로 설비별 .995 분위수 임계값을 고정했다. 정답 정상 선택과 중첩 창의 한계를 유지한다.
- EWMA: 기존 alpha .4, threshold3. 기존 validation 양팔 전체 metrics가 D16 원본과 정확히 일치했다.
- 새 확인: seed15371..15394로 생성한 자료의 validation15379..15386만 평가. 기존 source의 전체 시드와 겹침이 없고, 새 train은 적합에 쓰지 않았다. loader는 train/validation prefix를 읽으며 test 본문은 읽거나 해시하지 않았다.
- 각 조건은8run×300초다. 기존46+새42=서로 다른 시드의88원인 사건이다. full/weak는 같은 사건의 강도 짝이므로176독립 사건으로 합산하지 않는다.
- 양팔·양단계 모두 factual 재생과 최초 고장 전 twin 동일성 검사를 통과했다. 원본 runtime48파일·보정·예측·소스 해시를 보존했다.
- 테스트12개 PASS, 줄 커버리지244 statements 중11 miss(95%). branch coverage는 측정하지 않았다. `output/mes-timestral-green-final-20261021.txt`, `output/mes-timestral-line-coverage-20261021.json`에 보존했다.

## 모델·비용·재현

공식 코드 commit `a534bdbd244d64f3d9d743f46c7bf6fc330ed4ff`, 모델 revision `49b26409ac87b5935539a5d8ffe7f397b720db47`. 가중치 SHA256 `dfc83c6220937ce5fc6687b35a4df94cd25e28a2cfe6fb92a23dad6301b2015d`. Python3.13.15 / torch2.14.1+cpu / numpy2.2.6 / sklearn1.7.2. 기존 프로젝트 환경을 바꾸지 않고 C: 임시 격리 환경에서 실행했다. 설비 데이터를 외부 추론 서비스로 전송하지 않았다.

- 기존 비교 전체 1012.005초. full/weak 예측 wall time은 각각 376.606/393.262초.
- 새 확인 전체 1236.812초. full/weak 예측 wall time은 각각 540.414/390.430초.

난수 처리량 측정으로 결과 확인 전에1thread×4workers, B1으로 정정했다. 창당 처리량은 .199.. .286초였고, 단계별5회 단건 측정은 .34.. .54초 범위였다. 단일 PC 관측이며 장치·서버 전용 벤치마크가 아니다. 정상 보정 예측33.610초는 앞서 만든 calibration에서 재사용했다. 설치·데이터 생성·중단한 계산은 위 단계별 전체 시간에 포함하지 않는다.

아래는 보존된 calibration을 재사용하는 실행 예다. `--out`은 기존 결과와 다른 파일이어야 하고 `--artifacts`에는 이전 phase NPZ가 없는 새 폴더를 사용한다. 원본 데이터·모델·frozen runtime은 ignored `output/`에 보존하며 Git에는 넣지 않는다.

```powershell
$experimentPython = Join-Path $env:TEMP 'shiftlink-timestral-20261021/Scripts/python.exe'
& $experimentPython scripts/mes_timestral_comparison.py --runtime output/mes-diagnostic-runtime-20261021 --train-full output/mes-fault-current-v7-seed2371-full-20261021 --full output/mes-fault-timestral-v7-seed15371-full-20261021 --weak output/mes-fault-timestral-v7-seed15371-weak-20261021 --artifacts output/mes-timestral-replay-20261021 --calibration output/mes-timestral-20261021/calibration.json --phase confirmation --out output/mes-timestral-replay-20261021.json
```

원본: [기존 비교 JSON](../../output/mes-timestral-development-20261021.json), [새 확인 JSON](../../output/mes-timestral-confirmation-20261021.json), [환경 버전](../../output/mes-timestral-environment-20261021.txt). 실행 스크립트는 `scripts/mes_timestral_comparison.py`, 테스트는 `tests/test_mes_timestral_comparison.py`다.

## 범위와 남은 불확실성

결론은 이64프레임·정상 보정 설정과 합성 running 모드에 한정된다. .2는 임의 변위 스트레스이며 수동 시료도 합성 매프레임 갱신이다. 실측 정상 운전, 정비 확인 고장, 다양한 운전 모드, 다른 context/보정/파인튜닝, 장치 추론 성능은 검증하지 않았다. 현장 고장 원인 분류 정확도를 입증한 결과가 아니다. 운영 배포와 기존 화면·예측기는 변경하지 않았다.
