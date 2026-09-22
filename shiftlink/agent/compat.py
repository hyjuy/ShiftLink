"""Compatibility conversion from schema v0.9 to v1.0.

Contract: docs/design/D26-29_계약_v1.0.md §3.

Standing rules this module must not break:
- Never invent a missing safety_basis, resolution step, handover method, or
  failure reason. A record that lacks them is parked as ``needs_review``
  (개발계획_20260921-1002 §3.1, 통합본 4.7.4 "검증 기준").
- ``rejected`` is only for input outside the support boundary (not a dict, or a
  broken ``card_id``). Everything else must be read and classified.
- A converted card is always ``status="draft"``; auto promotion to ``accepted``
  is zero by construction.
- The input record is preserved verbatim in ``original`` for every outcome, so
  a ``needs_review`` result doubles as the review-queue record
  (``result.model_dump()``).

Issue codes emitted here (``ConversionIssue.code``):

===========================  ========== ====================================
code                         severity   meaning
===========================  ========== ====================================
not_a_dict                   deficiency input is not a mapping
card_id_invalid              deficiency card_id missing or not ``K-nnnn``
tacit_type_unknown           deficiency tacit_type outside T1~T6
t4_handover_method_missing   deficiency D-27 payload absent
t3_steps_missing             deficiency D-28 payload absent
t6_restart_type_missing      deficiency D-29/T6 payload absent
t5_safety_flag_missing       deficiency T5 without safety_flag
safety_basis_missing         deficiency D-26 basis absent
confidence_not_numeric       deficiency legacy grade string ("high")
payload_conflict             deficiency legacy key and type_payload disagree
payload_invalid              deficiency type_payload is not a mapping
step_scoped_field_unmappable deficiency step-scoped legacy value, no target
schema_validation_error      deficiency unmapped pydantic error
t3_steps_duplicated          deficiency duplicate step_id/order
t3_steps_out_of_order        deficiency steps not ascending
restart_type_conflict        deficiency attempt type != card type
payload_scope_violation      deficiency payload field on the wrong type
symptom_missing              deficiency T1/T3 without symptom
conditions_missing           deficiency T2 without conditions
grade_status_mismatch        deficiency accepted without grade L1
status_downgraded            warning    original status lowered to draft
field_relocated              warning    legacy top-level key moved to payload
extension_field_dropped      warning    v0.9 extension proposal, no v1.0 field
unknown_field_dropped        warning    unrecognised key, kept in ``original``
grade_not_revalidated        warning    grade carried over, gates not re-run
safety_review_required       warning    D-26 full human review before accept
tacit_type_out_of_v09_range  warning    input already uses T6
===========================  ========== ====================================
"""

import copy
from typing import Any, Iterable, Literal

from pydantic import BaseModel, Field, ValidationError, computed_field

from shiftlink.agent.schemas import SCHEMA_VERSION, KnowledgeCard

Severity = Literal["deficiency", "warning"]
Outcome = Literal["converted", "needs_review", "rejected"]

V09_TACIT_TYPES = ("T1", "T2", "T3", "T4", "T5")
# T6 is a post-meeting team decision, not a v0.9 type. This module never
# reclassifies an existing card into T6 (계약 §2.1.2 "소급 재분류하지 않는다").
V10_TACIT_TYPES = V09_TACIT_TYPES + ("T6",)

# Legacy top-level keys that hold what v1.0 nests under type_payload.
# Seen in docs/data/01_kb_cards_shared.json.
_PAYLOAD_KEYS = ("restart_type", "tried_and_failed")

# Legacy top-level keys that v1.0 scopes to a single ResolutionStep. There is no
# deterministic target step, so a non-empty value goes to review instead of
# being guessed onto a step.
_STEP_SCOPED_KEYS = ("stop_conditions", "expected_result")

# Extension proposals that never became v1.0 fields
# (docs/guides/카드_작성_가이드_초안.md §8). Dropped from the converted card,
# kept in ``original``.
_EXTENSION_KEYS = (
    "scope_level",
    "line_id",
    "equipment_ids",
    "component_ids",
    "segment_ids",
    "relation_ids",
    "context_conditions",
    "manual_refs",
    "is_synthetic",
    "valid_until",
    "verifier",
)

