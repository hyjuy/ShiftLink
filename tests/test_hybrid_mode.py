"""answer_mode="hybrid": the model writes the answer; the H guard falls back to E1 for restart/charge/open advice
on a card that holds or prohibits it (pre-registered 10/6). Handover and extract/model modes are unchanged."""
import pytest

from shiftlink.agent.compose import hybrid_needs_e1
from shiftlink.agent.pipeline import FixedPipeline
from test_router_pipeline import RecordingTools

HOLD_CARD = {"card_id": "K-0001", "title": "재가동 보류", "tacit_type": "T1", "condition_status": "verified",
             "know_how": "승인 전까지 재기동을 보류한다. 원인을 먼저 확인한다. 셋째 문장.", "safety_flag": False}
FREE_CARD = {**HOLD_CARD, "know_how": "필터를 교체한다. 압력을 다시 읽는다. 셋째 문장."}
QUERY = {"question": "멈춘 설비를 다시 켜도 돼요", "line_id": "L1", "eq_id": "HPU-01"}


def tools_with(card):
    class Tools(RecordingTools):
        def search_cards(self, **_):
            return [dict(card)]
    return Tools()


class Model:
    def __init__(self, answer):
        self.answer, self.calls = answer, 0

    def __call__(self, **_):
        self.calls += 1
        return {"answer": self.answer, "cited_card_ids": ["K-0001"]}


def run(answer, card=HOLD_CARD, **kw):
    model = Model(answer)
    kw.setdefault("judge", lambda q, c: 3)
    result = FixedPipeline(model=model, tools=tools_with(card), answer_mode="hybrid", **kw).run(QUERY)
    return model, result


@pytest.mark.parametrize("answer, card, expected", [
    ("한 번 더 식혀서 돌려 보세요.", HOLD_CARD, True),
    ("프로젝트 계통압 155 bar로 충전합니다.", HOLD_CARD, True),
    ("승인 전까지 재기동하지 마세요.", HOLD_CARD, False),          # negation in the same sentence
    ("한 번 더 식혀서 돌려 보세요.", FREE_CARD, False),             # the card holds nothing
    ("필터를 교체하고 압력을 확인하세요.", HOLD_CARD, False),      # no restart/charge/open advice
])
def test_guard_rule(answer, card, expected):
    assert hybrid_needs_e1(answer, card) is expected


def test_safe_model_answer_is_kept_with_one_model_call():
    model, result = run("원인을 먼저 확인하고 승인을 받으세요.")
    out = result.output
    assert model.calls == 1 and out.answer == "원인을 먼저 확인하고 승인을 받으세요."
    assert result.tool_results["answer_mode"] == "hybrid" and "hybrid_fallback" not in result.tool_results


def test_restart_advice_on_a_holding_card_becomes_the_e1_answer():
    model, result = run("한 번 더 식혀서 돌려 보세요.")
    out = result.output
    assert model.calls == 1
    assert "승인 전까지 재기동을 보류한다." in out.answer and "돌려 보세요" not in out.answer
    assert out.answer.endswith("(K-0001 참조)") and out.cited_card_ids == ["K-0001"] and not out.review_queue


def test_blank_or_blocked_model_result_ends_as_e1():
    class Failing:
        calls = 0

        def __call__(self, **_):
            Failing.calls += 1
            raise ValueError("bad format")

    model = Failing()
    result = FixedPipeline(model=model, tools=tools_with(FREE_CARD), answer_mode="hybrid", judge=lambda q, c: 3).run(QUERY)
    out = result.output
    assert Failing.calls == 2  # one retry, then the E1 fallback
    assert out.answer.endswith("(K-0001 참조)") and "필터를 교체한다." in out.answer and not out.review_queue
    assert result.tool_results["hybrid_fallback"]


def test_hybrid_still_abstains_when_the_judge_rejects():
    model, result = run("아무 답", judge=lambda q, c: 1)
    assert model.calls == 0 and result.output.no_knowledge


def test_handover_is_unchanged_in_hybrid_mode():
    model = Model("인계 요약")
    result = FixedPipeline(model=model, tools=tools_with(FREE_CARD), answer_mode="hybrid", judge=lambda q, c: 3).run(
        {"memo_text": "HPU-01 소음 인계", "shift": "A", "eq_ids": ["HPU-01"]})
    assert result.mode == "handover" and model.calls == 1
    assert "answer_mode" not in result.tool_results
