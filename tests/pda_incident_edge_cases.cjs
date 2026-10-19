const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const context=vm.createContext({URLSearchParams});
vm.runInContext(fs.readFileSync('shiftlink/mes/web/pda.js','utf8'),context);
const equipment=[{equipment_id:'EQ-A',code:'HPU-01',signals:[]},{equipment_id:'EQ-B',code:'HPU-02',signals:[]}];
function log(id,{incident='INC-A',parent=null,created='2026-10-17T12:00:00+09:00',worker='기록 근무자',steps=[],equipmentId='EQ-A',story='압력 점검',outcome='open'}={}){
 const r={type:'고장·정비',equipment:[equipmentId],story,outcome,occurred_at:'2026-10-15T09:20',action_steps:steps};
 if(parent)r.followup_from={handover_id:parent,record_index:0};
 return {kind:'work_log',handover_id:id,created_at:created,equipment_ids:[equipmentId],required_context:{author:worker,start_at:'2026-10-17T08:00',end_at:'2026-10-17T16:00'},incidents:[{record_index:0,incident_id:incident}],work_report:{records:[r],legacy_memo:'',remarks:''}};
}
function rows(logs){context.logs=logs;context.equipment=equipment;return JSON.parse(vm.runInContext('JSON.stringify(handoverIncidentRows(logs,equipment))',context));}
function step(worker,at,action='필터 점검',result='미해결'){return {worker,performed_at:at,action,observed_result:result,failed:false};}
let checks=0;
function test(name,fn){fn();checks++;console.log('PASS: '+name);}
test('4 linked handovers collapse into the latest report even with equal save timestamps',()=>{
 const logs=[log('HO-1'),log('HO-2',{parent:'HO-1'}),log('HO-3',{parent:'HO-2'}),log('HO-4',{parent:'HO-3',steps:[step('최종 근무자','2026-10-17T11:00','필터 교체','정상 압력')],outcome:'resolved'})];
 for(const input of [logs,logs.slice().reverse()]){const got=rows(input);assert.equal(got.length,1);assert.equal(got[0].h.handover_id,'HO-4');assert.equal(got[0].row.author,'최종 근무자');assert.match(got[0].row.summary,/정상 압력/);assert.equal(got[0].row.occurred,'2026-10-15\n09:20');}
});
test('separate incidents on the same equipment remain separate',()=>{
 assert.equal(rows([log('HO-A'),log('HO-B',{incident:'INC-B'})]).length,2);
});
test('multiple records in a single report use their own equipment and incident',()=>{
 const first=log('HO-MULTI'),second=log('HO-TEMP',{equipmentId:'EQ-B',incident:'INC-B',story:'온도 점검'});
 first.equipment_ids.push('EQ-B');first.work_report.records.push(second.work_report.records[0]);first.incidents.push({record_index:1,incident_id:'INC-B'});
 const got=rows([first]);assert.equal(got.length,2);assert.deepEqual(got.map(x=>x.row.equipment),['HPU-01','HPU-02']);assert.match(got[1].row.summary,/온도 점검/);
});
test('latest performed action is selected by time rather than input row order',()=>{
 const got=rows([log('HO-A',{steps:[step('늦은 조치 근무자','2026-10-17T11:00','교체','회복'),step('이른 조치 근무자','2026-10-17T10:00','청소','변화 없음')]})])[0];
 assert.equal(got.row.author,'늦은 조치 근무자');assert.match(got.row.summary,/회복/);assert.match(got.row.summary,/최근 조치: 교체/);
});
test('unknown optional action time retains the recorded sequence and legacy worker fallback',()=>{
 const got=rows([log('HO-A',{worker:'일지 근무자',steps:[step('','', '점검','미해결')]})])[0];assert.equal(got.row.author,'일지 근무자');assert.match(got.row.summary,/미해결/);
});
test('truncated history still uses the explicitly linked newest record',()=>{
 const got=rows([log('HO-31',{parent:'HO-30'}),log('HO-32',{parent:'HO-31',steps:[step('최근 근무자','2026-10-17T11:00')]})]);assert.equal(got.length,1);assert.equal(got[0].h.handover_id,'HO-32');assert.equal(got[0].row.occurred,'2026-10-15\n09:20');
});
test('plain notes without an incident are not accidentally merged',()=>{
 const a=log('HO-A'),b=log('HO-B');for(const h of [a,b]){h.incidents=[];h.work_report.records[0].type='추가 기록';}assert.equal(rows([a,b]).length,2);
});
test('grouping never mutates saved source reports or action metadata',()=>{
 const logs=[log('HO-A'),log('HO-B',{parent:'HO-A',steps:[step('근무자','2026-10-17T10:00')]})],before=JSON.stringify(logs);rows(logs);assert.equal(JSON.stringify(logs),before);
});
console.log(`PASS: ${checks} incident edge scenarios`);
