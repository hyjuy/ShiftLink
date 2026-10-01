"""가짜 HTTP 응답으로 Ollama 어댑터의 계약을 검증한다. 실제 모델을 부르지 않는다."""

import copy
import io
import json
import socket
import urllib.error
from pathlib import Path

import pytest

from shiftlink.agent.pipeline import FixedPipeline
from shiftlink.agent.router import HandoverRequest, QueryRequest
from shiftlink.edge.ollama import (
    QUERY_MAX_CANDIDATES,
    CANARY_PREFIXES,
    HANDOVER_SYSTEM_PROMPT,
    MODEL_CARD_FIELDS,
    OUTPUT_SCHEMA,
    OllamaModel,
    build_messages,
    _parse_output,
    card_context,
)
from shiftlink.rag.loader import load_card_provider

KB_CARDS = Path(__file__).resolve().parents[1] / "docs/data/knowledge_cards/kb/20260929-A/cards.json"
KB_MERGED = Path(__file__).resolve().parents[1] / "docs/data/knowledge_cards/kb/kb_cards.json"


def make_request():
    return QueryRequest(
        question="호스 압력이 낮다",
        line_id="LN-0001",
        eq_id="HPU",
        observations=[{"signal": "pressure", "value": 8}],
    )


def make_tool_results(**card_overrides):
    card = {
        "card_id": "K-0108",
        "tacit_type": "T5",
        "equipment": "HPU",
        "component": "hose",
        "title": "호스 점검",
        "know_how": "정지 후 점검",
        "rationale": "고압 위험",
        "safety_flag": True,
        "safety_basis": "KOSHA GUIDE",
        "condition_status": "verified",
        # 화이트리스트 밖 필드는 프롬프트에 나가면 안 된다.
        "provenance": {"seed_ids": ["SD-001"], "persona_id": "V-13"},
        "split": "kb",
    }
    card.update(card_overrides)
    return {"cards": [card]}


class FakeHTTP:
    """urlopen 대체. 호출 횟수를 세고, 정해둔 응답이나 예외를 돌려준다."""

    def __init__(self, content=None, *, raise_exc=None, body=None):
        self.content = content
        self.raise_exc = raise_exc
        self.body = body
        self.calls = []

    def __call__(self, request, timeout=None):
        self.calls.append(json.loads(request.data.decode("utf-8")))
        if self.raise_exc is not None:
            raise self.raise_exc
        body = self.body
        if body is None:
            body = {"message": {"content": self.content}, "load_duration": 1_500_000_000,
                    "eval_count": 25}
        return _Response(json.dumps(body).encode("utf-8"))


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def call(monkeypatch, fake, *, mode="query", **kwargs):
    monkeypatch.setattr("urllib.request.urlopen", fake)
    model = OllamaModel()
    output = model(
        mode=mode,
        request=make_request(),
        tool_results=make_tool_results(),
        **kwargs,
    )
    return model, output


def test_returns_only_the_agreed_fields(monkeypatch):
    fake = FakeHTTP(json.dumps({"answer": "정지 후 점검하세요", "cited_card_ids": ["K-0108"]}))
    model, output = call(monkeypatch, fake)

    assert output == {"answer": "정지 후 점검하세요", "cited_card_ids": ["K-0108"]}
    assert model.last_call["latency_s"] >= 0
    assert model.last_call["load_duration_s"] == 1.5
    assert model.last_call["eval_count"] == 25


def test_one_model_call_per_invocation(monkeypatch):
    """재시도는 파이프라인 책임이므로 어댑터는 절대 스스로 다시 부르지 않는다."""
    fake = FakeHTTP(json.dumps({"answer": "a", "cited_card_ids": []}))
    call(monkeypatch, fake)
    assert len(fake.calls) == 1


