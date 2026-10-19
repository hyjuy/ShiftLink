const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const context=vm.createContext({URLSearchParams});
vm.runInContext(fs.readFileSync('shiftlink/mes/web/pda.js','utf8'),context);
context.equipment=[{equipment_id:'EQ-1',code:'HPU-01'}];
const make=(id,day,author,parent)=>({kind:'work_log',handover_id:id,created_at:`2026-10-${day}T10:00:00+09:00`,equipment_ids:['EQ-1'],
 required_context:{author,start_at:`2026-10-${day}T08:00`,end_at:`2026-10-${day}T16:00`},
 incidents:[{record_index:0,incident_id:'INC-ONE'}],work_report:{records:[{type:'고장·정비',equipment:['EQ-1'],story:`기록 ${id}`,occurred_at:'2026-10-15T09:10',outcome:parent?'resolved':'open',
 ...(parent?{incident_id:'INC-ONE',followup_from:{handover_id:parent,record_index:0}}:{}),
 action_steps:[{worker:author,performed_at:`2026-10-${day}T09:30`,action:`조치 ${id}`,observed_result:`결과 ${id}`,failed:false}]}]}});
const first=make('FIRST','15','첫 근무자'),middle=make('MIDDLE','16','둘째 근무자','FIRST'),last=make('LAST','17','일지 근무자','MIDDLE');
last.work_report.records[0].action_steps[0].worker='마지막 조치 근무자';
context.reports=[first,last,middle];
const read=()=>JSON.parse(JSON.stringify(vm.runInContext('handoverIncidentRows(reports,equipment)',context)));
let rows=read();
assert.equal(rows.length,1);
assert.equal(rows[0].h.handover_id,'LAST');
assert.equal(rows[0].row.author,'마지막 조치 근무자');
assert.equal(rows[0].row.date,'2026-10-17');
assert.equal(rows[0].row.occurred,'2026-10-15\n09:10');
assert.match(rows[0].row.summary,/해결/);assert.match(rows[0].row.summary,/결과 LAST/);assert.match(rows[0].row.summary,/조치 LAST/);
last.work_report.records[0].action_steps.push({worker:'이른 시각 근무자',performed_at:'2026-10-17T08:30',action:'먼저 한 점검',observed_result:'점검 중',failed:false});
assert.equal(read()[0].row.author,'마지막 조치 근무자','actual action time wins over entry order when all times are known');
const observation=make('OBSERVE','18','관찰 기록 근무자','LAST');
observation.work_report.records[0].action_steps=[];
observation.work_report.records[0].result='정상 운전 추가 관찰 완료';
context.reports=[first,middle,last,observation];
assert.equal(read()[0].h.handover_id,'OBSERVE');
assert.equal(read()[0].row.author,'마지막 조치 근무자','observation-only followup keeps the actual last action worker');
assert.match(read()[0].row.summary,/정상 운전 추가 관찰 완료/);
assert.match(read()[0].row.summary,/조치 LAST/);
assert.equal(first.required_context.author,'첫 근무자','originals stay unchanged');
// Parent links win when uploads share a timestamp and IDs are not chronological.
context.reports=[last,middle,first].map(h=>({...h,created_at:'2026-10-17T10:00:00Z'}));
assert.equal(read()[0].h.handover_id,'LAST');
// Pending/offline root payloads may not include the returned incident links.
context.reports=[{...first,incidents:[]},middle,last];assert.equal(read().length,1);
// Same equipment is not enough to combine two separate incidents.
const other=make('OTHER','17','다른 사건 근무자');other.incidents=[{record_index:0,incident_id:'INC-TWO'}];
context.reports=[first,middle,last,other];assert.equal(read().length,2);
// Unlinked notes remain separate; missing timestamps and legacy records remain viewable.
context.reports=[{...first,incidents:[]},other,{handover_id:'LEGACY',memo_text:'별도 인계',open_items:[{text:'기존 특이사항'}]}];assert.equal(read().length,3);
console.log('PASS: one latest row per incident, latest action worker/result, original discovery, tied timestamps, offline root and separate incidents');
