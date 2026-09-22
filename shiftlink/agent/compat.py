"""Compatibility conversion from schema v0.9 to v1.0."""

from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from shiftlink.agent.schemas import KnowledgeCard


class V09ConversionResult(BaseModel):
    """Result of converting a v0.9 card to v1.0."""
    outcome: Literal["converted", "needs_review", "rejected"]
    card: KnowledgeCard | None = None
    original: dict  # Original input preserved as-is.
    deficiencies: list[str] = []


def convert_card_v09(raw: Any) -> V09ConversionResult:
    """
    Convert v0.9 KnowledgeCard dict to v1.0 schema.

    Outcome:
    - "converted": Successfully validated and converted to v1.0, status set to "draft".
    - "needs_review": Lacks required v1.0 fields (T4 handover_method, T3 steps, safety_basis).
      No automatic creation of these fields.
    - "rejected": Input is not a dict or has malformed card_id (support boundary).

    Original dict is always preserved in original field.
    """
    # Input validation: must be dict and have valid card_id format.
    if not isinstance(raw, dict):
        return V09ConversionResult(
            outcome="rejected",
            original=raw if isinstance(raw, dict) else {},
            deficiencies=["Input is not a dict"],
        )

    card_id = raw.get("card_id")
    if not isinstance(card_id, str) or not (card_id.startswith("K-") and card_id[2:].isdigit()):
        return V09ConversionResult(
            outcome="rejected",
            original=raw,
            deficiencies=["card_id format invalid or missing"],
        )

    # Build conversion data: copy input, force status to "draft", check deficiencies.
    data = dict(raw)
    deficiencies: list[str] = []
    tacit_type = data.get("tacit_type")

    # Check for needed v1.0 fields without auto-creation.
    if tacit_type == "T4":
        payload = data.get("type_payload")
        if not payload or not isinstance(payload, dict) or not payload.get("handover_method"):
            deficiencies.append("T4 requires type_payload.handover_method (not auto-created)")

    if tacit_type == "T3":
        payload = data.get("type_payload")
        if not payload or not isinstance(payload, dict) or not payload.get("steps"):
            deficiencies.append("T3 requires type_payload.steps (not auto-created)")

    safety_flag = data.get("safety_flag")
    if safety_flag is True:
        safety_basis = data.get("safety_basis")
        if not safety_basis:
            deficiencies.append("safety_flag requires safety_basis (not auto-created)")

    # Force status to "draft" for all converted cards.
    data["status"] = "draft"

    # If deficiencies exist, return needs_review.
    if deficiencies:
        return V09ConversionResult(
            outcome="needs_review",
            original=raw,
            deficiencies=deficiencies,
        )

    # Attempt validation with v1.0 schema.
    try:
        card = KnowledgeCard.model_validate(data)
        return V09ConversionResult(
            outcome="converted",
            card=card,
            original=raw,
            deficiencies=[],
        )
    except ValidationError as e:
        # Validation failure → needs_review (malformed data beyond card_id scope).
        error_messages = [f"{err['loc']}: {err['msg']}" for err in e.errors()]
        return V09ConversionResult(
            outcome="needs_review",
            original=raw,
            deficiencies=error_messages,
        )
