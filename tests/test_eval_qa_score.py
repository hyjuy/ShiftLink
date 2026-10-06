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


def test_execution_error_is_not_abstain_success():
    label = {"answerable": False, "primary_card_ids": [], "acceptable_card_ids": [], "safety_card_ids": []}
    assert not score_item(label, out([]), error="RuntimeError: down")["abstain_ok"]

    class Boom:
        def run(self, payload):
            raise RuntimeError("down")

    item = {
        "qid": "Q-000", "eq_id": "HPU-01", "question": "막힌 질문", "observations": {},
        "answerable": False, "primary_card_ids": [], "acceptable_card_ids": [], "safety_card_ids": [],
    }
    rows = run([item], Boom())
    assert rows[0]["error"].startswith("RuntimeError")
    assert rows[0]["cited"] == []
    assert rows[0]["score"]["abstain_ok"] is False
    assert summarize(rows)["abstain_ok"] == 0.0 and summarize(rows)["errors"] == 1


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


# --- 10/6 final-scoring preparation: judge score/answer mode recorded, strict judge failures are errors, config + .INVALID ---
ITEM = {"qid": "X-1", "eq_id": "HPU-01", "question": "펌프 소음이 커요", "observations": {}, "answerable": True,
        "primary_card_ids": ["K-1004"], "acceptable_card_ids": [], "safety_card_ids": []}


def pipeline(judge, strict=False, **kw):
    provider = load_card_provider(KB).provider

    def model(**_):
        return {"answer": "흡입관 이음부부터 확인하세요.", "cited_card_ids": ["K-1004"]}

    return FixedPipeline(model=model, tools=provider, judge=judge, judge_strict=strict, **kw)


def test_rows_record_judge_score_and_answer_mode():
    [row] = run([ITEM], pipeline(lambda q, c: 3, answer_mode="extract"))
    assert row["judge_score"] == 3 and row["answer_mode"] == "extract" and row["error"] is None


def test_strict_judge_failure_is_recorded_as_an_error_not_an_abstain():
    def broken(q, c):
        raise ConnectionError("HTTP 404 model not found")

    [row] = run([{**ITEM, "answerable": False, "primary_card_ids": []}], pipeline(broken, strict=True))
    assert row["error"].startswith("JudgeUnavailableError")
    assert not row["score"]["abstain_ok"]  # a crash must not look like a correct abstain
    [loose] = run([ITEM], pipeline(broken, strict=False))
    assert loose["error"] is None  # evaluation scripts keep the old fall-through unless --judge-strict


def test_main_writes_config_and_marks_a_judge_failure_invalid(tmp_path, monkeypatch):
    import sys
    from eval.qa import score

    qa = tmp_path / "qa.json"
    qa.write_text(json.dumps([ITEM]), encoding="utf-8")
    monkeypatch.setattr(score.OllamaModel, "judge", lambda self, q, c: (_ for _ in ()).throw(ConnectionError("down")))
    monkeypatch.setattr(score.OllamaModel, "_post", lambda self, *a, **k: (_ for _ in ()).throw(ConnectionError("down")))
    out_path = tmp_path / "out.json"
    monkeypatch.setattr(sys, "argv", ["score", str(qa), "--host", "http://127.0.0.1:9", "--model", "m", "--out", str(out_path), "--judge-strict"])
    try:
        score.main()
    except SystemExit as exit_:
        assert "INVALID" in str(exit_)
    report = json.loads(out_path.read_text(encoding="utf-8"))
    assert report["summary"]["judge_failures"] == 1
    assert report["config"]["judge_strict"] is True and report["config"]["answer_model"] == "m"
    assert set(report["config"]) >= {"answer_mode", "judge_model", "num_ctx", "judge_num_ctx", "model_digests", "compose_layers"}
    assert (tmp_path / "out.json.INVALID").exists()
