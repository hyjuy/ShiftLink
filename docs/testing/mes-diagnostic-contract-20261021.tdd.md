# D16/D17 평가 계약 — TDD와 검증

사용자 여정: 현재 MES 수집 계약을 고정하고, 원인/반응/시간 문맥을 기존 점수와 대조한 뒤, 개별 사건을 늦추는 후보를 승격하지 않는다. [사전 등록](../research/mes-diagnostic-contract-prereg-20261021.md), [결과](../research/mes-diagnostic-contract-result-20261021.md).

## RED → GREEN

- core 테스트를 먼저 작성해 `ModuleNotFoundError: No module named 'scripts.mes_diagnostic_contract'`를 확인했다. RED 체크포인트 `fd48c19`.
- runtime 복사와 비교 실행기 테스트도 모듈이 없는 RED를 확인한 뒤 구현했다. 현재 운영 파일을 복구하지 않고 그대로 고정하며, 복사 중 소스 변경이면 유효 provenance를 쓰지 않는다.
- 초기 관련35검사 GREEN `01b017b`. 전역 상태 flag 표현과 방향 반전 분절/반응 coverage 손실을 강화한 체크포인트 `3369350`.
- race 반례까지 포함한 새15검사 통과, 기존 scorer와 release 회귀를 포함한 **38검사 통과**(27.907초). 가장 작은 관련 묶음으로 검증했으며 UI/API/배포는 변경하지 않았다.

```powershell
.venv/Scripts/python.exe -m unittest tests.test_mes_diagnostic_contract tests.test_mes_diagnostic_review tests.test_mes_research_runtime tests.test_evaluate_mes_fault_models tests.test_mes_ewma_release_review -q
```

실제38개 실행은 고정 runtime을 `sys.path` 첫 위치에 두고 위 모듈을 같은 unittest loader로 수집했다. 공유 운영 코드가 추가 변경되더라도 이번 수치의 의존 파일은 snapshot에 고정되어 있다.

## 보장하는 동작

| 경계 | 검사 |
| --- | --- |
| 문맥 분할 | source/episode-off/post-end/remote/background/incomparable가 배타적이며 비균일 간격의 시간 합도 기존 score와 일치 |
| 숫자 의미 | 위치키 연결, record 순서·metadata 배제, 단위·quality·fresh·중복·유한값 검사 |
| 정답 격리 | predictor가 label/twin을 입력으로 사용하지 않고 mode/run 경계를 초기화 |
| 후보 반례 | 방향 반전으로 지연/경보 분절, 반응 coverage 및 개별 사건 손실이 생기면 보류 |
| 학습 격리 | 완전 정상8프레임 창만 IF 학습, 이상 마지막 프레임이 정상 통계에 들어가지 않음 |
| 짝 자료 | 최초 고장 전 동일성·시각/일정 확인, 주입 뒤 차이를 잘못 거부하지 않음 |
| 코드 고정 | 과거 runtime을 덮어쓰지 않음, 복사 도중 변경 시 중단하고 provenance 미생성 |

실제 크기 실행은 양팔 재생 검사를 적합보다 먼저 통과했고, 원본 test 행을 읽지 않는 train/validation 전용 loader를 사용했다. 독립 검토자가48개 소스·두 prefix 해시, 여섯 모델의 집계, 양팔2400프레임 후보 부분집합, 각7개 실패를 저장 산출물로 재검증했다.

## 커버리지와 공백

외부 coverage 패키지를 설치하지 않고 Python3.13 `sys.monitoring`의 해당 코드 객체 local LINE 이벤트를 사용했다. 새15검사와 실제 실행의 같은 소스 해시를 확인한 뒤 합쳤다.

| 파일 | 실행 줄/가능 줄 | 줄 커버리지 |
| --- | ---: | ---: |
| mes_diagnostic_contract.py | 120/126 | 95.24% |
| mes_diagnostic_review.py | 199/213 | 93.43% |
| mes_research_runtime.py | 24/29 | 82.76% |

[원본 집계·누락 줄](../../output/mes-diagnostic-coverage-20261021.json). branch 커버리지는 측정하지 않았다. 실측 고장 진단, 다중 운전 모드, 배포 안정성은 이번 검증 범위가 아니다.
