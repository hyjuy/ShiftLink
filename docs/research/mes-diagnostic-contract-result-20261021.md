# D16/D17 결과 — 평가 계약 채택, 방향 보존 EWMA 보류

2026-10-21. 사용자 요청에 따라 현재 수집 방식에서 실험을 실행했다. **원인·반응·시간 문맥의 평가를 추가하고 기존 strict 점수는 유지한다.** 조건부 signed EWMA 후보는 탐지 지연과 경보 분절 때문에 보류했다. 운영 예측기와 배포는 변경하지 않았다.

[사전 등록](mes-diagnostic-contract-prereg-20261021.md), [원본 수치·trace](../../output/mes-diagnostic-contract-validation-20261021.json), [TDD 근거](../testing/mes-diagnostic-contract-20261021.tdd.md).

## 현재 입력과 실험 고정

- 구성 `23e0e6b3aa6f073857d48e81fd7430068ee40ca2f0cfe77147bae37741a0b036`. 69위치 중 최신 good 유한값은 매 프레임68개다. `EQ-0007 / rt_lift_delay` event만 unavailable이다. continuous59, derived4, manual_sample5, event1이며 합성 시료5개는 현재 매 프레임 갱신된다. 68개 모두를 연속 센서로 부르지 않는다.
- 현재 소스48개를 [고정 runtime](../../output/mes-diagnostic-runtime-20261021/provenance.json)에 복사했다. 공유 작업의 운영 변경은 되돌리지 않았다. 생성 후·점수 확인 전에 전역 상태 flag 이름과 IF 후행 입력 설명 두 가지를 정정하고 이전/새 해시·이유를 provenance에 남겼다. 생성기와 수치 계산은 그 정정에서 바뀌지 않았다.
- 독립 v7 full1.0/weak.2, seed2371..2394, 각 train/validation/test는8run×300초다. 두 팔은 **같은46개 validation 사건**이며 독립92사건이 아니다. full train2371..2378만 적합에 사용했다. 정상1386프레임, 설비별 완전 정상8프레임 창1147개, 관측률 마스크 합68개다.
- EWMA alpha.4/threshold3, robust z6, IF200trees/seed20261020/.65를 고정했다. 새 임계값 검색과 RF 추가는 하지 않았다. D15의 이전63채널·다른 구성·다른 사건과 직접 개선율을 비교하지 않는다.
- 각 팔 factual2400프레임 재현 및 고장 전606프레임 twin 동일성이 통과했다. 링크 제거255프레임/546값, 모든 고장 제거738프레임/2845값이 달랐다. full/weak의 시각·일정·고장 전 측정도 일치했다.
- 독립 감사는 양팔 각각 train+validation4800프레임의 위치·최신값·join을 확인했다. prefix 전체의 고장 전 동일1257프레임과 주입 후 차이1896프레임은 양립한다. 이번 validation에서는 고장 라벨이 없는 시점의 두 팔 차이가0이었다. 고장 후 정상 라벨이라는 이유로 동일성을 강제하지 않았다.

## 동일 조건의 기준 모델

| 반응 | 모델 | 원인 사건 탐지 | 미일치 경보 시작 | 중복 시작 | 오진 합집합 초 | 오진 설비·초 | 탐지 지연 p95초 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| full | EWMA | 44/46 | 31 | 14 | 286 | 358 | 3 |
| full | robust z | 44/46 | 67 | 67 | 0 | 0 | 5 |
| full | IF | 27/46 | 112 | 44 | 189 | 328 | 5 |
| weak .2 | EWMA | 35/46 | 30 | 30 | 21 | 21 | 14 |
| weak .2 | robust z | 3/46 | 3 | 3 | 0 | 0 | 5 |
| weak .2 | IF | 27/46 | 113 | 48 | 124 | 249 | 15 |

robust z의 오진 시간0은 약한 고장 미탐과 중복 경보 문제를 해결했다는 뜻이 아니다. 연구 기준은 EWMA를 유지한다. 이 모델은 설비 위치 탐지기이며 원인 유형 분류의 실측 성능을 검증한 것이 아니다.

## 오진 시간을 지우지 않고 설명하기

아래는 기존 strict 오진 설비·초의 상호 배타적 분할이다. 원인 활성 구간은 올바른 경보로 별도 기록했다. 모든 경보 설비·초, strict wrong 설비·초, strict wrong 합집합 초가 여섯 모델 결과에서 기존 scorer와 정확히 일치했다.

