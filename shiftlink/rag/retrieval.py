"""In-memory tool provider for knowledge cards retrieval."""

import re
from copy import deepcopy
from typing import Any

from shiftlink.agent.schemas import Condition, KnowledgeCard


GENERATION_PROMPT_TEMPLATE = """## 카드 생성 규칙 (D-26~29)

당신은 제조 현장 문제해결 지식을 카드 형식으로 생성하는 에이전트입니다. 다음 규칙을 엄격히 준수하세요.

### 공통 규칙
1. 안전 근거: safety_flag=True인 카드는 반드시 safety_basis(한국어 근거 텍스트)를 포함해야 합니다.
2. 미상 유지: 원인, 실패 이유, 재가동 유형 등이 명확하지 않으면 "미상" 문자열 자동 기입 금지. 필드를 None 또는 "unknown" 값으로 유지합니다.
3. 창작 금지: 근거 없이 단계, 인계 방법, 실패 이유를 만들지 마세요.

### T3 (단계)
- type_payload.steps 필수: order는 1부터 시작, 오름차순, 중복 없음.
- 각 단계: step_id(ST-001 형식), action(구체적 조치), expected_result(예상 결과).
- stop_conditions: 단계 중단 조건 목록 (길이 제한·요약 금지).

### T4 (인계)
- type_payload.handover_method 필수: 5개 필드 모두 기입.
  - required_context: 인계할 정보 목록 (최소 1개).
  - recipient_role: 대상 역할.
  - timing: 인계 시점.
  - channel: 인계 방법.
  - acknowledgement: 확인 방법.

### T6 (재가동)
- type_payload.restart_type 필수: "normal_stop_restart", "abnormal_stop_restart", "maintenance_restart" 중 택일.
- known 유형으로 명확할 때만 지정; 미상은 "unknown".

### 시도·실패 (tried_and_failed)
- 각 시도: attempt_id(AT-0001 형식), restart_type, action, observed_result.
- failure_reason: 알려진 이유만 기입, 미상은 None 유지.
- 카드의 restart_type과 attempt.restart_type 일치 또는 둘 다 unknown만 허용.

### 조건 (conditions, exclusions)
- signal: 측정 신호 이름.
- op: ==, !=, >, >=, <, <= 중 택일.
- value: 비교 대상값.
- unit: 선택사항.
"""


def _evaluate_condition(cond: Condition, observations: dict[str, Any] | None) -> bool | None:
    """
    Evaluate a condition against observations.
    Returns: True if condition is met, False if not met, None if unverifiable (signal missing).

    Single source of truth is Condition.evaluate (schemas.py) so the pipeline
    applies the same §4.2 rule to the merged card list.
    """
    return cond.evaluate(observations)


def _calculate_token_overlap(query: str, text: str) -> int:
    """Deterministic token overlap score (word-level)."""
    query_tokens = set(re.findall(r'\w+', query.lower()))
    text_tokens = set(re.findall(r'\w+', text.lower()))
    return len(query_tokens & text_tokens)


def check_card_rules(card: KnowledgeCard) -> list[str]:
    """Check P5 deterministic validation rules. Return list of error messages (empty if valid)."""
    errors = []

    # Schema re-validation (should pass since Pydantic validated at load time)
    try:
        _ = KnowledgeCard.model_validate(card.model_dump())
    except Exception as e:
        errors.append(f"Schema validation failed: {str(e)}")
        return errors

    # Check for duplicate card_ids if needed (within KB context)
    # Note: Single card validation does not detect duplicates; call from batch context.

    # T3: steps order strictly ascending
    if card.tacit_type == "T3" and card.type_payload and card.type_payload.steps:
        orders = [s.order for s in card.type_payload.steps]
        if orders != sorted(orders):
            errors.append(f"T3 steps not in ascending order: {orders}")

    # T4: handover_method required
    if card.tacit_type == "T4":
        if not card.type_payload or not card.type_payload.handover_method:
            errors.append("T4 missing handover_method")

    # T6: restart_type required
    if card.tacit_type == "T6":
        if not card.type_payload or not card.type_payload.restart_type:
            errors.append("T6 missing restart_type")

    # safety_flag: safety_basis required
    if card.safety_flag and not card.safety_basis:
        errors.append("safety_flag cards require safety_basis")

    return errors


