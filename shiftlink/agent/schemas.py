"""Pipeline data contracts for schema version 1.0."""

import operator
from datetime import datetime
from typing import Annotated, Any, Callable, Literal, Mapping

from pydantic import BaseModel, Field, StringConstraints, model_validator

SCHEMA_VERSION = "1.0"

# Allowed Condition operators (계약 §4.2). Anything else evaluates to unknown.
_COMPARISONS: dict[str, Callable[[Any, Any], bool]] = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
}


Split = Literal["kb", "dev", "sealed"]
Equipment = Literal["HPU", "GR", "RT", "CV", "COMMON"]

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
RestartType = Literal["normal_stop_restart", "abnormal_stop_restart", "maintenance_restart", "unknown"]


class Condition(BaseModel):
    signal: str
    op: str
    value: Any
    unit: str | None = None

    def evaluate(self, observations: Mapping[str, Any] | None) -> bool | None:
        """
        Deterministic condition match (계약 §4.2).

        True/False when the signal is observed and comparable, None when the
        signal is missing or not comparable (unknown — never treated as False).
        """
        if not observations or self.signal not in observations:
            return None
        observed = observations[self.signal]
        comparison = _COMPARISONS.get(self.op)
        if comparison is None:
            return None
        try:
            return comparison(observed, self.value)
        except TypeError:
            return None


class HandoverMethod(BaseModel):
    """D-27: T4 handover method details."""
    required_context: list[NonBlank] = Field(min_length=1)
    recipient_role: NonBlank
    timing: NonBlank
    channel: NonBlank
    acknowledgement: NonBlank


class ResolutionStep(BaseModel):
    """D-28: T3 resolution steps."""
    step_id: str = Field(pattern=r"^ST-\d{2,4}$")
    order: int = Field(ge=1)
    action: NonBlank
    preconditions: list[str] = Field(default_factory=list)
    expected_result: NonBlank
    stop_conditions: list[str] = Field(default_factory=list)


class FailedAttempt(BaseModel):
    """D-29: Restart attempt record with outcome."""
    attempt_id: str = Field(pattern=r"^AT-\d{4}$")
    restart_type: RestartType
    action: NonBlank
    observed_result: NonBlank
    failure_reason: str | None = None
    # Format check only; referential integrity is verified by the eval harness.
    evidence_ids: list[Annotated[str, StringConstraints(pattern=r"^(K|EV|AR)-\d{4}$")]] = Field(
        default_factory=list
    )


class TypePayload(BaseModel):
    """v1.0: Tacit type specific payload."""
    handover_method: HandoverMethod | None = None
    steps: list[ResolutionStep] | None = None
    restart_type: RestartType | None = None
    tried_and_failed: list[FailedAttempt] = Field(default_factory=list)


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
    tacit_type: Literal["T1", "T2", "T3", "T4", "T5", "T6"]
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
    type_payload: TypePayload | None = None

    # Implementation notes for v1.0 contracts (D-26~29 approved requirements):
    # D-26 approved: safety conditions extended to all safety_flag=True cards.
    # D-27 approved: T4 handover method details stored as structured data.
    # D-28 approved: T3 resolution steps shown with order. Field names are implementation proposals.
    # D-29 approved: Restart failures distinguished by restart type and attempt record.
    # T6 setup restart: team-confirmed after the 9/21 meeting; not part of the
    # meeting's own decisions (do not report as approved by that meeting).
    # Axis separation (Event vs Card) not approved in meeting scope.

    @model_validator(mode="after")
    def validate_k01_rules(self) -> "KnowledgeCard":
        # Existing v0.9 rules.
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

        # v1.0 rules.
        # Rule 1: T4 must have handover_method.
        if self.tacit_type == "T4":
            if not self.type_payload or not self.type_payload.handover_method:
                raise ValueError("T4 cards require type_payload.handover_method")

        # Rule 2: T3 must have steps with no duplicates and ascending order.
        if self.tacit_type == "T3":
            if not self.type_payload or not self.type_payload.steps:
                raise ValueError("T3 cards require type_payload.steps (at least 1)")
            if len(self.type_payload.steps) < 1:
                raise ValueError("T3 cards require type_payload.steps (at least 1)")
            step_ids = [step.step_id for step in self.type_payload.steps]
            if len(step_ids) != len(set(step_ids)):
                raise ValueError("T3 steps must have unique step_ids")
            orders = [step.order for step in self.type_payload.steps]
            if len(orders) != len(set(orders)):
                raise ValueError("T3 steps must have unique orders")
            if orders != sorted(orders):
                raise ValueError("T3 steps must be in ascending order by order field")

        # Rule 3: T6 must have restart_type.
        if self.tacit_type == "T6":
            if not self.type_payload or not self.type_payload.restart_type:
                raise ValueError("T6 cards require type_payload.restart_type")

        # Rule 4: tried_and_failed restart_type consistency.
        if self.type_payload and self.type_payload.tried_and_failed:
            card_restart = self.type_payload.restart_type
            if card_restart and card_restart != "unknown":
                for attempt in self.type_payload.tried_and_failed:
                    if attempt.restart_type != "unknown" and attempt.restart_type != card_restart:
                        raise ValueError(
                            f"Card restart_type {card_restart} conflicts with attempt "
                            f"restart_type {attempt.restart_type} (only unknown allowed to mix)"
                        )

        # Rule 5: handover_method and steps scope restriction.
        if self.type_payload:
            if self.type_payload.handover_method and self.tacit_type != "T4":
                raise ValueError("handover_method only allowed on T4 cards")
            if self.type_payload.steps and self.tacit_type != "T3":
                raise ValueError("steps only allowed on T3 cards")

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
    restart_attempts: list[FailedAttempt] = Field(default_factory=list)
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
