"""Every installed sensor has an explicit anomaly, without targeting a sibling."""

from dataclasses import replace
import json
import subprocess

import pytest

from shiftlink.agent.schemas import Condition
from shiftlink.mes.card_adapter import MesCardAdapter
from shiftlink.mes.configuration import finalize, from_catalog, from_payload, to_payload, validate
from shiftlink.mes.contracts import Run, SignalSpec
from shiftlink.mes.engine import MesEngine
from shiftlink.mes.scenarios.priority import sensor_anomalies
from shiftlink.rag.retrieval import InMemoryToolProvider, _evaluate_condition
from tests.test_mes_utility_scenarios import CATALOG, Observer


CONFIG = from_catalog(CATALOG)
SENSORS = [(eq, signal) for eq in CONFIG.equipment if eq.active for signal in eq.signals]


@pytest.mark.parametrize("eq,signal", SENSORS, ids=[f"{eq.code}-{s.signal}" for eq, s in SENSORS])
def test_each_installed_sensor_anomaly_reaches_search_and_recovers(eq, signal):
    scenario_id = f"sensor_anomaly_{eq.equipment_id}_{signal.signal}"
    spec = next((s for s in CONFIG.scenarios if s.scenario_id == scenario_id), None)
    assert spec is not None, f"no explicit anomaly for {eq.code}/{signal.signal}"
    assert spec.cause_equipment_id == eq.equipment_id
    assert len(spec.signal_effects) == 1
    value = spec.signal_effects[0].value
    assert value < signal.normal_min or value > signal.normal_max
    assert value >= 0
    if signal.unit == "bool":
        assert value == 1
    if signal.signal.endswith("oil_level") or signal.signal == "cv_queue_len":
        assert value <= 100

    engine = MesEngine(Run.create(seed=3, config_id=CONFIG.config_id), CONFIG)
    engine.start()
    engine.tick()
    provider = InMemoryToolProvider([], equipment_db=CATALOG["equipment"], equipment_types=CATALOG["equipment_types"])
    adapter = MesCardAdapter(Observer(engine), CONFIG, provider)
    engine.set_scenario(scenario_id)
    result = adapter.search(engine.run.run_id, eq.equipment_id, "sensor anomaly")
    observations = {o.signal: {"value": o.value, "unit": o.unit} for o in result["request"].observations}
    assert observations[signal.signal] == {"value": value, "unit": signal.unit}
    state = "low" if value < signal.normal_min else "high"
    assert observations[signal.signal + "_state"]["value"] == state
    boundary = signal.normal_min if state == "low" else signal.normal_max
    condition = Condition(signal=signal.signal, op="<" if state == "low" else ">", value=boundary, unit=signal.unit)
    assert _evaluate_condition(condition, observations) is True
    assert _evaluate_condition(condition, {signal.signal: {"value": boundary, "unit": signal.unit}}) is False
    assert {(a.equipment_id, a.code) for a in engine.snapshot.active_alarms} == {(eq.equipment_id, spec.alarm_code)}
    for m in engine.snapshot.measurements:
        if m.equipment_id != eq.equipment_id and m.signal == signal.signal:
            sibling = next(s for e in CONFIG.equipment if e.equipment_id == m.equipment_id for s in e.signals if s.signal == m.signal)
            assert sibling.normal_min <= m.value <= sibling.normal_max
    engine.recover()
    engine.tick(2)
    recovered = next(m for m in engine.snapshot.measurements if m.equipment_id == eq.equipment_id and m.signal == signal.signal)
    assert signal.normal_min <= recovered.value <= signal.normal_max
    assert not engine.snapshot.active_alarms


def test_exact_target_roundtrip_and_legacy_payload_are_preserved():
    assert validate(CONFIG) == []
    assert from_payload(to_payload(CONFIG)) == CONFIG
    legacy = finalize(replace(CONFIG, scenarios=tuple(s for s in CONFIG.scenarios if not s.scenario_id.startswith(("sensor_anomaly_", "symptom_")))))
    payload = to_payload(legacy)
    assert all("cause_equipment_id" not in s for s in payload["scenarios"])
    assert from_payload(payload) == legacy


@pytest.mark.parametrize("target", ["EQ-9999", "EQ-0002"])
def test_invalid_exact_target_never_falls_back_to_first_capability(target):
    scenario = next(s for s in CONFIG.scenarios if s.scenario_id == "sensor_anomaly_EQ-0005_gr_current")
    broken = replace(CONFIG, scenarios=(replace(scenario, cause_equipment_id=target),))
    assert validate(broken)
    engine = MesEngine(Run.create(seed=3), broken)
    with pytest.raises(ValueError):
        engine.set_scenario(scenario.scenario_id)


@pytest.mark.parametrize("signal,expected", [
    (SignalSpec("trip", "trip", "bool", 1, 1), 0),
    (SignalSpec("tiny_pressure", "pressure", "bar", 0.001, 0.002), 0),
    (SignalSpec("trip", "trip", "bool", 0, 1), None),
])
def test_custom_boolean_and_small_ranges_have_valid_anomalies(signal, expected):
    eq = replace(CONFIG.equipment[0], signals=(signal,))
    specs = list(sensor_anomalies([eq]))
    if expected is None:
        assert specs == []
    else:
        assert len(specs) == 1
        value = specs[0].signal_effects[0].value
        assert value == expected
        assert not signal.normal_min <= value <= signal.normal_max


def test_operator_screen_uses_exact_targets_for_all_sensor_scenarios():
    frames = []
    for eq, signal in SENSORS:
        engine = MesEngine(Run.create(seed=3, config_id=CONFIG.config_id), CONFIG)
        engine.start()
        engine.set_scenario(f"sensor_anomaly_{eq.equipment_id}_{signal.signal}")
        frames.append({"eq_id": eq.equipment_id, "signal": signal.signal, "snapshot": engine.snapshot.as_dict()})
    result = subprocess.run(["node", "-e", """
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {buildOperatorModel} = require('./shiftlink/mes/web/operator.js');
const {config, frames} = JSON.parse(fs.readFileSync(0, 'utf8'));
for (const f of frames) {
  const own = buildOperatorModel(f.snapshot, config, f.eq_id);
  assert.equal(own.cause.equipment_id, f.eq_id);
  assert.equal(own.measurements.find(m=>m.signal===f.signal).relevant, true);
  for (const eq of config.equipment.filter(e=>e.equipment_id!==f.eq_id)) {
    const other = buildOperatorModel(f.snapshot, config, eq.equipment_id);
    assert.equal(other.measurements.some(m=>m.relevant), false);
  }
}
"""], input=json.dumps({"config": to_payload(CONFIG), "frames": frames}, default=str),
        text=True, encoding="utf-8", capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
