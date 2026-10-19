const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require('playwright');

(async () => {
  const browser = await chromium.launch({channel:'chrome', headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1280,height:900}});
    const errors = []; page.on('pageerror', e => errors.push(e.message));
    const html = fs.readFileSync('shiftlink/mes/web/pda.html','utf8').replace(/<script[\s\S]*?<\/script>/g,'');
    await page.route('http://notes.test/**', route => route.fulfill({contentType:'text/html',body:html}));
    await page.goto('http://notes.test/');
    const js = fs.readFileSync('shiftlink/mes/web/pda.js','utf8');
    await page.addScriptTag({content:js.slice(0,js.indexOf("if (typeof module !== 'undefined')"))});
    await page.addScriptTag({content:js.slice(js.indexOf("$('reportRecords').addEventListener('input'"),js.indexOf("['reportMemo','reportAuthor'"))});
    await page.evaluate(() => {
      S.equipment=[{equipment_id:'EQ-1',code:'HPU-01',group:'유압',signals:[{signal:'flow',name:'유량',unit:'L/min',min:10,max:20,semantics:{}}]}];
      S.reportSelected=['EQ-1']; S.reportDraftLoaded=true;
      S.reportRecords=[{type:'추가 기록',equipment:['EQ-1'],story:'유량 저하',causes:[],result:null,pms:null,candidate:false}];
      $('reportAuthor').value='작업자';$('reportStart').value='2026-10-16T08:00';$('reportEnd').value='2026-10-16T16:00';
      getJson=async path => path==='/api/events'?{events:[{equipment_id:'EQ-1',occurred_at:'2026-10-16T09:00',observation:'유량 경보'}]}:{simulated_at:'2026-10-16T10:00',equipment:[{equipment_id:'EQ-1',operating_state:'running'}],active_alarms:[{equipment_id:'EQ-1',code:'FLOW-LOW',label:'유량 부족'}],measurements:[{equipment_id:'EQ-1',signal:'flow',value:8,unit:'L/min',quality:'good',observed_at:'2026-10-16T09:59'}]};
      show('reportWrite');renderReportRecords();
    });
    assert.equal(await page.locator('[data-key="solution"]').count(),0,'ordinary record stays compact');
    assert.deepEqual(await page.locator('[data-key="type"] option').allTextContents(),['추가 기록','이상 징후','고장 대응·수리','정기 예방정비']);
    await page.locator('[data-key="type"]').selectOption('이상증상');
    await page.locator('[data-key="solution"]').waitFor();
    await page.waitForFunction(()=>S.reportRecords[0].mes_context?.includes('유량 경보'));
    const captured=await page.evaluate(()=>S.reportRecords[0].mes_context);
    for(const text of ['8 L/min','10 ~ 20','2026-10-16T09:59','good','FLOW-LOW','유량 부족'])assert.ok(captured.includes(text),text);
    assert.equal(await page.locator('[data-key="occurred_at"]').inputValue(),'','capture time must not become occurrence time');
    await page.locator('[data-key="solution"]').fill('1. 필터 확인\n2. 청소');
    await page.locator('[data-key="outcome"]').selectOption('temporary');
    await page.locator('[data-key="result"]').fill('유량 회복, 다음 조 재확인');
    await page.locator('.report-review-notes summary').click();
    await page.locator('[data-key="operating_context"]').fill('정비 후 기동 중');
    await page.locator('[data-key="failed_attempts"]').fill('재기동만으로는 회복되지 않음');
    await page.locator('[data-key="safety_notes"]').fill('정지·격리 후 확인');
    await page.locator('[data-key="follow_up"]').fill('다음 근무에서 30분 관찰');
    await page.locator('[data-key="references"]').fill('<img src=x onerror=alert(1)> 매뉴얼 4쪽');
    const note = await page.evaluate(()=>selectedReportPayload(reportDraft(),S.equipment));
    for(const text of ['필터 확인','임시 복구','정비 후 기동 중','재기동만으로','정지·격리','30분 관찰','매뉴얼 4쪽'])assert.ok(note.memo_text.includes(text),text);
    await page.evaluate(note=>{ $('dutyPane').replaceChildren(renderReadOnlyWorklog(note));show('dutyDetail'); },note);
    const detail=await page.locator('#dutyPane').innerText();
    assert.match(detail,/기록 01\n이상 징후/);
    for(const text of ['필터 확인','임시 복구','정비 후 기동 중','재기동만으로','정지·격리','30분 관찰','매뉴얼 4쪽'])assert.ok(detail.includes(text),text);
    assert.equal(await page.locator('#dutyPane img').count(),0);
    for(const width of [1280,375]){
      await page.setViewportSize({width,height:900});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),width);
      fs.mkdirSync('artifacts/pda-abnormal-notes',{recursive:true});
      await page.screenshot({path:`artifacts/pda-abnormal-notes/detail-${width}.png`,fullPage:true});
      await page.evaluate(()=>{show('reportWrite');renderReportRecords();});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),width);
      await page.locator('[data-key="solution"]').scrollIntoViewIfNeeded();
      await page.screenshot({path:`artifacts/pda-abnormal-notes/write-${width}.png`,fullPage:true});
      await page.locator('.report-review-notes summary').click();
      await page.locator('[data-key="safety_notes"]').scrollIntoViewIfNeeded();
      await page.screenshot({path:`artifacts/pda-abnormal-notes/extra-${width}.png`,fullPage:true});
      await page.evaluate(()=>show('dutyDetail'));
    }
    await page.evaluate(()=>{window.faultRecord=JSON.parse(JSON.stringify(S.reportRecords[0]));show('reportWrite');});
    await page.locator('[data-key="type"]').selectOption('PMS 정비');
    await page.locator('[data-key="maintenance_items"]').fill('필터 오염·체결 점검');
    await page.locator('[data-key="solution"]').fill('필터 교체 후 시험운전');
    await page.locator('[data-key="parts_used"]').fill('필터 F01 1개 교체');
    await page.locator('[data-key="result"]').fill('정비 완료, 시험운전 정상');
    await page.locator('[data-key="next_maintenance"]').fill('다음 주 체결 상태 재확인');
    const maintenance=await page.evaluate(()=>selectedReportPayload(reportDraft(),S.equipment));
    for(const text of ['정기 예방정비','필터 오염·체결 점검','필터 F01 1개 교체','시험운전 정상','다음 주'])assert.ok(maintenance.memo_text.includes(text));
    assert.equal(maintenance.work_report.records[0].type,'PMS 정비');
    for(const width of [1280,375]){
      await page.setViewportSize({width,height:900});
      await page.locator('[data-key="parts_used"]').scrollIntoViewIfNeeded();
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),width);
      await page.screenshot({path:`artifacts/pda-abnormal-notes/maintenance-${width}.png`,fullPage:true});
    }
    await page.evaluate(note=>{$('dutyPane').replaceChildren(renderReadOnlyWorklog(note));show('dutyDetail');},maintenance);
    const maintenanceDetail=await page.locator('#dutyPane').innerText();
    for(const text of ['정기 예방정비','필터 오염·체결 점검','필터 F01 1개 교체','시험운전 정상','다음 주'])assert.ok(maintenanceDetail.includes(text));
    await page.evaluate(()=>{S.reportRecords[0]=window.faultRecord;show('reportWrite');renderReportRecords();});
    // A failed refresh retains the original captured evidence and worker text.
    await page.evaluate(async()=>{getJson=async()=>{throw Error('offline')};await importReportMes(0);});
    assert.match(await page.evaluate(()=>S.reportRecords[0].mes_context),/유량 경보/);
    assert.match(await page.locator('#reportStatus').textContent(),/불러오지 못/);
    assert.equal(await page.evaluate(()=>S.reportRecords[0].solution),'1. 필터 확인\n2. 청소');
    // Changing the equipment while a request is in flight cannot attach the old equipment's data.
    await page.evaluate(async()=>{
      let release;getJson=path=>path==='/api/events'?Promise.resolve({events:[]}):new Promise(resolve=>release=resolve);
      const pending=importReportMes(0);
      S.reportRecords[0].equipment=[];delete S.reportRecords[0].mes_context;
      release({simulated_at:'old',measurements:[]});await pending;
    });
    assert.equal(await page.evaluate(()=>S.reportRecords[0].mes_context),undefined);
    assert.deepEqual(errors,[]);
    console.log('PASS: abnormal-only inputs, automatic MES capture, original times, payload, handover detail, literal text, mobile and offline preservation');
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1});
