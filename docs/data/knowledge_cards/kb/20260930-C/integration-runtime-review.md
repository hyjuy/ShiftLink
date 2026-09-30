# 배치 C 런타임 통합 독립 검증

검증일: 2026-09-30. 운영 코드·운영 KB·승인 상태를 수정하지 않았다. `eval/` 및 평가 원문은 읽지 않았다.

## 판정

19개 카드의 스키마, 로더, 설비 분리, MES 상태 신호, 조건 필터, T6 payload에 현재 구현을 중단시키는 충돌을 발견하지 않았다. 다만 T6 안전 카드의 항상 병합 및 승인 메타데이터 해석은 사람 검수에서 확인해야 하는 기존 구현 제약이다. 이를 이유로 자동 accepted/L1 승격하지 않는다.

## 확인 결과

| 검사 | 실제 결과 |
|---|---|
| `cards.json` 기본 로드 | seen 19, loaded 0 |
| `out/` 기본 로드 | seen 19, loaded 0 |
| 두 경로 draft 포함 | 각각 19장 로드 |
| 메모리에서만 accepted/L1로 복제 | 19장 검증·로드 성공, 원본 변경 없음 |
| 설치 위치 | HPU-01 EQ-0001, GR-01 EQ-0004, RT-03 EQ-0008, CV-01 EQ-0009 |
| 설비 분리 | 각 카드의 대상 외 9개 설치 위치 검색에서 해당 카드 미반환 |
| T2 신호 10장 | 모든 조건 신호의 원본 측정값이 해당 설치 config에 존재 |
| T2 조건 | 모든 조건 일치 verified, 관측 없음 unverified, 조건 불일치 inapplicable |
| MES 어댑터 | 10장 모두 good 품질의 실제 숫자/단위로 상태 유도 후 verified, bad 품질은 unverified |
| T6 payload | restart_type 및 실패 시도의 타입 일치, null failure_reason 유지, steps 없이 파싱 성공 |
| 기존 관련 테스트 | `test_mes_card_adapter.py`, `test_retrieval_response.py`, `test_schemas.py` 총 112 passed |

## 재현한 제약과 판정 근거

### R1: T6는 재가동 이외 질문에도 실패 기록이 표시된다 — 중간, 기존 응답 설계의 적용 확대

위치: `cards.json:641` 등 K-1211~K-1219의 빈 conditions 및 safety_flag=true. `shiftlink/rag/retrieval.py:123,350`, `shiftlink/agent/response.py:174`.

재현: 19장만 accepted/L1로 메모리 복제한 provider에 HPU-01, 질문 `필터 막힘 표시기 종류 확인`, hpu_filter_dp_state=high를 전달했다. 안전 병합은 K-1211 및 K-1218을 포함하며 두 카드가 모두 verified가 된다. `render_response`의 재가동 실패 이력에는 AT-4001, AT-4004, AT-4002, AT-4043 총 4건이 표시되고 review_queue=false, validation_errors=[]이다. 여기서 verified는 빈 기계 조건을 통과했다는 뜻이며, 정비 완료·기동 승인 등이 현장에서 확인됐다는 뜻은 아니다.

판정: 안전 경고를 항상 검색하는 구현과 호환되지만 재가동과 무관한 질문에서도 합성 과거 실패가 노출되는 동작을 사람 검수자가 이해해야 한다. 임의의 restart_type MES 조건을 카드에 추가하면 관측할 수 없는 조건을 만들므로 배치 범위에서는 문서에 이 제한을 명시하고, 현재 안전 병합 표시를 수용할지 결정한다. 실패 기록 표시를 재가동 질문에 한정하려면 별도 응답 구현 작업이 필요하다.

### R2: safety_review는 채택·권한 게이트가 아니다 — 중간, 승인 절차 주의

위치: `shiftlink/agent/schemas.py:98`, `shiftlink/rag/retrieval.py:248-249`. 배치의 모든 safety_review는 null이다.

재현: status/grade만 accepted/L1로 바꾼 메모리 복제 19장은 safety_review=null이어도 모두 로드된다. 사람 승인과 권한 확인을 로더가 수행하지 않는다. 이는 SafetyReview 모델의 명시된 계약(카드 채택·워크플로 권한과 독립)에 부합하므로 스키마 버그로 판정하지 않는다.

배치 범위 조치: 현재 draft/L0 유지. 실제 승격 시 내용 승인과 현장 안전 검토 기록을 별도로 남긴다. 승인되지 않은 null을 approved로 자동 생성하지 않는다.

### R3: RT 설치 범위는 RT-03이며 RT 별칭의 기본 선택은 RT-01 — 낮음, 의도된 설치 제한

위치: `cards.json:378` K-1207 및 K-1208/K-1214/K-1217의 mes_equipment_id=EQ-0008. `shiftlink/mes/card_adapter.py:42`.

재현: catalog에서 EQ-0008은 RT-03이다. 동일 조건을 넣어도 RT-01·RT-02에서는 카드가 검색되지 않는다. MesCardAdapter에 `RT`를 주면 RT-01이 선택되므로 배치 RT 카드가 검색되지 않는다.

판정·배치 범위 조치: 오적용 방지에 필요한 제한이며 충돌이 아니다. 검수·시연은 RT-03 또는 EQ-0008로 수행한다. 원문 모델 적용성 확인 없이 RT-01·RT-02로 확대하지 않는다.

### R4: T2 verified는 원문 내 수동 분기 확인을 보증하지 않는다 — 낮음, 관측 계약의 한계

10장에 구조화된 conditions는 MES 상태만 들어 있다. 표시기 종류, 정지 후 실제 확인, 윤활·장기정지 이력 등의 세부 분기는 know_how에서 추가 확인하도록 설명된다. 현재 MES에는 해당 수동 확인을 전달하는 조건 신호가 없다. 위 good 측정값 테스트는 검색 조건 검증이며 모델의 모든 현장 분기 적용성 검증은 아니다.

배치 범위 조치: 카드의 수동 확인 문장과 generalization_scope를 사람 검수에서 확인한다. 사람이 확인하지 않은 항목을 새 MES 신호로 가정하지 않는다.

## 재현 자료

- `artifacts/batch-c-conflict/runtime_probe.py`: provider·MES 어댑터·응답 경로 검증. 임시 accepted 복제는 메모리 내에서만 생성한다.
- `artifacts/batch-c-conflict/runtime-probe-results.json`: 19장 및 T2 10장 결과.
- `artifacts/batch-c-conflict/runtime-probe-response.txt`: HPU 필터 질문에 포함된 실패 기록 표시 예시.

환경: Python 3.10, Pydantic 2.9.2. 이 독립 검증은 운영 설치·현장 구조의 실제 동일성 또는 LLM 자유 답변의 의미 정확성을 승인하지 않는다.
