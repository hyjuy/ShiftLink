"""Regression for syntactically valid answers containing only card IDs."""
import json

import pytest

from shiftlink.agent.pipeline import FixedPipeline
from shiftlink.agent.response import validate_model_output
from shiftlink.edge.ollama import _parse_output
from test_router_pipeline import RecordingTools

@pytest.mark.parametrize("answer", [
    "K-1001", " K-1001 ", "[K-1001]", "K-1001, K-1002",
    "`K-1001`", "K-9999", "K-1001\nK-1002",
])
def test_id_only_answer_is_rejected_by_shared_validator(answer):
    errors = validate_model_output(
        {"answer": answer, "cited_card_ids": ["K-1001"]},
        {"cards": [{"card_id": "K-1001"}]},
    )
    assert any("본문" in error for error in errors)

def test_prose_with_inline_card_id_is_allowed():
    assert validate_model_output(
        {"answer": "K-1001에 따라 정지 후 점검하세요.", "cited_card_ids": ["K-1001"]},
        {"cards": [{"card_id": "K-1001"}]},
    ) == []

@pytest.mark.parametrize("adapter", [False, True])
@pytest.mark.parametrize("recover", [False, True])
def test_pipeline_retries_id_only_then_recovers_or_holds(adapter, recover):
    calls = []
    def model(**kwargs):
        calls.append(kwargs.get("retry", False))
        output = {"answer": "정지 후 점검하세요." if recover and len(calls) == 2 else "K-0001",
                  "cited_card_ids": ["K-0001"]}
        return _parse_output({"message": {"content": json.dumps(output)}}) if adapter else output

    result = FixedPipeline(model=model, tools=RecordingTools()).run(
        {"question": "압력 저하 원인은?", "line_id": "L1", "eq_id": "HPU-01"}
    )
    assert calls == [False, True]
    assert result.output.review_queue is (not recover)
    assert result.output.answer == ("정지 후 점검하세요." if recover else "")
    assert not result.output.no_knowledge
