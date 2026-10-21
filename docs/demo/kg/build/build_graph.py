"""Build the isolated kg-demo-v1 presentation graph; Python standard library only.

Run from any directory: python <repo>/docs/demo/kg/build/build_graph.py
Run assertions without publishing outputs: add --self-test. No KB generator is used.
"""

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys


BUILD = Path(__file__).resolve().parent
ROOT = BUILD.parents[3]
BASE_SHA = "5167376b5ded1e33725394f2b65cb6977c121dec"
SCHEMA = "docs/demo/kg/schema.md"
KB = "docs/data/knowledge_cards/kb/kb_cards.json"
MASTER = "docs/data/reference/00_plant_and_relations.json"
SYMPTOMS = "docs/demo/kg/symptoms/symptom_concepts.json"
FROZEN_HASHES = {
    KB: "05cfc4e79a3087e3544fc01e6b830268b542f55ae3be31bd6ad7601fc1d6dd3a",
    MASTER: "aee891c5e5e2270e815080f22b153e9b64e9128951d2262240c1f41cdc5e1708",
}
NODE_TYPES = ("EquipmentType", "Symptom", "CardVersion", "DocumentVersion", "Asset", "AssetPart")
EDGE_TYPES = ("PART_OF", "ABOUT", "DESCRIBES_SYMPTOM", "CITES", "INSTANCE_OF", "INSTALLED_ON")
DOMAINS = {
    "PART_OF": ("EquipmentType", "EquipmentType"),
    "ABOUT": ("CardVersion", "EquipmentType"),
    "DESCRIBES_SYMPTOM": ("CardVersion", "Symptom"),
    "CITES": ("CardVersion", "DocumentVersion"),
    "INSTANCE_OF": ("Asset", "EquipmentType"),
    "INSTALLED_ON": ("AssetPart", "Asset"),
}


def require(condition, message):
    """Input/graph validation remains enabled under python -O."""
    if not condition:
        raise ValueError(message)


def string(value, context):
    require(isinstance(value, str) and bool(value.strip()), f"{context}: nonempty string required")
    return value


def escape(value):
    return string(value, "ID segment").replace("%", "%25").replace("/", "%2F").replace("@", "%40")


def type_id(equipment, component=None):
    return "type:" + escape(equipment) + ("/" + escape(component) if component is not None else "")


def card_id(card):
    return "card:" + escape(card["card_id"]) + "@" + escape(card["version"])


def document_id(source):
    return "doc:" + escape(source["source_id"]) + "@" + escape(source["document_version"])


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        require(key not in obj, f"duplicate JSON key: {key}")
        obj[key] = value
    return obj


def reject_constant(value):
    raise ValueError(f"non-JSON numeric constant: {value}")


def decode(data):
    return json.loads(data.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=reject_constant)


def exact_keys(obj, keys, context):
    require(isinstance(obj, dict) and set(obj) == set(keys), f"{context}: expected keys {sorted(keys)}")


def index_rows(rows, key, context):
    require(isinstance(rows, list), f"{context}: array required")
    result = {}
    for row in rows:
        require(isinstance(row, dict), f"{context}: object required")
        ident = string(row.get(key), f"{context}.{key}")
        require(ident not in result, f"{context}: duplicate {key} {ident}")
        result[ident] = row
    return result