# Pydantic messages mapped back to stable codes so the review queue can group
# failures. Unmatched errors fall through to schema_validation_error.
_ERROR_MARKERS: tuple[tuple[str, str], ...] = (
    ("T4 cards require type_payload.handover_method", "t4_handover_method_missing"),
    ("T3 cards require type_payload.steps", "t3_steps_missing"),
    ("T6 cards require type_payload.restart_type", "t6_restart_type_missing"),
    ("T5 cards must set safety_flag", "t5_safety_flag_missing"),
    ("safety_flag cards require safety_basis", "safety_basis_missing"),
    ("T1 and T3 cards require symptom", "symptom_missing"),
    ("T2 cards require at least one condition", "conditions_missing"),
    ("unique step_ids", "t3_steps_duplicated"),
    ("unique orders", "t3_steps_duplicated"),
    ("ascending order", "t3_steps_out_of_order"),
    ("conflicts with attempt", "restart_type_conflict"),
    ("handover_method only allowed", "payload_scope_violation"),
    ("steps only allowed", "payload_scope_violation"),
    ("accepted cards must have grade", "grade_status_mismatch"),
)


class ConversionIssue(BaseModel):
    """One finding from a v0.9 → v1.0 conversion."""

    code: str
    severity: Severity
    message: str
    field: str | None = None

    def rendered(self) -> str:
        return f"[{self.code}] {self.message}"


class V09ConversionResult(BaseModel):
    """Result of converting a v0.9 card to v1.0."""

    outcome: Outcome
    card: KnowledgeCard | None = None
    original: dict = Field(default_factory=dict)  # Input preserved as-is.
    issues: list[ConversionIssue] = Field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    @computed_field  # type: ignore[prop-decorator]
    @property
    def deficiencies(self) -> list[str]:
        """Blocking reasons. Non-empty for needs_review and rejected."""
        return [i.rendered() for i in self.issues if i.severity == "deficiency"]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def warnings(self) -> list[str]:
        """Non-blocking notes a reviewer still has to read."""
        return [i.rendered() for i in self.issues if i.severity == "warning"]


class V09ConversionBatch(BaseModel):
    """Aggregate of a batch conversion — the evidence for harness category E."""

    results: list[V09ConversionResult] = Field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    @computed_field  # type: ignore[prop-decorator]
    @property
    def counts(self) -> dict[str, int]:
        counts = {"total": len(self.results), "converted": 0, "needs_review": 0, "rejected": 0}
        for result in self.results:
            counts[result.outcome] += 1
        return counts

    @computed_field  # type: ignore[prop-decorator]
    @property
    def issue_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for result in self.results:
            for issue in result.issues:
                counts[issue.code] = counts.get(issue.code, 0) + 1
        return dict(sorted(counts.items()))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def duplicate_card_ids(self) -> list[str]:
        """card_ids appearing more than once. Reported, never silently merged."""
        seen: dict[str, int] = {}
        for result in self.results:
            card_id = result.original.get("card_id")
            if isinstance(card_id, str):
                seen[card_id] = seen.get(card_id, 0) + 1
        return sorted(cid for cid, n in seen.items() if n > 1)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def auto_accepted(self) -> int:
        """Cards that came out not-draft. Must stay 0 (계약 §3)."""
        return sum(
            1 for r in self.results if r.card is not None and r.card.status != "draft"
        )


def convert_card_v09(raw: Any) -> V09ConversionResult:
    """
    Convert a v0.9 KnowledgeCard dict to the v1.0 schema.

    Outcome:
    - "converted": validated against v1.0, ``status`` forced to "draft".
    - "needs_review": readable but missing or ambiguous v1.0 content
      (T4 handover_method, T3 steps, safety_basis, non-numeric confidence,
      step-scoped legacy values). Nothing is auto-created to make it pass.
    - "rejected": outside the support boundary — not a dict, or a broken
      ``card_id``.

    All findings are collected in one pass, so a reviewer sees every reason at
    once instead of one per round trip. The input is always preserved in
    ``original``.
    """
    if not isinstance(raw, dict):
        return V09ConversionResult(
            outcome="rejected",
            original={},
            issues=[
                ConversionIssue(
                    code="not_a_dict",
                    severity="deficiency",
                    message=f"Input is not a dict (got {type(raw).__name__})",
                )
            ],
        )

    original = copy.deepcopy(raw)

    card_id = raw.get("card_id")
    if not isinstance(card_id, str) or not (card_id.startswith("K-") and card_id[2:].isdigit()):
        return V09ConversionResult(
            outcome="rejected",
            original=original,
            issues=[
                ConversionIssue(
                    code="card_id_invalid",
                    severity="deficiency",
                    field="card_id",
                    message="card_id format invalid or missing (expected K-nnnn)",
                )
            ],
        )

    data = copy.deepcopy(raw)
    issues: list[ConversionIssue] = []
    issues += _normalise_legacy_fields(data)
    issues += _check_type_rules(data)
    issues += _apply_status_policy(data)

    # Always validate, even when deficiencies are already known: the reviewer
    # gets the full picture in one pass. Codes are deduplicated afterwards.
    card: KnowledgeCard | None = None
    try:
        card = KnowledgeCard.model_validate(data)
    except ValidationError as exc:
        issues += _map_validation_errors(exc)

    issues = _dedupe(issues)
    blocked = any(i.severity == "deficiency" for i in issues)

    if blocked or card is None:
        if not blocked:  # Defensive: needs_review must always carry a reason.
            issues.append(
                ConversionIssue(
                    code="schema_validation_error",
                    severity="deficiency",
                    message="Card could not be built under schema v1.0",
                )
            )
        return V09ConversionResult(outcome="needs_review", original=original, issues=issues)

    return V09ConversionResult(
        outcome="converted", card=card, original=original, issues=issues
    )


