const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
  constructor() { this.children = []; this.parts = {}; this.textContent = ''; this.classList = {remove(){},toggle(){},add(){}}; }
  set innerHTML(value) { this.children = []; this.parts = {}; }
  appendChild(child) { this.children.push(child); }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children=children; }
  querySelector(selector) { return this.parts[selector] ||= new Element(); }
  addEventListener() {}
  setAttribute(name,value) { this[name]=value; }
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
  // 질의 당시 센서값은 설비 칸이 보여 주므로 답 근거에 다시 싣지 않는다
  assert.doesNotMatch(context.answer.text(),/질의 당시|120 bar/);
  assert.doesNotMatch(context.answer.text(),/154\.845/);
  vm.runInContext(`S.eq.type='HPU'; S.cards=[{card_id:'K',equipment:'HPU',conditions:[{signal:'hpu_pressure',op:'<',value:145}]}];
    S.observations=[{signal:'hpu_pressure',value:155,unit:'bar',source:'manual'}];`,context);
  assert.equal(vm.runInContext('rankCards(S.eq).excluded.length',context),1);
  assert.equal(vm.runInContext('rankCards(S.eq, S.queryResponse.evidence.measurements).actions.length',context),1,'result ranking uses frozen evidence, not recovered live pressure');
  vm.runInContext('S.sensorSnapshot = null; renderEquipmentMetrics()', context);
  const frozenTime = nodes.metricsTime.textContent;
  assert.match(nodes.equipmentMetrics.text(), /154\.845/);
  snapshot.measurements[0].value = 160;
  snapshot.simulated_at = '2026-10-07T06:19:00.000000+00:00';
  await vm.runInContext('loadMesObservations(snapshot)', context);
  assert.match(nodes.equipmentMetrics.text(), /154\.845/, 'sensor panel keeps its values until refresh');
  assert.equal(nodes.metricsTime.textContent, frozenTime, 'snapshot time stays fixed');
  assert.equal(vm.runInContext('S.mes.readings[0].value',context), 160, 'live monitoring still updates');
  vm.runInContext('S.sensorSnapshot = null; renderEquipmentMetrics()',context);  // 새로고침 버튼과 같은 동작
  assert.match(nodes.equipmentMetrics.text(), /160/, 'refresh captures current readings');
  vm.runInContext(`S.eq.signals=[
    {signal:'hpu_pressure',name:'유압 압력',unit:'bar',min:145,max:165,semantics:{}},
    {signal:'hpu_flow',name:'유압 펌프 유량',unit:'L_min',min:38,max:46,semantics:{}},
    {signal:'rt_speed',name:'회전 속도',unit:'m_min',min:50,max:100,zeroStopped:true,semantics:{}}
  ];S.sensorSnapshot=null;S.mes={at:'2026-10-20T06:13:10Z',receivedAt:'2026-10-20T06:13:11Z',operating:'stopped',alarms:[],alarmItems:[],readings:[
    {signal:'hpu_pressure',value:150,unit:'bar',observed_at:'2026-10-20T06:13:10Z'},
    {signal:'hpu_flow',value:0,unit:'L_min',observed_at:'2026-10-20T06:13:10Z'},
    {signal:'rt_speed',value:0,unit:'m_min',observed_at:'2026-10-20T06:13:10Z'}]};renderEquipmentMetrics();`,context);
  assert.match(nodes.metricsTime.textContent,/2026-10-20 15:13:10 KST/);
  assert.match(nodes.equipmentMetrics.text(),/판정 기준 확인 필요/,'stopped flow has no confirmed zero allowance');
  assert.match(nodes.equipmentMetrics.text(),/정지 중 0 허용/,'only configured stopped-zero signal is allowed');
  assert.match(nodes.equipmentMetrics.text(),/0 L\/min/,'zero remains a measurement');
  vm.runInContext("S.sensorSnapshot=null;S.mes.operating='running';renderEquipmentMetrics()",context);
  assert.match(nodes.equipmentMetrics.text(),/하한 미만/,'running zero uses operating range');
  assert.equal(vm.runInContext('stateOf(S.eq.signals[1],0)',context),'low','underlying condition logic is unchanged');
  snapshot.measurements[0].value = 154.845;
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
