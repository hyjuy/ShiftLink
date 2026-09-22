import inspect

import pytest
from pydantic import ValidationError

from shiftlink.agent.pipeline import (
    CARD_TEXT_BUDGET,
    FixedPipeline,
    ResponseCache,
    ToolProvider,
)
from shiftlink.agent.response import render_response
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


def test_router_records_why_it_chose_the_mode() -> None:
    """4.12: 규칙 라우터의 판정 근거를 남긴다."""
    routed = route_request({"question": "상태?", "line_id": "L1", "eq_id": "HPU"})
    assert routed.route_reason == "format key 'question'"


@pytest.mark.parametrize(
    "observations",
    [
        [{"signal": "pressure"}],  # 값 없는 관측 기록
        [{"signal": "pressure", "value": 8, "unknown_key": 1}],
        [{"signal": "  ", "value": 8}],
        [{"signal": "pressure", "value": 8}, {"signal": "pressure", "value": 20}],
    ],
)
def test_router_rejects_malformed_observations(observations: list[dict]) -> None:
    """§4.2 조건 판정 입력은 경계에서 거른다 — 조용히 약화시키지 않는다."""
    with pytest.raises((ValueError, ValidationError)):
        route_request(
            {"question": "상태?", "line_id": "L1", "eq_id": "HPU", "observations": observations}
        )


def test_observation_map_feeds_condition_matching() -> None:
    routed = route_request(
        {
            "question": "상태?",
            "line_id": "L1",
            "eq_id": "HPU",
            "observations": [{"signal": "pressure", "value": 12, "unit": "bar"}],
        }
    )
    assert routed.request.observation_map() == {"pressure": 12}


def test_both_modes_share_the_same_accessors() -> None:
    """파이프라인이 모드별 필드명을 알 필요가 없다."""
    query = route_request({"question": "상태?", "line_id": "L1", "eq_id": "HPU"}).request
    handover = route_request(
        {"memo_text": "재확인", "shift": "A", "eq_ids": ["RT-01", "RT-01", "CV-01"]}
    ).request

    assert query.equipment_ids == ["HPU"]
    assert query.search_text == "상태?"
    assert query.shift is None
    assert query.k == 5
    # 중복 설비 ID는 한 번만 조회한다.
    assert handover.equipment_ids == ["RT-01", "CV-01"]
    assert handover.search_text == "재확인"
    assert handover.shift == "A"
    assert handover.k == 5
    assert handover.observation_map() == {}


def test_router_k_cap_follows_the_tool_contract() -> None:
    """4.8: 검색 결과 k ≤ 5. 상한은 도구 계약과 같은 값을 쓴다."""
    assert route_request({"question": "상태?", "line_id": "L1", "eq_id": "HPU"}).request.k == tool_stubs.MAX_K
    with pytest.raises(ValidationError):
        route_request(
            {"question": "상태?", "line_id": "L1", "eq_id": "HPU", "k": tool_stubs.MAX_K + 1}
        )


def test_router_rejects_non_mapping_payload() -> None:
    with pytest.raises(ValueError):
        route_request(None)  # type: ignore[arg-type]


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
    )


# --- v1.0 고도화: 지식 없음 게이트·조건 매칭·모델 입력 격리·캐시·감사 ---


class StubTools:
    """Tool provider returning configurable rows; any tool can be made to fail."""

    def __init__(self, cards=None, safety_cards=None, failing=()) -> None:
        self._cards = cards if cards is not None else []
        self._safety = safety_cards if safety_cards is not None else []
        self._failing = set(failing)
        self.calls: list[str] = []

    def _maybe_fail(self, name: str) -> None:
        self.calls.append(name)
        if name in self._failing:
            raise RuntimeError(f"{name} storage down")

    def lookup_equipment(self, **_: object) -> list[dict[str, object]]:
        self._maybe_fail("lookup_equipment")
        return [{"equipment_id": "HPU-01"}]

    def search_cards(self, **_: object) -> list[dict[str, object]]:
        self._maybe_fail("search_cards")
        return list(self._cards)

    def search_safety_cards(self, **_: object) -> list[dict[str, object]]:
        self._maybe_fail("search_safety_cards")
        return list(self._safety)

    def list_handover(self, **_: object) -> list[dict[str, object]]:
        self._maybe_fail("list_handover")
        return []

    def propose_handover(self, **_: object) -> list[dict[str, object]]:
        self._maybe_fail("propose_handover")
        return []

    def get_checklist(self, **_: object) -> list[dict[str, object]]:
        self._maybe_fail("get_checklist")
        return []


