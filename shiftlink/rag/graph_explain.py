"""Read kg-demo-v1 only to explain final citations; never retrieve or alter answers."""
from collections import defaultdict
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

from shiftlink.agent.schemas import KnowledgeCard

DEFAULT_GRAPH = Path(__file__).resolve().parents[2] / "docs/demo/kg/build/graph.json"
SCHEMA = "kg-demo-v1"
MAX_RELATED_PER_CARD = 10
MAX_RELATED_PER_RESPONSE = 20
MAX_PATHS_PER_REFERENCE = 3
DOMAINS = {"ABOUT": ("CardVersion", "EquipmentType"), "CITES": ("CardVersion", "DocumentVersion"),
           "DESCRIBES_SYMPTOM": ("CardVersion", "Symptom"), "PART_OF": ("EquipmentType", "EquipmentType"),
           "INSTANCE_OF": ("Asset", "EquipmentType")}
TYPES = {"CardVersion", "EquipmentType", "DocumentVersion", "Symptom", "Asset"}


def require(condition):
    if not condition:
        raise ValueError("invalid kg-demo-v1 artifact")


def nonblank(value):
    return isinstance(value, str) and bool(value.strip())


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def decode(raw):
    def invalid_constant(value):
        raise ValueError("invalid JSON constant")
    return json.loads(raw, object_pairs_hook=unique_object, parse_constant=invalid_constant)


def card_dict(card):
    return KnowledgeCard.model_validate(card).model_dump(mode="json")


