"""In-memory tool provider for knowledge cards retrieval."""

from typing import Any, Annotated, get_args
import re
from heapq import nsmallest
from dataclasses import dataclass
from shiftlink.agent.schemas import KnowledgeCard, Condition, Equipment, SCHEMA_VERSION


GENERATION_PROMPT_TEMPLATE = f"""## 카드 생성 규칙 (스키마 v{SCHEMA_VERSION})

당신은 제조 현장 문제해결 지식을 카드 형식으로 생성하는 에이전트입니다. 다음 규칙을 엄격히 준수하세요.

### 공통 규칙
0. KnowledgeCard는 재사용 지식입니다. 사건별 상태는 Event/원문/인계 기록으로 구분합니다.
   신규 초안은 status="draft", grade="L0"로 작성하며 모델이 accepted/L1로 승격하지 않습니다.
   ID·version·split·생성 시각·실행 버전은 입력/실행기가 제공한 값만 사용합니다.
   provenance.schema_version은 실제 구현 버전이며 기존 카드 version을 소급 변경하지 않습니다.
   confidence를 근거 없이 만들지 않습니다. 필수 정보가 부족하면 부족 항목을 보완 대기로 보고하고 유효 카드로 꾸미지 않습니다.
   보완 대기는 별도 검수 기록이며 status에 임의 값을 추가하지 않습니다.
1. 안전 근거: safety_flag=True인 카드는 반드시 safety_basis(한국어 근거 텍스트)를 포함해야 합니다.
2. 미상 유지: failure_reason 등 선택 문자열은 JSON null, 선택 목록은 [] 또는 생략합니다.
   필수값을 null로 대체하지 않습니다. 재가동 유형이 미상이면 "unknown"을 사용합니다.
   symptom·safety_basis는 문자열로 제공하면 공백만일 수 없습니다.
3. 창작 금지: 근거 없이 단계, 인계 방법, 실패 이유를 만들지 마세요.
4. v1.1 선택 메타데이터: 확인된 자료가 있을 때만 추가하며, 모르면 null 또는 빈 목록을 유지합니다.
   - generalization_evidence: supporting_event_ids, contradicting_event_ids, generalization_scope, confidence_basis.
     출처 사건 ID와 지지·반대 관계는 구별하고, 사건 정답 본문을 가져오지 않습니다.
   - provenance.sources: source_id, locator, document_version; extraction_method 및 model/prompt/index/schema_version은 실제 실행 정보만 기록합니다.
   - generalization_evidence의 사건 ID는 EV-숫자 4자리이며 목록 내 중복 및 지지/반대 목록 간 겹침을 금지합니다.
   - safety_review: 사람의 검토 기록만 복사합니다. 카드 status와 별개입니다. 승인 상태·승인자·역할·검토일·유효기한·근거 등급을 추정하거나 자동 승인하지 않습니다.
     status는 draft/pending_review/approved/restricted/expired/withdrawn입니다.
     approved 기록에는 approved_by, approver_role, reviewed_at, valid_until, evidence_grade가 필요합니다.
     날짜는 시간대를 포함하고 valid_until은 reviewed_at 이후여야 합니다. review_triggers와 safety_level은 선택입니다.
     이 기록만으로 승인 권한 확인·자동 만료·KB 채택이 이루어지는 것은 아닙니다.

### 유형 경계 및 T1/T2/T5
- T1: 감각 기반 이상 징후 해석. symptom 필수.
- T2: 조건에 따라 적용할 요령이 달라지는 것이 핵심일 때 선택합니다. conditions 1개 이상 필수. 조건이 단순한 적용 범위라면 원래 유형을 유지합니다.
- T3: 증상에서 원인을 좁히는 확인 절차. symptom 필수.
- T4: 재사용 가능한 인계 방법. 사건 상태 전달문만으로 T4를 만들지 않습니다.
- T5: 금지·중지·격리 자체가 핵심인 독립적인 안전 지식. safety_flag=True 필수. 다른 지식에 딸린 주의사항은 해당 유형에 safety_flag와 근거를 기록합니다.
- T6: 정지 후 재가동·상태 복귀의 지식. 인계 방법은 T4, 원인 규명은 T3로 구분합니다.
- 카드 하나에 주된 목적 하나를 지정합니다. 각각 따로 검색해도 쓸모 있는 독립적인 목적이 둘이면 분리하고, 같은 목적의 근거·조건·부연 설명은 분리하지 않습니다.
- T1은 징후의 의미 해석, T3는 확인을 통한 원인 구분입니다. 증상 유무나 단계 수만으로 구분하지 않습니다.
- 독립적인 안전 금기는 T5로 분리하되 원래 카드에 필요한 안전 표시·근거·중지 조건을 제거하지 않습니다. 전체 유형의 기계적인 우선순위를 두지 않습니다.

### T3 (단계)
- type_payload.steps는 1개 이상 필수. 각 order는 1 이상의 정수, 오름차순, 중복 없음.
- 1부터 시작하거나 연속일 필요는 없습니다. 원문 순번을 보존하며 검증기는 자동 정렬하지 않습니다.
- 각 단계: step_id(ST- 뒤 숫자 2~4자리, 카드 내 중복 금지), 공백 아닌 action과 expected_result.
- steps는 T3만 허용하며 다른 유형의 steps=[]도 금지입니다. 다른 유형은 null/생략합니다.
- stop_conditions: 단계 중단 조건 목록 (길이 제한·요약 금지).
- verification_step, rollback_action, escalation_target, escalation_channel: 근거 있는 확인·복구·보고 정보만 선택적으로 기록합니다.

### T4 (인계)
- type_payload.handover_method 필수: 5개 필드 모두 기입.
  handover_method는 T4만 허용하며 모든 문자열은 공백이 아니어야 합니다. 누락 내용을 창작하지 않습니다.
  - required_context: 인계할 정보 목록 (최소 1개).
  - recipient_role: 대상 역할.
  - timing: 인계 시점.
  - channel: 인계 방법.
  - acknowledgement: 확인 방법.

### T6 (재가동)
- type_payload.restart_type 필수: "normal_stop_restart", "abnormal_stop_restart", "maintenance_restart", "unknown" 중 택일.
- 미상이면 "unknown". T6 설명은 know_how 및 재가동 필드에 기록하며 steps를 넣지 않습니다.
- 원인 진단과 재가동이 각각 독립적인 지식이면 T3와 T6로 분리합니다. 재가동 순서를 저장하려는 이유만으로 T3로 바꾸지 않습니다.

### 시도·실패 (tried_and_failed)
- restart_type과 tried_and_failed는 모든 유형에 허용합니다. T1~T5의 카드 restart_type은 null/생략 가능합니다.
- 각 시도: attempt_id(AT- 뒤 숫자 4자리), restart_type, 공백 아닌 action과 observed_result.
- failure_reason: 알려진 이유만 기입, 미상은 JSON null 유지.
- evidence_gap: not_observed, not_recorded, insufficient_evidence, conflicting_evidence 중 확인된 유형만 지정합니다.
- next_observations, required_data, data_collection_role: 필요한 관찰·자료·수집 역할을 알 때만 기록합니다.
- 카드와 시도 restart_type이 모두 known일 때만 같은 유형이어야 합니다. 서로 다른 known은 거부합니다.
- known 카드 + unknown 시도는 허용합니다. 카드가 unknown 또는 null/생략이면 시도는 어떤 허용 유형이든 가능합니다.
- evidence_ids는 K-/EV-/AR- 뒤 숫자 4자리입니다. 형식 통과가 실제 근거의 존재를 보장하지 않습니다.

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
    """
    if not observations or cond.signal not in observations:
        return None  # Signal missing, unknown status

    obs_value = observations[cond.signal]
    if isinstance(obs_value, dict) and set(obs_value) == {"value", "unit"}:
        if cond.unit is not None and obs_value["unit"] != cond.unit:
            return None
        obs_value = obs_value["value"]
    op = cond.op
    target = cond.value

    try:
        if op == "==":
            return obs_value == target
        elif op == "!=":
            return obs_value != target
        elif op == ">":
            return obs_value > target
        elif op == ">=":
            return obs_value >= target
        elif op == "<":
            return obs_value < target
        elif op == "<=":
            return obs_value <= target
        else:
            return None  # Invalid op
    except (TypeError, ValueError):
        return None  # Comparison failed


