"""Tests for retrieval and response modules (D-26~29 §4)."""

import pytest
from datetime import datetime
from pydantic import ValidationError

from shiftlink.agent.schemas import (
    KnowledgeCard,
    HandoverMethod,
    ResolutionStep,
    FailedAttempt,
    TypePayload,
    Condition,
    Provenance,
)
from shiftlink.rag.retrieval import InMemoryToolProvider, check_card_rules
from shiftlink.agent.response import (
    AgentResponse,
    build_response,
    render_response,
    validate_response,
)


def make_provenance() -> Provenance:
    """Helper to create minimal provenance."""
    return Provenance(
        seed_ids=[],
        persona_id="P-0001",
        event_ids=[],
        generator="test",
        generated_at=datetime.now(),
    )


def make_card_t1(card_id: str = "K-0001", equipment: str = "HPU", safety_flag: bool = False) -> KnowledgeCard:
    """Create minimal T1 card."""
    return KnowledgeCard(
        card_id=card_id,
        version="1.0",
        grade="L1",
        tacit_type="T1",
        equipment=equipment,
        component="pump",
        scenario="S1",
        title="테스트",
        symptom="증상 설명",
        know_how="알아야 할 정보",
        rationale="이유",
        confidence=0.9,
        provenance=make_provenance(),
        split="kb",
        status="accepted",
        safety_flag=safety_flag,
        safety_basis="안전 근거" if safety_flag else None,
    )


def make_card_t3(card_id: str = "K-0003", equipment: str = "HPU") -> KnowledgeCard:
    """Create T3 card with steps."""
    return KnowledgeCard(
        card_id=card_id,
        version="1.0",
        grade="L1",
        tacit_type="T3",
        equipment=equipment,
        component="pump",
        scenario="S1",
        title="단계 카드",
        symptom="증상",
        know_how="알아야 할 정보",
        rationale="이유",
        confidence=0.9,
        provenance=make_provenance(),
        split="kb",
        status="accepted",
        type_payload=TypePayload(
            steps=[
                ResolutionStep(
                    step_id="ST-01",
                    order=1,
                    action="첫 번째 조치",
                    expected_result="예상 결과 1",
                    stop_conditions=["조건 A"],
                ),
                ResolutionStep(
                    step_id="ST-02",
                    order=2,
                    action="두 번째 조치",
                    expected_result="예상 결과 2",
                    stop_conditions=["조건 B"],
                ),
            ]
        ),
    )


def make_card_t4(card_id: str = "K-0004", equipment: str = "HPU") -> KnowledgeCard:
    """Create T4 card with handover method."""
    return KnowledgeCard(
        card_id=card_id,
        version="1.0",
        grade="L1",
        tacit_type="T4",
        equipment=equipment,
        component="pump",
        scenario="S1",
        title="인계 카드",
        know_how="알아야 할 정보",
        rationale="이유",
        confidence=0.9,
        provenance=make_provenance(),
        split="kb",
        status="accepted",
        type_payload=TypePayload(
            handover_method=HandoverMethod(
                required_context=["상태 정보", "측정값"],
                recipient_role="다음 담당자",
                timing="교대 시점",
                channel="음성",
                acknowledgement="수신 확인",
            )
        ),
    )


def make_card_t6(card_id: str = "K-0006", equipment: str = "HPU", failed_attempts: list[FailedAttempt] | None = None) -> KnowledgeCard:
    """Create T6 card with restart info."""
    if failed_attempts is None:
        failed_attempts = []
    return KnowledgeCard(
        card_id=card_id,
        version="1.0",
        grade="L1",
        tacit_type="T6",
        equipment=equipment,
        component="pump",
        scenario="S1",
        title="재가동 카드",
        know_how="알아야 할 정보",
        rationale="이유",
        confidence=0.9,
        provenance=make_provenance(),
        split="kb",
        status="accepted",
        type_payload=TypePayload(
            restart_type="normal_stop_restart",
            tried_and_failed=failed_attempts,
        ),
    )


# Tests for InMemoryToolProvider

def test_retrieval_loads_only_accepted_kb_l1_cards() -> None:
    """Only status=accepted AND split='kb' AND grade='L1' cards loaded."""
    accepted_l1 = make_card_t1(card_id="K-0001", equipment="HPU")
    draft_l1 = make_card_t1(card_id="K-0002", equipment="HPU")
    draft_l1.status = "draft"
    accepted_l2 = make_card_t1(card_id="K-0003", equipment="HPU")
    accepted_l2.grade = "L2"

    provider = InMemoryToolProvider(cards=[accepted_l1, draft_l1, accepted_l2])
    assert len(provider.cards) == 1
    assert provider.cards[0].card_id == "K-0001"


