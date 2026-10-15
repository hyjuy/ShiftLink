const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const pda = require('../shiftlink/mes/web/pda.js');
const equipment = ['HPU-01','HPU-02','GR-01','GR-02'].map((code,i)=>({equipment_id:'EQ-'+i,code,type:code.split('-')[0],group:code,signals:[]}));
const draft={ids:['EQ-0','EQ-2'],author:'정비 담당',memo:'HPU-01 점검, GR-01 정비',start:'2026-10-15T09:00',end:'2026-10-15T18:00',context:'기록'};
assert.deepEqual(pda.selectedReportPayload(draft,equipment).equipment_ids,['EQ-0','EQ-2']);
assert.equal(pda.selectedReportPayload(draft,equipment).equipment_id,null);
assert.throws(()=>pda.selectedReportPayload({...draft,ids:[]},equipment),/대상/);
assert.throws(()=>pda.selectedReportPayload({...draft,end:'2026-10-15T08:00'},equipment),/시간/);
assert.throws(()=>pda.selectedReportPayload({...draft,author:''},equipment),/작성자/);
assert.deepEqual(pda.reportTargets(equipment,'fault',[{eq:equipment[2]}],[]),[equipment[2]]);
assert.deepEqual(pda.handoverEquipment({memo_text:'HPU-010 무관 GR-01 재확인'},equipment),[equipment[2]]);
assert.equal(pda.dutyTimeline({open_items:[{text:'GR-01 재확인'},{text:'HPU-01 점검'}]},equipment[2]).length,1);
assert.deepEqual(pda.equipmentGroups(equipment).map(g=>g.equipment.length),[2,2]);

// DOM 경계만 대체하고 실제 선택·초안·저장 함수를 실행한다.
function element(tag='div') {
 return {tag,children:[],value:'',textContent:'',checked:false,disabled:false,indeterminate:false,hidden:false,
  classList:{toggle(){}},setAttribute(){},appendChild(child){this.children.push(child);return child;},
  append(...children){this.children.push(...children);},replaceChildren(...children){this.children=children;}};
}
const nodes=new Map();const store=new Map();const posted=[];let stored=[];let loseAck=true;
const context=vm.createContext({console,Date,URLSearchParams,Set,Map,JSON,Promise,crypto:require('node:crypto').webcrypto,
 document:{getElementById(id){if(!nodes.has(id))nodes.set(id,element());return nodes.get(id);},createElement:element},
 localStorage:{getItem:key=>store.get(key)||null,setItem:(key,value)=>store.set(key,value),removeItem:key=>store.delete(key)},
 fetch:async(path,init)=>{
  if(path==='/api/outbox/pending')return {ok:true,json:async()=>({handovers:stored})};
  assert.equal(path,'/api/work-reports');const payload=JSON.parse(init.body);posted.push(payload);
  if(loseAck){loseAck=false;throw new Error('lost acknowledgement');}
  stored=[{...payload,created_at:'2026-10-15T18:01:00+09:00'}];return {ok:true,json:async()=>({handover_id:payload.handover_id})};
 }});
vm.runInContext(fs.readFileSync(require.resolve('../shiftlink/mes/web/pda.js'),'utf8').split('// Node 테스트는 DOM 없이')[0],context);
vm.runInContext(`show=(screen)=>{S.screen=screen;};renderHome=()=>{};api=(path,init)=>fetch(path,init);getJson=async(path)=>(await fetch(path)).json();`,context);
context.equipment=equipment;context.draft=draft;
(async()=>{
 vm.runInContext('S.equipment=equipment;S.eq=equipment[1];openEquipmentReport();',context);
 assert.equal(nodes.get('reportCount').textContent,'선택 1대');
 assert.equal(JSON.parse(store.get('shiftlink.report.draft')).ids[0],'EQ-1');
 store.set('shiftlink.report.draft',JSON.stringify(draft));
 vm.runInContext('openEquipmentReport()',context);
 assert.deepEqual(JSON.parse(store.get('shiftlink.report.draft')).ids,draft.ids,'equipment report entry preserves an existing draft');
 vm.runInContext('S.reportDraftLoaded=false',context);
 store.set('shiftlink.report.draft',JSON.stringify(draft));
 vm.runInContext('saveReportDraft()',context);
 assert.equal(JSON.parse(store.get('shiftlink.report.draft')).memo,draft.memo,'unopened draft must not be overwritten on logout');
 vm.runInContext(`S.equipment=equipment;S.reportDraftLoaded=true;S.reportSelected=['EQ-0','EQ-2','EQ-3'];S.reportFilter='all';renderReportSelection();`,context);
 assert.equal(nodes.get('reportCount').textContent,'선택 3대');
 assert.equal(nodes.get('reportSelectAll').indeterminate,true);
 const rows=nodes.get('reportEquipment').children;
 const hpu2=rows[1].children[0].children[0].children[0];hpu2.checked=true;hpu2.onchange();
 assert.equal(nodes.get('reportCount').textContent,'선택 4대');assert.equal(nodes.get('reportSelectAll').checked,true);
 vm.runInContext(`S.reportFilter='recent';S.recent=['GR-01'];renderReportSelection();`,context);
 assert.equal(nodes.get('reportEquipment').children.length,1);assert.equal(nodes.get('reportCount').textContent,'선택 4대');
 const gr1=nodes.get('reportEquipment').children[0].children[0].children[0].children[0];gr1.checked=false;gr1.onchange();
 assert.equal(nodes.get('reportCount').textContent,'선택 3대');assert.equal(nodes.get('reportSelectAll').checked,false);
 vm.runInContext(`$('reportMemo').value=draft.memo;$('reportAuthor').value=draft.author;$('reportStart').value=draft.start;$('reportEnd').value=draft.end;S.reportContext='MES 첨부';saveReportDraft();`,context);
 assert.equal(JSON.parse(store.get('shiftlink.report.draft')).ids.length,3);
 await vm.runInContext('saveReport()',context);
 assert.match(nodes.get('reportStatus').textContent,/저장 확인 실패/);assert.equal(posted.length,1);assert.ok(store.has('shiftlink.handover.pending'));
 vm.runInContext(`S.reportSelected=[];$('reportMemo').value='';openReport();openReportWrite();`,context);
 assert.equal(nodes.get('reportMemo').value,draft.memo);assert.equal(nodes.get('reportCount').textContent,'선택 3대');
 await vm.runInContext('saveReport()',context);
 assert.equal(posted.length,2);assert.deepEqual(posted[1],posted[0]);assert.deepEqual(stored[0].equipment_ids,['EQ-0','EQ-1','EQ-3']);
 assert.equal(store.has('shiftlink.handover.pending'),false);assert.equal(store.has('shiftlink.report.draft'),false);
 assert.equal(vm.runInContext('S.screen',context),'home');
 assert.equal(vm.runInContext('allHandovers()[0].required_context.author',context),draft.author);
 console.log('PDA v2: equipment groups, exact equipment history, selection/filter, draft, multi-target payload, lost-ack retry and saved list PASS');
})().catch(error=>{console.error(error);process.exitCode=1;});
