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
console.log('PASS: no draft clears old MES context; saved draft still restores');