def convert_cards_v09(raws: Iterable[Any]) -> V09ConversionBatch:
    """Convert a batch and aggregate the evidence (counts, issue codes, duplicates)."""
    return V09ConversionBatch(results=[convert_card_v09(raw) for raw in raws])


def _is_empty(value: Any) -> bool:
    return value is None or value == [] or value == {} or value == ""


def _payload_view(data: dict) -> dict:
    payload = data.get("type_payload")
    return payload if isinstance(payload, dict) else {}


def _normalise_legacy_fields(data: dict) -> list[ConversionIssue]:
    """Relocate, drop, or flag v0.9 keys that v1.0 does not accept in place."""
    issues: list[ConversionIssue] = []

    payload = data.get("type_payload")
    if payload is not None and not isinstance(payload, dict):
        issues.append(
            ConversionIssue(
                code="payload_invalid",
                severity="deficiency",
                field="type_payload",
                message="type_payload must be an object",
            )
        )
        return issues

    # v1.0 nests restart_type / tried_and_failed under type_payload. Moving them
    # is relocation, not creation — the content is unchanged.
    for key in _PAYLOAD_KEYS:
        if key not in data:
            continue
        value = data.pop(key)
        if _is_empty(value):
            continue
        existing = _payload_view(data).get(key)
        if not _is_empty(existing) and existing != value:
            issues.append(
                ConversionIssue(
                    code="payload_conflict",
                    severity="deficiency",
                    field=key,
                    message=(
                        f"Top-level {key} disagrees with type_payload.{key}; "
                        "not merged automatically"
                    ),
                )
            )
            continue
        if not isinstance(data.get("type_payload"), dict):
            data["type_payload"] = {}
        data["type_payload"][key] = value
        issues.append(
            ConversionIssue(
                code="field_relocated",
                severity="warning",
                field=key,
                message=f"Moved top-level {key} into type_payload.{key}",
            )
        )

    # stop_conditions / expected_result belong to a single step in v1.0. Which
    # step is not derivable, so a non-empty value goes to review.
    for key in _STEP_SCOPED_KEYS:
        if key not in data:
            continue
        value = data.pop(key)
        if _is_empty(value):
            continue
        issues.append(
            ConversionIssue(
                code="step_scoped_field_unmappable",
                severity="deficiency",
                field=key,
                message=(
                    f"{key} is a per-step field in v1.0 (ResolutionStep.{key}); "
                    "the target step cannot be inferred, so it is not moved"
                ),
            )
        )

    confidence = data.get("confidence")
    if "confidence" in data and (
        isinstance(confidence, bool) or not isinstance(confidence, (int, float))
    ):
        issues.append(
            ConversionIssue(
                code="confidence_not_numeric",
                severity="deficiency",
                field="confidence",
                message=(
                    f"confidence must be a number in [0, 1] (got {confidence!r}); "
                    "legacy grade strings are not auto-converted — no mapping is defined"
                ),
            )
        )

    known = set(KnowledgeCard.model_fields)
    for key in [k for k in data if k not in known]:
        data.pop(key)
        if key in _EXTENSION_KEYS:
            issues.append(
                ConversionIssue(
                    code="extension_field_dropped",
                    severity="warning",
                    field=key,
                    message=f"{key} is a v0.9 extension proposal, not a v1.0 field; kept in original",
                )
            )
        else:
            issues.append(
                ConversionIssue(
                    code="unknown_field_dropped",
                    severity="warning",
                    field=key,
                    message=f"Unrecognised field {key} dropped from the card; kept in original",
                )
            )

    return issues


