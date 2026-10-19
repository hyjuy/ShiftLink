const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const pda=require('../shiftlink/mes/web/pda.js');
// Exercise browser date/shift functions without adding test-only exports.
const context=vm.createContext({URLSearchParams});
vm.runInContext(fs.readFileSync(require.resolve('../shiftlink/mes/web/pda.js'),'utf8'),context);
const nodes={reportWorkDate:{value:''},reportShift:{value:''},reportStart:{value:''},reportEnd:{value:''}};
context.document={getElementById:id=>nodes[id]};
for(const [time,date,code] of [
  ['2026-10-14T14:59:00Z','2026-10-14','B'],
  ['2026-10-14T15:00:00Z','2026-10-15','C'],
  ['2026-10-14T22:59:00Z','2026-10-15','C'],
  ['2026-10-14T23:00:00Z','2026-10-15','A'],
  ['2026-10-15T06:59:00Z','2026-10-15','A'],
  ['2026-10-15T07:00:00Z','2026-10-15','B']
])assert.deepEqual(JSON.parse(JSON.stringify(vm.runInContext(`shiftAt(new Date('${time}'))`,context))),{date,code});
for(const [date,code,start,end] of [
  ['2026-10-15','A','2026-10-15T08:00','2026-10-15T16:00'],
  ['2026-10-15','C','2026-10-15T00:00','2026-10-15T08:00'],
  ['2028-02-28','B','2028-02-28T16:00','2028-02-29T00:00'],
  ['2028-02-29','B','2028-02-29T16:00','2028-03-01T00:00'],
  ['2026-12-31','B','2026-12-31T16:00','2027-01-01T00:00']
]){
  nodes.reportWorkDate.value=date;nodes.reportShift.value=code;
  vm.runInContext('syncReportShift()',context);
  assert.equal(nodes.reportStart.value,start);assert.equal(nodes.reportEnd.value,end);
}
for(const [date,code] of [['','A'],['2026-10-15','pending']]){
  nodes.reportWorkDate.value=date;nodes.reportShift.value=code;
  const previous=[nodes.reportStart.value,nodes.reportEnd.value];
  vm.runInContext('syncReportShift()',context);
  assert.deepEqual([nodes.reportStart.value,nodes.reportEnd.value],previous);
}
const equipment=[{equipment_id:'EQ-1',code:'HPU-01'}];
const draft={ids:['EQ-1'],author:' 작업자 ',start:'2026-10-15T08:00',end:'2026-10-15T16:00',memo:'',context:'',records:[]};
const note=pda.selectedReportPayload(draft,equipment);
assert.equal(note.memo_text,'별도 작성 내용 없음');assert.deepEqual(note.work_report.records,[]);
assert.equal(note.required_context.author,'작업자');assert.equal(note.required_context.start_at,draft.start);
assert.equal(note.required_context.end_at,draft.end);
assert.equal(pda.selectedReportPayload({...draft,memo:'다음 근무 압력 재확인'},equipment).work_report.legacy_memo,'다음 근무 압력 재확인');
for(const invalid of [{ids:[]},{author:' '},{start:''},{end:'not-a-date'},{end:'2026-10-15T07:59'}]){
  assert.throws(()=>pda.selectedReportPayload({...draft,...invalid},equipment),/대상 장비|근무자|근무 시작·종료/);
}
console.log('PASS: Korea shift boundaries, leap-day/year rollover, pending shift preservation, empty shift, memo and required inputs');