def validate_inputs(kb, master, mapping):
    require(isinstance(kb, dict), "KB: object required")
    cards = index_rows(kb.get("cards"), "card_id", "cards (multiple versions per card_id unsupported)")
    require(bool(cards), "cards: empty input")
    for card in cards.values():
        for key in ("version", "equipment", "component", "title"):
            string(card.get(key), f"{card['card_id']}.{key}")
        require(type(card.get("safety_flag")) is bool, "card.safety_flag: boolean required")
        require("symptom" in card and (card["symptom"] is None or isinstance(card["symptom"], str)),
                "card.symptom: string or null required")
        require(isinstance(card.get("provenance"), dict), "card.provenance: object required")
        sources = card["provenance"].get("sources")
        require(isinstance(sources, list) and bool(sources), "card.provenance.sources: nonempty array required")
        for source in sources:
            require(isinstance(source, dict), "source: object required")
            string(source.get("source_id"), "source.source_id")
            string(source.get("locator"), "source.locator")
            if source.get("document_version") not in (None, ""):
                string(source["document_version"], "source.document_version")
    require(isinstance(master, dict) and isinstance(master.get("_meta"), dict), "master metadata required")
    require(master["_meta"].get("is_synthetic") is True, "master must be synthetic")
    require(master["_meta"].get("dataset_version") == "DS-v1.0", "master must use DS-v1.0")
    types = index_rows(master.get("equipment_types"), "equipment_type_id", "equipment_types")
    require(len({string(t.get('type_code'), 'type_code') for t in types.values()}) == len(types),
            "equipment_types: duplicate type_code")
    assets = index_rows(master.get("equipment"), "equipment_id", "equipment")
    codes = set()
    card_types = {c["equipment"] for c in cards.values()}
    for asset in assets.values():
        string(asset.get("code"), "equipment.code")
        require(asset["code"] not in codes, "equipment: duplicate code")
        codes.add(asset["code"])
        fk = string(asset.get("equipment_type_id"), "equipment.equipment_type_id")
        require(fk in types, f"equipment: missing type FK {fk}")
        require(types[fk]["type_code"] in card_types, "master type missing from card classifications")
        require(asset.get("is_synthetic") is True, "equipment must be synthetic")
    if mapping is not None:
        validate_mapping(mapping, cards)
    return cards, types, assets


def validate_mapping(mapping, cards):
    exact_keys(mapping, ("concepts", "card_map", "needs_review"), "symptom mapping")
    concepts = index_rows(mapping["concepts"], "id", "concepts")
    for concept in concepts.values():
        exact_keys(concept, ("id", "label", "definition"), "concept")
        require(re.fullmatch(r"sym:[a-z0-9]+(?:-[a-z0-9]+)*", concept["id"]) is not None,
                f"invalid symptom ID: {concept['id']}")
        string(concept["label"], "concept.label")
        string(concept["definition"], "concept.definition")
    require(isinstance(mapping["card_map"], dict) and set(mapping["card_map"]) == set(cards),
            "card_map must contain exactly the input card IDs")
    reviews = index_rows(mapping["needs_review"], "card_id", "needs_review")
    require(set(reviews) == set(cards), "needs_review must contain exactly the input card IDs")
    for review in reviews.values():
        exact_keys(review, ("card_id", "reason"), "needs_review item")
        string(review["reason"], "needs_review.reason")
    referenced = set()
    for ident, ids in mapping["card_map"].items():
        require(isinstance(ids, list) and all(isinstance(i, str) for i in ids), "card_map values: string arrays required")
        require(len(ids) == len(set(ids)), f"duplicate symptom mapping for {ident}")
        require(set(ids) <= set(concepts), f"undefined symptom mapping for {ident}")
        card = cards[ident]
        require(not ids or not (card["safety_flag"] or card["symptom"] is None),
                f"blocked safety/null symptom mapping: {ident}")
        referenced.update(ids)
    require(referenced == set(concepts), "unreferenced symptom concept")


