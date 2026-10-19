const assert=require('node:assert/strict');
const {selectedReportPayload}=require('../shiftlink/mes/web/pda.js');
const equipment=[{equipment_id:'EQ-1',code:'HPU-01'}];
const record={type:'이상증상',equipment:['EQ-1'],story:'유량 저하',causes:[],result:'유량 회복',pms:null,candidate:false,
  solution:'1. 필터 확인\n2. 청소',outcome:'temporary',operating_context:'정비 후 기동 중',
  failed_attempts:'재기동 실패',safety_notes:'정지·격리',follow_up:'30분 관찰',references:'매뉴얼 4쪽',mes_context:'관측 시각 · 저장 당시'};
const draft={ids:['EQ-1'],author:'작업자',start:'2026-10-16T08:00',end:'2026-10-16T16:00',memo:'',context:'',records:[record]};
const note=selectedReportPayload(draft,equipment);
assert.match(note.memo_text,/이상 징후/);
for(const [type,label] of [['고장·정비','고장 대응·수리'],['PMS 정비','정기 예방정비']]){
  const typed=selectedReportPayload({...draft,records:[{...record,type}]},equipment);
  assert.ok(typed.memo_text.includes(label));
  assert.equal(typed.work_report.records[0].type,type,'existing storage values remain compatible');
}
for(const text of ['필터 확인','임시 복구','정비 후 기동 중','재기동 실패','정지·격리','30분 관찰','매뉴얼 4쪽'])assert.ok(note.memo_text.includes(text),text);
assert.deepEqual(note.work_report.records,[record]);
const maintenance={...record,type:'PMS 정비',maintenance_items:'필터 오염·체결 상태 점검',parts_used:'필터 F01 1개',next_maintenance:'다음 정기점검 시 재확인'};
const planned=selectedReportPayload({...draft,records:[maintenance]},equipment);
for(const text of ['필터 오염·체결 상태 점검','필터 F01 1개','다음 정기점검 시 재확인'])assert.ok(planned.memo_text.includes(text));
assert.throws(()=>selectedReportPayload({...draft,records:[{...record,outcome:'fake'}]},equipment),/조치 결과/);
assert.throws(()=>selectedReportPayload({...draft,records:[{...record,safety_notes:42}]},equipment),/안전/);
assert.throws(()=>selectedReportPayload({...draft,records:[{...record,follow_up:'가'.repeat(4001)}]},equipment),/4000/);
const legacy={type:'고장·정비',equipment:['EQ-1'],story:'이전 원문',causes:[],result:null,pms:null,candidate:false};
assert.deepEqual(selectedReportPayload({...draft,records:[legacy]},equipment).work_report.records,[legacy]);
const observation={...record,normal_run_status:'no_recurrence',normal_run_minutes:120,normal_run_evidence:'10:00~12:00 연속 운전 확인'};
assert.match(selectedReportPayload({...draft,records:[observation]},equipment).memo_text,/120분/);
for(const invalid of [{normal_run_minutes:-1},{normal_run_minutes:NaN},{normal_run_status:'unconfirmed'},{normal_run_evidence:' '}]){
  assert.throws(()=>selectedReportPayload({...draft,records:[{...observation,...invalid}]},equipment),/정상 운전/);
}
console.log('PASS: abnormal review context, result labels, legacy records and validation');
