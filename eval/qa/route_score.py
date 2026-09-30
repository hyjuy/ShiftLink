"""Offline routing score for the autoresearch retrieval loop (no model, runs in seconds).

    python eval/qa/route_score.py [--kb PATH]

Primary  dev_route_acc: dev answerable Qs whose search rank-1 is a primary card
                        + dev unanswerable Qs that get no search result ("해당 지식 없음"), over all dev Qs.
Handover t4_route_acc: the same on eval/qa/20260930-T4/qa_dev_t4.json (20 blind handover questions, dev only).
Secondary sanity_route_acc: the same on sanity.json (card-derived 9/29 bench, answerable) + reserve.json (unanswerable).
qa_test.json is never read here: it is for the final score only.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shiftlink.rag.loader import load_card_provider  # noqa: E402

QA = ROOT / "eval/qa/20260929"
KB = ROOT / "docs/data/knowledge_cards/kb/kb_cards.json"


def route(provider, item: dict) -> list[str]:
    obs = {s: v["value"] for s, v in item.get("observations", {}).items()} or None
    hits = provider.search_cards(query=item["question"], equipment_ids=[item["eq_id"]], k=5, observations=obs)
    return [c["card_id"] for c in hits]


def route_ok(item: dict, ranked: list[str]) -> bool:
    if item["answerable"]:
        return bool(ranked) and ranked[0] in item["primary_card_ids"]
    return not ranked


def score(provider, items: list[dict]) -> tuple[int, list[str]]:
    misses = [x["qid"] for x in items if not route_ok(x, route(provider, x))]
    return len(items) - len(misses), misses


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", default=str(KB))
    args = ap.parse_args()
    provider = load_card_provider(args.kb).provider
    load = lambda name: json.loads((QA / name).read_text(encoding="utf-8"))  # noqa: E731
    dev = load("qa_dev.json")
    sanity = load("sanity.json") + load("reserve.json")
    d, d_miss = score(provider, dev)
    s, s_miss = score(provider, sanity)
    t4 = json.loads((QA.parent / "20260930-T4/qa_dev_t4.json").read_text(encoding="utf-8"))
    h, h_miss = score(provider, t4)
    print(f"dev_route_acc: {d}/{len(dev)}")
    print(f"t4_route_acc: {h}/{len(t4)}")
    print(f"sanity_route_acc: {s}/{len(sanity)}")
    print(f"dev_misses: {' '.join(d_miss)}")
    print(f"t4_misses: {' '.join(h_miss)}")
    print(f"sanity_misses: {' '.join(s_miss)}")


if __name__ == "__main__":
    main()
