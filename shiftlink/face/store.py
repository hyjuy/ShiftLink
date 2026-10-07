"""등록 임베딩 저장소. 임베딩만 저장하고 원본 이미지는 저장하지 않는다. 사번당 파일 하나, 권한 600."""
from __future__ import annotations

import os
import re
from pathlib import Path

import numpy as np

from . import MODEL_VERSION, TEMPLATE_DIR

_ID = re.compile(r"^[A-Za-z0-9_-]{1,16}$")  # employee.employee_id 길이와 같고, 경로 문자를 막는다


class FaceStore:
    def __init__(self, directory: Path = TEMPLATE_DIR) -> None:
        self.directory = directory

    def _path(self, employee_id: str) -> Path:
        if not isinstance(employee_id, str) or not _ID.match(employee_id):
            raise ValueError("employee_id must match [A-Za-z0-9_-]{1,16}")
        return self.directory / f"{employee_id}.npz"

    def save(self, employee_id: str, embeddings: np.ndarray, model_version: str = MODEL_VERSION) -> Path:
        """등록을 덮어쓴다(재등록)."""
        path = self._path(employee_id)
        data = np.asarray(embeddings, dtype=np.float32)
        if data.ndim != 2 or len(data) == 0:
            raise ValueError("embeddings must be a non-empty (N, D) array")
        self.directory.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with tmp.open("wb") as handle:
            np.savez(handle, embeddings=data, model_version=np.array(model_version))
        os.chmod(tmp, 0o600)  # Windows에서는 읽기 전용 여부만 반영된다
        os.replace(tmp, path)
        return path

    def load(self, employee_id: str, model_version: str = MODEL_VERSION) -> np.ndarray | None:
        """등록이 없거나 다른 모델로 만든 등록이면 None(재등록 필요)."""
        path = self._path(employee_id)
        if not path.exists():
            return None
        with np.load(path) as data:
            if str(data["model_version"]) != model_version:
                return None
            return data["embeddings"]

    def delete(self, employee_id: str) -> bool:
        path = self._path(employee_id)
        if not path.exists():
            return False
        path.unlink()
        return True
