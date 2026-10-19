const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require('playwright');
const equipment = {equipment_id:'EQ-0001',code:'HPU-01',name:'유압 장치',signals:[{signal:'hpu_pressure',name:'유압 압력',unit:'bar',normal_min:145,normal_max:165}]};
const safety = {card_id:'SAFE-1',equipment:'HPU',safety_flag:true,tacit_type:'T5',title:'작업 전 압력 해제',know_how:'압력을 해제하고 확인하세요.',conditions:[]};
let value=155, questionCount=0, noKnowledge=false;
function snapshot() {return {simulated_at:new Date().toISOString(),equipment:[{equipment_id:'EQ-0001',operating_state:'running',fault_level:'normal'}],measurements:[{equipment_id:'EQ-0001',signal:'hpu_pressure',value,unit:'bar',quality:'good',observed_at:new Date().toISOString()}],active_alarms:[],symptom_diagnostics:[]};}
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try {
  const page=await browser.newPage(); const errors=[];page.on('pageerror',e=>errors.push(e.stack));
  await page.route('**/*',async route=>{
   const path=new URL(route.request().url()).pathname;
   if(path==='/pda.html')return route.fulfill({contentType:'text/html',body:fs.readFileSync('shiftlink/mes/web/pda.html','utf8')});
   if(path==='/static/pda.js')return route.fulfill({contentType:'text/javascript',body:fs.readFileSync('shiftlink/mes/web/pda.js','utf8')});
   if(path==='/api/analytics')return route.fulfill({status:503,contentType:'application/json',body:'{}'});
   const bodies={'/api/config':{config:{equipment:[equipment]}},'/api/catalog':{data:{}},'/api/kb/cards':{cards:[safety]},'/api/state':snapshot()};
   if(path==='/api/query') {questionCount++;bodies[path]={answer:'펌프 흡입부와 릴리프 밸브를 확인하세요.',cited_card_ids:[],safety_notices:[{card_id:'SAFE-1',stop_conditions:['잔압이 있으면 작업을 중지하세요.']}],no_knowledge:noKnowledge,review_queue:false};}
   return route.fulfill({contentType:'application/json',body:JSON.stringify(bodies[path]||{})});
  });
  await page.goto('http://shiftlink.test/pda.html');await page.locator('#s-account.on').waitFor();
  for(const width of [1280,375]) {
   await page.setViewportSize({width,height:800});await page.evaluate(()=>show('account'));
   assert.equal(await page.locator('#s-account>.appbar').isVisible(),false,'no empty login header');
   await page.screenshot({path:`output/pda-login-updated-${width}.png`});
   await page.evaluate(()=>{S.operator={id:'test',name:'검증'};setContext(S.equipment[0],'manual_selection');show('ctx');});
   await page.locator('#equipmentMetrics .sensor-row').first().waitFor({state:'attached'});
   assert.equal(await page.locator('#mesPin').count(),0);
   assert.equal(await page.locator('.equipment-functions .panel-head h2').innerText(),'장비');
   assert.equal(await page.locator('#chatPanel .panel-head h2').innerText(),'채팅');
   assert.equal(await page.locator('#splitWorkspace').count(),0,'no separate split button');
   // 가운데 줄: › 장비 전체, ‹ 채팅 전체. 전체 화면에서는 반대쪽 버튼 하나가 함께 보기로 되돌린다(좁은 화면은 위아래 배치라 없음)
   if(width>600) for(const [id,hidden,back] of [['expandEquipment','#chatPanel','expandChat'],['expandChat','.equipment-functions','expandEquipment']]) {
    await page.locator('#'+id).click();assert.equal(await page.locator(hidden).isVisible(),false);
    assert.equal(await page.locator('#'+id).isVisible(),false,'only the way back is shown');
    assert.equal(await page.locator('#'+back).getAttribute('aria-label'),'함께 보기');
    await page.locator('#'+back).click();assert.equal(await page.locator(hidden).isVisible(),true);
   }
   assert.ok(await page.locator('#chatPanel').isVisible());
   const gap=await page.evaluate(()=>document.querySelector('.equipment-functions .work-actions').getBoundingClientRect().top-document.querySelector('.equipment-functions .section-heading').getBoundingClientRect().bottom);
   assert.ok(gap>=24,'work buttons moved below heading: '+gap);
   const old=await page.locator('#equipmentMetrics').innerText(), time=await page.locator('#metricsTime').innerText();
   value=160;await page.evaluate(()=>loadMesObservations());
   assert.equal(await page.locator('#equipmentMetrics').innerText(),old);
   assert.equal(await page.locator('#metricsTime').innerText(),time);
   await page.locator('#mesRefresh').click();await page.waitForFunction(()=>/160/.test(document.getElementById('equipmentMetrics').innerText));
   assert.match(await page.locator('#equipmentMetrics').innerText(),/160/);
   // Many sensors must scroll inside the existing panel, with no visible scrollbar.
   await page.evaluate(()=>{const base=S.eq.signals[0];S.eq.signals=Array.from({length:30},(_,i)=>({...base,signal:i?'extra_'+i:base.signal,name:'센서 '+i}));renderEquipmentMetrics();});
   for(const mode of ['expandEquipment','expandChat']) {
    if(width>600) await page.locator('#'+mode).click();
    const grid=page.locator('#equipmentMetrics');
    assert.ok(await grid.evaluate(e=>e.scrollHeight>e.clientHeight),'sensor values overflow inside bounded panel');
    assert.equal(await grid.evaluate(e=>getComputedStyle(e).overflowY),'auto');
    assert.equal(await grid.evaluate(e=>getComputedStyle(e).scrollbarWidth),'none');
    await grid.hover();await page.mouse.wheel(0,240);
    await page.waitForFunction(()=>document.getElementById('equipmentMetrics').scrollTop>0);
    await grid.focus();await page.keyboard.press('End');
   }
   const summary=page.locator('#askSafety>details>summary');
   assert.equal(await page.locator('#askSafety>details').evaluate(e=>e.open),false);
   await summary.click();assert.equal(await page.locator('#askSafety>details').evaluate(e=>e.open),true);
   await page.locator('#question').fill('유압이 낮아요');
   await page.locator('#doSearch').click();await page.locator('#chatLog .ans').filter({hasText:'펌프 흡입부'}).waitFor();
   assert.equal(await page.locator('#chatLog .safety-group,#chatLog .safety').count(),0);
   assert.match(await page.locator('#askSafety').innerText(),/잔압이 있으면 작업을 중지/);
   assert.equal(await page.locator('#askSafety>details').evaluate(e=>e.open),true);
   await summary.click();
   await page.evaluate(()=>{for(let i=0;i<20;i++){const p=document.createElement('p');p.textContent='이전 대화 내용 '+i;p.style.minHeight='80px';document.getElementById('chatLog').appendChild(p);}});
   const before=await summary.boundingBox();await page.locator('#chatPane').evaluate(e=>e.scrollTop=e.scrollHeight);const after=await summary.boundingBox();
   assert.equal(after.y,before.y,'safety bar stays outside chat scrolling');
   await summary.click();await summary.click();
   assert.ok(await summary.isVisible());
   // Accepting the no-knowledge report offer must return directly to this chat.
   noKnowledge=true;
   await page.locator('#question').fill('등록되지 않은 증상');await page.locator('#doSearch').click();
   await page.locator('#chatLog .report-ask').waitFor();
   await page.locator('#chatLog .report-ask').getByRole('button',{name:'네',exact:true}).click();
   await page.locator('#s-reportWrite.on').waitFor();
   await page.locator('#navigationBack').click();
   await page.locator('#s-ctx.on').waitFor();
   assert.equal(await page.locator('#s-reportSelect.on').count(),0,'skip intermediate equipment selection');
   assert.match(await page.locator('#chatLog').innerText(),/등록되지 않은 증상/);
   assert.match(await page.locator('#chatLog').innerText(),/펌프 흡입부/);
   assert.equal(await page.evaluate(()=>S.reportRecords.at(-1).story.includes('등록되지 않은 증상')),true,'report draft is preserved');
   noKnowledge=false;
   await page.screenshot({path:`output/pda-workspace-updated-${width}.png`});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),width);
  }
  assert.equal(questionCount,4);assert.deepEqual(errors,[]);
  console.log('PASS: hidden-scrollbar sensor scrolling, direct return from chat report, frozen sensors, safety bar and 1280/375 layouts');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