def compose(kb, master, mapping=None):
    """Pure transformation, also usable with small in-memory self-check inputs."""
    cards, types, assets = validate_inputs(kb, master, mapping)
    nodes, edges, unversioned = {}, {}, []

    def node(ident, kind, label, props):
        value = {"id": ident, "type": kind, "label": label, "props": deepcopy(props)}
        require(ident not in nodes or encode(nodes[ident]) == encode(value), f"conflicting node: {ident}")
        nodes[ident] = value

    def edge(source, target, kind, props):
        key = (kind, source, target)
        value = {"source": source, "target": target, "type": kind, "props": deepcopy(props)}
        require(key not in edges or encode(edges[key]) == encode(value), f"conflicting edge: {key}")
        edges[key] = value

    for card in cards.values():
        equipment, component = card["equipment"], card["component"]
        equipment_node, component_node = type_id(equipment), type_id(equipment, component)
        common = equipment == "COMMON"
        node(equipment_node, "EquipmentType", equipment,
             {"kind": "equipment", "equipment": equipment, "is_common_scope": common})
        node(component_node, "EquipmentType", component,
             {"kind": "component", "equipment": equipment, "component": component, "is_common_scope": common})
        edge(component_node, equipment_node, "PART_OF", {"basis": "card_classification"})
        cid = card_id(card)
        node(cid, "CardVersion", card["title"], card)
        edge(cid, equipment_node, "ABOUT", {"basis": "card_equipment"})
        edge(cid, component_node, "ABOUT", {"basis": "card_component"})
        citations = {}
        for source in card["provenance"]["sources"]:
            if source.get("document_version") in (None, ""):
                unversioned.append({"card_id": card["card_id"], "card_version": card["version"],
                                    "source": deepcopy(source), "reason": "document_version_missing"})
                continue
            did = document_id(source)
            node(did, "DocumentVersion", source["source_id"] + " @ " + source["document_version"],
                 {"source_id": source["source_id"], "document_version": source["document_version"]})
            aggregate = citations.setdefault(did, {"locators": [], "source_ref_count": 0})
            if source["locator"] not in aggregate["locators"]:
                aggregate["locators"].append(source["locator"])
            aggregate["source_ref_count"] += 1
        for did, props in citations.items():
            edge(cid, did, "CITES", props)
    for equipment in assets.values():
        eid = equipment["equipment_id"]
        aid = "AS-" + eid + "-001"
        fk = equipment["equipment_type_id"]
        type_code = types[fk]["type_code"]
        ident = "asset:" + escape(aid)
        node(ident, "Asset", equipment["code"] + " (합성 장비)", {
            "asset_id": aid, "equipment_id": eid, "code": equipment["code"], "equipment_type_id": fk,
            "type_code": type_code, "is_synthetic": True, "dataset_version": "DS-v1.0",
            "identity_basis": "from_catalog_default", "source_path": MASTER,
        })
        edge(ident, type_id(type_code), "INSTANCE_OF", {"basis": "catalog_equipment_type_id", "is_synthetic": True})
    if mapping is not None:
        for concept in mapping["concepts"]:
            node(concept["id"], "Symptom", concept["label"],
                 {"definition": concept["definition"], "review_status": "needs_review"})
        for ident, ids in mapping["card_map"].items():
            for symptom in ids:
                edge(card_id(cards[ident]), symptom, "DESCRIBES_SYMPTOM",
                     {"review_status": "needs_review", "basis": "symptom_concepts"})
    graph = {"nodes": sorted(nodes.values(), key=lambda n: n["id"]),
             "edges": sorted(edges.values(), key=lambda e: (e["type"], e["source"], e["target"]))}
    unversioned.sort(key=lambda item: (item["card_id"], item["card_version"], encode(item["source"])))
    return graph, unversioned