def _instance_matches(card: KnowledgeCard, canonical_ids: set[str], type_only: set[str]) -> bool:
    """A card bound to one MES unit matches that unit, or any request naming only its type.

    A type code ("CAU") resolves to no catalog row; the asker has not said which unit,
    so cards bound to a unit of that type still apply (10/1: eval sets ask by type).
    """
    return (not card.mes_equipment_id or card.mes_equipment_id in canonical_ids
            or card.equipment in type_only)


def _condition_status(card: KnowledgeCard, observations: dict[str, Any] | None) -> str:
    """Reject definite mismatches; all checks must pass to be verified."""
    status = "verified"
    for conditions, forbidden in ((card.conditions, False), (card.exclusions, True)):
        for condition in conditions:
            result = _evaluate_condition(condition, observations)
            if result is forbidden:
                return "inapplicable"
            if result is None:
                status = "unverified"
    return status


def _search_tokens(card: KnowledgeCard) -> set[str]:
    """Search knowledge content, not reviewer identities or generation metadata."""
    texts = [card.know_how, card.title, card.symptom, card.component]
    if card.generalization_evidence:
        texts.append(card.generalization_evidence.generalization_scope)
    if card.type_payload:
        for step in card.type_payload.steps or []:
            texts.extend([step.action, step.expected_result, step.verification_step])
            texts.extend(step.preconditions)
        if card.type_payload.handover_method:
            texts.extend(card.type_payload.handover_method.required_context)
        for attempt in card.type_payload.tried_and_failed:
            texts.extend([attempt.action, attempt.observed_result, attempt.failure_reason])
            texts.extend(attempt.next_observations)
            texts.extend(attempt.required_data)
    return set(re.findall(r'\w+', ' '.join(text for text in texts if text).lower()))


