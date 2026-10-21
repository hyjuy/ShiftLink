const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('shiftlink/mes/web/pda.js','utf8');
const context=vm.createContext({module:{exports:{}}});
vm.runInContext(source,context);
const fields=new Map();const handlers={};const closeListeners=[];
const dialog={open:false,returnValue:'cancel',showModal(){this.open=true;},
  addEventListener(name,fn){if(name==='close')closeListeners.push(fn);},
  close(value='cancel'){this.open=false;this.returnValue=value;closeListeners.splice(0).forEach(fn=>fn());}};
fields.set('reportDeleteConfirm',dialog);
fields.set('reportRecords',{addEventListener:(name,fn)=>handlers[name]=fn});
context.document={getElementById:id=>{if(!fields.has(id))fields.set(id,{value:'',textContent:''});return fields.get(id);}};
vm.runInContext(`renderReportRecords=()=>{};var saved=[];saveReportDraft=()=>{saved=JSON.parse(JSON.stringify(S.reportRecords));};
 S.reportRecords=[{story:'first',causes:[]},{story:'second',causes:[]}];`,context);
vm.runInContext(source.slice(source.indexOf("$('reportRecords').addEventListener('click'"),source.indexOf("$('reportAuthor').addEventListener('input'")),context);
const click=(action,record=0,cause=0)=>handlers.click({target:{closest:selector=>selector==='button[data-action]'?{dataset:{action,record:String(record),cause:String(cause)}}:null}});
(async()=>{
 let pending=click('remove');assert.equal(dialog.open,true);
 dialog.close('cancel');await pending;assert.equal(vm.runInContext('S.reportRecords.length',context),2);
 pending=click('remove');dialog.close('delete');await pending;
 assert.equal(vm.runInContext('S.reportRecords[0].story',context),'second');
 assert.equal(vm.runInContext('saved.length',context),1,'confirmed deletion updates the stored draft');
 vm.runInContext('S.reportRecords[0].causes=[{note:"",sensor_ref:{signal:"pressure"}}];',context);
 pending=click('remove-cause');assert.equal(dialog.open,true,'sensor-only evidence also needs confirmation');
 dialog.close('cancel');await pending;assert.equal(vm.runInContext('S.reportRecords[0].causes.length',context),1);
 pending=click('remove-cause');dialog.close('delete');await pending;
 assert.equal(vm.runInContext('S.reportRecords[0].causes.length',context),0);
 pending=click('remove');dialog.close('delete');await pending;
 assert.equal(vm.runInContext('saved.length',context),0,'last record deletion persists an empty list');
 console.log('PASS: in-app deletion confirms/cancels and persists record and sensor-only cause removal');
})().catch(error=>{console.error(error);process.exitCode=1;});
