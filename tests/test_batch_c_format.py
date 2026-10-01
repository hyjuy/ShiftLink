"""C review rendering follows A and preserves human decisions on regeneration."""
import importlib.util
import json
from pathlib import Path

import pytest


KB = Path(__file__).resolve().parents[1] / "docs/data/knowledge_cards/kb"


def test_c_review_uses_a_labels_and_keeps_legacy_and_current_decisions(tmp_path):
    spec = importlib.util.spec_from_file_location("c_build_docs", KB / "20260930-C/build_docs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.HERE = tmp_path
    cards = json.loads((KB / "20260930-C/cards.json").read_text(encoding="utf-8"))
    cards = [cards[0], next(c for c in cards if c["safety_flag"]), next(c for c in cards if c["tacit_type"] == "T6")]
    (tmp_path / "cards.json").write_text(json.dumps(cards, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "review.md").write_text(
        f"## {cards[0]['card_id']}\n- **사람 판정**: 수정\n- **사람 판정 근거**: 위치 확인\n\n"
        f"## {cards[1]['card_id']}\n- **판정**: 근거 부족\n- **판정 근거**: 모델 확인\n",
        encoding="utf-8",
    )
    module.build()
    review = (tmp_path / "review.md").read_text(encoding="utf-8")
    assert review.startswith("# KB-20260930-C 검수표")
    assert review.count("**판정**:") == len(cards)
    assert "**사람 판정**" not in review and "**검색 조건**" not in review
    assert "**조건**:" in review and "**작성 노트**:" in review
    assert "· ⚠ 안전 —" in review and "**안전 근거**:" in review
    assert "**판정**: 수정" in review and "**판정 근거**: 위치 확인" in review
    assert "**판정**: 근거 부족" in review and "**판정 근거**: 모델 확인" in review
    for card in cards:
        assert card["know_how"] in review and card["provenance"]["prompt_version"] in review
    module.build()
    assert (tmp_path / "review.md").read_text(encoding="utf-8") == review


def test_c_json_keeps_a_common_field_order_and_matches_outputs():
    reference = json.loads((KB / "20260929-A/cards.json").read_text(encoding="utf-8"))[0]
    cards = json.loads((KB / "20260930-C/cards.json").read_text(encoding="utf-8"))
    outputs = [c for path in (KB / "20260930-C/out").glob("*.json")
               for c in json.loads(path.read_text(encoding="utf-8"))]
    assert len(cards) == len(outputs) == 19
    assert {c["card_id"]: c for c in cards} == {c["card_id"]: c for c in outputs}
    for card in cards:
        common = [key for key in reference if key in card]
        assert list(card)[:len(common)] == common
        assert card["status"] == "accepted" and card["grade"] == "L1"


def test_c_promotion_matches_human_review_and_runtime_kb():
    import re
    review = (KB / "human-review-checklist-20260930.md").read_text(encoding="utf-8")
    cards = json.loads((KB / "20260930-C/cards.json").read_text(encoding="utf-8"))
    kb = json.loads((KB / "kb_cards.json").read_text(encoding="utf-8"))
    merged = {c["card_id"]: c for c in kb["cards"]}
    for card in cards:
        block = next(b for b in re.split(r"(?=^## K-\d{4})", review, flags=re.M)
                     if b.startswith("## " + card["card_id"] + " "))
        assert re.search(r"^- \*\*판정\*\*: accepted$", block, re.M)
        assert merged[card["card_id"]] == card


def test_c_promotion_does_not_clear_policy_issues_or_approve_changed_cards(monkeypatch):
    import copy
    spec = importlib.util.spec_from_file_location("c_policy_gate", KB / "20260930-C/policy_gate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cards = json.loads((KB / "20260930-C/cards.json").read_text(encoding="utf-8"))
    pending = module.adoption_issues(cards)
    assert len(pending) == 19
    assert module.unapproved_adoption_issues(cards) == {}
    changed = copy.deepcopy(cards)
    changed[0]["know_how"] += " changed"
    assert changed[0]["card_id"] in module.unapproved_adoption_issues(changed)
    pending[cards[0]["card_id"]].append("new_policy_issue")
    monkeypatch.setattr(module, "adoption_issues", lambda *args: copy.deepcopy(pending))
    assert "new_policy_issue" in module.unapproved_adoption_issues(cards)[cards[0]["card_id"]]


def test_c_promotion_rejects_a_changed_checklist(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("c_policy_gate", KB / "20260930-C/policy_gate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cards = json.loads((KB / "20260930-C/cards.json").read_text(encoding="utf-8"))
    pending = module.adoption_issues(cards)
    monkeypatch.setattr(module, "adoption_issues", lambda *args: pending.copy())
    record = json.loads((KB / "20260930-C/l1-promotion-20261001.json").read_text(encoding="utf-8"))
    record["review_file"] = "review.md"
    (tmp_path / "review.md").write_text("changed", encoding="utf-8")
    (tmp_path / "l1-promotion-20261001.json").write_text(json.dumps(record), encoding="utf-8")
    assert module.unapproved_adoption_issues(cards, tmp_path, tmp_path)


@pytest.mark.parametrize("change,allowed", [("unrelated", True), ("body", False), ("verdict", False), ("missing", False)])
def test_c_promotion_checks_only_its_own_review_block(tmp_path, monkeypatch, change, allowed):
    import copy
    import re
    spec = importlib.util.spec_from_file_location("c_policy_gate", KB / "20260930-C/policy_gate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cards = json.loads((KB / "20260930-C/cards.json").read_text(encoding="utf-8"))
    pending = module.adoption_issues(cards)
    monkeypatch.setattr(module, "adoption_issues", lambda *args: copy.deepcopy(pending))
    record = json.loads((KB / "20260930-C/l1-promotion-20261001.json").read_text(encoding="utf-8"))
    review = (KB / "human-review-checklist-20260930.md").read_text(encoding="utf-8")
    if change == "unrelated":
        review = "Unrelated A review update\n" + review
    else:
        blocks = re.split(r"(?=^## K-\d{4})", review, flags=re.M)
        for index, block in enumerate(blocks):
            if block.startswith("## K-1201 "):
                if change == "body":
                    blocks[index] = block.replace("- **노하우**:", "- **노하우**: changed", 1)
                elif change == "verdict":
                    blocks[index] = block.replace("- **판정**: accepted", "- **판정**: rejected", 1)
                else:
                    blocks[index] = ""
        review = "".join(blocks)
    record["review_file"] = "review.md"
    (tmp_path / "review.md").write_text(review, encoding="utf-8")
    (tmp_path / "l1-promotion-20261001.json").write_text(json.dumps(record), encoding="utf-8")
    issues = module.unapproved_adoption_issues(cards, tmp_path, tmp_path)
    assert ("K-1201" not in issues) is allowed
