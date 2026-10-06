"""T6 exemptions and public case lineage must remain bound to reviewed evidence."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

GATE = Path(__file__).resolve().parents[1] / "docs/data/knowledge_cards/kb/20260930-C/policy_gate.py"

def digest(card):
    return hashlib.sha256(json.dumps(card, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

@pytest.fixture
def policy(tmp_path):
    spec = importlib.util.spec_from_file_location("tested_policy_gate", GATE)
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    (tmp_path / "seeds").mkdir()
    (tmp_path / "splits").mkdir()
    manifest = {"cards": {"K-9001": {"group_ids": ["G-SYN"], "independent_supporting_group_count": 1}},
                "event_groups": {"EV-9001": "G-SYN"}}
    manifest_path = tmp_path / "policy_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf8")
    card = {"card_id": "K-9001", "tacit_type": "T6", "split": "kb", "status": "accepted", "grade": "L1",
            "know_how": "Reviewed restart procedure",
            "provenance": {"sources": [], "index_version":
                "docs/data/knowledge_cards/kb/20260930-C/policy_manifest.json@sha256:" +
                hashlib.sha256(manifest_path.read_bytes()).hexdigest()},
            "generalization_evidence": {"supporting_event_ids": ["EV-9001"]}}
    (tmp_path / "splits/prototype_split.json").write_text(json.dumps(
        {"assignments": [{"group_id": "G-SYN", "split": "kb", "lineage_review_status": "approved"}]}))
    evidence = {"authorization": "explicit_user_request", "request": "Existing project exception",
                "reviewed_by": "Human reviewer", "date": "2026-10-02", "cards": {}, "exceptions": {}}
    sources = []
    def run():
        (tmp_path / "seeds/source_registry.json").write_text(json.dumps({"sources": sources}))
        (tmp_path / "t6_independent_evidence-20261002.json").write_text(json.dumps(evidence))
        return gate.adoption_issues([card], tmp_path, tmp_path)
    return gate, tmp_path, card, evidence, sources, run

def case(source_id, group="REAL-1", use_scope="K-9001 independent repeat evidence"):
    return {"source_id": source_id, "is_synthetic": False, "review_status": "approved_for_draft",
            "document_version": "v1", "approved_scope": [{
                "scope_id": source_id + "-case", "locator": "Public report p.1", "document_version": "v1",
                "text_sha256": "0" * 64, "allowed_claims": ["Event summary"], "exclusions": [],
                "reviewed_by": "Human reviewer", "reviewed_at": "2026-10-02T15:00:00+09:00",
                "use_scope": use_scope, "kind": "case", "group_id": group, "reference_ids": [source_id]}]}

@pytest.mark.parametrize("change", ["authorization", "reviewer", "request", "date", "empty", "hash", "content"])
def test_unapproved_or_changed_exception_is_rejected(policy, change):
    _, _, card, evidence, _, run = policy
    evidence["exceptions"][card["card_id"]] = {"reason": "No real case", "basis": "One synthetic group",
                                              "card_sha256": digest(card)}
    if change == "authorization": evidence["authorization"] = "pending"
    elif change == "reviewer": evidence["reviewed_by"] = " "
    elif change == "request": evidence["request"] = ""
    elif change == "date": evidence["date"] = "invalid"
    elif change == "empty": evidence["exceptions"][card["card_id"]] = {}
    elif change == "hash": evidence["exceptions"][card["card_id"]]["card_sha256"] = "f" * 64
    else: card["know_how"] += " changed"
    assert "independent_repeat_evidence_insufficient" in run()[card["card_id"]]

def test_exact_previously_approved_exception_remains_allowed(policy):
    _, _, card, evidence, _, run = policy
    evidence["exceptions"][card["card_id"]] = {"reason": "No real case", "basis": "One synthetic group",
                                              "card_sha256": digest(card)}
    assert run() == {}

@pytest.mark.parametrize("change", ["scope_missing", "wrong_card", "background", "no_group",
                                   "unapproved", "synthetic", "wrong_version", "missing_reviewer"])
def test_unlinked_public_case_cannot_count_as_independent_evidence(policy, change):
    _, _, card, evidence, sources, run = policy
    source = case("RC-1")
    scope = source["approved_scope"][0]
    if change == "scope_missing": source["approved_scope"] = []
    elif change == "wrong_card": scope["use_scope"] = "K-9002 independent repeat evidence"
    elif change == "background": scope["kind"] = "background"
    elif change == "no_group": scope["group_id"] = None
    elif change == "unapproved": source["review_status"] = "pending"
    elif change == "synthetic": source["is_synthetic"] = True
    elif change == "wrong_version": scope["document_version"] = "v2"
    else: scope["reviewed_by"] = ""
    sources.append(source)
    evidence["cards"][card["card_id"]] = {"case_group_ids": ["RC-1"]}
    assert "independent_repeat_evidence_insufficient" in run()[card["card_id"]]

def test_approved_case_group_supplements_synthetic_group(policy):
    _, _, card, evidence, sources, run = policy
    sources.append(case("RC-1"))
    evidence["cards"][card["card_id"]] = {"case_group_ids": ["RC-1"]}
    assert run() == {}

def test_two_sources_for_one_event_count_as_one_group(policy):
    _, root, card, evidence, sources, run = policy
    manifest_path = root / "policy_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["cards"][card["card_id"]] = {"group_ids": [], "independent_supporting_group_count": 0}
    manifest_path.write_text(json.dumps(manifest))
    card["provenance"]["index_version"] = (
        "docs/data/knowledge_cards/kb/20260930-C/policy_manifest.json@sha256:" +
        hashlib.sha256(manifest_path.read_bytes()).hexdigest())
    card["generalization_evidence"]["supporting_event_ids"] = []
    sources.extend([case("RC-1"), case("RC-2")])
    evidence["cards"][card["card_id"]] = {"case_group_ids": ["RC-1", "RC-2"]}
    assert "independent_repeat_evidence_insufficient" in run()[card["card_id"]]
    sources[1]["approved_scope"][0]["group_id"] = "REAL-2"
    assert run() == {}

def test_generic_l1_promotion_cannot_override_revoked_t6_approval(policy):
    gate, root, card, evidence, _, run = policy
    evidence["exceptions"][card["card_id"]] = {}
    run()
    review = "Reviewed card"
    (root / "review.md").write_text(review)
    record = {"authorization": "explicit_user_request", "review_file": "review.md",
              "review_sha256_lf": hashlib.sha256(review.encode()).hexdigest(),
              "cards": {card["card_id"]: {"verdict": "accepted", "card_sha256": digest(card),
                  "pending_policy_issues": ["independent_repeat_evidence_insufficient"]}}}
    (root / "l1-promotion-20261001.json").write_text(json.dumps(record))
    assert card["card_id"] in gate.unapproved_adoption_issues([card], root, root)
