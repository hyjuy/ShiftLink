import inspect

import pytest
from pydantic import ValidationError

from shiftlink.agent.pipeline import FixedPipeline, ToolProvider
from shiftlink.agent.router import HandoverRequest, QueryRequest, route_request
from shiftlink.agent import tools as tool_stubs
from shiftlink.agent.response import render_response


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
        {
            "question": "상태?",
            "line_id": "L1",
            "eq_id": "RT-01",
            "scope_id": "S1",
        },
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

    def search_safety_cards(self, **_: object) -> list[dict[str, object]]:
        self.calls.append("search_safety_cards")
        return [{"card_id": "K-0002", "safety_flag": True}]

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

    def __call__(self, **_: object) -> dict[str, object]:
        self.events.append("model")
        self.calls += 1
        return {"answer": "확인한 카드에 근거한 답변입니다.", "cited_card_ids": ["K-0002"]}


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
        "search_safety_cards",
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
        "search_safety_cards",
        "list_handover",
        "get_checklist",
        "model",
    ]
    assert model.calls == 1


def test_six_tool_stubs_are_explicitly_unimplemented() -> None:
    calls = {
        "lookup_equipment": lambda: tool_stubs.lookup_equipment(equipment_ids=["RT-01"]),
        "search_cards": lambda: tool_stubs.search_cards(
            query="진동", equipment_ids=["RT-01"]
        ),
        "search_safety_cards": lambda: tool_stubs.search_safety_cards(
            equipment_ids=["RT-01"]
        ),
        "list_handover": lambda: tool_stubs.list_handover(equipment_ids=["RT-01"]),
        "propose_handover": lambda: tool_stubs.propose_handover(extraction_result={}),
        "get_checklist": lambda: tool_stubs.get_checklist(equipment_ids=["RT-01"]),
    }

    assert tuple(calls) == tool_stubs.TOOL_STUBS
    for call in calls.values():
        with pytest.raises(NotImplementedError):
            call()


def test_registered_tool_provider_and_search_signature_match_registry() -> None:
    assert "propose_handover" in ToolProvider.__dict__
    assert tuple(inspect.signature(tool_stubs.search_cards).parameters) == (
        "query",
        "equipment_ids",
        "k",
        "observations",
    )


@pytest.mark.parametrize("observations", [
    [{"value": 10}],
    [{"signal": "pressure"}],
    [{"signal": "", "value": 10}],
    [{"signal": " \t", "value": 10}],
    [{"signal": "pressure", "value": 10, "unt": "bar"}],
    [{"signal": "pressure", "value": 10, "unit": " "}],
    [{"signal": "pressure", "value": 10}, {"signal": "pressure", "value": 20}],
    [{"signal": "pressure", "value": 10}, {"signal": " pressure ", "value": 20}],
])
def test_invalid_observations_stop_before_tools_and_model(observations) -> None:
    tools = RecordingTools()
    model = RecordingModel(tools.calls)
    with pytest.raises(ValidationError):
        FixedPipeline(tools=tools, model=model).run({
            "question": "상태?", "line_id": "L1", "eq_id": "HPU",
            "observations": observations,
        })
    assert tools.calls == []
    assert model.calls == 0


def test_observations_reach_search_and_model_without_value_loss() -> None:
    observed = []

    class ObservationTools(RecordingTools):
        def search_cards(self, **kwargs):
            observed.append(kwargs["observations"])
            return [{"card_id": "K-0001"}]

        def search_safety_cards(self, **kwargs):
            observed.append(kwargs["observations"])
            return []

    observations = [
        {"signal": " pressure ", "value": 0, "unit": " bar "},
        {"signal": "running", "value": False},
        {"signal": "mode", "value": "stopped"},
        {"signal": "temperature", "value": 21.5},
    ]
    expected = [dict(observations[0], signal="pressure", unit="bar")] + [
        dict(item, unit=None) for item in observations[1:]
    ]
    model_requests = []

    def model(**kwargs):
        model_requests.append(kwargs["request"].model_dump(mode="json"))
        return {}

    FixedPipeline(tools=ObservationTools(), model=model).run({
        "question": "상태?", "line_id": "L1", "eq_id": "HPU",
        "observations": observations,
    })
    assert observed == [{"pressure": 0, "running": False, "mode": "stopped", "temperature": 21.5}] * 2
    assert model_requests[0]["observations"] == expected


def test_observation_value_is_required_but_explicit_null_is_preserved() -> None:
    request = QueryRequest.model_validate({
        "question": "상태?", "line_id": "L1", "eq_id": "HPU",
        "observations": [{"signal": "pressure", "value": None}],
    })
    assert request.model_dump()["observations"] == [
        {"signal": "pressure", "value": None, "unit": None}
    ]


def test_pipeline_uses_model_answer_and_only_model_citations() -> None:
    result = FixedPipeline(tools=RecordingTools(), model=lambda **_: {
        "answer": "근거 기반 답변", "cited_card_ids": ["K-0001"]
    }).run({"question": "상태?", "line_id": "L1", "eq_id": "HPU"})

    assert result.output.answer == "근거 기반 답변"
    assert result.output.cited_card_ids == ["K-0001"]
    assert "근거 기반 답변" in render_response(result.output)


@pytest.mark.parametrize("model_output", [
    {"cited_card_ids": ["K-0001"]},
    {"answer": "   ", "cited_card_ids": ["K-0001"]},
    {"answer": "답변", "cited_card_ids": ["K-0001"], "extra": True},
    {"answer": 12, "cited_card_ids": ["K-0001"]},
    {"answer": "답변", "cited_card_ids": "K-0001"},
    {"answer": "답변", "cited_card_ids": ["K-9999"]},
    {"answer": "답변", "cited_card_ids": ["BAD-ID"]},
    {"answer": "답변", "cited_card_ids": []},
])
def test_invalid_model_output_is_retried_once_then_held(model_output) -> None:
    calls = []

    def model(**kwargs):
        calls.append(kwargs)
        return model_output

    result = FixedPipeline(tools=RecordingTools(), model=model).run(
        {"question": "상태?", "line_id": "L1", "eq_id": "HPU"}
    )

    assert len(calls) == 2
    assert calls[1]["retry"] is True
    assert result.output.review_queue is True
    assert result.output.answer == ""
    assert result.output.validation_errors


def test_adapter_value_error_retries_once_then_holds() -> None:
    calls = []

    def model(**kwargs):
        calls.append(kwargs)
        raise ValueError("adapter output parse failed")

    result = FixedPipeline(tools=RecordingTools(), model=model).run(
        {"question": "상태?", "line_id": "L1", "eq_id": "HPU"}
    )

    assert len(calls) == 2
    assert calls[1]["retry"] is True
    assert result.output.review_queue is True
    assert result.output.answer == ""
    assert result.output.validation_errors == ["모델 출력 형식 오류"]


@pytest.mark.parametrize("error", [TimeoutError("timeout"), ConnectionError("HTTP 404")])
def test_transport_errors_are_held_without_retry(error) -> None:
    calls = []

    def model(**_):
        calls.append(1)
        raise error

    result = FixedPipeline(tools=RecordingTools(), model=model).run(
        {"question": "상태?", "line_id": "L1", "eq_id": "HPU"}
    )

    assert calls == [1]
    assert result.output.review_queue is True
    assert result.output.answer == ""
    assert result.output.validation_errors
