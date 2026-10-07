from __future__ import annotations

import hashlib
import stat
import sys
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")  # CI(requirements.txt)에는 numpy가 없다. requirements-vision.txt 환경에서 돈다.

from shiftlink.face import MODEL_DIR  # noqa: E402
from shiftlink.face.engine import FaceEngine, cosine  # noqa: E402
from shiftlink.face.models import MANIFEST, fetch_models, sha256  # noqa: E402
from shiftlink.face.store import FaceStore  # noqa: E402
from shiftlink.face.verify import append_attempt, decide, frame_score  # noqa: E402


def unit(*values: float) -> np.ndarray:
    vector = np.array(values, dtype=np.float32)
    return vector / np.linalg.norm(vector)


class FakeDetector:
    def __init__(self, faces) -> None:
        self.faces = faces
        self.size = None

    def setInputSize(self, size) -> None:  # noqa: N802
        self.size = size

    def detect(self, frame):
        return 1, (np.array(self.faces, dtype=np.float32) if self.faces else None)


class FakeRecognizer:
    """alignCrop은 face 행의 4~8번 값을 '얼굴 이미지'로 돌려주고, feature는 그것을 그대로 임베딩으로 쓴다."""

    def alignCrop(self, frame, face):  # noqa: N802
        return face[4:8]

    def feature(self, crop):
        return crop.reshape(1, -1) * 3.0  # 정규화 전 값이어도 engine이 L2 정규화한다


FRAME = np.zeros((100, 200, 3), dtype=np.uint8)


def row(width: float, height: float, *vector: float) -> list[float]:
    return [10, 10, width, height, *vector] + [0] * 7


def test_embed_picks_largest_face_and_normalises() -> None:
    engine = FaceEngine(FakeDetector([row(20, 20, 1, 0, 0, 0), row(60, 50, 0, 3, 4, 0)]), FakeRecognizer())
    embedding = engine.embed(FRAME)
    assert embedding is not None
    assert np.allclose(embedding, unit(0, 3, 4, 0))
    assert engine.detector.size == (200, 100)  # (너비, 높이)


def test_embed_returns_none_without_face_or_zero_vector() -> None:
    assert FaceEngine(FakeDetector([]), FakeRecognizer()).embed(FRAME) is None
    assert FaceEngine(FakeDetector([row(30, 30, 0, 0, 0, 0)]), FakeRecognizer()).embed(FRAME) is None


def test_cosine_and_frame_score_use_best_enrolled_vector() -> None:
    template = np.stack([unit(1, 0, 0, 0), unit(0, 1, 0, 0)])
    assert cosine(unit(1, 0, 0, 0), unit(1, 0, 0, 0)) == pytest.approx(1.0)
    assert frame_score(unit(0, 1, 0, 0), template) == pytest.approx(1.0)
    assert frame_score(unit(0, 0, 1, 0), template) == pytest.approx(0.0)


def test_decide_requires_min_passing_frames() -> None:
    template = np.stack([unit(1, 0, 0, 0)])
    same, other = unit(1, 0.1, 0, 0), unit(0, 1, 0, 0)
    ok = decide([same, same, same, other, None], template, threshold=0.9, min_pass=3)
    assert (ok.passed, ok.frames_seen, ok.frames_passed) == (True, 4, 3)
    assert decide([same, same, other, other, None], template, threshold=0.9, min_pass=3).passed is False
    nothing = decide([None, None], template)
    assert (nothing.passed, nothing.best_score, nothing.frames_seen) == (False, None, 0)


def test_other_person_is_rejected_even_if_all_frames_agree() -> None:
    template = np.stack([unit(1, 0, 0, 0), unit(0.9, 0.1, 0, 0)])
    stranger = unit(0, 0, 1, 0)
    assert decide([stranger] * 5, template, threshold=0.363, min_pass=3).passed is False


