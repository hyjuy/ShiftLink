# Pi 4용 Timestral 추가 실험 결과

2026-10-21. PC에서 저자원 추론 설정을 유지하고 기존 추가 학습 Timestral의 경보 방식을 비교했다. [단독 사전 고정](mes-timestral-pi-followup-prereg-20261021.md), [결합 사전 고정](mes-timestral-pi-hybrid-prereg-20261021.md), [선정 고정](mes-timestral-pi-selection-20261021.md), [테스트 근거](../testing/mes-timestral-pi-followup-20261021.tdd.md)를 따른다.

**36후보를 개발 자료에서 비교하고 선정한 하나를 새45사건으로 확인했지만, 현재 EWMA보다 탐지율과 오경보를 동시에 개선하지 못했다.** 결합 후보는 탐지33→40건, 오경보15→16설비·초였다. 중복20→132건과 지연p959→21초도 악화했다. 후보를 운영으로 승격하지 않고 현재 EWMA를 유지한다. 새 결과를 보고 threshold를 다시 조정하지 않았다.

## 독립 확인 결과

| 방법 | 탐지/전체 (탐지율) | 미탐 | 오경보 설비·초 | 중복 시작 | 탐지지연p95초 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 현재 EWMA | 33/45 (73.3%) | 12 | 15 | 20 | 9 |
| 정상 통계 재적합 EWMA | 33/45 (73.3%) | 12 | 17 | 20 | 9 |
| 기본 FT Timestral | 33/45 (73.3%) | 12 | 45 | 25 | 27 |
| 단독 진단 후보(.75,1of1) | 37/45 (82.2%) | 8 | 148 | 34 | 24 |
| 선정 EWMA+Timestral 결합 | 40/45 (88.9%) | 5 | 16 | 132 | 21 |

결합의 탐지율은 현재 EWMA 대비15.6%p 높지만 오경보는1설비·초 증가했다. 개발자료에서는19→16으로 줄었으나 독립 확인에서 감소가 재현되지 않았다. 정상재적합 EWMA의17 대비16은 낮지만, 기준을 현재 EWMA의15에서 바꾸어 성공이라고 선언하지 않는다. 기본 Timestral 대비 개선도 현재 EWMA 대비 개선을 대신하지 않는다.

현재 EWMA의 탐지 손실0건·새 탐지7건이며 공통 탐지 중6건은 더 늦었다. 기본 FT 대비는3건 손실·10건 획득이다. 추가 독립 분석에서 새 탐지7건 모두 탐지 시점과 직전 시점에 EWMA가 꺼져 있었다. 따라서 이7건은 기존 EWMA 경보를 끊어 새 시작으로 재매칭한 효과로 설명되지 않고 Timestral 추가 경보 분기의 획득이다. 경보 시작 매칭으로 집계한 사건 탐지율이며 중복 증가 부담은 별도로 유지한다. 이것만으로 센서 예측 정확도가 좋아졌다고 주장하지 않는다.

| 방법 | 미일치 경보 시작 | 잘못된 경보 합집합 초 | 활성원인 경보/활성설비·프레임 |
| --- | ---: | ---: | ---: |
| 현재 EWMA | 20 | 15 | 577/1039 |
| 정상재적합 EWMA | 20 | 17 | 564/1039 |
| 기본 FT | 69 | 12 | 73/1039 |
| 선정 결합 | 138 | 16 | 391/1039 |

최초 고장 전772프레임에서는 현재 EWMA와 결합 모두 경보0, 기본 FT는12설비·프레임이었다. 정상 라벨1497프레임에서도 EWMA와 결합은0이었다. 결합이 기본 FT 대비 고장 없는 배경 경보를 줄였다는 사실과 활성 원인 경보의 분절·중복 증가는 구분한다.

## 분석 그림

![독립 확인 네 지표](../../output/mes-timestral-pi-followup-figures-20261021/confirmation.png)

![개발36후보 탐색](../../output/mes-timestral-pi-followup-figures-20261021/development.png)

![탐지 성공 사건의 지연 분포](../../output/mes-timestral-pi-followup-figures-20261021/delay-cdf.png)

![경보 분절 진단 시계열](../../output/mes-timestral-pi-followup-figures-20261021/alarm-trace.png)

