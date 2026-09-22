"""Agent response building and rendering (D-26~29 §4.3).

Contracts implemented here (통합본 v1.1 §3.1·§3.3·§3.4·§4.8·§4.10, 계약 §4.3):
- safety_notices lead the response and come from code, never from the model
  ranking (D-26). A safety card without safety_basis is a validation error.
- Every cited card is rendered with its grade label ("L1 합성·시뮬레이션 검증")
  and the response always carries the "실제 작업지시 아님" notice (4.10).
- Citations are checked against the retrieval result. When the model cites only
  unknown ids the answer is replaced with "해당 지식 없음" (3.3, 4.8 코드 검증).
- T3 steps keep their order per card and are never interleaved across cards;
  stop_conditions are never shortened or dropped (D-28, §2.2).
- T4 handover methods are kept per card — a second T4 card does not overwrite
  the first (D-27).
- Restart failures keep restart_type grouping, unknown, evidence ids and a
  None failure_reason as "미상" (D-29).
- Handover items are rendered as 등록 후보 only; nothing is stored (3.4 F-04).
"""

from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, computed_field

from shiftlink.agent.router import HandoverRequest, QueryRequest

# 4.10 등급·상태 체계. MVP에서 인용 가능한 최고 등급은 L1이다.
GRADE_LABELS: dict[str, str] = {
    "L0": "L0 합성 가설(검증 전)",
    "L1": "L1 합성·시뮬레이션 검증",
    "L2": "L2 전문가 승인",
    "L3": "L3 현장 검증",
}
UNKNOWN_GRADE_LABEL = "등급 미표기"

# 4.10: 데모 화면에 상시 표시.
DISCLAIMER = (
    "실제 작업지시 아님 — 합성 지식 기반 보조 응답입니다. "
    "안전·품질·설비 정지 판단은 승인된 표준절차와 책임자를 따릅니다."
)

NO_KNOWLEDGE_TEXT = (
    "적용 가능한 근거 카드가 없어 답변을 보류합니다. 승인된 절차와 담당자 확인을 우선하세요."
)

# Only these come from the model's own output, so only these can be fixed by
# the single retry (§4.3). Data-side findings go straight to the review queue —
# re-running inference cannot change a deterministic card-derived block.
MODEL_ATTRIBUTABLE_CODES = frozenset({"cited_card_unknown", "handover_candidate_unknown_card"})


class CardCitation(BaseModel):
    """One cited card with the grade the answer must display (4.10)."""

    card_id: str
    title: str = ""
    tacit_type: str = ""
    grade: str = ""
    grade_label: str = UNKNOWN_GRADE_LABEL
    safety_flag: bool = False
    condition_status: str | None = None


class SafetyNotice(BaseModel):
    """Safety card notice (card_id, safety_basis, stop_conditions)."""
    card_id: str
    safety_basis: str
    stop_conditions: list[str] = Field(default_factory=list)
    condition_status: str | None = None


class StepRender(BaseModel):
    """Resolution step in order. card_id keeps steps of different cards apart."""
    step_id: str
    order: int
    action: str
    expected_result: str
    stop_conditions: list[str] = Field(default_factory=list)
    card_id: str = ""


class HandoverMethodRender(BaseModel):
    """T4 handover method (5 elements)."""
    required_context: list[str] = Field(min_length=1)
    recipient_role: str
    timing: str
    channel: str
    acknowledgement: str
    card_id: str = ""


class RestartFailure(BaseModel):
    """Single restart failure attempt."""
    attempt_id: str
    restart_type: str  # "normal_stop_restart", "abnormal_stop_restart", "maintenance_restart", "unknown"
    action: str
    observed_result: str
    failure_reason: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    card_id: str = ""


class HandoverCandidate(BaseModel):
    """
    Proposed handover item (3.4 F-04). Candidates are never stored here — the
    status stays "proposed" until a user accepts it.
    """

    text: str
    card_ids: list[str] = Field(default_factory=list)
    status: Literal["proposed"] = "proposed"


