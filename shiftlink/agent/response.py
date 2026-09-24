"""Agent response building and rendering (D-26~29 §4.3)."""

import re
from typing import Any
from pydantic import BaseModel, Field, ConfigDict
from shiftlink.agent.router import QueryRequest, HandoverRequest
from shiftlink.agent.schemas import EvidenceGap, GeneralizationEvidence, Provenance, SafetyReview


class SafetyNotice(BaseModel):
    """Safety card notice (card_id, safety_basis, stop_conditions)."""
    card_id: str
    safety_basis: str
    stop_conditions: list[str] = Field(default_factory=list)


class StepRender(BaseModel):
    """Resolution step in order."""
    step_id: str
    order: int
    action: str
    expected_result: str
    stop_conditions: list[str] = Field(default_factory=list)
    verification_step: str | None = None
    rollback_action: str | None = None
    escalation_target: str | None = None
    escalation_channel: str | None = None


class HandoverMethodRender(BaseModel):
    """T4 handover method (5 elements)."""
    required_context: list[str] = Field(min_length=1)
    recipient_role: str
    timing: str
    channel: str
    acknowledgement: str


class RestartFailure(BaseModel):
    """Single restart failure attempt."""
    attempt_id: str
    restart_type: str  # "normal_stop_restart", "abnormal_stop_restart", "maintenance_restart", "unknown"
    action: str
    observed_result: str
    failure_reason: str | None = None
    evidence_gap: EvidenceGap | None = None
    next_observations: list[str] = Field(default_factory=list)
    required_data: list[str] = Field(default_factory=list)
    data_collection_role: str | None = None


class CardMetadata(BaseModel):
    provenance: Provenance
    generalization_evidence: GeneralizationEvidence | None = None
    safety_review: SafetyReview | None = None


class AgentResponse(BaseModel):
    """Structured response output (D-26~29 §4.3)."""
    model_config = ConfigDict(use_enum_values=True)

    mode: str  # "query" or "handover"
    safety_notices: list[SafetyNotice] = Field(default_factory=list)
    steps: list[StepRender] = Field(default_factory=list)
    handover_method: HandoverMethodRender | None = None
    restart_failures: list[RestartFailure] = Field(default_factory=list)
    cited_card_ids: list[str] = Field(default_factory=list)
    answer: str = ""
    validation_errors: list[str] = Field(default_factory=list)
    unverified_card_ids: list[str] = Field(default_factory=list)
    card_metadata: dict[str, CardMetadata] = Field(default_factory=dict)
    review_queue: bool = False
    no_knowledge: bool = False


