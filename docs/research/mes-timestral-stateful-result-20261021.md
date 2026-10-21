# Pi4용 상태 유지·해제 경보 개선 실험

2026-10-21. PC에서 CPU1thread/interop1/worker1/B1, 기존 FT checkpoint·FP32·68채널·context64·horizon1을 유지하며 경보 후처리를 개선했다. 새 학습·추가 신경망·모델 압축·장치 배포는 하지 않았다. Raspberry Pi 4 Model B Rev 1.5의 RAM과 ARM 속도는 SSH 인증 문제로 여전히 미확인이다. Pi4용 저자원 설정을 유지한 PC 실험과 실제 Pi 탑재 실측은 구분한다.

[최초 사전 고정](mes-timestral-stateful-prereg-20261021.md), [증거 기반 해제](mes-timestral-stateful-release-prereg-20261021.md), [마지막 탐색 범위](mes-timestral-stateful-final-grid-20261021.md), [새 확인 전 선정](mes-timestral-stateful-selection-20261021.md), [테스트·독립 감사](../testing/mes-timestral-stateful-20261021.tdd.md).

**새51사건에서 중복과 탐지지연p95는 낮아졌지만, 탐지율은 EWMA와 같고 오경보 시간이 크게 늘었다. 후보는 채택하지 않고 현재 EWMA를 유지한다.** 같은 새자료의 이전 결합 대비 중복137→27, p958→7초이나 추가 탐지4건을 잃었다. 현재 EWMA대비 중복28→27, p958→7초, 탐지42→42건, 오경보11→82설비·초다. 네 지표의 동시개선에 실패했고 두 요청 지표인 탐지율·오경보도 개선하지 못했다.

## 독립 확인 결과

| 방법 | 탐지/전체 (탐지율) | 미탐 | 오경보 설비·초 | 중복 시작 | 탐지지연p95초 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 현재 EWMA | 42/51 (82.4%) | 9 | 11 | 28 | 8 |
| 정상통계 재적합 EWMA | 40/51 (78.4%) | 11 | 10 | 26 | 10 |
| 기본 FT Timestral | 37/51 (72.5%) | 14 | 12 | 14 | 30 |
| 이전 결합 | 46/51 (90.2%) | 5 | 9 | 137 | 8 |
| 새 상태 유지 결합 | 42/51 (82.4%) | 9 | 82 | 27 | 7 |
| TS 없는 EWMA 상태 유지 | 42/51 (82.4%) | 9 | 61 | 27 | 8 |

현재 EWMA와 새 후보는 동일한42사건을 탐지했다.11건은 더 빨랐고 늦어진 사건은0건이다. 따라서 현재 EWMA대비 p95감소는 다른 사건만 골라 탐지한 효과가 아니다. 반면 이전 결합 대비는4사건 손실·새 획득0, 공통탐지 중17건이 늦고8건이 빨랐다. 이전 결합 대비p95감소만으로 모든 사건의 탐지가 빨라졌다고 해석하지 않는다.

이전 결합은 이번자료에서 탐지율·오경보만 보면 EWMA보다 좋아졌지만 중복137건이 남았다. 이전45사건에서는오경보16대EWMA15로 동시개선에 실패했으므로 이번자료만 골라 기존 결합을 성공으로 승격하지 않는다. 새상태유지는 오경보82로 이 문제를 해결하지 못했다.

TS없는 대조군도 동일42사건·중복27건이다. TS의추가효과는 이자료에서 성공건p95를8→7초로 낮추는 대신 오경보를61→82설비·초로 늘렸다. 모델을 계속 실행해야 얻는 탐지율 확대는 확인되지 않았다.

## 중복 감소와 오경보 증가의 원인 진단

독립 분석에서 새후보의오경보82설비·초 중81은 이미 켜진 경보를 유지하는 중이었다.58은 현재 유지증거가 부족하지만 release2의유예로 이어진 구간이었다. 현재유지증거가 남은24 중EWMA ON은8, TS증거만 남은 구간은16이었다. 이는 모델 상태 분석이며 물리적 고장 원인을 확정한 결과는 아니다.

| 방법 | 전체 경보 시작 | 미일치 시작 | 총 경보 설비·초 | 평균 경보 구간초 | 최대 구간초 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 현재 EWMA | 71 | 29 | 658 | 9.27 | 30 |
| 이전 결합 | 187 | 141 | 381 | 2.04 | 13 |
| 새 상태 유지 | 70 | 28 | 772 | 11.03 | 32 |
| TS없는 상태 유지 | 70 | 28 | 722 | 10.31 | 31 |

최초 고장 전810프레임 경보는 모든방법0이었다. 정상 라벨1403프레임에서 새상태유지12설비·프레임, 대조군7, EWMA0이었다. 활성 원인1098설비·프레임 중 경보는EWMA647, 이전결합372, 새상태유지690이었다. 오래 켜진 경보가 원인 활성 시간과 잘못된 경보 시간을 함께 늘린 것이다. 중복을 줄인 효과를 전체 경보 품질 개선으로 부르지 않는다.

