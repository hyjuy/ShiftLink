const assert = require('node:assert/strict');
const { equipmentFromLink } = require('../shiftlink/mes/web/pda.js');
const equipment = [{equipment_id:'EQ-0004', active:true}, {equipment_id:'EQ-0005', active:true}];
assert.equal(equipmentFromLink('?equipment_id=EQ-0004', equipment), equipment[0]);
assert.equal(equipmentFromLink('?equipment_id=EQ-0005&source=unity', equipment), equipment[1]);
assert.equal(equipmentFromLink('', equipment), null);
assert.equal(equipmentFromLink('?equipment_id=unknown', equipment), null);
assert.equal(equipmentFromLink('?equipment_id=EQ-0004&equipment_id=EQ-0005', equipment), null);
assert.equal(equipmentFromLink('?equipment_id=%3Cscript%3E', equipment), null);
assert.equal(equipmentFromLink('?equipment_id=EQ-0004', []), null);
console.log('Unity -> PDA equipment link PASS');

// Exercise boot with HTTP/UI boundaries stubbed: link entry keeps its own source.
const vm = require('node:vm');
const fs = require('node:fs');
const context = vm.createContext({ URLSearchParams, window: {location: {search: '?equipment_id=EQ-0004'}} });
vm.runInContext(fs.readFileSync(require.resolve('../shiftlink/mes/web/pda.js'), 'utf8'), context);
vm.runInContext(`
  getJson = async (path) => path === '/api/config' ? {config:{equipment:[{equipment_id:'EQ-0004'}]}}
    : path === '/api/catalog' ? {data:{}} : {cards:[{}]};
  renderManualList = () => {};
  setContext = (eq, source) => { S.eq = eq; S.source = source; };
  show = (screen) => { S.screen = screen; };
`, context);
vm.runInContext('boot().then(() => ({source:S.source, id:S.eq.equipment_id, screen:S.screen}))', context)
  .then((state) => {
    assert.equal(state.source, 'unity_link');
    assert.equal(state.id, 'EQ-0004');
    assert.equal(state.screen, 'ctx');
    console.log('Unity link boot source PASS');
  }).catch((error) => { console.error(error); process.exitCode = 1; });
