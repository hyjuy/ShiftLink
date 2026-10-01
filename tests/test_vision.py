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
