const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {spawn}=require('node:child_process');
const {once}=require('node:events');
const {chromium}=require('playwright');

(async()=>{
  const root=path.resolve(__dirname,'..'),artifact=path.join(root,'artifacts/pda-worklog-http-20261019');
  fs.mkdirSync(artifact,{recursive:true});
  const child=spawn(process.env.PYTHON_BIN||'python',['-u','tests/typed_report_server.py'],{
    cwd:root,windowsHide:true,env:{...process.env,PYTHONPATH:root,PYTHONUTF8:'1'},stdio:['pipe','pipe','pipe']});
  let diagnostics='',browser;
  child.stderr.on('data',data=>diagnostics+=data.toString());
  try{
    const metadata=await new Promise((resolve,reject)=>{
      let buffer='';const timer=setTimeout(()=>reject(Error('Test server startup timeout: '+diagnostics)),20000);
      child.stdout.on('data',data=>{buffer+=data.toString();if(buffer.includes('\n')){
        clearTimeout(timer);try{resolve(JSON.parse(buffer.split('\n')[0]));}catch(error){reject(error);}
      }});
      child.once('exit',code=>{clearTimeout(timer);reject(Error('Test server exited '+code+': '+diagnostics));});
    });
    const base='http://127.0.0.1:'+metadata.port,errors=[],failedApi=[];
    browser=await chromium.launch({channel:'chrome',headless:true});
    const page=await browser.newPage({viewport:{width:1280,height:900}});
    page.setDefaultTimeout(10000);
    page.on('pageerror',error=>errors.push(error.message));
    page.on('response',response=>{if(response.url().includes('/api/')&&response.status()>=400)failedApi.push([response.status(),response.url()]);});
    // Load the actual HTML, script, event wiring and HTTP routes without interception.
    await page.goto(base+'/pda.html');
    await page.locator('#employeeId').fill('BROWSER-01');
    await page.locator('#employeePassword').fill('local-browser-test-only');
    await page.locator('#accountForm button[type=submit]').click();
    await page.locator('#s-home.on').waitFor();
    const begin=async()=>{
      await page.locator('#toReport').click();
      await page.locator('#reportEquipment input[type=checkbox]').first().check();
      await page.locator('#reportWrite').click();
      await page.locator('#s-reportWrite.on').waitFor();
    };
    const save=async()=>{
      const responsePromise=page.waitForResponse(r=>r.url()===base+'/api/work-reports'&&r.request().method()==='POST');
      await page.locator('#reportSave').click();await page.locator('#reportSaveYes').click();
      const response=await responsePromise;assert.equal(response.status(),200,await response.text());
      const saved=await response.json();await page.locator('#s-home.on').waitFor();return saved;
    };
    const shot=async name=>page.screenshot({path:path.join(artifact,name+'.png'),fullPage:true});
    await begin();
    await page.locator('#reportWorkDate').fill('2026-10-16');await page.locator('#reportShift').selectOption('B');
    assert.equal(await page.locator('#reportEnd').inputValue(),'2026-10-17T00:00');
    await page.locator('#reportSave').click();await page.locator('#reportSaveNo').click();
    assert.equal(await page.locator('#reportSaveConfirm').isVisible(),false);
    const normal=await save();
    const normalDetail=await (await page.request.get(base+'/api/work-reports/'+normal.handover_id)).json();
    assert.deepEqual(normalDetail.report.work_report.records,[]);
    await begin();await page.locator('#reportAdd').click();
    await page.locator('[data-key=type]').selectOption('고장·정비');
    await page.locator('[data-key=occurred_at]').fill('2026-10-16T09:10');
    await page.locator('[data-key=story]').fill('로컬 E2E · 압력 저하, 다음 근무에서 필터 재확인');
    await page.locator('[data-key=action]').fill('필터 상태 점검');
    await page.locator('[data-key=observed_result]').fill('오염 의심, 추가 점검 필요');
    await page.locator('[data-key=worker]').fill('첫 조치 근무자');
    await page.locator('[data-key=performed_at]').fill('2026-10-16T09:20');
    await page.locator('[data-key=outcome]').selectOption('temporary');
    await shot('write-1280');
    const first=await save();
    const firstDetail=await (await page.request.get(base+'/api/work-reports/'+first.handover_id)).json();
    assert.equal(firstDetail.report.work_report.records[0].action_steps[0].worker,'첫 조치 근무자');
    assert.equal(firstDetail.report.work_report.records[0].occurred_at,'2026-10-16T09:10');
    assert.equal(firstDetail.report.server_sensor_evidence.scope,'save_snapshot');
    await page.locator('#toHandoverHome').click();await page.locator('#s-handover.on').waitFor();
    const issueRows=page.locator('.handover-table tbody tr').filter({hasText:'로컬 E2E'});
    assert.equal(await issueRows.count(),1,'one test issue; reference handovers remain visible');
    await issueRows.locator('button').click();await page.locator('#s-dutyDetail.on').waitFor();
    assert.equal(await page.locator('#dutyPane input,#dutyPane textarea').count(),0);
    await page.locator('.incident-actions button').click();await page.locator('#s-reportWrite.on').waitFor();
    assert.equal(await page.locator('[data-key=occurred_at]').inputValue(),'2026-10-16T09:10');
    await page.locator('[data-key=story]').fill('로컬 E2E · 후속 조치로 필터 교체');
    await page.locator('[data-key=action]').fill('필터 교체');
    await page.locator('[data-key=observed_result]').fill('압력 정상 범위 복귀');
    await page.locator('[data-key=worker]').fill('인수 근무자');
    await page.locator('[data-key=performed_at]').fill('2026-10-17T10:00');
    await page.locator('[data-key=outcome]').selectOption('resolved');
    await page.locator('[data-key=normal_run_status]').selectOption('no_recurrence');
    await page.locator('[data-key=normal_run_minutes]').fill('120');
    await page.locator('[data-key=normal_run_evidence]').fill('10:00~12:00 연속 운전, 정지·재발 없음');
    const second=await save();
    const secondDetail=await (await page.request.get(base+'/api/work-reports/'+second.handover_id)).json();
    const followup=secondDetail.report.work_report.records[0];
    assert.deepEqual(followup.followup_from,{handover_id:first.handover_id,record_index:0});
    assert.equal(followup.incident_id,first.incidents[0].incident_id);
    assert.equal(followup.action_steps[0].worker,'인수 근무자');
    const incident=await (await page.request.get(base+'/api/incidents/'+followup.incident_id)).json();
    assert.equal(incident.incident.records.length,2);
    await page.locator('#toHandoverHome').click();await page.locator('#s-handover.on').waitFor();
    assert.equal(await issueRows.count(),1,'followup updates one incident row');
    assert.match(await issueRows.innerText(),/인수 근무자/);
    for(const width of [1280,768,375]){
      await page.setViewportSize({width,height:900});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),width);
      await shot('handover-'+width);
    }
    await issueRows.locator('button').click();
    for(const width of [1280,375]){
      await page.setViewportSize({width,height:900});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),width);
      await shot('detail-'+width);
    }
    await page.locator('#dutyPane details').filter({has:page.locator('summary',{hasText:'같은 문제의 기록'})}).locator('summary').click();
    await page.waitForFunction(()=>document.querySelectorAll('.incident-history li').length===2);
    await page.reload();await page.locator('#s-home.on').waitFor();
    assert.match(await page.locator('#homeHandover').innerText(),/필터 교체/);
    const query=await (await page.request.post(base+'/api/query',{data:{question:'로컬 검증용 카드 없는 고장',equipment_id:metadata.equipment[0].equipment_id}})).json();
    assert.ok(query.query_id,'actual query response must carry the durable ID for report linking');
    assert.equal(query.knowledge_status,'no_applicable_card');
    assert.deepEqual(errors,[]);assert.deepEqual(failedApi,[]);
    fs.writeFileSync(path.join(artifact,'results.json'),JSON.stringify({passed:true,errors,failedApi,
      scenarios:['real login and boot','normal shift/overnight/cancel/save','worklog capture and HTTP roundtrip',
        'followup links one incident','readonly detail and history','1280/768/375px','reload retains reports','durable query ID'],
      reports:[normal.handover_id,first.handover_id,second.handover_id]},null,2));
    console.log('PASS: unmodified page -> login -> controls -> HTTP -> temporary SQLite -> followup/history/reload, desktop/tablet/mobile and query metadata');
  }finally{
    if(browser)await browser.close();
    if(child.exitCode===null){child.stdin.end('\n');await once(child,'exit');}
    assert.equal(child.exitCode,0,diagnostics);
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
