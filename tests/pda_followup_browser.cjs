const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const html=fs.readFileSync('shiftlink/mes/web/pda.html','utf8').replace(/<script[\s\S]*?<\/script>/g,'');
  await page.route('http://followup.test/**',r=>r.fulfill({contentType:'text/html',body:html}));await page.goto('http://followup.test/');
  const js=fs.readFileSync('shiftlink/mes/web/pda.js','utf8');
  await page.addScriptTag({content:js.slice(0,js.indexOf("if (typeof module !== 'undefined')"))});
  await page.addScriptTag({content:js.slice(js.indexOf("$('reportRecords').addEventListener('input'"),js.indexOf("['reportMemo','reportAuthor'"))});
  await page.evaluate(()=>{
   S.operator={id:'TEST',name:'다음 근무자'};S.equipment=[{equipment_id:'EQ-1',code:'HPU-01',signals:[]}];
   window.original={kind:'work_log',handover_id:'HO-ORIGINAL',equipment_ids:['EQ-1'],required_context:{author:'이전 근무자',start_at:'2026-10-15T08:00',end_at:'2026-10-15T16:00'},work_report:{records:[{type:'고장·정비',equipment:['EQ-1'],story:'압력 저하',causes:[{equipment:['EQ-1'],certainty:'추정',note:'필터 오염'}],solution:'필터 점검',result:'미해결',outcome:'open',pms:null,candidate:false}],legacy_memo:'',mes_context:''}};
   original.work_report.records[0].occurred_at='2026-10-15T09:20';
   window.full={...original,incidents:[{record_index:0,incident_id:'INC-TEST'}]};
   window.incidentRows=[{handover_id:original.handover_id,record_index:0,created_at:'2026-10-15T09:00',required_context:original.required_context,record:original.work_report.records[0]}];window.incidentCandidates=[];
   window.reads=[];getJson=async path=>{reads.push(path);if(path==='/api/work-reports?limit=30')return {reports:[full]};if(path==='/api/work-reports/HO-ORIGINAL')return {report:full};if(path==='/api/incidents/INC-TEST')return {incident:{incident_id:'INC-TEST',records:incidentRows,candidates:incidentCandidates}};if(path==='/api/events')return {events:[]};if(path==='/api/state')return {simulated_at:'2026-10-16T09:00',measurements:[]};throw Error(path)};
   S.savedHandovers=[];S.handovers=[];openHandover();
  });
  assert.equal(await page.locator('#globalHeader').isVisible(),true);
  assert.equal(await page.locator('#globalHeader>.brand').isVisible(),true);
  assert.match(await page.locator('#globalHeader>.brand').innerText(),/ShiftLink/);
  assert.equal(await page.locator('#globalHeader>#navigationBack').isVisible(),true);
  assert.equal(await page.locator('#hoPane .handover-summary').innerText(),'인계 사항');
  assert.equal(await page.locator('#handoverTableHint').count(),0);
  assert.equal(await page.locator('#globalHeader #toScan').isVisible(),true);
  assert.deepEqual(await page.locator('.handover-table thead th').allTextContents(),['설비명','특이사항','발생시각','근무일','근무조','근무자','상세보기']);
  assert.match(await page.locator('.handover-table tbody tr').first().locator('td').nth(0).innerText(),/압력 저하/);
  assert.equal(await page.locator('.handover-table tbody tr').first().locator('td').nth(2).innerText(),'2026-10-15');
  assert.equal(await page.locator('.handover-table tbody tr').first().locator('td').nth(3).innerText(),'A조');
  assert.equal(await page.locator('.handover-table tbody tr').first().locator('td').nth(1).innerText(),'2026-10-15\n09:20');
  const verticalBorders=await page.locator('.handover-table tr:first-child>*:not(:last-child)').evaluateAll(cells=>cells.map(el=>getComputedStyle(el).borderRightWidth));
  assert.ok(verticalBorders.length&&verticalBorders.every(width=>width==='1px'));
  const detailButton=page.locator('.handover-detail').first();
  assert.equal(await detailButton.innerText(),'');
  assert.equal(await detailButton.locator('svg[aria-hidden="true"]').count(),1);
  assert.match(await detailButton.getAttribute('aria-label'),/근무일지.*상세/);
  const colors=await detailButton.evaluate(el=>{const s=getComputedStyle(el);return {background:s.backgroundColor,text:s.color,height:el.getBoundingClientRect().height,font:s.fontSize};});
  assert.equal(colors.background,'rgb(36, 95, 90)');assert.equal(colors.text,'rgb(255, 255, 255)');assert.ok(colors.height>=48);assert.equal(colors.font,'16px');
  const luminance=rgb=>{const channels=rgb.match(/\d+/g).slice(0,3).map(Number).map(v=>{v/=255;return v<=0.04045?v/12.92:((v+0.055)/1.055)**2.4});return channels[0]*0.2126+channels[1]*0.7152+channels[2]*0.0722;};
  assert.ok((luminance(colors.text)+0.05)/(luminance(colors.background)+0.05)>=7,'field-worker button contrast');
  await detailButton.hover();
  await page.waitForFunction(()=>getComputedStyle(document.querySelector('.handover-detail')).backgroundColor==='rgb(25, 75, 70)');
  await page.mouse.move(0,0);await detailButton.focus();
  assert.equal(await detailButton.evaluate(el=>getComputedStyle(el).outlineWidth),'3px');
  for(const width of [1280,375]){
   await page.setViewportSize({width,height:900});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),width);
   fs.mkdirSync('artifacts/pda-followup',{recursive:true});await page.screenshot({path:`artifacts/pda-followup/handover-header-${width}.png`,fullPage:true});
  }
  await page.setViewportSize({width:1280,height:900});
  await page.locator('#hoPane button').click();
  assert.equal(await page.locator('#globalHeader').isVisible(),true);
  assert.equal(await page.locator('#globalHeader>.brand').isVisible(),true);
  assert.match(await page.locator('#globalHeader>.brand').innerText(),/ShiftLink/);
  assert.equal(await page.locator('#globalHeader>#navigationBack').isVisible(),true);
  assert.equal(await page.locator('#globalHeader #toScan').isVisible(),true);
  assert.equal(await page.locator('#globalHeader #toManual').isVisible(),true);
  assert.equal(await page.locator('#s-dutyDetail>.appbar').isVisible(),false);
  const detailStyle=await page.locator('#dutyPane .duty-report').evaluate(el=>({width:el.getBoundingClientRect().width,background:getComputedStyle(el).backgroundColor}));
  assert.ok(detailStyle.width>900,'saved worklog uses available desktop width');
  assert.equal(detailStyle.background,'rgb(255, 255, 255)');
  assert.match(await page.locator('.worklog-meta').innerText(),/A조/);
  assert.match(await page.locator('.worklog-fields').innerText(),/발생시각/);
  assert.match(await page.locator('.worklog-fields').innerText(),/09:20/);
  assert.equal(await page.locator('.worklog-id').count(),0);
  const followupButton=page.getByRole('button',{name:'이어서 기록',exact:true});
  assert.ok(await followupButton.evaluate(el=>el.getBoundingClientRect().height>=48));
  for(const width of [1280,768,375]){
   await page.setViewportSize({width,height:900});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),width);
   await page.screenshot({path:`artifacts/pda-followup/detail-${width}.png`,fullPage:true});
  }
  await page.setViewportSize({width:1280,height:900});
  assert.equal(await page.evaluate(()=>S.savedHandovers.length),0,'loading handover history does not change home data');
  await page.getByRole('button',{name:'이어서 기록',exact:true}).click();
  await page.waitForFunction(()=>S.screen==='reportWrite');
  const followup=await page.evaluate(()=>JSON.parse(JSON.stringify(S.reportRecords[0])));
  assert.equal(followup.incident_id,'INC-TEST');assert.deepEqual(followup.followup_from,{handover_id:'HO-ORIGINAL',record_index:0});
  assert.equal(followup.story,'');assert.equal(followup.solution,'');assert.equal(followup.query_id,undefined);assert.equal(followup.outcome,'open');
  assert.equal(await page.locator('[data-key="type"]').isDisabled(),true);
  assert.match(await page.locator('#reportRecords').innerText(),/이전 근무자/);
  assert.equal(await page.locator('[data-key="occurred_at"]').inputValue(),'2026-10-15T09:20');
  assert.equal(await page.locator('[data-key="occurred_at"]').getAttribute('readonly'),'');
  assert.equal(await page.locator('[data-key="worker"]').inputValue(),'다음 근무자');
  assert.equal(await page.locator('[data-key="performed_at"]').inputValue(),'');
  assert.equal(await page.locator('[data-key="follow_up"]').count(),1);
  assert.equal(await page.locator('[data-key="follow_up"]').locator('xpath=ancestor::details').count(),0);
  await page.locator('[data-key="worker"]').fill('지원 근무자');
  await page.locator('[data-key="performed_at"]').fill('2026-10-16T10:00');
  await page.getByRole('button',{name:'조치 추가',exact:true}).click();
  assert.equal(await page.locator('[data-key="worker"]').nth(1).inputValue(),'다음 근무자');
  assert.equal(await page.locator('[data-key="performed_at"]').nth(1).inputValue(),'');
  await page.locator('[data-action="remove-step"][data-step="1"]').click();
  for(const width of [1280,768,375]){
   await page.setViewportSize({width,height:900});
   await page.locator('.capture-step-meta').scrollIntoViewIfNeeded();
   const stepBox=await page.locator('.capture-step').boundingBox();
   const boxes={};
   for(const key of ['worker','performed_at','action','observed_result'])boxes[key]=await page.locator('[data-key="'+key+'"]').boundingBox();
   for(const [upper,lower] of [['worker','action'],['performed_at','observed_result']]){
    assert.ok(Math.abs(boxes[upper].x-boxes[lower].x)<=1,'matching field left edges at '+width);
    assert.ok(Math.abs(boxes[upper].width-boxes[lower].width)<=1,'matching field widths at '+width);
   }
   assert.equal(boxes.worker.height,boxes.performed_at.height);
   assert.equal(boxes.action.height,boxes.observed_result.height);
   for(const field of ['worker','performed_at']){
    const box=await page.locator('[data-key="'+field+'"]').boundingBox();
    assert.ok(box.x>=stepBox.x&&box.x+box.width<=stepBox.x+stepBox.width+1,'step field contained at '+width);
   }
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),width);
   await page.screenshot({path:`artifacts/pda-followup/step-worker-${width}.png`,fullPage:true});
  }
  await page.setViewportSize({width:1280,height:900});
  await page.getByRole('button',{name:'이전 기록 보기',exact:true}).click();
  await page.locator('#reportPreviousDialog').waitFor({state:'visible'});
  assert.equal(await page.evaluate(()=>S.screen),'reportWrite');
  assert.match(await page.locator('#reportPreviousBody').innerText(),/압력 저하/);
  assert.equal(await page.locator('#reportPreviousBody .incident-actions').count(),0);
  await page.getByRole('button',{name:'닫기',exact:true}).click();
  assert.equal(await page.evaluate(()=>S.screen),'reportWrite');
  assert.equal(await page.locator('[data-key="worker"]').inputValue(),'지원 근무자');
  await page.locator('[data-key="story"]').fill('필터 막힘 확인');
  assert.equal(followup.capture_version,1);assert.equal(followup.candidate,true);
  await page.locator('[data-key="action"]').fill('필터 교체 후 시운전');
  await page.locator('[data-key="observed_result"]').fill('압력 회복 확인');
  await page.locator('[data-key="outcome"]').selectOption('resolved');
  await page.locator('[data-key="normal_run_status"]').selectOption('no_recurrence');
  await page.locator('[data-key="normal_run_minutes"]').fill('120');
  await page.locator('[data-key="normal_run_evidence"]').fill('10:00~12:00 연속 운전, 정지·재발 없음');
  const note=await page.evaluate(()=>selectedReportPayload(reportDraft(),S.equipment));
  assert.equal(note.work_report.records[0].normal_run_minutes,120);assert.match(note.memo_text,/120분/);
  assert.equal(note.work_report.records[0].action_steps[0].worker,'지원 근무자');
  assert.equal(note.work_report.records[0].action_steps[0].performed_at,'2026-10-16T10:00');
  assert.equal(note.required_context.author,'다음 근무자');
  assert.equal(await page.evaluate(()=>original.work_report.records[0].result),'미해결');
  for(const width of [1280,375]){
   await page.setViewportSize({width,height:900});await page.locator('[data-key="normal_run_minutes"]').scrollIntoViewIfNeeded();
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),width);
   fs.mkdirSync('artifacts/pda-followup',{recursive:true});await page.screenshot({path:`artifacts/pda-followup/write-${width}.png`,fullPage:true});
  }
  await page.evaluate(note=>{$('dutyPane').replaceChildren(renderReadOnlyWorklog({...note,handover_id:'HO-NEXT'}));show('dutyDetail');},note);
  assert.match(await page.locator('#dutyPane').innerText(),/120분/);
  assert.match(await page.locator('#dutyPane').innerText(),/지원 근무자/);
  assert.match(await page.locator('#dutyPane').innerText(),/2026-10-16 10:00/);
  assert.match(await page.locator('#dutyPane').innerText(),/HO-ORIGINAL/);
  await page.evaluate(()=>{$('dutyPane').replaceChildren(renderReadOnlyWorklog(original));show('dutyDetail');});
  await page.locator('summary').filter({hasText:'같은 문제의 기록'}).click();
  await page.waitForFunction(()=>document.getElementById('dutyPane').textContent.includes('이전 근무자 ·'));
  assert.match(await page.locator('#dutyPane').innerText(),/필터 점검/);
  // Existing drafts survive another handover, and unsent payloads cannot be changed by it.
  await page.getByRole('button',{name:'이어서 기록',exact:true}).click();
  await page.locator('#reportFollowupChoice').waitFor({state:'visible'});
  await page.getByRole('button',{name:'취소',exact:true}).click();
  assert.equal(await page.evaluate(()=>S.screen),'dutyDetail');
  await page.getByRole('button',{name:'이어서 기록',exact:true}).click();
  await page.getByRole('button',{name:'유지하고 계속 기록',exact:true}).click();
  await page.waitForFunction(()=>S.screen==='reportWrite');
  assert.equal(await page.evaluate(()=>S.reportRecords.length),1);
  assert.equal(await page.evaluate(()=>S.reportRecords[0].normal_run_minutes),120);
  await page.evaluate(()=>{localStorage.setItem(HANDOVER_PENDING_KEY,JSON.stringify({kind:'work_log'}));$('dutyPane').replaceChildren(renderReadOnlyWorklog(original));show('dutyDetail');});
  await page.getByRole('button',{name:'이어서 기록',exact:true}).click();
  await page.waitForFunction(()=>document.getElementById('dutyPane').textContent.includes('전송 대기'));
  assert.equal(await page.evaluate(()=>S.reportRecords.length),1);
  await page.evaluate(()=>{
   localStorage.removeItem(HANDOVER_PENDING_KEY);localStorage.removeItem(REPORT_DRAFT_KEY);S.reportDraftLoaded=false;S.reportRecords=[];
   incidentRows.push({handover_id:'HO-MIDDLE',record_index:0,required_context:{author:'중간 근무자',start_at:'2026-10-15T16:00',end_at:'2026-10-16T00:00'},record:{...original.work_report.records[0],story:'차압 상승 확인',followup_from:{handover_id:'HO-ORIGINAL',record_index:0}}});
   $('dutyPane').replaceChildren(renderReadOnlyWorklog(original));show('dutyDetail');
  });
  await page.getByRole('button',{name:'이어서 기록',exact:true}).click();await page.waitForFunction(()=>S.screen==='reportWrite');
  assert.equal(await page.evaluate(()=>S.reportRecords[0].followup_from.handover_id),'HO-MIDDLE','old detail continues the latest report');
  assert.match(await page.locator('#reportRecords').innerText(),/중간 근무자/);
  await page.evaluate(()=>{
   incidentRows.push({handover_id:'HO-FINAL',record_index:0,required_context:{author:'마지막 근무자',start_at:'2026-10-16T00:00',end_at:'2026-10-16T08:00'},record:{...original.work_report.records[0],story:'필터 교체 후 복구',outcome:'resolved',normal_run_status:'no_recurrence',normal_run_minutes:120,normal_run_evidence:'120분 정상 운전 확인',followup_from:{handover_id:'HO-MIDDLE',record_index:0}}});
   incidentCandidates=[{handover_id:'HO-FINAL',record_index:0,draft_id:'K-7000',reason:'pending_review'}];
   $('dutyPane').replaceChildren(renderReadOnlyWorklog(original));show('dutyDetail');
  });
  await page.getByRole('button',{name:'이어서 기록',exact:true}).click();
  await page.waitForFunction(()=>document.getElementById('dutyPane').textContent.includes('완료된 사건'));
  assert.equal(await page.evaluate(()=>S.screen),'dutyDetail');
  await page.locator('summary').filter({hasText:'같은 문제의 기록'}).click();
  await page.waitForFunction(()=>document.querySelectorAll('.incident-history>li').length===3);
  assert.match(await page.locator('.incident-status').innerText(),/검토 대기/);
  assert.match(await page.locator('.incident-status').innerText(),/사건의 최신 상태.*마지막 근무자/s);
  assert.equal(await page.getByRole('button',{name:'이어서 기록',exact:true}).isDisabled(),true);
  for(const width of [1280,375]){
   await page.setViewportSize({width,height:900});await page.locator('.incident-history').scrollIntoViewIfNeeded();
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),width);
   await page.screenshot({path:`artifacts/pda-followup/history-${width}.png`,fullPage:true});
  }
  await page.evaluate(()=>openDutyDetail({kind:'handover',handover_id:'HO-LEGACY-HIDDEN',memo_text:'이전 인계 내용',equipment_ids:['EQ-1'],occurred_at:'2026-10-15T10:30',required_context:{author:'이전 담당자',start_at:'2026-10-15T16:00',end_at:'2026-10-16T00:00'}},'handover'));
  assert.equal(await page.locator('#dutyPane>.lbl').count(),0);
  assert.equal(await page.locator('#dutyTitle').innerText(),'근무일지');
  assert.equal(await page.locator('.worklog-head h2').innerText(),'근 무 일 지');
  assert.doesNotMatch(await page.locator('#dutyPane').innerText(),/당\s*직\s*일\s*지/);
  assert.doesNotMatch(await page.locator('#dutyPane').innerText(),/HO-LEGACY-HIDDEN/);
  assert.match(await page.locator('.worklog-meta').innerText(),/이전 담당자/);
  assert.match(await page.locator('.worklog-meta').innerText(),/B조/);
  assert.match(await page.locator('.worklog-fields').innerText(),/10:30/);
  assert.deepEqual(errors,[]);console.log('PASS: handover columns and original occurrence, matching saved-worklog design, legacy author, structured continuation, ordered history and pending review');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