def validate_graph(graph, kb, master, mapping=None):
    """Validate structure and semantics independently of graph insertion helpers.

    Compare the complete projection too, so dropped/extra nodes, edges, card fields,
    master attributes and citation locators cannot pass just by having valid types.
    """
    exact_keys(graph, ("nodes", "edges"), "graph")
    require(isinstance(graph["nodes"], list) and isinstance(graph["edges"], list), "graph arrays required")
    nodes = {}
    for node in graph["nodes"]:
        exact_keys(node, ("id", "type", "label", "props"), "node")
        ident = string(node["id"], "node.id")
        require(ident not in nodes, f"duplicate node ID: {ident}")
        require(node["type"] in NODE_TYPES, f"unknown node type: {node['type']}")
        string(node["label"], "node.label")
        require(isinstance(node["props"], dict), "node.props: object required")
        props, kind = node["props"], node["type"]
        if kind == "EquipmentType":
            require(props.get("kind") in ("equipment", "component"), "invalid EquipmentType.kind")
            component = props.get("component") if props["kind"] == "component" else None
            if props["kind"] == "component":
                string(component, "component")
            require(ident == type_id(props.get("equipment"), component), "invalid EquipmentType ID")
            require(props.get("is_common_scope") is (props["equipment"] == "COMMON"), "invalid common scope")
        elif kind == "CardVersion":
            require(ident == card_id(props), "invalid CardVersion ID")
            require(type(props.get("safety_flag")) is bool, "invalid safety flag")
            require("symptom" in props, "missing original symptom")
        elif kind == "DocumentVersion":
            require(ident == document_id(props), "invalid DocumentVersion ID")
        elif kind == "Symptom":
            require(re.fullmatch(r"sym:[a-z0-9]+(?:-[a-z0-9]+)*", ident) is not None, "invalid Symptom ID")
            string(props.get("definition"), "Symptom.definition")
            require(props.get("review_status") == "needs_review", "unreviewed symptom must be marked")
        elif kind == "Asset":
            require(ident == "asset:" + escape(props.get("asset_id")), "invalid Asset ID")
            require(props.get("is_synthetic") is True and props.get("identity_basis") == "from_catalog_default",
                    "Asset must be a default synthetic snapshot")
        else:
            raise ValueError("AssetPart is design-only; no nodes allowed")
        nodes[ident] = node
    require(graph["nodes"] == sorted(graph["nodes"], key=lambda n: n["id"]), "nodes not sorted by ID")
    keys, incident = set(), set()
    for edge in graph["edges"]:
        exact_keys(edge, ("source", "target", "type", "props"), "edge")
        source, target, kind, props = (edge[k] for k in ("source", "target", "type", "props"))
        string(source, "edge.source")
        string(target, "edge.target")
        require(kind in EDGE_TYPES, f"unknown edge type: {kind}")
        require(isinstance(props, dict), "edge.props: object required")
        key = (kind, source, target)
        require(key not in keys, f"duplicate edge: {key}")
        keys.add(key)
        require(source in nodes and target in nodes, f"missing edge endpoint: {key}")
        a, b = nodes[source], nodes[target]
        require((a["type"], b["type"]) == DOMAINS[kind], f"invalid edge domain/range: {key}")
        ap, bp = a["props"], b["props"]
        if kind == "PART_OF":
            require(ap["kind"] == "component" and bp["kind"] == "equipment" and ap["equipment"] == bp["equipment"],
                    "PART_OF must stay within one equipment classification")
            require(props == {"basis": "card_classification"}, "invalid PART_OF basis")
        elif kind == "ABOUT":
            require(ap["equipment"] == bp["equipment"], "ABOUT equipment mismatch")
            if bp["kind"] == "component":
                require(ap["component"] == bp["component"], "ABOUT component mismatch")
            require(props == {"basis": "card_" + bp["kind"]}, "invalid ABOUT basis")
        elif kind == "DESCRIBES_SYMPTOM":
            require(not ap["safety_flag"] and ap["symptom"] is not None, "blocked safety/null symptom edge")
            require(mapping is not None and target in mapping["card_map"].get(ap["card_id"], []), "unmapped symptom edge")
            require(props == {"review_status": "needs_review", "basis": "symptom_concepts"}, "invalid symptom edge status")
        elif kind == "CITES":
            exact_keys(props, ("locators", "source_ref_count"), "CITES props")
            require(isinstance(props["locators"], list) and bool(props["locators"]), "CITES locators required")
            require(all(isinstance(x, str) for x in props["locators"]), "CITES locators must be strings")
            require(len(props["locators"]) == len(set(props["locators"])), "duplicate CITES locator")
            require(type(props["source_ref_count"]) is int and props["source_ref_count"] >= len(props["locators"]),
                    "invalid CITES source_ref_count")
        elif kind == "INSTANCE_OF":
            require(bp["kind"] == "equipment" and ap["type_code"] == bp["equipment"], "INSTANCE_OF type mismatch")
            require(props.get("is_synthetic") is True and props.get("basis") == "catalog_equipment_type_id",
                    "invalid INSTANCE_OF provenance")
        else:
            raise ValueError("INSTALLED_ON is design-only; no edges allowed")
        incident.update((source, target))
    require(graph["edges"] == sorted(graph["edges"], key=lambda e: (e["type"], e["source"], e["target"])),
            "edges not sorted")
    orphan_nodes = [{k: n[k] for k in ("id", "type", "label")} for n in graph["nodes"] if n["id"] not in incident]
    require(not orphan_nodes, f"orphan nodes: {orphan_nodes}")
    expected, _ = compose(kb, master, mapping)
    require(encode(graph) == encode(expected), "graph differs from full source projection (IDs/props/relations/locators)")
    node_counts, edge_counts = Counter(n["type"] for n in graph["nodes"]), Counter(e["type"] for e in graph["edges"])
    return {"node_counts": {t: node_counts[t] for t in NODE_TYPES},
            "edge_counts": {t: edge_counts[t] for t in EDGE_TYPES},
            "total_nodes": len(nodes), "total_edges": len(keys), "orphan_nodes": orphan_nodes, "errors": []}


