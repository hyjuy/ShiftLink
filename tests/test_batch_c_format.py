"""C review rendering follows A and preserves human decisions on regeneration."""
import importlib.util
import json
from pathlib import Path


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
        assert card["status"] == "draft" and card["grade"] == "L0"
