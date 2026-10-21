# D15 정상 학습 출처 실험 — TDD 근거

사용자 요청은 다음 MES 실험 진행이다. [사전 등록](../research/mes-training-source-prereg-20261021.md)에 따라 사용자 여정을 '정상 생성 경로가 달라도 모델·전처리·창 수를 고정한 비교를 재현하고, 시험 행을 읽지 않은 결과로 승격 여부를 판단한다'로 정했다. UI나 API는 바꾸지 않는 오프라인 CLI 실험이다.

## RED → GREEN

1. 새 API를 먼저 참조한 `tests/test_mes_training_source.py`를 실행했다. `ModuleNotFoundError: No module named 'scripts.mes_training_source'`로 실패했다. 필요한 비교 실행기가 아직 없다는 의도된 RED다. 체크포인트 `cbd92b9`.
2. 최소 비교기를 구현한 뒤 초기 6개 테스트가 통과했다. 독립 비판자가 정상 구간 집계가 sequence gap을 놓치는 반례를 찾았다. 별도 테스트를 먼저 실행해 `AssertionError: 1 != 2`를 재현했다. 체크포인트 `296aa8e`.
3. sequence 연속성을 검사하고, 사전 재현 검사를 모델 적합/점수 계산보다 먼저 수행하며, 참조·전처리·읽은 prefix 해시를 보존했다. 관련 테스트 36개가 통과했다. GREEN 체크포인트 `f88556c`.

아래는 동일 타깃의 표준 재실행 명령이다. 실제 36개 실행은 아래 설명한 inline collector에서 이 세 모듈을 같은 unittest loader로 수집했다.

```powershell
.venv/Scripts/python.exe -m unittest tests.test_mes_training_source tests.test_mes_forest_models tests.test_evaluate_mes_fault_models -q
```

처음 36개 실행은 stdlib 기반 coverage collector 안에서 수행됐다. 테스트 자체는 모두 통과했지만 Python3.13의 executable line marker `None` 때문에 **테스트 종료 뒤 집계만 실패**했다. 이를 숨기지 않고 집계기를 정정해 고정 연구 환경에서 새 테스트 7개를 다시 실행했다. 7개가 통과했고, 실행 가능 줄 262개 중 239개, **91.221%**를 관측했다. 기본 coverage 패키지는 설치하지 않았다. 방법과 누락 줄은 [원본 coverage](../../output/mes-training-source-coverage-20261021.json)에 있다. 이는 줄 커버리지이며 branch 커버리지 보장은 아니다.

## 보장하는 동작

| 보장 | 테스트 | 종류 | 결과 |
| --- | --- | --- | --- |
| 두 출처 창 수가 같고 hash 표집이 결정적이며 시간 순서를 보존 | matched_sampling | unit | PASS |
| 8프레임 모두 정상인 창만 선택 | only_all_healthy | unit | PASS |
| sequence gap과 run 경계를 정상 구간으로 합치지 않음 | healthy_spans | unit | RED 확인 후 PASS |
| 부족한 표본·다른 차원·비유한 값·설비 누락은 중단 | bad_count_dimension | unit | PASS |
| 출처 seed/run 중복과 잘못된 생성기 거부 | sources_reject | unit | PASS |
| intensity0 및 그 뒤 7프레임을 정상 배경에서 제외 | background_excludes | unit | PASS |
| 실제 데이터 생성→읽기→적합→재현→채점 경로가 손상된 시험 행을 읽지 않음 | tiny_end_to_end | integration/E2E CLI core | PASS |

기존 forest 및 scorer 회귀도 함께 통과했다. 실제 크기 실행의 CLI 결과·재현 수치는 [결과 보고서](../research/mes-training-source-result-20261021.md)에 기록한다. 소규모 통합 테스트와 실제 실험 모두 모델/전처리 적합은 train만, 평가의 label 사용은 정상 선택·채점·사후 진단에 한정한다.

## 고정 환경과 알려진 공백

공유 작업 폴더에서 시료 수집 관련 코드가 동시에 바뀌어 첫 비교가 **점수 계산 전에** 구성 검사로 중단됐다. ID 검사를 우회하지 않았다. 운영 파일을 되돌리지 않고 `output/mes-training-source-runtime-20261021/`의 고정 스냅숏에서 검사를 재실행했다. 독립 감사자가 45개 파일 해시, 이전 수집 파일 3개와 HEAD의 바이트 일치, 과거 검증 2,400프레임과 고장 전 662프레임의 동일성을 확인했다.

실측 고장·다양한 운전 모드·장치 추론 성능·외부 서비스·브라우저는 검증 대상이 아니다. 지식 카드/서버/배포를 수정하지 않았다. 합성 데이터의 정상 정답 의존과 중첩 창 자기상관은 남는다.