시계열은 후보 경보 시작이 가장 많은 run/설비를 고정 규칙으로 골랐으며 동률은 사전식 순서다. 좋은 사례만 고르지 않았다. 두 EWMA 경보 구간이 결합에서는 여러 짧은 구간으로 나뉘는 것을 확인할 수 있다. 지연 분포는 미탐을 제외하고 범례에 탐지/전체를 표시한다. 점선 p95는 frozen scorer와 같은 경험적 순위 정의를 쓴다.

## 검증과 실행 비용

실제 새 checkpoint 추론과 factual replay를 완료했다. 독립 검토자가 저장 q01/median/q99 및 실제 입력에서 점수·설비최대·결합 경보를 별도로 재구성했다.5방법의 전체 alerts/metrics/background,4대조군의 paired events와 개선 판정이 모두 일치했다. 선정 JSON·checkpoint·실행코드·runtime48파일·fresh prefix·예측 NPZ의 해시도 일치했다. confirm의 grid는 null로 새 자료에서 재탐색하지 않았다. test 본문은0행이다.

최종27개 테스트가 통과했다. 실험 스크립트 줄 커버리지는167 statements 중3 miss, **98%**다. branch coverage와 그림 생성 코드 커버리지는 측정하지 않았다. 네 그림을 생성하고 직접 열어 축·범례·표기·경보 시계열을 확인했다. 로그는 `output/mes-timestral-pi-followup-final-green-20261021.txt`, 커버리지는 `output/mes-timestral-pi-followup-lines-20261021.json`이다.

전체 확인 CLI868.974초(약14.5분), 실제1888창 추론725.062초, 창당 평균 .384초였다. 추가5개 단건 호출은 .326.. .410초였다. 결합 경보1888창 재구성은1.091초로 모델 호출 비용과 구분한다. offline프로세스 peak RSS645,238,784bytes(약615.3MiB)는 데이터 로딩까지 포함한다. 설치·자료 생성·그림·별도 테스트는 전체 CLI 시간에 포함하지 않는다. 공유 PC의 단일 실행 관측으로 정밀 벤치마크나 Pi4속도가 아니다.

## 자원 범위와 모델

기존 FT checkpoint의 전체27,821,184 parameters·FP32·68채널·context64·horizon1을 그대로 유지했다. CPU1thread·interop1thread·worker1·batch1에서 공식 forecast()를 실행했다. 후보에는 EWMA 상태와 설비별 점수 비교만 추가되며 신경망 호출 횟수와 모델 파일 크기는 증가하지 않는다. 결합 실험은 새 모델 추가 학습이 아니라 이미 학습된 모델과 EWMA의 경보 판정 개선 실험이다.

기존 checkpoint 파일111,296,432bytes, SHA256 `6345f20b018bdb82c4766216b1734679595e08a7cabafa93247a6516eb273ff4`다. 기존 PC 단일 프로세스12회 추론 probe는 p50 .367초, p95 .488초, 로딩·추론 peak RSS 약423.5MiB였다. 이 값은 [앞선 저자원 검사](mes-timestral-low-resource-20261021.md)이며 Pi속도로 외삽하지 않는다. 이번 전체 offline실행 peak RSS에는 원천 JSON 로딩·모든 평가창 적재가 포함돼 실제 온라인 추론 메모리 요구량과 다르다.

장치 기록은 Raspberry Pi 4 Model B Rev 1.5다. RAM·ARM 추론 지연·PDA/CNN 동시 실행 비용은 SSH 인증 문제로 여전히 미확인이다. 따라서 저자원 설정을 유지한 PC 실험이지 Pi 탑재 가능성을 실측 입증한 결과는 아니다. 장치 배포나 운영 화면은 변경하지 않았다.

## 개발 탐색: 기존35사건 재사용

기존 validation45379..45386은 후보 선정에 쓰인 개발자료다. 단독 후보18개는 임계값 배수 {.5,.75,1,1.25,1.5,2}×{1of1,2of3,3of5}다. 단독 통과0개를 확인한 뒤 새 확인자료를 만들기 전에 별도 결합 설계를 고정했다. 결합18개는 gate {.1,.25,.5}×강한 신호 scale {1,1.5,2}×{1of1,2of3}다.

결합 = (현재 EWMA 경보 AND Timestral 점수 > 정상임계값×gate) OR (현재 Timestral 점수 > 정상임계값×scale AND 최근n시점 중k시점 초과). 경보 필터는 현재 초과를 요구하고 run/sequence 단절 때 이력을 비운다. 고장 라벨과 미래값으로 상태를 바꾸지 않는다. 결합 방식이 통과해도 Timestral 단독 개선이라고 부르지 않는다.

