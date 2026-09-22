from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from shiftlink.agent.schemas import (
    Artifact,
    Condition,
    Event,
    FailedAttempt,
    HandoverMethod,
    KnowledgeCard,
    Provenance,
    ResolutionStep,
    TypePayload,
)


@pytest.mark.parametrize("op", ["==", "!=", ">", ">=", "<", "<="])
def test_condition_accepts_supported_operators(op: str) -> None:
    assert Condition(signal="pressure", op=op, value=10).op == op


@pytest.mark.parametrize("op", ["=>", "=", "", "contains"])
def test_condition_rejects_unsupported_operators(op: str) -> None:
    with pytest.raises(ValidationError, match="op"):
        Condition(signal="pressure", op=op, value=10)


@pytest.mark.parametrize(
    "overrides, error",
    [
        ({"safety_flag": True, "safety_basis": " \t\n"}, "safety_basis"),
        ({"symptom": " \t\n"}, "symptom"),
        ({"type_payload": {"steps": []}}, "steps only allowed on T3"),
    ],
)
def test_card_rejects_validation_loopholes(overrides: dict, error: str) -> None:
    base = dict(
        card_id="K-0001", version="1.0", tacit_type="T1", equipment="HPU",
        component="pump", scenario="S1", title="Pump noise", symptom="Noise",
        know_how="Inspect pump", rationale="Wear", confidence=0.8, split="kb",
        provenance=dict(
            seed_ids=[], persona_id="P-01", event_ids=[], generator="test",
            generated_at="2026-09-22T00:00:00Z",
        ),
    )
    KnowledgeCard.model_validate(base)
    with pytest.raises(ValidationError, match=error):
        KnowledgeCard.model_validate(base | overrides)


def test_schema_v09_and_k01_validation_rules() -> None:
    base = {
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
        "provenance": Provenance(
            seed_ids=["SEED-001"],
            persona_id="P-01",
            event_ids=["EV-0001"],
            generator="fixture",
            generated_at=datetime.now(timezone.utc),
        ),
        "split": "kb",
        "status": "draft",
        "type_payload": None,
    }

    for overrides in (
        {"tacit_type": "T5", "safety_flag": False},
        {"safety_flag": True, "safety_basis": None},
        {"tacit_type": "T3", "symptom": None},
        {"tacit_type": "T2", "symptom": None, "conditions": []},
        {"status": "accepted", "grade": "L0"},
    ):
        with pytest.raises(ValidationError):
            KnowledgeCard.model_validate(base | overrides)

    # Valid T2 card (payload not required for T1, T2, T5).
    card = KnowledgeCard.model_validate(
        base
        | {
            "tacit_type": "T2",
            "symptom": None,
            "conditions": [Condition(signal="pressure", op=">", value=10)],
            "status": "accepted",
        }
    )
    event = Event(
        event_id="EV-0001",
        scenario="S1",
        equipment="HPU",
        timeline=["압력 저하", "설비 정지"],
        true_cause="펌프 마모",
        true_actions=["설비 정지"],
        measurements={"pressure": 10},
        cards_expected=[card.card_id],
        restart_attempts=[],
        split="kb",
    )
    artifact = Artifact(
        artifact_id="AR-0001",
        kind="work_note",
        event_id=event.event_id,
        card_ids=[card.card_id],
        persona_id="P-01",
        text="압력이 저하되어 설비를 정지함",
        split=event.split,
        status="draft",
    )

    assert (card.grade, event.split, artifact.event_id) == ("L1", "kb", "EV-0001")


def test_v10_t4_handover_method_required() -> None:
    """T4 cards must have handover_method in type_payload."""
    prov = Provenance(
        seed_ids=["S-01"],
        persona_id="P-01",
        event_ids=["EV-0001"],
        generator="test",
        generated_at=datetime.now(timezone.utc),
    )
    base = {
        "card_id": "K-0010",
        "version": "1.0",
        "grade": "L1",
        "tacit_type": "T4",
        "equipment": "HPU",
        "component": "pump",
        "scenario": "S1",
        "title": "인계 방법",
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
        "type_payload": None,
    }
    # T4 with no type_payload → error.
    with pytest.raises(ValidationError):
        KnowledgeCard.model_validate(base)

    # T4 with empty type_payload → error.
    with pytest.raises(ValidationError):
        KnowledgeCard.model_validate(base | {"type_payload": TypePayload()})

    # T4 with valid handover_method → success.
    payload = TypePayload(
        handover_method=HandoverMethod(
            required_context=["압력 수치"],
            recipient_role="정비팀",
            timing="즉시",
            channel="전화",
            acknowledgement="확인 서명",
        )
    )
    card = KnowledgeCard.model_validate(base | {"type_payload": payload})
    assert card.type_payload.handover_method is not None