class AgentResponse(BaseModel):
    """Structured response output (D-26~29 §4.3)."""
    model_config = ConfigDict(use_enum_values=True)

    mode: str  # "query" or "handover"
    answer: str | None = None
    safety_notices: list[SafetyNotice] = Field(default_factory=list)
    steps: list[StepRender] = Field(default_factory=list)
    handover_methods: list[HandoverMethodRender] = Field(default_factory=list)
    handover_candidates: list[HandoverCandidate] = Field(default_factory=list)
    restart_failures: list[RestartFailure] = Field(default_factory=list)
    cards: list[CardCitation] = Field(default_factory=list)
    cited_card_ids: list[str] = Field(default_factory=list)
    # Ids the model cited that retrieval never returned (4.8 코드 검증).
    dropped_citations: list[str] = Field(default_factory=list)
    # No applicable card: the answer is withheld instead of generated
    # (3.3, 4.9 지식 없음 처리, 4.12).
    no_knowledge: bool = False
    review_queue: bool = False
    # Why it was queued — a review-queue entry without a reason is not auditable.
    validation_errors: list[str] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def handover_method(self) -> HandoverMethodRender | None:
        """First T4 method. Kept for the §4.3 field name; see handover_methods."""
        return self.handover_methods[0] if self.handover_methods else None


def build_response(
    mode: str,
    request: QueryRequest | HandoverRequest,
    tool_results: dict[str, Any],
    model_output: dict[str, Any] | None = None,
) -> AgentResponse:
    """
    Build AgentResponse from the retrieval result and the single model call.

    Card-derived content (safety notices, steps, handover methods, restart
    failures, grades) is produced by code so the model cannot reorder or drop
    it. Only the answer text, the citations and the handover candidates come
    from ``model_output``; citations are filtered against what retrieval
    actually returned.
    """
    resp = AgentResponse(mode=mode)
    cards = tool_results.get("cards", []) or []

    retrieved_ids: list[str] = []
    for card in cards:
        card_id = card.get("card_id")
        if not card_id:
            continue
        retrieved_ids.append(card_id)
        type_payload = card.get("type_payload") or {}
        steps = type_payload.get("steps") or []

        resp.cards.append(
            CardCitation(
                card_id=card_id,
                title=card.get("title", ""),
                tacit_type=card.get("tacit_type", ""),
                grade=card.get("grade", ""),
                grade_label=GRADE_LABELS.get(card.get("grade", ""), UNKNOWN_GRADE_LABEL),
                safety_flag=bool(card.get("safety_flag")),
                condition_status=card.get("condition_status"),
            )
        )

        # D-26: every safety_flag=True card is exposed, with all stop conditions
        # it carries — not just the first step's.
        if card.get("safety_flag"):
            resp.safety_notices.append(
                SafetyNotice(
                    card_id=card_id,
                    safety_basis=card.get("safety_basis") or "",
                    stop_conditions=_collect_stop_conditions(steps),
                    condition_status=card.get("condition_status"),
                )
            )

        # D-28: T3 steps, order preserved, attributed to their card.
        if card.get("tacit_type") == "T3" and steps:
            for step_dict in steps:
                resp.steps.append(
                    StepRender(
                        step_id=step_dict.get("step_id", ""),
                        order=step_dict.get("order", 0),
                        action=step_dict.get("action", ""),
                        expected_result=step_dict.get("expected_result", ""),
                        stop_conditions=list(step_dict.get("stop_conditions", []) or []),
                        card_id=card_id,
                    )
                )

        # D-27: one entry per T4 card; a later card never overwrites an earlier one.
        if card.get("tacit_type") == "T4" and type_payload.get("handover_method"):
            hm_dict = type_payload["handover_method"]
            resp.handover_methods.append(
                HandoverMethodRender(
                    required_context=hm_dict.get("required_context", []),
                    recipient_role=hm_dict.get("recipient_role", ""),
                    timing=hm_dict.get("timing", ""),
                    channel=hm_dict.get("channel", ""),
                    acknowledgement=hm_dict.get("acknowledgement", ""),
                    card_id=card_id,
                )
            )

        # D-29: attempts keep their type, evidence and an unknown failure reason.
        for attempt_dict in type_payload.get("tried_and_failed") or []:
            resp.restart_failures.append(
                RestartFailure(
                    attempt_id=attempt_dict.get("attempt_id", ""),
                    restart_type=attempt_dict.get("restart_type", "unknown"),
                    action=attempt_dict.get("action", ""),
                    observed_result=attempt_dict.get("observed_result", ""),
                    failure_reason=attempt_dict.get("failure_reason"),
                    evidence_ids=list(attempt_dict.get("evidence_ids", []) or []),
                    card_id=card_id,
                )
            )

    _apply_model_output(resp, mode, model_output, retrieved_ids)
    return resp


