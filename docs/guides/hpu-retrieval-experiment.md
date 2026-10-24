# HPU 관계 검색 실험 (6단계)

기준: 2026-10-25 로컬 구현. `shiftlink/mes/hpu_retrieval_experiment.py`의 별도 Python 실행 API다.
`/api/query`, 기존 검색기·답변기·설명 API에 자동 hook을 추가하지 않는다.
기본 `SHIFTLINK_HPU_RETRIEVAL=off`이며 off는 자료 조회·투영·검색·모델 호출을 하지 않는다.
`experiment` 환경 변수만 설정해도 MES 질의에서 실험이 실행되지는 않는다.

## 입력과 실행

호출자는 승인 자료의 격리 서비스, 현재 게시 검증을 통과한 S30h 질의별 view,
HPU 사건의 기존 base graph, 그 사건의 게시 카드를 실제 인용했던 witness 질의 ID를 제공한다.
base graph는 `read_incident_bundle`/`project_hpu`로 만든 1~4단계 결과이며 페이지로 잘린 API 응답을 쓰지 않는다.
승인 복사본에 witness 질의와 원 일지가 있어야 하고, 서비스 자료와 원본 해시가 일치해야 한다.

```python
from shiftlink.mes.hpu_retrieval_experiment import run_experiment

comparison = run_experiment(
    isolated_service, validated_s30h_view,
    {"question": "근무일지의 필터 교체 순서와 결과는?",
     "eq_id": equipment_id, "asset_id": asset_id,
     "incident_id": original_incident_id, "observations": observations},
    database=approved_database_copy, graph=base_graph,
    witness_query_id=saved_citation_query_id, mode="experiment",
)
```

명시 `mode`가 환경 변수보다 우선한다. S30h만 지원하며 FixedPipeline/hybrid에는 적용하지 않는다.
실제 모델을 구성한 view로 명시 실행하면 임베딩·판정·생성을 두 경로에서 호출할 수 있다.
새 모델·인덱스를 설치하거나 서비스 설정을 바꾸는 기능은 없다.

## 수용 범위와 후보 보완

1. 기존 `is_history_question`이 과거 원문 조회로 분류한 질문만 대상이다.
2. HPU와 명시한 사건·설비·현재 자산이 일치해야 한다. 현재 작업 승인·다른 사건/자산은 보완하지 않는다.
3. 5단계 `connect`의 현재 게시 ticket·출처·원문 리비전 검증을 재사용한다.
4. 같은 검증된 검색 풀에 이미 있는 카드/청크/벡터만 사용할 수 있다.
   내용·판본·벡터가 게시 artifact와 일치하고 현재 관측 조건도 verified여야 한다.
5. 기존 검색 결과의 첫 후보 뒤에 관계 카드 최대 2개를 보완한다. 이미 검색된 카드는 중복 보완하지 않는다.
   기존 `G.evidence`의 청크·토큰·중복 페이지·event 예산을 유지하므로 뒤쪽 후보가 빠질 수 있다.
6. 기존 judge·보류 임계값·원문 이력 필터·생성/인용 검사를 그대로 실행한다.
   관계가 있어도 판정 거절이나 미기록 수치를 답변으로 승격하지 않는다.
7. 관계 후보를 사용한 뒤 게시 연결 해시를 재확인한다. 도중 반려/변경은 쌍 전체를 invalidated로 처리한다.

실험은 독립 view를 만들며 원 view·DB·KB·인덱스·질의 로그에 쓰지 않는다.
질의 저장·새 인용 ticket 발급·인덱스 자동 수리·운영 답변 교체를 수행하지 않는다.
현재 검증된 view를 호출자가 준비해야 하며, 오래된 임의 검색 풀을 운영 기준선으로 취급하지 않는다.

## 비교 결과 읽기

`baseline`과 `trial`에는 실제 최종 인용 ID, 보류 여부·사유, 답변 해시, 후보/판정 수가 있다.
답변·일지 원문은 비교 보고서에 복사하지 않는다. `added_card_ids`는 실제 예산 안에 들어간 관계 후보다.
`timings_ms`에는 관계 준비, 각 view 복사, 각 실행, 재확인이 분리되어 있다.
baseline_total은 기준 view 준비+실행, trial_total은 관계 준비+실험 view 준비+실행+재확인이다.
후보 판정·생성 시간만 비교해 관계 준비 비용을 숨기지 않는다.

오류는 안전한 유형만 반환한다. off/error/invalidated는 completed 비교로 집계하지 않는다.
`score_case`는 사전 고정 오라클을, `summarize`는 인용 정밀도/재현율·보류·오인용·오연결·평균/p95 지연을 집계한다.
오인용은 기대한 카드 밖의 최종 인용, 오연결은 사건/자산 오라클이 허용하지 않은 관계 후보 추가다.
관계가 올바르지만 질문에 답하지 못해 judge가 거절한 것은 오연결로 세지 않는다.
필수 인용 누락·보류 기대값 불일치도 oracle_failures로 표시한다.
`fixture_pass_only`는 유한 fixture 통과 표시이며 운영 채택이나 실제 모델 품질 승인으로 사용하지 않는다.

## 고정 비교 재현

`tests/fixtures/hpu_retrieval_cases.json`은 긍정 2개와 미기록 수치·현재 승인·자산 교체·판정 거절·다른 사건·반려의 반례를 고정한다.
`tests/test_hpu_retrieval_experiment.py`는 실제 S30h를 사용하되 임베딩·판정·모델 출력은 명시적인 fixture다.
관련 카드의 dense rank를 35개 경쟁 현장 일지 뒤로 둔 의도적인 검색 누락 조건이므로 운영 질의 분포를 대표하지 않는다.
최초 비교는 매뉴얼 35개를 사용했다. 후속 일지 전용 검색 수정으로 이 조건이 기본 경로에서 회복되어,
매뉴얼 조건은 `tests/test_hpu_history_recheck.py`에 보존하고 관계 보완 fixture는 경쟁 일지로 강화했다.
각 사례를 5회, 기준/실험 실행 순서를 교차해 비교한다.

```powershell
# 새 경로만 지정한다. 기존 결과 파일은 덮어쓰지 않는다.
$env:SHIFTLINK_HPU_EXPERIMENT_REPORT='D:\approved\new-comparison.json'
python -m pytest tests/test_hpu_retrieval_experiment.py -q
```

실행한 [비교 JSON](../testing/hpu-retrieval-comparison-20261025.json)과
[검증 기록](../testing/hpu-retrieval-experiment-20261025.tdd.md)을 참고한다.
로컬 fixture 지연은 실제 Ollama·Pi/Jetson의 지연이나 운영 p95를 보장하지 않는다.

2026-10-25에는 운영 모델·자연 검색 인덱스로 본평가 32쌍과 별도 탐색 8쌍을 실행했다.
표현에 따른 실제 인용 회복은 확인했지만 공통 이력 분류/보류 문제와 지연 때문에 **운영 적용 보류·기본 off 유지**다.
[실제 모델 비교](../testing/hpu-retrieval-live-20261025.md)의 평가군 구분과 남은 문제를 확인한다.

같은 질문으로 수행한 [분류·조건 보류·검색 지연 후속 검증](../testing/hpu-retrieval-recheck-20261025.md)은
모델 학습 없이 명시적 일지 검색의 범위를 검수 현장 청크로 좁힌다.
미기록 기간/날짜는 검색 전에 거르고, 적합한 검색 후보는 기존 judge를 반드시 통과해야 한다.
일반 현재 판단과 관계 검색 실험의 기본 off는 유지하며 운영 미배포다.
