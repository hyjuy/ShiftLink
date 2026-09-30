"""Build kb_cards.json: the one list of every accepted L1 KB card (what the app and eval load).

    python docs/data/knowledge_cards/kb/build_kb.py

Edit cards in their batch folder, then rerun. Add a batch by appending it to BATCHES.
The list lives under a "cards" key, not as a bare array, so batch verify.py ID-clash scans
(which only read top-level arrays) do not count it as a duplicate. Same inputs -> same bytes.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).parent
BATCHES = ["20260929-A", "20260930-T4"]
OUT = HERE / "kb_cards.json"


def build() -> dict:
    cards, batches = [], []
    for batch in BATCHES:
        raw = (HERE / batch / "cards.json").read_bytes()
        data = json.loads(raw)
        items = data if isinstance(data, list) else data.get("knowledge_cards") or data["cards"]
        kept = [c for c in items if (c.get("status"), c.get("grade"), c.get("split")) == ("accepted", "L1", "kb")]
        cards += kept
        batches.append({"batch": batch, "cards_in_file": len(items), "included": len(kept),
                        "sha256_lf": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()})
    ids = [c["card_id"] for c in cards]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    assert not dup, f"duplicate card_id across batches: {dup}"
    cards.sort(key=lambda c: c["card_id"])
    counts = {}
    for c in cards:
        counts[c["tacit_type"]] = counts.get(c["tacit_type"], 0) + 1
    meta = {"note": "자동 생성 — 직접 고치지 말고 배치 폴더를 고친 뒤 build_kb.py를 다시 실행", "total": len(cards),
            "by_tacit_type": dict(sorted(counts.items())), "batches": batches}
    return {"_meta": meta, "cards": cards}


def render(kb: dict) -> str:
    return json.dumps(kb, ensure_ascii=False, indent=1) + "\n"


if __name__ == "__main__":
    kb = build()
    OUT.write_text(render(kb), encoding="utf-8", newline="\n")
    print(f"kb_cards.json: {kb['_meta']['total']} cards {kb['_meta']['by_tacit_type']}")
