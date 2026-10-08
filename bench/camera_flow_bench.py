"""W3-1 — Unity 사진 → 파이 분류 → Jetson 인식 기록 → 그 설비로 질의 → 답, N건의 성공 수와 p95.

PC(Unity 쪽)에서 실행한다(표준 라이브러리만). 파이는 classify --listen 으로, Jetson MES는 :8000 으로 떠 있어야 한다.

    python bench/camera_flow_bench.py --images data/vision/unity-cls/test --pi http://<파이>:8090 \
        --server http://<jetson>:8000 --device-id pi-01 [--n 20] [--warmup 1] [--out ../ShiftLink-records/experiments/w31]

- 사진: --images/<클래스>/*.png 중 시연 질문이 있는 클래스(HPU·GR·CV)를 번갈아 하나씩 쓴다. 폴더 이름이 정답 클래스다.
- 질문: docs/planning/시연_질문_9개_20261006.md 표에서 그 설비의 질문을 차례로 쓴다.
- 한 건 = 사진 POST /classify(파이가 확정하면 Jetson에 기록) → 이 장치의 새 scan_id → POST /api/query {question, scan_id}.
  PDA가 스캔을 받아 질의하는 것과 같은 요청이다. 사람이 누르는 시간은 넣지 않는다.
- 성공(미리 고정): 파이가 Jetson에 보냈고(sent), 인식 클래스 = 정답 클래스, 질의 HTTP 200, 응답의 설비 = 정답 설비,
  답 또는 '해당 지식 없음'이 있다. 실패는 이유를 하나 적는다(보류·오분류·질의 실패 …).
- 지연: 사진 전송부터 답까지(e2e). 분류 구간과 질의 구간을 따로도 적는다. p95는 nearest-rank이고, 질의까지 간 건
  (Jetson 기록이 생긴 건, 오분류 포함 — PDA도 그 설비로 질의한다)만 센다. 오분류 설비는 '해당 지식 없음'이
  빨리 나와 p95를 낮출 수 있으므로 성공 건만의 p95(p95_ok_s)도 함께 적고, 발표에는 둘 다 쓴다. 보류·전송 실패는 성공 수에만 반영한다.
- 결과: <out>/w31_<시각>.jsonl(건별) · .json(요약), 마지막 줄은 bench/experiments.tsv 형식.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import re
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from jetson_query_bench import call, equipment_ids, p95

ROOT = Path(__file__).resolve().parents[1]


def demo_questions(path: Path) -> dict[str, list[str]]:
    """시연 질문 표의 `| HPU | 질문 | K-.. |` 행 → {설비: [질문…]}."""
    out: dict[str, list[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*(HPU|GR|CV|RT|CAU|PDP)\s*\|\s*([^|]+?)\s*\|\s*K-\d+", line)
        if m:
            out.setdefault(m.group(1), []).append(m.group(2))
    return out


def plan(images: Path, questions: dict[str, list[str]], total: int) -> list[tuple[str, Path, str]]:
    """(정답 클래스, 사진, 질문)을 설비를 번갈아 total개. 사진·질문은 클래스 안에서 차례로 돈다."""
    pools = {c: sorted(p for p in (images / c).glob("*") if p.suffix.lower() in (".png", ".jpg", ".jpeg"))
             for c in questions if (images / c).is_dir()}
    classes = [c for c in questions if pools.get(c)]
    if not classes:
        raise SystemExit(f"사진 폴더에 시연 설비({', '.join(questions)}) 하위 폴더가 없음: {images}")
    cyc = {c: (itertools.cycle(pools[c]), itertools.cycle(questions[c])) for c in classes}
    order = itertools.cycle(classes)
    return [(c, next(cyc[c][0]), next(cyc[c][1])) for c in itertools.islice(order, total)]


def post_image(pi: str, image: Path, timeout: float = 10) -> dict:
    req = urllib.request.Request(pi.rstrip("/") + "/classify", data=image.read_bytes(),
                                 headers={"Content-Type": "application/octet-stream"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read())


def new_scan(server: str, device_id: str, seen: set[str], wait_s: float = 3.0) -> dict | None:
    """이 장치가 방금 기록한 scan(이전에 본 적 없는 것). 다른 장치의 기록은 건너뛴다."""
    end = time.perf_counter() + wait_s
    while time.perf_counter() < end:
        _, body = call(server + "/api/equipment/scan/recent?limit=10", timeout=5)
        for s in body.get("scans", []):
            if s.get("device_id") == device_id and s.get("scan_id") not in seen:
                return s
        time.sleep(0.1)
    return None


def judge(truth: str, truth_eq: str, r: dict, scan: dict | None, status: int, res: dict) -> str:
    """'ok' 또는 실패 이유 하나."""
    if not r.get("sent"):
        return "보류(확신도 미달)" if not r.get("confirmed") else "파이→Jetson 전송 실패"
    if r.get("class") != truth:
        return f"오분류({r.get('class')})"
    if scan is None:
        return "Jetson 인식 기록 없음"
    if status != 200:
        return f"질의 HTTP {status}"
    if (res.get("evidence") or {}).get("equipment_id") != truth_eq:
        return f"응답 설비 다름({(res.get('evidence') or {}).get('equipment_id')})"
    if not (res.get("answer") or res.get("no_knowledge") or res.get("review_queue")):
        return "답 없음"
    return "ok"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--images", type=Path, required=True, help="<클래스>/사진 구조의 폴더(unity-cls/test 등)")
    parser.add_argument("--pi", required=True)
    parser.add_argument("--server", required=True, help="Jetson MES 주소")
    parser.add_argument("--device-id", required=True, help="파이 classify --device-id 와 같은 값")
    parser.add_argument("--questions", type=Path, default=ROOT / "docs/planning/시연_질문_9개_20261006.md")
    parser.add_argument("--n", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--out", type=Path, default=Path.home() / "shiftlink-bench")
    args = parser.parse_args()
    server = args.server.rstrip("/")

    eq = equipment_ids(call(server + "/api/catalog")[1]["data"])
    items = plan(args.images, demo_questions(args.questions), args.warmup + args.n)
    args.out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw = args.out / f"w31_{stamp}.jsonl"
    seen = {s["scan_id"] for s in call(server + "/api/equipment/scan/recent?limit=50")[1].get("scans", [])}

    e2e, e2e_ok, ok, reasons = [], [], 0, {}  # e2e: 질의까지 간 건, e2e_ok: 성공 건만
    with raw.open("w", encoding="utf-8") as f:
        for i, (truth, image, question) in enumerate(items):
            warm = i < args.warmup
            t0 = time.perf_counter()
            try:
                r = post_image(args.pi, image)
            except OSError as err:
                r = {"error": type(err).__name__}
            t1 = time.perf_counter()
            scan = new_scan(server, args.device_id, seen) if r.get("sent") else None
            status, res = (call(server + "/api/query", {"question": question, "scan_id": scan["scan_id"]})
                           if scan else (0, {}))
            t2 = time.perf_counter()
            if scan:
                seen.add(scan["scan_id"])
            verdict = judge(truth, eq.get(truth, ""), r, scan, status, res)
            row = {"i": i, "warmup": warm, "truth": truth, "image": image.name, "question": question,
                   "pred": r.get("class"), "conf": r.get("conf"), "pi_ms": r.get("ms"), "sent": r.get("sent"),
                   "scan_id": scan and scan["scan_id"], "status": status, "classify_s": round(t1 - t0, 3),
                   "query_s": round(t2 - t1, 3), "e2e_s": round(t2 - t0, 3), "cited": res.get("cited_card_ids"),
                   "safety": len(res.get("safety_notices") or []), "no_knowledge": res.get("no_knowledge"),
                   "verdict": verdict, "error": r.get("error") or res.get("error")}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            if not warm:
                if scan:
                    e2e.append(t2 - t0)
                if verdict == "ok":
                    e2e_ok.append(t2 - t0)
                ok += verdict == "ok"
                reasons[verdict] = reasons.get(verdict, 0) + 1
            print(f"{'warm' if warm else i - args.warmup + 1:>4} {truth}→{r.get('class')} {verdict} e2e {t2 - t0:5.1f}s", flush=True)

    summary = {"date": stamp, "pi": args.pi, "server": server, "device_id": args.device_id, "images": str(args.images),
               "n": args.n, "n_timed": len(e2e), "ok": ok, "verdicts": reasons, "p50_s": round(sorted(e2e)[len(e2e) // 2], 2) if e2e else None,
               "p95_s": round(p95(e2e), 2) if e2e else None, "max_s": round(max(e2e), 2) if e2e else None,
               "p95_ok_s": round(p95(e2e_ok), 2) if e2e_ok else None, "raw": str(raw)}
    (args.out / f"w31_{stamp}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    notes = f"W3-1 Unity사진→파이→Jetson 질의; ok={ok}/{args.n}; timed={len(e2e)}; {reasons}; raw={raw}"
    print("\t".join([datetime.now().strftime("%Y-%m-%d"), os.environ.get("USERNAME", os.environ.get("USER", "")), "load",
                     "camera+jetson", "", str(args.n), "flow_ok_rate", f"{ok / args.n:.2f}", f"{summary['p95_s']}",
                     "", "", notes]))


if __name__ == "__main__":
    main()
