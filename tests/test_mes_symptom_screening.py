"""Symptoms are inferred from observable combinations, never injected cause labels."""
from dataclasses import asdict, replace
from pathlib import Path
import json
import subprocess

import pytest

from shiftlink.mes.configuration import from_catalog, from_payload, to_payload
from shiftlink.mes.contracts import Run
from shiftlink.mes.engine import MesEngine
from shiftlink.mes.server import MesService


CATALOG_PATH = Path("docs/data/reference/00_plant_and_relations.json")
CONFIG = from_catalog(json.loads(CATALOG_PATH.read_text(encoding="utf-8")))


@pytest.mark.parametrize("equipment,pattern", [
    ("EQ-0001", "hpu_delivery"), ("EQ-0001", "hpu_restriction"), ("EQ-0001", "hpu_heat"),
    ("EQ-0003", "cau_supply"), ("EQ-0003", "cau_flow_demand"),
    ("EQ-0002", "pdp_voltage"), ("EQ-0002", "pdp_current"), ("EQ-0002", "pdp_trip"),
    ("EQ-0004", "gr_lubrication"), ("EQ-0005", "gr_load"),
    ("EQ-0006", "rt_resistance"), ("EQ-0008", "rt_clamp"), ("EQ-0007", "rt_lift"),
    ("EQ-0009", "cv_slip"), ("EQ-0010", "cv_resistance"),
])
def test_symptom_scenarios_produce_observable_candidates(equipment, pattern):
    engine = MesEngine(Run.create(seed=3, config_id=CONFIG.config_id), CONFIG)
    engine.start()
    engine.tick()
    engine.set_scenario(f"symptom_{equipment}_{pattern}")
    engine.tick(3)
    result = engine.symptom_diagnostics()
    match = next(r for r in result if r["equipment_id"] == equipment and r["pattern_id"] == pattern)
    assert match["status"] == "candidate"
    assert match["confirmed"] is False
    assert len(match["evidence"]) >= 3
    assert match["candidates"] and match["checks"] and match["sources"]
    assert match["threshold_basis"] == "synthetic_config"
    assert all(r["equipment_id"] == equipment for r in result)
    engine.recover()
    engine.tick(2)
    assert engine.symptom_diagnostics() == []


def test_candidates_depend_on_measurements_and_distinguish_symptoms():
    from shiftlink.mes.symptoms import screen_symptoms
    engine = MesEngine(Run.create(seed=3, config_id=CONFIG.config_id), CONFIG)
    engine.start()
    engine.set_scenario("symptom_EQ-0003_cau_flow_demand")
    frames = [asdict(engine.tick()) for _ in range(3)]
    for f in frames:
        f["scenario_id"] = "SECRET_FAKE_CAUSE"
        f["active_alarms"] = []
        f["equipment"] = []
    result = screen_symptoms(frames, CONFIG)
    match = next(r for r in result if r["pattern_id"] == "cau_flow_demand")
    assert "SECRET" not in str(result)
    assert "누설" in " ".join(match["candidates"])
    assert "수요" in " ".join(match["candidates"])
    assert "cau_supply" not in {r["pattern_id"] for r in result}


@pytest.mark.parametrize("change", ["missing", "bad_quality", "unit", "nan", "boolean", "stale"])
def test_incomplete_or_unreliable_evidence_does_not_confirm_candidates(change):
    from shiftlink.mes.symptoms import screen_symptoms
    engine = MesEngine(Run.create(seed=3), CONFIG)
    engine.start()
    engine.set_scenario("symptom_EQ-0009_cv_slip")
    frames = [asdict(engine.tick()) for _ in range(3)]
    for f in frames:
        reading = next(m for m in f["measurements"] if m["equipment_id"] == "EQ-0009" and m["signal"] == "cv_belt_tension")
        if change == "missing": f["measurements"] = tuple(m for m in f["measurements"] if m is not reading)
        elif change == "bad_quality": reading["quality"] = "bad"
        elif change == "unit": reading["unit"] = "bar"
        elif change == "nan": reading["value"] = float("nan")
        elif change == "boolean": reading["value"] = True
        else: reading["observed_at"] = "2000-01-01T00:00:00+00:00"
    records = screen_symptoms(frames, CONFIG)
    match = next(r for r in records if r["pattern_id"] == "cv_slip")
    assert match["status"] == "unverified"
    assert match["confirmed"] is False


def test_transients_pause_reset_and_duplicate_frames_do_not_accumulate_confirmation():
    from shiftlink.mes.symptoms import screen_symptoms
    engine = MesEngine(Run.create(seed=3), CONFIG)
    engine.start()
    engine.set_scenario("symptom_EQ-0002_pdp_current")
    frame = asdict(engine.tick())
    assert all(r["status"] != "candidate" for r in screen_symptoms([frame] * 3, CONFIG))
    engine.tick(2)
    assert any(r["status"] == "candidate" for r in engine.symptom_diagnostics())
    engine.pause()
    assert all(r["status"] != "candidate" for r in engine.symptom_diagnostics())
    engine.reset()
    assert engine.symptom_diagnostics() == []


def test_trip_has_zero_current_and_other_symptoms_remain_observable_while_running():
    engine = MesEngine(Run.create(seed=3), CONFIG)
    engine.start()
    engine.set_scenario("symptom_EQ-0002_pdp_current")
    state = next(e for e in engine.snapshot.equipment if e.equipment_id == "EQ-0002")
    assert (state.operating_state, state.fault_level) == ("running", "warning")
    assert engine.snapshot.active_alarms[0].severity == "warning"
    engine.set_scenario("symptom_EQ-0002_pdp_trip")
    values = {m.signal: m.value for m in engine.snapshot.measurements if m.equipment_id == "EQ-0002"}
    assert values["breaker_trip"] == 1 and values["bus_current"] == 0
    assert from_payload(to_payload(CONFIG)) == CONFIG


def test_service_and_operator_display_observation_candidates():
    service = MesService(CATALOG_PATH)
    try:
        service.engine.start()
        service.engine.set_scenario("symptom_EQ-0009_cv_slip")
        for _ in range(3): service.tick()
        state = service.state()
        assert state["symptom_diagnostics"]
        result = subprocess.run(["node", "-e", """
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {buildOperatorModel,evidenceView}=require('./shiftlink/mes/web/operator.js');
const {snapshot,config}=JSON.parse(fs.readFileSync(0,'utf8'));
const html=evidenceView(buildOperatorModel(snapshot,config,'EQ-0009'));
assert.match(html,/원인 후보/);
assert.match(html,/슬립/);
assert.match(html,/확정 진단/);
"""], input=json.dumps({"snapshot": state, "config": to_payload(service.active_config)}),
            text=True, encoding="utf-8", capture_output=True)
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        service.storage.close()
