"""Answer composition layers L1~L3 (docs/planning/답변_보정_설계_20261006.md). Failure types ①~⑤ as small cases."""

import json
from pathlib import Path

from shiftlink.agent.compose import compose_answer, layers_from_env
from shiftlink.agent.pipeline import FixedPipeline
from shiftlink.agent.response import (
    DIRECTION_FALLBACK_ANSWER, GUARD_FALLBACK_ANSWER, NO_MEASURE_ANSWER, NO_READING_NOTE, REFERENCE_NOTE,
)
from shiftlink.rag.retrieval import InMemoryToolProvider
from tests.test_retrieval_response import make_card_t1

PRESSURE_LOW = {"signal": "hpu_pressure", "label": "압력", "value": 130, "unit": "bar",
                "state": "low", "normal_min": 145, "normal_max": 165}
VIB_OK = {"signal": "gr_vib_rms", "label": "진동", "value": 1.2, "unit": "mm_s",
          "state": "normal", "normal_min": 0.5, "normal_max": 2.8}
T1 = {"card_id": "K-1004", "tacit_type": "T1", "know_how": "에어레이션 징후를 먼저 본다. 흡입관을 점검한다.",
      "condition_status": "verified"}
T3 = {"card_id": "K-1010", "tacit_type": "T3", "know_how": "정렬부터 본다.", "condition_status": "verified",
      "type_payload": {"steps": [
          {"order": 1, "action": "빈 벨트로 운전한다.", "preconditions": ["아이들러 설치 완료"],
           "stop_conditions": ["빈 벨트가 틀어져도 풀리를 조정해 바로잡으려 하지 않는다(베어링에 무리)."]},
          {"order": 2, "action": "아이들러를 틀어 준다.",
           "preconditions": ["정비 전 스위치를 OFF에 자물쇠로 잠갔다."]}]}}


def tr(*cards, facts=()):
    return {"ranked_cards": list(cards), "cards": list(cards), "observation_facts": list(facts)}


def run(answer, cards, facts=(), layers=("L1", "L2", "L3"), cited=None, errors=()):
    return compose_answer(answer, cited or [cards[0]["card_id"]], tr(*cards, facts=facts), layers, errors)


# ---- L1: ① 측정하지 않은 값을 관측된 것처럼 씀 ----
def test_l1_no_reading_says_so():
    assert run("유량 38 미만이 관찰됩니다.", [T1], layers=("L1",)).splitlines()[0] == NO_READING_NOTE


def test_l1_states_out_of_range_reading_and_skips_normal_ones():
    out = run("압력을 확인하세요.", [T1], facts=[PRESSURE_LOW, VIB_OK], layers=("L1",))
    assert out.splitlines()[0] == "현재 압력(hpu_pressure) 130 bar — 정상 범위 145–165보다 낮음."
    assert "gr_vib_rms" not in out


def test_l1_reads_signals_the_card_conditions_name():
    card = {**T1, "conditions": [{"signal": "gr_vib_rms_state", "op": "==", "value": "high", "unit": None}]}
    out = run("진동을 본다.", [card], facts=[PRESSURE_LOW, VIB_OK], layers=("L1",))
    assert out.splitlines()[0] == "현재 진동(gr_vib_rms) 1.2 mm_s — 정상 범위 0.5–2.8 안."
    assert "hpu_pressure" not in out


def test_l1_reference_card_is_not_compared_with_a_reading():
    card = {**T1, "condition_status": "reference"}
    assert run("20–120 m/min입니다.", [card], facts=[PRESSURE_LOW], layers=("L1",)).splitlines()[0] == REFERENCE_NOTE


# ---- L2: ① ④ 근거 없는 방향 단정 ----
def test_l2_drops_assertion_about_unmeasured_reading_and_falls_back_to_card_sentence():
    out = run("유량이 38 L_min 미만으로 관찰됩니다.", [T1], layers=("L2",))
    assert out == f"{NO_MEASURE_ANSWER} 카드 기준: 에어레이션 징후를 먼저 본다."


def test_l2_keeps_criteria_hedges_and_card_ids():
    answer = "유량이 38 미만이면 K-1004를 확인하세요. K-1004 카드가 높은 우선순위입니다."
    assert run(answer, [T1], layers=("L2",)) == answer


def test_l2_keeps_conditional_and_check_instruction_sentences():
    answer = "온도와 소음이 정상 범위를 벗어나면 주 모터를 끈다. 온도가 58°C를 초과하는지 확인하세요."
    assert run(answer, [T1], layers=("L2",)) == answer


def test_l2_a_leftover_fragment_counts_as_an_empty_summary():
    out = run("베어링 온도가 62°C를 초과하고 있습니다. (K-1004 참조)", [T1], layers=("L2",))
    assert out == f"{NO_MEASURE_ANSWER} 카드 기준: 에어레이션 징후를 먼저 본다."


def test_l2_with_readings_only_drops_signals_nobody_measured():
    answer = "압력이 낮습니다. 온도가 높습니다. 흡입관을 점검하세요."
    out = run(answer, [T1], facts=[PRESSURE_LOW], layers=("L2",))
    assert out == "압력이 낮습니다. 흡입관을 점검하세요."


def test_l2_skips_criterion_questions():
    card = {**T1, "condition_status": "reference"}
    answer = "유량이 38 L_min 미만입니다."
    assert run(answer, [card], layers=("L2",)) == answer