def test_v10_t3_steps_required_and_ordered() -> None:
    """T3 cards must have steps, with unique ids/orders in ascending order."""
    prov = Provenance(
        seed_ids=["S-01"],
        persona_id="P-01",
        event_ids=["EV-0001"],
        generator="test",
        generated_at=datetime.now(timezone.utc),
    )
    base = {
        "card_id": "K-0011",
        "version": "1.0",
        "grade": "L1",
        "tacit_type": "T3",
        "equipment": "HPU",
        "component": "pump",
        "scenario": "S1",
        "title": "단계적 해결",
        "symptom": "압력 저하",
        "know_how": "단계 1, 단계 2",
        "rationale": "순차 진행",
        "conditions": [],
        "exclusions": [],
        "safety_flag": False,
        "safety_basis": None,
        "confidence": 0.9,
        "provenance": prov,
        "split": "kb",
        "status": "draft",
        "type_payload": None,
    }

    # T3 with no steps → error.
    with pytest.raises(ValidationError):
        KnowledgeCard.model_validate(base)

    # T3 with empty steps list → error.
    with pytest.raises(ValidationError):
        KnowledgeCard.model_validate(base | {"type_payload": TypePayload(steps=[])})

    # T3 with duplicate step_ids → error.
    payload_dup_id = TypePayload(
        steps=[
            ResolutionStep(
                step_id="ST-01",
                order=1,
                action="점검",
                expected_result="정상",
            ),
            ResolutionStep(
                step_id="ST-01",
                order=2,
                action="조정",
                expected_result="정상",
            ),
        ]
    )
    with pytest.raises(ValidationError, match="unique step_ids"):
        KnowledgeCard.model_validate(base | {"type_payload": payload_dup_id})

    # T3 with duplicate orders → error.
    payload_dup_order = TypePayload(
        steps=[
            ResolutionStep(
                step_id="ST-01",
                order=1,
                action="점검",
                expected_result="정상",
            ),
            ResolutionStep(
                step_id="ST-02",
                order=1,
                action="조정",
                expected_result="정상",
            ),
        ]
    )
    with pytest.raises(ValidationError, match="unique orders"):
        KnowledgeCard.model_validate(base | {"type_payload": payload_dup_order})

    # T3 with out-of-order steps → error.
    payload_unordered = TypePayload(
        steps=[
            ResolutionStep(
                step_id="ST-01",
                order=2,
                action="조정",
                expected_result="정상",
            ),
            ResolutionStep(
                step_id="ST-02",
                order=1,
                action="점검",
                expected_result="정상",
            ),
        ]
    )
    with pytest.raises(ValidationError, match="ascending order"):
        KnowledgeCard.model_validate(base | {"type_payload": payload_unordered})

    # Valid T3 with ordered steps.
    payload_valid = TypePayload(
        steps=[
            ResolutionStep(
                step_id="ST-01",
                order=1,
                action="점검",
                expected_result="정상",
            ),
            ResolutionStep(
                step_id="ST-02",
                order=2,
                action="조정",
                expected_result="정상",
            ),
        ]
    )
    card = KnowledgeCard.model_validate(base | {"type_payload": payload_valid})
    assert len(card.type_payload.steps) == 2


def test_v10_t6_restart_type_required() -> None:
    """T6 cards must have restart_type in type_payload."""
    prov = Provenance(
        seed_ids=["S-01"],
        persona_id="P-01",
        event_ids=["EV-0001"],
        generator="test",
        generated_at=datetime.now(timezone.utc),
    )
    base = {
        "card_id": "K-0012",
        "version": "1.0",
        "grade": "L1",
        "tacit_type": "T6",
        "equipment": "HPU",
        "component": "pump",
        "scenario": "S1",
        "title": "재가동 지식",
        "symptom": None,
        "know_how": "재가동 방법",
        "rationale": "신설 제안",
        "conditions": [],
        "exclusions": [],
        "safety_flag": False,
        "safety_basis": None,
        "confidence": 0.9,
        "provenance": prov,
        "split": "kb",
        "status": "draft",
        "type_payload": None,
    }

    # T6 with no restart_type → error.
    with pytest.raises(ValidationError):
        KnowledgeCard.model_validate(base)

    # T6 with valid restart_type.
    payload = TypePayload(restart_type="normal_stop_restart")
    card = KnowledgeCard.model_validate(base | {"type_payload": payload})
    assert card.type_payload.restart_type == "normal_stop_restart"


