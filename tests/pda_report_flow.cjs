const assert=require('node:assert/strict');
const {selectedReportPayload}=require('../shiftlink/mes/web/pda.js');

const equipment=[{equipment_id:'EQ-1',code:'HPU-01'}];
const base={ids:['EQ-1'],author:'근무자',start:'2026-10-19T08:00',end:'2026-10-19T16:00',memo:'',context:'',records:[]};
const record={type:'고장·정비',equipment:['EQ-1'],occurred_at:'2026-10-19T09:00',story:'압력 저하',causes:[],result:null,pms:null,candidate:false,capture_version:1,action_steps:[],restart_performed:false,restart_type:'unknown',outcome:'open'};

const saved=selectedReportPayload({...base,records:[record]},equipment).work_report.records[0];
assert.deepEqual(saved.action_steps,[],'unattempted work can be saved');
assert.equal(saved.outcome,'open');
const unconfirmed=selectedReportPayload({...base,records:[{...record,action_steps:[{action:'압력 확인',observed_result:'',failed:false}]}]},equipment).work_report.records[0];
assert.equal(unconfirmed.action_steps[0].observed_result,'','unconfirmed result can be saved');
assert.throws(()=>selectedReportPayload({...base,records:[{...record,occurred_at:''}]},equipment),/발생시각/);
assert.throws(()=>selectedReportPayload({...base,records:[{...record,story:' '}]},equipment),/상황/);
console.log('PASS: situation and occurrence time required, action and result optional');