class CapturingModel:
    def __init__(self) -> None:
        self.calls = 0
        self.seen: list[dict] = []

    def __call__(self, **kwargs: object) -> dict[str, str]:
        self.calls += 1
        self.seen.append(kwargs["tool_results"])
        return {"status": "draft"}


QUERY = {"question": "압력 저하 원인은?", "line_id": "L1", "eq_id": "HPU"}


def _card(**overrides) -> dict:
    card = {
        "card_id": "K-0001",
        "grade": "L1",
        "tacit_type": "T1",
        "equipment": "HPU",
        "component": "pump",
        "title": "펌프 이상음",
        "symptom": "고주파 소음",
        "know_how": "설비를 정지하고 점검한다.",
        "rationale": "시뮬레이션 재현",
        "conditions": [],
        "exclusions": [],
        "safety_flag": False,
    }
    card.update(overrides)
    return card


def test_query_without_applicable_card_withholds_the_answer() -> None:
    """3.3·4.9: 근거가 없으면 모델을 호출하지 않고 '지식 없음'으로 응답한다."""
    model = CapturingModel()
    result = FixedPipeline(tools=StubTools(), model=model).run(QUERY)

    assert result.no_knowledge is True
    assert result.model_calls == 0
    assert model.calls == 0
    assert result.output.no_knowledge is True
    assert "해당 지식 없음" in render_response(result.output)


def test_handover_without_cards_still_runs_the_model() -> None:
    """인계 모드는 메모에서 항목을 추출하므로 카드가 없어도 보류하지 않는다."""
    model = CapturingModel()
    result = FixedPipeline(tools=StubTools(), model=model).run(
        {"memo_text": "RT-01 진동 재확인", "shift": "A", "eq_ids": ["RT-01"]}
    )

    assert result.no_knowledge is False
    assert model.calls == 1


def test_condition_mismatched_card_is_not_applied() -> None:
    """4.8: 병합 시 중복 제거와 함께 조건 불일치 카드는 적용하지 않는다."""
    tools = StubTools(
        cards=[
            _card(card_id="K-0001", conditions=[{"signal": "pressure", "op": ">=", "value": 10}]),
            _card(card_id="K-0002"),
        ]
    )
    result = FixedPipeline(tools=tools, model=CapturingModel()).run(
        {**QUERY, "observations": [{"signal": "pressure", "value": 8}]}
    )

    assert [c["card_id"] for c in result.tool_results["cards"]] == ["K-0002"]
    dropped = [r for r in result.audit if r.name == "condition_mismatch"]
    assert dropped and dropped[0].detail["dropped"][0]["card_id"] == "K-0001"


def test_unobserved_signal_keeps_the_card_but_marks_it_unverified() -> None:
    """§4.2: 신호가 관측되지 않으면 unknown — 제외하지 않고 unverified로 표기."""
    tools = StubTools(
        cards=[_card(conditions=[{"signal": "pressure", "op": ">=", "value": 10}])]
    )
    result = FixedPipeline(tools=tools, model=CapturingModel()).run(QUERY)

    assert result.tool_results["cards"][0]["condition_status"] == "unverified"


def test_ground_truth_and_canary_never_reach_the_model() -> None:
    """§2.4·§5: Event 정답과 카나리 토큰은 모델 입력에 전달하지 않는다."""
    model = CapturingModel()
    tools = StubTools(
        cards=[
            _card(card_id="K-0001", true_cause="오링 열화", cards_expected=["K-0009"]),
            _card(card_id="K-0002", know_how="누수 카나리 zzk9-ev0024-1c8e 포함"),
        ]
    )
    result = FixedPipeline(tools=tools, model=model).run(QUERY)

    seen_cards = model.seen[0]["cards"]
    assert [c["card_id"] for c in seen_cards] == ["K-0001"]  # 카나리 카드는 차단
    assert "true_cause" not in seen_cards[0]
    assert "cards_expected" not in seen_cards[0]
    blocked = [r for r in result.audit if r.name == "canary_blocked"]
    assert blocked and blocked[0].detail["card_ids"] == ["K-0002"]
    # 원본 검색 결과는 검증·감사를 위해 그대로 남는다.
    assert result.tool_results["cards"][0]["true_cause"] == "오링 열화"


