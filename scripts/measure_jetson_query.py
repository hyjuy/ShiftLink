"""Measure actual MES HTTP + Ollama on Linux/Jetson, retaining raw answer evidence."""
import json
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shiftlink.agent.pipeline import FixedPipeline
from shiftlink.edge.ollama import ANSWER_MAX_CHARS, OllamaModel
from shiftlink.mes.server import MesService, _Handler, _run_ticks
from shiftlink.mes.storage import MesStorage
from shiftlink.rag.loader import load_card_provider


def memory():
    values = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        name, value = line.split(":", 1)
        values[name] = int(value.split()[0])
    status = Path("/proc/self/status").read_text()
    return {"at_s": time.monotonic(), "total_mib": values["MemTotal"] / 1024,
            "available_mib": values["MemAvailable"] / 1024,
            "mes_rss_mib": int(re.search(r"VmRSS:\s+(\d+)", status)[1]) / 1024}


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("jetson-live-result.json")
    kb = Path("docs/data/knowledge_cards/kb/kb_cards.json")
    card = next(c for c in json.loads(kb.read_text())["cards"] if c["card_id"] == "K-1001")
    questions = [card["title"], "기어·베인 펌프 출구 압력이 없을 때 확인 순서와 각 단계의 이유를 자세히 설명해줘"]
    samples, calls, readings, responses = [], [], [], []
    stop_sampling = threading.Event()
    def sample():
        while not stop_sampling.is_set():
            samples.append(memory())
            stop_sampling.wait(.2)
    sampler = threading.Thread(target=sample)
    stats = None
    stats_reader = None
    if shutil.which("tegrastats"):
        stats = subprocess.Popen(["tegrastats", "--interval", "200"], stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True)
        def read_stats():
            for line in stats.stdout:
                found = re.search(r"RAM (\d+)/(\d+)MB", line)
                if found:
                    readings.append({"used_mb": int(found[1]), "total_mb": int(found[2])})
        stats_reader = threading.Thread(target=read_stats)
        stats_reader.start()
    service = MesService(Path("docs/data/reference/00_plant_and_relations.json"),
                         MesStorage(output.with_suffix(".sqlite3")))
    model = OllamaModel(model="exaone3.5:2.4b-instruct-q4_K_M", num_ctx=4096, timeout_s=120)
    post_model = model._post
    def record(path, payload):
        body = post_model(path, payload)
        calls.append({"payload": payload, "body": body})
        return body
    model._post = record
    service.query_pipeline = FixedPipeline(model=model, tools=load_card_provider(kb).provider)
    handler = type("MeasuredMesHandler", (_Handler,), {
        "service": service, "web_root": Path("shiftlink/mes/web"), "api_only": False})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    stopped = threading.Event()
    worker = threading.Thread(target=server.serve_forever)
    ticker = threading.Thread(target=_run_ticks, args=(service, stopped))
    def post(path, payload):
        request = Request(f"http://127.0.0.1:{server.server_port}" + path,
                          json.dumps(payload).encode(), {"Content-Type": "application/json"})
        with urlopen(request, timeout=180) as response:
            return json.load(response)
    sampler.start()
    worker.start()
    ticker.start()
    try:
        scan = post("/api/equipment/scan", {"class": "HPU", "conf": .95, "device_id": "live-measurement"})
        for question in questions:
            first_call = len(calls)
            started = time.monotonic()
            response = post("/api/query", {"question": question, "scan_id": scan["scan"]["scan_id"]})
            raw_answers = []
            for call in calls[first_call:]:
                content = json.loads(call["body"]["message"]["content"])
                if "answer" in content:
                    answer = content["answer"]
                    raw_answers.append({"answer": answer, "chars": len(answer),
                        "at_char_limit": len(answer) == ANSWER_MAX_CHARS,
                        "ends_with_sentence_punctuation": answer.rstrip().endswith((".", "!", "?")),
                        "done_reason": call["body"].get("done_reason"),
                        "eval_count": call["body"].get("eval_count")})
            responses.append({"question": question, "http_latency_s": time.monotonic() - started,
                              "response": response, "raw_answers": raw_answers})
    finally:
        stopped.set()
        ticker.join()
        server.shutdown()
        worker.join()
        server.server_close()
        service.storage.close()
        stop_sampling.set()
        sampler.join()
        if stats:
            stats.terminate()
            stats.wait(timeout=5)
            stats_reader.join()
    report = {"host": socket.gethostname(), "model": model.model, "num_ctx": model.num_ctx,
              "scope": "Isolated MES HTTP server with production tick loop + actual Ollama; camera/PDA injected, other demo apps not started",
              "mem_available_min_mib": min(s["available_mib"] for s in samples),
              "mes_rss_max_mib": max(s["mes_rss_mib"] for s in samples), "memory_samples": samples,
              "tegrastats_ram": readings, "queries": responses, "model_calls": calls}
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({key: report[key] for key in ("host", "num_ctx", "mem_available_min_mib", "mes_rss_max_mib")}))
    print(json.dumps([{"http_latency_s": r["http_latency_s"],
                      "answer": r["response"]["answer"], "raw_answers": r["raw_answers"],
                      "review_queue": r["response"]["review_queue"]} for r in responses], ensure_ascii=False))


if __name__ == "__main__":
    main()