class GraphSnapshot:
    """Request-local snapshot. No shared mutable graph or cached stale file on failure."""

    def __init__(self, path):
        raw = path.read_bytes()
        report = decode(path.with_name("validation.json").read_bytes())
        self.digest = hashlib.sha256(raw).hexdigest()
        require(report["schema_version"] == SCHEMA and report["errors"] == []
                and report["graph_sha256"] == self.digest)
        graph = decode(raw)
        require(set(graph) == {"nodes", "edges"} and isinstance(graph["nodes"], list) and isinstance(graph["edges"], list))
        self.nodes, self.cards, self.outgoing = {}, {}, defaultdict(list)
        self.incoming = defaultdict(list)
        for node in graph["nodes"]:
            require(set(node) == {"id", "type", "label", "props"} and nonblank(node["id"])
                    and node["id"] not in self.nodes and node["type"] in TYPES
                    and nonblank(node["label"]) and isinstance(node["props"], dict))
            props, kind = node["props"], node["type"]
            if kind == "CardVersion":
                card = card_dict(props)
                require(card["card_id"] not in self.cards)
                self.cards[card["card_id"]] = (node, card)
            elif kind == "EquipmentType":
                require(props["kind"] in ("equipment", "component") and nonblank(props["equipment"]))
                if props["kind"] == "component": require(nonblank(props["component"]))
            elif kind == "DocumentVersion":
                require(nonblank(props["source_id"]) and nonblank(props["document_version"]))
            elif kind == "Symptom":
                require(props["review_status"] == "needs_review" and nonblank(props["definition"]))
            elif kind == "Asset":
                require(props["is_synthetic"] is True and props["identity_basis"] == "from_catalog_default")
            self.nodes[node["id"]] = node
        seen, incident = set(), set()
        for edge in graph["edges"]:
            require(set(edge) == {"source", "target", "type", "props"} and isinstance(edge["props"], dict))
            source, target, kind = edge["source"], edge["target"], edge["type"]
            require(source in self.nodes and target in self.nodes and kind in DOMAINS)
            require((self.nodes[source]["type"], self.nodes[target]["type"]) == DOMAINS[kind])
            key = (source, target, kind)
            require(key not in seen)
            seen.add(key); incident.update((source, target))
            a, b = self.nodes[source]["props"], self.nodes[target]["props"]
            if kind == "ABOUT":
                require(a["equipment"] == b["equipment"] and
                        (b["kind"] == "equipment" or a["component"] == b["component"]))
            elif kind == "PART_OF":
                require(a["kind"] == "component" and b["kind"] == "equipment" and a["equipment"] == b["equipment"])
            elif kind == "INSTANCE_OF":
                require(b["kind"] == "equipment" and a["type_code"] == b["equipment"])
            elif kind == "DESCRIBES_SYMPTOM":
                require(a["safety_flag"] is False and a["symptom"] is not None
                        and edge["props"] == {"review_status": "needs_review", "basis": "symptom_concepts"})
            self.outgoing[source].append(edge)
            if kind in ("CITES", "DESCRIBES_SYMPTOM"):
                self.incoming[target].append(edge)
        require(incident == set(self.nodes))
        require(report["total_nodes"] == len(self.nodes) and report["total_edges"] == len(seen))
        require({k: sum(n["type"] == k for n in self.nodes.values()) for k in TYPES | {"AssetPart"}} == report["node_counts"])
        require({k: sum(e["type"] == k for e in graph["edges"]) for k in set(DOMAINS) | {"INSTALLED_ON"}} == report["edge_counts"])
        # Check each citation against preserved original sources, not just endpoint types.
        for node, card in self.cards.values():
            expected, actual = defaultdict(list), {}
            for ref in card["provenance"]["sources"]:
                if ref.get("document_version"):
                    expected[ref["source_id"], ref["document_version"]].append(ref["locator"])
            for edge in self.outgoing[node["id"]]:
                if edge["type"] == "CITES":
                    ref = self.nodes[edge["target"]]["props"]
                    key = (ref["source_id"], ref["document_version"])
                    locators = edge["props"]["locators"]
                    require(isinstance(locators, list) and all(nonblank(x) for x in locators))
                    require(key not in actual and key in expected and len(locators) == len(set(locators))
                            and set(locators) == set(expected[key]) and edge["props"]["source_ref_count"] == len(expected[key]))
                    actual[key] = locators
            require(set(actual) == set(expected))

    def bind_current(self, cid, visible, eq_type, eq_id):
        """Graph membership alone never authorizes either a root or a related card."""
        candidates = visible.get(cid, [])
        if len(candidates) != 1:
            return None, "card_not_visible_or_ambiguous"
        card = candidates[0]
        if not (eq_type and (card["status"], card["grade"], card["split"]) == ("accepted", "L1", "kb")
                and card["equipment"] in (eq_type, "COMMON") and card.get("mes_equipment_id") in (None, eq_id)):
            return None, "card_scope_or_status_mismatch"
        match = self.cards.get(cid)
        if not match or match[1] != card:
            return None, "card_version_or_content_mismatch"
        return match, ""

    def add_publications(self, visible, published_card_ids, eq_type, eq_id):
        """Only the publication snapshot's ticket may add request-local field cards."""
        added = []
        def node(kind, props, label):
            existing = next((n for n in self.nodes.values() if n['type'] == kind
                             and all(n['props'].get(k) == v for k, v in props.items())), None)
            if existing:
                return existing['id']
            identity = [props['card_id'], props['version']] if kind == 'CardVersion' else props
            ident = 'publication:' + json.dumps([kind, identity], ensure_ascii=False, sort_keys=True)
            self.nodes[ident] = {'id': ident, 'type': kind, 'label': label, 'props': deepcopy(props)}
            return ident
        def edge(source, target, kind, props=None):
            require((self.nodes[source]['type'], self.nodes[target]['type']) == DOMAINS[kind])
            if any(e['target'] == target and e['type'] == kind for e in self.outgoing[source]):
                return
            item = {'source': source, 'target': target, 'type': kind, 'props': props or {}}
            self.outgoing[source].append(item)
            if kind == 'CITES':
                self.incoming[target].append(item)
        for cid in sorted(set(published_card_ids)):
            current = visible.get(cid, [])
            if cid in self.cards or len(current) != 1:
                continue
            card = current[0]
            if (not eq_type or (card['status'], card['grade'], card['split']) != ('accepted', 'L1', 'kb')
                    or card['equipment'] not in (eq_type, 'COMMON') or card.get('mes_equipment_id') != eq_id
                    or not nonblank(card['component'])):
                continue
            cn = node('CardVersion', card, card['title'])
            self.cards[cid] = (self.nodes[cn], card)
            equipment = node('EquipmentType', {'kind': 'equipment', 'equipment': card['equipment']}, card['equipment'])
            component = node('EquipmentType', {'kind': 'component', 'equipment': card['equipment'],
                                              'component': card['component']}, card['component'])
            edge(cn, component, 'ABOUT'); edge(cn, equipment, 'ABOUT'); edge(component, equipment, 'PART_OF')
            references = defaultdict(list)
            for ref in card['provenance']['sources']:
                if all(nonblank(ref.get(k)) for k in ('source_id', 'document_version', 'locator')):
                    references[ref['source_id'], ref['document_version']].append(ref['locator'])
            for (sid, version), locators in sorted(references.items()):
                dn = node('DocumentVersion', {'source_id': sid, 'document_version': version}, sid)
                edge(cn, dn, 'CITES', {'locators': list(dict.fromkeys(locators)), 'source_ref_count': len(locators)})
            added.append(cid)
        return added

    def expand_two_hop(self, item, eligible, seen, remaining):
        """Enumerate three allowed patterns, never generic BFS or recursive expansion."""
        paths, candidates = [], {}
        def receipt(first, second, end):
            return {"nodes": [item["node_id"], first["target"], end],
                    "edges": [{k: edge[k] for k in ("source", "target", "type")}
                              for edge in (first, second)]}
        for first in sorted(self.outgoing[item["node_id"]], key=lambda e: (e["type"], e["target"])):
            via = self.nodes[first["target"]]
            if first["type"] == "ABOUT" and via["props"]["kind"] == "component":
                for second in sorted(self.outgoing[via["id"]], key=lambda e: (e["type"], e["target"])):
                    if second["type"] == "PART_OF":
                        paths.append({**receipt(first, second, second["target"]), "relation": "PART_OF",
                                      "component": via["props"]["component"],
                                      "equipment": self.nodes[second["target"]]["props"]["equipment"]})
            if first["type"] not in ("CITES", "DESCRIBES_SYMPTOM"):
                continue
            for second in self.incoming[via["id"]]:
                if second["type"] != first["type"] or second["source"] not in eligible:
                    continue
                node, card = eligible[second["source"]]
                cid = card["card_id"]
                if cid in seen:
                    continue
                related = candidates.setdefault(cid, {"card_id": cid, "version": card["version"],
                                                       "node_id": node["id"], "paths": []})
                path = {**receipt(first, second, node["id"]), "relation": first["type"]}
                if first["type"] == "CITES":
                    path.update(source_id=via["props"]["source_id"], document_version=via["props"]["document_version"],
                                cited_locators=list(first["props"]["locators"]),
                                related_locators=list(second["props"]["locators"]))
                else:
                    path.update(label=via["label"], review_status="needs_review")
                related["paths"].append(path)
        # Ordering is an identifier order, not a relevance/safety ranking.
        chosen = sorted(candidates)[:min(MAX_RELATED_PER_CARD, remaining)]
        item.update(paths=paths[:MAX_RELATED_PER_CARD], paths_omitted=max(0, len(paths)-MAX_RELATED_PER_CARD),
                    related_cards=[candidates[cid] for cid in chosen], related_cards_omitted=len(candidates)-len(chosen))
        for related in item["related_cards"]:
            related["paths_omitted"] = max(0, len(related["paths"])-MAX_PATHS_PER_REFERENCE)
            related["paths"] = related["paths"][:MAX_PATHS_PER_REFERENCE]
        seen.update(chosen)
        return remaining-len(chosen)

    def describe(self, node, card):
        result = {"card_id": card["card_id"], "version": card["version"], "node_id": node["id"],
                  "classifications": [], "citations": [], "symptom_candidates": [],
                  "held_citations": [deepcopy(s) for s in node["props"]["provenance"]["sources"] if not s.get("document_version")]}
        for edge in self.outgoing[node["id"]]:
            target = self.nodes[edge["target"]]; props = target["props"]
            if edge["type"] == "ABOUT":
                result["classifications"].append({"node_id": target["id"], "kind": props["kind"],
                    "equipment": props["equipment"], "component": props.get("component")})
            elif edge["type"] == "CITES":
                result["citations"].append({"node_id": target["id"], "source_id": props["source_id"],
                    "document_version": props["document_version"], "locators": list(edge["props"]["locators"])})
            elif edge["type"] == "DESCRIBES_SYMPTOM":
                result["symptom_candidates"].append({"node_id": target["id"], "label": target["label"],
                    "review_status": "needs_review"})
        return result


