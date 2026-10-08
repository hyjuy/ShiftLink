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


def test_frame_scanner_sends_once_and_again_after_gap(tmp_path, monkeypatch):
    from shiftlink.vision import classify

    (tmp_path / "labels.txt").write_text("HPU\nGR\n", encoding="utf-8")
    sent = []
    monkeypatch.setattr(classify, "classify_bytes", lambda s, labels, data: ("HPU", 0.95, 1.0))
    monkeypatch.setattr(classify, "post_scan", lambda server, label, conf, dev: sent.append(label) or True)
    sc = classify.FrameScanner(tmp_path, "http://jetson", "pi-01", frames=2, gap_s=0.2, session=object())

    def offer():
        assert sc.offer(b"jpg")
        sc._busy.acquire(); sc._busy.release()  # 분류 스레드가 끝날 때까지

    for _ in range(4):
        offer()
    assert sent == ["HPU"]  # 같은 설비를 계속 비춰도 한 번
    sc._last -= 1  # 스캔 화면을 나갔다가 다시 열었다
    offer(); offer()
    assert sent == ["HPU", "HPU"]
