"""Recheck scenario evidence against the project's signal and run contracts."""
from dataclasses import asdict, replace
import json
import subprocess

import pytest

from shiftlink.mes.contracts import Run
from shiftlink.mes.engine import MesEngine
from shiftlink.mes.configuration import from_payload, to_payload, validate
from shiftlink.mes.symptoms import screen_symptoms, symptom_scenarios
from tests.test_mes_symptom_screening import CONFIG
from tests.test_mes_card_adapter import adapter, measurement


@pytest.mark.parametrize("value", [-1, 2, 0.5])
def test_illegal_boolean_values_are_not_condition_or_symptom_evidence(value):
    engine = MesEngine(Run.create(seed=3), CONFIG)
    engine.start()
    engine.set_scenario("symptom_EQ-0002_pdp_trip")
    frames = [asdict(engine.tick()) for _ in range(3)]
    for f in frames:
        for m in f["measurements"]:
            if m["equipment_id"] == "EQ-0002" and m["signal"] == "breaker_trip": m["value"] = value
    assert all(r["status"] != "candidate" for r in screen_symptoms(frames, CONFIG))
    reading = measurement(value, unit="bool", signal="breaker_trip", equipment_id="EQ-0002")
    result = adapter([reading]).search("run", "PDP", "trip")
    assert not result["request"].observations
    assert not result["evidence"]["measurements"][0]["used_for_conditions"]


@pytest.mark.parametrize("change", ["missing_run", "naive_time"])
def test_incomplete_collection_identity_cannot_sustain_a_candidate(change):
    engine = MesEngine(Run.create(seed=3), CONFIG)
    engine.start()
    engine.set_scenario("symptom_EQ-0002_pdp_current")
    frames = [asdict(engine.tick()) for _ in range(3)]
    for f in frames:
        if change == "missing_run": f.pop("run_id")
        else:
            f["simulated_at"] = f["simulated_at"].replace(tzinfo=None)
            for m in f["measurements"]: m["observed_at"] = m["observed_at"].replace(tzinfo=None)
    assert all(r["status"] != "candidate" for r in screen_symptoms(frames, CONFIG))


@pytest.mark.parametrize("bounds", [(1, 1), (0, 1)])
def test_boolean_normal_range_cannot_generate_a_false_trip_scenario(bounds):
    eq = CONFIG.equipment_by_id()["EQ-0002"]
    eq = replace(eq, signals=tuple(replace(s, normal_min=bounds[0], normal_max=bounds[1])
        if s.signal == "breaker_trip" else s for s in eq.signals))
    assert not any(s.scenario_id.endswith("_pdp_trip") for s in symptom_scenarios([eq]))


def test_small_positive_band_still_generates_low_symptom_evidence():
    eq = CONFIG.equipment_by_id()["EQ-0003"]
    eq = replace(eq, signals=tuple(replace(s, normal_min=0.001, normal_max=0.002)
        if s.signal == "air_pressure" else s for s in eq.signals))
    scenarios = list(symptom_scenarios([eq]))
    assert scenarios
    assert all(next(e.value for e in s.signal_effects if e.signal == "air_pressure") < 0.001 for s in scenarios)


def test_operator_does_not_accept_wrong_unit_or_invalid_boolean_as_trusted():
    engine = MesEngine(Run.create(seed=3), CONFIG)
    frame = asdict(engine.snapshot)
    for m in frame["measurements"]:
        if m["equipment_id"] == "EQ-0002":
            if m["signal"] == "breaker_trip": m["value"] = 2
            elif m["signal"] == "bus_current": m["unit"] = "bar"
    script = """
const assert=require('node:assert/strict'),fs=require('node:fs');
const {buildOperatorModel}=require('./shiftlink/mes/web/operator.js');
const {frame,config}=JSON.parse(fs.readFileSync(0,'utf8'));
const model=buildOperatorModel(frame,config,'EQ-0002');
for(const name of ['breaker_trip','bus_current'])
 assert.equal(model.measurements.find(m=>m.signal===name).trustworthy,false,name);
"""
    result = subprocess.run(["node", "-e", script], input=json.dumps({"frame": frame, "config": to_payload(CONFIG)}, default=str),
        text=True, encoding="utf-8", capture_output=True)
    assert result.returncode == 0, result.stderr


def test_config_rejects_illegal_boolean_effect():
    payload = to_payload(CONFIG)
    scenario = next(s for s in payload["scenarios"] if s["scenario_id"] == "symptom_EQ-0002_pdp_trip")
    next(e for e in scenario["signal_effects"] if e["signal"] == "breaker_trip")["value"] = 2
    assert validate(from_payload(payload))


@pytest.mark.parametrize("stage", ["create_run", "record_config_change"])
def test_failed_config_apply_is_not_adopted_on_restart(monkeypatch, stage):
    from shiftlink.mes.server import MesService
    from tests.test_mes_symptom_screening import CATALOG_PATH
    service = MesService(CATALOG_PATH)
    storage = service.storage
    try:
        old_config = service.active_config.config_id
        old_run = service.engine.run.run_id
        draft = to_payload(service.active_config)
        draft["version_label"] = "failed-criteria-test"
        original = getattr(storage, stage)
        def fail_after_write(*args, **kwargs):
            original(*args, **kwargs)
            raise ValueError("criteria failure injection")
        with monkeypatch.context() as m:
            m.setattr(storage, stage, fail_after_write)
            with pytest.raises(ValueError, match="criteria failure injection"):
                service.apply_config({"base_config_id": old_config, "draft": draft})
        assert service.active_config.config_id == old_config
        assert service.engine.run.run_id == old_run
        assert len(storage.list_runs()) == 1
        restarted = MesService(CATALOG_PATH, storage=storage)
        assert restarted.active_config.config_id == old_config
    finally:
        storage.close()
