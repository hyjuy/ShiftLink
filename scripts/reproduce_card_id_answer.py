"""Replay the K-1001 title query with a real Ollama model; save raw evidence."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="http://localhost:11434")
    parser.add_argument("--model", default="qwen2.5:3b-instruct-q4_K_M")
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--mes", action="store_true", help="Include the default MES observations, as in the original failure")
    parser.add_argument("--baseline-revision", help="Load the three original pipeline modules from a local Git commit")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.baseline_revision:
        import importlib
        import re
        import subprocess
        if not re.fullmatch(r"[0-9a-f]{40}", args.baseline_revision):
            parser.error("--baseline-revision must be a full commit SHA")
        for name in ("shiftlink.agent.response", "shiftlink.agent.pipeline", "shiftlink.edge.ollama"):
            module = importlib.import_module(name)
            source = subprocess.check_output(
                ["git", "show", args.baseline_revision + ":" + name.replace(".", "/") + ".py"]
            )
            exec(compile(source, module.__file__, "exec"), module.__dict__)
    from shiftlink.agent.pipeline import FixedPipeline
    from shiftlink.edge.ollama import OllamaModel
    from shiftlink.rag.loader import load_card_provider

    kb = Path("docs/data/knowledge_cards/kb/kb_cards.json")
    card = next(c for c in json.loads(kb.read_text(encoding="utf8"))["cards"] if c["card_id"] == "K-1001")
    payload = {"question": card["title"], "line_id": "LN-0001", "eq_id": "HPU-01"}
    model = OllamaModel(host=args.host, model=args.model, timeout_s=120)
    original_post = model._post
    calls = []
    def post(path, data):
        if args.cpu:
            data["options"]["num_gpu"] = 0
        body = original_post(path, data)
        calls.append({"payload": data, "body": body})
        return body
    model._post = post
    pipeline = FixedPipeline(model=model, tools=load_card_provider(kb).provider)
    pipeline_inputs = []
    run = pipeline.run
    def capture(data):
        pipeline_inputs.append(data)
        return run(data)
    pipeline.run = capture
    if args.mes:
        from shiftlink.mes.server import MesService
        service = MesService(Path("docs/data/reference/00_plant_and_relations.json"))
        try:
            scan = service.record_scan({"class": "HPU", "conf": .95, "device_id": "card-id-repro"})
            service.query_pipeline = pipeline
            response = service.query({"question": card["title"], "scan_id": scan["scan"]["scan_id"]})
        finally:
            service.storage.close()
    else:
        response = pipeline.run(payload).output.model_dump(mode="json")
    report = {"input": payload, "model": args.model, "host": args.host,
              "cpu": args.cpu, "baseline_revision": args.baseline_revision,
              "mes": args.mes, "pipeline_inputs": pipeline_inputs, "calls": calls, "response": response}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps({"answer": response["answer"], "cited_card_ids": response["cited_card_ids"],
                      "review_queue": response["review_queue"], "validation_errors": response["validation_errors"],
                      "calls": len(calls), "evidence": str(args.output)}, ensure_ascii=False))
    if response["review_queue"] or not response["answer"] or not response["cited_card_ids"]:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
