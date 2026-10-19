const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require('playwright');
const source=fs.readFileSync('shiftlink/mes/web/pda.js','utf8');
const prefix=source.slice(0,source.indexOf("if (typeof module !== 'undefined')"));
const on=source.match(/^function on\(id, fn\).*$/m)[0];
const filters=source.split('\n').find(line=>line.startsWith("[['homeHandoverPending'"));
const equipment=['GR-01','HPU-01','RT-01','CV-01'].map((code,i)=>({equipment_id:'E'+i,code,type:code.split('-')[0],group:code,signals:[]}));
const records=[
 {outcome:'open',story:'진동 지속',follow_up:'전문 점검 결과와 부품 상태 확인',action:'구동부 점검',observed_result:'진동 지속',worker:'김민수',normal_run_status:'unconfirmed'},
 {outcome:'temporary',story:'압력 저하',follow_up:'압력 복구 후 재발 여부 확인',action:'압력 조정',observed_result:'155 bar 복구',worker:'박지훈',normal_run_status:'observing'},
 {outcome:'resolved',story:'롤러 동작 복구',follow_up:'정상 운전 확인 결과 기록',action:'롤러 점검·조정',observed_result:'동작 복구',worker:'이서연',normal_run_status:'unconfirmed'},
 {outcome:'resolved',story:'구동 상태 확인',follow_up:'',action:'구동부 점검',observed_result:'동작 복구',worker:'최민준',normal_run_status:'no_recurrence',normal_run_minutes:30,normal_run_evidence:'30분 구간 관찰, 재발 없음'}
];
const reports=records.map((r,i)=>({handover_id:'DESIGN-'+i,kind:'work_log',created_at:`2026-10-19T${String(10-i).padStart(2,'0')}:50:00+09:00`,required_context:{start_at:'2026-10-19T08:00',author:r.worker},equipment_ids:['E'+i],work_report:{records:[{...r,type:'고장·정비',equipment:['E'+i],occurred_at:'2026-10-19T08:30',incident_id:'INC-'+i,capture_version:1,restart_performed:false,restart_type:'unknown',causes:[],result:null,pms:null,action_steps:[{action:r.action,observed_result:r.observed_result,worker:r.worker,performed_at:'2026-10-19T10:40',failed:false}]}]}}));
reports.push({...reports[3],handover_id:'EXPIRED',created_at:'2026-10-11T07:50:00+09:00',work_report:{records:[{...reports[3].work_report.records[0],incident_id:'EXPIRED'}]}});
const setup=`Date.now=()=>Date.parse('2026-10-19T12:00:00+09:00');S.operator={id:'preview',name:'화면 검증 · 예시 데이터'};S.equipment=${JSON.stringify(equipment)};S.savedHandovers=${JSON.stringify(reports)};S.handovers=[];show('home');`;
const html=fs.readFileSync('shiftlink/mes/web/pda.html','utf8').replace(/<script\b[\s\S]*?<\/script>/gi,'').replace('</body>',`<script>${(prefix+'\n'+on+'\n'+filters+'\n'+setup).replace(/<\/script/gi,'<\\/script')}</script></body>`);
const output='output/design/pda-home-handover-implemented';fs.mkdirSync(output,{recursive:true});
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});try{
 const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('http://home-preview.test/**',r=>r.fulfill({contentType:'text/html',body:html}));await page.goto('http://home-preview.test/');
 for(const [width,height] of [[1280,800],[1024,768],[768,1024],[390,844]]){
  await page.setViewportSize({width,height});
  assert.equal(await page.locator('#homeHandoverPending').textContent(),'조치 필요 3','category preserved under the new term');
  assert.equal(await page.locator('#homeHandoverComplete').textContent(),'해결완료 1');
  assert.equal(await page.locator('#homeHandoverCount').textContent(),'전체 4건');
  assert.equal(await page.locator('#homeHandover .home-handover-entry').count(),3);
  assert.equal(await page.locator('#homeHandover .home-handover-recorded').first().textContent(),'2026-10-19 10:50');
  assert.match(await page.locator('#homeHandover').innerText(),/미확인/);
  assert.doesNotMatch(await page.locator('#homeHandover .home-handover-normal').allTextContents().then(values=>values.join('\n')),/정상 운전/);
  assert.equal(await page.locator('#homeHandoverColumns,.home-handover-action,.home-handover-meta,.home-handover-label').count(),0,'home contains only identity, primary content and relevant verification');
  const aligned=await page.locator('.home-panel-handover').evaluate(panel=>{
   const row=panel.querySelector('.home-handover-entry');
   const cells=[...row.children];
   const first=cells[0].getBoundingClientRect(),second=cells[1].getBoundingClientRect();
   return cells.length===2 && (second.left>=first.right-1 || second.top>=first.bottom-1);
  });
  assert.ok(aligned,width+' column headers align with their cells or reflow on a narrow panel');
  assert.ok(await page.locator('.home-handover-identity').evaluateAll(elements=>elements.every(el=>{
   const name=el.querySelector('.home-handover-equipment').getBoundingClientRect();
   const status=el.querySelector('.home-handover-status').getBoundingClientRect();
   return status.top>=name.bottom && Math.abs(status.left-name.left)<=1;
  })),width+' status tag is below and left-aligned with the equipment name');
  const headings=await page.locator('#s-home .home-panel>.section-heading').evaluateAll(elements=>elements.map(el=>{
   const style=getComputedStyle(el),box=el.getBoundingClientRect();
   return {border:style.borderBottomWidth,color:style.borderBottomColor,padding:style.paddingBottom,y:box.top,bottom:box.bottom};
  }));
  assert.equal(headings[0].border,'1px','handover heading has a single separator');
  assert.equal(headings[0].border,headings[1].border,'both heading lines have the same thickness');
  assert.equal(headings[0].color,headings[1].color,'both heading lines have the same color');
  assert.equal(headings[0].padding,headings[1].padding,'both headings use the same bottom spacing');
  const quietRows=await page.locator('.home-panel-handover').evaluate(panel=>{
   const selectors=['.home-handover-filters','.home-handover-filters button','#homeHandoverColumns','.home-handover-entry'];
   return selectors.every(selector=>[...panel.querySelectorAll(selector)].every(el=>getComputedStyle(el).borderBottomWidth==='0px'));
  });
  assert.ok(quietRows,'filters, column headings and records use no horizontal rules below the title');
  const rowSurfaces=await page.locator('.home-handover-entry').evaluateAll(rows=>rows.slice(0,2).map(row=>getComputedStyle(row).backgroundColor));
  assert.notEqual(rowSurfaces[0],rowSurfaces[1],'alternating row surfaces distinguish adjacent records');
  if(Math.abs(headings[0].y-headings[1].y)<=1)assert.ok(Math.abs(headings[0].bottom-headings[1].bottom)<=1,'side-by-side separators share a baseline');
  const defects=await page.locator('.home-panel-handover').evaluate(panel=>({
   overflow:panel.scrollWidth>panel.clientWidth+1,
   pageOverflow:document.documentElement.scrollWidth>innerWidth,
   small:[...panel.querySelectorAll('button')].filter(el=>{const b=el.getBoundingClientRect();return b.width<48||b.height<48;}).length,
   clipped:[...panel.querySelectorAll('.home-handover-identity,.home-handover-body,.home-handover-verification,.home-handover-meta')].filter(el=>{const b=el.getBoundingClientRect(),p=el.closest('.home-handover-entry').getBoundingClientRect();return b.x<p.x-1||b.right>p.right+1;}).length
  }));
  assert.deepEqual(defects,{overflow:false,pageOverflow:false,small:0,clipped:0},width+' responsive layout');
  await page.mouse.move(5,5);
  await page.screenshot({path:`${output}/home-${width}.png`});
  await page.locator('#homeHandoverComplete').click();
  assert.equal(await page.locator('#homeHandover .home-handover-entry').count(),1);
  assert.match(await page.locator('#homeHandover').innerText(),/30분/);
  assert.equal(await page.locator('#homeHandover .home-handover-recorded').textContent(),'2026-10-19 07:50','completed items also show the record save time');
  assert.equal(await page.locator('#homeHandover .home-handover-normal').count(),0,'completed observation evidence appears only as primary content');
  assert.equal((await page.locator('#homeHandover').innerText()).match(/30분/g).length,1,'observation duration is not repeated');
  await page.locator('#homeHandoverPending').click();
 }
 await page.evaluate(()=>{Date.now=()=>Date.parse('2026-10-26T07:50:00+09:00');renderHome();});
 assert.equal(await page.locator('#homeHandover .home-handover-entry').count(),3,'pending records remain');
 assert.equal(await page.locator('#homeHandoverComplete').textContent(),'해결완료 0','completed records expire after seven days');
 await page.locator('#homeHandoverComplete').click();
 assert.match(await page.locator('#homeHandover').innerText(),/최근 7일/);
 await page.locator('#homeHandoverPending').click();
 assert.equal(await page.evaluate(()=>S.savedHandovers.length),5,'original work logs are retained');
 await page.evaluate(()=>{Date.now=()=>Date.parse('2026-10-19T12:00:00+09:00');renderHome();});
 await page.setViewportSize({width:1280,height:600});
 await page.evaluate(()=>{const list=document.getElementById('homeHandover');list.scrollTop=40;renderHome();});
 assert.equal(await page.locator('#homeHandover').evaluate(el=>el.scrollTop),40,'refresh preserves reading position');
 await page.evaluate(()=>document.getElementById('homeHandover').scrollTop=0);
 await page.setViewportSize({width:1280,height:800});
 await page.mouse.move(5,5);
 await page.screenshot({path:`${output}/home-1280.png`});
 // Full detail still opens the original record rather than a rewritten summary.
 await page.locator('#homeHandover .home-handover-entry').first().click();
 assert.ok(await page.locator('#s-dutyDetail.on').isVisible());
 assert.match(await page.locator('#dutyPane').innerText(),/진동 지속/);
 await page.evaluate(()=>{S.savedHandovers=[];S.handovers=[];renderHome();show('home');});
 assert.equal(await page.locator('#homeHandover').textContent(),'등록된 인계 사항이 없습니다.');

 assert.deepEqual(errors,[],'no browser errors');
 console.log('PASS: renamed category and tabs preserved, seven-day completed visibility, 1280/1024/768/390px layout, 48px buttons, source detail and empty state');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