# ---- L3: ② ③ ⑤ 카드의 금지·정지 문장 ----
def test_l3_puts_card_prohibition_and_lockout_first():
    out = run("벨트를 정렬하세요.", [T3], layers=("L3",))
    # the stop condition is also the first prohibition: one sentence. The lockout precondition is not a prohibition.
    assert out.splitlines()[0] == "먼저: 빈 벨트가 틀어져도 풀리를 조정해 바로잡으려 하지 않는다(베어링에 무리). (K-1010)"
    assert out.splitlines()[1] == "벨트를 정렬하세요."


def test_l3_takes_a_second_sentence_from_the_first_stop_condition():
    card = {**T3, "type_payload": {"steps": [
        {"order": 1, "action": "a", "preconditions": ["속도 퓨즈는 분리하지 않는다."],
         "stop_conditions": ["하중 시 사행이 반복되면 슈트를 조정한다."]}]}}
    assert run("점검하세요.", [card], layers=("L3",)).splitlines()[0] == (
        "먼저: 속도 퓨즈는 분리하지 않는다. 하중 시 사행이 반복되면 슈트를 조정한다. (K-1010)")


def test_l3_does_not_repeat_a_sentence_the_answer_already_has():
    answer = "정비 전 스위치를 OFF에 자물쇠로 잠갔다."
    assert "자물쇠" not in run(answer, [T3], layers=("L3",)).splitlines()[0]


def test_l3c_uses_the_cited_card_only():
    other = {**T1, "card_id": "K-1211", "safety_flag": True, "safety_basis": "배관을 열기 전에 감압한다."}
    assert compose_answer("점검하세요.", ["K-1004"], tr(T1, other), ("L3C",)) == "점검하세요."


def test_l3_has_nothing_for_a_card_without_structured_prohibitions():
    assert run("점검하세요.", [T1], layers=("L3",)) == "점검하세요."


def test_l3_safety_basis_fallback_drops_source_citation_and_quotes():
    card = {**T1, "card_id": "K-1003", "safety_flag": True, "safety_basis":
            'Manual.pdf PDF p.7 / 인쇄 p.5 §3.7.2 DANGER: "Overpressure." 릴리프 밸브를 최대 정격 압력보다 높게 설정하지 말 것.'}
    line = run("점검하세요.", [card], layers=("L3",)).splitlines()[0]
    assert line == "먼저: 릴리프 밸브를 최대 정격 압력보다 높게 설정하지 말 것. (K-1003)"
    assert "pdf" not in line.lower() and "§" not in line


def test_l3_adds_one_verified_safety_card_that_was_not_cited():
    other = {**T1, "card_id": "K-1211", "safety_flag": True, "safety_basis": "배관을 열기 전에 감압한다."}
    out = compose_answer("점검하세요.", ["K-1004"], tr(T1, other), ("L3",))
    assert out.splitlines()[0] == "먼저: 배관을 열기 전에 감압한다. (K-1211)"


# ---- #172: 대체 문장은 원인별로 ----
def test_direction_block_gets_its_own_fallback_sentence_and_still_gets_the_facts():
    out = run(GUARD_FALLBACK_ANSWER, [T1], facts=[PRESSURE_LOW], layers=("L1",),
              errors=["압력은 정상 범위보다 낮은데 답이 높다고 말합니다."])
    assert out.splitlines()[-1] == DIRECTION_FALLBACK_ANSWER
    assert out.splitlines()[0].startswith("현재 압력")


def test_number_block_keeps_the_stock_fallback():
    out = run(GUARD_FALLBACK_ANSWER, [T1], layers=("L1",), errors=["카드·질문·측정값에 없는 수치: 24"])
    assert out.splitlines()[-1] == GUARD_FALLBACK_ANSWER


# ---- 스위치 ----
def test_layers_from_env(monkeypatch):
    monkeypatch.setenv("SHIFTLINK_COMPOSE", "l1, L3,l3c,bogus")
    assert layers_from_env() == {"L1", "L3", "L3C"}
    monkeypatch.delenv("SHIFTLINK_COMPOSE")
    assert layers_from_env() == frozenset()


def test_no_layer_leaves_the_answer_alone():
    assert run("아무 문장입니다.", [T3], layers=()) == "아무 문장입니다."


# ---- 파이프라인: 모델 호출은 늘지 않는다 ----
def _provider():
    catalog = json.loads((Path(__file__).resolve().parents[1] /
                          "docs/data/reference/00_plant_and_relations.json").read_text(encoding="utf-8"))
    return InMemoryToolProvider(cards=[make_card_t1("K-0003", equipment="GR")],
                                equipment_db=catalog["equipment"], equipment_types=catalog["equipment_types"])


def _run(layers, mode="query"):
    calls = []

    def model(**kwargs):
        calls.append(kwargs.get("retry", False))
        return {"answer": "점검하세요.", "cited_card_ids": ["K-0003"]}

    payload = {"question": "진동", "line_id": "L1", "eq_id": "GR"}
    if mode == "handover":
        payload = {"mode": "handover", "memo_text": "진동 확인", "line_id": "L1", "eq_ids": ["GR"], "shift": "A"}
    result = FixedPipeline(tools=_provider(), model=model, compose_layers=layers).run(payload)
    return result, calls


def test_pipeline_composes_after_validation_without_extra_model_calls():
    result, calls = _run({"L1"})
    assert calls == [False]
    assert result.output.answer == f"{NO_READING_NOTE}\n점검하세요."


def test_pipeline_default_is_off(monkeypatch):
    monkeypatch.delenv("SHIFTLINK_COMPOSE", raising=False)
    result, _ = _run(None)
    assert result.output.answer == "점검하세요."
