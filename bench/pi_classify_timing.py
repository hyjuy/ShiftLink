"""J4 — 라즈베리파이에서 웹캠 1프레임 분류 시간(전처리+ONNX 추론)을 잰다 (루브릭 W3-2).

파이의 ~/shiftlink/app 에서 실행한다 (.venv: opencv·onnxruntime·numpy, shiftlink.vision 배포됨).

    PYTHONPATH=. .venv/bin/python bench/pi_classify_timing.py --model ~/shiftlink/models/cnn [--frames 200] [--camera 0]

- classify.py와 같은 preprocess·InferenceSession(CPU)을 쓴다. 앞 20프레임은 워밍업으로 뺀다.
- 분류 시간은 모델 구조로 정해지므로 학습 전 모델로도 잴 수 있다. 학습 전 모델(train.py와 같은 구조)은 PC에서:
    m = torchvision.models.mobilenet_v3_small(weights=None); m.classifier[-1] = nn.Linear(m.classifier[-1].in_features, 6)
    torch.onnx.export(m.eval(), torch.zeros(1, 3, 224, 224), "model.onnx", input_names=["input"], output_names=["logits"], opset_version=17)
- 마지막 줄은 bench/experiments.tsv 형식 한 줄.
"""

from __future__ import annotations

import argparse
import math
import statistics
import subprocess
import time
from datetime import date
from pathlib import Path


def p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def main() -> None:
    import cv2
    import onnxruntime as ort

    from shiftlink.vision.classify import preprocess

    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True, help="model.onnx가 있는 폴더")
    parser.add_argument("--frames", type=int, default=200)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--note", default="", help="TSV notes 앞에 붙일 말 (예: 학습 전 모델)")
    args = parser.parse_args()

    session = ort.InferenceSession(str(args.model / "model.onnx"), providers=["CPUExecutionProvider"])
    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise SystemExit(f"카메라 {args.camera}를 열 수 없음")
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    pre, inf, tot = [], [], []
    t_start = time.perf_counter()
    for i in range(args.warmup + args.frames):
        ok, frame = cap.read()
        if not ok:
            raise SystemExit("프레임 읽기 실패")
        t0 = time.perf_counter()
        x = preprocess(frame)
        t1 = time.perf_counter()
        session.run(None, {"input": x})
        t2 = time.perf_counter()
        if i >= args.warmup:
            pre.append((t1 - t0) * 1000); inf.append((t2 - t1) * 1000); tot.append((t2 - t0) * 1000)
    fps = (args.warmup + args.frames) / (time.perf_counter() - t_start)
    cap.release()

    def run(cmd: list[str]) -> str:
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout.strip()
        except OSError:
            return ""

    temp = run(["vcgencmd", "measure_temp"]).replace("temp=", "").replace("'C", "")
    board = Path("/proc/device-tree/model").read_text(errors="ignore").strip("\x00\n") if Path("/proc/device-tree/model").exists() else ""
    print(f"{board} · frame {w}x{h} · n={len(tot)} · loop {fps:.1f}fps · temp {temp}°C · throttled {run(['vcgencmd', 'get_throttled'])}")
    for name, v in (("preprocess", pre), ("inference", inf), ("classify", tot)):
        print(f"{name:10s} p50={statistics.median(v):6.1f}ms  p95={p95(v):6.1f}ms  max={max(v):6.1f}ms")
    notes = (f"{args.note}{board}, 웹캠 {w}x{h}, onnxruntime CPU; 전처리 p50 {statistics.median(pre):.1f}·추론 p50 "
             f"{statistics.median(inf):.1f}/p95 {p95(inf):.1f}ms; 캡처 포함 {fps:.0f}fps; {temp}°C; bench/pi_classify_timing.py")
    print("\t".join([date.today().isoformat(), "claude", "cnn_latency", "MobileNetV3-Small ONNX (Pi 4)", "", str(len(tot)),
                     "classify_ms_p50", f"{statistics.median(tot):.1f}", f"{p95(tot) / 1000:.4f}", temp, "keep", notes]))


if __name__ == "__main__":
    main()
