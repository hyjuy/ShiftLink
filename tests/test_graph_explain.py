"""Explain-only graph binding: real artifact, fail-closed metadata, unchanged answer."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from shiftlink.rag.graph_explain import explain
from shiftlink.agent.schemas import KnowledgeCard
from test_work_report_reuse_harness import service

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "docs/demo/kg/build"
CARDS = json.loads((ROOT / "docs/data/knowledge_cards/kb/kb_cards.json").read_text(encoding="utf-8"))["cards"]
CARD = next(c for c in CARDS if c["card_id"] == "K-1004")
OUTPUT = {"answer": "원래 답변", "cited_card_ids": ["K-1004"]}


def call(output=None, cards=None, **kw):
    return explain(output or OUTPUT, cards if cards is not None else CARDS, "HPU", "EQ-0001", mode="explain", **kw)


def test_off_never_loads_graph(tmp_path):
    assert explain(OUTPUT, [], "HPU", "EQ-0001", mode="off", path=tmp_path / "missing") is None


def test_real_artifact_exact_card_and_locators_without_mutation():
    output, cards = deepcopy(OUTPUT), deepcopy(CARDS)
    result = call(output, [KnowledgeCard.model_validate(c) for c in cards])
    assert result["status"] == "ok"
    assert result["graph_sha256"] == hashlib.sha256((BUILD / "graph.json").read_bytes()).hexdigest()
    item, = result["cards"]
    assert item["card_id"] == "K-1004" and item["version"] == CARD["version"]
    assert item["symptom_candidates"][0]["review_status"] == "needs_review"
    assert {loc for ref in item["citations"] for loc in ref["locators"]} == {
        src["locator"] for src in CARD["provenance"]["sources"] if src.get("document_version")}
    assert result["retrieval_used"] is False and result["synthetic_assets_used"] is False
    assert cards == CARDS and output == OUTPUT


@pytest.mark.parametrize("damage", ["version", "content", "scope", "rejected", "duplicate", "absent"])
def test_stale_or_ineligible_card_not_explained(damage):
    cards = [deepcopy(CARD)]
    if damage == "version": cards[0]["version"] += "-new"
    if damage == "content": cards[0]["know_how"] += "다른 조치"
    if damage == "scope": cards[0]["mes_equipment_id"] = "EQ-9999"
    if damage == "rejected": cards[0]["status"] = "rejected"
    if damage == "duplicate": cards *= 2
    if damage == "absent": cards = []
    result = call(cards=cards)
    assert result["status"] == "unmatched" and result["cards"] == []


@pytest.mark.parametrize("flags", [{"no_knowledge": True}, {"review_queue": True}, {"validation_errors": ["bad"]}])
def test_withheld_answers_never_get_successful_graph_context(flags):
    result = call({**OUTPUT, **flags})
    assert result["status"] == "withheld" and result["cards"] == []


def test_safety_null_and_unversioned_sources_stay_held():
    ids = [c["card_id"] for c in CARDS if c["equipment"] in ("HPU", "COMMON")]
    result = call({"answer":"answer", "cited_card_ids":ids})
    for item in result["cards"]:
        card = next(c for c in CARDS if c["card_id"] == item["card_id"])
        if card["safety_flag"] or card["symptom"] is None: assert item["symptom_candidates"] == []
        assert item["held_citations"] == [s for s in card["provenance"]["sources"] if not s.get("document_version")]
    assert sum(len(c["held_citations"]) for c in result["cards"]) == 42


@pytest.mark.parametrize("damage", ["missing", "invalid_json", "hash", "duplicate", "endpoint", "domain", "schema"])
def test_bad_artifact_returns_unavailable_without_changing_answer(tmp_path, damage):
    graph = json.loads((BUILD / "graph.json").read_text(encoding="utf-8"))
    report = json.loads((BUILD / "validation.json").read_text(encoding="utf-8"))
    if damage == "duplicate": graph["nodes"].append(deepcopy(graph["nodes"][0]))
    if damage == "endpoint": graph["edges"][0]["target"] = "missing"
    if damage == "domain": graph["edges"][0]["type"] = "INSTANCE_OF"
    if damage == "schema": report["schema_version"] = "other"
    raw = json.dumps(graph, ensure_ascii=False).encode()
    report["graph_sha256"] = "wrong" if damage == "hash" else hashlib.sha256(raw).hexdigest()
    if damage != "missing": (tmp_path / "graph.json").write_bytes(b"bad" if damage == "invalid_json" else raw)
    (tmp_path / "validation.json").write_text(json.dumps(report), encoding="utf-8")
    output = deepcopy(OUTPUT);result = call(output, path=tmp_path / "graph.json")
    assert result["status"] == "unavailable" and result["cards"] == [] and output == OUTPUT


def test_legacy_s30h_chunk_requires_current_full_know_how():
    chunk = {"metadata":{"kind":"card", "source":"K-1004"}, "text":CARD["know_how"]}
    assert call(cited_chunks=[chunk])["status"] == "ok"
    assert call(cited_chunks=[])["cards"] == []
    assert call(cited_chunks=[{**chunk,"text":"old card text"}])["cards"] == []
    chunk["metadata"]["version"] = "old"
    assert call(cited_chunks=[chunk])["cards"] == []


def test_query_context_is_additive_and_persisted(service, monkeypatch):
    from shiftlink.agent.response import AgentResponse
    from shiftlink.mes.query import query_service
    payloads = []
    pipe = SimpleNamespace(cards=CARDS, run=lambda payload: payloads.append(deepcopy(payload)) or
                           SimpleNamespace(output=AgentResponse(mode="query", **OUTPUT)))
    service.query_pipeline = pipe
    body = {"question":"펌프 소음과 거품", "equipment_id":"EQ-0001"}
    monkeypatch.setenv("SHIFTLINK_KG_MODE", "off")
    baseline = query_service(service, body)
    monkeypatch.setenv("SHIFTLINK_KG_MODE", "explain")
    actual = query_service(service, body)
    assert actual.pop("graph_context")["status"] == "ok" and actual == baseline
    assert payloads[0] == payloads[1]
    saved = service.query(body)
    assert service.storage.get_query(saved["query_id"])["payload"]["graph_context"] == saved["graph_context"]


# Use the actual S30h evidence selection and judge gates, with deterministic model calls.
from test_s30h import pipe, E, G


@pytest.mark.parametrize("depth", ["1", "2"])
def test_s30h_explain_does_not_change_prompt_rank_or_output(service, pipe, monkeypatch, depth):
    monkeypatch.setenv("SHIFTLINK_KG_DEPTH", depth)
    pipe.cards = deepcopy(CARDS)
    pipe.rows[1]["metadata"]["source"] = "K-1004"
    pipe.rows[1]["text"] = CARD["know_how"]
    service.query_pipeline = pipe
    monkeypatch.setattr(E, "judge_dist", lambda question, row, *a, **kw:
                        [0, 0, 1, 0] if row["chunk_id"] == "c2" else [1, 0, 0, 0])
    prompts = []
    monkeypatch.setattr(G, "ask_raw", lambda prompt, *a, **kw: prompts.append(prompt) or
        {"raw":json.dumps({"insufficient_evidence":False,"answer":"원문을 확인합니다 [S1]","citations":["S1"]})})
    from shiftlink.mes.query import query_service
    body = {"question":"펌프 소음과 거품", "equipment_id":"EQ-0001"}
    monkeypatch.setenv("SHIFTLINK_KG_MODE", "off");off = query_service(service, body)
    monkeypatch.setenv("SHIFTLINK_KG_MODE", "explain");on = query_service(service, body)
    assert on.pop("graph_context")["status"] == "ok"
    off["s30h_trace"].pop("seconds");on["s30h_trace"].pop("seconds")
    assert off == on and prompts[0] == prompts[1]
    monkeypatch.setattr(E, "judge_dist", lambda *a, **kw: [1, 0, 0, 0])
    blocked = query_service(service, body)
    assert blocked["no_knowledge"] and blocked["graph_context"]["status"] == "withheld"
    assert len(prompts) == 2


def test_missing_graph_does_not_change_mes_answer_or_evidence(service, monkeypatch, tmp_path):
    from shiftlink.agent.response import AgentResponse
    from shiftlink.mes.query import query_service
    service.query_pipeline = SimpleNamespace(cards=CARDS, run=lambda payload:
        SimpleNamespace(output=AgentResponse(mode="query", **OUTPUT)))
    body = {"question":"펌프 이상", "equipment_id":"EQ-0001"}
    monkeypatch.setenv("SHIFTLINK_KG_MODE", "off");off = query_service(service, body)
    monkeypatch.setenv("SHIFTLINK_KG_MODE", "explain")
    monkeypatch.setenv("SHIFTLINK_KG_PATH", str(tmp_path / "missing.json"))
    on = query_service(service, body)
    assert on.pop("graph_context")["status"] == "unavailable" and off == on



def test_request_views_and_returned_metadata_are_isolated():
    result = call();result["cards"][0]["citations"].clear()
    again = call();assert again["cards"][0]["citations"]
    assert call(cards=[])["cards"] == []
    assert explain(OUTPUT, CARDS, "GR", "EQ-0004", mode="explain")["cards"] == []
    assert explain(OUTPUT, CARDS, None, "EQ-0001", mode="explain")["cards"] == []
    assert explain(OUTPUT, CARDS, "HPU", "EQ-0001", mode="retrieve")["reason"] == "unsupported_mode"
    assert call({"answer":"매뉴얼 답변","cited_card_ids":[]})["status"] == "empty"