| 개발 방법 | 탐지/전체 | 오경보 설비·초 | 중복 시작 | 지연p95초 |
| --- | ---: | ---: | ---: | ---: |
| 현재 EWMA | 29/35 | 19 | 20 | 10 |
| 기본 FT Timestral | 32/35 | 32 | 19 | 24 |
| 단독 진단 후보(.75,1of1) | 34/35 | 126 | 30 | 24 |
| 선정 결합(.1 gate,1.5 scale,1of1) | 32/35 | 16 | 102 | 12 |

결합18개 중 개발에서 두 요청 지표를 통과한 후보는3개다. 탐지수 최대→오경보 최소→p95 최소→고정 parameter 순으로 하나만 선정했다. 중복102건은 경보 분절 증가를 나타내며 두 지표 개발 통과를 전체 경보 품질 개선으로 해석하지 않는다. 총36개를 탐색한 선택편향이 있으므로 새 시드 확인을 별도로 수행한다.

## 독립 확인 설계와 지표 정의

선정 JSON SHA와 실행 코드를 commit `cd34d70`에 고정한 뒤 frozen v7 independent seed55371을 생성했다. validation55379..55386의8run×300초, 고장45건을 평가했다. response_scale.2/hazard.003/warmup60이며 기존 source·normal·development 전체 seed/run과 겹치지 않는다. loader는 train/validation prefix를 읽지만 새 train은 적합에 쓰지 않는다. test 본문은 읽거나 해시하지 않는다. 생성 manifest의 test 건수는 평가 근거로 쓰지 않는다.

현재 EWMA는 기존2371..2378 train 정상1386프레임의 통계와 alpha.4/threshold3을 유지한다. 정상재적합 EWMA는 기존 추가 학습 정상 fit35371..35374의640프레임으로 통계만 다시 적합한다. Timestral 정상 임계값은 기존 calibration35377..35382의288창을 그대로 유지한다. 새 고장으로 checkpoint·정상 임계값을 다시 맞추지 않는다.

고장 탐지는 관측 가능한 활성 원인 사건에 새 경보 시작이 대응할 때 인정한다. 오경보 설비·초는 활성 원인이 없는 설비의 경보 시간을 설비별로 합산하며 다른 설비의 실제 수치 반응과 고장 종료 후 반응도 포함하는 strict 지표다. 현장 오진 확정 시간이 아니다. 미일치 시작은 중복·비활성·조기 경보를 포함하므로 중복과 별도로 합산하지 않는다. 탐지지연 p95는 성공 사건만이며 미탐과 함께 읽는다. PC추론 p95와는 다르다.

## 재현

원본 출력은 `output/mes-timestral-pi-followup-development-20261021`, `output/mes-timestral-pi-hybrid-development-20261021`, `output/mes-timestral-pi-followup-confirmation-20261021`에 보존한다. source·checkpoint·예측·자료는 ignored output에 있으며 Git에는 실험 코드와 보고서만 넣는다.

```powershell
$experimentPython = Join-Path $env:TEMP 'shiftlink-timestral-20261021/Scripts/python.exe'
& $experimentPython scripts/mes_timestral_pi_followup.py --phase confirm --fresh output/mes-timestral-pi-confirm-v7-seed55371-20261021 --selection output/mes-timestral-pi-hybrid-development-20261021/result.json --out-dir output/mes-timestral-pi-followup-confirmation-replay-20261021
```

출력은 새 폴더여야 한다. 선정코드 SHA가 다르면 실행을 거부하므로 고정 commit의 코드를 사용한다. Python3.13.15 / torch2.14.1+cpu / numpy2.2.6으로 실행하고 그림은 격리 실험 환경의 matplotlib3.11.2로 만든다. 주 프로젝트 의존성은 변경하지 않았다.

현장 정상/정비 확인 고장·다양한 운전 모드·실제 Pi 실행 비용은 검증 범위 밖이다. .2는 임의 변위 스트레스이며 합성 매프레임 manual sample도 포함한다. 이번 새45사건만으로 통계적·현장 우월성을 주장하지 않는다. 개발35와 새45의 성공 사례만 합쳐 최종 성능으로 보고하지 않는다.