## 그림과 검증

![새51사건 네 지표 비교](../../output/mes-timestral-stateful-figures-20261021/confirmation.png)

![탐지 성공건 지연 분포와 p95](../../output/mes-timestral-stateful-figures-20261021/delay-cdf.png)

![경보 상태 유지 시계열](../../output/mes-timestral-stateful-figures-20261021/alarm-trace.png)

시계열은 이전결합의 경보 시작이 가장 많은 run/설비를 고정 규칙으로 선택하고 동률은 사전식 순서로 골랐다. 좋은 사례만 고르지 않았다. 지연CDF는 미탐을 제외하고 범례에 탐지/전체를 표시한다. 그림 코드가 사건수와 경험적 순위 p95를 저장metrics와 assert로 대조했고 세PNG를 직접 열어 축·범례·시계열을 확인했다.

새자료의 factual replay, 공식모델1888창 예측과6방법의채점을 완료했다. 독립 검토자가 저장 q3/actual에서 점수·rawZ·ratio·reset을 직접 재계산하고 별도 scalar 상태 머신으로 전체경보/metrics/paired events/background/개선관문을 재현했다. 모델·선정·코드·이전실행코드·runtime48파일·fresh prefix·NPZ해시가 모두 일치했다.2400validation행·8runs·test본문0행이며 새결과에서 재탐색하지 않았다.

34개 테스트가 통과했다. 코드 동결 후 새 coverage DB에서34개 테스트와 마지막48개 개발후보 재현을 측정한 줄 커버리지는163 statements 중21 miss, **87%**다. 개발48개 전체metrics·선정·provenance도 원본과 일치했다. 수정 전 코드와 합친 coverage는 보고 수치에서 제외했다. 독립 확인 실제CLI는 별도E2E검증이며 이87%에 합산하지 않았다. branch coverage·그림코드 coverage는 측정하지 않았다. 원본은 `output/mes-timestral-stateful-frozen-lines-20261021.json`과 `output/mes-timestral-stateful-final-green-20261021.txt`다.

## PC 비용

새모델을 추가하지 않았고 상태부는 설비별 boolean·해제카운터와현재rawZ만 더 필요하다. 전체평가용원천자료·모든시점경보목록은 offline분석의저장비용이며 이들을 Pi메모리 요구량으로 해석하지 않는다.

- 기록된 확인단계1270.831초(초기setup 제외),1888창 추론1088.391초, 창당평균.576초다. 새경보2400프레임 재구성은.115초였다. 자료생성·그림·별도테스트는 포함하지 않는다.
- offline프로세스peak RSS551,575,552bytes(약526.0MiB)는 원천자료 로딩까지 포함한다.
- 별도단일프로세스에서 동일checkpoint의기존3입력을12회 측정한 PC추론p50 .712초/p95 .874초, 로딩·추론peak RSS408,846,336bytes(약389.9MiB)였다. 예측은 기존cache와허용오차 내 일치하고 가중치해시도같다. 원본 `output/mes-timestral-stateful-low-resource-pc-20261021.json`이다.

공유Windows AMD64 PC의한번측정이며 Pi4속도·메모리·1Hz마감보장이 아니다. 같은모델의앞선probe와숫자가달라도 모델압축/성능변경효과라고부르지 않는다. 실제Pi에서는 OS/PDA/CNN동시부하를포함해확인해야 한다.

## 무엇을 바꿨는가

이전 결합은 매시점 Timestral 점수를 gate로 써서 EWMA 경보를 끊었다. 새 방식은 설비별 ON/OFF와 해제 카운터를 둔다. OFF 진입에는 현재 rawZ 하한을 요구하고, ON은 현재 EWMA 또는 TS증거가 남아 있을 때 유지한다. rawZ=현재 측정값과 기존 train평균 차이/기존scale의 설비별최대다. 라벨·미래값·고장 종료 정답을 상태에 쓰지 않는다.

선정 설정은 gate0/on_scale1/on_z2.5/off_z1.5/release2/hold_ts.1이다. OFF→ON은 rawZ>=1.5이면서 (EWMA ON 또는 (TSratio>1이고rawZ>=2.5))일 때다. ON은 rawZ>=1.5이면서(EWMA ON 또는TSratio>.1)인 동안 유지하고, 이 조건 미달2회 연속이면 그 현재 프레임부터 해제한다. rawZ누락은 즉시 해제한다. 같은 해제 프레임에 다시 진입하지 않는다. run/time/sequence/mode와 TS 준비 상태 전환에서 초기화한다.

동일 설정에서 TS gate·추가진입·유지증거를 모두 뺀 EWMA 상태 유지 대조군도 비교한다. 이 대조군은 모델 없이 EWMA+rawZ+해제카운터만 사용한다. 후처리 효과를 Timestral 고유 효과로 부르지 않는다.

## 개발 탐색과 선택편향

