"""Fixed four-stage pipeline: route, retrieval, one model call, validation."""

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol

from shiftlink.agent import tools as tool_stubs
from shiftlink.agent.router import HandoverRequest, Mode, QueryRequest, route_request
from shiftlink.agent.response import AgentResponse, build_response, validate_response


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
        if routed.mode == "query" and not tool_results["cards"]:
            return PipelineResult(
                mode=routed.mode, tool_results=tool_results,
                output=AgentResponse(mode=routed.mode, no_knowledge=True),
            )
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
        return PipelineResult(mode=routed.mode, tool_results=tool_results, output=output)

    def _call_model(self, **kwargs: Any) -> tuple[Any, str | None, bool]:
        try:
            return self.model(**kwargs), None, False
        except ValueError:
            return None, "모델 출력 형식 오류", True
        except TimeoutError:
            return None, "모델 요청 시간 초과", False
        except ConnectionError:
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