| strict wrong 문맥 | EWMA full | EWMA weak | robust full/weak | IF full | IF weak |
| --- | ---: | ---: | ---: | ---: | ---: |
| 로컬 episode의 intensity0 구간 | 147 | 20 | 0/0 | 44 | 18 |
| 로컬 고장 종료 뒤0..7초 | 82 | 1 | 0/0 | 102 | 60 |
| 다른 원인 활성 중 현재 숫자 반응 | 124 | 0 | 0/0 | 16 | 6 |
| 현재 twin 숫자·유효 집합 동일 | 5 | 0 | 0/0 | 166 | 165 |
| 합계 | 358 | 21 | 0/0 | 328 | 249 |

비교 불가와 남은 twin 차이는 이번 경보에 없었지만 코드와 테스트에서 보존한다. EWMA full의 마지막5설비·초는 모두 **이전 고장 이후**이며 최초 주입 전은0이다. 현재값 동일만으로 정상 이력의 오경보라고 단정할 수 없다. EWMA 기억과 IF 후행8프레임에는 과거 차이가 남을 수 있다.

full/weak 각각 숫자 반응1440설비·초 중 EWMA 경보 coverage는931/451, robust761/36, IF348/226이다. remote 반응532설비·초 중 EWMA131/0, robust0/0, IF25/9다. 이는 설비·시간 coverage이며 사건 재현율이 아니다. 숫자 차이는 합성 개입 민감도이며 공학적 중요도나 단일 고장의 물리적 인과관계를 증명하지 않는다.

## D17: 조건부 후보의 득실과 보류

abs를 먼저 적용한 누적에 의존하는 strict wrong은 full15/358=4.19%, weak4/21=19.05%였다. 사전 등록한 임의 연구 기준10%를 weak가 넘겨 signed EWMA 후보 하나를 검토했다. 매 프레임 후보가 기준의 부분집합인지도 확인했다. [NIST의 EWMA 설명](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc324.htm)은 관측값을 먼저 평활하는 일반 정의의 근거이며, 프로젝트 alpha.4/threshold3의 현장 보정 근거는 아니다.

| 반응 | 사건 탐지 | 미일치 시작 | 중복 시작 | 오진 설비·초 | 오진 합집합 초 | 전체 p95 |
| --- | --- | --- | --- | --- | --- | --- |
| full 기준→후보 | 44→44/46 | 31→34 | 14→17 | 358→343 | 286→274 | 3→3 |
| weak 기준→후보 | 35→35/46 | 30→32 | 30→32 | 21→17 | 21→17 | 14→14 |

상쇄된 총계만 보면 놓치는 손실이 있다. full 기존7사건, weak 기존5사건이 각각1초 늦어졌다. full `EQ-0004`, `EQ-0005`, `bearing_drag` p95와 weak `EQ-0001`, `hydraulic_leak`, `heat_rejection_loss` p95가 악화했다. 정확한 run ID/episode ID와 전후 지연은 원본 `conditional_D17.arms.*.delayed_existing_events`에 있다.

숫자 반응 coverage도 full11설비·초(원인7·종료 후1·다른 원인3), weak5설비·초(모두 원인 활성)를 잃었다. 각 팔에서 미일치 시작·집단 지연·중복·개별 사건 지연·반응 손실의 **7개 관문 실패**를 독립 검토자가 재계산했다. D17은 보류하며 재튜닝과 신규 확인을 하지 않았다. 후속 D18은 원래 경보를 그대로 보존하는 별도 [알림 계층 실험](mes-notification-prereg-20261021.md)이다.

## 재현·비용·한계

학습9.174초, 재생 검사·적합·채점·계측을 포함한 본 실행203.370초다. 데이터 생성 시간은 이 수치에 포함하지 않는다. 원본 test4800행은 생성됐지만 읽거나 평가한 행은0이다. 현장 자료·실제 정비 확인·다양한 운전 모드·장치 성능은 미검증이다. oracle 정상 선택, 중첩 창, 합성 단일 running 모드 한계를 유지한다. v6 .2는 무효이며 v7 .2도 임의 스트레스다.

```powershell
.venv/Scripts/python.exe output/mes_diagnostic_coverage_20261021.py --runtime output/mes-diagnostic-runtime-20261021 --report output/mes-diagnostic-reproduction-coverage.json --full output/mes-fault-current-v7-seed2371-full-20261021 --weak output/mes-fault-current-v7-seed2371-weak-20261021 --out output/mes-diagnostic-reproduction.json
```

새 출력 이름을 써야 하며 기존 결과 덮어쓰기는 거부한다. 실행에 필요한 snapshot과 대형 자료는 ignored `output/`에 있고 Git에는 포함하지 않는다. 같은 스냅숏에서 builder의 `--seed 2371 --runs-per-split 8 --ticks 300 --hazard .003 --warmup-ticks 60 --profile independent --response-scale 1` 및 `.2`로 생성했다. snapshot은 소스48개와 카탈로그 해시를 보존한다. 연구 코드와 테스트만 커밋했으며 공유 작업의 운영 변경은 보존했다.
