"""The merged KB list (kb_cards.json) and handover-only T4 safety notices."""

import importlib.util
from pathlib import Path

from shiftlink.rag.loader import load_card_provider

KB = Path(__file__).resolve().parents[1] / "docs/data/knowledge_cards/kb"


def _build_module():
    spec = importlib.util.spec_from_file_location("build_kb", KB / "build_kb.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_kb_cards_json_matches_batches():
    build = _build_module()
    kb = build.build()
    assert (KB / "kb_cards.json").read_text(encoding="utf-8") == build.render(kb), "rerun build_kb.py"
    ids = [c["card_id"] for c in kb["cards"]]
    assert len(ids) == len(set(ids)) == kb["_meta"]["total"]
    assert load_card_provider(KB / "kb_cards.json").seen == kb["_meta"]["total"]


def test_t4_safety_cards_only_in_handover_mode():
    provider = load_card_provider(KB / "kb_cards.json").provider
    t4_safety = {c.card_id for c in provider.cards if c.tacit_type == "T4" and c.safety_flag}
    assert t4_safety
    query = {c["card_id"] for c in provider.search_safety_cards(equipment_ids=["HPU"])}
    handover = {c["card_id"] for c in provider.search_safety_cards(equipment_ids=["HPU"], include_handover=True)}
    assert not query & t4_safety
    assert t4_safety <= handover
