"""Score the QA eval set (eval/qa/<batch>/qa_*.json) against a live Ollama model.

    python eval/qa/score.py eval/qa/20260929/qa_dev.json --host http://127.0.0.1:11435 \
        --model exaone3.5:2.4b-instruct-q4_K_M --out eval/results/qa_dev_exaone.json

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

KB = ROOT / "docs/data/knowledge_cards/kb/kb_cards.json"


def score_item(item: dict, out: dict) -> dict:
    """Automatic per-question metrics from a label and a pipeline outcome."""
    cited = out["cited"]
    primary, acceptable = set(item["primary_card_ids"]), set(item["acceptable_card_ids"])
    abstained = out["no_knowledge"] or not cited
    row = {
        "safety_ok": set(item["safety_card_ids"]) <= set(out["safety"]),
        "wrong_cite_rate": (sum(c not in primary | acceptable for c in cited) / len(cited)) if cited else 0.0,
    }
    if item["answerable"]:
        row["hit"] = bool(primary & set(cited))
        row["partial"] = not row["hit"] and bool(acceptable & set(cited))
        row["retrieval_hit_at_1"] = out["ranked"][:1] != [] and out["ranked"][0] in primary
        row["retrieval_hit_at_k"] = bool(primary & set(out["ranked"]))
    else:
        row["abstain_ok"] = abstained
    return row


def summarize(rows: list[dict]) -> dict:
    ans = [r for r in rows if "hit" in r["score"]]
    unans = [r for r in rows if "abstain_ok" in r["score"]]
    rate = lambda rs, k: round(sum(r["score"][k] for r in rs) / len(rs), 3) if rs else None  # noqa: E731
    warm = sorted(r["e2e_s"] for r in rows[1:] if not r["error"])
    pick = lambda q: warm[max(0, -(-len(warm) * q // 100) - 1)] if warm else None  # noqa: E731  nearest-rank
    return {
        "n": len(rows), "answerable": len(ans), "unanswerable": len(unans),
        "citation_hit": rate(ans, "hit"), "citation_partial": rate(ans, "partial"),
        "retrieval_hit_at_1": rate(ans, "retrieval_hit_at_1"), "retrieval_hit_at_k": rate(ans, "retrieval_hit_at_k"),
        "wrong_cite_rate": rate(ans, "wrong_cite_rate"), "safety_ok": rate(rows, "safety_ok"),  # unanswerable: see abstain_ok
        "abstain_ok": rate(unans, "abstain_ok"),
        "review_queue": sum(bool(r["review_queue"]) for r in rows), "errors": sum(bool(r["error"]) for r in rows),
        "cold_s": rows[0]["e2e_s"] if rows else None, "p50_s": pick(50), "p95_s": pick(95),
    }


def run(items: list[dict], pipe: FixedPipeline) -> list[dict]:
    rows = []
    for item in items:
        obs = [{"signal": s, **v} for s, v in item["observations"].items()]
        payload = {"question": item["question"], "line_id": "L1", "eq_id": item["eq_id"], **({"observations": obs} if obs else {})}
        t, err = time.monotonic(), None
        try:
            res = pipe.run(payload)
            o = res.output
            out = {"answer": o.answer, "cited": list(o.cited_card_ids), "safety": [n.card_id for n in o.safety_notices],
                   "ranked": [c["card_id"] for c in res.tool_results.get("ranked_cards", [])],
                   "no_knowledge": o.no_knowledge, "review_queue": o.review_queue}
        except Exception as e:  # keep scoring; a failure is a result
            err = f"{type(e).__name__}: {e}"[:200]
            out = {"answer": "", "cited": [], "safety": [], "ranked": [], "no_knowledge": False, "review_queue": None}
        row = {"qid": item["qid"], "eq_id": item["eq_id"], "answerable": item["answerable"],
               "e2e_s": round(time.monotonic() - t, 3), "error": err, **out}
        row["score"] = score_item(item, out)
        rows.append(row)
        print(f"{item['qid']} {item['eq_id']} {row['e2e_s']:5.1f}s cited={out['cited']} {row['score']}", flush=True)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("qa_file")
    ap.add_argument("--host", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    items = json.loads(Path(args.qa_file).read_text(encoding="utf-8"))
    loaded = load_card_provider(KB)
    bind_tool_provider(loaded.provider)
    pipe = FixedPipeline(model=OllamaModel(host=args.host, model=args.model), tools=loaded.provider)
    rows = run(items, pipe)
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    report = {"qa_file": args.qa_file, "model": args.model, "git_rev": rev, "kb": str(KB.relative_to(ROOT)),
              "summary": summarize(rows), "rows": rows}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