class InMemoryToolProvider:
    """In-memory knowledge card storage implementing ToolProvider protocol."""

    def __init__(
        self,
        cards: list[KnowledgeCard] | None = None,
        equipment_db: list[dict[str, Any]] | None = None,
        handover_db: list[dict[str, Any]] | None = None,
        checklist_db: list[dict[str, Any]] | None = None,
    ) -> None:
        """
        Initialize with KB cards and optional equipment/handover/checklist data.

        Args:
            cards: List of KnowledgeCard objects to load. Only accepted/kb/L1 cards are loaded.
            equipment_db: Optional equipment metadata.
            handover_db: Optional existing handovers.
            checklist_db: Optional checklists.

        Raises:
            ValueError: If dev or sealed cards are mixed in (gate enforcement).
        """
        self.cards: list[KnowledgeCard] = []
        if cards:
            for card in cards:
                if card.split in ("dev", "sealed"):
                    raise ValueError(
                        f"InMemoryToolProvider does not accept dev/sealed cards: {card.card_id}"
                    )
                # Gate: only accept accepted/kb/L1
                if card.status == "accepted" and card.split == "kb" and card.grade == "L1":
                    self.cards.append(card)

        self.equipment_db = equipment_db or []
        self.handover_db = handover_db or []
        self.checklist_db = checklist_db or []

    def lookup_equipment(self, *, equipment_ids: list[str]) -> list[dict[str, Any]]:
        """Return equipment metadata. Rows are copies — tools are read only."""
        results = []
        for eq_id in equipment_ids:
            eq = next(
                (e for e in self.equipment_db if e.get("equipment_id") == eq_id),
                None,
            )
            if eq:
                results.append(deepcopy(eq))
        return results

    def search_cards(
        self,
        *,
        query: str,
        equipment_ids: list[str],
        k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Search cards by query with equipment filter and condition matching.

        Returns top-k results (deterministic ranking by token overlap, then card_id).
        """
        # Equipment filter: card.equipment in equipment_ids or card.equipment == "COMMON"
        candidate_cards = [
            c for c in self.cards
            if c.equipment in equipment_ids or c.equipment == "COMMON"
        ]

        # Condition matching: exclude cards with False or True (exclusion) conditions.
        filtered_cards = []
        for card in candidate_cards:
            include = True
            condition_status = "verified"

            # Check conditions
            for cond in card.conditions:
                result = _evaluate_condition(cond, None)
                if result is False:
                    include = False
                    break
                elif result is None:
                    condition_status = "unverified"

            # Check exclusions
            if include:
                for excl in card.exclusions:
                    result = _evaluate_condition(excl, None)
                    if result is True:  # Exclusion condition is true -> exclude card
                        include = False
                        break
                    elif result is None:
                        condition_status = "unverified"

            if include:
                card_dict = card.model_dump(mode="json")
                if condition_status == "unverified":
                    card_dict["condition_status"] = "unverified"
                filtered_cards.append((card_dict, card.card_id))

        # Sort by token overlap (descending), then by card_id (ascending)
        scored = [
            (card_dict, _calculate_token_overlap(query, card_dict.get("know_how", "")), card_id)
            for card_dict, card_id in filtered_cards
        ]
        scored.sort(key=lambda x: (-x[1], x[2]))

        # Return top-k
        return [card_dict for card_dict, _, _ in scored[:k]]

    def search_safety_cards(
        self,
        *,
        equipment_ids: list[str],
        observations: dict[str, object] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Return all applicable safety cards (safety_flag=True).

        k limit does not apply; all matching safety cards are returned.
        Condition matching follows §4.2 rules.
        """
        # Equipment filter
        candidate_cards = [
            c for c in self.cards
            if c.safety_flag and (c.equipment in equipment_ids or c.equipment == "COMMON")
        ]

        # Condition matching with observations
        results = []
        for card in candidate_cards:
            include = True
            condition_status = "unverified"

            # Check conditions
            for cond in card.conditions:
                result = _evaluate_condition(cond, observations)
                if result is False:
                    include = False
                    break
                elif result is True:
                    condition_status = "verified"

            # Check exclusions
            if include:
                for excl in card.exclusions:
                    result = _evaluate_condition(excl, observations)
                    if result is True:  # Exclusion condition is true -> exclude card
                        include = False
                        break
                    elif result is True:
                        condition_status = "verified"

            if include:
                card_dict = card.model_dump(mode="json")
                card_dict["condition_status"] = condition_status
                results.append(card_dict)

        return results

    def list_handover(
        self, *, equipment_ids: list[str], shift: str | None = None
    ) -> list[dict[str, Any]]:
        """Return existing handover items as copies; nothing is accepted or closed."""
        return [
            deepcopy(h)
            for h in self.handover_db
            if h.get("equipment_id") in equipment_ids
            and (shift is None or h.get("shift") == shift)
        ]

    def propose_handover(self, *, extraction_result: dict[str, Any]) -> list[dict[str, Any]]:
        """Queue handover candidates (stub implementation)."""
        return []

    def get_checklist(self, *, equipment_ids: list[str]) -> list[dict[str, Any]]:
        """Return applicable checklists as copies; completion is never recorded."""
        return [
            deepcopy(c) for c in self.checklist_db if c.get("equipment_id") in equipment_ids
        ]
