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


def test_pump_noise_keeps_its_symptom_card_after_observation_review():
    provider = load_card_provider(KB / "kb_cards.json").provider
    hits = provider.search_cards(query="펌프 소음", equipment_ids=["HPU"])
    assert hits and hits[0]["card_id"] == "K-1004"


def test_t4_safety_cards_only_in_handover_mode():
    provider = load_card_provider(KB / "kb_cards.json").provider
    t4_safety = {c.card_id for c in provider.cards if c.tacit_type == "T4" and c.safety_flag}
    assert t4_safety
    query = {c["card_id"] for c in provider.search_safety_cards(equipment_ids=["HPU"])}
    handover = {c["card_id"] for c in provider.search_safety_cards(equipment_ids=["HPU"], include_handover=True)}
    assert not query & t4_safety
    assert t4_safety <= handover


def test_t4_evidence_text_is_kb_only_and_used_only_for_handover():
    import json
    kb = json.loads((KB / "kb_cards.json").read_text(encoding="utf-8"))
    evidence = kb["evidence_text"]
    t4_ids = {c["card_id"] for c in kb["cards"] if c["tacit_type"] == "T4"}
    assert evidence and set(evidence) <= t4_ids
    events = json.loads((KB / "20260930-T4/events.json").read_text(encoding="utf-8"))
    text = "\n".join(evidence.values())
    for ev in events:  # never the answer, never a dev/sealed event
        assert ev["true_cause"] not in text
        if ev["split"] != "kb":
            assert " ".join(ev["timeline"]) not in text

    provider = load_card_provider(KB / "kb_cards.json", min_top_relevance=0).provider
    card = next(c for c in provider.cards if c.card_id in evidence)
    word = sorted(provider._evidence_tokens[card.card_id] - provider._common_tokens)[0]
    score = lambda handover: next(  # noqa: E731
        i for i, c in enumerate(provider.search_cards(query=word, equipment_ids=["HPU"], k=100, handover=handover))
        if c["card_id"] == card.card_id)
    assert score(True) < score(False)  # evidence words lift the card only for a handover memo
