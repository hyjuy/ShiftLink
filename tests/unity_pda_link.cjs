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
context.document = {getElementById: () => ({innerHTML:''})};
vm.runInContext(`
  getJson = async (path) => path === '/api/config' ? {config:{equipment:[{equipment_id:'EQ-0004'}]}}
    : path === '/api/catalog' ? {data:{}} : {cards:[{}]};
  renderManualList = () => {};
  setContext = (eq, source) => { S.eq = eq; S.source = source; };
  show = (screen) => { S.screen = screen; };
`, context);
// enterWork is declared inside the browser wiring block; execute its actual source
// after stubbing the DOM boundaries, without running camera and polling setup.
const source = fs.readFileSync(require.resolve('../shiftlink/mes/web/pda.js'), 'utf8');
vm.runInContext(source.match(/function enterWork\(\) \{[\s\S]*?\n\}/)[0], context);
vm.runInContext('boot().then(() => ({source:S.source, eq:S.eq, linked:S.linkedEquipment.equipment_id, screen:S.screen}))', context)
  .then((state) => {
    assert.equal(state.source, null);
    assert.equal(state.eq, null);
    assert.equal(state.linked, 'EQ-0004');
    assert.equal(state.screen, 'login');
    vm.runInContext('enterWork()', context);
    assert.equal(vm.runInContext('S.source', context), 'unity_link');
    assert.equal(vm.runInContext('S.eq.equipment_id', context), 'EQ-0004');
    assert.equal(vm.runInContext('S.screen', context), 'ctx');
    vm.runInContext('S.linkedEquipment = null; enterWork()', context);
    assert.equal(vm.runInContext('S.screen', context), 'home');
    console.log('Unity link preserved through login and work entry PASS');
  }).catch((error) => { console.error(error); process.exitCode = 1; });
