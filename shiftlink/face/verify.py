"""1:1 검증 판정. 여러 프레임 중 충분히 많은 프레임이 임계값을 넘어야 통과한다(한 프레임 우연 통과 방지)."""
from __future__ import annotations

import csv
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from . import DEFAULT_THRESHOLD, FACE_FRAMES, FACE_NEED
from .engine import cosine


@dataclass(frozen=True)
class Verdict:
    passed: bool
    best_score: float | None      # 얼굴이 잡힌 프레임 중 최고 유사도. 없으면 None
    min_score: float | None       # 얼굴이 잡힌 프레임 중 최저 유사도
    min_passed_score: float | None  # 임계값을 넘은 프레임 중 최저. 통과 프레임이 없으면 None
    frames_seen: int
    frames_passed: int


def _score(value: float | None) -> str | float:
    return "" if value is None else round(value, 4)


def append_attempt(path: Path, employee_id: str, who: str, threshold: float, verdict: Verdict) -> None:
    """사칭·본인 시도 기록. 점수와 통과 여부만 남기고 이미지·임베딩은 쓰지 않는다. who는 '본인' 또는 익명 라벨."""
    new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        if new:
            writer.writerow(["time", "employee_id", "who", "threshold", "best_score", "min_score",
                             "min_passed_score", "frames_seen", "frames_passed", "passed"])
        writer.writerow([datetime.now().astimezone().isoformat(timespec="seconds"), employee_id, who, threshold,
                         _score(verdict.best_score), _score(verdict.min_score), _score(verdict.min_passed_score),
                         verdict.frames_seen, verdict.frames_passed, int(verdict.passed)])


def frame_score(embedding: np.ndarray, template: np.ndarray) -> float:
    """등록 임베딩 여러 장 중 가장 비슷한 것과의 코사인."""
    return max(cosine(embedding, row) for row in template)


_engine = None
_engine_lock = threading.Lock()


def score_login_jpeg(jpeg: bytes, employee_id: str) -> dict[str, object]:
    """한 프레임 JPEG의 유사도. 이미지는 저장하지 않고 점수만 돌려준다. 등록이 없으면 LookupError, 사번이 틀리면 ValueError."""
    global _engine
    from .store import FaceStore

    store = FaceStore()
    store._path(employee_id)  # 사번 형식 검사. 틀리면 모델·파일을 열기 전에 거절한다
    template = store.load(employee_id)
    if template is None:
        raise LookupError("등록된 얼굴이 없습니다")
    import cv2
    from .engine import FaceEngine

    frame = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("이미지를 읽지 못했습니다")
    with _engine_lock:
        if _engine is None:
            _engine = FaceEngine.load()
        embedding = _engine.embed(frame)
    rule = {"threshold": DEFAULT_THRESHOLD, "need": FACE_NEED, "frames": FACE_FRAMES}
    if embedding is None:
        return {"face": False, "score": None, **rule}
    return {"face": True, "score": round(frame_score(embedding, template), 4), **rule}


def decide(embeddings: list[np.ndarray | None], template: np.ndarray, threshold: float = DEFAULT_THRESHOLD,
           min_pass: int = FACE_NEED) -> Verdict:
    """embeddings: 프레임마다 `FaceEngine.embed` 결과(얼굴 없으면 None). 통과 프레임이 min_pass 이상이면 통과."""
    scores = [frame_score(e, template) for e in embeddings if e is not None]
    passed_scores = [score for score in scores if score >= threshold]
    return Verdict(len(passed_scores) >= min_pass,
                   max(scores) if scores else None,
                   min(scores) if scores else None,
                   min(passed_scores) if passed_scores else None,
                   len(scores), len(passed_scores))
