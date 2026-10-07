"""검출(YuNet) → 정렬 → 임베딩(SFace). cv2 객체를 주입받아 모델 없이도 테스트할 수 있다."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from . import MODEL_DIR


class FaceEngine:
    def __init__(self, detector: Any, recognizer: Any) -> None:
        self.detector = detector
        self.recognizer = recognizer

    @classmethod
    def load(cls, model_dir: Path = MODEL_DIR, score_threshold: float = 0.8) -> "FaceEngine":
        import cv2
        detector = cv2.FaceDetectorYN.create(str(model_dir / "face_detection_yunet_2023mar.onnx"), "", (320, 320),
                                             score_threshold, 0.3, 5000)
        recognizer = cv2.FaceRecognizerSF.create(str(model_dir / "face_recognition_sface_2021dec.onnx"), "")
        return cls(detector, recognizer)

    def embed(self, frame_bgr: np.ndarray) -> np.ndarray | None:
        """가장 큰 얼굴 하나의 L2 정규화 임베딩(128). 얼굴이 없으면 None. 얼굴이 여러 개면 가장 큰 것(가장 가까운 사람)."""
        height, width = frame_bgr.shape[:2]
        self.detector.setInputSize((width, height))
        _, faces = self.detector.detect(frame_bgr)
        if faces is None or len(faces) == 0:
            return None
        face = max(faces, key=lambda row: float(row[2]) * float(row[3]))  # 너비 x 높이
        feature = np.asarray(self.recognizer.feature(self.recognizer.alignCrop(frame_bgr, face)), dtype=np.float32).reshape(-1)
        norm = float(np.linalg.norm(feature))
        return feature / norm if norm else None


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    """정규화된 두 임베딩의 코사인 유사도."""
    return float(np.dot(a, b))
