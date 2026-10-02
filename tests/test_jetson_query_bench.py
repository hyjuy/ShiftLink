"""J3 측정 스크립트: p95 계산과 형식 코드 → 설비 ID 매핑."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("jqb", Path(__file__).resolve().parents[1] / "bench/jetson_query_bench.py")
jqb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jqb)


def test_p95_nearest_rank():
    assert jqb.p95([float(i) for i in range(1, 21)]) == 19.0
    assert jqb.p95([3.0]) == 3.0


def test_equipment_ids_pick_smallest_per_type():
    catalog = {
        "equipment_types": [{"type_code": "GR", "equipment_type_id": "T-GR"}, {"type_code": "CAU", "equipment_type_id": "T-CAU"}],
        "equipment": [{"equipment_id": "EQ-0005", "equipment_type_id": "T-GR"},
                      {"equipment_id": "EQ-0004", "equipment_type_id": "T-GR"}],
    }
    assert jqb.equipment_ids(catalog) == {"GR": "EQ-0004"}  # 설비 없는 형식은 빠진다
