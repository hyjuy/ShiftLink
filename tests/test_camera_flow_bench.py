import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bench"))
import camera_flow_bench as b  # noqa: E402


def test_demo_questions_reads_nine():
    q = b.demo_questions(b.ROOT / "docs/planning/시연_질문_9개_20261006.md")
    assert {k: len(v) for k, v in q.items()} == {"HPU": 3, "GR": 3, "CV": 3}


def test_plan_alternates_classes(tmp_path):
    for c in ("HPU", "GR"):
        (tmp_path / c).mkdir()
        for i in range(2):
            (tmp_path / c / f"{i}.png").write_bytes(b"x")
    items = b.plan(tmp_path, {"HPU": ["q1", "q2"], "GR": ["g1"], "CV": ["c1"]}, 5)
    assert [c for c, _, _ in items] == ["HPU", "GR", "HPU", "GR", "HPU"]
    assert [q for _, _, q in items][:3] == ["q1", "g1", "q2"]


def test_judge_reasons():
    ok = {"sent": True, "confirmed": True, "class": "HPU"}
    res = {"evidence": {"equipment_id": "EQ-1"}, "answer": "a"}
    assert b.judge("HPU", "EQ-1", ok, {"scan_id": "s"}, 200, res) == "ok"
    assert b.judge("HPU", "EQ-1", {"sent": False, "confirmed": False}, None, 0, {}).startswith("보류")
    assert b.judge("HPU", "EQ-1", {**ok, "class": "GR"}, {"scan_id": "s"}, 200, res).startswith("오분류")
    assert b.judge("HPU", "EQ-1", ok, {"scan_id": "s"}, 503, {}) == "질의 HTTP 503"
    assert b.judge("HPU", "EQ-1", ok, {"scan_id": "s"}, 200, {"evidence": {}, "no_knowledge": True}).startswith("응답 설비")