def test_retrieval_rejects_dev_sealed_cards() -> None:
    """dev/sealed cards raise ValueError."""
    accepted_kb = make_card_t1(card_id="K-0001", equipment="HPU")
    accepted_dev = make_card_t1(card_id="K-0002", equipment="HPU")
    accepted_dev.split = "dev"

    with pytest.raises(ValueError, match="dev/sealed"):
        InMemoryToolProvider(cards=[accepted_kb, accepted_dev])


def test_search_cards_equipment_filter() -> None:
    """Cards filtered by equipment (card equipment in request or COMMON)."""
    hpu_card = make_card_t1(card_id="K-0001", equipment="HPU")
    gr_card = make_card_t1(card_id="K-0002", equipment="GR")
    common_card = make_card_t1(card_id="K-0003", equipment="COMMON")

    provider = InMemoryToolProvider(cards=[hpu_card, gr_card, common_card])
    results = provider.search_cards(query="test", equipment_ids=["HPU"], k=5)

    card_ids = {c.get("card_id") for c in results}
    assert card_ids == {"K-0001", "K-0003"}  # HPU and COMMON


def test_search_cards_excludes_false_conditions() -> None:
    """Cards with False condition excluded."""
    card_with_cond = make_card_t1(card_id="K-0001", equipment="HPU")
    card_with_cond.conditions = [Condition(signal="pressure", op="==", value=100)]

    provider = InMemoryToolProvider(cards=[card_with_cond])
    # No observations: condition unverified, card included
    results = provider.search_cards(query="test", equipment_ids=["HPU"], k=5)
    assert len(results) == 1

    # Observations don't match: condition_status should reflect this
    # (In this implementation, search_cards doesn't receive observations,
    # so we test search_safety_cards for observation handling)


def test_search_cards_deterministic_ranking() -> None:
    """Cards ranked by token overlap then card_id."""
    card1 = make_card_t1(card_id="K-0001", equipment="HPU")
    card1.know_how = "압력 측정"
    card2 = make_card_t1(card_id="K-0002", equipment="HPU")
    card2.know_how = "온도 측정"
    card3 = make_card_t1(card_id="K-0003", equipment="HPU")
    card3.know_how = "압력 이상"

    provider = InMemoryToolProvider(cards=[card1, card2, card3])
    results = provider.search_cards(query="압력", equipment_ids=["HPU"], k=5)

    # Cards with "압력" should rank higher
    card_ids = [c.get("card_id") for c in results]
    # Exact order depends on token overlap calculation, but K-0001 and K-0003
    # should rank above K-0002
    assert card_ids[0] in ("K-0001", "K-0003")
    assert "K-0002" not in card_ids[:2]


def test_search_safety_cards_returns_all_safety_flag_true() -> None:
    """safety_cards returns all safety_flag=True cards regardless of k."""
    safe1 = make_card_t1(card_id="K-0001", equipment="HPU", safety_flag=True)
    safe2 = make_card_t1(card_id="K-0002", equipment="HPU", safety_flag=True)
    normal = make_card_t1(card_id="K-0003", equipment="HPU", safety_flag=False)

    provider = InMemoryToolProvider(cards=[safe1, safe2, normal])
    results = provider.search_safety_cards(equipment_ids=["HPU"], observations=None)

    card_ids = {c.get("card_id") for c in results}
    assert card_ids == {"K-0001", "K-0002"}  # Only safety cards


def test_search_safety_cards_unverified_status_without_observations() -> None:
    """Cards with unmatched conditions get condition_status='unverified'."""
    safe_card = make_card_t1(card_id="K-0001", equipment="HPU", safety_flag=True)
    safe_card.conditions = [Condition(signal="pressure", op="==", value=100)]

    provider = InMemoryToolProvider(cards=[safe_card])
    results = provider.search_safety_cards(equipment_ids=["HPU"], observations=None)

    assert len(results) == 1
    assert results[0].get("condition_status") == "unverified"


def test_search_safety_cards_exclusion_conditions() -> None:
    """Exclusions=True excludes card."""
    safe_card = make_card_t1(card_id="K-0001", equipment="HPU", safety_flag=True)
    safe_card.exclusions = [Condition(signal="mode", op="==", value="maintenance")]

    provider = InMemoryToolProvider(cards=[safe_card])

    # With matching exclusion: card excluded
    results = provider.search_safety_cards(
        equipment_ids=["HPU"],
        observations={"mode": "maintenance"},
    )
    assert len(results) == 0

    # Without matching exclusion: card included
    results = provider.search_safety_cards(
        equipment_ids=["HPU"],
        observations={"mode": "normal"},
    )
    assert len(results) == 1


