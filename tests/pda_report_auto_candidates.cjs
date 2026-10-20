const assert = require('node:assert/strict');
const {selectedReportPayload} = require('../shiftlink/mes/web/pda.js');

const equipment = [{equipment_id:'EQ-1',code:'HPU-01'}];
const record = {type:'이상증상',equipment:['EQ-1'],occurred_at:'2026-10-19T09:00',story:'평소와 다른 진동',causes:[],
  result:null,pms:null,candidate:false,capture_version:1,action_steps:[],
  restart_performed:false,restart_type:'unknown',outcome:'open',
  interpretation:'윤활 불량의 징후일 수 있음',interpretation_basis:'평소 진동과 비교',
  condition_signal:'운전 모드',condition_op:'==',condition_value:'기동 중',
  condition_method:'저속에서 먼저 확인',condition_result:'진동 감소',
  safety_notes:'커버가 열린 상태',safety_action:'작업 중지',safety_basis:'안전 절차서 4절'};
const draft = {ids:['EQ-1'],author:'근무자',start:'2026-10-19T08:00',end:'2026-10-19T16:00',
  memo:'',context:'',records:[record]};
const saved = selectedReportPayload(draft,equipment).work_report.records[0];
assert.equal(saved.auto_candidate,true);
for(const field of ['interpretation','condition_method','safety_action','safety_basis'])
  assert.equal(saved[field],record[field]);
assert.equal(saved.candidate,false,'legacy manual choice stays in source record');
console.log('PASS: structured work report sends automatic candidate review and source facts');
