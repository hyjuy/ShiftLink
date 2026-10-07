const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const timers = [];
const errors = {innerHTML:'', appendChild() { this.count = (this.count || 0) + 1; }};
const context = vm.createContext({URLSearchParams, window:{location:{search:''}},
  setTimeout:(fn, ms) => timers.push({fn, ms})});
vm.runInContext(fs.readFileSync(require.resolve('../shiftlink/mes/web/pda.js'), 'utf8'), context);
context.document = {getElementById:id => id === 'bootErr' ? errors : {},
  createElement:() => ({querySelector:() => ({})})};
vm.runInContext(`getJson = async () => { throw new Error('offline'); };`, context);
(async () => {
  await vm.runInContext('boot()', context);
  assert.equal(timers.length, 1, 'offline boot must schedule a retry');
  assert.equal(timers[0].ms, 3000);
  vm.runInContext(`getJson = async (path) => path === '/api/config'
    ? {config:{equipment:[{equipment_id:'EQ-0004'}]}}
    : path === '/api/catalog' ? {data:{}} : {cards:[{}]};
    renderManualList = () => {}; show = name => { S.screen = name; };`, context);
  await timers[0].fn();
  assert.equal(vm.runInContext('S.screen', context), 'login');
  assert.equal(vm.runInContext('S.eq', context), null, 'boot must not bypass login');
  assert.equal(vm.runInContext('S.equipment.length', context), 1, 'retry must load MES equipment');
  assert.equal(errors.innerHTML, '');
  console.log('PDA offline boot recovery PASS');
})().catch(err => {console.error(err); process.exitCode = 1;});
