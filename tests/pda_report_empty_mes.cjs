const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const data = new Map();
const fields = new Map();
const context = vm.createContext({
  module: {exports: {}},
  localStorage: {
    getItem: key => data.get(key) ?? null,
    setItem: (key, value) => data.set(key, value),
    removeItem: key => data.delete(key),
  },
});
const source = fs.readFileSync(path.join(__dirname, '../shiftlink/mes/web/pda.js'), 'utf8');
vm.runInContext(source, context);
context.document = {getElementById: id => {
  if (!fields.has(id)) fields.set(id, {value: '', textContent: ''});
  return fields.get(id);
}};
vm.runInContext('renderReportSelection=()=>{};show=()=>{};S.equipment=[{equipment_id:"EQ-1"}];S.operator={id:"M001"}', context);

vm.runInContext('S.reportContext="이전 MES 값";S.reportRecords=[{story:"이전 기록"}];S.reportSelected=["EQ-1"];openReport()', context);
assert.equal(vm.runInContext('S.reportContext', context), '');
assert.equal(vm.runInContext('S.reportRecords.length', context), 0);
assert.equal(vm.runInContext('S.reportSelected.length', context), 0);

data.set('shiftlink.report.draft', JSON.stringify({ids:['EQ-1'],context:'보관할 MES 값',records:[]}));
vm.runInContext('openReport()', context);
assert.equal(vm.runInContext('S.reportContext', context), '보관할 MES 값');
assert.equal(vm.runInContext('S.reportSelected[0]', context), 'EQ-1');
vm.runInContext('var realImportReportMes=importReportMes;var autoImports=0;importReportMes=()=>{autoImports++;};renderReportRecords=()=>{};', context);
data.clear();
vm.runInContext('resetReportForm();S.reportInProgress=false;S.reportSelected=["EQ-1"];openReportWrite()', context);
assert.equal(vm.runInContext('autoImports', context), 1, 'fresh report imports MES once');
vm.runInContext('enterReportWrite()', context);
assert.equal(vm.runInContext('autoImports', context), 1, 'restoring or returning to a report keeps captured values');
vm.runInContext('resetReportForm();enterReportWrite(true)', context);
assert.equal(vm.runInContext('autoImports', context), 2, 'explicit new report captures fresh MES');
vm.runInContext('localStorage.setItem(HANDOVER_PENDING_KEY,JSON.stringify({kind:"work_log"}));enterReportWrite(true)', context);
assert.equal(vm.runInContext('autoImports', context), 2, 'pending submission must retain its original payload');
console.log('PASS: new report captures MES once; saved drafts and pending submissions preserve values');

(async()=>{
  vm.runInContext(`
    localStorage.removeItem(HANDOVER_PENDING_KEY);
    importReportMes=realImportReportMes;
    reportMesContext=snapshot=>snapshot.text;
    var requests=[];
    getJson=path=>new Promise((resolve,reject)=>requests.push({path,resolve,reject}));
    resetReportForm();var requestA=importReportMes();
    resetReportForm();var requestB=importReportMes();
    requests[0].reject(new Error('OLD REQUEST FAILED'));requests[1].resolve({events:[]});
  `, context);
  await vm.runInContext('requestA', context);
  assert.equal(fields.get('reportImport').disabled, true, 'old failure cannot enable the new request button');
  assert.doesNotMatch(fields.get('reportStatus').textContent, /OLD REQUEST FAILED/);
  vm.runInContext('requests[2].resolve({text:"fresh MES"});requests[3].resolve({events:[]})', context);
  await vm.runInContext('requestB', context);
  assert.equal(vm.runInContext('S.reportContext', context), 'fresh MES');
  assert.equal(fields.get('reportImport').disabled, false);
  vm.runInContext(`
    var requestC=importReportMes();var requestD=importReportMes();
    requests[6].resolve({text:'newest MES'});requests[7].resolve({events:[]});
  `, context);
  await vm.runInContext('requestD', context);
  vm.runInContext('requests[4].resolve({text:"older MES"});requests[5].resolve({events:[]})', context);
  await vm.runInContext('requestC', context);
  assert.equal(vm.runInContext('S.reportContext', context), 'newest MES', 'late response cannot replace the newest capture');
  assert.equal(JSON.parse(data.get('shiftlink.report.draft')).context, 'newest MES');
  console.log('PASS: previous failures and late responses cannot overwrite the active MES request');
})().catch(error=>{console.error(error);process.exitCode=1;});
