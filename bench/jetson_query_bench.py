"""J3 — Jetson에서 MES 서버 + exaone(ollama)을 함께 띄운 상태로 질의 지연·여유 메모리를 잰다.

Jetson에서 실행한다(표준 라이브러리만, Python 3.10). MES 서버(:8000, /api/query 포함)와 ollama가 떠 있어야 한다.

    python3 bench/jetson_query_bench.py [--server http://127.0.0.1:8000] [--n 20] [--warmup 1]
                                        [--questions eval/qa/20261001-blind/qa_blind.json] [--out ~/shiftlink-bench]

- 질의: 질문 세트를 앞에서부터 n개, 하나씩 순서대로(동시 요청 없음). 워밍업은 집계에서 뺀다.
- 설비: 질문의 eq_id(HPU 등)를 /api/catalog로 equipment_id에 맞춘다(스캔과 같은 규칙: 형식별 가장 작은 ID).
  스캔을 기록하지 않으므로 PDA 화면의 '최근 인식'을 건드리지 않는다.
- 메모리: /proc/meminfo를 1초마다 읽어 MemAvailable 최솟값·Swap 사용 최댓값을 기록한다.
- 결과: <out>/j3_<시각>.jsonl(질의별) · .json(요약), 표준출력 마지막 줄은 bench/experiments.tsv 형식 한 줄.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path


def p95(values: list[float]) -> float:
    """nearest-rank p95 (n=20이면 19번째 값)."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def equipment_ids(catalog: dict) -> dict[str, str]:
    """형식 코드(HPU 등) → 그 형식에서 equipment_id가 가장 작은 설비. shiftlink/mes/server.py record_scan과 같은 규칙."""
    type_ids = {t["type_code"]: t["equipment_type_id"] for t in catalog["equipment_types"]}
    out = {}
    for code, type_id in type_ids.items():
        ids = [e["equipment_id"] for e in catalog["equipment"] if e["equipment_type_id"] == type_id]
        if ids:
            out[code] = min(ids)
    return out


def meminfo_mb() -> dict[str, int]:
    info = {}
    with open("/proc/meminfo") as f:
        for line in f:
            key, value = line.split(":", 1)
            info[key] = int(value.split()[0]) // 1024
    return {"total": info["MemTotal"], "available": info["MemAvailable"],
            "swap_used": info["SwapTotal"] - info["SwapFree"]}


class MemWatch(threading.Thread):
    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.samples: list[dict[str, int]] = []
        self.stop = threading.Event()

    def run(self) -> None:
        while not self.stop.is_set():
            self.samples.append(meminfo_mb())
            self.stop.wait(1.0)


def call(url: str, body: dict | None = None, timeout: float = 300) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.status, json.loads(res.read())
    except urllib.error.HTTPError as err:
        return err.code, {"error": err.read().decode(errors="replace")[:300]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default="http://127.0.0.1:8000")
    parser.add_argument("--questions", default=str(Path(__file__).resolve().parents[1] / "eval/qa/20261001-blind/qa_blind.json"))
    parser.add_argument("--n", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--out", default=str(Path.home() / "shiftlink-bench"))
    args = parser.parse_args()

    questions = json.loads(Path(args.questions).read_text(encoding="utf-8"))
    eq = equipment_ids(call(args.server + "/api/catalog")[1]["data"])
    items = [q for q in questions if q["eq_id"] in eq][: args.warmup + args.n]
    if len(items) < args.warmup + args.n:
        raise SystemExit(f"질문이 모자람: {len(items)} < {args.warmup + args.n}")

    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw = out / f"j3_{stamp}.jsonl"

    baseline = meminfo_mb()
    watch = MemWatch()
    watch.start()
    latencies = []
    ok = 0
    with raw.open("w", encoding="utf-8") as f:
        for i, q in enumerate(items):
            warm = i < args.warmup
            t0 = time.perf_counter()
            status, res = call(args.server + "/api/query", {"question": q["question"], "equipment_id": eq[q["eq_id"]]})
            dt = time.perf_counter() - t0
            row = {"i": i, "warmup": warm, "qid": q.get("qid"), "eq_id": q["eq_id"], "status": status, "latency_s": round(dt, 3),
                   "cited": res.get("cited_card_ids"), "safety": len(res.get("safety_notices") or []),
                   "answer_chars": len(res.get("answer") or ""), "error": res.get("error"), "mem": meminfo_mb()}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            if not warm:
                latencies.append(dt)
                ok += status == 200
            print(f"{'warm' if warm else i - args.warmup + 1:>4} {q.get('qid')} {status} {dt:6.1f}s", flush=True)
    watch.stop.set()
    watch.join()

    samples = watch.samples or [baseline]
    summary = {
        "date": stamp, "server": args.server, "questions": args.questions, "n": len(latencies), "ok": ok,
        "p50_s": round(sorted(latencies)[len(latencies) // 2], 2), "p95_s": round(p95(latencies), 2),
        "max_s": round(max(latencies), 2), "mem_total_mb": baseline["total"],
        "avail_before_mb": baseline["available"], "avail_min_mb": min(s["available"] for s in samples),
        "swap_used_max_mb": max(s["swap_used"] for s in samples), "raw": str(raw),
    }
    (out / f"j3_{stamp}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    # bench/experiments.tsv 한 줄 (date experimenter variable setting time_budget_min n_runs primary_metric
    #   primary_value secondary_p95_s secondary_temp_c verdict notes)
    notes = (f"J3 MES+exaone 동시; ok={ok}/{len(latencies)}; avail_min={summary['avail_min_mb']}MB "
             f"(before {summary['avail_before_mb']}MB); swap_max={summary['swap_used_max_mb']}MB; raw={raw}")
    print("\t".join([datetime.now().strftime("%Y-%m-%d"), os.environ.get("USER", "jetson"), "load", "mes+exaone",
                     "", str(len(latencies)), "query_ok_rate", f"{ok / len(latencies):.2f}",
                     f"{summary['p95_s']}", "", "", notes]))


if __name__ == "__main__":
    main()
