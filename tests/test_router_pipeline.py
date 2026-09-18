import pytest
from pydantic import ValidationError

from shiftlink.agent.pipeline import FixedPipeline
from shiftlink.agent.router import HandoverRequest, QueryRequest, route_request
from shiftlink.agent import tools as tool_stubs


def test_router_uses_input_shape_instead_of_text_keywords() -> None:
    query = route_request(
        {"question": "다음 교대에 무엇을 넘겨야 하나요?", "line_id": "L1", "eq_id": "RT-01"}
    )
    handover = route_request(
        {"memo_text": "RT-01 진동 재확인", "shift": "A", "eq_ids": ["RT-01"]}
    )

    assert query.mode == "query"
    assert isinstance(query.request, QueryRequest)
    assert handover.mode == "handover"
    assert isinstance(handover.request, HandoverRequest)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"question": "상태?", "memo_text": "인계", "line_id": "L1", "eq_id": "RT-01"},
        {"question": "   ", "line_id": "L1", "eq_id": "RT-01"},
        {"memo_text": "인계", "shift": "D", "eq_ids": []},
    ],
)
def test_router_rejects_missing_ambiguous_or_invalid_formats(payload: dict[str, object]) -> None:
    with pytest.raises((ValueError, ValidationError)):
        route_request(payload)


class RecordingTools:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def lookup_equipment(self, equipment_ids: list[str]) -> list[dict[str, object]]:
        self.calls.append("lookup_equipment")
        return [{"equipment_id": equipment_id} for equipment_id in equipment_ids]

    def search_cards(self, **_: object) -> list[dict[str, object]]:
        self.calls.append("search_cards")
        return [{"card_id": "K-0001"}]

    def list_handover(self, **_: object) -> list[dict[str, object]]:
        self.calls.append("list_handover")
        return []

    def propose_handover(self, **_: object) -> list[dict[str, object]]:
        self.calls.append("propose_handover")
        return [{"text": "진동 재확인"}]

    def get_checklist(self, **_: object) -> list[dict[str, object]]:
        self.calls.append("get_checklist")
        return []


class RecordingModel:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.calls = 0

    def __call__(self, **_: object) -> dict[str, str]:
        self.events.append("model")
        self.calls += 1
        return {"status": "draft"}


def test_query_pipeline_excludes_handover_tools_and_calls_model_once() -> None:
    tools = RecordingTools()
    model = RecordingModel(tools.calls)

    result = FixedPipeline(tools=tools, model=model).run(
        {"question": "압력 저하 원인은?", "line_id": "L1", "eq_id": "HPU-01"}
    )

    assert result.mode == "query"
    assert tools.calls == [
        "lookup_equipment",
        "search_cards",
        "get_checklist",
        "model",
    ]
    assert model.calls == 1


def test_handover_pipeline_lists_existing_items_before_one_model_call() -> None:
    tools = RecordingTools()
    model = RecordingModel(tools.calls)

    result = FixedPipeline(tools=tools, model=model).run(
        {"memo_text": "RT-01 진동 재확인", "shift": "A", "eq_ids": ["RT-01"]}
    )

    assert result.mode == "handover"
    assert tools.calls == [
        "lookup_equipment",
        "search_cards",
        "list_handover",
        "get_checklist",
        "model",
    ]
    assert model.calls == 1


def test_five_tool_stubs_are_explicitly_unimplemented() -> None:
    calls = {
        "lookup_equipment": lambda: tool_stubs.lookup_equipment(equipment_ids=["RT-01"]),
        "search_cards": lambda: tool_stubs.search_cards(
            query="진동", equipment_ids=["RT-01"]
        ),
        "list_handover": lambda: tool_stubs.list_handover(equipment_ids=["RT-01"]),
        "propose_handover": lambda: tool_stubs.propose_handover(extraction_result={}),
        "get_checklist": lambda: tool_stubs.get_checklist(equipment_ids=["RT-01"]),
    }

    assert tuple(calls) == tool_stubs.TOOL_STUBS
    for call in calls.values():
        with pytest.raises(NotImplementedError):
            call()