def test_model_context_is_capped_per_card_but_safety_cards_are_intact() -> None:
    """4.8 카드당 300자 절단, D-26·§2.2 안전 카드와 근거는 절단 대상이 아니다."""
    long_text = "가" * 500
    model = CapturingModel()
    tools = StubTools(
        cards=[_card(card_id="K-0001", know_how=long_text)],
        safety_cards=[
            _card(
                card_id="K-0002",
                tacit_type="T5",
                safety_flag=True,
                safety_basis="KOSHA GUIDE M-101-2012",
                know_how=long_text,
            )
        ],
    )
    FixedPipeline(tools=tools, model=model).run(QUERY)

    seen = {c["card_id"]: c for c in model.seen[0]["cards"]}
    assert len(seen["K-0001"]["know_how"]) <= CARD_TEXT_BUDGET + 1  # 말줄임 1자
    assert seen["K-0002"]["know_how"] == long_text
    assert seen["K-0002"]["safety_basis"] == "KOSHA GUIDE M-101-2012"


def test_repeated_query_reuses_the_cached_model_output() -> None:
    """4.8: 동일 질의·동일 검색 결과는 재추론하지 않는다."""
    model = CapturingModel()
    pipeline = FixedPipeline(tools=StubTools(cards=[_card()]), model=model, cache=ResponseCache())

    first = pipeline.run(QUERY)
    second = pipeline.run(QUERY)

    assert first.cache_hit is False and first.model_calls == 1
    assert second.cache_hit is True and second.model_calls == 0
    assert model.calls == 1


def test_cache_misses_when_retrieved_cards_change() -> None:
    model = CapturingModel()
    tools = StubTools(cards=[_card()])
    pipeline = FixedPipeline(tools=tools, model=model, cache=ResponseCache())

    pipeline.run(QUERY)
    tools._cards = [_card(card_id="K-0003")]
    second = pipeline.run(QUERY)

    assert second.cache_hit is False
    assert model.calls == 2


def test_optional_tool_failure_degrades_without_killing_the_run() -> None:
    """4.11·4.12: 부가 도구 실패가 분석을 중단시키지 않되 감사 로그에 남는다."""
    model = CapturingModel()
    tools = StubTools(cards=[_card()], failing=["get_checklist"])
    result = FixedPipeline(tools=tools, model=model).run(QUERY)

    assert result.tool_results["checklist"] == []
    assert model.calls == 1
    failed = [r for r in result.audit if r.name == "checklist"]
    assert "RuntimeError" in failed[0].detail["error"]


def test_card_retrieval_failure_withholds_the_answer() -> None:
    """근거 조회 자체가 실패하면 생성형 답변을 보류한다(4.12 자료 부족)."""
    model = CapturingModel()
    tools = StubTools(cards=[_card()], failing=["search_cards"])
    result = FixedPipeline(tools=tools, model=model).run(QUERY)

    assert result.no_knowledge is True
    assert model.calls == 0
    assert result.tool_results["retrieval_error"] == "search_cards unavailable"


def test_safety_retrieval_failure_withholds_the_answer() -> None:
    """D-26 노출을 보장할 수 없으면 일반 카드가 있어도 답변하지 않는다."""
    model = CapturingModel()
    tools = StubTools(cards=[_card()], failing=["search_safety_cards"])
    result = FixedPipeline(tools=tools, model=model).run(QUERY)

    assert result.no_knowledge is True
    assert model.calls == 0
    assert result.tool_results["retrieval_error"] == "search_safety_cards unavailable"


def test_model_is_called_at_most_twice() -> None:
    """3.3: 요청 1건당 1회 호출, 검증 실패 시 재시도 1회까지."""
    model = CapturingModel()

    def always_failing_validator(**_: object):
        class _Out:
            review_queue = True

        return _Out()

    result = FixedPipeline(
        tools=StubTools(cards=[_card()]), model=model, validator=always_failing_validator
    ).run(QUERY)

    assert model.calls == 2
    assert result.model_calls == 2
    assert result.output.review_queue is True


