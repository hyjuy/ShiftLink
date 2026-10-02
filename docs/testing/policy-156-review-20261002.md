# H4 — PR #156 정책 게이트 검토 (2026-10-02)

판정: **수정 의견**. 출처 승인 및 이미 생성·검토에 사용한 합성 계보를 `kb`로 확정하고 독립 평가에서 제외한 방향은 수용한다. 다만 새 T6 우회 조건의 검증을 보강해야 한다.

검토 대상: https://github.com/hyjuy/ShiftLink/pull/156, head `4dcc113ea9cd201fb0a057c39061d4ad1cd26cb2`. PR은 이미 `2026-10-02T02:33:02Z`에 merge commit `8a52e89632653fd30144fac6248fff4126fce34a`로 병합됐고 NickyJeon의 APPROVED가 있다. 이 문서는 병합 후 별도 검토 의견이며 GitHub 리뷰를 게시하지 않았다.

## 재현된 수정 사항

1. **P1 — 예외가 승인·카드 내용과 결합되지 않음.** `docs/data/knowledge_cards/kb/20260930-C/policy_gate.py`의 T6 분기는 `card_id`가 `exceptions`에 있으면 통과한다. 파일의 `authorization`, 승인자, 예외 사유, 검토 카드 SHA를 읽지 않는다. 승인되지 않은 빈 예외와 내용이 바뀐 동일 ID 카드도 `adoption_issues() == {}`가 된다. `unapproved_adoption_issues()`는 이미 비어 있는 issues를 받으므로 기존 SHA 검증으로 막지 못한다. 예외는 명시적 승인 기록과 정확한 검토 카드 SHA에 묶고 불일치 시 `independent_repeat_evidence_insufficient`를 유지해야 한다.
2. **P2 — 등록 출처 ID를 독립 계보로 직접 계산함.** `real_cases`는 `review_status == approved_for_draft`만 확인한다. 실제 `case` scope, 해당 카드에 대한 허용 범위, `group_id`, 동일 사건·출처 계보 중복을 검증하지 않는다. `approved_scope=[]`인 무관한 승인 출처 하나도 합성 계보와 합쳐 독립 그룹 2개로 계산돼 통과한다. 유효한 case scope와 카드 연결을 확인하고 승인된 사건 계보 `group_id`로 중복 제거해야 한다. 원문 미보관을 나타내는 0 SHA와 요약 근거의 추적 가능성도 별도로 구분해야 한다.

위 변경에 대해 승인 없는 예외, 검토 후 내용 변경, case scope 누락·카드 불일치, 같은 사건 출처 2개를 넣는 음성 테스트가 필요하다. 현재 PR에서 수정한 승격 테스트는 과거 issues를 monkeypatch해 재생하므로 새 T6 분기의 이러한 실패 조건을 검증하지 않는다.

## 확인 방법과 범위

- GitHub connector로 PR 정보·diff 및 정확한 head의 `policy_gate.py`, `seeds/source_registry.json`을 읽었다. 공개 사례의 원문 적합성까지 승인한 것은 아니다.
- 원격 gate 사본 `tmp/policy-156/gate.py`에 대해 합성 최소 manifest/registry/split 입력으로 `tmp/policy-156/reproduce.py`를 실행했다. scope 검증이나 gate를 mock하지 않았다.
- 실행: `$env:PYTHONPATH='.;tmp/card-review-deps;.test-deps'; python tmp/policy-156/reproduce.py` → 두 우회 재현 assertion 통과.
- 로컬 작업 트리는 PR #156 이전 gate여서 로컬 전체 pytest 결과를 해당 원격 head의 성공으로 주장하지 않는다. PR 설명의 `669 passed`는 작성자의 기록이다.

프로젝트 수준으로 실제 사례 미확보 4장을 예외 처리한 사람의 결정 자체는 존중한다. 수정 요청은 그 승인 범위가 이후 카드 변경이나 다른 출처로 자동 확대되지 않게 만드는 것이다.
