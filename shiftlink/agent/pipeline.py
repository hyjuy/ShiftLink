"""Fixed four-stage pipeline: route, retrieval, one model call, validation."""

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol

from shiftlink.agent import tools as tool_stubs
from shiftlink.agent.router import HandoverRequest, Mode, QueryRequest, route_request
from shiftlink.agent.response import build_response, validate_response


class ToolProvider(Protocol):
    def lookup_equipment(self, *, equipment_ids: list[str]) -> list[dict[str, Any]]: ...

    def search_cards(
        self, *, query: str, equipment_ids: list[str], k: int = 5,
        observations: dict[str, object] | None = None,
    ) -> list[dict[str, Any]]: ...

    def search_safety_cards(
        self, *, equipment_ids: list[str], observations: dict[str, object] | None = None
    ) -> list[dict[str, Any]]: ...

    def list_handover(self, **kwargs: object) -> list[dict[str, Any]]: ...

    def propose_handover(self, **kwargs: object) -> list[dict[str, Any]]: ...

    def get_checklist(self, **kwargs: object) -> list[dict[str, Any]]: ...


ModelCall = Callable[..., Any]
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
    ) -> None:
        self.tools = tools
        self.model = model
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
                if errors:
                    resp.review_queue = True
                return resp
            self.validator = default_validator
        else:
            self.validator = validator

    def run(self, payload: Mapping[str, object]) -> PipelineResult:
        routed = route_request(payload)
        # Tool results are fully collected before the single model call.
        tool_results = self._run_tools(routed.request)
        model_output = self.model(
            mode=routed.mode,
            request=routed.request,
            tool_results=tool_results,
        )
        output = self.validator(
            mode=routed.mode,
            request=routed.request,
            tool_results=tool_results,
            model_output=model_output,
        )
        # One retry only when validation flagged the output; a second failure
        # stays in the review queue instead of triggering more model calls.
        if getattr(output, "review_queue", False):
            model_output = self.model(
                mode=routed.mode,
                request=routed.request,
                tool_results=tool_results,
                retry=True,
            )
            output = self.validator(
                mode=routed.mode,
                request=routed.request,
                tool_results=tool_results,
                model_output=model_output,
            )
        return PipelineResult(mode=routed.mode, tool_results=tool_results, output=output)

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
            observations_dict = {obs.get("signal"): obs.get("value") for obs in observations if "signal" in obs}

        # Both modes share equipment and card retrieval, in this fixed order.
        results = {
            "equipment": self.tools.lookup_equipment(equipment_ids=equipment_ids),
            "cards": self.tools.search_cards(
                query=query,
                equipment_ids=equipment_ids,
                k=k,
                observations=observations_dict,
            ),
        }

        # Keep ranked results separate from the uncapped safety merge for evaluation.
        results["ranked_cards"] = list(results["cards"])

        # Retrieve safety cards independently (all applicable, not subject to k limit).
        safety_cards = self.tools.search_safety_cards(
            equipment_ids=equipment_ids,
            observations=observations_dict,
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
        return results
