# Timestral-28M 비교 검증 근거 — 2026-10-21

사용자 요청: 현재 EWMA 대비 약한 고장 탐지율, 오경보, 중복 경보, 탐지 지연을 실제 모델 실행으로 비교한다. 설계는 [사전 고정 문서](../research/mes-timestral-prereg-20261021.md), 결과는 [연구 보고서](../research/mes-timestral-result-20261021.md)에 둔다.

## RED → GREEN

- `b2c8433`: 구현 전 causal windows / quantile score / normal calibration / threshold mapping / comparison gates를 `NotImplementedError`로 두고 7개 테스트를 실행했다. `Ran 7 tests`, `FAILED (errors=7)`이며 의도한 미구현 경로에서 실패했다. `output/mes-timestral-red-20261021.txt`에 보존했다.
- `9b36e4d`: 최소 구현과 forecast adapter / 보존 / background 보조 검증까지 10개 테스트가 통과했다. `output/mes-timestral-green-20261021.txt`는 이 시점의 로그다.
- `44c9ac1`: 독립 설계 검토 후 학습 원천·정규화 통계 해시, full/weak pairing과 독립 시드 검사를 추가했다. 결과 확인 전 난수 처리량 측정으로 계산 설정만 정정했다. 최종 12개 테스트가 통과했다.

```powershell
$experimentPython = Join-Path $env:TEMP 'shiftlink-timestral-20261021/Scripts/python.exe'
& $experimentPython -m unittest tests.test_mes_timestral_comparison
& $experimentPython -m coverage report --data-file=output/mes-timestral-coverage-20261021 --include='*/scripts/mes_timestral_comparison.py'
```

기존 데이터의 실제 실행까지 합친 줄 커버리지는 244 statements 중 11 miss, **95%**였다. branch coverage는 측정하지 않았다. 새 시드 실행까지 포함한 최종 수치는 연구 보고서와 원본 coverage JSON에 기록한다.

## 보장하는 동작

| 테스트 | 검증 내용 | 종류 |
| --- | --- | --- |
| causal windows | 현재값 t를 입력에 넣지 않고 과거64개만 사용, 다른 run 이력을 섞지 않음 | unit |
| mode/time reset | 정지·시간 단절을 넘어 이력을 연결하지 않음 | unit |
| missing values | 누락은 NaN이며 예측 API에 label 인자가 없음 | unit |
| asymmetric quantiles | 비대칭 q01/median/q99, train scale 하한, 비정상 분위수·무한값 거부 | unit |
| clean calibration | 과거64개와 현재 모두 faults=[]인 학습 창만 보정에 사용 | unit |
| equipment thresholds | 설비별 .995 분위수(method=higher), 최소1, 엄격한 > 경보 | unit |
| comparison gates | 탐지 손실을 짧은 지연으로 상쇄하지 않음, 엄격한 개선 필요 | unit |
| forecast adapter | 입력·출력 축, 정상 창 subset, NPZ 저장, 기존 파일 덮어쓰기 거부 | integration |
| runtime integrity | provenance 해시 변경과 JSON 덮어쓰기 거부 | unit |
| background | 최초 고장 전·정상 라벨 시각·활성 원인 경보 집계 분리 | unit |
| calibration provenance | 다른 학습 정규화 통계의 보정값 재사용 거부 | unit |
| seed pairing | full/weak pairing 불일치 및 train/validation·confirmation 시드 중복 거부 | unit |

## 실제 모델과 독립 감사

Timestral 공식 코드 commit `a534bdbd244d64f3d9d743f46c7bf6fc330ed4ff`, 가중치 revision `49b26409ac87b5935539a5d8ffe7f397b720db47`를 CPU에서 실행했다. 실제 예측을 사용한 CLI 실행은 별도 E2E 근거다. mock adapter 결과를 성능 수치로 쓰지 않았다.

독립 검토자는 모델을 재실행하지 않고 원천 데이터와 저장 예측으로 다음을 확인했다.

- 보존 runtime48개 파일과 provenance 해시 일치.
- 정상 train1386프레임, 선택68채널, 과거64+현재 정상171창과 저장 key 집합 일치.
- 저장 actual과 원천 측정값 일치. 비대칭 점수·설비 최대·임계값의 별도 수식 계산이 저장값과 정확히 일치.
- 기존 validation 양팔 NPZ 임계값 판정과 JSON 경보, frozen scorer 전체 metrics·paired events·background 및 개선 관문 재계산 일치.
- code/calibration/forecast/train+validation prefix 해시 일치. full/weak는 동일46사건이며 두 배로 세지 않음.

고장·정상 라벨은 보정 선택과 채점에만 쓰며 예측에는 전달하지 않는다. test 본문은 읽거나 해시하지 않는다. 운영 예측기·화면·배포는 이 실험에서 변경하지 않았다.

## 새 시드 최종 확인

실제 새 validation seed는15379..15386이며 생성 시작 시드15371과 구분한다. 독립 검토자는 작은 메모리의 prefix stream으로 full/weak 동일42사건, 기존 전체 run의 seed·ID와 비중복, NPZ→경보 판정·전체 metrics·사건별 손익·background·양쪽 개선 관문의 정확한 일치를 확인했다. code/calibration/forecast/prefix/runtime48파일 해시가 모두 일치했다. test 본문은0행이었다.

새 weak는 EWMA36/42→Timestral30/42, 오경보23→73설비·초, 중복36→18, p95는20→20초다. 기존 탐지11건을 잃고5건을 얻었다. 이는 보정값을 바꾸지 않은 새 시드 확인에서도 전반 개선을 지지하지 않는다는 결과다.

최종 `python -m unittest tests.test_mes_timestral_comparison`은 **12 tests / OK**였고 `output/mes-timestral-green-final-20261021.txt`에 보존했다. 두 실제 실행까지 포함한 최종 줄 커버리지도244 statements /11 miss / **95%**였다. coverage JSON은 coverage DB의 자동 병합 파일 이름과 충돌하지 않게 `output/mes-timestral-line-coverage-20261021.json`에 보존했다.