def build_response(
    mode: str,
    request: QueryRequest | HandoverRequest,
    tool_results: dict[str, Any],
    model_output: Any = None,
    model_error: str | None = None,
) -> AgentResponse:
    """
    Build AgentResponse from retrieved cards and a validated model result.
    """
    resp = AgentResponse(mode=mode)
    if model_error:
        resp.validation_errors.append(model_error)
        resp.review_queue = True
    elif model_output is not None:
        errors = validate_model_output(model_output, tool_results)
        resp.validation_errors.extend(errors)
        resp.review_queue = bool(errors)
        if not errors:
            resp.answer = model_output["answer"]
            resp.cited_card_ids = list(model_output["cited_card_ids"])

    # Stub: Extract safety cards from tool_results
    cards = tool_results.get("cards", [])
    available_ids = set()

    for card in cards:
        card_id = card.get("card_id")
        if card_id:
            available_ids.add(card_id)
            if card.get("provenance"):
                resp.card_metadata[card_id] = CardMetadata(
                    provenance=card["provenance"],
                    generalization_evidence=card.get("generalization_evidence"),
                    safety_review=card.get("safety_review"),
                )

        # T5/safety cards with safety_flag=True go to safety_notices
        if card.get("safety_flag"):
            type_payload = card.get("type_payload")
            stop_conditions = []
            if type_payload and type_payload.get("steps"):
                stop_conditions = list(dict.fromkeys(
                    condition for step in type_payload["steps"]
                    for condition in step.get("stop_conditions", [])
                ))
            notice = SafetyNotice(
                card_id=card_id or "",
                safety_basis=card.get("safety_basis", ""),
                stop_conditions=stop_conditions,
            )
            resp.safety_notices.append(notice)

        # Preserve warnings without presenting unchecked procedures as applicable.
        if card.get("condition_status") == "unverified":
            if card_id:
                resp.unverified_card_ids.append(card_id)
            continue

        # T3 steps
        type_payload = card.get("type_payload")
        if card.get("tacit_type") == "T3" and type_payload and type_payload.get("steps"):
            for step_dict in type_payload["steps"]:
                step = StepRender(
                    step_id=step_dict.get("step_id", ""),
                    order=step_dict.get("order", 0),
                    action=step_dict.get("action", ""),
                    expected_result=step_dict.get("expected_result", ""),
                    stop_conditions=step_dict.get("stop_conditions", []),
                    verification_step=step_dict.get("verification_step"),
                    rollback_action=step_dict.get("rollback_action"),
                    escalation_target=step_dict.get("escalation_target"),
                    escalation_channel=step_dict.get("escalation_channel"),
                )
                resp.steps.append(step)

        # T4 handover_method
        if card.get("tacit_type") == "T4" and type_payload and type_payload.get("handover_method"):
            hm_dict = type_payload["handover_method"]
            resp.handover_method = HandoverMethodRender(
                required_context=hm_dict.get("required_context", []),
                recipient_role=hm_dict.get("recipient_role", ""),
                timing=hm_dict.get("timing", ""),
                channel=hm_dict.get("channel", ""),
                acknowledgement=hm_dict.get("acknowledgement", ""),
            )

        # T6 / tried_and_failed
        if type_payload and type_payload.get("tried_and_failed"):
            for attempt_dict in type_payload["tried_and_failed"]:
                attempt = RestartFailure(
                    attempt_id=attempt_dict.get("attempt_id", ""),
                    restart_type=attempt_dict.get("restart_type", "unknown"),
                    action=attempt_dict.get("action", ""),
                    observed_result=attempt_dict.get("observed_result", ""),
                    failure_reason=attempt_dict.get("failure_reason"),
                    evidence_gap=attempt_dict.get("evidence_gap"),
                    next_observations=attempt_dict.get("next_observations", []),
                    required_data=attempt_dict.get("required_data", []),
                    data_collection_role=attempt_dict.get("data_collection_role"),
                )
                resp.restart_failures.append(attempt)

    if model_output is None and model_error is None:
        # Preserve the helper's legacy behavior for callers that build a
        # card-only response outside the model pipeline.
        resp.cited_card_ids = sorted(available_ids)
    return resp


def validate_model_output(model_output: Any, tool_results: dict[str, Any]) -> list[str]:
    """Validate the adapter's strict answer and citation contract."""
    if not isinstance(model_output, dict):
        return ["모델 출력은 객체여야 합니다."]
    if set(model_output) != {"answer", "cited_card_ids"}:
        return ["모델 출력에는 answer와 cited_card_ids만 있어야 합니다."]
    answer = model_output["answer"]
    cited_ids = model_output["cited_card_ids"]
    errors = []
    if not isinstance(answer, str) or not answer.strip():
        errors.append("answer는 비어 있지 않은 문자열이어야 합니다.")
    if not isinstance(cited_ids, list) or any(not isinstance(value, str) for value in cited_ids):
        errors.append("cited_card_ids는 문자열 목록이어야 합니다.")
        return errors
    if len(cited_ids) != len(set(cited_ids)):
        errors.append("인용 카드 ID가 중복되었습니다.")
    if not cited_ids:
        errors.append("답변에 유효한 카드 인용이 없습니다.")
    available_ids = {
        card.get("card_id") for card in tool_results.get("cards", [])
        if isinstance(card, dict) and card.get("card_id")
    }
    for card_id in cited_ids:
        if not re.fullmatch(r"K-\d{4}", card_id):
            errors.append(f"잘못된 카드 ID 형식: {card_id}")
        if card_id not in available_ids:
            errors.append(f"이번 검색 결과에 없는 카드 ID 인용: {card_id}")
    return errors


