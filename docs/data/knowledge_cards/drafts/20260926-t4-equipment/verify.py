"""Check this synthetic artifact batch using existing contracts; no KB writes."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path
import hashlib
import json
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT))
from pydantic import ValidationError
from eval.evaluators import evaluate_category_b
from shiftlink.agent.schemas import KnowledgeCard, HandoverMethod
from shiftlink.data.generation import _reject_unknown
from shiftlink.rag.retrieval import InMemoryToolProvider


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_catalog_ref(catalog, ref):
    value = catalog
    if "#/" in ref:
        path, pointer = ref.split("#", 1)
        assert path == "docs/data/reference/00_plant_and_relations.json"
        for key in pointer.split("/")[1:]:
            key = key.replace("~1", "/").replace("~0", "~")
            value = value[int(key)] if isinstance(value, list) else value[key]
    else:
        for part in ref.split("."):
            match = re.fullmatch(r"(\w+)(?:\[(\w+)=([^\]]+)\])?", part)
            assert match, ref
            field, selector, expected = match.groups()
            value = value[field]
            if selector:
                rows = [row for row in value if row.get(selector) == expected]
                assert len(rows) == 1, ref
                value = rows[0]
    return value


def main():
    cards = read(HERE / "cards.json")
    manifest = read(HERE / "manifest.json")
    mappings = read(HERE / "equipment-map.json")["cards"]
    sources = read(HERE / "synthetic-sources.json")
    catalog = read(ROOT / "docs/data/reference/00_plant_and_relations.json")
    equipment = {e["equipment_id"]: e for e in catalog["equipment"]}
    types = {t["equipment_type_id"]: t["type_code"] for t in catalog["equipment_types"]}
    specs = [s for name in ("specs-hpu-gr.json", "specs-rt-cv.json")
             for s in read(HERE / name)["specs"]]
    specs.sort(key=lambda s: s["method_key"])
    assert cards and len(cards) == len(mappings) == len(sources) == len(specs)
    assert len({s["method_key"] for s in specs}) == len(specs)
    assert len({c["card_id"] for c in cards}) == len(cards)
    assert [c["card_id"] for c in cards] == manifest["card_ids"]
    assert not set(manifest["card_ids"]) & set(manifest["prior_card_ids"])
    for name, value in manifest["input_hashes"].items():
        assert digest(ROOT / name) == value, ("changed input", name)
    assert digest(HERE / "cards.json") == manifest["cards_sha256"]
    negative = Counter()
    for card, mapping, source, spec in zip(cards, mappings, sources, specs):
        parsed = KnowledgeCard.model_validate(card)
        _reject_unknown(card, parsed.model_dump(mode="json"))
        assert evaluate_category_b({"case_id": card["card_id"], "input": card}, {"outcome": "valid"}).passed
        assert (card["tacit_type"], card["status"], card["grade"], card["split"]) == ("T4", "draft", "L0", "dev")
        assert card["confidence"] == 0 and card["provenance"]["event_ids"] == []
        assert card["safety_review"]["status"] == "pending_review"
        assert card["safety_flag"] and "합성" in card["safety_basis"]
        assert "합성" in card["title"] and "합성" in card["know_how"]
        assert card["type_payload"]["handover_method"] == spec["handover_method"]
        assert source["design"] == spec and source["is_synthetic"] is True
        assert source["direct_original_support_fields"] == []
        assert source["source_id"] == card["provenance"]["seed_ids"][0]
        assert mapping["card_id"] == card["card_id"]
        assert mapping["method_key"] == source["method_key"] == spec["method_key"]
        assert mapping["applicable_equipment_ids"] == spec["applicable_equipment_ids"]
        assert mapping["equipment_family"] == spec["equipment_family"]
        family = mapping["equipment_family"]
        assert card["equipment"] == (family if family in {"HPU", "GR", "RT", "CV"} else "COMMON")
        assert mapping["applicable_equipment_ids"]
        for eqid in mapping["applicable_equipment_ids"]:
            assert eqid in equipment
            assert types[equipment[eqid]["equipment_type_id"]] == family
        for eqid in mapping.get("related_equipment_ids", []):
            assert eqid in equipment
        assert mapping["catalog_refs"]
        for ref in mapping["catalog_refs"]:
            resolve_catalog_ref(catalog, ref)
        assert card["provenance"]["persona_id"] in {"V-11", "V-12", "V-13"}
        for field in HandoverMethod.model_fields:
            for mutation in ("missing", "blank"):
                bad = deepcopy(card)
                hm = bad["type_payload"]["handover_method"]
                if mutation == "missing":
                    del hm[field]
                else:
                    hm[field] = [" "] if field == "required_context" else " "
                try:
                    KnowledgeCard.model_validate(bad)
                    raise AssertionError(("accepted invalid T4", card["card_id"], field))
                except ValidationError as exc:
                    assert any(tuple(e["loc"][:3]) == ("type_payload", "handover_method", field) for e in exc.errors())
                assert evaluate_category_b({"case_id": "negative", "input": bad}, {"outcome": "invalid"}).passed
                negative[mutation] += 1
        try:
            InMemoryToolProvider(cards=[parsed])
            raise AssertionError("dev data accepted")
        except ValueError as exc:
            assert "does not accept dev/sealed cards" in str(exc)
        assert not InMemoryToolProvider(cards=[parsed.model_copy(update={"split": "kb"})]).cards
    previous = read(HERE.parent / "20260925-t4-synthetic/cards.json")
    pairs = []
    for a, b in combinations(previous + cards, 2):
        left = a["type_payload"]["handover_method"]
        right = b["type_payload"]["handover_method"]
        assert left != right, ("identical method", a["card_id"], b["card_id"])
        # Lexical triage only: independent reviewers judge semantic duplication.
        ratio = SequenceMatcher(None, json.dumps(left, ensure_ascii=False), json.dumps(right, ensure_ascii=False)).ratio()
        pairs.append({"left": a["card_id"], "right": b["card_id"], "similarity": round(ratio, 4)})
    review_path = HERE / "review-final.json"
    review_checked = False
    if review_path.exists():
        review = read(review_path)
        assert review["verdict"] == "pass"
        assert len(review["cards"]) == len(cards)
        assert {r["card_id"] for r in review["cards"]} == {c["card_id"] for c in cards}
        assert all(r["verdict"] == "pass" for r in review["cards"])
        for name, expected in review["input_hashes"].items():
            assert digest(HERE / name) == expected, ("stale review", name)
        review_checked = True
    result = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "cards_sha256": digest(HERE / "cards.json"),
        "schema_passed": len(cards), "negative_probes_rejected": sum(negative.values()),
        "negative_groups": dict(negative), "dev_gate_blocked": len(cards), "draft_L0_excluded": len(cards),
        "equipment_family_counts": dict(Counter(m["equipment_family"] for m in mappings)),
        "instance_coverage": {e["code"]: sum(e["equipment_id"] in m["applicable_equipment_ids"] for m in mappings)
                              for e in catalog["equipment"]},
        "all_card_pairs_checked": len(pairs), "top_lexical_pairs": sorted(pairs, key=lambda p: -p["similarity"])[:25],
        "original_method_support_fields": 0, "operational_adoption": False,
        "final_review_hashes_verified": review_checked,
        "scope": "Schema, inventory, declared applicability, provenance, gates, lexical triage. Not semantic proof or efficacy.",
        "verifier_sha256": digest(Path(__file__)),
    }
    (HERE / "validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("schema_passed", "negative_probes_rejected", "instance_coverage")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
