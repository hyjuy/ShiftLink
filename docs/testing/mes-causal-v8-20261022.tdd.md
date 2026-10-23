# 인과 합성 MES v8 검증 기록

범위: 별도 localhost 센서 MES, A/B 정상 동역학, 자료 분리, 정상 예측 헤드 재학습, 고정 후보의 네 시험군 비교. 기존 MES/PDA 서비스와 Pi는 변경하지 않는다.

## RED → GREEN 근거

| 요구 | 실패를 먼저 확인한 체크포인트 | 구현·교정 체크포인트 | 검증 |
|---|---|---|---|
| 단일 센서 오류 비전파, 공정 개입 지연, HTTP·69신호·64프레임 계약, 시험 접근 제한 | `79352ba` 모듈 부재 | `022c78c` | `tests/test_mes_causal_benchmark.py` |
| fit 전용 통계, 정상 분위수 보정, 실제 작은 Timestral 추론, 역할 중복 거부 | `cb0b718` 모듈 부재 | `610e4ed` | `tests/test_mes_causal_train.py` |
| bool 0/1, 정상에도 범위 이탈 허용 | `d698405` | `610e4ed` | 양쪽 생성기 240틱 계약 검사 |
| 40°C 조건화 시료·형상에 운전 온도 인과식을 강제하지 않음 | `2932220` | `19701fd` | 두 생성기에서 온도 상승과 시료·형상 불변을 함께 검사 |
| 정상 전용 노출과 잔류·하류 반응 구분, 제거 대조의 중립 ratio | 기존 검사 재실행 | `e39b4a9` | 새 14개 + 기존 guarded 12개, 총 26개 통과 |

`1b51823`의 초기 점도 방향 가정은 카탈로그를 재검토한 뒤 폐기했다. 조건화 시료를 운전 중 점도로 오인한 테스트를 성공 근거로 세지 않는다. 초기 `data/`, `data-v2/`, 중단된 첫 `training/`은 보존하고 최종 학습에 사용하지 않았다.

## 실행 명령

저장소 루트에서 아래 Python은 기존 로컬 연구 환경의 실행 파일이다. 설치·다운로드 없이 `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`로 실행한다.

```powershell
$modelPython = Join-Path $env:TEMP 'shiftlink-timestral-20261021/Scripts/python.exe'
& $modelPython -X utf8 -B -m unittest tests.test_mes_causal_benchmark tests.test_mes_causal_train tests.test_mes_timestral_tail_guarded
& $modelPython -X utf8 -B -m scripts.mes_causal_train --out output/mes-causal-v8-20261022/run-final --data output/mes-causal-v8-20261022/data-v3 --phase train
& $modelPython -X utf8 -B -m scripts.mes_causal_train --out output/mes-causal-v8-20261022/run-final --data output/mes-causal-v8-20261022/data-v3 --phase evaluate
```

학습·평가 명령은 산출물이 이미 있으면 실패하는 보존용 실행 경로다. 재현 시에는 원본 경로를 지우지 말고 별도 새 경로를 사용해야 한다. 평가 재실행 자료를 다시 미사용 평가셋이라고 부르지 않는다.

실제 확인: 최종 26개 테스트 통과(23.757초), 정상 학습 5 epochs 완료, backbone 불변·head 변경 확인. 새 프로세스에서 체크포인트 재로딩 후 정상 창 3개의 공식 forecast와 특징 재구성 결과를 `rtol=1e-5, atol=1e-5`로 비교해 통과했다(최대 절대 차이 0.00025177001953125). 절대 차이가 0이라고 표현하지 않는다.

후보 고정 후 `tests/test_mes_causal_contract_edges.py`의 추가 3개 검사도 통과했다(0.009초). 공통 준비 전 통지의 정상 오통지율 제외, 불량·오래된 관측·비유한값·단위 불일치 제외와 중복 측정 거부, 정지·순번 누락 후 64개 과거 프레임 재준비를 확인했다. 추가 검사는 기존 동작의 회귀 확인이며 후보 코드·파라미터를 수정하지 않았다. 따라서 검증 수는 26개+3개다.

단위 검증만의 새 6개 모듈 문장 커버리지는 65%다. 전체 학습·평가 실행 경로는 별도 실제 실행으로 검증하며, 최종 평가·커버리지·보존 감사 결과는 연구 결과 문서에 기록한다. UI 변경이 없어 브라우저 E2E는 범위에 없고, localhost HTTP 수집→고정 모델→네 비교군→장부 채점이 이번 E2E다.

최종 단위·추가 경계·실제 평가 E2E 합산은 626문장 중 563문장, **89.94%**다. source/challenge/schema/score는 100%, data는 95%, train은 78%다(표시 반올림). 학습 함수는 별도 실제 완료 실행으로 검증했으며 커버리지를 올리기 위해 다시 학습하지 않았다. 이는 문장 커버리지로, 모든 분기·현장 상황을 검증했다는 뜻은 아니다. `coverage/summary.json`과 `coverage/verified-db`를 최종 근거로 사용한다. 최초 보고에서 DB와 같은 접두사의 JSON을 도구가 DB로 오인한 경고가 있어 해당 파일을 보존하고 서로 다른 이름으로 재집계해 경고 없이 확인했다.

평가 4군의 총 60개 사건과 정상 전용 준비 이후 1,280초를 모두 채점했다. 고정 파일 38개·보호한 원본 71개 불변, 전체 8역할의 run/seed/nonce 분리와 69채널·단위·1초 시각 계약을 최종 감사했다. 결과는 [연구 결과](../research/mes-causal-v8-result-20261022.md), 기계 판독 근거는 `output/mes-causal-v8-20261022/run-final/post-test-audit.json`이다.

## 남는 한계

생성기의 정성적 인과 가정·카탈로그·작성자는 공유한다. 모든 69신호의 보정 물리를 구현하지 않았다. Pi 처리량·실측 센서·운영 경보·네트워크·화면까지의 끝단 지연은 이번 검증 대상이 아니다.
