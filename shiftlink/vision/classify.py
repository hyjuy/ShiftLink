"""실시간 분류(라즈베리파이). 확정된 클래스명만 출력한다. Jetson 전송은 /api/equipment/scan 구현 후 붙인다.

    python -m shiftlink.vision.classify [--model data/vision/model] [--camera 0] [--min-conf 0.8] [--frames 5] [--headless]
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from shiftlink.vision import MODEL_DIR

SIZE = 224
MEAN = (0.485, 0.456, 0.406)
STD = (0.229, 0.224, 0.225)


class Stabilizer:
    """같은 클래스가 min_conf 이상으로 frames번 연속 나오면 한 번만 확정한다.

    객체를 치워 저신뢰가 frames번 이어지면 초기화되어, 같은 객체를 다시 놓아도 다시 확정된다.
    """

    def __init__(self, min_conf: float = 0.8, frames: int = 5) -> None:
        self.min_conf = min_conf
        self.frames = frames
        self._last: str | None = None
        self._run = 0
        self._sent: str | None = None

    def update(self, label: str, conf: float) -> str | None:
        current = label if conf >= self.min_conf else None
        if current == self._last:
            self._run += 1
        else:
            self._last, self._run = current, 1
        if self._run != self.frames:
            return None
        if current is None:
            self._sent = None
            return None
        if current == self._sent:
            return None
        self._sent = current
        return current


def preprocess(frame_bgr):
    """train.py의 val 전처리와 같다: RGB, 224x224, ImageNet 정규화, NCHW float32."""
    import cv2
    import numpy as np

    rgb = cv2.cvtColor(cv2.resize(frame_bgr, (SIZE, SIZE)), cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    rgb = (rgb - np.array(MEAN, dtype=np.float32)) / np.array(STD, dtype=np.float32)
    return rgb.transpose(2, 0, 1)[None]


def main() -> None:
    import cv2
    import numpy as np
    import onnxruntime as ort

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", type=Path, default=Path(MODEL_DIR))
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--min-conf", type=float, default=0.8)  # 현장 조명에 맞춰 조정
    parser.add_argument("--frames", type=int, default=5)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    labels = (args.model / "labels.txt").read_text(encoding="utf-8").split()
    session = ort.InferenceSession(str(args.model / "model.onnx"), providers=["CPUExecutionProvider"])
    stab = Stabilizer(args.min_conf, args.frames)
    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise SystemExit(f"카메라 {args.camera}를 열 수 없음")
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                raise SystemExit("프레임 읽기 실패")
            t0 = time.perf_counter()
            logits = session.run(None, {"input": preprocess(frame)})[0][0]
            probs = np.exp(logits - logits.max())
            probs /= probs.sum()
            i = int(probs.argmax())
            ms = (time.perf_counter() - t0) * 1000
            confirmed = stab.update(labels[i], float(probs[i]))
            if confirmed:
                print(f"확정 {confirmed} conf={probs[i]:.2f} {ms:.0f}ms", flush=True)
            if not args.headless:
                cv2.putText(frame, f"{labels[i]} {probs[i]:.2f} {ms:.0f}ms", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                cv2.imshow("classify (q quit)", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
