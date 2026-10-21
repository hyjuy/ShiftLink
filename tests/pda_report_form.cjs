const assert = require('node:assert/strict');
const {selectedReportPayload,reportArchiveText,reportCandidateLines,reportPreviewLines} = require('../shiftlink/mes/web/pda.js');
const equipment=[{equipment_id:'EQ-1',code:'HPU-01'},{equipment_id:'EQ-2',code:'CL-01'}];
const draft={ids:['EQ-1','EQ-2'],author:'작업자',start:'2026-10-15T08:00',end:'2026-10-15T17:00',memo:'',context:'MES 원본',records:[]};
assert.match(selectedReportPayload(draft,equipment).memo_text,/별도 작성 내용 없음/);
const record={type:'고장·정비',equipment:['EQ-1','EQ-2'],story:'고온 경보 확인 후 냉각기 청소',causes:[{equipment:['EQ-2'],certainty:'추정',note:'오염 가능성'}],result:'다음 조 재확인',pms:'PMS-01',candidate:true};
const note=selectedReportPayload({...draft,records:[record]},equipment);
assert.match(note.memo_text,/CL-01.*고온 경보 확인 후 냉각기 청소/);
assert.deepEqual(note.work_report.records,[record]);
const longRecord={...record,story:'압력 저하',interpretation:'해석'.repeat(1200)};
const longNote=selectedReportPayload({...draft,records:[longRecord,longRecord]},equipment);
assert.ok(longNote.memo_text.length<=4000);
assert.equal(longNote.work_report.records[1].interpretation,longRecord.interpretation);
const archive=reportArchiveText({...longNote,memo_text:'이전 상세 메모',required_context:longNote.required_context},equipment);
assert.match(archive,/징후 판단: 해석/);
assert.doesNotMatch(archive,/이전 상세 메모/);
const older=reportArchiveText({...note,memo_text:'이전 상세 메모',required_context:note.required_context,
  work_report:{...note.work_report,records:[{...record,action_steps:[{action:'조치'}],capture_version:1}]}},equipment);
assert.match(older,/고온 경보 확인 후 냉각기 청소/);
assert.doesNotMatch(older,/이전 상세 메모/);
assert.deepEqual(reportCandidateLines([
  {record_index:0,kind:'T1',draft_id:'D-1',reason:'pending_review'},
  {record_index:0,kind:'T5',reason:'insufficient_capture'},
  {record_index:1,kind:'T4',draft_id:'D-4'}],0),
['이상증상 분석 · 후보 검토 대기','안전 조치 · 원인·조치 결과·정상 운전 근거 보완 필요']);
assert.deepEqual(reportCandidateLines([{record_index:0,kind:'T1',reason:'insufficient_t1'},
  {record_index:0,kind:'T2',reason:'insufficient_t2'},
  {record_index:0,kind:'T5',reason:'insufficient_safety'}],0),
  ['이상증상 분석 · 징후 판단·정상 상태 대비 근거 보완 필요','운전 조건별 조치 · 운전 조건·수행 조치·확인 결과 보완 필요',
    '안전 조치 · 위험 요인·정지·격리 조치·적용 안전 기준 보완 필요']);
assert.deepEqual(reportPreviewLines({...record,interpretation:'진동 증가',interpretation_basis:'평소와 비교'})
  .filter(([label])=>['징후 판단','정상 상태 대비 근거'].includes(label)),
  [['징후 판단','진동 증가'],['정상 상태 대비 근거','평소와 비교']]);
const withSensor={...record,causes:[{...record.causes[0],sensor_ref:{equipment_id:'EQ-2',signal:'pressure'},
  sensor_reading:{value:154.8,unit:'bar',observed_at:'2026-10-20T09:00:00+09:00'}}]};
assert.deepEqual(selectedReportPayload({...draft,records:[withSensor]},equipment).work_report.records[0].causes[0].sensor_reading,
  withSensor.causes[0].sensor_reading);
assert.match(reportPreviewLines(withSensor).find(([label])=>label==='원인·판단 근거')[1],
  /pressure · 154\.80 bar · 측정시각 2026-10-20T09:00:00\+09:00/);
assert.throws(()=>selectedReportPayload({...draft,records:[{...record,equipment:[]}]},equipment),/대상 설비/);
assert.throws(()=>selectedReportPayload({...draft,records:[{...record,story:' '}]},equipment),/상황/);
assert.throws(()=>selectedReportPayload({...draft,ids:['EQ-1'],records:[record]},equipment),/대상 설비/);
assert.throws(()=>selectedReportPayload({...draft,records:[{...record,story:'가'.repeat(4001)}]},equipment),/4000/);
console.log('PASS: normal shift, multi-equipment records, optional details, candidate, required fields and storage limit');

assert.throws(()=>selectedReportPayload({...draft,ids:['EQ-1'],records:[{...record,equipment:['EQ-1']}]},equipment),/원인의 대상 설비/);

const withSymptom={...record,symptom:'고온 경보가 반복됨'};
assert.equal(selectedReportPayload({...draft,records:[withSymptom]},equipment).work_report.records[0].symptom,'고온 경보가 반복됨');
assert.match(reportArchiveText(selectedReportPayload({...draft,records:[withSymptom]},equipment),equipment),/발생 현상: 고온 경보가 반복됨/);
assert.throws(()=>selectedReportPayload({...draft,records:[{...record,symptom:'가'.repeat(4001)}]},equipment),/발생 현상.*4000/);
