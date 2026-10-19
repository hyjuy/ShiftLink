const assert=require('node:assert/strict');
const pda=require('../shiftlink/mes/web/pda.js');
const equipment=[{equipment_id:'EQ-1',code:'HPU-01'}];
const base={ids:['EQ-1'],author:'일지 근무자',start:'2026-10-16T08:00',end:'2026-10-16T16:00',memo:'',context:'',records:[]};
const record={type:'고장·정비',equipment:['EQ-1'],story:'유압 저하',causes:[],result:null,pms:null,candidate:false,
  capture_version:1,restart_performed:false,restart_type:'unknown',outcome:'temporary',
  action_steps:[{worker:'실제 작업자',performed_at:'2026-10-16T09:10',action:'필터 점검',observed_result:'오염 확인',failed:false},
    {action:'필터 교체',observed_result:'압력 회복',failed:false},
    {action:' ',observed_result:'',failed:false}]};
const original=JSON.stringify(record);
for(const [type,label] of [['이상증상','이상 징후'],['고장·정비','고장 대응·수리'],['PMS 정비','정기 예방정비']]){
  const note=pda.selectedReportPayload({...base,records:[{...record,type}]},equipment);
  const saved=note.work_report.records[0];
  assert.equal(saved.type,type);assert.equal(saved.capture_version,1);
  assert.equal(saved.action_steps.length,2,'blank steps are excluded from saved actions');
  assert.deepEqual(saved.action_steps[0],record.action_steps[0]);
  assert.equal(saved.action_steps[1].worker,'일지 근무자');assert.equal(saved.action_steps[1].performed_at,'');
  assert.equal(saved.solution,'1. 필터 점검\n2. 필터 교체');
  assert.equal(saved.result,'압력 회복');
  for(const text of [label,'실제 작업자','필터 점검','필터 교체','압력 회복','임시 복구'])assert.ok(note.memo_text.includes(text),text);
}
assert.equal(JSON.stringify(record),original,'normalization must not mutate the editable draft');
const save=changes=>pda.selectedReportPayload({...base,records:[{...record,...changes}]},equipment).work_report.records[0];
assert.equal(save({result:'작업자가 직접 기록한 결과'}).result,'작업자가 직접 기록한 결과');
assert.equal(save({normal_run_status:'no_recurrence',normal_run_minutes:120,normal_run_evidence:'2시간 재발 없음'}).result,'2시간 재발 없음');
const restart=save({restart_performed:true,restart_type:'maintenance_restart',action_steps:[{...record.action_steps[0],failed:true}]});
assert.equal(restart.restart_performed,true);assert.equal(restart.restart_type,'maintenance_restart');assert.equal(restart.action_steps[0].failed,true);
for(const invalid of [
  {capture_version:2},{action_steps:null},{action_steps:Array(51).fill(record.action_steps[0])},
  {restart_performed:'yes'},{restart_type:'invalid'},{outcome:'invalid'},
  {action_steps:[{...record.action_steps[0],worker:42}]},
  {action_steps:[{...record.action_steps[0],performed_at:'yesterday'}]},
  {action_steps:[{...record.action_steps[0],action:'가'.repeat(4001)}]},
  {normal_run_minutes:-1},{normal_run_minutes:NaN},
  {normal_run_minutes:30,normal_run_status:'unconfirmed',normal_run_evidence:'관찰'},
  {normal_run_minutes:30,normal_run_status:'observing',normal_run_evidence:' '}
])assert.throws(()=>save(invalid),/조치|근무자|정상 운전/);
const legacy={type:'PMS 정비',equipment:['EQ-1'],story:'이전 정비 기록',causes:[],result:'점검 완료',pms:'PMS-01',candidate:false};
assert.deepEqual(pda.selectedReportPayload({...base,records:[legacy]},equipment).work_report.records,[legacy]);
console.log('PASS: record-level capture, action metadata, result priority, restart evidence, validation and immutable legacy records');
