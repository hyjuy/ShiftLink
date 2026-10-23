# MES v9 지속 증거·센서 고착 검증 기록

범위는 새 로컬 자료·후보·추가학습·고정 후 시험이다. Pi·PDA·MES 운영 서비스와 기존 경보는 변경하지 않는다. v8 결과를 수정하지 않는다.

## 원인 재현과 RED/GREEN

v8 A 정상 실행의 저장 예측을 다시 계산해 결합 통지 27개 중 12개가 당시 TS 보정 ratio ≤1에서 발생했음을 확인했다. TS 보정만으로 다른 raw_z 경로의 통지를 제한하지 못한다. 고착은 변동 소실을 검사하는 경로가 없고, v8 시험의 고착 첫 통지 매칭은 1/10이었다. 이 관찰은 계측·통지 설계 개선 근거이며 현장 원인 진단이 아니다.

| 단계 | 체크포인트 | 확인 |
|---|---|---|
| RED | `555db14` | 새 모듈 부재로 지속·고착·reset·잠금 테스트 실행 실패 |
| GREEN | `81c0923` | 단발 충격 억제·지속 변화 첫 통지·변동 채널 한정 고착·결측/reset 검사 4개 통과 |
| RED | `731a575` | 현재 관측이 전부 불량인데 유지된 EWMA가 통지를 만드는 경계 재현 |
| GREEN | `6a19490` | 현재 good 관측이 없으면 지속 증거를 허용하지 않도록 교정, 동일 검사 포함 5개 통과 |
| 통합 | `a62e3c1` | HTTP A/B 수집·정상 12초 반복 관측·paired 우연 일치 제외·정상 예산 우선 선택, 새 8개 통과 |
| 회귀 | `b96745d` | 새 8개+기존 29개 총 37개 통과(27.669초); v8 head의 공식 forecast 직접 대조를 시험 실행에 추가 |

## 실행

기존 연구 환경을 그대로 사용하고 Hugging Face/Transformers offline 설정을 유지한다.

```powershell
$modelPython=Join-Path $env:TEMP 'shiftlink-timestral-20261021/Scripts/python.exe'
& $modelPython -X utf8 -B -m unittest tests.test_mes_causal_v9 tests.test_mes_causal_benchmark tests.test_mes_causal_train tests.test_mes_causal_contract_edges tests.test_mes_timestral_tail_guarded
& $modelPython -X utf8 -B -m scripts.mes_causal_v9_run --out output/mes-causal-v9-20261023 --phase train
& $modelPython -X utf8 -B -m scripts.mes_causal_v9_run --out output/mes-causal-v9-20261023 --phase test
```

산출물 경로가 이미 있으면 덮어쓰지 않고 실패한다. 재현에는 별도 새 경로를 사용해야 하며 이미 사용한 시험을 다시 미사용이라고 부르지 않는다. test는 train의 후보 잠금 이후에만 생성 가능하다. training/test coverage는 별도 파일에 기록해 원본 v8 coverage를 변경하지 않는다.

최초 train은 개발 예측의 상대 경로 `development.npz` 생성에서 `OSError: [Errno 22] Invalid argument`로 중단됐다. 해당 파일은 생성되지 않았고, 같은 폴더의 별도 절대 경로 생성은 성공해 원인은 미확인이다. 최초 산출물과 생성 시험 파일도 삭제하지 않았다. 이후 `3813dc9`에서 구간 재사용·입력/모델 불일치 거부·독점 저장 실패를 먼저 검사하고, `b7c698c`에서 GREEN을 확인했다. `5497358`에서 저장된 checkpoint·정상 특징·보정 NPZ를 재사용하는 잠금 전 resume를 추가했다. 새 10개+기존 29개 총 39개 통과(38.992초). 복구는 `--phase resume`이며 정상 head 재현이 실제 checkpoint와 일치해야 진행한다. 개발 추론은 `development-recovered.npz`와 128창별 독점 저장을 사용한다. 후보·시험 결과를 다시 튜닝하는 경로가 아니다.

데이터 설계·개발 예산·선택 순서는 [사전 명세](../research/mes-causal-v9-prereg-20261023.md)에 고정했다. 최종 실제 학습·평가·커버리지·보존 감사는 완료 후 별도 결과 문서와 함께 기록한다. 브라우저 UI E2E는 변경 범위 밖이며 이번 E2E는 localhost 수집→모델→통지→paired 장부 채점이다.

## 최종 확인

복구 정상 head는 최초 저장 checkpoint와 비트 단위로 일치했다. 선택 epoch 5, checkpoint SHA-256은 `efc0e5839767c88a83f121f66b2c6b16260f867cef8992a1b6b2055ab3502351`이다. 개발 종료 후 full은 q=.995, 지속 8, 고착 대기 16으로 고정했다. 개발 정상 통지는 1/1,920초라 사전 목표 시간당 1회 이하를 충족하지 못했으며, 사전 명세의 목표 미달 시 최소 통지율 선택 규칙을 적용했다. 이후 시험으로 재선정하지 않았다.

새 시험은 22실행·12 seed group, 고장 30개(고착 10개)와 paired control이다. 모든 예측 저장 후 장부를 열었다. full은 21/30건, 배경 제외 21/30건, 고착 10/10건, 중복 0건, 정상 통지 2/3,840초, 성공 건 합성 p95 31초다. 같은 입력의 v8은 17/30건, 배경 제외 7/30건, 고착 3/10건, 중복 3건, 정상 통지 352/3,840초, p95 45초다. 누설은 새 후보가 0/6건으로 모두 미탐했다. TS 제거 및 v8 head 대조는 새 full과 같은 결과다.

현재 소스와 일치하는 단위·resume·test coverage만 합산했다. 최초 중단 train의 예전 줄 위치 자료는 합산하지 않고 보존했다. 새 3모듈은 **373/410문장, 90.98%**이며 v9/core와 cache는 100%, runner는 84%(반올림)다. 문장 커버리지이며 모든 운영 상황을 검증했다는 뜻은 아니다. 예측 두 종류 모두 [7040,63,3], 비유한값·분위수 역전 0개다. 개발 4쌍·시험 10쌍의 개입 전 센서값 일치, 69신호·단위·유한값·bool·config·1초 시각·역할 분리와 해시를 감사했다. 보호 파일 171개·잠금 파일의 대상 226개가 유지됐다.

기계 판독 근거는 `output/mes-causal-v9-20261023/`의 `training/recovery-check.json`, `training/settings.json`, `candidate-lock.json`, `evaluation/result.json`, `final-audit.json`, `coverage-summary.json`이다. [결과와 남은 한계](../research/mes-causal-v9-result-20261023.md)에 전체 대조와 유형별 실패를 기록했다. 정상 통지 예산 미달·누설 미탐·실측 미검증으로 운영 연결은 보류하며 Pi·기존 경보는 변경하지 않았다.
