const assert = require('node:assert/strict');
const {selectedReportPayload} = require('../shiftlink/mes/web/pda.js');
const equipment=[{equipment_id:'EQ-1',code:'HPU-01'},{equipment_id:'EQ-2',code:'CL-01'}];
const draft={ids:['EQ-1','EQ-2'],author:'작업자',start:'2026-10-15T08:00',end:'2026-10-15T17:00',memo:'',context:'MES 원본',records:[]};
assert.match(selectedReportPayload(draft,equipment).memo_text,/별도 작성 내용 없음/);
const record={type:'고장·정비',equipment:['EQ-1','EQ-2'],story:'고온 경보 확인 후 냉각기 청소',causes:[{equipment:['EQ-2'],certainty:'추정',note:'오염 가능성'}],result:'다음 조 재확인',pms:'PMS-01',candidate:true};
const note=selectedReportPayload({...draft,records:[record]},equipment);
assert.match(note.memo_text,/CL-01.*추정.*오염 가능성/);
assert.match(note.memo_text,/PMS-01/);
assert.match(note.memo_text,/지식카드 후보/);
assert.deepEqual(note.work_report.records,[record]);
assert.throws(()=>selectedReportPayload({...draft,records:[{...record,equipment:[]}]},equipment),/대상 설비/);
assert.throws(()=>selectedReportPayload({...draft,records:[{...record,story:' '}]},equipment),/상황·조치/);
assert.throws(()=>selectedReportPayload({...draft,ids:['EQ-1'],records:[record]},equipment),/대상 설비/);
assert.throws(()=>selectedReportPayload({...draft,records:[{...record,story:'가'.repeat(4001)}]},equipment),/4000/);
console.log('PASS: normal shift, multi-equipment records, optional details, candidate, required fields and storage limit');

assert.throws(()=>selectedReportPayload({...draft,ids:['EQ-1'],records:[{...record,equipment:['EQ-1']}]},equipment),/원인의 대상 설비/);
