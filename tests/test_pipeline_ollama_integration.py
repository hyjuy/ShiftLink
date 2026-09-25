"""Exercise the real pipeline and Ollama adapter together without a model server."""

import io
import json
import socket

import pytest
from pydantic import ValidationError

from shiftlink.agent.pipeline import FixedPipeline
from shiftlink.agent.response import render_response
from shiftlink.edge.__main__ import DEFAULT_FIXTURE, build_provider, load_case
from shiftlink.edge.ollama import OllamaModel


class FakeOllama:
    def __init__(self, *, cited_id="K-0108", error=None):
        self.cited_id = cited_id
        self.error = error
        self.calls = []

    def __call__(self, request, timeout=None):
        self.calls.append(json.loads(request.data))
        if self.error:
            raise self.error
        content = json.dumps({"answer": "근거 카드에 따른 답변", "cited_card_ids": [self.cited_id]})
        body = {"message": {"content": content}, "load_duration": 0, "eval_count": 1}
        return io.BytesIO(json.dumps(body).encode())


def run_case(monkeypatch, case_id, fake, *, payload=None):
    monkeypatch.setattr("urllib.request.urlopen", fake)
    case = load_case(DEFAULT_FIXTURE, case_id)
    pipeline = FixedPipeline(model=OllamaModel(), tools=build_provider(case))
    return pipeline.run(payload or case["input"])


def test_real_pipeline_and_adapter_render_valid_answer(monkeypatch):
    fake = FakeOllama()
    result = run_case(monkeypatch, "F-e2e-001", fake)
    assert len(fake.calls) == 1
    assert not result.output.review_queue
    assert result.output.cited_card_ids == ["K-0108"]
    assert "## 답변" in render_response(result.output)


def test_empty_kb_skips_adapter(monkeypatch):
    fake = FakeOllama()
    result = run_case(monkeypatch, "F-e2e-002", fake)
    assert fake.calls == []
    assert result.output.no_knowledge


def test_invalid_observation_stops_before_adapter(monkeypatch):
    fake = FakeOllama()
    case = load_case(DEFAULT_FIXTURE, "F-e2e-001")
    payload = {**case["input"], "observations": [{"signal": "pressure"}]}
    with pytest.raises(ValidationError):
        run_case(monkeypatch, "F-e2e-001", fake, payload=payload)
    assert fake.calls == []


def test_invalid_citation_retries_once_then_holds(monkeypatch):
    fake = FakeOllama(cited_id="K-9999")
    result = run_case(monkeypatch, "F-e2e-001", fake)
    assert len(fake.calls) == 2
    assert "[재시도]" in fake.calls[1]["messages"][1]["content"]
    assert result.output.review_queue
    assert result.output.answer == ""


def test_timeout_holds_without_retry(monkeypatch):
    fake = FakeOllama(error=socket.timeout("timed out"))
    result = run_case(monkeypatch, "F-e2e-001", fake)
    assert len(fake.calls) == 1
    assert result.output.review_queue
    assert result.output.validation_errors == ["모델 요청 시간 초과"]
