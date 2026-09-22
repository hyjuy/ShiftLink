"""Test v0.9 to v1.0 conversion compatibility."""

from datetime import datetime, timezone

import pytest

from shiftlink.agent.compat import convert_card_v09, convert_cards_v09
from shiftlink.agent.schemas import Provenance


def _codes(result) -> list[str]:
    return [issue.code for issue in result.issues]


def _v09_card(**overrides) -> dict:
    """A v0.9 T1 card in the shape real fixtures use (JSON-like provenance)."""
    card = {
        "card_id": "K-0100",
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
        "provenance": {
            "seed_ids": ["SD-001"],
            "persona_id": "V-01",
            "event_ids": ["EV-0001"],
            "generator": "gen-model-A",
            "generated_at": "2026-09-21T00:00:00+00:00",
        },
        "split": "kb",
        "status": "draft",
    }
    card.update(overrides)
    return card


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


# --- v1.0 고도화: 실제 v0.9 데이터 형태 처리 ---


def test_legacy_string_confidence_is_not_auto_converted() -> None:
    """docs/data/01_kb_cards_shared.json 형태: confidence="high" → needs_review."""
    result = convert_card_v09(_v09_card(confidence="high"))
    assert result.outcome == "needs_review"
    assert "confidence_not_numeric" in _codes(result)
    # No mapping from "high" to a number is defined, so nothing is invented.
    assert result.card is None


def test_extension_fields_are_dropped_with_a_warning_not_a_deficiency() -> None:
    """v0.9 확장 제안 필드는 카드에서 빠지되 original에 남고 변환은 진행된다."""
    result = convert_card_v09(
        _v09_card(scope_level="equipment", manual_refs=["MS-0007"], is_synthetic=True)
    )
    assert result.outcome == "converted"
    assert _codes(result).count("extension_field_dropped") == 3
    assert result.deficiencies == []
    assert result.original["manual_refs"] == ["MS-0007"]


def test_unknown_field_is_reported_separately() -> None:
    result = convert_card_v09(_v09_card(totally_new_field=1))
    assert result.outcome == "converted"
    assert "unknown_field_dropped" in _codes(result)


def test_top_level_restart_payload_is_relocated_not_lost() -> None:
    """D-29 재가동 데이터가 최상위에 있으면 type_payload로 옮긴다(창작 아님)."""
    attempt = {
        "attempt_id": "AT-0001",
        "restart_type": "abnormal_stop_restart",
        "action": "리셋 후 기동",
        "observed_result": "재정지",
        "failure_reason": None,
    }
    result = convert_card_v09(
        _v09_card(restart_type="abnormal_stop_restart", tried_and_failed=[attempt])
    )
    assert result.outcome == "converted"
    assert _codes(result).count("field_relocated") == 2
    assert result.card.type_payload.restart_type == "abnormal_stop_restart"
    assert result.card.type_payload.tried_and_failed[0].attempt_id == "AT-0001"
    # 미상 실패 이유는 문자열로 채우지 않는다.
    assert result.card.type_payload.tried_and_failed[0].failure_reason is None


def test_payload_conflict_is_not_merged() -> None:
    result = convert_card_v09(
        _v09_card(
            restart_type="maintenance_restart",
            type_payload={"restart_type": "normal_stop_restart"},
        )
    )
    assert result.outcome == "needs_review"
    assert "payload_conflict" in _codes(result)


def test_step_scoped_legacy_value_goes_to_review() -> None:
    """stop_conditions는 v1.0에서 단계 단위이므로 임의의 단계에 붙이지 않는다."""
    result = convert_card_v09(_v09_card(stop_conditions=["압력 상승 시 중지"]))
    assert result.outcome == "needs_review"
    assert "step_scoped_field_unmappable" in _codes(result)


def test_empty_step_scoped_value_does_not_block() -> None:
    result = convert_card_v09(_v09_card(stop_conditions=[], expected_result=None))
    assert result.outcome == "converted"
    assert "step_scoped_field_unmappable" not in _codes(result)


