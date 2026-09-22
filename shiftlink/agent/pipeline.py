"""Fixed four-stage pipeline: route, retrieval, one model call, validation.

Contracts implemented here (통합본 v1.1 §4.8, D26-29_계약_v1.0 §4):
- Rule router first, no model call (router.py).
- Fixed tool order: equipment → cards → safety cards → (handover) → checklist.
  safety_flag=True cards are retrieved independently of top-k and merged first.
- Condition mismatch is applied to the merged list: a card whose condition is
  definitively False against the observations is not applied (§4.2, 4.8).
- "해당 지식 없음": a query with no applicable card never reaches the model
  (3.3, 4.9 지식 없음 처리, 4.12 자료 부족 시 생성형 답변 보류).
- One model call per request, at most one retry on validation failure
  (3.3, §4.3). The model only ever sees the trimmed, leak-checked context —
  Event ground truth and canary tokens never reach it (§2.4, §5).
- Card context is capped at 300 characters per card (4.8 발열·지연 대응).
  Safety cards, safety_basis and stop_conditions are exempt — they are never
  truncated or summarised away (§2.2, D-26).
- Optional hash-keyed response cache for repeated demo queries (4.8).
- Tool calls are recorded for the local audit log (4.12).
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Protocol

from shiftlink.agent import tools as tool_stubs
from shiftlink.agent.response import build_response, is_model_retryable, validate_response
from shiftlink.agent.router import HandoverRequest, Mode, QueryRequest, route_request
from shiftlink.agent.schemas import Condition

# Fields the model is allowed to see. A whitelist, so a new storage field can
# never leak ground truth (true_cause, cards_expected, canary_token, ...).
MODEL_CARD_FIELDS = (
    "card_id",
    "grade",
    "tacit_type",
    "equipment",
    "component",
    "title",
    "symptom",
    "know_how",
    "rationale",
    "conditions",
    "exclusions",
    "safety_flag",
    "safety_basis",
    "type_payload",
    "condition_status",
)

# Per-card free-text budget for the model context (4.8).
CARD_TEXT_BUDGET = 300
_TRUNCATABLE_FIELDS = ("symptom", "know_how", "rationale")

# One call, plus at most one retry (3.3, §4.3).
MAX_MODEL_CALLS = 2

# Eval canary shapes (§5). Their presence in a model context is a leak, not a card.
_CANARY_RE = re.compile(r"(?:zzk9|qqz7)-[A-Za-z0-9-]+")

# A failing optional tool degrades the answer; a failing card search removes the
# grounding altogether and must fall through to "지식 없음" (4.12).
_OPTIONAL_TOOLS = ("equipment", "handover", "checklist")


class ToolProvider(Protocol):
    def lookup_equipment(self, *, equipment_ids: list[str]) -> list[dict[str, Any]]: ...

    def search_cards(self, **kwargs: object) -> list[dict[str, Any]]: ...

    def search_safety_cards(
        self, *, equipment_ids: list[str], observations: dict[str, object] | None = None
    ) -> list[dict[str, Any]]: ...

    def list_handover(self, **kwargs: object) -> list[dict[str, Any]]: ...

    def propose_handover(self, **kwargs: object) -> list[dict[str, Any]]: ...

    def get_checklist(self, **kwargs: object) -> list[dict[str, Any]]: ...


ModelCall = Callable[..., Any]
OutputValidator = Callable[..., Any]


@dataclass(frozen=True)
class AuditRecord:
    """One auditable step of a run (4.12 감사 로그)."""

    seq: int
    stage: str  # "tool" | "model" | "gate"
    name: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PipelineResult:
    mode: Mode
    tool_results: dict[str, Any]
    output: Any
    model_calls: int = 0
    no_knowledge: bool = False
    cache_hit: bool = False
    audit: tuple[AuditRecord, ...] = ()


class ResponseCache:
    """
    Hash-keyed model-output cache: same question + same retrieved cards reuses
    the previous output instead of re-running inference (4.8 발열·지연 대응).

    Only outputs that passed validation are stored.
    """

    def __init__(self, max_entries: int = 64) -> None:
        self.max_entries = max_entries
        self._entries: dict[str, Any] = {}

    def get(self, key: str) -> Any | None:
        return self._entries.get(key)

    def put(self, key: str, value: Any) -> None:
        if key in self._entries:
            return
        if len(self._entries) >= self.max_entries:
            self._entries.pop(next(iter(self._entries)))  # Oldest insertion.
        self._entries[key] = value


class FixedPipeline:
    def __init__(
        self,
        *,
        model: ModelCall,
        tools: ToolProvider = tool_stubs,
        validator: OutputValidator | None = None,
        cache: ResponseCache | None = None,
    ) -> None:
        self.tools = tools
        self.model = model
        self.cache = cache
        # Default validator: build response and validate invariants
        if validator is None:
            def default_validator(**values: Any) -> Any:
                resp = build_response(
                    mode=values["mode"],
                    request=values["request"],
                    tool_results=values["tool_results"],
                    model_output=values.get("model_output"),
                )
                errors = validate_response(resp, values["tool_results"])
                resp.validation_errors = errors
                if errors:
                    resp.review_queue = True
                return resp
            self.validator = default_validator
        else:
            self.validator = validator

    def run(
        self,
        payload: Mapping[str, object],
        *,
        actor: str | None = None,
        device: str | None = None,
    ) -> PipelineResult:
        routed = route_request(payload)
        audit: list[AuditRecord] = []
        if actor or device:
            audit.append(
                AuditRecord(
                    seq=0, stage="gate", name="actor", detail={"actor": actor, "device": device}
                )
            )

        # Tool results are fully collected before the single model call.
        tool_results = self._run_tools(routed.request, audit)

        # "해당 지식 없음": no applicable card means no grounding, so the model is
        # not called at all. Handover mode still runs — it extracts items from
        # the memo itself, not from cards.
        if routed.mode == "query" and not tool_results["cards"]:
            audit.append(
                AuditRecord(
                    seq=len(audit),
                    stage="gate",
                    name="no_knowledge",
                    detail={"reason": tool_results.get("retrieval_error") or "no applicable card"},
                )
            )
            output = self.validator(
                mode=routed.mode,
                request=routed.request,
                tool_results=tool_results,
                model_output=None,
            )
            _mark_no_knowledge(output)
            return PipelineResult(
                mode=routed.mode,
                tool_results=tool_results,
                output=output,
                model_calls=0,
                no_knowledge=True,
                audit=tuple(audit),
            )

        # The model sees the trimmed, leak-checked view; validation keeps using
        # the full results so citations are checked against real retrieval.
        context = self._build_model_context(routed.mode, tool_results, audit)
        cache_key = _cache_key(routed.mode, routed.request, context)

        cached = self.cache.get(cache_key) if self.cache else None
        model_calls = 0
        if cached is not None:
            model_output = cached
            audit.append(
                AuditRecord(seq=len(audit), stage="model", name="cache_hit", detail={"key": cache_key[:12]})
            )
        else:
            model_output = self._call_model(routed, context, audit)
            model_calls += 1

        output = self.validator(
            mode=routed.mode,
            request=routed.request,
            tool_results=tool_results,
            model_output=model_output,
        )

        # One retry only when the failure is the model's own; a second failure
        # stays in the review queue instead of triggering more model calls.
        # Data-side findings never retry — the answer would be identical.
        if (
            getattr(output, "review_queue", False)
            and model_calls < MAX_MODEL_CALLS
            and _is_retryable(output)
        ):
            model_output = self._call_model(routed, context, audit, retry=True)
            model_calls += 1
            output = self.validator(
                mode=routed.mode,
                request=routed.request,
                tool_results=tool_results,
                model_output=model_output,
            )

        if self.cache and cached is None and not getattr(output, "review_queue", False):
            self.cache.put(cache_key, model_output)

        return PipelineResult(
            mode=routed.mode,
            tool_results=tool_results,
            output=output,
            model_calls=model_calls,
            cache_hit=cached is not None,
            audit=tuple(audit),
        )

    def _call_model(
        self,
        routed: Any,
        context: dict[str, Any],
        audit: list[AuditRecord],
        *,
        retry: bool = False,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "mode": routed.mode,
            "request": routed.request,
            "tool_results": context,
        }
        if retry:
            kwargs["retry"] = True
        audit.append(
            AuditRecord(
                seq=len(audit),
                stage="model",
                name="retry" if retry else "call",
                detail={"cards": len(context.get("cards", []))},
            )
        )
        return self.model(**kwargs)

    def _run_tools(
        self, request: QueryRequest | HandoverRequest, audit: list[AuditRecord]
    ) -> dict[str, Any]:
        # Both request types expose the same accessors (router.py), so the
        # pipeline does not branch on mode-specific field names.
        equipment_ids = request.equipment_ids
        shift = request.shift
        query = request.search_text
        k = request.k
        # Signal → value map for §4.2; empty stays None so "no reading" and
        # "nothing observed" are the same unknown to the tools.
        observations_dict = request.observation_map() or None

        # Both modes share equipment and card retrieval, in this fixed order.
        results: dict[str, Any] = {
            "equipment": self._call_tool(
                audit, "equipment", self.tools.lookup_equipment, equipment_ids=equipment_ids
            ),
            "cards": self._call_tool(
                audit,
                "cards",
                self.tools.search_cards,
                query=query,
                equipment_ids=equipment_ids,
                k=k,
            ),
        }
        if results["cards"] is None:
            results["retrieval_error"] = "search_cards unavailable"
            results["cards"] = []

        # Retrieve safety cards independently (all applicable, not subject to k limit).
        safety_cards = self._call_tool(
            audit,
            "safety_cards",
            self.tools.search_safety_cards,
            equipment_ids=equipment_ids,
            observations=observations_dict,
        )
        if safety_cards is None:
            # Safety retrieval is never silently degraded: without it, D-26
            # exposure cannot be guaranteed, so the answer is withheld.
            results["retrieval_error"] = "search_safety_cards unavailable"
            results["cards"] = []
            results["safety_cards"] = []
            safety_cards = []

        # Merge safety_cards and cards: remove duplicates by card_id, safety cards first.
        seen_ids = set()
        merged_cards = []
        dropped: list[dict[str, str]] = []
        for card in list(safety_cards) + list(results["cards"]):
            card_id = card.get("card_id")
            if not card_id or card_id in seen_ids:
                continue
            seen_ids.add(card_id)
            # 4.8: "중복 ID를 제거하고 조건 불일치 카드는 적용하지 않는다".
            include, condition_status = _condition_verdict(card, observations_dict)
            if not include:
                dropped.append({"card_id": card_id, "reason": condition_status})
                continue
            if condition_status == "unverified":
                card = {**card, "condition_status": "unverified"}
            merged_cards.append(card)

        if dropped:
            audit.append(
                AuditRecord(
                    seq=len(audit), stage="gate", name="condition_mismatch", detail={"dropped": dropped}
                )
            )
        results["cards"] = merged_cards
        # Keep the raw safety retrieval so the merge itself can be audited independently.
        results.setdefault("safety_cards", safety_cards)

        if isinstance(request, HandoverRequest):
            # Existing handovers need an explicit shift and are never read for a query.
            results["handover"] = self._call_tool(
                audit,
                "handover",
                self.tools.list_handover,
                equipment_ids=equipment_ids,
                shift=shift,
            )
        # Checklist retrieval always follows the optional handover lookup.
        results["checklist"] = self._call_tool(
            audit, "checklist", self.tools.get_checklist, equipment_ids=equipment_ids
        )
        for name in _OPTIONAL_TOOLS:
            if name in results and results[name] is None:
                results[name] = []
        return results

    def _call_tool(
        self, audit: list[AuditRecord], name: str, tool: Callable[..., Any], **kwargs: Any
    ) -> Any:
        """
        Call one tool and record it. Returns None when the tool failed — an
        optional tool degrades the answer, card retrieval withholds it (4.12).
        """
        try:
            result = tool(**kwargs)
        except Exception as exc:  # Storage/adapter failure must not kill the run.
            audit.append(
                AuditRecord(
                    seq=len(audit),
                    stage="tool",
                    name=name,
                    detail={"args": _audit_args(kwargs), "error": f"{type(exc).__name__}: {exc}"},
                )
            )
            return None
        detail: dict[str, Any] = {"args": _audit_args(kwargs), "result_count": len(result)}
        # Contract drift of a storage adapter is recorded, not silently accepted.
        violations = tool_stubs.check_tool_output(getattr(tool, "__name__", ""), result)
        if violations:
            detail["output_contract"] = violations
        audit.append(AuditRecord(seq=len(audit), stage="tool", name=name, detail=detail))
        return result

    def _build_model_context(
        self, mode: Mode, tool_results: dict[str, Any], audit: list[AuditRecord]
    ) -> dict[str, Any]:
        """Whitelist, truncate, and leak-check what the single model call receives."""
        cards: list[dict[str, Any]] = []
        leaked: list[str] = []
        for card in tool_results["cards"]:
            trimmed = _trim_card(card)
            if _CANARY_RE.search(json.dumps(trimmed, ensure_ascii=False, sort_keys=True, default=str)):
                leaked.append(str(card.get("card_id")))
                continue
            cards.append(trimmed)

        if leaked:
            audit.append(
                AuditRecord(
                    seq=len(audit), stage="gate", name="canary_blocked", detail={"card_ids": leaked}
                )
            )

        context: dict[str, Any] = {
            "mode": mode,
            "cards": cards,
            "equipment": tool_results.get("equipment", []),
            "checklist": tool_results.get("checklist", []),
        }
        if "handover" in tool_results:
            context["handover"] = tool_results["handover"]
        return context


def _condition_verdict(card: Mapping[str, Any], observations: Mapping[str, Any] | None) -> tuple[bool, str]:
    """
    Apply §4.2 to a retrieved card dict.

    Returns (include, status). A definitively False condition or a definitively
    True exclusion drops the card; a missing signal stays unknown and the card
    is kept (conservative, safety cards included).
    """
    status = "verified"
    for raw in card.get("conditions") or []:
        verdict = _evaluate(raw, observations)
        if verdict is False:
            return False, "condition_mismatch"
        if verdict is None:
            status = "unverified"
    for raw in card.get("exclusions") or []:
        verdict = _evaluate(raw, observations)
        if verdict is True:
            return False, "exclusion_hit"
        if verdict is None:
            status = "unverified"
    return True, status


def _evaluate(raw: Any, observations: Mapping[str, Any] | None) -> bool | None:
    if isinstance(raw, Condition):
        return raw.evaluate(observations)
    if not isinstance(raw, Mapping):
        return None
    try:
        return Condition.model_validate(dict(raw)).evaluate(observations)
    except Exception:
        return None  # Malformed condition is unknown, never a silent match.


def _trim_card(card: Mapping[str, Any]) -> dict[str, Any]:
    """
    Whitelist the fields the model may see and cap free text at 300 characters.

    Safety cards are exempt: D-26 exposure and safety_basis must reach the model
    intact, and §2.2 forbids shortening stop_conditions.
    """
    trimmed = {key: card[key] for key in MODEL_CARD_FIELDS if key in card}
    if card.get("safety_flag"):
        return trimmed

    budget = CARD_TEXT_BUDGET
    for key in _TRUNCATABLE_FIELDS:
        text = trimmed.get(key)
        if not isinstance(text, str):
            continue
        if budget <= 0:
            trimmed[key] = ""
        elif len(text) > budget:
            trimmed[key] = text[:budget] + "…"
        budget -= len(text)
    return trimmed


def _cache_key(mode: Mode, request: Any, context: Mapping[str, Any]) -> str:
    """Same question + same retrieved cards → same key (4.8)."""
    payload = {
        "mode": mode,
        "request": request.model_dump(mode="json"),
        "context": context,
    }
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _audit_args(kwargs: Mapping[str, Any]) -> dict[str, Any]:
    """Tool arguments for the audit log, without dragging whole records in."""
    return {k: v for k, v in kwargs.items() if k != "observations" or v}


def _mark_no_knowledge(output: Any) -> None:
    if hasattr(output, "no_knowledge"):
        output.no_knowledge = True


def _is_retryable(output: Any) -> bool:
    """A custom validator that reports no reason keeps the old retry behaviour."""
    errors = getattr(output, "validation_errors", None)
    if errors is None:
        return True
    return is_model_retryable(errors)
