"""10/15 stage 1: score every config-C evidence chunk for relevance, without generating answers.

    python -m shiftlink.rag2.evidence_score --dir <rag dir> --scorer judge [--host URL]        # v1 judge, Ollama logprobs
    python -m shiftlink.rag2.evidence_score --dir <rag dir> --scorer decider --model <path>    # Mapika/decider-2b
    python -m shiftlink.rag2.evidence_score --dir <rag dir> report                              # AUROC tables, no model
    python -m shiftlink.rag2.evidence_score test

Rows go to <rag dir>/escore__<scorer>.jsonl, one per (qid, chunk): rank, gold (generate.score's gold_hit), answerable,
p = distribution over the judge's 0..3 rubric, and for the decider also yes = P(evidence helps). Reruns skip written rows.
The judge payload is generate.judge's, plus logprobs: the score digit is a single token, so its top_logprobs are the
distribution (normalised over 0..3). The decider gets the same rubric in English (its card: English only, so this run
also measures how it copes with Korean questions and mixed Korean/English evidence).
"""
import argparse
import json
import math
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from .generate import CONFIGS, JUDGE_PROMPT, Retriever, evidence
from .retrieve import gold_hit

RUBRIC = ["0: unrelated to the question (greeting, schedule, specification of something else, a different task)",
          "1: only the equipment or some words are similar; the situation is different",
          "2: the same situation; it helps the worker check or act",
          "3: it directly covers what the question asks"]
YES_Q = "Does this evidence help answer the worker's question?"
SCORE_Q = "How well does this evidence answer the worker's question?"


def pairs(d: Path, cfg="C") -> list[dict]:
    items = json.loads((d / "dev.json").read_text(encoding="utf-8"))
    ret = Retriever(d, CONFIGS[cfg], items, "http://127.0.0.1:11434")
    out = []
    for i, it in enumerate(items):
        for k, r in enumerate(evidence(ret.rows, ret.rank(i, it, top=ret.cfg.get("top", 20)), ret.cfg)):
            out.append({"qid": it["qid"], "question": it["question"], "answerable": it["answerable"], "rank": k,
                        "chunk": r, "gold": bool(it["answerable"] and gold_hit(r, it))})
    return out


KEEP_ALIVE = None   # the app sets -1 (judge-only server); evaluation runs leave it unset


def judge_dist(question: str, chunk: dict, host: str, model="exaone-sft-judge", ctx=None) -> list[float] | None:
    m = chunk["metadata"]
    body = f"질문: {question}\n\n카드 제목: {m.get('section') or m['source']}\n증상: -\n내용: {chunk['text'][:600]}"
    payload = {"model": model, "messages": [{"role": "system", "content": JUDGE_PROMPT}, {"role": "user", "content": body}],
               "stream": False, "format": {"type": "object", "properties": {"score": {"type": "integer", "enum": [0, 1, 2, 3]}},
                                           "required": ["score"]}, "options": {"temperature": 0, "num_ctx": ctx or 4096, "num_predict": 20},
               "logprobs": True, "top_logprobs": 20, **({"keep_alive": KEEP_ALIVE} if KEEP_ALIVE is not None else {})}
    # This judge emits its score by token 6; the unused closing JSON token need not be decoded.
    if model in ('exaone-sft-judge', 'exaone-sft-judge:latest'):
        payload['options']['num_predict'] = 6
    for _ in range(3):
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(f"{host}/api/chat", data=json.dumps(payload).encode()), timeout=300))
            score = digit_dist(d.get("logprobs") or [])
            if score is not None or payload['options']['num_predict'] == 20:
                return score
            payload['options']['num_predict'] = 20
        except (urllib.error.HTTPError, urllib.error.URLError, ValueError, KeyError):
            time.sleep(1)
    return None