def self_check():
    """Adversarial assertions; fixtures stay in memory and require no dependencies."""
    require(__debug__, "assert self-checks require Python without -O")
    checked = []

    def rejected(name, operation, expected_message):
        try:
            operation()
        except ValueError as error:
            assert expected_message in str(error), (name, str(error))
        else:
            raise AssertionError(f"accepted invalid case: {name}")
        checked.append(name)

    base_card = {"card_id": "K/@% 한글", "version": "v/@%", "equipment": "E/@%", "component": "부품/@%",
                 "title": "원문 제목", "symptom": "압력 없음", "safety_flag": False,
                 "provenance": {"sources": [
                     {"source_id": "manual/@%", "document_version": "edition/@%", "locator": "p.1"},
                     {"source_id": "manual/@%", "document_version": "edition/@%", "locator": "p.1"},
                     {"source_id": "manual/@%", "document_version": "edition/@%", "locator": "p.2"},
                     {"source_id": "EV-1", "locator": "原文 / @ %"}]}}
    safe = dict(deepcopy(base_card), card_id="SAFE", safety_flag=True)
    null = dict(deepcopy(base_card), card_id="NULL", symptom=None)
    kb = {"cards": [base_card, safe, null]}
    master = {"_meta": {"is_synthetic": True, "dataset_version": "DS-v1.0"},
              "equipment_types": [{"equipment_type_id": "ET-1", "type_code": base_card["equipment"]}],
              "equipment": [{"equipment_id": "EQ-1", "code": "E-1", "equipment_type_id": "ET-1", "is_synthetic": True}]}
    mapping = {"concepts": [{"id": "sym:pressure-absent", "label": "압력 없음", "definition": "압력이 없음. 낮음과 구별."}],
               "card_map": {base_card["card_id"]: ["sym:pressure-absent"], "SAFE": [], "NULL": []},
               "needs_review": [{"card_id": c["card_id"], "reason": "사람 검수 전 또는 안전/null 보류"} for c in kb["cards"]]}
    graph, withheld = compose(kb, master, mapping)
    summary = validate_graph(graph, kb, master, mapping)
    assert summary["node_counts"]["Symptom"] == 1 and summary["edge_counts"]["DESCRIBES_SYMPTOM"] == 1
    assert escape("%/@ 한글") == "%25%2F%40 한글"
    assert escape("%2F") != escape("/")
    assert card_id(base_card) == "card:K%2F%40%25 한글@v%2F%40%25"
    assert len(withheld) == 3 and withheld[0]["source"] in base_card["provenance"]["sources"]
    citation = next(e for e in graph["edges"] if e["type"] == "CITES")
    assert citation["props"] == {"locators": ["p.1", "p.2"], "source_ref_count": 3}
    without, _ = compose(kb, master)
    assert validate_graph(without, kb, master)["node_counts"]["Symptom"] == 0
    assert encode(graph) == encode(compose(kb, master, mapping)[0])
    shuffled = deepcopy(kb)
    shuffled["cards"].reverse()
    assert encode(graph) == encode(compose(shuffled, master, mapping)[0])
    checked.extend(("valid_mapping", "absent_mapping", "ID_escaping", "citation_aggregation_and_raw_preservation", "deterministic_order"))

    def bad_graph(name, mutate, message):
        changed = deepcopy(graph)
        mutate(changed)
        rejected(name, lambda: validate_graph(changed, kb, master, mapping), message)

    def add_edge(g, edge):
        g["edges"].append(edge)
        g["edges"].sort(key=lambda e: (e["type"], e["source"], e["target"]))

    bad_graph("missing_endpoint", lambda g: g["edges"][0].update(target="type:missing"), "missing edge endpoint")
    bad_graph("wrong_domain_range", lambda g: g["edges"][0].update(target="sym:pressure-absent"), "invalid edge domain/range")
    for card, name in ((safe, "safety_card_edge"), (null, "null_card_edge")):
        bad_graph(name, lambda g, c=card: add_edge(g, {"source": card_id(c), "target": "sym:pressure-absent",
                  "type": "DESCRIBES_SYMPTOM", "props": {"review_status": "needs_review", "basis": "symptom_concepts"}}),
                  "blocked safety/null symptom edge")
    bad_graph("duplicate_node", lambda g: g["nodes"].append(deepcopy(g["nodes"][0])), "duplicate node ID")
    bad_graph("duplicate_edge", lambda g: g["edges"].append(deepcopy(g["edges"][0])), "duplicate edge")
    bad_graph("wrong_id", lambda g: g["nodes"][0].update(id="asset:wrong"), "invalid Asset ID")
    bad_graph("lost_card_field", lambda g: next(n["props"] for n in g["nodes"] if n["type"] == "CardVersion").pop("title"),
              "graph differs from full source projection")
    bad_graph("missing_relation", lambda g: g["edges"].pop(0), "graph differs from full source projection")
    def orphan(g):
        g["nodes"].append({"id": "sym:orphan", "type": "Symptom", "label": "미참조", "props": {"definition": "미참조", "review_status": "needs_review"}})
        g["nodes"].sort(key=lambda n: n["id"])
    bad_graph("orphan_node", orphan, "orphan nodes")
    bad_graph("unexpected_graph_key", lambda g: g.update(coordinates={}), "graph: expected keys")
    bad_graph("unknown_relation", lambda g: g["edges"][0].update(type="CAUSES"), "unknown edge type")
    bad_graph("wrong_relation_props", lambda g: g["edges"][0]["props"].update(basis="inferred"), "invalid ABOUT basis")
    bad_graph("citation_count_loss", lambda g: next(e["props"] for e in g["edges"] if e["type"] == "CITES").update(source_ref_count=2),
              "graph differs from full source projection")

    def bad_mapping(name, mutate, message):
        changed = deepcopy(mapping)
        mutate(changed)
        rejected(name, lambda: compose(kb, master, changed), message)

    for ident in ("SAFE", "NULL"):
        bad_mapping(ident + "_mapping", lambda m, i=ident: m["card_map"][i].append("sym:pressure-absent"), "blocked safety/null")
    bad_mapping("undefined_concept", lambda m: m["card_map"][base_card["card_id"]].append("sym:undefined"), "undefined symptom")
    bad_mapping("duplicate_mapping", lambda m: m["card_map"][base_card["card_id"]].append("sym:pressure-absent"), "duplicate symptom mapping")
    bad_mapping("missing_card", lambda m: m["card_map"].pop("SAFE"), "card_map must contain exactly")
    bad_mapping("extra_card", lambda m: m["card_map"].update(UNKNOWN=[]), "card_map must contain exactly")
    bad_mapping("missing_review", lambda m: m["needs_review"].pop(), "needs_review must contain exactly")
    bad_mapping("blank_review_reason", lambda m: m["needs_review"][0].update(reason=" "), "nonempty string required")
    bad_mapping("duplicate_review", lambda m: m["needs_review"].append(deepcopy(m["needs_review"][0])), "duplicate card_id")
    bad_mapping("unreferenced_concept", lambda m: m["concepts"].append({"id": "sym:unused", "label": "미사용", "definition": "미사용"}),
                "unreferenced symptom")
    bad_mapping("invalid_slug", lambda m: m["concepts"][0].update(id="sym:Bad_Slug"), "invalid symptom ID")
    bad_mapping("wrong_mapping_type", lambda m: m["card_map"].update(SAFE="sym:pressure-absent"), "string arrays required")
    duplicate = deepcopy(kb)
    duplicate["cards"].append(dict(deepcopy(base_card), version="another-version"))
    rejected("multiple_card_versions", lambda: compose(duplicate, master), "duplicate card_id")
    broken_master = deepcopy(master)
    broken_master["equipment"][0]["equipment_type_id"] = "missing"
    rejected("master_FK", lambda: compose(kb, broken_master), "missing type FK")
    rejected("duplicate_JSON_key", lambda: decode(b'{"card_map":{"K":[],"K":[]}}'), "duplicate JSON key")
    rejected("invalid_JSON_number", lambda: decode(b'{"x":NaN}'), "non-JSON numeric constant")
    return checked