def test_all_deficiencies_collected_in_one_pass() -> None:
    """T4 payload 누락과 safety_basis 누락을 한 번에 보고한다."""
    result = convert_card_v09(
        _v09_card(card_id="K-0101", tacit_type="T4", safety_flag=True, symptom=None)
    )
    assert result.outcome == "needs_review"
    codes = _codes(result)
    assert "t4_handover_method_missing" in codes
    assert "safety_basis_missing" in codes
    # 같은 사유가 모델 검증에서 반복돼도 한 번만 보고한다.
    assert codes.count("t4_handover_method_missing") == 1


def test_t5_without_safety_flag_is_not_auto_flagged() -> None:
    result = convert_card_v09(
        _v09_card(card_id="K-0102", tacit_type="T5", symptom=None, safety_flag=False)
    )
    assert result.outcome == "needs_review"
    assert "t5_safety_flag_missing" in _codes(result)


def test_safety_card_carries_full_review_warning() -> None:
    """D-26: safety_flag 카드는 변환돼도 전수 검토 대상임을 표시한다."""
    result = convert_card_v09(
        _v09_card(card_id="K-0103", safety_flag=True, safety_basis="KOSHA GUIDE M-101-2012")
    )
    assert result.outcome == "converted"
    assert "safety_review_required" in _codes(result)


def test_status_and_grade_warnings() -> None:
    result = convert_card_v09(_v09_card(status="accepted", grade="L1"))
    assert result.outcome == "converted"
    assert result.card.status == "draft"
    codes = _codes(result)
    assert "status_downgraded" in codes
    # grade는 보존하되 재검증 전임을 남긴다.
    assert "grade_not_revalidated" in codes
    assert result.card.grade == "L1"


def test_t6_input_is_kept_not_reclassified() -> None:
    result = convert_card_v09(
        _v09_card(
            card_id="K-0104",
            tacit_type="T6",
            symptom=None,
            type_payload={"restart_type": "normal_stop_restart"},
        )
    )
    assert result.outcome == "converted"
    assert "tacit_type_out_of_v09_range" in _codes(result)
    assert result.card.tacit_type == "T6"


def test_t6_without_restart_type_needs_review() -> None:
    result = convert_card_v09(_v09_card(card_id="K-0105", tacit_type="T6", symptom=None))
    assert result.outcome == "needs_review"
    assert "t6_restart_type_missing" in _codes(result)


def test_unknown_tacit_type_is_reported_clearly() -> None:
    result = convert_card_v09(_v09_card(tacit_type="T9"))
    assert result.outcome == "needs_review"
    assert "tacit_type_unknown" in _codes(result)


def test_original_is_an_independent_deep_copy() -> None:
    raw = _v09_card(provenance={"seed_ids": ["SD-001"], "persona_id": "V-01",
                                "event_ids": [], "generator": "g",
                                "generated_at": "2026-09-21T00:00:00+00:00"})
    result = convert_card_v09(raw)
    raw["provenance"]["seed_ids"].append("SD-999")
    raw["title"] = "변경됨"
    assert result.original["provenance"]["seed_ids"] == ["SD-001"]
    assert result.original["title"] == "펌프 이상음"


def test_batch_conversion_reports_evidence() -> None:
    batch = convert_cards_v09(
        [
            _v09_card(card_id="K-0200", status="accepted"),
            _v09_card(card_id="K-0200", confidence="high"),  # duplicate id + deficiency
            _v09_card(card_id="K-0201", tacit_type="T4", symptom=None),
            "not a dict",
        ]
    )
    assert batch.counts == {
        "total": 4,
        "converted": 1,
        "needs_review": 2,
        "rejected": 1,
    }
    assert batch.duplicate_card_ids == ["K-0200"]
    assert batch.auto_accepted == 0  # 계약 §3: 자동 accepted 편입 0건
    assert batch.issue_counts["confidence_not_numeric"] == 1
    assert batch.issue_counts["t4_handover_method_missing"] == 1


def test_result_serialises_as_a_review_queue_record() -> None:
    result = convert_card_v09(_v09_card(card_id="K-0202", tacit_type="T3", steps=None))
    dumped = result.model_dump()
    assert dumped["outcome"] == "needs_review"
    assert dumped["original"]["card_id"] == "K-0202"
    assert dumped["deficiencies"]  # 결함 사유가 직렬화에 포함된다
    assert dumped["schema_version"] == "1.0"
