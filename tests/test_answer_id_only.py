import pytest

from shiftlink.agent.response import validate_model_output

CARDS = {"cards": [{"card_id": "K-1001", "title": "t", "condition_status": "verified"}]}


@pytest.mark.parametrize("answer", ["K-1001", " K-1001. ", "(K-1001)", "K-1001 참조"])
def test_answer_with_only_card_id_is_rejected(answer):
    errors = validate_model_output({"answer": answer, "cited_card_ids": ["K-1001"]}, CARDS)
    assert any("카드 ID뿐" in e for e in errors)


def test_sentence_answer_is_accepted():
    answer = "펌프 출구 압력이 없으면 압력계 작동부터 확인합니다 (K-1001 참조)."
    assert validate_model_output({"answer": answer, "cited_card_ids": ["K-1001"]}, CARDS) == []