def explain(output, cards, eq_type, eq_id, *, mode=None, path=None, cited_chunks=None, depth=None,
            published_card_ids=()):
    """None means disabled. Failures omit graph details, never change the answer."""
    mode = os.environ.get("SHIFTLINK_KG_MODE", "off") if mode is None else mode
    if mode == "off":
        return None
    result = {"mode": "explain", "schema_version": SCHEMA, "graph_sha256": None, "status": "unavailable",
              "reason": "unsupported_mode", "cards": [], "unmatched": [],
              "retrieval_used": False, "synthetic_assets_used": False}
    if mode != "explain":
        return result
    depth = str(os.environ.get("SHIFTLINK_KG_DEPTH", "1") if depth is None else depth)
    if depth == "2":
        result["depth"] = 2
    if output.get("no_knowledge") or output.get("review_queue") or output.get("validation_errors"):
        return {**result, "status": "withheld", "reason": "answer_withheld"}
    if not output.get("cited_card_ids"):
        return {**result, "status": "empty", "reason": "no_cited_cards"}
    try:
        graph = GraphSnapshot(Path(path or os.environ.get("SHIFTLINK_KG_PATH") or DEFAULT_GRAPH))
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
        return {**result, "reason": "graph_missing_or_invalid"}
    result["graph_sha256"] = graph.digest
    visible = defaultdict(list)
    for card in cards:
        try:
            card = card_dict(card)
        except (ValueError, TypeError):
            continue
        visible[card["card_id"]].append(card)
    added = graph.add_publications(visible, published_card_ids, eq_type, eq_id)
    if added:
        result['publication_overlay'] = {'card_ids': added, 'scope': 'validated_query_snapshot'}
    for cid in dict.fromkeys(output["cited_card_ids"]):
        match, reason = graph.bind_current(cid, visible, eq_type, eq_id)
        if match:
            node, card = match
            # Only final cited roots require chunk binding; related references are not evidence.
            bound = cited_chunks is None or any(
                row.get("metadata", {}).get("kind") == "card"
                and row["metadata"].get("source") == cid
                and row["metadata"].get("version", card["version"]) == card["version"]
                and nonblank(card["know_how"]) and card["know_how"] in row.get("text", "")
                for row in cited_chunks)
            if bound:
                result["cards"].append(graph.describe(node, card))
                continue
            reason = "cited_chunk_mismatch"
        result["unmatched"].append({"card_id": cid, "reason": reason})
    if depth == "2" and result["cards"]:
        eligible = {}
        for cid in visible:
            match, _ = graph.bind_current(cid, visible, eq_type, eq_id)
            if match:
                eligible[match[0]["id"]] = match
        seen, remaining = set(output["cited_card_ids"]), MAX_RELATED_PER_RESPONSE
        for item in result["cards"]:
            remaining = graph.expand_two_hop(item, eligible, seen, remaining)
    result["status"] = "partial" if result["cards"] and result["unmatched"] else "ok" if result["cards"] else "unmatched"
    result["reason"] = "" if result["status"] == "ok" else "some_citations_not_bound"
    return result
