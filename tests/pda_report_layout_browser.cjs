const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const {chromium}=require('playwright');
const source=fs.readFileSync('shiftlink/mes/web/pda.js','utf8');
const prefix=source.slice(0,source.indexOf("if (typeof module !== 'undefined')"));
const setup=`
 S.equipment=[{equipment_id:'EQ-1',code:'HPU-01',group:'유압 유닛',signals:[]}];
 S.reportSelected=['EQ-1'];S.reportDraftLoaded=true;
 S.reportRecords=[{type:'추가 기록',equipment:['EQ-1'],occurred_at:'2026-10-17T09:10',story:'화면 검증용 예시 · 설비 점검 후 다음 근무에서 압력 재확인',causes:[{equipment:['EQ-1'],certainty:'추정',note:'필터 오염 여부 추가 확인'}],result:'다음 근무에서 압력 추이 확인',pms:'기존 초안 계획 ID',candidate:false}];
 $('reportAuthor').value='화면 검증용 작업자';$('reportStart').value='2026-10-17T08:00';$('reportEnd').value='2026-10-17T16:00';
 $('reportWorkDate').value='2026-10-17';$('reportShift').value='A';$('reportTargets').textContent='HPU-01';
 S.reportContext='화면 검증용 예시 · MES 기록은 기존 형식으로 보존됩니다.';
 show('reportWrite');renderReportRecords();
`;
const html=fs.readFileSync('shiftlink/mes/web/pda.html','utf8').replace(/<script[\s\S]*?<\/script>/g,'').replace('</body>',`<script>${(prefix+'\n'+setup).replace(/<\/script/gi,'<\\/script')}</script></body>`);
fs.mkdirSync('artifacts/pda-report-layout',{recursive:true});
fs.writeFileSync('artifacts/pda-report-layout/fixture.html',html);
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const taste=process.env.TASTE_SKILL_DIR?{
   ...await import(pathToFileURL(path.join(process.env.TASTE_SKILL_DIR,'scripts/lib/probe.mjs')).href),
   ...await import(pathToFileURL(path.join(process.env.TASTE_SKILL_DIR,'scripts/lib/rules.mjs')).href)
  }:null;
  const tasteReports=[];
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('http://layout.test/**',r=>r.fulfill({contentType:'text/html',body:html}));await page.goto('http://layout.test/');
  for(const width of [1280,768,375]){
   await page.setViewportSize({width,height:900});await page.locator('.document-head').scrollIntoViewIfNeeded();
   await page.screenshot({path:`artifacts/pda-report-layout/header-${width}.png`,fullPage:true});
   assert.equal(await page.locator('[data-key="pms"],[data-action="pms"],[data-action="remove-pms"]').count(),0,'maintenance plan controls removed');
   assert.doesNotMatch(await page.locator('#reportRecords').innerText(),/정기정비 계획/);
   assert.equal(await page.locator('tr').filter({has:page.locator('[data-key="occurred_at"]')}).locator('th').textContent(),'발생시각');
   const archive=await page.locator('#reportArchiveOpen').boundingBox(),head=await page.locator('.document-head').boundingBox();
   const title=await page.locator('.document-head h2').boundingBox();
   assert.ok(Math.abs(archive.x+archive.width-head.x-head.width)<=1,'archive aligned to top right');
   assert.ok(Math.abs(archive.y-head.y)<=1,'archive aligned to header top');
   assert.ok(Math.abs(title.x+title.width/2-head.x-head.width/2)<=1,'title centered independently of archive');
   assert.ok(archive.x>=title.x+title.width || archive.y+archive.height<=title.y,'title and archive never overlap');
   assert.equal(await page.locator('.report-equipment tr').count(),2,'equipment label and name use two rows');
   assert.equal(await page.locator('.report-equipment th').textContent(),'설비명');
   assert.equal(await page.locator('.report-equipment tr').nth(1).locator('td').getAttribute('id'),'reportTargets');
   const headerCell=await page.locator('.record-head th').boundingBox();
   const equipmentLabel=page.locator('.record>table>tbody>tr>th').filter({hasText:/^설비명$/});
   const equipmentCell=await equipmentLabel.boundingBox();
   assert.ok(headerCell&&Math.abs(headerCell.width-equipmentCell.width)<=1&&Math.abs(headerCell.x-equipmentCell.x)<=1,'record header aligns to body columns');
   assert.equal(await equipmentLabel.textContent(),'설비명');
   const labelStyles=await page.locator('.record>table>tbody>tr>th').evaluateAll(cells=>cells.map(el=>{
    const style=getComputedStyle(el);return {font:style.fontSize,weight:style.fontWeight,align:style.textAlign,vertical:style.verticalAlign};
   }));
   assert.ok(labelStyles.every(s=>s.font===labelStyles[0].font&&s.weight===labelStyles[0].weight&&s.align==='left'&&s.vertical==='middle'),'all row labels use the same left-aligned typography');
   assert.equal(await page.locator('#reportTargets').evaluate(el=>getComputedStyle(el).textAlign),'left','equipment names align left');
   assert.ok((await page.locator('#s-reportWrite .paper>table th').evaluateAll(cells=>cells.map(el=>getComputedStyle(el).textAlign))).every(align=>align==='center'),'column headings remain centered');
   const tableEdges=await page.locator('#s-reportWrite .paper>table,#reportRecords>.record>table').evaluateAll(tables=>tables.map(el=>{const box=el.getBoundingClientRect();return {x:box.x,right:box.right};}));
   assert.ok(tableEdges.every(e=>Math.abs(e.x-tableEdges[0].x)<=1&&Math.abs(e.right-tableEdges[0].right)<=1),'all main report table edges align');
   assert.equal(await page.locator('tr').filter({has:page.locator('[data-key="story"]')}).locator('th').textContent(),'상황·조치');
   const importButton=await page.locator('#reportImport').boundingBox();
   for(const selector of ['#reportArchiveOpen','[data-action="remove"]','[data-action="remove-cause"]','[data-action="remove-result"]','[data-action="cause"]']){
    const box=await page.locator(selector).boundingBox();assert.ok(Math.abs(box.height-importButton.height)<=1,selector+' height matches import');
   }
   const centered=await page.locator('[data-action="remove-cause"]').evaluate(el=>{
    const button=el.getBoundingClientRect(),range=document.createRange();range.selectNodeContents(el);const text=range.getBoundingClientRect();
    return {x:Math.abs(text.x+text.width/2-button.x-button.width/2),y:Math.abs(text.y+text.height/2-button.y-button.height/2)};
   });
   assert.ok(centered.x<=2&&centered.y<=3,JSON.stringify(centered));
   await page.locator('.record-head').scrollIntoViewIfNeeded();
   await page.screenshot({path:`artifacts/pda-report-layout/record-header-${width}.png`,fullPage:true});
   await page.locator('[data-action="remove-cause"]').scrollIntoViewIfNeeded();
   await page.screenshot({path:`artifacts/pda-report-layout/table-${width}.png`,fullPage:true});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),width);
   const field=await page.locator('[data-key="note"]').boundingBox();assert.ok(field.width>=90,'input remains readable on phone');
   if(width===375)assert.ok((await page.locator('#reportWorkDate').boundingBox()).width>=200,'date is readable on phone');
   if(taste){const metrics=await page.evaluate(taste.probe);tasteReports.push({width,findings:taste.judge(metrics,{width})});}
  }
  for(const width of [1280,768,375])for(const type of ['추가 기록','이상증상','고장·정비','PMS 정비']){
   await page.setViewportSize({width,height:900});
   await page.evaluate(type=>{S.reportRecords[0].type=type;S.reportRecords[0].outcome='resolved';renderReportRecords();document.querySelectorAll('.report-review-notes').forEach(el=>el.open=true);},type);
   assert.ok((await page.locator('#reportRecords input[type="number"]').evaluateAll(fields=>fields.map(el=>getComputedStyle(el).textAlign))).every(align=>align==='right'),'numeric inputs align right');
   const defects=await page.locator('#reportRecords').evaluate(root=>{
    const rows=[...root.querySelectorAll('.record>table>tbody>tr')].filter(r=>r.querySelector(':scope>th'));
    const reference=rows[0].firstElementChild.getBoundingClientRect();
    const wrongColumns=rows.filter(r=>{const b=r.firstElementChild.getBoundingClientRect();return Math.abs(b.x-reference.x)>1||Math.abs(b.width-reference.width)>1;}).length;
    const overflowing=[...root.querySelectorAll('input,select,textarea,button')].filter(el=>{
     const cell=el.closest('td');if(!cell||!el.getClientRects().length)return false;
     const b=el.getBoundingClientRect(),c=cell.getBoundingClientRect();return b.x<c.x-1||b.right>c.right+1;
    }).map(el=>el.getAttribute('aria-label') || el.textContent);
    return {wrongColumns,overflowing};
   });
   assert.equal(defects.wrongColumns,0,type+' columns at '+width);
   assert.deepEqual(defects.overflowing,[],type+' controls at '+width);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),width);
   assert.doesNotMatch(await page.locator('#reportRecords').innerText(),/MES 자동 첨부 기록/);
   assert.equal(await page.locator('[data-action="mes"]').count(),0);
  }
  assert.equal(await page.locator('#reportImport').count(),1,'single main MES import button remains');
  if(taste)fs.writeFileSync('artifacts/pda-report-layout/taste-runtime.json',JSON.stringify(tasteReports,null,2));
  assert.deepEqual(errors,[]);console.log('PASS: text left, numbers right, column headings centered; aligned tables and contained controls at 1280/768/375px');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
