"""Offline routing score for the autoresearch retrieval loop (no model, runs in seconds).

    python eval/qa/route_score.py [--kb PATH]

Primary  dev_route_acc: dev answerable Qs whose search rank-1 is a primary card
                        + dev unanswerable Qs that get no search result ("해당 지식 없음"), over all dev Qs.
Handover t4_route_acc: the same on eval/qa/20260930-T4/qa_dev_t4.json, dev only.
Deferred items and gold sets requiring multiple cards are excluded from rank-1;
their count is printed separately. Search itself is unchanged.
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
from eval.qa.label_contract import matches_primary, rank1_evaluable

QA = ROOT / "eval/qa/20260929"
KB = ROOT / "docs/data/knowledge_cards/kb/kb_cards.json"


def route(provider, item: dict, handover: bool = False) -> list[str]:
    obs = {s: v["value"] for s, v in item.get("observations", {}).items()} or None
    hits = provider.search_cards(query=item["question"], equipment_ids=[item["eq_id"]], k=5, observations=obs,
                                 handover=handover)
    return [c["card_id"] for c in hits]


def route_ok(item: dict, ranked: list[str]) -> bool | None:
    if not rank1_evaluable(item):
        return None
    if item["answerable"]:
        return matches_primary(item, ranked[:1])
    return not ranked


def score(provider, items: list[dict], handover: bool = False) -> tuple[int, list[str]]:
    eligible = [x for x in items if rank1_evaluable(x)]
    misses = [x["qid"] for x in eligible if not route_ok(x, route(provider, x, handover))]
    return len(eligible) - len(misses), misses


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
    h, h_miss = score(provider, t4, handover=True)  # handover memos run in handover mode in the pipeline
    print(f"dev_route_acc: {d}/{sum(rank1_evaluable(x) for x in dev)}")
    print(f"t4_route_acc: {h}/{sum(rank1_evaluable(x) for x in t4)}")
    print(f"t4_rank1_excluded: {' '.join(x['qid'] for x in t4 if not rank1_evaluable(x))}")
    print(f"sanity_route_acc: {s}/{sum(rank1_evaluable(x) for x in sanity)}")
    print(f"dev_misses: {' '.join(d_miss)}")
    print(f"t4_misses: {' '.join(h_miss)}")
    print(f"sanity_misses: {' '.join(s_miss)}")


if __name__ == "__main__":
    main()
