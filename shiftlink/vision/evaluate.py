"""ONNX 분류 모델의 클래스별 정확도·혼동·1장 추론 시간(G5·W3-2 표).

    python -m shiftlink.vision.evaluate --model data/vision/model/model.onnx --data data/vision/unity-cls/test [--json out.json]

전처리는 파이와 같은 classify.preprocess를 쓴다. labels.txt는 모델 파일과 같은 폴더에서 읽는다.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from shiftlink.vision.classify import preprocess

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}


def load_images(data: Path) -> list[tuple[str, Path]]:
    """(정답 클래스, 경로). 폴더 구조는 data/<클래스>/<사진>."""
    return [(d.name, f) for d in sorted(p for p in data.iterdir() if p.is_dir())
            for f in sorted(d.iterdir()) if f.suffix.lower() in IMAGE_SUFFIXES]


def summarize(labels: list[str], pairs: list[tuple[str, str]], ms: list[float]) -> dict:
    """pairs = [(정답, 예측)]. 클래스별 정답률과 혼동 행렬, 시간 분위수."""
    per = {c: {"n": 0, "correct": 0} for c in labels}
    confusion = {c: {p: 0 for p in labels} for c in labels}
    for truth, pred in pairs:
        per[truth]["n"] += 1
        per[truth]["correct"] += truth == pred
        confusion[truth][pred] += 1
    for v in per.values():
        v["acc"] = round(v["correct"] / v["n"], 4) if v["n"] else None
    ordered = sorted(ms)
    q = lambda f: round(ordered[min(len(ordered) - 1, int(len(ordered) * f))], 2) if ordered else None  # noqa: E731
    total = sum(v["correct"] for v in per.values())
    return {"n": len(pairs), "acc": round(total / len(pairs), 4) if pairs else None, "per_class": per,
            "confusion": confusion, "ms_p50": q(0.5), "ms_p95": q(0.95)}


def evaluate(model: Path, data: Path) -> dict:
    import cv2
    import numpy as np
    import onnxruntime as ort

    labels = (model.parent / "labels.txt").read_text(encoding="utf-8").split()
    session = ort.InferenceSession(str(model), providers=["CPUExecutionProvider"])
    images = load_images(data)
    unknown = {c for c, _ in images} - set(labels)
    if unknown:
        raise SystemExit(f"모델에 없는 클래스 폴더: {sorted(unknown)}")
    pairs, ms = [], []
    for truth, path in images:
        frame = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)  # 한글 경로도 읽힌다
        t0 = time.perf_counter()
        logits = session.run(None, {"input": preprocess(frame)})[0][0]
        ms.append((time.perf_counter() - t0) * 1000)
        pairs.append((truth, labels[int(logits.argmax())]))
    return {"model": model.name, "size_kb": round(model.stat().st_size / 1024), **summarize(labels, pairs, ms)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--json", type=Path, help="결과를 JSON으로도 저장")
    args = parser.parse_args()
    r = evaluate(args.model, args.data)
    print(f"{r['model']} ({r['size_kb']} KB): 전체 {r['acc']} (n={r['n']}), 1장 p50 {r['ms_p50']} ms · p95 {r['ms_p95']} ms")
    for c, v in r["per_class"].items():
        print(f"  {c:4s} {v['correct']}/{v['n']} = {v['acc']}")
    if args.json:
        args.json.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
