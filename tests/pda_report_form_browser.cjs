const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
 const page=await browser.newPage({viewport:{width:1280,height:800}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const html=fs.readFileSync('shiftlink/mes/web/pda.html','utf8').replace(/<script[\s\S]*?<\/script>/g,'');
 await page.route('http://report.test/**',r=>r.fulfill({contentType:'text/html',body:html}));await page.goto('http://report.test/');
 const js=fs.readFileSync('shiftlink/mes/web/pda.js','utf8');await page.addScriptTag({content:js.split('// Node 테스트는 DOM 없이')[0]});
 await page.addScriptTag({content:`const on=(id,fn)=>$(id).addEventListener('click',fn);`+js.slice(js.indexOf("on('reportArchiveOpen'"),js.indexOf("on('logout'"))});
 await page.evaluate(()=>{
 S.equipment=[{equipment_id:'EQ-1',code:'HPU-01',group:'유압 유닛',signals:[]},{equipment_id:'EQ-2',code:'CL-01',group:'냉각기',signals:[]}];S.operator={name:'작업자'};
 openReport();S.reportSelected=['EQ-1','EQ-2'];$('reportStart').value='2026-10-15T08:00';$('reportEnd').value='2026-10-15T17:00';$('reportType').value='정상 근무';openReportWrite();
 $('reportSave').onclick=saveReport;$('reportImport').onclick=importReportMes;
 renderHome=()=>{};refreshSavedHandovers=async()=>{};showToast=()=>{};
 api=async(path,init)=>{if(path!=='/api/work-reports')throw new Error('unexpected save route');window.posted=JSON.parse(init.body);return {ok:true,json:async()=>({handover_id:'HO-test'})}};
 getJson=async(path)=>path==='/api/events'?{events:[]}:{simulated_at:'2026-10-15T09:00',equipment:[],measurements:[]};
 });
 assert.equal(await page.locator('#reportRecords .record').count(),0);
 await page.locator('#reportSave').click();assert.match(await page.evaluate(()=>posted.memo_text),/근무 유형: 정상 근무/);
 await page.evaluate(()=>{openReport();S.reportSelected=['EQ-1','EQ-2'];$('reportType').value='정상 근무';openReportWrite()});
 await page.locator('#reportAdd').click();
 page.once('dialog',dialog=>dialog.accept());await page.locator('[data-action="remove"]').click();
 assert.equal(await page.locator('#reportRecords .record').count(),0);
 assert.deepEqual(await page.evaluate(()=>JSON.parse(localStorage.getItem('shiftlink.report.draft')).records),[]);
 await page.locator('#reportAdd').click();await page.locator('#reportRecords [data-eq="EQ-1"]').uncheck();await page.locator('#reportRecords [data-eq="EQ-2"]').uncheck();await page.locator('#reportSave').click();assert.match(await page.locator('#reportStatus').innerText(),/대상 설비/);
 await page.locator('#reportRecords [data-eq="EQ-1"]').check();await page.locator('#reportRecords [data-eq="EQ-2"]').check();
 await page.locator('#reportSave').click();assert.match(await page.locator('#reportStatus').innerText(),/상황·조치/);
 await page.locator('[data-key="story"]').fill('냉却状態確認 <script>alert(1)</script>');
 await page.locator('[data-action="cause"]').click();assert.equal(await page.locator('[data-key="note"]').count(),2);for(const field of await page.locator('[data-key="note"]').all())await field.fill('냉각기 오염 확인');for(const field of await page.locator('[data-key="certainty"]').all())await field.selectOption('확인');
 await page.locator('[data-action="result"]').click();await page.locator('[data-key="result"]').fill('다음 조 확인');
 await page.locator('[data-action="pms"]').click();await page.locator('[data-key="pms"]').fill('PMS-01');await page.locator('[data-key="candidate"]').check();
 await page.locator('#reportImport').click();assert.match(await page.locator('#reportMes').innerText(),/관측 시각/);
 await page.evaluate(()=>{openReport();openReportWrite()});assert.equal(await page.locator('[data-key="pms"]').inputValue(),'PMS-01');assert.ok(await page.locator('[data-key="candidate"]').isChecked());
 await page.locator('#reportAdd').click();
 page.once('dialog',dialog=>dialog.dismiss());await page.locator('[data-action="remove"]').last().click();
 assert.equal(await page.locator('#reportRecords .record').count(),2);
 page.once('dialog',dialog=>dialog.accept());await page.locator('[data-action="remove"]').last().click();
 assert.equal(await page.locator('#reportRecords .record').count(),1);
 assert.equal(await page.locator('[data-key="pms"]').inputValue(),'PMS-01');
 for(const width of [1280,375]){
 await page.setViewportSize({width,height:800});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),width);
 await page.locator('#reportAdd').scrollIntoViewIfNeeded();await page.screenshot({path:'artifacts/typed-work-report-20261016/legacy-'+width+'.png'});
 }
 await page.evaluate(()=>{S.reportRecords[0].causes=[{...S.reportRecords[0].causes[0],equipment:['EQ-1','EQ-2']}];S.reportSelected=['EQ-1'];openReportWrite()}); // Restore a legacy multi-equipment cause before testing scope validation.
 assert.ok(await page.locator('[data-eq="EQ-2"][data-cause="0"]').isVisible(),JSON.stringify(await page.evaluate(()=>({selected:S.reportSelected,records:S.reportRecords.map(r=>({equipment:r.equipment,causes:r.causes}))}))));
 await page.locator('[data-eq="EQ-2"]:not([data-cause])').uncheck();
 await page.locator('#reportSave').click();assert.match(await page.locator('#reportStatus').innerText(),/원인의 대상 설비/);
 await page.locator('[data-eq="EQ-2"][data-cause="0"]').uncheck();
 await page.locator('#reportSave').click();assert.equal(await page.evaluate(()=>posted.work_report.records[0].candidate),true);
 assert.deepEqual(await page.evaluate(()=>posted.equipment_ids),['EQ-1']);
 assert.deepEqual(await page.evaluate(()=>posted.work_report.records[0].causes[0].equipment),['EQ-1']);assert.match(await page.evaluate(()=>posted.memo_text),/PMS-01/);
 await page.evaluate(()=>{
 show('reportWrite');
 getJson=async(path)=>path.includes('?')?{reports:[{handover_id:posted.handover_id,created_at:'2026-10-15',required_context:posted.required_context}]}:{report:{...posted,status:'uploaded'}};
 });
 await page.locator('#reportArchiveOpen').click();await page.locator('#reportArchiveList button').click();
 assert.match(await page.locator('#reportArchiveDetail').innerText(),/PMS-01/);
 assert.match(await page.locator('#reportArchiveStatus').innerText(),/업로드 완료/);
 await page.locator('#reportArchiveClose').click();
 await page.evaluate(()=>{window.archiveRequests=[];getJson=path=>new Promise(resolve=>archiveRequests.push({path,resolve}))});
 await page.locator('#reportArchiveOpen').click();await page.keyboard.press('Escape');
 await page.locator('#reportArchiveOpen').click();
 await page.evaluate(()=>{archiveRequests[1].resolve({reports:[{handover_id:'HO-NEW',required_context:{author:'NEW'}}]});archiveRequests[0].resolve({reports:[{handover_id:'HO-OLD',required_context:{author:'OLD'}}]})});
 assert.equal(await page.locator('#reportArchiveList button').count(),1);
 assert.match(await page.locator('#reportArchiveList').innerText(),/NEW/);
 await page.locator('#reportArchiveList button').click();await page.keyboard.press('Escape');
 await page.locator('#reportArchiveOpen').click();
 await page.evaluate(()=>{archiveRequests[3].resolve({reports:[]});archiveRequests[2].resolve({report:{handover_id:'HO-OLD',memo_text:'OLD',required_context:{}}})});
 assert.equal(await page.locator('#reportArchiveDetail').innerText(),'');
 assert.match(await page.locator('#reportArchiveStatus').innerText(),/없습니다/);
 await page.locator('#reportArchiveClose').click();
 assert.deepEqual(errors,[]);console.log('PASS: PDA report browser, normal save, required fields, multiple equipment/causes, draft restore, MES import, optional fields, 1280/375px, zero browser errors');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
