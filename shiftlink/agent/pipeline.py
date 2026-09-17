"""Fixed four-stage pipeline: route, tools, one model call, validation."""

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol

from shiftlink.agent import tools as tool_stubs
from shiftlink.agent.router import HandoverRequest, Mode, QueryRequest, route_request


class ToolProvider(Protocol):
    def lookup_equipment(self, *, equipment_ids: list[str]) -> list[dict[str, Any]]: ...

    def search_cards(self, **kwargs: object) -> list[dict[str, Any]]: ...

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
        self.validator = validator or (lambda **values: values["model_output"])

    def run(self, payload: Mapping[str, object]) -> PipelineResult:
        routed = route_request(payload)
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
        return PipelineResult(mode=routed.mode, tool_results=tool_results, output=output)

    def _run_tools(self, request: QueryRequest | HandoverRequest) -> dict[str, Any]:
        if isinstance(request, QueryRequest):
            equipment_ids = [request.eq_id]
            shift = None
            query = request.question
            scope_id = request.scope_id
            source_kind = request.source_kind
            k = request.k
        else:
            equipment_ids = request.eq_ids
            shift = request.shift
            query = request.memo_text
            scope_id = None
            source_kind = "card"
            k = 5

        results = {
            "equipment": self.tools.lookup_equipment(equipment_ids=equipment_ids),
            "cards": self.tools.search_cards(
                query=query,
                equipment_ids=equipment_ids,
                scope_id=scope_id,
                source_kind=source_kind,
                k=k,
            ),
            "handover": self.tools.list_handover(
                equipment_ids=equipment_ids,
                shift=shift,
            ),
            "checklist": self.tools.get_checklist(equipment_ids=equipment_ids),
        }
        if isinstance(request, HandoverRequest):
            results["handover_proposal"] = self.tools.propose_handover(
                memo_text=request.memo_text,
                equipment_ids=equipment_ids,
                shift=request.shift,
                existing_items=results["handover"],
            )
        return results