def test_attempt_log_has_scores_only(tmp_path: Path) -> None:
    template = np.stack([unit(1, 0, 0, 0)])
    log = tmp_path / "logs" / "attempts.csv"
    append_attempt(log, "E-001", "본인", 0.363, decide([unit(1, 0.1, 0, 0)] * 3, template))
    append_attempt(log, "E-001", "팀원A", 0.363, decide([unit(0, 0, 1, 0), None], template))
    append_attempt(log, "E-001", "팀원B", 0.363, decide([None], template))
    rows = [line.split(",") for line in log.read_text(encoding="utf-8").splitlines()]
    assert rows[0] == ["time", "employee_id", "who", "threshold", "best_score", "frames_seen", "frames_passed", "passed"]
    assert [r[2] for r in rows[1:]] == ["본인", "팀원A", "팀원B"]
    assert [r[7] for r in rows[1:]] == ["1", "0", "0"]
    assert rows[3][4] == ""  # 얼굴이 안 잡힌 시도는 점수 칸이 비어 있다
    assert not any("embedding" in cell.lower() for row in rows for cell in row)  # 점수 외 데이터 없음


def test_store_roundtrip_overwrite_delete(tmp_path: Path) -> None:
    store = FaceStore(tmp_path / "templates")
    assert store.load("E-001") is None
    path = store.save("E-001", np.stack([unit(1, 0, 0, 0), unit(0, 1, 0, 0)]))
    assert store.load("E-001").shape == (2, 4)
    store.save("E-001", np.stack([unit(0, 0, 1, 0)]))
    assert store.load("E-001").shape == (1, 4)
    if sys.platform != "win32":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert store.delete("E-001") is True
    assert store.delete("E-001") is False
    assert store.load("E-001") is None


def test_store_rejects_bad_ids_and_empty_embeddings(tmp_path: Path) -> None:
    store = FaceStore(tmp_path)
    for bad in ("", "../x", "a/b", "x" * 17, "한글"):
        with pytest.raises(ValueError):
            store.save(bad, np.stack([unit(1, 0, 0, 0)]))
    with pytest.raises(ValueError):
        store.save("E-001", np.zeros((0, 4)))
    assert list(tmp_path.iterdir()) == []


def test_store_ignores_template_from_another_model(tmp_path: Path) -> None:
    store = FaceStore(tmp_path)
    store.save("E-001", np.stack([unit(1, 0, 0, 0)]), model_version="old-model")
    assert store.load("E-001") is None  # 재등록 필요
    assert store.load("E-001", model_version="old-model") is not None


def test_store_has_no_image_files_only_npz(tmp_path: Path) -> None:
    store = FaceStore(tmp_path)
    store.save("E-001", np.stack([unit(1, 0, 0, 0)]))
    assert [p.suffix for p in tmp_path.iterdir()] == [".npz"]


def test_manifest_pins_commit_and_hashes() -> None:
    assert set(MANIFEST) == {"face_detection_yunet_2023mar.onnx", "face_recognition_sface_2021dec.onnx"}
    for url, digest in MANIFEST.values():
        assert "/47534e27c9851bb1128ccc0102f1145e27f23f98/" in url
        assert len(digest) == 64


def test_fetch_models_skips_download_when_hash_matches(tmp_path: Path, monkeypatch) -> None:
    content = b"fake-model"
    digest = hashlib.sha256(content).hexdigest()
    monkeypatch.setattr("shiftlink.face.models.MANIFEST", {"m.onnx": ("http://invalid.example/m.onnx", digest)})
    (tmp_path / "m.onnx").write_bytes(content)
    assert fetch_models(tmp_path) == {"m.onnx": tmp_path / "m.onnx"}  # 다운로드를 시도하면 invalid URL이라 실패한다


def test_fetch_models_deletes_download_with_wrong_hash(tmp_path: Path, monkeypatch) -> None:
    def fake_retrieve(url, path):
        Path(path).write_bytes(b"tampered")

    monkeypatch.setattr("shiftlink.face.models.MANIFEST", {"m.onnx": ("http://x/m.onnx", "0" * 64)})
    monkeypatch.setattr("shiftlink.face.models.urllib.request.urlretrieve", fake_retrieve)
    with pytest.raises(RuntimeError):
        fetch_models(tmp_path)
    assert not (tmp_path / "m.onnx").exists()


@pytest.mark.skipif(not all((MODEL_DIR / name).exists() for name in MANIFEST), reason="모델 미설치(python -m shiftlink.face fetch)")
def test_real_models_load_and_match_manifest() -> None:
    cv2 = pytest.importorskip("cv2")
    for name, (_, digest) in MANIFEST.items():
        assert sha256(MODEL_DIR / name) == digest
    engine = FaceEngine.load()
    assert engine.embed(np.zeros((240, 320, 3), dtype=np.uint8)) is None  # 얼굴 없는 검은 화면
    assert cv2.__version__
