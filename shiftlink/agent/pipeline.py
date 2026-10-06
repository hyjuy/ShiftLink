"""Fixed four-stage pipeline: route, retrieval, one model call, validation."""

import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Protocol

from shiftlink.agent import tools as tool_stubs
from shiftlink.agent.canary import has_canary
from shiftlink.agent.compose import compose_answer, layers_from_env
from shiftlink.agent.router import HandoverRequest, Mode, QueryRequest, route_request
from shiftlink.agent.response import (
    GUARD_FALLBACK_ANSWER,
    AgentResponse,
    build_response,
    answer_is_card_ids_only,
    guard_blocked,
    validate_response,
)


class ToolProvider(Protocol):
    def lookup_equipment(self, *, equipment_ids: list[str]) -> list[dict[str, Any]]: ...

    def search_cards(
        self, *, query: str, equipment_ids: list[str], k: int = 5,
        observations: dict[str, object] | None = None, handover: bool = False,
    ) -> list[dict[str, Any]]: ...

    def search_safety_cards(
        self, *, equipment_ids: list[str], observations: dict[str, object] | None = None,
        include_handover: bool = False,
    ) -> list[dict[str, Any]]: ...

    def list_handover(self, **kwargs: object) -> list[dict[str, Any]]: ...

    def propose_handover(self, **kwargs: object) -> list[dict[str, Any]]: ...

    def get_checklist(self, **kwargs: object) -> list[dict[str, Any]]: ...


# Questions that ask for a threshold or range rather than reporting a reading (10/2 blind-3).
# ponytail: keyword heuristic; "몇 바퀴" also matches but only matters when the top card is unverified.
_CRITERION = re.compile(r"몇|얼마|기준|정상 ?범위|어느 ?정도|이상인|이상이|적당")


def _asks_criterion(routed: Any) -> bool:
    request = routed.request
    return (routed.mode == "query" and not getattr(request, "observations", None)
            and bool(_CRITERION.search(request.question)))


def _mark_reference(tool_results: dict[str, Any], card_id: Any) -> None:
    for key in ("ranked_cards", "cards", "safety_cards"):
        for card in tool_results.get(key) or []:
            if card.get("card_id") == card_id and card.get("condition_status") == "unverified":
                card["condition_status"] = "reference"


ModelCall = Callable[..., Any]
MODEL_ERRORS = (ValueError, TimeoutError, ConnectionError, KeyError)
OutputValidator = Callable[..., Any]


@dataclass(frozen=True)
class PipelineResult:
    mode: Mode
    tool_results: dict[str, Any]
    output: Any


