"""Extractive answer layers E1/E2 (docs/experiments/answer-extractive-prereg-20261006.md)."""

from shiftlink.agent.compose import compose_answer, e1_answer
from shiftlink.agent.response import NO_READING_NOTE, REFERENCE_NOTE, _CARD_ID, _allowed_numbers, _number_tokens

PRESSURE_LOW = {"signal": "hpu_pressure", "label": "압력", "value": 130, "unit": "bar",
                "state": "low", "normal_min": 145, "normal_max": 165}
T1 = {"card_id": "K-1004", "title": "펌프 소음과 거품", "symptom": "소음 증가와 거품", "tacit_type": "T1",
      "know_how": "에어레이션 징후를 먼저 본다. 흡입관 이음부를 점검한다. 세 번째 문장은 나오지 않는다.",
      "condition_status": "verified"}
SAFE = {"card_id": "K-1211", "title": "잔압 확인", "tacit_type": "T5", "safety_flag": True, "condition_status": "verified",
        "know_how": "정비 전에 잔압을 뺀다.", "stop_conditions": ["잔압이 남아 있으면 배관을 풀지 않는다."]}
T3 = {"card_id": "K-1010", "title": "벨트 정렬", "tacit_type": "T3", "condition_status": "verified",
      "know_how": "정렬부터 본다.",
      "type_payload": {"steps": [{"order": 1, "action": "빈 벨트로 운전한다.",
                                  "stop_conditions": ["빈 벨트가 틀어져도 풀리를 조정하지 않는다."]}]}}


def tr(*cards, facts=()):
    return {"ranked_cards": list(cards), "cards": list(cards), "observation_facts": list(facts)}


def run(answer, cards, layers, facts=(), cited=None):
    return compose_answer(answer, cited or [cards[0]["card_id"]], tr(*cards, facts=facts), layers)


def test_e1_uses_only_card_words_first_two_sentences_and_reference():
    out = run("모델이 쓴 자유 문장입니다. 압력이 130으로 높습니다.", [T1], ("E1",))
    assert out.splitlines() == [NO_READING_NOTE, "에어레이션 징후를 먼저 본다. 흡입관 이음부를 점검한다.", "(K-1004 참조)"]
    assert "모델이" not in out and "세 번째" not in out


def test_e1_long_sentences_fall_back_to_first_only():
    card = {**T1, "know_how": ("가" * 130) + ". " + ("나" * 130) + "."}
    assert run("x", [card], ("E1",)).splitlines()[1] == ("가" * 130) + "."


def test_e1_adds_measurement_line_and_card_stop_conditions():
    out = run("x", [T3], ("E1",), facts=[PRESSURE_LOW]).splitlines()
    assert out[0].startswith("현재 압력(hpu_pressure) 130 bar")
    assert out[-2] == "정지 조건: 빈 벨트가 틀어져도 풀리를 조정하지 않는다."
    assert out[-1] == "(K-1010 참조)"


def test_e1_top_level_safety_stop_condition_and_all_cited_ids():
    out = run("x", [T1, SAFE], ("E1",), cited=["K-1004", "K-1211"])
    assert "정지 조건: 잔압이 남아 있으면 배관을 풀지 않는다." in out
    assert out.endswith("(K-1004, K-1211 참조)")


def test_e1_reference_card_gets_reference_note():
    card = {**T1, "condition_status": "reference"}
    assert run("x", [card], ("E1",)).splitlines()[0] == REFERENCE_NOTE


def test_unknown_cited_card_leaves_answer_unchanged():
    assert compose_answer("원래 답", ["K-9999"], tr(T1), ("E1", "E2")) == "원래 답"


def test_e2_keeps_grounded_sentence_and_drops_ungrounded_one():
    answer = "에어레이션 징후와 흡입관 이음부를 점검합니다. 베어링 교체 주기는 6개월입니다."
    out = run(answer, [T1], ("E2",))
    assert "흡입관 이음부를 점검합니다." in out and "교체 주기" not in out
    assert out.endswith("(K-1004 참조)")


def test_e2_drops_unmeasured_direction_claim_even_if_grounded():
    answer = "압력이 높게 측정되어 에어레이션 징후를 점검합니다. 흡입관 이음부를 점검합니다."
    out = run(answer, [T1], ("E2",))
    assert "높게 측정" not in out and "흡입관 이음부를 점검합니다." in out


def test_e2_with_nothing_left_equals_e1():
    answer = "관련 없는 자유 문장입니다. 전혀 다른 이야기입니다."
    assert run(answer, [T1], ("E2",)) == run(answer, [T1], ("E1",))


def test_e2_keeps_card_id_in_kept_sentence_without_double_reference():
    out = run("에어레이션 징후를 점검합니다 (K-1004 참조).", [T1], ("E2",))
    assert out.count("K-1004") == 1


def test_extractive_never_adds_numbers_outside_card_and_facts():
    cards = [T1, {**T3, "know_how": "정렬은 3 mm 이내로 맞춘다."}]
    for card in cards:
        for layer in ("E1", "E2"):
            out = run("모델이 지어낸 99 bar 문장입니다.", [card], (layer,))
            allowed = _allowed_numbers([card["card_id"]], tr(card))
            assert not (_number_tokens(_CARD_ID.sub(" ", out)) - allowed)


def test_e1_ignores_the_model_answer_entirely():
    assert run("A 답", [T1], ("E1",)) == run("전혀 다른 B 답", [T1], ("E1",))
    assert e1_answer([T1], tr(T1)) == run("x", [T1], ("E1",))


FIELD = {"card_id": "K-7000", "title": "HPU-01 유압유 온도 높음 — 팬 차단기 재투입", "tacit_type": "T3",
         "condition_status": "verified", "provenance": {"generator": "field-resolution-v1"},
         "know_how": "팬 차단기 트립 원인 확인 후 재투입\n팬 회전 방향과 소리 확인\n재가동 후 유온 추이 확인",
         "type_payload": {"steps": [
             {"order": 1, "action": "팬 차단기 트립 원인 확인 후 재투입", "expected_result": "팬 다시 돎"},
             {"order": 2, "action": "팬 회전 방향과 소리 확인", "expected_result": "현장 기록에 결과 없음 — 검수 보완"},
             {"order": 3, "action": "재가동 후 유온 추이 확인", "expected_result": "유온 정상, 경보 해제"}]}}


def test_e1_field_card_shows_every_step_with_its_result():
    # 10/13 시험 승격: know_how 앞 두 문장만 써서 3번째 조치가 빠졌다. 현장 카드는 단계를 그대로 쓴다.
    lines = run("x", [FIELD], ("E1",)).splitlines()
    assert lines[1:4] == ["1. 팬 차단기 트립 원인 확인 후 재투입 → 팬 다시 돎",
                          "2. 팬 회전 방향과 소리 확인",  # 빈 결과(검수 보완)는 보이지 않는다
                          "3. 재가동 후 유온 추이 확인 → 유온 정상, 경보 해제"]
    assert lines[-1] == "(K-7000 참조)"
    # 문서에서 만든 T3 카드는 그대로 앞 두 문장
    assert run("x", [T3], ("E1",)).splitlines()[1] == "정렬부터 본다."
