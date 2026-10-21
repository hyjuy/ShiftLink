const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const fields=new Map();
const data=new Map([['shiftlink.report.draft','old draft']]);
const context=vm.createContext({module:{exports:{}},setTimeout:()=>1,clearTimeout:()=>{},
  localStorage:{getItem:key=>data.get(key)||null,setItem:(key,value)=>data.set(key,value),removeItem:key=>data.delete(key)}});
vm.runInContext(fs.readFileSync('shiftlink/mes/web/pda.js','utf8'),context);
context.document={getElementById:id=>{
  if(!fields.has(id))fields.set(id,{value:'',textContent:'',hidden:true});
  return fields.get(id);
}};
vm.runInContext(`
  reportDraft=()=>({});selectedReportPayload=()=>({});
  api=async()=>({handover_id:'HO-SAVED',candidates:[]});
  submitHandover=async(note,send)=>send('/api/work-reports',{});
  refreshSavedHandovers=async()=>{};show=screen=>S.screen=screen;
  saveReportDraft=()=>{throw Error('successful save must not restore a cleared draft');};
`,context);
(async()=>{
  await vm.runInContext('saveReport()',context);
  assert.equal(vm.runInContext('S.screen',context),'home');
  assert.match(fields.get('reportStatus').textContent,/MES 로컬 저장 완료/);
  assert.match(fields.get('toast').textContent,/일지 저장 완료/);
  assert.equal(fields.get('toast').hidden,false);
  assert.equal(data.has('shiftlink.report.draft'),false);
  assert.equal(fields.get('reportSave').disabled,false);
  console.log('PASS: committed work log shows success without restoring an empty draft');
})().catch(error=>{console.error(error);process.exitCode=1;});
