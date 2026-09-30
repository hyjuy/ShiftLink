import json
from pathlib import Path

from eval.qa.score import KB, payload, run, score_item, summarize
from shiftlink.agent.pipeline import FixedPipeline
from shiftlink.edge.ollama import OllamaModel
from shiftlink.rag.loader import load_card_provider

T4_DEV = Path(__file__).resolve().parents[1] / "eval/qa/20260930-T4/qa_dev_t4.json"

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


def test_handover_mode_sends_memo_and_keeps_handover_method():
    item = json.loads(T4_DEV.read_text(encoding="utf-8"))[0]
    assert payload(item, "handover", "B") == {"memo_text": item["question"], "shift": "B", "eq_ids": [item["eq_id"]]}

    sent = []

    def post(path, body):
        sent.append(body)
        first = body["format"]["properties"]["cited_card_ids"]["items"]["enum"][0]
        return {"message": {"content": json.dumps({"answer": "인계 요지", "cited_card_ids": [first]})}}

    model = OllamaModel()
    model._post = post
    rows = run([item], FixedPipeline(model=model, tools=load_card_provider(KB).provider), mode="handover")

    assert "인계 메모:" in sent[0]["messages"][1]["content"]
    assert rows[0]["error"] is None and rows[0]["cited"]
    assert rows[0]["handover_method"]["recipient_role"]
    assert "hit" in rows[0]["score"]


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