def _check_type_rules(data: dict) -> list[ConversionIssue]:
    """Structural checks for D-26~29 payloads, phrased for a human reviewer."""
    issues: list[ConversionIssue] = []
    tacit_type = data.get("tacit_type")
    payload = _payload_view(data)

    if not isinstance(tacit_type, str) or tacit_type not in V10_TACIT_TYPES:
        issues.append(
            ConversionIssue(
                code="tacit_type_unknown",
                severity="deficiency",
                field="tacit_type",
                message=f"tacit_type {tacit_type!r} is outside {list(V10_TACIT_TYPES)}",
            )
        )
        return issues

    if tacit_type == "T6":
        issues.append(
            ConversionIssue(
                code="tacit_type_out_of_v09_range",
                severity="warning",
                field="tacit_type",
                message=(
                    "Input already uses T6 (post-meeting team type). Kept as-is; "
                    "this converter never reclassifies a card into T6"
                ),
            )
        )

    if tacit_type == "T4" and not payload.get("handover_method"):
        issues.append(
            ConversionIssue(
                code="t4_handover_method_missing",
                severity="deficiency",
                field="type_payload.handover_method",
                message=(
                    "T4 requires type_payload.handover_method "
                    "(내용·대상·시점·방법·확인, not auto-created)"
                ),
            )
        )

    if tacit_type == "T3" and not payload.get("steps"):
        issues.append(
            ConversionIssue(
                code="t3_steps_missing",
                severity="deficiency",
                field="type_payload.steps",
                message="T3 requires type_payload.steps (not auto-created)",
            )
        )

    if tacit_type == "T6" and not payload.get("restart_type"):
        issues.append(
            ConversionIssue(
                code="t6_restart_type_missing",
                severity="deficiency",
                field="type_payload.restart_type",
                message="T6 requires type_payload.restart_type (not auto-created)",
            )
        )

    if tacit_type == "T5" and data.get("safety_flag") is not True:
        issues.append(
            ConversionIssue(
                code="t5_safety_flag_missing",
                severity="deficiency",
                field="safety_flag",
                message="T5 requires safety_flag=True; the flag is not set automatically",
            )
        )

    if data.get("safety_flag") is True:
        if not data.get("safety_basis"):
            issues.append(
                ConversionIssue(
                    code="safety_basis_missing",
                    severity="deficiency",
                    field="safety_basis",
                    message="safety_flag requires safety_basis (not auto-created)",
                )
            )
        else:
            issues.append(
                ConversionIssue(
                    code="safety_review_required",
                    severity="warning",
                    field="safety_flag",
                    message=(
                        "D-26: every safety_flag=True card needs full human review "
                        "before it can be accepted again"
                    ),
                )
            )

    return issues


def _apply_status_policy(data: dict) -> list[ConversionIssue]:
    """Force status to draft and flag a grade that was never re-verified."""
    issues: list[ConversionIssue] = []

    previous = data.get("status")
    if previous != "draft":
        issues.append(
            ConversionIssue(
                code="status_downgraded",
                severity="warning",
                field="status",
                message=f"status {previous!r} lowered to 'draft' (no auto acceptance)",
            )
        )
    data["status"] = "draft"

    grade = data.get("grade")
    if grade in {"L1", "L2", "L3"}:
        issues.append(
            ConversionIssue(
                code="grade_not_revalidated",
                severity="warning",
                field="grade",
                message=(
                    f"grade {grade} carried over from v0.9; the v1.0 gates "
                    "(schema→rule→dedup→judge→human) have not been re-run"
                ),
            )
        )

    return issues


def _map_validation_errors(exc: ValidationError) -> list[ConversionIssue]:
    issues: list[ConversionIssue] = []
    for err in exc.errors():
        message = err["msg"]
        location = ".".join(str(part) for part in err["loc"]) or None
        code = next((c for marker, c in _ERROR_MARKERS if marker in message), None)
        if code is None:
            issues.append(
                ConversionIssue(
                    code="schema_validation_error",
                    severity="deficiency",
                    field=location,
                    message=f"{err['loc']}: {message}",
                )
            )
        else:
            issues.append(
                ConversionIssue(
                    code=code, severity="deficiency", field=location, message=message
                )
            )
    return issues


def _dedupe(issues: list[ConversionIssue]) -> list[ConversionIssue]:
    """
    Keep the first issue per code; the model validator repeats our own checks
    with a different wording. Per-field codes are kept once per field.
    """
    per_field = {
        "field_relocated",
        "extension_field_dropped",
        "unknown_field_dropped",
        "step_scoped_field_unmappable",
        "payload_conflict",
    }
    # A field already explained by a specific code does not need the raw
    # pydantic message on top of it.
    explained = {
        i.field
        for i in issues
        if i.severity == "deficiency" and i.code != "schema_validation_error" and i.field
    }
    seen: set[tuple[str, str | None]] = set()
    unique: list[ConversionIssue] = []
    for issue in issues:
        if issue.code == "schema_validation_error":
            if issue.field in explained:
                continue
            key = (issue.code, issue.message)
        elif issue.code in per_field:
            key = (issue.code, issue.field)
        else:
            key = (issue.code, None)
        if key in seen:
            continue
        seen.add(key)
        unique.append(issue)
    return unique
