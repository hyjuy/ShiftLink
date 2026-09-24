"""가짜 HTTP 응답으로 Ollama 어댑터의 계약을 검증한다. 실제 모델을 부르지 않는다."""

import io
import json
import socket
import urllib.error

import pytest

from shiftlink.agent.router import QueryRequest
from shiftlink.edge.ollama import (
    CANARY_PREFIXES,
    MODEL_CARD_FIELDS,
    OllamaModel,
    build_messages,
    card_context,
)


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
        "provenance": {"seed_ids": ["SD-001"], "persona_id": "V-03"},
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
    assert sent["options"] == {"temperature": 0, "num_ctx": 2048}
    # A의 validate_model_output과 같은 제약을 모델 쪽에도 걸어야 재시도가 줄어든다.
    schema = sent["format"]
    assert schema["required"] == ["answer", "cited_card_ids"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["answer"]["minLength"] == 1
    cited = schema["properties"]["cited_card_ids"]
    assert cited["minItems"] == 1 and cited["uniqueItems"] is True
    assert cited["items"]["pattern"] == r"^K-\d{4}$"


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


def test_handover_mode_is_rejected_not_silently_answered(monkeypatch):
    """계약 §2: handover를 query처럼 처리하면 안 된다. 모델도 부르지 않는다."""
    fake = FakeHTTP(json.dumps({"answer": "a", "cited_card_ids": []}))
    with pytest.raises(NotImplementedError):
        call(monkeypatch, fake, mode="handover")
    assert fake.calls == []


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
