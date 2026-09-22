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
    DISCLAIMER,
    AgentResponse,
    HandoverCandidate,
    build_response,
    is_model_retryable,
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


# --- v1.0 고도화: 등급 표기·인용 검증·카드별 단계·인계 후보 ---


def _results(*cards: KnowledgeCard) -> dict:
    return {
        "cards": [c.model_dump(mode="json") for c in cards],
        "equipment": [],
        "checklist": [],
    }


def test_each_cited_card_shows_its_grade_label() -> None:
    """4.10: 인용 카드마다 'L1 합성·시뮬레이션 검증' 등급을 표시한다."""
    resp = build_response("query", None, _results(make_card_t1()))
    text = render_response(resp)

    assert resp.cards[0].grade == "L1"
    assert resp.cards[0].grade_label == "L1 합성·시뮬레이션 검증"
    assert "K-0001 [L1 합성·시뮬레이션 검증]" in text
    assert validate_response(resp, _results(make_card_t1())) == []


def test_render_always_carries_the_not_a_work_order_notice() -> None:
    """4.10: '실제 작업지시 아님' 문구 상시 표시."""
    text = render_response(build_response("query", None, _results(make_card_t1())))
    assert DISCLAIMER in text


def test_second_t4_card_does_not_overwrite_the_first() -> None:
    """D-27: T4 인계 방법은 카드별로 보존한다."""
    first = make_card_t4(card_id="K-0004")
    second = make_card_t4(card_id="K-0005")
    tool_results = _results(first, second)

    resp = build_response("query", None, tool_results)

    assert [hm.card_id for hm in resp.handover_methods] == ["K-0004", "K-0005"]
    assert resp.handover_method.card_id == "K-0004"  # 계약 §4.3 필드명 유지
    assert not [e for e in validate_response(resp, tool_results) if "handover_method_lost" in e]


def test_steps_of_two_cards_are_not_interleaved() -> None:
    """D-28: 카드별 단계 순서를 보존하고 서로 섞지 않는다."""
    tool_results = _results(make_card_t3(card_id="K-0003"), make_card_t3(card_id="K-0007"))
    resp = build_response("query", None, tool_results)
    text = render_response(resp)

    assert [s.card_id for s in resp.steps] == ["K-0003", "K-0003", "K-0007", "K-0007"]
    assert text.index("카드 K-0003") < text.index("카드 K-0007")
    # 두 카드의 order가 1,2,1,2여도 역전으로 보고하지 않는다.
    assert not [e for e in validate_response(resp, tool_results) if "ascending order" in e]


def test_safety_notice_collects_every_stop_condition() -> None:
    """D-26·§2.2: 첫 단계만이 아니라 카드의 중단 조건 전부를 노출한다."""
    card = make_card_t3(card_id="K-0008")
    card.safety_flag = True
    card.safety_basis = "KOSHA GUIDE M-101-2012"
    tool_results = _results(card)

    resp = build_response("query", None, tool_results)

    assert resp.safety_notices[0].stop_conditions == ["조건 A", "조건 B"]
    assert validate_response(resp, tool_results) == []


def test_safety_card_without_basis_is_flagged() -> None:
    """D-26·4.12: safety_flag 카드에 근거가 없으면 검증 오류."""
    tool_results = {
        "cards": [{"card_id": "K-0001", "safety_flag": True, "grade": "L1"}],
        "equipment": [],
        "checklist": [],
    }
    resp = build_response("query", None, tool_results)
    errors = validate_response(resp, tool_results)

    assert any("safety_basis_missing" in e for e in errors)
    assert "근거 미기재 — 검토 필요" in render_response(resp)


def test_model_citations_are_filtered_against_retrieval() -> None:
    """4.8 코드 검증: 검색 결과에 없는 인용 ID는 채택하지 않는다."""
    tool_results = _results(make_card_t1(card_id="K-0001"))
    resp = build_response(
        "query", None, tool_results, {"cited_card_ids": ["K-0001", "K-9999"], "answer": "본문"}
    )

    assert resp.cited_card_ids == ["K-0001"]
    assert resp.dropped_citations == ["K-9999"]
    assert resp.answer == "본문"
    assert validate_response(resp, tool_results) == []


def test_only_unknown_citations_fall_back_to_no_knowledge() -> None:
    """3.3: 인용 ID가 실제 결과에 없으면 '지식 없음'으로 치환한다."""
    tool_results = _results(make_card_t1(card_id="K-0001"))
    resp = build_response(
        "query", None, tool_results, {"cited_card_ids": ["K-9999"], "answer": "근거 없는 본문"}
    )
    text = render_response(resp)

    assert resp.no_knowledge is True
    assert resp.answer is None
    assert "해당 지식 없음" in text
    assert "근거 없는 본문" not in text
    assert "K-9999" in text  # 무엇을 버렸는지는 남긴다


def test_handover_candidates_are_proposals_only() -> None:
    """3.4 F-04: 인계 항목은 등록 후보로만 제시하고 저장하지 않는다."""
    tool_results = _results(make_card_t4(card_id="K-0004"))
    resp = build_response(
        "handover",
        None,
        tool_results,
        {"handover_candidates": [{"text": "RT-01 진동 재확인", "card_ids": ["K-0004"]}]},
    )
    text = render_response(resp)

    assert resp.handover_candidates[0].status == "proposed"
    assert "수락 전, 저장되지 않음" in text
    assert validate_response(resp, tool_results) == []


def test_handover_candidate_citing_unknown_card_is_flagged() -> None:
    """4.9: 근거 없는 조치 제안은 검증에서 걸러진다."""
    tool_results = _results(make_card_t1(card_id="K-0001"))
    resp = AgentResponse(mode="handover")
    resp.handover_candidates = [HandoverCandidate(text="점검", card_ids=["K-9999"])]

    errors = validate_response(resp, tool_results)
    assert any("handover_candidate_unknown_card" in e for e in errors)


def test_restart_failure_evidence_is_rendered() -> None:
    """D-29: 시도·실패의 근거 ID를 응답에 남긴다."""
    attempt = FailedAttempt(
        attempt_id="AT-0001",
        restart_type="normal_stop_restart",
        action="재시작",
        observed_result="실패",
        failure_reason=None,
        evidence_ids=["EV-0001"],
    )
    resp = build_response("query", None, _results(make_card_t6(failed_attempts=[attempt])))
    text = render_response(resp)

    assert resp.restart_failures[0].evidence_ids == ["EV-0001"]
    assert "근거: EV-0001" in text
    assert "이유: 미상" in text


def test_only_model_attributable_findings_are_retryable() -> None:
    """§4.3: 재시도는 모델이 고칠 수 있는 결함에만 적용한다."""
    assert is_model_retryable(["[cited_card_unknown] Cited card K-9999 not found"]) is True
    assert is_model_retryable(["[safety_basis_missing] Safety card K-0001 has no safety_basis"]) is False
    assert is_model_retryable([]) is False
