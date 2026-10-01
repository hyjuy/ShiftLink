"""Read-only adoption gate. Registration and mechanical validation are not approval."""
import json
import hashlib
import re
from pathlib import Path

from shiftlink.data.generation import ApprovedScope

HERE = Path(__file__).parent
ROOT = HERE.parents[4]


def adoption_issues(cards, here=HERE, root=ROOT):
    manifest_path = here / "policy_manifest.json"
    if not manifest_path.exists():
        return {c["card_id"]: ["policy_manifest_missing"] for c in cards}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_pin = f"docs/data/knowledge_cards/kb/20260930-C/policy_manifest.json@sha256:{hashlib.sha256(manifest_path.read_bytes()).hexdigest()}"
    registry = json.loads((root / "seeds/source_registry.json").read_text(encoding="utf-8"))
    policy = json.loads((root / "splits/prototype_split.json").read_text(encoding="utf-8"))
    sources = {s["source_id"]: s for s in registry["sources"]}
    assignments = {g["group_id"]: g for g in policy["assignments"]}
    result = {}
    for card in cards:
        reasons = []
        if card["provenance"].get("index_version") != manifest_pin:
            reasons.append("policy_manifest_pin_mismatch")
        for ref in card["provenance"]["sources"]:
            source = sources.get(ref["source_id"])
            if not source or source.get("review_status") != "approved_for_draft":
                reasons.append(f"source_scope_unapproved:{ref['source_id']}")
                continue
            locator = ref["locator"].split(" | ", 1)[-1]
            linked = False
            for raw in source.get("approved_scope", []):
                try:
                    scope = ApprovedScope.model_validate(raw)
                except ValueError:
                    continue
                if (scope.locator, scope.document_version) != (locator, ref.get("document_version")):
                    continue
                if source["is_synthetic"]:
                    linked = (scope.kind == "case" and scope.group_id == source["group_id"]
                              and set(source["reference_ids"]) <= set(scope.reference_ids)
                              and scope.text_sha256 == source["local_snapshot"]["item_sha256"])
                else:
                    linked = (scope.kind == "background" and scope.group_id is None and not scope.reference_ids
                              and any(x["locator"] == locator and x["document_version"] == scope.document_version
                                      and x["text_sha256"] == scope.text_sha256 for x in source["review_candidates"]))
                if linked:
                    break
            if not linked:
                reasons.append(f"approved_scope_not_linked:{ref['source_id']}")
        entry = manifest["cards"].get(card["card_id"])
        if not entry:
            reasons.append("card_lineage_record_missing")
        else:
            supporting = (card.get("generalization_evidence") or {}).get("supporting_event_ids", [])
            actual_groups = {manifest["event_groups"].get(eid) for eid in supporting}
            if None in actual_groups or actual_groups != set(entry["group_ids"]):
                reasons.append("supporting_event_lineage_mismatch")
            if len(actual_groups) != entry["independent_supporting_group_count"]:
                reasons.append("supporting_group_count_mismatch")
            for gid in actual_groups - {None}:
                group = assignments.get(gid)
                if not group or group.get("lineage_review_status") != "approved":
                    reasons.append(f"lineage_assignment_unconfirmed:{gid}")
                elif group["split"] != card["split"]:
                    reasons.append(f"card_split_differs_from_group:{gid}")
            if card["tacit_type"] == "T6" and len(actual_groups - {None}) < 2:
                reasons.append("independent_repeat_evidence_insufficient")
        if reasons:
            result[card["card_id"]] = reasons
    return result


def unapproved_adoption_issues(cards, here=HERE, root=ROOT):
    """Honor the recorded user promotion only for its exact reviewed card snapshots."""
    issues = adoption_issues(cards, here, root)
    record_path = here / "l1-promotion-20261001.json"
    if not record_path.exists():
        return issues
    record = json.loads(record_path.read_text(encoding="utf-8"))
    checklist = root / record["review_file"]
    if record.get("authorization") != "explicit_user_request":
        return issues
    checksum = hashlib.sha256(checklist.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    review_blocks = {
        match[1]: hashlib.sha256(match[0].strip().encode("utf-8")).hexdigest()
        for match in re.finditer(r"^## (K-\d{4})\b[\s\S]*?(?=^## K-\d{4}\b|\Z)",
                                 checklist.read_text(encoding="utf-8"), re.M)
    }
    for card in cards:
        entry = record["cards"].get(card["card_id"], {})
        reviewed = (review_blocks.get(card["card_id"]) == entry["review_block_sha256"]
                    if "review_block_sha256" in entry else checksum == record["review_sha256_lf"])
        digest = hashlib.sha256(json.dumps(card, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        if (reviewed and entry.get("verdict") == "accepted" and entry.get("card_sha256") == digest
                and (card["status"], card["grade"]) == ("accepted", "L1")
                and set(issues.get(card["card_id"], [])) <= set(entry.get("pending_policy_issues", []))):
            issues.pop(card["card_id"], None)
    return issues


if __name__ == "__main__":
    cards = json.loads((HERE / "cards.json").read_text(encoding="utf-8"))
    issues = adoption_issues(cards)
    print(json.dumps({"kb_ready": not issues, "blocked_cards": len(issues), "reasons": issues}, ensure_ascii=False, indent=1))
    raise SystemExit(1 if issues else 0)