def render_response(resp: AgentResponse) -> str:
    """
    Render AgentResponse to deterministic text output (D-26~29 §4.3 contract).

    Order: Safety notices (top) → Steps (T3 order order) → T4 handover method →
    Restart failures (by restart_type, unknown preserved) → Citations.
    """
    lines = []

    if resp.no_knowledge:
        lines.append("해당 지식 없음: 현재 검색 결과에 적용 가능한 지식카드가 없어 답변을 보류합니다.")

    # Safety notices (always first)
    if resp.safety_notices:
        lines.append("## 안전 공지")
        for notice in resp.safety_notices:
            lines.append(f"- 카드: {notice.card_id}")
            lines.append(f"  근거: {notice.safety_basis}")
            if notice.stop_conditions:
                lines.append(f"  중단 조건: {'; '.join(notice.stop_conditions)}")

    if resp.unverified_card_ids:
        lines.append("\n## 조건 미확인")
        lines.append("- 적용·제외 조건을 확인할 수 없어 조치 제안을 보류합니다. 안전 공지는 참고 경고로 유지합니다.")
        lines.append(f"- 확인 대상 카드: {', '.join(resp.unverified_card_ids)}")

    if resp.answer and not resp.review_queue and resp.cited_card_ids:
        lines.append("\n## 답변")
        lines.append(resp.answer)

    # Steps (in order)
    if resp.steps:
        lines.append("")
        lines.append("## 조치 단계")
        # Sort by order to preserve T3 sequence
        sorted_steps = sorted(resp.steps, key=lambda s: s.order)
        for step in sorted_steps:
            lines.append(f"### {step.step_id} (단계 {step.order})")
            lines.append(f"- 조치: {step.action}")
            lines.append(f"- 예상 결과: {step.expected_result}")
            if step.stop_conditions:
                lines.append(f"- 중단 조건: {'; '.join(step.stop_conditions)}")
            for label, value in (
                ("결과 확인", step.verification_step), ("복구 조치", step.rollback_action),
                ("보고 대상", step.escalation_target), ("보고 채널", step.escalation_channel),
            ):
                if value:
                    lines.append(f"- {label}: {value}")

    # Handover method (T4)
    if resp.handover_method:
        lines.append("")
        lines.append("## 인계 방법 (T4)")
        hm = resp.handover_method
        lines.append(f"- 대상: {hm.recipient_role}")
        lines.append(f"- 시점: {hm.timing}")
        lines.append(f"- 방법: {hm.channel}")
        lines.append(f"- 확인: {hm.acknowledgement}")
        if hm.required_context:
            lines.append(f"- 전달 정보: {'; '.join(hm.required_context)}")

    # Restart failures (grouped by restart_type, unknown last)
    if resp.restart_failures:
        lines.append("")
        lines.append("## 재가동 실패 이력")
        # Group by restart_type, unknown last
        by_type = {}
        unknown_attempts = []
        for attempt in resp.restart_failures:
            if attempt.restart_type == "unknown":
                unknown_attempts.append(attempt)
            else:
                if attempt.restart_type not in by_type:
                    by_type[attempt.restart_type] = []
                by_type[attempt.restart_type].append(attempt)

        for rt_key in sorted(by_type.keys()):
            lines.append(f"### {rt_key}")
            for attempt in by_type[rt_key]:
                lines.append(f"- {attempt.attempt_id}: {attempt.action}")
                lines.append(f"  결과: {attempt.observed_result}")
                if attempt.failure_reason is not None:
                    lines.append(f"  이유: {attempt.failure_reason}")
                else:
                    lines.append(f"  이유: 미상")
                lines.extend(_render_evidence_gap(attempt))

        if unknown_attempts:
            lines.append("### unknown")
            for attempt in unknown_attempts:
                lines.append(f"- {attempt.attempt_id}: {attempt.action}")
                lines.append(f"  결과: {attempt.observed_result}")
                if attempt.failure_reason is not None:
                    lines.append(f"  이유: {attempt.failure_reason}")
                else:
                    lines.append(f"  이유: 미상")
                lines.extend(_render_evidence_gap(attempt))

    # Citations
    if resp.cited_card_ids:
        lines.append("")
        lines.append(f"## 참고 카드: {', '.join(resp.cited_card_ids)}")
        for card_id, metadata in resp.card_metadata.items():
            for source in metadata.provenance.sources:
                location = f" ({source.locator})" if source.locator else ""
                version = f" / 문서 버전 {source.document_version}" if source.document_version else ""
                lines.append(f"- {card_id} 출처: {source.source_id}{location}{version}")
            if metadata.generalization_evidence:
                evidence = metadata.generalization_evidence
                for label, value in (
                    ("적용 범위", evidence.generalization_scope),
                    ("신뢰도 근거", evidence.confidence_basis),
                    ("지지 사건", ', '.join(evidence.supporting_event_ids)),
                    ("반대 사건", ', '.join(evidence.contradicting_event_ids)),
                ):
                    if value:
                        lines.append(f"- {card_id} {label}: {value}")
            if metadata.safety_review:
                review = metadata.safety_review
                lines.append(f"- {card_id} 안전 검토 기록: {review.status}")
                if review.valid_until:
                    lines.append(f"  기록된 유효기한: {review.valid_until.isoformat()}")
                if review.review_triggers:
                    lines.append(f"  재검토 조건: {'; '.join(review.review_triggers)}")

    if resp.review_queue:
        lines.append("")
        lines.append("⚠️ 이 응답은 검증 실패로 review_queue에 대기 중입니다.")
        if resp.validation_errors:
            lines.extend(f"- {error}" for error in resp.validation_errors)

    return "\n".join(lines)


