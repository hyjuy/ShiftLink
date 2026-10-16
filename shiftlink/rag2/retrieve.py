"""RAG v2 stage 4: retrieval-only evaluation (no LLM).

    python -m shiftlink.rag2.retrieve --dir <rag dir> --size 450 --model bge-m3:567m [--mode dense|bm25|hybrid] [--no-filter]

Gold hit = a retrieved card chunk among gold cards, or a source chunk on a gold page +-1.
Reports recall@1/5/10 (any / card-only / source-only gold) and MRR on answerable items, and the
top-1 score distribution on unanswerable items (for a later abstain threshold).
"""
import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path

import numpy as np

from .embed import embed, prefixes, slug

COMMON_FOLDERS = {"shared", "safety", "COMMON"}


def load(d: Path, size: int):
    return [json.loads(l) for l in open(d / f"chunks_{size}.jsonl", encoding="utf-8")]


def toks(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+|[가-힣]+", text.lower())
    return [w[:2] if re.match(r"[가-힣]", w) and len(w) > 2 else w for w in words]  # crude Korean stem


class BM25:
    def __init__(self, docs: list[str], k1=1.2, b=0.75):
        self.tf = [Counter(toks(d)) for d in docs]
        self.len = np.array([sum(t.values()) for t in self.tf], float)
        df = Counter(w for t in self.tf for w in t)
        n = len(docs)
        self.idf = {w: math.log(1 + (n - c + .5) / (c + .5)) for w, c in df.items()}
        self.k1, self.b, self.avg = k1, b, self.len.mean()

    def scores(self, q: str) -> np.ndarray:
        s = np.zeros(len(self.tf))
        for w in set(toks(q)):
            if w not in self.idf:
                continue
            f = np.array([t.get(w, 0) for t in self.tf], float)
            s += self.idf[w] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len / self.avg))
        return s


def gold_hit(row: dict, item: dict) -> str | None:
    m = row["metadata"]
    if m["kind"] == "card" and f"card:{m['source']}" in item["relevant_sources"]:
        return "card"
    if m["kind"] == "source":
        for s in item["relevant_sources"]:
            if ":page_" in s:
                doc, page = s.rsplit(":page_", 1)
                if doc == m["source"] and abs(int(page) - m["page"]) <= 1:
                    return "source"
    return None


def query_vectors(d: Path, model: str, items: list[dict], host: str) -> np.ndarray:
    cache = d / f"qvec__{slug(model)}.npy"
    if cache.exists():
        q = np.load(cache)
        if len(q) == len(items):
            return q
    qp = prefixes(model)[1]
    q = np.vstack([embed([qp + it["question"] for it in items[i:i + 32]], model, host) for i in range(0, len(items), 32)])
    np.save(cache, q)
    return q


def rrf(*rankings, k=60, weights=None):
    s = Counter()
    for r, w in zip(rankings, weights or [1] * len(rankings)):
        for pos, idx in enumerate(r):
            s[idx] += w / (k + pos + 1)
    return [i for i, _ in s.most_common()]


