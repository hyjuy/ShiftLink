"""Synthetic utility anomalies reach observations and recover without changing bands."""

import json
from pathlib import Path

import pytest

from shiftlink.agent.schemas import Condition
from shiftlink.mes.card_adapter import MesCardAdapter
from shiftlink.mes.configuration import from_catalog, validate
from shiftlink.mes.contracts import Run
from shiftlink.mes.engine import MesEngine
from shiftlink.rag.retrieval import InMemoryToolProvider, _evaluate_condition


CATALOG = json.loads((Path(__file__).parents[1] / "docs/data/reference/00_plant_and_relations.json").read_text(encoding="utf-8"))


class Observer:
    def __init__(self, engine):
        self.engine = engine

    def observations(self, run_id, *, as_of=None):
        return {"config_id": self.engine.config.config_id, "snapshot": self.engine.snapshot.as_dict()}


@pytest.mark.parametrize("scenario,equipment,eq_id,alarm,readings", [
    ("cau_supply_fault", "CAU", "EQ-0003", "AL-AIR-LOW", [
        ("air_pressure", 450, "<", 550, "kPa", "low"),
        ("air_flow", 70, "<", 100, "L_min", "low"),
        ("compressor_current", 22, ">", 16, "A", "high"),
    ]),
    ("pdp_trip", "PDP", "EQ-0002", "AL-PDP-TRIP", [
        ("bus_voltage", 90, "<", 97, "pct", "low"),
        ("bus_current", 55, ">", 40, "A", "high"),
        ("breaker_trip", 1, "==", 1, "bool", "high"),
    ]),
])
def test_utility_fault_observations_conditions_and_recovery(scenario, equipment, eq_id, alarm, readings):
    config = from_catalog(CATALOG)
    assert validate(config) == []
    engine = MesEngine(Run.create(seed=3, config_id=config.config_id), config)
    provider = InMemoryToolProvider([], equipment_db=CATALOG["equipment"], equipment_types=CATALOG["equipment_types"])
    adapter = MesCardAdapter(Observer(engine), config, provider)
    engine.start()
    engine.tick()
    engine.set_scenario(scenario)
    result = adapter.search(engine.run.run_id, equipment, "utility anomaly")
    observations = {o.signal: {"value": o.value, "unit": o.unit} for o in result["request"].observations}
    assert alarm in result["evidence"]["alarms"]
    assert result["request"].eq_id == eq_id
    for signal, value, op, boundary, unit, state in readings:
        assert observations[signal] == {"value": value, "unit": unit}
        assert observations[signal + "_state"]["value"] == state
        condition = Condition(signal=signal, op=op, value=boundary, unit=unit)
        assert _evaluate_condition(condition, observations) is True
        normal_value = 0 if signal == "breaker_trip" else boundary
        assert _evaluate_condition(condition, {signal: {"value": normal_value, "unit": unit}}) is False

    engine.tick()
    assert {(m.signal, m.value) for m in engine.snapshot.measurements if m.equipment_id == eq_id} >= {
        (signal, value) for signal, value, *_ in readings}
    engine.recover()
    engine.tick(2)
    assert engine.snapshot.scenario_id == "normal"
    assert not engine.snapshot.active_alarms
    specs = {s.signal: s for e in config.equipment if e.equipment_id == eq_id for s in e.signals}
    for m in engine.snapshot.measurements:
        if m.equipment_id == eq_id:
            assert specs[m.signal].normal_min <= m.value <= specs[m.signal].normal_max