def read_inputs():
    raw = {path: (ROOT / path).read_bytes() for path in (KB, MASTER, SCHEMA)}
    present = (ROOT / SYMPTOMS).exists()
    if present:
        raw[SYMPTOMS] = (ROOT / SYMPTOMS).read_bytes()
    for path, expected in FROZEN_HASHES.items():
        require(digest(raw[path]) == expected, f"frozen baseline input hash mismatch: {path}; do not regenerate sources")
    return raw, present


def unchanged(raw, present):
    require((ROOT / SYMPTOMS).exists() == present, "symptom input presence changed during build; rerun")
    after = {path: digest((ROOT / path).read_bytes()) for path in raw}
    require(after == {path: digest(data) for path, data in raw.items()}, "input/contract changed during build; rerun")
    return after


def run():
    checks = self_check()
    raw, present = read_inputs()
    kb, master = decode(raw[KB]), decode(raw[MASTER])
    mapping = decode(raw[SYMPTOMS]) if present else None
    require(not present or isinstance(mapping, dict), "existing symptom mapping must be an object, never null")
    graph, unversioned = compose(kb, master, mapping)
    summary = validate_graph(graph, kb, master, mapping)
    expected_nodes = {"EquipmentType": 83, "CardVersion": 86, "DocumentVersion": 92, "Asset": 10, "AssetPart": 0}
    expected_edges = {"PART_OF": 76, "ABOUT": 172, "CITES": 156, "INSTANCE_OF": 10, "INSTALLED_ON": 0}
    require(all(summary["node_counts"][k] == v for k, v in expected_nodes.items()), "frozen baseline node counts differ")
    require(all(summary["edge_counts"][k] == v for k, v in expected_edges.items()), "frozen baseline edge counts differ")
    require(len(unversioned) == 42, "frozen baseline unversioned count differs")
    graph_bytes = encode(graph)
    repeated, repeated_unversioned = compose(decode(raw[KB]), decode(raw[MASTER]), decode(raw[SYMPTOMS]) if present else None)
    require(graph_bytes == encode(repeated) and encode(unversioned) == encode(repeated_unversioned), "nondeterministic conversion")
    require(encode(summary) == encode(validate_graph(repeated, kb, master, mapping)), "nondeterministic validation")
    after = unchanged(raw, present)
    cards = kb["cards"]
    safety = sorted(c["card_id"] for c in cards if c["safety_flag"])
    nulls = sorted(c["card_id"] for c in cards if c["symptom"] is None)
    citation_count = sum(len(c["provenance"]["sources"]) for c in cards)
    report = dict(summary, schema_version="kg-demo-v1", base_sha=BASE_SHA,
                  contract_sha256=digest(raw[SCHEMA]),
                  source_hashes={p: digest(data) for p, data in raw.items() if p != SCHEMA},
                  input_hashes_after={p: h for p, h in after.items() if p != SCHEMA},
                  source_hashes_unchanged=True, contract_hash_unchanged=True,
                  symptoms_loaded=present, unversioned_sources=unversioned,
                  review_card_ids=sorted(c["card_id"] for c in cards),
                  safety_review_card_ids=safety, null_symptom_card_ids=nulls,
                  blocked_symptom_card_ids=sorted(set(safety) | set(nulls)),
                  safety_symptom_edges=0, null_symptom_edges=0,
                  citation_counts={"source_refs": citation_count, "unversioned_refs": len(unversioned),
                                   "versioned_refs": citation_count - len(unversioned),
                                   "versioned_card_document_pairs": summary["edge_counts"]["CITES"]},
                  graph_sha256=digest(graph_bytes), deterministic_rebuild=True,
                  self_checks={"passed": len(checks), "cases": checks})
    report_bytes = encode(report)
    # Validate everything before either successful output can be replaced.
    unchanged(raw, present)
    for filename, data in (("graph.json", graph_bytes), ("validation.json", report_bytes)):
        target = BUILD / filename
        temporary = BUILD / (filename + ".tmp")
        temporary.write_bytes(data)
        temporary.replace(target)
    require((BUILD / "graph.json").read_bytes() == graph_bytes, "saved graph bytes differ")
    require((BUILD / "validation.json").read_bytes() == report_bytes, "saved validation bytes differ")
    print(json.dumps({"ok": True, "symptoms_loaded": present, "nodes": summary["total_nodes"],
                      "edges": summary["total_edges"], "unversioned_sources": len(unversioned),
                      "self_checks_passed": len(checks), "graph_sha256": digest(graph_bytes)}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="run assert checks without writing graph/validation")
    args = parser.parse_args()
    try:
        if args.self_test:
            checks = self_check()
            print(json.dumps({"ok": True, "self_checks_passed": len(checks), "cases": checks}, sort_keys=True))
        else:
            run()
    except (OSError, ValueError, KeyError, TypeError, AssertionError) as error:
        print(json.dumps({"ok": False, "errors": [f"{type(error).__name__}: {error}"]}, ensure_ascii=True), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
