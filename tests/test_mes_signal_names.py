"""화면에 신호 ID(gr_vib_rms 등)가 이름 대신 나오지 않는다."""
import json
from pathlib import Path

from shiftlink.mes import configuration

CATALOG = Path(__file__).resolve().parents[1] / "docs/data/reference/00_plant_and_relations.json"


def test_every_signal_has_a_korean_name():
    config = configuration.from_catalog(json.loads(CATALOG.read_text(encoding="utf-8")))
    raw = [(eq.code, s.signal) for eq in config.equipment for s in eq.signals if s.name == s.signal]
    assert raw == []


def test_stored_sensor_scenario_titles_use_names():
    from dataclasses import replace
    from shiftlink.mes.scenarios.priority import expand
    config = configuration.from_catalog(json.loads(CATALOG.read_text(encoding="utf-8")))
    # 이름이 채워지기 전에 저장된 구성처럼 만든다
    old = replace(config, scenarios=tuple(replace(s, title=s.title.replace("감속기 진동 RMS", "gr_vib_rms"))
                                          for s in config.scenarios))
    titles = {s.scenario_id: s.title for s in expand(old).scenarios}
    assert titles["sensor_anomaly_EQ-0005_gr_vib_rms"] == "GR-02 · 감속기 진동 RMS 이상"
