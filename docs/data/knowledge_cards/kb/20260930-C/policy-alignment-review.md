# 배치 C 상위 계약 반영 독립 재검증

검증일: 2026-09-30. 검토 역할: 앞서 출처·분할 충돌을 조사한 별도 서브에이전트. **보완 반영과 승인 차단 동작은 통과했다. KB 승인 상태는 여전히 보류다.** 카드·레지스트리·배정·코드는 이 재검증에서 수정하지 않았다.

## 데이터 반영 확인

| 검사항목 | 독립 확인 결과 |
|---|---|
| 기존 출처 유지 | HEAD 기준 기존 28개 출처 객체가 현재 레지스트리에 그대로 존재 |
| 신규 기준 출처 | PDF 7개 + 인용 Event/Artifact 45개 = 52개 등록. 모두 `pending_review`, `approved_scope=[]` |
| 원문 보존 | 카드 19장과 out 원본 19장의 canonical source ID 일치. 기존 파일명/EV/AR는 alias와 locator 접두부로 보존 |
| PDF 무결성 | PDF 7개 실제 바이트 SHA256·파일 크기가 local_snapshot과 일치 |
| 사건 무결성 | 45개 관측 투영 항목을 UTF-8 `json.dumps(item, ensure_ascii=False, sort_keys=True)`로 해시한 결과가 item_sha256과 일치 |
| 활성 배정 유지 | `splits/prototype_split.json`의 assignments가 HEAD 버전과 정확히 동일 |
| 후보 계보 | pending_groups 7개가 policy_manifest.groups와 동일. 각각 `assignment_active=false`, `lineage_review_status=pending_review` |
| 분할 해시 | `shiftlink-split-v1:<group_id>` UTF-8 SHA256 → big-endian 정수 → `%12`를 독립 계산하여 7개 bucket 모두 일치 |
| manifest 고정 | 최종 카드 19장·out 19장의 index_version이 실제 manifest 바이트 SHA256과 일치. 값 `29afb0ecb89456db9291e8c32bf240ef43467c6cbc852342f43c7bf98b20d37d` |
| 격리 | active records/dev_events.json 및 dev_artifacts.json은 빈 목록. 기존 dev 5건/Artifact 10건은 quarantined 파일로 보존 |
| 평가 자격 | policy_manifest의 independent_dev_event_ids는 빈 목록. event_plan 20건 모두 evaluation_eligible=false |
| 상태 | 카드 19장 모두 draft/L0. 통합 승인으로 바뀐 카드 없음 |

검증 중 처음에는 index_version이 canonical JSON 해시를 가리키고 실제 파일 바이트 해시와 달랐다. 루트 에이전트에 보고한 뒤 바이트 SHA256으로 재고정한 최종 파일을 다시 읽어 일치를 확인했다. 이 보고서는 수정 완료 후 결과다.

## 실제 차단 동작

Python `3.10`과 기존 `.test-deps`/cp310 core 캐시를 사용했다. 파일은 읽기만 했으며, 잘못된 입력은 unittest.mock으로 메모리에만 주입했다.

| 검사 | 결과 |
|---|---|
| 기본 verify.py | 구조·관측 투영·등록 출처 연결 PASS, 종료값 0. 정책 준비 상태 PENDING, 차단 카드 19장 |
| verify.py --kb-ready 동등 호출 | 종료값 1. 미승인 출처 및 T6 계보·독립 반복 근거가 준비되지 않았음을 확인 |
| 공식 `_prepare`, 기존 KB 그룹 + 신규 미승인 PDF | `Source not approved: M-C-006`으로 거절 |
| 공식 `_prepare`, 배치 C 후보 그룹 | `Group must be explicitly assigned to kb or dev; sealed is prohibited`로 거절. pending_groups가 활성 배정으로 사용되지 않음 |
| out K-1201을 메모리에서 accepted/L1로 변경 후 merge | `KB adoption blocked by source/lineage contract`로 저장 전에 거절. Path.write_text를 오류로 막아 실제 쓰기가 없는 것도 확인 |
| cards K-1201을 메모리에서 accepted/L1로 변경 후 verify | `accepted card has unresolved policy gates`로 거절 |
| active dev_events를 격리 5건으로 다시 활성화 | `quarantined evaluation inputs became active`로 거절 |
| manifest의 독립 그룹 수만 1→2로 변경 | `supporting_group_count_mismatch`로 거절. 선언 숫자로 승격 불가 |
| T6 supporting_event_ids를 다른 계보 사건으로 교체 | `supporting_event_lineage_mismatch`로 거절 |
| 출처만 approved로 바꾸고 locator/version만 있는 불완전 scope 주입 | `approved_scope_not_linked:M-C-006`으로 거절. ApprovedScope 필수 항목 검사 작동 |
| 카드 manifest pin을 이전 값으로 교체 | `policy_manifest_pin_mismatch`로 거절 |

소스검사도 확인했다. 승인 scope는 공식 ApprovedScope 모델로 파싱하며, PDF는 review_candidates의 locator/version/text_sha256과 연결하고 case는 그룹·참조·관측항목 해시와 연결한다. 실제 supporting_event_ids에서 그룹을 다시 계산하여 manifest의 group 목록과 개수를 대조한다.

## 남아 있는 승인 조건

1. 신규 PDF·합성 기록의 `approved_scope`는 비어 있다. 등록과 해시 일치는 출처 내용·판본·설비 적용성 승인이 아니다.
2. 7개 후보 계보와 candidate_split은 계산 기록이다. 사람의 계보 확정과 활성 배정 승인이 아직 없다. RT 정비 후보는 sealed, GR 비정상 정지 후보는 dev로 계산되므로 현재 카드 split=kb를 그대로 승인할 수 없다. 이미 생성·검토에 사용한 자료를 미열람 최종 sealed 자료로 주장할 수도 없다.
3. T6 9장 각각은 후보 독립 그룹 1개다. 사건 ID 두 개를 독립 반복 경험 두 건으로 인정하지 않도록 차단된다. 새로운 독립 근거나 카드 보류 판단이 필요하다.
4. 기존 dev 5건은 독립 평가에서 제외됐다. 15/5 고정 개수를 채우려면 분할 규칙에 맞는 독립 자료를 추가해야 한다. 기존 그룹 ID·배정값을 수에 맞춰 바꾸면 안 된다.
5. events.json/artifacts.json의 과거 split은 감사용으로 유지된다. 이를 임의로 새 평가 입력으로 사용하는 것은 계약 준수가 아니다. 현재 확인한 배치 검증 경로는 재활성화를 거절하지만 별도 신규 평가 도구까지 자동 통제한다고 주장하지 않는다.

앞선 integration-policy-review.md는 보완 전 발견사항 기록이다. 이번 변경으로 미등록 출처·누락 계보의 추적과 잘못된 승격 방어는 보완됐으며, 실제 출처 승인·독립성 확보·분할 활성화는 아직 끝나지 않았다. 전체 제품 회귀·검색 성능은 루트 검증 결과와 별도로 보고한다. eval/ 또는 sealed 의미내용은 이 재검증에서도 읽지 않았다.