def _collect_stop_conditions(steps: list[dict[str, Any]]) -> list[str]:
    """All stop conditions of a card, in step order, without duplicates."""
    collected: list[str] = []
    for step in steps:
        for condition in step.get("stop_conditions", []) or []:
            if condition not in collected:
                collected.append(condition)
    return collected


def _apply_model_output(
    resp: AgentResponse,
    mode: str,
    model_output: Mapping[str, Any] | None,
    retrieved_ids: list[str],
) -> None:
    """Take the answer, citations and handover candidates from the model call."""
    available = set(retrieved_ids)
    raw_citations = model_output.get("cited_card_ids") if isinstance(model_output, Mapping) else None

    if raw_citations is None:
        # The model produced no structured citation (deterministic stub or a
        # legacy caller): fall back to what retrieval returned, so the
        # rendered evidence still matches the result set.
        resp.cited_card_ids = sorted(available)
    else:
        cited = {cid for cid in raw_citations if cid in available}
        resp.cited_card_ids = sorted(cited)
        resp.dropped_citations = sorted({cid for cid in raw_citations if cid not in available})

    if isinstance(model_output, Mapping):
        answer = model_output.get("answer")
        if isinstance(answer, str) and answer.strip():
            resp.answer = answer
        for raw in model_output.get("handover_candidates") or []:
            if not isinstance(raw, Mapping):
                continue
            text = raw.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            resp.handover_candidates.append(
                HandoverCandidate(text=text, card_ids=list(raw.get("card_ids") or []))
            )

    # 3.3 / 4.8: no grounding left means the answer is replaced, not generated.
    if mode == "query" and not resp.cited_card_ids:
        resp.no_knowledge = True
        resp.answer = None