def test_request_payload_follows_documented_options(monkeypatch):
    fake = FakeHTTP(json.dumps({"answer": "a", "cited_card_ids": []}))
    call(monkeypatch, fake)

    sent = fake.calls[0]
    assert sent["stream"] is False
    # 문자열 "-1"이면 Ollama가 400을 내므로 타입까지 고정한다.
    assert sent["keep_alive"] == -1 and isinstance(sent["keep_alive"], int)
    # num_predict 없으면 JSON 모드 생성이 끝나지 않아 타임아웃까지 멈춘다(9/29 Jetson 3/20건).
    assert sent["options"] == {"temperature": 0, "num_ctx": 2048, "num_predict": 256}
    # A의 validate_model_output과 같은 제약을 모델 쪽에도 걸어야 재시도가 줄어든다.
    schema = sent["format"]
    assert schema["required"] == ["answer", "cited_card_ids"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["answer"]["minLength"] == 1
    # answer가 출력 상한 안에서 스스로 닫혀야 잘린 JSON이 생기지 않는다.
    assert schema["properties"]["answer"]["maxLength"] == 160
    cited = schema["properties"]["cited_card_ids"]
    assert cited["minItems"] == 1 and cited["uniqueItems"] is True
    # 후보 카드 ID만 문법으로 허용한다(ranked_cards 없는 구 호출자는 전 카드가 후보).
    assert cited["items"]["enum"] == ["K-0108"]


def test_retry_flag_changes_the_prompt(monkeypatch):
    fake = FakeHTTP(json.dumps({"answer": "a", "cited_card_ids": []}))
    call(monkeypatch, fake, retry=True)
    assert "[재시도]" in fake.calls[0]["messages"][1]["content"]

    fake_first = FakeHTTP(json.dumps({"answer": "a", "cited_card_ids": []}))
    call(monkeypatch, fake_first)
    assert "[재시도]" not in fake_first.calls[0]["messages"][1]["content"]


@pytest.mark.parametrize(
    "content",
    [
        "설명을 붙인 답변입니다",  # JSON 아님
        json.dumps(["K-0108"]),  # 객체 아님
        json.dumps({"answer": "a"}),  # cited_card_ids 누락
        json.dumps({"answer": 1, "cited_card_ids": []}),  # answer 타입 오류
        json.dumps({"answer": "a", "cited_card_ids": "K-0108"}),  # 배열 아님
        json.dumps({"answer": "a", "cited_card_ids": [1]}),  # 원소 타입 오류
        json.dumps({"answer": "   ", "cited_card_ids": ["K-0108"]}),  # 공백뿐인 answer
    ],
)
def test_malformed_model_output_raises_value_error(monkeypatch, content):
    fake = FakeHTTP(content)
    with pytest.raises(ValueError):
        call(monkeypatch, fake)


def test_missing_message_content_raises_value_error(monkeypatch):
    fake = FakeHTTP(body={"error": "model not found"})
    with pytest.raises(ValueError):
        call(monkeypatch, fake)


def test_timeout_raises_timeout_error(monkeypatch):
    fake = FakeHTTP(raise_exc=socket.timeout("timed out"))
    with pytest.raises(TimeoutError):
        call(monkeypatch, fake)


def test_timeout_wrapped_in_urlerror_is_still_timeout_error(monkeypatch):
    fake = FakeHTTP(raise_exc=urllib.error.URLError(socket.timeout("timed out")))
    with pytest.raises(TimeoutError):
        call(monkeypatch, fake)


def test_connection_refused_raises_connection_error(monkeypatch):
    fake = FakeHTTP(raise_exc=urllib.error.URLError(ConnectionRefusedError(61, "refused")))
    with pytest.raises(ConnectionError):
        call(monkeypatch, fake)


def test_http_error_raises_connection_error(monkeypatch):
    fake = FakeHTTP(
        raise_exc=urllib.error.HTTPError("u", 404, "not found", {}, None)
    )
    with pytest.raises(ConnectionError):
        call(monkeypatch, fake)


def test_timeout_is_not_swallowed_as_connection_error(monkeypatch):
    """TimeoutError도 OSError 하위라, ConnectionError 갈래로 새면 A가 재시도 판단을 못 한다."""
    fake = FakeHTTP(raise_exc=socket.timeout("timed out"))
    with pytest.raises(TimeoutError) as exc:
        call(monkeypatch, fake)
    assert not isinstance(exc.value, ConnectionError)


def test_unknown_mode_is_rejected_without_a_model_call(monkeypatch):
    fake = FakeHTTP(json.dumps({"answer": "a", "cited_card_ids": []}))
    with pytest.raises(NotImplementedError):
        call(monkeypatch, fake, mode="summary")
    assert fake.calls == []


HANDOVER_METHOD = {
    "required_context": ["소리 변화", "처음 들린 시각"],
    "recipient_role": "다음 근무 설비 담당",
    "timing": "교대 시",
    "channel": "인계 메모",
    "acknowledgement": "받는 사람 서명",
}


def make_handover_results():
    card = {"card_id": "K-0104", "tacit_type": "T4", "equipment": "COMMON",
            "title": "소리 변화 인계", "know_how": "소리 변화를 시각과 함께 적는다",
            "type_payload": {"handover_method": HANDOVER_METHOD}}
    return {"cards": [card], "ranked_cards": [card]}


def test_handover_mode_uses_memo_and_card_handover_method(monkeypatch):
    fake = FakeHTTP(json.dumps({"answer": "소리 변화 확인 필요", "cited_card_ids": ["K-0104"]}))
    monkeypatch.setattr("urllib.request.urlopen", fake)
    request = HandoverRequest(memo_text="HPU 소리가 거칠다", shift="A", eq_ids=["HPU"])

    output = OllamaModel()(mode="handover", request=request, tool_results=make_handover_results())

    assert output == {"answer": "소리 변화 확인 필요", "cited_card_ids": ["K-0104"]}
    system, user = (message["content"] for message in fake.calls[0]["messages"])
    assert system == HANDOVER_SYSTEM_PROMPT
    assert "인계 메모: HPU 소리가 거칠다" in user
    assert '"recipient_role": "다음 근무 설비 담당"' in user
    assert fake.calls[0]["format"]["properties"]["cited_card_ids"]["items"]["enum"] == ["K-0104"]


def test_handover_pipeline_renders_t4_card_as_handover_memo():
    """실제 KB: 인계 메모 → T4 후보 인용 → 인계 방법 블록이 카드에서 렌더된다."""
    provider = load_card_provider(KB_MERGED).provider
    sent = []

    def post(path, payload):
        sent.append(payload)
        first = payload["format"]["properties"]["cited_card_ids"]["items"]["enum"][0]
        return {"message": {"content": json.dumps({"answer": "인계 요지", "cited_card_ids": [first]})}}

    model = OllamaModel()
    model._post = post
    result = FixedPipeline(model=model, tools=provider).run({
        "memo_text": "HPU 운전 중 소리가 평소보다 거칠어졌는데 아직 원인은 모른다. 인계 때 뭘 적어야 해?",
        "shift": "A", "eq_ids": ["HPU-01"]})

    assert result.mode == "handover" and not result.output.review_queue
    assert sent[0]["messages"][0]["content"] == HANDOVER_SYSTEM_PROMPT
    assert result.output.cited_card_ids and result.output.handover_method is not None
    assert "K-1110" in {notice.card_id for notice in result.output.safety_notices}


def test_query_mode_does_not_send_handover_method():
    messages, _ = build_messages("query", make_request(), make_handover_results())
    assert "handover_method" not in messages[1]["content"]


def test_card_context_applies_whitelist():
    context, dropped = card_context(make_tool_results())
    assert dropped == []
    assert set(context[0]) <= set(MODEL_CARD_FIELDS)
    assert "provenance" not in context[0]
    assert "split" not in context[0]


def test_canary_card_is_dropped_from_context():
    tainted = make_tool_results(know_how=f"{CANARY_PREFIXES[1]}dev-f006 정지 후 점검")
    context, dropped = card_context(tainted)
    assert dropped == ["K-0108"]
    assert context == []


def test_canary_in_non_prompt_field_is_also_dropped():
    tainted = make_tool_results(type_payload={"steps": [{"action": "qqz7-secret"}]})
    context, dropped = card_context(tainted)
    assert context == []
    assert dropped == ["K-0108"]


def test_prompt_carries_question_observations_and_cards():
    messages, _ = build_messages("query", make_request(), make_tool_results())
    user = messages[1]["content"]
    assert "호스 압력이 낮다" in user
    assert '"signal": "pressure"' in user
    assert "K-0108" in user


def make_split_results():
    """안전 카드 K-0108은 검색에 안 걸렸고, 검색 순위는 K-0201 > K-0200이다."""
    safety = make_tool_results()["cards"][0]
    ranked = [
        {"card_id": "K-0201", "title": "펌프 소음", "symptom": "소리가 크다", "know_how": "a"},
        {"card_id": "K-0200", "title": "유온 상승", "symptom": "오일이 뜨겁다", "know_how": "b"},
    ]
    return {"cards": [safety, *ranked], "ranked_cards": ranked, "safety_cards": [safety]}


def call_with(monkeypatch, tool_results, **kwargs):
    monkeypatch.setattr("urllib.request.urlopen", FakeHTTP(
        json.dumps({"answer": "a", "cited_card_ids": ["K-0201"]})))
    sent = []
    model = OllamaModel()
    real_post = model._post
    model._post = lambda path, payload: (sent.append(payload), real_post(path, payload))[1]
    model(mode="query", request=make_request(), tool_results=tool_results, **kwargs)
    return model, sent[0]


def test_enum_is_candidates_in_rank_order_without_safety_references(monkeypatch):
    monkeypatch.setattr("shiftlink.edge.ollama.QUERY_MAX_CANDIDATES", 5)  # 후보 여러 장 경로 확인
    model, sent = call_with(monkeypatch, make_split_results())
    items = sent["format"]["properties"]["cited_card_ids"]["items"]
    assert items == {"type": "string", "enum": ["K-0201", "K-0200"]}
    assert model.last_call["candidate_card_ids"] == ["K-0201", "K-0200"]
    user = sent["messages"][1]["content"]
    assert "K-0201: 펌프 소음 / 소리가 크다" in user
    # 안전 참고 카드는 후보 블록 뒤에 제목 한 줄만, 인용 금지로 나간다(본문 없음).
    refs = user[user.index("안전 참고 카드"):]
    assert refs.count("K-0108") == 1 and '"card_id": "K-0108"' not in user
    assert "증상·제목이 가장 일치하는 카드를 먼저 인용하라" in sent["messages"][0]["content"]


def test_duplicate_citations_are_collapsed_in_order():
    body = {"message": {"content": '{"answer": "a", "cited_card_ids": ["K-0201", "K-0200", "K-0201"]}'}}
    assert _parse_output(body)["cited_card_ids"] == ["K-0201", "K-0200"]


def test_query_sends_only_top_ranked_candidates(monkeypatch):
    """질의 모드는 검색 상위 QUERY_MAX_CANDIDATES장만 모델에 넘긴다. 안전 참고는 그대로 나간다."""
    assert QUERY_MAX_CANDIDATES == 1
    model, sent = call_with(monkeypatch, make_split_results())
    assert sent["format"]["properties"]["cited_card_ids"]["items"]["enum"] == ["K-0201"]
    assert model.last_call["candidate_card_ids"] == ["K-0201"]
    user = sent["messages"][1]["content"]
    assert "K-0200" not in user and "안전 참고 카드" in user


def test_safety_card_found_by_search_stays_a_candidate(monkeypatch):
    monkeypatch.setattr("shiftlink.edge.ollama.QUERY_MAX_CANDIDATES", 5)  # 후보 여러 장 경로 확인
    results = make_split_results()
    results["ranked_cards"] = [results["cards"][0], *results["ranked_cards"]]
    _, sent = call_with(monkeypatch, results)
    enum = sent["format"]["properties"]["cited_card_ids"]["items"]["enum"]
    assert enum == ["K-0108", "K-0201", "K-0200"]
    assert "안전 참고 카드" not in sent["messages"][1]["content"]


def test_no_candidates_allows_empty_citation(monkeypatch):
    results = make_split_results()
    results["ranked_cards"] = []
    _, sent = call_with(monkeypatch, results)
    assert sent["format"]["properties"]["cited_card_ids"]["minItems"] == 0


def test_retry_prompt_lists_real_candidate_ids(monkeypatch):
    monkeypatch.setattr("shiftlink.edge.ollama.QUERY_MAX_CANDIDATES", 5)  # 후보 여러 장 경로 확인
    _, sent = call_with(monkeypatch, make_split_results(), retry=True)
    user = sent["messages"][1]["content"]
    retry = user[user.index("[재시도]"):]
    assert "K-0201, K-0200" in retry and "K-0108" not in retry
    assert all("K-0000" not in message["content"] for message in sent["messages"])


def test_global_output_schema_is_not_mutated(monkeypatch):
    before = copy.deepcopy(OUTPUT_SCHEMA)
    call_with(monkeypatch, make_split_results())
    call_with(monkeypatch, {**make_split_results(), "ranked_cards": []})
    assert OUTPUT_SCHEMA == before


def test_symptom_match_ranks_first_and_leads_the_enum(monkeypatch):
    """실제 KB: 소음·우유빛 거품 질문은 에어레이션(K-1004)이 수분 오염(K-1008)보다 앞선다."""
    provider = load_card_provider(KB_CARDS).provider
    question = "베인펌프 소리가 커지고 오일 표면에 우유빛 거품이 있다"
    ids = [card["card_id"] for card in
           provider.search_cards(query=question, equipment_ids=["HPU"])]
    assert ids.index("K-1004") < ids.index("K-1008")

    sent = []
    model = OllamaModel()
    model._post = lambda path, payload: (sent.append(payload), {"message": {"content": json.dumps(
        {"answer": "a", "cited_card_ids": ["K-1004"]})}})[1]
    FixedPipeline(model=model, tools=provider).run(
        {"question": question, "line_id": "LN-0001", "eq_id": "HPU"})
    enum = sent[0]["format"]["properties"]["cited_card_ids"]["items"]["enum"]
    assert enum == ids[:QUERY_MAX_CANDIDATES] and enum[0] == "K-1004"
