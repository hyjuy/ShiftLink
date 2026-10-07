"""answer_mode="extract": query answers come from the rank-1 card (E1) and the model is never called."""
import pytest

from shiftlink.agent.pipeline import FixedPipeline
from test_router_pipeline import RecordingTools

CARD = {"card_id": "K-0001", "title": "펌프 소음", "tacit_type": "T1", "condition_status": "verified",
        "know_how": "흡입관 이음부부터 본다. 거품이 보이면 유면을 확인한다. 셋째 문장.", "safety_flag": False}
QUERY = {"question": "펌프 소음이 커요", "line_id": "L1", "eq_id": "HPU-01"}


class Tools(RecordingTools):
    def search_cards(self, **_):
        return [dict(CARD)]


class Model:
    def __init__(self):
        self.calls = 0

    def __call__(self, **_):
        self.calls += 1
        return {"answer": "모델이 쓴 자유 문장입니다.", "cited_card_ids": ["K-0001"]}


def run(payload=QUERY, **kw):
    model = Model()
    kw.setdefault("judge", lambda q, c: 3)
    result = FixedPipeline(model=model, tools=Tools(), **kw).run(payload)
    return model, result


def test_extract_answers_from_rank1_card_without_calling_the_model():
    model, result = run(answer_mode="extract")
    out = result.output
    assert model.calls == 0
    assert out.cited_card_ids == ["K-0001"] and not out.review_queue and not out.no_knowledge
    assert "흡입관 이음부부터 본다. 거품이 보이면 유면을 확인한다." in out.answer
    assert "모델이" not in out.answer and "셋째" not in out.answer and out.answer.endswith("(K-0001 참조)")
    assert result.tool_results["answer_mode"] == "extract"
    assert [n.card_id for n in out.safety_notices] == ["K-0002"]  # safety notices still come from the cards


def test_extract_still_abstains_when_the_judge_rejects():
    model, result = run(answer_mode="extract", judge=lambda q, c: 1)
    assert model.calls == 0 and result.output.no_knowledge and result.output.cited_card_ids == []


def test_model_mode_is_unchanged():
    model, result = run()
    assert model.calls == 1 and result.output.answer == "모델이 쓴 자유 문장입니다."
    assert "answer_mode" not in result.tool_results


def test_handover_keeps_calling_the_model_in_extract_mode():
    model, result = run({"memo_text": "HPU-01 소음 인계", "shift": "A", "eq_ids": ["HPU-01"]}, answer_mode="extract")
    assert result.mode == "handover" and model.calls == 1


def test_env_selects_mode_and_rejects_unknown_values(monkeypatch):
    monkeypatch.setenv("SHIFTLINK_ANSWER_MODE", "extract")
    assert run()[0].calls == 0
    monkeypatch.setenv("SHIFTLINK_ANSWER_MODE", "nope")
    with pytest.raises(ValueError):
        FixedPipeline(model=Model(), tools=Tools())


def test_demo_query_pipeline_defaults_to_hybrid_with_sft_models(monkeypatch):
    from shiftlink.mes.query import build_query_pipeline
    for name in ("SHIFTLINK_ANSWER_MODE", "SHIFTLINK_QUERY_MODEL", "SHIFTLINK_JUDGE_MODEL"):
        monkeypatch.delenv(name, raising=False)
    pipe = build_query_pipeline()
    assert (pipe.answer_mode, pipe.model.model, pipe.model.judge_model) == ("hybrid", "exaone-sft-answer", "exaone-sft-judge")
    monkeypatch.setenv("SHIFTLINK_ANSWER_MODE", "model")
    assert build_query_pipeline().answer_mode == "model"
