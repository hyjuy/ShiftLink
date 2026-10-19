const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const bin = process.env.AGENT_BROWSER_BIN || 'agent-browser';
const url = process.env.PDA_URL || 'http://127.0.0.1:8767/pda.html';
assert.ok(['127.0.0.1','localhost'].includes(new URL(url).hostname),'Only run this writing test against a local test server');
const env = {...process.env}; delete env.PDA_TEST_PASSWORD;
const session = 'pda-handover-20261016';
function run(...args) {
  // DOM activation uses the real handlers and avoids headless native-click backend differences.
  if(args[0]==='click' || args[0]==='check') {
    return evaluate(`(()=>{const el=document.querySelector(${JSON.stringify(args[1])});if(!el)throw Error('Missing test control');${args[0]==='check'?'if(!el.checked)':''}el.click();return true;})()`);
  }
  return execFileSync(bin,['--session',session,...args],{encoding:'utf8',env,timeout:30000,windowsHide:true}).trim();
}
function evaluate(source) {
  const output = JSON.parse(run('eval','-b',Buffer.from(source).toString('base64'),'--json'));
  assert.equal(output.success,true,output.error); return output.data.result;
}
const artifact = path.resolve('artifacts/pda-handover-notes'); fs.mkdirSync(artifact,{recursive:true});
run('open',url); run('wait','#s-account.on, #s-home.on');
assert.ok(process.env.PDA_TEST_ID && process.env.PDA_TEST_PASSWORD,'Supply the local test account through environment variables');
if(evaluate('S.screen')==='account') {
  run('fill','#employeeId',process.env.PDA_TEST_ID); run('fill','#employeePassword',process.env.PDA_TEST_PASSWORD);
  evaluate(`document.getElementById('accountForm').requestSubmit()`); run('wait','#s-home.on');
}
assert.equal(evaluate('S.operator.id'),process.env.PDA_TEST_ID);

// Save one ordinary report using the actual form and confirmation dialog.
run('click','#toReport'); run('check','#reportEquipment tr:nth-child(1) input[type=checkbox]');
run('click','#reportWrite'); run('fill','#reportWorkDate','2026-10-16'); run('select','#reportShift','A');
run('click','#reportSave'); run('click','#reportSaveYes'); run('wait','#s-home.on');
// Enter an occurrence time in the real form and verify it survives the save.
run('click','#toReport'); run('check','#reportEquipment tr:nth-child(1) input[type=checkbox]');
run('click','#reportWrite'); run('click','#reportAdd');
run('fill','#reportRecords input[data-key=occurred_at]','2026-10-16T10:05');
run('fill','#reportRecords textarea[data-key=story]','교대 전 누유 흔적 확인 · 다음 근무에서 재점검');
evaluate(`['occurred_at','story'].forEach(key=>document.querySelector('#reportRecords [data-key='+key+']').dispatchEvent(new Event('input',{bubbles:true})))`);
assert.equal(evaluate('reportDraft().records[0].occurred_at'),'2026-10-16T10:05');
run('click','#reportSave');run('click','#reportSaveYes');run('wait','#s-home.on');
assert.ok(evaluate(`S.savedHandovers.some(h=>(h.work_report?.records||[]).some(r=>r.occurred_at==='2026-10-16T10:05'))`));

// Synthetic records exercise multiple equipment, overnight shifts, long text and literal HTML.
evaluate(`(async()=>{
  const ids=S.equipment.slice(0,2).map(eq=>eq.equipment_id);
  const draft={ids,author:'로컬 테스트 · 정비',start:'2026-10-17T16:00',end:'2026-10-18T00:00',memo:'',context:'로컬 화면 검증용 가상 일지',records:[
    {type:'고장·정비',equipment:[ids[0]],occurred_at:'2026-10-17T18:20',story:'유압 저하 확인 후 필터 점검',causes:[{equipment:[ids[0]],certainty:'추정',note:'필터 오염 여부 확인 필요'}],result:'다음 근무에서 압력 재확인',pms:null,candidate:false},
    {type:'PMS 정비',equipment:[ids[1]],occurred_at:'2026-10-17T17:30',story:'구동부 윤활 및 체결 상태 점검',causes:[],result:'윤활 완료 · 이음 여부 재확인',pms:'LOCAL-PMS-01',candidate:false}]};
  const payload={...selectedReportPayload(draft,S.equipment),handover_id:'LOCAL-TABLE-'+Date.now()};
  const res=await api('/api/work-reports',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  if(!res.ok)throw Error(await res.text());
  const long={...draft,author:'로컬 테스트 · 장문',start:'2026-10-15T08:00',end:'2026-10-15T16:00',records:[{...draft.records[0],occurred_at:'2026-10-15T10:30',story:'<img src=x onerror=alert(1)> '+('긴 상황·조치 기록 '.repeat(25)),result:'누락 없이 상세에서 원문 확인'}]};
  const second=await api('/api/work-reports',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...selectedReportPayload(long,S.equipment),handover_id:'LOCAL-LONG-'+Date.now()})});
  if(!second.ok)throw Error(await second.text());
  await refreshSavedHandovers();return true;
})()`);
run('click','#toHandoverHome'); run('wait','#s-handover.on');
const headers = evaluate(`Array.from(document.querySelectorAll('.handover-table thead th'),el=>el.textContent)`);
assert.deepEqual(headers,['설비명','특이사항','발생시각','근무일','근무조','근무자','상세보기']);
assert.equal(evaluate(`document.querySelectorAll('.handover-table tbody tr').length`),evaluate('handoverIncidentRows(allHandovers(),S.equipment).length'));
assert.ok(evaluate(`allHandovers().some(h=>h.kind==='work_log'&&!hasHandoverNotes(h))`),'ordinary reports remain saved');
assert.equal(evaluate(`document.getElementById('hoPane').textContent.includes('별도 작성 내용 없음')`),false);
const first = evaluate(`document.querySelector('.handover-table tbody tr').textContent`);
assert.match(first,/2026-10-17/); assert.match(first,/B조/); assert.match(first,/18:20/); assert.match(first,/유압 저하/);
assert.equal(evaluate(`document.querySelectorAll('#hoPane img').length`),0,'stored HTML is text only');
assert.ok(evaluate(`document.querySelector('#hoPane').textContent.includes('<img src=x onerror=alert(1)>')`));

