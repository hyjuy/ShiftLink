"""FP32 ONNX → INT8 ONNX(ONNX Runtime 정적 양자화, 파이 CPU용). labels.txt도 같이 둔다.

    python -m shiftlink.vision.quantize --model data/vision/model --calib data/vision/unity-cls/train [--n 100] [--conv-only]

보정(calibration)은 학습 사진에서 클래스마다 고르게 뽑는다. test 사진은 쓰지 않는다(평가 누수 방지).
결과는 evaluate.py로 FP32와 같은 test 폴더에서 비교한다.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from shiftlink.vision.classify import preprocess
from shiftlink.vision.evaluate import load_images


def calibration_paths(data: Path, n: int) -> list[Path]:
    """클래스별로 번갈아 뽑아 n장(클래스가 한쪽으로 쏠리지 않게)."""
    by_class: dict[str, list[Path]] = {}
    for cls, path in load_images(data):
        by_class.setdefault(cls, []).append(path)
    picked, i = [], 0
    while len(picked) < n and any(i < len(v) for v in by_class.values()):
        picked += [v[i] for v in by_class.values() if i < len(v)]
        i += 1
    return picked[:n]


def quantize(model_dir: Path, calib: Path, n: int = 100, conv_only: bool = False) -> Path:
    import cv2
    import numpy as np
    from onnxruntime.quantization import CalibrationDataReader, QuantFormat, QuantType, quantize_static
    from onnxruntime.quantization.shape_inference import quant_pre_process

    paths = calibration_paths(calib, n)
    if not paths:
        raise SystemExit(f"보정 사진이 없습니다: {calib}")

    class Reader(CalibrationDataReader):
        def __init__(self):
            self.it = iter(paths)

        def get_next(self):
            path = next(self.it, None)
            if path is None:
                return None
            return {"input": preprocess(cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR))}

    out_dir = model_dir.parent / (model_dir.name + ("-int8conv" if conv_only else "-int8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    prepared = out_dir / "model.prep.onnx"
    quant_pre_process(str(model_dir / "model.onnx"), str(prepared), skip_symbolic_shape=True)  # 입력 크기 고정 CNN이라 불필요(sympy 없이)
    target = out_dir / "model.onnx"
    # QDQ + 채널별 가중치. MobileNetV3는 hard-swish·SE 블록이 INT8에 민감하다: 10/7 합성 데이터 비교에서
    # 전체 양자화는 정확도가 크게 떨어졌고 Conv만 양자화하면 덜 떨어졌다(크기는 FP32의 약 60%). 실제 데이터로 둘 다 잰다.
    extra = {"op_types_to_quantize": ["Conv"]} if conv_only else {}
    quantize_static(str(prepared), str(target), Reader(), quant_format=QuantFormat.QDQ, per_channel=True,
                    activation_type=QuantType.QUInt8, weight_type=QuantType.QInt8, **extra)
    prepared.unlink()
    shutil.copy2(model_dir / "labels.txt", out_dir / "labels.txt")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", type=Path, required=True, help="model.onnx·labels.txt가 있는 폴더")
    parser.add_argument("--calib", type=Path, required=True, help="보정용 폴더(학습 사진, <클래스>/<사진>)")
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--conv-only", action="store_true", help="Conv만 INT8(정확도 손실이 작고 크기 절감은 작다)")
    args = parser.parse_args()
    print(f"INT8 -> {quantize(args.model, args.calib, args.n, args.conv_only)}")


if __name__ == "__main__":
    main()
