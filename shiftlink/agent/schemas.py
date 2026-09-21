"""Pipeline data contracts for schema version 0.9."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


Split = Literal["kb", "dev", "sealed"]
Equipment = Literal["HPU", "GR", "RT", "CV", "COMMON"]


class Condition(BaseModel):
    signal: str
    op: str
    value: Any
    unit: str | None = None


class Provenance(BaseModel):
    seed_ids: list[str]
    persona_id: str
    event_ids: list[str]
    generator: str
    generated_at: datetime


class KnowledgeCard(BaseModel):
    card_id: str = Field(pattern=r"^K-\d{4}$")
    version: str
    grade: Literal["L0", "L1", "L2", "L3"] = "L0"
    tacit_type: Literal["T1", "T2", "T3", "T4", "T5"]
    equipment: Equipment
    component: str
    scenario: Literal["S1", "S2", "S3"]
    title: str
    symptom: str | None = None
    know_how: str
    rationale: str
    conditions: list[Condition] = Field(default_factory=list)
    exclusions: list[Condition] = Field(default_factory=list)
    safety_flag: bool = False
    safety_basis: str | None = None
    conflict_group: str | None = None
    confidence: float = Field(ge=0, le=1)
    provenance: Provenance
    split: Split
    status: Literal[
        "draft",
        "accepted",
        "rejected_rule",
        "rejected_judge",
        "rejected_human",
        "rejected_safety",
    ] = "draft"

    # 아래 요구사항은 승인됨. v0.9에는 확장 미구현이며, 상세 필드명은
    # 구현 제안으로서 9/22 계약 검토 후 스키마 v1.0에 고정한다.
    # D-26 승인: 안전 조건을 safety_flag=True 전체로 확장한다.
    # T-27 / D-27 승인: T4에 어떻게 인수인계하는지 전달 방법을 담는다.
    # D-28 승인: 단계별 해결 순서를 보여줄 수 있도록 한다.
    # D-29 승인: 재가동 유형에 따라 실패를 구분할 수 있도록 한다.
    # 전달축 분리나 T6_setup_restart 신설까지 승인된 것으로 해석하지 않는다.

    @model_validator(mode="after")
    def validate_k01_rules(self) -> "KnowledgeCard":
        if self.tacit_type == "T5" and not self.safety_flag:
            raise ValueError("T5 cards must set safety_flag")
        if self.safety_flag and not self.safety_basis:
            raise ValueError("safety_flag cards require safety_basis")
        if self.tacit_type in {"T1", "T3"} and not self.symptom:
            raise ValueError("T1 and T3 cards require symptom")
        if self.tacit_type == "T2" and not self.conditions:
            raise ValueError("T2 cards require at least one condition")
        if self.status == "accepted" and self.grade != "L1":
            raise ValueError("accepted cards must have grade L1")
        return self


class Event(BaseModel):
    event_id: str = Field(pattern=r"^EV-\d{4}$")
    scenario: Literal["S1", "S2", "S3"]
    equipment: Equipment
    timeline: list[str]
    true_cause: str
    true_actions: list[str]
    measurements: dict[str, Any]
    cards_expected: list[str]
    split: Split


class Artifact(BaseModel):
    artifact_id: str = Field(pattern=r"^AR-\d{4}$")
    kind: Literal["qa", "work_note", "handover", "troubleshooting", "conditional_rule"]
    event_id: str = Field(pattern=r"^EV-\d{4}$")
    card_ids: list[str]
    persona_id: str
    text: str
    split: Split
    status: Literal["draft", "accepted", "rejected"] = "draft"
