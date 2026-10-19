const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const html=fs.readFileSync('shiftlink/mes/web/pda.html','utf8').replace(/<script[\s\S]*?<\/script>/g,'');
  await page.route('http://remove.test/**',r=>r.fulfill({contentType:'text/html',body:html}));await page.goto('http://remove.test/');
  const js=fs.readFileSync('shiftlink/mes/web/pda.js','utf8');
  await page.addScriptTag({content:js.slice(0,js.indexOf("if (typeof module !== 'undefined')"))});
  await page.addScriptTag({content:js.slice(js.indexOf("$('reportRecords').addEventListener('input'"),js.indexOf("['reportMemo','reportAuthor'"))});
  await page.evaluate(()=>{
   S.equipment=[{equipment_id:'EQ-1',code:'HPU-01',signals:[]}];S.reportSelected=['EQ-1'];S.reportDraftLoaded=true;
   S.reportRecords=[{type:'추가 기록',equipment:['EQ-1'],story:'보존할 원문',causes:[{equipment:['EQ-1'],certainty:'추정',note:'첫 원인'},{equipment:['EQ-1'],certainty:'확인',note:'두 번째 원인'}],result:'다음 근무 재확인',pms:null,candidate:false}];
   $('reportAuthor').value='작업자';$('reportStart').value='2026-10-16T08:00';$('reportEnd').value='2026-10-16T16:00';
   getJson=async path=>path==='/api/events'?{events:[]}:{simulated_at:'2026-10-16T09:00',measurements:[]};
   show('reportWrite');renderReportRecords();saveReportDraft();
  });
  assert.equal(await page.locator('[data-action="remove-cause"]').first().locator('svg path').count(),1);
  assert.equal(await page.locator('[data-action="remove-cause"]').first().getAttribute('aria-label'),'원인 삭제');
  assert.equal(await page.locator('[data-action="remove-result"] svg path').count(),1);
  assert.ok((await page.locator('.cause-sensors').allTextContents()).every(text=>text.includes('등록된 센서 없음')));
  assert.equal(await page.locator('[data-action="pms"],[data-key="pms"]').count(),0);
  page.once('dialog',d=>d.dismiss());await page.locator('[data-action="remove-cause"]').first().click();
  assert.equal(await page.locator('[data-key="note"]').count(),2);
  page.once('dialog',d=>d.accept());await page.locator('[data-action="remove-cause"]').first().click();
  assert.equal(await page.locator('[data-key="note"]').inputValue(),'두 번째 원인');
  await page.locator('[data-key="note"]').fill('남은 원인 수정');
  assert.equal(await page.evaluate(()=>S.reportRecords[0].causes[0].note),'남은 원인 수정');
  page.once('dialog',d=>d.accept());await page.locator('[data-action="remove-result"]').click();
  assert.equal(await page.locator('[data-key="result"]').count(),0);
  assert.equal(await page.evaluate(()=>S.reportRecords[0].result),null);
  await page.locator('[data-action="result"]').click();assert.equal(await page.locator('[data-key="result"]').inputValue(),'');
  assert.equal(await page.evaluate(()=>JSON.parse(localStorage.getItem(REPORT_DRAFT_KEY)).records[0].result),'');
  // Empty additions can be removed directly; unrelated record text remains intact.
  await page.locator('[data-action="remove-result"]').click();
  page.once('dialog',d=>d.accept());await page.locator('[data-action="remove-cause"]').click();
  assert.equal(await page.locator('[data-key="note"]').count(),0);
  assert.equal(await page.locator('[data-key="story"]').inputValue(),'보존할 원문');
  const note=await page.evaluate(()=>selectedReportPayload(reportDraft(),S.equipment));
  assert.deepEqual(note.work_report.records[0].causes,[]);assert.equal(note.work_report.records[0].pms,null);assert.equal(note.work_report.records[0].result,null);
  await page.locator('[data-action="cause"]').click();assert.equal(await page.locator('[data-key="note"]').inputValue(),'');
  for(const width of [1280,375]){
   await page.setViewportSize({width,height:900});await page.locator('[data-action="remove-cause"]').scrollIntoViewIfNeeded();
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),width);
   fs.mkdirSync('artifacts/pda-report-remove-fields',{recursive:true});await page.screenshot({path:`artifacts/pda-report-remove-fields/${width}.png`,fullPage:true});
  }
  for(const type of ['고장·정비','PMS 정비']){
   await page.locator('[data-key="type"]').selectOption(type);
   assert.equal(await page.locator('[data-key="result"]').count(),1);
   await page.locator('[data-action="remove-result"]').click();
   assert.equal(await page.locator('[data-key="result"]').count(),0);
   assert.equal(await page.locator('[data-key="solution"]').count(),1,'deleting results preserves action entry');
   await page.locator('[data-action="result"]').click();
   assert.equal(await page.locator('[data-key="result"]').inputValue(),'');
  }
  assert.deepEqual(errors,[]);console.log('PASS: optional cause/result deletion, cancel, reindex, draft persistence, re-add, text preservation and mobile; maintenance plan controls absent');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
