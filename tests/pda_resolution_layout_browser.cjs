const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require('playwright');

// Real DOM/rendering and resolution event handlers; API responses use an isolated fixture.
(async () => {
  const browser = await chromium.launch({channel:'chrome',headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1280,height:900}});
    page.setDefaultTimeout(8000);
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const html = fs.readFileSync('shiftlink/mes/web/pda.html','utf8').replace(/<script[\s\S]*?<\/script>/g,'');
    await page.route('http://resolution.test/**', route => route.fulfill({contentType:'text/html',body:html}));
    await page.goto('http://resolution.test/');
    const js = fs.readFileSync('shiftlink/mes/web/pda.js','utf8');
    await page.addScriptTag({content:js.slice(0,js.indexOf("if (typeof module !== 'undefined')"))});
    await page.addScriptTag({content:"function on(id, fn) { document.getElementById(id).addEventListener('click', fn); }\n" +
      js.slice(js.indexOf("on('resBack'"),js.indexOf("$('question').addEventListener"))});
    await page.evaluate(async () => {
      localStorage.clear();
      S.eq = {equipment_id:'EQ-1',code:'HPU-01',signals:[]}; S.equipment = [S.eq];
      S.operator = {id:'TEST',name:'테스트 근무자'}; $('workEquipment').textContent = 'HPU-01';
      window.requests = []; window.stepCount = 0;
      postJson = async (path, body) => {
        requests.push({path,body});
        if (path.endsWith('/start')) return {session_id:'RS-1',before:{simulated_at:'2026-10-20T04:00:00Z',alarms:['AL-HOT'],out_of_range:[{name:'유온',value:78,state:'high'}]},
          components:[{component_id:'cooling',name:'냉각기',suggested:true}],cause_suggestions:['냉각기 오염','원인 모름'],action_suggestions:[
            {text:'냉각기 점검',source:'card_step',card_id:'K-1',step_id:'ST-01',n:1},
            {text:'냉각기 점검',source:'card_step',card_id:'K-1',step_id:'ST-01',n:1},
            {text:'차단기 재투입',source:'card_step',card_id:'K-1',step_id:'ST-02',n:2,risky:true},
            {text:'냉각 성능 복구',source:'mes_recovery'},
            {text:'이전 청소 기록',source:'field_record'}]};
        if (path.endsWith('/step')) return {order:++stepCount,result_text:'유온 78 → 52'};
        if (path.endsWith('/finish')) return {verdict:'recovered',text:'MES 정상 복귀 확인',suggested_result:'resolved',after:{alarms:[]}};
        throw Error('Unexpected POST '+path);
      };
      getJson = async () => ({events:[],measurements:[]});
      await openResolve({question:'유압유 온도가 높음',started:Date.now(),response:{query_id:'Q-1'},ranked:{actions:[]}});
    });
    for (const width of [1280,375]) {
      await page.setViewportSize({width,height:900});
      await page.screenshot({path:'/private/tmp/resolution-initial-'+width+'.png',fullPage:true});
    }
    assert.equal(await page.locator('#resSymptom').inputValue(),'유압유 온도가 높음');
    assert.equal(await page.locator('#resComponents').inputValue(),'cooling');
    assert.equal(await page.locator('#resActionChips > .res-action-list .res-action').count(),2,'identical source/step shown once');
    assert.equal(await page.locator('#resFinish').isDisabled(),true);
    assert.equal(await page.locator('#resToReport').isVisible(),false);
    assert.equal(await page.getByText('MES 연동 조치 · 1건').isVisible(),true);
    assert.equal(await page.getByRole('button',{name:'냉각 성능 복구 선택',exact:true}).isVisible(),false);
    await page.getByRole('button',{name:'냉각기 점검 선택',exact:true}).click();
    assert.equal(await page.evaluate(() => requests.filter(r=>r.path.endsWith('/step')).length),0,'selection must not record a completed action');
    assert.equal(await page.locator('#resFinish').isVisible(),false);
    await page.getByRole('button',{name:'작업 완료 기록',exact:true}).click();
    assert.equal(await page.locator('#resSteps .res-step').count(),1);
    await page.getByRole('button',{name:'차단기 재투입 선택',exact:true}).click();
    assert.equal(await page.getByRole('button',{name:'작업 완료 기록',exact:true}).isDisabled(),true,'safety confirmation required');
    await page.locator('#resLive').getByRole('button',{name:'예',exact:true}).click();
    await page.getByRole('button',{name:'작업 완료 기록',exact:true}).click();
    assert.equal(await page.evaluate(() => requests.filter(r=>r.path.endsWith('/step')).at(-1).body.lockout),'예');
    await page.locator('#resFinish').click();
    assert.equal(await page.locator('#resToReport').isVisible(),true);
    assert.equal(await page.locator('#s-resolve > .pane').evaluate(el=>el.scrollTop),0,'result starts at top');
    assert.equal(await page.locator('#resSave').isVisible(),false,'alternate handover stays collapsed');
    assert.equal(await page.locator('#resCompleted').isVisible(),true,'completed work remains reviewable');
    await page.locator('#resToReport').click();
    assert.match(await page.locator('#resWarn').innerText(),/원인/,'validate before leaving');
    await page.locator('#resCauses').getByRole('button',{name:'냉각기 오염',exact:true}).click();
    for (const width of [1280,375]) {
      await page.setViewportSize({width,height:900});
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),false);
      await page.screenshot({path:'/private/tmp/resolution-result-'+width+'.png',fullPage:true});
    }
    await page.locator('#resMore').click();
    assert.equal(await page.locator('#resWork').isVisible(),true,'back returns to work phase');
    for (const width of [1280,375]) {
      await page.setViewportSize({width,height:900});
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),false);
      await page.screenshot({path:'/private/tmp/resolution-work-'+width+'.png',fullPage:true});
    }
    await page.locator('#resFinish').click();
    await page.evaluate(() => {
      $('reportAuthor').value='테스트 근무자'; $('reportStart').value='2026-10-20T08:00'; $('reportEnd').value='2026-10-20T16:00';
    });
    await page.locator('#resToReport').click();
    await page.locator('#s-reportWrite.on').waitFor();
    const record = await page.evaluate(() => S.reportRecords[0]);
    assert.equal(record.source_session_id,'RS-1');
    assert.equal(record.action_steps.length,2);
    assert.equal(record.outcome,'resolved');
    assert.match(record.safety_notes,/차단기 재투입: 예/);
    assert.deepEqual(errors,[]);
    console.log('PDA resolution layout/browser PASS: selection vs completion, safety, single primary action, validation, record transfer, desktop/mobile');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
