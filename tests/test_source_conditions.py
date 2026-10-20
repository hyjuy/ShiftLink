"""R5 source matching and non-mutating rendering; no model or external services."""
import copy
import json
from pathlib import Path

import pytest

from shiftlink.rag2.source_conditions import NOTICE, VERSION, with_source_conditions

ROOT = Path(__file__).resolve().parents[1]
CARDS = json.loads((ROOT / "docs/data/knowledge_cards/kb/kb_cards.json").read_text(encoding="utf-8"))["cards"]


def evidence(cid):
    card = next(c for c in CARDS if c["card_id"] == cid)
    return {"chunk_id": f"card_{cid}", "text": card["know_how"], "metadata": {"kind": "card", "source": cid}}


@pytest.mark.parametrize("cid,required", [
    ("K-1012", ["MISUMI", "지정 장력 조정 나사", "확인되지 않으면", "정비 담당자"]),
    ("K-1027", ["모터 전원을 차단", "재기동을 막은 뒤", "감속기가 식은", "작업 승인"]),
])
def test_exact_conditions_precede_unchanged_answer(cid, required):
    ev = [evidence(cid)]
    snapshot = copy.deepcopy((ev, CARDS))
    original = "관찰하고 기록합니다 [S1]."
    answer, applied = with_source_conditions(original, ["S1"], ev, CARDS)
    assert applied == [cid] and answer.endswith(NOTICE + "\n" + original)
    assert all(t in answer.split(NOTICE)[0] for t in required)
    assert (ev, CARDS) == snapshot


@pytest.mark.parametrize("case", ["not_cited", "event", "manual", "other_card", "stale_chunk", "unknown_revision", "wrong_chunk_id", "missing_condition"])
def test_no_application_to_unmatched_source(case):
    ev = [evidence("K-1027")]
    cards = copy.deepcopy(CARDS)
    cites = ["S1"]
    if case == "not_cited":
        cites = ["S2"]
    elif case in ("event", "manual"):
        ev[0]["metadata"]["kind"] = case
    elif case == "other_card":
        ev = [evidence("K-1005")]
    elif case == "stale_chunk":
        ev[0]["text"] = "이전 색인"
    elif case == "unknown_revision":
        next(c for c in cards if c["card_id"] == "K-1027")["version"] = "other"
    elif case == "wrong_chunk_id":
        ev[0]["chunk_id"] = "event_K-1027_c00"
    else:
        c = next(c for c in cards if c["card_id"] == "K-1027")
        c["know_how"] = c["know_how"].replace("재기동을 막은 뒤", "")
        ev[0]["text"] = c["know_how"]
    assert with_source_conditions("원래 답", cites, ev, cards) == ("원래 답", [])


def test_citation_number_and_order():
    ev = [evidence("K-1005"), evidence("K-1012"), evidence("K-1027")]
    answer, applied = with_source_conditions("원문 [S2][S3]", ["S3", "S2", "S2"], ev, CARDS)
    assert applied == ["K-1012", "K-1027"]
    assert answer.index("[S2]") < answer.index("[S3]") < answer.index(NOTICE)
    assert "[S1]" not in answer


def test_empty_answer_and_unreviewed_card_unchanged():
    assert with_source_conditions("", ["S1"], [evidence("K-1027")], CARDS) == ("", [])
    assert with_source_conditions("원문", ["S0", "S99", "Sx"], [evidence("K-1027")], CARDS) == ("원문", [])
    assert next(c for c in CARDS if c["card_id"] == "K-1027")["version"] == VERSION


def test_cv_does_not_invent_generic_approval_or_power_isolation():
    answer, _ = with_source_conditions("원문", ["S1"], [evidence("K-1012")], CARDS)
    assert "작업 승인" not in answer and "전원을 차단" not in answer
