const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require('playwright');

// Browser event/payload simulation; candidate creation itself is checked by the HTTP suite.
(async () => {
  const browser = await chromium.launch({channel:'chrome',headless:true});
  const passed = [];
  try {
    const page = await browser.newPage({viewport:{width:1280,height:900}});
    page.setDefaultTimeout(8000);
    const errors = [];
    page.on('pageerror',e=>errors.push(e.message));
    const html=fs.readFileSync('shiftlink/mes/web/pda.html','utf8').replace(/<script[\s\S]*?<\/script>/g,'');
    await page.route('http://scenario.test/**',r=>r.fulfill({contentType:'text/html',body:html}));
    await page.goto('http://scenario.test/');
    const js=fs.readFileSync('shiftlink/mes/web/pda.js','utf8');
    await page.addScriptTag({content:js.slice(0,js.indexOf("if (typeof module !== 'undefined')"))});
    await page.addScriptTag({content:js.slice(js.indexOf("$('reportRecords').addEventListener('input'"),js.indexOf("['reportMemo','reportAuthor'"))});
    await page.addScriptTag({content:js.slice(js.indexOf("['reportMemo','reportAuthor'"),js.indexOf("on('reportResumeLoad'"))});
    await page.addScriptTag({content:"['reportWorkDate','reportShift'].forEach(id=>$(id).addEventListener('change',syncReportShift));"});
    await page.evaluate(()=>{
      localStorage.clear();
      S.operator={id:'SIM',name:'최초 근무자'};
      S.equipment=[{equipment_id:'EQ-1',code:'시뮬레이션 유압기',signals:[]},{equipment_id:'EQ-2',code:'시뮬레이션 냉각기',signals:[]}];
      S.reportSelected=['EQ-1','EQ-2'];S.reportRecords=[];S.reportDraftLoaded=true;
      S.handovers=[];S.savedHandovers=[];
      window.saved=[];window.chain=[];window.candidates=[];
      getJson=async path=>{
        if(path==='/api/events')return {events:[]};
        if(path==='/api/state')return {simulated_at:'2026-10-17T09:00',measurements:[]};
        if(path.startsWith('/api/incidents/'))return {incident:{incident_id:'SIM-INC',records:chain,candidates}};
        if(path.startsWith('/api/work-reports?'))return {reports:saved};
        if(path.startsWith('/api/work-reports/'))return {report:saved.find(h=>h.handover_id===path.split('/').at(-1))};
        throw Error('Unexpected GET '+path);
      };
      $('reportAuthor').value='최초 근무자';$('reportStart').value='2026-10-14T08:00';$('reportEnd').value='2026-10-14T16:00';
      show('reportWrite');renderReportRecords();$('reportAdd').onclick=addReportRecord;
    });
    assert.equal(await page.locator('#reportAdd').isDisabled(),true);
    await page.locator('#reportRecordEquipment').selectOption('EQ-1');await page.locator('#reportAdd').click();
    await page.locator('[data-key="type"]').selectOption('고장·정비');
    await page.locator('#reportAuthor').fill('상단 수정 근무자');
    assert.equal(await page.locator('[data-key="worker"]').inputValue(),'상단 수정 근무자','untouched default actor follows corrected report author');
    await page.locator('#reportAuthor').fill('최초 근무자');
    await page.locator('[data-key="story"]').fill('유압 압력 저하 최초 발견');
    await page.locator('[data-key="occurred_at"]').fill('2026-10-14T09:10');
    await page.locator('[data-key="action"]').fill('육안 점검');
    await page.locator('[data-key="observed_result"]').fill('누유 없음, 원인 미확인');
    assert.equal(await page.locator('[data-key="worker"]').inputValue(),'최초 근무자');
    assert.equal(await page.locator('[data-key="performed_at"]').inputValue(),'');
    await page.locator('#reportAuthor').fill('다른 기록 근무자');
    assert.equal(await page.locator('[data-key="worker"]').inputValue(),'최초 근무자','already recorded action keeps its original worker');
    await page.locator('#reportAuthor').fill('최초 근무자');
    await page.locator('[data-key="worker"]').fill('실제 점검 근무자');
    await page.locator('#reportAuthor').fill('수정 후 기록 근무자');
    assert.equal(await page.locator('[data-key="worker"]').inputValue(),'실제 점검 근무자','explicit actual actor survives report author change');
    await page.locator('#reportAuthor').fill('최초 근무자');
    await page.locator('[data-key="performed_at"]').fill('2026-10-14T09:15');
    await page.locator('[data-key="outcome"]').selectOption('temporary');
    assert.equal(await page.locator('[data-key="worker"]').inputValue(),'실제 점검 근무자','status rerender preserves actor');
    assert.equal(await page.locator('[data-key="performed_at"]').inputValue(),'2026-10-14T09:15');
    await page.locator('[data-action="step"]').click();
    await page.locator('[data-key="action"]').nth(1).fill('삭제 시험');
    page.once('dialog',d=>d.dismiss());await page.locator('[data-action="remove-step"]').nth(1).click();
    assert.equal(await page.locator('.capture-step').count(),2,'cancel protects populated step');
    page.once('dialog',d=>d.accept());await page.locator('[data-action="remove-step"]').nth(1).click();
    assert.equal(await page.locator('.capture-step').count(),1);
    const first=await page.evaluate(()=>selectedReportPayload(reportDraft(),S.equipment));
    assert.equal(first.work_report.records[0].action_steps[0].worker,'실제 점검 근무자');
    assert.equal(first.required_context.author,'최초 근무자');
    passed.push('real controls: equipment picker, untouched actor follows author correction; explicit and recorded actors stay; unknown action time, state rerender, deletion cancel/confirm');
    await page.evaluate(first=>{
      const h={...first,handover_id:'SIM-HO-0',created_at:'2026-10-14T16:00:00',incidents:[{record_index:0,incident_id:'SIM-INC'}]};
      saved.push(h);chain.push({handover_id:h.handover_id,record_index:0,required_context:h.required_context,record:h.work_report.records[0]});
      localStorage.removeItem(REPORT_DRAFT_KEY);S.reportRecords=[];S.reportDraftLoaded=false;
      openHandover(saved);
    },first);
    for(let day=1;day<=3;day++){
      await page.evaluate(day=>{S.operator={id:'SIM-'+day,name:'인수 근무자 '+day};},day);
      await page.locator('.handover-detail').first().click();
      await page.getByRole('button',{name:'이어서 기록',exact:true}).click();
      await page.waitForFunction(()=>S.screen==='reportWrite');
      assert.equal(await page.locator('[data-key="worker"]').inputValue(),'인수 근무자 '+day);
      assert.equal(await page.locator('[data-key="performed_at"]').inputValue(),'');
      assert.equal(await page.locator('[data-key="occurred_at"]').inputValue(),'2026-10-14T09:10');
      assert.equal(await page.locator('[data-key="occurred_at"]').getAttribute('readonly'),'');
      assert.equal(await page.locator('[data-key="follow_up"]').locator('xpath=ancestor::details').count(),0);
      await page.locator('#reportWorkDate').fill(`2026-10-${14+day}`);await page.locator('#reportWorkDate').dispatchEvent('change');await page.locator('#reportShift').selectOption('A');
      await page.locator('[data-key="story"]').fill('진행 '+day);
      await page.locator('[data-key="action"]').fill('추가 점검 '+day);
      await page.locator('[data-key="observed_result"]').fill(day===3?'교체 후 압력 정상':'추가 원인 조사 필요 '+day);
      if(day!==2)await page.locator('[data-key="performed_at"]').fill(`2026-10-${14+day}T10:00`);
      await page.locator('[data-key="follow_up"]').fill('다음 근무에서 압력 재확인');
      await page.locator('[data-action="previous"]').click();await page.waitForFunction(()=>S.screen==='dutyDetail');
      await page.evaluate(()=>goBack());await page.waitForFunction(()=>S.screen==='reportWrite');
      assert.equal(await page.locator('[data-key="action"]').inputValue(),'추가 점검 '+day,'previous detail does not overwrite unsaved action');
      await page.evaluate(()=>{saveReportDraft();S.reportRecords=[];openReport();S.reportSelected=['EQ-1'];enterReportWrite();});
      assert.equal(await page.locator('[data-key="worker"]').inputValue(),'인수 근무자 '+day,'actor survives local draft restore');
      assert.equal(await page.locator('[data-key="follow_up"]').inputValue(),'다음 근무에서 압력 재확인');
      if(day===3){
        await page.locator('[data-key="outcome"]').selectOption('resolved');
        await page.locator('[data-key="normal_run_status"]').selectOption('no_recurrence');
        await page.locator('[data-key="normal_run_minutes"]').fill('120');
        await page.locator('[data-key="normal_run_evidence"]').fill('10:00~12:00 압력 정상, 정지와 재발 없음');
      }
      const current=await page.evaluate(()=>selectedReportPayload(reportDraft(),S.equipment));
      const record=current.work_report.records[0];
      assert.equal(record.followup_from.handover_id,'SIM-HO-'+(day-1));
      assert.equal(record.action_steps[0].worker,'인수 근무자 '+day);
      assert.equal(record.action_steps[0].performed_at||'',day===2?'':`2026-10-${14+day}T10:00`);
      await page.evaluate(({current,day})=>{
        const h={...current,handover_id:'SIM-HO-'+day,created_at:`2026-10-${14+day}T16:00:00`,incidents:[{record_index:0,incident_id:'SIM-INC'}]};
        saved.push(h);chain.push({handover_id:h.handover_id,record_index:0,required_context:h.required_context,record:h.work_report.records[0]});
        localStorage.removeItem(REPORT_DRAFT_KEY);S.reportRecords=[];S.reportDraftLoaded=false;openHandover(saved);
      },{current,day});
      assert.equal(await page.locator('.handover-table tbody tr').count(),1,'one row per incident after continuation '+day);
      const cells=await page.locator('.handover-table tbody tr>*').allTextContents();
      assert.match(cells[1],new RegExp('진행 '+day));assert.equal(cells[5],'인수 근무자 '+day);
      assert.match(cells[2],/2026-10-14\s*09:10/);assert.equal(cells[3],`2026-10-${14+day}`);
    }
    passed.push('three successive followups: latest parent, readonly first occurrence, actor/time, previous detail and draft restore, latest-only incident row');
    await page.locator('.handover-detail').click();
    await page.getByText('같은 문제의 기록',{exact:true}).click();
    await page.waitForFunction(()=>document.querySelectorAll('.incident-history>li').length===4);
    for(const actor of ['실제 점검 근무자','인수 근무자 1','인수 근무자 2','인수 근무자 3'])assert.match(await page.locator('.incident-history').innerText(),new RegExp(actor));
    assert.match(await page.locator('.incident-history').innerText(),/2026-10-17 10:00/);
    assert.equal(await page.locator('.incident-history>li').count(),4);
    fs.mkdirSync('artifacts/pda-worklog-scenarios',{recursive:true});
    for(const width of [1280,768,375]){
      await page.setViewportSize({width,height:900});
      await page.locator('.incident-history').scrollIntoViewIfNeeded();
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),width);
      await page.screenshot({path:`artifacts/pda-worklog-scenarios/history-${width}.png`,fullPage:true});
    }
    passed.push('four-report history preserves distinct workers and performed time; desktop/tablet/mobile have no document overflow');
    // A closed incident must not silently gain a fifth continuation once a draft exists.
    await page.evaluate(()=>{candidates=[{handover_id:'SIM-HO-3',record_index:0,draft_id:'SIM-DRAFT',reason:'pending_review'}];});
    await page.getByRole('button',{name:'이어서 기록',exact:true}).click();
    await page.waitForFunction(()=>document.getElementById('dutyPane').textContent.includes('완료된 사건'));
    assert.equal(await page.evaluate(()=>S.screen),'dutyDetail');
    passed.push('closed confirmed candidate blocks new continuation');
    await page.evaluate(()=>{
      const second=JSON.parse(JSON.stringify(saved.at(-1)));
      second.handover_id='SIM-OTHER';second.incidents=[{record_index:0,incident_id:'SIM-OTHER-INC'}];
      const r=second.work_report.records[0];delete r.followup_from;r.incident_id='SIM-OTHER-INC';
      r.story='같은 설비의 별개 고장';r.occurred_at='2026-10-17T10:50';
      r.action_steps=[{worker:'최근 조치 근무자',performed_at:'2026-10-17T13:00',action:'나중에 수행한 조치',observed_result:'13시 결과'},
        {worker:'앞선 조치 근무자',performed_at:'2026-10-17T11:00',action:'먼저 수행한 조치',observed_result:'11시 결과'}];
      openHandover([...saved,second]);
    });
    assert.equal(await page.locator('.handover-table tbody tr').count(),2,'separate incidents on same equipment remain separate rows');
    const otherRow=page.locator('.handover-table tbody tr').filter({hasText:'같은 설비의 별개 고장'});
    assert.match(await otherRow.innerText(),/최근 조치 근무자/);
    assert.match(await otherRow.innerText(),/13시 결과/);
    assert.doesNotMatch(await otherRow.innerText(),/앞선 조치 근무자/);
    passed.push('same equipment different incidents remain separate; latest performed timestamp wins over array order');
    await page.evaluate(()=>{
      S.savedHandovers=[];S.handovers=[];
      const make=index=>({kind:'work_log',handover_id:'PAGE-'+index,equipment_ids:['EQ-1'],required_context:{author:'조회 근무자',start_at:'2026-10-17T08:00',end_at:'2026-10-17T16:00'},work_report:{records:[{type:'추가 기록',equipment:['EQ-1'],story:index===30?'이전 페이지의 미해결 기록':'페이지 기록 '+index,causes:[],candidate:false}]}});
      getJson=async path=>{if(path==='/api/work-reports?limit=30&offset=30')return {reports:[make(30)]};throw Error(path);};
      openHandover(Array.from({length:30},(_,index)=>make(index)),true);
    });
    assert.equal(await page.locator('.handover-table tbody tr').count(),30);
    await page.getByRole('button',{name:'이전 인계 더 보기',exact:true}).click();
    await page.waitForFunction(()=>document.querySelectorAll('.handover-table tbody tr').length===31);
    assert.match(await page.locator('#hoPane').innerText(),/이전 페이지의 미해결 기록/);
    assert.equal(await page.getByRole('button',{name:'이전 인계 더 보기',exact:true}).count(),0);
    passed.push('older reports beyond the first 30 remain reachable through paging');
    // Saving failures keep the exact original payload for retry instead of mutating it.
    const retry=await page.evaluate(async payload=>{
      const requests=[];let fail=true;
      const request=async (_path,init)=>{requests.push(JSON.parse(init.body));if(fail)throw Error('simulation offline');return {ok:true,json:async()=>({handover_id:'SIM-RETRY'})};};
      try{await submitHandover(payload,request);}catch(_){}
      const pending=JSON.parse(localStorage.getItem(HANDOVER_PENDING_KEY));
      let changedRejected=false;try{await submitHandover({...payload,memo_text:'edited while retry pending'},request);}catch(_){changedRejected=true;}
      fail=false;await submitHandover(payload,request);
      return {requests,pending,changedRejected,remaining:localStorage.getItem(HANDOVER_PENDING_KEY)};
    },first);
    assert.deepEqual(retry.requests[0],retry.requests[1]);assert.equal(retry.remaining,null);assert.ok(retry.pending);assert.equal(retry.changedRejected,true);
    passed.push('offline retry resends identical idempotent payload and clears pending after success');
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({status:'PASS',scenarios:passed},null,2));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
