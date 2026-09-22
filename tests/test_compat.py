"""Test v0.9 to v1.0 conversion compatibility."""

from datetime import datetime, timezone

import pytest

from shiftlink.agent.compat import convert_card_v09
from shiftlink.agent.schemas import Provenance


def test_v09_t1_basic_conversion() -> None:
    """Valid v0.9 T1 card converts to v1.0 with status=draft."""
    prov = Provenance(
        seed_ids=["SEED-001"],
        persona_id="P-01",
        event_ids=["EV-0001"],
        generator="fixture",
        generated_at=datetime.now(timezone.utc),
    )
    v09_card = {
        "card_id": "K-0001",
        "version": "0.9",
        "grade": "L1",
        "tacit_type": "T1",
        "equipment": "HPU",
        "component": "pump",
        "scenario": "S1",
        "title": "펌프 이상음",
        "symptom": "고주파 소음",
        "know_how": "설비를 정지하고 점검한다.",
        "rationale": "시뮬레이션에서 재현됨",
        "conditions": [],
        "exclusions": [],
        "safety_flag": False,
        "safety_basis": None,
        "conflict_group": None,
        "confidence": 0.8,
        "provenance": prov,
        "split": "kb",
        "status": "accepted",  # v0.9 status should be downgraded to draft.
    }

    result = convert_card_v09(v09_card)
    assert result.outcome == "converted"
    assert result.card is not None
    assert result.card.status == "draft"
    assert result.card.tacit_type == "T1"
    assert result.original == v09_card


def test_v09_t2_with_conditions() -> None:
    """Valid v0.9 T2 card with conditions converts."""
    prov = Provenance(
        seed_ids=["SEED-002"],
        persona_id="P-02",
        event_ids=["EV-0002"],
        generator="fixture",
        generated_at=datetime.now(timezone.utc),
    )
    v09_card = {
        "card_id": "K-0002",
        "version": "0.9",
        "grade": "L1",
        "tacit_type": "T2",
        "equipment": "HPU",
        "component": "pump",
        "scenario": "S1",
        "title": "조건부 대처",
        "symptom": None,
        "know_how": "압력을 확인하고 대처한다.",
        "rationale": "기술 사양",
        "conditions": [
            {"signal": "pressure", "op": ">", "value": 10, "unit": "bar"}
        ],
        "exclusions": [],
        "safety_flag": False,
        "safety_basis": None,
        "confidence": 0.85,
        "provenance": prov,
        "split": "kb",
        "status": "draft",
    }

    result = convert_card_v09(v09_card)
    assert result.outcome == "converted"
    assert result.card is not None
    assert result.card.status == "draft"
    assert result.card.tacit_type == "T2"


def test_v09_t5_safety_with_basis() -> None:
    """Valid v0.9 T5 safety card converts."""
    prov = Provenance(
        seed_ids=["SEED-003"],
        persona_id="P-03",
        event_ids=["EV-0003"],
        generator="fixture",
        generated_at=datetime.now(timezone.utc),
    )
    v09_card = {
        "card_id": "K-0003",
        "version": "0.9",
        "grade": "L1",
        "tacit_type": "T5",
        "equipment": "HPU",
        "component": "pump",
        "scenario": "S1",
        "title": "안전 규칙",
        "symptom": None,
        "know_how": "안전 절차를 따른다.",
        "rationale": "법규 요구사항",
        "conditions": [],
        "exclusions": [],
        "safety_flag": True,
        "safety_basis": "ISO 12345",
        "confidence": 0.95,
        "provenance": prov,
        "split": "kb",
        "status": "accepted",
    }

    result = convert_card_v09(v09_card)
    assert result.outcome == "converted"
    assert result.card is not None
    assert result.card.status == "draft"
    assert result.card.safety_flag is True


def test_v09_t4_missing_handover_method() -> None:
    """v0.9 T4 without handover_method → needs_review."""
    prov = Provenance(
        seed_ids=["SEED-004"],
        persona_id="P-04",
        event_ids=["EV-0004"],
        generator="fixture",
        generated_at=datetime.now(timezone.utc),
    )
    v09_card = {
        "card_id": "K-0004",
        "version": "0.9",
        "grade": "L1",
        "tacit_type": "T4",
        "equipment": "HPU",
        "component": "pump",
        "scenario": "S1",
        "title": "인계",
        "symptom": None,
        "know_how": "어떻게 인계하는가",
        "rationale": "구조화된 인계",
        "conditions": [],
        "exclusions": [],
        "safety_flag": False,
        "safety_basis": None,
        "confidence": 0.9,
        "provenance": prov,
        "split": "kb",
        "status": "draft",
    }

    result = convert_card_v09(v09_card)
    assert result.outcome == "needs_review"
    assert result.card is None
    assert len(result.deficiencies) > 0
    assert "handover_method" in result.deficiencies[0]
    assert result.original == v09_card


