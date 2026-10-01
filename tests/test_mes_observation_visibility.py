"""Generic recovery plans for unauthored scenarios and out-of-range evidence highlighting."""

import subprocess

import pytest

from shiftlink.mes.contracts import Run
from shiftlink.mes.engine import MesEngine
from tests.test_mes_all_sensor_anomalies import CONFIG


def _engine(scenario_id):
    engine = MesEngine(Run.create(seed=3, config_id=CONFIG.config_id), CONFIG)
    engine.start()
    engine.tick()
    engine.set_scenario(scenario_id)
    engine.tick()
    return engine


def test_unauthored_scenario_gets_optional_check_repair_verify_plan():
    engine = _engine("sensor_anomaly_EQ-0001_hpu_pressure")
    plan = engine.snapshot.recovery
    assert plan["required"] is False and plan["stage"] == "actions"
    assert [a["action_id"] for a in plan["actions"]] == ["inspect", "repair", "verify"]
    assert "HPU-01" in plan["actions"][0]["detail"]

    for action in ("inspect", "repair", "verify"):
        engine.perform_action(action)
    pressure = next(m for m in engine.snapshot.measurements if m.equipment_id == "EQ-0001" and m.signal == "hpu_pressure")
    assert 145 <= pressure.value <= 165, "verify restores the injected signal"
    engine.recover()
    engine.tick(2)
    assert engine.snapshot.scenario_id == "normal"
    assert engine.snapshot.recovery["stage"] == "completed"


def test_optional_plan_never_blocks_direct_recovery_or_switching():
    engine = _engine("sensor_anomaly_EQ-0001_hpu_pressure")
    engine.set_scenario("sensor_anomaly_EQ-0004_gr_current")
    engine.recover()
    engine.tick(2)
    assert engine.snapshot.scenario_id == "normal"


def test_authored_plan_still_gates_recovery():
    engine = _engine("gearbox_overheat")
    assert engine.snapshot.recovery["required"] is True
    with pytest.raises(ValueError):
        engine.recover()
    with pytest.raises(ValueError):
        engine.set_scenario("normal")


def test_out_of_range_rows_lead_with_direction_deviation_and_fold_the_rest():
    result = subprocess.run(['node', '-e', r'''
const assert = require('node:assert/strict');
const {buildOperatorModel, evidenceView} = require('./shiftlink/mes/web/operator.js');
const signals = [
 {signal:'ok', name:'정상', unit:'bar', normal_min:145, normal_max:165},
 {signal:'low', name:'낮음', unit:'bar', normal_min:145, normal_max:165},
 {signal:'high', name:'높음', unit:'A', normal_min:15, normal_max:25},
 {signal:'zero', name:'정지', unit:'L_min', normal_min:38, normal_max:46, zero_when_stopped:true},
];
const config={equipment:[{equipment_id:'EQ',profile_id:'hpu',signals}],scenarios:[]};
const at='2026-10-01T00:00:00Z', values={ok:150,low:116,high:31.25,zero:0};
const state={equipment:[{equipment_id:'EQ',operating_state:'stopped',fault_level:'critical'}],simulated_at:at,scenario_id:'x',
  measurements:signals.map(s=>({equipment_id:'EQ',signal:s.signal,unit:s.unit,value:values[s.signal],quality:'good',observed_at:at}))};
const model=buildOperatorModel(state,config,'EQ');
assert.deepEqual(model.measurements.filter(m=>m.outOfRange).map(m=>[m.signal,m.direction]),[['low','low'],['high','high']]);
const html=evidenceView(model);
assert.match(html,/범위 이탈 2/);
assert.match(html,/href="#signal-EQ-low"/);
assert.match(html,/▼ 하한 미만/);
assert.match(html,/하한 145 대비 -29 bar \(-20%\)/);
assert.match(html,/▲ 상한 초과/);
assert.match(html,/상한 25 대비 \+6.25 A \(\+25%\)/);
const [main, rest]=html.split('class="signal-rest"');
assert.ok(main.includes('id="signal-EQ-low"') && main.includes('id="signal-EQ-high"'));
assert.ok(!main.includes('id="signal-EQ-ok"') && rest.includes('id="signal-EQ-ok"'), 'in-range rows fold away');
assert.match(rest.split('<tr').find(r=>r.includes('signal-EQ-zero')),/class="muted"/);
// Nothing out of range: one unfolded table.
state.measurements.forEach(m=>{ if (m.signal==='low') m.value=150; if (m.signal==='high') m.value=20; });
const calm=evidenceView(buildOperatorModel(state,config,'EQ'));
assert.ok(!calm.includes('signal-rest') && calm.includes('범위 이탈 0'));
'''], stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stdout + result.stderr


def test_recovery_view_offers_skip_only_for_optional_plans():
    result = subprocess.run(['node', '-e', r'''
const assert = require('node:assert/strict');
const {recoveryView} = require('./shiftlink/mes/web/app.js');
const plan=required=>({title:'t',stage:'actions',required,actions:[{action_id:'inspect',title:'확인',detail:'d',completed:false}]});
assert.match(recoveryView({recovery:plan(false),coils:[]},true),/조치 생략 · 바로 복귀 진행/);
assert.match(recoveryView({recovery:plan(false),coils:[]},true),/data-action="inspect"/);
assert.doesNotMatch(recoveryView({recovery:plan(true),coils:[]},true),/조치 생략/);
'''], stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stdout + result.stderr


def test_scenario_titles_drop_the_virtual_label_even_for_stored_baselines():
    from dataclasses import replace
    from shiftlink.mes.configuration import finalize
    from shiftlink.mes.scenarios.priority import expand
    assert not [s.title for s in CONFIG.scenarios if "(가상)" in s.title]
    old = finalize(replace(CONFIG, scenarios=tuple(replace(s, title=s.title + " (가상)") for s in CONFIG.scenarios)))
    assert not [s.title for s in expand(old).scenarios if "(가상)" in s.title]