def evaluate(d: Path, size: int, model: str | None, mode: str, use_filter: bool, host: str, top=20, bm25_w=1.0, card_model=None):
    rows = load(d, size)
    items = json.loads((d / "dev.json").read_text(encoding="utf-8"))
    folders = np.array([r["metadata"]["folder"] for r in rows])
    kinds = np.array([r["metadata"]["kind"] for r in rows])
    vec = np.load(d / f"vectors_{size}__{slug(model)}.npy") if mode != "bm25" else None
    qv = query_vectors(d, model, items, host) if mode != "bm25" else None
    bm = BM25([r["embed_text"] for r in rows]) if mode != "dense" else None
    cvec = np.load(d / f"vectors_{size}__{slug(card_model)}.npy") if card_model else vec   # card lane may use another model
    cqv = query_vectors(d, card_model, items, host) if card_model else qv
    res, unans = [], []
    for i, it in enumerate(items):
        mask = np.isin(folders, list(COMMON_FOLDERS | {it["eq"]})) if use_filter and it["eq"] else np.ones(len(rows), bool)
        idx = np.where(mask)[0]
        rank_d = idx[np.argsort(-(vec[idx] @ qv[i]))][:top].tolist() if vec is not None else []
        rank_b = idx[np.argsort(-bm.scores(it["question"])[idx])][:top].tolist() if bm is not None else []
        if mode == "lanes":   # cards: dense+BM25 fused; sources: dense only; interleave card, source, source, ...
            is_card = kinds[idx] != "source"
            ci, si = idx[is_card], idx[~is_card]
            card_rank = rrf(ci[np.argsort(-(cvec[ci] @ cqv[i]))][:top].tolist(),
                            ci[np.argsort(-bm.scores(it["question"])[ci])][:top].tolist(), weights=[1, bm25_w])
            src_rank = si[np.argsort(-(vec[si] @ qv[i]))][:top].tolist()
            ranking, c, s = [], iter(card_rank), iter(src_rank)
            for pick in ([c, s, s] * top)[:top]:
                nxt = next(pick, None)
                if nxt is not None:
                    ranking.append(nxt)
        else:
            ranking = rank_d if mode == "dense" else rank_b if mode == "bm25" else rrf(rank_d, rank_b, weights=[1, bm25_w])[:top]
        top1 = float(vec[ranking[0]] @ qv[i]) if vec is not None and ranking else None
        if not it["answerable"]:
            unans.append(top1)
            continue
        hits = [gold_hit(rows[j], it) for j in ranking[:10]]
        first = next((p for p, h in enumerate(hits) if h), None)
        res.append({"qid": it["qid"], "first": first, "kinds": [h for h in hits if h], "top1": top1,
                    "has_source_gold": any(":page_" in s for s in it["relevant_sources"]),
                    "top3": [rows[j]["chunk_id"] for j in ranking[:3]]})
    n = len(res)
    rec = lambda k, kind=None: sum(1 for r in res if r["first"] is not None and r["first"] < k
                                   and (kind is None or kind in r["kinds"][:1] or kind in r["kinds"])) / n
    src = [r for r in res if r["has_source_gold"]]
    summary = {"size": size, "model": model + (f" + cards:{card_model}" if card_model else ""), "mode": mode if mode not in ("hybrid", "lanes") else f"{mode}(bm25 w={bm25_w})", "filter": use_filter, "answerable": n,
               "R@1": round(rec(1), 3), "R@5": round(rec(5), 3), "R@10": round(rec(10), 3),
               "MRR": round(sum(1 / (r["first"] + 1) for r in res if r["first"] is not None) / n, 3),
               "card_R@5": round(sum(1 for r in res if "card" in r["kinds"]) / n, 3),
               "source_R@10(src-gold items)": round(sum(1 for r in src if "source" in r["kinds"]) / max(1, len(src)), 3),
               "ans_top1_p50": None if vec is None else round(float(np.median([r["top1"] for r in res])), 3),
               "unans_top1_p50": None if vec is None else round(float(np.median(unans)), 3)}
    return summary, res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--size", type=int, default=450)
    ap.add_argument("--model")
    ap.add_argument("--mode", default="dense", choices=["dense", "bm25", "hybrid", "lanes"])
    ap.add_argument("--no-filter", action="store_true")
    ap.add_argument("--host", default="http://127.0.0.1:11434")
    ap.add_argument("--bm25-weight", type=float, default=1.0)
    ap.add_argument("--card-model")
    a = ap.parse_args()
    summary, res = evaluate(a.dir, a.size, a.model, a.mode, not a.no_filter, a.host, bm25_w=a.bm25_weight, card_model=a.card_model)
    tag = f"{a.size}__{slug(a.model or 'none')}__{a.mode}{'_c' + slug(a.card_model) if a.card_model else ''}{a.bm25_weight if a.mode in ('hybrid', 'lanes') else ''}{'' if not a.no_filter else '__nofilter'}"
    (a.dir / f"retrieval__{tag}.json").write_text(json.dumps({"summary": summary, "rows": res}, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(a.dir / "experiments.tsv", "a", encoding="utf-8") as f:
        f.write("\t".join(str(v) for v in summary.values()) + "\n")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
