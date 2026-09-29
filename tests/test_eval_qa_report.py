import pytest

from eval.qa.report import render_report, verdict


def item(qid, answerable=True, primary=(), acceptable=()):
    return {
        "qid": qid,
        "eq_id": "HPU",
        "question": "펌프 소리가 거칠다",
        "primary_card_ids": list(primary),
        "acceptable_card_ids": list(acceptable),
    }


def row(qid, score, cited=(), ranked=(), safety=(), answer="답"):
    return {
        "qid": qid,
        "eq_id": "HPU",
        "answer": answer,
        "cited": list(cited),
        "ranked": list(ranked),
        "safety": list(safety),
        "score": score,
    }


def test_verdict_labels():
    assert verdict({"hit": True, "partial": False}) == "hit"
    assert verdict({"hit": False, "partial": True}) == "partial"
    assert verdict({"abstain_ok": True}) == "abstain_ok"
    assert verdict({"hit": False, "partial": False}) == "miss"
    assert verdict({"abstain_ok": False}) == "miss"


def test_wrong_items_first_and_human_blanks():
    result = {
        "summary": {"n": 4, "citation_hit": 0.5, "abstain_ok": 1.0},
        "rows": [
            row("Q-001", {"hit": True, "partial": False}, cited=["K-1004"], ranked=["K-1004", "K-1008", "K-1001", "K-1002"], safety=["K-1006"]),
            row("Q-002", {"hit": False, "partial": True}, cited=["K-1008"], ranked=["K-1008"]),
            row("Q-003", {"hit": False, "partial": False}, cited=["K-1001"], answer="지어낸 압력 12bar"),
            row("Q-004", {"abstain_ok": True}, cited=[]),
        ],
    }
    items = [
        item("Q-001", primary=["K-1004"], acceptable=["K-1008"]),
        item("Q-002", primary=["K-1004"], acceptable=["K-1008"]),
        item("Q-003", primary=["K-1004"]),
        item("Q-004", answerable=False),
    ]
    text = render_report(result, items)
    assert text.startswith("# QA 검수표\n")
    assert "| 인용 적중 | 0.5 |" in text
    order = [text.index(f"## {qid}") for qid in ("Q-002", "Q-003", "Q-001", "Q-004")]
    assert order == sorted(order)
    assert "primary: K-1004 / acceptable: K-1008" in text
    assert "| 실제 인용 | K-1001 |" in text
    assert "| 검색 상위 3 | K-1004, K-1008, K-1001 |" in text
    assert "| 표시된 안전 카드 | K-1006 |" in text
    assert "지어낸 압력 12bar" in text
    assert text.count("- 핵심 사실: [ ] 전부  [ ] 일부  [ ] 없음") == 4
    assert text.count("- 지어낸 내용: [ ] 있음  [ ] 없음") == 4
    assert "| 자동 판정 | partial |" in text
    assert "| 자동 판정 | abstain_ok |" in text


def test_missing_qid_raises():
    with pytest.raises(ValueError, match="Q-009"):
        render_report({"rows": [row("Q-009", {"hit": False})]}, [item("Q-001")])