def render_response(resp: AgentResponse) -> str:
    """
    Render AgentResponse to deterministic text output (D-26~29 §4.3 contract).

    Order: 지식 없음 → 안전 공지(선두 고정) → T3 단계(카드별 order 보존) →
    T4 인계 방법 → 재가동 실패(restart_type 그룹, unknown 마지막) →
    인계 후보 → 답변 → 인용 카드(등급 표기) → 상시 고지.
    """
    lines: list[str] = []

    if resp.no_knowledge:
        lines.append("## 해당 지식 없음")
        lines.append(f"- {NO_KNOWLEDGE_TEXT}")
        if resp.dropped_citations:
            lines.append(f"- 검색 결과에 없는 인용 ID: {', '.join(resp.dropped_citations)}")

    # Safety notices (always first)
    if resp.safety_notices:
        lines.append("")
        lines.append("## 안전 공지")
        for notice in resp.safety_notices:
            lines.append(f"- 카드: {notice.card_id}")
            lines.append(f"  근거: {notice.safety_basis or '근거 미기재 — 검토 필요'}")
            if notice.condition_status == "unverified":
                lines.append("  조건: 미확인(관측값 없음) — 보수적으로 노출")
            if notice.stop_conditions:
                lines.append(f"  중단 조건: {'; '.join(notice.stop_conditions)}")

    # Steps, grouped per card so two T3 cards never interleave.
    if resp.steps:
        lines.append("")
        lines.append("## 조치 단계")
        for card_id, steps in _group_steps(resp.steps):
            if card_id:
                lines.append(f"**카드 {card_id}**")
            for step in steps:
                lines.append(f"### {step.step_id} (단계 {step.order})")
                lines.append(f"- 조치: {step.action}")
                lines.append(f"- 예상 결과: {step.expected_result}")
                if step.stop_conditions:
                    lines.append(f"- 중단 조건: {'; '.join(step.stop_conditions)}")

    # Handover methods (T4), one block per card.
    if resp.handover_methods:
        lines.append("")
        lines.append("## 인계 방법 (T4)")
        for hm in resp.handover_methods:
            if hm.card_id:
                lines.append(f"**카드 {hm.card_id}**")
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
        known = sorted({a.restart_type for a in resp.restart_failures if a.restart_type != "unknown"})
        for restart_type in known:
            lines.append(f"### {restart_type}")
            lines.extend(_render_attempts(a for a in resp.restart_failures if a.restart_type == restart_type))
        unknown = [a for a in resp.restart_failures if a.restart_type == "unknown"]
        if unknown:
            lines.append("### unknown")
            lines.extend(_render_attempts(unknown))

    # Handover candidates: proposals only, never stored (3.4 F-04).
    if resp.handover_candidates:
        lines.append("")
        lines.append("## 인계 등록 후보 (수락 전, 저장되지 않음)")
        for candidate in resp.handover_candidates:
            lines.append(f"- {candidate.text}")
            if candidate.card_ids:
                lines.append(f"  근거 카드: {', '.join(candidate.card_ids)}")

    if resp.answer:
        lines.append("")
        lines.append("## 답변")
        lines.append(resp.answer)

    # Citations with grade labels (4.10).
    if resp.cited_card_ids:
        lines.append("")
        lines.append("## 참고 카드")
        by_id = {card.card_id: card for card in resp.cards}
        for card_id in resp.cited_card_ids:
            card = by_id.get(card_id)
            label = card.grade_label if card else UNKNOWN_GRADE_LABEL
            title = f" — {card.title}" if card and card.title else ""
            lines.append(f"- {card_id} [{label}]{title}")

    if resp.review_queue:
        lines.append("")
        lines.append("⚠️ 이 응답은 검증 실패로 review_queue에 대기 중입니다.")

    lines.append("")
    lines.append(f"> {DISCLAIMER}")

    return "\n".join(lines).lstrip("\n")


def _group_steps(steps: list[StepRender]) -> list[tuple[str, list[StepRender]]]:
    """Group steps by card, keeping first-seen card order and the given step order."""
    grouped: dict[str, list[StepRender]] = {}
    for step in steps:
        grouped.setdefault(step.card_id, []).append(step)
    return list(grouped.items())


def _render_attempts(attempts: Any) -> list[str]:
    lines: list[str] = []
    for attempt in attempts:
        lines.append(f"- {attempt.attempt_id}: {attempt.action}")
        lines.append(f"  결과: {attempt.observed_result}")
        # None stays "미상"; the data itself is never filled in.
        lines.append(f"  이유: {attempt.failure_reason if attempt.failure_reason is not None else '미상'}")
        if attempt.evidence_ids:
            lines.append(f"  근거: {', '.join(attempt.evidence_ids)}")
    return lines