const checks=[];
for(const width of [1280,768,375]) {
  run('set','viewport',String(width),'800');
  const metrics=evaluate(`(()=>{const el=document.querySelector('.handover-table-scroll'),r=el.getBoundingClientRect();return {pageWidth:document.documentElement.scrollWidth,viewport:innerWidth,tableWidth:el.scrollWidth,visibleWidth:el.clientWidth,right:r.right};})()`);
  assert.equal(metrics.pageWidth,width); assert.ok(metrics.right<=width);
  if(width<1060) assert.ok(metrics.tableWidth>metrics.visibleWidth);
  run('screenshot',path.join(artifact,'handover-'+width+'.png')); checks.push({width,...metrics});
}
evaluate(`document.querySelector('.handover-table-scroll').scrollLeft=10000`);
run('click','.handover-table tbody tr:first-child button'); run('wait','#s-dutyDetail.on');
assert.equal(evaluate(`document.getElementById('dutyTitle').textContent`),'근무일지');
assert.ok(evaluate(`document.getElementById('dutyPane').textContent.includes('LOCAL-PMS-01')`),'detail keeps complete original data');
assert.equal(evaluate(`document.querySelectorAll('#dutyPane .duty-report').length`),1);
assert.equal(evaluate(`document.querySelectorAll('#dutyPane .worklog-record').length`),2);
assert.equal(evaluate(`document.querySelectorAll('#dutyPane input,#dutyPane textarea,#dutyPane .timeline').length`),0,'saved report is a read-only form, without the generic timeline');
assert.ok(evaluate(`document.querySelector('#dutyPane .worklog-notes').textContent.includes('유압 저하 확인 후 필터 점검')`));
assert.equal(evaluate(`document.querySelector('#dutyPane .worklog-sensors').open`),false,'saved sensor evidence starts collapsed');
run('screenshot',path.join(artifact,'detail-375.png'));
run('click','#navigationBack'); run('wait','#s-handover.on');
assert.ok(evaluate(`document.querySelectorAll('.handover-table tbody tr').length>0`));

// The detail action stays a focusable native button; an empty list has guidance.
run('set','viewport','1280','800'); evaluate(`document.querySelector('.handover-table-scroll').scrollLeft=0;document.querySelector('.handover-table tbody tr button').focus()`);
assert.equal(evaluate(`document.activeElement.tagName`),'BUTTON');
evaluate(`window.tableTestSaved=S.savedHandovers;window.tableTestStatic=S.handovers;S.savedHandovers=[];S.handovers=[];openHandover()`);
assert.equal(evaluate(`document.querySelectorAll('.handover-table').length`),0);
assert.match(evaluate(`document.getElementById('hoPane').textContent`),/인계 사항/);
run('screenshot',path.join(artifact,'empty-1280.png'));
evaluate(`S.savedHandovers=window.tableTestSaved;S.handovers=window.tableTestStatic;openHandover()`);
run('screenshot',path.join(artifact,'handover-1280.png'));
const errors=JSON.parse(run('errors','--json')); assert.deepEqual(errors.data.errors,[]);
fs.writeFileSync(path.join(artifact,'browser-results.json'),JSON.stringify({url,checks,passed:true,errors:[]},null,2));
console.log('PASS: local account login, form save, work-log columns, sort, multi-equipment, overnight shift, literal HTML, responsive table, detail/back, focusable action, empty state, zero browser errors');