def test_v09_t3_missing_steps() -> None:
    """v0.9 T3 without steps → needs_review."""
    prov = Provenance(
        seed_ids=["SEED-005"],
        persona_id="P-05",
        event_ids=["EV-0005"],
        generator="fixture",
        generated_at=datetime.now(timezone.utc),
    )
    v09_card = {
        "card_id": "K-0005",
        "version": "0.9",
        "grade": "L1",
        "tacit_type": "T3",
        "equipment": "HPU",
        "component": "pump",
        "scenario": "S1",
        "title": "단계적 해결",
        "symptom": "압력 저하",
        "know_how": "단계별로 처리",
        "rationale": "절차",
        "conditions": [],
        "exclusions": [],
        "safety_flag": False,
        "safety_basis": None,
        "confidence": 0.9,
        "provenance": prov,
        "split": "kb",
        "status": "draft",
    }

    result = convert_card_v09(v09_card)
    assert result.outcome == "needs_review"
    assert result.card is None
    assert any("steps" in d for d in result.deficiencies)
    assert result.original == v09_card


def test_v09_safety_flag_without_basis() -> None:
    """v0.9 card with safety_flag but no safety_basis → needs_review."""
    prov = Provenance(
        seed_ids=["SEED-006"],
        persona_id="P-06",
        event_ids=["EV-0006"],
        generator="fixture",
        generated_at=datetime.now(timezone.utc),
    )
    v09_card = {
        "card_id": "K-0006",
        "version": "0.9",
        "grade": "L1",
        "tacit_type": "T1",
        "equipment": "HPU",
        "component": "pump",
        "scenario": "S1",
        "title": "안전 이슈",
        "symptom": "문제",
        "know_how": "조치",
        "rationale": "근거",
        "conditions": [],
        "exclusions": [],
        "safety_flag": True,
        "safety_basis": None,  # Missing!
        "confidence": 0.9,
        "provenance": prov,
        "split": "kb",
        "status": "draft",
    }

    result = convert_card_v09(v09_card)
    assert result.outcome == "needs_review"
    assert result.card is None
    assert any("safety_basis" in d for d in result.deficiencies)


def test_v09_non_dict_input() -> None:
    """Non-dict input → rejected."""
    result = convert_card_v09("not a dict")
    assert result.outcome == "rejected"
    assert result.card is None
    assert len(result.deficiencies) > 0


def test_v09_invalid_card_id() -> None:
    """Invalid card_id format → rejected."""
    result = convert_card_v09({"card_id": "INVALID-0001"})
    assert result.outcome == "rejected"
    assert result.card is None


def test_v09_missing_card_id() -> None:
    """Missing card_id → rejected."""
    result = convert_card_v09({})
    assert result.outcome == "rejected"
    assert result.card is None


def test_v09_converted_status_is_draft() -> None:
    """All converted cards must have status=draft, regardless of input."""
    prov = Provenance(
        seed_ids=["SEED-007"],
        persona_id="P-07",
        event_ids=["EV-0007"],
        generator="fixture",
        generated_at=datetime.now(timezone.utc),
    )
    v09_card = {
        "card_id": "K-0007",
        "version": "0.9",
        "grade": "L1",
        "tacit_type": "T2",
        "equipment": "HPU",
        "component": "pump",
        "scenario": "S1",
        "title": "테스트",
        "symptom": None,
        "know_how": "테스트",
        "rationale": "테스트",
        "conditions": [{"signal": "p", "op": ">", "value": 1}],
        "exclusions": [],
        "safety_flag": False,
        "safety_basis": None,
        "confidence": 0.9,
        "provenance": prov,
        "split": "kb",
        "status": "accepted",  # Try to import as accepted.
    }

    result = convert_card_v09(v09_card)
    assert result.outcome == "converted"
    assert result.card.status == "draft"  # Forced to draft.


def test_v09_original_preserved() -> None:
    """Original input always preserved in result.original."""
    original = {"card_id": "K-0008"}
    result = convert_card_v09(original)
    # Even if rejected, original is preserved.
    assert result.original == original


def test_v09_malformed_but_valid_card_id() -> None:
    """Card with valid ID but missing required fields → needs_review not rejected."""
    v09_card = {
        "card_id": "K-0009",
        "version": "0.9",
        # Missing many required fields...
    }
    result = convert_card_v09(v09_card)
    # Should be needs_review (validation error), not rejected.
    assert result.outcome == "needs_review"
    assert len(result.deficiencies) > 0
