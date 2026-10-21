const assert = require('node:assert/strict');
const {reportCandidatePreview, reportPreviewLines, reportSaveWarnings, selectedReportPayload} = require('../shiftlink/mes/web/pda.js');

const record={type:'고장·정비',equipment:['EQ-1'],occurred_at:'2026-10-20T09:00',story:'압력 저하',causes:[],result:null,
  capture_version:1,action_steps:[],restart_performed:false,restart_type:'unknown',outcome:'open',
  interpretation:'밸브 응답 지연',condition_signal:'부하',condition_op:'>=',condition_value:'80',
  safety_notes:'고압 위험'};
const preview=reportCandidatePreview(record);
assert.equal(preview.length,4,'one report can show several candidate paths');
assert.match(preview[0],/이상증상 분석.*정상 상태 대비 근거/);
assert.match(preview[1],/운전 조건별 조치.*조치 단계.*조치 후 결과/);
assert.match(preview[2],/안전 조치.*정지·격리 조치.*적용 안전 기준/);
assert.match(preview[3],/고장 조치 절차.*단계별 조치·결과/);
assert.match(reportSaveWarnings(record)[0],/다음 확인/);
assert.match(reportSaveWarnings({...record,next_check_at:'다음 조 시작'})[0],/남은 문제/,
  'a time alone is not a useful handover');
assert.deepEqual(reportCandidatePreview({...record,followup_from:{handover_id:'HO-1',record_index:0}}).at(-1),
  '교대 인계 사례 · 이전 인계 기록을 포함해 서버에서 검토');

const complete={...record,interpretation_basis:'평소 대비 2초 지연',
  safety_action:'펌프 정지',safety_basis:'안전 절차 12',causes:[{equipment:['EQ-1'],certainty:'확인',note:'밸브 오염'}],
  action_steps:[{action:'밸브 청소',observed_result:'압력 회복',failed:false}],outcome:'resolved',
  normal_run_status:'no_recurrence',normal_run_minutes:30,normal_run_evidence:'30분 현장 관찰'};
assert.equal(reportSaveWarnings(complete).length,0);
assert.ok(reportCandidatePreview(complete).every(line=>line.includes('후보 초안 예상')));
assert.match(reportSaveWarnings({...complete,normal_run_evidence:''})[0],/정상 운전/);
const draft={ids:['EQ-1'],author:'작업자',start:'2026-10-20T08:00',end:'2026-10-20T16:00',memo:'',context:'',records:[record]};
assert.equal(selectedReportPayload(draft,[{equipment_id:'EQ-1',code:'HPU-01'}]).work_report.records.length,1,
  'incomplete field observations remain saveable');
const general={...record,type:'추가 기록',story:'통로 청소 완료',causes:[],
  interpretation:'',condition_signal:'',condition_op:'',condition_value:'',safety_notes:'',result:'흡착포 보충 요청'};
assert.deepEqual(reportCandidatePreview(general),[],'ordinary work does not require fault resolution evidence');
assert.deepEqual(reportPreviewLines(general),[['작업 상황·조치','통로 청소 완료'],['조치 결과·인계사항','흡착포 보충 요청']]);
assert.deepEqual(reportPreviewLines({...general,result:null}),[['작업 상황·조치','통로 청소 완료']]);
assert.equal(reportPreviewLines(complete).find(([label])=>label==='정상 운전 확인')[1],'30분 현장 관찰');
assert.ok(!reportPreviewLines(complete).some(([label])=>label==='미완료 사항·인계'));
const maintenance={...general,type:'PMS 정비',maintenance_status:'completed',outcome:'open',
  normal_run_status:'unconfirmed',normal_run_minutes:null,normal_run_evidence:'',
  action_steps:[{action:'스트레이너 청소',observed_result:'오염 제거 확인',failed:false}],candidate:false};
assert.deepEqual(reportCandidatePreview(maintenance),[],'routine maintenance does not require fault evidence');
assert.deepEqual(reportSaveWarnings(maintenance),[],'work completion does not claim equipment recovery');
assert.deepEqual(reportPreviewLines(maintenance).find(([label])=>label==='정비 작업 완료'),['정비 작업 완료','작업 완료']);
assert.deepEqual(reportPreviewLines(maintenance).find(([label])=>label==='정비 후 설비 상태'),['정비 후 설비 상태','운전 미확인']);
assert.ok(!reportPreviewLines(maintenance).some(([label])=>label==='원인·판단 근거'),'routine maintenance does not flag an absent optional cause');
assert.match(reportCandidatePreview({...maintenance,restart_performed:true}).at(-1),/재가동 절차.*보완/);
assert.match(reportCandidatePreview({...maintenance,outcome:'resolved'}).at(-1),/정상 운전/);
console.log('PASS: candidate preview and nonblocking save warnings');