class FixedPipeline:
    def __init__(
        self,
        *,
        model: ModelCall,
        tools: ToolProvider = tool_stubs,
        validator: OutputValidator | None = None,
        judge: Callable[[str, dict[str, Any]], int] | None = None,
        judge_min_score: int = 2,
        compose_layers: Iterable[str] | None = None,
        answer_mode: str | None = None,
    ) -> None:
        self.tools = tools
        self.model = model
        # Abstain judge (query mode): scores whether the rank-1 card answers the question; below
        # judge_min_score the pipeline answers "no knowledge". Defaults to the model's own judge when it has one.
        self.judge = judge if judge is not None else getattr(model, "judge", None)
        self.judge_min_score = judge_min_score
        # Answer composition layers (compose.py). None reads SHIFTLINK_COMPOSE; default is off until a layer is adopted.
        self.compose_layers = frozenset(layers_from_env() if compose_layers is None else compose_layers)
        # "extract": query-mode answers are built from the rank-1 card (compose E1, adopted 10/6) and the model is not
        # called; the model's only job is then the abstain judge. None reads SHIFTLINK_ANSWER_MODE; default "model".
        self.answer_mode = answer_mode or os.environ.get("SHIFTLINK_ANSWER_MODE") or "model"
        if self.answer_mode not in ("model", "extract"):
            raise ValueError(f"answer_mode must be 'model' or 'extract', got {self.answer_mode!r}")
        self._default_validator = validator is None
        # Default validator: build response and validate invariants
        if validator is None:
            def default_validator(**values: Any) -> Any:
                resp = build_response(
                    mode=values["mode"],
                    request=values["request"],
                    tool_results=values["tool_results"],
                    model_output=values.get("model_output"),
                    model_error=values.get("model_error"),
                )
                errors = validate_response(resp, values["tool_results"])
                if errors:
                    resp.validation_errors.extend(errors)
                    resp.review_queue = True
                return resp
            self.validator = default_validator
        else:
            self.validator = validator

    def run(self, payload: Mapping[str, object]) -> PipelineResult:
        routed = route_request(payload)
        # Tool results are fully collected before the single model call.
        tool_results = self._run_tools(routed.request)
        dropped = {
            card.get("card_id", "<no-id>")
            for card in tool_results["cards"] if has_canary(card)
        }
        if dropped:
            for key in ("cards", "ranked_cards", "safety_cards"):
                tool_results[key] = [
                    card for card in tool_results[key] if not has_canary(card)
                ]
            tool_results["dropped_canary_card_ids"] = sorted(dropped)
        # No ranked card answers the question or memo -> "no knowledge" without a model call.
        # Applicable safety cards are still shown; they warn but do not answer (9/30 eval).
        # Handover too (10/1 T4 run: with no ranked card the model cited a safety card, abstain 0/4).
        # Revisit the handover case once memo item extraction exists (D26-29 contract §4.4).
        # Top card's conditions unverified (no reading for its signal): the validator would reject citing
        # it, and falling to the next card answered from an unrelated one (10/1 Jetson: 6/6 wrong). Show it
        # as a card to check instead of answering.
        top_unverified = bool(tool_results["ranked_cards"]) and             tool_results["ranked_cards"][0].get("condition_status") == "unverified"
        if top_unverified and _asks_criterion(routed):
            # A question asking for the threshold itself ("몇이면 이상?") has no reading by design; the card
            # answers it as a reference, not as a verified condition (10/2 blind-3 B3-003·B3-009).
            _mark_reference(tool_results, tool_results["ranked_cards"][0].get("card_id"))
            top_unverified = False
        if not tool_results["ranked_cards"] or top_unverified or self._judged_off_topic(routed, tool_results):
            output = build_response(routed.mode, routed.request, tool_results)
            output.cited_card_ids = []
            output.no_knowledge = True
            return PipelineResult(mode=routed.mode, tool_results=tool_results, output=output)
        model_output, model_error, retryable = self._call_model(
            mode=routed.mode, request=routed.request, tool_results=tool_results
        )
        output = self._validate_output(
            routed.mode, routed.request, tool_results, model_output, model_error
        )
        # Retry once for output/schema or response validation failures. Transport
        # failures and unsupported modes are held immediately.
        if retryable or (model_error is None and getattr(output, "review_queue", False)):
            model_output, model_error, _ = self._call_model(
                mode=routed.mode, request=routed.request,
                tool_results=tool_results, retry=True,
            )
            output = self._validate_output(
                routed.mode, routed.request, tool_results, model_output, model_error
            )
        self._fill_guard_fallback(output, model_output)
        layers = self.compose_layers | {"E1"} if self.answer_mode == "extract" and routed.mode == "query" else self.compose_layers
        if layers and routed.mode == "query" and getattr(output, "answer", None):
            output.answer = compose_answer(output.answer, output.cited_card_ids, tool_results, layers,
                                           getattr(output, "validation_errors", []))
        return PipelineResult(mode=routed.mode, tool_results=tool_results, output=output)

    def _fill_guard_fallback(self, output: Any, model_output: Any) -> None:
        """A guard-blocked answer is a sentence, not a blank. Schema failures stay blank."""
        if getattr(output, "answer", None) or not guard_blocked(getattr(output, "validation_errors", [])):
            return
        output.answer = GUARD_FALLBACK_ANSWER
        cited = model_output.get("cited_card_ids") if isinstance(model_output, dict) else None
        if isinstance(cited, list):
            output.cited_card_ids = [card_id for card_id in cited if isinstance(card_id, str)]
        output.review_queue = False

    def _judged_off_topic(self, routed: Any, tool_results: dict[str, Any]) -> bool:
        """True when the judge scores the rank-1 card below the threshold (query mode only)."""
        # ponytail: handover memos are not judged — the judge was only measured on query sets (10/2).
        if self.judge is None or routed.mode != "query" or not tool_results["ranked_cards"]:
            return False
        try:
            score = self.judge(routed.request.question, tool_results["ranked_cards"][0])
        except MODEL_ERRORS:
            return False  # judge unavailable: fall through to the normal model call and its own error handling
        tool_results["judge_score"] = score
        return score < self.judge_min_score

    def _call_model(self, **kwargs: Any) -> tuple[Any, str | None, bool]:
        if self.answer_mode == "extract" and kwargs.get("mode") == "query":
            # No model call. The placeholder only carries the rank-1 citation through the normal validator;
            # run() then replaces its text with the E1 answer.
            tool_results = kwargs["tool_results"]
            tool_results["answer_mode"] = "extract"
            return {"answer": "카드 근거 답변", "cited_card_ids": [tool_results["ranked_cards"][0]["card_id"]]}, None, False
        try:
            output = self.model(**kwargs)
            if isinstance(output, dict) and answer_is_card_ids_only(output.get("answer")):
                raise ValueError("answer 본문에는 카드 ID만 쓸 수 없습니다.")
            return output, None, False
        except ValueError:
            return None, "모델 출력 형식 오류", True
        except TimeoutError:
            return None, "모델 요청 시간 초과", False
        except ConnectionError as exc:
            if str(exc).startswith("HTTP 404 ") and "model" in str(exc).lower():
                return None, "설정한 모델을 찾을 수 없습니다.", False
            return None, "모델 연결 또는 HTTP 요청 실패", False
        except NotImplementedError:
            return None, "요청한 모드는 모델 어댑터에서 지원하지 않습니다", False

    def _validate_output(
        self, mode: Mode, request: QueryRequest | HandoverRequest,
        tool_results: dict[str, Any], model_output: Any, model_error: str | None,
    ) -> Any:
        if model_error and not self._default_validator:
            return build_response(mode, request, tool_results, model_error=model_error)
        values = dict(
            mode=mode, request=request, tool_results=tool_results,
            model_output=model_output,
        )
        if self._default_validator:
            values["model_error"] = model_error
        return self.validator(**values)

    def _run_tools(self, request: QueryRequest | HandoverRequest) -> dict[str, Any]:
        if isinstance(request, QueryRequest):
            equipment_ids = [request.eq_id]
            shift = None
            query = request.question
            k = request.k
            observations = request.observations
        else:
            equipment_ids = request.eq_ids
            shift = request.shift
            query = request.memo_text
            k = 5
            observations = None

        # Convert observations list to dict if present (query mode only)
        observations_dict = None
        if observations:
            observations_dict = {obs.signal: obs.value for obs in observations}

        # Both modes share equipment and card retrieval, in this fixed order.
        results = {
            "equipment": self.tools.lookup_equipment(equipment_ids=equipment_ids),
            "cards": self.tools.search_cards(
                query=query,
                equipment_ids=equipment_ids,
                k=k,
                observations=observations_dict,
                handover=isinstance(request, HandoverRequest),
            ),
        }

        # Keep ranked results separate from the uncapped safety merge for evaluation.
        results["ranked_cards"] = list(results["cards"])

        # Retrieve safety cards independently (all applicable, not subject to k limit).
        safety_cards = self.tools.search_safety_cards(
            equipment_ids=equipment_ids,
            observations=observations_dict,
            include_handover=isinstance(request, HandoverRequest),
        )

        # Merge safety_cards and cards: remove duplicates by card_id, safety cards first.
        seen_ids = set()
        merged_cards = []
        for card in safety_cards:
            card_id = card.get("card_id")
            if card_id and card_id not in seen_ids:
                merged_cards.append(card)
                seen_ids.add(card_id)
        for card in results["cards"]:
            card_id = card.get("card_id")
            if card_id and card_id not in seen_ids:
                merged_cards.append(card)
                seen_ids.add(card_id)
        results["cards"] = merged_cards
        # Keep the raw safety retrieval so the merge itself can be audited independently.
        results["safety_cards"] = safety_cards

        if isinstance(request, HandoverRequest):
            # Existing handovers need an explicit shift and are never read for a query.
            results["handover"] = self.tools.list_handover(
                equipment_ids=equipment_ids,
                shift=shift,
            )
        # Checklist retrieval always follows the optional handover lookup.
        results["checklist"] = self.tools.get_checklist(equipment_ids=equipment_ids)
        results["ask_text"] = query
        results["observation_facts"] = (
            self._observation_facts(equipment_ids, observations) if observations else []
        )
        return results

    def _observation_facts(self, equipment_ids, observations):
        """Catalog judgments for the model. Search still receives the raw value dict."""
        fn = getattr(self.tools, "observation_facts", None)
        if not callable(fn):
            return []
        packed = {obs.signal: {"value": obs.value, "unit": obs.unit} for obs in observations}
        return list(fn(equipment_ids=equipment_ids, observations=packed))
