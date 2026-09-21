"""Agent response building and rendering (D-26~29 §4.3)."""

from typing import Any, Annotated
from pydantic import BaseModel, Field, ConfigDict
from shiftlink.agent.router import QueryRequest, HandoverRequest


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


class AgentResponse(BaseModel):
    """Structured response output (D-26~29 §4.3)."""
    model_config = ConfigDict(use_enum_values=True)

    mode: str  # "query" or "handover"
    safety_notices: list[SafetyNotice] = Field(default_factory=list)
    steps: list[StepRender] = Field(default_factory=list)
    handover_method: HandoverMethodRender | None = None
    restart_failures: list[RestartFailure] = Field(default_factory=list)
    cited_card_ids: list[str] = Field(default_factory=list)
    review_queue: bool = False


def build_response(
    mode: str,
    request: QueryRequest | HandoverRequest,
    tool_results: dict[str, Any],
    model_output: dict[str, Any] | None = None,
) -> AgentResponse:
    """
    Build AgentResponse from pipeline components.

    Currently a stub that collects tool results. In production, this would parse
    model_output (model response) to populate response fields according to D-26~29 rules.
    """
    resp = AgentResponse(mode=mode)

    # Stub: Extract safety cards from tool_results
    cards = tool_results.get("cards", [])
    cited_ids = set()

    for card in cards:
        card_id = card.get("card_id")
        if card_id:
            cited_ids.add(card_id)

        # T5/safety cards with safety_flag=True go to safety_notices
        if card.get("safety_flag"):
            type_payload = card.get("type_payload")
            stop_conditions = []
            if type_payload and type_payload.get("steps"):
                first_step = type_payload["steps"][0]
                stop_conditions = first_step.get("stop_conditions", [])
            notice = SafetyNotice(
                card_id=card_id or "",
                safety_basis=card.get("safety_basis", ""),
                stop_conditions=stop_conditions,
            )
            resp.safety_notices.append(notice)

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
                )
                resp.restart_failures.append(attempt)

    resp.cited_card_ids = sorted(cited_ids)
    return resp


def render_response(resp: AgentResponse) -> str:
    """
    Render AgentResponse to deterministic text output (D-26~29 §4.3 contract).

    Order: Safety notices (top) → Steps (T3 order order) → T4 handover method →
    Restart failures (by restart_type, unknown preserved) → Citations.
    """
    lines = []

    # Safety notices (always first)
    if resp.safety_notices:
        lines.append("## 안전 공지")
        for notice in resp.safety_notices:
            lines.append(f"- 카드: {notice.card_id}")
            lines.append(f"  근거: {notice.safety_basis}")
            if notice.stop_conditions:
                lines.append(f"  중단 조건: {'; '.join(notice.stop_conditions)}")

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

        if unknown_attempts:
            lines.append("### unknown")
            for attempt in unknown_attempts:
                lines.append(f"- {attempt.attempt_id}: {attempt.action}")
                lines.append(f"  결과: {attempt.observed_result}")
                if attempt.failure_reason is not None:
                    lines.append(f"  이유: {attempt.failure_reason}")
                else:
                    lines.append(f"  이유: 미상")

    # Citations
    if resp.cited_card_ids:
        lines.append("")
        lines.append(f"## 참고 카드: {', '.join(resp.cited_card_ids)}")

    if resp.review_queue:
        lines.append("")
        lines.append("⚠️ 이 응답은 검증 실패로 review_queue에 대기 중입니다.")

    return "\n".join(lines)


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
        if card.get("tacit_type") == "T3" and card.get("type_payload", {}).get("steps"):
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
