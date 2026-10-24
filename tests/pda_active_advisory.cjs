/* Actual PDA JS functions, synthetic DOM; no kiosk or real vibration. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element {
  constructor(){this.children=[];this.parts={};this.textContent='';this.dataset={};this.hidden=false;this.classList={toggle(){},remove(){},add(){}};}
  set innerHTML(v){this.children=[];this.parts={};}
  querySelector(s){return this.parts[s] ||= new Element();}
  appendChild(c){this.children.push(c);return c;} append(...c){this.children.push(...c);}
  addEventListener(){} setAttribute(k,v){this[k]=v;}
}
const c=vm.createContext({URLSearchParams});vm.runInContext(fs.readFileSync(require.resolve('../shiftlink/mes/web/pda.js'),'utf8'),c);
const nodes={},vibrations=[];
c.document={getElementById:id=>nodes[id] ||= new Element(),createElement:()=>new Element(),querySelectorAll:()=>[],addEventListener(){}};
const source=fs.readFileSync(require.resolve('../shiftlink/mes/web/pda.js'),'utf8');
vm.runInContext(source.slice(source.indexOf('function faultsFrom(snap)'),source.indexOf('function renderDash()')),c);
c.navigator={vibrate:p=>vibrations.push(p)};c.setTimeout=()=>0;c.clearTimeout=()=>{};
vm.runInContext(`S.equipment=[{equipment_id:'E',code:'HPU-01',signals:[]}];S.alertAck={};
S.snapshot={run_id:'r',config_id:'c',sequence:160,line_mode:'running',equipment:[{equipment_id:'E',operating_state:'running'}],measurements:[],active_alarms:[],
ai_insights:{status:'ready',run_id:'r',config_id:'c',sequence:160,operational_notifications:false,items:[{equipment_id:'E',event_id:'r:105:E',sequence:105,observed_at:'2026-10-24T10:00:00Z',state:'active',signals:[]}]}};
renderAlert(faultsFrom(S.snapshot));renderNotifyPanel();`,c);
const rows=()=>nodes.notifyPanel.querySelector('.np-list').children.filter(r=>r.dataset.equipmentId==='E');
assert.equal(rows().length,1);assert.equal(vibrations.length,0);
for(let i=161;i<220;i++)vm.runInContext(`S.snapshot.sequence=${i};S.snapshot.ai_insights.sequence=${i};renderAlert(faultsFrom(S.snapshot));renderNotifyPanel();`,c);
assert.equal(rows().length,1);assert.equal(vibrations.length,0,'refresh must stay silent');
vm.runInContext(`S.snapshot.active_alarms=[{equipment_id:'E',code:'LEGACY',label:'기존 경보'}];renderAlert(faultsFrom(S.snapshot));renderNotifyPanel();`,c);
assert.equal(rows().length,1,'legacy and AI must share one equipment row');assert.equal(vibrations.length,1,'legacy first alert keeps its own haptic');
vm.runInContext(`S.alertAck.E=ackKey(S.faults[0]);S.snapshot.ai_insights.items[0].state='before_stop';S.snapshot.ai_insights.status='stopped';renderAlert(faultsFrom(S.snapshot));renderNotifyPanel();renderAlert(faultsFrom(S.snapshot));`,c);
assert.equal(rows().length,1);assert.equal(vibrations.length,1,'AI stop/history must not revibrate acknowledged legacy alarm');
vm.runInContext(`S.snapshot.active_alarms=[];S.snapshot.ai_insights={...S.snapshot.ai_insights,status:'ready',items:[]};renderAlert(faultsFrom(S.snapshot));renderNotifyPanel();`,c);
assert.equal(rows().length,0);assert.equal(vibrations.length,1);
console.log('PASS active AI refresh, recovery, same alarm row, legacy haptic preserved, AI repeat haptics 0');