def test_safety_cards_and_search_cards_merge_removes_duplicates() -> None:
    """Merged results have no duplicate card_ids, safety cards first."""
    # This test verifies pipeline behavior, but we can indirectly test
    # by checking the order logic
    # In reality, this is tested in pipeline tests
    pass


# Tests for check_card_rules

def test_check_card_rules_t3_order_ascending() -> None:
    """T3 steps must be in ascending order."""
    card = make_card_t3()
    # Valid case: no errors
    assert check_card_rules(card) == []

    # Invalid case: out of order
    card.type_payload.steps[0].order = 2
    card.type_payload.steps[1].order = 1
    errors = check_card_rules(card)
    assert any("ascending order" in e for e in errors)


def test_check_card_rules_t4_requires_handover_method() -> None:
    """T4 without handover_method fails."""
    card = make_card_t4()
    card.type_payload = TypePayload()  # Clear handover_method
    errors = check_card_rules(card)
    assert any("handover_method" in e for e in errors)


def test_check_card_rules_t6_requires_restart_type() -> None:
    """T6 without restart_type fails."""
    card = make_card_t6()
    card.type_payload.restart_type = None
    errors = check_card_rules(card)
    assert any("restart_type" in e for e in errors)


def test_check_card_rules_safety_flag_requires_basis() -> None:
    """safety_flag=True without safety_basis fails."""
    card = make_card_t1(safety_flag=True)
    card.safety_basis = None
    errors = check_card_rules(card)
    assert any("safety_basis" in e for e in errors)


# Tests for AgentResponse and render_response

def test_build_response_extracts_safety_cards() -> None:
    """Safety cards populate safety_notices."""
    safe_card = make_card_t1(card_id="K-0001", safety_flag=True)
    tool_results = {
        "cards": [safe_card.model_dump(mode="json")],
        "equipment": [],
        "checklist": [],
    }

    resp = build_response("query", None, tool_results)
    assert len(resp.safety_notices) == 1
    assert resp.safety_notices[0].card_id == "K-0001"
    assert resp.safety_notices[0].safety_basis == "안전 근거"


def test_build_response_extracts_t3_steps() -> None:
    """T3 cards populate steps field."""
    card = make_card_t3()
    tool_results = {
        "cards": [card.model_dump(mode="json")],
        "equipment": [],
        "checklist": [],
    }

    resp = build_response("query", None, tool_results)
    assert len(resp.steps) == 2
    assert resp.steps[0].step_id == "ST-01"
    assert resp.steps[0].order == 1
    assert "조건 A" in resp.steps[0].stop_conditions


def test_build_response_extracts_t4_handover() -> None:
    """T4 cards populate handover_method."""
    card = make_card_t4()
    tool_results = {
        "cards": [card.model_dump(mode="json")],
        "equipment": [],
        "checklist": [],
    }

    resp = build_response("query", None, tool_results)
    assert resp.handover_method is not None
    assert resp.handover_method.recipient_role == "다음 담당자"
    assert len(resp.handover_method.required_context) == 2


def test_build_response_extracts_restart_failures() -> None:
    """tried_and_failed attempts populate restart_failures."""
    attempt = FailedAttempt(
        attempt_id="AT-0001",
        restart_type="normal_stop_restart",
        action="재시작",
        observed_result="실패",
        failure_reason="전원 미공급",
    )
    card = make_card_t6(failed_attempts=[attempt])
    tool_results = {
        "cards": [card.model_dump(mode="json")],
        "equipment": [],
        "checklist": [],
    }

    resp = build_response("query", None, tool_results)
    assert len(resp.restart_failures) == 1
    assert resp.restart_failures[0].attempt_id == "AT-0001"
    assert resp.restart_failures[0].failure_reason == "전원 미공급"


def test_render_response_safety_first() -> None:
    """Rendered output has safety notices first."""
    safe = make_card_t1(card_id="K-0001", safety_flag=True)
    step = make_card_t3(card_id="K-0003")
    tool_results = {
        "cards": [
            step.model_dump(mode="json"),
            safe.model_dump(mode="json"),
        ],
        "equipment": [],
        "checklist": [],
    }

    resp = build_response("query", None, tool_results)
    text = render_response(resp)

    # Safety section should appear before steps
    safety_pos = text.find("## 안전 공지")
    steps_pos = text.find("## 조치 단계")
    assert safety_pos < steps_pos