def digit_dist(logprobs: list[dict]) -> list[float] | None:
    """Distribution over 0..3 at the first score-digit token; None if no digit position or no mass on 0..3."""
    for e in logprobs:
        if e["token"].strip() in ("0", "1", "2", "3"):
            p = [0.0] * 4
            for x in e.get("top_logprobs", []):
                t = x["token"].strip()
                if t in ("0", "1", "2", "3"):
                    p[int(t)] += math.exp(x["logprob"])
            s = sum(p)
            return [v / s for v in p] if s else None
    return None


def state(question: str, chunk: dict, trunc: int | None = None) -> str:
    """trunc: keep the first N characters of the evidence text (10/16 variant B; the judge reads 600)."""
    m = chunk["metadata"]
    where = f"card {m['source']}" if m["kind"] != "source" else f"{m['source']} page {m['page']}"
    return f"Worker's question (Korean):\n{question}\n\nEvidence ({where}):\n{chunk['text'][:trunc]}"


def run(d: Path, scorer: str, host: str, model: str | None, batch: int, name: str | None = None, trunc: int | None = None):
    out = d / f"escore__{name or scorer}.jsonl"
    done = {(r["qid"], r["chunk_id"]) for r in map(json.loads, open(out, encoding="utf-8"))} if out.exists() else set()
    todo = [p for p in pairs(d) if (p["qid"], p["chunk"]["chunk_id"]) not in done]
    print(f"{len(done)} done, {len(todo)} to score", flush=True)
    dec = None
    if scorer == "decider":
        sys.path.insert(0, model)                    # the model repo ships its decider/ package
        from decider.infer import Decider
        dec = Decider(model, use_graphs=False)       # graphs recompile for every new length bucket: 4% GPU on our states
    elif scorer == "decider_gguf":                   # model = the .gguf; decider/ package and decide_gguf.py on PYTHONPATH
        from decide_gguf import GGUFDecider
        g = GGUFDecider(model, n_ctx=4096)
        one = lambda st, q: g.decide(st, [q], max_ctx_tokens=2048)[0]   # one question per decode, as decide_batch rows
        dec = type("G", (), {"decide_batch": staticmethod(lambda reqs, max_ctx_tokens=2048: [
            [dict(r, probs_list=[r["probs"][o] for o in qs[0]["options"]])] for r, qs in ((one(st, qs[0]), qs) for st, qs in reqs)])})()
    t0 = time.time()
    with open(out, "a", encoding="utf-8") as f:
        for k in range(0, len(todo), batch):
            part = todo[k:k + batch]
            if dec is None:
                res = [{"p": judge_dist(x["question"], x["chunk"], host)} for x in part]
            else:
                # one question per row: decide() packs a request's questions into one row, and packed answers see the
                # earlier question text (model card: up to 12% of answers change with the order)
                reqs = [r for x in part for r in ((state(x["question"], x["chunk"], trunc), [{"question": SCORE_Q, "options": RUBRIC}]),
                                                  (state(x["question"], x["chunk"], trunc), [{"question": YES_Q, "options": ["no", "yes"]}]))]
                ans = dec.decide_batch(reqs, max_ctx_tokens=2048)
                res = [{"p": ans[2 * j][0]["probs_list"], "yes": ans[2 * j + 1][0]["probs"]["yes"]} for j in range(len(part))]
            for x, r in zip(part, res):
                f.write(json.dumps({"qid": x["qid"], "chunk_id": x["chunk"]["chunk_id"], "rank": x["rank"], "gold": x["gold"],
                                    "answerable": x["answerable"], **r}, ensure_ascii=False) + "\n")
            f.flush()
            n = k + len(part)
            if n % 100 < batch or n == len(todo):
                print(f"{n}/{len(todo)} {time.time() - t0:.0f}s", flush=True)


