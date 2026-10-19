const assert=require('node:assert/strict');
require('node:fs').mkdirSync('output',{recursive:true});
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
 const page=await browser.newPage({viewport:{width:1280,height:800}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(process.env.PDA_URL||'http://127.0.0.1:8765/pda.html');
 await page.locator('#s-account.on').waitFor();
 assert.ok(await page.locator('.factory-banner').evaluate(e=>e.complete&&e.naturalWidth>0));
 assert.ok(await page.locator('#globalHeader').isHidden());
 await page.screenshot({path:'output/pda-memo-login.png'});
 await page.locator('#accountFace').click();await page.locator('#navigationBack').click();assert.ok(await page.locator('#s-account').isVisible());
 await page.evaluate(()=>{S.operator={name:'시연 작업자',id:'local-review'};show('home');});
 assert.match(await page.locator('#homeWorkDate').innerText(),/[ABC]조/);
 assert.match(await page.locator('#homeShiftPeople').innerText(),/이전 근무자.*다음 근무자/);
 assert.deepEqual(await page.locator('#homeDashboard .label').allTextContents(),['전체 설비','가동 중','이상']);
 await page.screenshot({path:'output/pda-memo-home.png'});
 await page.locator('#toManual').click();assert.ok(await page.locator('#toManual').evaluate(e=>e.classList.contains('active')));
 await page.locator('#navigationBack').click();assert.ok(await page.locator('#s-home').isVisible());
 await page.locator('#toScan').click();await page.locator('#scanManual').click();await page.locator('#navigationBack').click();assert.ok(await page.locator('#s-scan').isVisible());
 assert.ok(await page.locator('#scanShoot').isVisible());await page.locator('#navigationBack').click();
 await page.locator('#toManual').click();await page.locator('#manualList button').first().click();
 const dimensions=await page.evaluate(()=>{const e=document.querySelector('.equipment-functions').getBoundingClientRect(),c=$('chatPanel').getBoundingClientRect();return[e.width,c.width]});
 assert.ok(Math.abs(dimensions[0]/(dimensions[0]+dimensions[1])-.6)<.03,JSON.stringify(dimensions));
 await page.evaluate(()=>{S.sensorsOpen=false;S.sensorWasBad=false;S.mes.fault='critical';renderMesStatus();});assert.ok(await page.locator('.equipment-mes').isVisible());
 await page.locator('#expandChat').click();assert.ok(await page.locator('.equipment-functions').isHidden());
 await page.locator('#expandEquipment').click();await page.locator('#expandEquipment').click();assert.ok(await page.locator('#chatPanel').isHidden());await page.locator('#expandChat').click();
 await page.locator('.workspace-divider').focus();await page.keyboard.press('ArrowRight');assert.equal(await page.locator('.workspace-divider').getAttribute('aria-valuenow'),'55');
 await page.screenshot({path:'output/pda-memo-equipment.png'});
 await page.locator('#toHandover').click();assert.match(await page.locator('#historyTitle').innerText(),/정비 이력/);await page.locator('#navigationBack').click();assert.ok(await page.locator('#s-ctx').isVisible());
 await page.locator('#headerHome').click();await page.locator('#toReport').click();
 const select=page.locator('#reportSelectAll');await select.check();await page.locator('#reportEquipment input').first().uncheck();assert.equal(await select.evaluate(e=>e.indeterminate),false);
 await page.locator('#reportWrite').click();assert.equal(await page.locator('#reportAuthor').inputValue(),'시연 작업자');
 await page.locator('#reportSave').click();assert.ok(await page.locator('#reportSaveConfirm').isVisible());await page.locator('#reportSaveNo').click();
 await page.locator('#reportWorkDate').fill('2026-10-15');
 for(const [shift,start,end] of [['A','2026-10-15T08:00','2026-10-15T16:00'],['B','2026-10-15T16:00','2026-10-16T00:00'],['C','2026-10-15T00:00','2026-10-15T08:00']]){
 await page.locator('#reportShift').selectOption(shift);assert.deepEqual(await page.evaluate(()=>[$('reportStart').value,$('reportEnd').value]),[start,end]);}
 await page.screenshot({path:'output/pda-memo-report.png'});
 await page.locator('#navigationBack').click();assert.ok(await page.locator('#s-reportSelect').isVisible());await page.locator('#navigationBack').click();assert.ok(await page.locator('#s-home').isVisible());
 await page.locator('#toDashboard').click();assert.ok(await page.locator('#globalHeader').isVisible());assert.equal(await page.locator('#anAction').count(),0);assert.ok(await page.locator('.loss-legend').isVisible());
 const cards=await page.evaluate(()=>['dashHeld','anGap'].map(id=>{const r=$(id).getBoundingClientRect();return{x:r.x,y:r.y,h:r.height}}));assert.ok(cards[1].x>cards[0].x);assert.equal(cards[0].y,cards[1].y);assert.equal(cards[0].h,cards[1].h);
 await page.screenshot({path:'output/pda-memo-dashboard.png'});
 for(const width of [800,375]){await page.setViewportSize({width,height:800});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),width);await page.screenshot({path:'output/pda-memo-dashboard-'+width+'.png'});}
 for(const width of [1280,375]){
  await page.setViewportSize({width,height:800});
  for(const screen of ['account','home','manual','ctx','scan','handover','dutyDetail','reportSelect','reportWrite','dashboard','faceSetup','face']){
   await page.evaluate(screen=>show(screen),screen);
   const back=page.getByRole('button',{name:'뒤로가기',exact:true}).filter({has:page.locator('svg')});
   if(['account','home'].includes(screen)){assert.ok(await page.locator('#navigationBack').isHidden());continue;}
   assert.ok(await back.isVisible(),screen);
   const box=await back.boundingBox();assert.ok(box.width>=48&&box.height>=48,screen);
   assert.ok(box.x<=(width>700?64:32)&&box.y<160,`${screen}: ${JSON.stringify(box)}`);
   assert.equal(await page.locator('#backDock').count(),0);
   for(const id of ['faceBack','scanClose','reportBack','faceSetupReturn'])assert.ok(await page.locator('#'+id).isHidden());
   assert.equal(await back.evaluate(el=>getComputedStyle(el).borderTopWidth),'0px');
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),width,screen);
   await back.focus();assert.equal(await page.evaluate(()=>document.activeElement.id),'navigationBack');
   if(['ctx','reportWrite','dashboard'].includes(screen))await page.screenshot({path:`output/pda-back-${screen}-${width}.png`});
  }
 }
 assert.deepEqual(errors,[]);
 console.log('PASS: memo UI, login/banner, back stack, 60/40 panes, sensors/resize/expand, shift dates, author, select-all, dashboard placement, responsive widths, zero browser errors');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
