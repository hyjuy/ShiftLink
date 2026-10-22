# 2-hop 참고 연결이 답변 근거로 오인되는 경계

## Summary

2026-10-22 2-hop 구현의 반증 검사와 /67 검토에서 정한 예방 기록이다. 운영 사고가 발생했다는 뜻은 아니다. 같은 문서·증상을 공유하는 카드도 현재 질의에 적용 가능한지 별도로 검사해야 한다.

## Root Cause

그래프 해시·판본 일치는 그래프 내부 일관성만 확인한다. 역방향 관계의 다른 카드가 현재 카드 뷰에 없거나 반려·변경·다른 설비 범위여도 그래프에는 남아 있을 수 있다. 단순한 이웃 확장이나 참고 카드를 최종 인용에 합치는 구현은 이 경계를 우회한다. 카드 개수만 제한하면 한 카드의 다수 연결 경로가 응답을 크게 만들 수도 있다.

## Prevention

요청별 현재 카드와 정확히 결합하고 허용 경로 세 종류만 사용한다. 참고 연결은 graph_context에만 둔다. 카드 상한과 경로 상한을 별도로 적용하며 원본 방향·양쪽 locator·needs_review를 보존한다. 기존 depth 1, 생성·인용·센서·게시 ticket은 유지한다.

## Detection

- `tests/test_graph_explain_two_hop.py::test_related_card_must_be_current_unique_in_scope_and_exact`
- `tests/test_graph_explain_two_hop.py::test_related_request_views_refresh_and_returned_metadata_is_isolated`
- `tests/test_graph_explain_two_hop.py::test_related_limits_are_deterministic_and_response_wide`
- `tests/test_graph_explain_two_hop.py::test_document_version_identity_and_path_caps`
- `tests/test_graph_explain_two_hop.py::test_depth_two_changes_only_graph_context_and_persists_without_mutation`
- `tests/test_graph_explain.py::test_s30h_explain_does_not_change_prompt_rank_or_output`
- `tests/test_graph_explain_browser.py::test_real_pda_graph_explain`

## Evidence

[구현·검증 및 /67 판정 기록](../demo/kg/two-hop-validation-20261022.md). 단위·HTTP·브라우저 검사는 모델 fixture를 사용한다. Jetson과 실제 모델의 재검증으로 해석하지 않는다.
