const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
  constructor() { this.children = []; this.parts = {}; this.textContent = ''; this.classList = {remove(){},toggle(){}}; }
  set innerHTML(value) { this.children = []; this.parts = {}; }
  appendChild(child) { this.children.push(child); }
  querySelector(selector) { return this.parts[selector] ||= new Element(); }
  addEventListener() {}
  text() { return [this.textContent, ...this.children.map(x=>x.text()), ...Object.values(this.parts).map(x=>x.text())].join(' '); }
}
const nodes = {};
const context = vm.createContext({URLSearchParams});
vm.runInContext(fs.readFileSync(require.resolve('../shiftlink/mes/web/pda.js'), 'utf8'), context);
context.document = {getElementById:id=>nodes[id] ||= new Element(),createElement:()=>new Element()};
vm.runInContext(`
  S.eq = {equipment_id:'EQ-0001',signals:[
    {signal:'hpu_pressure',name:'유압 압력',unit:'bar',min:145,max:165,semantics:{}},
    {signal:'hpu_oil_temp',name:'유온',unit:'degC',min:40,max:58,semantics:{}}
  ]};
  S.observations = [{signal:'hpu_pressure',value:100,unit:'bar',source:'manual'}];
  S.obsRemoved = ['hpu_oil_temp'];
  S.screen = 'ctx';
`,context);
const snapshot = {simulated_at:'2026-10-07T06:18:57.622226+00:00',equipment:[{equipment_id:'EQ-0001',operating_state:'running',fault_level:'normal'}],
  measurements:[
    {equipment_id:'EQ-0001',signal:'hpu_pressure',value:154.845,unit:'bar',quality:'good',observed_at:'2026-10-07T06:18:57.622226+00:00'},
    {equipment_id:'EQ-0001',signal:'hpu_oil_temp',value:47.05,unit:'degC',quality:'good',observed_at:'2026-10-07T06:18:57.622226+00:00'},
    {equipment_id:'OTHER',signal:'hpu_pressure',value:999,unit:'bar',quality:'good'}
  ],active_alarms:[],symptom_diagnostics:[]};
context.snapshot = snapshot;
(async()=>{
  await vm.runInContext('loadMesObservations(snapshot)',context);
  assert.match(nodes.ctxSensors.text(),/154\.845 bar/);
  assert.match(nodes.ctxSensors.text(),/47\.05 ℃/);
  assert.match(nodes.ctxSensors.text(),/정상 범위 145~165 bar/);
  assert.doesNotMatch(nodes.ctxSensors.text(),/999/);
  assert.match(nodes.obsList.text(),/100 bar/);
  assert.match(nodes.obsList.text(),/정상 범위 145~165 bar/);
  assert.equal(vm.runInContext('S.observations.length',context),1,'manual overrides and removals still apply to query inputs');
  vm.runInContext(`S.queryResponse = {answer:'확인', evidence:{equipment_id:'EQ-0001',simulated_at:'2026-10-07T06:00:00Z',
    measurements:[{equipment_id:'EQ-0001',signal:'hpu_pressure',value:120,unit:'bar',observed_at:'2026-10-07T06:00:00Z',used_for_conditions:true}]}};
    S.ranked = {safety:[],actions:[],excluded:[]}; answer = answerBody({response:S.queryResponse, ranked:S.ranked});`,context);
  assert.match(context.answer.text(),/질의 당시/);
  assert.match(context.answer.text(),/120 bar/);
  assert.doesNotMatch(context.answer.text(),/154\.845/);
  vm.runInContext(`S.eq.type='HPU'; S.cards=[{card_id:'K',equipment:'HPU',conditions:[{signal:'hpu_pressure',op:'<',value:145}]}];
    S.observations=[{signal:'hpu_pressure',value:155,unit:'bar',source:'manual'}];`,context);
  assert.equal(vm.runInContext('rankCards(S.eq).excluded.length',context),1);
  assert.equal(vm.runInContext('rankCards(S.eq, S.queryResponse.evidence.measurements).actions.length',context),1,'result ranking uses frozen evidence, not recovered live pressure');
  snapshot.measurements[0].quality = 'bad';
  await vm.runInContext('loadMesObservations(snapshot)',context);
  assert.doesNotMatch(nodes.ctxSensors.text(),/154\.845/);
  vm.runInContext(`getJson = async () => { throw new Error('offline'); };`,context);
  await vm.runInContext('loadMesObservations()',context);
  assert.match(nodes.ctxSensors.text(),/연결|읽지 못/);
  assert.doesNotMatch(nodes.ctxSensors.text(),/47\.05/);
  assert.equal(vm.runInContext('S.observations[0].source',context),'manual');
  vm.runInContext(`S.observations.push({source:'mes',signal:'hpu_oil_temp',value:47.05});`,context);
  await vm.runInContext('loadMesObservations()',context);
  assert.equal(vm.runInContext('S.observations.length',context),1,'disconnected sensor values cannot become current query evidence');
  console.log('PDA sensor display, quality, manual override and disconnect PASS');
})().catch(err=>{console.error(err);process.exitCode=1;});
