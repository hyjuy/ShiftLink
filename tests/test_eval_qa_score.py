from eval.qa.score import score_item, summarize

LABEL = {"answerable": True, "primary_card_ids": ["K-1004"], "acceptable_card_ids": ["K-1008"], "safety_card_ids": ["K-1006"]}


def out(cited, safety=(), ranked=(), no_knowledge=False):
    return {"cited": list(cited), "safety": list(safety), "ranked": list(ranked), "no_knowledge": no_knowledge}


def test_hit_partial_wrong_and_safety():
    s = score_item(LABEL, out(["K-1004", "K-1001"], safety=["K-1006"], ranked=["K-1004", "K-1008"]))
    assert s["hit"] and not s["partial"] and s["safety_ok"]
    assert s["wrong_cite_rate"] == 0.5
    assert s["retrieval_hit_at_1"] and s["retrieval_hit_at_k"]

    s = score_item(LABEL, out(["K-1008"], ranked=["K-1008", "K-1004"]))
    assert not s["hit"] and s["partial"] and not s["safety_ok"]
    assert not s["retrieval_hit_at_1"] and s["retrieval_hit_at_k"]


def test_unanswerable_abstain():
    label = {"answerable": False, "primary_card_ids": [], "acceptable_card_ids": [], "safety_card_ids": []}
    assert score_item(label, out([], no_knowledge=True))["abstain_ok"]
    s = score_item(label, out(["K-1001"]))
    assert not s["abstain_ok"] and s["wrong_cite_rate"] == 1.0


def test_summary_rates_and_latency():
    rows = [
        {"e2e_s": 30.0, "error": None, "review_queue": False, "score": {"hit": True, "partial": False, "retrieval_hit_at_1": True,
                                                                         "retrieval_hit_at_k": True, "wrong_cite_rate": 0.0, "safety_ok": True}},
        {"e2e_s": 5.0, "error": None, "review_queue": False, "score": {"hit": False, "partial": True, "retrieval_hit_at_1": False,
                                                                        "retrieval_hit_at_k": True, "wrong_cite_rate": 1.0, "safety_ok": True}},
        {"e2e_s": 7.0, "error": None, "review_queue": True, "score": {"abstain_ok": False, "wrong_cite_rate": 1.0, "safety_ok": False}},
    ]
    s = summarize(rows)
    assert (s["answerable"], s["unanswerable"]) == (2, 1)
    assert s["citation_hit"] == 0.5 and s["abstain_ok"] == 0.0 and s["review_queue"] == 1
    assert s["cold_s"] == 30.0 and s["p50_s"] == 5.0 and s["p95_s"] == 7.0  # warm excludes the first row
