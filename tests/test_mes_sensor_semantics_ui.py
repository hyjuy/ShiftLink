import subprocess


def test_sensor_semantics_are_used_for_operator_evidence():
    result = subprocess.run(['node', '-e', r'''
const assert = require('node:assert/strict');
const {buildOperatorModel, evidenceView} = require('./shiftlink/mes/web/operator.js');
const signals = [
 {signal:'fluid_viscosity', unit:'cSt', normal_min:40, normal_max:80, semantics:{acquisition:'manual_sample',location:'오일 시료',reference:'측정 온도 40 degC'}},
 {signal:'rt_lift_delay',unit:'s',normal_min:0,normal_max:3,semantics:{acquisition:'event'}},
 {signal:'hpu_accumulator_gas_pressure',unit:'bar',normal_min:145,normal_max:165},
 {signal:'hpu_accumulator_fluid_pressure',unit:'bar',normal_min:145,normal_max:165},
 {signal:'live',unit:'A',normal_min:0,normal_max:2},
];
const config={equipment:[{equipment_id:'EQ',profile_id:'hpu',signals}],scenarios:[]};
const state={equipment:[{equipment_id:'EQ',operating_state:'stopped',fault_level:'normal'}],simulated_at:'2026-10-01T00:00:59Z',scenario_id:'hpu_accumulator_precharge', measurements:signals.map(s=>({equipment_id:'EQ',signal:s.signal,unit:s.unit,value: s.signal==='fluid_viscosity'?60:s.signal==='hpu_accumulator_gas_pressure'?135:0,quality:s.signal==='rt_lift_delay'?'unavailable':'good',observed_at:'2026-10-01T00:00:00Z'}))};
let model=buildOperatorModel(state,config,'EQ');
assert.equal(model.measurements[0].trustworthy,true);
assert.equal(model.measurements[4].trustworthy,false);
let html=evidenceView(model);
assert.match(html,/시료·수동 측정/);
assert.match(html,/오일 시료/);
assert.match(html,/측정 온도 40 degC/);
assert.match(html,/이벤트 기록 없음/);
const eventRow=html.split('<tr').find(r=>r.includes('rt_lift_delay'));
assert.ok(!eventRow.includes('<b>0</b>'));
state.simulated_at='2026-10-01T00:01:00Z';
model=buildOperatorModel(state,config,'EQ');
assert.equal(model.measurements[0].trustworthy,false);
state.measurements.forEach(m=>m.observed_at=state.simulated_at);
model=buildOperatorModel(state,config,'EQ');
html=evidenceView(model);
assert.match(html,/130 ~ 140/);
assert.match(html,/유체 배출 확인/);
assert.equal(model.measurements[2].inRange,true);
assert.equal(model.measurements[3].inRange,true);
assert.ok(!html.split('<tr').find(r=>r.includes('hpu_accumulator_gas_pressure')).includes('이탈'));
'''], stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stdout + result.stderr
