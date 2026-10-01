"""Score the QA eval set (eval/qa/<batch>/qa_*.json) against a live Ollama model.

    python eval/qa/score.py eval/qa/20260929/qa_dev.json --host http://127.0.0.1:11435 \
        --model exaone3.5:2.4b-instruct-q4_K_M --out eval/results/qa_dev_exaone.json
    python eval/qa/score.py eval/qa/20260930-T4/qa_dev_t4.json --mode handover --host ... --model ... --out ...

--mode handover sends each question as a handover memo (HandoverRequest) and keeps the
rendered handover method per row.

Automatic items only (see docs/collaboration/eval-qa-set-assignment-20260930.md);
key facts and fabrication are graded by a person from the saved answers.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shiftlink.agent.pipeline import FixedPipeline  # noqa: E402
from shiftlink.agent.tools import bind_tool_provider  # noqa: E402
from shiftlink.edge.ollama import OllamaModel  # noqa: E402
from shiftlink.rag.loader import load_card_provider  # noqa: E402
from eval.qa.label_contract import matches_primary, rank1_evaluable

KB = ROOT / "docs/data/knowledge_cards/kb/kb_cards.json"


def score_item(item: dict, out: dict, *, error: str | None = None) -> dict:
    """Automatic per-question metrics from a label and a pipeline outcome.

    An execution error is not a successful abstain: an empty citation list
    after a crash must not raise abstain_ok.
    """
    if item.get('evaluation_status') == 'deferred':
        return {'evaluation_deferred': True}
    cited = out["cited"]
    primary, acceptable = set(item["primary_card_ids"]), set(item["acceptable_card_ids"])
    abstained = out["no_knowledge"] or not cited
    row = {
        "safety_ok": set(item["safety_card_ids"]) <= set(out["safety"]),
        "wrong_cite_rate": (sum(c not in primary | acceptable for c in cited) / len(cited)) if cited else 0.0,
    }
    if item["answerable"]:
        row["hit"] = matches_primary(item, cited)
        row["partial"] = not row["hit"] and bool(acceptable & set(cited))
        row["retrieval_hit_at_1"] = matches_primary(item, out['ranked'][:1]) if rank1_evaluable(item) else None
        row["retrieval_hit_at_k"] = matches_primary(item, out['ranked'])
    else:
        row["abstain_ok"] = abstained and not error
    return row


def summarize(rows: list[dict]) -> dict:
    ans = [r for r in rows if "hit" in r["score"]]
    unans = [r for r in rows if "abstain_ok" in r["score"]]
    evaluated = [r for r in rows if not r['score'].get('evaluation_deferred')]
    def rate(rs, key):
        values = [r['score'][key] for r in rs if r['score'].get(key) is not None]
        return round(sum(values) / len(values), 3) if values else None
    warm = sorted(r["e2e_s"] for r in evaluated[1:] if not r["error"])
    pick = lambda q: warm[max(0, -(-len(warm) * q // 100) - 1)] if warm else None  # noqa: E731  nearest-rank
    return {
        "n": len(rows), "answerable": len(ans), "unanswerable": len(unans),
        "evaluated": len(evaluated), "deferred": len(rows) - len(evaluated),
        "retrieval_rank1_answerable_n": sum(r['score'].get('retrieval_hit_at_1') is not None for r in ans),
        "citation_hit": rate(ans, "hit"), "citation_partial": rate(ans, "partial"),
        "retrieval_hit_at_1": rate(ans, "retrieval_hit_at_1"), "retrieval_hit_at_k": rate(ans, "retrieval_hit_at_k"),
        "wrong_cite_rate": rate(ans, "wrong_cite_rate"), "safety_ok": rate(evaluated, "safety_ok"),  # unanswerable: see abstain_ok
        "abstain_ok": rate(unans, "abstain_ok"),
        "review_queue": sum(bool(r["review_queue"]) for r in rows), "errors": sum(bool(r["error"]) for r in rows),
        "cold_s": evaluated[0]["e2e_s"] if evaluated else None, "p50_s": pick(50), "p95_s": pick(95),
    }


def payload(item: dict, mode: str = "query", shift: str = "A") -> dict:
    """Pipeline input for one question. Handover requests carry no observations."""
    if mode == "handover":
        if item["observations"]:
            raise ValueError(f"{item['qid']}: 인계 모드는 관측값을 받지 않습니다")
        return {"memo_text": item["question"], "shift": shift, "eq_ids": [item["eq_id"]]}
    obs = [{"signal": s, **v} for s, v in item["observations"].items()]
    return {"question": item["question"], "line_id": "L1", "eq_id": item["eq_id"], **({"observations": obs} if obs else {})}


def run(items: list[dict], pipe: FixedPipeline, mode: str = "query", shift: str = "A") -> list[dict]:
    rows = []
    for item in items:
        if item.get('evaluation_status') == 'deferred':
            rows.append({'qid': item['qid'], 'eq_id': item['eq_id'], 'answerable': item['answerable'],
                         'e2e_s': 0.0, 'error': None, 'answer': '', 'cited': [], 'safety': [], 'ranked': [],
                         'no_knowledge': False, 'review_queue': None, 'score': {'evaluation_deferred': True}})
            print(f"{item['qid']} deferred: {item['defer_reason']}", flush=True)
            continue
        t, err = time.monotonic(), None
        try:
            res = pipe.run(payload(item, mode, shift))
            o = res.output
            out = {"answer": o.answer, "cited": list(o.cited_card_ids), "safety": [n.card_id for n in o.safety_notices],
                   "ranked": [c["card_id"] for c in res.tool_results.get("ranked_cards", [])],
                   "no_knowledge": o.no_knowledge, "review_queue": o.review_queue}
            if mode == "handover":
                out["handover_method"] = o.handover_method.model_dump() if o.handover_method else None
        except Exception as e:  # keep scoring; a failure is a result
            err = f"{type(e).__name__}: {e}"[:200]
            out = {"answer": "", "cited": [], "safety": [], "ranked": [], "no_knowledge": False, "review_queue": None}
            if mode == "handover":
                out["handover_method"] = None
        row = {"qid": item["qid"], "eq_id": item["eq_id"], "answerable": item["answerable"],
               "e2e_s": round(time.monotonic() - t, 3), "error": err, **out}
        row["score"] = score_item(item, out, error=err)
        rows.append(row)
        print(f"{item['qid']} {item['eq_id']} {row['e2e_s']:5.1f}s cited={out['cited']} {row['score']}", flush=True)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("qa_file")
    ap.add_argument("--host", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", choices=["query", "handover"], default="query")
    ap.add_argument("--shift", choices=["A", "B", "C"], default="A", help="인계 모드 근무조")
    args = ap.parse_args()

    items = json.loads(Path(args.qa_file).read_text(encoding="utf-8"))
    loaded = load_card_provider(KB)
    bind_tool_provider(loaded.provider)
    pipe = FixedPipeline(model=OllamaModel(host=args.host, model=args.model), tools=loaded.provider)
    rows = run(items, pipe, args.mode, args.shift)
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    report = {"qa_file": args.qa_file, "mode": args.mode, "model": args.model, "git_rev": rev, "kb": str(KB.relative_to(ROOT)),
              "summary": summarize(rows), "rows": rows}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
