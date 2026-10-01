"""학습용 촬영. 데모와 같은 웹캠(라즈베리파이에 연결한 것)으로 찍는 것이 좋다.

    python -m shiftlink.vision.capture [--camera 0] [--out data/vision/raw]

숫자키 1~6을 누르면 현재 프레임을 해당 클래스 폴더에 저장한다. q는 종료.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2

from shiftlink.vision import CLASSES, RAW_DIR


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--out", type=Path, default=Path(RAW_DIR))
    args = parser.parse_args()

    dirs = [args.out / name for name in CLASSES]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    counts = [len(list(d.glob("*.jpg"))) for d in dirs]

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise SystemExit(f"카메라 {args.camera}를 열 수 없음")
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                raise SystemExit("프레임 읽기 실패")
            view = frame.copy()
            for i, (name, n) in enumerate(zip(CLASSES, counts)):
                cv2.putText(view, f"{i + 1}:{name} {n}", (10, 30 + 28 * i),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            cv2.imshow("capture (1-6 save, q quit)", view)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            idx = key - ord("1")
            if 0 <= idx < len(CLASSES):
                cv2.imwrite(str(dirs[idx] / f"{CLASSES[idx]}_{time.time_ns()}.jpg"), frame)
                counts[idx] += 1
    finally:
        cap.release()
        cv2.destroyAllWindows()
    print(dict(zip(CLASSES, counts)))


if __name__ == "__main__":
    main()