def _render_evidence_gap(attempt: RestartFailure) -> list[str]:
    lines = []
    for label, value in (
        ("근거 부족 유형", attempt.evidence_gap),
        ("다음 관찰 항목", '; '.join(attempt.next_observations)),
        ("필요 자료", '; '.join(attempt.required_data)),
        ("자료 수집 담당", attempt.data_collection_role),
    ):
        if value:
            lines.append(f"  {label}: {value}")
    return lines


def validate_response(
    resp: AgentResponse,
    tool_results: dict[str, Any],
) -> list[str]:
    """
    Validate response invariants (D-26~29 §4.3).

    Returns list of error messages (empty if valid):
    1. Cited IDs must exist in tool_results.
    2. No missing safety cards (safety_flag=True cards must appear in safety_notices).
    3. Steps preserve T3 order (order field strictly ascending).
    4. No lost stop_conditions (from T3 steps and safety cards).
    """
    errors = []
    available_card_ids = set()
    all_cards = tool_results.get("cards", [])

    for card in all_cards:
        card_id = card.get("card_id")
        if card_id:
            available_card_ids.add(card_id)

    # 1. Check cited IDs exist
    for cited_id in resp.cited_card_ids:
        if cited_id not in available_card_ids:
            errors.append(f"Cited card {cited_id} not found in tool_results")

    # 2. Check no missing safety cards
    safety_card_ids_in_results = {
        c.get("card_id") for c in all_cards if c.get("safety_flag")
    }
    cited_safety_ids = {n.card_id for n in resp.safety_notices}
    missing_safety = safety_card_ids_in_results - cited_safety_ids
    if missing_safety:
        errors.append(f"Missing safety cards in notices: {missing_safety}")

    # 3. Check steps order preservation
    if resp.steps:
        orders = [s.order for s in resp.steps]
        if orders != sorted(orders):
            errors.append(f"Steps not in ascending order: {orders}")

    # 4. Check stop_conditions not lost
    expected_stop_conds = set()
    for card in all_cards:
        if (card.get("tacit_type") == "T3"
                and (card.get("condition_status") != "unverified" or card.get("safety_flag"))
                and (card.get("type_payload") or {}).get("steps")):
            for step in card["type_payload"]["steps"]:
                for cond in step.get("stop_conditions", []):
                    expected_stop_conds.add(cond)
        if card.get("safety_flag"):
            for cond in card.get("stop_conditions", []):
                expected_stop_conds.add(cond)

    rendered_stop_conds = set()
    for step in resp.steps:
        rendered_stop_conds.update(step.stop_conditions)
    for notice in resp.safety_notices:
        rendered_stop_conds.update(notice.stop_conditions)

    lost_conds = expected_stop_conds - rendered_stop_conds
    if lost_conds:
        errors.append(f"Lost stop_conditions: {lost_conds}")

    return errors