def validate_response(
    resp: AgentResponse,
    tool_results: dict[str, Any],
) -> list[str]:
    """
    Validate response invariants (D-26~29 §4.3).

    Returns "[code] message" strings (empty when valid):
    - cited_card_unknown: a cited id is not in the retrieval result.
    - safety_notice_missing / safety_basis_missing: D-26 exposure and basis.
    - steps_out_of_order / steps_duplicated: D-28 order preserved per card.
    - stop_conditions_lost: D-28·§2.2 stop conditions never dropped.
    - handover_method_lost: a retrieved T4 method missing from the response.
    - handover_candidate_unknown_card: a candidate cites a card that was never
      retrieved (4.9 근거 없는 조치 0건).
    - grade_label_missing: a cited card rendered without its 4.10 grade.
    """
    errors: list[str] = []
    all_cards = tool_results.get("cards", []) or []
    available_card_ids = {c.get("card_id") for c in all_cards if c.get("card_id")}

    # 1. Cited ids must exist in the retrieval result.
    for cited_id in resp.cited_card_ids:
        if cited_id not in available_card_ids:
            errors.append(f"[cited_card_unknown] Cited card {cited_id} not found in tool_results")

    # 2. Every retrieved safety card must be exposed, with a basis (D-26).
    safety_card_ids_in_results = {c.get("card_id") for c in all_cards if c.get("safety_flag")}
    cited_safety_ids = {n.card_id for n in resp.safety_notices}
    missing_safety = safety_card_ids_in_results - cited_safety_ids
    if missing_safety:
        errors.append(f"[safety_notice_missing] Missing safety cards in notices: {missing_safety}")
    for notice in resp.safety_notices:
        if not notice.safety_basis.strip():
            errors.append(
                f"[safety_basis_missing] Safety card {notice.card_id} has no safety_basis"
            )

    # 3. Step order is preserved per card and step ids are not duplicated.
    for card_id, steps in _group_steps(resp.steps):
        orders = [s.order for s in steps]
        if orders != sorted(orders):
            errors.append(
                f"[steps_out_of_order] Steps for {card_id or 'unknown card'} "
                f"not in ascending order: {orders}"
            )
        step_ids = [s.step_id for s in steps]
        if len(step_ids) != len(set(step_ids)):
            errors.append(f"[steps_duplicated] Duplicate step ids for {card_id or 'unknown card'}")

    # 4. Stop conditions are never dropped or shortened (§2.2).
    expected_stop_conds: set[str] = set()
    for card in all_cards:
        steps = (card.get("type_payload") or {}).get("steps") or []
        expected_stop_conds.update(_collect_stop_conditions(steps))
    rendered_stop_conds: set[str] = set()
    for step in resp.steps:
        rendered_stop_conds.update(step.stop_conditions)
    for notice in resp.safety_notices:
        rendered_stop_conds.update(notice.stop_conditions)
    lost_conds = expected_stop_conds - rendered_stop_conds
    if lost_conds:
        errors.append(f"[stop_conditions_lost] Lost stop_conditions: {lost_conds}")

    # 5. A retrieved T4 method must not disappear (D-27).
    expected_t4 = {
        c.get("card_id")
        for c in all_cards
        if c.get("tacit_type") == "T4" and (c.get("type_payload") or {}).get("handover_method")
    }
    rendered_t4 = {hm.card_id for hm in resp.handover_methods}
    lost_t4 = expected_t4 - rendered_t4
    if lost_t4:
        errors.append(f"[handover_method_lost] Missing T4 handover methods: {lost_t4}")

    # 6. Handover candidates may only cite retrieved cards (4.9).
    for candidate in resp.handover_candidates:
        unknown = [cid for cid in candidate.card_ids if cid not in available_card_ids]
        if unknown:
            errors.append(
                f"[handover_candidate_unknown_card] Handover candidate cites unknown cards: {unknown}"
            )

    # 7. Every cited card carries its grade label (4.10).
    labelled = {c.card_id for c in resp.cards if c.grade_label != UNKNOWN_GRADE_LABEL}
    unlabelled = [cid for cid in resp.cited_card_ids if cid not in labelled]
    if unlabelled:
        errors.append(f"[grade_label_missing] Cited cards without a grade label: {unlabelled}")

    return errors


def is_model_retryable(errors: list[str]) -> bool:
    """
    True when at least one finding is the model's own (§4.3 재시도 1회).

    Data-side findings (missing safety_basis, lost stop_conditions, ...) are not
    retried: the blocks are built deterministically from the retrieval result,
    so a second inference call would produce the same response.
    """
    return any(f"[{code}]" in error for error in errors for code in MODEL_ATTRIBUTABLE_CODES)
