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
    "K-1001 참조", "카드 K-1001", "참고: K-1001", "K-1001 확인",
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

@pytest.mark.parametrize("invalid_answer", ["K-0001", "K-0001 확인", "카드 내용을 근거로 질문에 답하는 한국어 요약 문장"])
@pytest.mark.parametrize("adapter", [False, True])
@pytest.mark.parametrize("recover", [False, True])
def test_pipeline_retries_id_only_then_recovers_or_holds(adapter, recover, invalid_answer):
    calls = []
    def model(**kwargs):
        calls.append(kwargs.get("retry", False))
        output = {"answer": "정지 후 점검하세요." if recover and len(calls) == 2 else invalid_answer,
                  "cited_card_ids": ["K-0001"]}
        return _parse_output({"message": {"content": json.dumps(output)}}) if adapter else output

    result = FixedPipeline(model=model, tools=RecordingTools()).run(
        {"question": "압력 저하 원인은?", "line_id": "L1", "eq_id": "HPU-01"}
    )
    assert calls == [False, True]
    assert result.output.review_queue is (not recover)
    assert result.output.answer == ("정지 후 점검하세요." if recover else "")
    assert not result.output.no_knowledge

@pytest.mark.parametrize("answer", [
    "K-1001 참조", "카드 K-1001", "참고: K-1001", "K-1001 확인",
    "카드 내용을 근거로 질문에 답하는 한국어 요약 문장",
])
def test_adapter_rejects_id_noise_and_copied_example(answer):
    with pytest.raises(ValueError):
        _parse_output({"message": {"content": json.dumps(
            {"answer": answer, "cited_card_ids": ["K-1001"]})}})

@pytest.mark.parametrize("answer", [
    "K-1001에 따라 펌프 압력을 확인하세요.",
    "압력계 작동부터 확인합니다 (K-1001 참조).", "필터 확인 (K-1001)",
])
def test_id_noise_check_preserves_actual_instructions(answer):
    assert validate_model_output(
        {"answer": answer, "cited_card_ids": ["K-1001"]},
        {"cards": [{"card_id": "K-1001"}]},
    ) == []

LIVE_PARTIAL_ANSWER = "기어·베인 펌프의 출구 압력이 없을 때는 우선 펌프 출구 압력의 존재 여부를 확인하고, 축의 회전 상태를 관찰합니다. 무부하 상태인지 확인한 후 펌프의 동작 여부를 점검합니다. 그 다음 구동 회전 방향이 올바르게 설정되었는지 확인하고, 필요하다면 조립 상태를 재확인합니다. 프라이밍 과정"

def test_adapter_rejects_live_answer_cut_at_char_limit():
    assert len(LIVE_PARTIAL_ANSWER) == 160
    with pytest.raises(ValueError):
        _parse_output({"message": {"content": json.dumps(
            {"answer": LIVE_PARTIAL_ANSWER, "cited_card_ids": ["K-1001"]})}})

def test_pipeline_retries_live_partial_answer_into_complete_sentences():
    calls = []
    def model(**kwargs):
        calls.append(kwargs.get("retry", False))
        return {"answer": LIVE_PARTIAL_ANSWER if len(calls) == 1 else "정지 후 점검하세요.",
                "cited_card_ids": ["K-0001"]}
    result = FixedPipeline(model=model, tools=RecordingTools()).run(
        {"question": "압력 저하 원인은?", "line_id": "L1", "eq_id": "HPU-01"})
    assert calls == [False, True]
    assert result.output.answer == "정지 후 점검하세요."
    assert not result.output.review_queue
