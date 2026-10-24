# HPU 6단계 검색 실험·비교 검증

완료일: 2026-10-25 (Asia/Seoul). 2026-10-24에 작업을 시작했다.
시작 HEAD: `e7b3a9aa036d46bee3603c525ad2c50897fb6dbd`.
계획: [HPU 확장 설계](../design/hpu-ontology-extension.md) 6단계.
사용법: [실험 계약](../guides/hpu-retrieval-experiment.md).

## 사용자 흐름과 구현

승인 자료와 검증된 S30h view로 동일 질문을 기준/관계 보완 경로에서 각각 실행하고
인용·보류·오연결·지연을 비교한다. 기존 서비스/query/검색/답변 코드·원문은 수정하지 않는다.
신규 `hpu_retrieval_experiment.py`는 기본 off이고 외부에서 명시 호출해야 한다.
off는 입력/모델에 접근하지 않고, experiment 환경 변수도 일반 서비스 질의를 가로채지 않는다.

명시 HPU·사건·자산의 과거 원문 조회만 수용한다. 5단계 실제 인용 관계와 현재 검수 상태를 재사용하고,
같은 풀의 정확한 카드·청크·벡터·현재 관측 조건이 확인된 후보만 최대 2개 보완한다.
기존 `G.evidence` 예산과 S30h judge·보류·이력 원문·수치/인용 검사를 재사용한다.
원 view/DB는 쓰지 않고, 실험 중 게시 변경은 답변이 없는 invalidated 진단으로 분리한다.
FixedPipeline/hybrid·운영 HTTP 실험 라우트·자동 채택은 포함하지 않는다.

## RED/GREEN

- `python -m pytest tests/test_hpu_retrieval_experiment.py -q --tb=short`에서
  미구현 `hpu_retrieval_experiment` import 실패(exit 1). RED `2b7e86c`.
- 첫 구현 검증은 fixture가 공통 projector의 필수 `equipment_type`을 빠뜨려 setup 13 errors였다.
  fixture에 HPU를 명시한 뒤 **13 passed in 15.22s**, GREEN `03fcc20`.
- `test_missing_expected_citation_is_a_regression`은 양쪽 모두 필수 인용을 놓쳐도 성공으로
  집계하는 문제를 재현했다(1 failed in 19.39s). RED `c1f48d6`.
- 최종 oracle_failures 집계와 분리된 준비/실행 지연 측정을 반영했다.
  불필요해 보이는 import를 제거하자 드러난 기존 패키지 의존성 순환은
  retrieval helper를 사용 지점에서 로드하여 해결했다. 기존 패키지는 변경하지 않았다.
- 최종 GREEN `9dc71ed`: **16 passed in 30.48s**.

```text
python -m coverage run --data-file=.coverage-hpu-retrieval --source=shiftlink.mes.hpu_retrieval_experiment -m pytest tests/test_hpu_retrieval_experiment.py -q --tb=short
python -m coverage report --data-file=.coverage-hpu-retrieval -m
```

신규 모듈 커버리지 **95%**(130 statements/6 missed). 일부 조건 불일치·오류 분기는 미실행이다.

## 고정 비교

오라클: [hpu_retrieval_cases.json](../../tests/fixtures/hpu_retrieval_cases.json).
결과: [비교 JSON](hpu-retrieval-comparison-20261025.json).
8개 고유 사례를 5회씩, 기준/실험 실행 순서를 교차해 **40쌍**을 측정했다. 독립 질문 40개가 아니다.
실제 S30h를 실행하지만 임베딩·judge·모델 출력은 결정적 fixture다.
하나의 검수 카드가 35개 문서 뒤로 밀린 의도적인 dense 검색 누락 조건이다.

| 항목 | 기준 | 관계 보완 |
|---|---:|---:|
| 필수 인용 회복(10건) | 0 | 10 |
| 인용 재현율 | 0% | 100% |
| 인용 정밀도 | 인용 없음 | 100% |
| 보류(기대값 30건) | 40 | 30 |
| 오인용 / 오연결 | 0 / 0 | 0 / 0 |
| 기대값 불일치 | 10 | 0 |
| 후보 / judge 청크 합계 | 320 / 320 | 320 / 320 |
| 평균 지연 | 16.232ms | 62.632ms |
| p95 지연 | 24.258ms | 111.479ms |

평균 추가 지연 **46.400ms**. 기준은 view 복사+실행, 실험은 관계 준비+view 복사+실행+게시 재검증이다.
이 소규모 fixture의 로컬 wall time은 실제 모델/장비 성능이 아니다.
`fixture_pass_only`이며 운영 채택·성능 승인으로 해석하지 않는다. 기본 off를 유지한다.

## 테스트 보장

| 보장 | `tests/test_hpu_retrieval_experiment.py` | 종류 |
|---|---|---|
| off 무접근·환경 변수의 일반 질의 무영향 | `test_off_is_inert_and_does_not_change_normal_query` | 서비스 |
| 놓친 원문 인용 회복·예산·DB/view 불변 | `test_relation_recovers_missed_history_without_mutation` | 실제 S30h/SQLite |
| judge 거절·미기록 수치·현재 승인·타 자산/사건/설비·반려·legacy·변조 차단 | `test_negative_boundaries`(10개) | 반례/S30h |
| 실험 도중 반려의 결과 무효화 | `test_change_during_trial_invalidates_pair` | 변경 hook |
| 사전 기대값으로 40쌍 집계·비교 JSON 보존 | `test_paired_report_against_fixed_oracles` | 비교 실험 |
| 누락 인용을 성공으로 집계하지 않음 | `test_missing_expected_citation_is_a_regression` | 집계 |
| 오류·무효 실행을 성공 집계에서 제외 | `test_errors_and_invalidated_pairs_are_not_successes` | 집계 |

## 기존 회귀

```text
python -m pytest tests/test_hpu_retrieval_experiment.py tests/test_s30h.py tests/test_ontology_api.py tests/test_ontology_shadow.py tests/test_hpu_ontology.py tests/test_hpu_publication_links.py tests/test_publication_worker.py tests/test_knowledge_publication.py tests/test_publication_s30h.py tests/test_s30h_publication_integrity.py tests/test_publication_ontology_integration.py tests/test_knowledge_gap_loop.py tests/test_mes_query.py tests/test_work_report_capture.py tests/test_work_report_followup.py tests/test_publication_browser.py -q --tb=short
```

결과: **277 passed in 210.34s**. 기존 HTTP·S30h·게시·인용·원문과 실제 브라우저 검사를 포함한다.
skip/fail은 없었다. 이 회귀에서는 비교 JSON 출력 환경 변수를 비워 보관한 결과를 덮어쓰지 않았다.

`python scripts/check_knowledge_publication.py --history-scope stability`:
**72/72, semantic_failed: 0, decision: pass**.
`python -m pytest tests/test_field_history_integration.py -q --tb=short`:
**909 passed in 26.66s**.
기본 `python scripts/check_knowledge_publication.py`도 `ok: true`, `errors: []`,
`staged_python_checked: true`로 통과했다. metadata_and_syntax 검사이며 의미 검사와 구분한다.
문서 상대 링크·변경 Python 구문·공백·비교 JSON 40건 검사도 통과했다.

시작 HEAD부터 실행 코드 변경은 신규 `hpu_retrieval_experiment.py`뿐이다.
기존 server/query에 실험 hook이 없는 것도 확인했다.

한계: 운영 장비·실제 모델·실제 질문 분포·운영 p95는 미검증이다.
이 실험은 과거 기록 조회와 S30h에 한정되며 현재 작업 판단의 검색 확장을 검증하지 않는다.
