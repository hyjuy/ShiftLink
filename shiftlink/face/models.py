"""모델 manifest와 내려받기. 가중치는 저장소에 넣지 않고 공식 출처(OpenCV Zoo, 고정 커밋)에서 받아 해시를 확인한다.

라이선스: YuNet 디렉터리 전체 MIT, SFace 디렉터리 전체 Apache-2.0(고지 보존).
`third_party_licenses/opencv_zoo_*.txt` 참고. 조사 결과는 사전 등록 4절.
"""
from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path

from . import MODEL_DIR

ZOO_COMMIT = "47534e27c9851bb1128ccc0102f1145e27f23f98"
_BASE = f"https://github.com/opencv/opencv_zoo/raw/{ZOO_COMMIT}/models"

# 이름 -> (URL, sha256)
MANIFEST: dict[str, tuple[str, str]] = {
    "face_detection_yunet_2023mar.onnx": (
        f"{_BASE}/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"),
    "face_recognition_sface_2021dec.onnx": (
        f"{_BASE}/face_recognition_sface/face_recognition_sface_2021dec.onnx",
        "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_models(directory: Path = MODEL_DIR) -> dict[str, Path]:
    """없거나 해시가 다른 파일만 내려받는다. 받은 뒤에도 해시가 다르면 파일을 지우고 오류를 낸다."""
    directory.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, (url, expected) in MANIFEST.items():
        path = directory / name
        if not path.exists() or sha256(path) != expected:
            urllib.request.urlretrieve(url, path)
            if sha256(path) != expected:
                path.unlink()
                raise RuntimeError(f"{name}: 해시가 manifest와 다름(다운로드 손상 또는 출처 변경)")
        paths[name] = path
    return paths