def auroc(pos: list[float], neg: list[float]) -> float | None:
    """P(score of a positive > score of a negative), ties count half (Mann-Whitney)."""
    if not pos or not neg:
        return None
    allv = sorted([(v, 1) for v in pos] + [(v, 0) for v in neg])
    rank_sum, i = 0.0, 0
    while i < len(allv):
        j = i
        while j < len(allv) and allv[j][0] == allv[i][0]:
            j += 1
        avg = (i + j + 1) / 2                         # mean of 1-based ranks i+1..j
        rank_sum += avg * sum(1 for x in allv[i:j] if x[1])
        i = j
    return (rank_sum - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


FEATURES = {
    "rule(argmax>=2)": lambda r: float(max(range(4), key=lambda k: r["p"][k]) >= 2),
    "P(>=2)": lambda r: r["p"][2] + r["p"][3],
    "E[score]": lambda r: sum(k * v for k, v in enumerate(r["p"])),
    "yes": lambda r: r.get("yes"),
}


def report(d: Path):
    items = {it["qid"]: it["answerable"] for it in json.loads((d / "dev.json").read_text(encoding="utf-8"))}
    print("| 채점기 | 특징 | 조각 AUROC (정답 근거 대 나머지) | 문항 AUROC (답 있음 대 없음, 최댓값) | 점수 누락 |\n|---|---|---|---|---|")
    for f in sorted(d.glob("escore__*.jsonl")):
        rows = [json.loads(l) for l in open(f, encoding="utf-8")]
        ok = [r for r in rows if r.get("p")]
        for name, fn in FEATURES.items():
            if fn(ok[0]) is None:
                continue
            ans = [r for r in ok if r["answerable"]]
            chunk = auroc([fn(r) for r in ans if r["gold"]], [fn(r) for r in ans if not r["gold"]])
            best = {}
            for r in ok:
                best[r["qid"]] = max(best.get(r["qid"], 0.0), fn(r))
            q = auroc([best.get(k, 0.0) for k, a in items.items() if a], [best.get(k, 0.0) for k, a in items.items() if not a])
            print(f"| {f.stem.split('__')[1]} | {name} | {chunk:.3f} | {q:.3f} | {len(rows) - len(ok)} |")


def self_test():
    assert auroc([1, 2], [0]) == 1.0 and auroc([0], [1]) == 0.0 and auroc([1], [1]) == 0.5
    lp = [{"token": '{"', "top_logprobs": []}, {"token": "1", "top_logprobs": [
        {"token": "1", "logprob": math.log(.6)}, {"token": "2", "logprob": math.log(.3)}, {"token": "4", "logprob": math.log(.1)}]}]
    p = digit_dist(lp)
    assert abs(p[1] - 2 / 3) < 1e-9 and abs(p[2] - 1 / 3) < 1e-9 and digit_dist(lp[:1]) is None
    r = {"p": [0, .62, .35, .03]}
    assert FEATURES["rule(argmax>=2)"](r) == 0.0 and abs(FEATURES["P(>=2)"](r) - .38) < 1e-9
    print("self-test ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="score", choices=["score", "report", "test"])
    ap.add_argument("--dir", type=Path)
    ap.add_argument("--scorer", choices=["judge", "decider", "decider_gguf"])
    ap.add_argument("--host", default="http://127.0.0.1:11434")
    ap.add_argument("--model", help="decider: local snapshot of Mapika/decider-2b")
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--limit-q", type=int, help="smoke test: only the first N questions' chunks")
    ap.add_argument("--name", help="output escore__<name>.jsonl (default: the scorer), e.g. decider_ko for the tuned model")
    ap.add_argument("--trunc", type=int, help="decider scorers: evidence text cut to N characters (must match training)")
    a = ap.parse_args()
    if a.cmd == "test":
        return self_test()
    if a.cmd == "report":
        return report(a.dir)
    if a.limit_q:
        global pairs
        full = pairs
        pairs = lambda d, cfg="C": [p for p in full(d, cfg) if p["qid"] in
                                    {it["qid"] for it in json.loads((d / "dev.json").read_text(encoding="utf-8"))[:a.limit_q]}]
    run(a.dir, a.scorer, a.host, a.model, a.batch, a.name, a.trunc)


if __name__ == "__main__":
    main()
