"""PDA 얼굴 로그인(1:1 검증). 얼굴 이미지·임베딩은 이 기기 밖으로 나가지 않는다.

모델 파일(ONNX)과 임베딩은 저장소에 커밋하지 않는다: 모델은 `models.fetch_models()`가 공식 출처에서 받고,
임베딩은 `FACE_DIR` 아래에만 둔다.
"""
from __future__ import annotations

import os
from pathlib import Path

FACE_DIR = Path(os.environ.get("SHIFTLINK_FACE_DIR", Path.home() / "shiftlink" / "data" / "face"))
MODEL_DIR = FACE_DIR / "models"
TEMPLATE_DIR = FACE_DIR / "templates"

# 임베딩 모델이 바뀌면 기존 등록은 쓸 수 없다. employee.face_model_version에도 이 값을 쓴다.
MODEL_VERSION = "sface-2021dec"
# OpenCV가 SFace 예제에서 쓰는 코사인 권장 기본값. 현장 튜닝 전이다(사전 등록 6절: dev와 사칭 시도 점수로 판단).
DEFAULT_THRESHOLD = 0.363