def test_v10_restart_type_consistency() -> None:
    """Card restart_type must match attempt restart_type (unless unknown)."""
    prov = Provenance(
        seed_ids=["S-01"],
        persona_id="P-01",
        event_ids=["EV-0001"],
        generator="test",
        generated_at=datetime.now(timezone.utc),
    )
    base = {
        "card_id": "K-0013",
        "version": "1.0",
        "grade": "L1",
        "tacit_type": "T1",
        "equipment": "HPU",
        "component": "pump",
        "scenario": "S1",
        "title": "재시작 기록",
        "symptom": "마모",
        "know_how": "점검",
        "rationale": "기록",
        "conditions": [],
        "exclusions": [],
        "safety_flag": False,
        "safety_basis": None,
        "confidence": 0.9,
        "provenance": prov,
        "split": "kb",
        "status": "draft",
    }

    # Card with known restart_type and attempt with different known type → error.
    payload_conflict = TypePayload(
        restart_type="normal_stop_restart",
        tried_and_failed=[
            FailedAttempt(
                attempt_id="AT-0001",
                restart_type="abnormal_stop_restart",
                action="조정",
                observed_result="실패",
            )
        ],
    )
    with pytest.raises(ValidationError, match="conflicts with attempt"):
        KnowledgeCard.model_validate(base | {"type_payload": payload_conflict})

    # Card with unknown restart_type allows any attempt type.
    payload_unknown = TypePayload(
        restart_type="unknown",
        tried_and_failed=[
            FailedAttempt(
                attempt_id="AT-0002",
                restart_type="normal_stop_restart",
                action="조정",
                observed_result="실패",
            )
        ],
    )
    card = KnowledgeCard.model_validate(base | {"type_payload": payload_unknown})
    assert card.type_payload.tried_and_failed[0].restart_type == "normal_stop_restart"


def test_v10_failure_reason_none_preserved() -> None:
    """failure_reason=None should be preserved (not converted to string)."""
    prov = Provenance(
        seed_ids=["S-01"],
        persona_id="P-01",
        event_ids=["EV-0001"],
        generator="test",
        generated_at=datetime.now(timezone.utc),
    )
    attempt = FailedAttempt(
        attempt_id="AT-0003",
        restart_type="normal_stop_restart",
        action="조정",
        observed_result="실패",
        failure_reason=None,
    )
    assert attempt.failure_reason is None


def test_v10_evidence_ids_format() -> None:
    r"""evidence_ids should accept ^(K|EV|AR)-\d{4}$ format."""
    attempt_valid = FailedAttempt(
        attempt_id="AT-0004",
        restart_type="normal_stop_restart",
        action="조정",
        observed_result="실패",
        evidence_ids=["K-0001", "EV-0002", "AR-0003"],
    )
    assert len(attempt_valid.evidence_ids) == 3


def test_v10_handover_method_scope() -> None:
    """handover_method only allowed on T4 cards."""
    prov = Provenance(
        seed_ids=["S-01"],
        persona_id="P-01",
        event_ids=["EV-0001"],
        generator="test",
        generated_at=datetime.now(timezone.utc),
    )
    base = {
        "card_id": "K-0014",
        "version": "1.0",
        "grade": "L1",
        "tacit_type": "T1",
        "equipment": "HPU",
        "component": "pump",
        "scenario": "S1",
        "title": "일반 지식",
        "symptom": "문제",
        "know_how": "대처",
        "rationale": "근거",
        "conditions": [],
        "exclusions": [],
        "safety_flag": False,
        "safety_basis": None,
        "confidence": 0.9,
        "provenance": prov,
        "split": "kb",
        "status": "draft",
    }

    # T1 with handover_method → error.
    payload = TypePayload(
        handover_method=HandoverMethod(
            required_context=["정보"],
            recipient_role="역할",
            timing="시점",
            channel="방법",
            acknowledgement="확인",
        )
    )
    with pytest.raises(ValidationError, match="handover_method only allowed on T4"):
        KnowledgeCard.model_validate(base | {"type_payload": payload})


def test_v10_steps_scope() -> None:
    """steps only allowed on T3 cards."""
    prov = Provenance(
        seed_ids=["S-01"],
        persona_id="P-01",
        event_ids=["EV-0001"],
        generator="test",
        generated_at=datetime.now(timezone.utc),
    )
    base = {
        "card_id": "K-0015",
        "version": "1.0",
        "grade": "L1",
        "tacit_type": "T1",
        "equipment": "HPU",
        "component": "pump",
        "scenario": "S1",
        "title": "일반 지식",
        "symptom": "문제",
        "know_how": "대처",
        "rationale": "근거",
        "conditions": [],
        "exclusions": [],
        "safety_flag": False,
        "safety_basis": None,
        "confidence": 0.9,
        "provenance": prov,
        "split": "kb",
        "status": "draft",
    }

    # T1 with steps (not allowed for T1) → error.
    payload = TypePayload(
        steps=[
            ResolutionStep(
                step_id="ST-01",
                order=1,
                action="조정",
                expected_result="정상",
            )
        ]
    )
    with pytest.raises(ValidationError, match="steps only allowed on T3"):
        KnowledgeCard.model_validate(base | {"type_payload": payload})


def test_v10_event_restart_attempts() -> None:
    """Event should support restart_attempts field."""
    event = Event(
        event_id="EV-0005",
        scenario="S1",
        equipment="HPU",
        timeline=["시작"],
        true_cause="원인",
        true_actions=["조치"],
        measurements={},
        cards_expected=["K-0001"],
        restart_attempts=[
            FailedAttempt(
                attempt_id="AT-0005",
                restart_type="normal_stop_restart",
                action="조정",
                observed_result="실패",
            )
        ],
        split="kb",
    )
    assert len(event.restart_attempts) == 1
