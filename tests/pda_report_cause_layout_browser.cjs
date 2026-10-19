const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const page=await browser.newPage();
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const html=fs.readFileSync('shiftlink/mes/web/pda.html','utf8').replace(/<script[\s\S]*?<\/script>/g,'');
  await page.route('http://cause.test/**',r=>r.fulfill({contentType:'text/html',body:html}));await page.goto('http://cause.test/');
  const js=fs.readFileSync('shiftlink/mes/web/pda.js','utf8');
  await page.addScriptTag({content:js.slice(0,js.indexOf("if (typeof module !== 'undefined')"))});
  await page.addScriptTag({content:js.slice(js.indexOf("$('reportRecords').addEventListener('input'"),js.indexOf("['reportMemo','reportAuthor'"))});
  await page.evaluate(()=>{
   S.equipment=[{equipment_id:'EQ-1',code:'HPU-01',group:'유압 유닛',signals:[{signal:'pressure',name:'압력',unit:'bar',min:145,max:165,semantics:{}}]}];
   S.snapshot={simulated_at:'2026-10-17T09:00:00+09:00',equipment:[],active_alarms:[],measurements:[{equipment_id:'EQ-1',signal:'pressure',value:154.845,unit:'bar',quality:'good',observed_at:'2026-10-17T09:00:00+09:00'}]};
   S.reportSelected=['EQ-1'];S.reportDraftLoaded=true;
   S.reportRecords=[{type:'추가 기록',equipment:['EQ-1'],story:'압력 확인',causes:[{equipment:['EQ-1'],certainty:'추정',note:'필터 점검'}],result:null,pms:null,candidate:false}];
   show('reportWrite');renderReportRecords();
  });
  const sensor=page.locator('.cause-sensors'),value=page.locator('.cause-sensor-value');
  assert.equal(await value.isVisible(),false);
  await sensor.selectOption({label:'압력'});
  assert.equal(await value.innerText(),'154.845 bar');
  assert.equal(await page.evaluate(()=>S.reportRecords[0].causes[0].sensor_ref.signal),'pressure');
  fs.mkdirSync('artifacts/pda-report-cause-layout',{recursive:true});
  for(const width of [1280,768,375]){
   await page.setViewportSize({width,height:900});await sensor.scrollIntoViewIfNeeded();
   const s=await sensor.boundingBox(),v=await value.boundingBox(),c=await page.locator('[data-key=certainty]').boundingBox();
   assert.ok(c.y>=s.y+s.height-1,'certainty below sensor');
   assert.ok(v.x>=s.x+s.width-1,'value beside sensor');
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),width);
   await page.screenshot({path:`artifacts/pda-report-cause-layout/cause-${width}.png`});
  }
  await page.evaluate(()=>{S.snapshot.measurements[0].value=180;refreshReportCauseSensors();});
  assert.match(await value.innerText(),/180 bar.*범위 이탈/);
  await page.evaluate(()=>{S.snapshot.measurements[0].quality='bad';refreshReportCauseSensors();});
  assert.equal(await value.innerText(),'값 확인 불가');
  await page.evaluate(()=>{S.snapshot=null;refreshReportCauseSensors();});
  assert.equal(await value.innerText(),'값 확인 불가');
  await page.evaluate(()=>renderReportRecords());
  assert.equal(await sensor.inputValue(),JSON.stringify({equipment_id:'EQ-1',signal:'pressure'}));
  assert.equal(await value.innerText(),'값 확인 불가');
  await sensor.selectOption('');assert.equal(await value.isVisible(),false);
  assert.deepEqual(errors,[]);console.log('PASS: certainty below sensor, adjacent live value, selection persistence, quality and disconnect handling at 1280/768/375px');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
