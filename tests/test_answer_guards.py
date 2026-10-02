"""Answer guards: system range judgments, direction words, invented numbers."""

import json
from pathlib import Path

from shiftlink.agent.pipeline import FixedPipeline
from shiftlink.agent.response import validate_model_output
from shiftlink.agent.router import QueryRequest
from shiftlink.edge.ollama import SYSTEM_PROMPT, build_messages
from shiftlink.rag.retrieval import InMemoryToolProvider


def catalog_provider():
    catalog = json.loads((Path(__file__).resolve().parents[1] /
        "docs/data/reference/00_plant_and_relations.json").read_text(encoding="utf-8"))
    return InMemoryToolProvider(
        cards=[], equipment_db=catalog["equipment"], equipment_types=catalog["equipment_types"],
    )


def _card(card_id="K-1216"):
    return {"card_id": card_id, "know_how": "다시 돌린 뒤 온도를 지켜본다.", "condition_status": "verified"}


def test_vibration_in_range_is_injected_as_normal():
    """BN-019: 1.2 mm/s inside 0.5–2.8 must be stated as normal before the model speaks."""
    provider = catalog_provider()
    facts = provider.observation_facts(
        equipment_ids=["GR"],
        observations={"gr_vib_rms": {"value": 1.2, "unit": "mm_s"}},
    )
    assert facts == [{
        "signal": "gr_vib_rms", "value": 1.2, "unit": "mm_s",
        "state": "normal", "normal_min": 0.5, "normal_max": 2.8,
    }]
    request = QueryRequest(
        question="진동 1.2인데 돌려도 되나", line_id="L1", eq_id="GR",
        observations=[{"signal": "gr_vib_rms", "value": 1.2, "unit": "mm_s"}],
    )
    card = {"card_id": "K-0003", "title": "진동", "symptom": "진동", "condition_status": "verified"}
    messages, _ = build_messages("query", request, {
        "cards": [card], "ranked_cards": [card], "observation_facts": facts,
    })
    assert "측정값 판정(시스템 계산, 바꾸지 말 것):" in messages[1]["content"]
    assert "gr_vib_rms 1.2 mm_s → 정상 범위 0.5–2.8 안" in messages[1]["content"]
    handover, _ = build_messages("handover", request, {
        "cards": [card], "ranked_cards": [card], "observation_facts": facts,
    })
    assert "gr_vib_rms 1.2 mm_s → 정상 범위 0.5–2.8 안" in handover[1]["content"]


def test_low_pressure_fact_says_below_range():
    """BC-007: 130 bar is under 145–165, so the injected judgment says low."""
    facts = catalog_provider().observation_facts(
        equipment_ids=["HPU"],
        observations={"hpu_pressure": {"value": 130, "unit": "bar"}},
    )
    assert facts[0]["state"] == "low"
    request = QueryRequest(question="압력", line_id="L1", eq_id="HPU")
    card = {"card_id": "K-0001", "title": "압력", "condition_status": "verified"}
    messages, _ = build_messages("query", request, {
        "cards": [card], "ranked_cards": [card], "observation_facts": facts,
    })
    assert "hpu_pressure 130 bar → 정상 범위 145–165보다 낮음" in messages[1]["content"]


def test_all_normal_direction_words_fail_validation():
    """BN-019 wording: '확인 기준 초과' while the only judgment is normal."""
    tool_results = {
        "ask_text": "진동 1.2인데 돌려도 되나",
        "cards": [_card("K-0003")],
        "safety_cards": [],
        "observation_facts": [{
            "signal": "gr_vib_rms", "value": 1.2, "unit": "mm_s",
            "state": "normal", "normal_min": 0.5, "normal_max": 2.8,
        }],
    }
    errors = validate_model_output({
        "answer": "진동 1.2 mm/s는 확인 기준 초과라 주 모터를 정지하세요.",
        "cited_card_ids": ["K-0003"],
    }, tool_results)
    assert any("정상 범위" in error for error in errors)

    # ponytail ceiling: a low reading called "높게" is not rejected in this version.
    low = dict(tool_results)
    low["observation_facts"] = [{
        "signal": "hpu_pressure", "value": 130, "unit": "bar",
        "state": "low", "normal_min": 145, "normal_max": 165,
    }]
    low_errors = validate_model_output({
        "answer": "130 bar로 높게 측정되었습니다.",
        "cited_card_ids": ["K-0003"],
    }, low)
    assert not any("정상 범위" in error for error in low_errors)


def test_invented_duration_fails_and_card_id_digits_do_not():
    """NH-005: '24시간' is not in the question, reading, or cited card."""
    tool_results = {
        "ask_text": "얼마나 오래 봐야 해요?",
        "cards": [_card()],
        "safety_cards": [],
        "observation_facts": [{
            "signal": "gr_brg_temp", "value": 49, "unit": "degC",
            "state": "normal", "normal_min": 30, "normal_max": 62,
        }],
    }
    errors = validate_model_output({
        "answer": "최소 24시간 이상 관찰하세요.",
        "cited_card_ids": ["K-1216"],
    }, tool_results)
    assert any("24" in error for error in errors)

    ok = validate_model_output({
        "answer": "K-1216을 보세요. 온도 49도는 정상 범위 안입니다.",
        "cited_card_ids": ["K-1216"],
    }, tool_results)
    assert ok == []


def test_numeric_question_rule_is_in_the_query_prompt():
    assert "카드에 수치 기준이 없습니다. 설비 사양서나 담당자에게 확인하세요" in SYSTEM_PROMPT


def test_direction_error_retries_once():
    from tests.test_retrieval_response import make_card_t1
    catalog = json.loads((Path(__file__).resolve().parents[1] /
        "docs/data/reference/00_plant_and_relations.json").read_text(encoding="utf-8"))
    provider = InMemoryToolProvider(
        cards=[make_card_t1(), make_card_t1("K-0003", equipment="GR")],
        equipment_db=catalog["equipment"], equipment_types=catalog["equipment_types"],
    )
    answers = [
        {"answer": "확인 기준 초과입니다.", "cited_card_ids": ["K-0003"]},
        {"answer": "범위 안입니다.", "cited_card_ids": ["K-0003"]},
    ]
    calls = []

    def model(**kwargs):
        calls.append(kwargs)
        return answers[len(calls) - 1]

    result = FixedPipeline(tools=provider, model=model).run({
        "question": "진동", "line_id": "L1", "eq_id": "GR",
        "observations": [{"signal": "gr_vib_rms", "value": 1.2, "unit": "mm_s"}],
    })
    assert [call.get("retry", False) for call in calls] == [False, True]
    assert calls[0]["tool_results"]["observation_facts"][0]["state"] == "normal"
    assert result.output.review_queue is False
    assert result.output.answer == "범위 안입니다."