# 제목·증상이 질문과 겹치면 다른 필드보다 이 배수만큼 더 친다(안전 여부와 무관).
SYMPTOM_TITLE_WEIGHT = 2
# 실제 KB에서 1위 관련도가 이보다 낮으면 "답할 카드 없음"으로 본다(load_card_provider가 건다).
# 9/30 평가 개발용 30건: 답 있는 11건의 1위는 모두 5 이상, 답 없는 19건 중 11건은 5 미만.
# ponytail: 토큰 겹침 점수라 긴 질문일수록 점수가 커진다. 오판이 잦으면 질문 길이로 정규화하거나 임베딩 유사도로 바꾼다.
KB_MIN_TOP_RELEVANCE = 5
# 카드의 이 비율보다 많이 나오는 단어는 질의 점수에서 뺀다 (카드 수 기준, 목록을 손으로 관리하지 않는다).
COMMON_TOKEN_SHARE = 0.2
COMMON_TOKEN_MIN_CARDS = 20
# 근거 사건 문장(build_kb.py evidence_text)에만 있는 단어 하나당 점수. 카드 본문(1)보다 낮게 둔다.
EVIDENCE_WEIGHT = 0.5
# 현장 말투(질문 앞 두 글자) -> 카드가 쓰는 말. 설비 일반 어휘만 둔다 (평가 질문 문구를 옮기지 않는다).
# 10/1 블라인드(CAU·PDP·T2·T6)에서 채택: 새다→누설, 떨어지다→트립, 뜨끈→발열, 켜졌다·꺼졌다·멈췄다→기동·정지.
# 유압 '누유'와 공압 '누설'을 함께 걸어도 설비 필터가 갈라 준다. dev·sanity·t4 무변화 확인.
FIELD_SYNONYMS = {"기름": {"오일", "작동유"}, "소리": {"소음"}, "끼익": {"끽"}, "새요": {"누유", "누설"},
                  "샌다": {"누유", "누설"}, "새는": {"누유", "누설"}, "새고": {"누설"}, "뜨거": {"온도", "과열", "발열"},
                  "뜨끈": {"온도", "과열", "발열"}, "쏠려": {"사행"}, "쏠리": {"사행"}, "떨어": {"트립"},
                  "켜졌": {"기동"}, "꺼졌": {"정지"}, "멈췄": {"정지"}, "멈춰": {"정지"}}


def _stems(tokens: set[str]) -> set[str]:
    """Two-syllable prefixes so Korean inflections match (소리가/소리, 벗어난다/벗어나고)."""
    # ponytail: 앞 두 글자 비교라 형태소 분석기보다 거칠다. 오매칭이 늘면 형태소 분석으로 바꾼다.
    return {token[:2] for token in tokens if len(token) >= 2}


