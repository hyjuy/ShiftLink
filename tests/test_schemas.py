from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from shiftlink.agent.schemas import Artifact, Condition, Event, KnowledgeCard, Provenance


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
