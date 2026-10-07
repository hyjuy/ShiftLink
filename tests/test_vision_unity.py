"""Unity 사진 → 분류 데이터셋 변환, 평가 요약, INT8 보정 표본, 파이 사진 수신 모드, PC 감시 스크립트."""
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import cv2
import numpy as np
import pytest

from scripts.send_unity_captures import ready
from shiftlink.vision import classify
from shiftlink.vision.evaluate import summarize
from shiftlink.vision.quantize import calibration_paths
from shiftlink.vision.unity_cls import convert, dominant_class


def png(path: Path, color=(0, 0, 255)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), np.full((36, 64, 3), color, dtype=np.uint8))
    return path


def test_dominant_class_takes_the_largest_box_and_drops_tiny_or_empty():
    assert dominant_class("1 0.5 0.5 0.2 0.2\n3 0.5 0.5 0.6 0.5\n") == "CV"  # CLASSES[3], area 0.30 > 0.04
    assert dominant_class("0 0.5 0.5 0.1 0.1\n") is None  # 0.01 < MIN_AREA
    assert dominant_class("") is None


def test_convert_keeps_unity_splits_and_counts_skipped(tmp_path):
    ds = tmp_path / "yolo"
    for split, name, label in [("train", "a", "0 0.5 0.5 0.5 0.5\n"), ("train", "b", ""), ("test", "c", "5 0.5 0.5 0.4 0.4\n")]:
        png(ds / "images" / split / f"{name}.png")
        (ds / "labels" / split).mkdir(parents=True, exist_ok=True)
        (ds / "labels" / split / f"{name}.txt").write_text(label, encoding="utf-8")
    counts = convert(ds, tmp_path / "cls")
    assert counts["train"] == {"HPU": 1, "(제외)": 1} and counts["test"] == {"PDP": 1} and not counts["val"]
    assert (tmp_path / "cls" / "train" / "HPU" / "a.png").exists() and (tmp_path / "cls" / "test" / "PDP" / "c.png").exists()
    with pytest.raises(SystemExit):
        convert(ds, tmp_path / "cls")  # never overwrites


def test_summarize_reports_per_class_accuracy_and_confusion():
    r = summarize(["GR", "HPU"], [("GR", "GR"), ("GR", "HPU"), ("HPU", "HPU")], [3.0, 1.0, 2.0])
    assert r["acc"] == round(2 / 3, 4) and r["per_class"]["GR"] == {"n": 2, "correct": 1, "acc": 0.5}
    assert r["confusion"]["GR"]["HPU"] == 1 and r["ms_p50"] == 2.0 and r["ms_p95"] == 3.0


def test_calibration_takes_classes_in_turn(tmp_path):
    for i in range(3):
        png(tmp_path / "GR" / f"g{i}.png")
    png(tmp_path / "HPU" / "h0.png")
    picked = calibration_paths(tmp_path, 3)
    assert [p.parent.name for p in picked] == ["GR", "HPU", "GR"]


class FakeSession:
    def __init__(self, logits):
        self.logits = np.array([logits], dtype=np.float32)

    def run(self, _outputs, feed):
        assert feed["input"].shape == (1, 3, 224, 224)
        return [self.logits]


@pytest.fixture
def listen(monkeypatch):
    sent = []
    monkeypatch.setattr(classify, "post_scan", lambda server, label, conf, device: sent.append((label, device)) or True)

    def start(logits, min_conf=0.8):
        handler = classify.make_handler(FakeSession(logits), ["GR", "HPU"], min_conf, "http://jetson", "pi-01")
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server, f"http://127.0.0.1:{server.server_port}/classify"

    yield start, sent


def post(url, data):
    with urllib.request.urlopen(urllib.request.Request(url, data=data, method="POST"), timeout=5) as resp:
        return json.load(resp)


def test_listen_mode_classifies_a_photo_and_sends_only_confident_results(listen, tmp_path):
    start, sent = listen
    image = png(tmp_path / "shot.png").read_bytes()
    server, url = start([0.0, 5.0])
    try:
        r = post(url, image)
        assert r["class"] == "HPU" and r["confirmed"] and r["sent"] and sent == [("HPU", "pi-01")]
    finally:
        server.shutdown()
    server, url = start([0.0, 0.1])  # ~0.52: below min_conf → answer but do not send
    try:
        r = post(url, image)
        assert r["class"] == "HPU" and not r["confirmed"] and not r["sent"] and len(sent) == 1
        with pytest.raises(urllib.error.HTTPError) as bad:
            post(url, b"not an image")
        assert bad.value.code == 400
    finally:
        server.shutdown()


def test_watcher_sends_only_pngs_whose_json_is_saved(tmp_path):
    png(tmp_path / "done.png")
    (tmp_path / "done.json").write_text("{}", encoding="utf-8")
    png(tmp_path / "saving.png")
    assert ready(tmp_path) == {tmp_path / "done.png"}