def _relevance(query_tokens: set[str], card: KnowledgeCard) -> int:
    """Token overlap over all fields plus weighted stem overlap with title and symptom."""
    focus = _stems(set(re.findall(r'\w+', f"{card.title} {card.symptom or ''}".lower())))
    focus_hits = sum(1 for token in query_tokens if len(token) >= 2 and token[:2] in focus)
    return SYMPTOM_TITLE_WEIGHT * focus_hits + len(query_tokens & _search_tokens(card))


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
        equipment_types: list[dict[str, Any]] | None = None,
        include_draft: bool = False,
        min_top_relevance: int = 0,
        evidence_text: dict[str, str] | None = None,
    ) -> None:
        """
        Initialize with KB cards and optional equipment/handover/checklist data.

        Args:
            cards: List of KnowledgeCard objects to load. Only accepted/kb/L1 cards are loaded.
            equipment_db: Optional equipment metadata.
            handover_db: Optional existing handovers.
            checklist_db: Optional checklists.
            equipment_types: Catalog equipment_type_id/type_code records.
            min_top_relevance: search_cards returns nothing when the best card scores lower.

        Raises:
            ValueError: If dev or sealed cards are mixed in (gate enforcement).
        """
        self.min_top_relevance = min_top_relevance
        self.cards: list[KnowledgeCard] = []
        if cards:
            for card in cards:
                if card.split in ("dev", "sealed"):
                    raise ValueError(
                        f"InMemoryToolProvider does not accept dev/sealed cards: {card.card_id}"
                    )
                # Gate: accepted/kb/L1. Draft kb cards load only when include_draft is set.
                accepted = card.status == "accepted" and card.split == "kb" and card.grade == "L1"
                draft = include_draft and card.status == "draft" and card.split == "kb"
                if accepted or draft:
                    self.cards.append(card)

        # Words in more than COMMON_TOKEN_SHARE of the cards (확인·운전·후…) say nothing about which card fits.
        df: dict[str, int] = {}
        for card in self.cards:
            for token in _search_tokens(card):
                df[token] = df.get(token, 0) + 1
        # A frequency needs a real KB behind it; tiny fixture KBs would lose every word.
        common = len(self.cards) >= COMMON_TOKEN_MIN_CARDS
        self._common_tokens = {t for t, n in df.items() if common and n > COMMON_TOKEN_SHARE * len(self.cards)}
        # Evidence-event words the card itself lacks; scored at EVIDENCE_WEIGHT (see build_kb.evidence_text).
        self._evidence_tokens = {
            card.card_id: set(re.findall(r'\w+', evidence_text[card.card_id].lower())) - _search_tokens(card)
            for card in self.cards if card.card_id in (evidence_text or {})
        }

        self.equipment_db = equipment_db or []
        self.equipment_types = equipment_types or []
        self.handover_db = handover_db or []
        self.checklist_db = checklist_db or []

    def _resolve_equipment(self, equipment_ids: list[str]) -> list[tuple[str, str, dict[str, Any] | None]]:
        """Resolve registered IDs/codes; retain explicit schema types for legacy callers."""
        resolved = []
        for identifier in equipment_ids:
            matches = [row for row in self.equipment_db
                       if identifier in (row.get("equipment_id"), row.get("code"))]
            if len(matches) > 1:
                raise ValueError(f"Ambiguous equipment identifier: {identifier}")
            row = matches[0] if matches else None
            if row is None:
                if identifier not in get_args(Equipment):
                    raise ValueError(f"Unknown equipment identifier: {identifier}")
                resolved.append((identifier, identifier, None))
                continue
            type_id = row.get("equipment_type_id")
            if type_id is None and identifier in get_args(Equipment):
                type_code = identifier
            else:
                types = [item for item in self.equipment_types
                         if type_id is not None and item.get("equipment_type_id") == type_id]
                if len(types) != 1:
                    raise ValueError(f"Missing or ambiguous equipment type: {identifier}")
                type_code = types[0].get("type_code")
            if type_code not in get_args(Equipment):
                raise ValueError(f"Unsupported card equipment type: {type_code}")
            resolved.append((row["equipment_id"], type_code, row))
        return resolved

    def lookup_equipment(self, *, equipment_ids: list[str]) -> list[dict[str, Any]]:
        """Return canonical metadata, rejecting unresolved or unsupported equipment."""
        return [row for _, _, row in self._resolve_equipment(equipment_ids) if row is not None]

    def search_cards(
        self,
        *,
        query: str,
        equipment_ids: list[str],
        k: int = 5,
        observations: dict[str, object] | None = None,
        handover: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Search cards by query with equipment filter and condition matching.

        Returns top-k results (deterministic ranking by _relevance, then card_id).
        handover: a shift-handover memo; T4 evidence-event text is scored only then, so a
        symptom question never ranks a handover card on its source records (9/30 Q-067).
        """
        query_tokens = set(re.findall(r'\w+', query.lower())) - self._common_tokens
        query_tokens |= {alt for stem, alts in FIELD_SYNONYMS.items() if stem in _stems(query_tokens) for alt in alts}
        resolved = self._resolve_equipment(equipment_ids)
        equipment_codes = {code for _, code, _ in resolved}
        canonical_ids = {identifier for identifier, _, _ in resolved}
        type_only = {code for _, code, row in resolved if row is None}
        evidence = self._evidence_tokens if handover else {}

        def candidates():
            for card in self.cards:
                if card.equipment not in equipment_codes and card.equipment != "COMMON":
                    continue
                if not _instance_matches(card, canonical_ids, type_only):
                    continue
                status = _condition_status(card, observations)
                if status != "inapplicable":
                    score = _relevance(query_tokens, card)
                    score += EVIDENCE_WEIGHT * len(query_tokens & evidence.get(card.card_id, set()))
                    yield (-score, card.card_id, card, status)

        # Select before serializing: large provenance/payloads only copied for top-k.
        top = nsmallest(k, candidates(), key=lambda item: item[:2])
        if top and -top[0][0] < self.min_top_relevance:
            return []  # weakest-possible match only: let the pipeline answer "no knowledge"
        results = []
        for _, _, card, status in top:
            card_dict = card.model_dump(mode="json")
            card_dict["condition_status"] = status
            results.append(card_dict)
        return results


    def search_safety_cards(
        self,
        *,
        equipment_ids: list[str],
        observations: dict[str, object] | None = None,
        include_handover: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Return all applicable safety cards (safety_flag=True).

        k limit does not apply; all matching safety cards are returned.
        Condition matching follows §4.2 rules. T4 handover cards are always-on
        notices only in handover mode (include_handover); a query still shows one
        when search_cards ranks it.
        """
        # Equipment filter
        resolved = self._resolve_equipment(equipment_ids)
        equipment_codes = {code for _, code, _ in resolved}
        canonical_ids = {identifier for identifier, _, _ in resolved}
        type_only = {code for _, code, row in resolved if row is None}
        candidate_cards = [
            c for c in self.cards
            if c.safety_flag and (include_handover or c.tacit_type != "T4")
            and (c.equipment in equipment_codes or c.equipment == "COMMON")
            and _instance_matches(c, canonical_ids, type_only)
        ]

        # Condition matching with observations
        results = []
        for card in candidate_cards:
            condition_status = _condition_status(card, observations)
            if condition_status != "inapplicable":
                card_dict = card.model_dump(mode="json")
                card_dict["condition_status"] = condition_status
                results.append(card_dict)

        return results

    def list_handover(
        self, *, equipment_ids: list[str], shift: str | None = None
    ) -> list[dict[str, Any]]:
        """Return existing handover items."""
        canonical_ids = {identifier for identifier, _, _ in self._resolve_equipment(equipment_ids)}
        results = [
            h for h in self.handover_db
            if h.get("equipment_id") in canonical_ids
            and (shift is None or h.get("shift") == shift)
        ]
        return results

    def propose_handover(self, *, extraction_result: dict[str, Any]) -> list[dict[str, Any]]:
        """Queue handover candidates (stub implementation)."""
        return []

    def get_checklist(self, *, equipment_ids: list[str]) -> list[dict[str, Any]]:
        """Return applicable checklists."""
        canonical_ids = {identifier for identifier, _, _ in self._resolve_equipment(equipment_ids)}
        results = [
            c for c in self.checklist_db
            if c.get("equipment_id") in canonical_ids
        ]
        return results
