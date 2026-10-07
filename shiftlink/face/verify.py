"""1:1 검증 판정. 여러 프레임 중 충분히 많은 프레임이 임계값을 넘어야 통과한다(한 프레임 우연 통과 방지)."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from . import DEFAULT_THRESHOLD
from .engine import cosine


@dataclass(frozen=True)
class Verdict:
    passed: bool
    best_score: float | None  # 얼굴이 잡힌 프레임 중 최고 유사도. 얼굴이 하나도 없으면 None
    frames_seen: int          # 얼굴이 잡힌 프레임 수
    frames_passed: int


def append_attempt(path: Path, employee_id: str, who: str, threshold: float, verdict: Verdict) -> None:
    """사칭·본인 시도 기록. 점수와 통과 여부만 남기고 이미지·임베딩은 쓰지 않는다. who는 '본인' 또는 시도한 사람의 익명 라벨."""
    new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        if new:
            writer.writerow(["time", "employee_id", "who", "threshold", "best_score", "frames_seen", "frames_passed", "passed"])
        writer.writerow([datetime.now().astimezone().isoformat(timespec="seconds"), employee_id, who, threshold,
                         "" if verdict.best_score is None else round(verdict.best_score, 4),
                         verdict.frames_seen, verdict.frames_passed, int(verdict.passed)])


def frame_score(embedding: np.ndarray, template: np.ndarray) -> float:
    """등록 임베딩 여러 장 중 가장 비슷한 것과의 코사인."""
    return max(cosine(embedding, row) for row in template)


def decide(embeddings: list[np.ndarray | None], template: np.ndarray, threshold: float = DEFAULT_THRESHOLD,
           min_pass: int = 3) -> Verdict:
    """embeddings: 프레임마다 `FaceEngine.embed` 결과(얼굴 없으면 None). 통과 프레임이 min_pass 이상이면 통과."""
    scores = [frame_score(e, template) for e in embeddings if e is not None]
    passed = sum(score >= threshold for score in scores)
    return Verdict(passed >= min_pass, max(scores) if scores else None, len(scores), passed)
