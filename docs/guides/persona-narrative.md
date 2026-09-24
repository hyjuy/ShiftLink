# 페르소나 기반 합성 원문 생성

2026-09-24 구현. 진입점은 [`shiftlink/data/narrative.py`](../../shiftlink/data/narrative.py)다. 실제 검토 원문이 부족할 때 사건 원장과 페르소나에서 작업일지 원문을 만든다.

[근거 연결·검증·초안 저장 파이프라인](card-generation.md)의 **선행 단계**다. 카드 생성과는 별도 실행이며, 이 모듈은 등록부를 고치지 않고 등록 제안만 파일로 낸다. 승인은 사람이 한다.

## 두 단계의 역할 분리

| | Stage A (이 문서) | Stage B ([card-generation.md](card-generation.md)) |
|---|---|---|
| 모듈 | `shiftlink/data/narrative.py` | `shiftlink/data/generation.py` |
| 입력 | 사건 원장 + 페르소나 | 검토·승인된 발췌문 |
| 출력 | 작업일지 원문(평문) + 등록 제안 | 근거 연결된 카드 초안 |
| 페르소나 | 사용한다 | **사용하지 않는다** |

Stage B에 페르소나를 넣지 않는 이유는 근거 없는 문장이 섞여 evidence 검증이 깨지기 때문이다. 카드는 발췌문만 보고 쓴다.

## 호출 방법

```powershell
python -m shiftlink.data.narrative --scenario docs/data/scenarios/EV-0031_upstream_cause.json --persona V-01 --source-id SD-901 --print-prompt
python -m shiftlink.data.narrative --scenario ... --persona V-01 --source-id SD-901 --generator-command python path/to/your_generator.py
```

생성기는 UTF-8 프롬프트를 표준입력으로 받고 **평문** 원문을 표준출력으로 돌려준다. Stage B의 생성기가 JSON을 돌려주는 것과 다르다. 이미 만든 원문은 `--candidate`로 같은 검사·출력 경로에 넣는다. 결과는 `artifacts/narratives/<event>_<persona>.txt`와 `.json`이다.

`--personas`는 기본값이 `seeds/personas_v0.1.yaml`, `--catalog`는 `docs/data/reference/00_plant_and_relations.json`이다.

종료 코드: `0` 저장, `1` 입력 읽기·정답지 누출·생성기 실패.

## 프롬프트에 들어가는 것

화이트리스트(`EVENT_FIELDS`, `CONTEXT_FIELDS`, `OBSERVATION_FIELDS`)로 정해져 있다. 제외 목록이 아니라 허용 목록이므로 원장에 필드가 추가되어도 자동으로 노출되지 않는다.

- `true_cause`, `true_actions`, `true_cause_equipment_ids`, `cards_expected`, `canary_token` 등 정답지는 들어가지 않는다.
- 관측은 `observer_persona_id`가 일치하는 것만 넣는다. 원장 `timeline`은 모든 페르소나의 관측이 합쳐진 기록이므로 `kind=context` 항목만 쓴다. 이 구분이 없으면 한 페르소나의 프롬프트에 다른 페르소나의 계측값이 그대로 들어간다.
- 조치·결과·인계 등 사후 정보는 넣지 않는다. 일지는 t 시점에 쓰는 기록이다.
- 내부 ID는 기준정보의 현장 호칭으로 치환해서 넣는다(`EQ-0008` → `RT-03`, `SG-0001` → `ENTRY`). 호칭이 없는 ID가 남으면 생성 전에 거부한다. 치환하지 않으면 "내부 ID를 쓰지 말라"는 지시를 모델이 지킬 방법이 없다.

출력에 카나리 토큰이나 내부 ID가 섞이면 저장하지 않는다. 다만 이는 형식 검사이며, 원문이 실제로 원인을 암시하는지는 사람이 읽어야 한다.

## 등록 제안과 승인

`registry_proposal`은 `review_status`가 `pending_review`이고 `approved_scope`는 비어 있다. 검토자가 원문을 읽고 아래 순서로 승인한다.

1. `proposed_scope`에 `reviewed_by`·`reviewed_at`을 채운다.
2. 그 객체를 그대로 `approved_scope`의 항목으로 옮긴다.
3. `review_status`를 `approved_for_draft`로 바꾼다.
4. 제안 항목을 `seeds/source_registry.json`의 `sources`에 추가한다.

`proposed_scope`는 `generation.ApprovedScope`가 알 수 없는 필드를 거부하므로 **그대로 복사할 수 있는 내용만** 담는다. `derived_from_observation_ids`는 검토자 참고용이며 스코프 바깥에 따로 둔다. 절에 넣으면 승인 시점에 거부된다.

`kind`는 `case`, `group_id`는 사건의 `prototype_id`, `reference_ids`는 해당 사건 ID다. `allowed_claims`·`exclusions`는 초안값이므로 검토자가 원문을 읽고 조정한다.

## 여러 페르소나로 돌릴 때

같은 사건을 여러 페르소나에게 돌리면 관측 범위가 서로 다른 원문이 나온다. 이때도 **사건 원장의 사실은 하나이며**, 원문 간 차이는 관측·기록의 차이지 사실의 차이가 아니다. 상충하는 해석은 병합하지 않고 `conflict_group`으로 관리한다([`seeds/personas_v0.1.yaml`](../../seeds/personas_v0.1.yaml)의 `conflict_policy`).

페르소나를 늘리려면 원장의 `observations[].observer_persona_id`부터 늘려야 한다. 관측 귀속이 원장에 고정되어 있으므로 페르소나만 추가해도 쓸 관측이 없다.

## 이 단계의 한계

합성 작업일지는 `kind=case`뿐이라 "무슨 일이 있었나"만 말할 수 있고 "왜 그런가"는 말하지 못한다. 이 원문만으로 만든 카드는 `rationale`이 증상의 재진술에 그친다. 원리를 담은 `rationale`에는 `kind=background` 출처가 함께 필요하며, 그 승인은 이 모듈이 대신하지 않는다.