기존35사건(validation45379..45386)과 이전 확인45사건(validation55379..55386)을 모두 개발 자료로 전환했다. 첫108개는 rawZ 기반 유지, 다음32개는 EWMA 또는 현재 TS증거 기반 유지, 마지막48개는 낮은 진입rawZ와1/2프레임 해제 조합이다. 총188개를 같은80개 사건에서 탐색했다. 데이터는188×80개 독립 사건이 아니다.

| 단계별 진단 선정 | 개발35: 탐지/오경보/중복/p95 | 개발45: 탐지/오경보/중복/p95 |
| --- | --- | --- |
| 현재 EWMA | 29 / 19 / 20 / 10 | 33 / 15 / 20 / 9 |
| 첫108개 중 선정 | 30 / 297 / 14 / 9 | 34 / 274 / 16 / 9 |
| 다음32개 중 선정 | 29 / 0 / 24 / 10 | 33 / 0 / 24 / 9 |
| 마지막48개 중 선정 | 30 / 104 / 15 / 9 | 34 / 105 / 16 / 9 |

오경보 단위는 설비·초, p95는 탐지지연 초다. 두 개발자료 각각에서 탐지수>EWMA, 오경보<EWMA, 중복<=EWMA, p95<=EWMA를 만족하는 후보는 각단계0개였다. 따라서 마지막 후보는 성공 후보가 아니라 사전 고정 위반 최소화 순서로 선택한 진단 후보다. 초기 rawZ 유지가 중복을 줄이면서 잘못된 경보를 오래 유지하는 손실, 빠른 해제가 오경보를 줄이면서 경보를 다시 나누는 손실을 모두 남겼다.

## 독립 확인 설계

코드와 최종 선정 JSON을 `c992f05`에 고정한 뒤 frozen v7 independent seed65371 corpus를 생성했다. validation65379..65386의8run×300초·고장51건을 평가했다. hazard.003/warmup60/response_scale.2, 기존 source·정상·개발 시드와 비중복이다. loader는 train/validation prefix를 읽지만 새train은 적합·채점에 쓰지 않고 test본문은 읽거나 해시하지 않는다. 생성 manifest의 test 건수는 평가 근거가 아니다.

EWMA alpha.4/threshold3, 정상통계는 기존2371..2378 train 정상1386프레임으로 고정했다. Timestral의정상 임계값은35377..35382의288개 정상 보정 창을 재사용했다. 정상통계 재적합 EWMA는35371..35374의640정상프레임을 쓴다. 모델 checkpoint SHA256 `6345f20b018bdb82c4766216b1734679595e08a7cabafa93247a6516eb273ff4`, 파일111,296,432bytes, 전체27,821,184 parameters다.

오경보 설비·초는 활성 원인이 없는 설비의 경보 시간을 합산한 strict 지표다. 다른 설비의 실제 반응과 고장 후 잔류 영향도 포함하므로 현장 오진 확정 시간과 다르다. 사건 탐지는 관측 가능한 활성 원인에 새 경보 시작이 대응할 때다. 경보를 합치면서 두 원인 사건을 하나의 경보로 유지하면 원래 scorer에서 탐지를 잃을 수 있다. scorer를 새 후보에 맞춰 바꾸지 않는다. 탐지지연p95는 성공건만이고 미탐을 함께 읽는다. simulated_at 기준이며 실제추론/큐대기시간은가산하지않는다. 추론p95와 구분한다.

## 재현과 보존

선정 원본은 `output/mes-timestral-stateful-final-development-20261021/result.json`, SHA256 `3164d51981298760bfd3bd2a7b5c30a85e2b0b5e648f38c7a58c8b23b7f4ef77`다. 실행 코드 SHA256은 `97f10ee72376875acf2faa3215ee4ad84eb5162e4ff0914fec6c429f7458d6a8`이며 확인 결과를 보고 바꾸지 않는다. 원천자료·checkpoint·예측·JSON은 ignored output에 보존하고 Git에는 코드·문서만 넣는다.

```powershell
$experimentPython = Join-Path $env:TEMP 'shiftlink-timestral-20261021/Scripts/python.exe'
& $experimentPython scripts/mes_timestral_stateful.py --phase confirm --fresh output/mes-timestral-stateful-confirm-v7-seed65371-20261021 --selection output/mes-timestral-stateful-final-development-20261021/result.json --out-dir output/mes-timestral-stateful-confirmation-replay-20261021
```

출력은 새 폴더여야 한다. 코드·선정·모델·정규화 통계 해시가 다르면 실행을 거부한다. 기존 frozen inference/scorer를 호출하며 새 규칙은 별도 스크립트에 둔다. 프로젝트 의존성·기존 결과·PDA/Jetson/Pi 서비스는 변경하지 않았다.

합성 running모드/.2스트레스의 한정된 결과다. 현장 정상과 정비 확인 고장·다양한 모드·실제 Pi4 부하·실측 통계적 우월성은 검증하지 않는다. 개발188회 탐색의 선택편향 때문에 독립 확인 결과만 따로 읽어야 한다.