def test_tool_specs_match_the_declared_stub_surface() -> None:
    """4.8 도구 표가 코드 계약과 일치한다."""
    assert tuple(spec.name for spec in tool_stubs.TOOL_SPECS) == tool_stubs.TOOL_STUBS
    assert all(spec.read_only for spec in tool_stubs.TOOL_SPECS)
    assert tool_stubs.MAX_K == 5
    search = tool_stubs.SPEC_BY_NAME["search_cards"]
    assert search.accepted_inputs == ("query", "equipment_ids", "k")
    # D-26: 안전 조회는 k를 받지 않는다(전수).
    assert "k" not in tool_stubs.SPEC_BY_NAME["search_safety_cards"].accepted_inputs


def test_reference_providers_satisfy_the_tool_contract() -> None:
    from shiftlink.rag.retrieval import InMemoryToolProvider

    assert tool_stubs.verify_tool_provider(tool_stubs) == []
    assert tool_stubs.verify_tool_provider(InMemoryToolProvider()) == []


def test_verify_tool_provider_reports_missing_and_out_of_scope_tools() -> None:
    """읽기 전용·5종 범위 밖 도구를 계약 검사에서 잡는다(4.8 codex 8.2 대응)."""

    class BadProvider:
        def search_cards(self, *, query: str) -> list:  # equipment_ids/k 미수용
            return []

        def mes_write(self, **_: object) -> None: ...

        def update_handover(self, **_: object) -> None: ...

    errors = tool_stubs.verify_tool_provider(BadProvider())
    assert any("[tool_missing] lookup_equipment" in e for e in errors)
    assert any("tool_input_unsupported" in e and "equipment_ids" in e for e in errors)
    assert any("excluded_tool_exposed" in e and "mes_write" in e for e in errors)
    assert any("write_capable_method" in e and "update_handover" in e for e in errors)


def test_check_tool_output_flags_missing_documented_fields() -> None:
    assert tool_stubs.check_tool_output("search_cards", [{"card_id": "K-0001"}]) == [
        "[tool_output_field_missing] search_cards rows are missing "
        "['know_how', 'conditions', 'grade']"
    ]
    # 필드명이 미확정인 도구는 추측해서 검사하지 않는다.
    assert tool_stubs.check_tool_output("get_checklist", [{"anything": 1}]) == []


def test_pipeline_audits_tool_output_contract_violations() -> None:
    tools = StubTools(cards=[{"card_id": "K-0001"}])
    result = FixedPipeline(tools=tools, model=CapturingModel()).run(QUERY)

    cards_record = next(r for r in result.audit if r.name == "cards")
    assert "tool_output_field_missing" in cards_record.detail["output_contract"][0]


def test_read_only_tools_do_not_hand_out_internal_rows() -> None:
    """3.1·4.12: 도구 결과를 고쳐도 저장소가 바뀌지 않는다."""
    from shiftlink.rag.retrieval import InMemoryToolProvider

    provider = InMemoryToolProvider(
        equipment_db=[{"equipment_id": "HPU-01", "name": "유압 유닛"}],
        handover_db=[{"equipment_id": "HPU-01", "shift": "A", "text": "재확인"}],
        checklist_db=[{"equipment_id": "HPU-01", "item": "누유 점검"}],
    )

    provider.lookup_equipment(equipment_ids=["HPU-01"])[0]["name"] = "변조"
    provider.list_handover(equipment_ids=["HPU-01"])[0]["text"] = "변조"
    provider.get_checklist(equipment_ids=["HPU-01"])[0]["item"] = "변조"

    assert provider.equipment_db[0]["name"] == "유압 유닛"
    assert provider.handover_db[0]["text"] == "재확인"
    assert provider.checklist_db[0]["item"] == "누유 점검"


def test_audit_log_records_tool_order_and_actor() -> None:
    """4.12: 도구 호출 순서·인자·결과 수와 실행 주체를 남긴다."""
    result = FixedPipeline(tools=StubTools(cards=[_card()]), model=CapturingModel()).run(
        QUERY, actor="R-01", device="jetson-01"
    )

    assert result.audit[0].detail == {"actor": "R-01", "device": "jetson-01"}
    tool_names = [r.name for r in result.audit if r.stage == "tool"]
    assert tool_names == ["equipment", "cards", "safety_cards", "checklist"]
    cards_record = next(r for r in result.audit if r.name == "cards")
    assert cards_record.detail["result_count"] == 1
    assert cards_record.detail["args"]["k"] == 5