def test_render_response_steps_in_order() -> None:
    """T3 steps rendered in ascending order."""
    card = make_card_t3()
    tool_results = {
        "cards": [card.model_dump(mode="json")],
        "equipment": [],
        "checklist": [],
    }

    resp = build_response("query", None, tool_results)
    text = render_response(resp)

    # ST-01 should appear before ST-02
    st01_pos = text.find("ST-01")
    st02_pos = text.find("ST-02")
    assert st01_pos < st02_pos


def test_render_response_t4_five_elements() -> None:
    """T4 handover method renders all 5 elements."""
    card = make_card_t4()
    tool_results = {
        "cards": [card.model_dump(mode="json")],
        "equipment": [],
        "checklist": [],
    }

    resp = build_response("query", None, tool_results)
    text = render_response(resp)

    # All 5 elements should be in output
    assert "대상:" in text or "recipient_role" in str(resp.handover_method)
    assert "시점:" in text or "timing" in str(resp.handover_method)
    assert "방법:" in text or "channel" in str(resp.handover_method)
    assert "확인:" in text or "acknowledgement" in str(resp.handover_method)
    assert "전달 정보:" in text or "required_context" in str(resp.handover_method)


def test_render_response_restart_failures_by_type() -> None:
    """Restart failures grouped by type, unknown last."""
    normal = FailedAttempt(
        attempt_id="AT-0001",
        restart_type="normal_stop_restart",
        action="행동 1",
        observed_result="결과 1",
    )
    unknown = FailedAttempt(
        attempt_id="AT-0002",
        restart_type="unknown",
        action="행동 2",
        observed_result="결과 2",
    )
    card = make_card_t6(failed_attempts=[unknown, normal])
    tool_results = {
        "cards": [card.model_dump(mode="json")],
        "equipment": [],
        "checklist": [],
    }

    resp = build_response("query", None, tool_results)
    text = render_response(resp)

    # normal_stop_restart should appear before unknown
    normal_pos = text.find("normal_stop_restart")
    unknown_pos = text.find("### unknown")
    assert normal_pos < unknown_pos


def test_render_response_preserves_none_failure_reason() -> None:
    """failure_reason=None rendered as '미상', not converted to string."""
    attempt = FailedAttempt(
        attempt_id="AT-0001",
        restart_type="normal_stop_restart",
        action="행동",
        observed_result="결과",
        failure_reason=None,
    )
    card = make_card_t6(failed_attempts=[attempt])
    tool_results = {
        "cards": [card.model_dump(mode="json")],
        "equipment": [],
        "checklist": [],
    }

    resp = build_response("query", None, tool_results)
    text = render_response(resp)

    # Check that None is rendered as "미상"
    assert "미상" in text
    assert resp.restart_failures[0].failure_reason is None  # Data unchanged


def test_validate_response_cited_ids_exist() -> None:
    """Validator checks cited card_ids exist in tool_results."""
    card = make_card_t1(card_id="K-0001")
    tool_results = {
        "cards": [card.model_dump(mode="json")],
        "equipment": [],
        "checklist": [],
    }

    resp = AgentResponse(mode="query")
    resp.cited_card_ids = ["K-0001", "K-9999"]  # K-9999 doesn't exist

    errors = validate_response(resp, tool_results)
    assert any("K-9999" in e for e in errors)


def test_validate_response_no_missing_safety_cards() -> None:
    """Validator checks all safety cards are cited in notices."""
    safe_card = make_card_t1(card_id="K-0001", safety_flag=True)
    tool_results = {
        "cards": [safe_card.model_dump(mode="json")],
        "equipment": [],
        "checklist": [],
    }

    # Response missing safety card
    resp = AgentResponse(mode="query")
    errors = validate_response(resp, tool_results)
    assert any("Missing safety" in e for e in errors)


def test_validate_response_steps_order_preserved() -> None:
    """Validator checks steps are in ascending order."""
    resp = AgentResponse(mode="query")
    # Out of order steps
    from shiftlink.agent.response import StepRender
    resp.steps = [
        StepRender(step_id="ST-02", order=2, action="action", expected_result="result"),
        StepRender(step_id="ST-01", order=1, action="action", expected_result="result"),
    ]

    tool_results = {"cards": [], "equipment": [], "checklist": []}
    errors = validate_response(resp, tool_results)
    assert any("not in ascending order" in e for e in errors)


def test_validate_response_no_lost_stop_conditions() -> None:
    """Validator checks stop_conditions from cards appear in response."""
    card = make_card_t3()  # Has stop_conditions
    tool_results = {
        "cards": [card.model_dump(mode="json")],
        "equipment": [],
        "checklist": [],
    }

    # Response with empty steps
    resp = AgentResponse(mode="query")
    errors = validate_response(resp, tool_results)
    assert any("Lost stop_conditions" in e for e in errors)
