"""Two-hop metadata is reference context, never answer evidence or retrieval."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from shiftlink.rag.graph_explain import explain
from shiftlink.agent.response import AgentResponse
from test_graph_explain import CARDS, BUILD
from test_work_report_reuse_harness import service


def two_hop(ids=("K-1201",), cards=None, **kw):
    return explain({"answer": "unchanged", "cited_card_ids": list(ids)},
                   CARDS if cards is None else cards, "HPU", "EQ-0001", mode="explain", depth=2, **kw)


def related(result):
    return [c for root in result["cards"] for c in root["related_cards"]]


def test_two_hop_shared_symptom_and_document_are_deduplicated_and_directional():
    result = two_hop()
    assert result["depth"] == 2 and result["retrieval_used"] is False
    root, = result["cards"]
    other, = related(result)
    assert other["card_id"] == "K-1202"
    assert {p["relation"] for p in other["paths"]} == {"CITES", "DESCRIBES_SYMPTOM"}
    graph = json.loads((BUILD / "graph.json").read_text(encoding="utf-8"))
    edges = {(e["source"], e["target"], e["type"]) for e in graph["edges"]}
    for path in other["paths"]:
        assert len(path["nodes"]) == 3 and len(path["edges"]) == 2
        a, b = path["edges"]
        assert a["source"] == root["node_id"] and b["source"] == other["node_id"]
        assert a["target"] == b["target"] == path["nodes"][1]
        assert all((e["source"],e["target"],e["type"]) in edges for e in path["edges"])
        if path["relation"] == "DESCRIBES_SYMPTOM": assert path["review_status"] == "needs_review"
    assert all(p["relation"] == "PART_OF" and len(p["edges"]) == 2 for p in root["paths"])
    assert root["paths"] and "related_cards" not in other


def test_same_document_keeps_each_card_locator_and_never_follows_same_equipment():
    result = two_hop(("K-1004",))
    assert {c["card_id"] for c in related(result)} == {"K-1007", "K-1008"}
    for other in related(result):
        for path in other["paths"]:
            assert path["relation"] == "CITES"
            for cid, key in [("K-1004", "cited_locators"), (other["card_id"], "related_locators")]:
                card = next(c for c in CARDS if c["card_id"] == cid)
                expected = {r["locator"] for r in card["provenance"]["sources"]
                            if (r["source_id"],r.get("document_version")) == (path["source_id"],path["document_version"])}
                assert set(path[key]) == expected


@pytest.mark.parametrize("damage", ["version", "content", "scope", "rejected", "duplicate", "absent", "grade", "split", "equipment"])
def test_related_card_must_be_current_unique_in_scope_and_exact(damage):
    cards = deepcopy(CARDS)
    other = next(c for c in cards if c["card_id"] == "K-1202")
    if damage == "version": other["version"] += "-changed"
    if damage == "content": other["know_how"] += "changed"
    if damage == "scope": other["mes_equipment_id"] = "EQ-9999"
    if damage == "rejected": other["status"] = "rejected"
    if damage == "grade": other["grade"] = "L0"
    if damage == "split": other["split"] = "dev"
    if damage == "equipment": other["equipment"] = "CAU"
    if damage == "duplicate": cards.append(deepcopy(other))
    if damage == "absent": cards.remove(other)
    assert related(two_hop(cards=cards)) == []


@pytest.mark.parametrize("configured", [None, "1", "", "3", "invalid"])
def test_default_and_invalid_depth_preserve_one_hop_contract(monkeypatch, configured):
    monkeypatch.delenv("SHIFTLINK_KG_DEPTH", raising=False)
    output = {"answer":"unchanged", "cited_card_ids":["K-1201"]}
    baseline = explain(output, CARDS, "HPU", "EQ-0001", mode="explain")
    if configured is not None: monkeypatch.setenv("SHIFTLINK_KG_DEPTH", configured)
    assert explain(output, CARDS, "HPU", "EQ-0001", mode="explain") == baseline
    assert "depth" not in baseline and "related_cards" not in baseline["cards"][0]


def test_depth_two_env_is_optional_off_and_withheld_stay_closed(monkeypatch, tmp_path):
    monkeypatch.setenv("SHIFTLINK_KG_DEPTH", "2")
    output = {"answer":"unchanged", "cited_card_ids":["K-1201"]}
    assert explain(output, CARDS, "HPU", "EQ-0001", mode="explain")["depth"] == 2
    assert explain(output, [], "HPU", "EQ-0001", mode="off", path=tmp_path/"absent") is None
    for flag in ("no_knowledge", "review_queue", "validation_errors"):
        blocked = explain({**output,flag:True}, CARDS, "HPU", "EQ-0001", mode="explain")
        assert blocked["status"] == "withheld" and blocked["cards"] == []
    missing = two_hop(path=tmp_path/"absent")
    assert missing["status"] == "unavailable" and missing["cards"] == []


def test_two_hop_never_expands_uncited_or_stale_roots_and_preserves_holds():
    assert two_hop(())["cards"] == []
    cards = deepcopy(CARDS)
    next(c for c in cards if c["card_id"]=="K-1201")["version"] += "-new"
    assert two_hop(cards=cards)["cards"] == []
    result = two_hop(("K-1105",))
    assert result["cards"][0]["held_citations"] and related(result) == []
    assert two_hop(("K-1301",))["cards"] == []  # wrong equipment


def test_related_limits_are_deterministic_and_response_wide(tmp_path):
    graph = json.loads((BUILD/"graph.json").read_text(encoding="utf-8"))
    report = json.loads((BUILD/"validation.json").read_text(encoding="utf-8"))
    source = next(n for n in graph["nodes"] if n["type"]=="CardVersion" and n["props"]["card_id"]=="K-1201")
    outgoing = [e for e in graph["edges"] if e["source"]==source["id"]]
    cards = deepcopy(CARDS)
    for i in range(35):
        node = deepcopy(source); node["props"]["card_id"] = f"K-{9000+i:04}"
        node["id"] = f"card:{node['props']['card_id']}@{node['props']['version']}"
        graph["nodes"].append(node); cards.append(deepcopy(node["props"]))
        graph["edges"].extend({**deepcopy(e),"source":node["id"]} for e in outgoing)
    raw = json.dumps(graph,ensure_ascii=False).encode()
    (tmp_path/"graph.json").write_bytes(raw)
    report.update(graph_sha256=hashlib.sha256(raw).hexdigest(),total_nodes=len(graph["nodes"]),total_edges=len(graph["edges"]))
    for kind in report["node_counts"]: report["node_counts"][kind]=sum(n["type"]==kind for n in graph["nodes"])
    for kind in report["edge_counts"]: report["edge_counts"][kind]=sum(e["type"]==kind for e in graph["edges"])
    (tmp_path/"validation.json").write_text(json.dumps(report),encoding="utf-8")
    ids=("K-1201","K-1202","K-9034")
    result = two_hop(ids,cards,path=tmp_path/"graph.json")
    all_related = related(result)
    assert len(all_related) == len({c["card_id"] for c in all_related}) == 20
    assert all(len(c["related_cards"])<=10 for c in result["cards"])
    assert any(c["related_cards_omitted"]>0 for c in result["cards"])
    assert not set(ids) & {c["card_id"] for c in all_related}
    assert two_hop(ids,list(reversed(cards)),path=tmp_path/"graph.json") == result


def test_depth_two_changes_only_graph_context_and_persists_without_mutation(service, monkeypatch):
    from shiftlink.mes.query import query_service
    output = {"answer":"unchanged", "cited_card_ids":["K-1201"]}
    payloads=[]
    service.query_pipeline=SimpleNamespace(cards=deepcopy(CARDS),run=lambda payload:
        payloads.append(deepcopy(payload)) or SimpleNamespace(output=AgentResponse(mode="query",**output)))
    body={"question":"필터 차압", "equipment_id":"EQ-0001"}
    monkeypatch.setenv("SHIFTLINK_KG_MODE","off"); off=query_service(service,body)
    monkeypatch.setenv("SHIFTLINK_KG_MODE","explain")
    for depth in ("1","2"):
        monkeypatch.setenv("SHIFTLINK_KG_DEPTH",depth)
        response=query_service(service,body)
        context=response.pop("graph_context")
        assert response==off and (depth=="1" or related(context))
    assert payloads[0]==payloads[1]==payloads[2] and service.query_pipeline.cards==CARDS
    saved=service.query(body)
    assert saved["cited_card_ids"]==["K-1201"]
    assert service.storage.get_query(saved["query_id"])["payload"]["graph_context"]==saved["graph_context"]


def test_related_request_views_refresh_and_returned_metadata_is_isolated():
    first=two_hop()
    first["cards"][0]["related_cards"][0]["paths"].clear()
    assert related(two_hop())[0]["paths"]
    current=[c for c in CARDS if c["card_id"] != "K-1202"]
    assert related(two_hop(cards=current)) == []
    assert related(two_hop())[0]["card_id"] == "K-1202"


def test_document_version_identity_and_path_caps(tmp_path):
    graph=json.loads((BUILD/"graph.json").read_text(encoding="utf-8"))
    report=json.loads((BUILD/"validation.json").read_text(encoding="utf-8"))
    root=next(n for n in graph["nodes"] if n["type"]=="CardVersion" and n["props"]["card_id"]=="K-1201")
    other=next(n for n in graph["nodes"] if n["type"]=="CardVersion" and n["props"]["card_id"]=="K-1202")
    edge=next(e for e in graph["edges"] if e["source"]==root["id"] and e["type"]=="CITES")
    doc=next(n for n in graph["nodes"] if n["id"]==edge["target"])
    # Add exact shared versions and one same-source/different-version pair.
    for i in range(6):
        for version,owners in [(f"shared-{i}",[root,other])] if i<5 else [("left",[root]),("right",[other])]:
            node=deepcopy(doc);node["id"]=f"doc:test-{i}-{version}"
            node["props"].update(source_id=f"TEST-{i}",document_version=version)
            graph["nodes"].append(node)
            for owner in owners:
                locator=f"page-{owner['props']['card_id']}-{i}"
                owner["props"]["provenance"]["sources"].append({"source_id":f"TEST-{i}","document_version":version,"locator":locator})
                graph["edges"].append({"source":owner["id"],"target":node["id"],"type":"CITES",
                                       "props":{"locators":[locator],"source_ref_count":1}})
    def write():
        raw=json.dumps(graph,ensure_ascii=False).encode();(tmp_path/"graph.json").write_bytes(raw)
        report.update(graph_sha256=hashlib.sha256(raw).hexdigest(),total_nodes=len(graph["nodes"]),total_edges=len(graph["edges"]))
        for kind in report["node_counts"]:report["node_counts"][kind]=sum(n["type"]==kind for n in graph["nodes"])
        for kind in report["edge_counts"]:report["edge_counts"][kind]=sum(e["type"]==kind for e in graph["edges"])
        (tmp_path/"validation.json").write_text(json.dumps(report),encoding="utf-8")
    write()
    cards=[n["props"] for n in graph["nodes"] if n["type"]=="CardVersion"]
    result=two_hop(cards=cards,path=tmp_path/"graph.json")
    linked,=related(result)
    assert len(linked["paths"])==3 and linked["paths_omitted"]==4  # 6 shared docs + 1 symptom
    assert all(p.get("source_id") != "TEST-5" for p in linked["paths"])
    # Edge/node order cannot change receipts or which references survive limits.
    graph["nodes"].reverse();graph["edges"].reverse();write()
    again=two_hop(cards=cards,path=tmp_path/"graph.json")
    # Depth-one lists intentionally retain their existing file order; compare new receipts only.
    for a,b in zip(result["cards"],again["cards"]):
        for key in ("paths","paths_omitted","related_cards","related_cards_omitted"):
            assert a[key] == b[key]


def test_all_final_cited_roots_are_excluded_even_when_chunk_binding_fails():
    card=next(c for c in CARDS if c["card_id"]=="K-1201")
    chunks=[{"metadata":{"kind":"card","source":"K-1201"},"text":card["know_how"]}]
    result=two_hop(("K-1201","K-1202"),cited_chunks=chunks)
    assert result["status"]=="partial" and related(result)==[]
    assert result["unmatched"]==[{"card_id":"K-1202","reason":"cited_chunk_mismatch"}]
