"""Validate and merge batch drafts; never promotes them to human acceptance."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
from shiftlink.agent.schemas import KnowledgeCard
from policy_gate import unapproved_adoption_issues


def merge():
    cards = [c for file in sorted((HERE / "out").glob("*.json"))
             for c in json.loads(file.read_text(encoding="utf-8"))]
    cards.sort(key=lambda c: c["card_id"])
    ids = [c["card_id"] for c in cards]
    assert len(ids) == len(set(ids)), "duplicate card IDs"
    slots = {s["card_id"]: s for s in json.loads((HERE / "plan.json").read_text(encoding="utf-8"))["slots"]}
    assert set(ids) == set(slots) and len(cards) == 19, "missing or extra plan slots"
    for card in cards:
        KnowledgeCard.model_validate(card)
        slot = slots[card["card_id"]]
        assert (card["equipment"], card["tacit_type"]) == (slot["equipment"], slot["tacit_type"]), card["card_id"]
        path, digest = card["provenance"]["prompt_version"].rsplit("@sha256:", 1)
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, f"changed prompt: {card['card_id']}"
    accepted = [card for card in cards if card["status"] == "accepted"]
    blocked = unapproved_adoption_issues(accepted, HERE, ROOT) if accepted else {}
    assert not blocked, f"KB adoption blocked by source/lineage contract: {blocked}"
    index = {"batch_id": "KB-20260930-C", "seed": 20260930, "prompts": {}}
    for file in sorted((HERE / "prompts").glob("*.md")):
        index["prompts"][file.stem] = {"path": file.relative_to(HERE.parents[4]).as_posix(),
                                       "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
    index_path = HERE / "prompts" / "index.json"
    if index_path.exists():
        previous = json.loads(index_path.read_text(encoding="utf-8"))
        assert previous == index, "prompt index changed; preserve the dispatched prompt and index"
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n",
                                                  encoding="utf-8", newline="\n")
    (HERE / "cards.json").write_text(json.dumps(cards, ensure_ascii=False, indent=1) + "\n",
                                    encoding="utf-8", newline="\n")
    print(f"merged {len(cards)} validated cards; run verify.py")


if __name__ == "__main__":
    merge()
