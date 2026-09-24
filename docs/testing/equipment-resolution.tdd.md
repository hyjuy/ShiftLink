# 설비 ID 해소 검증 — 2026-09-24

사용자 요청: 관측값 구조 검증 다음 순서인 설비 ID 해소 진행. 기존 관측값 변경은 유지했다.

## 계약과 구현

기준정보 `docs/data/reference/00_plant_and_relations.json`의 관계를 사용한다.

`equipment.equipment_id / equipment.code → equipment_type_id → equipment_types.type_code`

예: `EQ-0001 / HPU-01 → ET-0001 → HPU`.

- InMemoryToolProvider 생성자에 선택 equipment_types 인자를 추가했다. 파일 자동 로딩은 하지 않으며 진입점이 equipment와 equipment_types 목록을 전달한다.
- 같은 해소 함수를 설비 조회·일반 검색·안전 검색·인계·체크리스트 조회에서 사용한다.
- 카드 검색은 유형, 인계·체크리스트는 정식 ID를 사용한다. 원래 모델 요청의 eq_id는 변경하지 않는다.
- 미등록 식별자, 중복 일치, 유형 관계 누락/중복, 카드 스키마 미지원 type_code는 ValueError다. 다른 유형이나 전체 카드 검색으로 대체하지 않는다.
- HPU/GR/RT/CV/COMMON 직접 입력은 이전 호출자 호환을 위해 허용한다. COMMON 카드의 기존 포함 정책은 유지한다.

## TDD 증빙

```powershell
$env:PYTHONPATH = "$PWD/.test-deps"
python -m pytest tests/test_retrieval_response.py -q -p no:cacheprovider --tb=short
```

최초 시도는 미구현 생성자 인자로 10개 setup 오류가 발생했다. 이것만으로 행동 검증을 완료했다고 보지 않고, 테스트에서 사전을 주입할 수 있도록 조정한 후 기존 검색 동작의 실패를 재현했다.

RED: **9 failed, 50 passed**. 정식 ID로 해당 설비 카드 미검색, 표시 코드 조회 실패, 미등록·미지원·모호한 사전의 무검증 통과를 확인했다.

```powershell
$env:COVERAGE_FILE = "$PWD/artifacts/equipment-resolution.coverage"
python -m coverage run --source=shiftlink.rag.retrieval -m pytest tests/test_retrieval_response.py tests/test_router_pipeline.py tests/test_eval_harness.py -q -p no:cacheprovider --tb=short
python -m coverage report -m --fail-under=80
```

GREEN: **104 passed**. retrieval.py 구문 커버리지 **89% (133/149)**. 새 생성자 인자를 사용하도록 fixture를 정리한 후 관련 파일 재실행도 **59 passed**.

| 보장 | 테스트 |
|---|---|
| EQ-0001과 HPU-01의 일반·안전 카드 일치, 인계·체크리스트 정식 ID 조회 | test_catalog_equipment_ids_and_codes_share_card_search |
| 미등록 HPU-99/EQ-9999와 미지원 PDP-01에서 모델 호출 0회, 직접 검색도 거부 | test_unresolved_equipment_stops_before_model |
| 원래 요청 eq_id 보존, 해소된 설비 정보·안전 카드 전달 | test_equipment_mapping_keeps_original_request |
| 코드 중복·유형 누락·유형 중복 거부 | test_ambiguous_or_missing_equipment_mapping_is_rejected |
| 기존 유형 직접 입력 호환 | test_direct_equipment_types_remain_supported |

## 남은 범위

- 설비 기준정보 전체의 사전 검증이나 모든 기존 인계 데이터의 이전 작업은 수행하지 않았다. 인계·체크리스트 저장 행은 정식 equipment_id를 사용해야 한다.
- 사전의 PDP·CAU를 카드 유형으로 추가하지 않았다. 미지원 유형 오류를 사용자 화면에 표시하는 일은 통합 단계에 남는다.
- 같은 유형의 장비 간 카드 세분화·line_id 필터·단위 처리·LLM 답변 검증은 별도 작업이다.
- 빈 KB의 모델 호출 방지는 아직 구현하지 않았다. 미등록 설비 거부와 지식 없음 처리는 다른 경로다.
- 실제 모델·Jetson 없이 코드 경계를 검증했다. 체크포인트 커밋은 생성하지 않고 RED/GREEN을 이 문서에 보존했다.

## 실패 경로 추가 검증 — 2026-09-24

사용자의 후속 요청으로 실패 경로 8개를 추가했다. 이번에는 테스트와 증빙만 변경하고 검색 구현은 변경하지 않았다.

| 입력 또는 상황 | 기대 결과 |
|---|---|
| 같은 정식 ID가 두 행에 등록됨 | 모호한 식별자 오류, 모델 호출 0회 |
| 장비 ID가 다른 장비의 표시 코드와 충돌 | 모호한 식별자 오류, 모델 호출 0회 |
| 장비의 equipment_type_id 누락 | 일반·안전 검색 오류, HPU-01 접두어로 추측하지 않음 |
| 유형 사전의 type_code 누락 | 일반·안전 검색 오류 |
| 정상 ID와 미등록 ID로 인계 조회 | 부분 결과 없이 오류 |
| 정상 ID와 미등록 ID로 체크리스트 조회 | 부분 결과 없이 오류 |
| 정상 장비와 미등록 장비를 섞은 인계 요청 | 모델 호출 0회, 요청 실패 |
| 같은 HPU 유형의 서로 다른 장비·교대 기록 | 다른 장비의 인계·체크리스트, 다른 교대의 인계가 섞이지 않음 |

```powershell
$env:PYTHONPATH = "$PWD/.test-deps"
python -m pytest tests/test_retrieval_response.py tests/test_router_pipeline.py -q -p no:cacheprovider --tb=short
```

결과: **87 passed**. 실패 상황을 입력했을 때 기대한 오류 또는 기록 격리가 발생하므로 테스트 자체는 통과한다. 이번 추가 테스트에서 새 구현 결함은 발견되지 않았다. 실제 모델 호출은 하지 않았다.
