from typing import get_args

from shiftlink.agent.schemas import Equipment
from shiftlink.vision import CLASSES
from shiftlink.vision.classify import Stabilizer


def test_classes_match_schema_equipment():
    assert set(CLASSES) == set(get_args(Equipment)) - {"COMMON"}


def feed(stab, seq):
    return [stab.update(label, conf) for label, conf in seq]


def test_confirms_once_after_n_frames():
    stab = Stabilizer(min_conf=0.8, frames=3)
    out = feed(stab, [("HPU", 0.9)] * 6)
    assert out == [None, None, "HPU", None, None, None]


def test_low_conf_and_flicker_do_not_confirm():
    stab = Stabilizer(min_conf=0.8, frames=3)
    assert feed(stab, [("HPU", 0.9), ("GR", 0.9), ("HPU", 0.9), ("HPU", 0.5), ("HPU", 0.9)]) == [None] * 5


def test_switch_class_and_reconfirm_after_removal():
    stab = Stabilizer(min_conf=0.8, frames=2)
    assert feed(stab, [("HPU", 0.9)] * 2)[-1] == "HPU"
    assert feed(stab, [("GR", 0.95)] * 2)[-1] == "GR"
    feed(stab, [("GR", 0.1)] * 2)  # 객체 치움
    assert feed(stab, [("GR", 0.95)] * 2)[-1] == "GR"


def test_shot_classifier_sends_only_confident_shots(tmp_path, monkeypatch):
    from shiftlink.vision import classify

    (tmp_path / "labels.txt").write_text("HPU\nGR\n", encoding="utf-8")
    sent, confs = [], iter([0.95, 0.5])
    monkeypatch.setattr(classify, "classify_bytes", lambda s, labels, data: ("HPU", next(confs), 1.0))
    monkeypatch.setattr(classify, "post_scan", lambda server, label, conf, dev: sent.append(label) or True)
    shoot = classify.ShotClassifier(tmp_path, "http://jetson", "pi-01", save_dir=tmp_path / "shots", session=object())

    assert shoot(b"jpg")["sent"] is True
    r = shoot(b"jpg")
    assert (r["confirmed"], r["sent"]) == (False, False)  # 0.8 미만은 Jetson에 보내지 않는다
    assert sent == ["HPU"] and len(list((tmp_path / "shots").iterdir())) == 2
