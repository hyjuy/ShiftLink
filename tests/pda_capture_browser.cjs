const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({channel:process.env.PDA_BROWSER_CHANNEL||(process.platform==='win32'?'msedge':'chrome'),headless:true});
 try{
  for(const width of [1280,390]){
   const page=await browser.newPage({viewport:{width,height:width===1280?800:844},hasTouch:width===390});
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   const html=fs.readFileSync('shiftlink/mes/web/pda.html','utf8').replace(/<script[\s\S]*?<\/script>/g,'');
   await page.route('http://capture.test/**',r=>r.fulfill({contentType:'text/html',body:html}));await page.goto('http://capture.test/');
   const js=fs.readFileSync('shiftlink/mes/web/pda.js','utf8');
   await page.addScriptTag({content:js.slice(0,js.indexOf("if (typeof module !== 'undefined')"))});
   await page.addScriptTag({content:'function on(id,fn){document.getElementById(id)?.addEventListener("click",fn);}\n'+js.slice(js.indexOf("on('reportAdd',addReportRecord);"),js.indexOf("on('reportResumeLoad'"))});
   await page.evaluate(()=>{
    S.equipment=[{equipment_id:'EQ-1',code:'HPU-01',signals:[{signal:'pressure',name:'유압 압력',unit:'bar',min:145,max:165,semantics:{}}]},{equipment_id:'EQ-2',code:'CL-02',signals:[]}];
    S.reportSelected=['EQ-1','EQ-2'];S.reportRecords=[];S.reportDraftLoaded=true;
    S.snapshot={simulated_at:'2026-10-21T09:00:00',equipment:[],measurements:[{equipment_id:'EQ-1',signal:'pressure',value:120,unit:'bar',quality:'good',observed_at:'2026-10-21T09:00:00'}]};
    $('reportAuthor').value='테스트 근무자';$('reportStart').value='2026-10-21T08:00';$('reportEnd').value='2026-10-21T16:00';
    show('reportWrite');renderReportRecords();
   });
   assert.equal(await page.locator('#reportAdd').isDisabled(),true);
   await page.locator('#reportRecordEquipment').selectOption('EQ-1');assert.equal(await page.locator('.record').count(),0);
   await page.locator('#reportAdd').click();assert.deepEqual(await page.evaluate(()=>S.reportRecords[0].equipment),['EQ-1']);
   assert.equal(await page.locator('[data-key="type"]').inputValue(),'추가 기록');
   assert.equal(await page.locator('[data-key="operating_context"]').count(),0);
   await page.locator('[data-occurrence-part="date"]').fill('2026-10-21');await page.locator('[data-occurrence-part="time"]').fill('09:00');
   assert.equal(await page.evaluate(()=>S.reportRecords[0].occurred_at),'2026-10-21T09:00');
   await page.locator('[data-key="type"]').selectOption('이상증상');
   const analysis=page.locator('details').filter({has:page.locator('[data-key="interpretation"]')});
   await analysis.locator(':scope>summary').click();await page.locator('[data-key="interpretation"]').fill('압력 저하');await page.locator('[data-key="interpretation_basis"]').fill('평상시 운전값과 비교');
   await page.locator('[data-key="story"]').fill('기동 중 유압 저하');await page.locator('[data-key="note"]').fill('필터 오염 추정');
   await page.locator('[data-key="sensor_ref"]').selectOption(JSON.stringify({equipment_id:'EQ-1',signal:'pressure'}));
   assert.equal(await page.locator('.cause-sensor-value').inputValue(),'120.00 bar');
   await page.evaluate(()=>{S.snapshot.measurements[0].value=155;refreshReportCauseSensors();});
   assert.equal(await page.locator('.cause-sensor-value').inputValue(),'120.00 bar','cause evidence remains frozen');
   await page.locator('[data-key="type"]').selectOption('고장·정비');
   await page.locator('[data-action="step"]').click();await page.locator('[data-key="action"]').fill('전원 차단 후 필터 교체');await page.locator('[data-key="observed_result"]').fill('압력 정상 복귀');
   await page.locator('[data-key="operating_context"]').fill('기동 직후 발생');
   await page.locator('[data-key="outcome"]').selectOption('resolved');await page.locator('[data-key="normal_run_status"]').selectOption('no_recurrence');
   await page.locator('[data-key="normal_run_minutes"]').fill('30');await page.locator('[data-key="normal_run_evidence"]').fill('09:10~09:40 운전 확인');
   const safety=page.locator('details').filter({has:page.locator('[data-key="safety_action"]')});await safety.locator(':scope>summary').click();
   await page.locator('[data-key="safety_notes"]').fill('잔압 분출 위험');await page.locator('.report-safety-source').focus();await page.locator('.report-safety-source').selectOption('0');
   assert.equal(await page.locator('[data-key="safety_action"]').inputValue(),'전원 차단 후 필터 교체');
   const help=safety.locator('.report-help-button').first();await help.scrollIntoViewIfNeeded();
   if(width===390)await help.tap();else await help.hover();
   assert.equal(await page.locator('#reportHelpMemo').isVisible(),true);
   await page.keyboard.press('Escape');assert.equal(await page.locator('#reportHelpMemo').isVisible(),false);
   const geometry=await page.locator('#reportRecords').evaluate(root=>{
    const rows=[...root.querySelectorAll('tr')],buttons=[...root.querySelectorAll('.report-help-button')];const before=rows.map(r=>r.getBoundingClientRect().height);
    buttons.forEach(b=>b.style.display='none');const after=rows.map(r=>r.getBoundingClientRect().height);buttons.forEach(b=>b.style.removeProperty('display'));
    const summaries=[...root.querySelectorAll('.record>table>tbody>tr>td>details>summary')];
    return {heightChange:Math.max(...before.map((v,i)=>Math.abs(v-after[i]))),starts:summaries.map(s=>s.getBoundingClientRect().left)};
   });
   assert.equal(geometry.heightChange,0,'help buttons do not grow rows');assert.ok(Math.max(...geometry.starts)-Math.min(...geometry.starts)<=1,'fold headings align');
   const note=await page.evaluate(()=>selectedReportPayload(reportDraft(),S.equipment));
   assert.equal(note.work_report.records[0].occurred_at,'2026-10-21T09:00');assert.equal(note.work_report.records[0].causes[0].sensor_reading.value,120);
   assert.equal(note.work_report.records[0].operating_context,'기동 직후 발생');assert.match(note.work_report.records[0].solution,/필터 교체/);
   await page.locator('[data-key="type"]').selectOption('PMS 정비');await page.locator('[data-key="maintenance_status"]').selectOption('completed');await page.locator('[data-key="outcome"]').selectOption('open');
   assert.equal(await page.locator('[data-key="maintenance_status"]').inputValue(),'completed');assert.equal(await page.locator('[data-key="outcome"]').inputValue(),'open','work completion does not imply normal operation');
   await page.locator('[data-action="remove-cause"]').click();await page.locator('#reportDeleteConfirm [value="cancel"]').click();await page.waitForFunction(()=>!document.getElementById('reportDeleteConfirm').open);assert.equal(await page.evaluate(()=>S.reportRecords[0].causes.length),1);
   await page.locator('[data-action="remove-cause"]').click();await page.locator('#reportDeleteConfirm [value="delete"]').click();await page.waitForFunction(()=>S.reportRecords[0].causes.length===0);assert.equal(await page.evaluate(()=>S.reportRecords[0].causes.length),0);
   await page.locator('[data-action="remove"]').click();await page.locator('#reportDeleteConfirm [value="delete"]').click();await page.waitForFunction(()=>S.reportRecords.length===0);assert.equal(await page.locator('.record').count(),0);
   assert.equal(await page.evaluate(()=>JSON.parse(localStorage.getItem(REPORT_DRAFT_KEY)).records.length),0);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);assert.deepEqual(errors,[]);
   fs.mkdirSync('artifacts/pda-capture',{recursive:true});await page.screenshot({path:`artifacts/pda-capture/checked-${width}.png`});await page.close();
  }
  console.log('PASS: four worklog types, split date/time, frozen MES evidence, safety reuse, help geometry, deletion and PDA/mobile');
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1;});
